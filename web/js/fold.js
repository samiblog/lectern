// 제목 접기: 문서 속 제목을 누르면 그 절(다음 같은 수준 이상의 제목 전까지)을 접고, 다시 누르면 편다.
//
// 문서 DOM은 markdown-it 이 만든 평평한 구조 그대로 둔다 (절을 <section> 으로 감싸면 CSS·찾기·목차가 영향을 받는다).
// 접을 수 있는 제목에 lec-fold, 접힌 제목에 lec-folded, 그 아래 숨는 최상위 블록에 lec-fold-hidden 을 준다.
// 접은 상태는 문서 경로별로 이번 실행 동안만 기억한다 (자동 새로고침·뒤로 가기에도 유지, 디스크에 쓰지 않음).

import { $ } from './util.js';

const folds = new Map();   // 문서 경로 → 접힌 제목 키 집합
let docPath = '';          // 지금 보이는 문서. lec-fold 제목은 문서 화면에만 있으므로 접을 때는 늘 이 문서다
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
  docPath = path;
  const saved = folds.get(path);
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

/** 다른 폴더를 열면 접은 상태를 잊는다. */
export function forgetFolds() {
  folds.clear();
}

function setFolded(h, folded) {
  const root = view();
  h.classList.toggle('lec-folded', folded);
  const keys = headings(root).flatMap((x, i) => (x.classList.contains('lec-folded') ? [keyOf(x, i)] : []));
  if (keys.length) folds.set(docPath, new Set(keys));
  else folds.delete(docPath);
}

function toggle(h) {
  setFolded(h, !h.classList.contains('lec-folded'));
  apply(view());
}

/**
 * el 이 접힌 절 안에 있으면 그 절들을 편다. 목차·앵커 링크·찾기가 숨은 곳으로 갈 때 먼저 부른다.
 * (숨은 요소는 display:none 이라 위치가 0이어서 스크롤할 수 없다)
 */
export function unfoldTo(el) {
  const root = view();
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

function onClick(e) {
  if (e.detail > 1) return;   // 두 번째 누름은 dblclick 에서 다룬다
  lastToggled = null;
  const h = e.target.closest('.lec-fold');
  // 제목 속 링크는 링크로, Shift+클릭 등으로 글자를 고른 것은 고르기로 둔다
  if (!h || e.target.closest('a') || !getSelection().isCollapsed) return;
  toggle(h);
  lastToggled = h;
}

function onDoubleClick(e) {
  // 두 번 눌러 낱말을 고르면 첫 번째 누름의 접기를 되돌린다
  if (lastToggled && e.target.closest('.lec-fold') === lastToggled) toggle(lastToggled);
  lastToggled = null;
}

export function initFold() {
  view().addEventListener('click', onClick);
  view().addEventListener('dblclick', onDoubleClick);
}
