// 창 나누기: 문서 화면을 가로로 최대 3칸까지 나눠 본다 (사용자 요청). 칸은 같은 폭이고, 하나면 전체 폭이다.
//
// - 칸(pane)마다 화면·스크롤 상자·뒤로/앞으로 기록·렌더링 순번이 따로다. 그리기는 nav.js 가 칸을 정해 doc.js·htmldoc.js·overview.js 에 넘긴다.
// - 선택된 칸(S.pane) 하나를 목차·찾기·장 하이라이트·상태줄·바뀐 곳 버튼·툴바(뒤로/앞으로)·트리 표시·창 제목이 따른다.
//   칸 안을 누르면(우클릭·html 문서 안 포함) 그 칸이 선택된다. 칸이 둘 이상이면 칸마다 머리줄(제목·닫기)이 보이고 선택된 칸에 색 띠가 붙는다.
// - 선택된 칸의 스크롤 상자와 본문에 #lec-content·#lec-view id 를 옮겨 단다. 선택된 칸만 다루는 코드(찾기·우클릭 메뉴 등)는
//   그 id 로 찾고, 선택되지 않은 칸도 그리는 코드는 칸 객체를 쓴다. 찾기 막대(#lec-findbar)도 선택된 칸으로 옮긴다.
// - 새 칸은 선택된 칸 바로 오른쪽에 생긴다 (Ctrl+클릭, 우클릭 '오른쪽 창에 열기' → nav.js 의 openBeside).

import { S, emit, on } from './store.js';
import { $, basename } from './util.js';

export const MAX_PANES = 3;

const PANE_HTML = `<div class="pane-head"><span class="pane-title"></span>
  <button type="button" class="icon-btn small pane-close" title="이 창 닫기"><svg><use href="#i-close"/></svg></button></div>
  <div class="lec-scroll" tabindex="-1"><article></article></div>`;

function createPane(el) {
  const pane = {
    el,                                       // section.lec-pane
    scroller: el.querySelector('.lec-scroll'),
    view: el.querySelector('.lec-scroll > article'),
    current: null,                            // 이 칸의 화면 {type, path}. 선택된 칸이면 S.view 와 같다
    history: [], hIndex: -1, wanted: null,    // 뒤로/앞으로 (nav.js)
    pending: 0, missedRefresh: false,         // 진행 중인 이동 수, 이동 중에 들어온 새로고침 (nav.js)
    renderId: 0,                              // 늦게 끝난 렌더링이 새 화면을 덮지 않도록 하는 순번 (doc.js·htmldoc.js·overview.js)
    tocRoot: null,                            // 목차를 만들 곳 (toc.js)
    status: { path: '', info: '' },           // 상태줄 (status.js)
    source: null,                             // 우클릭 메뉴가 쓰는 원문 {path, lines} (docmenu.js)
    marks: { list: [], next: 0 },             // 자동 새로고침으로 바뀐 곳 (diffmark.js)
  };
  el.querySelector('.pane-close').addEventListener('click', () => closePane(pane));
  return pane;
}

/** node 가 든 칸. html 문서(iframe) 안의 node 면 그 iframe 이 든 칸 */
export function paneOf(node) {
  const el = node?.ownerDocument && node.ownerDocument !== document ? node.ownerDocument.defaultView?.frameElement : node;
  return el ? S.panes.find((p) => p.el.contains(el)) || null : null;
}

/** 칸 머리줄의 제목: 문서 제목(없으면 파일명) 또는 폴더 이름 */
export function showTitle(pane) {
  const v = pane.current;
  const f = v?.type === 'doc' ? S.fileMap.get(v.path) : null;
  const title = !v ? '' : v.type === 'doc' ? (f?.title || basename(v.path)) : (v.path ? basename(v.path) : S.name);
  const el = pane.el.querySelector('.pane-title');
  el.textContent = title;
  el.title = v ? (v.type === 'doc' ? v.path : `${v.path || S.name}/`) : '';
}

function layout() {
  $('#lec-panes').classList.toggle('split', S.panes.length > 1);
  for (const p of S.panes) p.el.querySelector('.pane-close').hidden = S.panes.length < 2;
}

/** 칸을 고른다. 목차·상태줄 등은 'pane' 을 듣고 이 칸 것으로 바꾸고, 트리·툴바·창 제목은 'view' 를 듣는다 */
export function selectPane(pane) {
  if (!pane || pane === S.pane) return;
  const old = S.pane;
  if (old) {
    old.el.classList.remove('active');
    old.scroller.removeAttribute('id');
    old.view.removeAttribute('id');
  }
  pane.el.classList.add('active');
  pane.scroller.id = 'lec-content';
  pane.view.id = 'lec-view';
  pane.scroller.prepend($('#lec-findbar'));
  S.pane = pane;
  S.view = pane.current;
  emit('pane', pane);
  emit('view', S.view);
}

/** after 칸 바로 오른쪽에 빈 칸을 만든다 (고르지는 않는다). 이미 3칸이면 null */
export function addPane(after = S.pane) {
  if (S.panes.length >= MAX_PANES) return null;
  const el = document.createElement('section');
  el.className = 'lec-pane';
  el.innerHTML = PANE_HTML;
  after.el.after(el);
  const pane = createPane(el);
  S.panes.splice(S.panes.indexOf(after) + 1, 0, pane);
  layout();
  emit('panes');
  return pane;
}

/** 칸을 닫는다. 선택된 칸이었으면 왼쪽 칸(없으면 오른쪽)을 고른다. 마지막 하나는 닫지 않는다 */
export function closePane(pane) {
  const i = S.panes.indexOf(pane);
  if (i < 0 || S.panes.length < 2) return false;
  if (pane === S.pane) selectPane(S.panes[i ? i - 1 : 1]);
  S.panes.splice(i, 1);
  pane.renderId += 1;   // 그리던 것이 있으면 버리게
  pane.el.remove();
  layout();
  emit('panes');
  return true;
}

/** 칸을 하나로 되돌리고 그 칸의 기록을 지운다 (다른 폴더를 열 때) */
export function resetPanes() {
  selectPane(S.panes[0]);
  for (const p of S.panes.slice(1)) closePane(p);
  Object.assign(S.pane, { current: null, history: [], hIndex: -1, wanted: null, tocRoot: null, source: null, marks: { list: [], next: 0 } });
  S.view = null;
  showTitle(S.pane);
}

export function initPanes() {
  S.panes = [createPane($('.lec-pane'))];
  selectPane(S.panes[0]);
  layout();
  const box = $('#lec-panes');
  // 누르기 전에 고른다 — 클릭·우클릭을 다루는 코드는 고른 칸(#lec-view)을 본다.
  // 닫기 단추를 왼쪽 단추로 누르면 고르지 않고 닫는다 (우클릭은 그 칸을 골라 그 칸의 메뉴가 뜨게)
  const pick = (e) => { if (!(e.button === 0 && e.target.closest('.pane-close'))) selectPane(paneOf(e.target)); };
  box.addEventListener('pointerdown', pick, true);
  box.addEventListener('focusin', pick);
  on('tree', () => S.panes.forEach(showTitle));   // 문서 제목이 바뀌었을 수 있다
}
