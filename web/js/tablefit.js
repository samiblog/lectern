// 표 열 너비 맞추기 (D68·D173). 여러 모양을 실제로 그려 보고 나은 것을 쓴다 (choose):
// ㄱ. 모든 열 맞추기 (D173): 칸마다 한 줄로 쓴 글 폭·이웃한 두 낱말 폭(canvas 로 글꼴 계산)과 열마다 가장 긴 낱말 폭(lec-measure-min)을 잰다.
//    열은 가장 긴 낱말 폭(바닥은 칸의 글 폭 2.5em, 위 12em 또는 쓸 폭의 40%)부터. 후보 다섯 — 남는 폭을 '표가 가장 많이 낮아지는' 열에 차례로
//    (행의 높이는 그 행에서 가장 많이 감긴 칸 — 줄 수 어림의 넉넉함 1·1.15), 열의 평균 글 양에 비례·그 제곱근에 비례(사용자 제안 — 한 행의 칸들이
//    비슷한 줄 수로), 이웃한 두 낱말이 한 줄에 드는 폭부터(한 줄에 낱말 하나씩 감기는 열을 피하려고). 바닥들로도 넘치면 글 폭 2em 까지 좁힌다
//    (숫자 열은 줄바꿈하지 않으므로 그대로). 폭은 table-layout: fixed 로 첫 행의 칸에 (lec-fit, --lec-w·--lec-tw — 화면에서만, 인쇄는 브라우저대로).
// ㄴ. 첫 열 넓히기 (D68 — firstInfo·widenAll, 아래): 첫 열의 글이 다른 열보다 여러 줄로 감겨 행이 높아지면 첫 열을 넓혀 본다.
// 고르기: 지금 모양(머리행·첫 열의 낱말 지키기 lec-words), 후보 다섯, 첫 열 넓히기를 그려 — 가장 낮은 것보다 10% 넘게 높은 것은 빼고,
// 나쁨(6줄이 넘는 칸·세로로 감긴 칸·한 줄에 낱말 하나쯤인 칸·칸 밖으로 넘친 글)이 적은 것, 같으면 반 줄 넘게 낮은 것.
// 옆으로 스크롤은 마지막 수단 (사용자: 한눈에 들어오지 않는다) — 좁혀 넣으면 세로로 감기는 칸이 많은 표만 열마다 글 폭 4.5em 으로 대어 본다.
// 그래도 안 되는 표(열이 너무 많거나 한 칸에 글이 너무 많음)는 쓰는 쪽이 고친다 — 작성 안내 writing.md 의 표 모양.
// 칸 폭·글자 크기·문서 폭이 바뀌거나 접힌 절을 펴면 다시 맞춘다 (표 상자의 ResizeObserver, text-size).
// 실제 문서 표 780개에서 잰 것은 DECISIONS 의 D173.
// 보이는 폭만 바꾼다 (원문·저장은 그대로). Lectern 슬라이드·맨 앞 설정의 표·코드 화면(csv)·html 문서는 하지 않는다.

import { S, on } from './store.js';

const WIDE = 'lec-wide1';                    // 첫 열을 넓힌 표 — 폭은 CSS 변수 --lec-col1 (base.css)
const PIN = 'lec-pin';                       // 그 표에서 지금 폭에 묶어 둔 열(첫 행의 칸) — 폭은 --lec-pin
const WORDS = 'lec-words';                   // 머리행·첫 열의 낱말을 끊지 않는 표 (base.css)
const FIT = 'lec-fit';                       // 모든 열을 맞춘 표 (D173) — 열 폭은 첫 행 칸의 --lec-w, 표 폭은 --lec-tw (base.css)
const MEASURE_MIN = 'lec-measure-min';      // 재는 동안: 낱말을 끊지 않는 가장 좁은 폭 (열마다 가장 긴 낱말)
const MAX_ROWS = 200;                       // 어림에 쓰는 행 (많으면 고르게 뽑는다)
// 열 폭의 바닥은 칸의 글 폭(안쪽 여백을 뺀 폭)으로 센다 — 마지막 머리 칸에는 [복사] 단추 자리로 여백이 56px 더 있다
const FLOOR_EM = 2.5;                       // 첫 폭의 바닥 (글 폭 em — 한글 두세 자)
const LAST_EM = 2;                          // 좁혀 넣는 바닥 (글 폭 em) — 열마다 이만큼도 줄 수 없으면 옆으로 스크롤
const SCROLL_EM = 4.5;                      // 옆으로 스크롤할 때 열의 바닥 (글 폭 em)
const TALLER = 1.1;                         // 가장 낮은 후보보다 이만큼 넘게 높은 후보는 쓰지 않는다
const NARROW_MANY = 3;                      // 좁혀 넣은 표에 좁은 열에서 세로로 감긴 칸이 이만큼 있으면 옆 스크롤을 대어 본다 (마지막 수단)
const CAP = 0.45;                            // 첫 열은 표 폭의 이만큼까지
const FACTORS = [1.25, 1.5, 1.75, 2, 2.5, 3];   // 지금 첫 열 폭에 곱해 대어 볼 값 (좁은 것부터)

