// 현재 위치와 하이라이트 (D74·D75). md 문서와 코드 화면(csv·txt 포함)에서, 줄은 원문 줄이다 (lineunits.js — 한 줄로 쓴 문단·목록 항목·
// 제목·표의 행은 블록 통째, 여러 줄로 나눠 쓴 문단은 줄마다, 코드는 줄마다, 다이어그램·수식은 통째).
//
// - 현재 위치 (D75): 지금 보는 줄 — 본문 왼쪽 여백의 작은 삼각형(.lec-here). 누르면 그 줄, ↑·↓ 로 한 줄씩(화면이 따라감 — 화면보다 큰 줄은
//   그 줄 안을 먼저 스크롤). 휠·스크롤 막대·PageUp·PageDown 으로 화면 밖으로 나가면 화면 안의 가장 가까운 줄로 따라온다.
//   목차·찾기·검색·앵커로 가면 그 줄로 ('reveal'). 칸(문서 탭)마다 원문 줄로 남는다 (pane.here — 다시 그려도 같은 줄, 처음은 화면 맨 위 줄).
//   나중에 책갈피 등으로 넓힌다.
// - 줄 하이라이트 (D75): Shift+누르기·Shift+끌기, Shift+Enter(현재 줄), Shift+↑·↓. 편집기의 고르기처럼 처음 줄(anchor)은 두고 끝 줄(focus)을
//   옮긴다 — 끝 줄이 현재 위치. 하이라이트가 있으면 Shift+누르기는 거기까지 넓히고, Shift+↑·↓ 는 끝 줄을 옮겨 넓히거나 줄이고(처음 줄을 넘으면
//   반대쪽으로), ↑·↓ 는 하이라이트를 풀고 현재 위치를 옮긴다. 하이라이트가 없을 때 Shift+↑·↓ 는 현재 줄부터.
//   범위는 원문 줄로 남겨 다시 그려도 같은 곳이다 (그 줄이 없어졌거나 다른 문서면 푼다). 흐린 곳을 누르거나 Esc·버튼으로 끈다.
// - 장 하이라이트: 툴바 버튼 (장이 없는 문서·코드 화면이면 현재 줄을 하이라이트). 장은 문서의 맨 위 수준 절이다. H1 이 하나뿐이면(문서 제목)
//   그 아래 수준(보통 H2) 절, 아니면 H1 절. 첫 장 앞의 제목·머리말도 한 장이다. 장의 범위는 그 장 제목을 눌러 접을 때 숨는 범위와 같다
//   (다음 같은 수준 이상의 제목 앞까지, 각주 제외 — fold.js 와 같은 규칙). ↑·↓·PageUp·PageDown·버튼 옆 ∧∨ 로 앞뒤 장, 흐린 곳을 누르면 그 장,
//   목차·찾기·앵커·전체 검색·바뀐 곳으로 가면 그곳의 장으로 (fold.js 의 unfoldTo 가 보내는 'reveal'). Shift+↑·↓ 를 누르면 그 장의 처음~끝 줄을
//   줄 하이라이트로 바꿔 넓히고 줄인다.
// - 키 (main.js 의 keydown 이 spotKey 로): Shift+→ 하이라이트한 곳을 맨 앞 터미널(보통 1번 — Claude Code)에 '@경로 a~b행' 으로 (Enter 없이 —
//   D51·D69 와 같은 길, 초점은 문서에), Ctrl+Shift+→ 같은 일을 하고 초점도 터미널로 (D79), Shift+← 그 위치 복사, Ctrl+C 원문 복사 (고른 글이 없을 때),
//   F2 현재 줄·한 줄 하이라이트를 한 줄 편집 (D76).
//   상태줄에 하이라이트한 줄 범위 (#lec-st-lit).
// - 우클릭 메뉴(docmenu.js)는 하이라이트한 곳 안이면 그 범위의 선택 상자 — litAt.
// - 그리기: 칸의 스크롤 상자에 덮개(.lec-spot — 하이라이트 위·아래를 덮는 반투명 회색 둘과 왼쪽 강조 막대)와 현재 위치 삼각형을 겹쳐 둔다 (base.css).
//   문서 DOM 은 그대로이고 장의 블록에 lec-lit 만 붙인다. 위치는 블록의 화면 위치로 재므로, 문서의 크기가 바뀌면(그림을 불러옴·접기·칸 폭·
//   글자 크기 — ResizeObserver) 다시 잰다. 덮개는 누르기를 막지 않는다 (pointer-events: none).
//   한 줄 편집 중(lineedit.js, D76)에는 회색을 걷고 막대만 둔다 (.lec-spot.editing — 위아래 글을 읽으며 고치게, ↑·↓ 로 이어 고치는 동안도).
// - html 문서(iframe)는 원문 줄을 몰라 쓰지 않는다. 슬라이드로 보는 Lectern 슬라이드(D59)는 슬라이드 하나가 한 장 (장 하이라이트만).
// - 선택된 탭의 칸(#lec-view)의 화면에 한다. 다른 탭을 고르면 하이라이트는 꺼지고, 현재 위치는 그 칸의 것이 보인다.

import { S, on, emit } from './store.js';
import { html, setHtml } from './html.js';
import { $, toast, copyText, rangeText, lineRef } from './util.js';
import { t } from './i18n.js';
import { collectUnits, indexOfLine, hasLine, unitAt, markOf, baseOf, blockOfLine } from './lineunits.js';

let active = false;
let mode = 'chapter';   // 'chapter' — 장 하이라이트, 'range' — 줄 하이라이트
let anchor = 0;         // 줄 하이라이트의 처음 줄·끝 줄 (원문 줄 — 단위의 첫 줄). 끝 줄이 현재 위치
let focus = 0;
let chapters = [];      // [[블록, …], …] — 블록은 #lec-view 의 자식
let current = 0;
let shownPath = null;   // 마지막으로 그린 화면의 문서·코드 경로
let painted = null;     // 마지막으로 칠한 화면 — 다른 탭을 고르면 거기서 지운다
let drag = null;        // Shift+끌기 중 {units, x, y, raf}
let swallowClick = false;   // 끌기를 마친 누르기 (링크·접기로 쓰지 않는다)
let resizer = null;
let observed = null;
let cache = null;       // 줄 단위 {root, key, units}
let gen = 0;            // 다시 그리거나 크기가 바뀌면 늘려 줄 단위를 다시 잰다
let codeSrc = { text: null, lines: [] };
let followRaf = 0;
let revealing = 0;      // 'reveal' 뒤 현재 위치를 그곳으로 옮기기 전 — 그사이의 스크롤로 따라오지 않게
let revealLine = null; // 다음 'reveal' 에서 현재 위치로 삼을 원문 줄 — 여러 줄 블록 안의 자리로 돌아갈 때 (뒤로·앞으로, nav.js)

