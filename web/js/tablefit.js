// 표 첫 열 넓히기 (D68): md 문서의 표에서 첫 열의 글이 다른 열보다 여러 줄로 감겨 행이 높아지면 첫 열을 넓힌다.
// 몇 가지 폭을 대어 보고, 표가 낮아지거나 첫 열 때문에 높은 행이 줄어드는(표는 높아지지 않고) 폭 가운데 표가 가장 낮고 그런 행이
// 가장 적은, 그중 가장 좁은 폭으로 — 넓혀서 다른 열이 더 감겨 오히려 높아지면 그대로 둔다.
// 칸 폭·글자 크기·문서 폭이 바뀌거나 접힌 절을 펴면 다시 맞춘다 (표 상자의 ResizeObserver, text-size).
// 머리행·첫 열은 낱말 가운데서 끊지 않게 하고(lec-words), 그 때문에 표가 옆으로 넘치면 예전처럼 아무 데서나 끊는다.
// 보이는 폭만 바꾼다 (원문·저장은 그대로). 발표 문서·맨 앞 설정의 표·코드 화면(csv)·html 문서는 하지 않는다.

import { S, on } from './store.js';

const WIDE = 'lec-wide1';                    // 첫 열을 넓힌 표 — 폭은 CSS 변수 --lec-col1 (base.css)
const PIN = 'lec-pin';                       // 그 표에서 지금 폭에 묶어 둔 열(첫 행의 칸) — 폭은 --lec-pin
const WORDS = 'lec-words';                   // 머리행·첫 열의 낱말을 끊지 않는 표 (base.css)
const CAP = 0.45;                            // 첫 열은 표 폭의 이만큼까지
const FACTORS = [1.25, 1.5, 1.75, 2, 2.5, 3];   // 지금 첫 열 폭에 곱해 대어 볼 값 (좁은 것부터)

const fitted = new WeakMap();    // .table-wrap → 맞출 때의 폭 (넓혀서 바뀐 폭으로 다시 맞추지 않게)
const watched = new WeakMap();   // 문서 본문 → 지켜보는 표 상자들 (다시 그리면 앞의 것은 그만 본다)
const timers = new WeakMap();
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

/** 표 하나의 첫 열 폭을 맞춘다 (먼저 넓힌 것을 걷고 잰다) */
function fitTable(table) {
  const wrap = table.parentElement;
  const head = [...(table.rows[0]?.cells || [])];
  table.classList.remove(WIDE);
  table.style.removeProperty('--lec-col1');
  for (const c of head) c.classList.remove(PIN);
  // 머리행·첫 열의 낱말을 지킨다 — 긴 낱말(`log(RGDPSA-CGFRSA/CPI)`·`2025년(실적)` 이 여럿)로 표가 넘치면 예전처럼 끊는다
  table.classList.add(WORDS);
  if (overflows(wrap)) table.classList.remove(WORDS);
  const width = table.getBoundingClientRect().width;
  if (width && head.length > 1 && table.rows.length > 1 && head.every((c) => c.colSpan === 1)) {
    const line = lineOf(head[0]);
    const tall = tallRows(table, line);
    if (tall) {
      const widths = head.map(innerWidth);
      const height = table.getBoundingClientRect().height;
      const cap = width * CAP;
      // 넓힐 폭은 가장 넓은 열(긴 설명)에서만 가져온다 — 나머지 열은 지금 폭 그대로 (좁은 열이 더 감겨 높아지지 않게)
      const rest = widths.slice(1);
      const widest = 1 + rest.indexOf(Math.max(...rest));   // 첫 열은 빼고 (첫 열이 가장 넓어도 다른 열 하나는 풀어 둔다)
      head.forEach((c, i) => {
        if (i === 0 || i === widest) return;
        c.style.setProperty('--lec-pin', `${Math.round(widths[i])}px`);
        c.classList.add(PIN);
      });
      let best = null;
      table.classList.add(WIDE);
      for (const f of FACTORS) {
        const w = Math.min(widths[0] * f, cap);
        if (w <= widths[0] + 4) break;
        table.style.setProperty('--lec-col1', `${Math.round(w)}px`);
        if (overflows(wrap)) break;   // 묶은 열과 첫 열로 표가 넘친다 — 더 넓혀도 마찬가지
        const h = table.getBoundingClientRect().height;
        const n = tallRows(table, line);
        // 표가 반 줄 넘게 낮아지거나, 높아지지 않으면서 첫 열 때문에 높은 행이 준 폭. 그중 더 낮은(반 줄 넘게) 것, 같으면 그런 행이
        // 더 적은 것 — 그만큼 나아지지 않으면 앞의 좁은 폭
        const better = h < height - line / 2 || (h <= height + line / 2 && n < tall);
        if (better && (!best || h < best.h - line / 2 || (h <= best.h + line / 2 && n < best.n))) best = { w, h, n };
        if (w >= cap) break;
      }
      if (best) table.style.setProperty('--lec-col1', `${Math.round(best.w)}px`);
      else {
        table.classList.remove(WIDE);
        table.style.removeProperty('--lec-col1');
        for (const c of head) c.classList.remove(PIN);
      }
    }
  }
  fitted.set(wrap, wrap.getBoundingClientRect().width);
}

function onResize(entries) {
  for (const { target } of entries) {
    const width = target.getBoundingClientRect().width;
    if (!target.isConnected || !width || Math.abs(width - (fitted.get(target) ?? -1)) < 2) continue;   // 접혀서 0 이거나 맞춘 그대로
    clearTimeout(timers.get(target));
    timers.set(target, setTimeout(() => {
      const table = target.querySelector(':scope > table');
      if (target.isConnected && table) fitTable(table);
    }, 150));
  }
}

/** 문서 본문(view)의 표들을 맞추고, 폭이 바뀌면 다시 맞추도록 지켜본다 (doc.js 가 바꿔 끼운 뒤에) */
export function fitTables(view) {
  resizer ||= new ResizeObserver(onResize);
  for (const old of watched.get(view) || []) resizer.unobserve(old);
  const wraps = view.classList.contains('lec-deck') || view.classList.contains('code-view') ? []
    : [...view.querySelectorAll('.table-wrap')].filter((w) => w.firstElementChild?.tagName === 'TABLE');
  for (const wrap of wraps) fitTable(wrap.firstElementChild);
  for (const wrap of wraps) resizer.observe(wrap);
  watched.set(view, wraps);
}

export function initTableFit() {
  // 글자 크기만 바뀌고 칸 폭은 그대로일 수 있다 (문서가 칸보다 넓을 때) — 다음 그림에서 모든 칸의 표를 다시
  on('text-size', () => requestAnimationFrame(() => {
    for (const pane of S.panes) if (pane.current?.type === 'doc') fitTables(pane.view);
  }));
}
