// 문장 속 서식의 계산 (D141, DOM 없음): 굵게·기울임·취소선·코드·형광펜·글자색.
// 고른 글을 표시로 감싸고, 같은 서식을 다시 하면 풀고, 형광펜·글자색은 색을 차례로 바꾸다가 마지막에 푼다.
// 칸의 글(lineedit.js — 고른 글에)과 줄 전체(docops.js 의 formatLines — 줄의 글 통째에)가 함께 쓴다. 칸 안에서 서식을 보이게
// 칠하는 범위도 여기서 낸다 (paintOf). 규칙 시험은 tools/edges/inlinefmt_cases.js.
//
// 원문에 들어가는 것 — 굵게 `**글**`, 기울임 `*글*`, 취소선 `~~글~~`, 코드 `` `글` ``, 형광펜 `<mark>글</mark>`(노랑)·
// `<mark class="green">글</mark>`, 글자색 `<span style="color:red">글</span>`. 색은 이름 있는 몇 가지뿐이다 (미세한 색은 고르지 않는다).
// 형광펜의 색은 class 라 다른 프로그램에서는 보통 형광펜으로 보이고, 글자색은 style 이라 style 을 그리는 곳이면 그 색으로 보인다.

/** 형광펜의 색 — '' 는 노랑(class 없는 <mark>). 차례로 바뀐다 */
export const MARK_COLORS = ['', 'green', 'pink', 'blue'];
/** 글자색 — 차례로 바뀐다. goldenrod 는 밝은 바탕에서도 읽히는 노랑이다 */
export const TEXT_COLORS = ['red', 'blue', 'green', 'goldenrod'];
/** 감싸는 서식 */
export const SIMPLE = { bold: '**', italic: '*', strike: '~~', code: '`' };
const VALUES = { mark: MARK_COLORS, color: TEXT_COLORS };

const openOf = (kind, value = '') => (kind === 'mark' ? (value ? `<mark class="${value}">` : '<mark>')
  : kind === 'color' ? `<span style="color:${value}">` : SIMPLE[kind]);
const closeOf = (kind) => (kind === 'mark' ? '</mark>' : kind === 'color' ? '</span>' : SIMPLE[kind]);

/** 글자 수가 같은 가림 글 — 가린 곳은 다른 서식의 표시로 읽지 않는다 */
const blank = (s, a, b) => s.slice(0, a) + '\u0001'.repeat(b - a) + s.slice(b);

/**
 * 글 속의 서식 범위들 [{kind, value, oa, a, b, cb}] — oa~a 가 여는 표시, a~b 가 안의 글, b~cb 가 닫는 표시.
 * 코드 안은 다른 서식으로 읽지 않는다. 여닫는 짝이 맞는 것만 (Markdown 의 모든 경우를 따지지는 않는다 — 한 줄의 흔한 꼴)
 */