const fitted = new WeakMap();    // .table-wrap → 맞출 때의 폭 (넓혀서 바뀐 폭으로 다시 맞추지 않게)
const watched = new WeakMap();   // 문서 본문 → 지켜보는 표 상자들 (다시 그리면 앞의 것은 그만 본다)
let resizer = null;

function contentHeight(cell) {
  const range = document.createRange();
  range.selectNodeContents(cell);
  return range.getBoundingClientRect().height;
}

/** 칸의 글 폭 — min-width 는 안쪽 여백·테두리를 뺀 폭에 걸린다 */
function innerWidth(cell) {
  const css = getComputedStyle(cell);
  return cell.getBoundingClientRect().width - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight)
    - parseFloat(css.borderLeftWidth) - parseFloat(css.borderRightWidth);
}

const lineOf = (cell) => {
  const css = getComputedStyle(cell);
  return parseFloat(css.lineHeight) || parseFloat(css.fontSize) * 1.5;
};

/** 첫 열 때문에 높은 행의 수: 첫 칸이 3줄쯤 이상이고 다른 칸들보다 한 줄 넘게 많다 */
function tallRows(table, line) {
  let n = 0;
  for (const row of table.rows) {
    const [first, ...rest] = row.cells;
    if (!first || !rest.length || first.colSpan > 1) continue;
    const h = contentHeight(first);
    if (h >= line * 2.6 && h > Math.max(0, ...rest.map(contentHeight)) + line * 0.9) n += 1;
  }
  return n;
}

/** 표가 상자보다 넓어 옆으로 넘치는지 */
const overflows = (wrap) => wrap.scrollWidth > wrap.clientWidth + 1;

/** 맞춘 것을 모두 걷는다 */
function clear(table) {
  const head = [...(table.rows[0]?.cells || [])];
  table.classList.remove(WIDE, FIT);
  table.style.removeProperty('--lec-col1');
  table.style.removeProperty('--lec-tw');
  for (const c of head) {
    c.classList.remove(PIN);
    c.style.removeProperty('--lec-w');
  }
}

/** 어림에 쓰는 행 — 많으면 고르게 뽑는다 */
const sampled = (rows) => (rows.length > MAX_ROWS ? rows.filter((_, i) => i % Math.ceil(rows.length / MAX_ROWS) === 0) : rows);

/**
 * 지금 그려진 표의 나쁨 — 칸의 수: 6줄이 넘는 칸, 글 폭이 2.5em(한글 두세 자)보다 좁은데 3줄 넘게 감긴 칸(narrow — 글이 세로로 감김),
 * 4줄 넘게 감겼는데 한 줄에 낱말이 하나쯤인 칸(좁은 열에 짓눌림 — '전력망/투자/계획'), 글이 칸 밖으로 넘친 칸(둘로 셈 — 옆 칸에 겹친다). 표 높이
 */
function badness(table) {
  let bad = 0;
  let narrow = 0;
  let cells = 0;
  let line = 0;
  for (const row of sampled([...table.rows])) {
    for (const cell of row.cells) {
      cells += 1;
      line ||= lineOf(cell);
      const n = Math.round(contentHeight(cell) / line);
      if (n >= 6) bad += 1;
      if (n >= 3) {
        const em = parseFloat(getComputedStyle(cell).fontSize);
        if (cell.getBoundingClientRect().width - padOf(cell) < em * 2.5) narrow += 1;
        else if (n >= 4 && plainText(cell).split(' ').length / n < 1.6) bad += 1;   // 한 줄에 낱말 하나쯤 — 좁은 열에 짓눌렸다
      }
      if (cell.scrollWidth > cell.clientWidth + 1) bad += 2;   // 끊지 않는 숫자·코드·그림
    }
  }
  return { bad: bad + narrow, narrow, cells, h: table.getBoundingClientRect().height, line: line || 20 };
}

