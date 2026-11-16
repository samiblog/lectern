// 업무 관리 (D124): 업무 현황(공통 폴더의 폴더 개요 맨 위), 업무 카드 만들기, 일정 더하기, 폴더 더하기, 공통 폴더 정하기, 알림 칸.
// 업무 나무 (D149): 폴더마다 WORK.md, 상위는 하위를 모아 보인다 — 업무 현황, 총괄·묶음 폴더의 폴더 개요, 상위 WORK.md 아래의 '하위 업무' 칸.
// 나무 표·칸반과 상위에서 고치기는 workview.js. WORK.md 의 글을 읽어 계산하는 것은 workdata.js (DOM 없음), 서버는 lectern/work.py.
// 파일을 쓰는 길 — 사용자가 누를 때: 업무 카드 만들기(POST /api/save 의 create — 새 문서처럼, 있으면 만들지 않는다, 하위 폴더에도),
// 일정 더하기(POST /api/work/card — 고른 WORK.md 의 '일정' 절 끝에 한 줄, 그사이 바뀌었으면 409), 상위에서 고치기(workview.js — 같은 길로 그 줄 하나).

import { S, on, emit } from './store.js';
import { getJSON, getText, postJSON, native } from './api.js';
import { openFolder } from './tabs.js';
import { openTarget, openInNewTab, selectDocTab } from './doctabs.js';
import { solo } from './solo.js';
import { html, setHtml } from './html.js';
import { $, toast, blockedReadOnly, rangeText } from './util.js';
import { t, LANG } from './i18n.js';
import { pickDate } from './datepick.js';
import { mountTree, initWorkView, WHY } from './workview.js';
import {
  readWork, attention, groupOf, dueTodos, dayEvents, daysBetween, isoDay, addDays, nextWeekday, eventLine, insertEvent, fillTemplate, normDay,
  linkTree, treeWhy, trail, CLOSED,
} from './workdata.js';

export const WORK_FILE = 'WORK.md';
const SCHEDULE = LANG === 'en' ? 'Schedule' : '일정';   // i18n-ok — 파일에 쓰는 값
const ALL_DAY = LANG === 'en' ? 'all-day' : '종일';   // i18n-ok — 파일에 쓰는 값
const PRIORITIES = LANG === 'en' ? ['high', 'medium', 'low'] : ['상', '중', '하'];   // i18n-ok — 파일에 쓰는 값
const PROBLEM = {
  front: t('머리 설정이 닫히지 않았습니다 — 맨 앞 --- 의 짝이 없어 상태·마감을 읽지 못합니다'),
  key: t('머리 설정의 키 이름이 틀린 것 같습니다'),
  status: t('정해진 상태 값이 아닙니다 — 예정·진행·지연위험·막힘·보류·완료·중단'),
  due: t('마감 날짜를 읽지 못했습니다 — YYYY-MM-DD'),
  start: t('시작 날짜를 읽지 못했습니다 — YYYY-MM-DD'),
  'start-after-due': t('시작이 마감보다 늦습니다 — 간트에는 마감 날의 점으로 보입니다'),
  'todo-due': t('할 일의 기한을 읽지 못했습니다 — 줄 끝에 (YYYY-MM-DD) 또는 (M/D)'),
  'todo-box': t('체크 칸 모양이 아닙니다 — - [ ] 할 일'),
  'event-date': t('일정의 날짜가 없는 날입니다'),
  'event-time': t('일정의 시각을 읽지 못해 시각 없는 일정으로 봅니다 — HH:MM'),
  'event-text': t('일정에 내용이 없습니다'),
};
const ERROR = {
  'missing-folder': t('폴더가 없습니다 — 옮겼거나 지웠거나 드라이브가 연결되지 않았습니다'),
  'missing-card': t('WORK.md 가 없습니다'),
  slow: t('응답이 없습니다 — 드라이브가 연결되어 있는지 보세요'),
  unreadable: t('읽지 못했습니다'),
  'too-big': t('WORK.md 가 2MB 를 넘어 읽지 않습니다 — 기록을 다른 문서로 옮기세요'),
};

const norm = (p) => String(p || '').replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();
const samePath = (a, b) => !!a && !!b && norm(a) === norm(b);
export const isHome = (tab) => !!tab && samePath(tab.root, S.config.work_home);
const weekday = (day) => new Date(`${day}T12:00:00`).toLocaleDateString(LANG === 'en' ? 'en-US' : 'ko-KR', { weekday: 'short' });

// ---- 읽기 -----------------------------------------------------------------------

/**
 * 업무 현황의 재료 — 서버가 준 글을 오늘 기준으로 읽는다
 * @returns {Promise<{today: string, home: any, homeError: string|null, rows: any[], bad: any[], alerts: boolean}>}
 */
export async function loadBoard() {
  const d = await getJSON('/api/work');
  const today = isoDay(new Date());
  const read = (f) => {
    const card = readWork(f.text, today);
    return { path: f.path, name: f.name, card, mtime: f.mtime, title: card.title || f.name, why: [] };
  };
  const rows = [];
  const bad = [];
  for (const f of d.folders) {
    if (f.error) {
      bad.push(f);
      continue;
    }
    rows.push(read(f));
  }
  const roots = linkTree(rows);   // 업무 나무 (D149) — 부모·하위·하위에서 셈한 상태
  for (const row of rows) {
    row.why = [...attention(row.card, row.mtime, today), ...treeWhy(row)];
    row.group = groupOf({ status: row.eff }, row.why);
  }
  const home = d.home && !d.home.error ? { ...read(d.home), home: true } : null;
  lastBoard = { today, home, homeError: d.home?.error || null, rows, roots, bad, alerts: d.alerts };
  return lastBoard;
}

