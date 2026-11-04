// 한 줄 편집 (D76): 현재 줄·한 줄 하이라이트에서 F2, 한 줄 하이라이트에서 Shift+Enter(spotlight.js 가 'line-edit' 을 보낸다), 본문 두 번 누르기(누른 자리에 커서)
// — 그 줄을 화면의 그 자리에서 고친다. F2·두 번 누르기는 하이라이트를 만들지 않는다 (끝낸 뒤 회색이 남지 않게).
//
// - 그 줄이 보이는 자리(lineunits.js 의 lineSlot — 블록의 글, 나눠 쓴 문단의 그 줄, 코드 블록·코드 화면의 그 줄, 표의 칸)의 내용을 떼어 두고
//   글 칸(contenteditable="plaintext-only" 인 .lec-line-edit)을 넣는다. 칸은 그 블록 안이라 제목 크기·글머리표·박스 색·코드 글꼴이 그대로다.
//   칸에는 원문의 그 줄에서 앞뒤 표시를 뗀 글이 들어간다 — 문장 속 서식은 `**굵게**`·`[링크](주소)` 처럼 글자로 (WYSIWYG 는 하지 않는다).
//   잠그는 것: 인용 >·들여쓰기·목록 표시(- * + 1. 1))·할 일 [ ]·제목 #·박스글 [!NOTE]·각주 [^1]:, 제목 끝의 #, 줄 끝의 공백·\(줄바꿈 표시),
//   코드 블록이 인용·목록 안이면 그 앞부분. 표의 행은 칸마다 (| 는 잠금, Tab·Shift+Tab 으로 옆 칸, 칸 글의 | 는 \| 로 저장).
// - Enter(·Ctrl+S): 저장. 원문을 새로 받아 그 줄이 시작할 때와 같으면 그 줄만 바꿔 /api/save — 편집 모드(D54)와 같은 길이라 줄바꿈·BOM·
//   읽기 전용·프로그램 폴더(D71)를 서버가 지킨다. 줄 번호만 밀렸으면 근처에서 같은 줄을 찾아 하나뿐일 때 그 자리에 (linefind.js).
//   그 줄 자체가 바뀌었거나 어느 것인지 모르면 저장하지 않고 고친 줄을 클립보드에.
//   저장하면 그 칸을 바로 다시 그린다 (바뀐 곳 강조). Esc: 그만두기. 칸 밖을 누르거나 다른 탭을 고르면 고친 것이 있으면 저장, 없으면 그만둔다.
//   ↑·↓: 글이 화면에서 여러 줄로 꺾이면 칸 안에서 움직이고, 맨 윗줄·맨 아랫줄에서는 저장하고 위·아래 줄을 이어서 (표는 같은 칸 차례).
//   Shift+→(글 끝에서): 저장하고 그 줄의 위치를 맨 앞 터미널에 (Claude 로 보내기).
//   한글 조합 중의 Enter·화살표는 조합의 것이다 (isComposing).
// - 본문의 할 일 체크박스를 누르면 원문의 [ ] ↔ [x] 를 바꿔 저장한다 (같은 저장 길, 같은 되돌리기).
// - 저장은 replaceLines 하나로 — 범위(시작 줄, 원래 줄들, 새 줄들)를 바꾼다. 줄 추가·옮기기처럼 여러 줄을 바꾸는 편집도 이 길로.
// - 저장한 뒤 Ctrl+Z·Ctrl+Y(main.js — 문서 칸에서): 파일마다 기록을 따라 되돌리고 다시 한다 — 파일이 마지막 저장 그대로일 때만 (hash).
//   그사이 파일이 바뀌었으면 그 파일의 기록을 버린다 (Claude Code 가 고친 것을 덮어쓰지 않게). 빠르게 눌러도 차례로 (turn).
// - 편집하는 동안 그 칸은 자동 새로고침·F5 로 다시 그리지 않는다 (nav.refreshView 가 pane.lineEdit 을 본다 — 끝낸 뒤 그린다).
//   글 칸 안의 키는 칸의 것이다 (앱 단축키는 쉰다), 누르기는 제목 접기·링크로 가지 않는다.

