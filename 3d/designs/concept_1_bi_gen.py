# -*- coding: utf-8 -*-
"""
交泰璧 —— 泰卦·出廓谷纹璧 挂坠正视图生成器
坐标系：原点=璧心，mm 真实尺寸，y 轴向下（SVG 惯例）。
谱系：战国谷纹璧（窄缘+宽谷纹带）+ 出廓璧（冠部出廓）+ 明清卦纹璧（卦爻居盘）。
"""
import math
import xml.etree.ElementTree as ET

OUT = r"D:\审美\3d\designs\concept_1_bi.svg"

INK, GOLD, RED, PAPER, BG = "#2A2419", "#8A6A2F", "#9E2B20", "#E9DDBC", "#DDD2B4"
FONT = "Serif, 'Noto Serif SC', 'Songti SC', 'Microsoft YaHei', serif"

# ---------------- 参数（单位 mm，全部为 0.5 的整数倍） ----------------
R_DISC   = 45.0   # 璧外缘
R_RIM_IN = 41.0   # 鎏金缘带内缘（带宽 4）
R_DIV_OUT= 29.5   # 鎏金分隔环外缘（环宽 2.5）
R_MED    = 27.0   # 宣纸卦盘半径（Ø54）

BEAD_RING_R, BEAD_R, N_BEAD = 38.5, 1.4, 44     # 联珠：Ø2.8，44 颗，节距 5.5
DOT_ROWS, DOT_R, N_DOT = (35.5, 32.5), 1.1, 40  # 谷纹：Ø2.2，2 环×40 列（9° 一列）

LOBE_R,  LOBE_CY  = 9.5, -50.5    # 出廓主瓣（云头中弧）
SIDE_DX, SIDE_DY, SIDE_R = 11.5, -46.5, 6.5  # 出廓侧瓣（云头侧弧）×2
HOLE_R,  HOLE_CY  = 3.25, -52.0   # 穿绳孔 Ø6.5（≥5）
SIDE_DOT_R = 1.5                  # 侧瓣朱砂点睛 Ø3

BAR_W, BAR_T, BAR_G, YIN_GAP = 28.0, 4.0, 3.0, 5.0   # 爻宽/爻厚/爻距/阴爻断口
LINES_BOTTOM_UP = [1, 1, 1, 0, 0, 0]                  # 泰 111000：下三阳上三阴

STACK_HALF = (6 * BAR_T + 5 * BAR_G) / 2.0            # = 19.5
YIN_SEG = (BAR_W - YIN_GAP) / 2.0                     # = 11.5

def f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"

# ---------------- 图元 ----------------
E = []
E.append(f'<rect x="-53" y="-68" width="106" height="125" fill="{BG}"/>')

# 出廓云头冠（鎏金，先画，被璧体叠压的部分颜色一致）
E.append(f'<circle cx="0"   cy="{f(LOBE_CY)}"  r="{f(LOBE_R)}" fill="{GOLD}"/>')
for sx in (-1, 1):
    E.append(f'<circle cx="{f(sx*SIDE_DX)}" cy="{f(SIDE_DY)}" r="{f(SIDE_R)}" fill="{GOLD}"/>')

# 璧体：金缘（Ø90）→ 墨肉（Ø82）→ 金隔环（Ø59）→ 宣纸卦盘（Ø54）
E.append(f'<circle cx="0" cy="0" r="{f(R_DISC)}"    fill="{GOLD}"/>')
E.append(f'<circle cx="0" cy="0" r="{f(R_RIM_IN)}"  fill="{INK}"/>')
E.append(f'<circle cx="0" cy="0" r="{f(R_DIV_OUT)}" fill="{GOLD}"/>')
E.append(f'<circle cx="0" cy="0" r="{f(R_MED)}"     fill="{PAPER}"/>')

# 联珠纹（朱砂，44 颗，正上方起针）
for k in range(N_BEAD):
    a = math.radians(90.0 + k * 360.0 / N_BEAD)
    E.append(f'<circle cx="{f(BEAD_RING_R*math.cos(a))}" cy="{f(-BEAD_RING_R*math.sin(a))}" '
             f'r="{f(BEAD_R)}" fill="{RED}"/>')

# 谷纹（鎏金阳点，2 环 × 40 列，径向对位）
for rr in DOT_ROWS:
    for k in range(N_DOT):
        a = math.radians(90.0 + k * 360.0 / N_DOT)
        E.append(f'<circle cx="{f(rr*math.cos(a))}" cy="{f(-rr*math.sin(a))}" '
                 f'r="{f(DOT_R)}" fill="{GOLD}"/>')