/** 그 폴더(절대 경로)의 업무 행 — 없으면 null */
const rowAt = (b, folder) => b.rows.find((r) => samePath(r.path, folder)) || null;

/** 문서·폴더(절대 경로)가 속한 가장 깊은 업무 — 일정 더하기의 넣을 곳 */
function rowFor(b, path) {
  const p = norm(path);
  let best = null;
  for (const r of b.rows) if ((p === norm(r.path) || p.startsWith(`${norm(r.path)}/`)) && (!best || norm(r.path).length > norm(best.path).length)) best = r;
  return best;
}

/** 탭의 폴더 기준 상대 경로를 절대 경로로 */
const absPath = (tab, rel) => (rel ? `${String(tab.root).replace(/[\\/]+$/, '')}/${rel}` : String(tab.root));

/** 할 일·일정을 모을 카드들 — 과제들과 공통 */
const allCards = (b) => [...b.rows, ...(b.home ? [b.home] : [])];

// ---- 업무 현황 ---------------------------------------------------------------------

const leftText = (left) => (left < 0 ? t('{n}일 지남', { n: -left }) : left === 0 ? t('오늘') : `D-${left}`);
const timeText = (ev) => (ev.allDay ? t('종일') : ev.time ? `${ev.time}${ev.end ? `–${ev.end}` : ''}` : '');

const MAX_LIST = 50;   // 확인할 줄·할 일·일정 목록에 보이는 수 — 나머지는 개수로
const more = (items) => (items.length > MAX_LIST ? html`<li class="wk-none">${t('그 밖에 {n}개 — WORK.md 에서 봅니다', { n: items.length - MAX_LIST })}</li>` : '');

let shownBoard = null;   // 마지막으로 그린 업무 현황 (누른 행이 무엇인지)

/** 업무 이름에 위 업무들을 붙인 것: '총괄 › 이슈리포트 › 02 리튬' */
const pathTitle = (r) => [...trail(r), r.title].join(' › ');

function boardHtml(b) {
  const parts = [];
  parts.push(html`<div class="wk-head"><h2>${t('업무 현황')}</h2><span class="wk-today">${b.today} (${weekday(b.today)})</span>
    <span class="wk-tools"><button type="button" data-wk="event" title="${t('일정 더하기 (Alt+S)')}">${t('일정 더하기')}</button><button type="button" data-wk="add" title="${t('WORK.md 가 있는 폴더를 열지 않고 목록에 더합니다')}">${t('폴더 더하기')}</button>${b.home ? html`<button type="button" data-wk="home-card">${t('공통 WORK.md 열기')}</button>` : ''}<button type="button" data-wk="refresh" title="${t('다시 읽기')}" aria-label="${t('다시 읽기')}">↻</button></span></div>`);
  if (!b.home) {
    parts.push(html`<p class="wk-note">${t('공통 폴더에 WORK.md 가 없습니다. 과제 밖의 일정·할 일을 적는 곳입니다.')} <button type="button" data-wk="make-home">${t('공통 WORK.md 만들기')}</button></p>`);
  }
  // 주의할 것 — 나무의 어느 깊이에 있든 한데 모아 (접힌 묶음 안의 막힘도 보이게)
  const hot = b.rows.filter((r) => r.why.length && (!CLOSED.has(r.eff) || r.why.includes('kids-open'))).sort((x, y) => String(x.card.due || '9').localeCompare(String(y.card.due || '9')));
  if (hot.length) {
    parts.push(html`<h3>${t('주의할 것')}</h3><ul class="wk-list wk-hotlist">${hot.slice(0, MAX_LIST).map((r) => {
      const left = r.card.due ? daysBetween(b.today, r.card.due) : null;
      return html`<li><button type="button" data-wk-go="${b.rows.indexOf(r)}"><span class="wk-left ${left !== null && left < 0 ? 'late' : left !== null && left <= 3 ? 'soon' : ''}">${left !== null ? leftText(left) : ''}</span><span class="wk-what">${pathTitle(r)}</span><span class="wk-folder">${r.why.map((w) => WHY[w]).join(' · ')}</span></button></li>`;
    })}${more(hot)}</ul>`);
  }
  if (b.rows.length) parts.push(html`<h3>${t('업무')}</h3><div class="wk-tree-slot"></div>`);
  else if (!b.bad.length) {
    parts.push(html`<p class="wk-note">${t('기억한 업무 폴더가 없습니다. WORK.md 가 있는 폴더를 열거나 \'폴더 더하기\'를 누르세요. 프로젝트 탭을 우클릭해 \'업무 카드 만들기\'로 WORK.md 를 만들 수 있습니다.')}</p>`);
  }
  if (b.bad.length) {
    parts.push(html`<h3>${t('읽지 못한 폴더')}</h3><ul class="wk-bad">${b.bad.map((f) => html`<li><span class="wk-folder" title="${f.path}">${f.path}</span>
      <span>${ERROR[f.error] || ''}${f.detail ? ` (${f.detail})` : ''}</span><button type="button" data-wk-drop="${f.path}">${t('목록에서 빼기')}</button></li>`)}</ul>`);
  }
  const cards = allCards(b);
  const todos = dueTodos(cards.map((r) => r.card), b.today);
  const whose = (card) => cards.find((r) => r.card === card);
  const label = (r) => (r.home ? t('공통') : pathTitle(r));
  const ref = (r) => (r.home ? 'home' : String(b.rows.indexOf(r)));
  const checks = cards.filter((r) => !CLOSED.has(r.card.status)).flatMap((r) => r.card.problems.map((p) => ({ r, p })));
  if (checks.length) {
    parts.push(html`<h3>${t('확인할 줄')}</h3><ul class="wk-list wk-check">${checks.slice(0, MAX_LIST).map(({ r, p }) => html`<li><button type="button" data-wk-go="${ref(r)}" data-line="${p.line}" title="${p.text}">
      <span class="wk-left">${rangeText([p.line, p.line])}</span><span class="wk-what">${PROBLEM[p.kind]}${p.hint ? ` (${p.hint})` : ''} — <code>${p.text}</code></span><span class="wk-folder">${label(r)}</span></button></li>`)}${more(checks)}</ul>`);
  }
  parts.push(html`<h3>${t('기한 있는 할 일')}</h3>`);
  parts.push(todos.length ? html`<ul class="wk-list">${todos.slice(0, MAX_LIST).map(({ card, todo, left }) => {
    const r = whose(card);
    return html`<li><button type="button" data-wk-go="${ref(r)}" data-line="${todo.line}"><span class="wk-left ${left < 0 ? 'late' : left === 0 ? 'soon' : ''}">${leftText(left)}</span><span class="wk-what">${todo.text}</span><span class="wk-folder">${label(r)}</span></button></li>`;
  })}${more(todos)}</ul>` : html`<p class="wk-none">${t('이번 주까지 기한이 있는 할 일이 없습니다')}</p>`);
  const events = dayEvents(cards.map((r) => r.card), b.today);
  parts.push(html`<h3>${t('오늘 일정')}</h3>`);
  parts.push(events.length ? html`<ul class="wk-list">${events.slice(0, MAX_LIST).map(({ card, event }) => {
    const r = whose(card);
    return html`<li><button type="button" data-wk-go="${ref(r)}" data-line="${event.line}"><span class="wk-left">${timeText(event)}</span><span class="wk-what">${event.text}</span><span class="wk-folder">${label(r)}</span></button></li>`;
  })}${more(events)}</ul>` : html`<p class="wk-none">${t('오늘 일정이 없습니다')}</p>`);
  return parts;
}

