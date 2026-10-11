// 바뀐 부분 강조: 자동 새로고침으로 같은 문서를 다시 그릴 때, 이전과 달라진 최상위 블록(문단·표·목록 등)에
// 잠깐 배경색을 주고, 바뀐 곳이 화면 밖이면 상태줄에 '바뀐 곳 N곳' 버튼을 띄운다 (누르면 차례로 이동).
//
// 처음 열 때와 내용이 같은 다시 그리기(스타일 변경 등)는 강조하지 않는다.
// 판정은 블록의 '서명'(태그 + 글자 + 그림 주소, 다이어그램은 원문)이 이전 화면에 있었는지로 한다.
// 지워진 블록은 표시할 곳이 없어 알리지 않는다.

import { on } from './store.js';
import { unfoldTo } from './fold.js';
import { $ } from './util.js';

const FLASH_MS = 4000;
let marked = [];   // 이번 화면에서 바뀐 블록
let next = 0;      // '바뀐 곳' 버튼이 다음에 갈 순번
let path = null;   // 그 블록들이 있는 문서

function signature(el) {
  const text = el.matches('pre.mermaid') ? (el.dataset.source ?? '') : el.textContent.replace(/\s+/g, ' ').trim();
  const imgs = [...el.querySelectorAll('img')].map((i) => (i.getAttribute('src') || '').replace(/\?v=\d+$/, ''));
  return `${el.tagName}|${text}|${imgs.join(',')}`;
}

/** 다시 그리기 직전의 화면을 기록한다. 같은 문서를 다시 그릴 때만 쓴다. */
export function snapshot(view) {
  const seen = new Map();
  for (const el of view.children) {
    const s = signature(el);
    seen.set(s, (seen.get(s) || 0) + 1);
  }
  return seen;
}

function flash(el) {
  el.classList.remove('lec-changed');
  void el.offsetWidth;   // 애니메이션을 처음부터 다시
  el.classList.add('lec-changed');
  setTimeout(() => el.classList.remove('lec-changed'), FLASH_MS + 200);
}

function outOfView(el) {
  const box = $('#lec-content').getBoundingClientRect();
  const r = el.getBoundingClientRect();
  return r.height === 0 || r.bottom < box.top || r.top > box.bottom;
}

function renderButton() {
  const btn = $('#lec-st-changes');
  btn.hidden = !marked.length;
  btn.textContent = `바뀐 곳 ${marked.length}곳 ↓`;
  btn.title = '자동 새로고침으로 바뀐 곳으로 차례로 이동';
}

/**
 * 문서를 그린 직후 부른다. before 는 snapshot() 결과(처음 열 때는 null).
 * 바뀐 블록을 강조하고, 하나라도 화면 밖이면 '바뀐 곳' 버튼을 보인다.
 */
export function markChanges(view, docPath, before) {
  marked = [];
  next = 0;
  path = docPath;
  if (before) {
    const left = new Map(before);
    for (const el of view.children) {
      const s = signature(el);
      if (left.get(s)) left.set(s, left.get(s) - 1);
      else marked.push(el);
    }
    marked.forEach(flash);
  }
  if (!marked.some(outOfView)) marked = [];
  renderButton();
}

export function clearChanges() {
  marked = [];
  path = null;
  renderButton();
}

function goNext() {
  if (!marked.length) return;
  const el = marked[next % marked.length];
  next += 1;
  unfoldTo(el);
  el.scrollIntoView({ block: 'center' });
  flash(el);
}

export function initChangeMarks() {
  $('#lec-st-changes').addEventListener('click', goNext);
  on('view', (v) => { if (v.type !== 'doc' || v.path !== path) clearChanges(); });
}
