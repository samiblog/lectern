// 문서 구성 요소의 계산 (D107~, DOM 없음): 원문 줄 배열을 받아 바뀐 줄 배열을 돌려준다. 저장은 lineedit.js 가 commit 으로 한다.
// lineops.js 가 줄을 다룬다면 여기는 줄의 종류, 제목과 절을 다룬다. 줄 번호는 1부터, 잘못된 요청은 {error: 까닭 이름}.
//
// - 표시는 사람이 고치지 않는다: setKind 가 줄의 표시를 떼고 새 표시를 단다.
// - 제목 줄은 절의 손잡이다: 수준 바꾸기(shiftHeadings)는 하위 절까지, 옮기기(moveSection)·지우기(sectionSpan)는 본문까지 함께.

import { quoteOf, itemOf, isBlank, fencesOf, fenceAt, frontEnd, blocksOf, blockAt, tableIn, deckOf, bodyEnd, notesStart, itemSpan, indentLines, indentItem, outdentItem,
  listNear, renumberFrom, renumberAt, siblingsOf } from './lineops.js';
import { wholeOf, stripFormat, wrapWhole, nextValue, spansOf, SIMPLE } from './inlinefmt.js';

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
 * 줄 a~b 를 kind 로 바꾼다: 'h1'~'h6', 'para', 'bullet', 'number', 'task', 'quote'. {lines, line, a, b, renumbered} — 바뀐 범위의 줄 번호.
 * bare: 제목의 번호를 떼는 함수 (없으면 글 그대로). 코드 블록·표·구분선은 바꾸지 않는다.
 * 이웃 (D155): 고른 줄만 바꾸고, 이웃은 뜻이 깨질 때만 따라 고친다 —
 * - 강조글·인용 안의 줄은 안에서 바꾼다 (머리 줄 [!NOTE] 은 두고, 사이는 '>' 로). 인용 글을 문단으로 바꾸면 인용 밖으로 (Q 를 다시 누른 것과 같다)
 * - 목록으로 바꾸는 줄의 바로 위·아래가 같은 종류의 목록이면 거기에 붙는다 — 그 목록의 표시와 번호, 빈 줄로 띄운 목록이면 빈 줄 하나
 * - 번호 목록에서 줄이 빠지면 뒤 항목의 번호를 앞 항목에 잇는다 (renumbered: 고른 줄 밖에서 번호가 바뀐 항목 수)
 */
