# -*- coding: utf-8 -*-
"""
卦坠生成器：腰牌式穿绳挂件，四色 AMS 方案。

形制（自上而下）：
  金色圆帽（穿绳受力）→ 绳孔（6×12mm）→ 金色横梁 → 肩部收窄
  → 墨色梯形牌身（微收底）→ 朱砂六爻（初爻在下）
  → 太极圆章（金环 + 宣纸白盘 + 墨色双鱼 + 朱砂鱼眼）

配色（与玄機閣网站一致，4 槽 AMS）：
  墨 #2A2419 / 鎏金 #8A6A2F / 朱砂 #9E2B20 / 宣纸 #E9DDBC

用法：
  python guapai_pendant.py --name 泰
  python guapai_pendant.py --bits 111000 --outdir .
"""
import argparse
import math
import os
import sys

sys.path.insert(0, r"D:\审美\.claude\skills\bambu-studio-ai\scripts")

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

PALETTE = ["#2A2419", "#8A6A2F", "#9E2B20", "#E9DDBC"]   # 墨 / 鎏金 / 朱砂 / 宣纸
INK, GOLD, RED, IVORY = 0, 1, 2, 3

# ---------------- 网格基础（与 guapai.py 同一套，含正确外法线绕序） ----------------
class Mesh:
    def __init__(self):
        self.tris = []

    def add_tri(self, a, b, c):
        self.tris.append((a, b, c))

    def add_quad(self, a, b, c, d):
        self.add_tri(a, b, c)
        self.add_tri(a, c, d)

    def add_box(self, x0, y0, z0, x1, y1, z1):
        p = lambda x, y, z: (x, y, z)
        self.add_quad(p(x0,y0,z0), p(x0,y1,z0), p(x1,y1,z0), p(x1,y0,z0))
        self.add_quad(p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1))
        self.add_quad(p(x0,y0,z0), p(x0,y0,z1), p(x0,y1,z1), p(x0,y1,z0))
        self.add_quad(p(x1,y0,z0), p(x1,y1,z0), p(x1,y1,z1), p(x1,y0,z1))
        self.add_quad(p(x0,y0,z0), p(x1,y0,z0), p(x1,y0,z1), p(x0,y0,z1))
        self.add_quad(p(x0,y1,z0), p(x0,y1,z1), p(x1,y1,z1), p(x1,y1,z0))

    def add_prism(self, poly, z0, z1):
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i+1) % n]
            self.add_quad((a[0],a[1],z0), (b[0],b[1],z0), (b[0],b[1],z1), (a[0],a[1],z1))
        for i in range(1, n-1):
            a, b, c = poly[0], poly[i], poly[i+1]
            self.add_tri((a[0],a[1],z1), (b[0],b[1],z1), (c[0],c[1],z1))
            self.add_tri((a[0],a[1],z0), (c[0],c[1],z0), (b[0],b[1],z0))

    def save_stl(self, path, name=b"guazhui"):
        import struct
        with open(path, "wb") as f:
            f.write(name.ljust(80, b"\0")[:80])
            f.write(struct.pack("<I", len(self.tris)))
            for a, b, c in self.tris:
                ux,uy,uz = b[0]-a[0],b[1]-a[1],b[2]-a[2]
                vx,vy,vz = c[0]-a[0],c[1]-a[1],c[2]-a[2]
                nx,ny,nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
                L = math.sqrt(nx*nx+ny*ny+nz*nz) or 1.0
                f.write(struct.pack("<3f", nx/L, ny/L, nz/L))
                for v in (a, b, c):
                    f.write(struct.pack("<3f", *v))
                f.write(struct.pack("<H", 0))

def rect(cx, cy, w, h):
    return [(cx-w/2,cy-h/2),(cx+w/2,cy-h/2),(cx+w/2,cy+h/2),(cx-w/2,cy+h/2)]

