// 줄 단위 (D75): 화면(md 문서·코드 화면)의 원문 줄과 그 줄이 보이는 자리. 현재 위치와 줄 하이라이트(spotlight.js)가 쓴다.
//
// - 단위는 원문 한 줄이다. 한 줄로 쓴 문단·목록 항목·제목·표의 행은 그 블록 통째, 여러 줄로 나눠 쓴 문단·목록 항목은 줄마다
//   (markdown-it 이 줄바꿈 자리에 남긴 \n 으로 나눈다 — 화면에서는 이어져 흐르므로 이웃 줄과 세로로 겹칠 수 있다), 코드 블록은 줄마다.
//   다이어그램·차트·수식 블록은 통째로 한 단위. 코드 화면은 .cv-line 하나가 한 단위 (csv 의 여러 줄 행은 data-end 까지).
// - 원문 줄은 markdown.js 가 블록마다 단 data-lines 다. 줄마다 그 줄을 가진 가장 안쪽 블록이 그 줄을 보여 준다.
//   빈 줄과 화면에 없는 블록(머리 정보, raw HTML)의 줄은 단위가 없다. 코드 블록의 ``` 줄은 뺀다.
//   보이는 글이 없는 줄(표의 구분 줄 |---|, 강조글의 [!NOTE] 줄, setext 제목의 === 줄)은 이웃 단위에 붙인다.
// - 단위는 문서 차례(화면 위에서 아래로)이고, 자리는 스크롤 상자 안 좌표 {top, bottom} 이다 (스크롤해도 그대로).
//   단위: {a, b(원문 줄, 1부터, 끝 포함), el, top, bottom, range?(여러 줄 문단의 그 줄 — Range), row?(코드 블록의 줄 차례)}

