// 터미널 모음 (D40): 열린 프로젝트들의 터미널을 한 화면에 격자로 모아 보인다. 툴바의 '터미널 모음' 버튼·Ctrl+Shift+`.
//
// - 탭 하나에 칸 하나 (탭 순서). 터미널이 여럿인 탭(D69)은 칸 머리의 번호로 고른 터미널을 보인다.
//   셸이 있는 탭은 그 터미널 화면(tab.term.box)을 오른쪽 패널에서 이 칸으로 옮겨 보이고,
//   셸이 없는 탭은 '터미널 시작' 버튼만 둔다 — 쓰지 않는 프로젝트까지 셸을 한꺼번에 띄우지 않는다. 닫으면 화면을 패널로 되돌린다
//   (셸은 그대로). 칸 크기에 맞춰 셸의 글자 칸 수도 바뀐다 (터미널 프로그램은 다시 그린다).
// - 격자: 1 = 하나, 2 = 좌우, 3~4 = 2×2, 5~6 = 3×2, 7~9 = 3×3, 10 = 4×3. 칸 머리를 두 번 누르거나 '크게'로 그 칸만 크게.
// - 프로젝트 탭을 누르면(이미 선택된 탭이어도) 모음을 닫고 그 프로젝트의 문서 화면으로. 칸의 '이 프로젝트로'·Ctrl+` 는
//   그 프로젝트로 가서 오른쪽 터미널을 연다. 탭을 닫거나 폴더를 새로 열면 모음은 열린 채 칸만 바뀐다.
// - 칸 안의 키는 셸 것이다. 앱은 Ctrl+Tab(다음 칸)·Ctrl+`·Ctrl+Shift+` 만 받는다 (main.js).
// - 모아 보는 동안 2초마다 셸에서 프로그램이 도는지(/api/term/info) 보고 칸 머리에 '실행 중'·'대기'·'끝남'·'시작 전'을 보인다.
//   셸에서 띄운 프로그램이 시작하다 멈췄으면(D58 — tab.term.stuck) '멈춤'과 다시 시작 버튼 강조.

import { S, on } from './store.js';
import { selectTab } from './tabs.js';
import {
  ensureTerminal, restartTerminal, fitTerminal, returnTerminals, liveTerminals, terminalBusy, toggleTerminal,
  stuckMessage, termsOf, termLabel, selectTerminal,
} from './terminal.js';
import { $, $$, esc, toast } from './util.js';
import { t } from './i18n.js';

const POLL_MS = 2000;
const root = document.documentElement;
const grid = () => $('#lec-gather');

let shown = false;
let pollTimer = 0;
let lastTab = null;   // 마지막으로 입력이 간 칸의 탭 (Ctrl+` 로 그 프로젝트로)

export const gatherOn = () => shown;

/** 칸 수 → [열, 행] */
function shapeOf(n) {
  if (n <= 1) return [1, 1];
  if (n === 2) return [2, 1];
  const cols = Math.ceil(Math.sqrt(n));
  return [cols, Math.ceil(n / cols)];
}

const tileOf = (tab) => $$('.g-tile', grid()).find((el) => el.dataset.tab === tab.id);
const tabOfTile = (el) => S.tabs.find((tab) => tab.id === el?.closest('.g-tile')?.dataset.tab) || null;

