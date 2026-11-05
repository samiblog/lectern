// 메모의 글 (D92, DOM 없음): .lectern/notes.md ↔ 메모 목록. 화면은 notes.js.
//
// 사람과 Claude Code 가 그대로 읽는 Markdown 이다. 메모마다 맨 앞에 설명 줄 하나:
//
//   <!-- lectern-note id=n1 color=yellow pinned=1 path=docs%2Fa.md line=12 end=20 -->
//   ## 제목
//
//   본문 — '- [ ] 할 일' 이 있으면 할 일 칸으로 보인다
//
// 값은 encodeURIComponent 로 적어 빈칸·따옴표·'-->' 가 줄을 깨지 않는다. 설명 줄이 없는 글(사람이 파일에 직접 쓴 것)도
// 잃지 않는다 — 맨 앞의 글은 메모 하나가 된다. 모르는 값은 그대로 다시 적는다.

const HEADER = '<!-- lectern-notes: read and written by Lectern, safe to edit by hand -->';
const META = /^<!-- lectern-note ?(.*?) ?-->$/;
const TASK = /^(\s*)[-*+] \[( |x|X)\] (.*)$/;
export const COLORS = ['', 'yellow', 'green', 'blue', 'purple', 'pink', 'gray'];

let seq = 0;

/** 새 메모의 id. 같은 순간에 여럿 만들어도 겹치지 않게 */
export function newId(now = Date.now()) {
  seq += 1;
  return `n${now.toString(36)}${seq.toString(36)}`;
}

function readMeta(line) {
  const out = {};
  for (const part of line.split(' ').filter(Boolean)) {
    const at = part.indexOf('=');
    if (at < 1) continue;
    try {
      out[part.slice(0, at)] = decodeURIComponent(part.slice(at + 1));
    } catch {
      out[part.slice(0, at)] = part.slice(at + 1);
    }
  }
  return out;
}

