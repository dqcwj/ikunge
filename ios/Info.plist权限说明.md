# Info.plist 权限配置说明

RoomPlan 需要相机；北向校准需要定位（读取 `trueHeading`）。
在 Xcode 里选中 Target → **Info** 标签页（或直接编辑 `Info.plist`）添加以下两行：

```xml
<!-- 相机权限：RoomPlan 扫描必须 -->
<key>NSCameraUsageDescription</key>
<string>用于扫描房间结构（RoomPlan），生成户型平面图供风水分析使用。</string>

<!-- 定位权限：CLLocationManager 读取罗盘 trueHeading 必须授权定位 -->
<key>NSLocationWhenInUseUsageDescription</key>
<string>扫描开始时读取设备罗盘朝向（真北方位角），用于把户型图旋转为“北向上”坐标。不采集你的位置轨迹。</string>
```

对应的 Target → Info 界面填写方式：

| Key (Property List) | Value |
|---|---|
| Privacy - Camera Usage Description (`NSCameraUsageDescription`) | 用于扫描房间结构（RoomPlan），生成户型平面图供风水分析使用。 |
| Privacy - Location When In Use Usage Description (`NSLocationWhenInUseUsageDescription`) | 扫描开始时读取设备罗盘朝向（真北方位角），用于把户型图旋转为“北向上”坐标。不采集你的位置轨迹。 |

补充说明：

1. **为什么罗盘需要定位权限**：`CLHeading.trueHeading`（真北）依赖定位服务校准磁偏角；
   仅用 `magneticHeading`（磁北）不需要授权，但风水坐向以真北为准，
   所以代码里优先 `trueHeading`、拿不到时才回退磁北（八宅/玄空的“替卦不处理、仅下卦”
   同样基于真北坐标体系，见 README 已知限制）。
2. **建议同时勾选** Target → Signing & Capabilities 无需额外 Capability，
   上述两个 plist key 是唯一前置条件。
3. **iOS 16+ 真机（带 LiDAR）才可运行扫描**；模拟器上 App 可启动但扫描页不可用，
   罗盘同样不可用（`CLLocationManager.headingAvailable()` 返回 false）。
