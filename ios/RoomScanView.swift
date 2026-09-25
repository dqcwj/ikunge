//
//  RoomScanView.swift
//  FengShuiScanner
//
//  扫描页：RoomPlan 取景器 + 罗盘北向校准 + 导出/上传。
//

import SwiftUI
import RoomPlan
import CoreLocation

// MARK: - 扫描阶段状态机

enum ScanPhase: Equatable {
    case idle          // 未开始
    case scanning      // 扫描中
    case processing    // 已点“完成”，等待最终结果
    case finished      // 已导出 JSON
}

// MARK: - 罗盘服务：扫描开始时记录设备真北朝向

/// 用 CLLocationManager 的 heading 信息获取 trueHeading。
/// 说明：trueHeading 需要定位授权（When-In-Use）+ 已启用定位服务；
/// 在飞机模式或磁力计受干扰时可能为 -1，此时回退用 magneticHeading。
final class HeadingService: NSObject, ObservableObject, CLLocationManagerDelegate {

    @Published var lastHeading: CLHeading?
    @Published var authorizationDenied = false

    private let manager = CLLocationManager()

    /// 当前可用的北向角（真北优先，磁北兜底），单位：度，[0, 360)。
    var currentNorthOffsetDeg: Double? {
        guard let h = lastHeading else { return nil }
        let raw = h.trueHeading >= 0 ? h.trueHeading : h.magneticHeading
        guard raw >= 0 else { return nil }
        return NorthUpConverter.normalizeDeg(raw)
    }

    override init() {
        super.init()
        manager.delegate = self
    }

    /// 请求定位权限并开始读取罗盘。
    func begin() {
        let status = manager.authorizationStatus
        switch status {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            authorizationDenied = true
        default:
            break
        }
        // heading 服务不需要定位权限为 .authorized，但 trueHeading 需要。
        if CLLocationManager.headingAvailable() {
            manager.startUpdatingHeading()
        }
    }

    func end() {
        manager.stopUpdatingHeading()
    }

    // MARK: CLLocationManagerDelegate

    func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        lastHeading = newHeading
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .denied || manager.authorizationStatus == .restricted {
            authorizationDenied = true
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        print("定位/罗盘错误：\(error.localizedDescription)")
    }
}

// MARK: - RoomPlan 扫描控制器（session + delegate）

/// 持有 RoomCaptureSession 并实现 RoomCaptureSessionDelegate。
/// delegate 各回调职责：
///   - captureSession(_:didChange:)  会话状态变化（setup/ready/scanning/网格生成/完成）→ 驱动界面文案；
///   - captureSession(_:didUpdate:)  扫描过程中不断吐出“当前最新的参数化房间模型”，
///                                   我们保存最新一份，并统计墙/门/窗数量做实时进度提示。
final class RoomScanController: NSObject, ObservableObject, RoomCaptureSessionDelegate {

    let session = RoomCaptureSession()   // RoomPlan 扫描会话

    @Published var phase: ScanPhase = .idle
    @Published var stateText = "准备就绪"
    @Published var wallCount = 0
    @Published var doorCount = 0
    @Published var windowCount = 0
    @Published var roomCount = 0
    @Published var errorMessage: String?
    @Published var exportedScan: ScanExport?

    /// 扫描开始时快照下来的北向校准角（trueHeading）。
    private var northOffsetAtStart: Double = 0

    /// 开始扫描。northOffsetDeg 为按下“开始”瞬间的罗盘读数。
    func start(northOffsetDeg: Double?) {
        northOffsetAtStart = northOffsetDeg ?? 0
        errorMessage = nil
        exportedScan = nil
        wallCount = 0; doorCount = 0; windowCount = 0; roomCount = 0
        session.delegate = self

        let configuration = RoomCaptureSession.Configuration()
        configuration.isCoachingEnabled = false   // 我们自己显示中文提示，关闭系统英文教练层
        phase = .scanning
        stateText = "请缓慢移动手机，绕房间一圈"
        session.run(configuration: configuration)
    }