function makeNote(meta, lines, index) {
  const rest = [...lines];
  while (rest.length && !rest[0].trim()) rest.shift();
  let title = '';
  if (/^## /.test(rest[0] || '')) title = rest.shift().slice(3).trim();
  while (rest.length && !rest[0].trim()) rest.shift();
  while (rest.length && !rest.at(-1).trim()) rest.pop();
  const { id, color, pinned, path, line, end, ...extra } = meta;
  return {
    id: id || `x${index}`,
    title,
    body: rest.join('\n'),
    color: COLORS.includes(color) ? color : '',
    pinned: pinned === '1',
    path: path || '',
    line: Number(line) || 0,
    end: Number(end) || 0,
    extra,
  };
}

/** 파일의 글 → 메모 목록 (파일 차례) */
export function parseNotes(text) {
  const notes = [];
  let meta = null;
  let lines = [];
  const flush = () => {
    if (meta || lines.some((l) => l.trim())) notes.push(makeNote(meta || {}, lines, notes.length));
    lines = [];
  };
  for (const line of String(text || '').replace(/^﻿/, '').replace(/\r\n?/g, '\n').split('\n')) {
    if (line.startsWith('<!-- lectern-notes')) continue;
    const m = META.exec(line.trim());
    if (m) {
      flush();
      meta = readMeta(m[1]);
    } else {
      lines.push(line);
    }
  }
  flush();
  return notes;
}

const isEmpty = (note) => !note.title.trim() && !note.body.trim();

/** 메모 목록 → 파일의 글. 아무것도 적지 않은 메모는 쓰지 않는다 */
export function writeNotes(notes) {
  const parts = [HEADER];
  for (const n of notes) {
    if (isEmpty(n)) continue;
    const meta = { id: n.id, color: n.color, pinned: n.pinned ? '1' : '', path: n.path, line: n.line || '', end: n.end || '', ...n.extra };
    const fields = Object.entries(meta).filter(([, v]) => v !== '' && v != null).map(([k, v]) => `${k}=${encodeURIComponent(v)}`);
    const title = n.title.trim() ? `## ${n.title.trim().replace(/\n/g, ' ')}\n\n` : '';
    parts.push(`<!-- lectern-note ${fields.join(' ')} -->\n${title}${n.body.trim()}`);
  }
  return `${parts.join('\n\n')}\n`;
}

/** 고정한 메모 먼저, 그 안에서는 파일 차례 */
export const shownOrder = (notes) => [...notes.filter((n) => n.pinned), ...notes.filter((n) => !n.pinned)];

/** 글자로 거르기: 낱말이 모두 제목·본문에 들어 있는 것 (대소문자 무시) */
export function filterNotes(notes, query) {
  const terms = String(query || '').toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return notes;
  return notes.filter((n) => {
    const hay = `${n.title}\n${n.body}`.toLowerCase();
    return terms.every((w) => hay.includes(w));
  });
}

/** 본문의 줄을 글·할 일로 [{task, done, text, indent}] */
export function bodyLines(body) {
  return String(body || '').split('\n').map((line) => {
    const m = TASK.exec(line);
    return m ? { task: true, done: m[2] !== ' ', text: m[3], indent: m[1] } : { task: false, done: false, text: line, indent: '' };
  });
}

/** 본문이 할 일 목록인지 — 글이 있는 줄이 모두 할 일 */
export function isTaskList(body) {
  const lines = bodyLines(body).filter((l) => l.task || l.text.trim());
  return lines.length > 0 && lines.every((l) => l.task);
}

const taskLine = (l) => `${l.indent}- [${l.done ? 'x' : ' '}] ${l.text}`;

/** 글 ↔ 할 일 목록: 할 일이 아니면 줄마다 체크 칸을 달고, 할 일이면 체크 칸을 뗀다 */
export function switchList(body) {
  if (isTaskList(body)) return bodyLines(body).filter((l) => l.task).map((l) => l.text).join('\n');
  return bodyLines(body).filter((l) => l.task || l.text.trim()).map((l) => taskLine({ ...l, task: true, text: l.text.replace(/^\s*[-*+]\s+/, '') })).join('\n');
}

/** i 번째 할 일을 바꾸고 끝낸 것을 아래로 (할 일만 있는 목록일 때) — 글이 섞인 메모는 자리를 그대로 둔다 */
export function toggleTask(body, i) {
  const lines = bodyLines(body);
  const task = lines.filter((l) => l.task)[i];
  if (!task) return body;
  task.done = !task.done;
  const render = (l) => (l.task ? taskLine(l) : l.text);
  if (!isTaskList(body)) return lines.map(render).join('\n');
  return [...lines.filter((l) => l.task && !l.done), ...lines.filter((l) => l.task && l.done)].map(render).join('\n');
}

/** i 번째 할 일의 글을 바꾼다. 비우면 그 줄을 뺀다 */
export function setTask(body, i, text) {
  const lines = bodyLines(body);
  const task = lines.filter((l) => l.task)[i];
  if (!task) return body;
  task.text = text;
  return lines.filter((l) => !(l === task && !text.trim())).map((l) => (l.task ? taskLine(l) : l.text)).join('\n');
}

/** 할 일을 끝낸 것 앞에 더한다 */
export function addTask(body, text) {
  const lines = bodyLines(body).filter((l) => l.task || l.text.trim());
  const at = lines.findIndex((l) => l.task && l.done);
  lines.splice(at < 0 ? lines.length : at, 0, { task: true, done: false, text, indent: '' });
  return lines.map((l) => (l.task ? taskLine(l) : l.text)).join('\n');
}

/** 메모의 출처 글: @경로 12~20행 */
export function fromText(note, rangeText) {
  if (!note.path) return '';
  return note.line ? `@${note.path} ${rangeText([note.line, note.end || note.line])}` : `@${note.path}`;
}

/** 복사·보내기에 쓰는 글: 제목, 본문, 출처 */
export function noteText(note, rangeText) {
  const from = fromText(note, rangeText);
  return [note.title.trim() ? `## ${note.title.trim()}` : '', note.body.trim(), from].filter(Boolean).join('\n\n');
}