def half_disc(cx, cy, r, segs=32, side="up"):
    start = {"up":0.0,"down":math.pi,"right":-math.pi/2,"left":math.pi/2}[side]
    return [(cx+r*math.cos(start+math.pi*i/segs), cy+r*math.sin(start+math.pi*i/segs))
            for i in range(segs+1)]

def circle(cx, cy, r, segs):
    return [(cx+r*math.cos(2*math.pi*i/segs), cy+r*math.sin(2*math.pi*i/segs))
            for i in range(segs)]

def rot_rect(cx, cy, w, h, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]
    return [(cx+x*ca-y*sa, cy+x*sa+y*ca) for x, y in pts]

# ---------------- 卦坠建模 ----------------
def build_parts(bits, s=1.0):
    """返回 [(Mesh, 配色索引), ...]，坐标：x 宽、y 高、z 厚（z=0 贴床）"""
    parts = []   # (mesh, label)

    def new(label):
        m = Mesh(); parts.append((m, label)); return m

    BODY_T = 4.4*s      # 牌身厚
    TOP    = 6.0*s      # 总厚（浮雕顶）
    BW_TOP = 46*s       # 牌身上宽
    BW_BOT = 40*s       # 牌身下宽（微收）
    BH     = 78*s       # 牌身高
    SH     = 8*s        # 肩高
    NW     = 16*s       # 颈宽
    SLOT_W = 6*s        # 绳孔宽
    SLOT_H = 12*s       # 绳孔高
    CAP_R  = 8.5*s      # 圆帽半径
    BAR_W  = 30*s       # 爻线总宽
    BAR_H  = 5.2*s      # 爻线截面高
    YIN_G  = 7*s        # 阴爻中缝

    y_sh1 = BH + SH            # 肩顶（颈底）
    y_cross0, y_cross1 = y_sh1 + 1*s, y_sh1 + 5*s          # 横梁
    y_slot_top = y_cross1 + SLOT_H                          # 绳孔顶（金帽下沿）
    y_cap = y_slot_top                                       # 圆帽圆心（叠入绳孔顶）

    # —— 墨色牌身：整体轮廓（梯形身 + 外扩肩 + 收颈）为单个凸多边形 ——
    body = new(INK)
    body.add_prism([(-BW_BOT/2,0),(BW_BOT/2,0),(BW_TOP/2,BH),(NW/2,y_sh1),(-NW/2,y_sh1),(-BW_TOP/2,BH)], 0, BODY_T)
    # 颈侧条（绳孔两侧）：下端深探入牌身内部，顶端没入金帽
    strip_x = SLOT_W/2
    neck_top = y_cap + 2*s
    body.add_box(-NW/2, BH - 6*s, 0, -strip_x, neck_top, BODY_T)
    body.add_box(strip_x, BH - 6*s, 0, NW/2, neck_top, BODY_T)

    # —— 金色件：圆帽 / 横梁 ——
    cap = new(GOLD)
    cap.add_prism(half_disc(0, y_cap, CAP_R, segs=36), 0, TOP)
    cross = new(GOLD)
    cross.add_box(-NW/2-0.5*s, y_cross0, 0, NW/2+0.5*s, y_cross1, TOP)

    frame = new(GOLD)
    inset, fw = 1.0*s, 2.6*s
    frame.add_box(-BW_TOP/2+inset+1*s, BH-inset-fw, BODY_T, BW_TOP/2-inset-1*s, BH-inset, TOP)   # 顶
    frame.add_box(-BW_BOT/2+inset+1*s, inset, BODY_T, BW_BOT/2-inset-1*s, inset+fw, TOP)          # 底
    # 两侧斜边框（沿牌身斜边，向内让位）
    for sign in (-1, 1):
        ex0, ey0 = sign*BW_BOT/2, 0
        ex1, ey1 = sign*BW_TOP/2, BH
        dx, dy = ex1-ex0, ey1-ey0
        L = math.hypot(dx, dy)
        nx, ny = -dy/L*sign, dx/L*sign        # 指向内侧的法线
        cx, cy = (ex0+ex1)/2 + nx*(inset+fw/2), (ey0+ey1)/2 + ny*(inset+fw/2)
        frame.add_prism(rot_rect(cx, cy, fw, L*0.92, math.atan2(dy, dx)), BODY_T, TOP)

    # —— 朱砂六爻（初爻在下） ——
    yao = new(RED)
    y_top, step = BH - 9*s, 8*s
    for row, bit in enumerate(bits):
        cy = y_top - row*step
        if bit == "1":
            yao.add_box(-BAR_W/2, cy-BAR_H/2, BODY_T, BAR_W/2, cy+BAR_H/2, TOP)
        else:
            seg = (BAR_W - YIN_G)/2
            yao.add_box(-BAR_W/2, cy-BAR_H/2, BODY_T, -BAR_W/2+seg, cy+BAR_H/2, TOP)
            yao.add_box(BAR_W/2-seg, cy-BAR_H/2, BODY_T, BAR_W/2, cy+BAR_H/2, TOP)

    # —— 太极圆章 ——
    tcy = 15*s
    ring_r = 9.5*s
    ring = new(GOLD)
    for i in range(16):   # 整环分段
        a1, a2 = 2*math.pi*i/16, 2*math.pi*(i+1)/16
        mx, my = ring_r*math.cos((a1+a2)/2), tcy + ring_r*math.sin((a1+a2)/2)
        ring.add_prism(rot_rect(mx, my, 1.8*s, 2*math.pi*ring_r/16*1.15, (a1+a2)/2+math.pi/2), BODY_T, TOP)
    disc = new(IVORY)
    disc_r = ring_r - 0.7*s                     # 与金环搭接 0.2mm
    disc.add_prism(circle(0, tcy, disc_r, 28), BODY_T, TOP)
    fish = new(INK)
    lens_r = disc_r/2 - 0.3*s                   # 双鱼透镜整体收在盘内
    fish.add_prism(half_disc(0, tcy+disc_r/2, lens_r, 14, "right"), TOP-0.8*s, TOP)
    fish.add_prism(half_disc(0, tcy-disc_r/2, lens_r, 14, "left"),  TOP-0.8*s, TOP)
    eyes = new(RED)
    for ey in (tcy+disc_r/2, tcy-disc_r/2):
        eyes.add_prism(circle(0, ey, 1.3*s, 12), TOP-0.6*s, TOP)

    return parts