const ATOMIC = 'pre.mermaid, pre.lec-chart, .diagram-error, .math-block';
// 요소 자신의 글을 셀 때 들어가지 않는 블록 (안쪽 블록의 줄은 그 블록이 보여 준다)
const BARRIER = 'p, ul, ol, li, table, thead, tbody, tr, pre, blockquote, div, section, h1, h2, h3, h4, h5, h6, hr, dl, dt, dd, details, figure, [data-lines]';
// 글은 없지만 보이는 것 (줄바꿈을 세지 않는다)
const OPAQUE = 'img, svg, .katex, math, input, video, iframe';
const CALLOUT = /^\s*(?:>\s*)+\[!\w+\]\s*$/;
const FENCE = /^\s*(?:>\s*)*(?:`{3,}|~{3,})/;

const isCodeLines = (el) => el.tagName === 'CODE' && el.parentElement?.tagName === 'PRE' && !el.closest(ATOMIC);

function spanOf(el) {
  const m = /^(\d+)-(\d+)$/.exec(el.dataset.lines || '');
  return m ? [+m[1], +m[2]] : null;
}

/** 스크롤 상자 안 좌표의 기준 (화면 좌표 - 이 값 = 스크롤 상자 안 좌표) */
export function baseOf(view) {
  const sc = view.parentElement;
  return sc.getBoundingClientRect().top - sc.scrollTop;
}

/** 화면(view — #lec-view)의 줄 단위들. src: 원문 줄 배열 (md 의 빈 줄을 가리는 데 쓴다) */
export function collectUnits(view, src = []) {
  if (!view?.parentElement) return [];
  const base = baseOf(view);
  if (view.classList.contains('code-view')) return codeViewUnits(view, base);
  const blank = (n) => !String(src[n - 1] ?? '').replace(/^[\s>]*/, '').trim();

  const els = [];
  const owner = new Map();   // 줄 → 그 줄을 가진 가장 안쪽 요소 (안쪽 요소가 문서 차례로 뒤에 오므로 차례로 덮어쓴다)
  for (const el of view.querySelectorAll('[data-lines]')) {
    const span = spanOf(el);
    if (!span || el.closest('.front-matter')) continue;
    els.push(el);
    for (let n = span[0]; n <= span[1]; n++) owner.set(n, el);
  }
  const own = new Map();   // 요소 → 자기가 보여 주는 줄 (빈 줄 뺌, 코드는 그대로)
  for (const [n, el] of owner) {
    if (!isCodeLines(el) && blank(n)) continue;
    if (!own.has(el)) own.set(el, []);
    own.get(el).push(n);
  }

  const units = [];
  const orphans = [];   // 보이는 글이 없는 줄 [줄, 그 줄을 가진 요소]
  for (const el of els) {
    const lines = own.get(el)?.sort((x, y) => x - y);
    if (!lines?.length || !el.getClientRects().length) continue;   // 접힌 절·닫힌 details 안
    const r = el.getBoundingClientRect();
    const whole = (a, b) => units.push({ a, b, el, top: r.top - base, bottom: r.bottom - base });
    if (isCodeLines(el)) {
      codeUnits(el, r, base, spanOf(el), src, units);
      continue;
    }
    const inner = el.querySelector('[data-lines]');
    if (el.matches(ATOMIC) || (lines.length === 1 && !inner)) {   // 흔한 경우: 한 줄짜리 블록
      whole(lines[0], lines.at(-1));
      continue;
    }
    const segs = segmentsOf(el);
    if (!segs.length) {
      if (el.matches('.lec-cell, .lec-slide-wrap, .lec-textbox')) continue;   // 칸·장·박스글의 표시 줄은 어느 글의 것도 아니다
      if (inner) for (const n of lines) orphans.push([n, el]);   // 표의 구분 줄 등 — 이웃 단위에
      else whole(lines[0], lines.at(-1));   // 글 없는 블록 (hr 등)
      continue;
    }
    if (segs.length === 1 && !inner) {
      whole(lines[0], lines.at(-1));
      continue;
    }
    // 화면의 같은 줄에서 시작하는 원문 줄은 한 단위로 — 짧게 나눠 쓴 줄들이 한 화면 줄에 이어지면 따로 고를 수도, 현재 위치로 구별할 수도 없다
    let prev = null;
    groupsOf(lines, segs, src).forEach(({ lines: g, parts }) => {
      const box = boxOf(parts, base);
      if (!box) return;
      const last = parts.at(-1);
      if (prev && Math.abs(box.top - prev.top) < 2) {
        prev.b = g.at(-1);
        prev.bottom = Math.max(prev.bottom, box.bottom);
        prev.range = prev.range.cloneRange();
        prev.range.setEnd(last.endContainer, last.endOffset);
        return;
      }
      const range = parts[0].cloneRange();
      range.setEnd(last.endContainer, last.endOffset);
      prev = { a: g[0], b: g.at(-1), el, top: box.top, bottom: box.bottom, range };
      units.push(prev);
    });
  }
  mergeOrphans(units, orphans, blank);
  return units;
}

/**
 * 여러 줄 블록의 자기 줄들(lines)을 줄바꿈 자리로 나눈 조각(segs)과 잇는다: [{lines, parts}].
 * 조각이 모자라면 남는 줄을 붙인다 — 강조글의 [!NOTE] 줄(첫 줄)은 첫 조각에, 그 밖은 마지막 조각에
 * (setext 제목의 === 줄, 줄을 넘는 코드·수식 조각처럼 \n 이 남지 않는 것). 조각이 남으면 마지막 줄에 모두
 */
function groupsOf(lines, segs, src) {
  const k = segs.length;
  let groups;
  if (k >= lines.length) groups = lines.map((n) => [n]);
  else if (CALLOUT.test(src[lines[0] - 1] ?? '')) groups = [lines.slice(0, lines.length - k + 1), ...lines.slice(lines.length - k + 1).map((n) => [n])];
  else groups = [...lines.slice(0, k - 1).map((n) => [n]), lines.slice(k - 1)];
  return groups.map((g, i) => ({ lines: g, parts: i < groups.length - 1 ? [segs[i]] : segs.slice(i) }));
}

/** 펜스 코드의 내용 줄 [첫 줄, 끝 줄] (``` 줄 뺌) */
function codeSpan(span, src) {
  let [a, b] = span;
  if (FENCE.test(src[a - 1] ?? '')) {
    a += 1;
    if (b >= a && FENCE.test(src[b - 1] ?? '')) b -= 1;
  }
  return [a, b];
}

