// 팝업 메뉴, 확대 보기(라이트박스)

import { emit } from './store.js';
import { html, setHtml } from './html.js';
import { $ } from './util.js';
import { t } from './i18n.js';

// ---- 팝업 메뉴 -------------------------------------------------------------

/**
 * 메뉴 묶음을 구분선으로 잇는다 (빈 묶음은 뺀다). 묶음의 차례는 어느 메뉴나 같다 (D91):
 * 대상 고유 동작 → Claude → 복사 → 모으기·보내기 → 편집·열기 → 보기 → 위험한 동작
 * @param {MenuItem[][]} groups
 * @returns {MenuItem[]}
 */
export const menuGroups = (...groups) => groups.filter((g) => g?.length).flatMap((g, i) => (i ? ['-', ...g] : g));

let menuItems = [];
let onMenuClose = null;
let heldTerm = null;   // 메뉴가 열린 동안 누르고 있는 숫자 1~5 → 터미널 번호(0 부터) — 숫자+누르기로 그 터미널에 보낸다 (D137)

function menuItemHtml(it, i) {
  if (it === '-') return html`<div class="menu-sep" role="separator"></div>`;
  if (it.header) return html`<div class="menu-head">${it.header}</div>`;
  const attrs = html`${it.icon ? html` class="with-icon"` : ''}${it.current ? html` aria-current="true"` : ''}`;
  const main = html`<button role="menuitem" data-i="${i}"${attrs}${it.tip ? html` title="${it.tip}"` : ''}>${it.icon || ''}<span>${it.label}</span>${it.hint ? html`<small>${it.hint}</small>` : ''}</button>`;
  if (!it.term) return main;
  // 복사 항목 옆의 터미널 버튼: 같은 글을 터미널에 붙여 넣는다 (D51 — terminal.js 의 pasteToTerminal)
  const tip = t('터미널에 붙여 넣기 (Enter 는 누르지 않음) — 숫자 키를 누른 채 누르면 그 번호의 터미널에');
  return [html`<div class="menu-row">${main}<button role="menuitem" class="menu-term" data-term="${i}" title="${tip}" aria-label="${tip}">`, html`<svg aria-hidden="true"><use href="#i-term"/></svg>${t('터미널')}</button></div>`];
}

/** items: [{label, hint?, tip?, action, term?, icon?, current?}], {header}(누를 수 없는 머리말) 또는 '-'(구분선). hint 는 오른쪽의 단축키, tip 은 마우스를 올리면 보이는 설명. onClose 는 메뉴가 닫힐 때.
 * icon: 앞에 둘 아이콘 HTML (icons.js — 한 줄에 아이콘·이름·흐린 hint), current: 지금 고른 것 (강조 — 열린 문서 탭 목록, D67)
 * @param {number} x
 * @param {number} y
 * @param {MenuItem[]} items
 * @param {(() => void) | null} [onClose]
 *
 * term: 그 항목 옆에 '터미널에 붙여 넣기' 버튼을 달고 누르면 이 글을 터미널에 넣는다 (복사하는 글과 같은 것 — 경로는 끝에 공백) */
export function showMenu(x, y, items, onClose = null) {
  const menu = $('#lec-menu');
  hideMenu();
  menuItems = items;
  onMenuClose = onClose;
  setHtml(menu, items.map(menuItemHtml));
  menu.hidden = false;
  const { innerWidth: w, innerHeight: h } = window;
  const r = menu.getBoundingClientRect();
  menu.style.left = `${Math.min(x, w - r.width - 8)}px`;
  menu.style.top = `${Math.min(y, h - r.height - 8)}px`;
  menu.querySelector('button')?.focus();
}

export function hideMenu() {
  const menu = $('#lec-menu');
  if (menu.hidden) return false;
  menu.hidden = true;
  menuItems = [];
  setHeld(null);
  const done = onMenuClose;
  onMenuClose = null;
  done?.();
  return true;
}

// ---- 확대 보기 ---------------------------------------------------------------

export function openLightbox(node) {
  const box = $('#lec-lightbox');
  node.classList.add('lb-content');
  if (node.tagName.toLowerCase() === 'svg') {
    node.removeAttribute('width');
    node.removeAttribute('height');
    node.style.maxWidth = 'none';
    node.style.width = '92vw';
    node.style.height = '86vh';
  }
  box.replaceChildren(node);
  box.hidden = false;
}

export function closeLightbox() {
  const box = $('#lec-lightbox');
  if (box.hidden) return false;
  box.hidden = true;
  box.replaceChildren();
  return true;
}

/** 누르고 있는 숫자를 메뉴 위에 보인다 ('→ 3번 터미널') */
function setHeld(n) {
  heldTerm = n;
  const menu = $('#lec-menu');
  menu.classList.toggle('term-held', n != null);
  if (n != null) menu.dataset.termHeld = t('→ {n}번 터미널', { n: n + 1 });
  else delete menu.dataset.termHeld;
}

const digitOf = (e) => (/^(?:Digit|Numpad)[1-5]$/.test(e.code) ? Number(e.code.at(-1)) - 1 : null);

export function initUi() {
  const menu = $('#lec-menu');
  menu.addEventListener('click', (e) => {
    const n = heldTerm;
    const term = e.target.closest('button[data-term]');
    if (term) {
      const item = menuItems[+term.dataset.term];
      hideMenu();
      if (item?.term) emit('term-paste', n == null ? item.term : { text: item.term, n });
      return;
    }
    const btn = e.target.closest('button[data-i]');
    if (!btn) return;
    const item = menuItems[+btn.dataset.i];
    hideMenu();
    // 숫자+누르기: 이 항목이 곧바로 터미널에 보내는 글은 그 번호로 (D137 — 'Claude로 보내기'·요청 글 등)
    if (n != null) emit('term-target', n);
    try {
      item?.action?.();
    } finally {
      if (n != null) emit('term-target', null);
    }
  });
  // 메뉴가 열린 동안의 숫자 키 (메뉴가 초점을 가진다 — 문서의 숫자 키(D128)로 가지 않는다)
  document.addEventListener('keydown', (e) => {
    if (menu.hidden || e.ctrlKey || e.altKey || e.metaKey || digitOf(e) == null) return;
    e.preventDefault();
    if (!e.repeat) setHeld(digitOf(e));
  }, true);
  document.addEventListener('keyup', (e) => { if (digitOf(e) === heldTerm) setHeld(null); }, true);
  menu.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const btns = [...menu.querySelectorAll('button')];
    const i = btns.indexOf(document.activeElement);
    btns[(i + (e.key === 'ArrowDown' ? 1 : -1) + btns.length) % btns.length]?.focus();
  });
  document.addEventListener('mousedown', (e) => {
    if (!menu.hidden && !menu.contains(e.target)) hideMenu();
  });
  window.addEventListener('blur', () => {
    setHeld(null);
    hideMenu();
  });
  window.addEventListener('resize', hideMenu);
  $('#lec-lightbox').addEventListener('click', closeLightbox);
}
