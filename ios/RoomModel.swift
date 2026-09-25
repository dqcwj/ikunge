//
//  RoomModel.swift
//  FengShuiScanner
//
//  数据模型与序列化：把 RoomPlan 的 CapturedRoom 转成后端约定的 JSON。
//

import Foundation
import RoomPlan
import simd

// MARK: - 北向上坐标转换（纯数学，便于单元测试）

/// RoomPlan（底层 ARKit，gravity 对齐）世界坐标系约定：
///   - +Y 向上（重力反向），地面为 XZ 水平面，单位：米。
///   - 扫描开始的瞬间，设备后置摄像头大致朝向世界 -Z 方向，摄像头右侧为 +X。
/// 我们在扫描开始时用 CLLocationManager 的 trueHeading 记录设备实际朝向
/// （相对真北、顺时针角度，记为 h），据此把世界 XZ 坐标旋转到「北向上」坐标系：
///   - 输出 x 轴 = 东，输出 y 轴 = 北（北在屏幕/图纸上方）。
/// 推导：朝向 h 时，世界 -Z 对应罗盘方向 (sin h, cos h)，世界 +X 对应 (cos h, -sin h)，
/// 展开即得下方公式（已在单元测试中用 h=0° / h=90° 验证）。
public enum NorthUpConverter {

    /// 把 RoomPlan 世界水平面坐标 (x, z) 转到北向上坐标 (east, north)，单位米。
    public static func toNorthUp(x: Double, z: Double, northOffsetDeg: Double) -> (east: Double, north: Double) {
        let h = northOffsetDeg * .pi / 180
        let east  =  x * cos(h) - z * sin(h)
        let north = -x * sin(h) - z * cos(h)
        return (east, north)
    }

    /// 计算北向上向量的罗盘方位角（0°=北，90°=东，顺时针，范围 [0,360)）。
    /// 后端形煞的「朝向判定」可直接使用该角度。
    public static func bearingDeg(east: Double, north: Double) -> Double {
        let a = atan2(east, north) * 180 / .pi
        return a < 0 ? a + 360 : a
    }

    /// 把角度规整到 [0, 360)。
    public static func normalizeDeg(_ deg: Double) -> Double {
        var d = deg.truncatingRemainder(dividingBy: 360)
        if d < 0 { d += 360 }
        return d
    }
}

// MARK: - 导出 JSON 的数据结构（与后端字段一一对应）

/// 顶层结构：{"captured_at": "...", "north_offset_deg": 0.0, "rooms": [...]}
public struct ScanExport: Codable, Equatable {
    public var capturedAt: String        // ISO8601 时间，如 2026-09-25T08:30:00Z
    public var northOffsetDeg: Double    // 北向校准角：扫描开始时的 trueHeading
    public var rooms: [RoomExport]

    enum CodingKeys: String, CodingKey {
        case capturedAt = "captured_at"
        case northOffsetDeg = "north_offset_deg"
        case rooms
    }

    public init(capturedAt: String, northOffsetDeg: Double, rooms: [RoomExport]) {
        self.capturedAt = capturedAt
        self.northOffsetDeg = northOffsetDeg
        self.rooms = rooms
    }

    /// 编码为 UTF-8 JSON 数据。
    public func jsonData(pretty: Bool = false) throws -> Data {
        let encoder = JSONEncoder()
        if pretty { encoder.outputFormatting = [.prettyPrinted, .sortedKeys] }
        return try encoder.encode(self)
    }
}

/// 单个房间：{"area_m2": 0, "walls": [...], "doors": [...], "windows": [...], "openings": [...]}
public struct RoomExport: Codable, Equatable {
    public var areaM2: Double
    public var walls: [WallExport]
    public var doors: [DoorExport]
    public var windows: [WindowExport]
    public var openings: [OpeningExport]

    enum CodingKeys: String, CodingKey {
        case areaM2 = "area_m2"
        case walls, doors, windows, openings
    }

    public init(areaM2: Double,
                walls: [WallExport],
                doors: [DoorExport],
                windows: [WindowExport],
                openings: [OpeningExport]) {
        self.areaM2 = areaM2
        self.walls = walls
        self.doors = doors
        self.windows = windows
        self.openings = openings
    }
}

/// 墙：{"start": [x,y], "end": [x,y], "length_m": 0, "height_m": 0}
/// start/end 为北向上二维坐标（米）；length_m 为水平投影长度；height_m 为墙高。
public struct WallExport: Codable, Equatable {
    public var start: [Double]
    public var end: [Double]
    public var lengthM: Double
    public var heightM: Double

    enum CodingKeys: String, CodingKey {
        case start, end
        case lengthM = "length_m"
        case heightM = "height_m"
    }

    public init(start: [Double], end: [Double], lengthM: Double, heightM: Double) {
        self.start = start
        self.end = end
        self.lengthM = lengthM
        self.heightM = heightM
    }

