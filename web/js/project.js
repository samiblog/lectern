// 트리 데이터 불러오기 (탭마다)

import { S, emit } from './store.js';
import { getJSON } from './api.js';

/**
 * 탭(기본: 선택된 탭)의 트리를 받는다. fresh: 서버의 스캔 결과를 다시 쓰지 않고 새로 훑는다 (F5 — 감시가 놓친 변경까지).
 * 그 탭의 첫 트리는 서버가 기억한 제목만으로 바로 받는다 (quick — D140). 제목을 아직 모르는 문서가 있으면(pending) 이름으로 먼저 그리고,
 * 서버가 그 문서들을 읽은 트리를 뒤에서 받아 제목을 채운다 — 문서가 수백 개인 프로젝트를 처음 열 때 기다리지 않게
 */
export async function loadTree({ fresh = false, tab = S.tab } = {}) {
  const gen = (tab.treeGen = (tab.treeGen || 0) + 1);
  const quick = !tab.treeLoaded && !fresh;
  const url = `/api/tree?p=${encodeURIComponent(tab.id)}`;
  const data = await getJSON(`${url}${fresh ? '&fresh=1' : ''}${quick ? '&quick=1' : ''}`);
  applyTree(tab, data);
  if (!data.pending) return;
  getJSON(url).then((full) => {
    if (tab.treeGen === gen && S.tabs.includes(tab)) applyTree(tab, full);   // 그사이 다시 받았으면 그쪽이 새것이다
  }).catch(() => {});   // 제목 없이도 트리는 쓸 수 있다 — 다음 새로고침이 다시 받는다
}

/** 받은 트리를 탭에 놓고 알린다 */
function applyTree(tab, data) {
  const files = [];
  const dirs = new Set(['']);
  const walk = (nodes) => {
    for (const n of nodes) {
      if (n.type === 'file') files.push(n);
      else {
        dirs.add(n.path);
        walk(n.children);
      }
    }
  };
  walk(data.tree);
  tab.tree = data.tree;
  tab.files = files;
  tab.dirs = dirs;
  tab.fileMap = new Map(files.map((f) => [f.path, f]));
  tab.treeLoaded = true;
  for (const p of [...tab.changed]) if (!tab.fileMap.has(p)) tab.changed.delete(p);
  for (const p of [...tab.open]) if (!dirs.has(p)) tab.open.delete(p);
  if (tab === S.tab) emit('tree');
}
