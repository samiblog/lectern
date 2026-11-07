// 문서 구성 요소의 계산 (D107~, DOM 없음): 원문 줄 배열을 받아 바뀐 줄 배열을 돌려준다. 저장은 lineedit.js 가 commit 으로 한다.
// lineops.js 가 줄을 다룬다면 여기는 줄의 종류, 제목과 절을 다룬다. 줄 번호는 1부터, 잘못된 요청은 {error: 까닭 이름}.
//
// - 표시는 사람이 고치지 않는다: setKind 가 줄의 표시를 떼고 새 표시를 단다.
// - 제목 줄은 절의 손잡이다: 수준 바꾸기(shiftHeadings)는 하위 절까지, 옮기기(moveSection)·지우기(sectionSpan)는 본문까지 함께.

import { quoteOf, itemOf, isBlank, fencesOf, fenceAt, frontEnd, blocksOf, blockAt, tableIn, deckOf, bodyEnd, notesStart } from './lineops.js';

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

// ---- 박스글 -------------------------------------------------------------------------

export const BOXES = ['NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION'];
const BOX_HEAD = /^[ \t]*>[ \t]?\[!([A-Za-z]+)\][ \t]*$/;

const depth = (s) => (quoteOf(s).match(/>/g) || []).length;

/** 줄 n 이 든 박스글 {a, b, kind}. 박스글이 아니면 null */
export function boxAt(lines, n) {
  if (!depth(lines[n - 1] ?? '')) return null;
  let a = n;
  while (a > 1 && depth(lines[a - 2])) a -= 1;
  let b = n;
  while (b < lines.length && depth(lines[b])) b += 1;
  const m = BOX_HEAD.exec(lines[a - 1]);
  return m ? { a, b, kind: m[1].toUpperCase() } : null;
}

/** 박스글의 종류를 바꾼다 (표시 한 줄) */
export function setBox(lines, n, kind) {
  const box = boxAt(lines, n);
  if (!box) return { error: 'not-box' };
  const next = lines.slice();
  next[box.a - 1] = next[box.a - 1].replace(/\[![A-Za-z]+\]/, `[!${kind}]`);
  return { lines: next, line: n };
}

/** 박스글을 풀어 보통 문단으로 — 인용 표시와 종류 줄을 뗀다 */
export function unwrapBox(lines, n) {
  const box = boxAt(lines, n);
  if (!box) return { error: 'not-box' };
  const body = lines.slice(box.a, box.b).map((s) => s.replace(/^[ \t]*>[ \t]?/, ''));
  return { lines: [...lines.slice(0, box.a - 1), ...body, ...lines.slice(box.b)], line: Math.max(box.a, n - 1) };
}

/** 줄 a~b 를 박스글로 감싼다 */
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