/** 공통 폴더의 폴더 개요(맨 위)에 업무 현황을 그린다. 다시 그리면(같은 칸의 렌더링 순번이 바뀌면) 버린다 */
async function drawBoard(pane) {
  const id = pane.renderId;
  let slot = pane.view.querySelector('.wk-board');
  if (!slot) {
    slot = document.createElement('section');
    slot.className = 'ov-sec wk-board';
    const headEl = pane.view.querySelector('.ov-head');
    if (headEl) headEl.after(slot);
    else pane.view.prepend(slot);
    setHtml(slot, html`<p class="wk-none">${t('업무 현황을 읽는 중…')}</p>`);
  }
  let b;
  try {
    b = await loadBoard();
  } catch (e) {
    if (pane.renderId === id) setHtml(slot, html`<p class="wk-note">${t('업무 현황을 읽지 못했습니다: {error}', { error: e.message })}</p>`);
    return;
  }
  if (pane.renderId !== id || !slot.isConnected) return;
  shownBoard = b;
  setHtml(slot, boardHtml(b));
  const tree = slot.querySelector('.wk-tree-slot');
  if (tree) mountTree(tree, b, { kind: 'board' });
}

const boardPane = () => (S.pane && isHome(S.tab) && S.pane.view.classList.contains('overview') && !S.pane.current?.path ? S.pane : null);

/** 보이는 업무 현황을 다시 그린다 (일정을 넣었거나 목록이 바뀜) */
export function redrawBoard() {
  const pane = boardPane();
  if (pane) drawBoard(pane);
}

/** 업무 현황으로 간다: 공통 폴더를 탭으로 열고 그 개요를. 공통 폴더가 없으면 먼저 정한다 */
export async function openBoard() {
  if (solo) return;
  if (!S.config.work_home) {
    askHome();
    return;
  }
  if (!await openFolder(S.config.work_home)) {   // 공통 폴더를 옮겼거나 지웠다 — 다시 고른다
    askHome(true);
    return;
  }
  // 업무 현황을 보이는 문서 탭이 이미 있으면 그 탭으로 (지금 보는 문서를 개요로 바꾸지 않는다)
  const shown = S.tab.panes.find((pane) => pane.current?.type === 'overview' && !pane.current.path);
  if (shown) {
    if (shown !== S.pane) await selectDocTab(shown);
    drawBoard(shown);
  } else emit('open', { type: 'overview', path: '' });
}

/** 품은 폴더인지 — inner 가 outer 와 같거나 그 아래 */
const within = (inner, outer) => norm(inner) === norm(outer) || norm(inner).startsWith(`${norm(outer)}/`);

/**
 * 그 폴더의 WORK.md 를 연다 (line 이면 그 줄로). folder 가 'home' 이면 공통 폴더.
 * 하위 업무는 그 폴더를 따로 열지 않고 품은 프로젝트의 탭에서 연다 (D149) — 지금 탭, 열린 탭 가운데 가장 바깥 것, 없으면 나무의 맨 위 업무 폴더
 */
export async function openCard(folder, line = 0) {
  const path = folder === 'home' ? S.config.work_home : folder;
  if (!path) return;
  let root = path;
  if (folder !== 'home') {
    const tabs = S.tabs.filter((x) => !x.readonly && within(path, x.root)).sort((a, b) => norm(a.root).length - norm(b.root).length);
    const top = lastBoard ? (() => { let r = rowAt(lastBoard, path); while (r?.parent) r = r.parent; return r?.path; })() : null;
    root = (S.tab && tabs.includes(S.tab) ? S.tab.root : tabs[0]?.root) || top || path;
  }
  if (!await openFolder(root)) return;
  const rel = norm(path) === norm(root) ? '' : String(path).replace(/\\/g, '/').slice(String(root).replace(/\\/g, '/').replace(/\/+$/, '').length + 1);
  const want = rel ? `${rel}/${WORK_FILE}` : WORK_FILE;
  const doc = S.fileMap.has(want) ? want : [...S.fileMap.keys()].find((k) => k.toLowerCase() === want.toLowerCase());
  if (!doc) {
    toast(t('이 폴더에 WORK.md 가 없습니다'), 'error');
    return;
  }
  await openTarget({ type: 'doc', path: doc });
  if (line) emit('go-line', { line });
}

