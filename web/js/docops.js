// 문서 구성 요소의 계산 (D107~, DOM 없음): 원문 줄 배열을 받아 바뀐 줄 배열을 돌려준다. 저장은 lineedit.js 가 commit 으로 한다.
// lineops.js 가 줄을 다룬다면 여기는 줄의 종류, 제목과 절을 다룬다. 줄 번호는 1부터, 잘못된 요청은 {error: 까닭 이름}.
//
// - 표시는 사람이 고치지 않는다: setKind 가 줄의 표시를 떼고 새 표시를 단다.
// - 제목 줄은 절의 손잡이다: 수준 바꾸기(shiftHeadings)는 하위 절까지, 옮기기(moveSection)·지우기(sectionSpan)는 본문까지 함께.

import { quoteOf, itemOf, isBlank, fencesOf, fenceAt, frontEnd, blocksOf, blockAt, tableIn, deckOf } from './lineops.js';

const HEADING = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;

/** 표시를 뗀 글: 인용 >·목록 표시·할 일 칸·제목 # */
export function bareText(line) {
  let s = line.slice(quoteOf(line).length);
  const it = itemOf(s);
  if (it) s = it.text;
  const h = HEADING.exec(s);
  return (h ? h[2] ?? '' : s).trim();
}

/** 제목 줄의 수준 (1~6). 제목이 아니면 0 */
export const headLevel = (line) => HEADING.exec(line)?.[1].length ?? 0;

/** 문서의 제목들 [{n, level}] — 머리 설정과 코드 블록 안은 뺀다 */
export function headsOf(lines) {
  const fences = fencesOf(lines);
  const start = frontEnd(lines);
  const out = [];
  lines.forEach((s, i) => {
    const n = i + 1;
    const level = n > start && !fenceAt(fences, n) ? headLevel(s) : 0;
    if (level) out.push({ n, level });
  });
  return out;
}

/** 빈 줄을 앞뒤로 둔다 — 줄 앞뒤가 글이면 블록이 이어지지 않게 */
const padded = (before, body, after) => [
  ...before,
  ...(before.length && before.at(-1).trim() ? [''] : []),
  ...body,
  ...(after.length && after[0].trim() ? [''] : []),
  ...after,
];

/**
 * 줄 a~b 를 kind 로 바꾼다: 'h1'~'h6', 'para', 'bullet', 'number', 'task', 'quote'. {lines, line, a, b} — 바뀐 범위의 줄 번호.
 * bare: 제목의 번호를 떼는 함수 (없으면 글 그대로). 코드 블록·표·구분선은 바꾸지 않는다
 */
export function setKind(lines, a, b, kind, { bare = (s) => s } = {}) {
  const fences = fencesOf(lines);
  const blocks = blocksOf(lines);
  const texts = [];
  for (let n = a; n <= b; n++) {
    const s = lines[n - 1];
    if (isBlank(s)) continue;
    const blk = blockAt(blocks, n);
    if (fenceAt(fences, n) || blk?.kind === 'front' || blk?.kind === 'wall') return { error: 'kind' };
    if (tableIn(lines, blk)) return { error: 'table-kind' };
    const text = bareText(s);
    if (!text) continue;
    texts.push(headLevel(s) ? bare(text) : text);
  }
  if (!texts.length) return { error: 'kind' };
  const level = /^h([1-6])$/.exec(kind)?.[1];
  const quoted = quoteOf(lines[a - 1]);
  const prev = itemOf(lines[a - 2] ?? '');
  const start = prev?.ordered && kind === 'number' ? prev.num + 1 : 1;
  let body;
  if (level) body = texts.flatMap((s, i) => [...(i ? [''] : []), `${'#'.repeat(Number(level))} ${s}`]);
  else if (kind === 'para') body = texts.flatMap((s, i) => [...(i ? [''] : []), s]);
  else if (kind === 'quote') body = texts.flatMap((s, i) => [...(i ? ['>'] : []), `> ${s}`]);
  else {
    const mark = (i) => ({ bullet: '- ', number: `${start + i}. `, task: '- [ ] ' }[kind]);
    if (!mark(0)) return { error: 'kind' };
    body = texts.map((s, i) => `${quoted}${mark(i)}${s}`);
  }
  const before = lines.slice(0, a - 1);
  const after = lines.slice(b);
  const list = !level && kind !== 'para' && kind !== 'quote';
  const near = (s) => list && !!s && !!itemOf(s);   // 같은 목록이면 빈 줄 없이 잇는다
  const next = near(before.at(-1)) || near(after[0])
    ? [...before, ...body, ...after]
    : padded(before, body, after);
  const line = next.indexOf(body[0], Math.max(0, a - 1)) + 1;
  return { lines: next, line, a: line, b: line + body.length - 1 };
}

