//
//  SettingsView.swift
//  FengShuiScanner
//
//  设置页：后端 URL 配置 + 扫描/罗盘操作提示。
//

import SwiftUI

/// 全局设置键（@AppStorage 底层是 UserDefaults，卸载重装会清空）。
enum SettingsKeys {
    static let backendURL = "backend_url"
}

struct SettingsView: View {

    /// 后端上传地址，持久化在 UserDefaults。
    @AppStorage(SettingsKeys.backendURL) private var backendURL: String = ""

    /// URL 合法性即时校验结果。
    private var urlIsValid: Bool {
        !backendURL.isEmpty && NetworkService.normalizeBackendURL(backendURL) != nil
    }

    var body: some View {
        NavigationStack {
            Form {
                // MARK: 后端配置
                Section {
                    TextField("https://api.example.com/fengshui/scan", text: $backendURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    if !backendURL.isEmpty && !urlIsValid {
                        Label("URL 格式不正确，需以 http:// 或 https:// 开头", systemImage: "exclamationmark.triangle.fill")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    } else if urlIsValid {
                        Label("URL 有效，扫描完成后可在此上传", systemImage: "checkmark.circle.fill")
                            .font(.footnote)
                            .foregroundStyle(.green)
                    }
                } header: {
                    Text("后端上传地址")
                } footer: {
                    Text("扫描结果会以 POST application/json 提交到该地址，JSON 结构见 README。留空则不上传，仅本地保存。")
                }

                // MARK: 扫描提示
                Section("扫描操作要点") {
                    tipRow("1", "站在房间中央点击“开始扫描”，先原地缓慢转一圈让 LiDAR 建立空间基准。")
                    tipRow("2", "手持手机平稳、缓慢地绕房间行走，逐一扫过四面墙、门、窗；高度保持在 1.2–1.5 米。")
                    tipRow("3", "靠近门、窗、开放区域时放慢速度，提高识别准确度；避免强反光地面（镜面、高光大理石）。")
                    tipRow("4", "墙、门、窗识别框变绿（高置信度）即覆盖完成；进度提示不再变化时可点击“完成扫描”。")
                }

                // MARK: 罗盘校准建议
                Section("北向校准（罗盘）说明") {
                    tipRow("A", "开始扫描的瞬间，App 会读取一次设备罗盘 trueHeading 作为北向校准角，请让手机保持水平、远离金属与电器。")
                    tipRow("B", "室内钢筋、家电会干扰磁力计，误差常见 ±10°–30°。建议先到窗边或室外空旷处画 8 字校准罗盘，再回到室内立刻开始扫描。")
                    tipRow("C", "精度要求高时，可连续扫描两次对比 north_offset_deg，取均值；或用外部罗盘手动校核后修正后端数据。")
                }

                Section("关于") {
                    LabeledContent("版本", value: "1.0 (M3)")
                    LabeledContent("适用机型", value: iPhone 12 Pro 及以上（需 LiDAR）")
                    LabeledContent("系统要求", value: iOS 16.0+")
                }
            }
            .navigationTitle("设置")
        }
    }

    /// 带序号的提示行。
    private func tipRow(_ badge: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(badge)
                .font(.caption.bold())
                .frame(width: 22, height: 22)
                .background(Circle().fill(.tint.opacity(0.15)))
                .foregroundStyle(.tint)
            Text(text).font(.subheadline)
        }
        .padding(.vertical, 2)
    }
}

#Preview {
    SettingsView()
}
