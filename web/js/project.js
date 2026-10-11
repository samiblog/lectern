// 트리 데이터 불러오기

import { S, emit } from './store.js';
import { getJSON } from './api.js';

/** fresh: 서버의 스캔 결과를 다시 쓰지 않고 새로 훑는다 (F5 — 감시가 놓친 변경까지) */
export async function loadTree({ fresh = false } = {}) {
  const data = await getJSON(fresh ? '/api/tree?fresh=1' : '/api/tree');
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
  S.tree = data.tree;
  S.files = files;
  S.dirs = dirs;
  S.fileMap = new Map(files.map((f) => [f.path, f]));
  for (const p of [...S.changed]) if (!S.fileMap.has(p)) S.changed.delete(p);
  for (const p of [...S.open]) if (!dirs.has(p)) S.open.delete(p);
  emit('tree');
}
