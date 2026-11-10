// 업무 관리 (D124): 업무 현황(공통 폴더의 폴더 개요 맨 위), 업무 카드 만들기, 일정 더하기, 폴더 더하기, 공통 폴더 정하기, 알림 칸.
// WORK.md 의 글을 읽어 계산하는 것은 workdata.js (DOM 없음), 서버는 lectern/work.py (GET /api/work 등).
// 파일을 쓰는 길은 둘뿐이다 — 사용자가 누를 때: 업무 카드 만들기(POST /api/save 의 create — 새 문서처럼, 있으면 만들지 않는다),
// 일정 더하기(POST /api/work/card — 고른 WORK.md 의 '일정' 절 끝에 한 줄, 그사이 바뀌었으면 409).

import { S, on, emit } from './store.js';
import { getJSON, getText, postJSON, native } from './api.js';
import { openFolder } from './tabs.js';
import { openTarget, openInNewTab, selectDocTab } from './doctabs.js';
import { solo } from './solo.js';
import { html, setHtml } from './html.js';
import { $, toast, timeAgo, formatDateTime, blockedReadOnly } from './util.js';
import { t, LANG } from './i18n.js';
import {
  readWork, attention, groupOf, byDue, dueTodos, dayEvents, daysBetween, isoDay, addDays, nextWeekday, eventLine, insertEvent, fillTemplate,
  STALE_DAYS, CLOSED,
} from './workdata.js';

export const WORK_FILE = 'WORK.md';
const SCHEDULE = LANG === 'en' ? 'Schedule' : '일정';   // i18n-ok — 파일에 쓰는 값
const ALL_DAY = LANG === 'en' ? 'all-day' : '종일';   // i18n-ok — 파일에 쓰는 값
const PRIORITIES = LANG === 'en' ? ['high', 'medium', 'low'] : ['상', '중', '하'];   // i18n-ok — 파일에 쓰는 값
const STATUS_LABEL = {
  planned: t('예정'), active: t('진행'), 'at-risk': t('지연위험'), blocked: t('막힘'), 'on-hold': t('보류'), done: t('완료'), dropped: t('중단'),
};
const WHY = {
  blocked: t('막힘'), 'at-risk': t('지연위험'), overdue: t('마감 지남'), 'due-soon': t('마감 임박'), stale: t('{n}일 넘게 안 바뀜', { n: STALE_DAYS }),
};
const PROBLEM = {
  front: t('머리 설정이 닫히지 않았습니다 — 맨 앞 --- 의 짝이 없어 상태·마감을 읽지 못합니다'),
  key: t('머리 설정의 키 이름이 틀린 것 같습니다'),
  status: t('정해진 상태 값이 아닙니다 — 예정·진행·지연위험·막힘·보류·완료·중단'),
  due: t('마감 날짜를 읽지 못했습니다 — YYYY-MM-DD'),
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
    const row = read(f);
    row.why = attention(row.card, row.mtime, today);
    row.group = groupOf(row.card, row.why);
    rows.push(row);
  }
  const home = d.home && !d.home.error ? { ...read(d.home), home: true } : null;
  return { today, home, homeError: d.home?.error || null, rows, bad, alerts: d.alerts };
}

/** 할 일·일정을 모을 카드들 — 과제들과 공통 */
const allCards = (b) => [...b.rows, ...(b.home ? [b.home] : [])];

// ---- 업무 현황 ---------------------------------------------------------------------

const leftText = (left) => (left < 0 ? t('{n}일 지남', { n: -left }) : left === 0 ? t('오늘') : `D-${left}`);
const statusHtml = (card) => {
  const key = card.status;
  return key ? html`<span class="wk-st st-${key}">${STATUS_LABEL[key]}</span>` : html`<span class="wk-st st-unknown" title="${t('정해진 값이 아닙니다 — 예정·진행·지연위험·막힘·보류·완료·중단')}">${card.statusText || t('값 없음')}</span>`;
};
const timeText = (ev) => (ev.allDay ? t('종일') : ev.time ? `${ev.time}${ev.end ? `–${ev.end}` : ''}` : '');

let shownBoard = null;   // 마지막으로 그린 업무 현황 (누른 행이 무엇인지)

