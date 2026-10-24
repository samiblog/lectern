// 편집 모드의 위치 잇기 (D55): 읽는 화면(칸의 문서·코드 화면)과 편집기(editor.js)가 원문의 같은 줄을 가리키게 하는 계산.
//
// - 읽는 화면의 블록은 원문 줄 범위를 안다 — md 는 data-lines(markdown.js), 코드 화면은 줄마다 .cv-line[data-line].
//   html 문서는 줄을 모르므로 제목(h1~h6)만 쓴다: 원문에서 n 번째 <hN 태그의 줄 = 화면의 n 번째 제목 (headLines).
//   블록 안, 블록과 블록 사이, 제목과 제목 사이는 줄 수에 맞춰 높이를 나눈다.
// - 읽는 화면은 마지막으로 그린 원문의 줄이다. 그 뒤 편집기에서 줄이 늘거나 준 것을 기록(log)해 두고 줄 번호를 옮긴다
//   (toEditor·toView). 저장한 것을 화면이 다시 그리면 그때까지의 기록은 버린다 (editor.js).
// - 줄은 0부터 세는 '자리'다 — 정수 부분이 줄, 소수 부분이 그 줄 안에서 내려온 비율.

import { screenRect } from './util.js';

/** 편집기에서 바뀐 곳 하나를 기록에 (CodeMirror 의 change). 줄 수가 그대로인 고침은 줄 번호를 옮기지 않으므로 넣지 않는다 */
export function logChange(log, change) {
  const from = change.from.line;
  const to = change.to.line;
  const n = change.text.length;   // 새 줄 수 (지운 것만이어도 1)
  if (n !== to - from + 1) log.push({ from, to, n });
}

/** 읽는 화면의 자리 → 편집기의 자리 */
export function toEditor(log, at) {
  let line = Math.floor(at);
  const frac = at - line;
  for (const c of log) {
    if (line > c.to) line += c.n - (c.to - c.from + 1);
    else if (line >= c.from) line = c.from + Math.min(line - c.from, c.n - 1);
  }
  return line + frac;
}

/** 편집기의 자리 → 읽는 화면의 자리 */
export function toView(log, at) {
  let line = Math.floor(at);
  const frac = at - line;
  for (let i = log.length - 1; i >= 0; i--) {
    const c = log[i];
    if (line >= c.from + c.n) line -= c.n - (c.to - c.from + 1);
    else if (line >= c.from) line = c.from + Math.min(line - c.from, c.to - c.from);
  }
  return line + frac;
}

// 제목이 아닌 <hN 을 건너뛴다: 주석, 글자로만 읽는 요소(script·style·textarea·title), 화면에 없는 template
const HEAD_TAG = /<!--[\s\S]*?(?:-->|$)|<(script|style|textarea|title|template)\b[\s\S]*?(?:<\/\1\s*>|$)|<h[1-6][\s>/]/gi;

/** html 원문에서 제목 태그(<h1>~<h6>)가 있는 줄들 (0부터) — 화면의 제목 순서와 같다 */
export function headLines(text) {
  const lines = [];
  let line = 0;
  let last = 0;
  for (const m of text.matchAll(HEAD_TAG)) {
    if (m[1] || m[0].startsWith('<!')) continue;
    for (let i = last; i < m.index; i++) if (text.charCodeAt(i) === 10) line += 1;
    last = m.index;
    lines.push(line);
  }
  return lines;
}

const OUTSIDE = '.front-matter, .footnotes';   // 원문 순서와 다른 곳에 그려지는 것 (머리 정보, 각주)

/**
 * 읽는 화면에서 원문 줄을 아는 자리들 [{s, e, el}] — s 는 첫 줄, e 는 끝 줄 다음 (0부터). 문서 순서이고 s 가 줄지 않는다.
 * heads: html 문서의 제목 줄들 (headLines)
 */
