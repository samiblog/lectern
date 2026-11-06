// 슬라이드의 원문 계산 (D96, DOM 없음): 칸 머리 줄·글자 크기 지시어를 읽고 고치고, 장을 더하고 복제하고 옮기고 지운다. 저장은 lineedit.js 가 한다.
// 줄 번호는 1부터. 장의 줄 범위 [a, b] 는 화면의 data-lines (slides.js 의 slideRule) — a 는 --- 다음 줄, b 는 다음 --- 앞 줄이다.
// 잘못된 요청은 {error: 까닭 이름} — 알림 문구는 부르는 쪽이 정한다.

/** 글자 크기를 정하는 구성 요소: 안쪽 이름 → 문서에 쓰는 한국어 낱말 (영어 낱말은 안쪽 이름 그대로) */
export const TEXT_WORDS = { title: '제목', sub: '소제목', body: '본문', table: '표', box: '박스글', code: '코드' };   // i18n-ok (문서의 문법)
/** 칸 배치: 이름 → [칸 자리(줄은 /), 열, 행]. t 는 제목 자리 */
export const LAYOUTS = {
  two: ['t t / a b', '1fr 1fr', 'auto 1fr'],
  'two-left': ['t t / a b', '2fr 1fr', 'auto 1fr'],
  'two-right': ['t t / a b', '1fr 2fr', 'auto 1fr'],
  three: ['t t t / a b c', '1fr 1fr 1fr', 'auto 1fr'],
  quad: ['t t / a b / c d', '1fr 1fr', 'auto 1fr 1fr'],
  'left-stack': ['t t / a b / a c', '3fr 2fr', 'auto 1fr 1fr'],
  'right-stack': ['t t / a b / c b', '2fr 3fr', 'auto 1fr 1fr'],
  kpi: ['t t t t / a b c d / e e e e', '1fr 1fr 1fr 1fr', 'auto auto 1fr'],
  'kpi-two': ['t t t / a b c / d d e', '1fr 1fr 1fr', 'auto auto 1fr'],
  stack: ['t / a / b', '1fr', 'auto 1fr 1fr'],
};

const KINDS = Object.fromEntries(Object.entries(TEXT_WORDS).flatMap(([kind, word]) => [[kind, kind], [word, kind]]));
const SIZE = /^\d{1,3}(?:\.\d)?$/;
// 격자·열·행 값 (style 속성에 들어간다). 13열 간트처럼 큰 격자도 쓴다 — 길이는 그것을 막지 않을 만큼만
export const SAFE_AREA = /^[\p{L}\p{N}_\s/.-]{1,4000}$/u;
export const SAFE_TRACK = /^[\w\s.,%()-]{1,600}$/;

/** text 값('표 14, 제목 30')들을 뒤의 것이 이기게 합친다 {table: 14, title: 30}. 모르는 낱말은 넘어간다 */
export function textSizes(...values) {
  const out = {};
  for (const value of values) {
    for (const part of typeof value === 'string' ? value.split(',') : []) {
      const m = /^\s*(\S+)\s+(\d{1,3}(?:\.\d)?)\s*$/.exec(part);
      if (m && Object.hasOwn(KINDS, m[1])) out[KINDS[m[1]]] = Number(m[2]);
    }
  }
  return out;
}

/** 칸 머리 줄을 낱말로: {name, words, size, at, odd(읽지 못한 것들)} */
function parseHead(head) {
  const [name = '', ...rest] = String(head).trim().split(/\s+/);
  const words = [];
  const odd = [];
  let size = null;
  let at = null;
  for (let i = 0; i < rest.length; i++) {
    const w = rest[i];
    if (w === 'at') {
      const box = rest.slice(i + 1, i + 5);
      if (box.length === 4 && box.every((x) => /^\d{1,4}$/.test(x))) {
        at = box.map(Number);
        i += 4;
      } else {   // 뒤의 수를 글자 크기로 읽지 않는다
        let n = i + 1;
        while (n < rest.length && /^-?\d/.test(rest[n])) n += 1;
        odd.push(rest.slice(i, n).join(' '));
        i = n - 1;
      }
    } else if (SIZE.test(w) && Number(w) > 0) size = Number(w);
    else if (/^[A-Za-z][\w-]*$/.test(w) && !w.startsWith('lec-')) words.push(w);
    else odd.push(w);
  }
  return { name, words, size, at, odd };
}

/** 칸 머리 줄의 ::: 뒤: 이름 다음에 꾸밈 낱말, 글자 크기(수), 자리(at x y 너비 높이). {name, words, size, at} */
export function readCellHead(head) {
  const { name, words, size, at } = parseHead(head);
  return { name, words, size, at };
}

/** 칸 머리 줄에서 읽지 못한 낱말들 (점검이 알린다 — slidelint.js) */
export const cellHeadOdds = (head) => parseHead(head).odd;