/** 코드 블록(<pre><code data-lines>)의 줄마다 — 줄바꿈하지 않으므로(white-space: pre) 줄 높이가 같다. ``` 줄은 뺀다 */
function codeUnits(el, r, base, span, src, units) {
  const [a, b] = codeSpan(span, src);
  const rows = Math.max(1, el.textContent.replace(/\n$/, '').split('\n').length);
  const h = r.height / rows;
  for (let n = a; n <= b && n - a < rows; n++) {
    const i = n - a;
    units.push({ a: n, b: n, el, top: r.top - base + i * h, bottom: r.top - base + (i + 1) * h, row: i });
  }
}

function codeViewUnits(view, base) {
  const units = [];
  for (const el of view.querySelectorAll('.cv-line[data-line]')) {
    if (!el.getClientRects().length) continue;   // csv 에서 거른 행
    const r = el.getBoundingClientRect();
    const a = Number(el.dataset.line);
    units.push({ a, b: Math.max(a, Number(el.dataset.end) || a), el, top: r.top - base, bottom: r.bottom - base });
  }
  return units;
}

/** 요소 자신의 글(안쪽 블록 밖)을 줄바꿈(\n) 자리로 나눈 조각들 (Range). 앞뒤의 공백·줄바꿈은 태그 사이의 것이라 세지 않는다 */
function segmentsOf(el) {
  const runs = [[]];
  const walk = (node) => {
    for (let c = node.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === Node.TEXT_NODE) runs.at(-1).push({ node: c });
      else if (c.nodeType === Node.ELEMENT_NODE) {
        if (c.matches(BARRIER)) runs.push([]);
        else if (c.matches(OPAQUE)) runs.at(-1).push({ opaque: c });
        else if (c.tagName !== 'BR') walk(c);
      }
    }
  };
  walk(el);
  const segs = [];
  for (const run of runs) {
    let start = null;
    let end = null;
    let pending = [];
    const cuts = [];
    const content = (from, to) => {
      if (!start) start = from;
      end = to;
      cuts.push(...pending);   // 글이 이어지면 그 앞의 줄바꿈은 진짜 줄바꿈
      pending = [];
    };
    for (const it of run) {
      if (it.opaque) {
        const parent = it.opaque.parentNode;
        const i = [...parent.childNodes].indexOf(it.opaque);
        content([parent, i], [parent, i + 1]);
        continue;
      }
      const s = it.node.nodeValue;
      for (let i = 0; i < s.length; i++) {
        if (s[i] === '\n') {
          if (start) pending.push([it.node, i]);
        } else if (s[i].trim()) content([it.node, i], [it.node, i + 1]);
      }
    }
    if (!start) continue;
    let from = start;
    for (const cut of cuts) {
      segs.push(rangeOf(from, cut));
      from = [cut[0], cut[1] + 1];
    }
    segs.push(rangeOf(from, end));
  }
  return segs;
}

function rangeOf(from, to) {
  const r = document.createRange();
  r.setStart(from[0], from[1]);
  r.setEnd(to[0], to[1]);
  return r;
}

/** 조각들이 보이는 세로 범위 (스크롤 상자 안 좌표) */
function boxOf(ranges, base) {
  let top = Infinity;
  let bottom = -Infinity;
  for (const range of ranges) {
    for (const r of range.getClientRects()) {
      if (!r.height) continue;
      top = Math.min(top, r.top - base);
      bottom = Math.max(bottom, r.bottom - base);
    }
  }
  return top < bottom ? { top, bottom } : null;
}

/** 보이는 글이 없는 줄을 같은 블록 안의 앞(빈 줄 건너)이나 뒤 단위에 붙인다 — 표의 구분 줄은 머리행에 */
function mergeOrphans(units, orphans, blank) {
  if (!orphans.length) return;
  const at = new Map();
  for (const u of units) for (let n = u.a; n <= u.b; n++) at.set(n, u);
  for (const [n, el] of orphans) {
    let u = null;
    for (let m = n - 1; m > 0 && !u; m--) {
      u = at.get(m);
      if (!u && !blank(m)) break;
    }
    if (!u || !el.contains(u.el)) u = at.get(n + 1);
    if (!u || !el.contains(u.el)) continue;
    u.a = Math.min(u.a, n);
    u.b = Math.max(u.b, n);
    at.set(n, u);
  }
}

