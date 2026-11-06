// 사이드바 목록의 차례 (D97): 문서·코드·자료 모두 폴더 먼저, 파일 다음이고, 그 안의 차례를 이름순·시간순·형식순으로 고른다 (설정 side_sort).
// 이름순은 서버가 준 차례 그대로다. 시간순은 새것이 위로, 폴더는 그 안에서 가장 새 파일의 시각으로. 형식순은 확장자 차례이고 폴더는 이름순.

import { S } from './store.js';
import { natCompare } from './util.js';

const seen = new WeakMap();   // 폴더 → 그 안에서 가장 새 시각 (트리를 다시 받으면 노드가 바뀐다)

function latest(n) {
  if (n.type === 'file') return n.mtime || 0;
  if (!seen.has(n)) seen.set(n, Math.max(0, ...(n.children || []).map(latest)));
  return seen.get(n);
}

const byName = (a, b) => natCompare(a.name, b.name);
const byTime = (a, b) => latest(b) - latest(a) || byName(a, b);
const extOf = (name) => (name.includes('.') ? name.slice(name.lastIndexOf('.') + 1).toLowerCase() : '');
const byType = (a, b) => natCompare(extOf(a.name), extOf(b.name)) || byName(a, b);

/** 한 수준의 노드들을 지금 고른 차례로 */
export function sideOrder(nodes) {
  const way = S.config.side_sort;
  if (way !== 'time' && way !== 'type') return nodes;
  const dirs = nodes.filter((n) => n.type !== 'file');
  const files = nodes.filter((n) => n.type === 'file');
  return [...dirs.sort(way === 'time' ? byTime : byName), ...files.sort(way === 'time' ? byTime : byType)];
}