let dimmed = false;     // 고른 줄을 하이라이트했는지 (D108) — 고른 줄은 범위일 뿐이고, 하이라이트는 나머지를 흐리게 보는 것이다

const PAD = 10;   // 하이라이트 띠의 위·아래 여유 (px)
const view = () => $('#lec-view');
/** 선택된 칸에서 한 줄 편집 중인지 — 시작해서 끝낼 때까지, ↑·↓ 로 다음 줄로 넘어가는 사이(lineEditHold)도 */
const lineEditing = () => !!(S.pane?.lineEdit || S.pane?.lineEditHold);
// 'rendered' 때는 S.view 가 아직 앞 화면이므로 화면(DOM)으로 본다. doc.js 가 그린 md 문서에 data-doc-path, codeview.js 가 data-code-path 를 단다
const isMdDoc = () => view().classList.contains('md-body') && !!view().dataset.docPath && !view().querySelector('.doc-missing');
const isCodeView = () => view().classList.contains('code-view') && !!view().dataset.codePath;
const isDeck = () => view().classList.contains('lec-deck');
/** 현재 위치·줄 하이라이트를 쓰는 화면: md 문서(Lectern 슬라이드 뺌)와 코드 화면 */
const linesOn = () => isMdDoc() || isCodeView();
const pathOf = () => (isCodeView() ? view().dataset.codePath : view().dataset.docPath);
const levelOf = (el) => (/^H([1-6])$/.exec(el.tagName) ? Number(el.tagName[1]) : 0);
const lit = () => active && (mode === 'range' ? linesOn() : chapters.length > 0);
const ranged = () => lit() && mode === 'range';
// 누르기로 줄을 고르지 않는 곳 — 코드 화면의 머리줄·csv 의 거르기 칸 등
const NO_PICK = 'input, button, select, textarea, .cv-head, .csv-bar, .csv-filter, .csv-head';
// 본문의 할 일 체크박스는 글처럼 — 누르면 그 줄이 현재 위치, 흐린 곳이면 하이라이트만 끈다 (lineedit.js 의 onTaskClick 이 받기 전에)
const noPick = (el) => !!el.closest(NO_PICK) && !el.matches('.task-list-item-checkbox');

/** 원문 줄 배열 — md 는 doc.js 가 넘긴 원문(docmenu.setDocSource), 코드 화면은 그 글 */
function srcLines() {
  if (isCodeView()) {
    const text = view().codeText ?? '';
    if (codeSrc.text !== text) codeSrc = { text, lines: text.replace(/^﻿/, '').split(/\r\n?|\n/) };
    return codeSrc.lines;
  }
  const src = S.pane?.source;
  return src && src.path === view().dataset.docPath ? src.lines : [];
}

/** 지금 화면의 줄 단위 (lineunits.js). 다시 그리거나 크기가 바뀌기 전까지 재지 않는다 */
function units() {
  const root = view();
  if (!linesOn()) return [];
  const key = `${gen}|${root.offsetWidth}|${root.offsetHeight}`;
  if (cache?.root !== root || cache.key !== key) cache = { root, key, units: collectUnits(root, srcLines()) };
  return cache.units;
}

/** 칸에 보이는 곳 (스크롤 상자 안 좌표). 코드 화면은 위에 붙은 머리줄(csv 는 머리행도) 아래부터 */
function viewport() {
  const root = view();
  const sc = root.parentElement;
  let inset = 0;
  if (isCodeView()) {
    inset = root.querySelector(':scope > .cv-head')?.offsetHeight || 0;
    inset += root.querySelector('.csv-table > thead')?.offsetHeight || 0;
  }
  return { sc, top: sc.scrollTop + inset, bottom: sc.scrollTop + sc.clientHeight };
}

/** 본문 글의 왼쪽 끝 (스크롤 상자 안 x) — 그 왼쪽 여백에 하이라이트 막대와 현재 위치 삼각형 */
function textLeft(root) {
  const sc = root.parentElement;
  return root.getBoundingClientRect().left - sc.getBoundingClientRect().left + parseFloat(getComputedStyle(root).paddingLeft || '0');
}

// ---- 장 -------------------------------------------------------------------------

/** 장을 나누는 제목 수준. 장이 둘 이상 나오지 않으면 0 */
function chapterLevel(blocks) {
  const heads = blocks.filter(levelOf);
  if (!heads.length) return 0;
  const h1 = heads.filter((h) => h.tagName === 'H1');
  if (h1.length === 1) {   // H1 이 하나뿐이면 문서 제목 — 그 아래 절로 나눈다 (fold.js 가 제목을 접지 않는 규칙과 같다)
    const rest = heads.filter((h) => h.tagName !== 'H1').map(levelOf);
    return rest.length ? Math.min(...rest) : 0;
  }
  return Math.min(...heads.map(levelOf));
}

function build() {
  if (isDeck()) {   // Lectern 슬라이드: 슬라이드마다 한 장 (slides.js)
    chapters = [...view().querySelectorAll(':scope > .lec-slide-wrap')].map((el) => [el]);
    if (chapters.length < 2) chapters = [];
    return;
  }
  const blocks = [...view().children].filter((el) => !el.matches('.footnotes-sep, .footnotes'));
  const lv = chapterLevel(blocks);
  chapters = [];
  if (!lv) return;
  let cur = [];
  for (const el of blocks) {
    const h = levelOf(el);
    // 메타데이터 표(frontmatter)만 있는 앞부분은 장으로 떼지 않고 다음(제목) 장에 붙인다
    if (h && h <= lv && cur.length && !cur.every((b) => b.matches('.front-matter'))) {
      chapters.push(cur);
      cur = [];
    }
    cur.push(el);
  }
  if (cur.length) chapters.push(cur);
  if (chapters.length < 2) chapters = [];
}

/** 지금 장의 블록에 든 첫·끝 줄 단위의 차례 [lo, hi] (없으면 null) */
function chapterIndexes(us) {
  const blocks = new Set(chapters[current] || []);
  let lo = -1;
  let hi = -1;
  us.forEach((u, i) => {
    let top = u.el;
    while (top && top.parentElement !== view()) top = top.parentElement;
    if (!blocks.has(top)) return;
    if (lo < 0) lo = i;
    hi = i;
  });
  return lo < 0 ? null : [lo, hi];
}

