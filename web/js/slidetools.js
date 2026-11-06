// 슬라이드 도구 (D96): 발표 문서를 슬라이드로 볼 때 상태줄의 '구조 보기'와 '점검'.
//
// - 구조 보기: 화면에 없는 칸 머리 줄(::: a card)과 지시어·노트 주석 줄을 꼬리표로 보인다. 꼬리표는 줄 단위라서 F2·두 번 누르기로 그 줄을 한 줄 편집한다.
//   꺼 둔 동안 꼬리표는 글도 data-lines 도 없다 — 찾기·줄 단위·편집 동기화에 들지 않게 (slides.js 의 addTags 가 자리만 만든다).
// - 점검: 넘친 칸과 잘못 쓴 칸(slides.js 의 wrap.dataset.issues)을 모은다. 누르면 목록 — 고른 장으로 가거나, 목록을 터미널에 붙여 넣는다 (Enter 없이 — D51).

import { S, on, emit } from './store.js';
import { $, $$, copyText, toast } from './util.js';
import { showMenu } from './ui.js';
import { followLine, forgetUnits } from './spotlight.js';
import { t } from './i18n.js';

let structure = false;   // 구조 보기 — 앱을 켜 둔 동안 창마다 하나

const isDeck = (pane = S.pane) => !!pane?.view?.classList.contains('lec-deck');

/** 칸(pane)의 꼬리표를 구조 보기 상태에 맞춘다 */
function applyStructure(pane) {
  if (!isDeck(pane)) return;
  pane.view.classList.toggle('lec-structure', structure);
  for (const tag of $$('.lec-tag', pane.view)) {
    if (structure) {
      tag.textContent = tag.dataset.tag;
      tag.dataset.lines = `${tag.dataset.tagLine}-${tag.dataset.tagLine}`;
    } else {
      tag.textContent = '';
      delete tag.dataset.lines;
    }
  }
  if (pane === S.pane) forgetUnits();
}

function toggleStructure() {
  structure = !structure;
  applyStructure(S.pane);
  updateButtons();
}

/** 지금 화면의 고칠 것들 [{page, text, line}] */
function issuesOf(view) {
  return $$(':scope > .lec-slide-wrap', view).flatMap((wrap, i) => (wrap.dataset.issues ? JSON.parse(wrap.dataset.issues).map((it) => ({ ...it, page: i + 1 })) : []));
}

function updateButtons() {
  const deck = isDeck();
  const toggle = $('#lec-st-structure');
  toggle.hidden = !deck;
  toggle.classList.toggle('on', structure);
  toggle.setAttribute('aria-pressed', String(structure));
  const issues = deck ? issuesOf(S.pane.view) : [];
  const pages = new Set(issues.map((it) => it.page)).size;
  const check = $('#lec-st-check');
  check.hidden = !pages;
  check.querySelector('span').textContent = t('점검 {n}장', { n: pages });
}

/** 터미널에 넣을 한 줄 — 여러 줄이면 터미널이 줄마다 보낸다 */
function issuesText(path, issues) {
  const rows = issues.map((it) => t('{page}장({line}행) {text}', { page: it.page, line: it.line, text: it.text }));
  const ask = t('@{path} 슬라이드 점검 결과입니다. 고쳐 주세요: {rows}', { path, rows: rows.join(' / ') });
  return S.slidesGuide ? `${ask} ${t('(작성 안내: {path})', { path: S.slidesGuide })}` : ask;
}

function openCheck() {
  const pane = S.pane;
  const issues = issuesOf(pane.view);
  if (!issues.length) return;
  const text = issuesText(pane.current?.path || '', issues);
  const r = $('#lec-st-check').getBoundingClientRect();
  showMenu(r.left, r.top, [
    { header: t('넘치거나 잘못 쓴 곳') },
    ...issues.map((it) => ({ label: t('{page}장 — {text}', { page: it.page, text: it.text }), action: () => { emit('jump'); followLine(it.line); } })),
    '-',
    { label: t('목록을 터미널에 붙여 넣기'), tip: t('터미널에 (Enter 는 누르지 않음)'), action: () => emit('term-paste', text) },
    { label: t('목록 복사'), action: () => copyText(text).then(() => toast(t('복사했습니다'))) },
  ]);
}

export function initSlideTools() {
  $('#lec-st-structure').addEventListener('click', toggleStructure);
  $('#lec-st-check').addEventListener('click', openCheck);
  on('rendered', (pane) => {
    applyStructure(pane);
    if (pane === S.pane) updateButtons();
  });
  on('pane', updateButtons);
  on('deck-shown', updateButtons);
  on('deck-checked', updateButtons);
}
