# -*- coding: utf-8 -*-
"""
玄機閣 · 局域网服务器（零依赖，Python 3.8+ 标准库）

用法：
  python server.py            # 默认 0.0.0.0:8000
  python server.py 9000       # 自定义端口

然后在同一 Wi-Fi 的手机上访问  http://<电脑IP>:8000/
（电脑 IP 用 ipconfig 查看，一般是 192.168.x.x）

注意：iOS 的方向传感器只在 HTTPS（安全上下文）下开放，
局域网 HTTP 访问时罗盘页请用「手动定向」滑杆；要启用手机罗盘，
请部署到 HTTPS 环境（如 GitHub Pages，见 README）。
"""
import http.server
import socketserver
import os
import sys
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    os.chdir(ROOT)
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"玄機閣 已启动:  http://{lan_ip()}:{PORT}   （Ctrl+C 停止）")
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
