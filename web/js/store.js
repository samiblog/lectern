// 앱 상태와 간단한 이벤트 버스.
//
// 이벤트 목록 (emit 하는 곳 → on 하는 곳)
//   open             {type:'doc'|'overview', path, hash?, side?} 화면 이동 요청. side 면 오른쪽 새 창에 (tree·palette·doc 링크·overview → nav)
//   view             선택된 창의 이동이 끝남, 또는 다른 창을 고름        (nav·panes → tree·main·status·position)
//   pane             다른 창을 고름 (pane)                               (panes → toc·status·find·spotlight·diffmark)
//   panes            창이 생기거나 닫힘                                  (panes → position)
//   tree             트리 데이터를 새로 받음                             (project·main → tree·panes)
//   changed          '변경됨' 표시 집합이 바뀜                            (watch·doc → tree)
//   refresh-view     창(pane, 없으면 모든 창)을 같은 스크롤 위치로 다시 그림 (watch·theme·settings → nav)
//   rendered         창(pane)의 문서/개요 렌더링 완료                    (doc·htmldoc·overview → find·spotlight)
//   synced           변경 확인 주기 완료                                 (watch → status)
//   project-switched 서버의 열린 폴더가 바뀜                            (watch → main)
//   reveal           문서 속 요소로 가기 직전 (목차·찾기·앵커·바뀐 곳)  (fold.unfoldTo → spotlight)
//   text-size        글자 크기가 바뀜                                    (textsize → htmldoc)
// 팔레트(palette.js)는 이벤트를 듣지 않고 열 때마다 S.files 를 읽는다.

const metaMode = document.querySelector('meta[name="lec-mode"]')?.content;

export const S = {
  mode: metaMode && !metaMode.includes('{') ? metaMode : 'browser', // 'app' | 'browser'
  root: null,          // 열린 폴더 전체 경로 (서버 기준)
  name: '',            // 폴더 이름
  sep: '\\',           // 서버 OS의 경로 구분자
  watch: '',           // 변경 감시 방식: watchdog | polling
  tree: [],            // /api/tree 결과
  files: [],           // 트리의 모든 md 파일 노드
  fileMap: new Map(),  // path → 파일 노드
  dirs: new Set(),     // 폴더 경로 집합 ('' = 루트)
  config: {},          // /api/config
  panes: [],           // 문서 창(칸) 목록, 왼쪽부터 (panes.js — 칸마다 화면·뒤로/앞으로 기록·렌더링 순번)
  pane: null,          // 선택된 창
  view: null,          // 선택된 창의 화면 {type, path}
  changed: new Set(),  // 열어 보기 전에 바뀐 문서 경로
  open: new Set(),     // 트리에서 펼쳐진 폴더 경로
  seq: 0,              // 서버 변경 기록 순번
  lastSync: null,      // 마지막으로 변경을 반영한 시각
  reloading: false,
};

const handlers = new Map();

export function on(event, fn) {
  if (!handlers.has(event)) handlers.set(event, new Set());
  handlers.get(event).add(fn);
}

export function emit(event, data) {
  for (const fn of handlers.get(event) || []) {
    try {
      const r = fn(data);
      if (r && typeof r.catch === 'function') r.catch((e) => console.error(`[${event}]`, e));
    } catch (e) {
      console.error(`[${event}]`, e);
    }
  }
}