function makeTile(tab) {
  const tile = document.createElement('section');
  tile.className = 'g-tile';
  tile.dataset.tab = tab.id;
  tile.setAttribute('aria-label', t('{name} 터미널', { name: tab.name }));
  tile.innerHTML = `<div class="g-head" title="${esc(tab.root)}\n${t('머리를 두 번 누르면 이 칸만 크게')}">
      <svg class="g-icon" aria-hidden="true"><use href="#i-folder"/></svg><span class="g-name">${esc(tab.name)}</span>
      <span class="g-terms" role="tablist" aria-label="${t('터미널')}"></span>
      <span class="g-state"></span>
      <button type="button" class="icon-btn small g-solo" title="${t('이 칸만 크게')}" aria-label="${t('이 칸만 크게')}"><svg><use href="#i-expand"/></svg></button>
      <button type="button" class="icon-btn small g-restart" title="${t('셸 다시 시작 (지금 셸과 거기서 띄운 프로그램은 끝남)')}" aria-label="${t('셸 다시 시작')}"><svg><use href="#i-restart"/></svg></button>
      <button type="button" class="icon-btn small g-go" title="${t('이 프로젝트로 — 문서와 오른쪽 터미널 (Ctrl+`)')}" aria-label="${t('이 프로젝트로')}"><svg><use href="#i-forward"/></svg></button>
    </div><div class="g-body"></div>`;
  return tile;
}

/** 칸 머리의 터미널 번호 (터미널이 여럿일 때만 — 누르면 그 터미널을 이 칸에) */
function renderNums(tab, tile) {
  const terms = termsOf(tab);
  tile.querySelector('.g-terms').innerHTML = terms.length < 2 ? '' : terms.map((term) => `<button type="button" role="tab"`
    + ` class="g-term${term === tab.term ? ' on' : ''}" data-n="${term.n}" aria-selected="${term === tab.term}"`
    + ` title="${esc(`${term.n + 1} · ${termLabel(term)}`)}">${term.n + 1}</button>`).join('');
}

/** 칸의 몸통: 셸이 있으면 고른 터미널의 화면, 없으면 '터미널 시작' (보기만 하는 프로젝트는 안내만 — D71) */
function fillBody(tab, tile) {
  const body = tile.querySelector('.g-body');
  const term = tab.term;
  renderNums(tab, tile);
  if (tab.readonly) {
    if (!body.querySelector('.g-empty')) {
      body.innerHTML = `<div class="g-empty"><p>${esc(t('보기만 하는 프로젝트입니다 — Lectern 프로그램 폴더 안이라 터미널을 열지 않습니다'))}</p>
        <small>${esc(tab.root)}</small></div>`;
    }
  } else if (term) {
    body.querySelector('.g-empty')?.remove();
    for (const other of termsOf(tab)) if (other !== term && other.box.parentElement === body) other.box.hidden = true;
    if (term.box.parentElement !== body) body.append(term.box);
    term.box.hidden = false;
  } else if (!body.querySelector('.g-empty')) {
    body.innerHTML = `<div class="g-empty"><button type="button" class="primary g-start">${t('터미널 시작')}</button>
      <small>${esc(tab.root)}</small></div>`;
  }
}

function setState(tile, tab, busy) {
  const el = tile.querySelector('.g-state');
  const term = tab.term;
  const [text, cls] = tab.readonly ? [t('보기만'), 'none'] : !term ? [t('시작 전'), 'none'] : !term.alive ? [t('끝남'), 'ended'] : term.stuck?.length ? [t('멈춤 — 다시 시작하세요'), 'stuck']
    : busy ? [t('실행 중'), 'busy'] : [t('대기'), 'idle'];
  el.textContent = text;
  el.className = `g-state ${cls}`;
  el.title = cls === 'stuck' ? stuckMessage(term.stuck) : '';
  const restart = tile.querySelector('.g-restart');
  restart.disabled = !term;
  restart.classList.toggle('attention', cls === 'stuck');
}

/** 탭 목록에 맞춰 칸을 만들고 지우고 순서를 맞춘다. 있는 칸(과 그 안의 화면)은 그대로 둔다 */
function render() {
  const box = grid();
  const keep = new Set(S.tabs.map((tab) => tab.id));
  for (const el of $$('.g-tile', box)) if (!keep.has(el.dataset.tab)) el.remove();
  box.querySelector('.g-none')?.remove();
  S.tabs.forEach((tab, i) => {
    const tile = tileOf(tab) || makeTile(tab);
    if (box.children[i] !== tile) box.insertBefore(tile, box.children[i] || null);
    fillBody(tab, tile);
    if (!tile.querySelector('.g-state').textContent || !tab.term?.alive) setState(tile, tab, false);
  });
  if (!S.tabs.length) {
    box.insertAdjacentHTML('beforeend', `<p class="g-none">${t('열린 프로젝트가 없습니다. 폴더를 열면 그 프로젝트의 터미널이 여기에 생깁니다.')}</p>`);
  }
  const solo = box.querySelector('.g-tile.solo');
  if (box.classList.contains('solo') && !solo) box.classList.remove('solo');
  const [cols, rows] = shapeOf(Math.max(1, S.tabs.length));
  box.style.setProperty('--g-cols', cols);
  box.style.setProperty('--g-rows', rows);
  updateButton();
  requestAnimationFrame(fitAll);
}

function fitAll() {
  if (!shown) return;
  for (const tab of S.tabs) if (tab.term) fitTerminal(tab.term);
}

function updateButton() {
  const n = liveTerminals();
  const count = $('#lec-gather-count');
  count.textContent = n ? String(n) : '';
  count.hidden = !n;
  const btn = $('#lec-btn-gather');
  btn.setAttribute('aria-pressed', String(shown));
  btn.title = `${t('터미널 모음 — 열린 프로젝트들의 터미널을 한 화면에 (Ctrl+Shift+`)')}${n ? `\n${t('셸 {n}개가 돌고 있습니다', { n })}` : ''}`;
}

async function poll() {
  for (const tab of S.tabs) {
    const tile = tileOf(tab);
    if (!tile) continue;
    setState(tile, tab, tab.term?.alive ? await terminalBusy(tab.term) : false);
  }
}

async function startTile(tab) {
  const tile = tileOf(tab);
  if (!tile || tab.readonly) return;
  const body = tile.querySelector('.g-body');
  body.querySelector('.g-empty')?.remove();
  try {
    const term = await ensureTerminal(tab, body);
    setState(tile, tab, false);
    term.xterm.focus();
  } catch (e) {
    toast(e.message, 'error');
    fillBody(tab, tile);
  }
}

function toggleSolo(tile) {
  const box = grid();
  const solo = !tile.classList.contains('solo');
  for (const el of $$('.g-tile.solo', box)) el.classList.remove('solo');
  tile.classList.toggle('solo', solo);
  box.classList.toggle('solo', solo);
  const btn = tile.querySelector('.g-solo');
  btn.title = solo ? t('모두 보기') : t('이 칸만 크게');
  btn.setAttribute('aria-label', btn.title);
  btn.querySelector('use').setAttribute('href', solo ? '#i-grid' : '#i-expand');
  requestAnimationFrame(fitAll);
  focusTile(tile);
}

function focusTile(tile) {
  const tab = tabOfTile(tile);
  if (tab?.term) tab.term.xterm.focus();
  else tile?.querySelector('.g-start')?.focus();
}

/** Ctrl+Tab / Ctrl+Shift+Tab: 다음·이전 칸으로 (크게 보는 중이면 그 칸을 바꾼다) */
export function focusNextTile(step) {
  const tiles = $$('.g-tile', grid());
  if (!tiles.length) return;
  const cur = tiles.findIndex((el) => el.contains(document.activeElement));
  const next = tiles[(cur + step + tiles.length) % tiles.length];
  if (grid().classList.contains('solo')) toggleSolo(next);
  else focusTile(next);
}

export function enterGather() {
  if (shown) return;
  shown = true;
  root.classList.add('gather-on');
  grid().hidden = false;
  render();
  poll();
  pollTimer = setInterval(poll, POLL_MS);
  const tile = (S.tab && tileOf(S.tab)) || $('.g-tile', grid());
  requestAnimationFrame(() => focusTile(tile));
}

/** 모음을 닫는다. tab: 그 프로젝트로 간다, panel: 오른쪽 터미널을 연다 */
export async function leaveGather({ tab = null, panel = false } = {}) {
  if (!shown) return;
  shown = false;
  clearInterval(pollTimer);
  root.classList.remove('gather-on');
  returnTerminals();   // 화면들을 오른쪽 패널로 (gather-on 을 뗀 뒤에 — 패널이 다시 맡는다)
  const box = grid();
  box.hidden = true;
  box.classList.remove('solo');
  box.innerHTML = '';
  updateButton();
  if (tab && tab !== S.tab && S.tabs.includes(tab)) await selectTab(tab);
  if (panel) toggleTerminal(true);
  else $('#lec-content')?.focus({ preventScroll: true });
}

export const toggleGather = () => (shown ? leaveGather() : enterGather());

/** Ctrl+` (모아 보는 중): 마지막으로 쓰던 칸의 프로젝트로 가서 오른쪽 터미널을 연다 */
export const leaveToFocused = () => leaveGather({ tab: tabOfTile(document.activeElement) || lastTab || S.tab, panel: true });

