// 독립창 (D95): 프로젝트의 문서를 별도 창에서 본다. 메인 창과 같은 화면이고 주소의 ?solo=<프로젝트 id>&w=<창 id> 만 다르다.
// 문서 탭 줄과 문서가 기본이고 사이드바는 Ctrl+B 로 꺼낸다. 프로젝트 탭·터미널·메모·설정은 메인 창에만 있다.
// 서버의 탭 목록·문서 탭 기록·설정은 메인 창의 것이라 여기서 바꾸지 않는다 (tabs·position·api). 창을 숨기고 닫는 것은 서버 쪽 windows.py.
// 다른 모듈이 모두 읽으므로 아무것도 불러오지 않는다 (순환이 생기지 않게).

const q = new URLSearchParams(location.search);

/** 독립창이면 {project, id, deck(슬라이드 창 — D96), start: {type, path}, top}, 메인 창이면 null */
export const solo = q.get('solo') ? {
  project: q.get('solo'),
  id: q.get('w') || '',
  deck: q.get('deck') === '1',
  start: { type: q.get('type') === 'code' ? 'code' : 'doc', path: q.get('path') || '', hash: q.get('hash') || undefined, line: Number(q.get('line')) || undefined },
  top: Number(q.get('top')) || 0,
} : null;

/** 독립창을 여는 주소의 뒤쪽 */
export function soloQuery(project, target, top = 0, deck = false) {
  const id = [...crypto.getRandomValues(new Uint8Array(8))].map((b) => b.toString(16).padStart(2, '0')).join('');
  const fields = { solo: project, w: id, type: target.type, path: target.path, top: String(Math.round(top)) };
  if (target.hash) fields.hash = target.hash;
  if (target.line) fields.line = String(target.line);
  if (deck) fields.deck = '1';
  return `?${new URLSearchParams(fields)}`;
}
