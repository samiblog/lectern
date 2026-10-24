// 발표 모드 (D59): 슬라이드로 보는 발표 문서(slides.js)를 창 전체에 한 장씩. 상태줄 '발표'·Shift+F5·슬라이드의 ▶.
//
// - 칸의 슬라이드를 복제해 #lec-present 에 보인다 (원본은 그대로 — 그사이 문서가 바뀌어 다시 그려지면 같은 번호를 다시 복제).
//   문서의 style: CSS 는 [data-deck] 범위로 입혀져 있어 여기서도 같다 (slides.js 의 scopedCss).
// - 키(main.js 가 맨 먼저 넘긴다): → ↓ Space PageDown Enter 다음, ← ↑ PageUp Backspace 이전, Home·End, N 발표자 노트,
//   F·F11 전체 화면, Esc 끝내기. 누르면 다음, 휠로 앞뒤. 링크는 따라가지 않는다 (인터넷 주소만 브라우저로).
// - 시작할 때 창을 전체 화면으로 (창 모드는 native.set_fullscreen, 브라우저는 Fullscreen API), 끝내면 되돌리고 칸을 그 장으로.

import { S, on } from './store.js';
import { native } from './api.js';
import { $, $$ } from './util.js';
import { slideAtTop } from './slides.js';
import { t } from './i18n.js';

let state = null;   // { pane, index, notes, full }
let idleTimer = 0;
let wheelAt = 0;

const box = () => $('#lec-present');
const wrapsOf = (pane) => $$(':scope > .lec-slide-wrap', pane.view);

export const presenting = () => !!state;

function layout() {
  if (!state) return;
  const holder = $('.pr-deck', box());
  const section = holder?.querySelector('.lec-slide');
  if (!section) return;
  const notes = $('.pr-notes', box());
  const room = box().getBoundingClientRect();
  const h = room.height - (notes.hidden ? 0 : notes.offsetHeight);
  const scale = Math.min(room.width / section.offsetWidth, h / section.offsetHeight);
  holder.style.setProperty('--slide-scale', String(scale));
  holder.style.width = `${section.offsetWidth * scale}px`;
  holder.style.height = `${section.offsetHeight * scale}px`;
}

function show(index) {
  const wraps = wrapsOf(state.pane);
  if (!wraps.length) {
    stopPresent();
    return;
  }
  state.index = Math.max(0, Math.min(wraps.length - 1, index));
  const wrap = wraps[state.index];
  const holder = document.createElement('div');
  holder.className = 'pr-deck md-body lec-deck';
  holder.dataset.deck = wrap.dataset.deck;
  const section = wrap.querySelector('.lec-slide').cloneNode(true);
  for (const el of $$('.lec-target, .lec-changed, .lec-picked', section)) el.classList.remove('lec-target', 'lec-changed', 'lec-picked');
  holder.append(section);
  $('.pr-stage', box()).replaceChildren(holder);
  const notes = wrap.querySelector('.lec-slide-notes')?.textContent || '';
  const notesBox = $('.pr-notes', box());
  notesBox.textContent = notes || t('이 슬라이드에는 노트가 없습니다');
  notesBox.classList.toggle('empty', !notes);
  notesBox.hidden = !state.notes;
  $('.pr-count', box()).textContent = t('{n} / {total}', { n: state.index + 1, total: wraps.length });
  layout();
}

export function startPresent(pane = S.pane, index = null) {
  if (!pane?.view.classList.contains('lec-deck') || !wrapsOf(pane).length) return;
  if (state) stopPresent();
  state = { pane, index: 0, notes: false, full: false };
  box().hidden = false;
  show(index ?? slideAtTop(pane));
  box().focus({ preventScroll: true });
  setFullscreen(true);
  nudge();
}

export function stopPresent() {
  if (!state) return false;
  const { pane, index } = state;
  if (state.full) setFullscreen(false);
  state = null;
  box().hidden = true;
  $('.pr-stage', box()).replaceChildren();
  const wrap = wrapsOf(pane)[index];
  if (wrap && pane === S.pane) wrap.scrollIntoView({ block: 'start' });
  pane.scroller.focus({ preventScroll: true });
  return true;
}

