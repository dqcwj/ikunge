# -*- coding: utf-8 -*-
"""
卦牌生成器：把六十四卦任一卦生成可 3D 打印的 STL 立式摆件。

设计：
  - 碑形背板（圆拱顶），正面凸起六爻（自下而上：初爻至上爻）
  - 阳爻为整条，阴爻为两段，动感的留白节奏与卦象一致
  - 底座两层收边，正面嵌太极浮雕
  - 导出方向即最佳打印方向：背板贴床、爻面朝上，无需支撑

用法：
  python guapai.py --name 乾
  python guapai.py --bits 111000
  python guapai.py --index 11
可选：--outdir 目录   --scale 倍数
"""
import argparse
import math
import os
import struct

# ---------- 六十四卦（King Wen 序），bits 自下而上 ----------
HEX_NAMES = ["乾","坤","屯","蒙","需","讼","师","比","小畜","履","泰","否",
             "同人","大有","谦","豫","随","蛊","临","观","噬嗑","贲","剥","复",
             "无妄","大畜","颐","大过","坎","离","咸","恒","遁","大壮","晋","明夷",
             "家人","睽","蹇","解","损","益","夬","姤","萃","升","困","井",
             "革","鼎","震","艮","渐","归妹","丰","旅","巽","兑","涣","节",
             "中孚","小过","既济","未济"]
HEX_BITS = ["111111","000000","100010","010001","111010","010111","010000","000010",
            "111011","110111","111000","000111","101111","111101","001000","000100",
            "100110","011001","110000","000011","100101","101001","000001","100000",
            "100111","111001","100001","011110","010010","101101","001110","011100",
            "001111","111100","000101","101000","101011","110101","001010","010100",
            "110001","100011","111110","011111","000110","011000","010110","011010",
            "101110","011101","100100","001001","001011","110100","101100","001101",
            "011011","110110","010011","110010","110011","001100","101010","010101"]

# ---------------- STL 基础 ----------------
class Mesh:
    def __init__(self):
        self.tris = []          # [(v0,v1,v2), ...] 顶点为 (x,y,z) 元组

    @staticmethod
    def _normal(a, b, c):
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        L = math.sqrt(nx*nx+ny*ny+nz*nz) or 1.0
        return nx/L, ny/L, nz/L

    def add_tri(self, a, b, c):
        self.tris.append((a, b, c))

    def add_quad(self, a, b, c, d):
        """按 a-b-c-d 顺序添加一个四边形面（自动保证外法线）"""
        n = self._normal(a, b, c)
        # 用面的对角线中心做外向检查由调用方保证方向，这里固定拆分
        self.add_tri(a, b, c)
        self.add_tri(a, c, d)

    def add_box(self, x0, y0, z0, x1, y1, z1):
        p = lambda x, y, z: (x, y, z)
        # 每个面均按外法线绕序（右手法则）
        self.add_quad(p(x0,y0,z0), p(x0,y1,z0), p(x1,y1,z0), p(x1,y0,z0))   # z0 面 -z
        self.add_quad(p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1))   # z1 面 +z
        self.add_quad(p(x0,y0,z0), p(x0,y0,z1), p(x0,y1,z1), p(x0,y1,z0))   # x0 -x
        self.add_quad(p(x1,y0,z0), p(x1,y1,z0), p(x1,y1,z1), p(x1,y0,z1))   # x1 +x
        self.add_quad(p(x0,y0,z0), p(x1,y0,z0), p(x1,y0,z1), p(x0,y0,z1))   # y0 -y
        self.add_quad(p(x0,y1,z0), p(x0,y1,z1), p(x1,y1,z1), p(x1,y1,z0))   # y1 +y

    def add_prism(self, poly, z0, z1):
        """凸多边形 poly（CCW）沿 z 挤出；非凸会盖帽出错，请保证凸"""
        n = len(poly)
        # 侧面（外法线：对 CCW 多边形取有向边的右侧）
        for i in range(n):
            a, b = poly[i], poly[(i+1) % n]
            self.add_quad((a[0],a[1],z0), (b[0],b[1],z0), (b[0],b[1],z1), (a[0],a[1],z1))
        # 顶/底盖（扇形三角化）
        for i in range(1, n-1):
            a, b, c = poly[0], poly[i], poly[i+1]
            self.add_tri((a[0],a[1],z1), (b[0],b[1],z1), (c[0],c[1],z1))    # 顶 +z
            self.add_tri((a[0],a[1],z0), (c[0],c[1],z0), (b[0],b[1],z0))    # 底 -z

    def save_stl(self, path, name=b"guapai"):
        with open(path, "wb") as f:
            f.write(name.ljust(80, b"\0")[:80])
            f.write(struct.pack("<I", len(self.tris)))
            for a, b, c in self.tris:
                n = self._normal(a, b, c)
                f.write(struct.pack("<3f", *n))
                for v in (a, b, c):
                    f.write(struct.pack("<3f", *v))
                f.write(struct.pack("<H", 0))

