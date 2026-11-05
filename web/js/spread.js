// 모두 펼치기 (D73): 선택된 프로젝트의 문서 탭들을 창 전체에 격자로 펼친다 — 터미널 모음(D40)처럼. 문서 탭 줄 오른쪽 끝,
// 열린 문서 탭 목록 [n ∨] 옆의 [▦] 버튼으로 켜고 끈다 (다시 누르면 원래 화면으로).
//
// - 칸 하나에 문서 탭 하나 (탭 차례). 오른쪽 아래 칸은 이 프로젝트의 터미널 — 오른쪽 패널(#lec-term)을 그대로 쓰므로 머리줄의 터미널 탭·+ 도 그대로다.
//   칸 수가 격자에 맞지 않아 빈 자리가 생기면 같은 줄 왼쪽의 문서 칸이 옆으로, 마지막 줄이 터미널뿐이면 위 줄의 문서 칸이 아래로 늘어 채운다
//   (layoutOf). 보기만 하는 프로젝트(D71)는 터미널 칸이 없다.
// - 사이드바·목차는 감춘다. 프로젝트 탭 막대·문서 탭 줄·상태줄은 그대로. 사이드바·목차 버튼(Ctrl+B 도)을 누르면 펼치기를 끝내고 그것을 보인다.
// - 펼칠 때 터미널이 닫혀 있으면 연다 (셸이 없으면 Ctrl+` 처럼 시작) — 끝낼 때 다시 감춘다 (셸은 그대로). 펼친 동안 사용자가 터미널을
//   열거나 감췄으면 끝낼 때 그대로 둔다. 펼친 채 다른 프로젝트 탭을 고르면 그 프로젝트의 문서 탭들과 터미널이 펼쳐진다.
// - 화면은 CSS 로만 바꾼다: #lec-main 이 격자가 되고 #lec-panes 는 display: contents — 칸(.lec-pane)을 옮기지 않으므로 스크롤·편집 상자·
//   그린 문서가 그대로다. 칸마다 머리(.sp-head: 이름, [⤢] 이 문서만 보기)를 붙였다가 끝낼 때 뗀다.
// - 칸을 누르면 그 문서 탭을 고른다 (html 문서는 iframe 안의 누름을 htmldoc.js 가 넘겨 준다). 목차·상태줄·찾기·우클릭 메뉴·단축키는 고른 칸의 것.
// - 펼친 동안은 선택된 탭의 칸이 모두 보이므로(panes.paneShown) 자동 새로고침·F5·스타일 바꾸기가 칸마다 바로 다시 그린다.
//   아직 그리지 않은 칸(되살린 문서 탭 — deferred)과 숨은 동안 바뀐 칸(stale)은 펼칠 때 그린다.

import { S, on } from './store.js';
import { paneOf } from './panes.js';
import { describe, selectDocTab, tabMenu } from './doctabs.js';
import { navigate, refreshView } from './nav.js';
import { terminalOpen, toggleTerminal } from './terminal.js';
import { shapeOf } from './gather.js';
import { showMenu } from './ui.js';
import { html, setHtml } from './html.js';
import { $ } from './util.js';
import { t } from './i18n.js';

const root = document.documentElement;

let shown = false;
let termWanted = false;   // 펼친 동안 터미널을 둘지 (사용자가 감추면 false — 다른 프로젝트 탭을 골라도 다시 열지 않는다)
let openedTerm = false;   // 펼치면서 연 터미널 (끝낼 때 감춘다)
let selfToggle = false;   // 이 모듈이 터미널을 열고 닫는 중 ('term-panel' 을 사용자의 것으로 보지 않게)

export const spreadOn = () => shown;

/**
 * 문서 n 개(+ 터미널)의 자리: {cols, rows, cells: [{row, col, rows, cols}](문서마다, 0부터), term: {row, col} | null}.
 * 격자는 터미널 모음과 같다 (1 = 하나, 2 = 좌우, 3~4 = 2×2, 5~6 = 3×2, 7~9 = 3×3 …). 터미널은 오른쪽 아래 한 칸이고,
 * 빈 자리는 마지막 줄의 마지막 문서가 옆으로 — 마지막 줄이 터미널뿐이면 위 줄의 문서들이 아래로 늘어 채운다
 */