export function spansOf(text) {
  const out = [];
  let masked = text;
  const take = (kind, re, src, hide) => {
    for (const m of src.matchAll(re)) {
      const value = m.length > 2 ? m[1] ?? '' : '';
      const inner = m[m.length - 1];
      const oa = m.index;
      const cb = oa + m[0].length;
      const b = cb - closeOf(kind).length;
      const a = b - inner.length;
      out.push({ kind, value, oa, a, b, cb });
      if (hide === 'all') masked = blank(masked, oa, cb);
      else if (hide === 'marks') masked = blank(blank(masked, oa, a), b, cb);
    }
  };
  take('code', /`([^`]+)`/g, text, 'all');
  take('bold', /\*\*(?=[^\s*\u0001]|\*[^\s*])(.+?)(?<=[^\s\u0001])\*\*(?!\*)/g, masked, 'marks');
  take('italic', /(?<!\*)\*(?=[^\s*\u0001])([^*\u0001]*?[^\s*\u0001]|[^\s*\u0001])\*(?!\*)/g, masked, null);
  take('strike', /~~(?=[^\s\u0001])(.+?)(?<=[^\s\u0001])~~/g, masked, null);
  take('mark', /<mark(?: class="(green|pink|blue)")?>(.*?)<\/mark>/g, masked, null);
  take('color', /<span style="color:(red|blue|green|goldenrod)">(.*?)<\/span>/g, masked, null);
  return out.sort((x, y) => x.oa - y.oa);
}

/** 고른 범위 a~b 를 감싼 그 서식 — 안의 글(이나 그 일부)을 골랐거나, 표시까지 골랐거나, 커서가 그 안에 있을 때 */
function around(text, a, b, kind) {
  return spansOf(text).filter((s) => s.kind === kind && ((s.a <= a && b <= s.b) || (s.oa === a && s.cb === b)))
    .sort((x, y) => (x.cb - x.oa) - (y.cb - y.oa))[0] ?? null;
}

const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));

function unwrap(text, s, a, b) {
  const inner = text.slice(s.a, s.b);
  const d = s.a - s.oa;
  return { text: text.slice(0, s.oa) + inner + text.slice(s.cb), a: clamp(a - d, s.oa, s.oa + inner.length), b: clamp(b - d, s.oa, s.oa + inner.length) };
}

/** 감싼다 — 고른 글 앞뒤의 공백은 표시 밖에 둔다 ('** 글 **' 은 굵게 그려지지 않는다). 고른 글이 없으면 빈 표시 사이에 커서 */
function wrap(text, a, b, kind, value) {
  while (a < b && /\s/.test(text[a])) a += 1;
  while (b > a && /\s/.test(text[b - 1])) b -= 1;
  const open = openOf(kind, value);
  return { text: text.slice(0, a) + open + text.slice(a, b) + closeOf(kind) + text.slice(b), a: a + open.length, b: b + open.length };
}

/**
 * 고른 범위 a~b (a = b 면 커서)에 서식 kind 를 한다 → {text, a, b} (b 는 안의 글의 끝 — 그대로 고른 채 남는다).
 * 굵게·기울임·취소선·코드: 이미 그 서식이면 풀고, 아니면 감싼다.
 * 형광펜(mark)·글자색(color): 없으면 첫 색, 있으면 다음 색, 마지막 색이면 푼다. value 를 주면 그 색으로 (같은 색이면 푼다 — 메뉴)
 */
export function applyFormat(text, a, b, kind, value) {
  if (a > b) [a, b] = [b, a];
  const s = around(text, a, b, kind);
  const values = VALUES[kind];
  if (!values) return s ? unwrap(text, s, a, b) : wrap(text, a, b, kind);
  if (!s) return wrap(text, a, b, kind, value ?? values[0]);
  const next = value !== undefined ? (value === s.value ? undefined : value) : values[values.indexOf(s.value) + 1];
  if (next === undefined) return unwrap(text, s, a, b);
  const open = openOf(kind, next);
  const d = open.length - (s.a - s.oa);
  const inside = a >= s.a;   // 표시까지 고른 것이면 안의 글을 고른 것으로 바꾼다
  return { text: text.slice(0, s.oa) + open + text.slice(s.a), a: inside ? a + d : s.a + d, b: inside ? b + d : s.b + d };
}

/** 고른 범위에 걸친 서식을 모두 푼다 (커서면 그 자리를 감싼 것) → {text, a, b} */
export function clearFormats(text, a, b) {
  if (a > b) [a, b] = [b, a];
  for (let guard = 0; guard < 40; guard += 1) {
    const s = spansOf(text).filter((x) => (a === b ? x.oa <= a && a <= x.cb : x.oa < b && a < x.cb)).at(-1);
    if (!s) break;
    const before = text.length;
    const d = s.a - s.oa;
    text = text.slice(0, s.oa) + text.slice(s.a, s.b) + text.slice(s.cb);
    a = a <= s.oa ? a : clamp(a - d, s.oa, s.b - d);
    b = b >= s.cb ? b - (before - text.length) : clamp(b - d, s.oa, s.b - d);
  }
  return { text, a, b };
}

/** 글 통째가 그 서식 하나로 감싸여 있으면 그 범위 (앞뒤 공백은 빼고), 아니면 null */
export function wholeOf(text, kind) {
  const t = text.trim();
  if (!t) return null;
  const at = text.indexOf(t);
  return spansOf(text).find((s) => s.kind === kind && s.oa === at && s.cb === at + t.length) ?? null;
}

/** 그 서식의 표시를 모두 걷는다 */
export function stripFormat(text, kind) {
  for (const s of spansOf(text).filter((x) => x.kind === kind).reverse()) text = text.slice(0, s.oa) + text.slice(s.a, s.b) + text.slice(s.cb);
  return text;
}

/** 글 통째를 그 서식으로 — 일부에 있던 같은 서식은 걷고 통째로 (표시가 겹치지 않게). 빈 글은 그대로 */
export function wrapWhole(text, kind, value) {
  const inner = stripFormat(text, kind).trim();
  if (!inner) return text;
  const lead = /^\s*/.exec(text)[0];
  const tail = /\s*$/.exec(text)[0];
  return `${lead}${openOf(kind, value)}${inner}${closeOf(kind)}${tail}`;
}

/** 줄 전체에 한 번 누를 때의 다음 색 — 지금 통째로 그 서식이 아니면 첫 색, 마지막 색 다음은 undefined (푼다) */
export function nextValue(text, kind) {
  const values = VALUES[kind];
  const s = wholeOf(text, kind);
  return s ? values[values.indexOf(s.value) + 1] : values[0];
}

/**
 * 칸 안에서 서식이 보이게 칠할 범위 — { marks: [[a, b]…] (표시 글자 — 흐리게), 그리고 서식마다 [[a, b]…] }.
 * 키는 bold·italic·strike·code·mark·mark-green·mark-pink·mark-blue·color-red·color-blue·color-green·color-goldenrod
 */
export function paintOf(text) {
  /** @type {Record<string, number[][]>} */
  const out = { marks: [] };
  for (const s of spansOf(text)) {
    out.marks.push([s.oa, s.a], [s.b, s.cb]);
    const key = s.kind === 'mark' ? (s.value ? `mark-${s.value}` : 'mark') : s.kind === 'color' ? `color-${s.value}` : s.kind;
    (out[key] ||= []).push([s.a, s.b]);
  }
  return out;
}