/** 칸의 안쪽 여백·테두리 (열 폭에서 글이 쓸 수 없는 폭) */
function padOf(cell) {
  const css = getComputedStyle(cell);
  return parseFloat(css.paddingLeft) + parseFloat(css.paddingRight) + parseFloat(css.borderLeftWidth) + parseFloat(css.borderRightWidth);
}

let pen = null;   // 글 폭을 재는 canvas (배치하지 않고 글꼴로 — 어림에만 쓴다. 고르기는 실제로 그려서)

const plainText = (cell) => cell.textContent.replace(/\s+/g, ' ').trim();

/** 칸의 글꼴 — 칸 종류(머리·숫자·글)마다 하나로 어림 (굵게·코드 같은 서식은 보지 않는다) */
function fontOf(cell, fonts) {
  const kind = cell.tagName + (cell.classList.contains('num') ? '#' : '');
  if (!fonts.has(kind)) {
    const css = getComputedStyle(cell);
    fonts.set(kind, `${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`);
  }
  return fonts.get(kind);
}

/** 줄바꿈 없이 쓴 칸의 글 폭 */
function textWidths(rows) {
  pen ||= document.createElement('canvas').getContext('2d');
  const fonts = new Map();
  return rows.map((r) => [...r.cells].map((cell) => {
    pen.font = fontOf(cell, fonts);
    return pen.measureText(plainText(cell)).width;
  }));
}

/** 칸마다 이웃한 두 낱말을 한 줄에 쓴 폭 가운데 가장 넓은 것 — 한 줄에 낱말 하나만 들어가는 열을 피하려고 (낱말이 하나이거나 40개가 넘는 칸은 0) */
function pairWidths(rows) {
  const fonts = new Map();
  return rows.map((r) => [...r.cells].map((cell) => {
    const words = plainText(cell).split(' ');
    if (words.length < 2 || words.length > 40) return 0;
    pen.font = fontOf(cell, fonts);
    let best = 0;
    for (let i = 1; i < words.length; i++) best = Math.max(best, pen.measureText(`${words[i - 1]} ${words[i]}`).width);
    return best;
  }));
}

/** 모든 열 맞추기 (D173)를 할 표인지와 쓸 수 있는 폭 — 합친 칸이 있거나 열이 하나면 null. {table, head, rows, room, em} */
function prepare(table) {
  const wrap = table.parentElement;
  const host = wrap.parentElement;
  const head = [...(table.rows[0]?.cells || [])];
  const n = head.length;
  if (n < 2 || table.rows.length < 2 || !host) return null;
  const rows = [...table.rows];
  if (!rows.every((r) => r.cells.length === n && [...r.cells].every((c) => c.colSpan === 1 && c.rowSpan === 1))) return null;
  const hs = getComputedStyle(host);
  const room = host.clientWidth - parseFloat(hs.paddingLeft) - parseFloat(hs.paddingRight)
    - (wrap.offsetWidth - wrap.clientWidth);   // 표 상자의 테두리·세로 스크롤 막대
  if (!(room > 0)) return null;
  return { table, head, rows: sampled(rows), room, em: parseFloat(getComputedStyle(table).fontSize) || 15 };
}

/**
 * 두 번 재기 — 모든 표를 한꺼번에 (바꾸고 읽기를 표마다 되풀이하면 긴 문서를 표 수만큼 다시 배치한다):
 * 줄바꿈 없이 칸마다 한 줄 글 폭(textW·maxCol — 글꼴로 계산), 낱말을 끊지 않는 가장 좁은 열 폭(minCol — 한 번 배치). 한 줄로 다 들어가는 표는 뺀다
 */
