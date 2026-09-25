# -*- coding: utf-8 -*-
"""
下载 coco-ssd 识别模型到本目录（供 scan.html 离线识物用）。

用法：  python get_model.py [代理地址]
示例：  python get_model.py http://127.0.0.1:7897
说明：从 Google 模型库下载 ssd_mobilenet_v2（tfjs 格式，17 分片约 68MB），
      支持断点续传（已完整的文件跳过）；直连被干扰时走本地代理（如 Clash 默认口 7897）。
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://storage.googleapis.com/tfjs-models/savedmodel/ssd_mobilenet_v2/"
PROXY = sys.argv[1] if len(sys.argv) > 1 else None
TRIALS = 6


def fetch(name, tries=TRIALS):
    cmd = ["curl", "-sL", "--max-time", "150"]
    if PROXY:
        cmd += ["-x", PROXY]
    cmd += ["-o", name, BASE + name]
    for i in range(tries):
        r = subprocess.run(cmd)
        if r.returncode == 0 and os.path.exists(name) and os.path.getsize(name) > 1000:
            return True
        time.sleep(1 + i)
    return False


def main():
    os.chdir(HERE)
    if not (os.path.exists("model.json") and os.path.getsize("model.json") > 1000):
        if not fetch("model.json"):
            sys.exit("model.json 下载失败；可试 python get_model.py http://127.0.0.1:7897")
    try:
        paths = json.load(open("model.json", encoding="utf-8"))["weightsManifest"][0]["paths"]
    except Exception:
        sys.exit("model.json 损坏，删除后重跑")
    ok = True
    for p in paths:
        if os.path.exists(p) and os.path.getsize(p) > 10000:
            print(f"  = {p} 已存在，跳过")
            continue
        if fetch(p):
            print(f"  + {p} ({os.path.getsize(p)//1024} KB)", flush=True)
        else:
            print(f"  ✗ {p} 失败", flush=True)
            ok = False
    print("模型就绪" if ok else "部分分片失败，重跑本脚本续传")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
