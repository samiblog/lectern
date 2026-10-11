// 장 하이라이트 (툴바 버튼): 문서에서 한 장만 지금 모양 그대로 보이고, 나머지 글자·선·그림은 바탕색 쪽으로 흐려진다.
//
// - 장은 문서의 맨 위 수준 절이다. H1 이 맨 앞에 하나뿐이면(문서 제목) H2 절, 아니면 H1 절. 첫 장 앞의 제목·머리말도 한 장이다.
//   각주(.footnotes)는 어느 장에도 들지 않는다.
// - 켜져 있으면 ↑·↓·PageUp·PageDown 으로 앞뒤 장(main.js 가 부른다), 흐린 곳을 누르면 그 장, Esc·버튼으로 끈다.
//   목차·찾기·앵커·전체 검색·바뀐 곳으로 가면 그곳의 장으로 옮긴다 (fold.js 의 unfoldTo 가 보내는 'reveal').
// - 흐리게 하는 것은 CSS 뿐이다 (base.css 의 .lec-spotlight, opacity). 문서 DOM 은 그대로 두고 블록에 lec-lit 만 붙인다.
// - md 문서만. html 문서(iframe)는 구조가 문서마다 달라 장을 나눌 수 없다.

import { on } from './store.js';
import { $ } from './util.js';

let active = false;
let chapters = [];   // [[블록, …], …] — 블록은 #lec-view 의 자식
let current = 0;
let shownPath = null;   // 장을 나눈 문서

const view = () => $('#lec-view');
// 'rendered' 때는 S.view 가 아직 앞 화면이므로 화면(DOM)으로 본다. doc.js 가 그린 md 문서에 data-doc-path 를 단다
const isMdDoc = () => view().classList.contains('md-body') && !!view().dataset.docPath && !view().querySelector('.doc-missing');
const levelOf = (el) => (/^H([1-6])$/.exec(el.tagName) ? Number(el.tagName[1]) : 0);

/** 장을 나누는 제목 수준. 장이 둘 이상 나오지 않으면 0 */
function chapterLevel(blocks) {
  const heads = blocks.filter(levelOf);
  if (!heads.length) return 0;
  const h1 = heads.filter((h) => h.tagName === 'H1');
  if (h1.length === 1 && heads[0] === h1[0]) {   // 맨 앞의 H1 하나는 문서 제목 — 그 아래 절로 나눈다
    const rest = heads.slice(1).map(levelOf);
    return rest.length ? Math.min(...rest) : 0;
  }
  return Math.min(...heads.map(levelOf));
}

function build() {
  const blocks = [...view().children].filter((el) => !el.matches('.footnotes-sep, .footnotes'));
  const lv = chapterLevel(blocks);
  chapters = [];
  if (!lv) return;
  let cur = [];
  for (const el of blocks) {
    const h = levelOf(el);
    if (h && h <= lv && cur.length) {
      chapters.push(cur);
      cur = [];
    }
    cur.push(el);
  }
  if (cur.length) chapters.push(cur);
  if (chapters.length < 2) chapters = [];
}

function paint() {
  const root = view();
  root.classList.toggle('lec-spotlight', active && chapters.length > 0);
  for (const el of root.querySelectorAll(':scope > .lec-lit')) el.classList.remove('lec-lit');
  if (active && chapters[current]) for (const el of chapters[current]) el.classList.add('lec-lit');
  updateButton();
}

function updateButton() {
  const btn = $('#lec-btn-spot');
  const usable = isMdDoc() && chapters.length > 0;
  btn.classList.toggle('on', active);
  btn.disabled = !usable && !active;
  btn.title = usable || active
    ? `장 하이라이트 ${active ? '끄기' : '켜기'} — 켜면 ↑·↓·PageUp·PageDown 으로 앞뒤 장 (Esc 로 끄기)`
    : '장 하이라이트: 제목으로 나뉜 Markdown 문서에서 쓸 수 있습니다';
}

