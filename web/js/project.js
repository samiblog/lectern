// 트리 데이터 불러오기 (탭마다)

import { S, emit } from './store.js';
import { getJSON } from './api.js';

/** 탭(기본: 선택된 탭)의 트리를 받는다. fresh: 서버의 스캔 결과를 다시 쓰지 않고 새로 훑는다 (F5 — 감시가 놓친 변경까지) */
export async function loadTree({ fresh = false, tab = S.tab } = {}) {
  const data = await getJSON(`/api/tree?p=${encodeURIComponent(tab.id)}${fresh ? '&fresh=1' : ''}`);
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
