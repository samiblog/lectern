// 마지막 위치 기억: 탭마다 보고 있는 문서와 스크롤 위치를 서버에 알려 둔다 (POST /api/position {p, path, scroll}).
// 다음에 그 폴더를 열면(다음 실행에 탭을 되살릴 때도) tabs.js 가 그 문서와 위치로 연다 (nav.js 의 restorePosition).
// 설정 restore_last 가 꺼져 있으면 보내지 않는다. 설정 파일에 쓰므로 자주 쓰지 않게, 스크롤이 멈추고 1.5초 뒤에 한 번 보낸다.
// 폴더 개요를 보는 탭은 기록하지 않는다.

import { S, on } from './store.js';
import { postJSON } from './api.js';
import { openDocs } from './doctabs.js';
import { solo } from './solo.js';
import { debounce } from './util.js';

const sent = new WeakMap();   // 탭 → 마지막으로 보낸 값

/** 탭의 위치를 바뀌었으면 바로 보낸다 — 고른 문서 탭의 문서와 위치, 열어 둔 문서 탭들(docs — D64). 탭을 닫기 전에도 부른다 (tabs.js) */
export function rememberPosition(tab) {
  if (solo) return Promise.resolve();   // 다음 실행에 되살릴 문서 탭은 메인 창의 것이다 (D95)
  // 고른 문서 탭이 문서가 아니면(코드·폴더 개요) 가장 최근에 본 문서 탭의 것 — 문서 탭 목록은 그래도 남게
  const isDoc = (p) => p.current?.type === 'doc' && tab.fileMap.has(p.current.path);
  const pane = isDoc(tab.pane) ? tab.pane : tab.panes.filter(isDoc).sort((a, b) => (b.used || 0) - (a.used || 0))[0];
  // 지워졌거나 이름이 바뀐 문서('문서 없음' 화면)는 보내지 않는다 (서버가 404 로 거절한다)
  if (S.config.restore_last === false || !pane) return Promise.resolve();
  const body = { p: tab.id, path: pane.current.path, scroll: Math.round(pane.scroller.scrollTop), docs: openDocs(tab) };
  const key = JSON.stringify(body);
  if (sent.get(tab) === key) return Promise.resolve();
  sent.set(tab, key);
  return postJSON('/api/position', body).catch(() => { sent.delete(tab); });
}

/**
 * 사용자가 문서 탭을 모두 닫아 폴더 개요만 남았다 (doctabs.js 의 'docs-closed' — 마지막 문서 탭 닫기 D127, 열린 문서 모두 닫기 D133):
 * 서버가 기억한 마지막 문서와 문서 탭 목록을 비운다 — 다음에 열 때 닫은 문서들이 돌아오지 않게. 위의 기록은 폴더 개요면 아무것도
 * 보내지 않으므로(처음 열 때·아직 그리지 않은 탭) 따로 둔다 — 폴더 개요를 그냥 보는 것으로는 비우지 않는다
 */
function forgetDocs(tab) {
  if (solo || S.config.restore_last === false || !tab) return;
  sent.delete(tab);
  postJSON('/api/position', { p: tab.id, path: '', docs: [] }).catch(() => {});
}

export function initPosition() {
  on('docs-closed', forgetDocs);
  // 모든 탭을 본다 — 스크롤하고 1.5초 안에 다른 탭을 골라도 앞 탭의 위치가 남게 (숨은 탭의 위치는 바뀌지 않으니 보내지 않는다)
  const later = debounce(() => S.tabs.forEach(rememberPosition), 1500);
  on('view', later);
  on('rendered', later);
  on('doctabs', later);   // 고르지 않은 문서 탭을 닫음 (doctabs.js)
  // 스크롤은 거품처럼 올라오지 않으므로 잡기 단계에서 듣는다
  document.addEventListener('scroll', (e) => { if (e.target.classList?.contains('lec-scroll')) later(); }, { capture: true, passive: true });
}