# ---------------- 2D 辅助 ----------------
def rect(cx, cy, w, h):
    return [(cx-w/2, cy-h/2), (cx+w/2, cy-h/2), (cx+w/2, cy+h/2), (cx-w/2, cy+h/2)]

def half_disc(cx, cy, r, segs=32, side="up"):
    """半圆多边形（直径为底，弓朝上/下/左/右），角度递增保证 CCW"""
    start = {"up": 0.0, "down": math.pi, "right": -math.pi/2, "left": math.pi/2}[side]
    pts = []
    for i in range(segs+1):
        t = start + math.pi * i / segs
        pts.append((cx + r*math.cos(t), cy + r*math.sin(t)))
    return pts

def rot_rect(cx, cy, w, h, ang):
    """绕中心旋转的矩形，CCW"""
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]
    return [(cx + x*ca - y*sa, cy + x*sa + y*ca) for x, y in pts]

# ---------------- 卦牌建模 ----------------
def build(bits, s=1.0):
    """
    坐标系（打印方向）：
      x = 面宽，y = 牌面高，z = 厚度（z=0 为背板贴床面）
    """
    m = Mesh()
    # ---- 尺寸参数（毫米）----
    W    = 64*s          # 背板宽
    RECT = 62*s          # 背板矩形部分高
    R    = W/2           # 拱顶半径
    T    = 5*s           # 背板厚
    FR   = 2.2*s         # 浮雕抬升
    barW = 42*s          # 阳爻总宽
    barH = 5.5*s         # 爻厚（高度方向）
    yinGap = 10*s        # 阴爻中缝
    rowStep = 9.3*s      # 爻行距
    BASE_H = 15*s        # 底座总高
    BASE_D = 30*s        # 底座深（z 向）

    # ---- 背板：矩形 + 顶部半圆拱，合并为单个凸轮廓（避免接缝）----
    segs_arc = 40
    arch = [(R*math.cos(math.pi*i/segs_arc), RECT + R*math.sin(math.pi*i/segs_arc))
            for i in range(1, segs_arc)]          # 跳过两端点，避免与侧边顶点重复
    panel_poly = [(W/2, 0), (W/2, RECT)] + arch + [(-W/2, RECT), (-W/2, 0)]
    m.add_prism(panel_poly, 0, T)

    # ---- 正面边框（下边 + 两侧 + 拱顶弧段）----
    fw = 3*s   # 框线宽
    # 左右边框：贴着拱顶内沿，只做矩形段的竖框
    inner = fw + 2*s
    m.add_box(-W/2+2*s, 4*s, T, -W/2+2*s+fw, RECT-2*s, T+FR)          # 左
    m.add_box(W/2-2*s-fw, 4*s, T, W/2-2*s, RECT-2*s, T+FR)            # 右
    # 拱顶弧框：沿内弧的短矩形段
    arcR = R - inner - fw/2
    segs = 14
    for i in range(segs):
        a1 = math.pi - math.pi*i/segs
        a2 = math.pi - math.pi*(i+1)/segs
        cx, cy = arcR*math.cos((a1+a2)/2), RECT + arcR*math.sin((a1+a2)/2)
        ang = (a1+a2)/2 - math.pi/2
        m.add_prism(rot_rect(cx, cy, fw, arcR*2*math.pi/segs*1.15, ang), T, T+FR)

    # ---- 六爻（自下而上）----
    for row, bit in enumerate(bits):          # bits[0] = 初爻 = 最下一行
        cy = 10*s + (5-row)*rowStep           # 初爻在最下
        if bit == "1":                        # 阳爻
            m.add_box(-barW/2, cy-barH/2, T, barW/2, cy+barH/2, T+FR)
        else:                                 # 阴爻
            seg = (barW - yinGap)/2
            m.add_box(-barW/2, cy-barH/2, T, -barW/2+seg, cy+barH/2, T+FR)
            m.add_box(barW/2-seg, cy-barH/2, T, barW/2, cy+barH/2, T+FR)

    # ---- 底座（两层收边）----
    bw1, bh1 = 92*s, 8*s        # 下层
    bw2, bh2 = 78*s, 7*s        # 上层
    zc = BASE_D/2
    # 面板插入底座：底座以牌面坐标 y∈[-BASE_H, 0] 为准，z 居中包住背板
    m.add_box(-bw1/2, -bh1, zc-BASE_D/2, bw1/2, 0, zc+BASE_D/2)
    m.add_box(-bw2/2, -bh1-bh2, zc-(BASE_D-8*s)/2, bw2/2, -bh1, zc+(BASE_D-8*s)/2)
    # 底座与背板的连接补块（防止悬空薄边）
    m.add_box(-W/2+2*s, -bh1, 0, W/2-2*s, 0, T)

    # ---- 太极浮雕（底座正面）----
    zt = zc + BASE_D/2                     # 底座前脸 z
    tx, ty, tr = 0, -(bh1+bh2)/2 - 1*s, 5.5*s
    m.add_prism(circle(tx, ty, tr, 28), zt, zt+1.2*s)                 # 底盘整圆
    # S 界线：上半圆凸起归右鱼、下半圆凸起归左鱼（±0.02 错开避免精确相切）
    m.add_prism(half_disc(tx, ty+tr/2+0.02, tr/2, 16, "right"), zt+1.2*s, zt+2.2*s)
    m.add_prism(half_disc(tx, ty-tr/2-0.02, tr/2, 16, "left"),  zt+1.2*s, zt+2.2*s)
    # 两只鱼眼（小圆点）
    for ey in (ty+tr/2, ty-tr/2):
        m.add_prism(circle(tx, ey, tr/7, 14), zt+2.2*s, zt+3*s)

    return m

