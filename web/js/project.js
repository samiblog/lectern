// 트리 데이터 불러오기

import { S, emit } from './store.js';
import { getJSON } from './api.js';

export async function loadTree() {
  const data = await getJSON('/api/tree');
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
