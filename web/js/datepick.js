// 달력 입력 (D149): 날짜 하나를 고르는 작은 달력. 업무 카드·일정 더하기의 날짜 칸, 업무 현황에서 마감·기한 고치기,
// 칸 편집·전체 편집의 Ctrl+; (날짜 넣기)가 함께 쓴다. 고르는 일만 한다 — 무엇을 쓸지는 부른 쪽이 정한다.
// 키: ←→ 하루, ↑↓ 한 주, PageUp·PageDown 한 달, Home·End 그 주의 처음·끝, Enter 고르기, Esc 그만두기, T 오늘.

import { $ } from './util.js';
import { html, setHtml } from './html.js';
import { t, LANG } from './i18n.js';

const pad = (n) => String(n).padStart(2, '0');
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const dayOf = (s) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''));
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  return d && d.getMonth() === Number(m[2]) - 1 ? d : null;
};
const shift = (d, days) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
const addMonths = (d, n) => {
  const last = new Date(d.getFullYear(), d.getMonth() + n + 1, 0).getDate();
  return new Date(d.getFullYear(), d.getMonth() + n, Math.min(d.getDate(), last));
};
/** 오늘에서 다가오는 그 요일 (오늘이면 다음 주) — dow: 0 일 … 6 토 */
const nextDow = (today, dow) => shift(today, ((dow - today.getDay() + 7) % 7) || 7);

let waiting = null;   // {resolve, cursor: Date, value, marks, clear}

const box = () => $('#lec-datepick');

function monthTitle(d) {
  return d.toLocaleDateString(LANG === 'en' ? 'en-US' : 'ko-KR', { year: 'numeric', month: 'long' });
}

function draw() {
  const w = waiting;
  const today = new Date();
  const first = new Date(w.cursor.getFullYear(), w.cursor.getMonth(), 1);
  const start = shift(first, -first.getDay());   // 일요일부터
  const names = LANG === 'en' ? ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'] : ['일', '월', '화', '수', '목', '금', '토'];   // i18n-ok — 요일 머리, 화면 언어마다
  const cells = [];
  for (let i = 0; i < 42; i++) {
    const d = shift(start, i);
    const day = iso(d);
    const cls = [d.getMonth() !== w.cursor.getMonth() ? 'dp-out' : '', day === iso(today) ? 'dp-today' : '', day === w.value ? 'dp-value' : '',
      day === iso(w.cursor) ? 'dp-cursor' : '', d.getDay() === 0 ? 'dp-sun' : d.getDay() === 6 ? 'dp-sat' : '', w.marks?.has(day) ? 'dp-mark' : ''].filter(Boolean).join(' ');
    cells.push(html`<button type="button" class="${cls}" data-day="${day}" tabindex="${day === iso(w.cursor) ? '0' : '-1'}" aria-label="${d.toLocaleDateString(LANG === 'en' ? 'en-US' : 'ko-KR', { dateStyle: 'full' })}">${d.getDate()}</button>`);
  }
  setHtml(box(), html`<div class="dp-head"><button type="button" data-step="-1" aria-label="${t('지난달')}">‹</button><b>${monthTitle(w.cursor)}</b><button type="button" data-step="1" aria-label="${t('다음 달')}">›</button></div>
    ${w.title ? html`<div class="dp-title">${w.title}</div>` : ''}
    <div class="dp-week">${names.map((n, i) => html`<span class="${i === 0 ? 'dp-sun' : i === 6 ? 'dp-sat' : ''}">${n}</span>`)}</div>
    <div class="dp-grid" role="grid">${cells}</div>
    <div class="dp-quick"><button type="button" data-quick="today">${t('오늘')}</button><button type="button" data-quick="tomorrow">${t('내일')}</button><button type="button" data-quick="fri">${t('이번 주 금요일')}</button><button type="button" data-quick="mon">${t('다음 주 월요일')}</button>${w.clear ? html`<button type="button" data-quick="clear">${t('비우기')}</button>` : ''}</div>`);
  box().querySelector('.dp-cursor')?.focus();
}

function finish(value) {
  const w = waiting;
  if (!w) return;
  waiting = null;
  box().hidden = true;
  w.restore?.focus?.();
  w.resolve(value);
}

