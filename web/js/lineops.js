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

export const quoteOf = (s) => QUOTE.exec(s)[0];
const depthOf = (s) => (quoteOf(s).match(/>/g) || []).length;
const bodyOf = (s) => s.slice(quoteOf(s).length);
export const isBlank = (s) => !bodyOf(s).trim();

/** 앞 공백의 폭 (탭은 다음 4칸으로) */
function colsOf(lead) {
  let w = 0;
  for (const c of lead) w += c === '\t' ? 4 - (w % 4) : 1;
  return w;
}
const widthOf = (body) => colsOf(/^[ \t]*/.exec(body)[0]);

/** 목록 항목 줄이면 {quote, lead, width, marker, ordered, num, delim, gap, task, text, content(글이 시작하는 폭)}, 아니면 null */
export function itemOf(line) {
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
export function fencesOf(lines) {
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

export const fenceAt = (fences, n) => fences.find((f) => n >= f.a && n <= f.b) || null;
const innerEnd = (f) => (f.closed ? f.b - 1 : f.b);

/** 머리 정보(--- … ---)의 끝 줄. 없으면 0 */
export function frontEnd(lines) {
  if (lines[0]?.trim() !== '---') return 0;
  for (let i = 1; i < lines.length; i++) if (/^(?:---|\.\.\.)\s*$/.test(lines[i])) return i + 1;
  return 0;
}

/** 맨 앞 설정에 marp: true 인 Lectern 슬라이드인지 — 값을 읽는 법은 slides.js 의 readYaml 과 같게 (yes·on 도, 따옴표는 글) */
export const deckOf = (lines) => lines.slice(1, frontEnd(lines)).some((s) => /^[ \t]*marp[ \t]*:[ \t]+(?:true|yes|on)[ \t]*$/i.test(s) && s.trim().startsWith('marp'));

/** Lectern 슬라이드에서 장을 가르는 줄인지. 바로 위가 글이면 구분 줄이 아니라 그 글의 밑줄 제목이다 (제목\n---) */
function slideBreak(lines, n, fences) {
  if (!RULE.test(lines[n - 1])) return false;
  const p = lines[n - 2];
  return n < 2 || !SETEXT.test(lines[n - 1]) || isBlank(p) || !!fenceAt(fences, n - 1) || !!itemOf(p) || depthOf(p) > 0
    || HEADING.test(p) || RULE.test(p) || CELL_MARK.test(p.trim()) || COMMENT_LINE.test(p);
}

/** 문서의 블록들 [{a, b, kind: 'front'|'fence'|'heading'|'text'|'wall'}] (빈 줄 뺌). wall: Lectern 슬라이드의 칸(:::)·장(---)·지시어 줄 — 글이 넘지 않는다 */
export function blocksOf(lines) {
  const fences = fencesOf(lines);
  const blocks = [];
  const front = frontEnd(lines);
  const deck = deckOf(lines);
  const wall = (n) => deck && (CELL_MARK.test(lines[n - 1].trim()) || COMMENT_LINE.test(lines[n - 1]) || slideBreak(lines, n, fences));
  if (front) blocks.push({ a: 1, b: front, kind: 'front' });
  let n = front + 1;
  while (n <= lines.length) {
    const f = fenceAt(fences, n);
    const s = lines[n - 1];
    if (f) {
      blocks.push({ a: f.a, b: f.b, kind: 'fence' });
      n = f.b + 1;
    } else if (isBlank(s)) n += 1;
    else if (wall(n)) {
      blocks.push({ a: n, b: n, kind: 'wall' });
      n += 1;
    } else if (HEADING.test(bodyOf(s))) {
      blocks.push({ a: n, b: n, kind: 'heading' });
      n += 1;
    } else {
      let b = n;
      while (b < lines.length && !isBlank(lines[b]) && depthOf(lines[b]) === depthOf(s) && !fenceAt(fences, b + 1) && !HEADING.test(bodyOf(lines[b])) && !wall(b + 1)) b += 1;
      blocks.push({ a: n, b, kind: 'text' });
      n = b + 1;
    }
  }
  return blocks;
}

/** 블록 안의 표 {head, sep, first, last} (첫 본문 행·끝 행 — 본문이 없으면 first > last). 표가 아니면 null */
export function tableIn(lines, blk) {
  if (blk?.kind !== 'text') return null;
  for (let i = blk.a + 1; i <= blk.b; i++) {
    if (TABLE_SEP.test(bodyOf(lines[i - 1])) && bodyOf(lines[i - 2]).includes('|')) return { head: i - 1, sep: i, first: i + 1, last: blk.b };
  }
  return null;
}

export const blockAt = (blocks, n) => blocks.find((x) => n >= x.a && n <= x.b) || null;

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
      if (depthOf(s) < depth) break;   // 인용보다 얕은 빈 줄은 인용을 끝낸다 (D189 — 빈 줄로 나뉜 두 인용의 목록을 한 목록으로 봤다)
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
  const deck = deckOf(lines);
  const wall = (s) => deck && (CELL_MARK.test(s.trim()) || RULE.test(s));   // 앞 칸·앞 장의 목록은 이 줄의 주인이 아니다
  if (wall(lines[n - 1])) return 0;
  const depth = depthOf(lines[n - 1]);
  const width = widthOf(bodyOf(lines[n - 1]));
  let gap = false;
  for (let i = n - 1; i >= 1; i--) {
    const s = lines[i - 1];
    if (isBlank(s)) {
      if (depthOf(s) < depth) return 0;
      gap = true;
      continue;
    }
    if (depthOf(s) !== depth || HEADING.test(bodyOf(s)) || wall(s)) return 0;
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
    if (isBlank(s)) {
      if (depthOf(s) < depth) return 0;
      continue;
    }
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
  while (i <= lines.length && isBlank(lines[i - 1])) {
    if (depthOf(lines[i - 1]) < depthOf(lines[n - 1])) return 0;
    i += 1;
  }
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
    if (isBlank(s)) {
      if (depthOf(s) < depth) return 0;
      continue;
    }
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

/** 줄 n 이 든 목록 항목의 범위 [항목 줄, 끝 줄] — 하위 항목·이어진 줄까지. 목록 밖이면 null (D152) */
export function itemSpan(lines, n) {
  const own = ownerItem(lines, n);
  return own ? [own, itemEnd(lines, own)] : null;
}

/** 줄 a~b 의 들여쓰기를 delta 칸 옮긴 새 배열 (빈 줄은 그대로, 0 칸 아래로는 가지 않는다 — D152) */
export function indentLines(lines, a, b, delta) {
  const next = lines.slice();
  for (let i = a; i <= b; i++) next[i - 1] = shifted(next[i - 1], delta);
  return next;
}

/** 줄 n 이 든 번호 목록의 번호를 첫 항목의 번호부터 다시 매긴 새 배열 — 모두 같은 번호로 쓴 목록·번호 목록이 아니면 그대로 (D152 — vi 의 p·P) */
export function renumberAt(lines, n) {
  if (!itemOf(lines[n - 1] ?? '')?.ordered) return lines;
  let first = n;
  for (let p = prevSibling(lines, first); p; p = prevSibling(lines, first)) first = p;
  const nums = [];
  for (let i = first; i; i = nextSibling(lines, i)) nums.push(itemOf(lines[i - 1]).num);
  if (nums.length < 2 || nums.every((x) => x === nums[0])) return lines;
  const next = lines.slice();
  renumber(next, first, { start: nums[0], flat: false });
  return next;
}

/** 줄 n 이 든 목록에서 같은 수준의 항목들 [항목 줄…] — 첫 항목부터 (D155). 목록 밖이면 [] */
export function siblingsOf(lines, n) {
  const own = ownerItem(lines, n);
  if (!own) return [];
  let first = own;
  for (let p = prevSibling(lines, first); p; p = prevSibling(lines, first)) first = p;
  const out = [];
  for (let i = first; i; i = nextSibling(lines, i)) out.push(i);
  return out;
}

/**
 * 줄 n 이 든 번호 목록을 start 부터 다시 매긴다 {lines, count(번호가 바뀐 항목 수)} (D155 — 줄을 목록 밖으로 바꾼 뒤 뒤 항목을 앞 항목에 잇는다).
 * 모두 같은 번호로 쓴 목록(1. 1. 1.)·번호 목록이 아니면 그대로
 */
export function renumberFrom(lines, n, start) {
  if (!itemOf(lines[n - 1] ?? '')?.ordered) return { lines, count: 0 };
  const sib = siblingsOf(lines, n);
  const nums = sib.map((i) => itemOf(lines[i - 1]).num);
  if (nums.length > 1 && nums.every((x) => x === nums[0])) return { lines, count: 0 };
  const next = lines.slice();
  let count = 0;
  sib.forEach((i, k) => {
    const it = itemOf(next[i - 1]);
    if (it.num === start + k) return;
    remark(next, i, `${start + k}${it.delim}`);
    count += 1;
  });
  return { lines: next, count };
}

/**
 * 줄 n 의 위(dir<0)·아래(dir>0)에 이어진 목록의 항목 — 빈 줄은 건너뛰고, 같은 인용 깊이에서 폭이 width 인 것 (D155 — 바꾼 줄을 이웃 목록에 붙일 때).
 * 위쪽은 그 줄을 품은 항목을 width 까지 거슬러 올라간다. {n(항목 줄), it, end(그 항목의 끝 줄), loose(빈 줄로 띄운 목록 — 항목이 하나뿐이면 null)} 또는 null
 */
export function listNear(lines, n, dir, width = 0) {
  const depth = depthOf(lines[n - 1] ?? '');
  let i = n + dir;
  while (i >= 1 && i <= lines.length && isBlank(lines[i - 1]) && depthOf(lines[i - 1]) === depth) i += dir;
  if (i < 1 || i > lines.length || depthOf(lines[i - 1]) !== depth) return null;
  let own = dir < 0 ? ownerItem(lines, i) : itemOf(lines[i - 1]) ? i : 0;
  while (dir < 0 && own && itemOf(lines[own - 1]).width > width) own = parentItem(lines, own);   // 아래쪽은 거슬러 오르지 않는다 — n 자신의 하위일 수 있다
  if (!own) return null;
  const it = itemOf(lines[own - 1]);
  if (it.width !== width) return null;
  const sib = siblingsOf(lines, own);
  const loose = sib.length > 1 ? sib.some((x, k) => k > 0 && lines.slice(itemEnd(lines, sib[k - 1]), x - 1).some(isBlank)) : null;
  return { n: own, it, end: itemEnd(lines, own), loose };
}

/**
 * 줄 n 이 든 목록의 같은 수준 항목을 모두 kind 로 — 'bullet'·'number'·'task' (D155 — 바꾸기 창의 '이 목록 전체를'). 하위 항목은 그대로 따라 옮긴다.
 * 번호는 첫 항목의 번호부터(번호 목록이 아니었으면 1), 할 일의 체크는 할 일끼리면 지킨다. {lines, line, a, b} 또는 {error: 'not-list'}
 */
export function relist(lines, n, kind) {
  const sib = siblingsOf(lines, n);
  if (!sib.length) return { error: 'not-list' };
  const next = lines.slice();
  const first = itemOf(lines[sib[0] - 1]);
  const start = first.ordered ? first.num : 1;
  sib.forEach((i, k) => {
    const it = itemOf(next[i - 1]);
    remark(next, i, kind === 'number' ? `${start + k}${it.ordered ? it.delim : '.'}` : it.ordered ? '-' : it.marker);
    const x = itemOf(next[i - 1]);
    const task = kind === 'task' ? x.task || '[ ] ' : '';
    next[i - 1] = `${x.quote}${x.lead}${x.marker}${x.gap || ' '}${task}${x.text}`;
  });
  return { lines: next, line: n, a: sib[0], b: itemEnd(next, sib.at(-1)) };
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
    const closing = after != null && deckOf(lines) && CELL_MARK.test(after.trim());   // 칸의 끝 — 닫는 줄 앞에 빈 줄을 두지 않는다
    return { ...para, at, pre: [sep], post: !inside && !closing && after != null && !isBlank(after) ? [sep] : [] };
  }
  const a = blk?.a ?? n;
  if (CALLOUT.test(bodyOf(lines[a - 1]).trim())) return { ...para, at: a, pre: [], post: [sep] };   // 강조글의 [!NOTE] 줄은 맨 앞에 남는다
  if (!quote && !split) {   // 위에 넣는 줄은 위 블록의 양식을 따른다 (D155) — 문단·제목 바로 위가 목록·인용이면 그 끝에 잇는다 (from: 화면에서 붙일 줄)
    let p = a - 1;
    while (p >= 1 && isBlank(lines[p - 1])) p -= 1;
    const above = p >= 1 ? blockAt(blocks, p) : null;
    if (above?.kind === 'text' && !tableIn(lines, above) && (ownerItem(lines, p) || quoteOf(lines[p - 1]))) {
      const up = planNew(lines, p, true);
      if (!up.error) return { ...up, from: p };
    }
  }
  const before = lines[a - 2];
  return { ...para, at: a - 1, pre: before != null && !isBlank(before) ? [sep] : [], post: [sep] };
}

/**
 * 문서 끝의 새 줄 계획 (D106 — 마지막 줄에서 ↓, 빈 문서): 끝이 목록·인용이면 planNew 처럼 같은 레벨, 아니면 마지막 글 뒤의 빈 문단.
 * 표·코드 블록·수식·구분선 뒤에도 문단을 연다. 끝의 빈 줄은 건너뛴다
 */
/** 문서 끝에 모인 각주 정의(와 들여 쓴 뒷줄)가 시작하는 줄 — 없으면 0. 주는 문서 맨 끝에 모인다 (D110) */
export function notesStart(lines) {
  let start = 0;
  for (let n = lines.length; n >= 1; n--) {
    const s = lines[n - 1];
    if (!s.trim() || /^(?: {2,}|\t)/.test(s)) continue;   // 빈 줄·주의 뒷줄
    if (!/^\[\^[^\]]+\]:/.test(s)) break;
    start = n;
  }
  return start;
}

/** 끝의 각주를 뺀 본문의 끝 글 줄 (last 까지만 본다) — 끝에 쓰는 새 줄·붙임이 그 뒤에 들어간다 */
export function bodyEnd(lines, last = lines.length) {
  const start = notesStart(lines);
  if (!start || start > last) return last;
  let end = start - 1;
  while (end && !lines[end - 1].trim()) end -= 1;
  return end;
}

export function planEnd(lines, after = 0) {
  let last = lines.length;
  while (last && !lines[last - 1].trim()) last -= 1;
  if (!after) last = bodyEnd(lines, last);   // 끝에 쓰는 글은 각주 앞에
  if (after) last = blockAt(blocksOf(lines), after)?.b ?? after;   // 그 블록 뒤에 — 슬라이드의 칸, 표·그림 뒤
  const para = { head: '', fill: '', kind: 'para', list: null, post: [] };
  if (!last) return { ...para, at: 0, pre: [] };
  const blk = blockAt(blocksOf(lines), last);
  if (blk?.kind === 'text' && !fenceAt(fencesOf(lines), last) && !tableIn(lines, blk) && (ownerItem(lines, last) || quoteOf(lines[last - 1]))) return planNew(lines, last, true);
  return { ...para, at: last, pre: [''], post: after && lines[last] != null && !isBlank(lines[last]) && !CELL_MARK.test(lines[last].trim()) ? [''] : [] };
}

/** 블록 앞의 새 문단 계획 (D117 — 차트·수식처럼 줄 안에 새 줄을 넣을 수 없는 블록의 위에) */
export function planBefore(lines, n) {
  const a = blockAt(blocksOf(lines), n)?.a ?? n;
  const prev = lines[a - 2];
  return { head: '', fill: '', kind: 'para', list: null, at: a - 1, pre: prev != null && !isBlank(prev) && !CELL_MARK.test(prev.trim()) ? [''] : [], post: [''] };
}

/** 항목 줄 위쪽에서 test 에 맞는 항목을 찾는다 {n, it} — 목록이 끝나는 곳에서 멈춘다 */
function itemAbove(lines, from, depth, test) {
  for (let n = from; n >= 1; n--) {
    const s = lines[n - 1];
    if (isBlank(s) && depthOf(s) === depth) continue;
    const it = depthOf(s) === depth ? itemOf(s) : null;
    if (it && test(it)) return { n, it };
    if (!it && (depthOf(s) !== depth || widthOf(bodyOf(s)) === 0)) return null;
  }
  return null;
}

/** 문단 계획 — quote 안에서, at 앞뒤로 빈 줄을 둔다 */
export function paraAt(lines, at, quote) {
  const sep = quote.trimEnd();
  const after = lines[at];
  return { at, pre: [sep], post: after != null && !isBlank(after) ? [sep] : [], head: quote, fill: '', kind: 'para', list: null };
}

/**
 * 아직 파일에 없는 빈 새 줄의 레벨을 바꾼다 (D106 — Tab·Shift+Tab·↓). 바뀐 계획, 더 갈 곳이 없으면 null.
 * dir > 0: 윗 항목의 하위로. dir < 0: 한 레벨 밖으로 — 맨 바깥 항목은 문단이 되어 목록이 끝나고, 인용 안의 문단은 인용 밖으로 나간다
 */
export function shiftPlan(lines, plan, dir) {
  const quote = quoteOf(plan.head);
  const depth = depthOf(plan.head);
  if (plan.kind === 'item') {
    const it = itemOf(`${plan.head}x`);
    const mark = (o) => (o.ordered ? `${o.num + 1}${o.delim}` : o.marker);
    if (dir > 0) {
      const prev = itemAbove(lines, plan.at, depth, (o) => o.width === it.width);
      if (!prev) return null;
      const marker = it.ordered ? `1${it.delim}` : it.marker;
      return { ...plan, head: `${quote}${' '.repeat(prev.it.content)}${marker}${it.gap || ' '}${it.task}`, list: null };
    }
    const parent = itemAbove(lines, plan.at, depth, (o) => o.width < it.width);
    if (parent) {
      const o = parent.it;
      return { ...plan, at: itemEnd(lines, parent.n), pre: [], post: [], head: `${quote}${o.lead}${mark(o)}${o.gap || ' '}${it.task}`, list: listInfo(lines, parent.n) };
    }
    return paraAt(lines, plan.at, quote);
  }
  if (plan.kind !== 'para' || dir > 0 || !depth) return null;
  let at = plan.at;
  while (at < lines.length && depthOf(lines[at]) >= depth) at += 1;   // 이 인용이 끝나는 줄 뒤로
  return paraAt(lines, at, quote.replace(/[ \t]*>[ \t]?$/, ''));
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
  // 문서 끝의 각주 정의와 본문은 서로 넘어가지 않는다 — 주는 문서 맨 끝에 모인다 (D110). 각주끼리는 바꿔도 된다
  const notes = notesStart(lines);
  if (notes && [first.a, last.b, other.a].some((n) => n >= notes) && ![first.a, last.b, other.a].every((n) => n >= notes)) return { error: 'edge' };
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
 * 코드는 그 줄만. md: 표의 머리행·구분 줄만 걸치면 {error: 'table-head'} (표 전체는 표째), 코드 블록의 ``` 줄만 걸치면 {error: 'fence'} (안의 줄 전부면 블록째 —
 * 그 바깥 줄과 함께여도), 지운 뒤 빈 줄이 겹치면 하나로, 번호 목록은 다시 매긴다.
 * 남은 줄은 보이는 모양(종류·레벨·목록의 간격) 그대로 둔다 (D189 — tools/edges/delete_fuzz.js 가 본다): 지운 항목의 글이 남으면 그 첫 줄이 표시를 넘겨받고,
 * 하위 항목은 남은 앞 형제 아래로 레벨 그대로 (앞 형제가 없으면 지운 항목의 자리로 올린다), 강조글의 머리 줄은 그 글이 남으면 둔다, 두 인용을 가르던
 * 빈 줄은 남기고, 빈 줄째 지워 위아래 블록이 붙으면 빈 줄을 하나 두며, 목록 안의 빈 줄이 바깥 목록의 항목 사이로 가지 않게 옮기거나 걷는다
 */
export function deleteLines(lines, a, b, { code = false, plain = false } = {}) {
  if (code || plain) {   // plain: 글머리 글자 목록(D192)의 항목 — '- '·'2.' 줄도 Markdown 목록이 아니므로 그 줄들만
    const next = lines.slice();
    next.splice(a - 1, b - a + 1);
    return { lines: next, a, b, line: Math.max(1, Math.min(a, next.length)), ask: b - a + 1 > 10 };
  }
  const fences = fencesOf(lines);
  for (const f of fences) {
    if (f.b < a || f.a > b) continue;
    const inner = a > f.a && b <= innerEnd(f);
    // 안의 줄 전부 — 블록째. ``` 줄은 화면의 줄이 아니라 고를 수 없으니, 앞뒤 문단부터 코드의 끝 줄(첫 줄)까지 고른 것도 블록째 (D189 — 전에는 '블록이 깨집니다')
    if (a <= f.a + 1 && b >= innerEnd(f)) {
      a = Math.min(a, f.a);
      b = Math.max(b, f.b);
    } else if (!inner) return { error: 'fence' };
  }
  // 강조글의 첫 글 줄은 머리 줄(> [!NOTE])과 한 화면 단위다 — 그 뒤에 글이 남으면 머리 줄은 둔다 (D189 — 남은 글이 일반 인용이 됐다).
  // 머리 줄이 범위 가운데에 있으면(앞 블록부터 고름) 머리 줄의 앞과 뒤를 따로 지운다
  const keepsHead = (h) => h < b && !fenceAt(fences, h) && calloutHead(lines[h - 1]) && lines.slice(h - 1, b).every((s) => depthOf(s) >= depthOf(lines[h - 1])) && quoteGoesOn(lines, b, depthOf(lines[h - 1]));
  for (let h = a + 1; h <= b; h++) {
    if (!keepsHead(h)) continue;
    const tail = deleteLines(lines, h, b);
    if (tail.error) return tail;
    const head = deleteLines(tail.lines, a, h - 1);
    return head.error ? head : { ...head, b, ask: head.ask || tail.ask };
  }
  if (keepsHead(a)) a += 1;
  const inFence = !!fenceAt(fences, a) && a > fenceAt(fences, a).a;
  const blocks = blocksOf(lines);
  const deck = deckOf(lines);
  if (deck) {   // 칸을 통째로가 아니면 칸 표시를 지우지 않는다 (앞 칸의 끝과 다음 칸의 머리를 함께 지우면 두 칸이 붙는다). 장의 구분 줄도
    let depth = 0;
    for (let n = a; n <= b; n++) {
      if (fenceAt(fences, n)) continue;
      const s = lines[n - 1].trim();
      if (CELL_MARK.test(s)) depth += s === ':::' ? -1 : 1;
      if (depth < 0 || slideBreak(lines, n, fences)) return { error: 'wall' };
    }
    if (depth) return { error: 'wall' };
  }
  for (const blk of blocks) {
    if (blk.b < a || blk.a > b) continue;
    const table = tableIn(lines, blk);
    if (table && a <= table.sep && b >= table.head && !(a <= table.head && b >= table.last)) return { error: 'table-head' };
  }
  let ask = b - a + 1 > 10;
  for (let n = a; n <= b && !ask; n++) {
    if (fenceAt(fences, n)) continue;
    const body = bodyOf(lines[n - 1]);
    ask = HEADING.test(body) || (n > 1 && SETEXT.test(body) && !isBlank(lines[n - 2]) && !itemOf(lines[n - 2]) && !RULE.test(body)) || (deck && COMMENT_LINE.test(lines[n - 1]));   // 발표의 주석은 지시어·노트
  }
  const after = (() => {   // 범위 뒤의 첫 글 줄 (번호를 다시 매길 목록)
    let n = b + 1;
    while (n <= lines.length && isBlank(lines[n - 1])) n += 1;
    return n <= lines.length && !inFence ? n : 0;
  })();
  const info = after && itemOf(lines[after - 1]) ? listInfo(lines, after) : null;
  const next = lines.slice();
  let took = 0;   // 항목 표시를 넘겨받은 줄
  let tookFrom = 0;   // 표시를 넘겨준 (지운) 항목
  let drop = 0;   // 넘겨받은 줄 앞에서 함께 걷는 빈 줄
  let gapTo = 0;   // 걷은 빈 줄을 옮길 곳 (다음 형제 항목 — 원문의 줄)
  let gapLine = '';
  let lift = null;   // 부모 항목 안에서 첫 항목의 하위 항목을 올렸으면 {n, end, it}
  if (!inFence) {
    // 지우는 항목의 남는 줄 (D189): 그 항목의 글(이어 쓴 줄·둘째 문단)이 남으면 그 첫 줄이 항목 표시를 넘겨받아 같은 레벨에 남는다 — 전에는
    // 모두 지운 항목의 표시 자리로 당겨, 남은 글이 윗 항목의 문단이 되고 아래 번호 항목들이 목록에서 빠져 그 문단의 글이 됐다.
    // 남는 것이 하위 항목뿐이면 지운 항목의 자리로 올린다. 안쪽 항목부터 — 넘겨받은 줄은 바깥 항목에게는 하위 항목이다
    for (let n = b; n >= a; n--) {
      const it = itemOf(lines[n - 1]);
      if (!it) continue;
      const end = itemEnd(lines, n);
      if (end <= b) continue;
      let f = b + 1;
      while (f < end && isBlank(next[f - 1])) f += 1;
      if (!took && takesMarker(next[f - 1])) {
        next[f - 1] = `${it.quote}${it.lead}${it.marker}${it.gap || ' '}${it.task}${bodyOf(next[f - 1]).trimStart()}`;
        took = f;
        tookFrom = n;
        const prev = keptSibling(lines, n, a);
        if (!prev) {   // 첫 항목이면 사이의 빈 줄을 걷어 다음 형제 앞으로 — 앞에 형제가 있으면 그 자리에 두어 목록의 간격(느슨함)이 그대로
          drop = f - b - 1;
          const ns = drop ? nextSibling(lines, n) : 0;
          if (ns && !isBlank(lines[ns - 2])) [gapTo, gapLine] = [ns, next[b]];
        }
        continue;
      }
      // 하위 항목만 남으면: 앞 형제 항목이 있으면 레벨 그대로 그 아래로 (들여쓰기를 앞 형제의 글 자리에 맞춘다), 목록의 첫 항목이면 지운 항목의 자리로
      // 올린다 — 부모가 없어 레벨을 지킬 수 없다 (D189 — 전에는 늘 올렸다. 줄을 지워도 남은 줄의 레벨은 그대로가 자연스럽다)
      const prev = keptSibling(lines, n, a);
      const delta = prev ? itemOf(lines[prev - 1]).content - it.content : it.width - it.content;
      for (let i = b + 1; i <= end; i++) next[i - 1] = shifted(next[i - 1], delta);
      if (!prev) lift = { n, end, it, parent: !!parentItem(lines, n) };   // 남은 앞 형제가 없어 올렸다 — 올린 목록 앞뒤의 빈 줄과 번호를 아래에서 본다 (바깥 항목이 나중에 덮어쓴다)
    }
  }
  next.splice(a - 1, b - a + 1 + drop);
  let here = a;   // 지운 뒤 현재 줄 — 지운 곳 바로 아래 줄
  // 지운 범위(넘겨받은 줄 앞의 빈 줄까지)와 그 위아래에서 가장 얕은 빈 줄 — 인용보다 얕으면 두 인용을 가르던 것이다 (그 줄을 지우면 아래 인용이 위 인용에 붙는다)
  const sep = [next[a - 2], next[a - 1], ...lines.slice(a - 1, b + drop)].filter((s) => s != null && isBlank(s)).sort((x, y) => depthOf(x) - depthOf(y))[0];
  if (!inFence) {
    const up = next[a - 2];
    const down = next[a - 1];
    // 겹친 빈 줄은 하나로 — 인용의 빈 줄(>)과 진짜 빈 줄이 만나면 인용의 것을 지운다 (D189 — 진짜 빈 줄을 지우면 아래 인용·강조글이 위 인용에 붙었다)
    if (down != null && isBlank(down) && (up == null || isBlank(up)) && next.length > 1) {
      next.splice(up != null && depthOf(up) > depthOf(down) ? a - 2 : a - 1, 1);
      if (a >= 2 && sep != null && depthOf(sep) < depthOf(next[a - 2])) next[a - 2] = sep;
      // 목록의 마지막 항목의 마지막 문단이었으면, 그 앞의 빈 줄이 목록을 느슨하게 하던 것일 수 있다 — 그 항목 앞(앞 형제와의 사이)에 하나 두어 간격이 그대로 (D189)
      const host = ownerItem(lines, a);
      if (host && host < a && itemEnd(lines, host) <= b && !nextSibling(lines, host) && prevSibling(lines, host) && !isBlank(lines[host - 2])) {
        next.splice(host - 1, 0, up ?? down);
        here += 1;
      }
      // 두 목록 사이의 글을 지워 같은 종류의 목록이 하나로 합쳐지면, 둘 다 붙은 목록이었으면 사이의 빈 줄을 걷는다 — 두면 합친 목록의
      // 모든 항목이 띄운 목록이 된다 (D189). 하나라도 띄운 목록이면 그대로
      const p = after && isBlank(next[here - 2] ?? '') && !isBlank(next[here - 3] ?? '') && itemOf(next[here - 1] ?? '') ? prevSibling(next, here) : 0;
      if (p && itemOf(lines[after - 1]) && !prevSibling(lines, after) && tightList(lines, after) && tightList(next, p, here - 2)) {
        next.splice(here - 2, 1);
        here -= 1;
      }
    } else if (up != null && isBlank(up) && down == null && a > 2) next.splice(a - 2, 1);
    else if (up != null && isBlank(up) && itemOf(down ?? '') && b < lines.length && !isBlank(lines[b])) {
      // 항목의 마지막 문단(또는 목록의 마지막 항목)을 지웠고 바로 아래가 더 얕은 항목이면, 그 앞의 빈 줄은 그 목록 안의 것이다 — 두면
      // 바깥 목록의 항목 사이가 벌어져 바깥 항목들의 간격(느슨함)이 바뀐다 (D189). 원래 아래 항목 앞에 빈 줄이 있었으면 그대로.
      // 걷은 빈 줄은 그 항목 앞(앞 형제와의 사이)으로 옮긴다 — 그 목록의 간격도 그대로
      const host = ownerItem(lines, a);
      const it = host ? itemOf(lines[host - 1]) : null;
      if (it && depthOf(lines[host - 1]) === depthOf(down) && itemOf(down).width < it.width) {
        let u = a - 2;
        while (u >= 1 && isBlank(next[u - 1])) u -= 1;
        const gap = next[u];
        next.splice(u, a - 1 - u);
        here -= a - 1 - u;
        const keep = host < a ? host : prevSibling(lines, host);   // 이 항목 앞으로 (지운 것이 항목이면 그 앞 형제 앞으로)
        if (keep && prevSibling(lines, keep) && !isBlank(lines[keep - 2])) {
          next.splice(keep - 1, 0, gap);
          here += 1;
        }
      }
    } else if (up != null && down != null && !isBlank(up) && !isBlank(down) && lines.slice(a - 1, b).some(isBlank)) {
      // 여러 블록에 걸쳐 빈 줄째 지우면 위아래 줄이 붙어 한 블록이 된다 — 아래 문단이 위 항목·인용의 이어 쓴 줄이 되거나 두 문단이 하나로 (D189).
      // 빈 줄 하나를 둔다. 아래가 항목이면: 위가 같은 목록의 항목이면 붙은 목록끼리일 때만 붙이고 (원래 한 목록이었으면 그 목록이 붙은 목록일 때),
      // 위 항목의 하위 목록이 되거나 바깥 항목이면 붙인다 — 빈 줄이 그 목록들의 간격을 바꾼다. 두 인용을 가르던 빈 줄은 늘 둔다
      let need = true;
      if (itemOf(down) && depthOf(sep) >= Math.min(depthOf(up), depthOf(down)) && depthOf(up) === depthOf(down) && ownerItem(next, a - 1)) {
        const p = prevSibling(next, a);
        let same = false;
        if (p && itemOf(lines[b] ?? '')) for (let s = prevSibling(lines, b + 1); s && !same; s = prevSibling(lines, s)) same = s === p;
        need = !!p && !(same ? tightList(lines, p) : tightList(lines, p, a - 1) && !!itemOf(lines[b] ?? '') && tightList(lines, b + 1));
      }
      if (need) {
        next.splice(a - 1, 0, sep);
        here += 1;
      }
    } else if (up != null && !isBlank(up) && down != null && isBlank(down) && !took) {
      // 중첩 목록의 첫 항목을 지웠고 그 뒤가 빈 줄이면, 빈 줄이 부모 항목의 글과 목록 사이로 간다 — 두면 부모 목록이 느슨해진다 (D189).
      // 걷고, 그 목록의 다음 형제 앞으로 옮긴다 — 그 목록의 간격도 그대로
      // 하위 항목을 올렸으면(lift) 올라온 목록 앞의 빈 줄 — 그 목록 안의 것이었으니 걷기만 한다
      const lifted = !!lift;
      const it = lifted ? lift.it : itemOf(lines[a - 1]);
      const parent = it && itemOf(lines[a - 1]) && (itemEnd(lines, a) <= b || lifted) && !prevSibling(lines, a) ? ownerItem(lines, a - 1) : 0;
      let v = a;
      while (v <= next.length && isBlank(next[v - 1])) v += 1;
      const y = itemOf(next[v - 1] ?? '');
      if (parent && depthOf(lines[parent - 1]) === depthOf(lines[a - 1]) && itemOf(lines[parent - 1]).width < it.width && y && y.width === it.width && (lifted || sameList(y, it))) {
        const gap = next[a - 1];
        next.splice(a - 1, v - a);
        if (lifted) lift.trim = v - a;
        else {
          const ns = nextSibling(next, a);
          if (ns && !isBlank(next[ns - 2])) next.splice(ns - 1, 0, gap);
        }
      }
    }
  }
  // 두 인용을 가르던 빈 줄을 지웠으면 다시 둔다 — 어느 길로 지웠든 아래 인용이 위 인용(강조글)에 붙지 않게 (D189)
  if (!inFence && sep != null && here >= 2 && here <= next.length) {
    let x = here - 1;
    while (x >= 1 && isBlank(next[x - 1])) x -= 1;
    const low = depthOf(sep);
    if (x >= 1 && low < depthOf(next[x - 1]) && low < depthOf(next[here - 1]) && !next.slice(x, here - 1).some((s) => depthOf(s) <= low)) {
      if (x < here - 1) next[x] = sep;
      else {
        next.splice(here - 1, 0, sep);
        here += 1;
      }
    }
  }
  const removed = lines.length - next.length;
  if (info) {
    const y = after - removed;
    const joined = y >= 1 && !!itemOf(next[y - 1] ?? '') && prevSibling(next, y) && !prevSibling(lines, after);   // 두 목록이 하나로 — 위 목록의 번호부터 잇는다
    if (y >= 1) renumber(next, y, joined ? listInfo(next, y) : info);
  } else if (took && itemOf(next[took - removed - 1] ?? '')?.ordered) {
    // 번호는 원래 목록의 시작 번호부터 — 남은 첫 항목이 2. 처럼 1 이 아닌 번호로 시작하면 위 문단을 끊지 못해 그 글이 된다
    renumber(next, took - removed, listInfo(lines, tookFrom));
  }
  let moved = 0;   // 옮겨 넣은 빈 줄
  if (took && gapTo) {   // 첫 항목이 넘겨준 빈 줄 — 다음 형제 앞으로 옮겨 목록의 간격이 그대로 (D189)
    const at = gapTo - (lines.length - next.length);
    if (at >= 2 && !isBlank(next[at - 2])) {
      next.splice(at - 1, 0, gapLine);
      moved = 1;
    }
  }
  if (lift) {
    // 목록의 첫 항목을 지우고 다른 종류의 하위 항목(번호 목록 안의 글머리표 등)을 올렸으면 (D189): 남은 형제들과 다른 목록이 된다 —
    // 그 사이의 빈 줄은 부모 항목의 두 목록 사이에 끼어 부모 목록을 띄운 목록으로 만드니 걷고, 남은 형제의 번호는 지운 항목의 번호부터
    const q = here + (lift.end - b) - (lift.trim ?? 0) - drop + moved;   // 올린 줄들 다음 줄 (걷은 빈 줄·옮겨 넣은 빈 줄만큼)
    let r = q;
    while (r <= next.length && isBlank(next[r - 1])) r += 1;
    const first = itemOf(next[here - 1] ?? '');
    const sib = itemOf(next[r - 1] ?? '');
    if (first && first.width === lift.it.width && !sameList(first, lift.it) && sib && sib.width === lift.it.width && sameList(sib, lift.it)) {
      if (r > q && lift.parent) {
        next.splice(q - 1, r - q);
        r = q;
      }
      if (sib.ordered) renumber(next, r, listInfo(lines, lift.n));
    }
  }
  return { lines: next, a, b, line: Math.max(1, Math.min(here, next.length)), ask };
}