/** 원문 줄 line 을 보여 주는 단위의 차례. 없으면(빈 줄·없어진 줄) 줄 번호가 가장 가까운 단위, 단위가 없으면 -1 */
export function indexOfLine(units, line) {
  let near = -1;
  let gap = Infinity;
  for (let i = 0; i < units.length; i++) {
    const u = units[i];
    if (line >= u.a && line <= u.b) return i;
    const d = line < u.a ? u.a - line : line - u.b;
    if (d < gap) {
      gap = d;
      near = i;
    }
  }
  return near;
}

/** 원문 줄 line 을 보여 주는 단위가 있는지 */
export const hasLine = (units, line) => units.some((u) => line >= u.a && line <= u.b);

/** 원문 줄 line 이 든 가장 작은 블록 (코드 화면은 그 줄). 없으면 null */
export function blockOfLine(view, line) {
  const row = view.querySelector(`.cv-line[data-line="${Number(line)}"]`);
  if (row) return row;
  let best = null;
  let size = Infinity;
  for (const el of view.querySelectorAll('[data-lines]')) {
    const s = spanOf(el);
    if (s && s[0] <= line && line <= s[1] && s[1] - s[0] < size) {
      best = el;
      size = s[1] - s[0];
    }
  }
  return best;
}

/**
 * 세로 위치 y(스크롤 상자 안 좌표)의 단위 차례: y 를 품은 것, 없으면(블록 사이 여백) 가장 가까운 것.
 * 여러 줄 문단은 이웃 줄과 한 화면 줄을 나눠 쓰므로, 겹치면 point(화면 좌표 {x, y})의 글자가 든 줄로 고른다
 */
export function unitAt(units, y, point = null) {
  const hits = [];
  let near = -1;
  let gap = Infinity;
  const under = point && document.elementFromPoint(point.x, point.y);
  const tag = under?.closest('.lec-tag');   // 구조 보기의 꼬리표는 한 줄에 나란하다 — 누른 그것
  if (tag && units.some((u) => u.el === tag)) return units.findIndex((u) => u.el === tag);
  const cell = under?.closest('.lec-cell');   // 슬라이드의 칸은 나란히 놓여 높이만으로는 어느 칸인지 모른다
  units.forEach((u, i) => {
    if (cell && !cell.contains(u.el)) return;
    if (y >= u.top && y <= u.bottom) hits.push(i);
    else {
      const d = y < u.top ? u.top - y : y - u.bottom;
      if (d < gap) {
        gap = d;
        near = i;
      }
    }
  });
  if (hits.length > 1 && point) {
    const pos = document.caretRangeFromPoint?.(point.x, point.y);
    const hit = pos && hits.find((i) => units[i].range?.isPointInRange(pos.startContainer, pos.startOffset));
    if (hit != null) return hit;
  }
  if (!hits.length) return near;
  return hits.reduce((best, i) => (units[i].bottom - units[i].top < units[best].bottom - units[best].top ? i : best));
}

/** 단위의 첫 화면 줄 가운데 높이 (스크롤 상자 안 좌표) — 현재 위치 표시(삼각형)를 둔다 */
export function markOf(u, base) {
  const h = u.bottom - u.top;
  if (u.row != null) return u.top + h / 2;
  if (!u.el.matches(ATOMIC)) {
    let range = u.range;
    if (!range) {
      range = document.createRange();
      range.selectNodeContents(u.el);
    }
    const r = [...range.getClientRects()].find((x) => x.height > 0 && x.width > 0);
    const y = r && (r.top + r.bottom) / 2 - base;
    if (y != null && y >= u.top - 2 && y <= u.bottom + 2) return y;
  }
  return u.top + Math.min(h / 2, 12);
}

// ---- 한 줄 편집 (lineedit.js, D76) ------------------------------------------------

