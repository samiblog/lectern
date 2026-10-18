// 마지막 위치 기억: 창마다 보고 있는 문서와 스크롤 위치, 선택된 창을 서버에 알려 둔다 (POST /api/position).
// 다음에 그 폴더를 열면 main.js 가 그 창들을 되살린다 (nav.js 의 restorePanes). 설정 restore_last 가 꺼져 있으면 보내지 않는다.
// 설정 파일에 쓰므로 자주 쓰지 않게, 스크롤이 멈추고 1.5초 뒤에 한 번 보낸다. 폴더 개요를 보는 창은 기록하지 않는다.

import { S, on } from './store.js';
import { postJSON } from './api.js';
import { debounce } from './util.js';

let sent = '';

function send() {
  const docs = S.panes.filter((p) => p.current?.type === 'doc');
  if (S.config.restore_last === false || !docs.length) return;
  const body = {
    panes: docs.map((p) => ({ path: p.current.path, scroll: Math.round(p.scroller.scrollTop) })),
    active: Math.max(0, docs.indexOf(S.pane)),
  };
  const key = `${S.root}|${JSON.stringify(body)}`;
  if (key === sent) return;
  sent = key;
  postJSON('/api/position', body).catch(() => { sent = ''; });
}

export function initPosition() {
  const later = debounce(send, 1500);
  on('view', later);
  on('panes', later);
  // 스크롤은 거품처럼 올라오지 않으므로 잡기 단계에서 듣는다 (모든 창)
  document.addEventListener('scroll', (e) => { if (e.target.classList?.contains('lec-scroll')) later(); }, { capture: true, passive: true });
}
