// 팝업 메뉴, 확대 보기(라이트박스)

import { emit } from './store.js';
import { $, esc } from './util.js';
import { t } from './i18n.js';

// ---- 팝업 메뉴 -------------------------------------------------------------

let menuItems = [];
let onMenuClose = null;

function menuItemHtml(it, i) {
  if (it === '-') return '<div class="menu-sep" role="separator"></div>';
  if (it.header) return `<div class="menu-head">${esc(it.header)}</div>`;
  const main = `<button role="menuitem" data-i="${i}"><span>${esc(it.label)}</span>${it.hint ? `<small>${esc(it.hint)}</small>` : ''}</button>`;
  if (!it.term) return main;
  // 복사 항목 옆의 터미널 버튼: 같은 글을 터미널에 붙여 넣는다 (D51 — terminal.js 의 pasteToTerminal)
  const tip = t('터미널에 붙여 넣기 (Enter 는 누르지 않음)');
  return `<div class="menu-row">${main}<button role="menuitem" class="menu-term" data-term="${i}" title="${esc(tip)}" aria-label="${esc(tip)}">`
    + `<svg aria-hidden="true"><use href="#i-term"/></svg>${t('터미널')}</button></div>`;
}

/** items: [{label, hint?, action, term?}], {header}(누를 수 없는 머리말) 또는 '-'(구분선). onClose 는 메뉴가 닫힐 때.
 * term: 그 항목 옆에 '터미널에 붙여 넣기' 버튼을 달고 누르면 이 글을 터미널에 넣는다 (복사하는 글과 같은 것 — 경로는 끝에 공백) */
export function showMenu(x, y, items, onClose = null) {
  const menu = $('#lec-menu');
  hideMenu();
  menuItems = items;
  onMenuClose = onClose;
  menu.innerHTML = items.map(menuItemHtml).join('');
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

export function initUi() {
  const menu = $('#lec-menu');
  menu.addEventListener('click', (e) => {
    const term = e.target.closest('button[data-term]');
    if (term) {
      const item = menuItems[+term.dataset.term];
      hideMenu();
      if (item?.term) emit('term-paste', item.term);
      return;
    }
    const btn = e.target.closest('button[data-i]');
    if (!btn) return;
    const item = menuItems[+btn.dataset.i];
    hideMenu();
    item?.action?.();
  });
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
  window.addEventListener('blur', hideMenu);
  window.addEventListener('resize', hideMenu);
  $('#lec-lightbox').addEventListener('click', closeLightbox);
}
