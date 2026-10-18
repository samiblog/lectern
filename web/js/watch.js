// 자동 새로고침: 1초마다 서버의 변경 기록을 확인한다 (GET /api/changes?since=seq)

import { S, emit } from './store.js';
import { getJSON } from './api.js';
import { loadTree } from './project.js';

const INTERVAL_MS = 1000;
let timer = 0;
let busy = false;

async function tick() {
  if (busy || document.hidden || !S.root || S.reloading) return;
  busy = true;
  try {
    const d = await getJSON(`/api/changes?since=${S.seq}`);
    if (d.root !== S.root) {
      emit('project-switched');
      return;
    }
    if (d.seq === S.seq && !d.reset) return;
    S.seq = d.seq;
    await loadTree();

    const shown = new Set(S.panes.filter((p) => p.current?.type === 'doc').map((p) => p.current.path));
    for (const p of d.paths) {
      // 지워졌거나 이름이 바뀐(옛 이름) 경로, 창에 보이는 문서는 표시하지 않는다
      if (S.fileMap.has(p) && !shown.has(p)) S.changed.add(p);
    }
    S.lastSync = new Date();
    emit('changed');
    emit('synced');

    for (const pane of S.panes) {
      const view = pane.current;
      if (!view) continue;
      if (view.type === 'doc' && (d.reset || d.paths.includes(view.path) || !S.fileMap.has(view.path))) {
        emit('refresh-view', pane);
      } else if (view.type === 'overview') {
        const prefix = view.path ? `${view.path}/` : '';
        if (d.structure || d.paths.some((p) => p.startsWith(prefix))) emit('refresh-view', pane);
      }
    }
  } catch {
    // 서버가 잠시 응답하지 않음 — 다음 주기에 다시 시도
  } finally {
    busy = false;
  }
}

export function startWatch() {
  stopWatch();
  timer = setInterval(tick, INTERVAL_MS);
}

export function stopWatch() {
  clearInterval(timer);
  timer = 0;
}

export function initWatch() {
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
}
