// 제목 접기: 제목 왼쪽 여백의 화살표를 누르거나 Ctrl+Shift+[ · ] 로 그 절(다음 같은 수준 이상의 제목 전까지)을 접고 편다.
// 제목 글자를 누르면 접지 않는다 — 다른 줄처럼 현재 줄이 된다 (D120 — 제목을 고르려다 절이 접혔다).
//
// 문서 DOM은 markdown-it 이 만든 평평한 구조 그대로 둔다 (절을 <section> 으로 감싸면 CSS·찾기·목차가 영향을 받는다).
// 접을 수 있는 제목에 lec-fold, 접힌 제목에 lec-folded, 그 아래 숨는 최상위 블록에 lec-fold-hidden 을 준다.
// 접은 상태는 탭마다(칸의 화면별로) 문서 경로별로 이번 실행 동안만 기억한다 (자동 새로고침·뒤로 가기에도 유지, 디스크에 쓰지 않음).
// 두 프로젝트에 같은 경로의 문서(README.md 등)가 있어도 섞이지 않는다. 메뉴의 '모두 접기' 등은 선택된 탭의 칸(#lec-view).

import { S, emit } from './store.js';
import { $ } from './util.js';
import { blockOfLine } from './lineunits.js';

const folds = new WeakMap();   // 칸의 화면(article) → (문서 경로 → 접힌 제목 키 집합). 탭을 닫으면 함께 사라진다
const foldsOf = (root) => {
  if (!folds.has(root)) folds.set(root, new Map());
  return folds.get(root);
};
let lastToggled = null;    // 두 번 눌러 낱말을 고를 때 첫 번째 누름의 접기를 되돌리기 위해

const view = () => $('#lec-view');
const levelOf = (el) => (/^H[1-6]$/.test(el.tagName) ? +el.tagName[1] : 0);
const isBreak = (el) => el.matches('.footnotes-sep, .footnotes');   // 각주는 마지막 절에 속하지 않는다
const headings = (root) => [...root.children].filter(levelOf);
const keyOf = (h, i) => h.id || `@${i}`;

/** 절의 내용: 제목 뒤부터 같은 수준 이상의 제목·각주 앞까지 */
function hasBody(h) {
  const next = h.nextElementSibling;
  if (!next || isBreak(next)) return false;
  const lv = levelOf(next);
  return !lv || lv > levelOf(h);
}

/** 접힌 제목 아래의 최상위 블록을 숨긴다. 펼친 절 안의 접힌 하위 절은 그대로 접혀 있다. */
function apply(root) {
  const open = [];   // 바깥 절부터 [수준, 접힘]
  for (const el of root.children) {
    if (isBreak(el)) open.length = 0;
    const lv = levelOf(el);
    if (lv) while (open.length && open[open.length - 1][0] >= lv) open.pop();
    el.classList.toggle('lec-fold-hidden', open.some(([, folded]) => folded));
    if (lv) open.push([lv, el.classList.contains('lec-folded')]);
  }
}

/** 문서를 그린 직후 부른다. 접을 수 있는 제목을 표시하고, 이 문서에서 접어 두었던 절을 다시 접는다. */
export function setupFolds(root, path) {
  const saved = foldsOf(root).get(path);
  const list = headings(root);
  // 목차처럼, H1이 하나뿐이면 문서 제목으로 보고 접지 않는다 (접으면 문서 전체가 사라진다)
  const title = list.filter((h) => h.tagName === 'H1').length === 1;
  list.forEach((h, i) => {
    if (title && h.tagName === 'H1') return;
    if (!hasBody(h)) return;
    h.classList.add('lec-fold');
    h.classList.toggle('lec-folded', !!saved?.has(keyOf(h, i)));
  });
  apply(root);
}

function remember(root) {
  const keys = headings(root).flatMap((x, i) => (x.classList.contains('lec-folded') ? [keyOf(x, i)] : []));
  if (keys.length) foldsOf(root).set(root.dataset.docPath, new Set(keys));
  else foldsOf(root).delete(root.dataset.docPath);
}

/** 접는 제목은 칸 화면의 바로 아래 자식이다 */
function setFolded(h, folded) {
  h.classList.toggle('lec-folded', folded);
  remember(h.parentElement);
}

function toggle(h) {
  setFolded(h, !h.classList.contains('lec-folded'));
  apply(h.parentElement);
}

/** 접을 수 있는 제목이 있는지 (본문 우클릭 메뉴가 '모두 접기'를 보일지) */
export const hasFolds = () => !!view().querySelector(':scope > .lec-fold');

/** 같은 수준(level, 1~6)의 접을 수 있는 제목을 모두 접거나 편다 (제목 우클릭 메뉴) */
export function foldLevel(level, folded) {
  const root = view();
  for (const h of root.querySelectorAll(`:scope > h${level}.lec-fold`)) h.classList.toggle('lec-folded', folded);
  remember(root);
  apply(root);
}

/** 접을 수 있는 제목을 모두 접거나 편다. */
export function foldAll(folded) {
  const root = view();
  for (const h of root.querySelectorAll(':scope > .lec-fold')) h.classList.toggle('lec-folded', folded);
  remember(root);
  apply(root);
}

