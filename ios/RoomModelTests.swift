//
//  RoomModelTests.swift
//  FengShuiScanner
//
//  序列化与坐标转换单元测试。
//  使用方法：把本文件加入 Xcode 的 Test Target（FengShuiScannerTests），
//  菜单 Product > Test 运行；本文件只依赖 Foundation/XCTest，模拟器即可跑。
//

import XCTest
@testable import FengShuiScanner

final class RoomModelTests: XCTestCase {

    // MARK: - 北向上坐标转换

    // 设备朝北开始扫描（h=0）：世界 -Z 是北，世界 +X 是东。
    // 前方 1 米的点 (x=0, z=-1) 应落在正北 1 米处。
    func testNorthUp_zeroHeading_frontIsNorth() {
        let r = NorthUpConverter.toNorthUp(x: 0, z: -1, northOffsetDeg: 0)
        XCTAssertEqual(r.east, 0, accuracy: 1e-9)
        XCTAssertEqual(r.north, 1, accuracy: 1e-9)
    }

    // h=0：右侧 1 米的点 (x=1, z=0) 应落在正东 1 米处。
    func testNorthUp_zeroHeading_rightIsEast() {
        let r = NorthUpConverter.toNorthUp(x: 1, z: 0, northOffsetDeg: 0)
        XCTAssertEqual(r.east, 1, accuracy: 1e-9)
        XCTAssertEqual(r.north, 0, accuracy: 1e-9)
    }

    // 设备朝东开始扫描（h=90）：前方 (0,-1) 应在正东，右侧 (1,0) 应在正南。
    func testNorthUp_eastHeading() {
        let front = NorthUpConverter.toNorthUp(x: 0, z: -1, northOffsetDeg: 90)
        XCTAssertEqual(front.east, 1, accuracy: 1e-9)
        XCTAssertEqual(front.north, 0, accuracy: 1e-9)

        let right = NorthUpConverter.toNorthUp(x: 1, z: 0, northOffsetDeg: 90)
        XCTAssertEqual(right.east, 0, accuracy: 1e-9)
        XCTAssertEqual(right.north, -1, accuracy: 1e-9)
    }

    // 旋转不改变长度。
    func testNorthUp_preservesDistance() {
        let h = 37.5
        let r = NorthUpConverter.toNorthUp(x: 3, z: 4, northOffsetDeg: h)
        XCTAssertEqual(hypot(r.east, r.north), 5, accuracy: 1e-9)
    }

    // MARK: - 方位角

    func testBearing() {
        XCTAssertEqual(NorthUpConverter.bearingDeg(east: 0, north: 1), 0, accuracy: 1e-9)   // 北
        XCTAssertEqual(NorthUpConverter.bearingDeg(east: 1, north: 0), 90, accuracy: 1e-9)  // 东
        XCTAssertEqual(NorthUpConverter.bearingDeg(east: 0, north: -1), 180, accuracy: 1e-9)// 南
        XCTAssertEqual(NorthUpConverter.bearingDeg(east: -1, north: 0), 270, accuracy: 1e-9)// 西
    }

    func testNormalizeDeg() {
        XCTAssertEqual(NorthUpConverter.normalizeDeg(-30), 330, accuracy: 1e-9)
        XCTAssertEqual(NorthUpConverter.normalizeDeg(725), 5, accuracy: 1e-9)
    }

    // 墙朝向：北向上从 (0,0) 到 (1,0)（东向墙）的外法线应朝南 180°。
    func testWallFacing() {
        let wall = WallExport(start: [0, 0], end: [1, 0], lengthM: 1, heightM: 2.8)
        XCTAssertEqual(wall.facingDeg, 180, accuracy: 1e-6)
    }

    // MARK: - JSON 序列化

    func testEncodeDecodeRoundTrip() throws {
        let scan = ScanExport(
            capturedAt: "2026-09-25T08:30:00Z",
            northOffsetDeg: 15.5,
            rooms: [RoomExport(
                areaM2: 20.25,
                walls: [WallExport(start: [0, 0], end: [4.5, 0], lengthM: 4.5, heightM: 2.8)],
                doors: [DoorExport(position: [1.0, 0], widthM: 0.9)],
                windows: [WindowExport(position: [3.0, 0], widthM: 1.5, heightM: 1.4)],
                openings: [OpeningExport(position: [4.5, 1.2], widthM: 1.0, heightM: 2.2)]
            )]
        )

        let data = try JSONEncoder().encode(scan)
        let decoded = try JSONDecoder().decode(ScanExport.self, from: data)
        XCTAssertEqual(decoded, scan)
    }

    // 验证 JSON 字段名与后端约定完全一致（蛇形命名）。
    func testJSONKeys() throws {
        let scan = ScanExport(
            capturedAt: "2026-09-25T08:30:00Z",
            northOffsetDeg: 0,
            rooms: [RoomExport(
                areaM2: 12.5,
                walls: [WallExport(start: [0, 0], end: [3, 4], lengthM: 5, heightM: 2.7)],
                doors: [DoorExport(position: [1, 1], widthM: 0.9)],
                windows: [WindowExport(position: [2, 2], widthM: 1.2, heightM: 1.5)],
                openings: []
            )]
        )

        let json = try XCTUnwrap(String(data: scan.jsonData(), encoding: .utf8))
        for key in ["\"captured_at\"", "\"north_offset_deg\"", "\"rooms\"",
                    "\"area_m2\"", "\"walls\"", "\"doors\"", "\"windows\"", "\"openings\"",
                    "\"start\"", "\"end\"", "\"length_m\"", "\"height_m\"",
                    "\"position\"", "\"width_m\""] {
            XCTAssertTrue(json.contains(key), "JSON 缺少字段 \(key)")
        }
    }

    // 位数处理：避免浮点噪声进入 JSON。
    func testRounding() {
        XCTAssertEqual(3.3000000000000003.rounded(toPlaces: 3), 3.3, accuracy: 1e-12)
        XCTAssertEqual(2.8499999.rounded(toPlaces: 2), 2.85, accuracy: 1e-12)
    }

    // 空房间（极端兜底路径）也能正常编码。
    func testEmptyRoomsEncodes() throws {
        let scan = ScanExport(capturedAt: "2026-09-25T00:00:00Z", northOffsetDeg: 0, rooms: [])
        let data = try scan.jsonData(pretty: true)
        XCTAssertTrue(data.count > 0)
    }

    // WallExport 的 length 应由两端点计算（导出时由几何得出，这里验证一致性帮助文档化）。
    func testWallLengthFromPoints() {
        let a = NorthUpConverter.toNorthUp(x: 1, z: 1, northOffsetDeg: 123)
        let b = NorthUpConverter.toNorthUp(x: 4, z: 5, northOffsetDeg: 123)
        let length = hypot(b.east - a.east, b.north - a.north)
        XCTAssertEqual(length, 5, accuracy: 1e-9)
    }
}