function measureAll(list) {
  for (const m of list) {
    m.pad = m.head.map(padOf);
    m.textW = textWidths(m.rows);
    m.maxCol = m.head.map((_, i) => Math.max(...m.textW.map((row) => row[i])) + m.pad[i] + 1);
  }
  const wraps = list.filter((m) => m.maxCol.reduce((a, b) => a + b, 0) > m.room);   // 감기는 표만
  for (const m of wraps) m.table.classList.add(MEASURE_MIN);
  for (const m of wraps) m.minCol = m.head.map((c) => c.getBoundingClientRect().width);
  for (const m of wraps) m.nowrap = m.head.map((_, i) => m.rows.slice(1).some((r) => r.cells[i]?.classList.contains('num')));   // 숫자 열 (base.css 의 td.num — 줄바꿈하지 않는다)
  for (const m of wraps) {
    const pairs = pairWidths(m.rows);
    m.pairCol = m.head.map((_, i) => Math.max(...pairs.map((row) => row[i])) + m.pad[i] + 1);
  }
  for (const m of wraps) m.table.classList.remove(MEASURE_MIN);
  return wraps;
}

const sum = (xs) => xs.reduce((a, b) => a + b, 0);

/** 열의 첫 폭: 가장 긴 낱말 폭 (바닥은 글 폭 2.5em — 글이 그보다 짧으면 그 폭, 위는 max(12em, 쓸 폭의 40%) — 긴 주소 하나가 표를 차지하지 않게) */
function floorsOf({ minCol, maxCol, pad, room, em }) {
  const cap = Math.max(12 * em, room * 0.4);
  return minCol.map((w, i) => Math.min(Math.max(w, Math.min(maxCol[i], pad[i] + FLOOR_EM * em)), Math.max(cap, pad[i] + FLOOR_EM * em), maxCol[i]));
}

/** 좁혀 넣는 바닥: 글 폭 2em (글이 그보다 짧으면 그 폭, 줄바꿈하지 않는 숫자 열은 그 폭 그대로 — 숫자를 끊거나 옆 칸에 겹치지 않게). 이것도 못 주면 옆으로 스크롤 */
const lastFloors = ({ maxCol, minCol, nowrap, pad, em }) => maxCol.map((w, i) => (nowrap[i] ? minCol[i] : Math.min(w, pad[i] + LAST_EM * em)));

/**
 * 열의 평균 글 양에 비례해 나눈다 (사용자 제안 — '셀에 든 글자 수 대비 열 너비 비율', '열 평균'): 열마다 몸통 칸 글 폭의 평균에 비례하게,
 * 바닥(가장 긴 낱말·글 폭 2.5em)과 한 줄 폭 사이에서 (합이 쓸 폭이 되는 배율을 이분법으로). power 0.5 는 제곱근 — 글이 아주 긴 열이 다 가져가지 않게. 한 행의 칸들이 비슷한 줄 수로
 * 감긴다 — 칸이 높아져도 이웃 칸과 비슷하면 이상해 보이지 않는다. 바닥들로도 넘치면 plan 과 같이 줄인다
 */
function planAvg(m, power = 1) {
  const { pad, textW, maxCol, room: A } = m;
  const floors = floorsOf(m);
  if (sum(floors) >= A) return plan(m, 1);
  const body = textW.length > 1 ? textW.slice(1) : textW;   // 머리행은 짧은 이름표라 뺀다
  const avg = maxCol.map((_, i) => (body.reduce((t, row) => t + row[i], 0) / body.length + pad[i]) ** power);
  // 열 폭 = 평균 × k 를 바닥과 한 줄 폭 사이로 — 합이 쓸 폭이 되는 k 를 이분법으로 (합은 k 에 따라 늘기만 한다.
  // 넘치는 열과 모자라는 열을 차례로 고정하며 나누면 한 번에 둘 다 생길 때 합이 쓸 폭을 넘었다 — 1000px 에서 넘친 표 2 → 10)
  const at = (k) => avg.map((a, i) => Math.min(maxCol[i], Math.max(floors[i], a * k)));
  let lo = 0;
  let hi = 1;
  while (sum(at(hi)) < A && hi < 1e6) hi *= 2;
  for (let step = 0; step < 40; step += 1) {
    const mid = (lo + hi) / 2;
    if (sum(at(mid)) <= A) lo = mid;
    else hi = mid;
  }
  return at(lo);
}

/**
 * 열마다 이웃한 두 낱말이 한 줄에 들어가는 폭을 첫 폭으로 (글이 긴 열이 남는 폭을 다 가져가 다른 열이 낱말 하나씩 감기지 않게 —
 * 표는 높아질 수 있다. 사용자: '셀 높이가 커져도 다른 열과 비슷하면 이상해 보이지 않는다'). 들어가지 않거나 바뀌는 것이 없으면 null
 */
