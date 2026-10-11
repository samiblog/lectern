// 앱 상태와 간단한 이벤트 버스.
//
// 이벤트 목록 (emit 하는 곳 → on 하는 곳)
//   open             {type:'doc'|'overview', path, hash?} 화면 이동 요청  (tree·palette·doc 링크·overview → nav)
//   view             이동이 끝남                                        (nav → tree·main·status)
//   tree             트리 데이터를 새로 받음                             (project·main → tree)
//   changed          '변경됨' 표시 집합이 바뀜                            (watch·doc → tree)
//   refresh-view     지금 화면을 같은 스크롤 위치로 다시 그림             (watch·theme → nav)
//   rendered         문서/개요 렌더링 완료                               (doc·overview → find)
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
  view: null,          // 지금 화면 {type, path}
  history: [],         // 뒤로/앞으로 기록
  hIndex: -1,
  renderId: 0,         // 늦게 끝난 렌더링이 새 화면을 덮지 않도록 하는 순번
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
