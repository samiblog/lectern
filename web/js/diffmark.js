// 바뀐 부분 강조: 자동 새로고침으로 같은 문서를 다시 그릴 때, 이전과 달라진 최상위 블록(문단·표·목록 등)에
// 잠깐 배경색을 주고, 바뀐 곳이 화면 밖이면 상태줄에 '바뀐 곳 N곳' 버튼을 띄운다 (누르면 차례로 이동).
//
// 처음 열 때와 내용이 같은 다시 그리기(스타일 변경 등)는 강조하지 않는다.
// 판정은 블록의 '서명'(태그 + 글자 + 그림 주소, 다이어그램은 원문)이 이전 화면에 있었는지로 한다.
// 지워진 블록은 표시할 곳이 없어 알리지 않는다.
// html 문서(iframe)는 구조가 문서마다 달라, 최상위 자식 대신 문단·목록 항목·표의 행 같은 작은 블록을 비교한다.
// 바뀐 블록은 칸(탭)마다 따로 기억하고(pane.marks — list: 바뀐 블록, next: 버튼이 다음에 갈 순번), 버튼은 선택된 탭의 것을 보인다.

import { S, on } from './store.js';
import { unfoldTo } from './fold.js';
import { $, screenRect } from './util.js';
import { t } from './i18n.js';

const FLASH_MS = 4000;

function signature(el) {
  const text = el.matches('pre.mermaid, pre.lec-chart') ? (el.dataset.source ?? '') : el.textContent.replace(/\s+/g, ' ').trim();
  const imgs = [...el.querySelectorAll('img')].map((i) => (i.getAttribute('src') || '').replace(/\?v=\d+$/, ''));
  return `${el.tagName}|${text}|${imgs.join(',')}`;
}

const HTML_BLOCKS = 'p, li, h1, h2, h3, h4, h5, h6, tr, pre, blockquote, figure, dt, dd, img';

/** 비교할 블록: md 는 #lec-view 의 최상위 자식, html 문서는 iframe body 안의 작은 블록 */
const blocksOf = (root) => (root.ownerDocument === document ? [...root.children] : [...root.querySelectorAll(HTML_BLOCKS)]);

/** 다시 그리기 직전의 화면을 기록한다. 같은 문서를 다시 그릴 때만 쓴다. */
export function snapshot(root) {
  const seen = new Map();
  for (const el of blocksOf(root)) {
    const s = signature(el);
    seen.set(s, (seen.get(s) || 0) + 1);
  }
  return seen;
}

/** 블록(여럿이면 한꺼번에)을 잠깐 강조한다 (전체 검색 결과로 갈 때도 쓴다) */
export function flashBlock(...els) {
  if (!els.length) return;
  for (const el of els) el.classList.remove('lec-changed');
  void els[0].offsetWidth;   // 애니메이션을 처음부터 다시 — 블록마다 하면 큰 문서에서 화면 배치를 수천 번 다시 한다
  for (const el of els) el.classList.add('lec-changed');
  setTimeout(() => { for (const el of els) el.classList.remove('lec-changed'); }, FLASH_MS + 200);
}

function outOfView(el, pane) {
  const box = pane.scroller.getBoundingClientRect();
  const r = screenRect(el);
  return r.height === 0 || r.bottom < box.top || r.top > box.bottom;
}

function renderButton() {
  const marked = S.pane?.marks.list || [];
  const btn = $('#lec-st-changes');
  btn.hidden = !marked.length;
  btn.textContent = `${t('바뀐 곳 {n}곳', { n: marked.length })} ↓`;
  btn.title = t('자동 새로고침으로 바뀐 곳으로 차례로 이동');
}

/**
 * 칸(pane)에 문서를 그린 직후 부른다. before 는 snapshot() 결과(처음 열 때는 null).
 * 바뀐 블록을 강조하고, 하나라도 화면 밖이면 '바뀐 곳' 버튼을 보인다.
 */
export function markChanges(root, before, pane) {
  let marked = [];
  if (before) {
    const left = new Map(before);
    for (const el of blocksOf(root)) {
      const s = signature(el);
      if (left.get(s)) left.set(s, left.get(s) - 1);
      else marked.push(el);
    }
    if (root.ownerDocument !== document) {
      // html: 바뀐 목록 항목 안의 문단은 한 번만. 조상을 따라 올라가며 본다 (블록끼리 모두 비교하면 큰 표에서 멈춘다).
      // md 는 최상위 블록끼리라 겹치지 않는다
      const set = new Set(marked);
      marked = marked.filter((el) => {
        for (let a = el.parentElement; a && a !== root; a = a.parentElement) if (set.has(a)) return false;
        return true;
      });
    }
    flashBlock(...marked);
  }
  if (!marked.some((el) => outOfView(el, pane))) marked = [];
  pane.marks = { list: marked, next: 0 };
  if (pane === S.pane) renderButton();
}

/** 칸(pane)의 바뀐 곳을 지운다 (문서 없음·폴더 개요) */
export function clearChanges(pane) {
  pane.marks = { list: [], next: 0 };
  if (pane === S.pane) renderButton();
}

function goNext() {
  const m = S.pane.marks;
  if (!m.list.length) return;
  const el = m.list[m.next % m.list.length];
  m.next += 1;
  unfoldTo(el);
  el.scrollIntoView({ block: 'center' });
  flashBlock(el);
}

export function initChangeMarks() {
  $('#lec-st-changes').addEventListener('click', goNext);
  on('pane', renderButton);
}