function planPair(m) {
  const floors = floorsOf(m);
  const two = floors.map((f, i) => (m.nowrap[i] ? f : Math.min(m.maxCol[i], Math.max(f, m.pairCol[i]))));
  if (sum(two) > m.room || two.every((w, i) => w <= floors[i] + 0.5)) return null;
  return plan(m, 1, two);
}

/** 대어 볼 열 폭들 — 표가 가장 낮아지게 차례로(줄 수 어림의 넉넉함 1·1.15 — 낱말 단위로 감기면 글자 폭 어림보다 줄이 는다), 열 평균 비례(그대로·제곱근 — 글이 아주 긴 열이 다 가져가지 않게), 두 낱말 폭부터 */
const PLANS = [(m) => plan(m, 1), (m) => plan(m, 1.15), (m) => planAvg(m, 1), (m) => planAvg(m, 0.5), planPair];

/** 옆으로 스크롤하는 폭 — 열마다 가장 긴 낱말·글 폭 4.5em (한 줄 폭과 위 cap 까지). 쓸 폭에 들어가면 null (스크롤할 까닭이 없다) */
function scrollPlan(m) {
  const cap = Math.max(12 * m.em, m.room * 0.4);
  const widths = m.maxCol.map((w, i) => Math.min(w, Math.max(m.minCol[i], m.pad[i] + SCROLL_EM * m.em), Math.max(cap, m.pad[i] + SCROLL_EM * m.em)));
  return sum(widths) > m.room ? widths : null;
}

/** 잰 값으로 열 폭을 정한다 (slack: 줄 수 어림의 넉넉함, start: 열의 첫 폭). 열 폭 배열 */
function plan(m, slack, start = floorsOf(m)) {
  const { pad, textW, maxCol, room: A } = m;
  const n = maxCol.length;
  const linesAt = (i, w) => textW.map((row) => Math.max(1, Math.ceil(row[i] * slack / Math.max(1, w - pad[i]) - 0.02)));
  let widths = start.slice();
  const last = lastFloors(m);
  if (sum(last) > A) return last;   // 열마다 글 폭 2em 도 줄 수 없다 — 그 폭으로 두고 옆으로 스크롤 (마지막 수단)
  let left = A - sum(widths);
  if (left < 0) {   // 가장 긴 낱말들로는 넘친다 — 글 폭 2em(글이 짧으면 그 폭, 숫자 열은 그대로)까지 고르게 줄인다 (긴 낱말은 끊긴다)
    const extra = widths.map((w, i) => w - last[i]);
    const total = extra.reduce((a, b) => a + b, 0);
    widths = widths.map((w, i) => w - (total > 0 ? extra[i] * Math.min(1, -left / total) : 0));
    left = A - widths.reduce((a, b) => a + b, 0);
  }
  const lines = widths.map((w, i) => linesAt(i, w));
  const heightOf = () => textW.reduce((h, _, r) => h + Math.max(...lines.map((l) => l[r])), 0);
  let H = heightOf();
  // 남는 폭을 표가 가장 많이 낮아지는 열에 — 후보는 행마다 한 줄 덜·반·한 줄이 되는 폭 (가까운 것부터 24개)
  for (let guard = 0; left > 0.5 && guard < 300; guard += 1) {
    let best = null;
    for (let i = 0; i < n; i++) {
      if (widths[i] >= maxCol[i] - 0.5) continue;
      const cand = new Set();
      for (const row of textW) {
        const l = Math.max(1, Math.ceil(row[i] * slack / Math.max(1, widths[i] - pad[i]) - 0.02));
        if (l > 1) for (const k of [l - 1, Math.ceil(l / 2), 1]) cand.add(Math.min(maxCol[i], row[i] * slack / k + pad[i] + 0.5));
      }
      const others = textW.map((_, r) => lines.reduce((mx, l, j) => (j === i ? mx : Math.max(mx, l[r])), 1));   // 이 열 말고 행마다 가장 많은 줄
      for (const w of [...cand].filter((x) => x > widths[i] + 0.5 && x - widths[i] <= left).sort((a, b) => a - b).slice(0, 24)) {
        const next = linesAt(i, w);
        const gain = H - next.reduce((h, l, r) => h + Math.max(l, others[r]), 0);
        if (gain > 0 && (!best || gain / (w - widths[i]) > best.rate)) best = { i, w, rate: gain / (w - widths[i]) };
      }
    }
    if (!best) break;
    left -= best.w - widths[best.i];
    widths[best.i] = best.w;
    lines[best.i] = linesAt(best.i, best.w);
    H = heightOf();
  }
  // 한 열만 넓혀서는 낮아지지 않는 남은 폭(같은 행에서 여러 열이 감김) — 아직 감긴 열에 넘치는 글 양만큼
  const want = widths.map((w, i) => Math.max(0, maxCol[i] - w));
  const wantSum = want.reduce((a, b) => a + b, 0);
  if (left > 1 && wantSum > 0) widths = widths.map((w, i) => w + want[i] * Math.min(1, left / wantSum));
  return widths;
}