/** 제목 줄 n 의 절이 끝나는 줄 — 같거나 높은 수준의 다음 제목 앞 (끝의 빈 줄은 뺀다) */
export function sectionEnd(lines, n) {
  const level = headLevel(lines[n - 1]);
  const next = headsOf(lines).find((h) => h.n > n && h.level <= level);
  let end = next ? next.n - 1 : lines.length;
  while (end > n && !lines[end - 1].trim()) end -= 1;
  return end;
}

/** 제목 줄 n 과 그 하위 제목의 수준을 dir 만큼 바꾼다 (dir > 0 이면 안으로). 1~6 을 벗어나면 {error: 'edge'} */
export function shiftHeadings(lines, n, dir) {
  if (!headLevel(lines[n - 1])) return { error: 'not-heading' };
  const end = sectionEnd(lines, n);
  const heads = headsOf(lines).filter((h) => h.n >= n && h.n <= end);
  if (heads.some((h) => h.level + dir < 1 || h.level + dir > 6)) return { error: 'edge' };
  const next = lines.slice();
  for (const h of heads) next[h.n - 1] = next[h.n - 1].replace(/#{1,6}/, '#'.repeat(h.level + dir));
  return { lines: next, line: n };
}

/** 절의 범위 [첫 줄, 다음 절 앞 줄] — 뒤의 빈 줄까지 */
function sectionBlock(lines, heads, h) {
  const next = heads.find((x) => x.n > h.n && x.level <= h.level);
  return [h.n, next ? next.n - 1 : lines.length];
}

/** 제목 줄 n 의 절을 같은 수준의 앞뒤 절과 바꾼다 — 본문과 하위 절까지 함께 (D107) */
export function moveSection(lines, n, dir) {
  if (deckOf(lines)) return { error: 'edge' };
  const heads = headsOf(lines);
  const me = heads.find((h) => h.n === n);
  if (!me) return { error: 'not-heading' };
  const [a, b] = sectionBlock(lines, heads, me);
  let other;
  if (dir < 0) {
    other = heads.findLast((h) => h.n < n && h.level <= me.level);
    if (other?.level !== me.level) return { error: 'edge' };
  } else {
    other = heads.find((h) => h.n > b);
    if (other?.level !== me.level) return { error: 'edge' };
  }
  const [c, d] = sectionBlock(lines, heads, other);
  const first = dir < 0 ? [c, d] : [a, b];
  const second = dir < 0 ? [a, b] : [c, d];
  const trim = (x) => {
    const out = x.slice();
    while (out.length && !out.at(-1).trim()) out.pop();
    return out;
  };
  const up = trim(lines.slice(first[0] - 1, first[1]));
  const down = lines.slice(second[0] - 1, second[1]);
  const tail = down.slice(trim(down).length);   // 문서 끝의 빈 줄은 끝에 남긴다
  const next = [...lines.slice(0, first[0] - 1), ...trim(down), '', ...up, ...tail, ...lines.slice(second[1])];
  const line = dir < 0 ? first[0] : first[0] + trim(down).length + 1;
  return { lines: next, line };
}

/** 절을 지울 범위 [a, b] — 뒤의 빈 줄까지 (지운 뒤 빈 줄이 겹치지 않게) */
export function sectionSpan(lines, n) {
  const heads = headsOf(lines);
  const me = heads.find((h) => h.n === n);
  return me ? sectionBlock(lines, heads, me) : null;
}

/** 절을 지운다 {lines, line, a, b} */
export function deleteSection(lines, n) {
  const span = sectionSpan(lines, n);
  if (!span) return { error: 'not-heading' };
  const [a, b] = span;
  const next = [...lines.slice(0, a - 1), ...lines.slice(b)];
  return { lines: next, line: Math.max(1, Math.min(a, next.length)), a, b };
}
