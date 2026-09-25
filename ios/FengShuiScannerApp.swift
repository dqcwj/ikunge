//
//  FengShuiScannerApp.swift
//  FengShuiScanner
//
//  App 入口：TabView 两个主页面（扫描 / 设置）。
//

import SwiftUI

@main
struct FengShuiScannerApp: App {
    var body: some Scene {
        WindowGroup {
            // TabView 承载两个页面：
            //   1) 扫描：RoomPlan 取景器 + 罗盘校准 + 导出/上传
            //   2) 设置：后端 URL、扫描与罗盘校准说明
            TabView {
                RoomScanView()
                    .tabItem {
                        Label("扫描", systemImage: "viewfinder")
                    }
                SettingsView()
                    .tabItem {
                        Label("设置", systemImage: "gearshape")
                    }
            }
            .tint(.teal)
        }
    }
}