export function initGather() {
  $('#lec-btn-gather').addEventListener('click', toggleGather);
  const box = grid();
  box.addEventListener('click', (e) => {
    const tab = tabOfTile(e.target);
    if (!tab) return;
    const num = e.target.closest('.g-term');
    if (num) {   // 터미널 번호 (D69): 그 터미널을 이 칸에 — 화면을 바꿔 끼우고 셸이 없으면 띄운다
      const term = termsOf(tab).find((x) => String(x.n) === num.dataset.n);
      if (term) {
        selectTerminal(tab, term);
        startTile(tab);
      }
    } else if (e.target.closest('.g-start')) startTile(tab);
    else if (e.target.closest('.g-solo')) toggleSolo(tileOf(tab));
    else if (e.target.closest('.g-restart')) restartTerminal(tab).then(() => { const tile = tileOf(tab); if (tile) setState(tile, tab, false); });
    else if (e.target.closest('.g-go')) leaveGather({ tab, panel: true });
  });
  box.addEventListener('dblclick', (e) => {
    if (e.target.closest('.g-head') && !e.target.closest('button')) toggleSolo(e.target.closest('.g-tile'));
  });
  box.addEventListener('focusin', (e) => { lastTab = tabOfTile(e.target) || lastTab; });
  // 프로젝트 탭을 누르면 모음을 닫는다 (이미 선택된 탭이어도 — tabs.js 가 이어서 그 탭을 고른다). 닫기(×)는 모음 안에서 칸만 없앤다
  $('#lec-tablist').addEventListener('click', (e) => {
    if (shown && e.target.closest('.lec-tab') && !e.target.closest('.tab-close')) leaveGather();
  }, true);
  new ResizeObserver(() => requestAnimationFrame(fitAll)).observe(box);
  on('tabs', () => { if (shown) render(); else updateButton(); });
  on('terms', () => {
    updateButton();
    if (!shown) return;
    for (const tab of S.tabs) {
      const tile = tileOf(tab);
      if (!tile) continue;
      if (tab.term) fillBody(tab, tile);   // 터미널이 생기거나 닫히거나 다른 번호를 골랐다 (D69)
      else renderNums(tab, tile);
      setState(tile, tab, tile.querySelector('.g-state').classList.contains('busy'));
    }
  });
  updateButton();
}