import { S, on, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { lineSlot, editableLines } from './lineunits.js';
import { locateLines } from './linefind.js';
import {
  currentUnits, sourceLines, followLine, unitAtPoint, showLineEdit,
} from './spotlight.js';
import { refreshView } from './nav.js';
import { $, toast, copyText, rangeText, blockedReadOnly } from './util.js';
import { t } from './i18n.js';

let session = null;   // 편집 중 {pane, tab, path, line, kind, original, parts, places:[{span, frag}], cell, el}
// 되돌리기 기록 — 파일마다 ('탭 id|경로' → {done, undone}). done 은 저장한 변경(마지막 것이 끝), undone 은 되돌린 변경.
// 변경 {line, before: [줄], after: [줄], hash(적용한 뒤의 파일), prior(되돌린 뒤의 파일)}
const records = new Map();
const MAX_UNDO = 50;
let turn = Promise.resolve();   // 되돌리기·다시 하기는 차례로 — 앞의 것이 저장을 마치기 전에 다음 것이 파일을 보면 '바뀌었다'고 잘못 안다
let opening = 0;     // 두 번 누른 뒤 칸을 열 때까지의 타이머 — 세 번째 누르기(문단 고르기)면 열지 않는다
let taskSaving = false;

const OPEN_WAIT = 250;
// 두 번 눌러도 열지 않는 곳: 링크·그림·다이어그램·차트·수식, 머리 정보, 코드 블록의 도구
const NO_OPEN = 'a, img, svg, input, button, select, textarea, summary, video, .math-block, .katex, pre.mermaid, pre.lec-chart, .diagram-error, .image-off, .front-matter, .code-tools, .lec-line-edit';
const TASK_BOX = '.task-list-item-checkbox';
// 할 일 줄의 [ ] — 앞의 인용 >·목록 표시(겹친 것도) 뒤
const TASK_LINE = /^((?:[ \t]*>[ \t]?|[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+)*\[)([ xX])\]/;

export const lineEditing = () => !!session;

/** 칸의 화면이 그려져 있는지 — 그리는 중에 글 칸을 넣으면 그리기가 끝날 때 화면째 바뀌어 칸이 사라진다 (친 글도 함께) */
const drawn = (pane) => !pane.pending && !pane.redrawing;
const nap = () => new Promise((r) => setTimeout(r, 50));

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

/** 화면 글 shown 의 끝이 원문 글 body 의 어디인지 — 서식 표시(**·[]() 등)는 건너뛰며 글자를 차례로 맞춘다 */
function sourceOffset(shown, body) {
  let at = 0;
  for (const ch of shown.trimStart()) {
    const i = body.indexOf(ch, at);
    if (i >= 0) at = i + ch.length;
  }
  return at;
}

/** 화면 자리 at(Range)이 든 칸의 차례와 그 칸의 글에서의 자리 {cell, offset} — 칸 밖이면 null */
function caretIn(ranges, bodies, at) {
  const i = ranges.findIndex((r) => r.isPointInRange(at.startContainer, at.startOffset));
  if (i < 0) return null;
  const shown = ranges[i].cloneRange();
  shown.setEnd(at.startContainer, at.startOffset);
  return { cell: i, offset: sourceOffset(shown.toString(), bodies[i]) };
}

/** 원문 줄 line 을 편집한다. cell: 표면 처음 고를 칸 차례, at: 커서를 둘 화면 좌표 {x, y} (두 번 누른 곳) */
async function begin(line, { cell = 0, at = null } = {}) {
  const pane = S.pane;
  if (!pane?.tab || session || pane.editor) return;
  if (blockedReadOnly(pane.tab)) return;   // Lectern 프로그램 폴더 안 (D71)
  // 다시 그리는 중(앞 줄을 저장한 뒤, 자동 새로고침 등)이면 다 그린 뒤에 — 지금 보이는 것은 곧 바뀔 화면이다
  for (let waited = 0; !drawn(pane) && waited < 5000; waited += 50) await nap();
  if (S.pane !== pane || session) return;
  if (!drawn(pane)) {
    toast(t('화면을 그리는 중입니다 — 다 그린 뒤 F2 를 누르세요'));
    return;
  }
  const view = $('#lec-view');
  const path = view.dataset.docPath || view.dataset.codePath;
  if (view.dataset.sheet != null && view.classList.contains('code-view') && view.dataset.codePath && /\.xls[xm]$/i.test(path)) {
    toast(t('엑셀 보기는 보기만 합니다 — 고치려면 엑셀로 여세요'));   // D77
    return;
  }
  if (!line || !path || !lineSlot(view, line, sourceLines())) {
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
  // 받는 사이에 시작한 다시 그리기가 있으면 끝날 때까지. 여기부터 칸을 넣고 pane.lineEdit 을 달 때까지는 멈추지 않는다 — 그 뒤의 다시 그리기는 refreshView 가 미룬다
  for (let waited = 0; !drawn(pane) && waited < 5000; waited += 50) await nap();
  if (S.pane !== pane || $('#lec-view') !== view || session) return;   // 그사이 다른 화면
  if (!drawn(pane)) {
    toast(t('화면을 그리는 중입니다 — 다 그린 뒤 F2 를 누르세요'));
    return;
  }
  // 자리는 받은 뒤에 찾는다 — 받는 사이에 자동 새로고침이 화면을 바꿨어도 지금 화면의 것으로
  const shown = sourceLines();
  const slot = lineSlot(view, line, shown);
  if (!slot) return;
  const original = src.text.split('\n')[line - 1];
  if (original == null || original !== shown[line - 1]) {   // 화면이 원문보다 늦다 (자동 새로고침 전)
    toast(t('화면이 원문과 달라 다시 그렸습니다 — F2 를 누르면 다시 시작합니다'));
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
  const point = at && document.caretRangeFromPoint?.(at.x, at.y);
  const caret = point ? caretIn(slot.ranges.slice(0, n), bodies, point) : null;   // 칸을 넣기 전에 — 넣으면 그 자리가 없어진다
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
  session = { pane, tab, path, line, kind: slot.kind, original, parts, places, el: slot.el, cell: Math.min(caret?.cell ?? cell, n - 1) };
  pane.lineEdit = session;
  for (const p of places) bind(p.span);
  document.addEventListener('mousedown', onOutside, true);
  focusPlace(session.cell);
  const text = caret && places[caret.cell].span.firstChild;
  if (text) getSelection().collapse(text, caret.offset);
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
    s.pane.lineEditMissed = false;
    const r = await replaceLines(s.pane, s.path, s.line, [s.original], [next]);
    if (!r) {   // 그사이 다른 곳에서 그 줄이 바뀌었다
      restore(s);
      await copyText(next);
      toast(t('다른 곳에서 이 줄이 바뀌어 저장하지 않았습니다 — 고친 줄은 클립보드에 복사했습니다'), 'error');
      refreshView(s.pane);
      return { ok: false, saved: false };
    }
    s.line = r.at;   // 위쪽이 바뀌어 줄이 밀렸으면 새 자리
    toast(t('저장했습니다: {where} — Ctrl+Z 로 되돌립니다', { where: `${s.path} ${rangeText([s.line, s.line])}` }));
    return { ok: true, saved: true };
  } catch (e) {
    restore(s);
    toast(t('저장하지 못했습니다: {error}', { error: e.message }), 'error');
    return { ok: false, saved: false };
  }
}

/**
 * 파일의 start 번째 줄부터 before(줄 배열)를 after(줄 배열)로 바꿔 저장한다 — 원문을 새로 받아서 (저장하는 사이에 바뀌면 한 번 더).
 * 줄 번호가 밀렸으면 근처에서 같은 줄들을 찾아 하나뿐일 때만 그 자리에 (linefind.js). {hash, at(쓴 자리)} — 자리를 찾지 못하면 null
 */
async function writeLines(tab, path, start, before, after) {
  for (let attempt = 0; ; attempt++) {
    const src = await getJSON(`/api/source?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}`);
    const lines = src.text.split('\n');
    const at = locateLines(lines, start, before);
    if (!at) return null;
    lines.splice(at - 1, before.length, ...after);
    try {
      return { ...await postJSON('/api/save', { p: tab.id, path, text: lines.join('\n'), hash: src.hash }), at };
    } catch (e) {
      if (e.status !== 409 || attempt) throw e;   // 받은 뒤 저장하기 전에 바뀌었다 — 다시 받아 본다
    }
  }
}

/**
 * 원문 줄 범위를 바꿔 저장하고 되돌리기 기록에 쌓고 칸을 다시 그린다 — 편집이 파일을 고치는 길은 이것 하나다.
 * before 는 한 줄 이상 (넣기는 앞 줄을 before·after 양쪽에). {hash, at} — 자리를 찾지 못해 저장하지 않았으면 null. 보기만 하는 프로젝트(D71)는 부르는 쪽이 막는다
 */
export async function replaceLines(pane, path, start, before, after) {
  const { tab } = pane;
  const r = await writeLines(tab, path, start, before, after);
  if (!r) return null;
  const rec = recordOf(tab.id, path);
  rec.done.push({ line: r.at, before, after, hash: r.hash });
  if (rec.done.length > MAX_UNDO) rec.done.shift();
  rec.undone.length = 0;   // 새로 고치면 되돌린 것을 다시 할 수 없다
  await refreshView(pane);
  return r;
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

/**
 * 커서가 칸의 글에서 화면상 맨 윗줄(dir < 0)·맨 아랫줄(dir > 0)인지. 칸(.whole)은 block 이라 상자가 하나뿐이므로 글의 줄 상자로 잰다.
 * Selection.modify 로는 알 수 없다 — 맨 윗줄에서도 글 맨 앞으로 움직인다
 */
function caretOnEdge(span, dir) {
  const sel = getSelection();
  if (!sel.rangeCount || !span.contains(sel.focusNode)) return true;
  const caret = sel.getRangeAt(0).cloneRange();
  caret.collapse(dir < 0);
  const text = span.firstChild;
  if (caret.startContainer === span && text) {   // 칸을 막 열면 자리가 글이 아니라 칸을 가리킨다 — 그 자리엔 상자가 없다
    caret.setStart(text, caret.startOffset ? text.length : 0);
    caret.collapse(true);
  }
  const box = caret.getClientRects()[0];
  const all = document.createRange();
  all.selectNodeContents(span);
  const lines = [...all.getClientRects()].filter((r) => r.height);
  if (!box || !lines.length) return true;   // 빈 칸
  const mid = (box.top + box.bottom) / 2;
  return dir < 0 ? mid < Math.min(...lines.map((r) => r.bottom)) : mid > Math.max(...lines.map((r) => r.top));
}

/** ↑·↓: 저장하고 위·아래 줄을 이어서 편집 (표는 같은 칸 차례). 넘어가는 사이에도 하이라이트의 회색은 걷어 둔다 (lineEditHold) */
async function step(dir) {
  const s = session;
  s.pane.lineEditHold = true;
  try {
    const res = await finish(true);
    if (!res.ok || S.pane !== s.pane) return;
    const src = sourceLines();
    const order = currentUnits().flatMap((u) => editableLines(u, src));
    const i = order.indexOf(s.line);
    // 고칠 수 없는 줄이 됐으면(글을 지운 목록 항목 등) 그 줄의 다음·앞 줄로 — 저장은 줄 수를 바꾸지 않는다
    const next = i >= 0 ? order[i + dir] : dir > 0 ? order.find((n) => n > s.line) : order.findLast((n) => n < s.line);
    if (next == null) {
      followLine(s.line);
      return;
    }
    followLine(next);
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
  if (e.key === 'F6') {   // 터미널로 — main.js 가 받는다. 칸은 그대로 두고, 돌아오면 이 자리로 (D79)
    const sel = getSelection();
    if (session) session.caret = [sel.focusNode, sel.focusOffset];
    return;
  }
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
    const dir = k === 'ArrowUp' ? -1 : 1;
    if (!caretOnEdge(span, dir)) return;   // 꺾인 글의 안쪽 줄: 칸 안에서 위·아래로 (기본 동작)
    e.preventDefault();
    step(dir);
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

/** F6 으로 돌아올 때 (main.js, D79): 칸의 그 자리로. 한 줄 편집 중이 아니면 false */
export function focusLineEdit() {
  if (!session) return false;
  session.places[session.cell]?.span.focus();
  if (session.caret) getSelection().collapse(...session.caret);
  return true;
}

// ---- 두 번 누르기 -------------------------------------------------------------------

/** 두 번 누른 곳의 줄을 그 자리 커서로 연다. 고칠 수 없는 곳이면 낱말 고르기 그대로 (알리지 않는다 — 읽다가 누른 것이다) */
function onDoubleClick(e) {
  const pane = S.pane;
  if (e.button !== 0 || e.ctrlKey || e.shiftKey || e.altKey || e.metaKey || session || !pane?.tab || pane.tab.readonly || pane.editor) return;
  if (e.target.closest(NO_OPEN)) return;
  const unit = unitAtPoint(e);
  if (!unit) return;
  const view = $('#lec-view');
  const src = sourceLines();
  const at = document.caretRangeFromPoint?.(e.clientX, e.clientY);
  // 한 화면 줄에 이어진 짧은 줄들은 한 단위다 — 누른 글자가 든 원문 줄로
  const hit = at && editableLines(unit, src).find((n) => lineSlot(view, n, src)?.ranges.some((r) => r.isPointInRange(at.startContainer, at.startOffset)));
  const line = hit ?? lineOf(unit);
  if (!line || !lineSlot(view, line, src)) return;
  opening = setTimeout(() => begin(line, { at: { x: e.clientX, y: e.clientY } }), OPEN_WAIT);
}

// ---- 할 일 체크박스 ----------------------------------------------------------------

/** 본문의 체크박스를 누르면: 원문의 [ ] ↔ [x] 를 바꿔 저장하고 다시 그린다 (화면은 그때 바뀐다) */
async function onTaskClick(e) {
  if (!e.target.matches?.(TASK_BOX)) return;
  e.preventDefault();
  const pane = S.panes.find((p) => p.view.contains(e.target));
  if (!pane?.tab || e.detail > 1 || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey || session || taskSaving) return;
  if (blockedReadOnly(pane.tab)) return;   // Lectern 프로그램 폴더 안 (D71)
  const line = Number(/^\d+/.exec(e.target.closest('li')?.dataset.lines || '')?.[0]);
  const before = pane.source?.lines[line - 1];
  const m = before == null ? null : TASK_LINE.exec(before);
  if (!m) {
    toast(t('이 할 일은 눌러서 바꿀 수 없습니다 — 편집 모드(Ctrl+E)에서 고칩니다'));
    return;
  }
  const path = pane.view.dataset.docPath;
  const after = `${m[1]}${m[2] === ' ' ? 'x' : ' '}${before.slice(m[1].length + 1)}`;
  taskSaving = true;
  try {
    const r = await replaceLines(pane, path, line, [before], [after]);
    if (!r) {
      toast(t('다른 곳에서 이 줄이 바뀌어 저장하지 않았습니다 — 화면을 다시 그렸습니다'), 'error');
      refreshView(pane);
      return;
    }
    toast(t('저장했습니다: {where} — Ctrl+Z 로 되돌립니다', { where: `${path} ${rangeText([r.at, r.at])}` }));
  } catch (err) {
    toast(t('저장하지 못했습니다: {error}', { error: err.message }), 'error');
  } finally {
    taskSaving = false;
  }
}

// ---- 되돌리기 ---------------------------------------------------------------------

/** 파일의 기록 (없으면 만든다) */
function recordOf(tabId, path) {
  const key = `${tabId}|${path}`;
  if (!records.has(key)) records.set(key, { done: [], undone: [] });
  return records.get(key);
}

/** 기록의 다음 변경을 되돌리거나(undoing) 다시 한다 — 파일이 그 변경의 앞뒤 상태 그대로일 때만 */
async function replay(pane, path, rec, undoing) {
  const [from, to] = undoing ? [rec.done, rec.undone] : [rec.undone, rec.done];
  const change = from.at(-1);
  if (!change) return;
  try {
    const src = await getJSON(`/api/source?p=${encodeURIComponent(pane.tab.id)}&path=${encodeURIComponent(path)}`);
    if (src.hash !== (undoing ? change.hash : change.prior)) {   // 그 뒤에 파일이 또 바뀌었다 (Claude Code·편집 모드 등) — 이 파일의 기록은 버린다
      rec.done.length = 0;
      rec.undone.length = 0;
      toast(undoing ? t('그사이 파일이 바뀌어 되돌리지 않았습니다') : t('그사이 파일이 바뀌어 다시 하지 않았습니다'));
      return;
    }
    const [gone, back] = undoing ? [change.after, change.before] : [change.before, change.after];
    const lines = src.text.split('\n');
    lines.splice(change.line - 1, gone.length, ...back);
    const saved = await postJSON('/api/save', { p: pane.tab.id, path, text: lines.join('\n'), hash: src.hash });
    if (undoing) change.prior = saved.hash;
    else change.hash = saved.hash;
    to.push(from.pop());
    await refreshView(pane);
    if (S.pane === pane) followLine(change.line);
    const where = `${path} ${rangeText([change.line, change.line + Math.max(back.length, 1) - 1])}`;
    toast(undoing ? t('되돌렸습니다: {where}', { where }) : t('다시 했습니다: {where}', { where }));
  } catch (e) {
    toast(undoing ? t('되돌리지 못했습니다: {error}', { error: e.message }) : t('다시 하지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

/** 지금 화면의 파일 기록에서 한 걸음. 할 것이 있으면 true (부른 쪽이 기본 동작을 막는다) — 저장은 차례가 오면 */
function walk(undoing) {
  const view = $('#lec-view');
  const path = view.dataset.docPath || view.dataset.codePath;
  const rec = S.tab && path ? records.get(`${S.tab.id}|${path}`) : null;
  if (session || !(undoing ? rec?.done : rec?.undone)?.length) return false;
  const pane = S.pane;
  turn = turn.then(() => replay(pane, path, rec, undoing));
  return true;
}

/** Ctrl+Z (main.js — 문서 칸에서, 한 줄 편집 중이 아닐 때): 지금 문서에서 저장한 마지막 변경을 고치기 전으로 */
export const undoLineEdit = () => walk(true);
/** Ctrl+Y: 되돌린 변경을 다시 */
export const redoLineEdit = () => walk(false);

export function initLineEdit() {
  on('line-edit', (unit) => begin(lineOf(unit)));
  on('pane', () => {   // 다른 탭을 고르면 고친 것은 저장하고 끝낸다
    if (session && session.pane !== S.pane) finish(true);
  });
  const panes = $('#lec-panes');
  panes.addEventListener('dblclick', onDoubleClick);   // fold.js 뒤에 — 첫 누르기의 접기를 되돌린 다음
  panes.addEventListener('click', onTaskClick);
  panes.addEventListener('mousedown', (e) => {
    clearTimeout(opening);   // 세 번째 누르기 — 문단 고르기 그대로
    if (e.target.matches?.(TASK_BOX)) e.preventDefault();   // 초점은 문서 칸에 — 이어서 치는 ↑·↓·F2 가 그대로 되게
  }, true);
}