/** 지금 장의 원문 줄 처음~끝 (접힌 것도) */
function chapterLines() {
  let a = Infinity;
  let b = -Infinity;
  for (const el of chapters[current] || []) {
    for (const x of [el, ...el.querySelectorAll('[data-lines]')]) {
      const m = /^(\d+)-(\d+)$/.exec(x.dataset?.lines || '');
      if (!m) continue;
      a = Math.min(a, +m[1]);
      b = Math.max(b, +m[2]);
    }
  }
  return a <= b ? [a, b] : null;
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

/** 현재 위치(작은 화살표)가 든 장 — 현재 위치가 없거나 어느 장에도 들지 않으면 화면 위쪽의 장 */
function chapterHere() {
  const here = S.pane?.here;
  const el = here?.path === pathOf() ? blockOfLine(view(), here.line) : null;
  const i = el ? chapterOf(el) : -1;
  return i >= 0 ? i : chapterAtTop();
}

/** 장 하이라이트를 그 장으로. 현재 위치가 그 장 밖이면 그 장의 첫 줄로 */
function select(i, { scroll = false } = {}) {
  if (!chapters[i]) return;
  active = true;
  mode = 'chapter';
  current = i;
  paint();
  if (scroll) {
    const first = chapters[i].find((el) => el.getClientRects().length) || chapters[i][0];
    const content = $('#lec-content');
    content.scrollTop += first.getBoundingClientRect().top - content.getBoundingClientRect().top - 18;
  }
  if (!linesOn()) return;
  const us = units();
  const ix = chapterIndexes(us);
  const h = hereIndex(us);
  if (ix && (h < ix[0] || h > ix[1])) setHere(us[ix[0]].a);
}

// ---- 현재 위치 --------------------------------------------------------------------

/** 화면 맨 위·맨 아래에 보이는 줄 단위의 차례 */
function edgeIndex(us, atTop) {
  const { top, bottom } = viewport();
  if (atTop) {
    let i = us.findIndex((u) => u.top >= top - 1);
    if (i < 0 || us[i].top >= bottom) i = us.findIndex((u) => u.bottom > top + 2);
    return Math.max(0, i);
  }
  let i = us.findLastIndex((u) => u.bottom <= bottom + 1);
  if (i < 0 || us[i].bottom <= top) i = us.findLastIndex((u) => u.top < bottom - 2);
  return Math.max(0, i);
}

/** 현재 위치의 줄 단위 차례 — 이 칸에서 처음이거나 다른 문서면 화면 맨 위에 보이는 줄로 */
function hereIndex(us = units()) {
  const pane = S.pane;
  if (!pane || !us.length) return -1;
  const path = pathOf();
  if (pane.here?.path !== path) pane.here = { path, line: us[edgeIndex(us, true)].a };
  return indexOfLine(us, pane.here.line);
}

/** 현재 위치를 원문 줄 line 으로. scroll: 그 줄이 보이게 (위·아래에 조금 여유를 두고) */
function setHere(line, { scroll = false } = {}) {
  if (!S.pane || !linesOn()) return;
  S.pane.here = { path: pathOf(), line };
  if (scroll) {
    const us = units();
    const i = indexOfLine(us, line);
    if (i >= 0) showUnit(us[i]);
  }
  drawHere();
}

function showUnit(u) {
  const vp = viewport();
  const margin = Math.min(48, (vp.bottom - vp.top) * 0.15);
  if (u.top < vp.top + margin) vp.sc.scrollTop -= vp.top + margin - u.top;
  else if (u.bottom > vp.bottom - margin) vp.sc.scrollTop += Math.max(0, Math.min(u.bottom - (vp.bottom - margin), u.top - (vp.top + margin)));
}

let herePainted = null;

/** 현재 위치 삼각형을 그 줄의 첫 화면 줄 왼쪽에 (선택된 칸에만) */
function drawHere() {
  const root = view();
  if (herePainted && herePainted !== root) herePainted.parentElement?.querySelector(':scope > .lec-here')?.remove();
  herePainted = root;
  const sc = root.parentElement;
  if (!sc?.classList.contains('lec-scroll')) return;
  let mark = sc.querySelector(':scope > .lec-here');
  const us = units();
  const i = hereIndex(us);
  if (i < 0) {
    mark?.remove();
    return;
  }
  if (!mark) {
    mark = document.createElement('div');
    mark.className = 'lec-here';
    mark.setAttribute('aria-hidden', 'true');
    sc.append(mark);
  }
  // 아직 파일에 없는 새 줄을 쓰는 동안은 그 줄에 (D106 — 줄 단위가 아니다). 스크롤로 다시 그려도 그대로
  const fresh = S.pane?.lineEdit?.fresh ? S.pane.lineEdit.el : null;
  mark.style.setProperty('--here-y', `${Math.round(fresh ? freshY(fresh, baseOf(root)) : markOf(us[i], baseOf(root)))}px`);
  const cell = us[i].el.closest?.('.lec-cell');
  const left = cell ? cell.getBoundingClientRect().left - sc.getBoundingClientRect().left : textLeft(root);
  mark.style.setProperty('--here-x', `${Math.round(Math.max(1, left - 12))}px`);
}

/** 새 줄의 첫 화면 줄 가운데 (스크롤 상자 안 좌표) */
function freshY(el, base) {
  const r = el.getBoundingClientRect();
  const line = parseFloat(getComputedStyle(el).lineHeight) || r.height;
  return r.top - base + Math.min(r.height, line) / 2;
}

/** 새 줄을 열었을 때 화살표를 그리로 (lineedit.js, D106) */
export const hereAtNew = () => drawHere();

/** ↑·↓: 현재 위치를 한 줄 옮기고 그 줄이 보이게. 화면보다 큰 줄은 그쪽의 남은 곳을 먼저 스크롤해 보인다. 마지막 줄의 ↓ 는 새 줄을 연다 (D106) */
function moveHere(step, repeat = false) {
  const us = units();
  if (!us.length && step > 0) {   // 빈 문서
    emit('line-end');
    return true;
  }
  const i = hereIndex(us);
  if (i < 0) return false;
  const vp = viewport();
  const u = us[i];
  const room = vp.bottom - vp.top;
  if (u.bottom - u.top > room * 0.6) {
    if (step > 0 && u.bottom > vp.bottom + 1 && u.top < vp.bottom) {
      vp.sc.scrollTop += Math.min(u.bottom - vp.bottom + 24, room * 0.4);
      return true;
    }
    if (step < 0 && u.top < vp.top - 1 && u.bottom > vp.top) {
      vp.sc.scrollTop -= Math.min(vp.top - u.top + 24, room * 0.4);
      return true;
    }
  }
  const j = Math.max(0, Math.min(us.length - 1, i + step));
  if (j === i) vp.sc.scrollTop += step * 40;   // 첫 줄·마지막 줄: 문서의 위·아래 여백까지
  setHere(us[j].a, { scroll: true });
  if (j === i && step > 0 && !repeat) emit('line-end');
  return true;
}

/** 스크롤해서 현재 위치가 화면 밖으로 나가면 화면 안의 가장 가까운 줄로 (줄 하이라이트 중에는 끝 줄이 현재 위치라 그대로) */
function followScroll() {
  followRaf = 0;
  if (!linesOn() || drag || revealing || ranged()) return;
  const us = units();
  const i = hereIndex(us);
  if (i < 0) return;
  const { top, bottom } = viewport();
  const u = us[i];
  if (u.bottom > top + 2 && u.top < bottom - 2) return;
  setHere(us[edgeIndex(us, u.bottom <= top + 2)].a);
}

// ---- 줄 하이라이트 ------------------------------------------------------------------

/** 줄 하이라이트의 단위 차례 [lo, hi] */
function litIndexes(us) {
  const i = indexOfLine(us, anchor);
  const j = indexOfLine(us, focus);
  return i < 0 || j < 0 ? null : [Math.min(i, j), Math.max(i, j)];
}

function startRange(line) {
  active = true;
  mode = 'range';
  anchor = line;
  focus = line;
}

/** Shift+Enter (장이 없으면 툴바 버튼도): 현재 줄을 하이라이트 */
function highlightHere() {
  const us = units();
  const i = hereIndex(us);
  if (i < 0) return false;
  startRange(us[i].a);
  paint();
  return true;
}

/** F2: 현재 줄을 한 줄 편집 (D76) — 한 줄만 하이라이트했으면 그 줄. 여러 줄이면 어느 줄인지 몰라 알리기만 한다 */
export function editHere() {
  if (!linesOn()) return false;
  const us = units();
  const ix = ranged() ? litIndexes(us) : null;
  if (ix && ix[0] !== ix[1]) {
    toast(t('한 줄 편집은 한 줄만 고칩니다 — 하이라이트를 풀고 F2 를 누르세요'));
    return true;
  }
  if (!us.length) {   // 빈 문서 — 처음 줄을 연다 (D106)
    emit('line-end');
    return true;
  }
  const i = ix ? ix[0] : hereIndex(us);
  if (i < 0) return false;
  emit('line-edit', us[i]);
  return true;
}

/** Shift+Enter (D108): 고른 줄을, 없으면 현재 줄을 하이라이트한다 (나머지를 흐리게). 다시 누르면 끈다 */
function dimHere() {
  if (ranged() && !dimmed) {
    dimmed = true;
    paint();
    return true;
  }
  if (ranged()) {
    toggleSpotlight(false);
    return true;
  }
  dimmed = true;
  return highlightHere();
}

/** Shift+↑·↓: 끝 줄을 옮겨 넓히거나 줄인다 (처음 줄은 그대로). 하이라이트가 없으면 현재 줄부터, 장 하이라이트면 그 장의 처음~끝 줄부터 */
function extend(step) {
  const us = units();
  if (!us.length) return false;
  if (!ranged()) {
    const ch = spotlightOn() ? chapterIndexes(us) : null;
    dimmed = !!ch;
    if (ch) {
      active = true;
      mode = 'range';
      anchor = us[ch[0]].a;
      focus = us[ch[1]].a;
    } else {
      const i = hereIndex(us);
      if (i < 0) return false;
      startRange(us[i].a);
    }
  }
  const j = Math.max(0, Math.min(us.length - 1, indexOfLine(us, focus) + step));
  focus = us[j].a;
  paint();
  setHere(focus, { scroll: true });
  return true;
}

/** 하이라이트한 곳의 원문 줄 [a, b] — 줄 하이라이트는 고른 줄 그대로 (코드의 빈 줄도), 장은 끝의 빈 줄을 뺀다 */
function litLines() {
  if (!lit()) return null;
  if (mode === 'range') {
    const us = units();
    const ix = litIndexes(us);
    if (!ix) return null;
    const part = us.slice(ix[0], ix[1] + 1);
    return [part.reduce((m, u) => Math.min(m, u.a), Infinity), part.reduce((m, u) => Math.max(m, u.b), -Infinity)];
  }
  const r = chapterLines();
  if (!r) return null;
  const src = srcLines();
  let [a, b] = r;
  if (src.length) b = Math.min(b, src.length);
  while (b > a && !src[b - 1]?.trim()) b -= 1;
  return [a, b];
}

/** 하이라이트한 곳 {path, range, ref(@경로 a~b행), text(원문), code(코드 화면인지), chapter(장 하이라이트인지)} — 없으면 null */
function litInfo() {
  const range = litLines();
  if (!range) return null;
  const path = pathOf();
  return {
    path, range, ref: lineRef(path, range, isCodeView() ? view().dataset.sheet || '' : ''), text: srcLines().slice(range[0] - 1, range[1]).join('\n'), code: isCodeView(), chapter: mode === 'chapter',
  };
}

const noLit = () => toast(t('하이라이트한 곳이 없습니다 — Shift+Enter 로 현재 줄을, Shift+↑·↓ 로 여러 줄을 하이라이트합니다'));

/** 메뉴 'Claude 로 보내기': 맨 앞 터미널(보통 1번 — Claude Code)에 '@경로 a~b행 ' (Enter 없이, terminal.js 의 pasteToTerminal), 초점도 터미널로 */
export function sendLit() {
  const info = litInfo();
  if (!info) noLit();
  else emit('term-paste', `${info.ref} `);
}

/**
 * Shift+→: 하이라이트한 곳(없으면 현재 줄)의 위치를 맨 앞 터미널에 넣고 초점도 그 터미널로 (D97).
 * stay (Ctrl+Shift+→): 초점은 문서에 둔다 — 여러 곳을 이어서 넣게 (D79)
 */
function sendHere(stay = false) {
  const info = litInfo();
  const us = info ? [] : units();
  const i = info ? -1 : hereIndex(us);
  if (!info && i < 0) return false;
  const ref = info ? info.ref : lineRef(pathOf(), [us[i].a, us[i].b], isCodeView() ? view().dataset.sheet || '' : '');
  emit(stay ? 'term-paste-stay' : 'term-paste', `${ref} `);
  return true;
}

/** 현재 줄의 정보 — 파일을 바꾸지 않는 키는 고른 줄이 없으면 현재 줄에 한다 (D108) */
function hereInfo() {
  const us = units();
  const i = hereIndex(us);
  if (i < 0) return null;
  const range = [us[i].a, us[i].b];
  return { path: pathOf(), range, ref: lineRef(pathOf(), range, isCodeView() ? view().dataset.sheet || '' : ''), text: srcLines().slice(range[0] - 1, range[1]).join('\n') };
}

/** Shift+← · 메뉴 'Claude용 위치 복사' */
export async function copyLitRef() {
  const info = litInfo() ?? hereInfo();
  if (!info) noLit();
  else toast(await copyText(info.ref) ? t('복사했습니다: {what}', { what: info.ref }) : t('복사하지 못했습니다'));
}

/** Ctrl+C(고른 글이 없을 때) · 메뉴 '원문 복사' */
export async function copyLitSource() {
  const info = litInfo() ?? hereInfo();
  if (!info) noLit();
  else toast(await copyText(info.text) ? t('복사했습니다: {what}', { what: `${info.path} ${rangeText(info.range)}` }) : t('복사하지 못했습니다'));
}

// ---- 그리기 ------------------------------------------------------------------

/**
 * 하이라이트한 곳의 세로 범위 {top, bottom, padTop, padBottom} (스크롤 상자 안 좌표, 여유 없이). pad: 덮개를 띄울 여유 —
 * 줄 하이라이트는 이웃 줄과의 틈의 반까지(코드·표의 행처럼 붙은 줄이면 1px — 이웃 줄을 가리지 않게)
 */
function litBox() {
  if (mode === 'range') {
    const us = units();
    const ix = litIndexes(us);
    if (!ix) return null;
    const part = us.slice(ix[0], ix[1] + 1);
    const top = part.reduce((m, u) => Math.min(m, u.top), Infinity);
    const bottom = part.reduce((m, u) => Math.max(m, u.bottom), -Infinity);
    const gap = (d) => Math.max(1, Math.min(PAD, d / 2));
    return {
      top, bottom, padTop: ix[0] > 0 ? gap(top - us[ix[0] - 1].bottom) : PAD, padBottom: ix[1] < us.length - 1 ? gap(us[ix[1] + 1].top - bottom) : PAD,
    };
  }
  const shown = (chapters[current] || []).filter((el) => el.getClientRects().length);
  if (!shown.length) return null;
  const base = baseOf(view());
  return {
    top: shown[0].getBoundingClientRect().top - base, bottom: Math.max(...shown.map((el) => el.getBoundingClientRect().bottom)) - base, padTop: PAD, padBottom: PAD,
  };
}

/** 화면 좌표 y 가 하이라이트한 곳 안인지. target: 누른 요소 — 슬라이드의 칸은 나란해서 같은 높이의 다른 칸은 밖이다 */
function insideLit(y, target = null) {
  const r = lit() && painted === view() ? litBox() : null;
  if (!r) return false;
  const base = baseOf(view());
  if (y < r.top + base - r.padTop || y > r.bottom + base + r.padBottom) return false;
  const cell = target?.closest?.('.lec-cell');
  const own = cell && ranged() ? blockOfLine(view(), litLines()[0])?.closest?.('.lec-cell') : null;
  return !own || cell === own;
}

/** 칸의 스크롤 상자에 겹친 덮개 (make: 없으면 만든다) */
function overlay(root, make) {
  const sc = root?.parentElement;
  if (!sc?.classList.contains('lec-scroll')) return null;
  let box = sc.querySelector(':scope > .lec-spot');
  if (!box && make) {
    box = document.createElement('div');
    box.className = 'lec-spot';
    box.setAttribute('aria-hidden', 'true');
    setHtml(box, html`<div class="spot-band"></div><div class="spot-shade spot-above"></div><div class="spot-shade spot-below"></div><div class="spot-bar"></div>`);
    sc.append(box);
  }
  return box;
}

/** 덮개를 하이라이트한 곳에 맞춘다: 그 위·아래(문서 끝까지)를 덮고, 본문 왼쪽 여백에 막대 */
function place() {
  const root = painted;
  const box = overlay(root, false);
  if (!box) return;
  const r = lit() && root === view() ? litBox() : null;
  box.hidden = !r;
  if (!r) return;
  box.classList.toggle('editing', lineEditing());
  box.classList.toggle('pick', ranged() && !dimmed);   // 고른 줄: 흐리지 않고 그 줄들에만 옅은 띠 (D108)
  const top = Math.max(0, r.top - r.padTop);
  const bottom = r.bottom + r.padBottom;
  const end = Math.max(bottom, root.offsetTop + root.offsetHeight);
  box.style.setProperty('--spot-top', `${Math.round(top)}px`);
  box.style.setProperty('--spot-bottom', `${Math.round(bottom)}px`);
  box.style.setProperty('--spot-end', `${Math.round(end)}px`);
  box.style.setProperty('--spot-bar', `${Math.round(Math.max(4, textLeft(root) - 22))}px`);
}

function paint() {
  const root = view();
  if (painted && painted !== root) {
    painted.classList.remove('lec-spotlight');
    for (const el of painted.querySelectorAll(':scope > .lec-lit')) el.classList.remove('lec-lit');
    overlay(painted, false)?.remove();
  }
  painted = root;
  const on = lit();
  root.classList.toggle('lec-spotlight', on);
  for (const el of root.querySelectorAll(':scope > .lec-lit')) el.classList.remove('lec-lit');
  if (on && mode === 'chapter' && chapters[current]) for (const el of chapters[current]) el.classList.add('lec-lit');
  if (on) overlay(root, true);
  place();
  drawHere();
  resizer ||= new ResizeObserver(() => {
    gen += 1;
    requestAnimationFrame(() => {
      place();
      drawHere();
    });
  });
  if (observed !== root) {
    resizer.disconnect();
    resizer.observe(root);
    observed = root;
  }
  updateButton();
  updateStatus();
}

function updateButton() {
  const btn = $('#lec-btn-spot');
  const hasChapters = isMdDoc() && chapters.length > 0;
  const usable = hasChapters || linesOn();
  btn.classList.toggle('on', lit());
  btn.disabled = !usable && !lit();
  const keys = t('Shift+누르기·끌기, Shift+Enter: 줄 하이라이트 — Shift+↑·↓ 로 넓히고 줄이기, Shift+→ Claude 로 보내기');
  if (lit()) btn.title = `${t('하이라이트 끄기')} (Esc)\n${keys}`;
  else if (hasChapters) btn.title = `${t('장 하이라이트 켜기')} — ${t('켜면 ↑·↓·PageUp·PageDown 으로 앞뒤 장 (Esc 로 끄기)')}\n${keys}`;
  else if (usable) btn.title = `${t('현재 줄 하이라이트')} (Shift+Enter)\n${keys}`;
  else btn.title = t('하이라이트: Markdown 문서와 코드 화면에서 쓸 수 있습니다');
  // 옆의 ∧∨: 장 하이라이트 중에만, 첫 장·마지막 장에서는 그쪽으로 못 간다
  const chapterOn = spotlightOn();
  $('#lec-spot-prev').disabled = !chapterOn || current <= 0;
  $('#lec-spot-next').disabled = !chapterOn || current >= chapters.length - 1;
}

/** 상태줄: 하이라이트한 줄 범위 (한 줄 편집 중이면 그 줄과 키 — lineedit.js, D76) */
function updateStatus() {
  const el = $('#lec-st-lit');
  const edit = S.pane?.lineEdit;
  if (edit && painted === view()) {
    el.hidden = false;
    el.textContent = `${t('한 줄 편집')} ${rangeText([edit.line, edit.line])}`;
    el.title = t('Enter 저장 · Esc 그만두기 · ↑·↓ 저장하고 위·아래 줄 · Shift+→(글 끝) 저장하고 Claude 로 보내기');
    return;
  }
  const r = lit() && painted === view() ? litLines() : null;
  el.hidden = !r;
  if (!r) return;
  const pick = ranged() && !dimmed;
  el.textContent = `${pick ? t('고른 줄') : t('하이라이트')} ${rangeText(r)} · ${t('{n}줄', { n: r[1] - r[0] + 1 })}`;
  el.title = pick ? t('Delete 지우기 · Alt+↑·↓ 옮기기 · Tab 레벨 · Shift+→ Claude 로 보내기 · Shift+← 위치 복사 · Ctrl+C 원문 복사 · Shift+Enter 하이라이트 · Esc 풀기')
    : t('Shift+→ Claude 로 보내기 · Shift+← 위치 복사 · Ctrl+C 원문 복사 · Esc 해제');
}

// ---- 밖에서 부르는 것 ------------------------------------------------------------

/** 장 하이라이트 중인지 (↑·↓·PageUp·PageDown 이 앞뒤 장) */
export const spotlightOn = () => active && mode === 'chapter' && chapters.length > 0;

// 한 줄 편집(lineedit.js, D76)이 쓰는 것: 지금 화면의 줄 단위·원문 줄, 그 줄을 하이라이트, 상태줄 다시 쓰기
export const currentUnits = () => units();
/** 줄 단위가 달라졌다 — 다시 그리지 않고 화면의 요소를 바꿨을 때 (구조 보기, slidetools.js) */
export function forgetUnits() {
  cache = null;
}
export const sourceLines = () => srcLines();
/** 줄 하이라이트의 원문 줄 [a, b] (lineedit.js 의 줄 지우기·옮기기) — 줄 하이라이트가 아니면 null */
export const litSpan = () => (ranged() ? litLines() : null);
/** 옮긴 줄들로 줄 하이라이트를 옮긴다 (lineedit.js) */
export function setLitSpan(a, b) {
  if (!ranged()) return;
  anchor = a;
  focus = b;
  paint();
  setHere(b, { scroll: true });
}
/** 한 줄 편집을 시작·끝낼 때 (lineedit.js): 덮개의 회색과 상태줄을 맞춘다 */
export function showLineEdit() {
  place();
  updateStatus();
}

/** 한 줄 편집이 옮겨 간 원문 줄 line 을 현재 위치로 (보이게) — 줄 하이라이트 중이면 하이라이트도 그 줄로. F2·두 번 누르기로 연 편집은 하이라이트를 만들지 않는다 */
export function followLine(line) {
  if (!linesOn()) return;
  if (ranged()) {
    startRange(line);
    paint();
  }
  setHere(line, { scroll: true });
}

/** 다음 'reveal' 의 현재 위치를 블록의 첫 줄이 아니라 원문 줄 line 으로 (뒤로·앞으로 — nav.js 의 showPlace) */
export const revealAt = (line) => { revealLine = line; };

/** 두 번 누른 곳(e)의 줄 단위 (lineedit.js) — 본문의 글이 아니거나 줄을 고르지 않는 곳이면 null */
export function unitAtPoint(e) {
  const root = view();
  if (!root?.contains(e.target) || e.target === root || !linesOn() || noPick(e.target)) return null;
  const us = units();
  const i = unitAt(us, e.clientY - baseOf(root), { x: e.clientX, y: e.clientY });
  return i < 0 ? null : us[i];
}

/** ↑·↓·PageUp·PageDown·∧∨: 앞(-1)·뒤(+1) 장으로 가서 그 장의 처음을 화면 위에 둔다 */
export function moveSpotlight(step) {
  if (!spotlightOn()) return false;
  select(Math.max(0, Math.min(chapters.length - 1, current + step)), { scroll: true });
  return true;
}

/** 툴바 버튼: 장 하이라이트를 켜고 끈다 — 장이 없는 문서·코드 화면이면 현재 줄을 하이라이트. 끄면 줄 하이라이트도 끈다 */
/** 하이라이트가 한 줄뿐인지 — 우클릭 메뉴의 '여기서 편집' (F2 와 같다) */
export function litOneLine() {
  if (!ranged()) return false;
  const ix = litIndexes(units());
  return !!ix && ix[0] === ix[1];
}

/** Alt+H: 장 하이라이트 켜고 끄기 — 툴바 버튼을 쓸 수 있을 때만 (D91) */
export function spotButton() {
  if ($('#lec-btn-spot').disabled) return false;
  toggleSpotlight();
  return true;
}

/** Shift+F10: 현재 줄의 화면 위치 {x, y} — 없으면 null */
export function herePoint() {
  const us = linesOn() ? units() : [];
  const i = hereIndex(us);
  if (i < 0) return null;
  const root = view();
  const box = us[i].el.closest?.('.lec-slide') && us[i].el.getBoundingClientRect();   // 슬라이드의 칸은 왼쪽 여백에서 멀다 — 그 줄 위를 눌러야 장 메뉴가 나온다
  if (box) return { x: box.left + Math.min(12, box.width / 2), y: box.top + Math.min(8, box.height / 2) };
  return { x: root.getBoundingClientRect().left + 40, y: baseOf(root) + us[i].top + 8 };
}

export function toggleSpotlight(want = !lit()) {
  if (!want) {
    active = false;
    mode = 'chapter';
    dimmed = false;
    paint();
    return;
  }
  dimmed = true;
  if (isMdDoc() && chapters.length) select(chapterHere());
  else if (linesOn()) highlightHere();
}

export function stopSpotlight() {
  if (!lit()) return false;
  toggleSpotlight(false);
  return true;
}

/**
 * 우클릭한 세로 위치(화면 좌표 y)가 하이라이트한 곳 안이면 그곳 {path, range, ref, text, code, chapter} (litInfo).
 * 우클릭 메뉴(docmenu.js)가 그 범위의 선택 상자를 띄운다
 */
export function litAt(y, target = null) {
  return linesOn() || isMdDoc() ? (insideLit(y, target) ? litInfo() : null) : null;
}

/** 본문 우클릭 메뉴(docmenu.js)의 항목: 우클릭한 곳의 장 하이라이트 / 하이라이트 해제. 쓸 수 없는 화면이면 빈 목록 */
export function spotlightItems(target) {
  if (!isMdDoc() && !isCodeView()) return [];
  const items = [];
  if (chapters.length) {
    const i = chapterOf(target);
    if (!spotlightOn() || (i >= 0 && i !== current)) {
      items.push({
        label: i >= 0 ? t('이 장 하이라이트') : t('장 하이라이트'),
        hint: 'Alt+H',
        tip: t('나머지는 흐리게 — ↑·↓·PageUp·PageDown 으로 앞뒤 장'),
        action: () => select(i >= 0 ? i : chapterHere()),
      });
    }
  }
  if (lit()) items.push({ label: t('하이라이트 해제'), hint: 'Esc', action: () => toggleSpotlight(false) });
  return items;
}

// ---- 키 ------------------------------------------------------------------------

// 하이라이트 키를 받는 곳: 문서 칸(본문·스크롤 상자)과 툴바·목차·상태줄의 버튼 (사이드바 목록·메뉴·대화상자는 자기 ↑·↓ 가 있다)
const KEY_PLACES = '#lec-panes, #lec-toolbar, #lec-toc, #lec-status';
const NOT_KEYS = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), #lec-doctabs, .sp-head, .lec-editor, #lec-findbar';
const OVERLAYS = '.overlay:not([hidden]), #lec-menu:not([hidden]), #lec-help:not([hidden]), #lec-gather:not([hidden]), #lec-present:not([hidden])';

