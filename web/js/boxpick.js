// 담을 담기함 고르기 (D199): 거르기 칸과 담기함의 목록을 작은 창으로 — 최근에 담은 것부터. 고르는 일만 한다, 담는 것은 부른 쪽 (basket.js 의 boxMenu).
//
// - Alt+Shift+C(docmenu.js·parts.js)와 우클릭 '다른 담기함에 담기…', 조각의 '옮기기…·복사…' 가 함께 쓴다.
// - 처음 고른 줄은 지금 담기함이 아닌 첫 담기함이다 (지금 담기함에는 Alt+C 로 담는다).
// - 없는 이름을 치면 맨 아래 '새 담기함' 줄이 그 이름으로 만든다 — 사이드바로 가지 않는다.
// - 키 (거르기 칸에 초점을 둔 채): ↑↓ 옆 줄, Enter 고르기, Esc 그만두기. 닫으면 초점과 고른 글이 전처럼.

import { S, on } from './store.js';
import { clipsOf, boxName, newBox } from './clipstore.js';
import { $ } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';

let waiting = null;   // {tab, except, pick, sel, rows: [{box} | {name}], restore, ranges, naming}

const box = () => $('#lec-boxpick');
const input = () => /** @type {HTMLInputElement} */ ($('#lec-boxpick-find'));

/** 보일 줄 — 최근에 고친 것부터, 맨 아래에 새 담기함 (친 글이 있는 담기함의 이름과 같으면 없이) */
function rowsNow() {
  const w = waiting;
  const text = input().value.replace(/\s+/g, ' ').trim();
  if (w.naming) return text ? [{ name: text }] : [];
  const words = text.toLowerCase().split(' ').filter(Boolean);
  const boxes = clipsOf(w.tab).boxes.filter((b) => b !== w.except && !b.error).sort((a, b) => b.mtime - a.mtime);
  const shown = boxes.filter((b) => words.every((x) => boxName(b).toLowerCase().includes(x)));
  const same = boxes.some((b) => boxName(b).toLowerCase() === text.toLowerCase());
  return [...shown.map((b) => ({ box: b })), ...(text && same ? [] : [{ name: text }])];
}

function draw(first = false) {
  const w = waiting;
  const cur = clipsOf(w.tab).cur;
  w.rows = rowsNow();
  if (first) w.sel = Math.max(0, w.rows.findIndex((r) => !r.box || r.box.file !== cur || input().value.trim()));
  w.sel = Math.max(0, Math.min(w.sel, w.rows.length - 1));
  input().placeholder = w.naming ? t('새 담기함의 이름 — Enter') : t('담기함 거르기 — 없는 이름이면 새로 만듭니다');
  setHtml($('#lec-boxpick-body'), w.rows.map((r, i) => html`<button type="button" role="option" tabindex="-1" data-i="${i}" class="${i === w.sel ? 'sel' : ''}${r.box ? '' : ' new'}" aria-selected="${i === w.sel}"><svg class="ficon" aria-hidden="true"><use href="#${r.box ? 'i-clip' : 'i-plus'}"/></svg><span class="bp-name">${r.box ? boxName(r.box) : r.name ? t("새 담기함 '{name}'", { name: r.name }) : t('새 담기함…')}</span><small>${r.box ? (r.box.file === cur ? t('지금 담기함') : t('{n}개', { n: r.box.items.length })) : ''}</small></button>`));
  box().querySelector('button.sel')?.scrollIntoView({ block: 'nearest' });
}

function finish() {
  const w = waiting;
  if (!w) return null;
  waiting = null;
  box().hidden = true;
  const sel = getSelection();
  if (w.ranges.length) {
    sel.removeAllRanges();
    for (const r of w.ranges) sel.addRange(r);
  }
  if (w.restore?.isConnected) w.restore.focus({ preventScroll: true });
  return w;
}

