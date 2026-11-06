# JS 모듈

`web/js/` 의 모듈이 하는 일. 새 모듈을 만들면 한 행을 더한다 (`tests/test_rules.py` 가 빠진 것과 남은 것을 잡는다).

| JS 모듈 | 역할 |
|---|---|
| bootguard.js | 시작 스크립트를 못 받으면 다시 불러옴 (D81 — 일반 스크립트, `data-boot` 를 단 것이 대상, 세 번 뒤 `#lec-boot-fail`) |
| main.js | 초기화, 툴바, 단축키 (발표 중이면 키를 모두 present.js 로) |
| store.js | 상태 `S` 와 이벤트 버스 (`on`/`emit`). 이벤트 목록이 파일 머리에 있음. `S.root`·`S.tree` 등은 선택된 탭의 값 |
| tabs.js | 프로젝트 탭 — 탭 막대, 폴더 열기(새 탭)·닫기·고르기, 처음 고를 때 트리·마지막 문서, 서버의 탭 목록에 맞추기, 시작 화면 |
| panes.js | 문서 칸 — 문서 탭마다 하나를 겹쳐 두고 선택된 칸만 보임, 선택된 칸에 id 옮겨 달기 |
| solo.js | 독립창 (D95) — 주소의 `?solo=` 를 읽어 `solo` 로 알린다. 다른 모듈이 모두 읽으므로 아무것도 불러오지 않는다 |
| doctabs.js | 문서 탭 (D64·D67) — 문서 탭 줄과 오른쪽 끝 열린 문서 탭 목록(`listMenu`), 'open' 이벤트를 받아 여는 곳 정하기(`openTarget` — 열린 탭으로·새 탭·지금 탭, 두 번 누르기는 `openTwice` — 지금 탭에서 연 것을 새 탭으로), 새 탭(`openInNewTab` — 20개가 차면 가장 오래 안 본 탭), 닫기, Alt+1~8·Alt+9, 다음 실행에 되살리기(`restoreDocTabs`·`openDocs`) |
| nav.js | 화면 이동, 뒤로/앞으로 (D78 — 같은 문서 안에서 뛴 자리도: `noteJump`·`keepPlace`·`showPlace`), 다시 그리기 (칸마다), 탭을 처음 열 때 마지막 문서·위치 |
| doc.js | 문서 렌더링 후처리 (링크·이미지·표·코드·콜아웃·frontmatter) |
| markdown.js | markdown-it 설정, 수식 규칙, mermaid 코드 블록 |
| overview.js | 폴더 개요 화면 |
| tree.js | 사이드바 탭 바꾸기·트리·필터·우클릭 메뉴 |
| recent.js | 사이드바 '최근 변경' 탭 — '문서'·'코드'·'자료' 버튼, 문서(트리)와 코드·자료(GET /api/others/recent)를 섞어 최근 것부터 (D50) |
| others.js | 사이드바 파일 탭의 묶음 — 종류별 보기는 위에서부터 '문서'(트리)·'코드'·'자료' 세 묶음(접기·분리선)과 코드·자료의 탐색기 같은 목록 (GET /api/others 를 화면이 나눔), 폴더 보기는 문서·파일·코드를 합친 한 트리. 다른 탭의 파일 행 동작(`bindFileRows`)·파일 메뉴도 여기 |
| icons.js | 사이드바 목록의 파일 종류 아이콘 (확장자 → 종류, md·html 은 문서) |
| terminal.js | 오른쪽 터미널 — xterm.js(처음 열 때 불러옴), 탭마다 터미널 여러 개(`tab.terms`·고른 것 `tab.term` — 머리줄의 터미널 탭·+·×, 5개까지, D69), 긴 폴링으로 출력·키 입력 보내기, 패널 열기·닫기·폭, 탭을 닫기 전에 묻기 |
| spread.js | 모두 펼치기 (D73) — 문서 탭 줄 오른쪽 끝 ▦, `html.spread-on` 이면 `#lec-main` 이 격자·`#lec-panes` 는 display: contents 라 선택된 탭의 칸(`.sp-cell`)이 그대로 격자의 칸, 자리는 `layoutOf`(터미널은 오른쪽 아래 한 칸 — 오른쪽 패널 `#lec-term` 그대로), 칸 머리(`.sp-head`), 칸을 누르면 `selectDocTab`, 펼치면서 연 터미널만 끝낼 때 감춤 |
| gather.js | 터미널 모음 — 툴바 버튼, 탭마다 칸 하나의 격자(문서 화면 위를 덮음), 칸으로 각 탭의 고른 터미널 화면을 옮겨 보이고 닫으면 되돌림(터미널이 여럿이면 칸 머리의 번호로 — D69), 칸 크게·이 프로젝트로·다시 시작, '실행 중' 표시 |
| editor.js | 편집 모드 (D54) — 칸 위를 덮는 CodeMirror 5 (처음 편집할 때 불러옴), 저장·그사이 바뀜 묻기·저장하지 않은 것 묻기 (nav 의 leave guard, 탭 닫기, POST /api/editing), 위치 잇기 (D55 — 아래 화면을 편집기의 지금 보는 곳에 맞춰 둠, 목차·모아 보기·검색에서 고르면 편집기가 그 줄로) |
| editsync.js | 위치 잇기의 계산 (D55) — 읽는 화면의 원문 줄 자리(md 의 data-lines·코드의 줄·html 의 제목), 줄 ↔ 화면 높이, 편집으로 늘거나 준 줄 옮기기 |
| codeview.js | 코드 읽기 화면 (D43) — 코드 파일을 줄 번호·언어 색(highlight.js)으로, 보는 동안 수정 시각을 보고 다시 그림, '편집기로 열기'·'전체 복사'. 자료 파일(csv·tsv·txt·log, D60)도 — UTF-16·CP949 로도 읽고, csv·tsv 는 csvview.js 의 표 |
| csvview.js | CSV 표 (D60) — 머리행 어림, 열마다 거르기(`matcherOf`)·머리행 정렬·통계 줄(`statsOf`), 행은 `tr.cv-line[data-line]`(원문 줄). 요약 줄·계산 열(`st.calcs`, 열 머리 메뉴 `columnMenu`)·표 영역(`pickRegion`·`drawRegions`·`markRange`)·지금 보이는 표(`shownTable`) — D86 |
| outline.js | 코드 화면의 목차 — 언어마다 클래스·함수·메서드·구분 주석, 설정 파일은 키·섹션 (줄 단위 규칙), 확장자 → 언어 |
| notes.js | 프로젝트 메모 (D92) — 탭 막대 '메모'·Alt+M 의 오른쪽 패널, 카드(제목·본문·할 일·색·고정), 저장과 합치기. `tab.notes`, 'new-note' 로 더한다 |
| notesdata.js | 메모의 글 (D92, DOM 없음) — `.lectern/notes.md` ↔ 메모 목록, 할 일 줄 다루기 (`parseNotes`·`writeNotes`·`toggleTask`) |
| html.js | 자동 이스케이프 (D89, DOM 없음) — `html` 태그의 값은 글로 들어간다. 화면에 넣는 길은 `setHtml`·`addHtml`, 이미 안전한 HTML 은 `raw`, 결과는 `Safe`. 조각은 배열로 잇는다 |
| i18n.js | 화면 언어 (D46) — `t('한국어 문구', {값})` 와 index.html 글자 바꾸기(`translatePage`). 언어는 서버가 `<html lang>` 으로 준다 |
| help.js | 사용설명서(F1 — web/help/manual.md 를 사이드바·문서 위를 덮는 읽기 화면으로, 왼쪽 차례, Ctrl+F 는 설명서 안)와 단축키 표(툴바 '?', Ctrl+/). 단축키 목록 `SHORTCUTS` |
| watch.js | 1초 폴링으로 변경 반영 (모든 탭을 한 번에, 숨은 탭은 고를 때 다시 그림) |
| toc.js / find.js / palette.js | 목차(제목 아래에 표·그림 등 구성 요소, 종류 버튼) / 문서 안 찾기 / Ctrl+P (문서·코드 — 문서 탭 줄의 + 로 열면 새 탭에서, 맨 위에 '새 문서 만들기…') |
| fold.js | 제목을 눌러 절 접기·펴기 |
| spotlight.js | 현재 위치와 하이라이트 (D74·D75) — 현재 위치(`pane.here` 원문 줄, 삼각형 `.lec-here`, 누르기·↑·↓·스크롤 따라오기·'reveal'), 줄 하이라이트(`anchor`·`focus` 원문 줄 — Shift+누르기·끌기·Enter·↑·↓), 장 하이라이트(한 장만 그대로, ↑·↓·PageUp·PageDown 으로 앞뒤 장). 그 밖은 칸에 겹친 덮개(`.lec-spot`)가 회색으로 덮는다. 키는 `spotKey`(main.js 의 keydown — Shift+→ `sendLit`·Shift+← `copyLitRef`·Ctrl+C `copyLitSource`), 상태줄 `#lec-st-lit`. `litAt(y)` 로 우클릭 메뉴가 하이라이트한 곳의 선택 상자를 띄운다 (docmenu.js 의 `litMenu` — 코드 화면도) |
| lineedit.js | 한 줄 편집 (D76) — 'line-edit' 이벤트·본문 두 번 누르기(`onDoubleClick`)로 시작, 할 일 체크 칸(`onTaskClick`), `lineSlot` 의 Range 내용을 떼고 `.lec-line-edit` 칸을 넣음, 앞뒤 표시 잠금(`splitText`·`splitCode`·`splitRow`), 저장(`replaceLines` — 원문을 새로 받아 그 범위만, 밀렸으면 `locateLines`), ↑↓ 이어서, 되돌리기·다시 하기(`undoLineEdit`·`redoLineEdit` — main.js 의 Ctrl+Z·Ctrl+Y, 기록은 파일마다). 편집 중에는 `pane.lineEdit` (nav.refreshView 가 다시 그리기를 미룸) |
| lineunits.js | 줄 단위 (D75) — 화면(md·코드 화면)의 원문 줄과 그 자리 (`collectUnits` — 줄마다 가장 안쪽 `[data-lines]` 블록, 여러 줄 블록은 `\n` 자리로 나눈 Range, 코드는 줄, 표의 구분 줄 등은 이웃에), `unitAt`·`indexOfLine`·`markOf` |
| textsize.js | 툴바의 글자 크기 − 100% + (설정 font_scale, CSS 변수 --md-scale = 배율 × 기준 1.1 — D47) |
| lineops.js | 줄 구조 편집의 계산 (D83, DOM 없음) — 원문 줄 배열 → 바뀐 줄 배열 또는 `{error}`: 새 줄(`planNew`·`insertLine`), 나누기·합치기(`splitLine`·`joinLine`), 복제(`duplicateLine`), 레벨(`indentItem`·`outdentItem`), 옮기기(`moveLines`), 지우기(`deleteLines`), 저장할 범위(`diffRange`) |
| linefind.js | 밀린 줄 찾기 (D76, DOM 없음) — `locateLines`: 그 자리, 아니면 앞뒤 300줄 안에서 같은 줄들이 하나뿐일 때 그 자리 |
| linenums.js | 줄 번호 (D80) — 툴바 `#lec-btn-lines`·Alt+L(설정 line_numbers), 칸마다 스크롤 상자에 덮개 `.lec-gutter`, `collectUnits` 의 단위마다 원문 줄 번호, md 문서만 |
| docwidth.js | 툴바의 문서 폭 [좁게][폭 100%][넓게] (D68 — 설정 doc_width, CSS 변수 --md-wide 를 md 본문 max-width 에 곱함, '가득' = 칸 폭) |
| tablefit.js | 표 첫 열 넓히기 (D68) — 첫 열 때문에 높은 행이 있는 md 표의 첫 열 폭을 재어 정함 (`fitTables(view)` — doc.js 가 바꿔 끼운 뒤, 표 상자의 ResizeObserver·text-size 로 다시) |
| diffmark.js | 자동 새로고침 때 바뀐 블록 강조, 상태줄 '바뀐 곳' 버튼 |
| search.js | 사이드바 '검색' 탭 — 맨 위에 이름이 맞는 파일(문서·코드·자료), 그 아래 문서·코드 본문 검색 (서버는 lectern/search.py) |
| parts.js | 사이드바 '모아 보기' 탭 (캡션이 있으면 캡션이 이름, 우클릭은 Claude용 위치·원문 복사 — D61. 차트는 보일 때 그린 작은 그림, 할 일·링크·출처는 종류 아래 단추로 거르기, '문서 정보' 보기 — D62) — '문서 속 요소' / '파일 종류'(묶음마다 형식별 파일, 그림은 작은 그림 — D50). 문서 속 요소는 범위(프로젝트·폴더)의 문서를 화면 밖에서 그려 목차와 같은 규칙(`toc.js` 의 `readParts`)으로 구성 요소를 세고, 종류마다 문서별 목록(그림은 작은 그림 격자), 누르면 그 자리로 |
| settings.js / position.js | 설정 창 (톱니, Ctrl+,) / 탭마다 마지막 문서·스크롤 위치 기록 |
| pathlink.js | 본문 속 경로 표기(`src/app.py:42`) 자동 링크 |
| resize.js | 사이드바·목차 폭 조절 (경계 끌기, 두 번 누르면 기본 — 설정 sidebar_width·toc_width) |
| htmldoc.js | html 문서 보기 — 스크립트 없는 같은 출처 iframe (css/frame.css 를 넣는다) |
| docmenu.js | 본문 우클릭 메뉴 (텍스트·원문·표·그림 복사, Claude용 위치, 담기·보내기 — D63·D65) |
| basket.js | 담기·보내기 (D63·D65) — 조각 만들기(`snippetOf`), 사이드바 '담기' 탭(`tab.basket`), 보낼 곳 고르기 창(`#lec-insert` — 편집 중인 곳·새 문서·문서 탭에 열린 문서 → 자리, 새 문서 경로 — 새로 만들기 `askNewDoc` 도 이 창), `editor.js` 의 `insertIntoDoc` 으로 보내기, Claude 에 맡기기 요청 글 |
| rename.js | 이름 바꾸기 (D66) — 사이드바 파일의 우클릭 '이름 바꾸기…'·F2 (`rename` 이벤트), 이름을 묻는 창(`#lec-rename`), `POST /api/rename`, 바뀐 뒤 보던 문서 탭·뒤로 기록(`nav.renamePath`)·담은 조각을 새 이름으로 |
| newdoc.js | 새 문서 (D65) — 처음 경로(`newDocGuess`), 만들기(`createDoc` — `/api/new-doc` 으로 묻고 `/api/save` create 로 `# 제목`), 새 문서 탭에서 편집 모드로(`openCreated`) |
| snippet.js | 담은 조각 다듬기 (D63, DOM 없음) — 상대경로를 넣을 문서 기준으로(`rebase`), 각주 정의·이름(`noteDefs`), 제목 수준(`shiftHeadings`), 넣을 자리(`placeLine`·`levelAt`·`placeText`), 담은 곳 주석(`buildBody`) |
| theme.js | 문서 스타일 목록(THEMES)과 전환, 내 스타일(D53 — 3초마다 목록, 바탕 스타일 위에 #lec-user-css). 스타일 선택 목록도 이 표로 만들고, 설정 `theme_groups` 에 따라 용도별·분위기별·밝기별로 묶는다(GROUPINGS) |
| sideorder.js | 사이드바 목록의 차례 (D97): 폴더 먼저, 그 안은 이름순·시간순·형식순 (설정 side_sort) |
| slideops.js | 슬라이드의 원문 계산 (D96, DOM 없음): 칸 머리 줄·글자 크기 지시어, 장 더하기·복제·옮기기·지우기 |
| csssafe.js | 문서가 준 CSS 거르기 (D96): 브라우저 해석기로 읽고 정규화한 규칙만 슬라이드 틀 안에 가둔다 — 바깥 요청·앱을 건드리는 선택자·고정 위치를 뺀다 |
| slidelint.js | 슬라이드 점검의 앞단 (D96): 닫지 않은 주석·코드, 칸·구분 줄로 읽지 못한 줄, 지시어·칸 머리의 오타, 잘못된 격자, 바탕과 비슷한 글자, 옆으로 잘린 코드, 없는 그림 |
| slidetools.js | 슬라이드 도구 (D96): 상태줄의 구조 보기(숨은 줄 꼬리표)와 점검(넘침·잘못 쓴 칸 목록) |
| slides.js | 발표 문서 (D59·D96) — 맨 앞 설정 marp: true 읽기(`readDeck`), markdown-it 규칙 `slideRule`(줄마다 `.lec-slide-wrap > .lec-slide-frame > section.lec-slide`, 주석 → Marp 지시어·발표자 노트), 다듬기(배경 그림·그림 크기·style: CSS 범위·▶), 넘침 맞추기(`fitSlide`), 칸 폭에 맞춘 배율(`--slide-scale`), 상태줄 '문서로 보기'·'발표' |
| present.js | 발표 모드 (D59) — `#lec-present` 에 슬라이드를 복제해 창 전체에, 넘기기·N 노트·F 전체 화면·Esc (키는 main.js 가 맨 먼저 `presentKey` 로) |
| tabledata.js | 표 읽기 (D86, DOM 없음) — 구분자 어림(`delimiterOf`)·RFC 4180 읽기(`parseCsv`)·숫자(`numberOf`)·값 없는 칸(`isMissing`)·시점(`parseTime`)·주기(`frequencyOf`)·시간 열(`findTimeColumn`)·단위(`unitInfo`)·표 → 계열(`readTable`)·표 영역(`findRegions`·`reshapeRegion`·`regionOfLines`)·계산 열(`calcValues`) |
| quickchart.js | 빠른 차트 (D86) — `#lec-chart` 창 (`openChart({title, headers, rows, caption})`, 움직이는 ECharts — 문서 속 차트와 따로), 표 요소 읽기(`domTable`) |
| charts.js | 차트 (D56) — `pre.lec-chart`(markdown.js 가 ```vega-lite·```vega·```echarts·```plotly·```dot 를 바꾼 자리)를 Vega-Lite·ECharts·Plotly·Graphviz 로 SVG 를 그려 넣음. 라이브러리는 처음 쓸 때 불러옴, 설정은 JSON(따옴표 없는 키 등도 — `parseSpec`, 함수는 안 됨), 색은 `mermaidTheme()`, 문서 폭을 따르는 것은 폭이 바뀌면 다시 그림 |
| mermaid.js / ui.js / status.js / util.js / api.js / project.js | 보조 |