// ---- 상위에서 모아 보기 (D149): 총괄·묶음 폴더의 폴더 개요, 상위 WORK.md 아래의 '하위 업무' ------------------------

let lastBoard = null;   // 마지막으로 읽은 업무 나무 (하위 업무를 품은 프로젝트를 찾을 때)

/** 폴더 개요: 그 폴더의 WORK.md 에 하위 업무가 있으면 맨 위에 '이 폴더의 업무' (공통 폴더의 업무 현황과 따로) */
async function drawFolderWork(pane) {
  const id = pane.renderId;
  pane.view.querySelector('.wk-folder-work')?.remove();
  if (!pane.tab || pane.tab.readonly || !pane.tab.fileMap.has(pane.current?.path ? `${pane.current.path}/${WORK_FILE}` : WORK_FILE)) return;
  let b;
  try {
    b = await loadBoard();
  } catch {
    return;
  }
  const row = rowAt(b, absPath(pane.tab, pane.current?.path || ''));
  if (pane.renderId !== id || !row?.kids.length) return;
  const sec = document.createElement('section');
  sec.className = 'ov-sec wk-board wk-folder-work';
  setHtml(sec, html`<div class="wk-head"><h2>${t('이 폴더의 업무')}</h2><span class="wk-today">${t('하위 업무를 모아 봅니다 — 여기서 고치면 그 업무의 WORK.md 가 고쳐집니다')}</span></div><div class="wk-tree-slot"></div>`);
  const headEl = pane.view.querySelector('.ov-head');
  if (headEl) headEl.after(sec);
  else pane.view.prepend(sec);
  mountTree(sec.querySelector('.wk-tree-slot'), b, { kind: 'folder', scope: row });
}

/** 문서 화면: WORK.md 에 하위 업무가 있으면 문서 아래(본문 밖, 같은 스크롤)에 '하위 업무' 칸 — 파일에는 없다 */
async function drawUnder(pane) {
  const id = pane.renderId;
  const old = pane.scroller.querySelector(':scope > .wk-under');
  const path = pane.current?.type === 'doc' ? pane.current.path || '' : '';
  const name = path.split('/').pop();
  if (!pane.tab || pane.tab.readonly || name !== WORK_FILE) {
    old?.remove();
    return;
  }
  let b;
  try {
    b = await loadBoard();
  } catch {
    return;
  }
  const row = rowAt(b, absPath(pane.tab, path.split('/').slice(0, -1).join('/')));
  if (pane.renderId !== id) return;
  if (!row?.kids.length) {
    old?.remove();
    return;
  }
  const sec = old || document.createElement('section');
  sec.className = 'wk-under wk-board';
  setHtml(sec, html`<div class="wk-head"><h2>${t('하위 업무')}</h2><span class="wk-today">${t('하위 폴더의 WORK.md 를 모아 보입니다 — 이 칸은 파일에 없습니다. 여기서 고치면 그 업무의 WORK.md 가 고쳐집니다')}</span></div><div class="wk-tree-slot"></div>`);
  if (!old) pane.scroller.append(sec);
  mountTree(sec.querySelector('.wk-tree-slot'), b, { kind: 'under', scope: row });
}

/** 업무가 바뀌었다 (상위에서 고치기·일정 더하기) — 보이는 업무 칸을 모두 다시 그린다 */
function redrawWork() {
  redrawBoard();
  for (const pane of S.panes) {
    if (!pane.tab) continue;
    if (pane.view.querySelector('.wk-folder-work')) drawFolderWork(pane);
    if (pane.scroller.querySelector(':scope > .wk-under')) drawUnder(pane);
  }
}

// ---- 묻는 창 (공통 폴더 정하기·WORK.md 가 없는 폴더) -----------------------------------------

function overlay(id, body) {
  let box = $(`#${id}`);
  if (!box) {
    box = document.createElement('div');
    box.id = id;
    box.className = 'overlay';
    box.hidden = true;
    document.body.append(box);
    box.addEventListener('mousedown', (e) => { if (e.target === box) box.hidden = true; });
    box.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      e.stopPropagation();
      box.hidden = true;
    });
  }
  setHtml(box, body);
  return box;
}

/** 버튼 몇 개로 묻는다. buttons: [{label, primary, action}] — 누르면 창을 닫고 action */
function ask(title, text, buttons) {
  const box = overlay('lec-workask', html`<div class="palette-box insert-box" role="dialog" aria-labelledby="lec-workask-title">
    <div class="gallery-head"><span id="lec-workask-title">${title}</span></div><p class="insert-msg wk-ask">${text}</p>
    <div class="gallery-foot"><span class="gallery-keys"></span>${buttons.map((b, i) => html`<button type="button" data-i="${i}" class="${b.primary ? 'primary' : ''}">${b.label}</button>`)}</div></div>`);
  box.onclick = (e) => {
    const btn = e.target.closest('button[data-i]');
    if (!btn) return;
    box.hidden = true;
    buttons[Number(btn.dataset.i)].action?.();
  };
  box.hidden = false;
  box.querySelector('button.primary, button')?.focus();
}

function askHome(gone = false) {
  ask(t('업무 현황 — 공통 폴더 정하기'),
    gone ? t('공통 폴더를 열지 못했습니다: {path} — 옮겼거나 지웠으면 다른 폴더를 고르세요. 과제 폴더들의 목록은 그대로입니다.', { path: S.config.work_home })
      : t('업무 현황은 공통 폴더에 보입니다. 공통 폴더에는 과제 밖의 일정·할 일을 적는 WORK.md 와 주간·월간 정리를 둡니다. 보통 폴더 하나를 고르세요 — 예: 문서\\Lectern 업무 (고르는 창에서 새 폴더를 만들 수 있습니다).'),
    [{ label: t('폴더 고르기…'), primary: true, action: pickHome }, { label: t('그만두기') }]);
}

