// 하이라이트 (툴바 '하이라이트' 버튼·Alt+끌기): 문서에서 하이라이트한 곳만 지금 모양 그대로, 그 밖은 회색 바탕에 흐린 글자 (D74).
//
// - 장 하이라이트: 장은 문서의 맨 위 수준 절이다. H1 이 하나뿐이면(문서 제목) 그 아래 수준(보통 H2) 절, 아니면 H1 절. 첫 장 앞의 제목·머리말도 한 장이다.
//   장의 범위는 그 장 제목을 눌러 접을 때 숨는 범위와 같다 (다음 같은 수준 이상의 제목 앞까지, 각주 제외 — fold.js 와 같은 규칙).
//   각주(.footnotes)는 어느 장에도 들지 않는다. 켜져 있으면 ↑·↓·PageUp·PageDown·버튼 옆 ∧∨ 로 앞뒤 장(키는 main.js 가 부른다),
//   흐린 곳을 누르면 그 장, Esc·버튼으로 끈다. 목차·찾기·앵커·전체 검색·바뀐 곳으로 가면 그곳의 장으로 옮긴다 (fold.js 의 unfoldTo 가 보내는 'reveal').
// - Alt+끌기 (D74): Alt 를 누른 채 끌면(누르기만 해도) 걸친 블록들 — 문단·목록 항목·제목·표의 행·다이어그램, 코드 블록은 그 줄들 — 을
//   하이라이트한다. 블록은 원문 줄 범위(data-lines)가 있는 가장 안쪽 요소이고, 화면의 세로 위치로만 고른다 (여백에서 끌어도 된다).
//   범위는 원문 줄 [a, b] 로 남겨 다시 그려도 같은 곳이다. 끄는 동안 칸 위·아래 끝에 가면 스크롤한다. 흐린 곳을 누르거나 Esc·버튼으로 끈다.
//   ↑·↓ 는 보통 스크롤 (앞뒤 장은 장 하이라이트에서만).
// - 우클릭 메뉴(docmenu.js)는 하이라이트한 곳 안이면 맨 위에 그 범위의 Claude용 위치(▣ 터미널)·원문 복사·담기·보내기 — litAt.
// - 그리기: 칸의 스크롤 상자에 덮개(.lec-spot — 하이라이트 위·아래를 덮는 반투명 회색 둘과 왼쪽 강조 막대)를 겹쳐 둔다 (base.css).
//   문서 DOM 은 그대로이고 장의 블록에 lec-lit 만 붙인다. 위치는 블록의 화면 위치로 재므로, 문서의 크기가 바뀌면(그림을 불러옴·접기·칸 폭·
//   글자 크기 — ResizeObserver) 다시 잰다. 덮개는 누르기를 막지 않는다 (pointer-events: none).
// - md 문서만. html 문서(iframe)는 구조가 문서마다 달라 장을 나눌 수 없다. 슬라이드로 보는 발표 문서(D59)는 슬라이드 하나가 한 장 (Alt+끌기는 안 됨).
// - 선택된 탭의 칸(#lec-view)의 문서에 한다. 다른 탭을 고르면 꺼진다.

import { S, on } from './store.js';
import { $ } from './util.js';
import { t } from './i18n.js';

let active = false;
let mode = 'chapter';   // 'chapter' — 장 하이라이트, 'range' — Alt+끌기
let range = null;       // Alt+끌기로 고른 원문 줄 [a, b] (1부터, 끝 포함)
let chapters = [];      // [[블록, …], …] — 블록은 #lec-view 의 자식
let current = 0;
let shownPath = null;   // 장을 나눈 문서
let painted = null;     // 마지막으로 칠한 화면 — 다른 탭을 고르면 거기서 지운다
let drag = null;        // 끄는 중 {units, from, x, y, raf}
let swallowClick = false;   // 끌기를 마친 누르기 (링크·접기로 쓰지 않는다)
let resizer = null;

