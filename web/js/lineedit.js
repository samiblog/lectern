// 한 줄 편집 (D76): 현재 줄·한 줄 하이라이트에서 F2(spotlight.js 가 'line-edit' 을 보낸다), 본문 두 번 누르기(누른 자리에 커서)
// — 그 줄을 화면의 그 자리에서 고친다. F2·두 번 누르기는 하이라이트를 만들지 않는다 (끝낸 뒤 회색이 남지 않게).
//
// - 그 줄이 보이는 자리(lineunits.js 의 lineSlot — 블록의 글, 나눠 쓴 문단의 그 줄, 코드 블록·코드 화면의 그 줄, 표의 칸)의 내용을 떼어 두고
//   글 칸(contenteditable="plaintext-only" 인 .lec-line-edit)을 넣는다. 칸은 그 블록 안이라 제목 크기·글머리표·박스 색·코드 글꼴이 그대로다.
//   칸에는 원문의 그 줄에서 앞뒤 표시를 뗀 글이 들어간다 — 문장 속 서식은 `**굵게**`·`[링크](주소)` 처럼 글자로 (WYSIWYG 는 하지 않는다).
//   잠그는 것: 인용 >·들여쓰기·목록 표시(- * + 1. 1))·할 일 [ ]·제목 #·강조글 [!NOTE]·각주 [^1]:, 제목 끝의 #, 줄 끝의 공백·\(줄바꿈 표시),
//   코드 블록이 인용·목록 안이면 그 앞부분. 표의 행은 칸마다 (| 는 잠금, Tab·Shift+Tab 으로 옆 칸, 칸 글의 | 는 \| 로 저장).
// - Enter(·Ctrl+S): 저장. 원문을 새로 받아 그 줄이 시작할 때와 같으면 그 줄만 바꿔 /api/save — 편집 모드(D54)와 같은 길이라 줄바꿈·BOM·
//   읽기 전용·프로그램 폴더(D71)를 서버가 지킨다. 줄 번호만 밀렸으면 근처에서 같은 줄을 찾아 하나뿐일 때 그 자리에 (linefind.js).
//   그 줄 자체가 바뀌었거나 어느 것인지 모르면 저장하지 않고 고친 줄을 클립보드에.
//   저장하면 그 칸을 바로 다시 그린다 (바뀐 곳 강조). Esc: 그만두기. 칸 밖을 누르거나 다른 탭을 고르면 고친 것이 있으면 저장, 없으면 그만둔다.
//   ↑·↓: 글이 화면에서 여러 줄로 꺾이면 칸 안에서 움직이고, 맨 윗줄·맨 아랫줄에서는 저장하고 위·아래 줄을 이어서 (표는 같은 칸 차례).
//   한글 조합 중의 Enter·화살표는 조합의 것이다 (isComposing).
// - 본문의 할 일 체크박스를 누르면 원문의 [ ] ↔ [x] 를 바꿔 저장한다 (같은 저장 길, 같은 되돌리기).
// - 저장은 replaceLines 하나로 — 범위(시작 줄, 원래 줄들, 새 줄들)를 바꾼다. 줄 추가·옮기기처럼 여러 줄을 바꾸는 편집도 이 길로.
// - 줄 구조 (D83 — 계산은 lineops.js): Shift+Enter·Ctrl+Shift+Enter 로 아래·위에 새 줄 (글 가운데서 Shift+Enter 면 그 자리에서 나눔 — D164, 칸의 Ctrl+Enter 는 저장하고 그 줄 선택), 줄 맨 앞의 Backspace 로 윗줄과 합침,
//   목록의 Tab·Shift+Tab 으로 레벨 이동, Alt+↑·↓ 로 옮기기, Ctrl+Shift+K 지우기, Ctrl+Shift+D 복제. 하이라이트한 줄도 Alt+↑·↓ (moveLit)·Delete·Ctrl+X (deleteLit).
//   새 줄은 글을 쓸 때까지 화면에만 있다 (session.fresh — 그 자리에 빈 <li>·<p>·코드 줄을 넣고, 글 없이 끝내면 걷는다 — 파일은 그대로다).
//   이미 고친 글은 먼저 저장하고 구조를 바꾼다 (되돌리기는 두 걸음). 되지 않는 것은 칸을 그대로 두고 알린다.
// - 저장한 뒤 Ctrl+Z·Ctrl+Y(main.js — 문서 칸에서): 파일마다 기록을 따라 되돌리고 다시 한다 — 파일이 마지막 저장 그대로일 때만 (hash).
//   그사이 파일이 바뀌었으면 그 파일의 기록을 버린다 (Claude Code 가 고친 것을 덮어쓰지 않게). 빠르게 눌러도 차례로 (turn).
// - 편집하는 동안 그 칸은 자동 새로고침·F5 로 다시 그리지 않는다 (nav.refreshView 가 pane.lineEdit 을 본다 — 끝낸 뒤 그린다).
//   글 칸 안의 키는 칸의 것이다 (앱 단축키는 쉰다), 누르기는 제목 접기·링크로 가지 않는다.

