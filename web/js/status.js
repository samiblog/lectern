// 아래 상태 표시줄: 경로, 수정 시각, 자동 갱신 상태

import { S, on } from './store.js';
import { $, formatClock } from './util.js';

const WATCH_LABEL = { watchdog: '변경 감시 중', polling: '변경 감시 중 (주기 확인)' };

export function setStatus({ path = '', info = '' } = {}) {
  $('#lec-st-path').textContent = path;
  $('#lec-st-info').textContent = info;
}

function renderWatch() {
  const el = $('#lec-st-watch');
  if (!S.root) {
    el.textContent = '';
    return;
  }
  const base = WATCH_LABEL[S.watch] || '변경 감시 중';
  el.textContent = S.lastSync ? `${base}, 마지막 반영 ${formatClock(S.lastSync)}` : base;
}

export function initStatus() {
  on('synced', renderWatch);
  on('view', renderWatch);
}