const PAD = 10;   // 하이라이트 띠의 위·아래 여유 (px)
const view = () => $('#lec-view');
// 'rendered' 때는 S.view 가 아직 앞 화면이므로 화면(DOM)으로 본다. doc.js 가 그린 md 문서에 data-doc-path 를 단다
const isMdDoc = () => view().classList.contains('md-body') && !!view().dataset.docPath && !view().querySelector('.doc-missing');
const levelOf = (el) => (/^H([1-6])$/.exec(el.tagName) ? Number(el.tagName[1]) : 0);
const lit = () => active && (mode === 'range' ? !!range : chapters.length > 0);

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
  if (view().classList.contains('lec-deck')) {   // 발표 문서: 슬라이드마다 한 장 (slides.js)
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

// ---- Alt+끌기의 블록 (원문 줄) -------------------------------------------------

/** 펜스 코드 블록의 <code> (줄마다 고른다) — Mermaid·차트는 블록 통째 */
const isCodeLines = (el) => el.tagName === 'CODE' && el.parentElement?.tagName === 'PRE';

/** 요소의 원문 줄 [시작, 끝]. 코드는 펜스(```) 줄을 뺀 내용 줄. 끝의 빈 줄은 뺀다 (목록 항목의 범위에 붙는 빈 줄) */
function spanOf(el) {
  const m = /^(\d+)-(\d+)$/.exec(el.dataset.lines || '');
  if (!m) return null;
  let [a, b] = [+m[1], +m[2]];
  if (isCodeLines(el)) return [a + 1, Math.max(a + 1, b - 1)];
  const src = S.pane?.source?.lines || [];
  while (b > a && !src[b - 1]?.trim()) b -= 1;
  return [a, b];
}

/** 코드 블록 안 k 번째(0부터) 줄의 세로 위치 {top, bottom, k} (box 와 같은 좌표) — 줄바꿈하지 않으므로(white-space: pre) 줄 높이가 같다.
 * at: k 대신 세로 위치로 고른다 */
function codeLine(el, box, k, at = null) {
  const n = Math.max(1, el.textContent.replace(/\n$/, '').split('\n').length);
  const h = (box.bottom - box.top) / n;
  const i = Math.min(Math.max(at == null ? k : Math.floor((at - box.top) / h), 0), n - 1);
  return { top: box.top + i * h, bottom: box.top + (i + 1) * h, k: i };
}

/** 원문 줄이 있는 블록들 (보이는 것만) — 스크롤 상자 안 좌표 {el, span, top, bottom} */
function collectUnits(root) {
  const sc = root.parentElement;
  const base = sc.getBoundingClientRect().top - sc.scrollTop;
  const units = [];
  for (const el of root.querySelectorAll('[data-lines]')) {
    if (el.closest('.front-matter') || !el.getClientRects().length) continue;
    const span = spanOf(el);
    if (!span) continue;
    const r = el.getBoundingClientRect();
    units.push({ el, span, top: r.top - base, bottom: r.bottom - base });
  }
  return units;
}

/** 세로 위치 y(스크롤 상자 안 좌표)의 블록 {lines, top, bottom}: y 를 품은 것 가운데 가장 낮은(안쪽) 것, 없으면(블록 사이 여백) 가장 가까운 것 */
function unitAtY(units, y) {
  let best = null;
  let near = null;
  for (const u of units) {
    const h = u.bottom - u.top;
    if (y >= u.top && y <= u.bottom) {
      if (!best || h < best.bottom - best.top) best = u;
    } else {
      const d = y < u.top ? u.top - y : y - u.bottom;
      if (!near || d < near.d || (d === near.d && h < near.u.bottom - near.u.top)) near = { u, d };
    }
  }
  const u = best || near?.u;
  if (!u) return null;
  if (isCodeLines(u.el)) {
    const line = codeLine(u.el, u, 0, y);
    const n = u.span[0] + line.k;
    return { lines: [n, n], top: line.top, bottom: line.bottom };
  }
  return { lines: u.span, top: u.top, bottom: u.bottom };
}

/** 원문 줄 n 을 보여 주는 블록의 화면 위치 {top, bottom} (화면 좌표) — 그 줄을 품은 가장 낮은(안쪽) 블록, 코드면 그 줄 */
function lineBox(n) {
  let best = null;
  for (const el of view().querySelectorAll('[data-lines]')) {
    const span = spanOf(el);
    if (!span || n < span[0] || n > span[1] || el.closest('.front-matter') || !el.getClientRects().length) continue;
    const r = el.getBoundingClientRect();
    if (!best || r.height < best.r.height) best = { el, r, span };
  }
  if (!best) return null;
  if (isCodeLines(best.el)) return codeLine(best.el, best.r, n - best.span[0]);
  return { top: best.r.top, bottom: best.r.bottom };
}

// ---- 그리기 ------------------------------------------------------------------

/** 하이라이트한 곳의 화면 위치 {top, bottom} (화면 좌표, 여유 없이) */
function litRect() {
  if (mode === 'range') {
    const a = range && lineBox(range[0]);
    const b = range && lineBox(range[1]);
    return a && b ? { top: Math.min(a.top, b.top), bottom: Math.max(a.bottom, b.bottom) } : null;
  }
  const shown = (chapters[current] || []).filter((el) => el.getClientRects().length);
  if (!shown.length) return null;
  return { top: shown[0].getBoundingClientRect().top, bottom: Math.max(...shown.map((el) => el.getBoundingClientRect().bottom)) };
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
    box.innerHTML = '<div class="spot-shade spot-above"></div><div class="spot-shade spot-below"></div><div class="spot-bar"></div>';
    sc.append(box);
  }
  return box;
}