function keyPlace(el) {
  if (document.querySelector(OVERLAYS)) return false;
  if (!el?.closest || el === document.body || el === document.documentElement) return true;   // 초점이 문서 전체에 (document·body)
  return !!el.closest(KEY_PLACES) && !el.closest(NOT_KEYS);
}

/** 팝업·메뉴·사용설명서 같은 것이 문서 화면을 덮고 있는지 (main.js 의 F6) */
export const overlayOpen = () => !!document.querySelector(OVERLAYS);

/** 하이라이트 키를 받을 곳인지 — 문서 칸·툴바·목차·상태줄 (main.js 의 Ctrl+Z 되돌리기도 — lineedit.js) */
export const docKeyTarget = (e) => !e.defaultPrevented && keyPlace(e.target);

/**
 * 문서·코드 화면의 현재 위치·하이라이트 키 (main.js 의 keydown 이 부른다). 다뤘으면 true — 부른 쪽이 기본 동작(스크롤 등)을 막는다.
 * ↑·↓ 현재 위치 (장 하이라이트 중에는 앞뒤 장 — PageUp·PageDown 도), Shift+Enter 현재 줄 하이라이트 (한 줄만 하이라이트했으면 한 줄 편집 — D76), F2 한 줄 편집,
 * Shift+↑·↓ 넓히기·줄이기, Shift+→ Claude 로 보내기, Shift+← 위치 복사, Ctrl+C 원문 복사 (하이라이트 중이고 고른 글이 없을 때)
 */