function quick(kind) {
  const today = new Date();
  if (kind === 'clear') return finish('');
  const d = kind === 'today' ? today : kind === 'tomorrow' ? shift(today, 1) : kind === 'fri' ? (today.getDay() === 5 ? today : nextDow(today, 5)) : nextDow(today, 1);
  return finish(iso(d));
}

function onKey(e) {
  if (!waiting) return;
  const moves = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
  const c = waiting.cursor;
  let next = null;
  if (e.key in moves) next = shift(c, moves[e.key]);
  else if (e.key === 'PageUp') next = addMonths(c, -1);
  else if (e.key === 'PageDown') next = addMonths(c, 1);
  else if (e.key === 'Home') next = shift(c, -c.getDay());
  else if (e.key === 'End') next = shift(c, 6 - c.getDay());
  else if (e.key === 'Enter') {
    e.preventDefault();
    e.stopPropagation();
    const at = e.target.closest?.('button[data-day]');
    finish(at ? at.dataset.day : iso(c));
    return;
  } else if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();   // 달력을 띄운 창(일정 더하기 등)까지 닫히지 않게
    finish(null);
    return;
  } else if ((e.key === 't' || e.key === 'T') && !e.ctrlKey && !e.altKey) {
    next = new Date();
  } else if (e.key === 'Tab') {
    return;   // 빠른 단추로 옮겨 가게 둔다
  }
  if (!next) return;
  e.preventDefault();
  e.stopPropagation();
  waiting.cursor = next;
  draw();
}

function onClick(e) {
  const day = e.target.closest('button[data-day]');
  if (day) return finish(day.dataset.day);
  const step = e.target.closest('button[data-step]');
  if (step) {
    waiting.cursor = addMonths(waiting.cursor, Number(step.dataset.step));
    draw();
    return;
  }
  const q = e.target.closest('button[data-quick]');
  if (q) quick(q.dataset.quick);
}

/** 바깥을 누르면 그만둔다 (고른 것 없이) */
function onOutside(e) {
  if (waiting && !box().contains(e.target)) finish(null);
}

/**
 * 달력을 띄워 날짜 하나를 고른다.
 * @param {{at: Element | {x: number, y: number}, value?: string, marks?: Set<string> | null, clear?: boolean, title?: string}} o
 *   at: 그 아래에 띄울 요소나 화면 자리 · value: 지금 값 'YYYY-MM-DD' · marks: 점을 찍을 날 · clear: '비우기' 단추 · title: 무엇의 날짜인지
 * @returns {Promise<string | null>} 고른 날짜, 비우기면 '', 그만두면 null
 */
export function pickDate({ at, value = '', marks = null, clear = false, title = '' }) {
  if (waiting) finish(null);
  let el = box();
  if (!el) {
    el = document.createElement('div');
    el.id = 'lec-datepick';
    el.className = 'datepick';
    el.setAttribute('role', 'dialog');
    el.hidden = true;
    document.body.append(el);
    el.addEventListener('keydown', onKey);
    el.addEventListener('click', onClick);
    document.addEventListener('mousedown', onOutside, true);
  }
  el.setAttribute('aria-label', title || t('날짜 고르기'));
  const current = dayOf(value);
  return new Promise((resolve) => {
    waiting = { resolve, cursor: current || new Date(), value: current ? value : '', marks, clear, title, restore: document.activeElement };
    el.hidden = false;
    draw();
    place(el, at);
    el.querySelector('.dp-cursor')?.focus();
  });
}

/** 자리 잡기 — at 의 아래(넘치면 위), 창 안에 */
function place(el, at) {
  const r = at instanceof Element ? at.getBoundingClientRect() : { left: at?.x ?? 100, bottom: at?.y ?? 100, top: at?.y ?? 100 };
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  let x = Math.min(Math.max(8, r.left), innerWidth - w - 8);
  let y = r.bottom + 4;
  if (y + h > innerHeight - 8) y = Math.max(8, r.top - h - 4);
  el.style.left = `${Math.round(x)}px`;
  el.style.top = `${Math.round(y)}px`;
}

/** 열려 있는지 (다른 키 처리가 끼어들지 않게) */
export const datePicking = () => !!waiting;
