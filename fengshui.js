/* 玄機閣 · 风水引擎 M1（八宅 + 玄空飞星下卦）
 * 规则经多源考证与双路交叉校验（2026-09）：
 *  - 命卦：立春分界 + 统一式（男 11-数根 / 女 4+数根），余5男寄坤女寄艮；38 行逐年锚点验证
 *  - 八宅八星：变爻 XOR 法（与大游年歌 64 格一致；矩阵对称；每行皆为八星排列）
 *  - 玄空飞星下卦：运盘顺飞；山星/向星入中顺逆查「入中星本宫同元龙」阴阳；含三张已验证盘
 */
(function (root) {
  "use strict";

  const FS = {};

  /* ---------- 基础表 ---------- */
  const GUA_NAME = { 1: "坎", 2: "坤", 3: "震", 4: "巽", 6: "乾", 7: "兑", 8: "艮", 9: "离" };
  const GUA_DIR = { "坎": "北", "坤": "西南", "震": "东", "巽": "东南", "乾": "西北", "兑": "西", "艮": "东北", "离": "南" };
  const EAST4 = ["坎", "震", "巽", "离"];                       // 东四（宅/命）
  /* 三爻编码（初,中,上） */
  const TRI = { "乾": [1, 1, 1], "坎": [0, 1, 0], "艮": [0, 0, 1], "震": [1, 0, 0],
                "巽": [0, 1, 1], "离": [1, 0, 1], "坤": [0, 0, 0], "兑": [1, 1, 0] };
  /* 变爻 → 八星（d0d1d2 二进制键） */
  const DIFF_STAR = { 0: "伏位", 1: "生气", 2: "绝命", 4: "祸害", 3: "五鬼", 6: "天医", 5: "六煞", 7: "延年" };
  const STAR_GRADE = { "生气": 4, "延年": 3, "天医": 2, "伏位": 1, "祸害": -1, "六煞": -2, "五鬼": -3, "绝命": -4 };
  const STAR_DESC = {
    "生气": "贪狼木星，大吉。生机勃发之方，宜开门、主卧、书房。",
    "延年": "武曲金星，次吉。和谐长久之方，宜夫妻主卧、长辈房。",
    "天医": "巨门土星，中吉。康宁安泰之方，宜卧房、餐厅。",
    "伏位": "辅弼木星，小吉。平稳守成之方，宜神位、书房。",
    "祸害": "禄存土星，小凶。琐碎损耗之方，宜储物、厨房压之。",
    "六煞": "文曲水星，中凶。口舌纷扰之方，宜卫生间压之。",
    "五鬼": "廉贞火星，次凶。是非火厄之方，宜厨房（以火压火）或储物。",
    "绝命": "破军金星，至凶。伤病冲克之方，宜卫生间、储物压之，忌开门安居。"
  };

  /* ---------- 命卦 ---------- */
  /* 立春按 2月4日 近似（与站内八字模块一致）；2月3-5日出生者提示可能一年之差 */
  function adjustedYear(y, m, d) { return (m < 2 || (m === 2 && d < 4)) ? y - 1 : y; }
  function digitalRoot(n) {
    let s = n;
    while (s > 9) s = String(s).split("").reduce((a, c) => a + Number(c), 0);
    return s;
  }
  FS.mingGua = function (y, m, d, male) {
    const Y = adjustedYear(y, m, d);
    const S = digitalRoot(Y);
    let n = male ? (11 - S === 10 ? 1 : 11 - S) : (4 + S >= 10 ? 4 + S - 9 : 4 + S);
    if (n === 5) n = male ? 2 : 8;                 // 五黄：男寄坤，女寄艮
    const gua = GUA_NAME[n];
    return { year: Y, num: n, gua: gua, dir: GUA_DIR[gua], group: EAST4.includes(gua) ? "东四命" : "西四命" };
  };

  /* ---------- 八宅八星（变爻法） ---------- */
  FS.starOf = function (zhaiGua, dirGua) {
    const a = TRI[zhaiGua], b = TRI[dirGua];
    const key = ((a[0] ^ b[0]) << 2) | ((a[1] ^ b[1]) << 1) | (a[2] ^ b[2]);
    return DIFF_STAR[key];
  };
  FS.starsOf = function (zhaiGua) {
    const out = {};
    Object.keys(TRI).forEach(d => { out[d] = d === zhaiGua ? "伏位" : FS.starOf(zhaiGua, d); });
    return out;
  };

  /* ---------- 玄空飞星（下卦） ---------- */
  const POS = ["中", "乾", "兑", "艮", "离", "坎", "坤", "震", "巽"];      // 飞泊路径
  const HOME = { 1: "坎", 2: "坤", 3: "震", 4: "巽", 6: "乾", 7: "兑", 8: "艮", 9: "离" };
  const LUOSHU = { "坎": 1, "坤": 2, "震": 3, "巽": 4, "乾": 6, "兑": 7, "艮": 8, "离": 9 };
  const PALACE = { "坎": ["壬", "子", "癸"], "艮": ["丑", "艮", "寅"], "震": ["甲", "卯", "乙"],
                   "巽": ["辰", "巽", "巳"], "离": ["丙", "午", "丁"], "坤": ["未", "坤", "申"],
                   "兑": ["庚", "酉", "辛"], "乾": ["戌", "乾", "亥"] };
  const OPP_PALACE = { "坎": "离", "离": "坎", "艮": "坤", "坤": "艮", "震": "兑", "兑": "震", "巽": "乾", "乾": "巽" };
  const OPP_MTN = { "壬": "丙", "子": "午", "癸": "丁", "丑": "未", "艮": "坤", "寅": "申",
                    "甲": "庚", "卯": "酉", "乙": "辛", "辰": "戌", "巽": "乾", "巳": "亥",
                    "丙": "壬", "午": "子", "丁": "癸", "未": "丑", "坤": "艮", "申": "寅",
                    "庚": "甲", "酉": "卯", "辛": "乙", "戌": "辰", "乾": "巽", "亥": "巳" };
  const GRID = [["巽", "离", "坤"], ["震", "中", "兑"], ["艮", "坎", "乾"]];   // 上南下北地图式
  const norm = n => ((n - 1) % 9 + 9) % 9 + 1;
  const fly = (center, forward) => {
    const out = {};
    POS.forEach((p, k) => { out[p] = norm(center + (forward ? k : -k)); });
    return out;
  };
  const yang = (palace, idx) => LUOSHU[palace] % 2 === 1 ? idx === 0 : idx >= 1;
  FS.periodOf = year => Math.floor(((year - 1864) % 180) / 20) + 1;
  FS.mountainPalace = m => {
    for (const p of Object.keys(PALACE)) {
      const i = PALACE[p].indexOf(m);
      if (i >= 0) return { palace: p, idx: i };
    }
    return null;
  };
  FS.feiXing = function (year, sitting) {
    const sp = FS.mountainPalace(sitting);
    if (!sp) throw new Error("未知坐山：" + sitting);
    const fp = { palace: OPP_PALACE[sp.palace], idx: PALACE[OPP_PALACE[sp.palace]].indexOf(OPP_MTN[sitting]) };
    const P = FS.periodOf(year);
    const yun = fly(P, true);
    const M = yun[sp.palace], F = yun[fp.palace];
    const dirOf = (star, idx, srcPalace) => yang(star === 5 ? srcPalace : HOME[star], idx);
    const shan = fly(M, dirOf(M, sp.idx, sp.palace));
    const xiang = fly(F, dirOf(F, fp.idx, fp.palace));
    /* 局型判定：看当运星 P 落在山星盘/向星盘的坐向宫 */
    const sAtSit = shan[sp.palace], sAtFace = shan[fp.palace];
    const xAtSit = xiang[sp.palace], xAtFace = xiang[fp.palace];
    let pattern = "平和之局";
    if (sAtSit === P && xAtFace === P) pattern = "旺山旺向（到山到向，丁财两旺）";
    else if (sAtFace === P && xAtSit === P) pattern = "上山下水（山颠水倒，宜调整）";
    else if (sAtSit === P && xAtSit === P) pattern = "双星会坐（旺丁不旺财，宜坐空朝满）";
    else if (sAtFace === P && xAtFace === P) pattern = "双星会向（旺财不旺丁，宜向首开阔）";
    return { period: P, sitting: sitting, facing: OPP_MTN[sitting],
             sitPalace: sp.palace, facePalace: fp.palace,
             yun: yun, shan: shan, xiang: xiang, pattern: pattern };
  };
  FS.GRID = GRID;
  FS.STAR_GRADE = STAR_GRADE;
  FS.STAR_DESC = STAR_DESC;
  FS.GUA_DIR = GUA_DIR;
  FS.OPP_MTN = OPP_MTN;
  FS.EAST4 = EAST4;

  /* ---------- 自检（node 直接运行） ---------- */
  FS.runTests = function (log) {
    const L = log || console.log.bind(console);
    let pass = 0, fail = 0;
    const eq = (name, got, want) => {
      const canon = v => JSON.stringify(v, Object.keys(v || {}).sort());
      const ok = canon(got) === canon(want);
      ok ? pass++ : fail++;
      if (!ok) L("  ✗ " + name + " got=" + JSON.stringify(got) + " want=" + JSON.stringify(want));
    };
    /* 1) 命卦锚点年表（考证表3，38 行） */
    const anchors = {
      1988: ["震", "震"], 1989: ["坤", "巽"], 1990: ["坎", "艮"], 1991: ["离", "乾"],
      1992: ["艮", "兑"], 1993: ["兑", "艮"], 1994: ["乾", "离"], 1995: ["坤", "坎"],
      1996: ["巽", "坤"], 1997: ["震", "震"], 1998: ["坤", "巽"], 1999: ["坎", "艮"],
      2000: ["离", "乾"], 2001: ["艮", "兑"], 2002: ["兑", "艮"], 2003: ["乾", "离"],
      2004: ["坤", "坎"], 2005: ["巽", "坤"], 2006: ["震", "震"], 2007: ["坤", "巽"],
      2008: ["坎", "艮"], 2009: ["离", "乾"], 2010: ["艮", "兑"], 2011: ["兑", "艮"],
      2012: ["乾", "离"], 2013: ["坤", "坎"], 2014: ["巽", "坤"], 2015: ["震", "震"],
      2016: ["坤", "巽"], 2017: ["坎", "艮"], 2018: ["离", "乾"], 2019: ["艮", "兑"],
      2020: ["兑", "艮"], 2021: ["乾", "离"], 2022: ["坤", "坎"], 2023: ["巽", "坤"],
      2024: ["震", "震"], 2025: ["坤", "巽"]
    };
    L("命卦 38 行锚点：");
    for (const y in anchors) {
      eq(y + "男", FS.mingGua(+y, 6, 1, true).gua, anchors[y][0]);
      eq(y + "女", FS.mingGua(+y, 6, 1, false).gua, anchors[y][1]);
    }
    /* 立春边界：2025-01-10 女 → 归 2024 → 震 */
    eq("立春界 2025-01-10 女", FS.mingGua(2025, 1, 10, false).gua, "震");
    eq("立春界 1990-01-05 男", FS.mingGua(1990, 1, 5, true).gua, "坤");

    /* 2) 八宅：大游年歌乾宅行 + 对称性 + 行排列不变量 */
    L("八宅八星：");
    const qian = FS.starsOf("乾");
    eq("乾宅歌诀行", [qian["坎"], qian["艮"], qian["震"], qian["巽"], qian["离"], qian["坤"], qian["兑"]],
       ["六煞", "天医", "五鬼", "祸害", "绝命", "延年", "生气"]);
    eq("延年=夫妇对·乾坤", FS.starOf("乾", "坤"), "延年");
    eq("延年=夫妇对·坎离", FS.starOf("坎", "离"), "延年");
    eq("延年=夫妇对·震巽", FS.starOf("震", "巽"), "延年");
    eq("延年=夫妇对·艮兑", FS.starOf("艮", "兑"), "延年");
    const ALL = ["生气", "延年", "天医", "伏位", "祸害", "六煞", "五鬼", "绝命"];
    let symOK = true, permOK = true;
    for (const z of Object.keys(TRI)) {
      const row = FS.starsOf(z);
      if (new Set(Object.values(row)).size !== 8 || !ALL.every(s => Object.values(row).includes(s))) permOK = false;
      for (const d of Object.keys(TRI)) if (FS.starOf(z, d) !== FS.starOf(d, z)) symOK = false;
      /* 东四宅四吉方必在东四位 */
      const jiOK = ["坎", "震", "巽", "离"].every(p => STAR_GRADE[row[p]] > 0) &&
                   ["乾", "坤", "艮", "兑"].every(p => STAR_GRADE[row[p]] < 0);
      if (EAST4.includes(z) && !jiOK) permOK = false;
    }
    eq("八星矩阵对称", symOK, true);
    eq("每行皆八星排列 & 东四宅吉方在东四位", permOK, true);

    /* 3) 玄空飞星：三张已验证盘（例3 为审查勘误后版本） */
    L("玄空飞星（三张考证盘）：");
    eq("九运起讫", [FS.periodOf(2024), FS.periodOf(2043), FS.periodOf(2023)], [9, 9, 8]);
    let r = FS.feiXing(2026, "子");
    eq("九运子山午向·山星盘", r.shan, { "巽": 6, "离": 1, "坤": 8, "震": 7, "中": 5, "兑": 3, "艮": 2, "坎": 9, "乾": 4 });
    eq("九运子山午向·向星盘", r.xiang, { "巽": 3, "离": 8, "坤": 1, "震": 2, "中": 4, "兑": 6, "艮": 7, "坎": 9, "乾": 5 });
    eq("九运子山午向·局型", r.pattern.indexOf("双星会坐") >= 0, true);
    r = FS.feiXing(2026, "乾");
    eq("九运乾山巽向·山星盘", r.shan, { "巽": 2, "离": 6, "坤": 4, "震": 3, "中": 1, "兑": 8, "艮": 7, "坎": 5, "乾": 9 });
    eq("九运乾山巽向·向星盘", r.xiang, { "巽": 7, "离": 3, "坤": 5, "震": 6, "中": 8, "兑": 1, "艮": 2, "坎": 4, "乾": 9 });
    r = FS.feiXing(2004, "乾");
    eq("八运乾山巽向·山星盘(勘误后)", r.shan, { "巽": 1, "离": 5, "坤": 3, "震": 2, "中": 9, "兑": 7, "艮": 6, "坎": 4, "乾": 8 });
    eq("八运乾山巽向·向星盘", r.xiang, { "巽": 8, "离": 3, "坤": 1, "震": 9, "中": 7, "兑": 5, "艮": 4, "坎": 2, "乾": 6 });
    eq("八运乾山巽向·局型", r.pattern.indexOf("旺山旺向") >= 0, true);

    L("测试：通过 " + pass + "，失败 " + fail);
    return fail === 0;
  };

  if (typeof module !== "undefined" && module.exports) module.exports = FS;
  else root.FS = FS;
  if (typeof require !== "undefined" && require.main === module) FS.runTests();
})(typeof window !== "undefined" ? window : globalThis);