export function setKind(lines, a, b, kind, { bare = (s) => s } = {}) {
  const fences = fencesOf(lines);
  const blocks = blocksOf(lines);
  if (a <= b && BOX_HEAD.test(lines[a - 1])) a += 1;   // 강조글의 머리 줄은 두고 본문만
  const texts = [];
  const leads = [];   // 줄의 들여쓰기 — 목록 항목, 항목 안의 글 줄 (D152 — 목록끼리 바꿀 때 지킨다)
  const quotes = [];
  const kinds = [];
  const items = [];   // 고른 줄 가운데 목록 항목 {n, it}
  let firstText = 0;   // 고른 줄의 첫·끝 글 줄 — 앞뒤의 빈 줄을 함께 골랐어도 이웃과의 빈 줄을 바로 센다
  let lastText = 0;
  for (let n = a; n <= b; n++) {
    const s = lines[n - 1];
    if (isBlank(s)) continue;
    if (BOX_HEAD.test(s)) return { error: 'box-head' };
    const blk = blockAt(blocks, n);
    if (fenceAt(fences, n) || blk?.kind === 'front' || blk?.kind === 'wall') return { error: 'kind' };
    if (tableIn(lines, blk)) return { error: 'table-kind' };
    const text = bareText(s);
    if (!text) continue;
    const it = itemOf(s);
    texts.push(headLevel(s.slice(quoteOf(s).length)) ? bare(text) : text);
    leads.push(it?.lead ?? (itemSpan(lines, n) ? /^[ \t]*/.exec(s.slice(quoteOf(s).length))[0] : ''));   // 항목 안의 글 줄(이어진 문단)도 그 들여쓰기
    quotes.push(quoteOf(s));
    kinds.push(kindOfLine(s));
    if (it) items.push({ n, it });
    firstText ||= n;
    lastText = n;
  }
  if (!texts.length) return { error: a > b ? 'box-head' : 'kind' };
  const level = /^h([1-6])$/.exec(kind)?.[1];
  const list = ['bullet', 'number', 'task'].includes(kind);
  if (!level && !list && kind !== 'para' && kind !== 'quote') return { error: 'kind' };
  const quoted = quotes[0];
  if (quotes.some((x) => x !== quoted)) return { error: 'quote-mix' };   // 인용·강조글 안과 밖을 함께 — 한쪽으로 끌려 들어간다
  const inBox = !!quoted && !!boxAt(lines, a);
  const plain = kinds.every((k) => k === 'quote');   // 인용의 글 줄뿐 (목록·제목이 아닌)
  const inside = !!quoted && (list || inBox || kind !== 'para' || !plain);   // 인용 안에서 바꾼다 — 인용 글을 문단으로 바꾸는 것만 밖으로 (Q 를 다시 누른 것)
  const q = inside || list ? quoted : '';
  const sep = q.trimEnd();   // 블록 사이의 빈 줄 — 인용 안이면 '>'
  const outQuote = !!quoted && !q;   // 인용 밖으로 뺀다 — 이웃의 '>' 빈 줄은 보통 빈 줄로
  const widthOf = (lead) => itemOf(`${quoted}${lead}- x`)?.width ?? 0;
  const width = widthOf(leads[0]);
  // 이웃 목록 (D155): 같은 종류면 붙인다. 번호는 '번호 목록', 표시(-·*)는 글머리·할 일
  const fits = (x) => !!x && (kind === 'number' ? x.it.ordered : !x.it.ordered);
  const last = itemOf(lines[b - 1] ?? '');
  const own = last ? itemSpan(lines, b) : null;
  const kidsEnd = own && own[0] === b && own[1] > b ? own[1] : b;   // 마지막 줄이 하위가 있는 항목이면 그 하위의 끝 — 아래 이웃은 그 뒤에서 찾는다
  const nearEnd = kidsEnd > b ? kidsEnd : lastText;   // 이웃은 글 줄에서 찾는다 — 함께 고른 빈 줄은 인용 깊이가 없다
  const up = list && fits(listNear(lines, firstText, -1, width)) ? listNear(lines, firstText, -1, width) : null;
  const near = list ? listNear(lines, nearEnd, 1, width) : null;
  const sameMark = (x, y) => (x.ordered ? x.delim === y.delim : x.marker === y.marker);   // 표시가 다르면 Markdown 에서 다른 목록이다
  const down = fits(near) && (!up || sameMark(up.it, near.it)) ? near : null;
  const like = up?.it ?? down?.it;
  const flatOf = (x) => {   // 모두 같은 번호로 쓴 번호 목록이면 그 번호
    if (!x?.it.ordered) return 0;
    const ns = siblingsOf(lines, x.n).map((y) => itemOf(lines[y - 1]).num);
    return ns.length > 1 && ns.every((v) => v === ns[0]) ? ns[0] : 0;
  };
  let body;
  // 하위 항목은 부모 항목 안의 글로 남는다 — 들여쓰기는 고른 첫 줄보다 깊지 않게 (부모와 함께 바꾼 하위 줄은 부모의 수준으로)
  const keep = (i) => (outQuote ? '' : leads.slice(0, i + 1).reduce((x, y) => (y.length < x.length ? y : x)));   // 그 줄까지 가장 얕은 줄의 들여쓰기
  if (level) body = texts.flatMap((t, i) => [...(i ? [sep] : []), `${q}${keep(i)}${'#'.repeat(Number(level))} ${t}`]);
  else if (kind === 'para' || (kind === 'quote' && inside)) body = texts.flatMap((t, i) => [...(i ? [sep] : []), `${q}${keep(i)}${t}`]);
  else if (kind === 'quote') body = texts.flatMap((t, i) => [...(i ? ['>'] : []), `> ${t}`]);
  else {
    const dot = like?.ordered ? like.delim : '.';
    const dash = like && !like.ordered ? like.marker : '-';
    // 번호는 수준(들여쓰기)마다 센다 (D155): 처음 번호는 위의 같은 수준 번호 항목의 다음(같은 번호로 쓴 목록이면 그 번호), 없으면
    // 아래에 붙는 같은 번호 목록의 번호, 고른 줄이 번호 항목이었으면 그 번호, 아니면 1. 바깥 항목이 나오면 안쪽은 1 부터 다시
    const firstOf = new Map();
    for (const lead of new Set(leads)) {
      const prev = listNear(lines, firstText, -1, widthOf(lead));
      const below = listNear(lines, nearEnd, 1, widthOf(lead));
      const was = items.find((x) => x.it.lead === lead && x.it.ordered);
      firstOf.set(lead, prev?.it.ordered ? { n: flatOf(prev) || prev.it.num + 1, flat: !!flatOf(prev) }
        : flatOf(below) ? { n: flatOf(below), flat: true } : { n: was?.it.num ?? 1, flat: false });
    }
    const counts = new Map();
    const used = new Set();
    const nums = leads.map((lead) => {
      for (const k of [...counts.keys()]) if (k.length > lead.length) counts.delete(k);
      const f = firstOf.get(lead);
      const n = counts.has(lead) ? (f.flat ? f.n : counts.get(lead) + 1) : used.has(lead) ? 1 : f.n;
      counts.set(lead, n);
      used.add(lead);
      return n;
    });
    const mark = (i) => ({ bullet: `${dash} `, number: `${nums[i]}${dot} `, task: `${dash} [ ] ` }[kind]);
    body = texts.map((t, i) => `${q}${leads[i]}${mark(i)}${t}`);
  }
  // 하위가 있는 항목을 목록 밖(제목·문단·인용)으로 바꾸면 하위 항목을 그 항목이 있던 수준으로 당긴다 — 네 칸 들여쓴 하위가 코드 블록이 되지 않게 (D152)
  let source = lines;
  if (own && own[0] === b && own[1] > b && !list) source = indentLines(lines, b + 1, own[1], last.width - last.content);
  // 붙는 목록 사이의 빈 줄은 그 목록이 쓰던 대로 — 항목이 하나뿐이면 지금 있는 대로
  const upEnd = up ? Math.min(up.end, a - 1) : 0;   // 고른 줄이 위 항목의 이어진 줄이었으면 거기까지
  const gapUp = up && lines.slice(upEnd, firstText - 1).some(isBlank);
  const gapDown = down && lines.slice(nearEnd, down.n - 1).some(isBlank);
  // 위아래 두 목록 사이에 끼우면 한 목록이 된다 — 띄움을 하나로: 어느 한쪽이라도 띄운 목록이면 띄운다 (Markdown 은 빈 줄이 하나라도 있으면 목록 전체를 띄운다), 둘 다 모르면 있던 빈 줄
  const known = up && down ? [up.loose, down.loose].filter((x) => x !== null) : [];
  const joined = up && down ? (known.length ? known.some(Boolean) : gapUp || gapDown) : null;
  const looseUp = up && (joined ?? up.loose ?? gapUp);
  const looseDown = down && (joined ?? down.loose ?? gapDown);
  let head = up ? [...source.slice(0, upEnd), ...(looseUp ? [sep] : [])] : source.slice(0, a - 1);
  const kids = source.slice(b, kidsEnd);   // 마지막 항목의 하위 — 목록끼리 바꾸면 그 항목에 붙은 채
  let tail = down ? [...kids, ...(looseDown ? [sep] : []), ...source.slice(down.n - 1)] : source.slice(b);
  let cut = 0;   // tail 앞에서 걷은 줄 수
  if (outQuote) {   // 인용 가운데 줄을 빼면 그 앞뒤의 '>' 빈 줄은 인용을 닫는 빈 줄로
    while (head.length && isBlank(head.at(-1)) && quoteOf(head.at(-1))) head = head.slice(0, -1);
    while (tail.length && isBlank(tail[0]) && quoteOf(tail[0])) {
      tail = tail.slice(1);
      cut += 1;
    }
  }
  const depthText = (x) => quoteOf(x).replace(/\s/g, '');
  const close = (x) => list && !!x && !!itemOf(x) && depthText(x) === depthText(quoted);   // 바로 붙은 같은 깊이의 목록 줄 — 빈 줄 없이 잇는다
  const gapBefore = !up && head.length > 0 && !isBlank(head.at(-1)) && !BOX_HEAD.test(head.at(-1)) && !close(head.at(-1));
  const gapAfter = !down && tail.length > 0 && !isBlank(tail[0]) && !close(tail[0]);
  const gapLine = (x) => (depthText(x) === depthText(q) ? sep : '');   // 깊이가 다른 이웃(인용 밖)과는 보통 빈 줄
  let next = [...head, ...(gapBefore ? [gapLine(head.at(-1))] : []), ...body, ...(gapAfter ? [gapLine(tail[0])] : []), ...tail];
  const line = head.length + (gapBefore ? 1 : 0) + 1;
  const endLine = line + body.length - 1;
  // 번호 (D155): 번호 목록이 이어지면 수준마다 다시 매기고, 번호 목록에서 줄이 빠졌으면 뒤 항목을 앞 항목에 잇는다 (모두 같은 번호로 쓴 목록은 그대로)
  const before = next;
  if (kind === 'number') {
    for (const lead of new Set(leads)) next = renumberAt(next, line + leads.indexOf(lead));
  } else {
    const front = head.length + (gapBefore ? 1 : 0) + body.length + (gapAfter ? 1 : 0);   // tail 앞의 줄 수
    const moved = (n) => (down ? (n <= kidsEnd ? front + n - b : front + kids.length + (looseDown ? 1 : 0) + n - down.n + 1) : front + n - b - cut);   // 원래 줄 n(b 뒤)의 새 자리
    const done = new Set();
    for (const { n, it } of items) {   // 수준마다 처음 고른 번호 항목의 목록
      if (!it.ordered || done.has(it.width)) continue;
      done.add(it.width);
      const sib = siblingsOf(lines, n);
      const nums = sib.map((x) => itemOf(lines[x - 1]).num);
      if (nums.length > 1 && nums.every((x) => x === nums[0])) continue;
      const prev = sib.filter((x) => x < n).at(-1);
      const rest = sib.find((x) => x > b);
      const at = rest ? moved(rest) : 0;
      if (rest && itemOf(next[at - 1] ?? '')?.ordered) next = renumberFrom(next, at, prev ? itemOf(lines[prev - 1]).num + 1 : it.num).lines;
    }
  }
  const renumbered = next === before ? 0 : next.filter((x, i) => x !== before[i] && (i + 1 < line || i + 1 > endLine)).length;
  return { lines: next, line, a: line, b: endLine, renumbered };
}