export function spotKey(e) {
  if (e.defaultPrevented || e.altKey || e.metaKey || e.isComposing || !keyPlace(e.target)) return false;
  const k = e.key;
  if (e.ctrlKey) {
    if (e.shiftKey && k === 'ArrowRight') return sendHere(true);
    if (view().classList.contains('lec-deck')) {   // 슬라이드 (D96): 구성 요소의 글자 크기, 장 더하기·복제
      if (e.shiftKey && (e.code === 'Period' || e.code === 'Comma')) {
        emit('text-size', { dir: e.code === 'Period' ? 1 : -1 });
        return true;
      }
      if (!e.shiftKey && (e.code === 'KeyM' || e.code === 'KeyD')) {
        emit('slide-op', { op: e.code === 'KeyM' ? 'add' : 'copy' });
        return true;
      }
    }
    if (!e.shiftKey && (e.code === 'KeyL' || k.toLowerCase() === 'l')) {   // 현재 줄 하이라이트, 거듭 누르면 아래로 넓힘 (D91)
      if (!linesOn()) return false;
      if (ranged()) return extend(1);
      dimmed = false;
      return highlightHere();
    }
    if (!e.shiftKey && (e.code === 'KeyX' || k.toLowerCase() === 'x') && ranged() && !getSelection()?.toString()) {   // 잘라내기 (lineedit.js, D83)
      emit('line-delete', { cut: true });
      return true;
    }
    if (e.shiftKey || (e.code !== 'KeyC' && k.toLowerCase() !== 'c') || (!lit() && !linesOn()) || getSelection()?.toString()) return false;
    copyLitSource();
    return true;
  }
  if (e.shiftKey) {
    if (!linesOn() && !lit()) return false;
    if (k === 'Enter') return dimHere();   // 하이라이트 켜고 끄기 (D91·D108 — 편집은 F2)
    if (k === 'ArrowUp' || k === 'ArrowDown') return extend(k === 'ArrowUp' ? -1 : 1);
    if (k === 'ArrowRight') return sendHere();
    if (k === 'ArrowLeft') copyLitRef();
    else return false;
    return true;
  }
  if (k === 'F2') return editHere();
  if (k === 'Delete' && ranged()) {   // 줄 지우기 (lineedit.js, D83)
    emit('line-delete', {});
    return true;
  }
  if (k !== 'ArrowUp' && k !== 'ArrowDown' && k !== 'PageUp' && k !== 'PageDown') return false;
  const step = k === 'ArrowUp' || k === 'PageUp' ? -1 : 1;
  if (spotlightOn()) return moveSpotlight(step);
  if (k.startsWith('Page') || !linesOn()) return false;   // PageUp·PageDown 은 보통 스크롤 (현재 위치가 따라온다)
  if (ranged()) toggleSpotlight(false);   // 편집기처럼 줄 하이라이트를 풀고 옮긴다
  return moveHere(step, e.repeat);
}