/** 정한 열 폭을 준다 (table-layout: fixed — 첫 행의 칸) */
function applyWidths(table, head, widths) {
  head.forEach((c, i) => c.style.setProperty('--lec-w', `${widths[i].toFixed(1)}px`));
  table.style.setProperty('--lec-tw', `${widths.reduce((a, b) => a + b, 0).toFixed(1)}px`);
  table.classList.add(FIT);
}

const better = (a, b) => a.bad < b.bad || (a.bad === b.bad && a.h < b.h - a.line / 2);

/**
 * 후보 가운데 고른다 — 가장 낮은 후보보다 10%(와 한 줄) 넘게 높은 것은 빼고, 나쁨이 적은 것, 같으면 반 줄 넘게 낮은 것 (앞의 것이 먼저 — 첫째는 지금 모양).
 * 열을 고르게 하려고 표가 조금 높아지는 것은 받지만(사용자: '셀 높이가 커져도 다른 열과 비슷하면 이상해 보이지 않는다'), 글이 아주 긴 열이
 * 좁아져 표가 훨씬 높아지는 것은 받지 않는다 (사용자의 처음 불만이 '셀 높이가 아주 길어진다')
 */
function choose(cands) {
  const sane = cands.filter((c) => !c.score.narrow);   // 가장 낮은 높이는 세로로 감긴 칸이 없는 것에서 — 좁혀 넣어 낮아진 것이 기준이 되지 않게
  const low = Math.min(...(sane.length ? sane : cands).map((c) => c.score.h));
  let best = null;
  for (const c of cands) {
    if (c.score.h > low * TALLER + c.score.line) continue;
    if (!best || better(c.score, best.score)) best = c;
  }
  return best;
}

/** 표의 지금 모양 (class·첫 열 폭·묶은 열) — 견준 뒤 되돌릴 때 */
function snapshot(table, head) {
  return { cls: table.className, col1: table.style.getPropertyValue('--lec-col1'),
    pins: head.map((c) => (c.classList.contains(PIN) ? c.style.getPropertyValue('--lec-pin') : null)) };
}

function restore(table, head, snap) {
  clear(table);
  table.className = snap.cls;
  if (snap.col1) table.style.setProperty('--lec-col1', snap.col1);
  head.forEach((c, i) => { if (snap.pins[i] != null) c.style.setProperty('--lec-pin', snap.pins[i]); });
}

/**
 * 표들을 맞춘다 — 머리행·첫 열의 낱말 지키기(D68)를 바탕으로, 모든 열 맞추기(D173 — 후보 다섯)와 첫 열 넓히기(D68)를 그려 보고 나은 것으로 (choose),
 * 옆으로 스크롤은 마지막 수단. 단계마다 모든 표를 바꾸고 모든 표를 읽는다 (문서를 다시 배치하는 횟수가 표 수에 따라 늘지 않게 — 첫 열 넓히기는
 * 새 방식이 완벽하지 못한 표에만 대어 본다). 표마다 따로 하던 첫 원형은 표 53개 문서에서 0.75초였다
 */
