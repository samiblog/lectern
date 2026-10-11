// 마지막 위치 기억: 보고 있는 문서와 스크롤 위치를 서버에 알려 둔다 (POST /api/position).
// 다음에 그 폴더를 열면 main.js 가 그 문서와 위치로 연다. 설정 restore_last 가 꺼져 있으면 보내지 않는다.
// 설정 파일에 쓰므로 자주 쓰지 않게, 스크롤이 멈추고 1.5초 뒤에 한 번 보낸다.

import { S, on } from './store.js';
import { postJSON } from './api.js';
import { $, debounce } from './util.js';

let sent = '';

function send() {
  if (S.config.restore_last === false || S.view?.type !== 'doc') return;
  const scroll = Math.round($('#lec-content').scrollTop);
  const key = `${S.root}|${S.view.path}|${scroll}`;
  if (key === sent) return;
  sent = key;
  postJSON('/api/position', { path: S.view.path, scroll }).catch(() => { sent = ''; });
}

export function initPosition() {
  const later = debounce(send, 1500);
  on('view', later);
  $('#lec-content').addEventListener('scroll', later, { passive: true });
}