    /// 该墙外法线的罗盘方位角（用于八宅坐向 / 形煞判定），北向上坐标系。
    public var facingDeg: Double {
        let dx = end[0] - start[0], dy = end[1] - start[1]
        // 墙向量右侧法线（顺时针旋转 90°）作为外朝向
        return NorthUpConverter.bearingDeg(east: dy, north: -dx)
    }
}

/// 门：{"position": [x,y], "width_m": 0}
public struct DoorExport: Codable, Equatable {
    public var position: [Double]
    public var widthM: Double

    enum CodingKeys: String, CodingKey {
        case position
        case widthM = "width_m"
    }

    public init(position: [Double], widthM: Double) {
        self.position = position
        self.widthM = widthM
    }
}

/// 窗：{"position": [x,y], "width_m": 0, "height_m": 0}
/// height_m 为窗洞自身高度（不是离地高度）。
public struct WindowExport: Codable, Equatable {
    public var position: [Double]
    public var widthM: Double
    public var heightM: Double

    enum CodingKeys: String, CodingKey {
        case position
        case widthM = "width_m"
        case heightM = "height_m"
    }

    public init(position: [Double], widthM: Double, heightM: Double) {
        self.position = position
        self.widthM = widthM
        self.heightM = heightM
    }
}

/// 开口（既非门也非窗的洞口，如走廊连接处）。
public struct OpeningExport: Codable, Equatable {
    public var position: [Double]
    public var widthM: Double
    public var heightM: Double

    enum CodingKeys: String, CodingKey {
        case position
        case widthM = "width_m"
        case heightM = "height_m"
    }

    public init(position: [Double], widthM: Double, heightM: Double) {
        self.position = position
        self.widthM = widthM
        self.heightM = heightM
    }
}

// MARK: - CapturedRoom -> ScanExport 转换

public enum ScanExporter {

    /// 把 RoomPlan 扫描结果转换成自定义 JSON 模型。
    /// - Parameters:
    ///   - capturedRoom: RoomCaptureSession 完成后的扫描结果。
    ///   - northOffsetDeg: 扫描开始时刻录的 trueHeading（真北方位角）。
    public static func export(from capturedRoom: CapturedRoom,
                              northOffsetDeg: Double,
                              capturedAt: Date = Date()) -> ScanExport {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]   // 输出 2026-09-25T08:30:00Z
        let timeString = formatter.string(from: capturedAt)

        let model = capturedRoom.model
        let h = northOffsetDeg

        // 1. 先把所有墙转出来，并按 id 建索引（房间的 walls 存的是墙的 UUID）
        var wallByID: [UUID: WallExport] = [:]
        for surface in model.walls {
            let w = makeWall(from: surface, northOffsetDeg: h)
            wallByID[surface.id] = w
        }

        // 2. 门 / 窗 / 开口：位置取其 transform 平移量的 XZ 分量，宽高取 dimensions
        //    （Door/Window/Opening 结构同构，统一交给 openingCore 处理）
        let allDoors = model.doors.map { openingCore($0.transform, $0.dimensions, h) }      // (pos, w, h)
        let allWindows = model.windows.map { openingCore($0.transform, $0.dimensions, h) }
        let allOpenings = model.openings.map { openingCore($0.transform, $0.dimensions, h) }

        // 3. 按 Room 分组。RoomPlan 的 Room.walls 是墙 UUID 数组；
        //    门/窗归属：看它的位置落在哪个房间的哪面墙上（距墙中心线 < 0.4m 视为在该墙上），
        //    找不到时兜底分给水平距离最近的房间。
        var rooms: [RoomExport] = []
        for room in model.rooms {
            let roomWalls = room.walls.compactMap { wallByID[$0] }

            // 收集该房间所有墙的世界坐标线段，用于门窗归属判定
            let segments: [(a: SIMD2<Double>, b: SIMD2<Double>)] = room.walls.compactMap { id in
                guard let s = model.walls.first(where: { $0.id == id }) else { return nil }
                let seg = worldSegment(of: s)
                let a = NorthUpConverter.toNorthUp(x: seg.aX, z: seg.aZ, northOffsetDeg: h)
                let b = NorthUpConverter.toNorthUp(x: seg.bX, z: seg.bZ, northOffsetDeg: h)
                return (SIMD2(a.east, a.north), SIMD2(b.east, b.north))
            }

            // 门窗归属：位置落在该房间任意一面墙的中心线附近（<0.4m，含墙厚余量）即算
            func belongsToThisRoom(_ pos: SIMD2<Double>) -> Bool {
                for seg in segments where distancePointToSegment(pos, seg.a, seg.b) < 0.4 {
                    return true
                }
                return false
            }

            let doors = allDoors.filter { belongsToThisRoom($0.pos) }
            let windows = allWindows.filter { belongsToThisRoom($0.pos) }
            let openings = allOpenings.filter { belongsToThisRoom($0.pos) }

            rooms.append(RoomExport(
                areaM2: Double(room.area).rounded(toPlaces: 2),
                walls: roomWalls,
                doors: doors.map { DoorExport(position: [$0.pos.x, $0.pos.y], widthM: $0.w) },
                windows: windows.map { WindowExport(position: [$0.pos.x, $0.pos.y], widthM: $0.w, heightM: $0.h) },
                openings: openings.map { OpeningExport(position: [$0.pos.x, $0.pos.y], widthM: $0.w, heightM: $0.h) }
            ))
        }