/** 줄의 종류: 'h1'~'h6' · 'task' · 'number' · 'bullet' · 'quote' · 'para'. 빈 줄은 '' */
export function kindOfLine(line) {
  if (isBlank(line)) return '';
  const it = itemOf(line);
  if (it) return it.task ? 'task' : it.ordered ? 'number' : 'bullet';
  const quote = quoteOf(line);
  const level = headLevel(line.slice(quote.length));
  if (level) return `h${level}`;
  return quote ? 'quote' : 'para';
}

/**
 * 고른 줄의 한 글자 키(D128)로 바꿀 종류 — Lectern 모바일과 같다. 'heading'(H)은 첫 글 줄의 수준으로 제목 2 → 3 → 1 → 문단 차례,
 * 그 밖의 키는 고른 글 줄이 모두 이미 그 종류면 문단으로 (할 일은 목록으로) — 같은 키를 다시 누르면 되돌아간다
 */
export function toggledKind(lines, a, b, kind) {
  const kinds = [];
  for (let n = a; n <= b; n++) {
    const k = kindOfLine(lines[n - 1] ?? '');
    if (k) kinds.push(k);
  }
  if (kind === 'heading') return { h2: 'h3', h3: 'h1', h1: 'para' }[kinds[0]] ?? 'h2';
  if (kinds.length && kinds.every((k) => k === kind)) return kind === 'task' ? 'bullet' : 'para';
  return kind;
}

/** '**글**' 한 쌍으로만 감싼 글이면 그 안의 글, 아니면 null. '**가** 나 **다**' 는 통째가 아니다 (Lectern 모바일의 wholeBold) */
export function wholeBold(text) {
  const m = /^\*\*([\s\S]+)\*\*$/.exec(text.trim());
  if (!m) return null;
  const inner = m[1];
  return inner.includes('**') || /^\s|\s$/.test(inner) || /^\*+$/.test(inner) ? null : inner;
}