export function layoutOf(n, withTerm) {
  const [cols, rows] = shapeOf(Math.max(1, n + (withTerm ? 1 : 0)));
  const cells = Array.from({ length: n }, (_, i) => ({ row: Math.floor(i / cols), col: i % cols, rows: 1, cols: 1 }));
  const last = rows - 1;
  const room = withTerm ? cols - 1 : cols;   // 마지막 줄에서 문서가 쓸 수 있는 칸 수 (터미널은 맨 오른쪽)
  const inLast = n - last * cols;            // 마지막 줄의 문서 수
  if (inLast > 0) cells[n - 1].cols = room - inLast + 1;
  else for (let c = 0; c < room; c++) cells[(last - 1) * cols + c].rows = 2;
  return { cols, rows, cells, term: withTerm ? { row: last, col: cols - 1 } : null };
}

const place = (el, cell) => {
  el.style.gridRow = cell ? `${cell.row + 1} / span ${cell.rows || 1}` : '';
  el.style.gridColumn = cell ? `${cell.col + 1} / span ${cell.cols || 1}` : '';
};

/** 칸 머리: 아이콘·이름(문서 탭과 같게)·저장하지 않은 편집 ●·[⤢] 이 문서만 보기 */
function renderHead(pane) {
  let head = pane.el.querySelector(':scope > .sp-head');
  if (!head) {
    head = document.createElement('div');
    head.className = 'sp-head';
    pane.el.prepend(head);
  }
  const { icon, name, tip } = describe(pane);
  const only = t('이 문서만 보기 — 모두 펼치기를 끝냄');
  const markup = html`${[html`${icon}<span class="sp-name">${name}</span>`, html`${pane.editor?.dirty ? html`<span class="dirty" title="${t('저장하지 않은 편집이 있습니다')}">●</span>` : ''}`, html`<button type="button" class="icon-btn small sp-only" title="${only}" aria-label="${only}"><svg><use href="#i-expand"/></svg></button>`]}`;
  if (head.lecHtml !== markup.text) {   // 같으면 다시 넣지 않는다
    setHtml(head, markup);
    head.lecHtml = markup.text;
  }
  head.title = `${tip}\n${t('머리를 두 번 누르면 이 문서만')}`;
}

/** 아직 그리지 않은 칸(되살린 문서 탭)과 숨은 동안 바뀐 칸을 그린다 — 펼치면 모두 보인다 */
function drawPending(tab) {
  for (const pane of tab.panes) {
    if (pane.deferred) {
      const target = pane.deferred;
      pane.deferred = null;
      navigate(target, { pane, restoreScroll: true });
    } else if (pane.stale && pane.current) {
      refreshView(pane);
    }
  }
}

/** 선택된 탭의 문서 탭들과 터미널을 격자에 놓는다 (문서 탭이 생기거나 닫히거나, 터미널을 열고 닫거나, 다른 프로젝트 탭을 고를 때) */
function layout() {
  if (!shown) return;
  const tab = S.tab;
  if (!tab) {
    leaveSpread();
    return;
  }
  const withTerm = terminalOpen() && !tab.readonly;
  const { cols, rows, cells, term } = layoutOf(tab.panes.length, withTerm);
  const main = $('#lec-main');
  main.style.setProperty('--sp-cols', cols);
  main.style.setProperty('--sp-rows', rows);
  root.classList.toggle('sp-noterm', !withTerm);
  for (const pane of S.panes) {
    const i = pane.tab === tab ? tab.panes.indexOf(pane) : -1;
    pane.el.classList.toggle('sp-cell', i >= 0);
    place(pane.el, cells[i]);
    if (i >= 0) renderHead(pane);
    else pane.el.querySelector(':scope > .sp-head')?.remove();
  }
  place($('#lec-term'), term);
  drawPending(tab);
}