# ---------------- 合并导出 ----------------
def merged_arrays(parts):
    import numpy as np
    verts, faces, labels = [], [], []
    vi = 0
    for m, lab in parts:
        for a, b, c in m.tris:
            verts.extend((a, b, c))
            faces.append((vi, vi+1, vi+2))
            labels.append(lab)
            vi += 3
    return (np.array(verts, dtype=np.float64),
            np.array(faces, dtype=np.int64),
            np.array(labels, dtype=np.int64))

def single_stl(parts, path):
    m = Mesh()
    for pm, _ in parts:
        m.tris.extend(pm.tris)
    m.save_stl(path)

def svg_preview(bits, path):
    name = HEX_NAMES[HEX_BITS.index(bits)]
    rows = []
    y_top, step = 69, 8
    for row, bit in enumerate(bits):
        cy = y_top - row*step
        if bit == "1":
            rows.append(f'<rect x="8" y="{131-cy-2.6:.1f}" width="30" height="5.2" fill="#9E2B20"/>')
        else:
            rows.append(f'<rect x="8" y="{131-cy-2.6:.1f}" width="11.5" height="5.2" fill="#9E2B20"/>')
            rows.append(f'<rect x="26.5" y="{131-cy-2.6:.1f}" width="11.5" height="5.2" fill="#9E2B20"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-14 -12 80 142" width="430">
  <rect x="-14" y="-12" width="80" height="142" fill="#DDD2B4"/>
  <!-- 墨色牌身 + 颈 + 肩 -->
  <path d="M-20 131 L20 131 L23 53 L17 45 L-17 45 L-23 53 Z" fill="#2A2419"/>
  <rect x="-8" y="26" width="4.4" height="25" fill="#2A2419"/>
  <rect x="3.6" y="26" width="4.4" height="25" fill="#2A2419"/>
  <!-- 金：圆帽 / 横梁 -->
  <path d="M-8.5 28 A8.5 8.5 0 0 1 8.5 28 Z" fill="#8A6A2F"/>
  <rect x="-8.5" y="40" width="17" height="4" fill="#8A6A2F"/>
  <!-- 绳孔 -->
  <rect x="-3" y="28" width="6" height="12" fill="#DDD2B4"/>
  <!-- 金：边框 -->
  <rect x="-20.5" y="55.5" width="41" height="2.6" fill="#8A6A2F"/>
  <rect x="-17.5" y="128.4" width="35" height="2.6" fill="#8A6A2F"/>
  <polygon points="-19.3,127 -20.2,57.5 -17.6,57.3 -16.8,126.5" fill="#8A6A2F"/>
  <polygon points="19.3,127 20.2,57.5 17.6,57.3 16.8,126.5" fill="#8A6A2F"/>
  {''.join(rows)}
  <!-- 太极圆章 -->
  <circle cx="0" cy="116" r="9.5" fill="none" stroke="#8A6A2F" stroke-width="1.8"/>
  <circle cx="0" cy="116" r="8.5" fill="#E9DDBC"/>
  <path d="M0 107.5 A4.25 4.25 0 0 1 0 116 A4.25 4.25 0 0 0 0 124.5" fill="none" stroke="#2A2419" stroke-width="2.2"/>
  <circle cx="0" cy="111.75" r="1.3" fill="#9E2B20"/>
  <circle cx="0" cy="120.25" r="1.3" fill="#9E2B20"/>
  <text x="66" y="136" font-size="11" fill="#9E2B20" text-anchor="end" font-family="Kaiti SC,STKaiti,KaiTi,serif">{name} · 四色卦坠 · 绳孔 6×12mm</text>
</svg>'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--name")
    g.add_argument("--bits")
    g.add_argument("--index", type=int)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()

    if args.name:
        bits = HEX_BITS[HEX_NAMES.index(args.name)]
    elif args.bits:
        bits = args.bits
    else:
        bits = HEX_BITS[args.index - 1]

    idx = HEX_BITS.index(bits)
    name = HEX_NAMES[idx]
    parts = build_parts(bits, args.scale)
    os.makedirs(args.outdir, exist_ok=True)

    stl_path = os.path.join(args.outdir, f"卦坠_{name}_单色.stl")
    single_stl(parts, stl_path)

    from bambu_studio_ai.color import bambu_3mf
    v, f, lab = merged_arrays(parts)
    data = bambu_3mf.build_project(v, f, lab, PALETTE, f"卦坠 {name}")
    mf_path = os.path.join(args.outdir, f"卦坠_{name}_多色.3mf")
    with open(mf_path, "wb") as fh:
        fh.write(data)

    svg_preview(bits, os.path.join(args.outdir, f"预览_卦坠_{name}.svg"))

    ys = [t[1] for _, lb in parts for tr in _.tris for t in tr]
    print(f"第{idx+1}卦 {name}（{bits} 自下而上）")
    print(f"  多色工程：{mf_path}")
    print(f"  单色 STL：{stl_path}")
    print(f"  总三角形：{sum(len(m.tris) for m, _ in parts)}")
    print(f"  尺寸约：46×{115*args.scale:.0f}×6 mm（宽×高×厚，含圆帽）")

if __name__ == "__main__":
    main()
