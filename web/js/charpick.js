// 특수 문자 넣기 (D165): 문장 부호·화살표·도형·수학·단위·번호·첨자·그리스 문자를 묶음마다 칸으로 보이고 하나를 고른다.
// 칸 편집·전체 편집의 Ctrl+Shift+;, 넣기 창의 '특수 문자', 칸의 우클릭 메뉴가 함께 쓴다. 고르는 일만 한다 — 넣는 것은 부른 쪽 (달력 datepick.js 처럼).
//
// - 목록은 web/data/chars.json (문자마다 [글자, 한국어 이름, 영어 이름]) — 처음 열 때 읽는다. Markdown 표시로 읽히는 ASCII 는 들어 있지 않다.
// - 맨 위 줄은 최근 넣은 것 (설정 recent_chars, 열둘). 거르기 칸에 치면 이름(한·영 모두)·글자·초성(ㅎㅅ 화살표)으로 거른다.
// - 키 (거르기 칸에 초점을 둔 채): ←→ 옆 칸, ↑↓ 윗줄·아랫줄의 가까운 칸, Home·End 처음·끝, Enter 넣기, Esc 그만두기. 아래 줄에 고른 문자의 이름.

import { S } from './store.js';
import { getJSON, saveConfig } from './api.js';
import { initials } from './putmenu.js';
import { $ } from './util.js';
import { html, setHtml } from './html.js';
import { t, LANG } from './i18n.js';

const RECENT = 12;
let data = null;      // chars.json
let waiting = null;   // {resolve, sel, shown: [[글자, 한국어, 영어]], restore, title}

const box = () => $('#lec-chars');
const input = () => $('#lec-chars-find');
const nameOf = (x) => (LANG === 'en' ? x[2] : x[1]);

/** 거르기 — 이름(한·영)·글자, 자음만 친 글이면 한국어 이름의 첫소리 */
function matches(x, q) {
  if (x[0] === q || `${x[1]} ${x[2]}`.toLowerCase().includes(q)) return true;
  const bare = q.replace(/\s+/g, '');
  return /^[ㄱ-ㅎ]+$/.test(bare) && initials(x[1]).replace(/\s+/g, '').includes(bare);   // i18n-ok (자음)
}

/** 보일 묶음 [{name, items}] — 거르는 글이 없으면 맨 앞에 최근 넣은 것 */
function groupsNow() {
  const q = input().value.trim().toLowerCase();
  const all = data.groups.map((g) => ({ name: LANG === 'en' ? g.en : g.ko, items: g.chars }));
  if (q) return all.map((g) => ({ ...g, items: g.items.filter((x) => matches(x, q)) })).filter((g) => g.items.length);
  const index = new Map(data.groups.flatMap((g) => g.chars).map((x) => [x[0], x]));
  const recent = (S.config?.recent_chars || []).map((c) => index.get(c)).filter(Boolean).slice(0, RECENT);
  return recent.length ? [{ name: t('최근'), items: recent, recent: true }, ...all] : all;
}

function draw() {
  const w = waiting;
  const groups = groupsNow();
  w.shown = groups.flatMap((g) => g.items);
  w.sel = Math.max(0, Math.min(w.sel, w.shown.length - 1));
  let i = 0;
  setHtml($('#lec-chars-body'), groups.length ? groups.map((g) => html`<section class="cp-group${g.recent ? ' recent' : ''}"><div class="cp-name">${g.name}</div><div class="cp-grid">${g.items.map((x) => {
    const k = i++;
    return html`<button type="button" data-i="${k}" class="${k === w.sel ? 'sel' : ''}" title="${nameOf(x)}" tabindex="-1">${x[0]}</button>`;
  })}</div></section>`) : html`<p class="cp-none">${t('맞는 문자가 없습니다 — 다른 이름으로 찾아 보세요 (예: 화살, 원, 도)')}</p>`);
  showSel();
}

/** 고른 칸을 보이게 하고 아래 줄에 그 이름 */
function showSel() {
  const w = waiting;
  const x = w.shown[w.sel];
  for (const b of box().querySelectorAll('.cp-grid button.sel')) b.classList.remove('sel');
  const btn = box().querySelector(`.cp-grid button[data-i="${w.sel}"]`);
  btn?.classList.add('sel');
  btn?.scrollIntoView({ block: 'nearest' });
  $('#lec-chars-name').textContent = x ? `${x[0]}  ${nameOf(x)}` : '';
}