/** 지우는 항목의 남은 글 줄이 항목 표시를 넘겨받을 수 있는지 — 글 문단만 (코드·제목·표·HTML·수식은 표시 뒤에 오면 뜻이 바뀐다) */
function takesMarker(s) {
  const t = bodyOf(s ?? '').trim();
  return !!t && !itemOf(s) && !FENCE.test(t) && !HEADING.test(t) && !RULE.test(t) && !SETEXT.test(t) && !TABLE_SEP.test(t)
    && !/^[|<]/.test(t) && !t.startsWith('$$') && !CELL_MARK.test(t);
}

/**
 * 항목 n 이 든 목록이 붙은 목록인지 — 첫 형제부터 마지막 형제의 끝(last 가 있으면 그 줄)까지, 그 목록의 항목 사이나 한 항목의 자식 사이에
 * 빈 줄이 없다. 하위 목록 안(하위 항목 사이·하위 항목의 문단 사이)의 빈 줄은 하위 목록의 것이다
 */
function tightList(lines, n, last = 0) {
  const w = itemOf(lines[n - 1]).width;
  let first = n;
  for (let p = prevSibling(lines, first); p; p = prevSibling(lines, first)) first = p;
  let end = n;
  for (let s = n; s; s = nextSibling(lines, s)) end = s;
  const stop = last || itemEnd(lines, end);
  const ours = (k) => { const o = ownerItem(lines, k); return !!o && itemOf(lines[o - 1]).width === w; };
  for (let i = first; i <= stop; i++) {
    if (!isBlank(lines[i - 1])) continue;
    let j = i + 1;
    while (j <= stop && isBlank(lines[j - 1])) j += 1;
    if (j > stop) break;   // 끝의 빈 줄
    const it = itemOf(lines[j - 1]);
    if (it ? it.width === w || (!prevSibling(lines, j) && ours(i - 1)) : ours(j)) return false;
    i = j - 1;
  }
  return true;
}

/** 항목 n 의 앞 형제 가운데 지우지 않는 것(줄 a 앞) — 함께 지우는 형제는 건너뛴다. 없으면 0 */
function keptSibling(lines, n, a) {
  let p = prevSibling(lines, n);
  while (p && p >= a) p = prevSibling(lines, p);
  return p;
}

/** 강조글의 머리 줄(> [!NOTE])인지 */
const calloutHead = (s) => !!depthOf(s) && CALLOUT.test(bodyOf(s).trim());

/** 줄 b 뒤로 같은 인용(깊이 depth 이상)에 글이 더 있는지 */
function quoteGoesOn(lines, b, depth) {
  for (let i = b; i < lines.length && depthOf(lines[i]) >= depth; i++) if (!isBlank(lines[i])) return true;
  return false;
}
