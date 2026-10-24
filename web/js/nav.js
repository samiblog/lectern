// 화면 이동, 뒤로/앞으로, 다시 그리기. 칸(panes.js — 프로젝트 탭마다 하나)마다 따로 — 기본은 선택된 탭의 칸

import { S, emit, on } from './store.js';
import { showDoc } from './doc.js';
import { showHtml } from './htmldoc.js';
import { showOverview } from './overview.js';
import { showCode } from './codeview.js';
import { isHtml, toast } from './util.js';
import { t } from './i18n.js';

/** 화면 종류·문서 형식에 맞는 렌더러 (md: doc.js, html: htmldoc.js, 코드: codeview.js — D43, 폴더 개요: overview.js) */
function render(pane, target, opts) {
  if (target.type === 'code') return showCode(pane, target.path, opts);
  if (target.type === 'overview') return showOverview(pane, target.path, opts);
  return isHtml(target.path) ? showHtml(pane, target.path, opts) : showDoc(pane, target.path, opts);
}

const keyOf = (target) => `${target.type}:${target.path || ''}`;

/**
 * 화면 이동. 성공하면 true.
 * index: 뒤로/앞으로처럼 기록 안의 위치로 갈 때, 렌더링이 실제로 끝난 뒤에만 pane.hIndex 를 그 값으로 바꾼다.
 * scrollTop: 이 위치로. 없으면 restoreScroll 일 때 그 문서의 마지막 위치, 아니면 맨 위나 앵커
 */
let leaveGuard = null;   // 칸에서 다른 화면으로 가기 전에 — 편집 모드(editor.js, D54)가 저장하지 않은 것을 묻는다. false 면 가지 않는다

/** 다른 화면으로 가기 전에 부를 함수 (editor.js) */
export function setLeaveGuard(fn) {
  leaveGuard = fn;
}

export async function navigate(target, { pane = S.pane, push = true, restoreScroll = false, index = null, scrollTop } = {}) {
  if (!pane?.tab) return false;   // 시작 화면 (열린 탭이 없음)
  if (pane.editor && leaveGuard && !leaveGuard(pane)) return false;   // 편집 중 — 저장하지 않은 것을 버리지 않기로 함
  if (pane.current) pane.scrollPos.set(keyOf(pane.current), pane.scroller.scrollTop);
  if (index == null) pane.wanted = null;
  const next = { type: target.type, path: target.path || '' };
  const top = scrollTop ?? (restoreScroll ? pane.scrollPos.get(keyOf(next)) : undefined);
  pane.pending += 1;   // 이동 중에는 자동 새로고침이 끼어들지 않게 한다
  let done;
  try {
    done = await render(pane, next, { hash: target.hash, line: target.line, scrollTop: top, missing: target.missing });
  } catch (e) {
    console.error(e);
    toast(t('화면을 그리지 못했습니다: {error}', { error: e.message }), 'error');
    done = false;
  } finally {
    pane.pending -= 1;
    if (!pane.pending && pane.missedRefresh) {   // 이동 중에 들어온 새로고침 — 그사이 바뀐 문서를 놓치지 않게
      pane.missedRefresh = false;
      setTimeout(() => refreshView(pane));
    }
  }
  if (!done) return false;   // 더 나중의 이동이 이겼음 (또는 오류, 닫힌 탭)
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
  if (pane === S.pane) {
    S.view = next;
    emit('view', next);
  }
  return true;
}

/**
 * 탭을 처음 열 때 마지막에 보던 문서와 스크롤 위치로 (position.js 가 기록한 /api/state 의 position).
 * 문서별 위치도 넣어 두어 뒤로 가기·다시 열 때 쓴다. 그 문서가 없어졌으면 false (부르는 쪽이 폴더 개요를 연다).
 */
export async function restorePosition(pane, pos) {
  for (const [path, top] of Object.entries(pos?.scroll || {})) pane.scrollPos.set(keyOf({ type: 'doc', path }), top);
  if (!pos?.doc || !pane.tab.fileMap.has(pos.doc)) return false;
  return navigate({ type: 'doc', path: pos.doc }, { pane, restoreScroll: true });
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

/**
 * 칸의 화면을 같은 스크롤 위치로 다시 그린다 (자동 새로고침, 테마 변경).
 * pane 이 없으면 모든 탭: 선택된 탭은 바로, 숨은 탭은 표시만 해 두고 그 탭을 고를 때 그린다 (tabs.js — 보이지 않는 탭을 모두 그리지 않게).
 * 위치는 시작할 때가 아니라 바꿔 끼우기 직전에 읽는다 — 그리는 동안 사용자가 스크롤해도 되돌리지 않게.
 */
export async function refreshView(pane) {
  if (!pane) {
    for (const p of S.panes) if (p !== S.pane && p.current) p.stale = true;
    if (S.pane) await refreshView(S.pane);
    return;
  }
  const view = pane.current;
  if (!view || !S.panes.includes(pane)) return;   // 빈 칸, 닫힌 탭
  if (pane.pending) {
    pane.missedRefresh = true;
    return;
  }
  pane.stale = false;
  const scrollTop = () => pane.scroller.scrollTop;
  try {
    await render(pane, view, { scrollTop });
  } catch (e) {
    console.error(e);
    toast(t('다시 그리지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

export function initNav() {
  on('open', (target) => navigate(target));
  on('refresh-view', (pane) => refreshView(pane));
}
