// 자동 새로고침: 1초마다 서버의 변경 기록을 확인한다 (GET /api/changes?since=<탭 id>:<순번>,… — 열린 탭 모두를 한 번에).
// 선택된 탭은 바뀐 화면을 바로 다시 그리고, 숨은 탭은 트리와 '변경됨'만 갱신해 두었다가 그 탭을 고를 때 다시 그린다 (tabs.js).
// 서버의 탭 목록이 바뀌었으면(다른 실행이 넘긴 폴더) 탭을 다시 맞춘다.

import { S, emit } from './store.js';
import { getJSON } from './api.js';
import { loadTree } from './project.js';
import { knownTabsSeq, resyncTabs } from './tabs.js';

const INTERVAL_MS = 1000;
let timer = 0;
let busy = false;

/** 탭(tab)에 변경 기록(d)을 반영한다 */
async function apply(tab, d) {
  if (d.reset || d.structure || d.others) {   // 문서 외 파일 목록 (others.js — 보일 때만 다시 읽는다)
    tab.others.stale = true;
    if (tab === S.tab) emit('others', tab);
  }
  if (!d.reset && !d.structure && !d.paths.length) return;   // 문서 외 파일만 바뀜 — 문서 트리는 그대로
  if (!tab.loaded) {
    // 아직 고르지 않은 탭: 트리는 고를 때 읽는다. 바뀐 문서만 모아 탭에 점을 띄운다 (트리를 읽으면 없는 문서는 빠진다)
    for (const p of d.paths) tab.changed.add(p);
    emit('changed');
    return;
  }
  await loadTree({ tab });
  const { pane } = tab;
  const view = pane.current;
  const shown = tab === S.tab && view?.type === 'doc' ? view.path : null;
  for (const p of d.paths) {
    // 지워졌거나 이름이 바뀐(옛 이름) 경로, 지금 보고 있는 문서는 표시하지 않는다
    if (tab.fileMap.has(p) && p !== shown) tab.changed.add(p);
  }
  tab.lastSync = new Date();
  emit('changed');
  emit('synced');

  let affected = false;
  if (view?.type === 'doc') {
    affected = d.reset || d.paths.includes(view.path) || !tab.fileMap.has(view.path);
  } else if (view?.type === 'overview') {
    const prefix = view.path ? `${view.path}/` : '';
    affected = d.structure || d.paths.some((p) => p.startsWith(prefix));
  }
  if (!affected) return;
  if (tab === S.tab) emit('refresh-view', pane);
  else pane.stale = true;   // 고를 때 다시 그린다 — 바뀐 곳 강조도 그때 보인다
}

async function tick() {
  if (busy || document.hidden) return;
  busy = true;
  try {
    const tabs = S.tabs.filter((t) => !t.loading);   // 처음 그리는 중인 탭은 다음 주기에
    const since = tabs.map((t) => `${t.id}:${t.seq}`).join(',');
    const d = await getJSON(`/api/changes?since=${encodeURIComponent(since)}`);
    if (d.tabs_seq !== knownTabsSeq()) {
      await resyncTabs();
      return;
    }
    for (const tab of tabs) {
      const c = d.projects[tab.id];
      if (!c || !S.tabs.includes(tab) || tab.loading || (c.seq === tab.seq && !c.reset)) continue;
      tab.seq = c.seq;
      await apply(tab, c);
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