/**
 * el 이 접힌 절 안에 있으면 그 절들을 편다. 목차·앵커 링크·찾기가 숨은 곳으로 갈 때 먼저 부른다.
 * (숨은 요소는 display:none 이라 위치가 0이어서 스크롤할 수 없다)
 */
export function unfoldTo(el) {
  emit('reveal', el);   // 장 하이라이트(spotlight.js)가 그 장으로 옮긴다 — 목차·찾기·앵커·바뀐 곳이 모두 여기를 거친다
  const root = S.panes.find((p) => p.view.contains(el))?.view;
  if (!root) return;   // html 문서(iframe) 안 — 접기가 없다
  let top = el;
  while (top && top.parentElement !== root) top = top.parentElement;
  if (!top || !top.classList.contains('lec-fold-hidden')) return;
  let limit = levelOf(top) || 7;   // top 을 감싸는 제목은 top 보다 수준이 높다 (숫자가 작다)
  for (let prev = top.previousElementSibling; prev && limit > 1; prev = prev.previousElementSibling) {
    if (isBreak(prev)) break;
    const lv = levelOf(prev);
    if (!lv || lv >= limit) continue;
    limit = lv;
    if (prev.classList.contains('lec-folded')) setFolded(prev, false);
  }
  apply(root);
}

/** 누른 곳의 접기 화살표 — 제목 왼쪽 여백 (제목 줄 높이, 글 앞 32px 안). 제목 글자를 누르면 null (D120) */
function arrowAt(e) {
  const root = e.target.closest?.('.md-body') ?? e.target.querySelector?.(':scope > .md-body');
  if (!root) return null;
  const own = e.target.closest?.('.lec-fold');
  const list = own ? [own] : [...root.querySelectorAll(':scope > .lec-fold')];
  return list.find((h) => {
    const r = h.getBoundingClientRect();
    return e.clientX < r.left && e.clientX >= r.left - 32 && e.clientY >= r.top && e.clientY <= r.bottom;
  }) ?? null;
}

function onClick(e) {
  if (e.detail > 1) return;   // 두 번째 누름은 dblclick 에서 다룬다
  lastToggled = null;
  const h = arrowAt(e);
  if (!h || !getSelection().isCollapsed) return;   // Shift+클릭 등으로 글자를 고른 것은 고르기로 둔다
  toggle(h);
  lastToggled = h;
}

/** 블록이 든 가장 안쪽 절의 제목부터 바깥 절의 제목까지 */
function sectionsOf(top) {
  const out = [];
  let limit = levelOf(top) || 7;
  if (levelOf(top)) out.push(top);
  for (let prev = top.previousElementSibling; prev && limit > 1; prev = prev.previousElementSibling) {
    if (isBreak(prev)) break;
    const lv = levelOf(prev);
    if (!lv || lv >= limit) continue;
    limit = lv;
    out.push(prev);
  }
  return out.filter((h) => h.classList.contains('lec-fold'));
}

/** 제목 h 의 절 안에 접힌 하위 절을 모두 편다 */
function unfoldInside(h) {
  const lv = levelOf(h);
  for (let el = h.nextElementSibling; el && !isBreak(el); el = el.nextElementSibling) {
    const x = levelOf(el);
    if (x && x <= lv) break;
    if (x) el.classList.remove('lec-folded');
  }
  remember(h.parentElement);
  apply(h.parentElement);
}

/**
 * Ctrl+Shift+[ · ] (D120): 현재 줄이 든 절을 접고 편다. 이미 접혔으면 [ 는 바깥 절을 접고, 펴져 있으면 ] 는 안의 하위 절을 편다.
 * 본문 안에서 접으면 현재 줄은 그 제목으로 옮긴다 ('reveal' — spotlight.js). md 문서가 아니면 false
 */
export function foldHere(fold) {
  const root = view();
  if (!root?.classList.contains('md-body') || !root.querySelector(':scope > .lec-fold')) return false;
  let top = blockOfLine(root, S.pane?.here?.line || 0);
  while (top && top.parentElement !== root) top = top.parentElement;
  if (!top) return true;
  const heads = sectionsOf(top);
  const h = fold ? heads.find((x) => !x.classList.contains('lec-folded')) : heads.find((x) => x.classList.contains('lec-folded'));
  if (!h) {   // ] 인데 현재 절이 펴져 있다 — 그 안의 접힌 하위 절을 모두 편다 (두 번 누르면 끝까지)
    if (!fold && heads[0]) unfoldInside(heads[0]);
    return true;
  }
  setFolded(h, fold);
  apply(root);
  if (fold && h !== top) emit('reveal', h);
  return true;
}

function onDoubleClick(e) {
  // 두 번 눌러 낱말을 고르면 첫 번째 누름의 접기를 되돌린다
  if (lastToggled && e.target.closest('.lec-fold') === lastToggled) toggle(lastToggled);
  lastToggled = null;
}

export function initFold() {
  $('#lec-panes').addEventListener('click', onClick);
  $('#lec-panes').addEventListener('dblclick', onDoubleClick);
}
