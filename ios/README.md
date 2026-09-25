# 风水扫房 iOS App（M3 阶段）

用 iPhone（带 LiDAR 的 Pro 系列）扫描房间，导出**北向上的结构化户型 JSON**，
连同扫描瞬间的罗盘真北朝向（`north_offset_deg`）一并上传到你的后端；
后端已有的风水规则引擎（八宅、玄空飞星、形煞几何判定）直接消费这份 JSON。

---

## 1. 文件清单

| 文件 | 说明 |
|---|---|
| `FengShuiScannerApp.swift` | App 入口，TabView（扫描 / 设置） |
| `RoomScanView.swift` | 扫描页：RoomPlan 取景器、罗盘校准、状态机、导出/上传 UI |
| `RoomModel.swift` | 数据模型 + 序列化：CapturedRoom → 北向上 JSON |
| `NetworkService.swift` | URLSession 异步 POST JSON 上传、本地备份 |
| `SettingsView.swift` | 设置页：后端 URL、扫描与罗盘校准说明 |
| `RoomModelTests.swift` | XCTest 单元测试（坐标系转换 + JSON 序列化） |
| `Info.plist权限说明.md` | 相机 / 定位权限文案与配置方法 |

## 2. Xcode 新建项目步骤

1. Xcode ≥ 14.3（随 iOS 16 SDK），Mac 上 **File → New → Project → iOS App**。
2. Product Name 填 `FengShuiScanner`，Interface 选 **SwiftUI**，Language **Swift**，
   最低版本 Deployment Target 设为 **iOS 16.0**。
3. 删掉自动生成的 `ContentView.swift` 和 `FengShuiScannerApp.swift`（用本目录文件替换）。
4. 把本目录全部 `.swift` 文件拖进 Xcode 项目导航器（勾选 *Copy items if needed*
   和当前 Target）。
5. 按 `Info.plist权限说明.md` 添加两个权限文案（相机 + 定位）。
6. Target → Signing & Capabilities 选择你的开发者团队（真机调试需要；
   RoomPlan 必须真机，不能模拟器）。
7. **新建测试 Target**（如未自动创建）：File → New → Target → iOS Unit Testing Bundle，
   命名 `FengShuiScannerTests`，把 `RoomModelTests.swift` **只**加入该测试 Target。
8. 连接真机，⌘R 运行。

## 3. 真机运行要求

- **iPhone 12 Pro 及以上**（Pro 系列才有 LiDAR；iPhone 15 Pro / 16 Pro 均可）。
- **iOS 16.0+**（RoomPlan 最低版本）。
- 首次运行会先后弹出相机、定位权限，均需允许（定位仅用于罗盘真北校准）。
- 建议电量 > 20%、关闭省电模式；LiDAR 发热明显，长时间扫描注意散热。

## 4. RoomPlan 权限与隐私

- RoomPlan 本身无需额外 entitlement，仅依赖相机权限。
- 扫描数据全部在设备端实时处理，App 不上传照片/点云，只上传第 5 节的结构化 JSON。
- 若相机被拒绝，扫描页会黑屏/报错；定位被拒绝则 `north_offset_deg` 回退为 0
  （界面会显示橙色提示），此时朝向需后端手动修正。

## 5. JSON 字段说明

```jsonc
{
  "captured_at": "2026-09-25T08:30:00Z",  // ISO8601 UTC，扫描完成时间
  "north_offset_deg": 15.5,               // 扫描开始瞬间设备的 trueHeading（真北方位角）
  "rooms": [                              // 按房间分组（通常 1 个）
    {
      "area_m2": 20.25,                   // RoomPlan 识别的房间面积
      "walls": [
        {
          "start": [0.0, 1.2],            // 墙起点 [x, y]，北向上坐标，米
          "end": [4.5, 1.2],              // 墙终点
          "length_m": 4.5,                // 水平长度（投影）
          "height_m": 2.8                 // 墙高
        }
      ],
      "doors":    [ { "position": [1.0, 1.2], "width_m": 0.9 } ],
      "windows":  [ { "position": [3.0, 1.2], "width_m": 1.5, "height_m": 1.4 } ],
      "openings": [ { "position": [4.5, 3.0], "width_m": 1.0, "height_m": 2.2 } ]
    }
  ]
}
```

