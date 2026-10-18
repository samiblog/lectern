// 화면 이동, 뒤로/앞으로, 다시 그리기. 칸(panes.js)마다 따로 — 기본은 선택된 칸

import { S, emit, on } from './store.js';
import { showDoc } from './doc.js';
import { showHtml } from './htmldoc.js';
import { showOverview } from './overview.js';
import { forgetFolds } from './fold.js';
import { MAX_PANES, addPane, closePane, selectPane, resetPanes, showTitle } from './panes.js';
import { isHtml, toast } from './util.js';

/** 문서 형식에 맞는 렌더러 (md: doc.js, html: htmldoc.js) */
const render = (pane, path, opts) => (isHtml(path) ? showHtml(pane, path, opts) : showDoc(pane, path, opts));

const scrollPos = new Map();   // 문서·폴더별 마지막 스크롤 위치 (모든 칸이 함께 쓴다)
const keyOf = (t) => `${t.type}:${t.path || ''}`;

/**
 * 화면 이동. 성공하면 true.
 * index: 뒤로/앞으로처럼 기록 안의 위치로 갈 때, 렌더링이 실제로 끝난 뒤에만 pane.hIndex 를 그 값으로 바꾼다.
 * scrollTop: 이 위치로 (마지막에 열어 둔 창 되살리기). 없으면 restoreScroll 일 때 그 문서의 마지막 위치, 아니면 맨 위나 앵커
 */
export async function navigate(target, { pane = S.pane, push = true, restoreScroll = false, index = null, scrollTop } = {}) {
  if (pane.current) scrollPos.set(keyOf(pane.current), pane.scroller.scrollTop);
  if (index == null) pane.wanted = null;
  const next = { type: target.type, path: target.path || '' };
  const top = scrollTop ?? (restoreScroll ? scrollPos.get(keyOf(next)) : undefined);
  pane.pending += 1;   // 이동 중에는 자동 새로고침이 끼어들지 않게 한다
  let done;
  try {
    done = next.type === 'doc'
      ? await render(pane, next.path, { hash: target.hash, scrollTop: top })
      : await showOverview(pane, next.path, { scrollTop: top });
  } catch (e) {
    console.error(e);
    toast(`화면을 그리지 못했습니다: ${e.message}`, 'error');
    done = false;
  } finally {
    pane.pending -= 1;
    if (!pane.pending && pane.missedRefresh) {   // 이동 중에 들어온 새로고침 — 그사이 바뀐 문서를 놓치지 않게
      pane.missedRefresh = false;
      setTimeout(() => refreshView(pane));
    }
  }
  if (!done) return false;   // 더 나중의 이동이 이겼음 (또는 오류, 닫힌 칸)
  pane.current = next;
  if (index != null) {
    pane.hIndex = index;
  } else if (push) {
    const cur = pane.history[pane.hIndex];
    if (!cur || keyOf(cur) !== keyOf(next)) {
      pane.history.splice(pane.hIndex + 1);
      pane.history.push(next);
      pane.hIndex = pane.history.length - 1;
    }
  }
  showTitle(pane);
  if (pane === S.pane) {
    S.view = next;
    emit('view', next);
  }
  return true;
}

/** 선택된 칸 오른쪽에 새 칸을 열어 target 을 보인다 (Ctrl+클릭, 우클릭 '오른쪽 창에 열기'). 이미 3칸이면 선택된 칸에 연다 */
export async function openBeside(target) {
  if (!S.root) return false;
  const pane = addPane();
  if (!pane) {
    toast(`창은 ${MAX_PANES}개까지 열 수 있습니다. 선택된 창에 열었습니다`);
    return navigate(target);
  }
  selectPane(pane);
  if (await navigate(target, { pane })) return true;
  if (!pane.current && !pane.pending) closePane(pane);   // 열지 못했으면 빈 칸을 남기지 않는다
  return false;
}

/**
 * 마지막에 열어 둔 창들을 되살린다 (position.js 가 기록한 /api/state 의 position). 없어진 문서는 건너뛴다.
 * 하나도 열지 못하면 false.
 */
export async function restorePanes({ panes = [], active = 0 } = {}) {
  const want = panes[active];
  let target = null;
  for (const p of panes.filter((x) => S.fileMap.has(x.doc)).slice(0, MAX_PANES)) {
    const pane = target ? addPane(S.panes[S.panes.length - 1]) : S.pane;
    if (await navigate({ type: 'doc', path: p.doc }, { pane, scrollTop: p.scroll })) {
      if (!target || p === want) target = pane;
    } else if (pane !== S.pane) {
      closePane(pane);
    }
  }
  if (target) selectPane(target);
  return !!target;
}

function go(step) {
  const pane = S.pane;
  const index = (pane.wanted ?? pane.hIndex) + step;
  if (index < 0 || index >= pane.history.length) return;
  pane.wanted = index;   // 빠르게 여러 번 누르면 여기서 이어 간다
  navigate(pane.history[index], { pane, push: false, restoreScroll: true, index }).finally(() => {
    if (pane.wanted === index) pane.wanted = null;
  });
}

export const back = () => go(-1);
export const forward = () => go(1);

/** 서버가 기억한 문서별 스크롤 위치를 넣어 둔다 (폴더를 열 때 마지막 위치 복원, position.js) */
export function seedScroll(positions) {
  for (const [path, top] of Object.entries(positions || {})) scrollPos.set(keyOf({ type: 'doc', path }), top);
}

export function resetHistory() {
  resetPanes();
  scrollPos.clear();
  forgetFolds();
}

/**
 * 칸의 화면을 같은 스크롤 위치로 다시 그린다 (자동 새로고침, 테마 변경). pane 이 없으면 모든 칸.
 * 위치는 시작할 때가 아니라 바꿔 끼우기 직전에 읽는다 — 그리는 동안 사용자가 스크롤해도 되돌리지 않게.
 */
export async function refreshView(pane) {
  if (!pane) {
    await Promise.all(S.panes.map((p) => refreshView(p)));
    return;
  }
  const view = pane.current;
  if (!view || !S.panes.includes(pane)) return;   // 빈 칸, 닫힌 칸
  if (pane.pending) {
    pane.missedRefresh = true;
    return;
  }
  const scrollTop = () => pane.scroller.scrollTop;
  try {
    if (view.type === 'doc') await render(pane, view.path, { scrollTop });
    else await showOverview(pane, view.path, { scrollTop });
  } catch (e) {
    console.error(e);
    toast(`다시 그리지 못했습니다: ${e.message}`, 'error');
  }
}

export function initNav() {
  on('open', (t) => (t.side ? openBeside(t) : navigate(t)));
  on('refresh-view', (pane) => refreshView(pane));
}
