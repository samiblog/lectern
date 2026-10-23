// 문서 화면(칸): 프로젝트 탭(tabs.js)마다 하나씩, 그 탭의 화면·스크롤·뒤로/앞으로 기록·렌더링 순번을 가진다.
// 탭이 없을 때 보이는 시작 화면도 칸 하나다 (탭에 속하지 않는 칸, pane.tab 이 null).
//
// - 선택된 칸만 보인다. 나머지 칸은 자리를 지킨 채 숨긴다 (app.css 의 visibility) — display:none 이면 스크롤 위치를 잃고,
//   숨은 동안 그림·html 문서의 크기를 잴 수 없다. 탭을 오갈 때 다시 그리지 않으므로 읽던 화면이 그대로 남는다.
// - 그리기는 nav.js 가 칸을 정해 doc.js·htmldoc.js·overview.js 에 넘긴다. 렌더러는 칸의 탭(pane.tab)에서 프로젝트를 읽는다.
// - 선택된 칸의 스크롤 상자와 본문에 #lec-content·#lec-view id 를 옮겨 단다. 선택된 칸만 다루는 코드(찾기·우클릭 메뉴 등)는
//   그 id 로 찾고, 모든 칸을 다루는 코드는 칸 객체를 쓴다. 찾기 막대(#lec-findbar)도 선택된 칸으로 옮긴다.

import { S, emit } from './store.js';
import { $ } from './util.js';

let home = null;   // 시작 화면 칸 (index.html 에 처음부터 있는 칸)

function makePane(el, tab) {
  return {
    el,                                       // section.lec-pane
    tab,                                      // 이 칸이 속한 탭 (시작 화면이면 null)
    scroller: el.querySelector('.lec-scroll'),
    view: el.querySelector('.lec-scroll > article'),
    current: null,                            // 이 칸의 화면 {type, path}. 선택된 칸이면 S.view 와 같다
    history: [], hIndex: -1, wanted: null,    // 뒤로/앞으로 (nav.js)
    scrollPos: new Map(),                     // 문서·폴더별 마지막 스크롤 위치 (nav.js)
    pending: 0, missedRefresh: false,         // 진행 중인 이동 수, 이동 중에 들어온 새로고침 (nav.js)
    stale: false,                             // 숨은 동안 바뀌어 고를 때 다시 그릴 칸 (watch.js·nav.js → tabs.js)
    renderId: 0,                              // 늦게 끝난 렌더링이 새 화면을 덮지 않도록 하는 순번 (doc.js·htmldoc.js·overview.js)
    tocRoot: null,                            // 목차를 만들 곳 (toc.js)
    status: { path: '', info: '' },           // 상태줄 (status.js)
    source: null,                             // 우클릭 메뉴가 쓰는 원문 {path, lines} (docmenu.js)
    marks: { list: [], next: 0 },             // 자동 새로고침으로 바뀐 곳 (diffmark.js)
  };
}

/** node 가 든 칸. html 문서(iframe) 안의 node 면 그 iframe 이 든 칸 */
export function paneOf(node) {
  const el = node?.ownerDocument && node.ownerDocument !== document ? node.ownerDocument.defaultView?.frameElement : node;
  return el ? S.panes.find((p) => p.el.contains(el)) || null : null;
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

/** 탭의 칸을 만든다 (고르지는 않는다) */
export function createPane(tab) {
  const el = document.createElement('section');
  el.className = 'lec-pane';
  el.innerHTML = '<div class="lec-scroll" tabindex="-1"><article></article></div>';
  $('#lec-panes').append(el);
  const pane = makePane(el, tab);
  S.panes.push(pane);
  return pane;
}

/** 탭을 닫을 때 그 칸을 없앤다. 선택된 칸이었으면 시작 화면을 고른다 (부르는 쪽이 곧 다른 탭을 고른다) */
export function removePane(pane) {
  if (pane === S.pane) selectPane(home);
  pane.renderId += 1;   // 그리던 것이 있으면 버리게
  pane.el.remove();
  S.panes = S.panes.filter((p) => p !== pane);
}

/** 시작 화면 칸 (탭이 하나도 없을 때) */
export const homePane = () => home;

export function initPanes() {
  home = makePane($('.lec-pane'), null);
  S.panes = [home];
  selectPane(home);
}