/** 공통 폴더를 고른다 — 업무 현황에서 물었으면 고른 뒤 업무 현황으로 (설정 창에서는 그대로) */
export async function pickHome({ open = true } = {}) {
  const path = await native.chooseFolder();
  if (!path) return;
  try {
    await postJSON('/api/work/home', { path });
    S.config = await getJSON('/api/config');
  } catch (e) {
    toast(t('공통 폴더로 정하지 못했습니다: {error}', { error: e.message }), 'error', 6000);
    return;
  }
  emit('work-settings');
  if (open) await openBoard();
}

/** 설정 창의 '업무 관리' 칸: 공통 폴더와 업무 폴더 목록 (빼기) */
function renderSettings() {
  const homeEl = $('#lec-work-home');
  if (!homeEl) return;
  homeEl.textContent = S.config.work_home || t('공통 폴더를 정하지 않았습니다');
  homeEl.title = S.config.work_home || '';
  $('#lec-work-clear').hidden = !S.config.work_home;
  const list = S.config.work_folders || [];
  setHtml($('#lec-work-folders'), list.length
    ? list.map((p) => html`<li><span title="${p}">${p}</span><button type="button" class="text-btn" data-wk-drop="${p}" title="${t('목록에서만 뺍니다 — 파일은 그대로')}">${t('빼기')}</button></li>`)
    : html`<li class="wk-none">${t('기억한 업무 폴더가 없습니다 — WORK.md 가 있는 폴더를 열면 더해집니다')}</li>`);
}

/** 공통 폴더를 비운다 (설정 창) — 폴더와 파일은 그대로 */
export async function clearHome() {
  await postJSON('/api/work/home', { path: null });
  S.config = await getJSON('/api/config');
  emit('work-settings');
}

/** 업무 폴더 목록에서 뺀다 — 파일은 그대로 */
export async function dropFolder(path) {
  await postJSON('/api/work/folders', { remove: path });
  S.config = await getJSON('/api/config');
  emit('work-settings');
  redrawBoard();
}

async function addFolder() {
  const path = await native.chooseFolder();
  if (!path) return;
  try {
    await postJSON('/api/work/folders', { add: path });
  } catch (e) {
    if (e.code === 'no-card') {
      ask(t('폴더 더하기'), t('{path} 에 WORK.md 가 없습니다. 그 폴더를 열고 업무 카드를 만들까요?', { path }),
        [{ label: t('열고 만들기'), primary: true, action: async () => { if (await openFolder(path)) askCard(S.tab); } }, { label: t('그만두기') }]);
    } else toast(t('더하지 못했습니다: {error}', { error: e.message }), 'error', 6000);
    return;
  }
  S.config = await getJSON('/api/config');
  toast(t('업무 폴더 목록에 더했습니다: {path}', { path }));
  emit('work-settings');
  redrawBoard();
}

// ---- 업무 카드 만들기 ------------------------------------------------------------------

/**
 * 날짜 칸 (D149 — 달력 입력): 글로 쓰거나(YYYY-MM-DD — 2026.11.20 도 받는다) 옆의 달력 단추·Ctrl+; 로 고른다.
 * 창을 띄운 쪽이 wireDates(box) 로 단추를 잇는다
 */
const dateInput = (id, value = '') => html`<span class="wk-datefield"><input id="${id}" type="text" inputmode="numeric" placeholder="YYYY-MM-DD" value="${value}" spellcheck="false" autocomplete="off"><button type="button" class="icon-btn small wk-cal" data-cal="${id}" title="${t('달력 (Ctrl+;)')}" aria-label="${t('달력 (Ctrl+;)')}"><svg><use href="#i-cal"/></svg></button></span>`;

/** 창 안의 날짜 칸들: 달력 단추와 칸 안의 Ctrl+; */
function wireDates(box, title = '') {
  if (box.dataset.dates) return;   // 창은 다시 쓰인다 — 한 번만 잇는다
  box.dataset.dates = '1';
  const open = async (input) => {
    const day = await pickDate({ at: input, value: normDay(input.value) || '', clear: true, title });
    if (day === null) return;
    input.value = day;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  };
  box.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-cal]');
    if (btn) open(/** @type {HTMLInputElement} */ (box.querySelector(`#${btn.dataset.cal}`)));
  });
  box.addEventListener('keydown', (e) => {
    if (e.ctrlKey && !e.altKey && !e.shiftKey && e.code === 'Semicolon' && e.target.closest?.('.wk-datefield input')) {
      e.preventDefault();
      e.stopPropagation();
      open(e.target);
    }
  });
}

/** 날짜 칸의 값 — 비었으면 '', 날짜로 읽으면 'YYYY-MM-DD', 못 읽으면 null */
const dateValue = (input) => (!input.value.trim() ? '' : normDay(input.value));

/**
 * 기본 틀로 그 탭의 폴더(folder — 탭 기준 상대 경로, '' 이면 맨 위)에 WORK.md 를 만들고 연다.
 * kind: project(업무 하나 — work 틀) | group(묶음·총괄 — work-group 틀, 상태는 비워 하위에서 셈 — D149) | item(작은 업무 — work-item 틀) | common(공통용 틀)
 */
