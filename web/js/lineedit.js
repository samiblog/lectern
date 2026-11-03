// 한 줄 편집 (D76): 한 줄만 하이라이트한 채 Shift+Enter(spotlight.js 가 'line-edit' 을 보낸다) — 그 줄을 화면의 그 자리에서 고친다.
//
// - 그 줄이 보이는 자리(lineunits.js 의 lineSlot — 블록의 글, 나눠 쓴 문단의 그 줄, 코드 블록·코드 화면의 그 줄, 표의 칸)의 내용을 떼어 두고
//   글 칸(contenteditable="plaintext-only" 인 .lec-line-edit)을 넣는다. 칸은 그 블록 안이라 제목 크기·글머리표·박스 색·코드 글꼴이 그대로다.
//   칸에는 원문의 그 줄에서 앞뒤 표시를 뗀 글이 들어간다 — 문장 속 서식은 `**굵게**`·`[링크](주소)` 처럼 글자로 (WYSIWYG 는 하지 않는다).
//   잠그는 것: 인용 >·들여쓰기·목록 표시(- * + 1. 1))·할 일 [ ]·제목 #·박스글 [!NOTE]·각주 [^1]:, 제목 끝의 #, 줄 끝의 공백·\(줄바꿈 표시),
//   코드 블록이 인용·목록 안이면 그 앞부분. 표의 행은 칸마다 (| 는 잠금, Tab·Shift+Tab 으로 옆 칸, 칸 글의 | 는 \| 로 저장).
// - Enter(·Ctrl+S): 저장. 원문을 새로 받아 그 줄이 시작할 때와 같으면 그 줄만 바꿔 /api/save — 편집 모드(D54)와 같은 길이라 줄바꿈·BOM·
//   읽기 전용·프로그램 폴더(D71)를 서버가 지킨다. 그사이 그 줄이 다른 곳에서 바뀌었으면 저장하지 않고 고친 줄을 클립보드에.
//   저장하면 그 칸을 바로 다시 그린다 (바뀐 곳 강조). Esc: 그만두기. 칸 밖을 누르거나 다른 탭을 고르면 고친 것이 있으면 저장, 없으면 그만둔다.
//   ↑·↓: 저장하고 위·아래 줄을 이어서 (표는 같은 칸 차례). Shift+→(글 끝에서): 저장하고 그 줄의 위치를 맨 앞 터미널에 (Claude 로 보내기).
//   한글 조합 중의 Enter·화살표는 조합의 것이다 (isComposing).
// - 저장한 뒤 Ctrl+Z(main.js — 문서 칸에서): 그 줄을 고치기 전으로 되돌려 저장. 거듭 누르면 그 앞 것도 — 파일이 마지막 저장 그대로일 때만 (hash).
// - 편집하는 동안 그 칸은 자동 새로고침·F5 로 다시 그리지 않는다 (nav.refreshView 가 pane.lineEdit 을 본다 — 끝낸 뒤 그린다).
//   글 칸 안의 키는 칸의 것이다 (앱 단축키는 쉰다), 누르기는 제목 접기·링크로 가지 않는다.