/** 덮개를 하이라이트한 곳에 맞춘다: 그 위·아래(문서 끝까지)를 덮고, 본문 왼쪽 여백에 막대 */
function place() {
  const root = painted;
  const box = overlay(root, false);
  if (!box) return;
  const r = lit() && root === view() ? litRect() : null;
  box.hidden = !r;
  if (!r) return;
  const sc = root.parentElement;
  const sr = sc.getBoundingClientRect();
  const base = sr.top - sc.scrollTop;
  const top = Math.max(0, r.top - base - PAD);
  const bottom = r.bottom - base + PAD;
  const end = Math.max(bottom, root.offsetTop + root.offsetHeight);
  const left = root.getBoundingClientRect().left - sr.left + parseFloat(getComputedStyle(root).paddingLeft || '0') - 22;
  box.style.setProperty('--spot-top', `${Math.round(top)}px`);
  box.style.setProperty('--spot-bottom', `${Math.round(bottom)}px`);
  box.style.setProperty('--spot-end', `${Math.round(end)}px`);
  box.style.setProperty('--spot-bar', `${Math.round(Math.max(4, left))}px`);
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
  resizer ||= new ResizeObserver(() => requestAnimationFrame(place));
  resizer.disconnect();
  if (on) resizer.observe(root);
  updateButton();
}

function updateButton() {
  const btn = $('#lec-btn-spot');
  const usable = isMdDoc() && chapters.length > 0;
  btn.classList.toggle('on', lit());
  btn.disabled = !usable && !lit();
  btn.title = usable || lit()
    ? `${lit() ? t('하이라이트 끄기') : t('장 하이라이트 켜기')} — ${t('켜면 ↑·↓·PageUp·PageDown 으로 앞뒤 장 (Esc 로 끄기)')}\n${t('Alt+끌기: 끈 곳의 블록들만 하이라이트')}`
    : `${t('장 하이라이트: 제목으로 나뉜 Markdown 문서에서 쓸 수 있습니다')}\n${t('Alt+끌기: 끈 곳의 블록들만 하이라이트')}`;
  // 옆의 ∧∨: 장 하이라이트 중에만, 첫 장·마지막 장에서는 그쪽으로 못 간다
  const chapterOn = spotlightOn();
  $('#lec-spot-prev').disabled = !chapterOn || current <= 0;
  $('#lec-spot-next').disabled = !chapterOn || current >= chapters.length - 1;
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
  mode = 'chapter';
  range = null;
  current = i;
  paint();
  if (scroll) {
    const first = chapters[i].find((el) => el.getClientRects().length) || chapters[i][0];
    const content = $('#lec-content');
    content.scrollTop += first.getBoundingClientRect().top - content.getBoundingClientRect().top - 18;
  }
}

/** 장 하이라이트 중인지 (↑·↓·PageUp·PageDown 이 앞뒤 장 — main.js) */
export const spotlightOn = () => active && mode === 'chapter' && chapters.length > 0;

/** ↑·↓·PageUp·PageDown: 앞(-1)·뒤(+1) 장으로 가서 그 장의 처음을 화면 위에 둔다 */
export function moveSpotlight(step) {
  if (!spotlightOn()) return false;
  select(Math.max(0, Math.min(chapters.length - 1, current + step)), { scroll: true });
  return true;
}

/** 툴바 버튼: 장 하이라이트를 켜고 끈다 (Alt+끌기로 하이라이트한 것도 끈다) */
export function toggleSpotlight(want = !lit()) {
  if (want && !(isMdDoc() && chapters.length)) return;
  active = want;
  mode = 'chapter';
  range = null;
  if (active) current = chapterAtTop();
  paint();
}

export function stopSpotlight() {
  if (!lit()) return false;
  toggleSpotlight(false);
  return true;
}

/**
 * 우클릭한 세로 위치(화면 좌표 y)가 하이라이트한 곳 안이면 그 범위 — 장이면 {blocks}(그 장의 블록), Alt+끌기면 {lines: [a, b]}.
 * 우클릭 메뉴(docmenu.js)가 맨 위에 그 범위의 Claude용 위치·원문 복사·담기를 둔다
 */
export function litAt(y) {
  if (!lit() || painted !== view() || !isMdDoc()) return null;
  const r = litRect();
  if (!r || y < r.top - PAD || y > r.bottom + PAD) return null;
  return mode === 'range' ? { lines: [...range] } : { blocks: chapters[current] };
}