# 六爻（朱砂，初爻在下：下三阳整条，上三阴两段）
for i, yang in enumerate(LINES_BOTTOM_UP):
    cy = STACK_HALF - BAR_T / 2.0 - i * (BAR_T + BAR_G)
    if yang:
        E.append(f'<rect x="{f(-BAR_W/2)}" y="{f(cy-BAR_T/2)}" width="{f(BAR_W)}" '
                 f'height="{f(BAR_T)}" rx="0.8" fill="{RED}"/>')
    else:
        for sx in (-1, 1):
            x0 = sx * (YIN_GAP / 2.0) if sx > 0 else -BAR_W / 2.0
            x0 = (YIN_GAP / 2.0) if sx > 0 else (-BAR_W / 2.0)
            E.append(f'<rect x="{f(x0)}" y="{f(cy-BAR_T/2)}" width="{f(YIN_SEG)}" '
                     f'height="{f(BAR_T)}" rx="0.8" fill="{RED}"/>')

# 冠部点睛与穿绳孔
for sx in (-1, 1):
    E.append(f'<circle cx="{f(sx*SIDE_DX)}" cy="{f(SIDE_DY)}" r="{f(SIDE_DOT_R)}" fill="{RED}"/>')
E.append(f'<circle cx="0" cy="{f(HOLE_CY)}" r="{f(HOLE_R)}" fill="{BG}"/>')  # 通孔透背景

# 题注与图例
E.append(f'<text x="0" y="49.8" text-anchor="middle" font-family="{FONT}" font-size="3.6" '
         f'fill="{INK}" letter-spacing="0.4">泰卦 · 乾下坤上 · 天地交泰 —— Ø90 × 高105 × 厚6 mm · 浮雕 +1.5</text>')
E.append(f'<text x="0" y="54.2" text-anchor="middle" font-family="{FONT}" font-size="3.2">'
         f'<tspan fill="{INK}">■墨·璧肉 </tspan><tspan fill="{GOLD}">■鎏金·缘冠 </tspan>'
         f'<tspan fill="{RED}">■朱砂·爻珠 </tspan><tspan fill="{PAPER}">■宣纸·卦盘</tspan></text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="495" '
       f'viewBox="-53 -68 106 125">\n<title>交泰璧 · 泰卦出廓谷纹璧</title>\n'
       + "\n".join(E) + "\n</svg>\n")

with open(OUT, "w", encoding="utf-8") as fp:
    fp.write(svg)
ET.parse(OUT)  # 合法性校验

# ---------------- 自检 ----------------
def lens(r1, r2, d):
    if d >= r1 + r2 or d <= abs(r1 - r2):
        return 0.0
    a1 = math.acos((d*d + r1*r1 - r2*r2) / (2*d*r1))
    a2 = math.acos((d*d + r2*r2 - r1*r1) / (2*d*r2))
    t = (-d+r1+r2)*(d+r1-r2)*(d-r1+r2)*(d+r1+r2)
    return r1*r1*a1 + r2*r2*a2 - 0.5*math.sqrt(max(t, 0.0))

d_cs = math.hypot(SIDE_DX, LOBE_CY - SIDE_DY)      # 主瓣-侧瓣
d_cd = abs(LOBE_CY)                                 # 主瓣-璧心
d_sd = math.hypot(SIDE_DX, SIDE_DY)                 # 侧瓣-璧心
crest = (math.pi*LOBE_R**2 + 2*math.pi*SIDE_R**2 - math.pi*HOLE_R**2
         - 2*lens(LOBE_R, SIDE_R, d_cs)
         - lens(LOBE_R, R_DISC, d_cd) - 2*lens(SIDE_R, R_DISC, d_sd))
gold = (math.pi*(R_DISC**2 - R_RIM_IN**2) + math.pi*(R_DIV_OUT**2 - R_MED**2)
        + 2*N_DOT*math.pi*DOT_R**2 + max(crest, 0))
ink  = math.pi*(R_RIM_IN**2 - R_DIV_OUT**2)
red  = (3*BAR_W*BAR_T + 3*2*YIN_SEG*BAR_T + N_BEAD*math.pi*BEAD_R**2
        + 2*math.pi*SIDE_DOT_R**2)
paper = math.pi*R_MED**2 - (3*BAR_W + 3*2*YIN_SEG)*BAR_T
tot = ink + gold + red + paper
print("SVG OK ->", OUT, len(svg), "bytes")
print(f"面积占比  墨 {ink/tot:.1%} | 鎏金 {gold/tot:.1%} | 宣纸 {paper/tot:.1%} | 朱砂 {red/tot:.1%}")
wall = (HOLE_CY - HOLE_R) - (LOBE_CY - LOBE_R)
print(f"总高 {R_DISC + (abs(LOBE_CY)+LOBE_R):.1f}mm  宽 {2*R_DISC}mm  孔径 {2*HOLE_R}mm  孔上壁厚 {wall:.2f}mm")
print(f"半径阶梯 45/41/38.5/35.5/32.5/29.5/27  爻栈 {2*STACK_HALF} 角距盘缘 {R_MED-math.hypot(BAR_W/2, STACK_HALF):.2f}mm")
ang = lambda n: {(round(math.cos(math.radians(90+k*360/n)),6), round(math.sin(math.radians(90+k*360/n)),6)) for k in range(n)}
for n in (N_BEAD, N_DOT):
    s = ang(n)
    assert all((x, -y) in s for (x, y) in s), "对称性失败"
print("左右对称自检：联珠/谷纹角集合闭合于镜像轴 ✓")