// ---- 누르기·Shift+끌기 -----------------------------------------------------------

/** 끄는 동안: 처음 줄부터 지금 줄까지 */
function dragTo() {
  const i = unitAt(drag.units, drag.y - baseOf(view()), { x: drag.x, y: drag.y });
  if (i < 0 || drag.units[i].a === focus) return;
  focus = drag.units[i].a;
  setHere(focus);
  place();
  updateStatus();
}

/** 칸 위·아래 끝 가까이에서 끌면 스크롤한다 (프레임마다) */
function autoScroll() {
  if (!drag) return;
  const sc = view().parentElement;
  const r = sc.getBoundingClientRect();
  const edge = 36;
  let step = 0;
  if (drag.y < r.top + edge) step = -Math.ceil((r.top + edge - drag.y) / 3);
  else if (drag.y > r.bottom - edge) step = Math.ceil((drag.y - (r.bottom - edge)) / 3);
  if (step) {
    sc.scrollTop += step;
    dragTo();
  }
  drag.raf = requestAnimationFrame(autoScroll);
}

function onDragMove(e) {
  drag.x = e.clientX;
  drag.y = e.clientY;
  dragTo();
}

function endDrag() {
  if (!drag) return;
  cancelAnimationFrame(drag.raf);
  drag = null;
  overlay(view(), false)?.classList.remove('dragging');
  document.removeEventListener('mousemove', onDragMove);
  document.removeEventListener('mouseup', endDrag);
  window.removeEventListener('blur', endDrag);
  swallowClick = true;   // 이어 오는 click 은 링크·제목 접기로 쓰지 않는다
  setTimeout(() => { swallowClick = false; });
  place();
  updateButton();
  updateStatus();
}