async function makeCard(tab, { kind = 'project', folder = '', title = '', due = '', priority = '' } = {}) {
  const name = { common: 'work-common', group: 'work-group', item: 'work-item' }[kind] || 'work';
  const template = await getText(`/static/templates/${name}.${LANG}.md`);
  const text = kind === 'common' ? template : fillTemplate(template, { title, due, priority });
  const path = folder ? `${folder}/${WORK_FILE}` : WORK_FILE;
  await postJSON('/api/save', { p: tab.id, path, text, create: true });
  S.config = await getJSON('/api/config');   // 업무 폴더 목록에 들어갔다
  emit('work-settings');
  emit('work-changed');
  if (tab === S.tab) await openInNewTab({ type: 'doc', path });
}

/** 업무 카드 만들기 창 — 이미 있으면 연다. 공통 폴더 맨 위면 공통용 틀로 바로 만든다. folder: 탭 기준 상대 경로 (하위 폴더에도 — D149) */
export function askCard(tab = S.tab, folder = '') {
  if (!tab || blockedReadOnly(tab)) return;
  const path = folder ? `${folder}/${WORK_FILE}` : WORK_FILE;
  if (tab.fileMap.has(path)) {
    openTarget({ type: 'doc', path });
    return;
  }
  if (isHome(tab) && !folder) {
    makeCard(tab, { kind: 'common' }).catch((e) => toast(t('만들지 못했습니다: {error}', { error: e.message }), 'error', 6000));
    return;
  }
  const folderName = folder ? folder.split('/').pop() : tab.name;
  const box = overlay('lec-workcard', html`<div class="palette-box insert-box" role="dialog" aria-labelledby="lec-workcard-head">
    <div class="gallery-head"><span id="lec-workcard-head">${t('업무 카드 만들기')}</span></div>
    <p class="insert-msg">${folder ? t('{folder} 폴더에 WORK.md 를 기본 틀로 만듭니다. 위 폴더의 업무가 이 업무를 모아 봅니다.', { folder }) : t('이 프로젝트 맨 위에 WORK.md 를 기본 틀로 만듭니다. 업무 현황과 알림이 이 파일을 읽습니다.')}</p>
    <div class="newdoc-title"><label for="lec-workcard-kind">${t('종류')}</label><select id="lec-workcard-kind">
      <option value="project" ${folder ? '' : 'selected'}>${t('업무 — 현재 상태·할 일·일정·결정·기록·자료')}</option>
      <option value="group">${t('묶음·총괄 — 하위 폴더의 업무를 모음, 상태는 하위에서 셈')}</option>
      <option value="item" ${folder ? 'selected' : ''}>${t('작은 업무 — 할 일·일정·기록 (예: 이슈리포트 하나)')}</option></select></div>
    <div class="newdoc-title"><label for="lec-workcard-title">${t('제목')}</label><input id="lec-workcard-title" type="text" spellcheck="false" autocomplete="off"></div>
    <div class="newdoc-title"><label for="lec-workcard-due">${t('마감')}</label>${dateInput('lec-workcard-due')}
      <label for="lec-workcard-pri">${t('우선')}</label><select id="lec-workcard-pri">${PRIORITIES.map((p, i) => html`<option value="${p}" ${i === 1 ? 'selected' : ''}>${p}</option>`)}</select></div>
    <p id="lec-workcard-msg" class="insert-msg bad" role="alert" hidden></p>
    <div class="gallery-foot"><span class="gallery-keys">${t('Enter 만들기 · Esc 그만두기')}</span><button id="lec-workcard-go" type="button" class="primary">${t('만들기')}</button><button id="lec-workcard-no" type="button">${t('그만두기')}</button></div></div>`);
  wireDates(box, t('마감'));
  const titleEl = /** @type {HTMLInputElement} */ ($('#lec-workcard-title'));
  titleEl.value = folderName;
  const go = async () => {
    const title = titleEl.value.trim() || folderName;
    const due = dateValue(/** @type {HTMLInputElement} */ ($('#lec-workcard-due')));
    const msg = $('#lec-workcard-msg');
    if (due === null) {
      msg.textContent = t('마감 날짜를 읽지 못했습니다 — YYYY-MM-DD 로 쓰거나 달력에서 고르세요');
      msg.hidden = false;
      return;
    }
    const kind = /** @type {HTMLSelectElement} */ ($('#lec-workcard-kind')).value;
    try {
      await makeCard(tab, { kind, folder, title, due, priority: /** @type {HTMLSelectElement} */ ($('#lec-workcard-pri')).value });
    } catch (e) {
      const msg = $('#lec-workcard-msg');
      msg.textContent = e.message;
      msg.hidden = false;
      return;
    }
    box.hidden = true;
    toast(t('WORK.md 를 만들었습니다 — 업무 폴더 목록에 들어갔습니다'));
  };
  $('#lec-workcard-go').onclick = go;
  $('#lec-workcard-no').onclick = () => { box.hidden = true; };
  box.onkeydown = (e) => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
      e.preventDefault();
      go();
    }
  };
  box.hidden = false;
  titleEl.select();
  titleEl.focus();
}

// ---- 일정 더하기 ---------------------------------------------------------------------