/** 고르다 말고 다른 프로젝트·문서 탭으로 갔다 — 초점을 되돌리지 않고 닫는다 */
function leave() {
  if (!waiting) return;
  waiting = null;
  box().hidden = true;
}

async function choose(i = waiting?.sel) {
  const r = waiting?.rows[i];
  if (!r) return;
  if (!r.box && !r.name) {   // 이름을 적지 않은 '새 담기함…' — 같은 칸에 이름을
    waiting.naming = true;
    draw(true);
    input().focus();
    return;
  }
  const w = finish();
  const made = r.box || await newBox(w.tab, r.name);
  if (made && w.tab === S.tab) w.pick(made);
}

function onKey(e) {
  if (!waiting || e.isComposing || e.keyCode === 229) return;
  const n = waiting.rows.length;
  if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && !e.altKey) {
    if (n) waiting.sel = (waiting.sel + (e.key === 'ArrowDown' ? 1 : -1) + n) % n;
    draw();
  } else if (e.key === 'Enter') choose();
  else if (e.key === 'Escape') finish();
  else if (e.key !== 'Tab') return;   // Tab 은 창 밖으로 나가지 않게
  e.preventDefault();
  e.stopPropagation();
}

function make() {
  const el = document.createElement('div');
  el.id = 'lec-boxpick';
  el.className = 'charpick boxpick';
  el.setAttribute('role', 'dialog');
  el.hidden = true;
  setHtml(el, html`<div class="cp-head"><b id="lec-boxpick-title"></b></div><div class="cp-head"><input id="lec-boxpick-find" type="text" spellcheck="false" autocomplete="off" aria-label="${t('담기함 거르기')}"></div>
    <div id="lec-boxpick-body" class="bp-body" role="listbox"></div>
    <div class="cp-foot"><span class="cp-keys">${t('↑↓ 고르기 · Enter 정하기 · Esc 닫기')}</span></div>`);
  document.body.append(el);
  el.addEventListener('keydown', onKey);
  el.addEventListener('mousedown', (e) => { if (!e.target.closest('input')) e.preventDefault(); });   // 초점은 거르기 칸에
  el.addEventListener('click', (e) => {
    const b = /** @type {HTMLElement | null} */ (e.target.closest('button[data-i]'));
    if (b) choose(Number(b.dataset.i));
  });
  input().addEventListener('input', () => { if (waiting) draw(true); });
  document.addEventListener('mousedown', (e) => { if (waiting && !el.contains(/** @type {Node} */ (e.target))) finish(); }, true);
  for (const ev of ['tab', 'pane']) on(ev, () => leave());
  return el;
}

/** 자리 (x, y) 에 — 창 밖으로 나가지 않게 */
function place(el, x, y) {
  el.style.left = `${Math.round(Math.max(8, Math.min(x, innerWidth - el.offsetWidth - 8)))}px`;
  el.style.top = `${Math.round(Math.max(8, Math.min(y, innerHeight - el.offsetHeight - 8)))}px`;
}

/**
 * 담기함을 고르게 한다. pick(담기함) 은 고르거나 새로 만든 뒤 — 그만두면 부르지 않는다
 * @param {any} tab
 * @param {{ x: number, y: number, header: string, except?: any, pick: (box: any) => void }} how
 */
export function pickBox(tab, { x, y, header, except = null, pick }) {
  finish();
  const el = box() || make();
  const sel = getSelection();
  const ranges = [];
  if (!sel.isCollapsed) for (let i = 0; i < sel.rangeCount; i += 1) ranges.push(sel.getRangeAt(i).cloneRange());
  const at = /** @type {HTMLElement} */ (document.activeElement);
  waiting = { tab, except, pick, sel: 0, rows: [], restore: at && at !== document.body ? at : S.pane?.scroller, ranges, naming: false };
  $('#lec-boxpick-title').textContent = header;
  input().value = '';
  el.hidden = false;
  draw(true);
  place(el, x, y);
  input().focus({ preventScroll: true });
}