function rowHtml(row, i, today) {
  const { card } = row;
  const left = card.due ? daysBetween(today, card.due) : null;
  const open = card.todos.filter((x) => !x.done).length;
  return html`<tr data-wk-row="${i}" class="${row.why.length ? 'wk-hot' : ''}">
    <td>${statusHtml(card)}</td>
    <td class="wk-title"><button type="button" data-wk-row="${i}" title="${row.path}">${row.title}</button><span class="wk-folder">${row.name}</span>${row.why.map((w) => html`<span class="wk-why why-${w}">${WHY[w]}</span>`)}${card.problems.length ? html`<span class="wk-why why-check">${t('확인할 줄 {n}', { n: card.problems.length })}</span>` : ''}</td>
    <td>${card.priority}</td>
    <td class="wk-due" title="${card.dueText}">${card.due ? html`${card.due.slice(5)} <span class="${left < 0 ? 'late' : left <= 3 ? 'soon' : ''}">${leftText(left)}</span>` : card.dueText}</td>
    <td class="wk-num">${card.todos.length ? `${open} / ${card.todos.length}` : ''}</td>
    <td class="wk-when" title="${row.mtime ? formatDateTime(row.mtime) : ''}">${row.mtime ? timeAgo(row.mtime) : ''}</td></tr>`;
}

