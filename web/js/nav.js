// 화면 이동, 뒤로/앞으로, 다시 그리기

import { S, emit, on } from './store.js';
import { showDoc } from './doc.js';
import { showOverview } from './overview.js';
import { forgetFolds } from './fold.js';
import { $ } from './util.js';

const scrollPos = new Map();
const keyOf = (t) => `${t.type}:${t.path || ''}`;
let pending = 0;   // 진행 중인 이동 수. 이동 중에는 자동 새로고침이 끼어들지 않게 한다

/**
 * 화면 이동. 성공하면 true.
 * index: 뒤로/앞으로처럼 기록 안의 위치로 갈 때, 렌더링이 실제로 끝난 뒤에만 S.hIndex 를 그 값으로 바꾼다.
 */
export async function navigate(target, { push = true, restoreScroll = false, index = null } = {}) {
  if (S.view) scrollPos.set(keyOf(S.view), $('#lec-content').scrollTop);
  const next = { type: target.type, path: target.path || '' };
  const scrollTop = restoreScroll ? scrollPos.get(keyOf(next)) : undefined;
  pending += 1;
  let done;
  try {
    done = next.type === 'doc'
      ? await showDoc(next.path, { hash: target.hash, scrollTop })
      : await showOverview(next.path, { scrollTop });
  } finally {
    pending -= 1;
  }
  if (!done) return false;   // 더 나중의 이동이 이겼음
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

export function back() {
  if (S.hIndex <= 0) return;
  const index = S.hIndex - 1;
  navigate(S.history[index], { push: false, restoreScroll: true, index });
}

export function forward() {
  if (S.hIndex >= S.history.length - 1) return;
  const index = S.hIndex + 1;
  navigate(S.history[index], { push: false, restoreScroll: true, index });
}

export function resetHistory() {
  S.history = [];
  S.hIndex = -1;
  S.view = null;
  scrollPos.clear();
  forgetFolds();
}

/** 지금 화면을 같은 스크롤 위치로 다시 그린다 (자동 새로고침, 테마 변경). */
export async function refreshView() {
  if (!S.view || pending) return;
  const scrollTop = $('#lec-content').scrollTop;
  if (S.view.type === 'doc') await showDoc(S.view.path, { scrollTop });
  else await showOverview(S.view.path, { scrollTop });
}

export function initNav() {
  on('open', (t) => navigate(t));
  on('refresh-view', refreshView);
}