/** 일정 더하기 창 — 날짜·시각·내용·넣을 곳. 넣을 곳은 공통과 끝나지 않은 과제들 (지금 탭에 WORK.md 가 있으면 그것) */
/** 일정 더하기 창. date·folder: 처음 날짜와 넣을 곳 (D153 — 달력에서 날짜를 누르면). 단축키·단추로 열면 오늘·지금 보는 업무 */
export async function openEventDialog({ date = null, folder = null } = {}) {
  if (solo) return;
  let b;
  try {
    b = await loadBoard();
  } catch (e) {
    toast(t('업무 현황을 읽지 못했습니다: {error}', { error: e.message }), 'error');
    return;
  }
  // 넣을 곳: 공통, 그리고 끝나지 않은 업무를 나무 차례로 (하위는 위 업무 이름을 앞에 — D149)
  const order = [];
  const walk = (r) => {
    if (!CLOSED.has(r.eff)) order.push(r);
    r.kids.forEach(walk);
  };
  b.roots.forEach(walk);
  const targets = [...(b.home ? [{ folder: b.home.path, label: t('공통 — {name}', { name: b.home.name }) }] : []),
    ...order.map((r) => ({ folder: r.path, label: `${'　'.repeat(r.depth)}${pathTitle(r)} — ${r.name}` }))];
  if (!targets.length) {
    ask(t('일정 더하기'), t('일정을 넣을 WORK.md 가 없습니다. 업무 현황에서 공통 폴더를 정하거나, 프로젝트 탭을 우클릭해 업무 카드를 만드세요.'),
      [{ label: t('업무 현황'), primary: true, action: openBoard }, { label: t('그만두기') }]);
    return;
  }
  // 지금 보는 문서·폴더가 속한 가장 깊은 업무가 기본 (하위 폴더의 문서를 보고 있으면 그 하위 업무)
  const viewing = S.tab && !isHome(S.tab) ? rowFor(b, absPath(S.tab, S.view?.path || '')) : null;
  const here = viewing ? targets.find((x) => samePath(x.folder, viewing.path)) : null;
  const asked = typeof folder === 'string' ? targets.find((x) => samePath(x.folder, folder)) : null;
  const chosen = asked || here || targets[0];
  const today = b.today;
  const dows = LANG === 'en' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'] : ['월', '화', '수', '목', '금'];   // i18n-ok — 요일 단추, 화면 언어마다
  const box = overlay('lec-workevent', html`<div class="palette-box insert-box" role="dialog" aria-labelledby="lec-workevent-head">
    <div class="gallery-head"><span id="lec-workevent-head">${t('일정 더하기')}</span></div>
    <div class="newdoc-title"><label for="lec-workevent-date">${t('날짜')}</label>${dateInput('lec-workevent-date', typeof date === 'string' && date ? date : today)}
      <span class="wk-days"><button type="button" data-day="0">${t('오늘')}</button><button type="button" data-day="1">${t('내일')}</button>${dows.map((d, i) => html`<button type="button" data-dow="${i + 1}">${d}</button>`)}</span></div>
    <div class="newdoc-title"><label for="lec-workevent-time">${t('시각')}</label><input id="lec-workevent-time" type="time"><span>~</span><input id="lec-workevent-end" type="time" aria-label="${t('끝나는 시각')}">
      <label class="wk-allday"><input id="lec-workevent-allday" type="checkbox">${t('종일')}</label></div>
    <div class="newdoc-title"><label for="lec-workevent-text">${t('내용')}</label><input id="lec-workevent-text" type="text" spellcheck="false" autocomplete="off"></div>
    <div class="newdoc-title"><label for="lec-workevent-where">${t('넣을 곳')}</label><select id="lec-workevent-where">${targets.map((x, i) => html`<option value="${i}" ${x === chosen ? 'selected' : ''}>${x.label}</option>`)}</select></div>
    <p class="insert-msg wk-preview">${t('넣을 줄')}: <code id="lec-workevent-line"></code></p>
    <p id="lec-workevent-msg" class="insert-msg bad" role="alert" hidden></p>
    <div class="gallery-foot"><span class="gallery-keys">${t('Enter 넣기 · Esc 그만두기')}</span><button id="lec-workevent-go" type="button" class="primary">${t('넣기')}</button><button id="lec-workevent-no" type="button">${t('그만두기')}</button></div></div>`);
  const field = (id) => /** @type {HTMLInputElement} */ ($(`#lec-workevent-${id}`));
  const value = () => ({ date: normDay(field('date').value) || '', time: field('time').value, end: field('end').value, allDay: field('allday').checked, text: field('text').value });
  wireDates(box, t('일정 날짜'));
  const say = (text) => {
    const msg = $('#lec-workevent-msg');
    msg.textContent = text;
    msg.hidden = !text;
  };
  const preview = () => {
    const v = value();
    field('time').disabled = v.allDay;
    field('end').disabled = v.allDay || !v.time;
    $('#lec-workevent-line').textContent = v.date && v.text.trim() ? eventLine(v, ALL_DAY) : '';
  };
  box.oninput = preview;
  box.onchange = preview;
  box.onclick = (e) => {
    const btn = e.target.closest('button[data-day], button[data-dow]');
    if (!btn) return;
    field('date').value = btn.dataset.day != null ? addDays(today, Number(btn.dataset.day)) : nextWeekday(today, Number(btn.dataset.dow));
    preview();
  };
  const go = async () => {
    const v = value();
    if (!v.date) return say(field('date').value.trim() ? t('날짜를 읽지 못했습니다 — YYYY-MM-DD 로 쓰거나 달력에서 고르세요') : t('날짜를 고르세요'));
    if (!v.text.trim()) return say(t('내용을 쓰세요'));
    if (!v.allDay && v.time && v.end && v.end <= v.time) return say(t('끝나는 시각이 시작보다 앞입니다 — 고치거나 끝나는 시각을 비우세요'));
    const target = targets[Number(/** @type {HTMLSelectElement} */ ($('#lec-workevent-where')).value)];
    try {
      await addEvent(target.folder, eventLine(v, ALL_DAY), target.label);
    } catch (e) {
      return say(e.status === 409 ? t('그사이 그 WORK.md 가 바뀌었습니다 — 넣기를 다시 누르세요') : e.message);
    }
    box.hidden = true;
  };
  $('#lec-workevent-go').onclick = go;
  $('#lec-workevent-no').onclick = () => { box.hidden = true; };
  box.onkeydown = (e) => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
      e.preventDefault();
      go();
    }
  };
  preview();
  box.hidden = false;
  field('text').focus();
}