/**
 * 본문 누르기: 누른 줄이 현재 위치 (줄 하이라이트 중이면 끝 줄이 현재 위치이므로 하이라이트 밖 — 누르면 풀리는 흐린 곳 — 을 누를 때만).
 * Shift+누르기: 그 줄을 하이라이트하고 끌면 넓힌다 — 줄 하이라이트가 있으면 처음 줄은 두고 거기까지 (글 고르기·끌어 놓기 대신)
 */
function onMouseDown(e) {
  if (e.button !== 0 || e.ctrlKey || e.altKey || e.metaKey) return;
  const root = view();
  if (!root?.contains(e.target) || !linesOn() || noPick(e.target)) return;
  if (!e.shiftKey && ranged() && insideLit(e.clientY, e.target)) return;
  const us = units();
  const i = unitAt(us, e.clientY - baseOf(root), { x: e.clientX, y: e.clientY });
  if (i < 0) return;
  if (!e.shiftKey) {
    setHere(us[i].a);
    return;
  }
  e.preventDefault();
  getSelection()?.removeAllRanges();
  root.parentElement.focus({ preventScroll: true });   // 기본 동작을 막아 초점이 옮지 않는다 — 이어서 치는 키(Shift+↑·↓·Enter)가 이 칸으로 오게
  if (!ranged()) {
    anchor = us[i].a;
    dimmed = false;
  }
  active = true;
  mode = 'range';
  focus = us[i].a;
  drag = { units: us, x: e.clientX, y: e.clientY, raf: 0 };
  paint();
  setHere(focus);
  overlay(root, true).classList.add('dragging');   // 끄는 동안은 덮개가 바로 따라오게 (base.css 의 transition 을 끈다)
  document.addEventListener('mousemove', onDragMove);
  document.addEventListener('mouseup', endDrag);
  window.addEventListener('blur', endDrag);
  drag.raf = requestAnimationFrame(autoScroll);
}