// 글이 보이지 않는 표시 줄: 강조글의 [!NOTE] 줄, 표의 구분 줄, setext 제목의 밑줄, 코드 펜스
const MARKER_LINE = /^\s*(?:>\s*)*(?:\[!\w+\]\s*|\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*|=+\s*|-+\s*|(?:`{3,}|~{3,}).*)$/;

/** 단위에서 한 줄 편집으로 고칠 수 있는 원문 줄들 (다이어그램·수식·csv 표·표시 줄 뺌, 코드의 빈 줄은 넣음) */
export function editableLines(u, src) {
  if (u.el.matches(ATOMIC) || u.el.closest('.csv-table')) return [];
  if (u.row != null || u.el.classList.contains('cv-line')) return [u.a];
  const out = [];
  for (let n = u.a; n <= u.b; n++) {
    const s = String(src[n - 1] ?? '');
    if (s.replace(/^[\s>]*/, '').trim() && !MARKER_LINE.test(s)) out.push(n);
  }
  return out;
}

const contentsOf = (node) => {
  const r = document.createRange();
  r.selectNodeContents(node);
  return r;
};

/** 코드 요소 안 row 번째(0부터) 줄의 글 범위 (줄 끝의 \n 뺌). 없으면 null */
function codeRowRange(el, row) {
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let n = 0;
  let start = row === 0 ? [el, 0] : null;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const s = node.nodeValue;
    for (let i = 0; i < s.length; i++) {
      if (s[i] !== '\n') continue;
      if (n === row) return rangeOf(start, [node, i]);
      n += 1;
      if (n === row) start = [node, i + 1];
    }
  }
  return start ? rangeOf(start, [el, el.childNodes.length]) : null;
}

/** 요소의 자기 줄 (안쪽 [data-lines] 블록이 가진 줄과 빈 줄 뺌) */
function ownLines(el, src) {
  const span = spanOf(el);
  const inner = new Set();
  for (const x of el.querySelectorAll('[data-lines]')) {
    const s = spanOf(x);
    if (s) for (let n = s[0]; n <= s[1]; n++) inner.add(n);
  }
  const out = [];
  for (let n = span[0]; n <= span[1]; n++) {
    if (!inner.has(n) && String(src[n - 1] ?? '').replace(/^[\s>]*/, '').trim()) out.push(n);
  }
  return out;
}

/**
 * 원문 줄 line 이 화면에 보이는 자리 — 한 줄 편집(lineedit.js)이 그 자리에 글 칸을 넣는다.
 * {kind: 'text'|'code'|'table', el(그 줄을 가진 블록), ranges(글 칸을 넣을 Range — 표는 칸마다), whole(블록의 글 전체인지), fence(코드 블록의 ``` 줄)}.
 * 고칠 수 없는 줄(다이어그램·수식·raw HTML·표시 줄·csv 표·접힌 곳)이면 null
 */
export function lineSlot(view, line, src) {
  if (view.classList.contains('code-view')) {
    if (view.querySelector('.csv-table')) return null;
    const row = view.querySelector(`.cv-line[data-line="${Number(line)}"]`);
    const text = row?.querySelector('.cv-text');
    return text && row.getClientRects().length ? { kind: 'code', el: row, ranges: [contentsOf(text)], whole: true } : null;
  }
  let el = null;
  for (const x of view.querySelectorAll('[data-lines]')) {
    const s = spanOf(x);
    if (s && line >= s[0] && line <= s[1] && !x.closest('.front-matter')) el = x;   // 문서 차례로 뒤의 것이 더 안쪽
  }
  if (!el || !el.getClientRects().length || el.closest(ATOMIC)) return null;
  if (isCodeLines(el)) {
    const span = spanOf(el);
    const [a, b] = codeSpan(span, src);
    const range = line >= a && line <= b ? codeRowRange(el, line - a) : null;
    return range && { kind: 'code', el, ranges: [range], fence: a > span[0] ? String(src[span[0] - 1] ?? '') : '' };
  }
  if (el.tagName === 'TR') return { kind: 'table', el, ranges: [...el.cells].map(contentsOf), whole: true };
  if (el.matches('.lec-cell, .lec-slide-wrap, .lec-textbox')) return null;   // 칸·장·박스글의 표시 줄
  const lines = ownLines(el, src);
  if (!lines.includes(line) || MARKER_LINE.test(String(src[line - 1] ?? ''))) return null;
  const segs = segmentsOf(el);
  if (!segs.length) return null;   // 글이 없는 블록 (hr, 표·목록 자체)
  if (lines.length === 1 && !el.querySelector('[data-lines]')) return { kind: 'text', el, ranges: [contentsOf(el)], whole: true };
  const g = groupsOf(lines, segs, src).find((x) => x.lines.includes(line));
  if (!g) return null;
  const range = g.parts[0].cloneRange();
  const last = g.parts.at(-1);
  range.setEnd(last.endContainer, last.endOffset);
  return { kind: 'text', el, ranges: [range], whole: false };
}