/** text 값에서 읽지 못한 부분들 */
export function textOdds(value) {
  return (typeof value === 'string' ? value.split(',') : []).map((x) => x.trim()).filter((part) => {
    const m = /^(\S+)\s+(\d{1,3}(?:\.\d)?)$/.exec(part);
    return part && !(m && Object.hasOwn(KINDS, m[1]));
  });
}

const RULE_LINE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;

/** 줄마다 코드 블록 안(여닫는 줄 포함)인지 — 코드 속의 지시어·칸 표시는 코드다 */
function fencedLines(lines) {
  let open = '';
  return lines.map((s) => {
    const f = /^[ \t]*(`{3,}|~{3,})(.*)$/.exec(s);
    if (open) {
      if (f && f[1][0] === open[0] && f[1].length >= open.length && !f[2].trim()) open = '';
      return true;
    }
    if (f && !(f[1][0] === '`' && f[2].includes('`'))) open = f[1];
    return !!open;
  });
}

/** 장 a~b 에 지시어를 넣을 줄. 제목으로 갈리는 장(headingDivider)은 첫 줄이 제목이고 그 앞은 앞 장이라 제목 다음 줄에 */
function slideTop(lines, a, b) {
  let at = a;
  while (at <= b && (!lines[at - 1]?.trim() || RULE_LINE.test(lines[at - 1]))) at += 1;
  let before = at - 1;
  while (before > 0 && !lines[before - 1].trim()) before -= 1;
  return before > 0 && !RULE_LINE.test(lines[before - 1]) && /^#{1,6}\s/.test(lines[at - 1] ?? '') ? at + 1 : at;
}

/** 장(줄 a~b)의 지시어 <!-- text: 표 14 --> 에서 word 의 크기를 size 로 — 없으면 그 장 맨 앞에 넣는다. 바뀐 줄 배열 */
export function setTextSize(lines, a, b, word, size) {
  const next = lines.slice();
  const kind = KINDS[word];
  const fenced = fencedLines(lines);
  for (let n = a; n <= b; n++) {
    const m = fenced[n - 1] ? null : /^<!--\s*(_?text):\s*(.*?)\s*-->\s*$/.exec(lines[n - 1]);
    if (!m) continue;
    const parts = m[2].split(',').map((x) => x.trim()).filter((x) => x && KINDS[x.split(/\s+/)[0]] !== kind);
    next[n - 1] = `<!-- ${m[1]}: ${[...parts, `${word} ${size}`].join(', ')} -->`;
    return next;
  }
  const at = slideTop(lines, a, b);
  next.splice(at - 1, 0, `<!-- text: ${word} ${size} -->`, ...(lines[at - 1]?.trim() ? [''] : []));
  return next;
}

/** 칸 머리 줄(line)의 글자 크기를 size 로 — at 뒤의 수는 건드리지 않는다. 바뀐 줄 배열 */
export function setCellSize(lines, line, size) {
  const words = lines[line - 1].trim().split(/\s+/);
  const skip = words.indexOf('at');
  const i = words.findIndex((w, k) => k > 1 && SIZE.test(w) && !(skip >= 0 && k > skip && k <= skip + 4));
  if (i >= 0) words[i] = String(size);
  else words.push(String(size));
  const next = lines.slice();
  next[line - 1] = words.join(' ');
  return next;
}

const blank = (s) => !String(s ?? '').trim();

/** 범위의 앞뒤 빈 줄을 뺀 [a, b] */
function trimmed(lines, [a, b]) {
  let x = a;
  let y = b;
  while (x < y && blank(lines[x - 1])) x += 1;
  while (y > x && blank(lines[y - 1])) y -= 1;
  return [x, y];
}

const CELL_HEAD = /^:::\s+\S/;
const NOTE_LINE = /^\s*<!--.*-->\s*$/;

/**
 * 장 [a, b] 에 배치를 넣는다 — 사람이 키만으로 칸을 만드는 길 (D96). 배치 지시어를 쓰고(있던 배치·격자 지시어는 지운다),
 * 있는 칸은 차례대로 새 이름으로 바꾸고, 모자라는 칸은 뼈대로 더한다. 남는 칸은 그대로 둔다 (글을 지우지 않는다 — 점검에 나온다).
 * 칸이 없는 장의 글은 첫 칸에 넣는다. words: 뼈대의 글 {body, number, label}. {lines, line(첫 칸의 첫 줄)}
 */
export function setLayout(lines, span, name, words) {
  const names = [...new Set(LAYOUTS[name][0].split(/[\s/]+/))].filter((x) => x !== 't');
  const [start, end] = trimmed(lines, span);
  const top = slideTop(lines, start, end);   // 제목으로 갈리는 장이면 제목은 그 자리에 두고 다음 줄부터
  const fenced = fencedLines(lines);
  let cells = 0;
  const body = [];
  for (let n = top; n <= end; n++) {
    const s = lines[n - 1];
    if (fenced[n - 1] || !CELL_HEAD.test(s.trim())) {
      if (fenced[n - 1] || !/^<!--\s*_?(?:layout|grid|cols|rows):.*-->\s*$/.test(s)) body.push(s);
      continue;
    }
    const parts = s.trim().split(/\s+/);
    if (names[cells]) parts[1] = names[cells];
    cells += 1;
    body.push(parts.join(' '));
  }
  while (top > start && blank(body[0]) && body.length) body.shift();
  if (!cells) {
    const content = (s) => s.trim() && !NOTE_LINE.test(s) && !/^#{1,2}\s/.test(s);
    const first = body.findIndex(content);
    if (first >= 0) {
      const last = body.length - 1 - [...body].reverse().findIndex(content);
      body.splice(last + 1, 0, ':::');
      body.splice(first, 0, `::: ${names[0]}`);
      cells = 1;
    }
  }
  for (const [i, cell] of names.entries()) {
    if (i < cells) continue;
    const number = name.startsWith('kpi') && i < (name === 'kpi' ? 4 : 3);
    if (body.at(-1)?.trim()) body.push('');
    body.push(`::: ${cell} ${number ? 'kpi' : 'card'}`, ...(number ? [`**${words.number}**`, words.label] : [words.body]), ':::');
  }
  const out = [...(top > start ? [''] : []), `<!-- layout: ${name} -->`, '', ...body];
  const next = lines.slice();
  next.splice(top - 1, Math.max(0, end - top + 1), ...out);
  return { lines: next, line: top + out.findIndex((s) => CELL_HEAD.test(s)) + 1 };
}

/** 장 [a, b] 뒤에 제목만 있는 새 장을 넣는다. {lines, line(새 제목 줄)} */
export function addSlide(lines, span, title) {
  const [, end] = trimmed(lines, span);
  const next = lines.slice();
  next.splice(end, 0, '', '---', '', `## ${title}`);
  return { lines: next, line: end + 4 };
}

/** 장 [a, b] 를 바로 뒤에 복제한다. {lines, line(복제한 장의 첫 줄)} */
export function duplicateSlide(lines, span) {
  const [start, end] = trimmed(lines, span);
  const next = lines.slice();
  next.splice(end, 0, '', '---', '', ...lines.slice(start - 1, end));
  return { lines: next, line: end + 4 };
}

/** spans[i] 장을 앞(-1)·뒤(+1) 장과 맞바꾼다 — 사이의 --- 줄은 그대로. {lines, line(옮긴 장의 첫 줄)}, 끝이면 {error: 'edge'} */
export function moveSlide(lines, spans, i, dir) {
  if (!spans[i + dir]) return { error: 'edge' };
  const [front, back] = dir < 0 ? [spans[i + dir], spans[i]] : [spans[i], spans[i + dir]];
  const [x1, x2] = trimmed(lines, front);
  const [y1, y2] = trimmed(lines, back);
  // 구분 줄 없이 제목으로 갈리는 장은 제목이 있어야 다른 장에 붙지 않는다. 빈 장은 옮길 글이 없다
  const ruled = lines.slice(x2, y1 - 1).some((s) => RULE_LINE.test(s));
  const headed = (n) => /^#{1,6}\s/.test(lines[n - 1]);
  if (blank(lines[x1 - 1]) || blank(lines[y1 - 1]) || (!ruled && !(headed(x1) && headed(y1)))) return { error: 'edge' };
  const next = [...lines.slice(0, x1 - 1), ...lines.slice(y1 - 1, y2), ...lines.slice(x2, y1 - 1), ...lines.slice(x1 - 1, x2), ...lines.slice(y2)];
  return { lines: next, line: dir < 0 ? x1 : x1 + (y2 - y1 + 1) + (y1 - 1 - x2) };
}

/** spans[i] 장을 구분 줄과 함께 지운다. {lines, line(지운 뒤 그 자리의 장)}, 하나뿐이면 {error: 'only'} */
export function deleteSlide(lines, spans, i) {
  if (spans.length < 2) return { error: 'only' };
  const next = lines.slice();
  if (i < spans.length - 1) {
    const [a] = spans[i];
    next.splice(a - 1, spans[i + 1][0] - a);
    return { lines: next, line: trimmed(next, [a, a + spans[i + 1][1] - spans[i + 1][0]])[0] };
  }
  const [, from] = trimmed(lines, spans[i - 1]);   // 앞 장의 글 뒤부터 (--- 줄이 있으면 그 줄도)
  next.splice(from, lines.length - from, '');
  return { lines: next, line: trimmed(next, spans[i - 1])[0] };
}
