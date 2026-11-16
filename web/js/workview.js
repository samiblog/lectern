// 업무 나무와 칸반 (D149): 업무 현황, 총괄·묶음 폴더의 폴더 개요, 상위 WORK.md 아래의 '하위 업무' 칸이 함께 쓴다.
// 상위에서 모아 보이고, 상위에서 고치면 그 업무의 WORK.md 한 줄만 고친다 (원칙 1 — 사용자가 고른 칸 하나, 그 파일만):
// 상태·마감·우선(머리 설정), 할 일 체크·기한(그 줄), 할 일 더하기('할 일' 절 끝). 글 자체는 그 파일을 열어서 고친다.
// 쓰는 길은 일정 더하기와 같다 — GET /api/work/card 로 읽고 고쳐 POST (그사이 바뀌었으면 409, 다시 그린다).
// 업무를 여는 함수는 work.js 가 initWorkView 로 넘긴다 (work.js 가 이 모듈을 부르므로 거꾸로 import 하면 순환).

import { S, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { showMenu } from './ui.js';
import { html, setHtml } from './html.js';
import { toast, timeAgo, formatDateTime, rangeText } from './util.js';
import { t, LANG } from './i18n.js';
import { pickDate } from './datepick.js';
import {
  STATUSES, CLOSED, LANES, laneOf, leafCounts, trail, daysBetween, setMeta, setTodo, insertTodo, todoLine, statusWord, byDue, STALE_DAYS,
} from './workdata.js';

export const STATUS_LABEL = {
  planned: t('예정'), active: t('진행'), 'at-risk': t('지연위험'), blocked: t('막힘'), 'on-hold': t('보류'), done: t('완료'), dropped: t('중단'),
};
export const WHY = {
  blocked: t('막힘'), 'at-risk': t('지연위험'), overdue: t('마감 지남'), 'due-soon': t('마감 임박'), stale: t('{n}일 넘게 안 바뀜', { n: STALE_DAYS }),
  'kids-open': t('하위가 아직 열림'), 'kid-late': t('하위 마감이 더 늦음'),
};
const LANE_LABEL = { planned: t('예정'), active: t('진행'), watch: t('주의 (막힘·지연위험)'), hold: t('보류'), closed: t('완료·중단'), none: t('상태 없음') };
const PRIORITIES = LANG === 'en' ? ['high', 'medium', 'low'] : ['상', '중', '하'];   // i18n-ok — 파일에 쓰는 값
const TODO_HEAD = LANG === 'en' ? 'Todo' : '할 일';   // i18n-ok — 파일에 쓰는 값
const OPEN_DEPTH = 2;   // 처음에 펼쳐 두는 깊이 — 세 단계(0·1·2)가 보인다
const MAX_LANE = 40;    // 칸반 한 칸에 보이는 카드 수

let openCard = async (_path, _line) => {};
const hosts = new WeakMap();   // 칸 요소 → {b, kind, scope}
const toggled = new Map();     // 경로 → 펼침(true)·접음(false) — 사용자가 바꾼 것만 (이번 실행 동안)
const todoOpen = new Set();    // 할 일을 펼친 업무의 경로
const closedOpen = new Set();  // 끝난 하위를 펼친 업무의 경로
const modes = { board: 'list', folder: 'list', under: 'list' };   // 칸마다 목록·칸반 (이번 실행 동안)

const key = (p) => String(p || '').replace(/\\/g, '/').toLowerCase();
const leftText = (left) => (left < 0 ? t('{n}일 지남', { n: -left }) : left === 0 ? t('오늘') : `D-${left}`);
const leftClass = (left) => (left === null ? '' : left < 0 ? 'late' : left <= 3 ? 'soon' : '');

export function statusHtml(row) {
  const k = row.eff;
  if (!k) {
    const blank = !String(row.card.statusText || '').trim();
    return html`<span class="wk-st st-unknown" title="${blank ? t('상태를 비워 두었습니다 — 하위 업무가 있으면 하위에서 셈하고, 없으면 상태를 정하세요') : t('정해진 값이 아닙니다 — 예정·진행·지연위험·막힘·보류·완료·중단')}">${blank ? t('비어 있음') : row.card.statusText}</span>`;
  }
  return html`<span class="wk-st st-${k}${row.derived ? ' derived' : ''}" title="${row.derived ? t('비워 둔 상태 — 하위 업무에서 셈했습니다') : ''}">${STATUS_LABEL[k]}${row.derived ? '*' : ''}</span>`;
}

/** 행의 하위 요약: '하위 5 · 진행 3 · 막힘 1 · 완료 1' */
function kidsHtml(row) {
  if (!row.kids?.length) return '';
  const c = leafCounts(row);
  const parts = STATUSES.map((s) => (c.byStatus[s.key] ? `${STATUS_LABEL[s.key]} ${c.byStatus[s.key]}` : '')).filter(Boolean);
  return html`<span class="wk-kids">${t('하위 {n}', { n: c.total })}${parts.length ? ` · ${parts.join(' · ')}` : ''}</span>`;
}

const isOpen = (row) => (toggled.has(key(row.path)) ? toggled.get(key(row.path)) : row.depth - (row.baseDepth || 0) < OPEN_DEPTH);

function sortKids(kids) {
  const order = (r) => (CLOSED.has(r.eff) ? 3 : r.why?.length ? 0 : r.eff === 'on-hold' ? 2 : 1);
  return [...kids].sort((a, b) => order(a) - order(b) || byDue({ due: a.card.due || a.next, title: a.title }, { due: b.card.due || b.next, title: b.title }));
}

function rowHtml(b, row, depth) {
  const i = b.rows.indexOf(row);
  const { card } = row;
  const left = card.due ? daysBetween(b.today, card.due) : null;
  const open = card.todos.filter((x) => !x.done).length;
  const kids = row.kids?.length;
  const expanded = kids && isOpen(row);
  const out = [html`<tr class="wk-tr${row.why?.length ? ' wk-hot' : ''}${CLOSED.has(row.eff) ? ' wk-done' : ''}" data-wk-i="${i}">
    <td><button type="button" class="wk-cell" data-wk-act="status" title="${t('상태 바꾸기 — 이 업무의 WORK.md 에 씁니다')}">${statusHtml(row)}</button></td>
    <td class="wk-title" style="--wk-depth: ${depth}">${kids ? html`<button type="button" class="wk-twist" data-wk-act="twist" aria-expanded="${expanded ? 'true' : 'false'}" aria-label="${expanded ? t('접기') : t('펼치기')}">${expanded ? '▾' : '▸'}</button>` : html`<span class="wk-twist-sp"></span>`}<button type="button" class="wk-open" data-wk-act="open" title="${row.path}">${row.title}</button><span class="wk-folder">${row.name}</span>${(row.why || []).map((w) => html`<span class="wk-why why-${w}">${WHY[w]}</span>`)}${card.problems.length ? html`<span class="wk-why why-check">${t('확인할 줄 {n}', { n: card.problems.length })}</span>` : ''}${kidsHtml(row)}</td>
    <td><button type="button" class="wk-cell" data-wk-act="priority" title="${t('우선 바꾸기')}">${card.priority || html`<span class="wk-faint">—</span>`}</button></td>
    <td class="wk-due"><button type="button" class="wk-cell" data-wk-act="due" title="${card.dueText || t('마감 정하기 — 달력')}">${card.due ? html`${card.due.slice(5)} <span class="${leftClass(left)}">${leftText(left)}</span>` : card.dueText || html`<span class="wk-faint">${t('마감 없음')}</span>`}</button>${kids && row.next ? html`<span class="wk-next" title="${t('열린 하위 업무 가운데 가장 이른 마감')}">${t('다음 {day}', { day: row.next.slice(5) })}</span>` : ''}</td>
    <td class="wk-num"><button type="button" class="wk-cell" data-wk-act="todos" aria-expanded="${todoOpen.has(key(row.path)) ? 'true' : 'false'}" title="${t('할 일 보기·체크·더하기')}">${card.todos.length ? `${open} / ${card.todos.length}` : html`<span class="wk-faint">+</span>`}</button></td>
    <td class="wk-when" title="${row.mtime ? formatDateTime(row.mtime) : ''}">${row.mtime ? timeAgo(row.mtime) : ''}</td></tr>`];
  if (todoOpen.has(key(row.path))) out.push(todosHtml(b, row, depth));
  if (expanded) {
    const sorted = sortKids(row.kids);
    const done = sorted.filter((r) => CLOSED.has(r.eff));
    const live = sorted.filter((r) => !CLOSED.has(r.eff));
    for (const kid of live) out.push(...rowHtml(b, kid, depth + 1));
    if (done.length && (closedOpen.has(key(row.path)) || !live.length)) for (const kid of done) out.push(...rowHtml(b, kid, depth + 1));
    else if (done.length) {
      out.push(html`<tr class="wk-tr wk-more" data-wk-i="${i}"><td></td><td class="wk-title" style="--wk-depth: ${depth + 1}" colspan="5"><button type="button" data-wk-act="closed">${t('완료·중단 {n}건 보이기', { n: done.length })}</button></td></tr>`);
    }
  }
  return out;
}

function todosHtml(b, row, depth) {
  const i = b.rows.indexOf(row);
  const items = row.card.todos.map((td) => {
    const left = td.due ? daysBetween(b.today, td.due) : null;
    return html`<li class="${td.done ? 'done' : ''}"><label><input type="checkbox" data-wk-todo="${td.line}" ${td.done ? 'checked' : ''}><span>${td.text}</span></label>
      <button type="button" class="wk-chip" data-wk-tdue="${td.line}" title="${t('기한 — 달력')}">${td.due ? html`${td.due.slice(5)} <span class="${td.done ? '' : leftClass(left)}">${td.done ? '' : leftText(left)}</span>` : html`<span class="wk-faint">${t('기한')}</span>`}</button>
      <button type="button" class="wk-chip wk-go" data-wk-line="${td.line}" title="${t('WORK.md 의 그 줄로')}">${rangeText([td.line, td.line])}</button></li>`;   // 줄 번호 ('{n}행' 은 개수라 영어가 '12 rows')
  });
  return html`<tr class="wk-todos-row" data-wk-i="${i}"><td></td><td colspan="5" style="--wk-depth: ${depth}"><ul class="wk-todos">${items}</ul>
    <div class="wk-addtodo"><input type="text" data-wk-add="1" placeholder="${t('할 일 더하기 — 쓰고 Enter (이 업무의 WORK.md 에)')}" spellcheck="false" autocomplete="off"><button type="button" class="wk-chip" data-wk-act="adddue" title="${t('기한 — 달력')}">${t('기한')}</button></div></td></tr>`;
}

/** 나무 표 — roots 부터 (depth 는 칸 안에서 0 부터) */
function treeHtml(b, roots) {
  const head = html`<thead><tr><th>${t('상태')}</th><th>${t('업무')}</th><th>${t('우선')}</th><th>${t('마감')}</th><th>${t('할 일')}</th><th>${t('갱신')}</th></tr></thead>`;
  return html`<table class="wk-table wk-tree">${head}<tbody>${sortKids(roots).flatMap((r) => rowHtml(b, r, 0))}</tbody></table>`;
}

/** 칸반 — 끝 업무(하위가 없는 업무)를 상태 다섯 칸에. scope 의 경로는 카드 위에 작게 */
function kanbanHtml(b, leaves, scope) {
  const lanes = [...LANES.map((l) => l.key), ...(leaves.some((r) => laneOf(r.eff) === 'none') ? ['none'] : [])];
  return html`<div class="wk-kanban">${lanes.map((lane) => {
    const cards = sortKids(leaves.filter((r) => laneOf(r.eff) === lane));
    return html`<section class="wk-lane lane-${lane}" data-wk-lane="${lane}"><h4>${LANE_LABEL[lane]} <span>${cards.length}</span></h4>
      ${cards.slice(0, MAX_LANE).map((r) => cardHtml(b, r, scope))}${cards.length > MAX_LANE ? html`<p class="wk-none">${t('그 밖에 {n}개', { n: cards.length - MAX_LANE })}</p>` : ''}</section>`;
  })}</div>`;
}

function cardHtml(b, r, scope) {
  const i = b.rows.indexOf(r);
  const { card } = r;
  const left = card.due ? daysBetween(b.today, card.due) : null;
  const open = card.todos.filter((x) => !x.done);
  const where = trail(r, scope);
  return html`<article class="wk-kcard${r.why?.length ? ' wk-hot' : ''}" draggable="true" data-wk-i="${i}" tabindex="0">
    ${where.length ? html`<div class="wk-k-trail">${where.join(' › ')}</div>` : ''}
    <button type="button" class="wk-k-title" data-wk-act="open" title="${r.path}">${r.title}</button>
    <div class="wk-k-meta">${statusHtml(r)}<button type="button" class="wk-chip" data-wk-act="due">${card.due ? html`${card.due.slice(5)} <span class="${leftClass(left)}">${leftText(left)}</span>` : html`<span class="wk-faint">${t('마감 없음')}</span>`}</button>${card.priority ? html`<span class="wk-pri">${card.priority}</span>` : ''}${card.todos.length ? html`<span class="wk-faint">${t('할 일 {a}/{b}', { a: card.todos.length - open.length, b: card.todos.length })}</span>` : ''}</div>
    ${open[0] ? html`<div class="wk-k-next" title="${t('다음 할 일')}">${open[0].text}</div>` : ''}</article>`;
}

/**
 * 칸에 업무를 그린다. kind: board(업무 현황 — 모든 업무) | folder(총괄·묶음 폴더 개요 — 그 업무와 하위) | under(상위 WORK.md 아래 — 하위만)
 * @param {HTMLElement} host
 * @param {any} b loadBoard 의 결과 (rows 에 나무가 이어져 있다)
 * @param {{kind: 'board'|'folder'|'under', scope?: any}} o scope: folder·under 의 그 업무 행
 */
export function mountTree(host, b, { kind, scope = null }) {
  hosts.set(host, { b, kind, scope });
  host.classList.add('wk-host');
  const mode = modes[kind];
  const roots = kind === 'board' ? b.roots : kind === 'folder' ? [scope] : scope.kids;
  for (const r of b.rows) r.baseDepth = kind === 'under' ? (scope?.depth ?? 0) + 1 : kind === 'folder' ? scope?.depth ?? 0 : 0;
  const leaves = roots.flatMap((r) => (r.kids?.length ? r.leaves : [r]));
  const live = kind === 'board' ? roots.filter((r) => !CLOSED.has(r.eff)) : roots;
  const closed = kind === 'board' ? roots.filter((r) => CLOSED.has(r.eff)) : [];
  const switcher = html`<span class="wk-mode" role="group" aria-label="${t('보기')}"><button type="button" data-wk-mode="list" aria-pressed="${mode === 'list' ? 'true' : 'false'}">${t('목록')}</button><button type="button" data-wk-mode="kanban" aria-pressed="${mode === 'kanban' ? 'true' : 'false'}">${t('칸반')}</button></span>`;
  const body = mode === 'kanban'
    ? (leaves.length ? kanbanHtml(b, leaves, kind === 'board' ? null : kind === 'under' ? scope : scope?.parent) : html`<p class="wk-none">${t('업무가 없습니다')}</p>`)
    : html`${live.length ? treeHtml(b, live) : html`<p class="wk-none">${t('업무가 없습니다')}</p>`}${closed.length ? html`<details class="wk-closed"><summary>${t('완료·중단 {n}개', { n: closed.length })}</summary>${treeHtml(b, closed)}</details>` : ''}`;
  setHtml(host, html`<div class="wk-tree-head">${switcher}${mode === 'kanban' ? html`<span class="wk-faint">${t('카드를 다른 칸으로 끌어 놓으면 그 업무의 WORK.md 상태가 바뀝니다')}</span>` : ''}</div>${body}`);
}

// ---- 고치기 — 그 업무의 WORK.md 한 줄 ---------------------------------------------------------

/**
 * row 의 WORK.md 를 읽어 change(글) 로 고친 글을 쓴다. change 가 null 이면 그 줄이 그사이 바뀐 것 — 쓰지 않고 다시 그린다.
 * @returns {Promise<boolean>}
 */
export async function editRow(row, change, done = '') {
  let src;
  try {
    src = await getJSON(`/api/work/card?folder=${encodeURIComponent(row.path)}`);
  } catch (e) {
    toast(t('WORK.md 를 읽지 못했습니다: {error}', { error: e.message }), 'error', 6000);
    emit('work-changed');
    return false;
  }
  const next = change(src.text);
  if (next == null) {
    toast(t('그 줄이 그사이 바뀌어 고치지 않았습니다 — 다시 그렸습니다'), 'error', 6000);
    emit('work-changed');
    return false;
  }
  if (next === src.text) return true;
  try {
    await postJSON('/api/work/card', { folder: row.path, text: next, hash: src.hash });
  } catch (e) {
    toast(e.status === 409 ? t('그사이 그 WORK.md 가 바뀌었습니다 — 다시 그렸습니다. 한 번 더 고르세요') : t('고치지 못했습니다: {error}', { error: e.message }), 'error', 6000);
    emit('work-changed');
    return false;
  }
  toast(done || t('{name} 의 WORK.md 에 반영했습니다', { name: row.title }));
  emit('work-changed');
  return true;
}

const setStatus = (row, k) => editRow(row, (text) => setMeta(text, 'status', k ? statusWord(k, row.card.statusText, LANG) : ''),
  k ? t('{name}: 상태를 {status}(으)로 — WORK.md 에 반영했습니다', { name: row.title, status: STATUS_LABEL[k] }) : t('{name}: 상태를 비웠습니다 — 하위에서 셈합니다', { name: row.title }));

function statusMenu(row, x, y) {
  /** @type {any[]} */
  const items = STATUSES.map((s) => ({ label: STATUS_LABEL[s.key], hint: row.card.status === s.key ? t('지금') : '', action: () => setStatus(row, s.key) }));
  if (row.kids?.length) items.push('-', { label: t('비우기 — 하위에서 셈'), hint: !row.card.statusText ? t('지금') : '', action: () => setStatus(row, '') });
  showMenu(x, y, [{ header: t('상태 — {name}', { name: row.title }) }, ...items]);
}

function priorityMenu(row, x, y) {
  /** @type {any[]} */
  const items = PRIORITIES.map((p) => ({ label: p, hint: row.card.priority === p ? t('지금') : '', action: () => editRow(row, (text) => setMeta(text, 'priority', p)) }));
  items.push('-', { label: t('비우기'), action: () => editRow(row, (text) => setMeta(text, 'priority', '')) });
  showMenu(x, y, [{ header: t('우선 — {name}', { name: row.title }) }, ...items]);
}

/** 달력에 점을 찍을 날: 마감·할 일 기한·일정 */
function marksOf(b) {
  const out = new Set();
  for (const r of b.rows) {
    if (r.card.due) out.add(r.card.due);
    for (const td of r.card.todos) if (td.due && !td.done) out.add(td.due);
    for (const ev of r.card.events) out.add(ev.date);
  }
  return out;
}

async function pickDue(b, row, at) {
  const day = await pickDate({ at, value: row.card.due || '', marks: marksOf(b), clear: true, title: t('마감 — {name}', { name: row.title }) });
  if (day === null || day === (row.card.due || '')) return;
  await editRow(row, (text) => setMeta(text, 'due', day), day ? t('{name}: 마감을 {day}(으)로 — WORK.md 에 반영했습니다', { name: row.title, day }) : t('{name}: 마감을 비웠습니다', { name: row.title }));
}

function rowMenu(b, row, x, y) {
  showMenu(x, y, [{ header: row.title },
    { label: t('이 업무 열기'), action: () => openCard(row.path) },
    { label: t('상태 바꾸기…'), action: () => statusMenu(row, x, y) },
    { label: t('마감 바꾸기…'), action: () => pickDue(b, row, { x, y }) },
    { label: t('우선 바꾸기…'), action: () => priorityMenu(row, x, y) }]);
}

/** 칸반에 놓았을 때: 칸의 상태로. 주의 칸은 막힘·지연위험, 완료 칸은 완료·중단 가운데 고른다 */
function dropOn(row, lane, x, y) {
  const now = laneOf(row.eff);
  if (lane === now && lane !== 'watch' && lane !== 'closed') return;
  const pick = (keys) => showMenu(x, y, [{ header: t('상태 — {name}', { name: row.title }) }, ...keys.map((k) => ({ label: STATUS_LABEL[k], action: () => setStatus(row, k) }))]);
  if (lane === 'watch') pick(['blocked', 'at-risk']);
  else if (lane === 'closed') pick(['done', 'dropped']);
  else if (lane !== 'none') setStatus(row, LANES.find((l) => l.key === lane).statuses[0]);
}

// ---- 잇기 -------------------------------------------------------------------------------

const hostOf = (el) => el?.closest?.('.wk-host');
function target(e) {
  const host = hostOf(e.target);
  const data = host && hosts.get(host);
  if (!data) return null;
  const el = e.target.closest('[data-wk-i]');
  const row = el ? data.b.rows[Number(el.dataset.wkI)] : null;
  return { host, ...data, row };
}

function redraw(host) {
  const data = hosts.get(host);
  if (data) mountTree(host, data.b, data);
}

async function onClick(e) {
  const at = target(e);
  if (!at) return;
  const mode = e.target.closest('button[data-wk-mode]');
  if (mode) {
    modes[at.kind] = mode.dataset.wkMode;
    redraw(at.host);
    return;
  }
  const { b, row } = at;
  if (!row) return;
  const act = e.target.closest('[data-wk-act]')?.dataset.wkAct;
  const btn = e.target.closest('button');
  const r = btn?.getBoundingClientRect();
  if (act === 'twist') {
    toggled.set(key(row.path), !isOpen(row));
    redraw(at.host);
  } else if (act === 'closed') {
    closedOpen.add(key(row.path));
    redraw(at.host);
  } else if (act === 'todos') {
    const k = key(row.path);
    if (todoOpen.has(k)) todoOpen.delete(k);
    else todoOpen.add(k);
    redraw(at.host);
    if (todoOpen.has(k)) at.host.querySelector(`.wk-todos-row[data-wk-i="${b.rows.indexOf(row)}"] input[data-wk-add]`)?.focus();
  } else if (act === 'status') statusMenu(row, r.left, r.bottom + 2);
  else if (act === 'priority') priorityMenu(row, r.left, r.bottom + 2);
  else if (act === 'due') pickDue(b, row, btn);
  else if (act === 'adddue') {
    const input = btn.parentElement.querySelector('input[data-wk-add]');
    const day = await pickDate({ at: btn, value: btn.dataset.day || '', marks: marksOf(b), clear: true, title: t('새 할 일의 기한') });
    if (day === null) return;
    btn.dataset.day = day;
    btn.textContent = day ? day.slice(5) : t('기한');
    input?.focus();
  } else if (act === 'open') openCard(row.path);
  else if (e.target.closest('button[data-wk-tdue]')) {
    const line = Number(e.target.closest('button[data-wk-tdue]').dataset.wkTdue);
    const td = row.card.todos.find((x) => x.line === line);
    if (!td) return;
    const day = await pickDate({ at: btn, value: td.due || '', marks: marksOf(b), clear: true, title: t('기한 — {text}', { text: td.text }) });
    if (day === null || day === (td.due || '')) return;
    editRow(row, (text) => setTodo(text, line, td.text, { due: day }));
  } else if (e.target.closest('button[data-wk-line]')) openCard(row.path, Number(e.target.closest('button[data-wk-line]').dataset.wkLine));
  else if (!btn && !e.target.closest('input, label, .wk-todos-row') && e.target.closest('tr.wk-tr:not(.wk-more)')) openCard(row.path);
}

function onChange(e) {
  const box = e.target.closest?.('input[data-wk-todo]');
  if (!box) return;
  const at = target(e);
  if (!at?.row) return;
  const line = Number(box.dataset.wkTodo);
  const td = at.row.card.todos.find((x) => x.line === line);
  if (!td) return;
  editRow(at.row, (text) => setTodo(text, line, td.text, { done: box.checked }),
    box.checked ? t('{name}: 할 일을 했다고 표시했습니다', { name: at.row.title }) : t('{name}: 할 일을 다시 열었습니다', { name: at.row.title }));
}

function onKey(e) {
  const input = e.target.closest?.('input[data-wk-add]');
  if (input && e.key === 'Enter' && !e.isComposing) {
    e.preventDefault();
    const at = target(e);
    const words = input.value.trim();
    if (!at?.row || !words) return;
    const due = input.parentElement.querySelector('[data-wk-act="adddue"]')?.dataset.day || '';
    editRow(at.row, (text) => insertTodo(text, todoLine(words, due), TODO_HEAD).text, t('{name}: 할 일을 더했습니다', { name: at.row.title }));
    return;
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches?.('.wk-kcard')) {
    e.preventDefault();
    const at = target(e);
    if (at?.row) openCard(at.row.path);
  }
  if (e.key === 'ContextMenu' && e.target.matches?.('.wk-kcard')) {
    e.preventDefault();
    const at = target(e);
    const r = e.target.getBoundingClientRect();
    if (at?.row) rowMenu(at.b, at.row, r.left, r.bottom);
  }
}

function onContext(e) {
  const at = target(e);
  if (!at?.row || e.target.closest('input')) return;
  e.preventDefault();
  e.stopPropagation();
  rowMenu(at.b, at.row, e.clientX, e.clientY);
}

let dragging = null;
function onDragStart(e) {
  const card = e.target.closest?.('.wk-kcard');
  if (!card || !hostOf(card)) return;
  dragging = { host: hostOf(card), i: Number(card.dataset.wkI) };
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', card.querySelector('.wk-k-title')?.textContent || '');
  card.classList.add('dragging');
}
function onDragOver(e) {
  const lane = e.target.closest?.('.wk-lane');
  if (!dragging || !lane || hostOf(lane) !== dragging.host) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  for (const x of dragging.host.querySelectorAll('.wk-lane.over')) if (x !== lane) x.classList.remove('over');
  lane.classList.add('over');
}
function onDrop(e) {
  const lane = e.target.closest?.('.wk-lane');
  if (!dragging || !lane || hostOf(lane) !== dragging.host) return;
  e.preventDefault();
  const data = hosts.get(dragging.host);
  const row = data?.b.rows[dragging.i];
  lane.classList.remove('over');
  if (row) dropOn(row, lane.dataset.wkLane, e.clientX, e.clientY);
  dragging = null;
}
function onDragEnd() {
  for (const x of document.querySelectorAll('.wk-kcard.dragging, .wk-lane.over')) x.classList.remove('dragging', 'over');
  dragging = null;
}

/** work.js 가 부른다 — 업무를 여는 함수(그 폴더의 WORK.md, line 이면 그 줄로)를 넘긴다 */
export function initWorkView(o) {
  openCard = o.openCard;
  const root = document.getElementById('lec-panes') || document.body;
  root.addEventListener('click', onClick);
  root.addEventListener('change', onChange);
  root.addEventListener('keydown', onKey);
  root.addEventListener('contextmenu', onContext, true);
  root.addEventListener('dragstart', onDragStart);
  root.addEventListener('dragover', onDragOver);
  root.addEventListener('drop', onDrop);
  root.addEventListener('dragend', onDragEnd);
}

/** 지금 보이는 업무 칸들 (다시 그릴 때) */
export const visibleHosts = () => S.panes.flatMap((p) => [...p.scroller.querySelectorAll('.wk-host')]);
