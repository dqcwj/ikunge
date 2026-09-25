//
//  NetworkService.swift
//  FengShuiScanner
//
//  上传服务：把扫描结果 JSON POST 到设置页配置的后端 URL。
//

import Foundation

// MARK: - 错误定义

/// 上传过程可能出现的错误（UI 层据此给出中文提示）。
enum NetworkError: LocalizedError {
    case badURL                // URL 格式非法（缺协议头等）
    case invalidResponse       // 服务器返回的不是 HTTP 响应
    case serverError(Int)      // HTTP 状态码非 2xx
    case encodingFailed        // JSON 编码失败（理论上不会发生）
    case notConnected          // 网络不可达

    var errorDescription: String? {
        switch self {
        case .badURL:            return "后端 URL 无效，请在“设置”里检查（需要 http:// 或 https:// 开头）"
        case .invalidResponse:   return "服务器返回了无法识别的响应"
        case .serverError(let code): return "服务器错误（HTTP \(code)）"
        case .encodingFailed:    return "JSON 数据编码失败"
        case .notConnected:      return "网络不可用，请检查网络后重试"
        }
    }
}

// MARK: - 上传服务

/// 轻量上传服务：URLSession 异步 POST JSON。
final class NetworkService {

    static let shared = NetworkService()
    private let session: URLSession

    init(session: URLSession = .shared) {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = session
    }

    /// 规整用户输入的后端地址：补 https://、去首尾空白。
    /// 返回 nil 表示无法解析成合法 URL。
    static func normalizeBackendURL(_ raw: String) -> URL? {
        var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if !s.hasPrefix("http://") && !s.hasPrefix("https://") {
            s = "https://" + s        // 默认按 https 处理
        }
        guard let url = URL(string: s),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              url.host() != nil else { return nil }
        return url
    }

    /// 上传扫描结果。成功返回服务器状态码（2xx）。
    /// - Parameters:
    ///   - scan: 已序列化的导出模型
    ///   - rawURL: 设置页里填的后端地址字符串
    func upload(scan: ScanExport, to rawURL: String) async throws -> Int {
        guard let url = Self.normalizeBackendURL(rawURL) else {
            throw NetworkError.badURL
        }

        guard let body = try? scan.jsonData() else {
            throw NetworkError.encodingFailed
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        request.setValue("FengShuiScanner-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue("gzip", forHTTPHeaderField: "Accept-Encoding")
        request.httpBody = body

        // iOS 15+ 的 async URLSession API；错误统一映射成 NetworkError
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw NetworkError.invalidResponse
            }
            guard (200...299).contains(http.statusCode) else {
                // 尽量带出后端错误信息，方便联调
                let detail = String(data: data.prefix(300), encoding: .utf8) ?? ""
                print("上传失败 HTTP \(http.statusCode)：\(detail)")
                throw NetworkError.serverError(http.statusCode)
            }
            return http.statusCode
        } catch let e as NetworkError {
            throw e
        } catch {
            throw NetworkError.notConnected
        }
    }

    /// 保存导出 JSON 到本地“应用沙盒/Documents”，便于分享或手动导入后端。
    static func saveLocally(_ scan: ScanExport) throws -> URL {
        let data = try scan.jsonData(pretty: true)
        let stamp = scan.capturedAt
            .replacingOccurrences(of: ":", with: "-")
        let url = FileManager.default
            .urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("fengshui_scan_\(stamp).json")
        try data.write(to: url, options: [.atomic, .completeFileProtection])
        return url
    }
}