export function marksOf(pane, heads) {
  const { view } = pane;
  const frame = view.querySelector('iframe.lec-html:not(.lec-loading)');
  let list;
  if (frame) {
    const els = [...(frame.contentDocument?.body?.querySelectorAll('h1, h2, h3, h4, h5, h6') || [])];
    list = els.slice(0, heads?.length || 0).map((el, i) => ({ s: heads[i], e: heads[i] + 1, el }));
  } else if (view.classList.contains('code-view')) {
    list = [...view.querySelectorAll('.cv-line[data-line]')].map((el) => ({ s: +el.dataset.line - 1, e: +el.dataset.line, el }));
  } else {
    list = [...view.querySelectorAll('[data-lines]')].filter((el) => !el.closest(OUTSIDE)).map((el) => {
      const [a, b] = el.dataset.lines.split('-').map(Number);
      return { s: a - 1, e: Math.max(a, b || a), el };
    });
  }
  const marks = [];
  for (const m of list) if (!marks.length || m.s >= marks[marks.length - 1].s) marks.push(m);
  return marks;
}

const shown = (el) => el.getClientRects().length > 0;   // 접힌 절(display:none) 안이 아닌지

/** x 가 x0~x1 사이의 어디쯤인지에 맞춰 y0~y1 사이의 값 */
function between(x, x0, y0, x1, y1) {
  if (x1 <= x0) return y0;
  return y0 + ((Math.min(Math.max(x, x0), x1) - x0) / (x1 - x0)) * (y1 - y0);
}

/** at 줄에서 시작했거나 그 앞에서 시작한 마지막 자리의 번호 (없으면 -1) */
function lastStarting(marks, at) {
  let lo = 0;
  let hi = marks.length - 1;
  let k = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (marks[mid].s <= at) {
      k = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return k;
}

/** 그 자리를 담은 요소 (접혀 있어도) — 닫을 때 그 절을 펴려고 */
export function markAt(marks, at) {
  return marks[lastStarting(marks, at)]?.el || null;
}

/** 읽는 화면의 자리 → 화면 좌표 y (top: 읽는 화면 맨 위의 y). 자리를 모르면 null. 접힌 절 안의 줄은 그 절의 제목 쪽으로 */
export function yOfLine(marks, at, top) {
  const k = lastStarting(marks, at);
  let a = k;
  while (a >= 0 && !shown(marks[a].el)) a--;
  let b = k + 1;
  while (b < marks.length && !shown(marks[b].el)) b++;
  const A = marks[a];
  const B = marks[b];
  const ra = A && screenRect(A.el);
  const rb = B && screenRect(B.el);
  if (A && at < A.e) return ra.top + ((at - A.s) / (A.e - A.s)) * ra.height;   // 블록 안
  if (A && B) return between(at, A.e, ra.bottom, B.s, rb.top);   // 블록 사이
  if (A) return ra.bottom;
  if (B) return between(at, 0, top, B.s, rb.top);   // 첫 블록 앞 (머리 정보 등)
  return null;
}

/** 화면 좌표 y → 읽는 화면의 자리 (top: 읽는 화면 맨 위의 y) */
export function lineOfY(marks, y, top) {
  let A = null;
  let ra = null;
  let B = null;
  let rb = null;
  for (const m of marks) {
    if (!shown(m.el)) continue;
    const r = screenRect(m.el);
    if (r.top > y) {
      B = m;
      rb = r;
      break;
    }
    A = m;
    ra = r;
  }
  if (!A) return B ? between(y, top, 0, rb.top, B.s) : 0;
  if (y < ra.bottom) return A.s + ((y - ra.top) / (ra.height || 1)) * (A.e - A.s);
  return B ? between(y, ra.bottom, A.e, rb.top, B.s) : A.e;
}

/** 읽는 화면의 요소(목차의 제목·구성 요소)가 원문 몇째 줄의 것인지 (0부터) */
export function lineOfElement(marks, el, top) {
  if (el.dataset?.line) return +el.dataset.line - 1;   // 코드 화면의 줄
  const lines = (el.closest?.('[data-lines]') || el.querySelector?.('[data-lines]'))?.dataset.lines;
  if (lines) return +lines.split('-')[0] - 1;
  const m = marks.find((x) => x.el === el);   // html 문서의 제목
  if (m) return m.s;
  return Math.floor(lineOfY(marks, screenRect(el).top, top));   // html 문서의 그 밖의 것 — 높이로
}
