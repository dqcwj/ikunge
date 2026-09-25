# -*- coding: utf-8 -*-
"""
交泰璧 · 出廓玉璧式卦坠（评审修订版）

形制出处：战国谷纹璧（窄缘宽谷纹带）+ 出廓璧（缘上方出廓作冠）+ 卦纹居心盘。
修订（依三评委意见）：
  - 撤联珠环（非玉璧语汇、与谷点净距仅0.5mm），改弦纹细环，净距≥1.3mm
  - 朱砂只留六爻与云头双目，点睛更纯
构造：z=0 贴床、背面平；基板 6mm + 浮雕 1.5mm，冠部全高 7.5mm。
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

class Mesh:
    def __init__(self):
        self.tris = []
    def add_tri(self, a, b, c):
        self.tris.append((a, b, c))
    def add_quad(self, a, b, c, d):
        self.add_tri(a, b, c); self.add_tri(a, c, d)
    def add_prism(self, poly, z0, z1):
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i+1) % n]
            self.add_quad((a[0],a[1],z0), (b[0],b[1],z0), (b[0],b[1],z1), (a[0],a[1],z1))
        for i in range(1, n-1):
            a, b, c = poly[0], poly[i], poly[i+1]
            self.add_tri((a[0],a[1],z1), (b[0],b[1],z1), (c[0],c[1],z1))
            self.add_tri((a[0],a[1],z0), (c[0],c[1],z0), (b[0],b[1],z0))
    def add_ring(self, r_in, r_out, z0, z1, n=32, phase=0.0):
        """环形（弧段四边形拼成）。phase 为起始角偏移；顶点按段取模回绕，首尾严格同点"""
        pin  = [(r_in*math.cos(phase+2*math.pi*i/n),  r_in*math.sin(phase+2*math.pi*i/n))  for i in range(n)]
        pout = [(r_out*math.cos(phase+2*math.pi*i/n), r_out*math.sin(phase+2*math.pi*i/n)) for i in range(n)]
        for i in range(n):
            ia, ib = pin[i], pin[(i+1) % n]
            oa, ob = pout[i], pout[(i+1) % n]
            # 闭合环面 = 外弧壁 + 内弧壁 + 顶底盖（整环无段间壁）
            self.add_quad((oa[0],oa[1],z0), (ob[0],ob[1],z0), (ob[0],ob[1],z1), (oa[0],oa[1],z1))   # 外弧壁
            self.add_quad((ib[0],ib[1],z0), (ia[0],ia[1],z0), (ia[0],ia[1],z1), (ib[0],ib[1],z1))   # 内弧壁
            self.add_quad((ia[0],ia[1],z0), (ib[0],ib[1],z0), (ob[0],ob[1],z0), (oa[0],oa[1],z0))
            self.add_quad((ia[0],ia[1],z1), (oa[0],oa[1],z1), (ob[0],ob[1],z1), (ib[0],ib[1],z1))
    def add_disc(self, cx, cy, r, z0, z1, n=40):
        self.add_prism([(cx+r*math.cos(2*math.pi*i/n), cy+r*math.sin(2*math.pi*i/n))
                        for i in range(n)], z0, z1)
    def add_eccentric_ring(self, oc, oR, hc, hr, z0, z1, n=24):
        """外圆心 oc 半径 oR、孔心 hc 半径 hr 的非同心环（孔偏向受力下方）"""
        ip = [(hc[0]+hr*math.cos(2*math.pi*i/n), hc[1]+hr*math.sin(2*math.pi*i/n)) for i in range(n)]
        op = [(oc[0]+oR*math.cos(2*math.pi*i/n), oc[1]+oR*math.sin(2*math.pi*i/n)) for i in range(n)]
        for i in range(n):
            i1, i2 = ip[i], ip[(i+1) % n]
            o1, o2 = op[i], op[(i+1) % n]
            # 闭合环面 = 外弧壁 + 内弧壁（顶底盖随后）
            self.add_quad((o1[0],o1[1],z0), (o2[0],o2[1],z0), (o2[0],o2[1],z1), (o1[0],o1[1],z1))   # 外弧壁
            self.add_quad((i2[0],i2[1],z0), (i1[0],i1[1],z0), (i1[0],i1[1],z1), (i2[0],i2[1],z1))   # 内弧壁
            self.add_quad((i1[0],i1[1],z0), (i2[0],i2[1],z0), (o2[0],o2[1],z0), (o1[0],o1[1],z0))
            self.add_quad((i1[0],i1[1],z1), (o1[0],o1[1],z1), (o2[0],o2[1],z1), (i2[0],i2[1],z1))
    def save_stl(self, path, name=b"jiaotaibi"):
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
                for v in (a, b, c): f.write(struct.pack("<3f", *v))
                f.write(struct.pack("<H", 0))

def build_parts(bits, s=1.0):
    parts = []
    def new(label):
        m = Mesh(); parts.append((m, label)); return m

    BASE, RELIEF = 6.0*s, 1.5*s        # 基板高 / 浮雕抬升
    R = 45*s                           # 璧半径
    # —— 基板：宣纸心盘 + 墨肉环（交接带 0.7mm，被分隔环覆埋）——
    core = new(IVORY); core.add_disc(0, 0, 28.6*s, 0, BASE)
    rou  = new(INK);   rou.add_ring(27.9*s, R, 0, BASE)

    # —— 浮雕层（各环相位错开，杜绝顶点重合）——
    rim  = new(GOLD);  rim.add_ring(41*s,  R,     BASE, BASE+RELIEF, n=32, phase=math.pi/32)      # 窄金缘带
    xian = new(GOLD);  xian.add_ring(37.9*s, 39.1*s, BASE, BASE+RELIEF, n=28, phase=math.pi/14)   # 弦纹细环
    gu   = new(GOLD)                                                      # 谷纹两环
    for rr in (35.5*s, 32.5*s):
        for k in range(40):
            a = 2*math.pi*k/40
            gu.add_disc(rr*math.cos(a), rr*math.sin(a), 1.1*s, BASE, BASE+RELIEF, 12)
    sep  = new(GOLD);  sep.add_ring(26.6*s, 30.6*s, BASE, BASE+RELIEF, n=36, phase=math.pi/36)  # 分隔环（覆埋接缝）

    # —— 六爻（朱砂，初爻在下）——
    yao = new(RED)
    for row, bit in enumerate(bits):
        cy = (17.5 - row*7)*s
        if bit == "1":
            yao.add_box(-14*s, cy-2*s, BASE, 14*s, cy+2*s, BASE+RELIEF)
        else:
            yao.add_box(-14*s, cy-2*s, BASE, -2.5*s, cy+2*s, BASE+RELIEF)
            yao.add_box(2.5*s,  cy-2*s, BASE, 14*s,  cy+2*s, BASE+RELIEF)

    # —— 出廓冠（全高）：主瓣非同心环承绳孔 + 双侧瓣 ——
    crown = new(GOLD)
    crown.add_eccentric_ring((0, -50.5*s), 9.5*s, (0, -52*s), 3.25*s, 0, BASE+RELIEF)
    crown.add_disc(-11.5*s, -46.5*s, 6.5*s, 0, BASE+RELIEF)
    crown.add_disc( 11.5*s, -46.5*s, 6.5*s, 0, BASE+RELIEF)
    eyes = new(RED)
    eyes.add_disc(-11.5*s, -46.5*s, 1.5*s, BASE+RELIEF, BASE+3*s, 12)
    eyes.add_disc( 11.5*s, -46.5*s, 1.5*s, BASE+RELIEF, BASE+3*s, 12)

    return parts

# 给 Mesh 补一个 add_box（复用同套正确绕序）
def _add_box(self, x0, y0, z0, x1, y1, z1):
    p = lambda x, y, z: (x, y, z)
    self.add_quad(p(x0,y0,z0), p(x0,y1,z0), p(x1,y1,z0), p(x1,y0,z0))
    self.add_quad(p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1))
    self.add_quad(p(x0,y0,z0), p(x0,y0,z1), p(x0,y1,z1), p(x0,y1,z0))
    self.add_quad(p(x1,y0,z0), p(x1,y1,z0), p(x1,y1,z1), p(x1,y0,z1))
    self.add_quad(p(x0,y0,z0), p(x1,y0,z0), p(x1,y0,z1), p(x0,y0,z1))
    self.add_quad(p(x0,y1,z0), p(x0,y1,z1), p(x1,y1,z1), p(x1,y1,z0))
Mesh.add_box = _add_box

def merged_arrays(parts):
    import numpy as np
    verts, faces, labels = [], [], []
    vi = 0
    for m, lab in parts:
        for a, b, c in m.tris:
            verts.extend((a, b, c)); faces.append((vi, vi+1, vi+2)); labels.append(lab); vi += 3
    return (np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64),
            np.array(labels, dtype=np.int64))

def svg_preview(bits, path):
    name = HEX_NAMES[HEX_BITS.index(bits)]
    k = 3.4                                # mm→px
    cx, cy = 225, 205                      # 璧心（y 向下翻转）
    P = lambda x, y: (cx + x*k, cy - y*k)
    def circle_svg(r, fill, extra=""):
        x, y = P(0, 0)
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*k:.1f}" fill="{fill}" {extra}/>'
    def ring_svg(r, w, color):
        return circle_svg(r, "none", f'stroke="{color}" stroke-width="{w*k:.1f}"')
    def circle_at(x, y, r, fill):
        px, py = P(x, y)
        return f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r*k:.1f}" fill="{fill}"/>'
    gu = "".join(circle_at(rr*math.cos(a), rr*math.sin(a), 1.1, "#8A6A2F")
                 for rr in (35.5, 32.5) for a in [2*math.pi*i2/40 for i2 in range(40)])
    rows = []
    for row, bit in enumerate(bits):
        cyy = 17.5 - row*7
        for x0, x1 in ([( -14, 14 )] if bit == "1" else [(-14, -2.5), (2.5, 14)]):
            px, py = P(x0, cyy+2)
            rows.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{(x1-x0)*k:.1f}" height="{4*k:.1f}" fill="#9E2B20"/>')
    # 冠
    def lobe(x, y, r):
        px, py = P(x, y)
        return f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r*k:.1f}" fill="#8A6A2F"/>'
    hole = circle_at(0, -52, 3.25, "#DDD2B4")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 430" width="450">
  <rect width="450" height="430" fill="#DDD2B4"/>
  {circle_svg(45, "#2A2419")}                       <!-- 墨肉（基板） -->
  {ring_svg(43, 4, "#8A6A2F")}                      <!-- 金缘带 -->
  {ring_svg(38.5, 1.2, "#8A6A2F")}                  <!-- 弦纹 -->
  {gu}                                              <!-- 谷纹两环 -->
  {ring_svg(28.6, 4, "#8A6A2F")}                    <!-- 分隔环 -->
  {circle_svg(26.6, "#E9DDBC")}                     <!-- 宣纸卦盘 -->
  {"".join(rows)}                                   <!-- 六爻 -->
  {lobe(0, -50.5, 9.5)}{lobe(-11.5, -46.5, 6.5)}{lobe(11.5, -46.5, 6.5)}
  {hole}                                            <!-- 穿绳孔 Ø6.5 -->
  {circle_at(-11.5, -46.5, 1.5, "#9E2B20")}{circle_at(11.5, -46.5, 1.5, "#9E2B20")}
  <text x="442" y="420" font-size="13" fill="#9E2B20" text-anchor="end" font-family="Kaiti SC,STKaiti,KaiTi,serif">交泰璧 · {name} · Ø90mm · 修订版（弦纹替联珠）</text>
</svg>'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--name"); g.add_argument("--bits"); g.add_argument("--index", type=int)
    ap.add_argument("--outdir", default="."); ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()
    bits = (HEX_BITS[HEX_NAMES.index(args.name)] if args.name
            else args.bits if args.bits else HEX_BITS[args.index-1])
    name = HEX_NAMES[HEX_BITS.index(bits)]
    parts = build_parts(bits, args.scale)
    os.makedirs(args.outdir, exist_ok=True)

    stl = os.path.join(args.outdir, f"交泰璧_{name}_单色.stl")
    m = Mesh()
    for pm, _ in parts: m.tris.extend(pm.tris)
    m.save_stl(stl, f"jiaotaibi {name}".encode())

    from bambu_studio_ai.color import bambu_3mf
    v, f, lab = merged_arrays(parts)
    mf = os.path.join(args.outdir, f"交泰璧_{name}_多色.3mf")
    with open(mf, "wb") as fh: fh.write(bambu_3mf.build_project(v, f, lab, PALETTE, f"交泰璧 {name}"))

    svg_preview(bits, os.path.join(args.outdir, f"预览_交泰璧_{name}.svg"))
    print(f"{name}（{bits} 自下而上）")
    print(f"  多色工程: {mf}")
    print(f"  单色 STL: {stl}")
    print(f"  三角形: {sum(len(x.tris) for x,_ in parts)}")
    print(f"  尺寸: Ø{90*args.scale:.0f} × 高{105*args.scale:.0f} × 厚7.5mm")

if __name__ == "__main__":
    main()