/** 줄의 표시(인용 >·목록 표시·할 일 칸·제목 #)와 글, 끝(제목의 닫는 #·끝 공백) */
function markedParts(line) {
  const it = itemOf(line);
  const quote = quoteOf(line);
  const head = it ? line.slice(0, line.length - it.text.length)
    : quote + (/^ {0,3}#{1,6}(?:[ \t]+|$)/.exec(line.slice(quote.length))?.[0] ?? /^[ \t]*/.exec(line.slice(quote.length))[0]);
  const rest = line.slice(head.length);
  const end = (headLevel(line.slice(quote.length)) ? /(?:[ \t]+#+)?[ \t]*$/ : /[ \t]*$/).exec(rest)[0];
  return { head, text: rest.slice(0, rest.length - end.length), end };
}

/**
 * 줄 a~b 의 글을 통째로 굵게 (D128 — 모바일의 B). 글 줄이 모두 이미 통째로 굵으면 푼다. 일부만 굵던 줄은 그 표시를 걷고 통째로 ('****' 로 겹치지 않게).
 * 표시는 그대로. 코드 블록·표·머리 설정·구분 줄은 바꾸지 않는다. {lines, line, a, b}
 */
export function boldLines(lines, a, b) {
  const fences = fencesOf(lines);
  const blocks = blocksOf(lines);
  const parts = [];
  for (let n = a; n <= b; n++) {
    const s = lines[n - 1];
    if (isBlank(s)) continue;
    const blk = blockAt(blocks, n);
    if (fenceAt(fences, n) || blk?.kind === 'front' || blk?.kind === 'wall') return { error: 'kind' };
    if (tableIn(lines, blk)) return { error: 'table-kind' };
    const p = markedParts(s);
    if (p.text.trim()) parts.push({ n, ...p });
  }
  if (!parts.length) return { error: 'kind' };
  const undo = parts.every((p) => wholeBold(p.text) != null);
  const next = lines.slice();
  for (const p of parts) {
    const inner = p.text.replace(/\*\*/g, '').trim();
    if (undo) next[p.n - 1] = `${p.head}${wholeBold(p.text)}${p.end}`;
    else if (inner) next[p.n - 1] = `${p.head}**${inner}**${p.end}`;
  }
  return { lines: next, line: a, a, b };
}

/**
 * 줄 a~b 의 글을 통째로 서식 kind 로 (D141 — 기울임 italic·취소선 strike·형광펜 mark·글자색 color. 굵게는 boldLines).
 * 기울임·취소선: 글 줄이 모두 이미 통째로 그 서식이면 풀고, 아니면 모두 그 서식으로. 형광펜·글자색: 첫 글 줄의 색 다음 색으로 모두 —
 * 없으면 첫 색, 마지막 색이면 모두 푼다. 일부에만 있던 같은 서식은 걷고 통째로. 표시(목록·제목·인용)는 그대로.
 * 코드 블록·표·머리 설정·구분 줄은 바꾸지 않는다. {lines, line, a, b}
 */
export function formatLines(lines, a, b, kind) {
  const fences = fencesOf(lines);
  const blocks = blocksOf(lines);
  const parts = [];
  for (let n = a; n <= b; n++) {
    const s = lines[n - 1];
    if (isBlank(s)) continue;
    const blk = blockAt(blocks, n);
    if (fenceAt(fences, n) || blk?.kind === 'front' || blk?.kind === 'wall') return { error: 'kind' };
    if (tableIn(lines, blk)) return { error: 'table-kind' };
    const p = markedParts(s);
    if (p.text.trim()) parts.push({ n, ...p });
  }
  if (!parts.length) return { error: 'kind' };
  const simple = kind in SIMPLE;
  const undo = simple ? parts.every((p) => wholeOf(p.text, kind)) : nextValue(parts[0].text, kind) === undefined;
  const value = simple ? undefined : nextValue(parts[0].text, kind);
  const next = lines.slice();
  for (const p of parts) next[p.n - 1] = `${p.head}${undo ? stripFormat(p.text, kind) : wrapWhole(p.text, kind, value)}${p.end}`;
  return { lines: next, line: a, a, b };
}

/** 제목 줄 n 의 절이 끝나는 줄 — 같거나 높은 수준의 다음 제목 앞 (끝의 빈 줄은 뺀다) */
export function sectionEnd(lines, n) {
  const level = headLevel(lines[n - 1]);
  const next = headsOf(lines).find((h) => h.n > n && h.level <= level);
  let end = next ? next.n - 1 : Math.max(n, bodyEnd(lines));   // 마지막 절은 문서 끝의 각주 앞까지
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

/** 제목 줄 n 하나의 수준만 dir 만큼 (D152 — Tab·>>·고른 줄의 > <). 1~6 을 벗어나면 {error: 'edge'} */
export function shiftHeading(lines, n, dir) {
  const level = headLevel(lines[n - 1]);
  if (!level) return { error: 'not-heading' };
  if (level + dir < 1 || level + dir > 6) return { error: 'edge' };
  const next = lines.slice();
  next[n - 1] = next[n - 1].replace(/#{1,6}/, '#'.repeat(level + dir));
  return { lines: next, line: n };
}

/**
 * 고른 줄 a~b 의 레벨을 dir 만큼 (D152). 위에서부터 옮기되 앞에서 함께 옮긴 하위(목록의 하위 항목, 제목의 하위 절 제목)는 건너뛴다.
 * section: 제목을 하위 절까지(Alt+Shift — D107), 아니면 그 줄만. tab: 제목은 바꾸지 않는다 (D83).
 * {lines, subHeads(함께 옮긴 하위 절 제목 수), renumbered(번호를 다시 매긴 바깥 항목 수)} 또는 {error} —
 * 한 줄이면 까닭을 돌려주고, 여러 줄이면 옮길 수 없는 줄은 건너뛴다 ('edge' 는 멈춘다). 제목만 골라 Tab 이면 {error: 'heading-tab'}
 */
export function shiftLevels(lines, a, b, dir, { section = false, tab = false } = {}) {
  let out = lines;
  let headUntil = 0;   // 앞의 제목과 함께 옮긴 하위 절 제목은 이 줄까지
  let itemUntil = 0;   // 앞의 항목과 함께 옮긴 하위 항목은 이 줄까지
  let subHeads = 0;
  let headSkipped = false;
  const owned = [];   // 고른 줄과 함께 옮긴 범위 — 번호를 다시 매긴 바깥 항목을 셀 때 뺀다
  for (let n = a; n <= b; n++) {
    if (isBlank(out[n - 1] ?? '')) continue;
    if (headLevel(out[n - 1])) {
      if (tab) {
        headSkipped = true;
        continue;
      }
      if (n <= headUntil) continue;
      const end = section ? sectionEnd(out, n) : n;
      const r = section ? shiftHeadings(out, n, dir) : shiftHeading(out, n, dir);
      if (r.error) {
        if (r.error === 'edge' || a === b) return { error: r.error };
        continue;
      }
      if (section) subHeads += headsOf(out).filter((h) => h.n > n && h.n <= end).length;
      headUntil = end;
      owned.push([n, end]);
      out = r.lines;
      continue;
    }
    if (n <= itemUntil) continue;
    const span = itemSpan(out, n);
    const r = span ? (dir > 0 ? indentItem : outdentItem)(out, n) : { error: 'not-list' };
    if (r.error) {
      if (r.error === 'edge' || a === b) return { error: r.error };
      continue;
    }
    itemUntil = span[1];
    owned.push(span);
    out = r.lines;
  }
  if (out === lines) return headSkipped ? { error: 'heading-tab' } : { lines };
  let renumbered = 0;
  out.forEach((s, i) => {
    const n = i + 1;
    if (s !== lines[i] && !owned.some(([x, y]) => n >= x && n <= y) && itemOf(s)?.ordered) renumbered += 1;
  });
  return { lines: out, subHeads, renumbered };
}

/** 절의 범위 [첫 줄, 다음 절 앞 줄] — 뒤의 빈 줄까지 */
function sectionBlock(lines, heads, h) {
  const next = heads.find((x) => x.n > h.n && x.level <= h.level);
  const notes = notesStart(lines);
  return [h.n, next ? next.n - 1 : notes > h.n ? notes - 1 : lines.length];   // 마지막 절을 지우거나 옮겨도 각주는 문서 끝에 남는다 — 그 앞의 빈 줄까지가 절
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

/**
 * 제목 줄 n 의 절을 제목 줄 to 앞으로 옮긴다 — 본문과 하위 절까지 함께, 수준은 그대로 (목차에서 끌기 — D121).
 * to 가 null 이면 본문 끝(각주 앞)으로. 자기 절 안으로는 옮기지 않는다 ({error: 'inside'}). {lines, line(옮긴 제목 줄)}
 */
export function moveSectionTo(lines, n, to) {
  if (deckOf(lines)) return { error: 'edge' };
  const heads = headsOf(lines);
  const me = heads.find((h) => h.n === n);
  if (!me) return { error: 'not-heading' };
  if (to != null && !heads.some((h) => h.n === to)) return { error: 'not-heading' };
  const [a, b] = sectionBlock(lines, heads, me);
  if (to != null && to >= a && to <= b + 1) return to === a || to === b + 1 ? { error: 'same' } : { error: 'inside' };
  const end = to == null ? bodyEnd(lines) : null;
  if (to == null && b >= end) return { error: 'same' };
  const trim = (x) => {
    const out = x.slice();
    while (out.length && !out.at(-1).trim()) out.pop();
    return out;
  };
  const moving = trim(lines.slice(a - 1, b));
  const rest = [...lines.slice(0, a - 1), ...lines.slice(b)];
  // 넣을 자리 (rest 의 0부터): to 앞, 또는 본문 끝 뒤
  let at = to == null ? end - (b - a + 1) : (to > b ? to - (b - a + 1) : to) - 1;
  if (to == null) {
    while (at > 0 && !rest[at - 1].trim()) at -= 1;
  }
  const before = rest.slice(0, at);
  const after = rest.slice(at);
  while (before.length && !before.at(-1).trim()) before.pop();
  const lead = before.length ? [''] : [];
  const gap = after.length && after[0].trim() ? [''] : [];
  const next = [...before, ...lead, ...moving, ...gap, ...after];
  return { lines: next, line: before.length + lead.length + 1 };
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

// ---- 넣기 ---------------------------------------------------------------------------

/** 블록 block(줄 배열)을 줄 at 뒤에 넣는다 — 앞뒤에 빈 줄을 둔다. {lines, line(블록의 첫 줄)} */
export function insertBlock(lines, at, block) {
  const before = lines.slice(0, at);
  const after = lines.slice(at);
  return { lines: padded(before, block, after), line: at + (before.length && before.at(-1).trim() ? 1 : 0) + 1 };
}

/** 줄 n 이 든 블록의 끝 줄 — 그 뒤에 새 블록을 넣는다 */
export function blockEnd(lines, n) {
  return blockAt(blocksOf(lines), n)?.b ?? n;
}

/** 다음 캡션 번호: word('표'·'그림')로 시작하는 캡션 줄의 가장 큰 번호 + 1. 굵게·꺾쇠로 쓴 것도 센다 */
export function nextCaption(lines, word) {
  const re = new RegExp(`^(?:\\*\\*)?[〈<]?${word}\\s*(\\d+)`);
  return lines.reduce((most, s) => Math.max(most, Number(re.exec(s.trim())?.[1] ?? 0)), 0) + 1;
}

// ---- 표 -----------------------------------------------------------------------------

/** 표의 한 행 → {head(인용·들여쓰기), cells(칸의 글, 앞뒤 공백 그대로)} — 칸은 \| 가 아닌 | 로 나눈다 */
function rowCells(line) {
  const head = /^(?:[ \t]*>[ \t]?)*[ \t]*/.exec(line)[0];
  const row = line.slice(head.length);
  const pieces = [''];
  for (let i = 0; i < row.length; i++) {
    if (row[i] === '\\' && i + 1 < row.length) {
      pieces[pieces.length - 1] += row[i] + row[i + 1];
      i += 1;
    } else if (row[i] === '|') pieces.push('');
    else pieces[pieces.length - 1] += row[i];
  }
  const open = row.startsWith('|');
  const close = pieces.length > 1 && !pieces.at(-1).trim() && /\|[ \t]*$/.test(row);
  return { head, cells: pieces.slice(open ? 1 : 0, close ? -1 : undefined) };
}

const joinRow = (head, cells) => `${head}|${cells.join('|')}|`;

/** 줄 n 이 든 표 {head, sep, first, last}. 표가 아니면 null */
export function tableAt(lines, n) {
  const found = tableIn(lines, blockAt(blocksOf(lines), n));
  return found && n >= found.head && n <= found.last ? found : null;
}

/** 빈 표의 줄들: 머리행과 rows 줄의 본문 */
export function makeTable(cols, rows) {
  const row = `|${'  |'.repeat(cols)}`;
  return [row, `|${' --- |'.repeat(cols)}`, ...Array(rows).fill(row)];
}

/** 표 값(칸들의 줄)을 표의 줄들로 — 첫 행이 머리행. 칸 글의 | 는 \| 로 */
export function tableFromRows(rows) {
  const cols = Math.max(...rows.map((r) => r.length));
  const line = (r) => `| ${Array.from({ length: cols }, (_, i) => String(r[i] ?? '').trim().replace(/\|/g, '\\|')).join(' | ')} |`;
  return [line(rows[0]), `|${' --- |'.repeat(cols)}`, ...rows.slice(1).map(line)];
}

/** 붙여 넣은 글이 표인지 — 줄마다 탭으로 나뉘고 칸 수가 같다 (엑셀). 표면 칸들의 줄, 아니면 null */
export function rowsFromTsv(text) {
  const rows = text.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n').map((s) => s.split('\t'));
  return rows[0].length > 1 && rows.every((r) => r.length === rows[0].length) ? rows : null;
}

/** 줄 n 의 아래(below)·위에 빈 행을 더한다. 머리행 위에는 넣지 않는다 — 머리행의 아래는 첫 본문 행이다 {lines, line} */
export function addRow(lines, n, below) {
  const table = tableAt(lines, n);
  if (!table) return { error: 'not-table' };
  const { head, cells } = rowCells(lines[n - 1]);
  const at = n <= table.sep ? table.sep : below ? n : n - 1;   // 머리행·구분 줄이면 첫 본문 행 자리로
  const next = lines.slice();
  next.splice(at, 0, joinRow(head, cells.map(() => '  ')));
  return { lines: next, line: at + 1 };
}

/** 표의 줄마다 칸들을 op 로 바꾼다 */
function eachRow(lines, table, op) {
  const next = lines.slice();
  for (let i = table.head; i <= table.last; i++) {
    const { head, cells } = rowCells(next[i - 1]);
    next[i - 1] = joinRow(head, op(cells, i === table.sep));
  }
  return next;
}

/** col 번째 칸의 오른쪽(right)·왼쪽에 빈 열을 더한다 {lines, line, cell} */
export function addColumn(lines, n, col, right) {
  const table = tableAt(lines, n);
  if (!table) return { error: 'not-table' };
  const at = col + (right ? 1 : 0);
  return {
    lines: eachRow(lines, table, (cells, sep) => {
      const out = cells.slice();
      out.splice(at, 0, sep ? ' --- ' : '  ');
      return out;
    }),
    line: n,
    cell: at,
  };
}

/** col 번째 열을 지운다. 하나뿐인 열은 지우지 않는다 */
export function removeColumn(lines, n, col) {
  const table = tableAt(lines, n);
  if (!table) return { error: 'not-table' };
  if (rowCells(lines[table.head - 1]).cells.length < 2) return { error: 'last-column' };
  return { lines: eachRow(lines, table, (cells) => cells.filter((_, i) => i !== col)), line: n, cell: Math.max(0, col - 1) };
}

/** col 번째 열을 dir 만큼 옮긴다 */
export function moveColumn(lines, n, col, dir) {
  const table = tableAt(lines, n);
  if (!table) return { error: 'not-table' };
  const to = col + dir;
  if (to < 0 || to >= rowCells(lines[table.head - 1]).cells.length) return { error: 'edge' };
  return {
    lines: eachRow(lines, table, (cells) => {
      const out = cells.slice();
      [out[col], out[to]] = [out[to], out[col]];
      return out;
    }),
    line: n,
    cell: to,
  };
}

/** col 번째 열의 정렬을 바꾼다: 'left'·'center'·'right' */
export function alignColumn(lines, n, col, align) {
  const table = tableAt(lines, n);
  if (!table) return { error: 'not-table' };
  const mark = { left: ' :--- ', center: ' :---: ', right: ' ---: ' }[align];
  return { lines: eachRow(lines, table, (cells, sep) => (sep ? cells.map((c, i) => (i === col ? mark : c)) : cells)), line: n, cell: col };
}

/** 표 전체의 줄 범위 [a, b] */
export function tableSpan(lines, n) {
  const table = tableAt(lines, n);
  return table ? [table.head, table.last] : null;
}

// ---- 덩어리 바꾸기 (D155) -----------------------------------------------------------

/** 목록 항목의 글을 표의 칸으로: 탭 → ' — ' → 첫 ': ' 차례로 나눈다 */
function cellsOfItem(text) {
  if (text.includes('\t')) return text.split('\t');
  if (text.includes(' — ')) return text.split(' — ');
  const at = text.indexOf(': ');
  return at > 0 ? [text.slice(0, at), text.slice(at + 2)] : [text];
}

/**
 * 줄 n 이 든 목록(같은 수준의 항목들)을 표로 — 항목마다 한 행, 칸은 cellsOfItem. heads: 머리행의 이름 [첫 열, 둘째 열, (n) => 셋째부터].
 * 하위 항목·이어진 줄이 있는 목록은 바꾸지 않는다 ('nested-list'). {lines, line(표의 첫 줄)} 또는 {error}
 */
export function listToTable(lines, n, heads) {
  const sib = siblingsOf(lines, n);
  if (!sib.length) return { error: 'not-list' };
  const span = itemSpan(lines, sib.at(-1));
  if (sib.some((i, k) => itemSpan(lines, i)[1] !== i || (k && lines.slice(sib[k - 1], i - 1).some((x) => !isBlank(x))))) return { error: 'nested-list' };
  const quote = quoteOf(lines[sib[0] - 1]);
  const rows = sib.map((i) => cellsOfItem(itemOf(lines[i - 1]).text.trim()).map((c) => c.trim()));
  const cols = Math.max(...rows.map((r) => r.length));
  const head = Array.from({ length: cols }, (_, i) => (i === 0 ? heads[0] : i === 1 ? heads[1] : heads[2](i + 1)));
  const table = tableFromRows([head, ...rows]).map((x) => `${quote}${x}`);
  return { lines: padded(lines.slice(0, sib[0] - 1), table, lines.slice(span[1])), line: sib[0] };
}

/**
 * 줄 n 이 든 표를 목록으로 — 본문 행마다 한 항목, 빈 칸을 뺀 칸은 ' — ' 로 잇는다 (머리행은 뺀다).
 * caption: 표의 캡션 줄도 지운다 (부른 쪽이 묻는다). {lines, line} 또는 {error}
 */
export function tableToList(lines, n, { caption = 0 } = {}) {
  const table = tableAt(lines, n);
  if (!table) return { error: 'not-table' };
  if (table.first > table.last) return { error: 'empty-table' };
  const quote = quoteOf(lines[table.head - 1]);
  const items = [];
  for (let i = table.first; i <= table.last; i++) {
    const text = rowCells(lines[i - 1]).cells.map((c) => c.trim()).filter(Boolean).join(' — ');
    if (text) items.push(`${quote}- ${text}`);
  }
  if (!items.length) return { error: 'empty-table' };
  let from = table.head;
  if (caption) {
    from = caption;
    while (from > 1 && isBlank(lines[from - 2])) from -= 1;
  }
  const before = lines.slice(0, from - 1);
  return { lines: padded(before, items, lines.slice(table.last)), line: before.length + (before.length && !isBlank(before.at(-1)) ? 2 : 1) };
}

/** 줄 a~b 를 코드 블록으로 감싼다 — 글은 표시까지 그대로. 인용 안의 줄은 인용 안에서 {lines, line(여는 줄)} */
export function wrapCode(lines, a, b) {
  const fences = fencesOf(lines);
  for (let n = a; n <= b; n++) if (fenceAt(fences, n)) return { error: 'in-code' };
  while (a < b && isBlank(lines[a - 1])) a += 1;
  while (b > a && isBlank(lines[b - 1])) b -= 1;
  const quote = quoteOf(lines[a - 1]);
  const body = [`${quote}\`\`\``, ...lines.slice(a - 1, b), `${quote}\`\`\``];
  const before = lines.slice(0, a - 1);
  return { lines: padded(before, body, lines.slice(b)), line: before.length + (before.length && !isBlank(before.at(-1)) ? 2 : 1) };
}

/** 줄 n 이 든 코드 블록의 울타리(```)를 떼어 보통 글로 {lines, line(첫 글 줄)} */
export function unwrapCode(lines, n) {
  const f = fenceAt(fencesOf(lines), n);
  if (!f) return { error: 'not-code' };
  const inner = lines.slice(f.a, f.closed ? f.b - 1 : f.b);
  const before = lines.slice(0, f.a - 1);
  return { lines: padded(before, inner.length ? inner : [''], lines.slice(f.b)), line: before.length + (before.length && !isBlank(before.at(-1)) ? 2 : 1) };
}

// ---- 강조글 -------------------------------------------------------------------------

export const BOXES = ['NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION'];
const BOX_HEAD = /^[ \t]*>[ \t]?\[!([A-Za-z]+)\][ \t]*$/;

const depth = (s) => (quoteOf(s).match(/>/g) || []).length;

/** 줄 n 이 든 강조글 {a, b, kind}. 강조글이 아니면 null */
export function boxAt(lines, n) {
  if (!depth(lines[n - 1] ?? '')) return null;
  let a = n;
  while (a > 1 && depth(lines[a - 2])) a -= 1;
  let b = n;
  while (b < lines.length && depth(lines[b])) b += 1;
  const m = BOX_HEAD.exec(lines[a - 1]);
  return m ? { a, b, kind: m[1].toUpperCase() } : null;
}

/** 강조글의 종류를 바꾼다 (표시 한 줄) */
export function setBox(lines, n, kind) {
  const box = boxAt(lines, n);
  if (!box) return { error: 'not-box' };
  const next = lines.slice();
  next[box.a - 1] = next[box.a - 1].replace(/\[![A-Za-z]+\]/, `[!${kind}]`);
  return { lines: next, line: n };
}

/** 강조글을 풀어 보통 문단으로 — 인용 표시와 종류 줄을 뗀다 */
export function unwrapBox(lines, n) {
  const box = boxAt(lines, n);
  if (!box) return { error: 'not-box' };
  const body = lines.slice(box.a, box.b).map((s) => s.replace(/^[ \t]*>[ \t]?/, ''));
  return { lines: [...lines.slice(0, box.a - 1), ...body, ...lines.slice(box.b)], line: Math.max(box.a, n - 1) };
}

/** 줄 a~b 를 강조글로 감싼다 */
export function wrapBox(lines, a, b, kind) {
  const texts = [];
  for (let n = a; n <= b; n++) {
    const text = bareText(lines[n - 1]);
    if (text) texts.push(text);
  }
  if (!texts.length) return { error: 'kind' };
  const body = [`> [!${kind}]`, ...texts.flatMap((s, i) => [...(i ? ['>'] : []), `> ${s}`])];
  return { lines: padded(lines.slice(0, a - 1), body, lines.slice(b)), line: a + 1 };
}

/**
 * 고른 줄의 C (D128): 강조글(참고)로 감싼다. 이미 강조글 안이면 다음 종류로 — 참고 → 팁 → 중요 → 경고 → 주의 → 참고.
 * {lines, line, a, b} — a~b 는 그 강조글 (표시 줄부터)
 */
export function cycleBox(lines, a, b) {
  const box = boxAt(lines, a);
  const r = box ? setBox(lines, a, BOXES[(BOXES.indexOf(box.kind) + 1) % BOXES.length]) : wrapBox(lines, a, b, 'NOTE');
  if (r.error) return r;
  const made = boxAt(r.lines, box ? a : r.line);
  return { ...r, a: made?.a ?? a, b: made?.b ?? b };
}

// ---- 박스글 (D126) ------------------------------------------------------------------
// 본문과 따로 읽는 글 상자: '<!-- box -->' 줄과 '<!-- /box -->' 줄 사이. 다른 뷰어에서는 주석이 보이지 않아 보통 글이다.
// 닫는 줄이 없으면 다음 제목 앞(없으면 문서 끝)에서 끝난다 — 줄을 버리지 않는다. 박스글 안에 박스글은 없다: 여는 줄이 또 나오면 앞의 것이 거기서 끝난다.

export const TEXTBOX_OPEN = '<!-- box -->';
export const TEXTBOX_CLOSE = '<!-- /box -->';
// 이름이 있는 박스글 '<!-- box: 핵심 -->' (D145): 지면 틀이 그 이름의 자리(요약·핵심 수치 등)로 옮긴다. 틀이 모르면 보통 박스글
const TB_OPEN = /^ {0,3}<!--[ \t]*box(?:[ \t]*:[ \t]*([^\n]*?))?[ \t]*-->[ \t]*$/i;
const TB_CLOSE = /^ {0,3}<!--[ \t]*\/box[ \t]*-->[ \t]*$/i;

/** 박스글을 여는 줄·닫는 줄인지 (markdown.js 도 이것으로 본다) */
export const isTextboxOpen = (line) => TB_OPEN.test(line);
/** 박스글을 여는 줄의 이름 ('<!-- box: 핵심 -->' 이면 '핵심', 이름이 없으면 '') */
export const textboxName = (line) => (TB_OPEN.exec(line)?.[1] || '').trim();
export const isTextboxClose = (line) => TB_CLOSE.test(line);

/** 문서의 박스글 [{a(여는 줄), b(닫는 줄 — 없으면 0), end(박스글의 마지막 줄 — 닫는 줄, 없으면 안의 마지막 글 줄)}] — 머리 설정과 코드 블록 안은 뺀다 */
export function textboxesIn(lines) {
  const fences = fencesOf(lines);
  const start = frontEnd(lines);
  const out = [];
  let open = null;
  const lastText = (from, to) => {
    let n = to;
    while (n > from && isBlank(lines[n - 1])) n -= 1;
    return n;
  };
  lines.forEach((s, i) => {
    const n = i + 1;
    if (n <= start || fenceAt(fences, n)) return;
    if (open && (headLevel(s) || isTextboxOpen(s))) {   // 닫지 않은 박스글은 제목·다음 박스글 앞에서 끝난다
      out.push({ a: open, b: 0, end: lastText(open, n - 1) });
      open = null;
    }
    if (isTextboxOpen(s)) open = n;
    else if (open && isTextboxClose(s)) {
      out.push({ a: open, b: n, end: n });
      open = null;
    }
  });
  if (open) out.push({ a: open, b: 0, end: lastText(open, lines.length) });
  return out;
}

/** 줄 n 이 든 박스글 (여는 줄·닫는 줄도 그 박스글). 없으면 null */
export const textboxAt = (lines, n) => textboxesIn(lines).find((x) => n >= x.a && n <= x.end) || null;

/** 박스글의 제목 줄 — word 는 '박스'·'Box', title 은 제목 글 */
export const textboxTitle = (word, n, title) => `**${word} ${n}. ${title}**`;

/** 새 박스글의 줄들: 여는 줄, 제목, 내용 한 줄, 닫는 줄 */
export const makeTextbox = (word, n, title, body) => [TEXTBOX_OPEN, textboxTitle(word, n, title), '', body, TEXTBOX_CLOSE];

/**
 * 줄 a~b 를 박스글로 묶는다 — 앞뒤에 여는 줄·닫는 줄을 넣는다. 첫 줄이 '박스 1. …' 캡션이 아니면 제목 줄(titleLine)도 넣는다.
 * 제목·다른 박스글·머리 설정에 걸치면 묶지 않는다 (박스글은 절을 넘지 않는다)
 * @param {string[]} lines
 * @param {number} a
 * @param {number} b
 * @param {string} titleLine
 * @param {(line: string) => boolean} [isCaption] 줄이 박스 캡션인지 (refs.js 의 captionAt 으로 — 여기서 부르면 import 가 돈다)
 */
export function wrapTextbox(lines, a, b, titleLine, isCaption) {
  while (a <= b && isBlank(lines[a - 1] ?? '')) a += 1;
  while (b >= a && isBlank(lines[b - 1] ?? '')) b -= 1;
  if (a > b) return { error: 'kind' };
  if (a <= frontEnd(lines)) return { error: 'kind' };
  const fences = fencesOf(lines);
  const fa = fenceAt(fences, a);
  const fb = fenceAt(fences, b);
  if (fa) a = fa.a;   // 코드 블록의 가운데부터 묶지 않는다 — 블록째
  if (fb) b = fb.b;
  if (textboxesIn(lines).some((x) => a <= x.end && b >= x.a)) return { error: 'in-textbox' };
  for (let n = a; n <= b; n++) if (!fenceAt(fences, n) && headLevel(lines[n - 1])) return { error: 'textbox-heading' };
  const head = isCaption?.(lines[a - 1]) ? [] : [titleLine, ''];
  const body = [TEXTBOX_OPEN, ...head, ...lines.slice(a - 1, b), TEXTBOX_CLOSE];
  const before = lines.slice(0, a - 1);
  const r = padded(before, body, lines.slice(b));
  return { lines: r, line: a + (before.length && before.at(-1).trim() ? 1 : 0) + 1 };
}

/** 박스글을 풀어 보통 글로 — 여는 줄과 닫는 줄만 뺀다. 그 자리에 빈 줄이 겹치면 하나만 둔다 */
export function unwrapTextbox(lines, n) {
  const box = textboxAt(lines, n);
  if (!box) return { error: 'not-textbox' };
  const out = lines.slice();
  const drop = (at) => {
    out.splice(at - 1, 1);
    if (at >= 2 && at - 1 < out.length && isBlank(out[at - 2]) && isBlank(out[at - 1])) out.splice(at - 1, 1);   // 위아래가 모두 빈 줄
  };
  if (box.b) drop(box.b);
  drop(box.a);
  return { lines: out, line: Math.min(Math.max(1, box.a), out.length) };
}

/** 박스글의 줄 범위 [a, b] — 지울 때 */
export function textboxSpan(lines, n) {
  const box = textboxAt(lines, n);
  return box ? [box.a, box.end] : null;
}

// ---- 주 -----------------------------------------------------------------------------

const NOTE_REF = /\[\^([^\]\s]+)\](?!:)/g;
const NOTE_DEF = /^\[\^([^\]\s]+)\]:[ \t]*(.*)$/;

/** 쓰지 않은 주 이름 — 숫자로. 화면의 번호는 나온 차례로 저절로 매겨진다 */
export function nextNote(lines) {
  const used = new Set(lines.flatMap((s) => [...s.matchAll(/\[\^([^\]\s]+)\]/g)].map((m) => m[1])));
  let n = 1;
  while (used.has(String(n))) n += 1;
  return String(n);
}

/** 주 내용 줄을 문서 끝에 더한다 — 마지막 주 바로 뒤, 없으면 빈 줄 하나 뒤에 */
function appendNote(lines, label, text) {
  let last = lines.length;
  while (last && !lines[last - 1].trim()) last -= 1;
  const follows = last && NOTE_DEF.test(lines[last - 1]);
  const next = lines.slice();
  next.splice(last, 0, ...(follows || !last ? [] : ['']), `[^${label}]: ${text}`);
  return next;
}

/** 줄 n 의 글자 자리 col 에 주를 단다. 표시와 내용을 함께 넣는다 {lines, line, label} */
export function addNote(lines, n, col, text) {
  const label = nextNote(lines);
  const next = lines.slice();
  next[n - 1] = `${next[n - 1].slice(0, col)}[^${label}]${next[n - 1].slice(col)}`;
  return { lines: appendNote(next, label, text), line: n, label };
}

/** 줄 line 의 글자 자리 col 에 걸린 주 이름. 없으면 '' */
export function noteAt(line, col) {
  for (const m of line.matchAll(NOTE_REF)) if (col >= m.index && col <= m.index + m[0].length) return m[1];
  return '';
}

/** 주 label 의 내용 줄 {n, text}. 없으면 null */
export function noteText(lines, label) {
  const i = lines.findIndex((s) => NOTE_DEF.exec(s)?.[1] === label);
  return i < 0 ? null : { n: i + 1, text: NOTE_DEF.exec(lines[i])[2] };
}

/** 주 label 의 내용을 고친다 */
export function setNote(lines, label, text) {
  const found = noteText(lines, label);
  if (!found) return appendNote(lines, label, text);
  const next = lines.slice();
  next[found.n - 1] = `[^${label}]: ${text}`;
  return next;
}

/** 본문에서 쓰지 않는 주의 내용 줄을 찾는다 — old 에 있던 표시가 next 에서 사라진 것만 (이름들) */
export function droppedNotes(old, next) {
  const refs = (lines) => new Set(lines.filter((s) => !NOTE_DEF.test(s)).flatMap((s) => [...s.matchAll(NOTE_REF)].map((m) => m[1])));
  const now = refs(next);
  return [...refs(old)].filter((x) => !now.has(x) && noteText(next, x));
}

/** 주 내용 줄을 지운다 */
export function removeNotes(lines, labels) {
  const next = lines.filter((s) => !labels.includes(NOTE_DEF.exec(s)?.[1]));
  while (next.length > 1 && !next.at(-1).trim() && !next.at(-2).trim()) next.pop();
  return next;
}

// ---- 첨부·부록 ----------------------------------------------------------------------

const ATTACH_HEAD = /^##[ \t]+(?:붙임|첨부|별첨|attachments?)[ \t]*$/i;   // i18n-ok (절 이름)

/** '붙임' 절에 번호 항목으로 파일 링크를 더한다. 절이 없으면 문서 끝에 만든다 {lines, line}. heading: 새 절의 제목 */
export function addAttachment(lines, text, heading) {
  const own = headsOf(lines).find((h) => ATTACH_HEAD.test(lines[h.n - 1]));
  if (own) {
    const end = sectionEnd(lines, own.n);
    if (end === own.n) return insertBlock(lines, end, [`1. ${text}`]);
    let num = 0;
    for (let n = own.n + 1; n <= end; n++) num = Math.max(num, itemOf(lines[n - 1])?.num || 0);
    const next = lines.slice();
    next.splice(end, 0, `${num + 1}. ${text}`);
    return { lines: next, line: end + 1 };
  }
  let last = lines.length;
  while (last && !lines[last - 1].trim()) last -= 1;
  const r = insertBlock(lines, bodyEnd(lines, last), [`## ${heading}`, '', `1. ${text}`]);   // 문서 끝의 각주 앞에
  return { lines: r.lines, line: r.line + 2 };
}

/** 다음 부록 글자: 있는 '부록 A' 의 다음 */
export function nextAppendix(lines) {
  const used = lines.map((s) => /^#{1,6}[ \t]+(?:부록|appendix)[ \t]+([A-Z])\b/i.exec(s)?.[1]?.toUpperCase()).filter(Boolean);   // i18n-ok (절 이름)
  return String.fromCharCode(used.reduce((c, x) => Math.max(c, x.charCodeAt(0)), 64) + 1);
}

/** 여러 줄을 줄 n 뒤에 넣는다 — 붙여 넣기. item: 앞 줄의 목록 표시 (있으면 글마다 그 표시로) */
export function pasteAfter(lines, n, pasted, item = '') {
  const body = item ? pasted.filter((s) => s.trim()).map((s) => `${item}${bareText(s)}`) : pasted;
  const next = lines.slice();
  next.splice(n, 0, ...body);
  return { lines: next, line: n + body.length };
}

/** 형광펜 안의 글을 사이드바처럼 (marks.py 의 _plain) — 태그와 서식 표시를 걷는다 */
const markPlain = (s) => s.replace(/<[^>]+>/g, '').replace(/\*\*|__|~~|\*|`/g, '').trim();

/**
 * 형광펜을 걷는다 (D143) — 글은 그대로. line 이 있으면 그 줄(밀렸으면 그 글이 든 가장 가까운 줄)에서 글이 text 인 형광펜 하나,
 * 없으면 문서 전체(color 가 있으면 그 색만 — '' 는 노랑). 코드 블록 안은 건드리지 않는다. text 는 사이드바가 줄인 글일 수 있다 ('…' 로 끝남).
 * {lines, count, line}
 */
export function clearMarksIn(lines, { line = 0, text = '', color = null } = {}) {
  const fences = fencesOf(lines);
  const same = (inner) => {
    const p = markPlain(inner);
    return text.endsWith('…') ? p.startsWith(text.slice(0, -1)) : p === text;
  };
  const marksIn = (s) => spansOf(s).filter((x) => x.kind === 'mark' && (color == null || x.value === color));
  const strip = (s, list) => [...list].sort((p, q) => q.oa - p.oa).reduce((out, x) => out.slice(0, x.oa) + out.slice(x.a, x.b) + out.slice(x.cb), s);
  const next = lines.slice();
  if (line) {
    const order = lines.map((_, i) => i + 1).filter((n) => !fenceAt(fences, n)).sort((p, q) => Math.abs(p - line) - Math.abs(q - line));
    for (const n of order) {
      const hit = marksIn(lines[n - 1]).find((x) => same(lines[n - 1].slice(x.a, x.b)));
      if (hit) {
        next[n - 1] = strip(lines[n - 1], [hit]);
        return { lines: next, count: 1, line: n };
      }
    }
    return { lines: next, count: 0, line };
  }
  let count = 0;
  lines.forEach((s, i) => {
    if (fenceAt(fences, i + 1)) return;
    const list = marksIn(s);
    if (!list.length) return;
    next[i] = strip(s, list);
    count += list.length;
  });
  return { lines: next, count, line: 1 };
}