export function initSpotlight() {
  $('#lec-btn-spot').addEventListener('click', () => toggleSpotlight());
  $('#lec-spot-prev').addEventListener('click', () => moveSpotlight(-1));
  $('#lec-spot-next').addEventListener('click', () => moveSpotlight(1));
  // 다시 그리면(자동 새로고침·스타일 변경) 같은 곳을 다시 강조한다 (장은 같은 제목, 줄 하이라이트는 같은 원문 줄). 다른 문서면 장은 화면 위쪽의 장부터, 줄 하이라이트는 푼다
  const rebuild = () => {
    gen += 1;
    const md = isMdDoc();
    const path = md || isCodeView() ? pathOf() : null;
    const keep = chapters[current]?.[0];
    const keepId = keep && levelOf(keep) ? keep.id : null;
    if (md) build();
    else chapters = [];
    // 줄 하이라이트는 같은 문서일 때만 — 문서가 줄어 그 줄이 없어졌으면 푼다
    if (ranged()) {
      const us = units();
      if (path !== shownPath || !hasLine(us, anchor) || !hasLine(us, focus)) {
        active = false;
        mode = 'chapter';
      }
    }
    if (active && mode === 'chapter' && chapters.length) {
      const same = path === shownPath && keepId ? chapters.findIndex((blocks) => blocks[0].id === keepId) : -1;
      current = same >= 0 ? same : (path === shownPath ? Math.min(current, chapters.length - 1) : chapterAtTop());
    }
    shownPath = path;
    paint();
  };
  on('rendered', (pane) => { if (pane === S.pane) rebuild(); });
  on('pane', () => {
    endDrag();
    active = false;
    mode = 'chapter';
    rebuild();
  });
  // 목차·찾기·앵커·바뀐 곳·검색으로 가면: 장 하이라이트 중이면 그 장을, 현재 위치는 그 줄로 (줄 하이라이트 중이면 끝 줄이 현재 위치라 그대로)
  on('reveal', (el) => {
    const line = revealLine;
    revealLine = null;
    if (spotlightOn()) {
      const i = chapterOf(el);
      if (i >= 0 && i !== current) select(i);
    }
    if (!linesOn() || ranged() || !view().contains(el)) return;
    revealing += 1;
    requestAnimationFrame(() => requestAnimationFrame(() => {   // 스크롤한 뒤에
      revealing -= 1;
      if (!el.isConnected || !view().contains(el)) return;
      const us = units();
      const r = el.getBoundingClientRect();
      const i = unitAt(us, r.top - baseOf(view()) + Math.min(r.height / 2, 8));
      if (i >= 0) setHere(line ?? us[i].a);
    }));
  });
  // 누르기·Shift+끌기 — 거품 단계에서 받는다: 모두 펼치기(spread.js)가 잡기 단계에서 누른 칸을 먼저 고른다 (D73)
  $('#lec-panes').addEventListener('mousedown', onMouseDown);
  window.addEventListener('click', (e) => {
    if (!swallowClick) return;
    swallowClick = false;
    e.preventDefault();
    e.stopPropagation();
  }, true);
  // 흐린 곳을 누르면: 장 하이라이트는 그 장으로, 줄 하이라이트는 끈다 (그 누름은 링크·접기로 쓰지 않는다)
  $('#lec-panes').addEventListener('click', (e) => {
    if (!lit() || !view().contains(e.target) || e.shiftKey || noPick(e.target) || window.getSelection()?.toString()) return;
    if (mode === 'range') {
      if (insideLit(e.clientY, e.target)) return;
      if (dimmed) {   // 고른 줄은 흐린 곳이 없다 — 풀기만 하고 그 누르기는 그대로 쓴다 (D108)
        e.preventDefault();
        e.stopPropagation();
      }
      toggleSpotlight(false);
      return;
    }
    const i = chapterOf(e.target);
    if (i < 0 || i === current) return;
    e.preventDefault();
    e.stopPropagation();
    select(i);
  }, true);
  // 스크롤하면 현재 위치가 화면 안으로 따라온다. 스크롤은 거품처럼 올라오지 않으므로 잡기 단계에서 (선택된 칸만)
  document.addEventListener('scroll', (e) => {
    if (e.target === S.pane?.scroller && !followRaf) followRaf = requestAnimationFrame(followScroll);
  }, { capture: true, passive: true });
  window.addEventListener('resize', () => requestAnimationFrame(() => {
    place();
    drawHere();
  }));
}