def circle(cx, cy, r, segs):
    return [(cx + r*math.cos(2*math.pi*i/segs), cy + r*math.sin(2*math.pi*i/segs))
            for i in range(segs)]

# ---------------- SVG 预览 ----------------
def svg_preview(bits, path):
    name = HEX_NAMES[HEX_BITS.index(bits)]
    W, RECT, R = 64, 62, 32
    bars = []
    for row, bit in enumerate(bits):
        cy = 10 + (5-row)*9.3
        if bit == "1":
            bars.append(f'<rect x="11" y="{RECT+R-cy-2.75:.1f}" width="42" height="5.5" fill="#2A2419"/>')
        else:
            bars.append(f'<rect x="11" y="{RECT+R-cy-2.75:.1f}" width="16" height="5.5" fill="#2A2419"/>')
            bars.append(f'<rect x="37" y="{RECT+R-cy-2.75:.1f}" width="16" height="5.5" fill="#2A2419"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -25 128 145" width="420">
  <rect x="-20" y="-25" width="128" height="145" fill="#E9DDBC"/>
  <!-- 背板 -->
  <path d="M0 {R} v-{RECT} a{R},{R} 0 0 1 {W},0 v{RECT} z" fill="#F0E5C9" stroke="#B0483A" stroke-width="1.5" transform="translate(0,{R+RECT}) scale(1,-1) translate(0,-{R+RECT})"/>
  {''.join(bars)}
  <!-- 底座 -->
  <rect x="-14" y="{R+RECT}" width="92" height="8" fill="#C9B273" stroke="#8A6A2F"/>
  <rect x="-7" y="{R+RECT+8}" width="78" height="7" fill="#B89F63" stroke="#8A6A2F"/>
  <text x="86" y="{R+RECT+30}" font-size="11" fill="#9E2B20" text-anchor="end" font-family="Kaiti SC,STKaiti,KaiTi,serif">{name} · {bits}（自下而上）</text>
</svg>'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

# ---------------- 入口 ----------------
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--name", help="卦名，如 乾、泰")
    g.add_argument("--bits", help="六位 0/1，自下而上，如 111000")
    g.add_argument("--index", type=int, help="King Wen 序号 1-64")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()

    if args.name:
        if args.name not in HEX_NAMES:
            ap.error(f"卦名须为六十四卦之一：{args.name}")
        bits = HEX_BITS[HEX_NAMES.index(args.name)]
    elif args.bits:
        if len(args.bits) != 6 or set(args.bits) - {"0", "1"}:
            ap.error("bits 须为六位 0/1")
        bits = args.bits
    else:
        bits = HEX_BITS[args.index - 1]

    idx = HEX_BITS.index(bits)
    name = HEX_NAMES[idx]
    m = build(bits, args.scale)

    os.makedirs(args.outdir, exist_ok=True)
    stl_path = os.path.join(args.outdir, f"卦牌_{name}_{'%02d' % (idx+1)}.stl")
    m.save_stl(stl_path, f"guapai {name} {bits}".encode())
    svg_preview(bits, os.path.join(args.outdir, f"预览_{name}.svg"))

    xs = [v[0] for t in m.tris for v in t]; ys = [v[1] for t in m.tris for v in t]
    zs = [v[2] for t in m.tris for v in t]
    print(f"第{idx+1}卦 {name}（{bits} 自下而上）")
    print(f"  STL：{stl_path}")
    print(f"  三角面：{len(m.tris)}")
    print(f"  尺寸：{max(xs)-min(xs):.1f} × {max(ys)-min(ys):.1f} × {max(zs)-min(zs):.1f} mm（宽×高×厚，已含底座）")

if __name__ == "__main__":
    main()