/** 고른 WORK.md 의 '일정' 절 끝에 한 줄 — 읽은 뒤로 바뀌었으면 서버가 409. 넣은 뒤 알림 칸에 되돌리기 */
async function addEvent(folder, line, label) {
  const src = await getJSON(`/api/work/card?folder=${encodeURIComponent(folder)}`);
  const { text, line: at } = insertEvent(src.text, line, SCHEDULE);
  const saved = await postJSON('/api/work/card', { folder, text, hash: src.hash });
  emit('work-changed');   // 업무 칸을 다시 그린다 (redrawWork)
  notice({
    title: t('일정을 넣었습니다 — {where}', { where: label }), lines: [line],
    actions: [
      { label: t('열기'), action: () => openCard(folder, at) },
      { label: t('되돌리기'), close: true, action: () => undoEvent(folder, src.text, saved.hash) },
    ],
  });
}

async function undoEvent(folder, before, hash) {
  try {
    await postJSON('/api/work/card', { folder, text: before, hash });
  } catch (e) {
    toast(e.status === 409 ? t('그 뒤에 WORK.md 가 바뀌어 되돌리지 않았습니다 — 파일에서 직접 지우세요') : t('되돌리지 못했습니다: {error}', { error: e.message }), 'error', 6000);
    return;
  }
  toast(t('넣은 일정을 뺐습니다'));
  emit('work-changed');   // 업무 칸을 다시 그린다 (redrawWork)
}

// ---- 알림 칸 (닫을 때까지 남는다 — 창 오른쪽 아래) ---------------------------------------------

const MAX_NOTICES = 6;

/**
 * 알림 칸에 하나를 띄운다. actions: [{label, action, close}] — close 면 누른 뒤 닫는다 (열기는 남겨 둔다)
 * @param {{title: string, lines?: string[], actions?: {label: string, action?: Function, close?: boolean}[], kind?: string}} n
 */
export function notice({ title, lines = [], actions = [], kind = '' }) {
  let stack = $('#lec-work-notes');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'lec-work-notes';
    stack.setAttribute('role', 'log');
    stack.setAttribute('aria-live', 'polite');
    document.body.append(stack);
  }
  const card = document.createElement('div');
  card.className = `wk-notice${kind ? ` ${kind}` : ''}`;
  setHtml(card, html`<div class="wk-n-head"><b>${title}</b><button type="button" class="wk-n-close" title="${t('닫기')}" aria-label="${t('닫기')}">×</button></div>
    ${lines.length ? html`<ul>${lines.map((x) => html`<li>${x}</li>`)}</ul>` : ''}
    ${actions.length ? html`<div class="wk-n-acts">${actions.map((a, i) => html`<button type="button" data-i="${i}">${a.label}</button>`)}</div>` : ''}`);
  card.addEventListener('click', (e) => {
    if (e.target.closest('.wk-n-close')) {
      card.remove();
      return;
    }
    const btn = e.target.closest('button[data-i]');
    if (!btn) return;
    const act = actions[Number(btn.dataset.i)];
    if (act.close) card.remove();
    act.action?.();
  });
  stack.append(card);
  while (stack.children.length > MAX_NOTICES) stack.firstElementChild.remove();
}

// ---- 잇기 ---------------------------------------------------------------------------

function onBoardClick(e) {
  const slot = e.target.closest('.wk-board');
  if (!slot) return;
  const act = e.target.closest('button[data-wk]')?.dataset.wk;
  if (act === 'event') openEventDialog();
  else if (act === 'add') addFolder();
  else if (act === 'refresh') redrawBoard();
  else if (act === 'home-card' || act === 'make-home') askCard(S.tab);
  if (act) return;
  const drop = e.target.closest('button[data-wk-drop]');
  if (drop) {
    dropFolder(drop.dataset.wkDrop).catch((err) => toast(err.message, 'error'));
    return;
  }
  const go = e.target.closest('button[data-wk-go]');
  if (go && shownBoard) {
    const which = go.dataset.wkGo;
    openCard(which === 'home' ? 'home' : shownBoard.rows[Number(which)]?.path, Number(go.dataset.line) || 0);
  }
}

export function initWork() {
  if (solo) return;   // 업무 현황·알림은 메인 창에서만
  initWorkView({ openCard, addEvent: (date, folder) => openEventDialog({ date, folder }) });
  // 'rendered' 는 nav.js 가 pane.current 를 새 화면으로 바꾸기 전에 온다 — 한 박자 뒤에 본다 (같은 칸에서 문서를 바꿔 열 때)
  on('rendered', (pane) => setTimeout(() => {
    const overview = pane.view.classList.contains('overview');
    if (overview && !pane.current?.path && isHome(pane.tab)) drawBoard(pane);
    else if (overview) drawFolderWork(pane);   // 총괄·묶음 폴더의 개요 — 하위 업무를 모아 (D149)
    drawUnder(pane);   // 상위 WORK.md 아래의 '하위 업무' (아니면 지난 것을 치운다)
  }));
  on('work-changed', redrawWork);
  on('work-card', (d) => askCard(d?.tab || S.tab, d?.folder || ''));
  on('settings-open', renderSettings);
  on('work-settings', renderSettings);
  $('#lec-panes').addEventListener('click', onBoardClick);
  $('#lec-btn-work')?.addEventListener('click', openBoard);
  $('#lec-work-pick')?.addEventListener('click', () => pickHome({ open: false }));
  $('#lec-work-clear')?.addEventListener('click', () => clearHome().catch((e) => toast(e.message, 'error')));
  $('#lec-work-folders')?.addEventListener('click', (e) => {
    const drop = e.target.closest('button[data-wk-drop]');
    if (drop) dropFolder(drop.dataset.wkDrop).catch((err) => toast(err.message, 'error'));
  });
}