/** 본문 우클릭 메뉴(docmenu.js)의 항목: 우클릭한 곳의 장 하이라이트 / 하이라이트 해제. 쓸 수 없는 문서면 빈 목록 */
export function spotlightItems(target) {
  if (!isMdDoc()) return [];
  const items = [];
  if (chapters.length) {
    const i = chapterOf(target);
    if (!spotlightOn() || (i >= 0 && i !== current)) {
      items.push({
        label: i >= 0 ? t('이 장 하이라이트') : t('장 하이라이트'),
        hint: t('나머지는 흐리게 — ↑·↓·PageUp·PageDown 으로 앞뒤 장'),
        action: () => {
          active = true;
          select(i >= 0 ? i : chapterAtTop());
        },
      });
    }
  }
  if (lit()) items.push({ label: t('하이라이트 해제'), hint: 'Esc', action: () => toggleSpotlight(false) });
  return items;
}

// ---- Alt+끌기 ------------------------------------------------------------------

/** 끄는 동안: 누른 블록부터 지금 블록까지 (원문 줄로 합친다) */
function dragTo() {
  const root = view();
  const sc = root.parentElement;
  const y = drag.y - sc.getBoundingClientRect().top + sc.scrollTop;
  const u = unitAtY(drag.units, y);
  if (!u) return;
  const next = [Math.min(drag.from.lines[0], u.lines[0]), Math.max(drag.from.lines[1], u.lines[1])];
  if (range && next[0] === range[0] && next[1] === range[1]) return;
  range = next;
  place();
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
}

/** Alt+누르기: 그 블록부터 하이라이트를 시작한다 (글 고르기·끌어 놓기 대신) */
function startDrag(e) {
  if (!e.altKey || e.button !== 0 || e.ctrlKey || e.shiftKey || e.metaKey) return;
  const root = view();
  if (!root?.contains(e.target) || !isMdDoc() || root.classList.contains('lec-deck') || !S.pane?.source) return;
  const units = collectUnits(root);
  const sc = root.parentElement;
  const from = unitAtY(units, e.clientY - sc.getBoundingClientRect().top + sc.scrollTop);
  if (!from) return;
  e.preventDefault();
  getSelection()?.removeAllRanges();
  drag = { units, from, x: e.clientX, y: e.clientY, raf: 0 };
  active = true;
  mode = 'range';
  range = [...from.lines];
  paint();
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
  // 다시 그리면(자동 새로고침·스타일 변경) 같은 곳을 다시 강조한다 (장은 같은 제목, Alt+끌기는 같은 원문 줄). 다른 문서면 장은 화면 위쪽의 장부터, 끈 범위는 지운다
  const rebuild = () => {
    const path = isMdDoc() ? view().dataset.docPath : null;
    const keep = chapters[current]?.[0];
    const keepId = keep && levelOf(keep) ? keep.id : null;
    if (path) build();
    else chapters = [];
    // 끈 범위는 같은 문서일 때만 — 문서가 줄어 그 줄이 없어졌으면 지운다
    if (mode === 'range' && (path !== shownPath || !range || !lineBox(range[0]) || !lineBox(range[1]))) {
      active = false;
      mode = 'chapter';
      range = null;
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
    range = null;
    rebuild();
  });
  // 목차·찾기·앵커·바뀐 곳으로 가면 그 장을 강조한다 (장 하이라이트 중일 때)
  on('reveal', (el) => {
    if (!spotlightOn()) return;
    const i = chapterOf(el);
    if (i >= 0 && i !== current) select(i);
  });
  // Alt+끌기 — 거품 단계에서 받는다: 모두 펼치기(spread.js)가 잡기 단계에서 누른 칸을 먼저 고른다 (D73)
  $('#lec-panes').addEventListener('mousedown', startDrag);
  window.addEventListener('click', (e) => {
    if (!swallowClick) return;
    swallowClick = false;
    e.preventDefault();
    e.stopPropagation();
  }, true);
  // 흐린 곳을 누르면: 장 하이라이트는 그 장으로, Alt+끌기 하이라이트는 끈다 (그 누름은 링크·접기로 쓰지 않는다)
  $('#lec-panes').addEventListener('click', (e) => {
    if (!lit() || !view().contains(e.target) || e.altKey || window.getSelection()?.toString()) return;
    if (mode === 'range') {
      if (litAt(e.clientY)) return;
      e.preventDefault();
      e.stopPropagation();
      toggleSpotlight(false);
      return;
    }
    const i = chapterOf(e.target);
    if (i < 0 || i === current) return;
    e.preventDefault();
    e.stopPropagation();
    select(i);
  }, true);
  window.addEventListener('resize', () => requestAnimationFrame(place));
}