function fitMany(tables) {
  for (const t of tables) clear(t);
  const list = measureAll(tables.map(prepare).filter(Boolean));   // 맞추기 전에 잰다 — 넓힌 폭이 가장 좁은 폭에 섞이지 않게
  const firsts = new Map(firstInfo(tables).map((x) => [x.table, x]));   // 낱말 지키기 + 첫 열 때문에 높은 행이 있는 표 (D68)
  const listed = new Set(list.map((m) => m.table));
  widenAll([...firsts.values()].filter((x) => !listed.has(x.table)));   // 모든 열 맞추기를 하지 않는 표 — 예전처럼
  if (list.length) {
    for (const m of list) m.base = snapshot(m.table, m.head);
    for (const m of list) m.cands = [{ score: badness(m.table), widths: null, snap: m.base }];
    for (const planner of PLANS) {
      const plans = list.map(planner);   // null — 이 표에는 대어 볼 것이 없다
      list.forEach((m, i) => {
        if (!plans[i]) return;
        clear(m.table);
        m.table.classList.remove(WORDS);
        applyWidths(m.table, m.head, plans[i]);
      });
      list.forEach((m, i) => {
        if (!plans[i]) return;
        m.cands.push({ score: badness(m.table), widths: plans[i], snap: null });
      });
    }
    for (const m of list) m.best = choose(m.cands);
    // 첫 열 넓히기 — 첫 열 때문에 높은 행이 있고, 새 방식이 그런 칸을 다 없애지 못한 표에만
    const widen = list.filter((m) => firsts.has(m.table) && !(m.best.widths && m.best.score.bad === 0));
    for (const m of widen) restore(m.table, m.head, m.base);
    widenAll(widen.map((m) => firsts.get(m.table)));
    for (const m of widen) {
      m.cands.push({ score: badness(m.table), widths: null, snap: snapshot(m.table, m.head) });
      m.best = choose(m.cands);
    }
    // 마지막 수단 — 옆으로 스크롤하는 폭 (사용자: 스크롤하면 표가 한눈에 들어오지 않는다). 고른 것에 세로로 감긴 칸이 셋 넘고 표 칸의 10% 넘을 때만
    // 대어 보고, 어느 후보로도 얻을 수 있는 가장 적은 나쁨의 반 아래로 줄고 세로로 감긴 칸이 없어질 때만 쓴다
    const many = (m) => m.best.score.narrow >= Math.max(NARROW_MANY, m.best.score.cells * 0.1);
    const scrolls = list.filter(many).map((m) => [m, scrollPlan(m)]).filter(([, w]) => w);
    for (const [m, widths] of scrolls) {
      clear(m.table);
      m.table.classList.remove(WORDS);
      applyWidths(m.table, m.head, widths);
    }
    for (const [m, widths] of scrolls) {
      const score = badness(m.table);
      const least = Math.min(...m.cands.map((c) => c.score.bad));
      if (!score.narrow && score.bad * 2 <= least) m.best = { score, widths, snap: null };
    }
    for (const m of list) {
      if (m.best.widths) {
        clear(m.table);
        m.table.classList.remove(WORDS);
        applyWidths(m.table, m.head, m.best.widths);
      } else restore(m.table, m.head, m.best.snap);
    }
  }
  for (const t of tables) fitted.set(t.parentElement, t.parentElement.getBoundingClientRect().width);
}

/**
 * 첫 열 넓히기의 앞 단계 (D68) — 표들의 머리행·첫 열 낱말을 지키고(넘치면 예전처럼 끊음), 첫 열 때문에 높은 행이 있는 표를 고른다 (한꺼번에).
 * 넓히기는 widenAll — 배율마다 배치하므로 필요한 표에만
 */
function firstInfo(tables) {
  // 머리행·첫 열의 낱말을 지킨다 — 긴 낱말(`log(RGDPSA-CGFRSA/CPI)`·`2025년(실적)` 이 여럿)로 표가 넘치면 예전처럼 끊는다
  for (const t of tables) t.classList.add(WORDS);
  const over = tables.map((t) => overflows(t.parentElement));
  tables.forEach((t, i) => { if (over[i]) t.classList.remove(WORDS); });
  const todo = tables.map((table) => {
    const head = [...(table.rows[0]?.cells || [])];
    const width = table.getBoundingClientRect().width;
    if (!width || head.length < 2 || table.rows.length < 2 || !head.every((c) => c.colSpan === 1)) return null;
    const line = lineOf(head[0]);
    const tall = tallRows(table, line);
    return tall ? { table, head, width, line, tall, widths: head.map(innerWidth), height: table.getBoundingClientRect().height } : null;
  }).filter(Boolean);
  return todo;
}

/**
 * 첫 열 때문에 높은 행이 있는 표들의 첫 열을 넓혀 본다 (D68). 배율마다 모든 표를 바꾸고 모두 읽는다 — 표마다 따로 하면 배율 수 × 표 수만큼
 * 문서를 다시 배치한다
 */