/** ↑↓: 윗줄·아랫줄에서 가로 자리가 가장 가까운 칸 */
function vertical(dir) {
  const btns = [...box().querySelectorAll('.cp-grid button')];
  const cur = btns[waiting.sel];
  if (!cur) return;
  const r = cur.getBoundingClientRect();
  const cx = r.left + r.width / 2;
  const rows = btns.map((b) => b.getBoundingClientRect()).map((q, i) => ({ i, q })).filter(({ q }) => (dir > 0 ? q.top > r.top + 2 : q.top < r.top - 2));
  if (!rows.length) return;
  const top = dir > 0 ? Math.min(...rows.map((x) => x.q.top)) : Math.max(...rows.map((x) => x.q.top));
  const line = rows.filter((x) => Math.abs(x.q.top - top) < 2);
  waiting.sel = line.reduce((best, x) => (Math.abs(x.q.left + x.q.width / 2 - cx) < Math.abs(best.q.left + best.q.width / 2 - cx) ? x : best)).i;
  showSel();
}

function finish(c) {
  const w = waiting;
  if (!w) return;
  waiting = null;
  box().hidden = true;
  if (c) saveConfig({ recent_chars: [c, ...(S.config?.recent_chars || []).filter((x) => x !== c)].slice(0, RECENT) });
  w.restore?.focus?.({ preventScroll: true });
  w.resolve(c);
}

function choose(i = waiting?.sel) {
  const x = waiting?.shown[i];
  if (x) finish(x[0]);
}

function onKey(e) {
  if (!waiting || e.isComposing || e.keyCode === 229) return;
  const n = waiting.shown.length;
  let handled = true;
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    if (n) waiting.sel = (waiting.sel + (e.key === 'ArrowRight' ? 1 : -1) + n) % n;
    showSel();
  } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') vertical(e.key === 'ArrowDown' ? 1 : -1);
  else if ((e.key === 'Home' || e.key === 'End') && !input().value) {
    waiting.sel = e.key === 'Home' ? 0 : Math.max(0, n - 1);
    showSel();
  } else if (e.key === 'Enter') choose();
  else if (e.key === 'Escape') finish(null);
  else handled = false;
  if (!handled) return;
  e.preventDefault();
  e.stopPropagation();   // 띄운 칸·창(편집 상자 등)이 Esc·Enter 를 받지 않게
}

function make() {
  const el = document.createElement('div');
  el.id = 'lec-chars';
  el.className = 'charpick';
  el.setAttribute('role', 'dialog');
  el.hidden = true;
  setHtml(el, html`<div class="cp-head"><b id="lec-chars-title"></b><input id="lec-chars-find" type="text" spellcheck="false" autocomplete="off"
    placeholder="${t('이름으로 거르기 — 예: 화살, 원, 단위, ㅎㅅ')}" aria-label="${t('특수 문자 거르기')}"></div>
    <div id="lec-chars-body" class="cp-body"></div>
    <div class="cp-foot"><span id="lec-chars-name"></span><span class="cp-keys">${t('←↑↓→ 고르기 · Enter 넣기 · Esc 닫기')}</span></div>`);
  document.body.append(el);
  el.addEventListener('keydown', onKey);
  el.addEventListener('mousedown', (e) => { if (e.target.closest('.cp-grid button')) e.preventDefault(); });   // 초점은 거르기 칸에
  el.addEventListener('click', (e) => {
    const b = e.target.closest('.cp-grid button');
    if (b) choose(Number(b.dataset.i));
  });
  el.querySelector('#lec-chars-find').addEventListener('input', () => {
    if (!waiting) return;
    waiting.sel = 0;
    draw();
  });
  document.addEventListener('mousedown', (e) => { if (waiting && !el.contains(/** @type {Node} */ (e.target))) finish(null); }, true);
  return el;
}

/** 자리 잡기 — at 의 아래(넘치면 위), 창 안에 */
function place(el, at) {
  const r = at instanceof Element ? at.getBoundingClientRect() : { left: at?.x ?? 100, bottom: at?.y ?? 100, top: at?.y ?? 100 };
  const x = Math.min(Math.max(8, r.left), innerWidth - el.offsetWidth - 8);
  let y = r.bottom + 4;
  if (y + el.offsetHeight > innerHeight - 8) y = Math.max(8, r.top - el.offsetHeight - 4);
  el.style.left = `${Math.round(x)}px`;
  el.style.top = `${Math.round(y)}px`;
}

/** 지금 열려 있는지 (main.js 의 Esc 차례 — 창 안의 Esc 는 창이 먼저 받는다) */
export const charsOpen = () => !!waiting;

/**
 * 특수 문자 창을 띄워 하나를 고른다.
 * @param {{at: Element | {x: number, y: number}, title?: string}} o at: 그 아래에 띄울 요소나 화면 자리 · title: 창 머리
 * @returns {Promise<string | null>} 고른 문자, 그만두면 null
 */
export async function pickChar({ at, title = '' }) {
  if (waiting) finish(null);
  try {
    data ??= await getJSON('/static/data/chars.json');
  } catch {
    return null;
  }
  const el = box() || make();
  return new Promise((resolve) => {
    waiting = { resolve, sel: 0, shown: [], restore: document.activeElement, title };
    $('#lec-chars-title').textContent = title || t('특수 문자');
    input().value = '';
    el.hidden = false;
    draw();
    place(el, at);
    input().focus();
  });
}