/** 펼친 동안 터미널을 둔다 — 닫혀 있으면 연다 (보기만 하는 프로젝트, 사용자가 감춘 뒤는 열지 않는다). 입력은 문서 칸에 남긴다 */
function ensureTerminal(tab) {
  if (!termWanted || terminalOpen() || !tab || tab.readonly) return;
  selfToggle = true;
  try {
    toggleTerminal(true, { focus: false });
  } finally {
    selfToggle = false;
  }
  openedTerm = true;
}

function updateButton() {
  const btn = $('#lec-doctab-spread');
  btn.setAttribute('aria-pressed', String(shown));
  btn.title = shown ? t('모두 펼치기 끝내기 — 원래 화면으로')
    : t('모두 펼치기 — 열린 문서 탭들과 터미널을 창 전체에 (다시 누르면 원래대로)');
}

const focusPane = (pane) => {
  if (pane?.editor) pane.editor.cm.focus();
  else pane?.scroller.focus({ preventScroll: true });
};

export function enterSpread() {
  if (shown || !S.tab) return;
  shown = true;
  termWanted = true;
  openedTerm = false;
  root.classList.add('spread-on');
  ensureTerminal(S.tab);
  layout();
  updateButton();
  focusPane(S.pane);
}

/** 원래 화면으로: 칸을 겹쳐 두고 고른 문서 탭만 보인다. 펼치면서 연 터미널은 감춘다 (셸은 그대로) */
export function leaveSpread() {
  if (!shown) return;
  shown = false;
  root.classList.remove('spread-on', 'sp-noterm');
  const main = $('#lec-main');
  main.style.removeProperty('--sp-cols');
  main.style.removeProperty('--sp-rows');
  for (const pane of S.panes) {
    pane.el.classList.remove('sp-cell');
    place(pane.el, null);
    pane.el.querySelector(':scope > .sp-head')?.remove();
  }
  place($('#lec-term'), null);
  if (openedTerm && terminalOpen()) {
    selfToggle = true;
    try {
      toggleTerminal(false);
    } finally {
      selfToggle = false;
    }
  }
  openedTerm = false;
  updateButton();
  focusPane(S.pane);
}

export const toggleSpread = () => (shown ? leaveSpread() : enterSpread());

/** 칸 머리의 [⤢]·두 번 누르기: 그 문서 탭을 고르고 펼치기를 끝낸다 */
function onlyThis(pane) {
  if (!pane) return;
  selectDocTab(pane);
  leaveSpread();
}

export function initSpread() {
  $('#lec-doctab-spread').addEventListener('click', toggleSpread);
  const panes = $('#lec-panes');
  // 누른 칸의 문서 탭을 고른다 — 우클릭 메뉴(docmenu.js)가 그 칸의 것이 되도록 contextmenu 보다 먼저 (mousedown, 잡기 단계)
  panes.addEventListener('mousedown', (e) => {
    if (!shown) return;
    const pane = paneOf(e.target);
    if (pane && pane.tab === S.tab && pane !== S.pane) selectDocTab(pane);
  }, true);
  panes.addEventListener('click', (e) => {
    if (shown && e.target.closest('.sp-only')) onlyThis(paneOf(e.target));
  });
  panes.addEventListener('dblclick', (e) => {
    if (shown && e.target.closest('.sp-head') && !e.target.closest('button')) onlyThis(paneOf(e.target));
  });
  panes.addEventListener('contextmenu', (e) => {   // 칸 머리: 문서 탭의 메뉴 (닫기·다른 탭 닫기·경로)
    if (!shown || !e.target.closest('.sp-head')) return;
    const pane = paneOf(e.target);
    if (!pane) return;
    e.preventDefault();
    showMenu(e.clientX, e.clientY, tabMenu(pane));
  });
  on('doctab-list', layout);
  on('tab', () => {
    if (!shown) return;
    if (!S.tab) leaveSpread();
    else {
      ensureTerminal(S.tab);
      layout();
    }
  });
  on('tabs', () => { if (shown && !S.tab) leaveSpread(); });
  on('term-panel', (open) => {   // 터미널을 열거나 감춤 — 사용자가 했으면 끝낼 때 그대로 둔다
    if (!shown) return;
    if (!selfToggle) {
      termWanted = open;
      openedTerm = false;
    }
    layout();
  });
  updateButton();
}