function widenAll(infos) {
  for (const x of infos) {
    const { table, head, width, widths } = x;
    x.cap = width * CAP;
    // 넓힐 폭은 가장 넓은 열(긴 설명)에서만 가져온다 — 나머지 열은 지금 폭 그대로 (좁은 열이 더 감겨 높아지지 않게)
    const rest = widths.slice(1);
    const widest = 1 + rest.indexOf(Math.max(...rest));   // 첫 열은 빼고 (첫 열이 가장 넓어도 다른 열 하나는 풀어 둔다)
    head.forEach((c, i) => {
      if (i === 0 || i === widest) return;
      c.style.setProperty('--lec-pin', `${Math.round(widths[i])}px`);
      c.classList.add(PIN);
    });
    x.best = null;
    x.done = false;
    table.classList.add(WIDE);
  }
  for (const f of FACTORS) {
    const step = infos.filter((x) => !x.done);
    if (!step.length) break;
    for (const x of step) {   // 바꾸기
      x.w = Math.min(x.widths[0] * f, x.cap);
      if (x.w <= x.widths[0] + 4) x.done = true;
      else x.table.style.setProperty('--lec-col1', `${Math.round(x.w)}px`);
    }
    for (const x of step) {   // 읽기
      if (x.done) continue;
      const { table, line, tall, height, w } = x;
      if (overflows(table.parentElement)) {   // 묶은 열과 첫 열로 표가 넘친다 — 더 넓혀도 마찬가지
        x.done = true;
        continue;
      }
      const h = table.getBoundingClientRect().height;
      const n = tallRows(table, line);
      // 표가 반 줄 넘게 낮아지거나, 높아지지 않으면서 첫 열 때문에 높은 행이 준 폭. 그중 더 낮은(반 줄 넘게) 것, 같으면 그런 행이
      // 더 적은 것 — 그만큼 나아지지 않으면 앞의 좁은 폭
      const gain = h < height - line / 2 || (h <= height + line / 2 && n < tall);
      if (gain && (!x.best || h < x.best.h - line / 2 || (h <= x.best.h + line / 2 && n < x.best.n))) x.best = { w, h, n };
      if (w >= x.cap) x.done = true;
    }
  }
  for (const x of infos) {
    if (x.best) x.table.style.setProperty('--lec-col1', `${Math.round(x.best.w)}px`);
    else {
      x.table.classList.remove(WIDE);
      x.table.style.removeProperty('--lec-col1');
      for (const c of x.head) c.classList.remove(PIN);
    }
  }
}

const pending = new Set();   // 크기가 바뀐 표 상자들 — 잠깐 뒤에 한꺼번에 맞춘다
let pendingTimer = 0;

function onResize(entries) {
  for (const { target } of entries) {
    const width = target.getBoundingClientRect().width;
    if (!target.isConnected || !width || Math.abs(width - (fitted.get(target) ?? -1)) < 2) continue;   // 접혀서 0 이거나 맞춘 그대로
    pending.add(target);
  }
  if (!pending.size) return;
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(() => {
    const tables = [...pending].filter((w) => w.isConnected).map((w) => w.querySelector(':scope > table')).filter(Boolean);
    pending.clear();
    if (tables.length) fitMany(/** @type {HTMLTableElement[]} */ (tables));
  }, 150);
}

/** 문서 본문(view)의 표들을 맞추고, 폭이 바뀌면 다시 맞추도록 지켜본다 (doc.js 가 바꿔 끼운 뒤에) */
export function fitTables(view) {
  resizer ||= new ResizeObserver(onResize);
  for (const old of watched.get(view) || []) resizer.unobserve(old);
  const wraps = view.classList.contains('lec-deck') || view.classList.contains('code-view') ? []
    : [...view.querySelectorAll('.table-wrap')].filter((w) => w.firstElementChild?.tagName === 'TABLE');
  fitMany(wraps.map((w) => /** @type {HTMLTableElement} */ (w.firstElementChild)));
  for (const wrap of wraps) resizer.observe(wrap);
  watched.set(view, wraps);
}

export function initTableFit() {
  // 글자 크기만 바뀌고 칸 폭은 그대로일 수 있다 (문서가 칸보다 넓을 때) — 다음 그림에서 모든 칸의 표를 다시
  on('text-size', () => requestAnimationFrame(() => {
    for (const pane of S.panes) if (pane.current?.type === 'doc') fitTables(pane.view);
  }));
}