    /// 用户点击“完成扫描”：先 stop，会话停止后用最后一份 CapturedRoom 导出。
    func finish() {
        guard phase == .scanning else { return }
        phase = .processing
        stateText = "正在生成最终模型…"
        session.stop()
        // stop() 之后 RoomPlan 还会回调若干次 didUpdate 收尾；
        // 1.2 秒后统一导出，保证拿到最完整的模型。
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self] in
            self?.exportLatest()
        }
    }

    /// 把最后一份 CapturedRoom 转成自定义 JSON 并进入 finished。
    private func exportLatest() {
        // 若用户已重新开始扫描（phase 不再是 processing），本次结果作废
        guard phase == .processing else { return }
        // didUpdate 保存的最新结果即最终参数化模型
        if let room = latestCapturedRoom {
            exportedScan = ScanExporter.export(from: room, northOffsetDeg: northOffsetAtStart)
            phase = .finished
            stateText = "扫描完成"
        } else {
            phase = .idle
            errorMessage = "未捕获到任何房间数据，请重新扫描"
            stateText = "扫描失败，请重试"
        }
    }

    /// didUpdate 回调里保存的最新扫描结果（数据量较大，不必作为 @Published
    /// 让 SwiftUI 每帧 diff，界面只展示统计数字，导出时从这里取）。
    private var latestCapturedRoom: CapturedRoom?

    // MARK: RoomCaptureSessionDelegate

    /// 状态变化：用于界面提示与进度判断。
    func captureSession(_ session: RoomCaptureSession,
                        didChange state: RoomCaptureSession.SessionState) {
        switch state {
        case .setup:
            stateText = "初始化中…"
        case .ready:
            stateText = "就绪，请开始移动"
        case .scanning:
            if phase != .processing { stateText = "扫描中：请缓慢绕行，覆盖墙面/门/窗" }
        default:
            // 其它状态（网格生成、完成等）：等待 stop 后的导出
            if phase == .scanning { stateText = "正在处理点云…" }
        }
    }

    /// 模型更新：扫描期间会持续触发。保存最新模型并刷新统计。
    func captureSession(_ session: RoomCaptureSession,
                        didUpdate capturedRoom: CapturedRoom) {
        latestCapturedRoom = capturedRoom
        let model = capturedRoom.model
        wallCount = model.walls.count
        doorCount = model.doors.count
        windowCount = model.windows.count
        roomCount = model.rooms.count
        if phase == .scanning {
            stateText = "扫描中：墙 \(wallCount) · 门 \(doorCount) · 窗 \(windowCount)"
        }
    }

    /// 会话出错（相机被占用、设备不支持等）。
    func captureSession(_ session: RoomCaptureSession, didFailWith error: Error) {
        errorMessage = "扫描出错：\(error.localizedDescription)"
        phase = .idle
        stateText = "出错，请重试"
    }
}

// MARK: - RoomCaptureView 的 SwiftUI 包装

/// 把 RoomPlan 的 RoomCaptureView（UIView）包进 SwiftUI。
/// 视图本身由框架渲染实时取景 + 已识别墙面高亮，我们只叠加自己的中文提示层。
struct RoomCaptureViewContainer: UIViewRepresentable {
    let controller: RoomScanController

    func makeUIView(context: Context) -> RoomCaptureView {
        let view = RoomCaptureView(frame: .zero)
        view.captureSession = controller.session     // 把会话接到取景器
        return view
    }

    func updateUIView(_ uiView: RoomCaptureView, context: Context) {
        // 会话生命周期由 controller 管理，这里无需更新
    }
}

// MARK: - 扫描页

struct RoomScanView: View {
    @StateObject private var controller = RoomScanController()
    @StateObject private var heading = HeadingService()

    /// 后端地址（与设置页共用 UserDefaults key）。
    @AppStorage(SettingsKeys.backendURL) private var backendURL: String = ""