/** 지금 화면 위쪽에 보이는 장 */
function chapterAtTop() {
  const top = $('#lec-content').getBoundingClientRect().top;
  let found = 0;
  chapters.forEach((blocks, i) => {
    const first = blocks.find((el) => el.getClientRects().length) || blocks[0];
    if (first.getBoundingClientRect().top <= top + 80) found = i;
  });
  return found;
}

function chapterOf(el) {
  let top = el;
  while (top && top.parentElement !== view()) top = top.parentElement;
  return top ? chapters.findIndex((blocks) => blocks.includes(top)) : -1;
}

function select(i, { scroll = false } = {}) {
  if (!chapters[i]) return;
  current = i;
  paint();
  if (scroll) {
    const first = chapters[i].find((el) => el.getClientRects().length) || chapters[i][0];
    const content = $('#lec-content');
    content.scrollTop += first.getBoundingClientRect().top - content.getBoundingClientRect().top - 18;
  }
}

export const spotlightOn = () => active && chapters.length > 0;

/** ↑·↓·PageUp·PageDown: 앞(-1)·뒤(+1) 장으로 가서 그 장의 처음을 화면 위에 둔다 */
export function moveSpotlight(step) {
  if (!spotlightOn()) return false;
  select(Math.max(0, Math.min(chapters.length - 1, current + step)), { scroll: true });
  return true;
}

export function toggleSpotlight(on = !active) {
  if (on && !(isMdDoc() && chapters.length)) return;
  active = on;
  if (active) current = chapterAtTop();
  paint();
}

export function stopSpotlight() {
  if (!active) return false;
  toggleSpotlight(false);
  return true;
}

/** 본문 우클릭 메뉴(docmenu.js)의 항목: 우클릭한 곳의 장 하이라이트 / 하이라이트 해제. 쓸 수 없는 문서면 빈 목록 */
export function spotlightItems(target) {
  if (!isMdDoc() || !chapters.length) return [];
  const i = chapterOf(target);
  const items = [];
  if (!active || (i >= 0 && i !== current)) {
    items.push({
      label: i >= 0 ? '이 장 하이라이트' : '장 하이라이트',
      hint: '나머지는 흐리게 — ↑·↓·PageUp·PageDown 으로 앞뒤 장',
      action: () => {
        active = true;
        current = i >= 0 ? i : chapterAtTop();
        paint();
      },
    });
  }
  if (active) items.push({ label: '하이라이트 해제', hint: 'Esc', action: () => toggleSpotlight(false) });
  return items;
}

export function initSpotlight() {
  $('#lec-btn-spot').addEventListener('click', () => toggleSpotlight());
  // 다시 그리면(자동 새로고침·스타일 변경) 같은 장을 다시 강조한다. 다른 문서면 화면 위쪽의 장부터
  on('rendered', () => {
    const path = isMdDoc() ? view().dataset.docPath : null;
    const keep = chapters[current]?.[0];
    const keepId = keep && levelOf(keep) ? keep.id : null;
    if (path) build();
    else chapters = [];
    if (active && chapters.length) {
      const same = path === shownPath && keepId ? chapters.findIndex((blocks) => blocks[0].id === keepId) : -1;
      current = same >= 0 ? same : (path === shownPath ? Math.min(current, chapters.length - 1) : chapterAtTop());
    }
    shownPath = path;
    paint();
  });
  // 목차·찾기·앵커·바뀐 곳으로 가면 그 장을 강조한다
  on('reveal', (el) => {
    if (!spotlightOn()) return;
    const i = chapterOf(el);
    if (i >= 0 && i !== current) select(i);
  });
  // 흐린 장을 누르면 그 장을 강조한다 (그 누름은 링크·접기로 쓰지 않는다)
  view().addEventListener('click', (e) => {
    if (!spotlightOn() || window.getSelection()?.toString()) return;
    const i = chapterOf(e.target);
    if (i < 0 || i === current) return;
    e.preventDefault();
    e.stopPropagation();
    select(i);
  }, true);
}