坐标系约定（与 `RoomModel.swift` 内注释一致）：

- **单位统一为米**，二维平面。
- **y 轴 = 北，x 轴 = 东**（画到图上即“北在上”）。
- 转换公式：`east = x·cos(h) − z·sin(h)`，`north = −x·sin(h) − z·cos(h)`，
  其中 `(x, z)` 是 RoomPlan 世界水平面坐标，`h = north_offset_deg`。
  依据 RoomPlan（ARKit gravity 对齐）约定：扫描开始时设备朝世界 `-Z`、右为 `+X`。
- 墙朝向（坐向判定用）= 墙向量顺时针旋转 90° 的法线方位角，
  可直接 `atan2(dx_east, ...)` 或用 `NorthUpConverter.bearingDeg` 同式计算。
- `height_m` 对窗/开口是**洞口自身高度**，不是离地高度（离地需后端按窗台推断）。

## 6. 如何和网页后端对接

1. 设置页填后端地址，例如 `https://api.example.com/fengshui/scan`
   （会自动补 `https://`；内网调试可用 `http://192.168.x.x:8000/...`，
   但 ATS 默认禁止明文 HTTP，需在 Info.plist 加 `NSAppTransportSecurity` →
   `NSAllowsArbitraryLoads = YES`，仅调试用）。
2. App 以 `POST application/json` 提交上述结构，成功标准为 **HTTP 2xx**；
   失败（4xx/5xx/断网）会在界面弹窗提示，并保留本地副本。
3. 每次上传同时在 App 沙盒 `Documents/fengshui_scan_<时间>.json` 存一份
   pretty JSON，可通过“导出 JSON”按钮（系统分享）直接拿到文件。
4. 后端建议返回 `200 {"ok": true, "scan_id": "..."}`，之后由网页端的规则引擎
   消费：八宅（以门位/宅卦）、玄空飞星（以建造元运 + 坐向）、形煞（墙角/门冲几何判定）。

## 7. 已知限制

- **玄空飞星仅按下卦排盘，不做替卦**：山星向星直接按坐向卦位顺逆飞布，
  不处理替卦（卦线压在 3 度边界时的替卦起星）。建议后端对 `north_offset_deg`
  做 ±1.5° 邻域判定并给出提示。
- **室内罗盘误差**：iPhone 磁力计在室内受钢筋、家电干扰，误差常见 ±10°–30°。
  建议：① 到窗边/室外先画 8 字校准；② 回室内**保持手机水平**再点开始扫描；
  ③ 同一房间扫两次对比 `north_offset_deg`，差值 > 10° 说明干扰大，
  可取均值或用外部罗盘读数在后端覆盖。
- RoomPlan 对玻璃隔断、镜面、低矮家具上方墙段识别不稳定；
  开放式厨房/Loft 的“房间”划分可能与预期不同。
- 多房间户型建议逐间扫描、逐间上传，`rooms` 数组通常只含当前扫的一间。
- 坐标系推导假设“扫描开始时设备摄像头朝世界 -Z”。极少数机型的
  ARKit 世界对齐会引入固定偏差，若发现整体朝向偏转固定角度，
  用已知朝向的墙（如已知正南阳台）做一次校核即可在后期统一修正。
- 罗盘校准角是“快照”而非连续跟踪：扫描过程中转动手机不影响已记录的 h。

## 8. 运行单元测试

- `RoomModelTests.swift` 只依赖 Foundation/XCTest，模拟器即可运行（⌘U）。
- 覆盖：北向上坐标转换（朝北/朝东开始扫描的两种基准情形、长度不变性）、
  方位角计算、墙外法线朝向、JSON 编解码 round-trip、字段名（蛇形命名）校验、
  浮点位数处理、空数据兜底。