import { S, on, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { lineSlot, editableLines, blockOfLine } from './lineunits.js';
import { locateLines } from './linefind.js';
import { isCode, isDataEditable } from './icons.js';
import {
  diffRange, planNew, planEnd, planBefore, shiftPlan, paraAt, quoteOf, insertLine, splitLine, joinLine, duplicateLine, moveLines, deleteLines,
  blocksOf, blockAt, itemOf, fencesOf, fenceAt, tableIn, renumberAt, relist, listNear, siblingsOf, isBlank,
} from './lineops.js';
import {
  TEXT_WORDS, TEXT_WORDS_EN, setTextSize, setCellSize, duplicateSlide, moveSlide, deleteSlide, setLayout, templateLines, addTemplate, applyTemplate, setFrontKey,
  cellAt, setCellLook, swapCell, clearCell, splitCell, noteOf, setNote as setSlideNote, setImageWidth, imageWidth,
} from './slideops.js';
import { applyScheme, numberScheme, markLength, bareHeading, sameHeads } from './headstyle.js';
import {
  setKind, shiftLevels, kindOfLine, moveSection, moveSectionTo, deleteSection, headLevel, insertBlock, blockEnd, nextCaption, makeTable, tableFromRows, rowsFromTsv, addRow, addColumn, removeColumn,
  toggledKind, boldLines, formatLines, clearMarksIn, cycleBox, moveColumn, alignColumn, tableAt, tableSpan, boxAt, setBox, unwrapBox, wrapBox, textboxAt, textboxSpan, textboxTitle, makeTextbox, wrapTextbox, unwrapTextbox, boxToTextbox, textboxToBox, addNote, noteAt, noteText, setNote, droppedNotes, removeNotes, addAttachment, nextAppendix, pasteAfter,
} from './docops.js';
import { listToTable, tableToList, wrapCode, unwrapCode } from './docops.js';
import { pick, askText, putItems, changeItems, projectFiles } from './putmenu.js';
import { pickDate } from './datepick.js';
import { pickChar } from './charpick.js';
import { renumberCaptions, refTargets, referencesIn, citeOf, citedCount, tocLine, captionAt, PAGE_BREAK, lostHeadLinks } from './refs.js';
import { ATOMIC, openBlock, openFront, initLineBlock } from './lineblock.js';
import { writeValues, setChartKind, chartFromTable, inlineUrlData } from './chartops.js';
import { slugify } from './markdown.js';
import { slideAtTop } from './slides.js';
import { markOf, markText, RANKS } from './marklist.js';
import {
  currentUnits, sourceLines, followLine, showLineEdit, litSpan, setLitSpan, stopSpotlight, copyLitSource, hereAtNew, docKeyTarget, releasePick,
  kindKey, stepHere, litOneLine, manyBlocks, lightOn, pickedMany, lightHere, nextHere,
} from './spotlight.js';
import { refreshView } from './nav.js';
import { $, toast, copyText, rangeText, lineRef, blockedReadOnly, isMd } from './util.js';
import { t, LANG } from './i18n.js';
import { aiName, rewritePrompt } from './aitool.js';
import { applyFormat, clearFormats, paintOf, sourceRange } from './inlinefmt.js';
import { showMenu } from './ui.js';
import { labelOf } from './tree.js';

const FMT_PAINT = ['marks', 'bold', 'italic', 'strike', 'code', 'mark', 'mark-green', 'mark-pink', 'mark-blue', 'color-red', 'color-blue', 'color-green', 'color-goldenrod'];
let paintRaf = 0;
let session = null;   // 편집 중 {pane, tab, path, line, kind, original, parts, places:[{span, frag}], cell, el, fence, fresh?:{plan, lines, remove}}
// 되돌리기 기록 — 파일마다 ('탭 id|경로' → {done, undone}). done 은 저장한 변경(마지막 것이 끝), undone 은 되돌린 변경.
// 변경 {line, before: [줄], after: [줄], hash(적용한 뒤의 파일), prior(되돌린 뒤의 파일)}
const records = new Map();
const MAX_UNDO = 50;
let turn = Promise.resolve();   // 되돌리기·다시 하기는 차례로 — 앞의 것이 저장을 마치기 전에 다음 것이 파일을 보면 '바뀌었다'고 잘못 안다
const saving = new Set();   // 기록에 쌓이기 전인 저장 — 되돌리기는 이것들을 기다린다 (칸의 Enter 바로 뒤 Ctrl+Z 가 기록을 버리지 않게)
let taskSaving = false;
let moves = 0;       // 차례를 기다리는 줄 옮기기 — 키를 누르고 있으면 쌓이지 않게

const TASK_BOX = '.task-list-item-checkbox';
// 할 일 줄의 [ ] — 앞의 인용 >·목록 표시(겹친 것도) 뒤
const TASK_LINE = /^((?:[ \t]*>[ \t]?|[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+)*\[)([ xX])\]/;

export const lineEditing = () => !!session;

/** 칸의 화면이 그려져 있는지 — 그리는 중에 글 칸을 넣으면 그리기가 끝날 때 화면째 바뀌어 칸이 사라진다 (친 글도 함께) */
const drawn = (pane) => !pane.pending && !pane.redrawing;
const nap = () => new Promise((r) => setTimeout(r, 50));
const isCodeView = (view) => view.classList.contains('code-view');
const isSheet = (view) => view.dataset.sheet != null && isCodeView(view) && !!view.dataset.codePath && /\.xls[xm]$/i.test(view.dataset.codePath);
const pathIn = (view) => view.dataset.docPath || view.dataset.codePath;
/** UTF-8 이 아닌 글로 읽은 코드 화면 (D85 — Windows 인코딩의 prg, CP949 의 txt 등): 보기만 */
const notUtf8 = (view) => isCodeView(view) && !!view.dataset.encoding;
/** 코드 화면의 자료 파일 (csv·tsv·txt·log — D60): 한 줄 편집·줄 구조는 하지 않는다 — csv·tsv·txt 는 편집 모드로 (D171 — 원래 인코딩 그대로), log 는 보기만 */
const dataFile = (view) => isCodeView(view) && !!view.dataset.codePath && !isCode(view.dataset.codePath) && !isMd(view.dataset.codePath);
const DATA_FILE_NOTE = (view) => (isDataEditable(view.dataset.codePath || '') ? t('자료 파일은 편집 모드(Ctrl+E)에서 고칩니다 — F2·Enter 도 그 줄에서 편집 모드를 엽니다')
  : t('로그 파일은 보기만 합니다 — 프로그램이 덧붙이는 파일이라 고치는 사이에 바뀌기 쉽습니다. 고치려면 외부 편집기로 여세요'));

/** 칸을 다 그릴 때까지 (오래 걸리면 false) */
async function settled(pane) {
  for (let waited = 0; !drawn(pane) && waited < 5000; waited += 50) await nap();
  return drawn(pane);
}

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

/**
 * 글머리 글자 목록(D192)의 줄: '- '·'1. ' 도 화면에 글로 보이므로 칸에 둔다 — 인용 표시와 앞 빈칸만 머리로 (splitText 는 Markdown 목록 표시로 떼어 낸다)
 * @param {string} line
 */
function keepMark(line) {
  const { tail } = splitText(line);
  const head = /^(?:[ \t]*>[ \t]?)*[ \t\u3000]*/.exec(line)[0];   // 전각 빈칸의 들여쓰기도 — 화면에서는 수준이 대신한다
  return { head, body: line.slice(head.length, line.length - tail.length), tail };
}

/** 펼친 머리 설정의 줄: 키를 잠그고 값만 고친다 (D112) */
function lockKey(parts, el) {
  const m = el.closest?.('.lec-unfold-front') && /^([\w-]+:[ \t]*)(.*)$/.exec(parts.body);
  return m ? { ...parts, head: m[1], body: m[2] } : parts;
}

/** 번호가 있는 문서의 제목 줄: 번호도 표시처럼 잠근다 — 번호는 앱이 맞춘다 (D107) */
function lockNumber(parts, lines) {
  if (!headLevel(parts.head + parts.body)) return parts;
  const id = numberScheme(lines);
  const n = id ? markLength(parts.body, id) : 0;
  return n ? { ...parts, head: parts.head + parts.body.slice(0, n), body: parts.body.slice(n) } : parts;
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

/** 칸의 글 */
function read(p) {
  let text = p.span.textContent.replace(/[\r\n]+/g, ' ');
  if (!p.nbsp) text = text.replace(/ /g, ' ');   // 칸이 공백을 nbsp 로 바꾼 것 (원문에 없던 것만)
  return text;
}

/** 고친 글로 새 줄을 만든다 */
function buildLine(s) {
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
/**
 * 떼어 낸 줄 조각 끝의 줄바꿈 <br> (과 그 뒤 빈 글자) — 이어 쓴 줄(설정 md_breaks)은 줄 범위가 원문 줄 자리(\n)로 나뉘어 끝의 <br> 까지 든다.
 * 칸 뒤에 남겨 둘 조각으로 떼어 돌려준다. 그만두면 frag 가 칸 자리로 돌아가 이 <br> 앞에 붙으니 원래 모양 그대로다. 없으면 null
 */
function trailingBreak(frag) {
  let n = frag.lastChild;
  const after = [];
  while (n && n.nodeType === Node.TEXT_NODE && !n.textContent.trim()) {
    after.unshift(n);
    n = n.previousSibling;
  }
  if (n?.nodeName !== 'BR') return null;
  const out = document.createDocumentFragment();
  out.append(n, ...after);
  return out;
}

function caretIn(ranges, bodies, at) {
  const i = ranges.findIndex((r) => r.isPointInRange(at.startContainer, at.startOffset));
  if (i < 0) return null;
  const shown = ranges[i].cloneRange();
  shown.setEnd(at.startContainer, at.startOffset);
  return { cell: i, offset: sourceOffset(shown.toString(), bodies[i]) };
}

/**
 * 원문 줄 line 을 편집한다. cell: 표면 처음 고를 칸 차례, at: 커서를 둘 화면 좌표 {x, y} (두 번 누른 곳), offset: 커서를 둘 글 안의 자리,
 * select: true 면 글 전체를, 숫자면 그 자리부터 끝까지 골라 둔다. range: 칸 cell 의 글에서 고를 자리 [a, b] — 번호를 잠그기 전의 글 기준 (읽는 화면에서 고른 글, D142)
 * @param {number} line @param {{cell?: number, at?: any, offset?: number | null, select?: boolean | number, range?: number[] | null}} [o]
 */
async function begin(line, { cell = 0, at = null, offset = null, select: pick_ = false, range = null } = {}) {
  let select = pick_;
  const pane = S.pane;
  if (!pane?.tab || session || pane.editor) return;
  if (blockedReadOnly(pane.tab)) return;   // Lectern 프로그램 폴더 안 (D71)
  // 다시 그리는 중(앞 줄을 저장한 뒤, 자동 새로고침 등)이면 다 그린 뒤에 — 지금 보이는 것은 곧 바뀔 화면이다
  const ready = await settled(pane);
  if (S.pane !== pane || session) return;
  if (!ready) {
    toast(t('화면을 그리는 중입니다 — 다 그린 뒤 F2 를 누르세요'));
    return;
  }
  const view = $('#lec-view');
  const path = pathIn(view);
  if (isSheet(view)) {
    toast(t('엑셀 보기는 보기만 합니다 — 고치려면 엑셀로 여세요'));   // D77
    return;
  }
  if (dataFile(view)) {   // csv·tsv·txt: 그 줄에서 편집 모드 (D171 — 표의 행은 한 줄 칸으로 고치지 않는다, 인코딩도 그대로)
    if (isDataEditable(path || '')) emit('edit', { line: line || pane.here?.line || 0 });   // 표의 행은 한 줄 편집으로 고칠 줄이 없어 line 이 빈다 — 현재 줄
    else toast(DATA_FILE_NOTE(view));
    return;
  }
  if (notUtf8(view)) {
    toast(t('UTF-8 이 아닌 파일은 편집할 수 없습니다 (Lectern 은 UTF-8 글만 고칩니다)'));
    return;
  }
  if (!line || !path || !lineSlot(view, line, sourceLines())) {
    toast(t('이 줄은 한 줄 편집으로 고칠 수 없습니다 — 그림·다이어그램·수식·HTML 은 편집 모드(Ctrl+E)에서 고칩니다'));
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
  const again = await settled(pane);
  if (S.pane !== pane || $('#lec-view') !== view || session) return;   // 그사이 다른 화면
  if (!again) {
    toast(t('화면을 그리는 중입니다 — 다 그린 뒤 F2 를 누르세요'));
    return;
  }
  // 자리는 받은 뒤에 찾는다 — 받는 사이에 자동 새로고침이 화면을 바꿨어도 지금 화면의 것으로
  const shown = sourceLines();
  const slot = lineSlot(view, line, shown);
  if (!slot) return;
  const original = src.text.split('\n')[line - 1];
  if (samples && select === false && view.classList.contains('lec-deck') && samples.has(original?.trim())) select = true;   // 고치지 않은 안내 글 — 치면 바뀐다 (D116)
  if (original == null || original !== shown[line - 1]) {   // 화면이 원문보다 늦다 (자동 새로고침 전)
    toast(t('화면이 원문과 달라 다시 그렸습니다 — F2 를 누르면 다시 시작합니다'));
    refreshView(pane);
    return;
  }
  const parts = slot.kind === 'table' ? splitRow(original) : slot.kind === 'code' ? lockKey(splitCode(original, slot.fence), slot.el)
    : slot.el.closest?.('.lec-mark') ? keepMark(original) : lockNumber(splitText(original), shown);
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
    const br = trailingBreak(frag);   // 이어 쓴 줄의 끝 <br> 은 칸 뒤에 남긴다 — 함께 빠지면 다음 줄이 칸 옆으로 올라붙었다
    if (br) span.after(br);
    places.push({ span, frag, nbsp: bodies[i].includes(' ') });
  }
  releasePick();
  session = { pane, tab, path, line, kind: slot.kind, original, parts, places, el: slot.el, cell: Math.min(caret?.cell ?? cell, n - 1), fence: slot.fence || '' };
  pane.lineEdit = session;
  for (const p of places) bind(p.span);
  document.addEventListener('mousedown', onOutside, true);
  focusPlace(session.cell, !select || typeof select === 'number');
  const spot = select === true ? null : caret ?? (offset != null ? { cell: session.cell, offset } : null);
  const text = spot && places[spot.cell].span.firstChild;
  if (text) getSelection().collapse(text, Math.min(spot.offset, text.length));
  const first = places[session.cell].span.firstChild;
  if (typeof select === 'number' && first) getSelection().setBaseAndExtent(first, Math.min(select, first.length), first, first.length);   // 뒤의 글을 골라 둔다 (캡션의 '제목')
  if (range && first) {   // 읽는 화면에서 고른 글 그대로 (D142) — 제목의 번호를 잠갔으면 그만큼 앞으로
    const cut = slot.kind === 'text' ? parts.head.length - splitText(original).head.length : 0;
    const at = (n) => Math.max(0, Math.min(n - cut, first.length));
    getSelection().setBaseAndExtent(first, at(range[0]), first, at(range[1]));
  }
  showLineEdit();
}

/** 새 줄의 글 칸 */
function newCell(fill) {
  const span = document.createElement('span');
  span.className = 'lec-line-edit whole';
  span.contentEditable = 'plaintext-only';
  span.spellcheck = false;
  span.dataset.i = '0';
  span.textContent = fill;
  return span;
}

/** 문서 맨 위 블록 — 표·그림·구분선처럼 줄의 자리가 없는 것의 뒤에 새 줄을 놓을 때 */
function topBlock(view, el) {
  const stop = el.closest?.('.lec-cell') ?? el.closest?.('.lec-slide') ?? view;   // 슬라이드는 칸·장 안에서
  let top = el;
  while (top && top.parentElement !== stop) top = top.parentElement;
  return top;
}

/** 새 문단을 블록 el 의 앞뒤에 놓는다. el 이 없으면 본문의 끝에 (빈 문서도) {span, el, remove} */
function plantBeside(view, el, below) {
  const span = newCell('');
  const p = document.createElement('p');
  p.className = 'lec-new-line';
  p.append(span);
  const body = [...view.children].filter((x) => !x.matches('.footnotes-sep, .footnotes'));
  const top = el ? topBlock(view, el) : body.at(-1);
  if (top) top[below ? 'after' : 'before'](p);
  else view.append(p);
  return { span, el: p, remove: () => p.remove() };
}

/** 아직 파일에 없는 새 줄의 자리를 화면에 만든다 {span, el, remove} — slot: 기준 줄의 자리 */
function plantLine(slot, plan, below) {
  const span = newCell(plan.fill);
  const side = below ? 'after' : 'before';
  if (plan.kind === 'code' && !slot.el.classList.contains('cv-line')) {   // 코드 블록: 그 줄의 앞뒤에
    span.classList.remove('whole');
    const range = slot.ranges[0].cloneRange();
    range.collapse(!below);
    const nl = document.createTextNode('\n');
    const frag = document.createDocumentFragment();
    if (below) frag.append(nl, span);
    else frag.append(span, nl);
    range.insertNode(frag);
    return { span, el: slot.el, remove: () => { span.remove(); nl.remove(); } };
  }
  let el;
  if (plan.kind === 'code') {   // 코드 화면. data-line 이 없어 줄 단위에 들지 않고 번호도 비어 있다
    el = document.createElement('div');
    el.className = 'cv-line lec-new-line';
    const text = document.createElement('span');
    text.className = 'cv-text';
    text.append(span);
    el.append(text);
    slot.el[side](el);
  } else if (plan.kind === 'item') {
    el = document.createElement('li');
    el.className = 'lec-new-line';
    if (plan.task) {
      el.classList.add('task-list-item');
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.disabled = true;
      box.className = 'task-list-item-checkbox';
      el.append(box, ' ');
    }
    el.append(span);
    (slot.el.closest('li') ?? slot.el)[side](el);
    return {
      span, el, remove: () => {   // 레벨을 바꾸며 만든 하위 목록(nestFresh)이 비면 함께
        const list = el.parentElement;
        el.remove();
        if (list?.dataset.lecFresh != null && !list.children.length) list.remove();
      },
    };
  } else {
    el = document.createElement('p');
    el.className = plan.kind === 'mark' ? `lec-new-line lec-mark ${plan.level}` : 'lec-new-line';   // 글머리 글자 목록은 그 수준에 (D192)
    el.append(span);
    (plan.kind === 'mark' ? (below ? plan.place : slot.el.closest('.lec-mark')) ?? slot.el : slot.el)[side](el);
  }
  return { span, el, remove: () => el.remove() };
}

/**
 * 줄 base 의 아래(below)·위에 새 줄을 연다 — 글을 쓰고 끝낼 때 파일에 넣는다 (finishNew).
 * end: 문서 끝에 (D106 — 마지막 줄의 ↓, 빈 문서). 구분선·그림처럼 줄의 자리가 없는 곳은 그 블록의 앞뒤에 문단을 연다
 */
async function beginNew(base, below, { end = false, after = false, around = false, peek = false } = {}) {
  const pane = S.pane;
  const ready = await settled(pane);
  if (S.pane !== pane || session || !ready) return;
  const view = $('#lec-view');
  const src = sourceLines();
  const plan = around ? (below ? planEnd(src, base) : planBefore(src, base)) : end ? planEnd(src, after ? base : 0) : null;
  const at = plan && !around ? plan.at || base : base;
  const slot = !around && (!plan || plan.kind === 'item' || plan.head) && at ? lineSlot(view, at, src) : null;
  const code = isCodeView(view);
  const mark = !plan && slot?.el?.closest?.('.lec-mark');
  const next = plan ?? (mark ? planMark(src, mark, below) : planNew(src, base, below, { code, parts: slot?.kind === 'code' ? splitCode(src[base - 1], slot.fence) : null }));
  if (next.error) {
    toast(whyNot(next.error));
    return;
  }
  if (!slot && code) {
    toast(t('이 줄에는 새 줄을 더하지 못합니다 — 편집 모드(Ctrl+E)에서 고칩니다'));
    return;
  }
  const anchor = next.from ? lineSlot(view, next.from, src) : slot;   // 위 블록에 잇는 새 줄 (D156 — lineops.planNew 의 from)
  const made = anchor ? plantLine(anchor, next, next.from ? true : below) : plantBeside(view, at ? blockOfLine(view, at) : null, below);
  releasePick();
  session = {
    pane, tab: pane.tab, path: pathIn(view), line: base, kind: next.kind === 'code' ? 'code' : 'text', original: '', parts: { head: '', body: '', tail: '' },
    places: [{ span: made.span, frag: null, nbsp: false }], el: made.el, cell: 0, fence: slot?.fence || '', fresh: { plan: next, lines: src.slice(), remove: made.remove, peek },
  };
  pane.lineEdit = session;
  bind(made.span);
  document.addEventListener('mousedown', onOutside, true);
  focusPlace(0);
  made.span.scrollIntoView({ block: 'nearest' });
  hereAtNew();
  showLineEdit();
}

/**
 * 글머리 글자 목록(D192)의 항목 el 의 아래(below)·위에 새 항목 — 같은 머리 글자를 칸에 미리 넣는다 (fill). 아래면 이어 쓴 줄 뒤에.
 * 머리 글자만 둔 채 끝내면 넣지 않는다 (finishNew)
 * @param {string[]} src
 * @param {Element} el
 * @param {boolean} below
 */
function planMark(src, el, below) {
  const a = Number(String(/** @type {HTMLElement} */ (el).dataset.lines ?? '').split('-')[0]);
  const place = below ? subtreeEnd(el) : el;
  const b = Number(String(/** @type {HTMLElement} */ (place).dataset.lines ?? '').split('-')[1]);
  const line = src[a - 1] ?? '';
  const head = /^(?:[ \t]*>[ \t]?)*[ \t\u3000]*/.exec(line)[0];
  const fill = markOf(markText(line.slice(head.length)))?.prefix ?? '';
  const level = [...el.classList].find((c) => /^lec-lv\d$/.test(c)) ?? 'lec-lv0';
  return { at: below ? b : a - 1, pre: [], post: [], head, fill, base: fill.trim(), kind: 'mark', level, place, list: null };
}

/** 글머리 글자 목록의 항목 el 과 그 아래 더 깊은 항목들 가운데 마지막 (아래에 넣는 새 항목은 그 뒤 — 하위 항목을 가르지 않는다) */
function subtreeEnd(el) {
  const level = (x) => Number(/\blec-lv(\d)\b/.exec(x.className)?.[1] ?? 0);
  let last = el;
  for (let x = el.nextElementSibling; x?.matches('.lec-mark:not(.lec-new-line)') && level(x) > level(el); x = x.nextElementSibling) last = x;
  return last;
}

/**
 * 칸 없이 새 줄을 연다 (D117): Shift+Enter·Ctrl+Shift+Enter (D164). 현재 줄(잡은 줄·한 줄의 하이라이트도)의 위·아래에 열고 고르기를 푼다 — 여러 줄을
 * 골랐으면 spotlight.js 가 보내지 않는다 (D139).
 * 표의 행은 새 행을, 차트·수식은 그 블록의 앞뒤 문단을 연다
 */
function addHere(below) {
  const pane = S.pane;
  const view = pane?.view;
  if (!view || session || pane.lineEditHold || pane.unfold) return;
  if (pane.tab && blockedReadOnly(pane.tab)) return;
  if (!linesEditable()) return;
  const span = litSpan();
  const base = span ? span[below ? 1 : 0] : pane.here?.line;
  stopSpotlight();
  if (!base) {
    growEnd();
    return;
  }
  const el = blockOfLine(view, base);
  if (tableAt(sourceLines(), base)) {   // 줄로 본다 — 화면에서는 tbody 가 그 줄을 맡기도 한다
    menuOp((src) => addRow(src, base, below), (line) => begin(line, { cell: 0 }));
    return;
  }
  followLine(base);
  beginNew(base, below, { around: !!el?.closest?.(ATOMIC) });
}

/** 마지막 줄의 ↓ 로 줄을 더할 수 있는 화면인지 — md 문서와 Lectern 슬라이드. 코드 파일은 그대로 (D106) */
function canGrow(pane) {
  const view = pane?.view;
  return !!view?.dataset.docPath && !isCodeView(view) && linesEditable() && !session;
}

/**
 * 마지막 줄의 ↓·빈 문서의 F2: 문서 끝에 새 줄을 연다. 각주는 문서 끝에 모인 것이라 그 뒤에는 더하지 않는다.
 * peek: 읽는 화면에서 끝을 지나친 ↓ 가 연 줄 — 비어 있는 동안의 ↑ 는 편집을 잇지 않고 읽기로 돌아간다 (D128)
 */
function growEnd({ peek = false } = {}) {
  const pane = S.pane;
  if (!canGrow(pane)) return;
  const line = pane.here?.line || 0;
  if (pane.unfold || (line && blockOfLine(pane.view, line)?.closest('.footnotes'))) return;   // 주 내용 줄에서는 더하지 않는다 (D106)
  beginNew(line, true, { end: true, after: pane.view.classList.contains('lec-deck'), peek });   // 슬라이드는 그 칸 안에 (문서 끝은 닫는 ::: 뒤다)
}

/**
 * 아직 파일에 없는 새 항목(li)을 한 레벨 안(dir 1 — 앞 항목의 하위 목록 끝)·밖(-1 — 부모 항목 뒤)의 목록으로 옮긴다 (D189).
 * 여백만 밀면 같은 목록에 남아 글머리표 모양·번호가 옛 레벨 그대로였고, 글을 써서 끝내야 바뀌었다. tag: 그 레벨의 목록 (OL·UL)
 */
function nestFresh(li, dir, tag) {
  if (dir > 0) {
    const prev = li.previousElementSibling;
    if (prev?.tagName !== 'LI') return;
    let sub = prev.lastElementChild;
    if (sub?.tagName !== tag) {
      sub = document.createElement(tag);
      sub.dataset.lecFresh = '';   // 새 줄을 위해 만든 목록 — 비면 걷는다
      prev.append(sub);
    }
    sub.append(li);
    return;
  }
  const list = li.parentElement;
  const parent = list?.parentElement?.closest('li');
  if (!parent) return;
  parent.after(li);
  if (list.dataset.lecFresh != null && !list.children.length) list.remove();
}

/** 빈 새 줄의 레벨을 바꾸고 화면의 자리를 맞춘다 (D106 — 계산은 lineops.shiftPlan). 바뀌었으면 true */
function shiftFresh(s, dir) {
  if (s.fresh.plan.kind === 'mark') return shiftMark(s, dir);
  const plan = shiftPlan(s.fresh.lines, s.fresh.plan, dir);
  if (!plan) return false;
  const was = s.fresh.plan.kind;
  s.fresh.plan = plan;
  if (plan.kind === 'item') {
    nestFresh(s.el, dir, /^\s*(?:>\s*)*\s*\d/.test(plan.head) ? 'OL' : 'UL');
    focusPlace(0);
    hereAtNew();
    return true;
  }
  const span = s.places[0].span;
  const p = document.createElement('p');
  p.className = 'lec-new-line';
  p.append(span);
  let top = s.el;
  if (was === 'item') while (top.parentElement.closest('ul, ol')) top = top.parentElement.closest('ul, ol');
  else top = s.el.closest('blockquote') ?? s.el;
  (was === 'item' ? top.closest('ul, ol') ?? top : top).after(p);
  s.fresh.remove();   // 옛 자리 (새 항목이면 레벨을 바꾸며 만든 빈 하위 목록도)
  s.el = p;
  s.fresh.remove = () => p.remove();
  focusPlace(0);
  hereAtNew();
  return true;
}

/**
 * 새 글머리 글자 목록 줄(D192)의 Tab·Shift+Tab: 머리 글자를 한 차례 아래·위로 (□ → ○ → - → ·, ㅁ·ㅇ 로 쓴 문서는 ㅁ → ㅇ → - → ·).
 * 수준은 저장하고 다시 그리면 문서가 쓴 차례로 맞는다 — 그 전에는 한 칸씩
 */
/** 차례 rank 의 글머리 글자 — 그 문서가 그 차례에 쓴 글자, 없으면 처음 머리 글자(was)의 꼴로 (ㅁ·ㅇ 로 쓴 문서는 ㅁ·ㅇ) */
function markFor(rank, view, was) {
  for (const p of view.querySelectorAll('.lec-mark:not(.lec-new-line)')) {
    const m = markOf(p.textContent ?? '');
    if (m?.rank === rank) return m.prefix.trim();
  }
  const jamo = /[ㅁㅇ]/.test(was);
  return [jamo ? 'ㅁ' : '□', jamo ? 'ㅇ' : '○', '-', '·'][rank];
}

function shiftMark(s, dir) {
  const span = s.places[0].span;
  const text = span.textContent ?? '';
  const mark = markOf(`${text}x`);   // 아직 머리 글자뿐이어도 (markOf 는 뒤에 글이 있어야 머리 글자로 본다)
  if (!mark || mark.rank < 0) return false;
  const rank = mark.rank + dir;
  if (rank < 0 || rank >= RANKS.length) return true;
  const c = mark.prefix.trim();
  const to = markFor(rank, s.pane.view, s.fresh.plan.base ?? c);
  span.textContent = to + text.slice(c.length);
  s.fresh.plan = { ...s.fresh.plan, fill: to + mark.prefix.slice(c.length) };
  const level = Number(/lec-lv(\d)/.exec(s.el.className)?.[1] ?? 0);
  s.el.className = s.el.className.replace(/\blec-lv\d\b/, `lec-lv${Math.max(0, Math.min(5, level + dir))}`);
  focusPlace(0);
  hereAtNew();
  return true;
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
 * 편집을 끝낸다. save: 고친 것이 있으면 저장하고 그 칸을 다시 그린다. {ok, saved} — ok 가 false 면 저장하지 못했다(알렸다).
 * 칸이 닫히면 키보드 초점을 문서 칸으로 돌린다 (D158 — 이어 누르는 ↑·↓·PageDown 이 그 줄에서 듣게)
 */
async function finish(save) {
  const r = await finishCell(save);
  refocus();
  return r;
}

/** 칸이 닫힌 뒤 초점이 페이지 바닥이나 사라진 칸에 남았으면 문서 칸으로 — 사용자가 다른 곳(창·입력 칸)에 둔 초점은 그대로 */
function refocus() {
  if (session) return;
  const act = document.activeElement;
  if (act && act !== document.body && act.isConnected && !act.closest?.('.lec-line-edit, .lec-new-line')) return;
  S.pane?.scroller?.focus({ preventScroll: true });
}

async function finishCell(save) {
  const s = session;
  if (!s) return { ok: true, saved: false };
  session = null;
  paintSoon();
  s.pane.lineEdit = null;
  document.removeEventListener('mousedown', onOutside, true);
  if (s.fresh) return finishNew(s, save);
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
    s.line = r.at;   // 위쪽이 바뀌어 줄이 밀렸으면 새 자리 — 저장은 알리지 않는다 (D156 — 상태줄의 수정 시각이 바뀐다)
    askDroppedNotes(s, next);
    return { ok: true, saved: true };
  } catch (e) {
    restore(s);
    await copyText(next);   // 칸을 되돌리면 친 글이 사라진다
    toast(t('저장하지 못했습니다 — 고친 줄은 클립보드에 복사했습니다: {error}', { error: e.message }), 'error');
    return { ok: false, saved: false };
  }
}

/** 본문의 주 표시를 지웠으면 내용 줄도 지울지 묻는다 (D110) */
function askDroppedNotes(s, next) {
  if (s.kind !== 'text' || !s.original.includes('[^')) return;
  const lines = sourceLines();
  const gone = droppedNotes(lines.map((x, i) => (i === s.line - 1 ? s.original : x)), lines);
  if (!gone.length || lines[s.line - 1] !== next) return;
  if (window.confirm(t('주 표시를 지웠습니다. 문서 끝의 주 내용 {n}개도 지울까요?', { n: gone.length }))) commit(s.pane, s.path, lines, removeNotes(lines, gone));
}

/** 새 줄을 끝낸다: 글이 있으면 파일에 넣고, 없으면 화면의 자리를 걷는다 (파일은 그대로) */
async function finishNew(s, save) {
  const text = read(s.places[0]);
  const bare = s.fresh.plan.kind === 'mark' && text.trim() === String(s.fresh.plan.fill ?? '').trim();   // 미리 넣은 글머리 글자뿐 (D192)
  if (!save || !text.trim() || bare) {
    s.fresh.remove();
    showLineEdit();
    if (s.line) followLine(s.line);   // 화살표를 기준 줄로 되돌린다
    if (s.pane.lineEditMissed) {
      s.pane.lineEditMissed = false;
      refreshView(s.pane);
    }
    return { ok: true, saved: false };
  }
  const { span } = s.places[0];
  span.contentEditable = 'false';
  span.classList.add('saving');
  showLineEdit();
  const made = insertLine(s.fresh.lines, s.fresh.plan, text);
  const d = diffRange(s.fresh.lines, withNumbers(s.pane, s.fresh.lines, made.lines));
  try {
    s.pane.lineEditMissed = false;
    const r = await replaceLines(s.pane, s.path, d.start, d.before, d.after);
    if (r) noteCaptions();
    if (!r) {
      s.fresh.remove();
      await copyText(text);
      toast(t('다른 곳에서 이 줄이 바뀌어 저장하지 않았습니다 — 고친 줄은 클립보드에 복사했습니다'), 'error');
      refreshView(s.pane);
      return { ok: false, saved: false };
    }
    s.line = made.line + r.at - d.start;
    if (S.pane === s.pane) followLine(s.line);
    return { ok: true, saved: true };
  } catch (e) {
    s.fresh.remove();
    await copyText(text);
    toast(t('저장하지 못했습니다 — 고친 줄은 클립보드에 복사했습니다: {error}', { error: e.message }), 'error');
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
      // 409: 받은 뒤 저장하기 전에 바뀌었다. status 없음: 연결이 잠깐 실패했다 (D81) — 둘 다 원문을 다시 받아 두 번까지 더.
      // Claude 가 잇달아 쓰는 동안은 409 가 거푸 올 수 있다 (서버는 바꿔 끼우기 바로 앞에서도 본다 — editing.save_source)
      if ((e.status != null && e.status !== 409) || attempt >= 2) throw e;
    }
  }
}

/**
 * 원문 줄 범위를 바꿔 저장하고 되돌리기 기록에 쌓고 칸을 다시 그린다 — 편집이 파일을 고치는 길은 이것 하나다.
 * before 는 한 줄 이상 (넣기는 앞 줄을 before·after 양쪽에). {hash, at} — 자리를 찾지 못해 저장하지 않았으면 null. 보기만 하는 프로젝트(D71)는 부르는 쪽이 막는다
 */
export function replaceLines(pane, path, start, before, after) {
  const job = saveRecorded(pane, path, start, before, after);
  saving.add(job);
  const done = () => saving.delete(job);
  job.then(done, done);
  return job;
}

async function saveRecorded(pane, path, start, before, after) {
  const { tab } = pane;
  const lit = S.pane === pane && (lightOn() || pickedMany()) ? litSpan() : null;   // 바꾸기 전에 고른 줄 — 되돌리면 그 줄들을 다시 고른다
  const r = await writeLines(tab, path, start, before, after);
  if (!r) return null;
  const rec = recordOf(tab.id, path);
  rec.done.push({ line: r.at, before, after, hash: r.hash, lit: lit && lit.map((n) => n + r.at - start) });
  if (rec.done.length > MAX_UNDO) rec.done.shift();
  rec.undone.length = 0;   // 새로 고치면 되돌린 것을 다시 할 수 없다
  await refreshView(pane);
  return r;
}

let headNote = 0;   // withNumbers 가 다시 매긴 제목 번호 수 — 저장한 뒤 알린다 (D152)
let captionNote = null;   // 캡션 번호를 맞춘 저장이 남긴 알림 {plain, dangling} — 저장한 뒤에 띄운다 (noteCaptions)

/**
 * 제목이 바뀌면 제목 번호를 다시 맞춘다 (D107) — 번호가 있던 md 문서만. 표·그림을 더하거나 빼거나 옮기면 캡션 번호와 그 참조도 (D121 — refs.js).
 * 같은 저장에 묶여 되돌리기 한 걸음이다
 */
function withNumbers(pane, old, next) {
  const { view } = pane;
  if (!view.dataset.docPath || view.classList.contains('lec-deck')) return next;
  const heads = (lines) => lines.filter((s) => headLevel(s)).join('\n');
  let out = next;
  headNote = 0;
  if (!sameHeads(old, next) || heads(old) !== heads(next)) {   // 번호만 떨어졌어도 다시 붙인다
    const id = numberScheme(old);
    if (id) {
      out = applyScheme(next, id, slugify).lines;
      headNote = out.filter((s, i) => s !== next[i] && (old.length !== next.length || old[i] === next[i])).length;   // 이번 고침이 건드리지 않은 제목의 번호 (D152 — 알림)
    }
  }
  const c = renumberCaptions(old, out);
  captionNote = c.plain || c.dangling ? c : null;
  return c.lines;
}

/** 캡션 번호를 맞춘 뒤 고치지 않은 곳을 알린다 — 링크가 아닌 '표 3' 글자, 없어진 표를 가리키는 참조 */
function noteCaptions() {
  const c = captionNote;
  captionNote = null;
  if (!c) return;
  if (c.dangling) toast(t('없어진 표·그림을 가리키는 참조가 {n}곳 남았습니다 — 링크를 고치거나 지우세요', { n: c.dangling }));
  else toast(t('표·그림 번호를 다시 매겼습니다. 링크가 아닌 \'표 3\' 같은 글자 {n}곳은 고치지 않았습니다 — Ctrl+F 로 찾아보세요', { n: c.plain }));
}

/**
 * 줄 배열 old 를 next 로 저장한다 — 되돌리기 한 걸음으로. 줄이 밀린 수를 돌려준다. 저장하지 못했으면 알리고 null.
 * numbers: 제목이 바뀌면 번호도 함께 (머리글 모양을 바꾸는 restyle 만 끈다)
 */
async function commit(pane, path, old, next, { numbers = true, note = '' } = {}) {
  const saved = numbers ? withNumbers(pane, old, next) : next;
  const d = diffRange(old, saved);
  try {
    const r = await replaceLines(pane, path, d.start, d.before, d.after);
    if (r) {
      const captions = !!captionNote;
      noteCaptions();
      // 고른 줄 밖이 함께 바뀌었으면 한 줄로 알린다 (D152 — 하위 절 제목·뒤 항목의 번호·제목 번호)
      const lost = lostHeadLinks(old, saved, slugify);   // 없어진 제목을 가리키는 링크 (D155 — 제목을 문단으로 바꾸면)
      const parts = [note, numbers && headNote ? t('제목 번호 {n}곳을 다시 매겼습니다', { n: headNote }) : '',
        lost ? t('없어진 제목을 가리키는 링크 {n}곳이 남았습니다 — 링크를 고치거나 지우세요', { n: lost }) : ''].filter(Boolean);
      if (!captions && parts.length) toast(parts.join(' · '), '', 4000);   // 고른 줄 밖이 바뀐 것만 알린다 (D156)
      return r.at - d.start;
    }
    toast(t('다른 곳에서 이 줄이 바뀌어 저장하지 않았습니다 — 화면을 다시 그렸습니다'), 'error');
    refreshView(pane);
  } catch (e) {
    toast(t('저장하지 못했습니다: {error}', { error: e.message }), 'error');
  }
  return null;
}

/** 칸 밖을 누르면: 고친 것이 있으면 저장, 없으면 그만둔다 (그 블록 — 표면 그 행 — 안은 그대로) */
function onOutside(e) {
  if (!session || session.el.contains(e.target) || e.target.closest?.('#lec-put') || (cellMenuOpen && e.target.closest?.('#lec-menu'))) return;
  finish(true);
}

// ---- 칸 안의 키 ---------------------------------------------------------------------

/** 칸 안의 글 커서 자리 (글자 수). 글을 골랐거나 칸 밖이면 null */
function caretOffset(span) {
  const sel = getSelection();
  if (!sel.isCollapsed || !span.contains(sel.focusNode)) return null;
  const r = document.createRange();
  r.selectNodeContents(span);
  r.setEnd(sel.focusNode, sel.focusOffset);
  return r.toString().length;
}

/**
 * 커서가 칸의 글에서 화면상 맨 윗줄(dir < 0)·맨 아랫줄(dir > 0)인지. 칸(.whole)은 block 이라 상자가 하나뿐이므로 글의 줄 상자로 잰다.
 * Selection.modify 로는 알 수 없다 — 맨 윗줄에서도 글 맨 앞으로 움직인다.
 * 커서 자리는 커서의 상자가 아니라 그 옆 글자의 상자로 잰다 (D189) — 꺾인 자리(화면 줄의 맨 앞)의 커서는 크롬이 윗줄 끝에 있다고 재어,
 * 둘째 화면 줄 맨 앞(Home·그 자리를 누름)의 ↑ 가 칸 안에서 오르지 않고 윗줄로 넘어갔다. 꺾인 자리는 어느 화면 줄에 보이는지 알 수 없으니
 * 칸에 머무는 쪽으로 본다 — ↑ 는 커서 뒤 글자, ↓ 는 앞 글자의 줄. 잘못 보면 한 번 더 누르게 될 뿐 줄을 건너뛰지 않는다
 */
function caretOnEdge(span, dir) {
  const at = selOffsets(span);
  if (!at) return true;
  const all = document.createRange();
  all.selectNodeContents(span);
  const lines = [...all.getClientRects()].filter((r) => r.height);
  const len = span.textContent.length;
  if (!lines.length || !len) return true;   // 빈 칸
  const n = dir < 0 ? at[0] : at[1];   // 글을 골랐으면 ↑ 는 앞 끝, ↓ 는 뒤 끝에서
  const box = (dir < 0 ? [n, n - 1] : [n - 1, n]).filter((i) => i >= 0 && i < len).map((i) => charBox(span, i)).find(Boolean);
  if (!box) return true;
  const mid = (box.top + box.bottom) / 2;
  return dir < 0 ? mid < Math.min(...lines.map((r) => r.bottom)) : mid > Math.max(...lines.map((r) => r.top));
}

/** 칸의 글에서 i 번째 글자의 화면 상자 (없으면 null) */
function charBox(span, i) {
  const rects = [...(rangeIn(span, i, i + 1)?.getClientRects() ?? [])].filter((r) => r.height);
  return rects.find((r) => r.width) ?? rects[0] ?? null;
}

/** 고칠 수 있는 줄의 차례에서 line 의 앞뒤 줄 — 고칠 수 없는 줄이 됐으면(글을 지운 목록 항목 등) 그 줄의 다음·앞 줄로 */
function neighbor(line, dir) {
  const fold = S.pane?.unfold;
  if (fold?.a) return line + dir >= fold.a && line + dir <= fold.b ? line + dir : undefined;   // 패널 안에서만 (D112)
  const src = sourceLines();
  // 본문에서는 각주로 내려가지 않는다 — 본문 마지막 줄의 ↓ 가 새 줄을 열게 (D106). 각주 안에서는 각주끼리, ↑ 로 본문으로
  const notes = !!blockOfLine(S.pane.view, line)?.closest?.('.footnotes');
  const order = currentUnits().filter((u) => notes || !u.el.closest?.('.footnotes')).flatMap((u) => editableLines(u, src));
  const i = order.indexOf(line);
  return i >= 0 ? order[i + dir] : dir > 0 ? order.find((n) => n > line) : order.findLast((n) => n < line);
}

/** 행의 끝 칸에서 그쪽으로 Tab 을 눌렀고 그 표에 옆 행이 있는지 */
function rowEdge(at, back) {
  if (at !== (back ? 0 : session.places.length - 1)) return false;
  const src = sourceLines();
  const next = neighbor(session.line, back ? -1 : 1);
  return next != null && tableAt(src, next)?.last === tableAt(src, session.line)?.last;
}

/**
 * ↑·↓: 저장하고 위·아래 줄을 이어서 편집 (표는 같은 칸 차례). 넘어가는 사이에도 하이라이트의 회색은 걷어 둔다 (lineEditHold).
 * 마지막 줄의 ↓ 는 칸을 그대로 두고 줄을 더하는 키를 알린다 (D158 — 문서 중간과 끝이 같은 키 Shift+Enter). 빈 새 항목의 ↓ 는 한 레벨 밖으로 — 목록이 끝난다
 */
async function step(dir, repeat = false, cell = null) {
  const s = session;
  if (dir > 0 && s.line && neighbor(s.line, 1) == null && (!s.fresh || read(s.places[0]).trim())) {   // 마지막 줄 — 옮길 곳이 없다
    if (!repeat) toast(t('마지막 줄입니다 — 아래에 새 줄은 Shift+Enter'));
    return;
  }
  if (dir > 0 && s.fresh && !read(s.places[0]).trim()) {
    if (repeat || shiftFresh(s, -1) || (s.line ? neighbor(s.line, 1) == null : true)) return;
  }
  s.pane.lineEditHold = true;
  try {
    const res = await finish(true);
    if (!res.ok || S.pane !== s.pane) return;
    if (s.fresh && !res.saved && dir < 0) {   // 빈 새 줄을 떠나면 기준 줄로
      followLine(s.line);
      await begin(s.line);
      return;
    }
    const next = neighbor(s.line, dir);
    if (next == null) {
      followLine(s.line);
      if (dir > 0 && !repeat && !s.fresh?.plan.error) growEnd();
      return;
    }
    followLine(next);
    await begin(next, { cell: cell ?? (s.kind === 'table' ? s.cell : 0) });
  } finally {
    s.pane.lineEditHold = false;
    showLineEdit();
    drainSteps(s.pane);
  }
}

/**
 * 넘어가는 사이(lineEditHold)에 누른 ↑·↓ (D128 — spotlight.js 가 'line-step' 으로 넘긴다). 읽는 화면의 현재 줄로 보내면
 * 저장 뒤 다음 칸이 옛 차례의 줄에 열려 화살표가 되돌아가고 키가 빠진 것처럼 된다 — 모았다가 칸이 열리면 하나씩 잇는다
 */
let queued = [];

/**
 * 모아 둔 ↑·↓ 를 잇는다: 칸이 열려 있으면 그 칸의 ↑·↓ 하나 (그것이 끝나면 다음 것), 편집이 끝났으면 남은 것을 현재 줄로.
 * 칸에서 누른 ↑·↓ 와 같이 꺾인 글의 안쪽 줄에서는 칸 안에서 한 화면 줄씩 먼저 움직인다 (D189 — 빠르게 두 번 누른 ↑ 가 긴 줄을 건너뛰었다)
 */
function drainSteps(pane) {
  while (queued.length && session?.pane === pane && S.pane === pane) {
    const span = session.places[session.cell]?.span;
    if (!span || caretOnEdge(span, queued[0])) break;
    getSelection().modify('move', queued.shift() < 0 ? 'backward' : 'forward', 'line');
  }
  if (!queued.length) return;
  if (session?.pane === pane && S.pane === pane) {
    step(queued.shift());
    return;
  }
  const rest = queued;
  queued = [];
  if (S.pane === pane && !session) for (const dir of rest) stepHere(dir);
}

// ---- 줄 구조 (D83 — 계산은 lineops.js) ---------------------------------------------

/** lineops 가 돌려준 까닭의 알림 문구 */
function whyNot(error) {
  switch (error) {
    case 'edge': return t('더 옮길 곳이 없습니다');
    case 'mixed': return t('수준이 다른 항목은 함께 옮기지 못합니다 — 한 항목씩 옮깁니다');
    case 'table': return t('표의 행은 복제하지 않습니다 — Shift+Enter 로 새 행을 더합니다');
    case 'not-table': return t('표 안에서 누르세요');
    case 'last-column': return t('하나뿐인 열은 지우지 않습니다 — 표를 지우세요');
    case 'not-box': return t('강조글 안에서 누르세요');
    case 'not-textbox': return t('박스글 안에서 누르세요');
    case 'quote-in-textbox': return t('박스글 안에 인용·강조글이 있어 강조글로 바꾸지 않습니다 — 강조글 안의 강조글이 됩니다');
    case 'in-textbox': return t('박스글 안에는 박스글을 넣지 않습니다');
    case 'textbox-heading': return t('제목 줄은 박스글로 묶지 않습니다 — 박스글은 절 안에 둡니다');
    case 'not-cell': return t('칸 안에서 누르세요');
    case 'not-numeric': return t('값 열이 수가 아니라 차트로 바꾸지 못했습니다 — 첫 열은 항목, 다음 열들은 수여야 합니다');
    case 'first-item': return t('목록의 맨 앞 항목은 더 안으로 옮기지 못합니다');
    case 'top-level': return t('맨 바깥 항목은 더 밖으로 옮기지 못합니다');
    case 'different': return t('종류가 다른 줄은 합치지 않습니다');
    case 'kind': return t('이 줄의 종류는 바꿀 수 없습니다 — 코드 블록과 머리 설정은 그대로 둡니다');
    case 'table-kind': return t('표의 줄은 종류를 바꿀 수 없습니다');
    case 'not-heading': return t('제목 줄에서 누르세요');
    case 'fence': return t('코드 블록의 ``` 줄만 지우면 블록이 깨집니다 — 코드 블록 전체를 하이라이트하면 블록째 지웁니다');
    case 'caption': return t('캡션 줄은 종류를 바꾸지 않습니다 — 캡션을 지우려면 Delete');
    case 'box-head': return t('강조글의 머리 줄은 바꾸지 않습니다 — 종류는 C 나 우클릭 \'강조글 종류 바꾸기\'로');
    case 'not-list': return t('목록 안에서 누르세요');
    case 'nested-list': return t('하위 항목이 있는 목록은 표로 바꾸지 않습니다 — 하위 항목을 먼저 밖으로 옮기세요');
    case 'empty-table': return t('본문 행이 없는 표는 목록으로 바꾸지 않습니다');
    case 'in-code': return t('코드 블록 안의 줄은 다시 감싸지 않습니다');
    case 'not-code': return t('코드 블록 안에서 누르세요');
    case 'quote-mix': return t('인용·강조글 안과 밖의 줄은 함께 바꾸지 않습니다 — 나눠서 고르세요');
    default: return t('이 줄은 그렇게 고칠 수 없습니다 — 편집 모드(Ctrl+E)에서 고칩니다');
  }
}

const splitterOf = (s) => (s.kind === 'code' ? (line) => splitCode(line, s.fence) : s.el?.closest?.('.lec-mark') ? keepMark : splitText);   // 글머리 글자 목록은 칸의 글과 같게 (D192)

/**
 * 글머리 글자 목록(D192)의 줄 n 을 칸의 글 offset 에서 두 줄로 — 뒤 글은 같은 머리 글자의 새 항목 (이어 쓴 줄이면 이어 쓴 줄), 사이에 빈 줄을 두지 않는다.
 * 커서가 머리 글자 안이면 null (새 줄을 연다)
 */
function splitMark(lines, n, offset) {
  const parts = keepMark(lines[n - 1]);
  const mark = markOf(markText(parts.body))?.prefix ?? '';
  if (mark && offset <= mark.length) return null;
  const next = lines.slice();
  next.splice(n - 1, 1, parts.head + parts.body.slice(0, offset).trimEnd(), parts.head + mark + parts.body.slice(offset).trimStart() + parts.tail);
  return { lines: next, line: n + 1, offset: mark.length };
}

/**
 * 글머리 글자 목록(D192)의 줄 a~b 를 dir 쪽으로 — 그 항목들과 아래의 더 깊은 항목을 같은 수준의 앞·뒤 항목(과 그 하위) 너머로, 묶음 안에서만.
 * 원문으로는 '- ' 줄 뒤의 'ㅇ' 줄이 그 목록 항목에 이어 쓴 줄이라 보통 옮기기는 그 너머로 간다. 묶음의 줄이 아니면 null (보통 옮기기)
 * @returns {{lines?: string[], a?: number, b?: number, error?: string} | null}
 */
function moveMarks(view, lines, a, b, dir) {
  const list = blockOfLine(view, a)?.closest?.('.lec-marklist');
  if (!list) return null;
  for (let n = a; n <= b; n++) if (blockOfLine(view, n)?.closest?.('.lec-marklist') !== list) return null;
  const items = /** @type {HTMLElement[]} */ ([...list.children].filter((x) => x.matches('.lec-mark:not(.lec-new-line)')));
  const span = (el) => String(el.dataset.lines ?? '').split('-').map(Number);
  const level = (el) => Number(/\blec-lv(\d)\b/.exec(el.className)?.[1] ?? 0);
  let i = items.findIndex((el) => span(el)[1] >= a);
  let j = items.findIndex((el) => span(el)[1] >= b);
  if (i < 0 || j < 0) return null;
  const k = level(items[i]);
  while (j + 1 < items.length && level(items[j + 1]) > k) j += 1;   // 하위 항목도 함께
  let p = i;
  let q = j;
  if (dir > 0) {
    p = j + 1;
    if (p >= items.length || level(items[p]) < k) return { error: 'edge' };
    q = p;
    while (q + 1 < items.length && level(items[q + 1]) > k) q += 1;
  } else {
    q = i - 1;
    p = q;
    while (p >= 0 && level(items[p]) > k) p -= 1;
    if (p < 0 || level(items[p]) < k) return { error: 'edge' };
  }
  const [ua, ub] = [span(items[i])[0], span(items[j])[1]];
  const [oa, ob] = [span(items[p])[0], span(items[q])[1]];
  const unit = lines.slice(ua - 1, ub);
  const other = lines.slice(oa - 1, ob);
  const next = lines.slice();
  const top = Math.min(ua, oa);
  next.splice(top - 1, unit.length + other.length, ...(dir > 0 ? [...other, ...unit] : [...unit, ...other]));
  const shift = dir > 0 ? other.length : -other.length;
  return { lines: next, a: a + shift, b: b + shift };
}

/** 글머리 글자 목록의 줄 n 을 윗줄 끝에 — 이 줄의 머리 글자는 뗀다 (항목 둘을 하나로). 윗줄은 같은 묶음의 줄이어야 한다 */
function joinMark(lines, n) {
  const up = keepMark(lines[n - 2]);
  const cur = keepMark(lines[n - 1]);
  const mark = markOf(markText(cur.body))?.prefix ?? '';
  const next = lines.slice();
  next.splice(n - 2, 2, up.head + up.body + cur.body.slice(mark.length) + cur.tail);
  return { lines: next, line: n - 1, offset: up.body.length };
}

/** 줄 사이를 넘어가는 동안: 하이라이트의 회색을 걷어 둔다 */
async function hold(s, work) {
  s.pane.lineEditHold = true;
  try {
    await work();
  } finally {
    s.pane.lineEditHold = false;
    showLineEdit();
    drainSteps(s.pane);
  }
}

/**
 * 칸의 줄에 op(줄 배열 → {lines, line, offset?} | {error})를 한다 — 고친 글을 저장한 뒤 바꾸고 바뀐 줄에서 편집을 잇는다.
 * 되지 않으면 칸을 그대로 두고 알린다 (quiet: 알리지 않는다)
 */
async function restructure(op, { quiet = false } = {}) {
  const s = session;
  const { span } = s.places[s.cell];
  if (s.fresh && !read(s.places[0]).trim()) return;   // 아직 없는 줄
  const first = s.fresh ? null : op(sourceLines());
  if (first?.error) {
    if (!quiet) toast(s.kind === 'table' && first.error === 'table-head' ? t('표의 머리행은 옮기지 않습니다') : whyNot(first.error));
    return;
  }
  const offset = caretOffset(span);
  await hold(s, async () => {
    const res = await finish(true);
    if (!res.ok || S.pane !== s.pane) return;
    const src = sourceLines();
    const r = op(src);
    if (r.error) {
      toast(whyNot(r.error));
      await begin(s.line, { cell: s.cell, offset });
      return;
    }
    const shift = await commit(s.pane, s.path, src, r.lines, { note: r.note || '' });
    if (shift == null) return;
    followLine(r.line + shift);
    await begin(r.line + shift, { cell: r.cell ?? s.cell, offset: r.offset ?? offset });
  });
}

/**
 * 칸의 Ctrl+Enter (D164): 저장하고 닫은 뒤 그 줄을 선택(하이라이트)한다 — 읽는 화면의 Ctrl+Enter 와 같은 '줄 선택'.
 * 빈 새 줄이면 넣지 않고 닫기만 한다 (선택할 줄이 없다)
 */
async function saveAndPick() {
  const s = session;
  const empty = !!s.fresh && !read(s.places[0]).trim();
  await finish(!empty);
  if (empty || session || S.pane !== s.pane) return;
  if (await settled(s.pane) && S.pane === s.pane && !session) lightHere();
}

/**
 * 칸의 Enter (D168 — 사용자 결정): 저장하고 닫은 뒤 현재 줄만 다음 줄로 옮긴다 — 다음 줄을 열지는 않는다 (Enter 를 다시 누르면 연다 — D166).
 * 마지막 줄이면 그 줄에 둔다. 새 줄도 같다 (방금 쓴 줄의 다음으로). 바꾼 것이 없어도 옮긴다 — Enter·Enter 로 줄을 훑으며 고친다
 */
async function saveAndNext() {
  const s = session;
  await finish(true);
  if (session || S.pane !== s.pane) return;
  if (await settled(s.pane) && S.pane === s.pane && !session) nextHere();
}

/** Shift+Enter(below)·Ctrl+Shift+Enter: 새 줄. 글 가운데서 Shift+Enter 면 그 자리에서 두 줄로 나눈다 */
async function addLine(below) {
  const s = session;
  if (s.kind === 'table') {   // 표의 새 행 (D109)
    restructure((lines) => {
      const r = addRow(lines, s.line, below);
      return r.error ? r : { ...r, cell: 0, offset: 0 };
    });
    return;
  }
  const { span } = s.places[0];
  if (s.fresh && !read(s.places[0]).trim()) return;   // 빈 새 줄에서 또 — 쓴 것이 없다
  const offset = caretOffset(span);
  const length = span.textContent.length;
  const mark = s.kind === 'text' && !s.fresh && s.el?.closest?.('.lec-mark');
  if (below && offset && offset < length && mark && splitMark(sourceLines(), s.line, offset)) {   // 글머리 글자 목록: 같은 머리 글자의 새 항목 (D192)
    restructure((lines) => splitMark(lines, s.line, offset) ?? { error: 'different' });
    return;
  }
  if (below && offset && offset < length && !mark) {
    const code = isCodeView(s.pane.view);
    restructure((lines) => {
      const r = splitLine(lines, s.line, offset, { split: splitterOf(s), code });
      if (r.error) return r;
      const body = splitterOf(s)(r.lines[r.line - 1]).body;
      return { ...r, offset: s.kind === 'code' ? /^[ \t]*/.exec(body)[0].length : 0 };
    });
    return;
  }
  await hold(s, async () => {
    const res = await finish(true);
    if (res.ok && S.pane === s.pane) await beginNew(s.line, below);
  });
}

/** 줄 맨 앞의 Backspace: 윗줄 끝에 잇는다 */
function joinUp() {
  const s = session;
  const code = isCodeView(s.pane.view);
  const list = !s.fresh && s.el?.closest?.('.lec-marklist');
  if (list && s.line > 1 && blockOfLine(s.pane.view, s.line - 1)?.closest?.('.lec-marklist') === list) {   // 글머리 글자 목록: 위 항목에 잇고 이 줄의 머리 글자는 뗀다 (D192)
    restructure((lines) => joinMark(lines, s.line));
    return;
  }
  restructure((lines) => joinLine(lines, s.line, { split: splitterOf(s), code }));
}

/** Tab·Shift+Tab: 목록 항목을 한 단계 안·밖으로 (하위 항목과 함께). 목록이 아니면 아무것도 하지 않고, 제목이면 키를 알린다 (D152) */
function levelHere(dir) {
  const s = session;
  const op = (lines) => {
    const r = shiftLevels(lines, s.line, s.line, dir, { tab: true });
    return r.error ? r : { lines: r.lines, line: s.line, note: levelNote(r) };
  };
  if (s.fresh && (s.fresh.plan.kind === 'mark' || !read(s.places[0]).trim())) {   // 아직 없는 줄 — 쓰기 전에 레벨을 정한다 (D106). 글머리 글자 목록은 쓰는 중에도 머리 글자를 (D192)
    shiftFresh(s, dir);
    return;
  }
  if (s.fresh) {
    if (s.fresh.plan.kind !== 'item') return;
  } else {
    const first = op(sourceLines());
    if (first.error === 'heading-tab') toast(HEAD_TAB());
    if (first.error === 'not-list' || first.error === 'heading-tab') return;
  }
  restructure(op);
}

/** 제목 줄을 옮길 때 절째 옮기는 화면인지 — md 문서만 (Lectern 슬라이드는 장으로 옮긴다) */
const sectionsOn = (view) => !isCodeView(view) && !view.classList.contains('lec-deck');
/** 구성 요소를 넣고 서식 키를 쓰는 화면인지 — md 문서와 Lectern 슬라이드 */
const textOn = (view) => !isCodeView(view);
const deckOn = (view) => view.classList.contains('lec-deck');

/** Alt+↑·↓: 이 줄을 옮긴다 (lineops.moveLines). 제목 줄이면 그 절을 본문과 함께 (D107) */
function moveHere(dir) {
  const s = session;
  const code = isCodeView(s.pane.view);
  if (deckOn(s.pane.view) && s.kind === 'text' && !s.fresh) {   // 장의 제목 줄: 그 장을 옮긴다 — md 의 절째 옮기기와 같은 규칙 (D116)
    const lines = sourceLines();
    if (headLevel(lines[s.line - 1]) && !cellAt(lines, s.line)) {
      moveSlideHere(s, dir);
      return;
    }
  }
  restructure((lines) => {
    if (sectionsOn(s.pane.view) && s.kind === 'text' && headLevel(lines[s.line - 1])) return moveSection(lines, s.line, dir);
    const r = (s.kind === 'text' && moveMarks(s.pane.view, lines, s.line, s.line, dir)) || moveLines(lines, s.line, s.line, dir, { code });   // 글머리 글자 목록은 항목째 (D192)
    return r.error ? r : { lines: r.lines, line: r.a };
  });
}

/** 칸을 닫고 그 장을 옮긴 뒤 제목 줄을 다시 연다 */
async function moveSlideHere(s, dir) {
  const res = await finish(true);
  if (!res.ok || S.pane !== s.pane) return;
  await slideOp({ op: 'move', dir });
  const at = s.pane.here?.line ?? 1;
  const n = sourceLines().findIndex((x, i) => i >= at - 1 && headLevel(x)) + 1;
  if (n) {
    followLine(n);
    await begin(n);
  }
}

/** 제목의 번호를 떼는 함수 — 번호가 있는 문서에서 제목을 다른 종류로 바꿀 때 */
const bareOf = (lines) => {
  const id = numberScheme(lines);
  return id ? (text) => bareHeading(text, id) : (text) => text;
};

/** Ctrl+Alt+숫자: 이 줄의 종류를 바꾼다 (D107 — 계산은 docops.setKind). 아직 없는 빈 새 줄이면 쓰기 전에 정한다 */
function kindHere(kind) {
  const s = session;
  if (s.kind !== 'text') return;
  if (s.fresh && !read(s.places[0]).trim()) {
    freshKind(s, kind);
    return;
  }
  restructure((lines) => {
    const want = /^h[1-6]$/.test(kind) && kindOfLine(lines[s.line - 1]) === kind ? 'para' : kind;   // 같은 수준이면 문단으로 (D152 — 숫자 키와 같게)
    const r = kindOp(lines, s.line, s.line, want);
    return r.error ? r : { lines: r.lines, line: r.line, note: r.note };
  });
}

/** 빈 새 줄의 종류를 정한다 — 쓰기 전에는 파일이 그대로다: 제목·문단·목록·번호·할 일·인용·강조글 (D109) */
function freshKind(s, kind) {
  const level = /^h([1-6])$/.exec(kind)?.[1];
  const box = /^box:(\w+)$/.exec(kind)?.[1];
  const mark = { bullet: '- ', number: '1. ', task: '- [ ] ', quote: '> ' }[kind];
  if (!level && !box && kind !== 'para' && !mark) return;
  const old = s.fresh.plan;
  const quote = quoteOf(old.head);
  const plan = old.kind === 'para' ? old : paraAt(s.fresh.lines, old.at, quote);
  const pre = box ? [...plan.pre, `${quote}> [!${box}]`] : plan.pre;
  const head = `${quote}${level ? `${'#'.repeat(Number(level))} ` : box ? '> ' : mark ?? ''}`;
  const joined = mark && kind !== 'quote' ? joinFresh(s.fresh.lines, plan.at, quote, kind) : null;   // 이웃 목록에 붙는다 (D156)
  s.fresh.plan = joined ?? { ...plan, head, pre };
  const inner = document.createElement(level ? `h${level}` : mark && kind !== 'quote' ? 'li' : 'p');
  inner.append(s.places[0].span);
  let el = inner;
  if (box || kind === 'quote') {
    el = document.createElement('blockquote');
    if (box) el.className = `alert alert-${box.toLowerCase()}`;
    el.append(inner);
  } else if (mark) {
    el = document.createElement(kind === 'number' ? 'ol' : 'ul');
    if (joined && kind === 'number') el.setAttribute('start', /(\d+)[.)]/.exec(joined.head)?.[1] ?? '1');
    el.append(inner);
  }
  el.classList.add('lec-new-line');
  s.el.replaceWith(el);
  s.el = el;
  s.fresh.remove = () => el.remove();
  focusPlace(0);
}

/**
 * 빈 새 줄을 목록으로 고를 때 붙을 이웃 목록 (D156): 새 줄 자리(at 줄 뒤) 바로 위·아래의 같은 종류 목록 — 번호는 '번호 목록', 표시는 글머리·할 일.
 * 그 목록의 다음 항목 계획(표시·번호·빈 줄), 없으면 null
 */
function joinFresh(lines, at, quote, kind) {
  const probe = [...lines.slice(0, at), `${quote}x`, ...lines.slice(at)];   // 새 줄 자리에 글 한 줄을 넣어 보고 위아래를 찾는다
  const fits = (x) => !!x && (kind === 'number' ? x.it.ordered : !x.it.ordered);
  const up = listNear(probe, at + 1, -1, 0);
  const down = fits(up) ? null : listNear(probe, at + 1, 1, 0);
  const plan = fits(up) ? planNew(lines, up.n, true) : fits(down) ? planNew(lines, down.n - 1, false) : null;
  if (!plan || plan.error || plan.kind !== 'item') return null;
  if (kind === 'task') return plan.task ? plan : { ...plan, head: `${plan.head}[ ] `, task: true };
  return { ...plan, head: plan.head.replace(/\[[ xX]\] $/, ''), task: false };
}

/** Alt+Shift+←·→: 제목은 하위 절까지 수준을 바꾸고, 목록은 레벨을 옮긴다 (D107) */
function levelKey(dir) {
  const s = session;
  if (s.kind !== 'text') return;
  const line = s.fresh ? '' : sourceLines()[s.line - 1];
  if (line && headLevel(line)) {   // Alt+Shift 는 하위 절까지 (D107·D152)
    restructure((lines) => {
      const r = shiftLevels(lines, s.line, s.line, dir, { section: true });
      return r.error ? r : { lines: r.lines, line: s.line, note: levelNote(r) };
    });
  } else levelHere(dir);
}

/** Ctrl+Shift+D: 이 줄을 복제해 복제한 줄을 이어서 고친다 */
function duplicateHere() {
  const s = session;
  if (s.kind === 'table') {
    toast(whyNot('table'));
    return;
  }
  const code = isCodeView(s.pane.view);
  restructure((lines) => duplicateLine(lines, s.line, { split: splitterOf(s), code }));
}

/** 물어볼 줄 지우기면 묻는다 */
const sureToDelete = (r) => !r.ask || window.confirm(t('{n}줄을 지울까요? 제목이나 지시어가 들어 있거나 10줄이 넘습니다.', { n: r.b - r.a + 1 }));

const deleteWhy = (error) => {
  if (error === 'table-head') return t('표의 머리행이나 구분 줄만 지우면 표가 깨집니다 — 표 전체를 하이라이트하면 표째 지웁니다');
  if (error === 'wall') return t('칸이나 장의 경계를 넘어 지울 수 없습니다 — 칸은 통째로 고르고, 장은 우클릭의 장 지우기를 쓰세요');
  return whyNot(error);
};

/** Ctrl+Shift+K: 이 줄을 지우고 편집을 끝낸다 (고치던 글도 함께 — Ctrl+Z 로는 고치기 전의 줄이 돌아온다) */
async function deleteHere() {
  const s = session;
  if (s.fresh) {
    finish(false);
    return;
  }
  const src = sourceLines();
  const r = deleteLines(src, s.line, s.line, { code: isCodeView(s.pane.view), plain: marksOnly(s.pane.view, s.line, s.line) });
  if (r.error) {
    toast(deleteWhy(r.error));
    return;
  }
  if (!sureToDelete(r)) return;
  await hold(s, async () => {
    await finish(false);
    const shift = await commit(s.pane, s.path, src, r.lines);
    if (shift == null) return;
    if (S.pane === s.pane) followLine(r.line + shift);
    toast(t('{n}줄을 지웠습니다 — Ctrl+Z 로 되돌립니다', { n: r.b - r.a + 1 }));
  });
}

/** 줄 구조를 고칠 수 있는 화면인지 — md 문서·코드 화면 (csv 표·엑셀 보기·보기만 하는 프로젝트 뺌). 하이라이트 메뉴(docmenu.js)도 본다 */
export function linesEditable() {
  const pane = S.pane;
  const view = pane?.view;
  return !!view && !!pane.tab && !pane.tab.readonly && !pane.editor && !isSheet(view) && !notUtf8(view) && !dataFile(view);
}

/** 하이라이트한 줄에 할 수 있는지 — 안 되면 까닭을 알린다 */
function litOpen() {
  const pane = S.pane;
  const view = pane?.view;
  if (!view || !pane.tab || pane.editor || session || pane.lineEditHold) return false;
  if (blockedReadOnly(pane.tab)) return false;
  if (isSheet(view)) {
    toast(t('엑셀 보기는 보기만 합니다 — 고치려면 엑셀로 여세요'));
    return false;
  }
  if (dataFile(view)) {
    toast(DATA_FILE_NOTE(view));
    return false;
  }
  if (notUtf8(view)) {
    toast(t('UTF-8 이 아닌 파일은 편집할 수 없습니다 (Lectern 은 UTF-8 글만 고칩니다)'));
    return false;
  }
  return true;
}

/**
 * 줄 a~b 가 모두 한 글머리 글자 목록(D192)의 항목이고 목록에 다른 줄이 남는지 — 그러면 그 줄들만 지운다 (Markdown 목록·문단의 정리를 하지 않는다).
 * 목록째 지우면 앞뒤 빈 줄을 맞추는 보통 지우기로
 */
function marksOnly(view, a, b) {
  const list = blockOfLine(view, a)?.closest?.('.lec-marklist');
  const span = String(/** @type {HTMLElement | null} */ (list)?.dataset.lines ?? '').split('-').map(Number);
  if (!list || !(span[0] < a || span[1] > b)) return false;
  for (let n = a; n <= b; n++) if (blockOfLine(view, n)?.closest?.('.lec-marklist') !== list) return false;
  return true;
}

/** Delete·메뉴 '줄 지우기'·Ctrl+X(cut — 원문을 복사하고 지운다): 하이라이트한 줄을 지운다 */
async function deleteLit(cut) {
  const pane = S.pane;
  const span = litSpan();
  if (!span || !litOpen() || !await settled(pane) || S.pane !== pane) return;
  const view = pane.view;
  const src = sourceLines();
  const r = deleteLines(src, span[0], span[1], { code: isCodeView(view), plain: marksOnly(view, span[0], span[1]) });
  if (r.error) {
    toast(deleteWhy(r.error));
    return;
  }
  if (!sureToDelete(r)) return;
  if (cut) await copyLitSource();
  const shift = await commit(pane, pathIn(view), src, r.lines);
  if (shift == null) return;
  if (S.pane === pane) {
    stopSpotlight();
    followLine(r.line + shift);
  }
  const n = r.b - r.a + 1;
  toast(cut ? t('{n}줄을 잘라 냈습니다 — Ctrl+Z 로 되돌립니다', { n }) : t('{n}줄을 지웠습니다 — Ctrl+Z 로 되돌립니다', { n }));
}

async function moveLitNow(dir) {
  const pane = S.pane;
  const span = litSpan();
  if (!span || !litOpen() || !await settled(pane) || S.pane !== pane) return;
  const view = pane.view;
  const src = sourceLines();
  if (span[0] === span[1] && deckOn(view) && headLevel(src[span[0] - 1]) && !cellAt(src, span[0])) {   // Lectern 슬라이드의 제목 한 줄: 그 장을 옮긴다 (D152 — 칸 안과 같게)
    await slideOp({ op: 'move', dir });
    const at = S.pane === pane ? pane.here?.line : null;
    if (at) setLitSpan(at, at);
    return;
  }
  if (span[0] === span[1] && sectionsOn(view) && headLevel(src[span[0] - 1])) {   // 제목 한 줄을 고르면 그 절을 본문과 함께 (D107)
    const m = moveSection(src, span[0], dir);
    if (m.error) {
      toast(whyNot(m.error));
      return;
    }
    const moved = await commit(pane, pathIn(view), src, m.lines);
    if (moved != null && S.pane === pane) setLitSpan(m.line + moved, m.line + moved);
    return;
  }
  const r = moveMarks(view, src, span[0], span[1], dir) ?? moveLines(src, span[0], span[1], dir, { code: isCodeView(view) });   // 글머리 글자 목록은 항목째 (D192)
  if (r.error) {
    toast(r.error === 'table-head' ? t('표의 머리행은 옮기지 않습니다') : whyNot(r.error));
    return;
  }
  const shift = await commit(pane, pathIn(view), src, r.lines);
  if (shift != null && S.pane === pane) setLitSpan(r.a + shift, r.b + shift);
}

/**
 * vi 키의 p·P (D122 — vikeys.js): dd·yy 로 담아 둔 줄을 현재 줄의 블록 아래(above 면 위)에 넣는다. 목록 항목은 목록 안에 바로,
 * 나머지는 앞뒤에 빈 줄을 두는 블록으로. 되돌리기 한 걸음
 */
export function putLinesHere(lines, above = false) {
  turn = turn.then(async () => {
    const pane = S.pane;
    if (!lines.length) {
      toast(t('담아 둔 줄이 없습니다 — dd·yy 로 줄을 담습니다'));
      return;
    }
    if (session) await finish(true);
    if (!await settled(pane) || S.pane !== pane || blockedReadOnly(pane.tab) || !pathIn(pane.view)) return;
    const src = sourceLines();
    const here = Math.min(Math.max(1, pane.here?.line ?? 1), Math.max(1, src.length));
    let r;
    const tbl = tableIn(src, blockAt(blocksOf(src), here));
    if (tbl && here >= tbl.first && lines.every((s) => s.trim().startsWith('|'))) {   // 표의 행: 표 안 그 행의 아래·위에 (D152)
      const at = above ? here - 1 : here;
      r = { lines: [...src.slice(0, at), ...lines, ...src.slice(at)], line: at + 1 };
    } else if (itemOf(src[here - 1] ?? '') && lines.every((s) => itemOf(s))) {   // 목록 항목을 목록 안에 — 빈 줄 없이, 번호 목록은 다시 매김 (D152)
      const at = above ? here - 1 : here;
      r = { lines: renumberAt([...src.slice(0, at), ...lines, ...src.slice(at)], at + 1), line: at + 1 };
    } else {
      const b = blockAt(blocksOf(src), here);
      r = insertBlock(src, above ? (b ? b.a - 1 : here - 1) : (b ? b.b : here), lines);
    }
    const shift = await commit(pane, pathIn(pane.view), src, r.lines);
    if (shift == null || S.pane !== pane) return;
    followLine(r.line + shift);
  });
}

/** vi 키의 J (D122): 고른 줄을 한 줄로 합친다 (한 줄만 골랐으면 다음 줄과). 뒤 줄의 앞 공백을 떼고 빈칸 하나로 잇는다 — 한 문단 안의 줄만 */
export function joinPicked() {
  turn = turn.then(async () => {
    const pane = S.pane;
    const span = litSpan();
    if (!span || !litOpen() || !await settled(pane) || S.pane !== pane) return;
    const src = sourceLines();
    const a = span[0];
    const b = span[1] > span[0] ? span[1] : span[0] + 1;
    const fences = fencesOf(src);
    const part = src.slice(a - 1, b);
    if (b > src.length || part.some((s) => !s.trim() || /^\s*\|/.test(s)) || fenceAt(fences, a) || fenceAt(fences, b)) {
      toast(t('한 문단 안의 이어진 줄만 합칩니다'));
      return;
    }
    const joined = [part[0].replace(/\s+$/, ''), ...part.slice(1).map((s) => s.trim())].join(' ');
    const next = [...src.slice(0, a - 1), joined, ...src.slice(b)];
    const shift = await commit(pane, pathIn(pane.view), src, next);
    if (shift != null && S.pane === pane) setLitSpan(a + shift, a + shift);
  });
}

/** 목차에서 끈 절을 옮긴다 (D121 — toc.js 의 'section-move'): 제목 줄 from 의 절을 제목 줄 to 앞으로, to 가 null 이면 문서 끝으로 */
async function moveSectionNow({ from, to }) {
  const pane = S.pane;
  if (session) await finish(true);
  if (!await settled(pane) || S.pane !== pane || blockedReadOnly(pane.tab)) return;
  const src = sourceLines();
  const m = moveSectionTo(src, from, to);
  if (m.error) {
    if (m.error !== 'same') toast(m.error === 'inside' ? t('절을 자기 안으로는 옮기지 못합니다') : whyNot(m.error));
    return;
  }
  const shift = await commit(pane, pathIn(pane.view), src, m.lines);
  if (shift == null || S.pane !== pane) return;
  followLine(m.line + shift);
}

// ---- 슬라이드 (D96) -----------------------------------------------------------------

const TEXT_LABELS = { title: t('제목'), sub: t('소제목'), body: t('본문'), table: t('표'), box: t('강조글'), code: t('코드') };

/** 현재 줄의 구성 요소 — slideops.TEXT_WORDS 의 안쪽 이름 */
function textKind(el) {
  if (el.closest('table')) return 'table';
  if (el.closest('blockquote')) return 'box';
  if (el.closest('h1, h2')) return 'title';
  if (el.closest('h3, h4, h5, h6')) return 'sub';
  if (el.closest('pre')) return 'code';
  return 'body';
}

/**
 * Ctrl+Shift+> · <: 현재 줄의 구성 요소 글자 크기를 그 장에서 1pt 키우고 줄인다 — 숨은 줄 <!-- text: 표 14 --> 를 고치거나 더한다.
 * 칸 머리 줄에 크기가 있는 칸(::: b 16)이면 그 수를 고친다. 저장은 줄 편집과 같은 길이라 Ctrl+Z 로 되돌아온다.
 */
async function resizeHere(dir) {
  const pane = S.pane;
  if (!litOpen() || !await settled(pane) || S.pane !== pane) return;
  const view = pane.view;
  const line = pane.here?.line;
  const el = line && blockOfLine(view, line);
  const wrap = el?.closest('.lec-slide-wrap');
  if (!wrap || el.closest('pre.mermaid, pre.lec-chart, .diagram-error, .math-block, .lec-tag')) {
    toast(t('이 줄은 글자 크기를 바꿀 수 없습니다 — 차트·다이어그램은 칸 크기를 따릅니다'));
    return;
  }
  const src0 = sourceLines();
  if (/^\s*!\[/.test(src0[line - 1] ?? '')) {   // 그림 줄: 폭을 20px 씩 (D116)
    const width = Math.max(40, (imageWidth(src0[line - 1]) || el.querySelector('img')?.offsetWidth || 400) + dir * 20);
    const lines = src0.slice();
    lines[line - 1] = setImageWidth(src0[line - 1], width);
    const moved = await commit(pane, pathIn(view), src0, lines);
    if (moved != null) toast(t('그림 폭 {n}px', { n: width }));   // 누를 때마다 지금 값
    return;
  }
  const kind = textKind(el);
  const cell = el.closest('.lec-cell');
  const own = parseFloat(cell?.style.fontSize);
  const shown = own || parseFloat(getComputedStyle(wrap.querySelector('.lec-slide')).getPropertyValue(`--t-${kind}`)) || 18;
  const size = Math.max(8, shown + dir);
  const [a, b] = wrap.dataset.lines.split('-').map(Number);
  const src = sourceLines();
  const next = own ? setCellSize(src, parseInt(cell.dataset.lines, 10), size) : setTextSize(src, a, b, (LANG === 'en' ? TEXT_WORDS_EN : TEXT_WORDS)[kind], size);
  const shift = await commit(pane, pathIn(view), src, next);
  if (shift == null) return;
  if (S.pane === pane) followLine(line + (sourceLines().length - src.length));
  toast(t('{kind} {n}pt', { kind: own ? t('이 칸') : TEXT_LABELS[kind], n: size }));
}

/** md 문서의 머리글 모양을 바꾼다 (D103 — 계산은 headstyle.js). then: 저장한 뒤 터미널에 넣을 요청 글 (Enter 없이) */
async function restyle({ scheme, then = '' }) {
  const pane = S.pane;
  if (!litOpen() || !await settled(pane) || S.pane !== pane) return;
  const src = sourceLines();
  const r = applyScheme(src, scheme, slugify);
  if (r.changed) {
    const shift = await commit(pane, pathIn(pane.view), src, r.lines, { numbers: false });
    if (shift == null) return;
    toast(r.links ? t('머리글 {n}개와 이 문서의 절 링크 {links}개를 바꿨습니다', { n: r.changed, links: r.links })
      : t('머리글 {n}개를 바꿨습니다', { n: r.changed }));
  } else toast(t('바꿀 머리글이 없습니다'));
  if (then) emit('term-paste', then);
}

/** 템플릿을 고르는 창을 띄운다 (slidegallery.js). 고른 템플릿, 아니면 null */
const pickTemplate = (title, group) => new Promise((resolve) => { emit('pick-template', { title, resolve, group, start: 2 }); });

/** 문서가 쓰는 템플릿 묶음 (맨 앞 설정의 templates) — 그 묶음을 먼저 연다 */
function groupOf(src) {
  const end = src[0]?.trim() === '---' ? src.findIndex((s, i) => i > 0 && s.trim() === '---') : -1;
  const m = src.slice(1, Math.max(0, end)).map((s) => /^templates:\s*(.+?)\s*$/.exec(s)).find(Boolean);
  return m ? m[1].replace(/^['"]|['"]$/g, '') : '';
}

let samples = null;   // 템플릿의 안내 글들 — 슬라이드에서 이 글을 열면 전체를 골라 둔다 (D116)

/** 슬라이드를 처음 그릴 때 안내 글을 받아 둔다 */
async function loadSamples(pane) {
  if (samples || !pane.view?.classList.contains('lec-deck')) return;
  samples = new Set();
  try {
    samples = await placeholders();
  } catch { /* 없어도 칸은 열린다 */ }
}

/** 어느 템플릿에든 있는 안내 글 — 고치지 않은 안내 글은 다른 템플릿으로 옮기지 않는다 */
async function placeholders() {
  const { groups } = await getJSON('/api/slide-templates');
  return new Set(groups.flatMap((g) => g.templates).flatMap((x) => templateLines(x.text, t('제목')).map((s) => s.trim()).filter(Boolean)));
}

/** 이 장을 템플릿으로 저장 (D101): 장의 글 그대로 Lectern 전체의 템플릿 폴더에 새 파일 하나를 만든다 */
async function saveTemplate(src, [a, b]) {
  const name = await new Promise((resolve) => { emit('ask-template-name', { resolve }); });
  if (!name) return;
  try {
    const { template } = await postJSON('/api/slide-templates', { name, text: src.slice(a - 1, b).join('\n') });
    toast(t('{group} 묶음의 {n}번 {name} 으로 저장했습니다', { group: template.group, n: template.number, name: template.name }));
  } catch (e) {
    toast(e.message);
  }
}

/** 장 더하기·복제·옮기기·지우기·배치 넣기·템플릿 ({op, dir, index, layout, style}): index 가 없으면 현재 줄의 장 */
async function slideOp({ op, dir = 0, index = null, layout = '', style = '' }) {
  const pane = S.pane;
  if (!litOpen() || !await settled(pane) || S.pane !== pane) return;
  const { view } = pane;
  const spans = [...view.querySelectorAll(':scope > .lec-slide-wrap')].map((w) => w.dataset.lines.split('-').map(Number));
  if (!spans.length) return;
  const here = pane.here?.line;
  const found = index ?? spans.findIndex(([a, b]) => here >= a && here <= b);
  const i = found < 0 ? slideAtTop(pane) : found;
  const src = sourceLines();
  if (op === 'save-template') {
    await saveTemplate(src, spans[i]);
    return;
  }
  if (op === 'pptx-style') {   // pptx 로 전환에서 고른 스타일을 문서에 적는다 (D102)
    await commit(pane, pathIn(view), src, setFrontKey(src, 'pptxStyle', style));
    return;
  }
  const chosen = op === 'add' ? await pickTemplate(t('새 장 — 템플릿을 고르세요'), groupOf(src)) : op === 'template' ? await pickTemplate(t('이 장의 템플릿을 고르세요'), groupOf(src)) : null;
  if ((op === 'add' || op === 'template') && !chosen) return;
  if (S.pane !== pane) return;
  const body = chosen && templateLines(chosen.text, t('제목'));
  const samples = op === 'template' ? await placeholders() : null;
  const r = {
    add: () => addTemplate(src, spans[i], body),
    template: () => applyTemplate(src, spans[i], body, samples),
    copy: () => duplicateSlide(src, spans[i]),
    move: () => moveSlide(src, spans, i, dir),
    delete: () => deleteSlide(src, spans, i),
    layout: () => setLayout(src, spans[i], layout, { body: t('글'), number: '0', label: t('설명') }),
  }[op]();
  if (r.error) {
    toast(r.error === 'only' ? t('장이 하나뿐이라 지우지 않습니다') : t('더 옮길 곳이 없습니다'));
    return;
  }
  if (op === 'delete' && !window.confirm(t('{n}장을 지울까요?', { n: i + 1 }))) return;
  const shift = await commit(pane, pathIn(view), src, r.lines);
  if (shift == null || S.pane !== pane) return;
  followLine(r.line + shift);
  if (op === 'add' || op === 'template') begin(r.line + shift, { select: true });   // 새 장의 제목을 바로 쓰게 — 안내 글은 치면 바뀐다
  else if (op === 'delete' || op === 'layout') toast(op === 'delete' ? t('장을 지웠습니다 — Ctrl+Z 로 되돌립니다') : t('배치를 넣었습니다 — F2 로 글을 채웁니다'));   // 복제·옮기기는 화면이 따라가 보인다 (D156)
}

// ---- 넣기 (D109~D111): 구성 요소를 고르면 표시를 대신 쓴다 --------------------------------

/** 칸의 글 범위를 기억한다 — 작은 창이 초점을 가져갔다 돌아올 때 */
function keepCaret() {
  const sel = getSelection();
  return sel.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
}

function backTo(s, range) {
  if (session !== s) return;
  focusPlace(s.cell);
  if (!range) return;
  const sel = getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

/** 칸이 있는 곳의 아래에 블록을 넣고 그 줄에서 잇는다. make(줄들, 넣을 자리) → {lines, line, select?, then?} */
async function putBlock(s, make) {
  await hold(s, async () => {
    const at = s.fresh ? s.fresh.plan.at : null;
    const res = await finish(!s.fresh);
    if (!res.ok || S.pane !== s.pane) return;
    const src = sourceLines();
    const r = make(src, at ?? blockEnd(src, s.line));
    if (r.error) {
      toast(whyNot(r.error));
      return;
    }
    const shift = await commit(s.pane, s.path, src, r.lines);
    if (shift == null || S.pane !== s.pane) return;
    const line = r.line + shift;
    followLine(line);
    if (r.then) await r.then(line);
    else await begin(line, { select: r.select ?? false });
  });
}

/** 지금 칸을 새 빈 줄로 만들어 then 을 한다 — 글이 있는 줄이면 먼저 저장하고 아래에 새 줄을 연다 */
async function onEmptyLine(s, then) {
  if (s.fresh && !read(s.places[0]).trim()) {
    then(s);
    return;
  }
  await hold(s, async () => {
    const res = await finish(true);
    if (!res.ok || S.pane !== s.pane) return;
    await beginNew(s.line, true);
    if (session) then(session);
  });
}

const encodeRef = (path) => (/[\s()]/.test(path) ? `<${path}>` : path);

/** 문서(docPath) 기준의 상대 경로 */
function refFrom(docPath, target) {
  const from = docPath.split('/').slice(0, -1);
  const to = target.split('/');
  let i = 0;
  while (i < from.length && i < to.length - 1 && from[i] === to[i]) i += 1;
  return encodeRef([...from.slice(i).map(() => '..'), ...to.slice(i)].join('/'));
}

const IMAGE = /\.(?:png|jpe?g|gif|svg|webp|bmp)$/i;
const captionOf = (word, n) => `${word} ${n}. ${t('제목')}`;
/** 캡션 줄에서 '제목' 글자를 골라 둘 자리 */
const captionPick = (word, n) => `${word} ${n}. `.length;

/**
 * 전시물의 줄 (2026-11-20 — 캡션과 주·자료): 위에 캡션 'word n. 제목', 아래에 빈 '자료: ' 줄 — 표·그림·차트·다이어그램을 넣을 때.
 * {lines, line(캡션 줄), body(몸체의 첫 줄)}. 슬라이드에서는 몸체만 넣는다 (칸이 좁고, 장 제목이 캡션을 대신하는 일이 많다)
 */
function exhibitBlock(src, at, word, body) {
  const r = insertBlock(src, at, [captionOf(word, nextCaption(src, word)), '', ...body, '', t('자료: ')]);
  return { ...r, body: r.line + 2 };
}

/** 그림 줄과 캡션 */
const imageBlock = (src, at, ref, alt) => {
  if (deckOn(S.pane.view)) return insertBlock(src, at, [`![w:400 ${alt}](${ref})`]);   // 슬라이드는 칸이 캡션 자리까지 정한다
  const n = nextCaption(src, t('그림'));
  const r = exhibitBlock(src, at, t('그림'), [`![${alt}](${ref})`]);
  return { lines: r.lines, line: r.line, select: captionPick(t('그림'), n) };
};

async function putTable(s) {
  const at = s.places[0].span;
  const keep = keepCaret();
  const size = await askText({ title: t('표 크기 — 열 x 행'), at, value: '3x3', placeholder: '3x3' });
  if (size == null) {
    backTo(s, keep);
    return;
  }
  const m = /(\d+)\s*[x×*,]\s*(\d+)/i.exec(size);
  if (!m || +m[1] < 1 || +m[2] < 1 || +m[1] > 30 || +m[2] > 500) {
    toast(t('표 크기는 3x4 처럼 쓰세요 — 열은 30, 행은 500 까지입니다'));
    backTo(s, keep);
    return;
  }
  await putBlock(s, (src, line) => {
    if (deckOn(s.pane.view)) return insertBlock(src, line, makeTable(+m[1], +m[2]));
    const n = nextCaption(src, t('표'));
    const r = exhibitBlock(src, line, t('표'), makeTable(+m[1], +m[2]));
    return { lines: r.lines, line: r.line, select: captionPick(t('표'), n) };
  });
}

async function putImage(s) {
  const at = s.places[0].span;
  const keep = keepCaret();
  const files = await projectFiles((f) => IMAGE.test(f.name));
  if (!files.length) {
    toast(t('프로젝트에 그림 파일이 없습니다 — 그림을 복사해서 Ctrl+V 로 붙여 넣으세요'));
    backTo(s, keep);
    return;
  }
  const chosen = await pick({ items: files.map((f) => ({ id: f.path, name: f.name, sub: f.path })), title: t('넣을 그림'), at });
  if (!chosen) {
    backTo(s, keep);
    return;
  }
  await putBlock(s, (src, line) => imageBlock(src, line, refFrom(s.path, chosen.id), chosen.name.replace(/\.\w+$/, '')));
}

async function putAttach(s) {
  const at = s.places[0].span;
  const keep = keepCaret();
  const files = await projectFiles((f) => f.path !== s.path);
  const chosen = await pick({ items: files.map((f) => ({ id: f.path, name: labelOf(f), sub: f.path })), title: t('첨부할 파일 — 프로젝트 안에서'), at });
  if (!chosen) {
    backTo(s, keep);
    return;
  }
  await putBlock(s, (src) => {
    const r = addAttachment(src, `[${chosen.name}](${refFrom(s.path, chosen.id)})`, t('붙임'));
    return { ...r, then: () => toast(t('붙임 절에 넣었습니다: {name}', { name: chosen.name })) };
  });
}

/** 블록을 넣고 펼쳐서 고치게 한다 (수식·다이어그램·차트 — D112). 다이어그램·차트는 문서에서 위에 그림 캡션, 아래에 '자료: ' 줄 (슬라이드는 블록만) */
const fencedBlock = (body, exhibit = false) => (src, line) => {
  if (!exhibit || deckOn(S.pane.view)) {
    const r = insertBlock(src, line, body);
    return { ...r, then: (at) => unfold(at) };
  }
  const r = exhibitBlock(src, line, t('그림'), body);
  return { lines: r.lines, line: r.body, then: (at) => unfold(at) };
};

const SAMPLES = {
  chart: () => chartFromTable([t('항목'), t('값')], [['A', '3'], ['B', '5'], ['C', '4']]).lines,
  diagram: () => ['```mermaid', 'graph TD', '  A --> B', '```'],
  math: () => ['$$', 'x^2', '$$'],
};

/** 상태줄의 '원문 줄 보기' (D112): md 문서를 코드 화면으로 — 빈 줄·주석까지 모든 줄을 칸으로 고치는 안전망 */
function showSource() {
  const view = S.pane?.view;
  const path = view && pathIn(view);
  const btn = $('#lec-st-source');
  btn.hidden = !path || !isMd(path) || !!S.tab?.readonly;
  btn.textContent = view && isCodeView(view) ? t('md 문서로 보기') : t('원문 줄 보기');
}

/** 줄 line 이 든 블록을 펼치고 첫 줄을 연다 (D112) */
async function unfold(line) {
  const pane = S.pane;
  if (!openBlock(pane, line)) return;
  releasePick();
  await nap();
  await settled(pane);
  const fold = pane.unfold;
  if (!fold?.a || fold.values) return;   // 값 표는 칸이 스스로 초점을 받는다
  followLine(fold.a);
  await begin(fold.a);
}

/** 찾아 바꾸기 (Ctrl+H — find.js): 원문에서 글자 그대로 찾아 바꾼다. all: 모두 (되돌리기 한 걸음), 아니면 현재 줄 뒤의 첫 곳 */
async function replaceNow({ find, to, all }) {
  const pane = S.pane;
  if (!find || !litOpen() || !await settled(pane) || S.pane !== pane) return;
  const src = sourceLines();
  const start = src[0]?.trim() === '---' ? src.findIndex((s, i) => i > 0 && s.trim() === '---') + 1 : 0;
  const re = new RegExp(find.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  const next = src.slice();
  let count = 0;
  let line = 0;
  const wall = deckOn(pane.view) ? (s) => /^\s*(?:<!--|:::)/.test(s) : () => false;
  if (all) {
    for (let i = start; i < next.length; i++) {
      if (wall(next[i])) continue;
      next[i] = next[i].replace(re, () => {
        count += 1;
        line ||= i + 1;
        return to;
      });
    }
  } else {
    const from = Math.max(start, (pane.here?.line ?? 1) - 1);
    const order = [...Array(next.length - start).keys()].map((k) => start + ((k + from - start) % (next.length - start)));
    const i = order.find((n) => !wall(next[n]) && next[n].search(re) >= 0);
    if (i != null) {
      re.lastIndex = 0;
      next[i] = next[i].replace(new RegExp(re.source, 'i'), () => to);
      count = 1;
      line = i + 1;
    }
  }
  if (!count) {
    toast(t('찾은 글이 없습니다'));
    return;
  }
  const shift = await commit(pane, pathIn(pane.view), src, next);
  if (shift == null || S.pane !== pane) return;
  followLine(line + shift);
  toast(t('{n}곳을 바꿨습니다', { n: count }));
}

/**
 * 보내기 (D113): 문서에 글을 바로 넣는다 — 편집 모드를 열지 않는다. compute(문서 글) → {line, ch, text, offset, size}.
 * 저장은 replaceLines 그대로라 되돌리기 한 걸음이다. 넣었으면 true
 */
export async function insertLines(pane, path, compute) {
  if (session) await finish(true);
  if (!await settled(pane) || S.pane !== pane || blockedReadOnly(pane.tab)) return false;
  const src = sourceLines();
  const put = compute(src.join('\n'));
  if (!put) return false;
  const at = src.slice(0, put.line).join('\n').length + (put.line ? 1 : 0) + put.ch;
  const text = src.join('\n');
  const next = `${text.slice(0, at)}${put.text}${text.slice(at)}`.split('\n');
  const shift = await commit(pane, path, src, next);
  if (shift == null) return false;
  if (S.pane === pane) followLine(put.line + (put.text.slice(0, put.offset).match(/\n/g)?.length ?? 0) + 1 + shift);
  return true;
}

/** 고른 구성 요소를 칸 s 의 자리에 넣는다 */
async function putItem(s, id) {
  if (id === 'table') await putTable(s);
  else if (id === 'image') await putImage(s);
  else if (id === 'attach') await putAttach(s);
  else if (id === 'note') await noteHere();
  else if (id === 'speaker') await speakerNote(s);
  else if (id === 'link') await linkHere();
  else if (id === 'date') await dateHere();
  else if (id === 'chars') await charFromPut(s);
  else if (SAMPLES[id]) await putBlock(s, fencedBlock(SAMPLES[id](), id === 'chart' || id === 'diagram'));
  else if (id === 'code') await putBlock(s, (src, line) => { const r = insertBlock(src, line, ['```', '', '```']); return { ...r, line: r.line + 1 }; });
  else if (id === 'rule') await putBlock(s, (src, line) => ({ ...insertBlock(src, line, ['---']), then: (at) => beginNew(at, true) }));
  else if (id === 'textbox') await putBlock(s, (src, line) => {   // 박스글 (D126) — 제목 줄에서 고치기 시작한다
    if (textboxesAround(src, line)) return { error: 'in-textbox' };
    const r = insertBlock(src, line, makeTextbox(t('박스'), nextCaption(src, t('박스')), t('제목'), t('여기에 내용을 씁니다.')));
    return { ...r, line: r.line + 1 };
  });
  else if (id === 'pagebreak') await putBlock(s, (src, line) => ({ ...insertBlock(src, line, [PAGE_BREAK]), then: (at) => beginNew(at, true) }));
  else if (id === 'toc' || id === 'tables' || id === 'figures') await putBlock(s, (src, line) => ({ ...insertBlock(src, line, [tocLine(id, LANG === 'en')]), then: (at) => beginNew(at, true) }));
  else if (id === 'ref') await putRef(s);
  else if (id === 'cite') await putCite(s);
  else if (id === 'appendix') {
    await putBlock(s, (src, line) => {
      const head = `${t('부록 {x}.', { x: nextAppendix(src) })} `;
      const r = insertBlock(src, line, [`## ${head}${t('제목')}`]);
      return { ...r, select: head.length };
    });
  } else if (id === 'source' || id === 'tablenote') {
    await onEmptyLine(s, (x) => {
      x.places[0].span.textContent = id === 'source' ? t('자료: ') : t('주: ');
      focusPlace(0);
    });
  } else await onEmptyLine(s, (x) => freshKind(x, id));
}

/** 상호 참조 (D121): 표·그림의 캡션이나 절을 골라 그 자리에 링크를 넣는다 — '[표 3](#표-3)'. 번호가 바뀌면 저장할 때 함께 고친다 */
async function putRef(s) {
  const at = s.places[s.cell].span;
  const keep = keepCaret();
  const all = refTargets(sourceLines(), slugify);
  const caps = all.filter((x) => x.kind === 'caption').sort((a, b) => a.word.localeCompare(b.word) || a.n - b.n);
  const targets = [...caps, ...all.filter((x) => x.kind === 'section')];
  if (!targets.length) {
    backTo(s, keep);
    toast(t('가리킬 표·그림·절이 없습니다 — 캡션(표 1. 제목)이나 제목을 먼저 쓰세요'));
    return;
  }
  const items = targets.map((x, i) => ({ id: String(i), name: x.name, group: x.kind === 'caption' ? t('표·그림') : t('절'), sub: rangeText([x.line, x.line]) }));
  const chosen = await pick({ items, title: t('상호 참조'), at });
  backTo(s, keep);
  if (!chosen || session !== s) return;
  document.execCommand('insertText', false, targets[Number(chosen.id)].text);
}

/** 본문 인용 (D121): 참고문헌 절의 문헌을 골라 '(김영삼, 2026)' 을 넣는다. 본문에 아직 안 쓴 문헌을 함께 보인다 */
async function putCite(s) {
  const at = s.places[s.cell].span;
  const keep = keepCaret();
  const src = sourceLines();
  const refs = referencesIn(src);
  if (!refs.length) {
    backTo(s, keep);
    toast(t('참고문헌 절이 없습니다 — \'## 참고문헌\' 아래에 문헌을 목록으로 쓰면 고를 수 있습니다'));
    return;
  }
  const used = refs.map((r) => citedCount(src, r.text));
  const items = refs.map((r, i) => ({ id: String(i), name: r.text, sub: `${citeOf(r.text).cite} · ${used[i] ? t('본문 {n}곳', { n: used[i] }) : t('아직 안 씀')}` }));
  const unused = used.filter((x) => !x).length;
  const title = unused ? t('본문 인용 — 문헌 {n}개 가운데 {m}개는 본문에 아직 없습니다', { n: refs.length, m: unused }) : t('본문 인용');
  const chosen = await pick({ items, title, at });
  backTo(s, keep);
  if (!chosen || session !== s) return;
  document.execCommand('insertText', false, citeOf(refs[Number(chosen.id)].text).cite);
}

/** `/`·Ctrl+Shift+/: 넣기 창 (D109). 고른 것을 넣고, 그만두면 칸으로 돌아온다 */
async function openPut() {
  const s = session;
  const keep = keepCaret();
  const chosen = await pick({ items: putItems(deckOn(s.pane.view)), title: t('넣기'), at: s.places[s.cell].span, board: true });
  if (session !== s) return;
  if (chosen) await putItem(s, chosen.id);
  else backTo(s, keep);
}

/** Ctrl+;: 날짜 넣기 (D149 — 달력 입력). 달력에서 고른 날을 'YYYY-MM-DD' 로 커서 자리에 — 할 일 줄 끝의 (기한)·일정 줄의 날짜 */
async function dateHere() {
  const s = session;
  if (!s) return;
  const span = s.places[s.cell].span;
  const keep = keepCaret();
  const day = await pickDate({ at: span, title: t('날짜 넣기') });
  backTo(s, keep);
  if (!day || session !== s) return;
  document.execCommand('insertText', false, day);
}

/** Ctrl+Shift+;: 특수 문자 넣기 (D165 — charpick.js). 고른 문자를 커서 자리에 (고른 글이 있으면 그 자리를 바꾼다) */
async function charHere() {
  const s = session;
  if (!s) return;
  const span = s.places[s.cell].span;
  const keep = keepCaret();
  const c = await pickChar({ at: span, title: t('특수 문자 넣기') });
  backTo(s, keep);
  if (!c || session !== s) return;
  document.execCommand('insertText', false, c);
}

let putFrom = null;   // 읽는 화면의 / 로 연 넣기 창이면 그 현재 줄 (putBelow) — '특수 문자' 는 아래 새 줄이 아니라 그 줄 끝에 넣는다 (D165)

/**
 * 넣기 창의 '특수 문자' (D165): 칸 안에서 열었으면 커서 자리에. 읽는 화면에서 열었으면(아래에 연 빈 새 줄) 그 새 줄은 넣지 않고
 * 현재 줄의 칸을 열어 그 끝에 — 문자는 글 속에 넣는 것이다
 */
async function charFromPut(s) {
  const from = putFrom;
  if (from != null && s.fresh && !read(s.places[0]).trim()) {
    await finish(false);
    if (session) return;
    await begin(from);
    if (!session) return;
  }
  await charHere();
}

/** 읽는 화면의 Ctrl+Shift+; (spotlight.js 의 'line-chars', D165): 현재 줄의 칸을 열고 그 끝에 특수 문자를 */
async function charsAtLine() {
  const pane = S.pane;
  if (!pane?.view || session || pane.lineEditHold || pane.unfold) return;
  if (pane.tab && blockedReadOnly(pane.tab)) return;
  const line = pane.here?.line;
  if (!line || !linesEditable() || !pathIn(pane.view) || !textOn(pane.view)) return;
  stopSpotlight();
  await begin(line);
  if (session) await charHere();
}

/** Ctrl+K: 링크 — 프로젝트의 파일을 고르거나 주소를 쓴다. 고른 글이 있으면 그 글에 건다 */
async function linkHere() {
  const s = session;
  if (!s || s.kind !== 'text') return;
  const span = s.places[s.cell].span;
  const keep = keepCaret();
  const shown = getSelection().toString();
  const files = await projectFiles();
  const r = await pick({ items: files.map((f) => ({ id: f.path, name: labelOf(f), sub: f.path })), title: t('링크'), at: span, free: true, placeholder: t('파일 이름으로 거르거나 주소를 쓰세요') });
  backTo(s, keep);
  if (!r || session !== s) return;
  const target = r.id ? refFrom(s.path, r.id) : r.text;
  document.execCommand('insertText', false, `[${shown || r.name || r.text}](${target})`);
}

/** Ctrl+Alt+F: 글자 자리에 주를 단다 (D110). 주 표시 위면 그 주를 고친다. 본문과 내용을 한 번에 저장한다 */
async function noteHere() {
  const s = session;
  if (!s || s.kind !== 'text') return;
  const { span } = s.places[0];
  const body = read(s.places[0]);
  if (!body.trim()) {
    toast(t('주는 글에 답니다 — 글을 쓴 뒤 누르세요'));
    return;
  }
  const offset = caretOffset(span) ?? body.length;
  const label = noteAt(body, offset);
  const keep = keepCaret();
  const old = label ? noteText(sourceLines(), label)?.text ?? '' : '';
  const text = await askText({ title: label ? t('주 고치기') : t('주 내용'), at: span, value: old, placeholder: t('주 내용을 쓰고 Enter') });
  backTo(s, keep);
  if (text == null || !text.trim() || session !== s) return;
  await hold(s, async () => {
    const res = await finish(true);
    if (!res.ok || S.pane !== s.pane) return;
    const src = sourceLines();
    const col = splitText(src[s.line - 1]).head.length + offset;
    const r = label ? { lines: setNote(src, label, text.trim()), line: s.line } : addNote(src, s.line, col, text.trim());
    const shift = await commit(s.pane, s.path, src, r.lines);
    if (shift == null) return;
    followLine(r.line + shift);
    await begin(r.line + shift, { offset: label ? offset : offset + `[^${r.label}]`.length });
  });
}

/** 고른 글을 표시로 감싼다 (Ctrl+B·I·`). 고른 글이 없으면 표시 사이에 커서를 둔다 */
/** 칸 안에서 고른 글의 자리 [a, b] (글자 수 — 커서면 a = b). 칸 밖이면 null */
function selOffsets(span) {
  const sel = getSelection();
  if (!sel.rangeCount) return null;
  const r = sel.getRangeAt(0);
  if (!span.contains(r.startContainer) || !span.contains(r.endContainer)) return null;
  const pre = document.createRange();
  pre.selectNodeContents(span);
  pre.setEnd(r.startContainer, r.startOffset);
  const a = pre.toString().length;
  return [a, a + r.toString().length];
}

/** 칸의 글에서 글자 자리 a~b 의 범위 — 글 노드가 여럿이어도 (없으면 null) */
function rangeIn(span, a, b) {
  const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT);
  const r = document.createRange();
  let at = 0;
  let started = false;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const len = node.nodeValue.length;
    if (!started && a <= at + len) {
      r.setStart(node, a - at);
      started = true;
    }
    if (started && b <= at + len) {
      r.setEnd(node, b - at);
      return r;
    }
    at += len;
  }
  if (a !== 0 || b !== 0) return null;
  r.selectNodeContents(span);   // 빈 칸
  return r;
}

/**
 * 칸의 글에서 고른 곳(없으면 커서 자리, whole 이면 칸의 글 통째)에 서식을 한다 (D141 — 계산은 inlinefmt.js).
 * kind: bold·italic·strike·code·mark·color·clear(모두 풀기). 칸의 글을 insertText 로 바꿔 칸의 Ctrl+Z 한 걸음으로 남는다
 * @param {HTMLElement} span
 * @param {string} kind
 * @param {{ value?: string, whole?: boolean }} [opt] value: 형광펜·글자색의 색 (없으면 다음 색), whole: 고른 글이 없으면 칸의 글 통째에
 */
function formatHere(span, kind, { value, whole = false } = {}) {
  const at = selOffsets(span);
  if (!at) return;
  const text = span.textContent;
  const [a, b] = whole && at[0] === at[1] ? [0, text.length] : at;
  const r = kind === 'clear' ? clearFormats(text, a, b) : applyFormat(text, a, b, kind, value);
  if (r.text === text) return;
  const sel = getSelection();
  sel.selectAllChildren(span);
  document.execCommand('insertText', false, r.text);
  const back = rangeIn(span, r.a, r.b);
  if (back) {
    sel.removeAllRanges();
    sel.addRange(back);
  }
  paintCells();
}

/**
 * 칸 안에서 서식이 보이게 한다 (D141): 글자는 원문 그대로 두고 모양만 입힌다 — 굵게는 굵게, 색은 그 색, 형광펜은 바탕, 취소선은 줄,
 * 표시 글자(** · <mark> …)는 흐리게. CSS Custom Highlight 라 칸의 DOM 은 바뀌지 않는다 (base.css 의 ::highlight(lec-fmt-…)).
 * 기울임은 이 방식으로 글자를 기울일 수 없어 물결 밑줄이다
 */
function paintCells() {
  paintRaf = 0;
  const registry = /** @type {any} */ (globalThis).CSS?.highlights;
  const Mark = /** @type {any} */ (globalThis).Highlight;
  if (!registry || !Mark) return;
  /** @type {Record<string, Range[]>} */
  const found = {};
  if (session && session.kind !== 'code') {
    for (const p of session.places) {
      const text = p.span.textContent;
      if (!/[*~`<]/.test(text)) continue;
      for (const [name, list] of Object.entries(paintOf(text))) {
        for (const [a, b] of list) {
          const r = rangeIn(p.span, a, b);
          if (r) (found[name] ||= []).push(r);
        }
      }
    }
  }
  for (const name of FMT_PAINT) {
    if (found[name]) registry.set(`lec-fmt-${name}`, new Mark(...found[name]));
    else registry.delete(`lec-fmt-${name}`);
  }
}

/** 다음 그리기 때 칸의 서식을 다시 칠한다 — 글을 칠 때마다, 칸을 열고 닫을 때 */
function paintSoon() {
  if (!paintRaf) paintRaf = requestAnimationFrame(paintCells);
}

let cellMenuOpen = false;

/**
 * 칸 안의 우클릭 (D141): 서식의 선택 상자 — 키를 몰라도 쓰게, 항목 옆에 키를 보인다. 고른 글에 하고, 고른 글이 없으면 칸의 글 통째에.
 * 고르면 상자가 닫히고 고른 글과 커서가 그대로 남아 이어서 쓴다 (서식 막대는 두지 않는다 — 사용자 결정)
 */
function onCellMenu(e) {
  e.stopPropagation();
  const s = session;
  const span = e.currentTarget;
  if (!s || !textOn(s.pane.view) || (s.kind !== 'text' && s.kind !== 'table') || span.closest('.lec-tag')) return;
  e.preventDefault();
  if (!selOffsets(span)) focusPlace(Number(span.dataset.i) || 0);
  const keep = keepCaret();
  const picked = !!getSelection().toString();
  const run = (kind, value) => () => {
    backTo(s, keep);
    if (session === s) formatHere(span, kind, { value, whole: true });
  };
  const marks = [['', t('노랑')], ['green', t('초록')], ['pink', t('분홍')], ['blue', t('하늘')]];
  const colors = [['red', t('빨강')], ['blue', t('파랑')], ['green', t('초록')], ['goldenrod', t('노랑')]];
  cellMenuOpen = true;
  showMenu(e.clientX, e.clientY, [
    { header: picked ? t('고른 글의 서식') : t('이 줄의 서식') },
    { label: t('굵게'), hint: 'Ctrl+B', action: run('bold') },
    { label: t('기울임'), hint: 'Ctrl+I', action: run('italic') },
    { label: t('취소선'), hint: 'Ctrl+Shift+X', action: run('strike') },
    { label: t('코드'), hint: 'Ctrl+`', action: run('code') },
    '-',
    ...marks.map(([v, name], i) => ({ label: t('형광펜 — {color}', { color: name }), hint: i ? '' : 'Ctrl+Shift+H', tip: t('같은 색을 다시 고르면 풉니다. 키는 거듭 누르면 다음 색'), action: run('mark', v) })),
    '-',
    ...colors.map(([v, name], i) => ({ label: t('글자색 — {color}', { color: name }), hint: i ? '' : 'Ctrl+Shift+C', tip: t('같은 색을 다시 고르면 풉니다. 키는 거듭 누르면 다음 색'), action: run('color', v) })),
    '-',
    ...(s.kind === 'text' ? [{ label: t('링크…'), hint: 'Ctrl+K', action: () => { backTo(s, keep); linkHere(); } },
      { label: t('주…'), hint: 'Ctrl+Alt+F', action: () => { backTo(s, keep); noteHere(); } }] : []),
    { label: t('특수 문자…'), hint: 'Ctrl+Shift+;', tip: t('문장 부호·화살표·단위·원 숫자 같은 문자를 커서 자리에'), action: () => { backTo(s, keep); charHere(); } },
    { label: t('서식 풀기'), tip: t('고른 곳의 굵게·색·형광펜 같은 서식을 모두'), action: run('clear') },
  ], () => {
    cellMenuOpen = false;
    if (session === s && !document.activeElement?.closest?.('.lec-line-edit')) backTo(s, keep);   // Esc 로 닫아도 칸으로 돌아온다
  });
}

/** 칸의 줄 앞의 목록 표시 — 붙여 넣은 줄도 같은 표시로 */
const itemHead = (line) => /^[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+(?:\[[ xX]\][ \t]+)?/.exec(line)?.[0] ?? '';

/** 칸에 여러 줄을 붙여 넣는다 (D109): 줄마다 나눠 넣고 되돌리기 한 걸음. 엑셀 범위는 표로 */
async function pasteHere(text) {
  const s = session;
  const { span } = s.places[0];
  if (!getSelection().isCollapsed) document.execCommand('delete');
  const body = read(s.places[0]);
  const offset = caretOffset(span) ?? body.length;
  const rows = rowsFromTsv(text);
  if (rows && s.kind === 'text') {
    await putBlock(s, (src, line) => insertBlock(src, line, tableFromRows(rows)));
    return;
  }
  const pasted = text.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n');
  const rest = pasted.slice(1);
  rest[rest.length - 1] += body.slice(offset);
  const first = `${body.slice(0, offset)}${pasted[0]}`;
  await hold(s, async () => {
    const src = s.fresh ? s.fresh.lines : sourceLines();
    const made = s.fresh ? insertLine(src, s.fresh.plan, first) : null;
    const base = made ? made.lines : src.map((x, i) => (i === s.line - 1 ? `${s.parts.head}${first}${s.parts.tail}` : x));
    const n = made ? made.line : s.line;
    const r = pasteAfter(base, n, rest, s.kind === 'text' ? itemHead(base[n - 1]) : '');
    await finish(false);
    const shift = await commit(s.pane, s.path, src, r.lines);
    if (shift == null) return;
    followLine(r.line + shift);
    await begin(r.line + shift);
  });
}

// ---- 그림 붙여 넣기 (D111) ---------------------------------------------------------------

const imageIn = (data) => [...(data?.files ?? [])].find((f) => /^image\/(?:png|jpeg|gif|webp)$/.test(f.type)) ?? null;

const base64Of = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
  reader.onerror = () => reject(reader.error);
  reader.readAsDataURL(file);
});

/** 그림 파일을 문서 옆 폴더에 저장하고 지금 자리에 넣는다 — 사용자가 붙여 넣거나 끌어 넣을 때만 */
async function putImageFile(file) {
  const pane = S.pane;
  const s = session;
  const path = s?.path ?? pane.view.dataset.docPath;
  let saved;
  try {
    saved = await postJSON('/api/paste-image', { p: pane.tab.id, doc: path, data: await base64Of(file) });
  } catch (e) {
    toast(e.message, 'error');
    return;
  }
  const make = (src, line) => imageBlock(src, line, refFrom(path, saved.path), t('그림'));
  if (s && session === s) {
    await putBlock(s, make);
    return;
  }
  turn = turn.then(async () => {
    if (!await settled(pane) || S.pane !== pane) return;
    const src = sourceLines();
    const here = litSpan()?.[1] ?? pane.here?.line;   // 잡은 줄·한 줄의 하이라이트면 그 줄 (여러 줄을 골랐으면 받지 않는다 — D139)
    const r = make(src, here ? blockEnd(src, here) : 0);
    const shift = await commit(pane, path, src, r.lines);
    if (shift == null || S.pane !== pane) return;
    followLine(r.line + shift);
    await begin(r.line + shift, { select: r.select });
  });
}

// ---- 메뉴 (docmenu.js) -----------------------------------------------------------------

/** 칸이 없을 때 문서 줄에 계산 op 를 한다 — 되돌리기 한 걸음. after: 저장한 뒤 */
function menuOp(op, after = null) {
  turn = turn.then(async () => {
    const pane = S.pane;
    if (!litOpen() || !await settled(pane) || S.pane !== pane) return;
    const src = sourceLines();
    const r = op(src);
    if (r.error) {
      toast(whyNot(r.error));
      return;
    }
    if (r.ask && !window.confirm(r.ask)) return;
    const shift = await commit(pane, pathIn(pane.view), src, r.lines, { note: r.note || '' });
    if (shift == null || S.pane !== pane) return;
    followLine(Math.max(1, r.line + shift));
    after?.(r.line + shift, r);
  });
}

/** 메뉴의 '여기에 넣기…'·'이 줄 바꾸기…' 를 칸 없이 쓸 때: 그 줄 아래에 새 줄을 열고 고른다 */
async function putBelow(line, target) {
  await beginNew(line, true, { end: !!target.closest?.(`${ATOMIC}, img, table, pre`), after: true });   // 표·코드 블록의 줄이면 그 블록 아래에 — 행·코드 줄을 더하는 것은 Shift+Enter (D158·D164 — 문서 끝에서도 같다)
  if (!session) return;
  putFrom = line;
  try {
    await openPut();
  } finally {
    putFrom = null;
  }
}

/** 현재 줄의 '/'·Ctrl+Shift+/ (D139 — spotlight.js 의 putKey): 그 줄 아래에 새 줄을 열고 넣기 창을 연다. 우클릭 '여기에 넣기…' 와 같다 */
async function putHere() {
  const pane = S.pane;
  const view = pane?.view;
  if (!view || session || pane.lineEditHold || pane.unfold) return;
  if (pane.tab && blockedReadOnly(pane.tab)) return;
  if (!linesEditable() || !pathIn(view) || !textOn(view)) return;
  const line = litSpan()?.[1] ?? pane.here?.line;
  stopSpotlight();
  if (!line) {
    growEnd();
    return;
  }
  await putBelow(line, blockOfLine(view, line) ?? view);
}

/** 지금 칸이 든 장의 줄 범위 */
function slideSpan(line) {
  const wrap = blockOfLine(S.pane.view, line)?.closest?.('.lec-slide-wrap');
  return wrap?.dataset.lines?.split('-').map(Number) ?? null;
}

/** 발표자 노트를 쓴다 (D116) — 장 끝의 주석 한 줄. pptx 의 노트로 간다 */
async function speakerNote(s) {
  const span = slideSpan(s.line);
  if (!span) return;
  const old = noteOf(sourceLines(), span)?.text ?? '';
  const text = await askText({ title: t('발표자 노트'), at: s.places[0].span, value: old, placeholder: t('노트를 쓰고 Enter') });
  if (text == null || session !== s) return;
  await hold(s, async () => {
    await finish(!s.fresh);
    const src = sourceLines();
    const shift = await commit(s.pane, s.path, src, setSlideNote(src, slideSpan(s.line) ?? span, text).lines);
    if (shift != null) toast(t('노트를 저장했습니다 — 구조 보기에서 봅니다'));
  });
}

/** 메뉴의 노트 쓰기 — 칸 없이 */
async function noteMenu(wrap) {
  const span = wrap.dataset.lines.split('-').map(Number);
  const text = await askText({ title: t('발표자 노트'), at: wrap, value: noteOf(sourceLines(), span)?.text ?? '', placeholder: t('노트를 쓰고 Enter') });
  if (text != null) menuOp((src) => setSlideNote(src, span, text));
}

/** 패널의 차트 원문에 op(글 → 글)을 한다 (D115) */
function fenceOp(pane, op) {
  turn = turn.then(async () => {
    const u = pane.unfold;
    if (!u?.a || S.pane !== pane || !await settled(pane) || !linesEditable()) return;
    const src = sourceLines();
    const next = op(src.slice(u.a - 1, u.b).join('\n'));
    if (next == null) {
      toast(t('이 차트는 바꿀 수 없습니다 — 원문으로 고치세요'));
      return;
    }
    await commit(pane, pathIn(pane.view), src, [...src.slice(0, u.a - 1), ...next.split('\n'), ...src.slice(u.b)]);
  });
}

/** 칸의 표를 같은 값의 차트로 바꾼다 (D115) */
function tableToChart(line, table) {
  const [headers, ...rows] = [...table.rows].map((r) => [...r.cells].map((c) => c.textContent.trim()));
  const made = chartFromTable(headers, rows, { series: t('구분'), value: t('값') });
  menuOp((src) => {
    if (made.error) return made;
    const span = tableSpan(src, line);
    if (!span) return { error: 'not-table' };
    const out = [...src.slice(0, span[0] - 1), ...made.lines, ...src.slice(span[1])];
    // 표의 캡션은 차트의 캡션으로 — 차트는 '그림' 캡션만 받는다 (번호는 저장할 때 차례대로 맞춘다 — D121)
    const cap = captionAbove(src, tableAt(src, line)?.head ?? 0);
    const word = cap ? captionAt(src[cap - 1])?.word : '';
    if (word === '표' || word === 'Table') {   // i18n-ok (원문의 캡션 낱말)
      const fig = word === '표' ? '그림' : 'Figure';   // i18n-ok (원문의 캡션 낱말)
      out[cap - 1] = src[cap - 1].replace(/(표|Table)([ \t]*)\d{1,4}/, `${fig}$2${nextCaption(src, fig)}`);
    }
    return { lines: out, line: span[0] };
  });
}

/** 칸에서 넘친 첫 줄 — 칸 아래로 나간 줄 단위 */
function overflowLine(cell) {
  const bottom = cell.getBoundingClientRect().bottom;
  return currentUnits().find((u) => cell.contains(u.el) && (u.range ?? u.el).getBoundingClientRect().bottom > bottom + 1)?.a ?? 0;
}

const LOOKS = () => [['', t('없음')], ['card', t('상자')], ['accent', t('강조')], ['dark', t('어두운 상자')], ['note', t('메모')], ['kpi', t('큰 숫자')]];

/** 슬라이드의 칸 메뉴 (D116) */
function cellItems(target, line) {
  const cell = target.closest?.('.lec-cell');
  const wrap = target.closest?.('.lec-slide-wrap');
  if (!wrap) return [];
  const span = wrap.dataset.lines.split('-').map(Number);
  /** @type {MenuItem[]} */
  const items = [];
  if (cell && line) {
    const run = (op) => () => menuOp(op);
    items.push({ label: t('칸 꾸밈…'), tip: t('상자, 강조, 메모 같은 모양'), action: async () => {
      const chosen = await pick({ items: LOOKS().map(([id, name]) => ({ id: id || 'none', name })), title: t('칸 꾸밈'), at: cell });
      if (chosen) menuOp((src) => setCellLook(src, line, chosen.id === 'none' ? '' : chosen.id));
    } },
    { label: t('이 칸을 앞으로'), tip: t('글을 앞 칸과 맞바꿉니다'), action: run((x) => swapCell(x, span, line, -1)) },
    { label: t('이 칸을 뒤로'), tip: t('글을 뒤 칸과 맞바꿉니다'), action: run((x) => swapCell(x, span, line, 1)) },
    { label: t('칸 비우기'), action: run((x) => {
      const r = clearCell(x, line);
      return r.error ? r : { ...r, ask: t('이 칸의 글을 지울까요?') };
    }) });
    if (cell.classList.contains('lec-cell-over')) {
      const at = overflowLine(cell);
      if (at) items.push({ label: t('넘친 줄을 다음 장으로'), tip: t('같은 배치의 새 장으로 옮깁니다'), action: run((x) => splitCell(x, span, at, t('(이어서)'))) });
      items.push({ label: t('이 칸 줄이기 요청'), tip: t('터미널에 (Enter 는 누르지 않음)'), action: () => emit('term-paste', t('@{path} {line}행의 칸 글이 넘칩니다. 뜻을 지키며 칸에 맞게 줄여 주세요. 고치기 전에 어떻게 바꿀지 먼저 보여 주세요.', { path: S.pane.view.dataset.docPath, line })) });
    }
  }
  items.push({ label: t('발표자 노트 쓰기…'), tip: t('pptx 의 노트로 갑니다'), action: () => noteMenu(wrap) });
  return items;
}

/** 메뉴의 '이 줄 바꾸기…' (칸 없이 — 그 줄 하나) */
function changeLine(line, at) {
  openChange(line, line, at, false);
}

/** 줄 at 뒤에 넣으면 박스글 안인지 — 여는 줄부터 끝 줄 앞까지 */
const textboxesAround = (src, at) => { const box = textboxAt(src, at); return !!box && at < box.end; };

/** 고른 줄을 바꾼다 (우클릭 — docmenu.js): 문단 여러 개를 목록·강조글로, 고른 줄을 박스글로 (D126 — 슬라이드에는 없다) */
export const pickedItems = () => (litSpan() && S.pane?.view && textOn(S.pane.view) ? [
  ...(litOneLine() ? [{ label: t('아래에 넣기…'), hint: '/', tip: t('이 줄 아래에'), action: putPicked }] : []),   // 넣기는 한 줄(현재 줄)에서만 (D139)
  { label: litOneLine() ? t('이 줄 바꾸기…') : t('고른 줄 바꾸기…'), hint: '.', tip: t('제목·문단·목록·인용·강조글, 표·코드로'), action: changeLit },
  ...(deckOn(S.pane.view) ? [] : [{ label: t('박스글로 묶기'), tip: t('고른 줄을 본문과 따로 읽는 상자로'), action: wrapLit }, askTextboxItem(litSpan()[1])])] : []);

/**
 * 'Claude 에 박스글 요청' (D126): 지금까지의 대화를 정리해 줄 after 뒤에 박스글로 넣어 달라는 요청 글을 터미널에 넣는다 — Enter 는 사용자가 (D51).
 * 파일을 쓰는 것은 터미널의 Claude Code 다 (원칙 1 의 터미널 예외) — Lectern 은 자리와 규칙을 적어 줄 뿐이다. 자리는 그 줄이 든 블록의 끝, 박스글 안이면 그 박스글의 끝.
 * 요청 글은 한 줄이다 — 여러 줄이면 셸 프롬프트에서 줄마다 명령이 될 수 있다
 */
function askTextbox(after) {
  const view = S.pane?.view;
  if (!view) return;
  const src = sourceLines();
  let at = Math.max(1, blockEnd(src, after));
  const box = textboxAt(src, at);
  if (box) at = box.end;
  emit('term-paste', t('지금까지의 대화에서 이 문서에 남길 내용을 정리해 {ref} 바로 뒤에 박스글로 넣어 줘. 박스글은 `<!-- box -->` 줄과 `<!-- /box -->` 줄 사이에 보통 Markdown 으로 쓰고, 첫 줄은 `**{word} {n}. 제목**`, 안에 제목(#)은 넣지 않아. 앞뒤에 빈 줄을 두고 그 밖의 줄은 고치지 마. ',
    { ref: lineRef(pathIn(view), [at, at]), word: t('박스'), n: nextCaption(src, t('박스')) }));
}

const askTextboxItem = (after) => ({ label: t('{ai} 에 박스글 요청', { ai: aiName() }), tip: t('대화를 정리해 이 자리 뒤에 박스글로 — 터미널에 요청 글을 넣습니다 (Enter 는 누르지 않음)'), action: () => askTextbox(after) });

/** 원문 줄 a~b 를 박스글로 묶는다 — 여는 줄·제목 줄·닫는 줄을 넣는다 */
function wrapSpan(a, b) {
  const isCaption = (s) => /^(?:박스|Box)$/.test(captionAt(s)?.word ?? '');   // i18n-ok (원문의 캡션 낱말)
  menuOp((src) => wrapTextbox(src, a, b, textboxTitle(t('박스'), nextCaption(src, t('박스')), t('제목')), isCaption), () => stopSpotlight());
}

/** 고른 줄을 박스글로 묶는다 */
function wrapLit() {
  const span = litSpan();
  if (span) wrapSpan(span[0], span[1]);
}

/** 잡은 현재 줄·한 줄 하이라이트의 '아래에 넣기…': 그 줄 아래에 새 줄을 열고 넣기 창을 연다 (D119·D139) */
async function putPicked() {
  const span = litSpan();
  if (!span) return;
  const el = blockOfLine(S.pane.view, span[1]) ?? S.pane.view;
  stopSpotlight();
  await putBelow(span[1], el);
}

/** 고른 줄의 '고른 줄 바꾸기…' — 바꾼 뒤에도 고른 채 (한 글자 키와 같게) */
function changeLit() {
  const span = litSpan();
  if (span) openChange(span[0], span[1], blockOfLine(S.pane.view, span[1]) ?? null, true);
}

/** 현재 줄·고른 줄의 '.' (D155 — spotlight.js 의 changeWinKey): 바꾸기 창 */
function changeHere() {
  const pane = S.pane;
  if (!pane?.view || session || pane.lineEditHold || pane.unfold || !linesEditable() || (pane.tab && blockedReadOnly(pane.tab))) return;
  if (litSpan()) {
    changeLit();
    return;
  }
  const line = pane.here?.line;
  if (line) changeLine(line, blockOfLine(pane.view, line) ?? null);
}

/** 줄 a~b 의 지금 종류 — 바꾸기 창이 거기서 시작한다. 강조글이면 'box:NOTE' 꼴, 섞였으면 '' */
function kindNow(src, a, b) {
  const box = boxAt(src, a);
  if (box) return `box:${box.kind}`;
  const kinds = src.slice(a - 1, b).map((x) => kindOfLine(x)).filter(Boolean);
  return kinds.length && kinds.every((k) => k === kinds[0]) ? kinds[0] : '';
}

/** 줄 a~b 에 맞는 덩어리 바꾸기 — 바꾸기 창의 맨 앞 열 (D155) */
function fitItems(src, a, b) {
  const group = t('이 줄에 맞는 것');
  const out = [];
  const add = (id, name, words) => out.push({ id, group, name, words });
  const sib = siblingsOf(src, a);
  if (fenceAt(fencesOf(src), a)) add('code:unwrap', t('코드 풀기'), 'code unwrap 코드');   // i18n-ok (찾는 말)
  else if (tableAt(src, a)) {
    add('table:list', t('표를 목록으로'), 'table list 표 목록');   // i18n-ok (찾는 말)
    add('table:chart', t('이 표를 차트로'), 'table chart 표 차트');   // i18n-ok (찾는 말)
  } else {
    if (sib.length) {
      const first = itemOf(src[sib[0] - 1]);
      const now = first.ordered ? 'number' : first.task ? 'task' : 'bullet';
      if (now !== 'number') add('list:number', t('이 목록 전체를 번호 목록으로'), 'list number 목록 번호');   // i18n-ok (찾는 말)
      if (now !== 'bullet') add('list:bullet', t('이 목록 전체를 글머리 목록으로'), 'list bullet 목록 글머리');   // i18n-ok (찾는 말)
      if (now !== 'task') add('list:task', t('이 목록 전체를 할 일로'), 'list task 목록 할 일');   // i18n-ok (찾는 말)
      add('list:table', t('목록을 표로'), 'list table 목록 표');   // i18n-ok (찾는 말)
    }
    if (boxAt(src, a)) {
      add('box:unwrap', t('강조글 풀기'), 'callout unwrap 강조글');   // i18n-ok (찾는 말)
      if (!deckOn(S.pane?.view) && !textboxAt(src, a)) add('callout:textbox', t('박스글로 바꾸기'), 'callout textbox box 강조글 박스글');   // i18n-ok (찾는 말)
    } else if (textboxAt(src, a)) {
      add('textbox:callout', t('강조글로 바꾸기'), 'textbox callout 박스글 강조글');   // i18n-ok (찾는 말)
      add('textbox:unwrap', t('박스글 풀기'), 'textbox unwrap 박스글');   // i18n-ok (찾는 말)
    }
    add('code:wrap', t('코드로 감싸기'), 'code wrap 코드');   // i18n-ok (찾는 말)
  }
  add('ai:rewrite', t('바꿔 쓰기 요청'), 'ai rewrite 요청 바꿔 쓰기');   // i18n-ok (찾는 말)
  return out;
}

/** 바꾸기 창의 글 종류·강조글·줄 서식의 계산 — 저장은 부른 쪽이 */
function tryChange(src, a, b, id) {
  const box = /^box:(\w+)$/.exec(id)?.[1];
  const fmt = /^fmt:(\w+)$/.exec(id)?.[1];
  if (fmt) return formatOp(fmt)(src, a, b);
  if (!box) return kindOp(src, a, b, id);
  if (boxAt(src, a)) return setBox(src, a, box);   // 이미 강조글이면 종류만 (D152 — C 키와 같게)
  const check = kindOp(src, a, b, 'quote');   // 코드·표·캡션은 감싸지 않는다
  return check.error ? check : wrapBox(src, a, b, box);
}

/** 박스글의 제목 줄이면 제목 글 — 자리 글('제목')뿐이면 '' (강조글로 바꿀 때 뺀다), 박스 캡션이 아니면 null */
const boxTitleOf = (line) => {
  const c = captionAt(line);
  if (!c || !/^(?:박스|Box)$/.test(c.word)) return null;   // i18n-ok (원문의 캡션 낱말)
  return c.title === t('제목') ? '' : c.title;
};

/** 강조글 → 박스글의 계산 (줄 n 이 든 강조글) — 제목 줄은 다음 박스 번호로 */
const calloutToTextbox = (n) => (src) => boxToTextbox(src, n, textboxTitle(t('박스'), nextCaption(src, t('박스')), t('제목')),
  (s) => /^(?:박스|Box)$/.test(captionAt(s)?.word ?? ''));   // i18n-ok (원문의 캡션 낱말)

/** 표 위의 캡션 줄 (빈 줄 건너) — 없으면 0 */
function captionAbove(src, head) {
  let n = head - 1;
  while (n >= 1 && isBlank(src[n - 1])) n -= 1;
  return n >= 1 && captionAt(src[n - 1]) ? n : 0;
}

/**
 * 바꾸기 창 (D155): 넣기 창과 같은 판 — 맨 앞 열은 이 줄에 맞는 것(목록 전체를·표로·코드·바꿔 쓰기 요청), 그다음 글·강조글·줄 서식.
 * 지금 종류에서 시작하고, 바꿀 수 없는 것은 미리 해 보아 까닭과 함께 흐리게 둔다 (누르면 까닭을 알린다). picked: 고른 줄 — 바꾼 뒤에도 고른 채
 */
async function openChange(a, b, at, picked) {
  const pane = S.pane;
  const view = pane?.view;
  if (!view) return;
  const src = sourceLines();
  const items = changeItems(true);
  const off = {};
  for (const x of items) {
    const r = tryChange(src, a, b, x.id);
    if (r.error) off[x.id] = whyNot(r.error);
  }
  const first = fitItems(src, a, b);
  const chosen = await pick({ items: [...first, ...items], title: a === b ? t('이 줄 바꾸기') : t('고른 줄 바꾸기'), at, board: true,
    first: { name: t('이 줄에 맞는 것'), items: first }, current: kindNow(src, a, b), off, placeholder: t('이름·초성으로 거르기 — ㅂㅎ 번호 목록, ㅍ 표') });
  if (!chosen || S.pane !== pane) return;
  const id = chosen.id;
  const done = () => stopSpotlight();
  if (id === 'ai:rewrite') emit('term-paste', rewritePrompt(lineRef(pathIn(view), [a, b])));
  else if (id === 'table:chart') {
    const el = blockOfLine(view, a);
    const table = el?.closest?.('table') ?? el?.querySelector?.('table');
    if (table) tableToChart(a, table);
    else toast(whyNot('not-table'));
  } else if (id === 'table:list') {
    const head = tableAt(src, a)?.head ?? 0;
    const cap = head ? captionAbove(src, head) : 0;
    const drop = cap && window.confirm(t('표의 캡션 줄도 지울까요? ({caption}) — 취소를 누르면 캡션 줄은 그대로 둡니다', { caption: src[cap - 1].trim() }));
    menuOp((x) => tableToList(x, a, { caption: drop ? captionAbove(x, tableAt(x, a)?.head ?? 0) : 0 }), done);
  } else if (id.startsWith('list:')) {
    const kind = id.slice(5);
    menuOp((x) => (kind === 'table' ? listToTable(x, a, [t('항목'), t('값'), (n) => t('열 {n}', { n })]) : relist(x, a, kind)), done);
  } else if (id === 'box:unwrap') menuOp((x) => unwrapBox(x, a), done);
  else if (id === 'callout:textbox') menuOp(calloutToTextbox(a), done);
  else if (id === 'textbox:callout') menuOp((x) => textboxToBox(x, a, 'NOTE', boxTitleOf), done);
  else if (id === 'textbox:unwrap') menuOp((x) => unwrapTextbox(x, a), done);
  else if (id === 'code:wrap') menuOp((x) => wrapCode(x, a, b), done);
  else if (id === 'code:unwrap') menuOp((x) => unwrapCode(x, a), done);
  else if (picked && !id.startsWith('box:')) turn = turn.then(() => opLitNow((x, p, q) => tryChange(x, p, q, id)));   // 고른 채 — 이어서 키로 (한 글자 키와 같게)
  else menuOp((x) => tryChange(x, a, b, id), picked ? done : null);
}

/** 줄 번호 — 요소가 든 가장 안쪽 블록의 첫 줄 */
const lineOfEl = (el) => Number(/^\d+/.exec(el?.closest?.('[data-lines]')?.dataset.lines || '')?.[0]) || 0;

/** 본문 우클릭의 구성 요소 항목 (docmenu.js): 넣기·바꾸기, 표의 행과 열, 강조글, 절. 고칠 수 없는 화면이면 빈 목록 */
export function lineMenuItems(target) {
  const pane = S.pane;
  const view = pane?.view;
  if (!view?.dataset.docPath || !textOn(view) || !linesEditable() || session) return [];
  const deck = deckOn(view);
  /** @type {MenuItem[]} */
  const items = [];
  if (target.closest?.('.front-matter')) {
    items.push({ label: t('문서 정보 고치기'), tip: t('줄마다 값을 고칩니다'), action: () => {
      const first = openFront(pane);
      if (first) settled(pane).then(() => begin(first));
    } });
    return items;
  }
  const line = lineOfEl(target);
  if (!line) return deck ? cellItems(target, 0) : items;
  const chart = target.closest?.('pre.lec-chart');
  if (target.closest?.(ATOMIC)) items.push({ label: chart ? t('차트 값 고치기') : t('원문 펼치기'), hint: 'F2', tip: t('줄마다 고칩니다'), action: () => unfold(line) });
  if (chart) {
    items.push({ label: t('차트 종류…'), action: async () => {
      const kinds = [['bar', t('막대')], ['line', t('선')], ['area', t('영역')], ['arc', t('원')]];
      const chosen = await pick({ items: kinds.map(([id, name]) => ({ id, name })), title: t('차트 종류'), at: chart });
      if (!chosen) return;
      await unfold(line);
      fenceOp(pane, (text) => setChartKind(text, chosen.id));
    } });
  }
  items.push({ label: t('여기에 넣기…'), hint: '/', tip: deck ? t('표·강조글·그림·차트 같은 구성 요소를 아래에') : t('표·강조글·그림·주 같은 구성 요소를 아래에'), action: () => putBelow(line, target) });
  if (!deck) items.push(askTextboxItem(line));
  const src = sourceLines();
  if (!deck && textboxAt(src, line)) {   // 박스글 (D126) — 안의 표·강조글 항목보다 먼저
    items.push({ label: t('강조글로 바꾸기'), tip: t('여는 줄과 닫는 줄을 떼고 참고 강조글로 — 맨 위의 박스 제목은 굵은 첫 줄로'), action: () => menuOp((x) => textboxToBox(x, line, 'NOTE', boxTitleOf)) },
      { label: t('박스글 풀기'), tip: t('여는 줄과 닫는 줄만 뺍니다 — 글은 그대로'), action: () => menuOp((x) => unwrapTextbox(x, line)) },
      { label: t('박스글 지우기'), action: () => menuOp((x) => {
        const span = textboxSpan(x, line);
        return span ? { ...deleteLines(x, span[0], span[1]), ask: t('박스글을 지울까요? 안의 글도 지워집니다.') } : { error: 'not-textbox' };
      }) });
  }
  const cell = chart ? null : target.closest?.('td, th');   // 차트 아래 데이터 표(D136)의 칸은 문서의 표가 아니다
  if (cell) {
    const col = cell.cellIndex;
    const run = (op) => () => menuOp(op);
    items.push({ label: t('아래에 행 더하기'), hint: 'Shift+Enter', action: run((x) => addRow(x, line, true)) },
      { label: t('위에 행 더하기'), action: run((x) => addRow(x, line, false)) },
      { label: t('오른쪽에 열 더하기'), action: run((x) => addColumn(x, line, col, true)) },
      { label: t('왼쪽에 열 더하기'), action: run((x) => addColumn(x, line, col, false)) },
      { label: t('이 열 오른쪽으로 옮기기'), action: run((x) => moveColumn(x, line, col, 1)) },
      { label: t('이 열 왼쪽으로 옮기기'), action: run((x) => moveColumn(x, line, col, -1)) },
      { label: t('이 열 왼쪽 맞춤'), action: run((x) => alignColumn(x, line, col, 'left')) },
      { label: t('이 열 가운데 맞춤'), action: run((x) => alignColumn(x, line, col, 'center')) },
      { label: t('이 열 오른쪽 맞춤'), action: run((x) => alignColumn(x, line, col, 'right')) },
      ...(cell.style.textAlign ? [{ label: t('이 열 맞춤 표시 지우기'), tip: t('Lectern 이 맞춥니다 — 숫자는 오른쪽, 보고서식이면 짧은 열은 가운데 (설정 창의 표 칸 맞춤)'),
        action: run((x) => alignColumn(x, line, col, 'auto')) }] : []),
      { label: t('이 열 지우기'), action: run((x) => removeColumn(x, line, col)) },
      { label: t('이 표를 차트로'), tip: t('첫 열이 항목, 다음 열들이 값입니다'), action: () => tableToChart(line, cell.closest('table')) },
      { label: t('표 지우기'), action: run((x) => {
        const span = tableSpan(x, line);
        return span ? { ...deleteLines(x, span[0], span[1]), ask: t('표를 지울까요?') } : { error: 'not-table' };
      }) });
    return deck ? [...items, ...cellItems(target, line)] : items;
  }
  if (boxAt(src, line)) {
    const run = (op) => () => menuOp(op);
    items.push({ label: t('강조글 종류 바꾸기…'), action: () => changeBox(line, target) },
      { label: t('강조글 풀기'), tip: t('보통 문단으로'), action: run((x) => unwrapBox(x, line)) },
      ...(deck ? [] : [{ label: t('박스글로 바꾸기'), tip: t('종류 줄과 인용 표시를 떼고 박스글로 — 맨 위에 박스 제목 줄'), action: run(calloutToTextbox(line)) }]),
      { label: t('강조글 지우기'), action: run((x) => {
        const box = boxAt(x, line);
        return box ? { ...deleteLines(x, box.a, box.b), ask: t('강조글을 지울까요?') } : { error: 'not-box' };
      }) });
    return deck ? [...items, ...cellItems(target, line)] : items;
  }
  if (!target.closest?.('pre, .math-block, .front-matter, img')) {
    items.push({ label: t('이 줄 바꾸기…'), hint: '.', tip: t('제목·문단·목록·인용·강조글, 표·코드로'), action: () => changeLine(line, target) });
    const own = /^(\d+)-(\d+)$/.exec(target.closest?.('[data-lines]')?.dataset.lines ?? '');   // 그 줄이 든 블록 — 한 줄은 고르지 않고 메뉴에서 묶는다 (D139)
    if (!deck && own && !textboxAt(src, line)) items.push({ label: t('박스글로 묶기'), tip: t('이 줄을 본문과 따로 읽는 상자로'), action: () => wrapSpan(Number(own[1]), Number(own[2])) });
  }
  if (deck) return [...items, ...cellItems(target, line)];
  if (headLevel(src[line - 1] ?? '')) {
    items.push({ label: t('절 지우기'), tip: t('본문과 하위 절까지'), action: () => menuOp((x) => {
      const r = deleteSection(x, line);
      return r.error ? r : { ...r, ask: t('이 절을 지울까요? 본문과 하위 절까지 지워집니다.') };
    }) });
  }
  return items;
}

async function changeBox(line, at) {
  const chosen = await pick({ items: changeItems().filter((x) => x.id.startsWith('box:')), title: t('강조글 종류'), at });
  if (chosen) menuOp((src) => setBox(src, line, chosen.id.slice(4)));
}

/** 고른 줄에 op(줄 배열, a, b → {lines, a, b} | {error})를 하고, 바뀐 줄 a~b 를 고른 채 둔다 — 키를 이어 누르게 (D107·D128) */
async function opLitNow(op) {
  const pane = S.pane;
  const span = litSpan();
  if (!span || !litOpen() || !await settled(pane) || S.pane !== pane) return;
  const src = sourceLines();
  const r = op(src, span[0], span[1]);
  if (r.error) {
    toast(whyNot(r.error));
    return;
  }
  const shift = await commit(pane, pathIn(pane.view), src, r.lines, { note: r.note || '' });
  if (shift != null && S.pane === pane) setLitSpan(r.a + shift, r.b + shift);
}

// ---- 읽는 화면에서 고른 글 (D142 — wordpick.js 가 부른다) -------------------------------------------------

/** 원문 줄의 머리·글·끝 — 표의 행은 칸마다. {table, parts, bodies} | null (서식을 줄 수 없는 줄 — 코드·그림·다이어그램 등) */
function shownParts(view, line, src) {
  const original = src[line - 1];
  const slot = original == null || isCodeView(view) ? null : lineSlot(view, line, src);
  if (!slot || slot.kind === 'code') return null;
  if (slot.kind === 'table') {
    const parts = splitRow(original);
    return { table: true, parts, bodies: parts.cells.map((c) => c.body) };
  }
  const parts = splitText(original);
  return { table: false, parts, bodies: [parts.body] };
}

const SHOWN_NOTE = () => t('이 줄에는 바로 서식을 줄 수 없습니다 — F2 로 열어 칸 안에서 하세요');

/**
 * 읽는 화면에서 고른 글에 서식을 하고 저장한다 (D142). req: {line, seg(표의 칸 차례), shown(그 칸의 화면 글), va·vb(화면 글에서 고른 자리), kind, value}.
 * 계산은 inlinefmt.js — 화면의 글과 원문을 맞추지 못하거나(수식·각주 등) 서식의 경계를 걸쳐 골랐으면 하지 않고 알린다.
 * 저장하면 {line, seg, body(새 글), a, b(안의 글 자리)} — 부른 쪽이 같은 글을 다시 고른다. 되돌리기 한 걸음
 */
export function formatShown(req) {
  const job = turn.then(() => formatShownNow(req));
  turn = job.catch(() => null);
  return job;
}

async function formatShownNow({ line, seg = 0, shown, va, vb, kind, value }) {
  const pane = S.pane;
  if (!pane?.tab || !linesEditable() || !litOpen() || !await settled(pane) || S.pane !== pane) return null;
  const view = pane.view;
  const src = sourceLines();
  const got = shownParts(view, line, src);
  const body = got?.bodies[seg];
  if (body == null) {
    toast(SHOWN_NOTE());
    return null;
  }
  const m = sourceRange(body, shown, va, vb);
  if (m.error) {
    if (m.error === 'cross') toast(t('서식의 경계에 걸쳐 골랐습니다 — 굵게·색 같은 서식의 안에서만, 또는 밖에서만 고르세요'));
    else if (m.error === 'map') toast(SHOWN_NOTE());
    return null;
  }
  const out = kind === 'clear' ? clearFormats(body, m.a, m.b) : applyFormat(body, m.a, m.b, kind, value);
  if (out.text === body) return null;
  const { parts } = got;
  let next;
  if (got.table) {
    const cells = parts.cells.map((c, i) => (i === seg ? { ...c, body: escapePipes(out.text) } : c));
    next = parts.head + (parts.open ? '|' : '') + cells.map((c) => c.lead + c.body + c.trail).join('|') + (parts.close ? `|${parts.after}` : '');
  } else next = parts.head + out.text + parts.tail;
  const lines = src.slice();
  lines[line - 1] = next;
  const shift = await commit(pane, pathIn(view), src, lines);
  if (shift == null || S.pane !== pane) return null;
  return { line: line + shift, seg, body: out.text, a: out.a, b: out.b };
}

/** 읽는 화면에서 고른 글에서 F2 (D142): 그 줄의 칸을 열고 같은 글을 골라 둔다. 맞추지 못하면 그냥 연다 */
export function editShown({ line, seg = 0, shown, va, vb }) {
  const view = S.pane?.view;
  const got = view ? shownParts(view, line, sourceLines()) : null;
  const body = got?.bodies[seg];
  const m = body == null ? null : sourceRange(body, shown, va, vb);
  begin(line, { cell: seg, range: m && !m.error ? [m.a, m.b] : null });
}

/**
 * 형광펜을 걷는다 (D143 — 사이드바 '형광펜' 하위 묶음의 우클릭). 그 문서가 지금 보는 것이 아니면 먼저 연다 — 바뀐 것을 보고 Ctrl+Z 로 되돌리게.
 * 문서 전체를 걷을 때는 몇 곳인지 묻는다. 글은 그대로 두고 칠한 것만. 되돌리기 한 걸음
 */
async function clearMarksNow({ path, line = 0, text = '', color = null }) {
  if (!path || !S.pane?.tab || blockedReadOnly(S.pane.tab)) return;
  if (pathIn(S.pane.view) !== path) {
    emit('open', { type: 'doc', path });
    for (let i = 0; i < 80 && !(S.pane?.view && pathIn(S.pane.view) === path && S.pane.source?.path === path); i++) await new Promise((ok) => setTimeout(ok, 100));
  }
  const pane = S.pane;
  if (!pane?.view || pathIn(pane.view) !== path || !linesEditable() || !litOpen() || !await settled(pane) || S.pane !== pane) return;
  const src = sourceLines();
  const r = clearMarksIn(src, { line, text, color });
  if (!r.count) {
    toast(t('지울 형광펜이 없습니다 — 그사이 바뀌었으면 사이드바를 다시 보세요'));
    return;
  }
  if (!line && !window.confirm(t('이 문서의 형광펜 {n}곳을 지울까요? 글은 그대로 둡니다.', { n: r.count }))) return;
  const shift = await commit(pane, path, src, r.lines);
  if (shift == null) return;
  if (line) followLine(r.line + shift);
  toast(t('형광펜 {n}곳을 지웠습니다 — Ctrl+Z 로 되돌립니다', { n: r.count }));
}

/** 고른 줄(줄 전체)의 Ctrl 서식 키 — Ctrl+B·Ctrl+I·Ctrl+Shift+X·H·C (D142 — 한 글자 키는 litKey). 받았으면 true */
export function formatPicked(kind) {
  if (!litSpan() || isCodeView(S.pane.view)) return false;
  turn = turn.then(() => opLitNow(formatOp(kind)));
  return true;
}

/** 줄 전체에 하는 서식 (D141 — 굵게는 boldLines) */
const LINE_FORMATS = new Set(['italic', 'strike', 'mark', 'color']);
/** 줄 a~b 를 통째로 서식 fmt 로 */
const formatOp = (fmt) => (src, a, b) => (fmt === 'bold' ? boldLines(src, a, b) : formatLines(src, a, b, fmt));

/** 줄 a~b 에 캡션 줄이 있는지 — 캡션은 종류를 바꾸지 않는다 (D155) */
const captionIn = (src, a, b) => src.slice(a - 1, b).some((x) => !!captionAt(x));

/** 줄 a~b 의 종류를 바꾸는 계산 (D155): 캡션 줄은 두고, 고른 줄 밖에서 번호가 바뀌면 알림 글(note)을 단다 */
function kindOp(src, a, b, kind) {
  if (captionIn(src, a, b)) return { error: 'caption' };
  const r = setKind(src, a, b, kind, { bare: bareOf(src) });
  return r.error ? r : { ...r, note: levelNote(r) };
}

/** 캡션 줄이 있으면 하지 않는 계산 (강조글로 감싸기 — D155) */
const noCaption = (op) => (src, a, b) => (captionIn(src, a, b) ? { error: 'caption' } : op(src, a, b));

/** 고른 줄의 종류를 바꾼다 (D107). toggle: 한 글자 키 — 이미 그 종류면 문단으로, H 는 제목 차례로 (D128) */
const kindLitNow = (kind, toggle = false) => opLitNow((src, a, b) => kindOp(src, a, b, toggle ? toggledKind(src, a, b, kind) : kind));

/** 제목만 골라 Tab 을 눌렀을 때 (D83·D152) */
const HEAD_TAB = () => t('제목 수준은 숫자 키(1~6)나 Alt+Shift+←·→ 로 바꿉니다 — Tab 은 목록 항목만');

/** 레벨을 바꾸며 고른 줄 밖이 함께 바뀐 것 (D152 — 알림 글) */
function levelNote(r) {
  const parts = [];
  if (r.subHeads) parts.push(t('하위 절 제목 {n}개도 함께 옮겼습니다', { n: r.subHeads }));
  if (r.renumbered) parts.push(t('뒤 항목 {n}개의 번호를 다시 매겼습니다', { n: r.renumbered }));
  return parts.join(' · ');
}

/**
 * 고른 줄의 레벨을 바꾼다 (D152 — docops.shiftLevels): 목록은 하위 항목과 함께, 제목은 section 이면 하위 절까지(Alt+Shift) 아니면 그 줄만(vi 의 > <).
 * Tab 은 제목을 바꾸지 않는다 (D83). 앞에서 함께 옮긴 하위는 다시 옮기지 않는다. span: 누른 때의 고른 줄 (vi 는 누르자마자 고르기를 푼다).
 * keep: 바꾼 뒤에도 그 줄을 고른 채 둔다 — 키로 거듭 누를 수 있게 (vi 의 > < 는 푼다)
 */
async function levelLitNow(dir, { tab = false, section = false, span = litSpan(), keep = true } = {}) {
  const pane = S.pane;
  if (!span || !litOpen() || !await settled(pane) || S.pane !== pane) return;
  const src = sourceLines();
  const r = shiftLevels(src, span[0], span[1], dir, { tab, section });
  if (r.error) {
    toast(r.error === 'heading-tab' ? HEAD_TAB() : whyNot(r.error));
    return;
  }
  if (r.lines === src) return;
  const shift = await commit(pane, pathIn(pane.view), src, r.lines, { note: levelNote(r) });
  if (shift != null && S.pane === pane && keep) setLitSpan(span[0] + shift, span[1] + shift);
}

/** vi 의 > < (D152 — 고른 줄의 레벨, 제목은 그 줄만). 누른 때의 고른 줄로 */
export function levelPicked(dir) {
  const span = litSpan();
  if (span) turn = turn.then(() => levelLitNow(dir, { span, keep: false }));
}

/**
 * 고른 줄의 키 (main.js — 파일을 바꾸는 키는 칸이나 고른 줄에서만, D108): 한 글자 키(D128 — 1~6·0·P·H·L·-·N·T·Q·C·B), Ctrl+Alt+숫자,
 * Alt+Shift+←·→, Tab·Shift+Tab. 받았으면 true
 */
export function litKey(e) {
  if (!litSpan() || isCodeView(S.pane.view)) return false;
  const key = kindKey(e);
  if (key) {
    turn = turn.then(() => (key === 'bold' ? opLitNow(boldLines) : key === 'box' ? opLitNow(noCaption(cycleBox))
      : LINE_FORMATS.has(key) ? opLitNow((src, a, b) => formatLines(src, a, b, key)) : kindLitNow(key, true)));
    return true;
  }
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.altKey && !e.shiftKey && /^Digit[0-6]$/.test(e.code)) {
    const kind = e.code === 'Digit0' ? 'para' : `h${e.code.at(-1)}`;
    turn = turn.then(() => kindLitNow(kind, true));   // 같은 수준이면 문단으로 (D152 — 숫자 키와 같게)
    return true;
  }
  const tab = e.key === 'Tab' && !mod && !e.altKey;
  const dir = e.altKey && e.shiftKey && !mod && (e.key === 'ArrowLeft' || e.key === 'ArrowRight') ? (e.key === 'ArrowLeft' ? -1 : 1)
    : tab ? (e.shiftKey ? -1 : 1) : 0;
  if (!dir) return false;
  const span = litSpan();
  turn = turn.then(() => levelLitNow(dir, { tab, section: !tab, span }));   // Alt+Shift 는 하위 절까지, Tab 은 목록만 (D152)
  return true;
}

/** Alt+↑·↓ (main.js — 문서 칸에서, 줄 하이라이트 중일 때만): 하이라이트한 줄을 옮긴다. 받았으면 true. 차례로 — 누르고 있어도 쌓이지 않게 */
export function moveLit(dir) {
  if (!litSpan()) return false;
  if (moves < 2) {
    moves += 1;
    turn = turn.then(() => moveLitNow(dir)).finally(() => { moves -= 1; });
  }
  return true;
}

/** 칸 안에서도 앱이 받는 키 (D152) — main.js 가 전체 편집 상자에서 앱으로 넘기는 것과 같다: F1·Ctrl+/(단축키 표), 문서·프로젝트 탭, 문서 열기·새 문서·편집 모드·설정 */
function appKey(e) {
  const mod = e.ctrlKey || e.metaKey;
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (e.key === 'F1' || (mod && !e.altKey && !e.shiftKey && e.code === 'Slash')) return true;
  if (e.altKey && !mod && !e.shiftKey && /^[1-9]$/.test(e.key)) return true;
  if (!mod || e.altKey) return false;
  return e.key === 'Tab' || (!e.shiftKey && e.key === 'F4') || /^[1-9]$/.test(e.key) || e.key === ','
    || ['KeyW', 'KeyT', 'KeyP', 'KeyN', 'KeyE'].includes(e.code) || ['w', 't', 'p', 'n', 'e'].includes(key);
}

function onKey(e) {
  if (e.key === 'F6') {   // 터미널로 — main.js 가 받는다. 칸은 그대로 두고, 돌아오면 이 자리로 (D79)
    const sel = getSelection();
    if (session) session.caret = [sel.focusNode, sel.focusOffset];
    return;
  }
  if (session && appKey(e)) {   // 칸 안에서도 앱 키 (D152 — 전체 편집과 같은 목록): 칸을 저장하고 닫은 뒤 그 키를 앱에 다시 보낸다
    e.preventDefault();
    e.stopPropagation();
    const init = { key: e.key, code: e.code, ctrlKey: e.ctrlKey, shiftKey: e.shiftKey, altKey: e.altKey, metaKey: e.metaKey, bubbles: true, cancelable: true };
    finish(true).then(() => document.dispatchEvent(new KeyboardEvent('keydown', init)));
    return;
  }
  e.stopPropagation();   // 칸 안의 키는 칸의 것 — 앱 단축키(main.js)는 쉰다 (위의 앱 키 말고)
  if (!session || e.isComposing || e.keyCode === 229) return;   // 한글 조합 중
  const span = e.currentTarget;
  const mod = e.ctrlKey || e.metaKey;
  const k = e.key;
  // 구조 보기의 꼬리표(칸 머리 줄·지시어 줄)는 글만 고친다 — 줄을 더하고 옮기는 키가 칸을 깨뜨리지 않게
  if (span.closest('.lec-tag') && ((k === 'Enter' && mod) || (mod && e.shiftKey) || e.altKey || k === 'Tab' || (k === 'Backspace' && caretOffset(span) === 0))) {
    e.preventDefault();
    return;
  }
  const typing = textOn(session.pane.view) && session.kind === 'text' && !span.closest('.lec-tag');
  const fmt = textOn(session.pane.view) && (session.kind === 'text' || session.kind === 'table') && !span.closest('.lec-tag');   // 문장 속 서식 (D141) — 표의 칸에서도
  if (k === '/' && !mod && !e.altKey && typing && session.fresh && !span.textContent) {   // 넣기 창 (D109)
    e.preventDefault();
    openPut();
  } else if (mod && e.shiftKey && !e.altKey && e.code === 'Slash' && typing) {
    e.preventDefault();
    openPut();
  } else if (mod && !e.shiftKey && !e.altKey && fmt && e.code === 'KeyB') {
    e.preventDefault();
    formatHere(span, 'bold');
  } else if (mod && !e.shiftKey && !e.altKey && fmt && e.code === 'KeyI') {
    e.preventDefault();
    formatHere(span, 'italic');
  } else if (mod && !e.shiftKey && !e.altKey && fmt && e.code === 'Backquote') {
    e.preventDefault();
    formatHere(span, 'code');
  } else if (mod && e.shiftKey && !e.altKey && fmt && e.code === 'KeyX') {
    e.preventDefault();
    formatHere(span, 'strike');
  } else if (mod && e.shiftKey && !e.altKey && fmt && e.code === 'KeyH') {   // 형광펜 — 거듭 누르면 다음 색, 마지막에 풀린다
    e.preventDefault();
    formatHere(span, 'mark');
  } else if (mod && e.shiftKey && !e.altKey && fmt && e.code === 'KeyC') {   // 글자색 — 거듭 누르면 다음 색, 마지막에 풀린다
    e.preventDefault();
    formatHere(span, 'color');
  } else if (mod && !e.shiftKey && !e.altKey && typing && e.code === 'KeyK') {
    e.preventDefault();
    linkHere();
  } else if (mod && e.altKey && !e.shiftKey && typing && e.code === 'KeyF') {
    e.preventDefault();
    noteHere();
  } else if (mod && !e.altKey && !e.shiftKey && e.code === 'Semicolon') {   // 날짜 넣기 (D149)
    e.preventDefault();
    dateHere();
  } else if (mod && !e.altKey && e.shiftKey && e.code === 'Semicolon') {   // 특수 문자 넣기 (D165)
    e.preventDefault();
    charHere();
  } else if (k === 'Enter' && mod && !e.altKey) {
    e.preventDefault();
    if (e.shiftKey) addLine(false);   // 위에 새 줄
    else saveAndPick();   // 저장하고 그 줄 선택 — 읽는 화면의 Ctrl+Enter 와 같은 '줄 선택' (D164 — 전에는 Shift+Enter 와 같은 '아래에 새 줄')
  } else if (mod && e.shiftKey && !e.altKey && (e.code === 'Period' || e.code === 'Comma') && session.pane.view.classList.contains('lec-deck')) {
    e.preventDefault();   // 글자 크기 (D96): 고친 글을 저장하고 크기를 바꾼다
    finish(true).then(() => emit('slide-text-size', { dir: e.code === 'Period' ? 1 : -1 }));
  } else if (mod && e.shiftKey && !e.altKey && e.code === 'KeyK') {
    e.preventDefault();
    deleteHere();
  } else if (mod && e.shiftKey && !e.altKey && e.code === 'KeyD') {
    e.preventDefault();
    duplicateHere();
  } else if ((k === 'ArrowUp' || k === 'ArrowDown') && e.altKey && !mod && !e.shiftKey) {
    e.preventDefault();
    moveHere(k === 'ArrowUp' ? -1 : 1);
  } else if (mod && e.altKey && !e.shiftKey && /^Digit[0-6]$/.test(e.code)) {
    e.preventDefault();
    kindHere(e.code === 'Digit0' ? 'para' : `h${e.code.at(-1)}`);
  } else if (e.altKey && e.shiftKey && !mod && (k === 'ArrowLeft' || k === 'ArrowRight')) {
    e.preventDefault();
    levelKey(k === 'ArrowLeft' ? -1 : 1);
  } else if (k === 'Backspace' && !mod && !e.altKey && !e.shiftKey && session.kind !== 'table' && caretOffset(span) === 0) {
    if (session.fresh) {
      if (span.textContent) return;   // 글이 남은 새 줄의 맨 앞 — 윗줄이 아직 없다
      e.preventDefault();
      step(-1);
      return;
    }
    e.preventDefault();
    joinUp();
  } else if (k === 'Enter' && e.shiftKey && !mod && !e.altKey) {   // 저장하고 아래에 새 줄 (D158 — 글 가운데면 두 줄로. 읽는 화면의 Shift+Enter 와 같은 키 — D164)
    e.preventDefault();
    if (session.fresh && !read(session.places[0]).trim()) return;   // 빈 새 줄 — 쓴 것이 없다
    addLine(true);
  } else if (k === 'Enter' && !mod && !e.altKey && session.fresh && !read(session.places[0]).trim()) {   // 빈 새 줄의 Enter — 넣지 않고 끝낸다
    e.preventDefault();
    finish(false);
  } else if (k === 'Enter' && !mod && !e.altKey) {
    e.preventDefault();
    saveAndNext();   // 저장하고 닫은 뒤 현재 줄만 다음 줄로 (D168 — 사용자 결정. 이어 쓰려면 Shift+Enter)
  } else if (mod && !e.altKey && (e.code === 'KeyS' || k.toLowerCase() === 's')) {
    e.preventDefault();
    finish(true);   // 저장하고 닫는다 — 현재 줄은 그 줄 (D158)
  } else if (k === 'Escape') {
    e.preventDefault();
    finish(S.config?.vi_keys === true);   // vi 키(D122)를 켰으면 vi 처럼 저장하고 나온다 — 아니면 그만두기
  } else if ((k === 'ArrowUp' || k === 'ArrowDown') && !mod && !e.altKey && !e.shiftKey) {
    const dir = k === 'ArrowUp' ? -1 : 1;
    if (!caretOnEdge(span, dir)) return;   // 꺾인 글의 안쪽 줄: 칸 안에서 위·아래로 (기본 동작)
    e.preventDefault();
    if (dir < 0 && session.fresh?.peek && !read(session.places[0]).trim()) {   // 끝을 지나친 ↓ 가 연 빈 새 줄 — ↑ 는 읽기로 돌아간다 (D128)
      finish(false);
      return;
    }
    step(dir, e.repeat);
  } else if (k === 'Tab' && !mod && !e.altKey) {
    e.preventDefault();
    if (session.kind === 'table') {
      const at = Number(span.dataset.i);
      if (!e.shiftKey && at === session.places.length - 1 && tableAt(sourceLines(), session.line)?.last === session.line) addLine(true);   // 마지막 칸의 Tab: 새 행
      else if (rowEdge(at, e.shiftKey)) step(e.shiftKey ? -1 : 1, false, e.shiftKey ? session.places.length - 1 : 0);   // 행의 끝이면 옆 행으로 — 표를 줄줄이 쓰게 (기능 요청 4-7)
      else focusPlace(Math.max(0, Math.min(session.places.length - 1, at + (e.shiftKey ? -1 : 1))), false);
    }
    else if (session.kind === 'code' && !e.shiftKey) document.execCommand('insertText', false, '\t');
    else if (session.kind === 'text') levelHere(e.shiftKey ? -1 : 1);
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
  span.addEventListener('paste', (e) => {   // 글 칸(plaintext-only)은 beforeinput 에 붙여 넣은 글을 주지 않는다
    if (!session) return;
    const file = imageIn(e.clipboardData);
    if (file && textOn(session.pane.view)) {
      e.preventDefault();
      putImageFile(file);
      return;
    }
    const text = e.clipboardData?.getData('text/plain');
    if (!text || !/[\r\n]/.test(text)) return;
    e.preventDefault();
    if (!session.fence && session.kind !== 'table' && !span.closest('.lec-tag')) pasteHere(text);   // 줄마다 나눠 넣는다 (D109)
    else document.execCommand('insertText', false, text.replace(/\r\n?|\n/g, ' '));
  });
  // 칸 안을 누르는 것은 제목 접기·링크·현재 위치로 가지 않는다
  for (const type of ['mousedown', 'click', 'dblclick']) span.addEventListener(type, (e) => e.stopPropagation());
  span.addEventListener('mousedown', (e) => {   // 글을 고른 채 우클릭하면 고른 것을 그대로 둔다 — 고른 글 밖을 눌러도 커서가 옮겨 가지 않게 (선택 상자가 그 글에 한다)
    if (e.button === 2 && selOffsets(span) && getSelection().toString()) e.preventDefault();
  });
  span.addEventListener('contextmenu', onCellMenu);   // 서식의 선택 상자 (D141)
  span.addEventListener('input', paintSoon);
  paintSoon();
  span.addEventListener('focus', () => {
    if (session) session.cell = Number(span.dataset.i);
  });
}

/** F6 으로 돌아올 때 (main.js, D79): 칸의 그 자리로. 한 줄 편집 중이 아니면 false */
export function focusLineEdit() {
  if (!session) return false;
  session.places[session.cell]?.span.focus();
  if (session.caret) getSelection().collapse(session.caret[0], session.caret[1]);
  return true;
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
  } catch (err) {
    toast(t('저장하지 못했습니다: {error}', { error: err.message }), 'error');
  } finally {
    taskSaving = false;
  }
}

// ---- 되돌리기 ---------------------------------------------------------------------

/** 줄 line 이 지금 화면에 보이는지 (D156 — 되돌리기를 알릴지) */
function lineShown(pane, line) {
  const el = blockOfLine(pane.view, line);
  if (!el || !pane.scroller) return false;
  const r = el.getBoundingClientRect();
  const box = pane.scroller.getBoundingClientRect();
  return r.bottom > box.top && r.top < box.bottom;
}

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
  const keep = S.pane === pane && (lightOn() || pickedMany());   // 하이라이트·여러 줄 고르기는 되돌린 줄들로 옮겨 남긴다 — 끄는 것은 Shift+Enter·Esc (D139)
  try {
    const src = await getJSON(`/api/source?p=${encodeURIComponent(pane.tab.id)}&path=${encodeURIComponent(path)}`);
    if (src.hash !== (undoing ? change.hash : change.prior)) {   // 그 뒤에 파일이 또 바뀌었다 (Claude Code·편집 모드 등) — 이 파일의 기록은 버린다
      rec.done.length = 0;
      rec.undone.length = 0;
      toast(undoing ? t('그사이 파일이 바뀌어 되돌리지 않았습니다') : t('그사이 파일이 바뀌어 다시 하지 않았습니다'));
      return;
    }
    const seen = S.pane === pane && lineShown(pane, change.line);   // 바뀐 곳이 화면 안이었으면 알리지 않는다 (D156)
    const [gone, back] = undoing ? [change.after, change.before] : [change.before, change.after];
    const lines = src.text.split('\n');
    lines.splice(change.line - 1, gone.length, ...back);
    const saved = await postJSON('/api/save', { p: pane.tab.id, path, text: lines.join('\n'), hash: src.hash });
    if (undoing) change.prior = saved.hash;
    else change.hash = saved.hash;
    to.push(from.pop());
    await refreshView(pane);
    const last = change.line + Math.max(back.length, 1) - 1;
    if (S.pane === pane && keep) setLitSpan(...(undoing && change.lit ? change.lit : [change.line, last]));
    else if (S.pane === pane) followLine(change.line);
    const where = rangeText([change.line, last]);
    if (!seen) toast(undoing ? t('되돌렸습니다: {where}', { where }) : t('다시 했습니다: {where}', { where }));
  } catch (e) {
    toast(undoing ? t('되돌리지 못했습니다: {error}', { error: e.message }) : t('다시 하지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

/** 지금 화면의 파일 기록에서 한 걸음. 할 것이 있으면 true (부른 쪽이 기본 동작을 막는다) — 저장은 차례가 오면 */
function walk(undoing) {
  const view = $('#lec-view');
  const path = pathIn(view);
  const key = S.tab && path ? `${S.tab.id}|${path}` : null;
  const ready = () => (undoing ? records.get(key)?.done : records.get(key)?.undone)?.length;
  if (!key || session || S.pane?.lineEditHold || (!ready() && !saving.size)) return false;
  const pane = S.pane;
  // 저장 중인 편집이 기록에 쌓인 뒤에 — 앞서 보면 방금 저장한 파일을 '그사이 바뀌었다'고 여겨 기록을 버린다
  turn = turn.then(() => Promise.allSettled([...saving])).then(() => (ready() ? replay(pane, path, records.get(key), undoing) : null));
  return true;
}

/** Ctrl+Z (main.js — 문서 칸에서, 한 줄 편집 중이 아닐 때): 지금 문서에서 저장한 마지막 변경을 고치기 전으로 */
export const undoLineEdit = () => walk(true);
/** Ctrl+Y: 되돌린 변경을 다시 */
export const redoLineEdit = () => walk(false);

export function initLineEdit() {
  on('line-edit', (unit) => {
    if (unit.el.matches?.(ATOMIC)) unfold(unit.a);   // 수식·다이어그램·차트: 원문을 펼쳐 줄마다 (D112)
    else begin(lineOf(unit));
  });
  on('replace', (op) => { turn = turn.then(() => replaceNow(op)); });
  on('rendered', showSource);
  on('rendered', loadSamples);
  on('chart-values', ({ pane, fields, rows }) => fenceOp(pane, (text) => writeValues(text, fields, rows)));
  on('chart-kind', ({ pane, kind }) => fenceOp(pane, (text) => setChartKind(text, kind)));
  on('chart-inline', ({ pane, a, b, data }) => {   // 차트의 CSV 를 문서 안의 값으로 (chartdata.js, D136)
    turn = turn.then(async () => {
      if (S.pane !== pane || !await settled(pane) || S.pane !== pane || blockedReadOnly(pane.tab) || !linesEditable()) return;
      const src = sourceLines();
      const next = /^\s*(`{3,}|~{3,})/.test(src[a - 1] || '') ? inlineUrlData(src.slice(a - 1, b).join('\n'), data) : null;
      if (next == null) {
        toast(t('이 차트의 데이터를 문서 안으로 넣지 못했습니다 — 원문에서 data 의 url 을 values 로 고치세요'));
        return;
      }
      const shift = await commit(pane, pathIn(pane.view), src, [...src.slice(0, a - 1), ...next.split('\n'), ...src.slice(b)]);
      if (shift != null) toast(t('데이터를 문서 안으로 넣었습니다 — 이제 CSV 파일 없이도 그려집니다'));
    });
  });
  on('lint-fix', ({ pane, line, fix }) => {   // 문서 점검의 '고치기' (doccheck.js, D190) — 지금 원문에 다시 계산한다. 그사이 그 줄이 바뀌었으면 하지 않는다
    turn = turn.then(async () => {
      if (S.pane !== pane || session || !await settled(pane) || S.pane !== pane || blockedReadOnly(pane.tab) || !linesEditable()) return;
      const src = sourceLines();
      const next = fix(src.slice());
      if (!next) {
        toast(t('그사이 문서가 바뀌어 고치지 않았습니다 — 점검 목록을 다시 여세요'));
        return;
      }
      const shift = await commit(pane, pathIn(pane.view), src, next);
      if (shift != null && S.pane === pane) followLine(Math.max(1, Math.min(line + shift, sourceLines().length)));
    });
  });
  on('pane', showSource);
  $('#lec-st-source').addEventListener('click', () => {
    const { view } = S.pane;
    emit('open', { type: isCodeView(view) ? 'doc' : 'code', path: pathIn(view) });
  });
  initLineBlock(refreshView);
  on('line-open', ({ line, below = false, select = false }) => {   // 새 문서를 열면 바로 쓴다 (newdoc.js, D105)
    followLine(line);
    if (below) beginNew(line, true);
    else begin(line, { select });
  });
  on('line-end', (d) => growEnd({ peek: !!d?.arrow }));   // 마지막 줄의 ↓, 빈 문서의 F2·↓ (spotlight.js, D106)
  on('line-step', ({ dir }) => { if (S.pane?.lineEditHold && queued.length < 30) queued.push(dir); });   // 넘어가는 사이의 ↑·↓ (spotlight.js, D128)
  on('line-add', ({ below }) => addHere(below));
  on('line-change-win', () => changeHere());   // 현재 줄·고른 줄의 '.' — 바꾸기 창 (spotlight.js, D155)   // 칸 없이 새 줄 (spotlight.js, D117)
  on('line-put', () => { turn = turn.then(putHere); });
  on('line-chars', () => { turn = turn.then(charsAtLine); });   // 현재 줄의 Ctrl+Shift+; — 특수 문자 (spotlight.js, D165)
  on('clear-marks', (op) => { turn = turn.then(() => clearMarksNow(op)); });   // 형광펜 지우기 (tree.js — D143)   // 현재 줄의 / — 아래에 넣기 창 (spotlight.js, D139)
  on('line-delete', ({ cut = false }) => { turn = turn.then(() => deleteLit(cut)); });
  on('section-move', (op) => { turn = turn.then(() => moveSectionNow(op)); });   // 목차에서 절 끌기 (toc.js, D121)
  // 슬라이드 구성 요소의 글자 크기 (Ctrl+Shift+>·<). 문서 글자 크기(textsize.js 의 'text-size' — 배율 숫자)와 이름을 나눈다:
  // 같은 이름이었을 때는 Ctrl+=·Ctrl+- 마다 이 처리기가 dir 없이 돌아 슬라이드 파일에 NaN 을 쓸 수 있었다
  on('slide-text-size', ({ dir }) => { if (dir === 1 || dir === -1) turn = turn.then(() => resizeHere(dir)); });
  on('slide-op', (op) => { turn = turn.then(() => slideOp(op)); });
  on('md-headings', (op) => { turn = turn.then(() => restyle(op)); });
  on('pane', () => {   // 다른 탭을 고르면 고친 것은 저장하고 끝낸다
    if (session && session.pane !== S.pane) finish(true);
  });
  const panes = $('#lec-panes');
  const canPutImage = () => canGrow(S.pane) || (session && textOn(session.pane.view));
  document.addEventListener('paste', (e) => {   // 읽는 화면에서 Ctrl+V: 현재 줄 뒤에 그림 (D111)
    const file = imageIn(e.clipboardData);
    if (!file || session || !docKeyTarget(e) || !canPutImage()) return;
    e.preventDefault();
    if (!manyBlocks()) putImageFile(file);   // 넣기는 현재 줄에서 (D139)
  });
  panes.addEventListener('dragover', (e) => {
    if ([...(e.dataTransfer?.types ?? [])].includes('Files') && canPutImage()) e.preventDefault();
  });
  panes.addEventListener('drop', (e) => {
    const file = imageIn(e.dataTransfer);
    if (!file || !canPutImage()) return;
    e.preventDefault();
    if (session || !manyBlocks()) putImageFile(file);
  });
  panes.addEventListener('click', onTaskClick);
  panes.addEventListener('mousedown', (e) => {
    if (e.target.matches?.(TASK_BOX)) e.preventDefault();   // 초점은 문서 칸에 — 이어서 치는 ↑·↓·F2 가 그대로 되게
  }, true);
}
