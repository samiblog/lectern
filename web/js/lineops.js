// 줄 구조 편집의 계산 (D83, DOM 없음): 원문 줄 배열을 받아 바뀐 줄 배열을 돌려준다. 저장은 lineedit.js 가 replaceLines 로 한다.
// 줄 번호는 1부터. 잘못된 요청은 {error: 까닭 이름} — 알림 문구는 부르는 쪽이 정한다.
//
// - 목록은 들여쓰기로 읽는다: 항목의 범위(itemEnd — 하위 항목·이어진 줄까지), 같은 목록의 앞뒤 항목(표시 종류가 같고 들여쓰기가 같은 것).
//   번호 목록은 고친 뒤 번호를 다시 매긴다 (모두 같은 번호로 쓴 목록은 그대로). 번호 자릿수가 바뀌면 항목의 안쪽 줄도 그만큼 옮긴다.
// - 블록은 빈 줄로 나뉜다. 코드·수식 블록은 안의 빈 줄과 상관없이 통째, 제목은 한 줄이 한 블록, 인용 깊이가 바뀌면 다른 블록이다.
// - 표는 블록 안의 구분 줄로 찾는다. 머리행과 구분 줄은 옮기거나 따로 지우지 않는다.

const QUOTE = /^(?:[ \t]*>[ \t]?)*/;
const HEADING = /^ {0,3}(#{1,6})(?:[ \t]|$)/;
const RULE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const SETEXT = /^ {0,3}(?:=+|-+)[ \t]*$/;
const TABLE_SEP = /^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/;
const CALLOUT = /^\[![A-Za-z]+\]/;
const FENCE = /^[ \t]*(`{3,}|~{3,})(.*)$/;
const CELL_MARK = /^:::(?:[ \t]|$)/;
const COMMENT_LINE = /^[ \t]*<!--.*-->[ \t]*$/;

const quoteOf = (s) => QUOTE.exec(s)[0];
const depthOf = (s) => (quoteOf(s).match(/>/g) || []).length;
const bodyOf = (s) => s.slice(quoteOf(s).length);
const isBlank = (s) => !bodyOf(s).trim();

/** 앞 공백의 폭 (탭은 다음 4칸으로) */
function colsOf(lead) {
  let w = 0;
  for (const c of lead) w += c === '\t' ? 4 - (w % 4) : 1;
  return w;
}
const widthOf = (body) => colsOf(/^[ \t]*/.exec(body)[0]);

/** 목록 항목 줄이면 {quote, lead, width, marker, ordered, num, delim, gap, task, text, content(글이 시작하는 폭)}, 아니면 null */
function itemOf(line) {
  const quote = quoteOf(line);
  const body = line.slice(quote.length);
  if (RULE.test(body)) return null;
  const m = /^([ \t]*)([-*+]|(\d{1,9})([.)]))([ \t]+|$)(\[[ xX]\](?:[ \t]+|$))?/.exec(body);
  if (!m) return null;
  const width = colsOf(m[1]);
  return {
    quote, lead: m[1], width, marker: m[2], ordered: m[3] != null, num: Number(m[3]), delim: m[4] || '', gap: m[5], task: m[6] || '',
    text: body.slice(m[0].length), content: width + m[2].length + (m[5].length || 1),
  };
}

const sameList = (x, y) => x.ordered === y.ordered && (x.ordered ? x.delim === y.delim : x.marker === y.marker);

/** 코드·수식 블록들 [{a, b, closed}] — 닫지 않은 블록은 문서 끝까지 */
function fencesOf(lines) {
  const out = [];
  let open = null;
  lines.forEach((raw, i) => {
    const s = bodyOf(raw);
    const math = /^[ \t]*\$\$[ \t]*$/.test(s);
    const m = FENCE.exec(s);
    if (open) {
      const closes = open.ch === '$' ? math : m && m[1][0] === open.ch && m[1].length >= open.len && !m[2].trim();
      if (closes) {
        out.push({ a: open.a, b: i + 1, closed: true });
        open = null;
      }
    } else if (math) open = { a: i + 1, ch: '$', len: 2 };
    else if (m && !(m[1][0] === '`' && m[2].includes('`'))) open = { a: i + 1, ch: m[1][0], len: m[1].length };
  });
  if (open) out.push({ a: open.a, b: lines.length, closed: false });
  return out;
}

const fenceAt = (fences, n) => fences.find((f) => n >= f.a && n <= f.b) || null;
const innerEnd = (f) => (f.closed ? f.b - 1 : f.b);

/** 머리 정보(--- … ---)의 끝 줄. 없으면 0 */
function frontEnd(lines) {
  if (lines[0]?.trim() !== '---') return 0;
  for (let i = 1; i < lines.length; i++) if (/^(?:---|\.\.\.)\s*$/.test(lines[i])) return i + 1;
  return 0;
}

/** 맨 앞 설정에 marp: true 인 발표 문서인지 */
const deckOf = (lines) => lines.slice(1, frontEnd(lines)).some((s) => /^marp:[ \t]*true[ \t]*$/.test(s));

/** 문서의 블록들 [{a, b, kind: 'front'|'fence'|'heading'|'text'|'wall'}] (빈 줄 뺌). wall: 발표 문서의 칸(:::)·장(---)·지시어 줄 — 글이 넘지 않는다 */
function blocksOf(lines) {
  const fences = fencesOf(lines);
  const blocks = [];
  const front = frontEnd(lines);
  const deck = deckOf(lines);
  const wall = (s) => deck && (CELL_MARK.test(s.trim()) || RULE.test(s) || COMMENT_LINE.test(s));
  if (front) blocks.push({ a: 1, b: front, kind: 'front' });
  let n = front + 1;
  while (n <= lines.length) {
    const f = fenceAt(fences, n);
    const s = lines[n - 1];
    if (f) {
      blocks.push({ a: f.a, b: f.b, kind: 'fence' });
      n = f.b + 1;
    } else if (isBlank(s)) n += 1;
    else if (wall(s)) {
      blocks.push({ a: n, b: n, kind: 'wall' });
      n += 1;
    } else if (HEADING.test(bodyOf(s))) {
      blocks.push({ a: n, b: n, kind: 'heading' });
      n += 1;
    } else {
      let b = n;
      while (b < lines.length && !isBlank(lines[b]) && depthOf(lines[b]) === depthOf(s) && !fenceAt(fences, b + 1) && !HEADING.test(bodyOf(lines[b])) && !wall(lines[b])) b += 1;
      blocks.push({ a: n, b, kind: 'text' });
      n = b + 1;
    }
  }
  return blocks;
}

/** 블록 안의 표 {head, sep, first, last} (첫 본문 행·끝 행 — 본문이 없으면 first > last). 표가 아니면 null */
function tableIn(lines, blk) {
  if (blk?.kind !== 'text') return null;
  for (let i = blk.a + 1; i <= blk.b; i++) {
    if (TABLE_SEP.test(bodyOf(lines[i - 1])) && bodyOf(lines[i - 2]).includes('|')) return { head: i - 1, sep: i, first: i + 1, last: blk.b };
  }
  return null;
}

const blockAt = (blocks, n) => blocks.find((x) => n >= x.a && n <= x.b) || null;

// ---- 목록 -------------------------------------------------------------------------

/** 항목 n 이 끝나는 줄 — 하위 항목·들여쓴 줄·이어진 줄까지 (끝의 빈 줄은 뺀다) */
function itemEnd(lines, n) {
  const it = itemOf(lines[n - 1]);
  const depth = depthOf(lines[n - 1]);
  let end = n;
  let gap = false;
  for (let i = n + 1; i <= lines.length; i++) {
    const s = lines[i - 1];
    if (isBlank(s)) {
      gap = true;
      continue;
    }
    if (depthOf(s) !== depth) break;
    const body = bodyOf(s);
    if (widthOf(body) >= it.content) {
      end = i;
      gap = false;
    } else if (!gap && !itemOf(s) && !HEADING.test(body) && !RULE.test(body) && !FENCE.test(body) && !(CELL_MARK.test(body.trim()) && deckOf(lines))) end = i;   // 들여쓰지 않고 이어 쓴 줄
    else break;
  }
  return end;
}

/** 줄 n 이 든 목록 항목의 줄. 목록 밖이면 0 */
function ownerItem(lines, n) {
  if (itemOf(lines[n - 1])) return n;
  const depth = depthOf(lines[n - 1]);
  const width = widthOf(bodyOf(lines[n - 1]));
  let gap = false;
  for (let i = n - 1; i >= 1; i--) {
    const s = lines[i - 1];
    if (isBlank(s)) {
      gap = true;
      continue;
    }
    if (depthOf(s) !== depth || HEADING.test(bodyOf(s))) return 0;
    const it = itemOf(s);
    if (it && (!gap || width >= it.content)) return i;
    if (it && it.width === 0) return 0;
  }
  return 0;
}

/** 같은 목록의 바로 앞 항목. 없으면 0 */
function prevSibling(lines, n) {
  const it = itemOf(lines[n - 1]);
  const depth = depthOf(lines[n - 1]);
  for (let i = n - 1; i >= 1; i--) {
    const s = lines[i - 1];
    if (isBlank(s)) continue;
    if (depthOf(s) !== depth) return 0;
    const x = itemOf(s);
    if (x) {
      if (x.width === it.width) return sameList(x, it) ? i : 0;
      if (x.width < it.width) return 0;
    } else {
      const own = ownerItem(lines, i);
      if (!own || (itemOf(lines[own - 1]).width < it.width && itemEnd(lines, own) >= n)) return 0;   // 목록 밖의 글이거나 부모 항목의 글
      i = own + 1;   // 항목의 이어진 줄 — 그 항목으로
    }
  }
  return 0;
}

/** 같은 목록의 바로 뒤 항목. 없으면 0 */
function nextSibling(lines, n) {
  const it = itemOf(lines[n - 1]);
  let i = itemEnd(lines, n) + 1;
  while (i <= lines.length && isBlank(lines[i - 1])) i += 1;
  if (i > lines.length || depthOf(lines[i - 1]) !== depthOf(lines[n - 1])) return 0;
  const x = itemOf(lines[i - 1]);
  return x && x.width === it.width && sameList(x, it) ? i : 0;
}

/** 항목의 부모 항목. 없으면 0 */
function parentItem(lines, n) {
  const it = itemOf(lines[n - 1]);
  const depth = depthOf(lines[n - 1]);
  for (let i = n - 1; i >= 1; i--) {
    const s = lines[i - 1];
    if (isBlank(s)) continue;
    if (depthOf(s) !== depth) return 0;
    const x = itemOf(s);
    if (x && x.content <= it.width) return i;
    if (x && x.width === 0) return 0;
  }
  return 0;
}

/** 번호 목록의 번호 정보 {start, flat(모두 같은 번호)} — 번호 목록이 아니면 null */
function listInfo(lines, n) {
  const it = n ? itemOf(lines[n - 1]) : null;
  if (!it?.ordered) return null;
  let first = n;
  for (let p = prevSibling(lines, first); p; p = prevSibling(lines, first)) first = p;
  const nums = [];
  for (let i = first; i; i = nextSibling(lines, i)) nums.push(itemOf(lines[i - 1]).num);
  return { start: nums[0], flat: nums.length > 1 && nums.every((x) => x === nums[0]) };
}

/** 줄의 들여쓰기를 delta 칸 옮긴다 (빈 줄은 그대로, 인용 표시 뒤에서) */
function shifted(line, delta) {
  if (!delta || isBlank(line)) return line;
  const quote = quoteOf(line);
  const body = line.slice(quote.length);
  const lead = /^[ \t]*/.exec(body)[0];
  return quote + ' '.repeat(Math.max(0, colsOf(lead) + delta)) + body.slice(lead.length);
}

/** 항목의 표시를 marker 로 바꾸고 안쪽 줄도 그 폭만큼 옮긴다 — lines 를 바로 고친다. width: 새 들여쓰기 (없으면 그대로) */
function remark(lines, n, marker, width = null) {
  const it = itemOf(lines[n - 1]);
  const end = itemEnd(lines, n);
  const delta = (width == null ? 0 : width - it.width) + marker.length - it.marker.length;
  const lead = width == null ? it.lead : ' '.repeat(width);
  lines[n - 1] = `${it.quote}${lead}${marker}${it.gap}${it.task}${it.text}`;
  for (let i = n + 1; i <= end; i++) lines[i - 1] = shifted(lines[i - 1], delta);
}

/** n 이 든 목록의 번호를 info.start 부터 다시 매긴다 — lines 를 바로 고친다 */
function renumber(lines, n, info) {
  if (!info || info.flat || !itemOf(lines[n - 1])?.ordered) return;
  let first = n;
  for (let p = prevSibling(lines, first); p; p = prevSibling(lines, first)) first = p;
  let num = info.start;
  for (let i = first; i; i = nextSibling(lines, i)) {
    const it = itemOf(lines[i - 1]);
    if (it.num !== num) remark(lines, i, `${num}${it.delim}`);
    num += 1;
  }
}

// ---- 범위 바꾸기로 ----------------------------------------------------------------

/** 두 줄 배열의 다른 곳 {start, before, after} — replaceLines 로 그대로. before 는 한 줄 이상, 빈 줄뿐이면 앞의 글 줄까지 (밀린 줄을 찾을 수 있게) */
export function diffRange(old, next) {
  let a = 0;
  const max = Math.min(old.length, next.length);
  while (a < max && old[a] === next[a]) a += 1;
  let z = 0;
  while (z < max - a && old[old.length - 1 - z] === next[next.length - 1 - z]) z += 1;
  const before = old.slice(a, old.length - z);
  const after = next.slice(a, next.length - z);
  while (a > 0 && !before.join('').trim()) {
    a -= 1;
    before.unshift(old[a]);
    after.unshift(old[a]);
  }
  if (!before.length && z > 0) {   // 맨 앞에 넣기
    before.push(old[a]);
    after.push(old[a]);
  }
  return { start: a + 1, before, after };
}

// ---- 줄 추가·나누기·합치기 ----------------------------------------------------------

/**
 * 줄 n 의 아래(below)·위에 새 줄을 넣을 계획 {at(넣는 곳 앞의 줄 수), pre, post(앞뒤에 함께 넣는 줄), head(잠근 앞부분), fill(칸에 미리 넣는 글),
 * kind: 'item'|'para'|'code', task, list(번호 정보)}. 앞 줄의 형식을 물려받는다 — 목록은 같은 표시, 번호 목록은 다음 번호, 문단은 빈 줄을 두고 새 문단, 코드는 같은 들여쓰기.
 * code: 코드 화면의 줄. parts: 줄 n 의 {head, body} (코드 줄의 잠근 앞부분). split: 줄 나누기 — 그 줄 바로 뒤에 (아래 글이 뒤따르도록)
 */
export function planNew(lines, n, below, { code = false, parts = null, split = false } = {}) {
  const fence = code ? null : fenceAt(fencesOf(lines), n);
  if (code || fence) {
    return { at: below ? n : n - 1, pre: [], post: [], head: parts?.head ?? '', fill: /^[ \t]*/.exec(parts?.body ?? lines[n - 1])[0], kind: 'code', list: null };
  }
  const blocks = blocksOf(lines);
  const blk = blockAt(blocks, n);
  if (tableIn(lines, blk)) return { error: 'table' };
  const own = ownerItem(lines, n);
  if (own) {
    const it = itemOf(lines[own - 1]);
    const list = listInfo(lines, own);
    const prev = prevSibling(lines, own);
    const next = nextSibling(lines, own);
    const end = itemEnd(lines, own);
    const loose = (next && next > end + 1) || (prev && prev + 1 < own && isBlank(lines[own - 2]));
    const num = !list || list.flat ? it.num : below ? it.num + 1 : it.num;
    const head = `${it.quote}${it.lead}${it.ordered ? `${num}${it.delim}` : it.marker}${it.gap || ' '}${it.task ? '[ ] ' : ''}`;
    const sep = it.quote.trimEnd();
    if (!below) return { at: own - 1, pre: [], post: loose ? [sep] : [], head, fill: '', kind: 'item', task: !!it.task, list };
    return { at: split ? n : end, pre: loose ? [sep] : [], post: [], head, fill: '', kind: 'item', task: !!it.task, list };
  }
  const quote = quoteOf(lines[n - 1]);
  const sep = quote.trimEnd();
  const para = { head: quote, fill: '', kind: 'para', list: null };
  if (below) {
    const at = split ? n : blk?.b ?? n;
    const inside = split && blk && n < blk.b;   // 나눈 뒤 글이 그 문단의 다음 줄과 이어진다
    const after = lines[at];
    return { ...para, at, pre: [sep], post: !inside && after != null && !isBlank(after) ? [sep] : [] };
  }
  const a = blk?.a ?? n;
  if (CALLOUT.test(bodyOf(lines[a - 1]).trim())) return { ...para, at: a, pre: [], post: [sep] };   // 박스글의 [!NOTE] 줄은 맨 앞에 남는다
  const before = lines[a - 2];
  return { ...para, at: a - 1, pre: before != null && !isBlank(before) ? [sep] : [], post: [sep] };
}

/** 계획대로 글 text 를 넣는다 {lines, line(새 줄)} */
export function insertLine(lines, plan, text) {
  const next = lines.slice();
  next.splice(plan.at, 0, ...plan.pre, plan.head + text, ...plan.post);
  const line = plan.at + plan.pre.length + 1;
  if (plan.list) renumber(next, line, plan.list);
  return { lines: next, line };
}

/**
 * 줄 n 을 body 의 offset 자리에서 두 줄로 — 앞은 그 줄에, 뒤는 새 줄에 (앞 줄의 형식으로). 원문의 글 차례는 그대로다 (하위 항목은 뒤 글을 따른다).
 * split(line): 줄 → {head, body, tail}. {lines, line(뒤 글의 줄)}
 */
export function splitLine(lines, n, offset, { split, code = false }) {
  const parts = split(lines[n - 1]);
  const fenced = code || fenceAt(fencesOf(lines), n);
  const closing = parts.tail.includes('#');   // 제목 끝의 # 는 앞에 남는다, 줄 끝의 줄바꿈 표시는 뒤로 간다
  const left = parts.body.slice(0, offset);
  const right = parts.body.slice(offset);
  const base = lines.slice();
  base[n - 1] = parts.head + (fenced ? left : left.trimEnd()) + (closing ? parts.tail : '');
  const plan = planNew(base, n, true, { code, parts: { head: parts.head, body: parts.body }, split: true });
  if (plan.error) return plan;
  return insertLine(base, plan, (plan.fill || '') + right.trimStart() + (closing ? '' : parts.tail));
}

/** 줄 n 을 복제한다 — 줄 추가와 같은 자리에 같은 글로 (제목은 제목으로). {lines, line(복제한 줄), offset(글 끝)} */
export function duplicateLine(lines, n, { split, code = false }) {
  const parts = split(lines[n - 1]);
  const plan = planNew(lines, n, true, { code, parts });
  if (plan.error) return plan;
  const made = insertLine(lines, { ...plan, head: plan.kind === 'item' ? plan.head : parts.head }, parts.body + parts.tail);
  return { ...made, offset: parts.body.length };
}

/** 합칠 때 같은 종류인지 볼 이름 */
function kindOf(lines, n, fences, blocks) {
  if (fenceAt(fences, n)) return 'code';
  const body = bodyOf(lines[n - 1]);
  const depth = depthOf(lines[n - 1]);
  const h = HEADING.exec(body);
  if (h) return `h${h[1].length}`;
  if (RULE.test(body) || tableIn(lines, blockAt(blocks, n))) return `other${n}`;
  return `${ownerItem(lines, n) ? 'item' : 'para'}${depth}`;
}

/**
 * 줄 n 을 윗줄 끝에 잇는다 (줄 맨 앞의 Backspace) — 글을 그대로 붙이고 사이의 빈 줄은 없앤다. 같은 종류끼리만 ({error: 'different'}), 코드는 그 블록 안에서.
 * {lines, line(윗줄), offset(이은 자리)}
 */
export function joinLine(lines, n, { split, code = false }) {
  const fences = code ? [] : fencesOf(lines);
  const blocks = code ? [] : blocksOf(lines);
  const f = fenceAt(fences, n);
  let p = n - 1;
  if (!code && !f) while (p >= 1 && isBlank(lines[p - 1])) p -= 1;
  const fixed = (x) => ['wall', 'front'].includes(blockAt(blocks, x)?.kind);
  if (p < 1 || (f && p <= f.a) || fixed(p) || fixed(n)) return { error: 'different' };
  if (!code && kindOf(lines, p, fences, blocks) !== kindOf(lines, n, fences, blocks)) return { error: 'different' };
  const up = split(lines[p - 1]);
  const cur = split(lines[n - 1]);
  const item = !code && !f && itemOf(lines[n - 1]) ? n : 0;
  const info = item ? listInfo(lines, item) : null;
  const sib = item ? nextSibling(lines, item) : 0;
  const next = lines.slice();
  next.splice(p - 1, n - p + 1, up.head + up.body + cur.body + cur.tail);
  if (sib) renumber(next, sib - (n - p), info);
  return { lines: next, line: p, offset: up.body.length };
}

// ---- 레벨 이동 --------------------------------------------------------------------

/** 항목을 한 단계 안으로 — 앞 항목의 하위로, 하위 항목도 함께. 앞 항목에 하위 목록이 있으면 그 목록에 잇는다. {lines, line} */
export function indentItem(lines, n) {
  const own = ownerItem(lines, n);
  if (!own) return { error: 'not-list' };
  const prev = prevSibling(lines, own);
  if (!prev) return { error: 'first-item' };
  const it = itemOf(lines[own - 1]);
  const up = itemOf(lines[prev - 1]);
  let last = null;   // 앞 항목의 마지막 바로 아래 항목
  for (let i = prev + 1; i < own; i++) {
    const x = itemOf(lines[i - 1]);
    if (x && x.width >= up.content && (!last || x.width <= last.width)) last = x;
  }
  const width = last ? last.width : up.content;
  const like = last ?? it;
  const marker = like.ordered ? `${last ? last.num + 1 : 1}${like.delim}` : like.marker;
  const info = listInfo(lines, own);
  const sib = nextSibling(lines, own);
  const next = lines.slice();
  remark(next, own, marker, width);
  if (sib) renumber(next, sib, info);
  return { lines: next, line: n };
}

/** 항목을 한 단계 밖으로 — 부모의 목록으로, 하위 항목도 함께. 글 차례는 그대로다 (뒤의 같은 수준 항목은 이 항목의 하위가 된다). {lines, line} */
export function outdentItem(lines, n) {
  const own = ownerItem(lines, n);
  if (!own) return { error: 'not-list' };
  const parent = parentItem(lines, own);
  if (!parent) return { error: 'top-level' };
  const up = itemOf(lines[parent - 1]);
  const info = listInfo(lines, own);
  const upInfo = listInfo(lines, parent);
  const sib = nextSibling(lines, own);
  const next = lines.slice();
  remark(next, own, up.ordered ? `${up.num + 1}${up.delim}` : up.marker, up.width);
  if (upInfo) renumber(next, own, upInfo);
  if (sib) renumber(next, sib, info);
  return { lines: next, line: n };
}

// ---- 옮기기 -----------------------------------------------------------------------

/** a~b 를 한 줄 옮긴다 (lo~hi 안에서) */
function slide(lines, a, b, dir, lo, hi) {
  if (dir < 0 ? a <= lo : b >= hi) return { error: 'edge' };
  const next = lines.slice();
  next.splice(a - 1 + dir, 0, ...next.splice(a - 1, b - a + 1));
  return { lines: next, a: a + dir, b: b + dir };
}

/** 앞 범위 x1~x2 와 뒤 범위 y1~y2 를 맞바꾼다 (사이의 줄은 그대로) */
function swapped(lines, x1, x2, y1, y2) {
  const next = lines.slice();
  next.splice(x1 - 1, y2 - x1 + 1, ...lines.slice(y1 - 1, y2), ...lines.slice(x2, y1 - 1), ...lines.slice(x1 - 1, x2));
  return next;
}

/** 목록 항목들 a~b (하위 항목까지)를 같은 목록의 앞뒤 항목과 맞바꾼다. 한 목록 안이 아니면 null */
function moveItems(lines, a, b, dir) {
  const own = ownerItem(lines, a);
  if (!own) return null;
  let last = own;
  let end = itemEnd(lines, own);
  while (end < b) {
    last = nextSibling(lines, last);
    if (!last) return null;
    end = itemEnd(lines, last);
  }
  const info = listInfo(lines, own);
  if (dir < 0) {
    const p = prevSibling(lines, own);
    if (!p) return { error: 'edge' };
    const next = swapped(lines, p, itemEnd(lines, p), own, end);
    if (info) renumber(next, p, info);
    return { lines: next, a: a - own + p, b: b - own + p };
  }
  const q = nextSibling(lines, last);
  if (!q) return { error: 'edge' };
  const qEnd = itemEnd(lines, q);
  const next = swapped(lines, own, end, q, qEnd);
  const shift = qEnd - end;
  if (info) renumber(next, own, info);
  return { lines: next, a: a + shift, b: b + shift };
}

/**
 * 줄 a~b 를 위(dir -1)·아래(dir 1)로 옮긴다 {lines, a, b(옮긴 뒤 그 줄들)}. 코드는 그 블록 안에서 줄마다, 표의 행은 본문 안에서 (머리행은 {error: 'table-head'}),
 * 목록 항목은 하위 항목과 함께 같은 목록 안에서 (수준이 다른 항목을 함께 고르면 {error: 'mixed'}), 여러 줄 문단의 일부는 그 문단 안에서, 그 밖은 블록째 이웃 블록과 맞바꾼다. 끝이면 {error: 'edge'}
 */
export function moveLines(lines, a, b, dir, { code = false } = {}) {
  if (code) return slide(lines, a, b, dir, 1, lines.at(-1) === '' ? lines.length - 1 : lines.length);
  const fence = fenceAt(fencesOf(lines), a);
  if (fence && a > fence.a && b <= innerEnd(fence) && !(a === fence.a + 1 && b === innerEnd(fence))) return slide(lines, a, b, dir, fence.a + 1, innerEnd(fence));
  while (b > a && isBlank(lines[b - 1])) b -= 1;   // 범위 끝의 빈 줄은 옮기는 줄이 아니다
  while (a < b && isBlank(lines[a - 1])) a += 1;
  const blocks = blocksOf(lines);
  const blk = blockAt(blocks, a);
  const table = tableIn(lines, blk);
  if (table && a >= table.head && b <= table.last && !(a === table.head && b === table.last)) {
    return a <= table.sep ? { error: 'table-head' } : slide(lines, a, b, dir, table.first, table.last);
  }
  if (!fence && !table) {
    const moved = moveItems(lines, a, b, dir);
    if (moved) return moved;
  }
  const part = blocks.filter((x) => x.b >= a && x.a <= b && x.kind !== 'front');
  if (!part.length || part.some((x) => x.kind === 'wall')) return { error: 'edge' };
  const [first] = part;
  const last = part.at(-1);
  const callout = CALLOUT.test(bodyOf(lines[first.a - 1]).trim());
  const plain = first === last && first.kind === 'text' && !table
    && !lines.slice(first.a, first.b).some((s) => SETEXT.test(bodyOf(s)));
  if (plain && (a > first.a || b < first.b) && !(callout && a === first.a)) {
    if (lines.slice(first.a - 1, first.b).some(itemOf)) return { error: 'mixed' };   // 수준이 다른 항목들 — 줄째 옮기면 목록의 구조가 바뀐다
    return slide(lines, a, b, dir, first.a + (callout ? 1 : 0), first.b);
  }
  const i = blocks.indexOf(first);
  const j = blocks.indexOf(last);
  const other = dir < 0 ? blocks[i - 1] : blocks[j + 1];
  if (!other || other.kind === 'front' || other.kind === 'wall') return { error: 'edge' };
  if (other.a === 1 && dir < 0 && lines[first.a - 1].trim() === '---') return { error: 'edge' };   // 맨 앞의 --- 는 머리 정보로 읽힌다
  if (dir < 0) {
    return { lines: swapped(lines, other.a, other.b, first.a, last.b), a: a - first.a + other.a, b: b - first.a + other.a };
  }
  const shift = other.b - last.b;
  return { lines: swapped(lines, first.a, last.b, other.a, other.b), a: a + shift, b: b + shift };
}

// ---- 지우기 -----------------------------------------------------------------------

/**
 * 줄 a~b 를 지운다 {lines, a, b(실제로 지운 범위), line(지운 뒤 현재 줄), ask(묻고 지울지 — 10줄 넘게거나 제목이 들었으면)}.
 * 코드는 그 줄만. md: 표의 머리행·구분 줄만 걸치면 {error: 'table-head'} (표 전체는 표째), 코드 블록의 ``` 줄만 걸치면 {error: 'fence'} (안의 줄 전부면 블록째),
 * 지운 뒤 빈 줄이 겹치면 하나로, 남는 하위 항목은 지운 항목의 자리로 올리고, 번호 목록은 다시 매긴다
 */
export function deleteLines(lines, a, b, { code = false } = {}) {
  if (code) {
    const next = lines.slice();
    next.splice(a - 1, b - a + 1);
    return { lines: next, a, b, line: Math.max(1, Math.min(a, next.length)), ask: b - a + 1 > 10 };
  }
  const fences = fencesOf(lines);
  for (const f of fences) {
    if (f.b < a || f.a > b) continue;
    const inner = a > f.a && b <= innerEnd(f);
    if (inner && a === f.a + 1 && b === innerEnd(f)) {   // 안의 줄 전부 — 블록째
      a = f.a;
      b = f.b;
    } else if (!inner && !(a <= f.a && b >= f.b)) return { error: 'fence' };
  }
  const inFence = !!fenceAt(fences, a) && a > fenceAt(fences, a).a;
  const blocks = blocksOf(lines);
  if (deckOf(lines) && lines.slice(a - 1, b).filter((s) => CELL_MARK.test(s.trim())).length % 2) return { error: 'edge' };   // 칸의 한쪽 표시만 지우면 칸이 깨진다
  for (const blk of blocks) {
    if (blk.b < a || blk.a > b) continue;
    const table = tableIn(lines, blk);
    if (table && a <= table.sep && b >= table.head && !(a <= table.head && b >= table.last)) return { error: 'table-head' };
  }
  let ask = b - a + 1 > 10;
  for (let n = a; n <= b && !ask; n++) {
    if (fenceAt(fences, n)) continue;
    const body = bodyOf(lines[n - 1]);
    ask = HEADING.test(body) || (n > 1 && SETEXT.test(body) && !isBlank(lines[n - 2]) && !itemOf(lines[n - 2]) && !RULE.test(body));
  }
  const after = (() => {   // 범위 뒤의 첫 글 줄 (번호를 다시 매길 목록)
    let n = b + 1;
    while (n <= lines.length && isBlank(lines[n - 1])) n += 1;
    return n <= lines.length && !inFence ? n : 0;
  })();
  const info = after && itemOf(lines[after - 1]) ? listInfo(lines, after) : null;
  const next = lines.slice();
  if (!inFence) {   // 지우는 항목의 남는 안쪽 줄은 그 항목의 자리로
    for (let n = a; n <= b; n++) {
      const it = itemOf(lines[n - 1]);
      if (!it) continue;
      const end = itemEnd(lines, n);
      for (let i = b + 1; i <= end; i++) next[i - 1] = shifted(next[i - 1], it.width - it.content);
    }
  }
  next.splice(a - 1, b - a + 1);
  if (!inFence) {
    const up = next[a - 2];
    const down = next[a - 1];
    if (down != null && isBlank(down) && (up == null || isBlank(up)) && next.length > 1) next.splice(a - 1, 1);
    else if (up != null && isBlank(up) && down == null && a > 2) next.splice(a - 2, 1);
  }
  if (info) {
    const removed = lines.length - next.length;
    if (after - removed >= 1) renumber(next, after - removed, info);
  }
  return { lines: next, a, b, line: Math.max(1, Math.min(a, next.length)), ask };
}
