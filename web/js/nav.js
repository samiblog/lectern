// 화면 이동, 뒤로/앞으로, 다시 그리기

import { S, emit, on } from './store.js';
import { showDoc } from './doc.js';
import { showHtml } from './htmldoc.js';
import { showOverview } from './overview.js';
import { forgetFolds } from './fold.js';
import { $, isHtml, toast } from './util.js';

/** 문서 형식에 맞는 렌더러 (md: doc.js, html: htmldoc.js) */
const render = (path, opts) => (isHtml(path) ? showHtml(path, opts) : showDoc(path, opts));

const scrollPos = new Map();
const keyOf = (t) => `${t.type}:${t.path || ''}`;
let pending = 0;   // 진행 중인 이동 수. 이동 중에는 자동 새로고침이 끼어들지 않게 한다
let missedRefresh = false;   // 이동 중에 들어온 새로고침 — 이동이 끝나면 한 번 한다 (그사이 바뀐 문서를 놓치지 않게)
let wanted = null;   // 진행 중인 뒤로/앞으로의 기록 위치. 빠르게 여러 번 누르면 여기서 이어 간다

/**
 * 화면 이동. 성공하면 true.
 * index: 뒤로/앞으로처럼 기록 안의 위치로 갈 때, 렌더링이 실제로 끝난 뒤에만 S.hIndex 를 그 값으로 바꾼다.
 */
export async function navigate(target, { push = true, restoreScroll = false, index = null } = {}) {
  if (S.view) scrollPos.set(keyOf(S.view), $('#lec-content').scrollTop);
  if (index == null) wanted = null;
  const next = { type: target.type, path: target.path || '' };
  const scrollTop = restoreScroll ? scrollPos.get(keyOf(next)) : undefined;
  pending += 1;
  let done;
  try {
    done = next.type === 'doc'
      ? await render(next.path, { hash: target.hash, scrollTop })
      : await showOverview(next.path, { scrollTop });
  } catch (e) {
    console.error(e);
    toast(`화면을 그리지 못했습니다: ${e.message}`, 'error');
    done = false;
  } finally {
    pending -= 1;
    if (!pending && missedRefresh) {
      missedRefresh = false;
      setTimeout(refreshView);
    }
  }
  if (!done) return false;   // 더 나중의 이동이 이겼음 (또는 오류)
  S.view = next;
  if (index != null) {
    S.hIndex = index;
  } else if (push) {
    const cur = S.history[S.hIndex];
    if (!cur || keyOf(cur) !== keyOf(next)) {
      S.history.splice(S.hIndex + 1);
      S.history.push(next);
      S.hIndex = S.history.length - 1;
    }
  }
  emit('view', next);
  return true;
}

function go(step) {
  const index = (wanted ?? S.hIndex) + step;
  if (index < 0 || index >= S.history.length) return;
  wanted = index;
  navigate(S.history[index], { push: false, restoreScroll: true, index }).finally(() => {
    if (wanted === index) wanted = null;
  });
}

export const back = () => go(-1);
export const forward = () => go(1);

/** 서버가 기억한 문서별 스크롤 위치를 넣어 둔다 (폴더를 열 때 마지막 위치 복원, position.js) */
export function seedScroll(positions) {
  for (const [path, top] of Object.entries(positions || {})) scrollPos.set(keyOf({ type: 'doc', path }), top);
}

export function resetHistory() {
  S.history = [];
  S.hIndex = -1;
  wanted = null;
  S.view = null;
  scrollPos.clear();
  forgetFolds();
}

/**
 * 지금 화면을 같은 스크롤 위치로 다시 그린다 (자동 새로고침, 테마 변경).
 * 위치는 시작할 때가 아니라 바꿔 끼우기 직전에 읽는다 — 그리는 동안 사용자가 스크롤해도 되돌리지 않게.
 */
export async function refreshView() {
  if (!S.view) return;
  if (pending) {
    missedRefresh = true;
    return;
  }
  const scrollTop = () => $('#lec-content').scrollTop;
  try {
    if (S.view.type === 'doc') await render(S.view.path, { scrollTop });
    else await showOverview(S.view.path, { scrollTop });
  } catch (e) {
    console.error(e);
    toast(`다시 그리지 못했습니다: ${e.message}`, 'error');
  }
}

export function initNav() {
  on('open', (t) => navigate(t));
  on('refresh-view', refreshView);
}
