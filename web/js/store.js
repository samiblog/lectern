// 앱 상태와 간단한 이벤트 버스.
//
// 이벤트 목록 (emit 하는 곳 → on 하는 곳)
//   open             {type:'doc'|'overview', path, hash?} 선택된 탭에서 화면 이동 요청 (tree·palette·doc 링크·overview → nav)
//   view             선택된 탭의 이동이 끝남, 또는 다른 탭을 고름          (nav·panes → tree·main·status·position)
//   pane             다른 칸을 고름 = 다른 탭을 고름 (pane)               (panes → toc·status·find·spotlight·diffmark)
//   tab              다른 탭을 고름 {tab, prev} — 사이드바를 그 탭의 것으로 (tabs → tree·search)
//   tree             선택된 탭의 트리 데이터를 새로 받음                  (project → tree·search)
//   changed          '변경됨' 표시 집합이 바뀜 (어느 탭이든)              (watch·doc → tree·tabs)
//   refresh-view     칸(pane, 없으면 모든 탭)을 같은 스크롤 위치로 다시 그림 (watch·theme·settings → nav)
//   rendered         칸(pane)의 문서/개요 렌더링 완료                     (doc·htmldoc·overview → find·spotlight·position)
//   synced           변경 확인 주기 완료                                  (watch → status)
//   reveal           문서 속 요소로 가기 직전 (목차·찾기·앵커·바뀐 곳)   (fold.unfoldTo → spotlight)
//   text-size        글자 크기가 바뀜                                     (textsize → htmldoc)
// 팔레트(palette.js)는 이벤트를 듣지 않고 열 때마다 S.files 를 읽는다.

const metaMode = document.querySelector('meta[name="lec-mode"]')?.content;

export const S = {
  mode: metaMode && !metaMode.includes('{') ? metaMode : 'browser', // 'app' | 'browser'
  sep: '\\',           // 서버 OS의 경로 구분자
  config: {},          // /api/config
  tabs: [],            // 열린 프로젝트 탭, 왼쪽부터 (tabs.js — 탭마다 폴더·트리·사이드바 상태·문서 칸)
  tab: null,           // 선택된 탭 (없으면 시작 화면)
  panes: [],           // 문서 칸 목록 — 탭마다 하나와 시작 화면 (panes.js — 칸마다 화면·뒤로/앞으로 기록·렌더링 순번)
  pane: null,          // 선택된 칸 (선택된 탭의 칸, 탭이 없으면 시작 화면)
  view: null,          // 선택된 칸의 화면 {type, path}
};

// 선택된 탭의 프로젝트 값. 선택된 탭만 다루는 모듈(트리·팔레트·검색 등)은 S.root·S.files 처럼 읽고 쓰면 된다.
// 모든 탭을 다루는 코드(렌더러·자동 새로고침)는 탭 객체(pane.tab)를 쓴다. 탭이 없으면 빈 값
const PROJECT = {
  root: null,          // 폴더 전체 경로 (서버 기준)
  name: '',            // 폴더 이름
  watch: '',           // 변경 감시 방식: watchdog | polling
  tree: [],            // /api/tree 결과
  files: [],           // 트리의 모든 문서 파일 노드
  fileMap: new Map(),  // path → 파일 노드
  dirs: new Set(),     // 폴더 경로 집합 ('' = 루트)
  changed: new Set(),  // 열어 보기 전에 바뀐 문서 경로
  open: new Set(),     // 트리에서 펼쳐진 폴더 경로
  seq: 0,              // 서버 변경 기록 순번
  lastSync: null,      // 마지막으로 변경을 반영한 시각
};
for (const key of Object.keys(PROJECT)) {
  Object.defineProperty(S, key, {
    get: () => (S.tab ? S.tab[key] : PROJECT[key]),
    set: (value) => { if (S.tab) S.tab[key] = value; },
    enumerable: true,
  });
}

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