import { S, on, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { lineSlot, editableLines, indexOfLine } from './lineunits.js';
import { currentUnits, sourceLines, highlightLine, showLineEdit } from './spotlight.js';
import { refreshView } from './nav.js';
import { $, toast, copyText, rangeText, blockedReadOnly } from './util.js';
import { t } from './i18n.js';

let session = null;   // 편집 중 {pane, tab, path, line, kind, original, parts, places:[{span, frag}], cell, el}
const undos = [];     // 저장한 줄 [{tabId, path, line, before, after, hash}] — 마지막 것이 끝
const MAX_UNDO = 50;

export const lineEditing = () => !!session;

// ---- 줄 나누기: 잠그는 앞뒤 + 고칠 글 -------------------------------------------------

const QUOTE = /^(?:[ \t]*>[ \t]?)*/;

/** md 한 줄 → {head, body, tail} (head·tail 은 잠금) */
function splitText(line) {
  let i = 0;
  for (;;) {   // 인용 >·목록 표시(할 일 [ ] 까지)를 차례로 — '> - [ ] ' 처럼 겹친 것도
    const m = /^(?:[ \t]*>[ \t]?|[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$)(?:\[[ xX]\](?:[ \t]+|$))?)/.exec(line.slice(i));
    if (!m?.[0]) break;
    i += m[0].length;
  }
  i += /^[ \t]*/.exec(line.slice(i))[0].length;
  const quoted = /^[ \t]*>/.test(line);
  const lead = (quoted ? /^(?:#{1,6}(?:[ \t]+|$)|\[\^[^\]\s]+\]:[ \t]*|\[![A-Za-z]+\](?:[ \t]+|$))/ : /^(?:#{1,6}(?:[ \t]+|$)|\[\^[^\]\s]+\]:[ \t]*)/)
    .exec(line.slice(i));
  if (lead) i += lead[0].length;
  let body = line.slice(i);
  let tail = '';
  const close = lead?.[0].startsWith('#') && /[ \t]+#+[ \t]*$/.exec(body);   // 제목 끝의 # (닫는 표시)
  const end = close || /(?:[ \t]*\\|[ \t]+)$/.exec(body);   // 줄 끝 공백·\ (줄바꿈 표시)
  if (end) {
    tail = body.slice(end.index);
    body = body.slice(0, end.index);
  }
  return { head: line.slice(0, i), body, tail };
}

/** 코드 블록의 한 줄: 펜스가 인용·목록 안이면 그 앞부분(인용 >·펜스만큼의 들여쓰기)은 잠금 */
function splitCode(line, fence) {
  if (!fence) return { head: '', body: line, tail: '' };
  const fq = QUOTE.exec(fence)[0];
  const indent = /^ */.exec(fence.slice(fq.length))[0].length;
  const q = QUOTE.exec(line)[0];
  const lead = Math.min(indent, /^ */.exec(line.slice(q.length))[0].length);
  const head = line.slice(0, q.length + lead);
  return { head, body: line.slice(head.length), tail: '' };
}

/** 표의 한 행 → {head, cells:[{lead, body, trail}], open, close, after} — 칸은 \| 가 아닌 | 로 나눈다 */
function splitRow(line) {
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
  const cells = pieces.slice(open ? 1 : 0, close ? -1 : undefined).map((p) => {
    const m = /^(\s*)(.*?)(\s*)$/s.exec(p);
    if (m[2]) return { lead: m[1], body: m[2], trail: m[3] };
    const lead = p ? ' ' : '';   // 빈 칸: 글을 넣으면 '| 글 |' 이 되게
    return { lead, body: '', trail: p.slice(lead.length) };
  });
  return { head, cells, open, close, after: close ? pieces.at(-1) : '' };
}

/** 칸 글의 | 는 \| 로 (칸이 나뉘지 않게) */
function escapePipes(s) {
  let out = '';
  for (let i = 0; i < s.length; i++) {
    if (s[i] === '\\' && i + 1 < s.length) {
      out += s[i] + s[i + 1];
      i += 1;
    } else out += s[i] === '|' ? '\\|' : s[i];
  }
  return out;
}

/** 고친 글로 새 줄을 만든다 */
function buildLine(s) {
  const read = (p) => {
    let text = p.span.textContent.replace(/[\r\n]+/g, ' ');
    if (!p.nbsp) text = text.replace(/ /g, ' ');   // 칸이 공백을 nbsp 로 바꾼 것 (원문에 없던 것만)
    return text;
  };
  if (s.kind === 'table') {
    const { parts } = s;
    const cells = parts.cells.map((c, i) => {
      const place = s.places[i];
      return place ? { ...c, body: escapePipes(read(place)) } : c;
    });
    return parts.head + (parts.open ? '|' : '') + cells.map((c) => c.lead + c.body + c.trail).join('|') + (parts.close ? `|${parts.after}` : '');
  }
  return s.parts.head + read(s.places[0]) + s.parts.tail;
}

// ---- 시작 -----------------------------------------------------------------------

/** 단위(하이라이트한 한 줄)에서 고칠 줄 — 현재 위치가 그 안의 고칠 수 있는 줄이면 그 줄, 아니면 첫 줄 */
function lineOf(unit) {
  const lines = editableLines(unit, sourceLines());
  const here = S.pane?.here?.line;
  return lines.includes(here) ? here : lines[0];
}

/** 원문 줄 line 을 편집한다. cell: 표면 처음 고를 칸 차례 */
async function begin(line, { cell = 0 } = {}) {
  const pane = S.pane;
  if (!pane?.tab || session || pane.editor) return;
  if (blockedReadOnly(pane.tab)) return;   // Lectern 프로그램 폴더 안 (D71)
  // 다시 그리는 중(앞 줄을 저장한 뒤 등)이면 다 그린 뒤에 — 지금 보이는 것은 곧 바뀔 화면이다
  for (let waited = 0; pane.pending && waited < 5000; waited += 50) await new Promise((r) => setTimeout(r, 50));
  if (pane.pending || S.pane !== pane || session) return;
  const view = $('#lec-view');
  const path = view.dataset.docPath || view.dataset.codePath;
  if (view.dataset.sheet != null && view.classList.contains('code-view') && view.dataset.codePath && /\.xls[xm]$/i.test(path)) {
    toast(t('엑셀 보기는 보기만 합니다 — 고치려면 엑셀로 여세요'));   // D77
    return;
  }
  const shown = sourceLines();
  const slot = line && path ? lineSlot(view, line, shown) : null;
  if (!slot) {
    toast(view.querySelector('.csv-table') ? t('csv 표는 한 줄 편집을 하지 않습니다 — 편집 모드(Ctrl+E)에서 고칩니다')
      : t('이 줄은 한 줄 편집으로 고칠 수 없습니다 — 그림·다이어그램·수식·HTML 은 편집 모드(Ctrl+E)에서 고칩니다'));
    return;
  }
  const { tab } = pane;
  let src;
  try {
    src = await getJSON(`/api/source?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}`);
  } catch (e) {
    toast(t('한 줄 편집을 하지 못했습니다: {error}', { error: e.message }), 'error');
    return;
  }
  if (S.pane !== pane || $('#lec-view') !== view || session || !slot.el.isConnected) return;   // 그사이 다른 화면
  const original = src.text.split('\n')[line - 1];
  if (original == null || original !== shown[line - 1]) {   // 화면이 원문보다 늦다 (자동 새로고침 전)
    toast(t('화면이 원문과 달라 다시 그렸습니다 — Shift+Enter 를 다시 누르세요'));
    refreshView(pane);
    return;
  }
  const parts = slot.kind === 'table' ? splitRow(original) : slot.kind === 'code' ? splitCode(original, slot.fence) : splitText(original);
  const bodies = slot.kind === 'table' ? parts.cells.map((c) => c.body) : [parts.body];
  const n = Math.min(bodies.length, slot.ranges.length);
  if (!n) {
    toast(t('이 줄은 한 줄 편집으로 고칠 수 없습니다 — 그림·다이어그램·수식·HTML 은 편집 모드(Ctrl+E)에서 고칩니다'));
    return;
  }
  const places = [];
  for (let i = 0; i < n; i++) {
    const range = slot.ranges[i];
    const span = document.createElement('span');
    span.className = `lec-line-edit${slot.whole ? ' whole' : ''}`;
    span.contentEditable = 'plaintext-only';
    span.spellcheck = false;
    span.textContent = bodies[i];
    span.dataset.i = String(i);
    const frag = range.extractContents();
    range.insertNode(span);
    places.push({ span, frag, nbsp: bodies[i].includes(' ') });
  }
  session = { pane, tab, path, line, kind: slot.kind, original, parts, places, el: slot.el, cell: Math.min(cell, n - 1) };
  pane.lineEdit = session;
  for (const p of places) bind(p.span);
  document.addEventListener('mousedown', onOutside, true);
  focusPlace(session.cell);
  showLineEdit();
}

function focusPlace(i, atEnd = true) {
  const p = session?.places[i];
  if (!p) return;
  session.cell = i;
  p.span.focus();
  const r = document.createRange();
  r.selectNodeContents(p.span);
  if (atEnd) r.collapse(false);
  const sel = getSelection();
  sel.removeAllRanges();
  sel.addRange(r);
}

// ---- 끝내기 -----------------------------------------------------------------------

/** 떼어 둔 내용을 되돌려 놓는다 */
function restore(s) {
  for (const p of s.places) if (p.span.isConnected) p.span.replaceWith(p.frag);
}

/**
 * 편집을 끝낸다. save: 고친 것이 있으면 저장하고 그 칸을 다시 그린다. {ok, saved} — ok 가 false 면 저장하지 못했다(알렸다)
 */
async function finish(save) {
  const s = session;
  if (!s) return { ok: true, saved: false };
  session = null;
  s.pane.lineEdit = null;
  document.removeEventListener('mousedown', onOutside, true);
  const next = buildLine(s);
  if (!save || next === s.original) {
    restore(s);
    showLineEdit();
    if (s.pane.lineEditMissed) {   // 편집하는 동안 미룬 다시 그리기
      s.pane.lineEditMissed = false;
      refreshView(s.pane);
    }
    return { ok: true, saved: false };
  }
  for (const p of s.places) {
    p.span.contentEditable = 'false';
    p.span.classList.add('saving');
  }
  showLineEdit();
  try {
    const r = await writeLine(s.tab, s.path, s.line, s.original, next);
    if (!r) {   // 그사이 다른 곳에서 그 줄이 바뀌었다
      restore(s);
      await copyText(next);
      toast(t('다른 곳에서 이 줄이 바뀌어 저장하지 않았습니다 — 고친 줄은 클립보드에 복사했습니다'), 'error');
      refreshView(s.pane);
      return { ok: false, saved: false };
    }
    undos.push({ tabId: s.tab.id, path: s.path, line: s.line, before: s.original, after: next, hash: r.hash });
    if (undos.length > MAX_UNDO) undos.shift();
    s.pane.lineEditMissed = false;
    await refreshView(s.pane);
    toast(t('저장했습니다: {where} — Ctrl+Z 로 되돌립니다', { where: `${s.path} ${rangeText([s.line, s.line])}` }));
    return { ok: true, saved: true };
  } catch (e) {
    restore(s);
    toast(t('저장하지 못했습니다: {error}', { error: e.message }), 'error');
    return { ok: false, saved: false };
  }
}

/**
 * 파일의 line 번째 줄이 before 그대로이면 after 로 바꿔 저장한다 — 원문을 새로 받아서 (저장하는 사이에 바뀌면 한 번 더).
 * {hash} — 그 줄이 before 가 아니면 null
 */
async function writeLine(tab, path, line, before, after) {
  for (let attempt = 0; ; attempt++) {
    const src = await getJSON(`/api/source?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}`);
    const lines = src.text.split('\n');
    if (lines[line - 1] !== before) return null;
    lines[line - 1] = after;
    try {
      return await postJSON('/api/save', { p: tab.id, path, text: lines.join('\n'), hash: src.hash });
    } catch (e) {
      if (e.status !== 409 || attempt) throw e;   // 받은 뒤 저장하기 전에 바뀌었다 — 다시 받아 본다
    }
  }
}

/** 칸 밖을 누르면: 고친 것이 있으면 저장, 없으면 그만둔다 (그 블록 — 표면 그 행 — 안은 그대로) */
function onOutside(e) {
  if (!session || session.el.contains(e.target)) return;
  finish(true);
}

// ---- 칸 안의 키 ---------------------------------------------------------------------

/** 칸 안의 글 커서가 글 끝인지 (고른 글 없이) */
function caretAtEnd(span) {
  const sel = getSelection();
  if (!sel.isCollapsed || !span.contains(sel.focusNode)) return false;
  const r = document.createRange();
  r.selectNodeContents(span);
  r.setStart(sel.focusNode, sel.focusOffset);
  return !r.toString();
}

/** ↑·↓: 저장하고 위·아래 줄을 이어서 편집 (표는 같은 칸 차례). 넘어가는 사이에도 하이라이트의 회색은 걷어 둔다 (lineEditHold) */
async function step(dir) {
  const s = session;
  s.pane.lineEditHold = true;
  try {
    const res = await finish(true);
    if (!res.ok || S.pane !== s.pane) return;
    const units = currentUnits();
    const src = sourceLines();
    const order = units.flatMap((u) => editableLines(u, src));
    let i = order.indexOf(s.line);
    if (i < 0) {   // 그 줄이 없어졌다 — 가장 가까운 줄부터
      const u = indexOfLine(units, s.line);
      i = u < 0 ? -1 : order.indexOf(editableLines(units[u], src)[0]);
    }
    const next = order[i + dir];
    if (next == null) {
      highlightLine(s.line);
      return;
    }
    highlightLine(next);
    await begin(next, { cell: s.kind === 'table' ? s.cell : 0 });
  } finally {
    s.pane.lineEditHold = false;
    showLineEdit();
  }
}

/** Shift+→ (글 끝에서): 저장하고 그 줄의 위치를 맨 앞 터미널에 (spotlight 의 Shift+→ 와 같은 길 — Enter 없이) */
async function sendToClaude() {
  const s = session;
  const res = await finish(true);
  if (res.ok) emit('term-paste', `@${s.path} ${rangeText([s.line, s.line])} `);
}

function onKey(e) {
  e.stopPropagation();   // 칸 안의 키는 칸의 것 — 앱 단축키(main.js)는 쉰다
  if (!session || e.isComposing || e.keyCode === 229) return;   // 한글 조합 중
  const span = e.currentTarget;
  const mod = e.ctrlKey || e.metaKey;
  const k = e.key;
  if ((k === 'Enter' && !mod && !e.altKey) || (mod && !e.altKey && (e.code === 'KeyS' || k.toLowerCase() === 's'))) {
    e.preventDefault();
    finish(true);
  } else if (k === 'Escape') {
    e.preventDefault();
    finish(false);
  } else if ((k === 'ArrowUp' || k === 'ArrowDown') && !mod && !e.altKey && !e.shiftKey) {
    e.preventDefault();
    step(k === 'ArrowUp' ? -1 : 1);
  } else if (k === 'ArrowRight' && e.shiftKey && !mod && !e.altKey && caretAtEnd(span)) {
    e.preventDefault();
    sendToClaude();
  } else if (k === 'Tab' && !mod && !e.altKey) {
    e.preventDefault();
    if (session.kind === 'table') focusPlace(Math.max(0, Math.min(session.places.length - 1, Number(span.dataset.i) + (e.shiftKey ? -1 : 1))), false);
    else if (session.kind === 'code' && !e.shiftKey) document.execCommand('insertText', false, '\t');
  }
}

function bind(span) {
  span.addEventListener('keydown', onKey);
  // 줄바꿈은 넣지 않는다 — 붙여 넣은 글의 줄바꿈은 공백으로
  span.addEventListener('beforeinput', (e) => {
    if (e.inputType === 'insertParagraph' || e.inputType === 'insertLineBreak') e.preventDefault();
    else if (e.inputType === 'insertFromPaste' || e.inputType === 'insertFromDrop') {
      const text = e.dataTransfer?.getData('text/plain');
      if (text != null && /[\r\n]/.test(text)) {
        e.preventDefault();
        document.execCommand('insertText', false, text.replace(/\r\n?|\n/g, ' '));
      }
    }
  });
  // 칸 안을 누르는 것은 제목 접기·링크·현재 위치로 가지 않는다
  for (const type of ['mousedown', 'click', 'dblclick', 'contextmenu']) span.addEventListener(type, (e) => e.stopPropagation());
  span.addEventListener('focus', () => {
    if (session) session.cell = Number(span.dataset.i);
  });
}

// ---- 되돌리기 ---------------------------------------------------------------------

/**
 * Ctrl+Z (main.js — 문서 칸에서, 한 줄 편집 중이 아닐 때): 지금 문서에서 한 줄 편집으로 저장한 마지막 줄을 고치기 전으로.
 * 되돌릴 것이 있으면 true (부른 쪽이 기본 동작을 막는다) — 저장은 그 뒤에
 */
export function undoLineEdit() {
  const view = $('#lec-view');
  const path = view.dataset.docPath || view.dataset.codePath;
  const last = undos.at(-1);
  if (session || !last || !S.tab || last.tabId !== S.tab.id || last.path !== path) return false;
  undo(S.pane, last);
  return true;
}

async function undo(pane, last) {
  try {
    const src = await getJSON(`/api/source?p=${encodeURIComponent(pane.tab.id)}&path=${encodeURIComponent(last.path)}`);
    if (src.hash !== last.hash) {   // 그 뒤에 파일이 또 바뀌었다 (Claude Code·편집 모드 등) — 이 파일의 되돌리기는 버린다
      for (let i = undos.length - 1; i >= 0; i--) if (undos[i].path === last.path && undos[i].tabId === last.tabId) undos.splice(i, 1);
      toast(t('그사이 파일이 바뀌어 되돌리지 않았습니다'));
      return;
    }
    const lines = src.text.split('\n');
    lines[last.line - 1] = last.before;
    await postJSON('/api/save', { p: pane.tab.id, path: last.path, text: lines.join('\n'), hash: src.hash });
    undos.splice(undos.indexOf(last), 1);
    await refreshView(pane);
    if (S.pane === pane) highlightLine(last.line);
    toast(t('되돌렸습니다: {where}', { where: `${last.path} ${rangeText([last.line, last.line])}` }));
  } catch (e) {
    toast(t('되돌리지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

export function initLineEdit() {
  on('line-edit', (unit) => begin(lineOf(unit)));
  on('pane', () => {   // 다른 탭을 고르면 고친 것은 저장하고 끝낸다
    if (session && session.pane !== S.pane) finish(true);
  });
}