    @State private var showResult = false
    @State private var showJSON = false
    @State private var uploadMessage: String?
    @State private var isUploading = false
    @State private var localFileURL: URL?

    var body: some View {
        ZStack {
            // RoomPlan 实时取景
            RoomCaptureViewContainer(controller: controller)
                .ignoresSafeArea()

            VStack {
                topStatusBanner
                Spacer()
                bottomControls
            }
        }
        .alert("上传结果", isPresented: .init(get: { uploadMessage != nil },
                                           set: { if !$0 { uploadMessage = nil } })) {
            Button("好", role: .cancel) {}
        } message: {
            Text(uploadMessage ?? "")
        }
        .alert("扫描出错", isPresented: .init(get: { controller.errorMessage != nil },
                                           set: { if !$0 { controller.errorMessage = nil } })) {
            Button("好", role: .cancel) {}
        } message: {
            Text(controller.errorMessage ?? "")
        }
        .sheet(isPresented: $showJSON) {
            jsonPreviewSheet
        }
    }

    // MARK: 顶部状态条（实时朝向 + 进度）

    private var topStatusBanner: some View {
        VStack(spacing: 6) {
            HStack(spacing: 12) {
                Image(systemName: "location.north.circle.fill")
                    .foregroundStyle(.tint)
                if let deg = heading.currentNorthOffsetDeg {
                    Text(String(format: "真北 %.0f°", deg))
                        .font(.footnote.monospacedDigit())
                } else if heading.authorizationDenied {
                    Text("定位权限被拒绝，无法校准北向")
                        .font(.footnote)
                        .foregroundStyle(.orange)
                } else {
                    Text("罗盘校准中…")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(controller.stateText)
                    .font(.footnote)
                    .lineLimit(2)
                    .multilineTextAlignment(.trailing)
            }
            .padding(10)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal)
    }

    // MARK: 底部控制区（按阶段切换）

    @ViewBuilder
    private var bottomControls: some View {
        switch controller.phase {
        case .idle:
            startCard
        case .scanning:
            VStack(spacing: 12) {
                statsRow
                Button {
                    controller.finish()
                } label: {
                    Label("完成扫描", systemImage: "checkmark.circle.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
                Text("提示：墙/门/窗识别框稳定后即可完成；离门窗近一点效果更好")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding()
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
            .padding(.horizontal)

        case .processing:
            VStack(spacing: 10) {
                ProgressView()
                Text("正在把扫描结果转换为北向上平面图…")
                    .font(.footnote)
            }
            .padding()
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
            .padding()

        case .finished:
            resultCard
        }
    }

    /// 开始前的说明卡片。
    private var startCard: some View {
        VStack(spacing: 14) {
            Image(systemName: "viewfinder")
                .font(.system(size: 40))
                .foregroundStyle(.tint)
            Text("风水扫房")
                .font(.title2.bold())
            VStack(alignment: .leading, spacing: 8) {
                bullet("开始时会记录设备罗盘朝向作为北向校准角，请保持手机水平、远离金属")
                bullet("缓慢平稳地绕房间行走，依次扫过墙面、门、窗")
                bullet("需要 iPhone Pro 系列（带 LiDAR）真机")
            }
            Button {
                startScan()
            } label: {
                if isPreparing {
                    HStack(spacing: 8) {
                        ProgressView()
                        Text("正在校准罗盘…")
                    }
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                } else {
                    Label("开始扫描", systemImage: "play.circle.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(isPreparing)
        }
        .padding(20)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
    }

    /// 扫描中的实时统计。
    private var statsRow: some View {
        HStack(spacing: 16) {
            stat("房间", controller.roomCount)
            stat("墙", controller.wallCount)
            stat("门", controller.doorCount)
            stat("窗", controller.windowCount)
        }
    }

    private func stat(_ title: String, _ value: Int) -> some View {
        VStack(spacing: 2) {
            Text("\(value)").font(.title3.bold().monospacedDigit())
            Text(title).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    /// 完成后的结果卡片：汇总 + 上传/导出/重扫。
    private var resultCard: some View {
        VStack(spacing: 14) {
            HStack {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundStyle(.green)
                Text("扫描完成").font(.headline)
                Spacer()
                Button("重新扫描") {
                    controller.phase = .idle
                    controller.exportedScan = nil
                }
                .font(.subheadline)
            }

            if let scan = controller.exportedScan {
                let totalArea = scan.rooms.reduce(0) { $0 + $1.areaM2 }
                let totalWalls = scan.rooms.reduce(0) { $0 + $1.walls.count }
                let totalDoors = scan.rooms.reduce(0) { $0 + $1.doors.count }
                let totalWindows = scan.rooms.reduce(0) { $0 + $1.windows.count }

                VStack(spacing: 6) {
                    LabeledContent("总面积", value: String(format: "%.1f m²", totalArea))
                    LabeledContent("北向校准角", value: String(format: "%.1f°", scan.northOffsetDeg))
                    LabeledContent("结构", value: "墙 \(totalWalls) · 门 \(totalDoors) · 窗 \(totalWindows)")
                }
                .font(.subheadline)

                HStack(spacing: 10) {
                    Button {
                        Task { await upload(scan) }
                    } label: {
                        if isUploading {
                            ProgressView().frame(maxWidth: .infinity)
                        } else {
                            Label("上传后端", systemImage: "paperplane.fill")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isUploading || backendURL.isEmpty)

                    ShareLink(item: jsonText(scan)) {
                        Label("导出 JSON", systemImage: "square.and.arrow.up")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }

                Button("查看 JSON 预览") { showJSON = true }
                    .font(.footnote)

                if backendURL.isEmpty {
                    Text("尚未配置后端地址：请到“设置”页填写后再上传，或直接导出 JSON")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }
        }
        .padding(20)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
        .padding(.bottom, 8)
    }

    /// JSON 预览面板。
    private var jsonPreviewSheet: some View {
        NavigationStack {
            ScrollView {
                Text(controller.exportedScan.flatMap { try? String(data: $0.jsonData(pretty: true), encoding: .utf8) } ?? "（无数据）")
                    .font(.system(size: 12, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .textSelection(.enabled)
            }
            .navigationTitle("JSON 预览")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { showJSON = false }
                }
            }
        }
    }

    // MARK: 交互动作

    @State private var isPreparing = false

    private func startScan() {
        guard !isPreparing else { return }
        isPreparing = true
        // 1. 先启动罗盘，最多等 2 秒拿第一个读数（trueHeading 首次更新通常 < 1s）
        heading.begin()
        Task { @MainActor in
            var north = heading.currentNorthOffsetDeg
            var tries = 0
            while north == nil && tries < 8 {
                try? await Task.sleep(nanoseconds: 250_000_000)
                north = heading.currentNorthOffsetDeg
                tries += 1
            }
            // 2. 拿到读数（或超时兜底 nil）后，快照下来并开始 RoomPlan 会话
            controller.start(northOffsetDeg: north)
            isPreparing = false
        }
    }

    private func jsonText(_ scan: ScanExport) -> String {
        (try? String(data: scan.jsonData(pretty: true), encoding: .utf8)) ?? "{}"
    }

    private func upload(_ scan: ScanExport) async {
        isUploading = true
        defer { isUploading = false }
        do {
            // 顺便存一份本地副本，便于排查
            localFileURL = try? NetworkService.saveLocally(scan)
            let code = try await NetworkService.shared.upload(scan: scan, to: backendURL)
            uploadMessage = "上传成功（HTTP \(code)）。\n\(localFileURL.map { "本地副本：\($0.lastPathComponent)" } ?? "")"
        } catch {
            uploadMessage = "上传失败：\(error.localizedDescription)"
        }
    }
}

#Preview {
    RoomScanView()
}
