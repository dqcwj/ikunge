/* 量宅 · 形煞几何判定引擎（M2）
 * 输入坐标系：canvas 像素、y 向下、正上方为北（北向上户型图）
 * 规则来源：多源考证 + 交叉校验（2026-09），阈值见各规则注释
 */
(function (root) {
  "use strict";
  const XS = {};

  /* ---------- 几何基础 ---------- */
  XS.pip = function (pt, poly) {                     // 射线法点在多边形内
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
      if ((yi > pt[1]) !== (yj > pt[1]) &&
          pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  };
  XS.dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  XS.segInsidePoly = function (a, b, poly, samples) {   // 采样点全在多边形内 ⇒ 中间无墙
    const n = samples || 24;
    for (let i = 1; i < n; i++) {
      const t = i / n;
      if (!XS.pip([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], poly)) return false;
    }
    return true;
  };
  XS.polygonArea = poly => Math.abs(poly.reduce((s, p, i) => {
    const q = poly[(i + 1) % poly.length];
    return s + p[0] * q[1] - q[0] * p[1];
  }, 0)) / 2;

  /* 点到线段距离 + 最近墙的内法线（开口贴墙朝向用） */
  const distToSeg = (p, a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
    return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
  };
  XS.inwardNormal = function (poly, pt) {
    let best = null, bd = Infinity;
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length];
      const d = distToSeg(pt, a, b);
      if (d < bd) { bd = d; best = [a, b]; }
    }
    const [a, b] = best;
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
    let nx = -dy / L, ny = dx / L;                      // 两个候选法线之一
    if (!XS.pip([pt[0] + nx * 3, pt[1] + ny * 3], poly)) { nx = -nx; ny = -ny; }
    return [nx, ny];
  };
  XS.nearestEdgeDist = function (poly, pt) {
    let bd = Infinity;
    for (let i = 0; i < poly.length; i++) {
      bd = Math.min(bd, distToSeg(pt, poly[i], poly[(i + 1) % poly.length]));
    }
    return bd;
  };
  const facing = (poly, o, target) => {                 // 贴墙开口：连线须顺墙法线（±41°）；室内开口不校验
    if (XS.nearestEdgeDist(poly, [o.x, o.y]) > 30) return true;
    const n = XS.inwardNormal(poly, [o.x, o.y]);
    const dx = target[0] - o.x, dy = target[1] - o.y, L = Math.hypot(dx, dy) || 1;
    return (dx / L) * n[0] + (dy / L) * n[1] >= 0.75;
  };

  /* ---------- 九宫分格（北向上） ---------- */
  /* 行列到宫位：canvas y 向下，顶行=北。
     乾(西北) 坎(北) 艮(东北)
     兑(西)    中宫    震(东)
     坤(西南) 离(南) 巽(东南) */
  const GRID_PALACE = [["乾", "坎", "艮"], ["兑", "中", "震"], ["坤", "离", "巽"]];
  const PALACE_REN = {   // 宫位人事映射（后天八卦家人位，缺角影响之传统说法）
    "乾": "西北 · 老父 · 首", "坎": "正北 · 中男 · 耳", "艮": "东北 · 少男 · 手",
    "震": "正东 · 长男 · 足", "巽": "东南 · 长女 · 股", "离": "正南 · 中女 · 目",
    "坤": "西南 · 老母 · 腹", "兑": "正西 · 少女 · 口"
  };
  XS.PALACE_REN = PALACE_REN;
  XS.nineGrid = function (poly) {
    const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const cw = (x1 - x0) / 3, ch = (y1 - y0) / 3;
    const cells = {};
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
      const palace = GRID_PALACE[r][c];
      let inN = 0;
      for (let i = 0; i <= 5; i++) for (let j = 0; j <= 5; j++) {
        if (XS.pip([x0 + c * cw + (cw * (i + 0.5)) / 6, y0 + r * ch + (ch * (j + 0.5)) / 6], poly)) inN++;
      }
      cells[palace] = inN / 36;
    }
    return cells;
  };

  /* ---------- 矩形工具（床/梁，axis-aligned） ---------- */
  const rectOverlap = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) *
                              Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  const bedThirds = bed => {                          // 床三区：头/身/脚（按 headDir）
    const t = { head: {}, mid: {}, foot: {} };
    if (bed.head === "left" || bed.head === "right") {
      const w3 = bed.w / 3, from = bed.head === "left" ? 0 : bed.w;
      const seg = (k) => ({ x: bed.x + (bed.head === "left" ? w3 * k : bed.w - w3 * (k + 1)), y: bed.y, w: w3, h: bed.h });
      t.head = seg(0); t.mid = seg(1); t.foot = seg(2);
    } else {
      const h3 = bed.h / 3, top = bed.head !== "down";
      const seg = (k) => ({ x: bed.x, y: bed.y + (top ? h3 * k : bed.h - h3 * (k + 1)), w: bed.w, h: h3 });
      t.head = seg(0); t.mid = seg(1); t.foot = seg(2);
    }
    return t;
  };
  const rectCenter = r => [r.x + r.w / 2, r.y + r.h / 2];

  /* ---------- 主判定 ---------- */
  /* data = { poly, pxPerMeter, openings:[{type,x,y}], items:[{type,x,y,w,h,head}] }
     openings.type: entry 入户门 / door 内门 / window 窗 / balcony 阳台门落地窗 / elevator 电梯
     items.type:    bed 床 / stove 灶 / toilet 厕 / mirror 镜 / beam 梁          */
  XS.check = function (data) {
    const F = [];                                       // findings
    const add = (id, name, sev, detail, remedy) => F.push({ id, name, severity: sev, detail, remedy });
    if (!data.poly || data.poly.length < 3) return { findings: [{ id: "nopoly", name: "尚未画出户型", severity: 0, detail: "请先在户型页画出房屋轮廓", remedy: "" }] };
    const m = data.pxPerMeter || 20;
    const poly = data.poly;
    const ops = data.openings || [];
    const items = data.items || [];
    const entry = ops.find(o => o.type === "entry");

    /* R1 穿堂煞：入户门与通外开口直线贯通且互朝对方（±41°） */
    if (entry) {
      for (const o of ops) {
        if (o === entry) continue;
        if ((o.type === "balcony" || o.type === "window") &&
            XS.segInsidePoly([entry.x, entry.y], [o.x, o.y], poly) &&
            facing(poly, entry, [o.x, o.y]) && facing(poly, o, [entry.x, entry.y])) {
          add("chuantang", "穿堂煞", 2,
              `入户门与${o.type === "balcony" ? "阳台门" : "外窗"}直线相通，气穿堂而过（判定：连线全程在室内、无墙遮挡）`,
              "设玄关或不透光屏风、顶天鞋柜遮挡，使气迂回");
        }
      }
      /* R7 开口煞：入户门正对电梯 */
      for (const o of ops) {
        if (o.type === "elevator" && XS.dist([entry.x, entry.y], [o.x, o.y]) / m <= 5 &&
            XS.segInsidePoly([entry.x, entry.y], [o.x, o.y], poly) &&
            facing(poly, entry, [o.x, o.y]) && facing(poly, o, [entry.x, entry.y])) {
          add("kaikou", "开口煞", 2, "入户门正对电梯门（距离五米内且视线相通）", "门内设屏风或加高门槛");
        }
      }
    }

    /* R2 门冲煞：两门互朝对方且净距 ≤3m（连线在室内） */
    const doors = ops.filter(o => o.type === "entry" || o.type === "door");
    for (let i = 0; i < doors.length; i++) for (let j = i + 1; j < doors.length; j++) {
      const a = doors[i], b = doors[j];
      const d = XS.dist([a.x, a.y], [b.x, b.y]) / m;
      if (d <= 3 && XS.segInsidePoly([a.x, a.y], [b.x, b.y], poly) &&
          facing(poly, a, [b.x, b.y]) && facing(poly, b, [a.x, a.y])) {
        add("menchong", "门冲煞", 2, `两门相对（${(d).toFixed(1)} 米，视线相通）`, "挂过半门帘，或常闭其一");
      }
    }

    /* R3 缺角：九宫覆盖 <90% 记轻缺，<80% 记重缺 */
    const grid = XS.nineGrid(poly);
    for (const palace of Object.keys(grid)) {
      if (palace === "中") continue;
      const cov = grid[palace];
      if (cov < 0.8) add("quejiao", `缺角 · ${palace}宫`, 3,
        `${PALACE_REN[palace]}，该宫缺失约 ${Math.round((1 - cov) * 100)}%（重缺）`, "按方位五行酌补，或置屏景点缀");
      else if (cov < 0.9) add("quejiao", `缺角 · ${palace}宫`, 1,
        `${PALACE_REN[palace]}，该宫缺失约 ${Math.round((1 - cov) * 100)}%（轻缺）`, "轻缺可不论，保持整洁明亮");
    }

    /* R6 厨厕占中宫 */
    const centerRect = p2 => {
      const xs = p2.map(p => p[0]), ys = p2.map(p => p[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      const cw = (x1 - x0) / 3, ch = (y1 - y0) / 3;
      return [[x0 + cw, y0 + ch], [x0 + 2 * cw, y0 + ch], [x0 + 2 * cw, y0 + 2 * ch], [x0 + cw, y0 + 2 * ch]];
    };
    const C = centerRect(poly);
    for (const it of items) {
      if (it.type === "toilet" && XS.pip([it.x, it.y], C))
        add("zhonggong", "厕占中宫", 3, "卫生间落在房屋中宫（污秽居心，主流视为难化之局）", "保持干洁恒燥；条件允许宜改他用");
      if (it.type === "stove" && XS.pip([it.x, it.y], C))
        add("zhonggong", "灶压中宫", 2, "厨房落在房屋中宫（火烧心）", "注意通风与用火安全，门口常掩");
    }

    /* R4 梁压床/沙发：梁投影与床三区重叠面积最大者定级（并列取靠头）；沙发压到即中 */
    const beds = items.filter(i => i.type === "bed");
    const sofas = items.filter(i => i.type === "sofa");
    const beams = items.filter(i => i.type === "beam");
    for (const bed of beds) for (const beam of beams) {
      if (rectOverlap(bed, beam) <= 0) continue;
      const t = bedThirds(bed);
      const areas = [["压床头", rectOverlap(t.head, beam), 3], ["压床身", rectOverlap(t.mid, beam), 2], ["压床尾", rectOverlap(t.foot, beam), 1]];
      areas.sort((a, b) => b[1] - a[1]);
      add("liangya", "横梁压顶", areas[0][2], `梁与床重叠，取重叠最大区定级：${areas[0][0]}`, "移床避梁，或吊顶包梁、加高床头板");
    }
    for (const sofa of sofas) for (const beam of beams) {
      if (rectOverlap(sofa, beam) <= 0) continue;
      add("liangya", "横梁压顶", 2, "梁正压沙发常坐区", "移沙发避梁，或吊顶包梁");
    }

    /* R5 镜对床：镜在三米内且大致朝床（朝向需人工确认） */
    for (const bed of beds) for (const mir of items.filter(i => i.type === "mirror")) {
      const d = XS.dist(rectCenter(bed), [mir.x, mir.y]) / m;
      if (d <= 3) add("jingchuang", "镜子对床", d < 2 ? 3 : 2,
        `镜距床约 ${d.toFixed(1)} 米（请确认镜面确朝床身）`, "调整镜角、改镜柜或以布帘遮之");
    }

    F.sort((a, b) => b.severity - a.severity);
    return { findings: F, grid: grid, areaM2: XS.polygonArea(poly) / (m * m) };
  };

  /* ---------- 自检 ---------- */
  XS.runTests = function (log) {
    const L = log || console.log.bind(console);
    let pass = 0, fail = 0;
    const eq = (name, got, want) => { const ok = got === want; ok ? pass++ : fail++; if (!ok) L(`  ✗ ${name} got=${got} want=${want}`); };
    const m = 10;                                   // 10px = 1m
    const rect = [[0, 0], [600, 0], [600, 600], [0, 600]];   // 60m? no: 60px=6m 边长，够用
    /* 穿堂：入户门在下边中点，窗在上边中点 */
    let r = XS.check({ poly: rect, pxPerMeter: m,
      openings: [{ type: "entry", x: 300, y: 590 }, { type: "window", x: 300, y: 10 }] });
    eq("穿堂煞判定", r.findings.some(f => f.id === "chuantang"), true);
    /* 无穿堂：门与窗错位（连线出墙） */
    r = XS.check({ poly: rect, pxPerMeter: m,
      openings: [{ type: "entry", x: 60, y: 590 }, { type: "window", x: 590, y: 60 }] });
    eq("斜连线不判穿堂", r.findings.some(f => f.id === "chuantang"), false);
    /* 门冲：两门 2m 相对 */
    r = XS.check({ poly: rect, pxPerMeter: m,
      openings: [{ type: "door", x: 200, y: 300 }, { type: "door", x: 220, y: 300 }] });
    eq("门冲判定", r.findings.some(f => f.id === "menchong"), true);
    /* L 形缺东北角（艮） */
    const lshape = [[0, 0], [400, 0], [400, 200], [600, 200], [600, 600], [0, 600]];
    r = XS.check({ poly: lshape, pxPerMeter: m, openings: [] });
    const qj = r.findings.filter(f => f.id === "quejiao");
    eq("L形判缺角", qj.length > 0, true);
    eq("缺的是艮宫", qj.some(f => f.name.includes("艮")), true);
    /* 厕占中宫 */
    r = XS.check({ poly: rect, pxPerMeter: m, openings: [], items: [{ type: "toilet", x: 300, y: 300 }] });
    eq("厕占中宫", r.findings.some(f => f.id === "zhonggong" && f.name.includes("厕")), true);
    /* 梁压床头：床头朝上，梁压上1/3 */
    r = XS.check({ poly: rect, pxPerMeter: m, openings: [],
      items: [{ type: "bed", x: 100, y: 100, w: 150, h: 200, head: "up" },
              { type: "beam", x: 60, y: 120, w: 300, h: 30 }] });
    const ly = r.findings.find(f => f.id === "liangya");
    eq("梁压顶判定", !!ly, true);
    eq("压床头定级3", ly ? ly.severity : 0, 3);
    /* 梁压沙发 */
    r = XS.check({ poly: rect, pxPerMeter: m, openings: [],
      items: [{ type: "sofa", x: 100, y: 100, w: 180, h: 90 },
              { type: "beam", x: 60, y: 120, w: 300, h: 30 }] });
    const ls = r.findings.find(f => f.id === "liangya");
    eq("梁压沙发判定", !!ls && ls.severity === 2, true);
    /* 几何基础 */
    eq("点在多边形内", XS.pip([300, 300], rect), true);
    eq("点在多边形外", XS.pip([700, 300], rect), false);
    L(`形煞引擎：通过 ${pass}，失败 ${fail}`);
    return fail === 0;
  };

  if (typeof module !== "undefined" && module.exports) module.exports = XS;
  else root.XS = XS;
  if (typeof require !== "undefined" && require.main === module) XS.runTests();
})(typeof window !== "undefined" ? window : globalThis);