function boardHtml(b) {
  const parts = [];
  parts.push(html`<div class="wk-head"><h2>${t('업무 현황')}</h2><span class="wk-today">${b.today} (${weekday(b.today)})</span>
    <span class="wk-tools"><button type="button" data-wk="event" title="${t('일정 더하기 (Alt+S)')}">${t('일정 더하기')}</button><button type="button" data-wk="add" title="${t('WORK.md 가 있는 폴더를 열지 않고 목록에 더합니다')}">${t('폴더 더하기')}</button>${b.home ? html`<button type="button" data-wk="home-card">${t('공통 WORK.md 열기')}</button>` : ''}<button type="button" data-wk="refresh" title="${t('다시 읽기')}" aria-label="${t('다시 읽기')}">↻</button></span></div>`);
  if (!b.home) {
    parts.push(html`<p class="wk-note">${t('공통 폴더에 WORK.md 가 없습니다. 과제 밖의 일정·할 일을 적는 곳입니다.')} <button type="button" data-wk="make-home">${t('공통 WORK.md 만들기')}</button></p>`);
  }
  const order = ['attention', 'open', 'hold'];
  const live = b.rows.filter((r) => r.group !== 'closed').sort((x, y) => order.indexOf(x.group) - order.indexOf(y.group) || byDue(x.card, y.card));
  const closed = b.rows.filter((r) => r.group === 'closed').sort((x, y) => byDue(x.card, y.card));
  const index = (r) => b.rows.indexOf(r);
  const head = html`<thead><tr><th>${t('상태')}</th><th>${t('과제')}</th><th>${t('우선')}</th><th>${t('마감')}</th><th>${t('할 일')}</th><th>${t('갱신')}</th></tr></thead>`;
  if (live.length) parts.push(html`<table class="wk-table">${head}<tbody>${live.map((r) => rowHtml(r, index(r), b.today))}</tbody></table>`);
  else if (!b.rows.length && !b.bad.length) {
    parts.push(html`<p class="wk-note">${t('기억한 업무 폴더가 없습니다. WORK.md 가 있는 폴더를 열거나 \'폴더 더하기\'를 누르세요. 프로젝트 탭을 우클릭해 \'업무 카드 만들기\'로 WORK.md 를 만들 수 있습니다.')}</p>`);
  }
  if (closed.length) {
    parts.push(html`<details class="wk-closed"><summary>${t('완료·중단 {n}개', { n: closed.length })}</summary><table class="wk-table">${head}<tbody>${closed.map((r) => rowHtml(r, index(r), b.today))}</tbody></table></details>`);
  }
  if (b.bad.length) {
    parts.push(html`<h3>${t('읽지 못한 폴더')}</h3><ul class="wk-bad">${b.bad.map((f) => html`<li><span class="wk-folder" title="${f.path}">${f.path}</span>
      <span>${ERROR[f.error] || ''}${f.detail ? ` (${f.detail})` : ''}</span><button type="button" data-wk-drop="${f.path}">${t('목록에서 빼기')}</button></li>`)}</ul>`);
  }
  const cards = allCards(b);
  const todos = dueTodos(cards.map((r) => r.card), b.today);
  const whose = (card) => cards.find((r) => r.card === card);
  const label = (r) => (r.home ? t('공통') : r.title);
  const ref = (r) => (r.home ? 'home' : String(b.rows.indexOf(r)));
  const checks = cards.filter((r) => !CLOSED.has(r.card.status)).flatMap((r) => r.card.problems.map((p) => ({ r, p })));
  if (checks.length) {
    parts.push(html`<h3>${t('확인할 줄')}</h3><ul class="wk-list wk-check">${checks.map(({ r, p }) => html`<li><button type="button" data-wk-go="${ref(r)}" data-line="${p.line}" title="${p.text}">
      <span class="wk-left">${t('{n}행', { n: p.line })}</span><span class="wk-what">${PROBLEM[p.kind]}${p.hint ? ` (${p.hint})` : ''} — <code>${p.text}</code></span><span class="wk-folder">${label(r)}</span></button></li>`)}</ul>`);
  }
  parts.push(html`<h3>${t('기한 있는 할 일')}</h3>`);
  parts.push(todos.length ? html`<ul class="wk-list">${todos.map(({ card, todo, left }) => {
    const r = whose(card);
    return html`<li><button type="button" data-wk-go="${ref(r)}" data-line="${todo.line}"><span class="wk-left ${left < 0 ? 'late' : left === 0 ? 'soon' : ''}">${leftText(left)}</span><span class="wk-what">${todo.text}</span><span class="wk-folder">${label(r)}</span></button></li>`;
  })}</ul>` : html`<p class="wk-none">${t('이번 주까지 기한이 있는 할 일이 없습니다')}</p>`);
  const events = dayEvents(cards.map((r) => r.card), b.today);
  parts.push(html`<h3>${t('오늘 일정')}</h3>`);
  parts.push(events.length ? html`<ul class="wk-list">${events.map(({ card, event }) => {
    const r = whose(card);
    return html`<li><button type="button" data-wk-go="${ref(r)}" data-line="${event.line}"><span class="wk-left">${timeText(event)}</span><span class="wk-what">${event.text}</span><span class="wk-folder">${label(r)}</span></button></li>`;
  })}</ul>` : html`<p class="wk-none">${t('오늘 일정이 없습니다')}</p>`);
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

/** 그 폴더의 WORK.md 를 연다 (line 이면 그 줄로). folder 가 'home' 이면 공통 폴더 */
export async function openCard(folder, line = 0) {
  const path = folder === 'home' ? S.config.work_home : folder;
  if (!path || !await openFolder(path)) return;
  if (!S.fileMap.has(WORK_FILE)) {
    toast(t('이 폴더에 WORK.md 가 없습니다'), 'error');
    return;
  }
  await openTarget({ type: 'doc', path: WORK_FILE });
  if (line) emit('go-line', { line });
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

/** 기본 틀(web/templates/work.ko.md 등)로 그 탭의 맨 위에 WORK.md 를 만들고 연다. common 이면 공통용 틀 */
async function makeCard(tab, { common = false, title = '', due = '', priority = '' } = {}) {
  const template = await getText(`/static/templates/${common ? 'work-common' : 'work'}.${LANG}.md`);
  const text = common ? template : fillTemplate(template, { title, due, priority });
  await postJSON('/api/save', { p: tab.id, path: WORK_FILE, text, create: true });
  S.config = await getJSON('/api/config');   // 업무 폴더 목록에 들어갔다
  emit('work-settings');
  if (tab === S.tab) await openInNewTab({ type: 'doc', path: WORK_FILE });
}

/** 업무 카드 만들기 창 — 이미 있으면 연다. 공통 폴더면 공통용 틀로 바로 만든다 */
export function askCard(tab = S.tab) {
  if (!tab || blockedReadOnly(tab)) return;
  if (tab.fileMap.has(WORK_FILE)) {
    openTarget({ type: 'doc', path: WORK_FILE });
    return;
  }
  if (isHome(tab)) {
    makeCard(tab, { common: true }).catch((e) => toast(t('만들지 못했습니다: {error}', { error: e.message }), 'error', 6000));
    return;
  }
  const box = overlay('lec-workcard', html`<div class="palette-box insert-box" role="dialog" aria-labelledby="lec-workcard-head">
    <div class="gallery-head"><span id="lec-workcard-head">${t('업무 카드 만들기')}</span></div>
    <p class="insert-msg">${t('이 프로젝트 맨 위에 WORK.md 를 기본 틀로 만듭니다. 업무 현황과 알림이 이 파일을 읽습니다.')}</p>
    <div class="newdoc-title"><label for="lec-workcard-title">${t('제목')}</label><input id="lec-workcard-title" type="text" spellcheck="false" autocomplete="off"></div>
    <div class="newdoc-title"><label for="lec-workcard-due">${t('마감')}</label><input id="lec-workcard-due" type="date">
      <label for="lec-workcard-pri">${t('우선')}</label><select id="lec-workcard-pri">${PRIORITIES.map((p, i) => html`<option value="${p}" ${i === 1 ? 'selected' : ''}>${p}</option>`)}</select></div>
    <p id="lec-workcard-msg" class="insert-msg bad" role="alert" hidden></p>
    <div class="gallery-foot"><span class="gallery-keys">${t('Enter 만들기 · Esc 그만두기')}</span><button id="lec-workcard-go" type="button" class="primary">${t('만들기')}</button><button id="lec-workcard-no" type="button">${t('그만두기')}</button></div></div>`);
  const titleEl = /** @type {HTMLInputElement} */ ($('#lec-workcard-title'));
  titleEl.value = tab.name;
  const go = async () => {
    const title = titleEl.value.trim() || tab.name;
    try {
      await makeCard(tab, { title, due: /** @type {HTMLInputElement} */ ($('#lec-workcard-due')).value, priority: /** @type {HTMLSelectElement} */ ($('#lec-workcard-pri')).value });
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
export async function openEventDialog() {
  if (solo) return;
  let b;
  try {
    b = await loadBoard();
  } catch (e) {
    toast(t('업무 현황을 읽지 못했습니다: {error}', { error: e.message }), 'error');
    return;
  }
  const targets = [...(b.home ? [{ folder: b.home.path, label: t('공통 — {name}', { name: b.home.name }) }] : []),
    ...b.rows.filter((r) => !CLOSED.has(r.card.status)).map((r) => ({ folder: r.path, label: `${r.title} — ${r.name}` }))];
  if (!targets.length) {
    ask(t('일정 더하기'), t('일정을 넣을 WORK.md 가 없습니다. 업무 현황에서 공통 폴더를 정하거나, 프로젝트 탭을 우클릭해 업무 카드를 만드세요.'),
      [{ label: t('업무 현황'), primary: true, action: openBoard }, { label: t('그만두기') }]);
    return;
  }
  const here = S.tab && !isHome(S.tab) ? targets.find((x) => samePath(x.folder, S.tab.root)) : null;
  const chosen = here || targets[0];
  const today = b.today;
  const dows = LANG === 'en' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'] : ['월', '화', '수', '목', '금'];   // i18n-ok — 요일 단추, 화면 언어마다
  const box = overlay('lec-workevent', html`<div class="palette-box insert-box" role="dialog" aria-labelledby="lec-workevent-head">
    <div class="gallery-head"><span id="lec-workevent-head">${t('일정 더하기')}</span></div>
    <div class="newdoc-title"><label for="lec-workevent-date">${t('날짜')}</label><input id="lec-workevent-date" type="date" value="${today}">
      <span class="wk-days"><button type="button" data-day="0">${t('오늘')}</button><button type="button" data-day="1">${t('내일')}</button>${dows.map((d, i) => html`<button type="button" data-dow="${i + 1}">${d}</button>`)}</span></div>
    <div class="newdoc-title"><label for="lec-workevent-time">${t('시각')}</label><input id="lec-workevent-time" type="time"><span>~</span><input id="lec-workevent-end" type="time" aria-label="${t('끝나는 시각')}">
      <label class="wk-allday"><input id="lec-workevent-allday" type="checkbox">${t('종일')}</label></div>
    <div class="newdoc-title"><label for="lec-workevent-text">${t('내용')}</label><input id="lec-workevent-text" type="text" spellcheck="false" autocomplete="off"></div>
    <div class="newdoc-title"><label for="lec-workevent-where">${t('넣을 곳')}</label><select id="lec-workevent-where">${targets.map((x, i) => html`<option value="${i}" ${x === chosen ? 'selected' : ''}>${x.label}</option>`)}</select></div>
    <p class="insert-msg wk-preview">${t('넣을 줄')}: <code id="lec-workevent-line"></code></p>
    <p id="lec-workevent-msg" class="insert-msg bad" role="alert" hidden></p>
    <div class="gallery-foot"><span class="gallery-keys">${t('Enter 넣기 · Esc 그만두기')}</span><button id="lec-workevent-go" type="button" class="primary">${t('넣기')}</button><button id="lec-workevent-no" type="button">${t('그만두기')}</button></div></div>`);
  const field = (id) => /** @type {HTMLInputElement} */ ($(`#lec-workevent-${id}`));
  const value = () => ({ date: field('date').value, time: field('time').value, end: field('end').value, allDay: field('allday').checked, text: field('text').value });
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
    if (!v.date) return say(t('날짜를 고르세요'));
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
  redrawBoard();
  emit('work-changed');
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
  redrawBoard();
  emit('work-changed');
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
    return;
  }
  const row = e.target.closest('[data-wk-row]');
  if (row && shownBoard) openCard(shownBoard.rows[Number(row.dataset.wkRow)]?.path);
}

export function initWork() {
  if (solo) return;   // 업무 현황·알림은 메인 창에서만
  on('rendered', (pane) => {
    if (pane.view.classList.contains('overview') && !pane.current?.path && isHome(pane.tab)) drawBoard(pane);
  });
  on('work-card', (d) => askCard(d?.tab || S.tab));
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