        // 4. 兜底：极端情况下 RoomPlan 没识别出 Room（例如只扫了一面墙），
        //    则合成一个"整屋"房间，面积为 0，墙/门/窗全量输出。
        if rooms.isEmpty {
            rooms.append(RoomExport(
                areaM2: 0,
                walls: Array(wallByID.values),
                doors: allDoors.map { DoorExport(position: [$0.pos.x, $0.pos.y], widthM: $0.w) },
                windows: allWindows.map { WindowExport(position: [$0.pos.x, $0.pos.y], widthM: $0.w, heightM: $0.h) },
                openings: allOpenings.map { OpeningExport(position: [$0.pos.x, $0.pos.y], widthM: $0.w, heightM: $0.h) }
            ))
        }

        return ScanExport(capturedAt: timeString, northOffsetDeg: northOffsetDeg.rounded(toPlaces: 2), rooms: rooms)
    }

    // MARK: 几何提取

    /// Surface 的 transform 是它的中心位姿，dimensions 是局部包围盒尺寸。
    /// 墙是竖直薄板：水平延展 = 局部X轴×dims.x + 局部Z轴×dims.z，取水平投影即可得到两端点。
    private static func worldSegment(of surface: CapturedRoom.Surface)
        -> (aX: Double, aZ: Double, bX: Double, bZ: Double, height: Double) {
        let t = surface.transform                      // 列主序 4x4
        let pos = SIMD3(Double(t.columns.3.x), Double(t.columns.3.y), Double(t.columns.3.z))
        let axisX = SIMD3(Double(t.columns.0.x), Double(t.columns.0.y), Double(t.columns.0.z))
        let axisZ = SIMD3(Double(t.columns.2.x), Double(t.columns.2.y), Double(t.columns.2.z))
        let dims = surface.dimensions                  // SIMD3<Float>(x,y,z)，米

        // 水平方向向量（局部 X 与 Z 分量叠加，兼容墙沿局部 X 或 Z 两种摆放）
        let v = SIMD2(axisX.x * Double(dims.x) + axisZ.x * Double(dims.z),
                      axisX.z * Double(dims.x) + axisZ.z * Double(dims.z))
        let half = v / 2
        return (pos.x - half.x, pos.z - half.y,
                pos.x + half.x, pos.z + half.y,
                Double(dims.y))
    }

    private static func makeWall(from surface: CapturedRoom.Surface, northOffsetDeg: Double) -> WallExport {
        let seg = worldSegment(of: surface)
        let a = NorthUpConverter.toNorthUp(x: seg.aX, z: seg.aZ, northOffsetDeg: northOffsetDeg)
        let b = NorthUpConverter.toNorthUp(x: seg.bX, z: seg.bZ, northOffsetDeg: northOffsetDeg)
        let length = hypot(b.east - a.east, b.north - a.north)
        return WallExport(start: [a.east.rounded(toPlaces: 3), a.north.rounded(toPlaces: 3)],
                          end: [b.east.rounded(toPlaces: 3), b.north.rounded(toPlaces: 3)],
                          lengthM: length.rounded(toPlaces: 3),
                          heightM: seg.height.rounded(toPlaces: 3))
    }

    /// Door / Window / Opening 共用：transform 平移量的 XZ 为中心位置，
    /// dimensions.x ≈ 洞口宽度（沿墙方向），dimensions.y ≈ 洞口高度。
    private static func openingCore(_ transform: simd_float4x4,
                                    _ dimensions: SIMD3<Float>,
                                    _ northOffsetDeg: Double)
        -> (pos: SIMD2<Double>, w: Double, h: Double) {
        let t = transform
        let p = NorthUpConverter.toNorthUp(x: Double(t.columns.3.x),
                                           z: Double(t.columns.3.z),
                                           northOffsetDeg: northOffsetDeg)
        return (SIMD2(p.east.rounded(toPlaces: 3), p.north.rounded(toPlaces: 3)),
                Double(dimensions.x).rounded(toPlaces: 3),
                Double(dimensions.y).rounded(toPlaces: 3))
    }

    /// 点到线段的水平距离（米）。
    private static func distancePointToSegment(_ p: SIMD2<Double>, _ a: SIMD2<Double>, _ b: SIMD2<Double>) -> Double {
        let ab = b - a
        let len2 = simd_dot(ab, ab)
        guard len2 > 1e-9 else { return simd_distance(p, a) }
        let t = max(0, min(1, simd_dot(p - a, ab) / len2))
        let proj = a + ab * t
        return simd_distance(p, proj)
    }
}

// MARK: - 小工具

extension Double {
    /// 四舍五入到小数点后 n 位，避免 JSON 里出现 3.3000000000000003。
    func rounded(toPlaces n: Int) -> Double {
        let divisor = pow(10.0, Double(n))
        return (self * divisor).rounded() / divisor
    }
}
