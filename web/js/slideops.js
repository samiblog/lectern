// 슬라이드의 원문 계산 (D96, DOM 없음): 칸 머리 줄·글자 크기 지시어를 읽고 고치고, 장을 더하고 복제하고 옮기고 지운다. 저장은 lineedit.js 가 한다.
// 줄 번호는 1부터. 장의 줄 범위 [a, b] 는 화면의 data-lines (slides.js 의 slideRule) — a 는 --- 다음 줄, b 는 다음 --- 앞 줄이다.
// 잘못된 요청은 {error: 까닭 이름} — 알림 문구는 부르는 쪽이 정한다.

/** 글자 크기를 정하는 구성 요소: 안쪽 이름 → 문서에 쓰는 한국어 낱말 (영어 낱말은 안쪽 이름 그대로) */
export const TEXT_WORDS = { title: '제목', sub: '소제목', body: '본문', table: '표', box: '박스글', code: '코드' };   // i18n-ok (문서의 문법)
const KINDS = Object.fromEntries(Object.entries(TEXT_WORDS).flatMap(([kind, word]) => [[kind, kind], [word, kind]]));
const SIZE = /^\d{1,3}(?:\.\d)?$/;

/** text 값('표 14, 제목 30')들을 뒤의 것이 이기게 합친다 {table: 14, title: 30}. 모르는 낱말은 넘어간다 */
export function textSizes(...values) {
  const out = {};
  for (const value of values) {
    for (const part of typeof value === 'string' ? value.split(',') : []) {
      const m = /^\s*(\S+)\s+(\d{1,3}(?:\.\d)?)\s*$/.exec(part);
      if (m && KINDS[m[1]]) out[KINDS[m[1]]] = Number(m[2]);
    }
  }
  return out;
}

/** 칸 머리 줄의 ::: 뒤: 이름 다음에 꾸밈 낱말, 글자 크기(수), 자리(at x y 너비 높이). {name, words, size, at} */
export function readCellHead(head) {
  const [name = '', ...rest] = String(head).trim().split(/\s+/);
  const words = [];
  let size = null;
  let at = null;
  for (let i = 0; i < rest.length; i++) {
    const w = rest[i];
    const box = rest.slice(i + 1, i + 5);
    if (w === 'at' && box.length === 4 && box.every((x) => /^\d{1,4}$/.test(x))) {
      at = box.map(Number);
      i += 4;
    } else if (SIZE.test(w)) size = Number(w);
    else if (/^[A-Za-z][\w-]*$/.test(w)) words.push(w);
  }
  return { name, words, size, at };
}

/** 장(줄 a~b)의 지시어 <!-- text: 표 14 --> 에서 word 의 크기를 size 로 — 없으면 그 장 맨 앞에 넣는다. 바뀐 줄 배열 */
export function setTextSize(lines, a, b, word, size) {
  const next = lines.slice();
  const kind = KINDS[word];
  for (let n = a; n <= b; n++) {
    const m = /^<!--\s*text:\s*(.*?)\s*-->\s*$/.exec(lines[n - 1]);
    if (!m) continue;
    const parts = m[1].split(',').map((x) => x.trim()).filter((x) => x && KINDS[x.split(/\s+/)[0]] !== kind);
    next[n - 1] = `<!-- text: ${[...parts, `${word} ${size}`].join(', ')} -->`;
    return next;
  }
  let at = a;
  while (at <= b && (!lines[at - 1]?.trim() || /^-{3,}\s*$/.test(lines[at - 1]))) at += 1;
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
