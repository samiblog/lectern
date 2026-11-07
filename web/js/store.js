// 앱 상태와 간단한 이벤트 버스.
//
// 이벤트 목록 (emit 하는 곳 → on 하는 곳)
//   open             {type:'doc'|'overview', path, hash?} 선택된 탭에서 화면 이동 요청 (tree·palette·doc 링크·overview → nav)
//   view             선택된 탭의 이동이 끝남, 또는 다른 탭을 고름          (nav·panes → tree·main·status·position)
//   pane             다른 칸을 고름 = 다른 탭을 고름 (pane)               (panes → toc·status·find·spotlight·diffmark)
//   tab              다른 탭을 고름 {tab, prev} — 사이드바를 그 탭의 것으로 (tabs → tree·recent·search·parts)
//   tree             선택된 탭의 트리 데이터를 새로 받음                  (project → tree·search)
//   panel            사이드바 탭(파일·최근 변경·검색·모아 보기)을 바꿈 (이름) (tree → others·recent·parts)
//   parts            모아 보기를 엶 {path(범위 폴더), kind?, mode?('files' = 파일 종류)} (overview·tree·others → parts)
//   show-sidebar     사이드바가 숨어 있으면 보인다                         (parts → main)
//   others           탭(tab)의 문서 외 파일이 생기거나 지워짐             (watch → others·search·parts)
//   touched          탭(tab)의 문서 외 파일이 생기거나 지워지거나 고쳐짐   (watch → recent)
//   titles           '제목' 버튼(파일 이름 / 문서 제목)이 바뀜             (tree → recent·search·others)
//   changed          '변경됨' 표시 집합이 바뀜 (어느 탭이든)              (watch·doc → tree·tabs)
//   refresh-view     칸(pane, 없으면 모든 탭)을 같은 스크롤 위치로 다시 그림 (watch·theme·settings → nav)
//   open-window      문서를 독립창에서 엶 {type, path, hash?, line?} (tree·docmenu → doctabs, D95)
//   window-news      다른 창들과 받은 문서 {windows?, inbox?} (watch → doctabs, D95)
//   file-renamed     다른 창에서 바뀐 이름 {tab, path, to} (doctabs → rename, D96)
//   file-deleted     다른 창에서 지운 문서 {tab, path} (doctabs → deletedoc, D104)
//   delete-doc       트리의 우클릭 '문서 삭제…' {path} (tree → deletedoc, D104)
//   refresh-auto     감시가 알린 칸(pane) — 글이 같으면 그대로, 끄는 중이면 놓을 때 (watch → nav, D94)
//   rendered         칸(pane)의 문서/개요 렌더링 완료                     (doc·htmldoc·overview → find·spotlight·position)
//   synced           변경 확인 주기 완료                                  (watch → status)
//   reveal           문서 속 요소로 가기 직전 (목차·찾기·앵커·바뀐 곳)   (fold.unfoldTo·codeview.goToLine·toc → spotlight — 장, 현재 위치)
//   text-size        글자 크기가 바뀜                                     (textsize → htmldoc·tablefit)
//   doc-width        툴바의 문서 폭이 바뀜                                (docwidth → htmldoc, D68)
//   term-colors      설정 '터미널 색을 스타일에 맞춤'이 바뀜              (settings → terminal)
//   term-place       설정 '터미널 자리'가 바뀜                            (settings → terminal, D52)
//   user-styles      내 스타일 목록이 바뀜 (파일이 생기거나 고쳐짐)        (theme → settings, D53)
//   edit             편집 모드를 엶 {line?} — 우클릭 메뉴. 편집 중이면 그 줄로 (docmenu·search → editor, D54·D55)
//   editor           칸(pane)의 편집 상자가 열리거나 닫힘                 (editor → basket — 커서 자리로 보내기, D63)
//   new-doc          새로 만들기 {dir} — 우클릭 '새 문서 만들기…'   (tree·others·tabs → newdialog, D105)
//   new-folder       새 폴더 {dir} — 우클릭 '새 폴더 만들기…'   (tree·others·tabs → newdialog, D114)
//   doctabs          탭(tab)의 문서 탭을 닫음 — 다음 실행에 되살릴 목록     (doctabs → position, D64)
//   rename           이름 바꾸기 {path} — 파일 우클릭 '이름 바꾸기…'·F2       (tree·others → rename, D66)
//   doctab-list      선택된 탭(tab)의 문서 탭 줄을 다시 그림 — 탭이 생기거나 닫히거나 이름·고른 탭이 바뀜 (doctabs → spread, D73)
//   tabs             열린 탭 목록이 바뀜 (열기·닫기·서버에 맞추기)          (tabs → gather·spread)
//   terms            어느 탭의 셸이 생기거나 끝나거나 화면이 치워짐         (terminal → gather)
//   term-panel       오른쪽 터미널 패널을 열거나 감춤 (open)                (terminal → spread, D73)
//   term-paste       글(text)을 선택된 탭의 터미널에 붙여 넣음 — 우클릭 메뉴의 터미널 버튼 (ui → terminal, D51)
//   term-paste-stay  term-paste 와 같고 초점은 문서에 둠 — Ctrl+Shift+→ (spotlight → terminal, D79·D97)
//   line-edit        F2·한 줄 하이라이트에서 Shift+Enter — 그 단위(unit)를 한 줄 편집 (spotlight → lineedit, D76)
//   jump             같은 문서 안에서 뛰기 직전 — 뒤로 기록에 남김 (toc·doc·find·parts·search → nav, D78)
//   go-line          Ctrl+G 의 줄로 가기 {line} (palette·notes → search, D91)
//   new-note         새 메모로 보내기 {title?, body, path?, line?, end?} (docmenu·parts·basket → notes, D92)
//   note-send        메모를 문서로 보내기 {text, label} (notes → basket, D92)
//   history          뒤로 기록이 바뀜 — 화면은 그대로 (nav → main)
// 팔레트(palette.js)는 이벤트를 듣지 않고 열 때마다 S.files 를 읽는다.

const metaMode = document.querySelector('meta[name="lec-mode"]')?.content;

export const S = /** @type {AppState} */ ({
  mode: metaMode && !metaMode.includes('{') ? metaMode : 'browser', // 'app' | 'browser'
  sep: '\\',           // 서버 OS의 경로 구분자
  config: {},          // /api/config
  tabs: [],            // 열린 프로젝트 탭, 왼쪽부터 (tabs.js — 탭마다 폴더·트리·사이드바 상태·문서 칸)
  tab: null,           // 선택된 탭 (없으면 시작 화면)
  panes: [],           // 문서 칸 목록 — 탭마다 하나와 시작 화면 (panes.js — 칸마다 화면·뒤로/앞으로 기록·렌더링 순번)
  pane: null,          // 선택된 칸 (선택된 탭의 칸, 탭이 없으면 시작 화면)
  view: null,          // 선택된 칸의 화면 {type, path}
  samples: null,       // 예제 프로젝트 폴더 (/api/state — 없으면 null, D57)
  writingGuide: '',    // AI 용 작성 안내 파일 (web/help/writing.md, 화면 언어에 맞춘 것)
  slidesGuide: '',     // AI 용 Lectern 슬라이드 작성 안내 (web/help/slides.md — D96)
  skillsDir: '',       // Claude Code 스킬이 든 폴더 (skills/ — D98)
});

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