async function setFullscreen(on) {
  if (!state && on) return;
  try {
    if (native.has('set_fullscreen')) await window.pywebview.api.set_fullscreen(on);
    else if (on && !document.fullscreenElement) await document.documentElement.requestFullscreen?.();
    else if (!on && document.fullscreenElement) await document.exitFullscreen?.();
    if (state) state.full = on;
  } catch { /* 전체 화면을 쓸 수 없는 곳 — 창 안에서 */ }
  requestAnimationFrame(layout);
}

/** 마우스를 잠시 움직이지 않으면 커서와 아래 안내를 감춘다 */
function nudge() {
  box().classList.remove('pr-idle');
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => box()?.classList.add('pr-idle'), 2500);
}

const NEXT = new Set(['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter']);
const PREV = new Set(['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace']);

/** 발표 중의 키 (main.js 가 맨 먼저 부른다). 발표 중이면 앱의 다른 단축키는 쓰지 않는다 */
export function presentKey(e) {
  if (!state) return false;
  const plain = !e.ctrlKey && !e.altKey && !e.metaKey;
  const key = e.key;
  let handled = true;
  if (key === 'Escape') stopPresent();
  else if (plain && NEXT.has(key) && !e.shiftKey) show(state.index + 1);
  else if (plain && (PREV.has(key) || (key === ' ' && e.shiftKey))) show(state.index - 1);
  else if (plain && key === 'Home') show(0);
  else if (plain && key === 'End') show(Infinity);
  else if (plain && (key === 'n' || key === 'N')) {
    state.notes = !state.notes;
    $('.pr-notes', box()).hidden = !state.notes;
    layout();
  } else if (plain && (key === 'f' || key === 'F' || key === 'F11')) setFullscreen(!state.full);
  else handled = key !== 'F12';   // 그 밖의 키는 삼킨다 (개발자 도구만 둔다)
  if (handled) e.preventDefault();
  return true;
}

export function initPresent() {
  $('#lec-st-present').addEventListener('click', () => startPresent());
  // 슬라이드 틀의 ▶ (slides.js 의 prepareDeck) — 그 장부터
  $('#lec-panes').addEventListener('click', (e) => {
    const btn = e.target.closest('.lec-slide-play');
    if (!btn) return;
    const pane = S.panes.find((p) => p.view.contains(btn));
    const wrap = btn.closest('.lec-slide-wrap');
    if (pane) startPresent(pane, wrapsOf(pane).indexOf(wrap));
  });
  const el = box();
  el.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (a) {   // 복제한 화면의 링크는 앱이 다루지 않는다 — 앱 창이 떠나지 않게 막고, 인터넷 주소만 브라우저로
      e.preventDefault();
      if (a.classList.contains('ext')) window.open(a.getAttribute('href'), '_blank', 'noopener');
      return;
    }
    if (e.target.closest('.pr-close')) stopPresent();
    else if (e.target.closest('.pr-notes, .pr-bar')) return;
    else show(state.index + 1);
  });
  el.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (Date.now() - wheelAt < 350 || !state) return;
    wheelAt = Date.now();
    show(state.index + (e.deltaY > 0 ? 1 : -1));
  }, { passive: false });
  el.addEventListener('mousemove', nudge);
  window.addEventListener('resize', () => requestAnimationFrame(layout));
  document.addEventListener('fullscreenchange', () => {
    if (state && !document.fullscreenElement && !native.has('set_fullscreen')) state.full = false;
  });
  // 발표하는 문서가 다시 그려지면(자동 새로고침) 같은 장을 다시, 슬라이드가 아니게 되면 끝낸다
  on('rendered', (pane) => {
    if (!state || pane !== state.pane) return;
    if (pane.view.classList.contains('lec-deck')) show(state.index);
    else stopPresent();
  });
  on('tab', () => stopPresent());
}
