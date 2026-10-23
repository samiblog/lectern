# Lectern — Claude Code 작업 지침

Lectern(렉턴, 독서대)은 Windows용 로컬 문서 뷰어다. Claude Code·Claude가 프로젝트 폴더에 만든 문서를 **기계가 아닌 사람이** 한눈에 훑어보고 읽는 것이 목적이고, **보기 전용**이다.
Markdown(`.md`)과 HTML(`.html`) 문서를 본다. HTML은 문서로 보기만 하고 스크립트는 돌리지 않는다 (D27). 문서 형식은 서버가 `scanner.DOC_TYPES`, 화면이 `util.js` 의 `isMd`·`isHtml` 로 정한다 (형식을 더하면 둘 다).
구성: Python(pywebview 창 + Flask 로컬 서버) + 빌드 단계 없는 순수 JS(ES modules).

현재 버전 0.13.1 (v0.13.1 = 화면의 이름·설명 점검 — 툴바 '문서 열기', '박스글'·'인터넷 그림'으로 통일 등. v0.13.0 = 사이드바 '모아 보기' 탭 — 프로젝트(또는 폴더)의 표·그림·박스글·다이어그램·코드·수식을 종류마다 문서별로, 폴더 개요 버튼·폴더 우클릭으로도. v0.12.0 = 터미널 모음 — 탭 막대 오른쪽 끝 버튼·`` Ctrl+Shift+` `` 로 열린 프로젝트들의 터미널을 한 화면에 격자로, 셸에서 띄운 프로그램이 Ctrl+C 로 멈추지 않던 것 고침. v0.11.0 = 목차의 제목 아래에 그 절의 표·그림·박스글·다이어그램·코드·수식, 누르면 그 자리로, 종류 버튼으로 보이고 감추기. v0.10.1 = 터미널 색이 문서 스타일을 따름, 설정 창에서 끄면 늘 어둡게. v0.10.0 = 오른쪽 터미널 — 프로젝트 탭마다 PowerShell 하나를 그 폴더에서, 툴바 버튼·`` Ctrl+` ``. v0.9.1 = 프로젝트 탭 강조 — 크고 굵은 글자, 폴더 아이콘, 선택된 탭 바탕색. v0.9.0 = 사이드바 이름 앞 종류 아이콘, 종류별·폴더 보기 고르기('폴더' 버튼). v0.8.0 = 사이드바 '파일' 목록 — 문서 트리 아래 분리선 너머에 문서가 아닌 파일을 탐색기처럼, 두 번 누르면 열기(실행하지 않음). v0.7.1 = 트리는 파일 이름, 마우스를 올리면 문서 제목. v0.7.0 = 프로젝트 탭 — 폴더마다 탭 하나, 탭을 누르면 트리와 문서가 함께 바뀜, 창은 하나(또 실행하면 떠 있는 창에 탭으로). v0.6.0 의 창 나누기는 걷었다. v0.6.0 = math·latex 코드 블록 수식. v0.5.0 = 글자 크기 −·+ 와 장 하이라이트. v0.4.0 = 스타일 24종과 목록 묶는 방식 3가지. v0.3.2 = 전체 점검 후 수정 — 보안 3건 포함. ROADMAP 2·3·4단계 기능: 바뀐 부분 강조, 전체 검색, 설정 창·마지막 위치, HTML 문서, 절대경로, 사이드바 폭, 찾기 개선, 우클릭 2차, 경로 자동 링크, 인쇄, 트리 캐시, html 글자 바탕·앱 UI가 스타일을 따름). 남은 것은 Windows 실기 점검(2-1). 다음 할 일은 `docs/ROADMAP.md` 의 "다음 단계"에서 고른다.

## 반드시 지킬 원칙

1. **보기 전용.** 사용자 파일을 만들거나 고치거나 지우는 기능을 넣지 않는다. 디스크에 쓰는 것은 `%APPDATA%\Lectern\config.json` 하나뿐이다. **예외는 오른쪽 터미널(D38)이다**: 사용자가 직접 친 명령이 하는 일은 Lectern 이 한 것이 아니다. 대신 문서·링크·다른 기능이 셸로 명령을 보내는 길은 만들지 않는다.
2. **로컬 전용.** 앱이 스스로 외부에 요청하지 않는다 (CDN·웹폰트·분석·업데이트 확인 모두 금지). html 문서도 같다 — 서버가 `/doc/*.html` 에 붙이는 CSP가 스크립트·연결·인터넷 CSS·글꼴을 막고 그림만 `external_images` 를 따르게 한다 (D27). JS 라이브러리는 `web/vendor/` 에 들어 있다. **예외는 문서 속 외부 이미지 하나뿐**이다: 설정 `external_images`(기본 켜짐)가 켜져 있으면 `http(s)` 이미지를 referrer 없이 불러오고, 실패·15초 초과면 링크로 바꾼다 (D19). `doc.js` 의 DOMPurify 훅이 모든 `src` 를 떼어 두었다가 허용된 이미지에만 다시 주고, 그 밖에 그림을 부르는 길(`srcset`·`poster`·표의 `background`·SVG `image` 의 href·style 과 SVG 속성의 `url()`·`image-set()`)은 지운다. 놓친 길은 서버가 `/` 에 붙이는 CSP(`img-src`, D20)가 막는다. `tools/ui_smoke.py` 가 외부 요청이 `<img>` 뿐인지 확인한다.
3. **선택한 폴더와 그 하위만.** 서버는 프로젝트 밖 경로와 숨김 경로를 404로 막는다. 경로 검사는 반드시 `lectern/scanner.py` 의 `resolve_inside()` 를 거친다. 이 함수는 `resolve()` 전에 글자만으로 root 안인지 먼저 본다 — `\\서버\공유` 를 `resolve()` 하면 Windows 가 그 서버에 접속해 로그인 정보(NTLM)를 건넨다 (D29).
4. **숨김 제외.** 이름이 `.`으로 시작 / Windows 숨김·시스템 속성 / 심볼릭 링크·정션 / 제외 폴더(`node_modules` 등) / 문서가 없는 폴더는 트리에 나오지 않는다. html 은 앱 소스·빌드 폴더(`src`·`public`·`static`·`templates`·`web`·`www`·`frontend`·`out`) 안에서는 문서로 보지 않는다.
5. **코드 파일을 실행하지 않는다.** `os.startfile` 은 `.py`, `.js`, `.bat` 등을 실행해 버린다. 문서 속 링크는 `lectern/osutil.py` 의 `open_path()` 만 쓴다 (안전한 형식만 기본 앱, 나머지는 편집기나 탐색기). 프로그램은 이름만으로 띄우지 않는다 — Windows 는 현재 폴더에서 먼저 찾는데, `run.bat .`·탐색기 우클릭으로 띄우면 현재 폴더가 열린 프로젝트다 (D29). 터미널은 사용자가 친 명령만 돌린다 (D38) — 셸은 전체 경로로 띄우고, 셸에 글자를 보내는 API 는 사용자의 키 입력을 받는 `POST /api/term/input` 하나뿐이다.
6. **단순함 유지.** 레이아웃은 왼쪽 트리 하나 (툴바 아래 프로젝트 탭 막대 — 탭은 프로젝트만, 문서 탭은 하지 않는다, D34. 오른쪽 터미널은 열 때만, D38. 탭 막대 끝의 '터미널 모음'은 탭이 아니라 화면을 덮는 보기다, D40). 번들러·프레임워크(React, Vite 등)를 들이지 않는다. `docs/ROADMAP.md` 의 "하지 않기로 한 것"은 사용자가 다시 요청하기 전에는 넣지 않는다.

## 실행과 확인

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt

python app.py samples              :: 창으로 실행 (Lectern 창이 떠 있으면 그 창에 탭으로 넘기고 끝남)
python app.py --browser samples    :: 개발용: http://127.0.0.1:8765 를 일반 브라우저로 (dev.bat)
python app.py --debug samples      :: 창 + 개발자 도구 (F12, 기본 Ctrl+F 등도 켜짐). --browser 와 함께 떠 있는 창에 넘기지 않고 따로 뜬다
python -m pytest -q                :: 단위 테스트 (Windows가 아니어도 돎)
python tools/ui_smoke.py           :: 화면 회귀 점검 (playwright 필요, 캡처는 ui-shots/)
build.bat                          :: 테스트 후 dist\Lectern\Lectern.exe, Inno Setup 이 있으면 dist\Lectern-버전-setup.exe
```

변경을 마치면 최소한 `pytest` 를 돌리고, `web/` 을 고쳤다면 `tools/ui_smoke.py` 도 돌린다.
Windows 고유 동작(숨김 속성, 정션, 폴더 대화상자, 편집기 열기, WebView2)은 자동 테스트가 없으니 `docs/TESTING.md` 의 수동 점검표를 따른다.

## 폴더 구조

```
app.py                  진입점: 인자 처리, 서버 스레드, pywebview 창
lectern/
  state.py              열린 프로젝트들(탭마다 Project — 감시·변경 기록·스캔 캐시)·설정을 묶는 AppState
  instance.py           창 하나: 또 실행하면 이름 있는 파이프로 떠 있는 창에 폴더를 넘김
  server.py             Flask 라우트 (/api/*, /doc/*, /static/*)
  scanner.py            폴더 스캔, 숨김·제외 판정, resolve_inside()
  docinfo.py            제목·요약 추출 (트리 제목, 폴더 개요)
  changes.py            ChangeLog(변경 순번 기록) + Watcher(watchdog / 폴링 대체)
  config.py             config.json 읽기·쓰기, 프런트에서 바꿀 수 있는 키 제한
  search.py             전체 본문 검색 (/api/search)
  osutil.py             링크 대상 열기 (기본 앱 / 편집기 / 탐색기)
  native.py             pywebview js_api — 폴더 대화상자, 창 제목만
  terminal.py           오른쪽 터미널: 탭마다 셸 하나, 출력 버퍼·긴 폴링 (/api/term/*)
  conpty.py             Windows 의사 콘솔(ConPTY)을 ctypes 로 — 셸 하나를 작업 개체 안에서
  paths.py              리소스·설정 경로 (PyInstaller 대응)
web/
  index.html            앱 뼈대. vendor 스크립트 로드 후 js/main.js
  js/                   ES modules (아래 표)
  css/app.css           앱 UI 스타일
  css/frame.css         html 문서(iframe) 안에 넣는 찾기·바뀐 곳·우클릭 표시
  themes/               문서 본문 스타일: base.css + 스타일마다 <id>.css (목록은 theme.js 의 THEMES)
  vendor/               외부 라이브러리 (tools/update_vendor.py 로만 갱신, 직접 수정 금지)
samples/                기능 점검용 예시 프로젝트 (숨김·제외 케이스 포함)
assets/                 앱 아이콘 (lectern.svg → tools/make_icon.py → lectern.ico)
installer/              lectern.iss — Inno Setup 설치 파일 스크립트 (build.bat 이 씀)
tests/                  pytest
tools/                  update_vendor.py, ui_smoke.py, context_menu.py, make_icon.py
docs/                   ARCHITECTURE, DECISIONS, ROADMAP, TESTING
```

| JS 모듈 | 역할 |
|---|---|
| main.js | 초기화, 툴바, 단축키 |
| store.js | 상태 `S` 와 이벤트 버스 (`on`/`emit`). 이벤트 목록이 파일 머리에 있음. `S.root`·`S.tree` 등은 선택된 탭의 값 |
| tabs.js | 프로젝트 탭 — 탭 막대, 폴더 열기(새 탭)·닫기·고르기, 처음 고를 때 트리·마지막 문서, 서버의 탭 목록에 맞추기, 시작 화면 |
| panes.js | 문서 칸 — 탭마다 하나를 겹쳐 두고 선택된 탭의 칸만 보임, 선택된 칸에 id 옮겨 달기 |
| nav.js | 화면 이동, 뒤로/앞으로, 다시 그리기 (칸마다), 탭을 처음 열 때 마지막 문서·위치 |
| doc.js | 문서 렌더링 후처리 (링크·이미지·표·코드·콜아웃·frontmatter) |
| markdown.js | markdown-it 설정, 수식 규칙, mermaid 코드 블록 |
| overview.js | 폴더 개요 화면 |
| tree.js | 사이드바 트리·필터·최근 변경·우클릭 메뉴 |
| others.js | 사이드바 '파일' 목록 — 종류별 보기는 문서 트리 아래 분리선 너머의 탐색기 같은 목록 (GET /api/others), 폴더 보기는 문서와 파일을 합친 한 트리 |
| icons.js | 사이드바 목록의 파일 종류 아이콘 (확장자 → 종류, md·html 은 문서) |
| terminal.js | 오른쪽 터미널 — xterm.js(처음 열 때 불러옴), 탭마다 셸(`tab.term`), 긴 폴링으로 출력·키 입력 보내기, 패널 열기·닫기·폭, 탭을 닫기 전에 묻기 |
| gather.js | 터미널 모음 — 탭 막대 끝 버튼, 탭마다 칸 하나의 격자(문서 화면 위를 덮음), 칸으로 각 탭의 터미널 화면을 옮겨 보이고 닫으면 되돌림, 칸 크게·이 프로젝트로·다시 시작, '실행 중' 표시 |
| watch.js | 1초 폴링으로 변경 반영 (모든 탭을 한 번에, 숨은 탭은 고를 때 다시 그림) |
| toc.js / find.js / palette.js | 목차(제목 아래에 표·그림 등 구성 요소, 종류 버튼) / 문서 안 찾기 / Ctrl+P |
| fold.js | 제목을 눌러 절 접기·펴기 |
| spotlight.js | 장 하이라이트 — 한 장만 그대로, 나머지는 흐리게. ↑·↓·PageUp·PageDown 으로 앞뒤 장 |
| textsize.js | 툴바의 글자 크기 − 100% + (설정 font_scale, CSS 변수 --md-scale) |
| diffmark.js | 자동 새로고침 때 바뀐 블록 강조, 상태줄 '바뀐 곳' 버튼 |
| search.js | 사이드바 '검색' 탭 — 전체 본문 검색 (서버는 lectern/search.py) |
| parts.js | 사이드바 '모아 보기' 탭 — 범위(프로젝트·폴더)의 문서를 화면 밖에서 그려 목차와 같은 규칙(`toc.js` 의 `readParts`)으로 구성 요소를 세고, 종류마다 문서별 목록(그림은 작은 그림 격자), 누르면 그 자리로 |
| settings.js / position.js | 설정 창 (톱니, Ctrl+,) / 탭마다 마지막 문서·스크롤 위치 기록 |
| pathlink.js | 본문 속 경로 표기(`src/app.py:42`) 자동 링크 |
| resize.js | 사이드바 폭 조절 (경계 끌기, 두 번 누르면 기본) |
| htmldoc.js | html 문서 보기 — 스크립트 없는 같은 출처 iframe (css/frame.css 를 넣는다) |
| docmenu.js | 본문 우클릭 메뉴 (텍스트·원문·표·그림 복사, Claude용 위치) |
| theme.js | 문서 스타일 목록(THEMES)과 전환. 스타일 선택 목록도 이 표로 만들고, 설정 `theme_groups` 에 따라 용도별·분위기별·밝기별로 묶는다(GROUPINGS) |
| mermaid.js / ui.js / status.js / util.js / api.js / project.js | 보조 |

## 코딩 규칙

- Python 3.10+ (3.12+ 권장), 타입 힌트, 표준 라이브러리 우선. 정션은 `DirEntry.is_junction`(3.12+) 대신 `st_reparse_tag` 로 판정하므로 3.10·3.11에서도 걸러진다.
- 새 Python 의존성은 꼭 필요할 때만. 넣으면 `requirements.txt` 와 `docs/DECISIONS.md` 에 이유를 남긴다. 사내망 설치는 wheel 반입이 필요하다는 점을 잊지 않는다. 버전은 `==` 로 고정하고, 요구사항 파일 첫 줄의 `coding: utf-8` 선언은 지우지 않는다 (D22: 없으면 한국어 Windows의 pip 24 이하가 한글 주석을 못 읽는다).
- JS는 전역을 쓰지 않는다. 예외는 vendor 전역(`markdownit`, `markdownItAnchor`, `markdownitFootnote`, `markdownitTaskLists`, `hljs`, `katex`, `DOMPurify`, `mermaid`, 터미널을 처음 열 때 불러오는 `Terminal`·`FitAddon`·`Unicode11Addon`)과 `window.pywebview`.
- 앱 DOM id는 `lec-` 접두사를 붙인다. 문서 제목 앵커 id와 겹치지 않게 하기 위해서다. 문서 안 요소는 `#lec-view` 범위 안에서만 찾는다.
- UI 문구는 한국어, 짧은 평서문. 오류 메시지는 무엇이 안 됐고 어떻게 하면 되는지 말한다 ('F5 를 누르면 다시 불러옵니다'처럼 — 'F5 로 다시 불러옵니다'는 저절로 되는 것처럼 읽힌다).
- 같은 것은 같은 이름으로 (v0.13.1 점검): 그림(이미지 아님 — 인터넷 그림), 박스글(콜아웃·인용 상자), 누르기(클릭 아님), 거르기, 장 하이라이트·하이라이트 해제, '파일' 목록, 터미널 모음, 모아 보기. 툴바의 Ctrl+P 버튼은 '문서 열기'(이름·제목으로 열기)이고, '검색'은 본문 검색, '문서에서 찾기'는 Ctrl+F 다. 말줄임은 '…' 한 글자.
- API를 추가·변경하면 `docs/ARCHITECTURE.md` 의 API 표를 같이 고친다. 설계 판단은 `docs/DECISIONS.md` 에 한 항목으로 남긴다.
- 기능을 끝내면 `docs/ROADMAP.md` 의 체크 상태를 갱신한다.

## 알아 둘 함정

- pywebview는 디버그 모드가 아니면 WebView2의 기본 단축키(Ctrl+F, F5, Ctrl+P 인쇄 등)와 기본 우클릭 메뉴를 끈다. 필요한 기능은 직접 구현한다 (`find.js`, F5 처리 참고).
- `/api/*` 는 창 모드에서 `X-Token` 헤더(= `window.pywebview.token`)를 검사한다. `<img>` 가 써야 하는 `/doc/<탭 id>/*` 는 토큰 없이 열려 있다 (127.0.0.1 전용).
- 서버는 여러 프로젝트(탭)를 함께 연다 (D34). 프로젝트를 다루는 API 는 탭 id 를 `p` 로 받는다 (GET 은 `?p=`, POST 는 본문). 문서 주소는 `util.docUrl(tab, path)` 로 만든다 (`/doc/<id>/<경로>`). id 는 실행마다 무작위라 문서가 다른 탭의 주소를 짐작할 수 없다 — 상대경로가 `/doc/<그 탭 id>/` 밖으로 나가면 `resolveRef` 가 막는다.
- DOMPurify는 `SANITIZE_DOM: false` 로 쓴다. 기본값이면 'title', 'images' 같은 제목 앵커 id가 지워진다. 대신 `document.querySelector` 같은 이름을 가릴 수 있는 `img` 의 `name` 은 정화 훅이 지운다 (D15).
- 블록의 원문 줄 범위는 `data-lines="시작-끝"` 이다 (`markdown.js` 의 `sourceLines`). `data-src` 는 정화 훅이 그림 주소를 떼어 두는 데 쓰므로 다른 뜻으로 쓰지 않는다. 블록을 그리는 렌더러 규칙을 새로 만들면 `self.renderAttrs(token)` 으로 `data-lines` 를 내보낸다 (수식 블록·Mermaid 참고). 안 그러면 그 블록은 원문 복사가 안 된다.
- 문서 속 절대경로(`C:\...`, `file:///...`)는 프로젝트 안일 때만 열린다 (`doc.js` 의 `absoluteRef`). DOMPurify 설정의 `ALLOWED_URI_REGEXP` 를 좁히면 이 기능이 조용히 깨진다 (`ui_smoke` 의 [절대경로]가 잡는다).
- 문서 속 링크는 `a[href], area[href]` 를 모두 `bindLink` 가 다룬다. 다루지 않은 링크를 누르면 앱 창이 그 주소로 떠난다. SVG `<a>` 는 `target` 등이 읽기 전용 속성이라 `setAttribute` 로 준다.
- 구성 요소는 목차(`toc.js`)와 모아 보기(`parts.js`)가 같은 함수 `readParts` 로 센다. 모아 보기는 문서를 화면 밖(md 는 `template`, html 은 `DOMParser`)에서 세고, 누르면 그 문서를 그려 같은 종류·번호의 것을 찾아간다 — 그래서 판정(`partKind`)은 그림을 불러오기 전과 후가 같아야 한다 (불러온 크기·로드 상태를 쓰지 않는다. 아이콘은 width·height 속성으로, 불러오지 못한 그림 자리 `.image-off` 도 그림으로 센다).
- 목차의 링크는 제목이 `a[data-i]`, 구성 요소가 `a[data-c]` 다. 제목 링크만 세거나 고를 때는 `a[data-i]` 로 찾는다 (구성 요소의 글에 제목과 같은 낱말이 들어 있을 수 있다). 구성 요소를 새로 꾸미는 렌더러(예: 새 블록 종류)를 만들면 `toc.js` 의 `CANDIDATES`·`partKind` 에 넣을지 본다.
- 접힌 절의 블록은 `display:none`(`lec-fold-hidden`)이라 위치가 0이다. 문서 속 요소로 스크롤하는 코드는 먼저 `fold.js` 의 `unfoldTo(el)` 을 부른다 (목차·앵커 링크·찾기가 그렇게 한다). `unfoldTo` 는 `reveal` 을 보내 장 하이라이트도 그 장으로 옮기므로, 새로 문서 속으로 가는 기능도 이 함수를 거친다.
- 문서 본문의 글자 크기는 `--md-scale`(툴바의 글자 크기)을 곱한다. `base.css`·스타일 css 에 px 로 글자 크기를 새로 적으면 `calc(13px * var(--md-scale, 1))` 처럼 쓴다 (em 은 그대로 따라간다).
- 문서는 화면 밖 무대(`.lec-stage`)에서 그린 뒤 바꿔 끼운다. Mermaid는 DOM에 붙어 있어야 크기를 잴 수 있기 때문이다. 무대를 `display:none` 으로 바꾸면 다이어그램 크기가 0이 된다.
- 앱 아이콘용 SVG 스타일은 `button > svg` 로 한정되어 있다. 전역 `svg` 규칙을 만들면 Mermaid 그림이 깨진다.
- 수식의 `$` 규칙은 달러 표기(`$105/t`)를 보호하도록 pandoc 규칙을 따른다 (`markdown.js` 주석). 규칙을 넓히지 않는다.
- 렌더링은 칸마다 `pane.renderId` 로 순번을 매긴다. 늦게 끝난 렌더링은 결과를 버린다. 비동기 렌더링 함수를 새로 만들 때 칸을 첫 인자로 받고 같은 방식을 쓴다. 렌더러는 프로젝트를 `S.root`·`S.fileMap` 이 아니라 칸의 탭(`pane.tab.root`·`pane.tab.fileMap`·`pane.tab.id`)에서 읽는다 — 그리는 중에 다른 탭을 고를 수 있다.
- 문서 칸은 프로젝트 탭마다 하나다 (`panes.js`·`tabs.js`, D34). 칸은 겹쳐 두고 고르지 않은 탭의 칸은 `visibility: hidden` 이다 (`display:none` 으로 바꾸면 숨은 탭의 스크롤 위치를 잃고 다시 그릴 때 크기를 못 잰다). `S.root`·`S.tree`·`S.files`·`S.fileMap`·`S.dirs`·`S.changed`·`S.open`·`S.seq` 는 선택된 탭(`S.tab`)의 값을 읽고 쓰는 접근자다 — 선택된 탭만 다루는 모듈은 그대로 쓰고, 모든 탭을 다루는 코드(자동 새로고침·위치 기록)는 `S.tabs` 의 탭 객체를 쓴다. 탭마다 남길 사이드바 상태는 `tab.side` 에 두고 `tab` 이벤트({tab, prev})에서 앞 탭에 남기고 새 탭 것을 되살린다 (`tree.js`·`search.js`).
- `#lec-view`·`#lec-content` id 는 **선택된 칸**의 본문·스크롤 상자로 옮겨 다닌다 (D33 에서 만든 방식). 선택된 칸만 다루는 코드는 id 로 찾아도 되지만, 모든 칸에 해당하는 코드(렌더러·자동 새로고침 등)는 칸 객체(`S.panes`, `pane.view`·`pane.scroller`)를 쓴다. 문서 화면의 이벤트는 id 대신 `#lec-panes` 에 붙인다 (id 가 옮겨 가면 붙인 요소가 달라진다). 스크롤은 거품처럼 올라오지 않으므로 `document` 잡기 단계에서 듣는다 (`toc.js`·`position.js`).
- 목차·상태줄·원문(우클릭 메뉴)·바뀐 곳은 칸마다 남기고 선택된 칸 것만 보인다 — 렌더러는 `setToc(pane, …)`·`setStatus(…, pane)`·`setDocSource(pane, …)`·`markChanges(…, pane)` 로 넘긴다. 다른 탭을 고르면 `pane` 이벤트가 간다. 숨은 탭의 화면이 바뀌면 바로 그리지 않고 `pane.stale` 을 달아 그 탭을 고를 때 그린다 (`watch.js`·`nav.refreshView()`).
- 문서 속 요소의 id는 같은 이름의 전역이 없으면 `window.<id>` 로 잡힌다. 그래서 `## Mermaid` 제목(id `mermaid`)이 있으면 라이브러리를 불러오기 전의 `window.mermaid` 는 그 제목이다. 늦게 불러오는 전역은 있는지가 아니라 진짜 라이브러리인지 확인한다 (`mermaid.js` 의 `loaded()`).
- 앱은 설정을 저장할 때 기본값도 함께 적는다. 그래서 기본값만 바꾸면 이미 쓰던 사람에게는 반영되지 않는다 — 꼭 바꿔야 하면 `config.CONFIG_VERSION` 을 올리고 `_upgrade` 에 옛 판을 바꾸는 코드를 둔다 (D35).
- `config.json` 은 JSON 이 맞아도 값의 형식이 틀릴 수 있다 (`"exclude_dirs": "data"`). `config.value_ok` 가 `DEFAULTS` 와 같은 형식인지 보고, 틀린 값은 기본값으로 돌며 알린다. 새 키가 `null` 도 되면 `NULLABLE` 에 넣는다 (D29).
- `/api/*` 의 POST 는 `Content-Type: application/json` 만 받는다 (아니면 415). 토큰이 없는 브라우저 모드에서 다른 사이트의 폼이 보내지 못하게 하려는 것이니, 프런트는 `api.postJSON` 만 쓴다.
- 다시 그리기(`refreshView`)는 `scrollTop` 에 함수를 넘겨 바꿔 끼우기 직전의 위치를 읽는다. 그리는 동안 사용자가 스크롤해도 되돌리지 않게. 렌더러를 새로 만들면 같은 방식을 받는다.
- `config.json` 을 읽지 못하면(`Config.load_error`) 파일이 고쳐질 때까지 저장하지 않는다 (D21). 사용자가 실행 중에 파일을 고칠 수 있으므로, 설정을 바꾸는 코드는 반드시 `Config._update(change)` 를 거친다 (밖에서 고친 값을 다시 읽은 뒤 바꾸고 저장).
- Windows에서 Python `mimetypes` 는 레지스트리 값을 기본값보다 우선한다. 레지스트리에 `.js` 가 `text/plain` 으로 잡힌 PC에서는 모듈 스크립트가 거부되어 화면이 빈다. 그래서 `server.py` 의 `FIXED_TYPES` 가 `.js`·`.mjs`·`.css`·`.svg`·`.woff2` 의 형식을 정한다. 앱이 새 확장자의 파일을 내보내면 여기에 넣을지 본다.
- 새 스타일은 `theme.js` 의 `THEMES` 에 `light(이름, 용도, 분위기, 밝기, Mermaid 색)` 또는 `dark(이름, Mermaid 색)` 로 넣는다. 밝은 스타일은 세 묶는 방식 모두의 묶음을 정해야 목록에 나온다 (D30). 머리행을 짙게 칠하는 스타일은 `--md-th-fg` 로 글자색을 준다 (인쇄 때는 검정으로 덮인다). 터미널 색은 스타일의 `--md-code-bg`·`--md-fg`·`--md-link` 와 밝기로 저절로 정해진다 — 이름이 같은 터미널 색표(Solarized 등)가 있는 스타일만 `terminal.js` 의 `PALETTES` 에 더한다.
- 앱 UI 색(`--ui-*`)은 문서 스타일의 `--md-*` 에서 만든다 (D28). 새 스타일은 `--md-*` 만 정하면 툴바·사이드바도 따라오니, `app.css` 에 스타일별 UI 색을 따로 넣지 않는다.
- 문서 스타일은 PC에 있는 글꼴만 쓴다 (웹 글꼴 금지, 내장도 안 함 — D26). 글꼴 목록은 영문 글꼴 → 한글 글꼴 → `Malgun Gothic`·`Batang` 같은 Windows 기본 글꼴 순으로 끝내서, 그 글꼴이 없는 PC에서도 한글이 보이게 한다. 새 스타일은 `ui_smoke.py` 가 글자 대비(WCAG 4.5:1)와 제목 색·표 머리행 구분을 확인한다.
- `installer/lectern.iss` 는 UTF-8(BOM)이어야 한다 (BOM이 없으면 한글이 깨진다). `AppId` 는 바꾸지 않는다 — 바꾸면 새 버전이 덮어 설치되지 않고 따로 설치된다.
- html 문서는 `<iframe sandbox="allow-same-origin allow-modals">` 이다 (`allow-modals` 는 앱이 그 문서를 인쇄하려고). **`allow-scripts` 를 더하지 않는다** — 같은 출처라서 스크립트가 돌면 앱의 `/api/*`·토큰에 닿는다. 서버 CSP(`html_doc_policy`)도 함께 막는다.
- iframe 안의 키·마우스 이벤트는 앱 문서로 올라오지 않는다. `htmldoc.js` 가 keydown·mouseup·mousedown 을 앱으로 넘기므로, 새 단축키는 `main.js` 에만 넣으면 html 문서에서도 된다. 문서 속 요소를 찾을 때는 `util.docRoot()`, 화면 좌표는 `util.screenRect()` 를 쓴다 (iframe 위치를 더함).
- 문서 외 파일 목록(`/api/others`, `scanner.scan_others`)은 문서 트리와 따로 읽고, 감시는 문서 외 파일의 생성·삭제·이동만 `others` 로 남긴다 (내용 수정은 보지 않는다 — 소스를 고칠 때마다 다시 읽지 않게). 목록에서 여는 것도 `osutil.open_path` 를 거친다: 실행·설치 파일·압축 등(`REVEAL_ONLY_EXT`)은 탐색기에서 선택만 한다. 이 목록에 이름 바꾸기·지우기 같은 탐색기 기능을 넣지 않는다 (보기 전용).
- 트리 스캔은 `Project.scan()` 을 거친다 (탭마다) — 변경 기록(seq)이 그대로면 마지막 결과를 다시 쓰므로 돌려받은 노드 목록을 고치지 않는다 (복사해서 쓴다). 감시가 놓치는 변경은 F5(`fresh`)로 새로 훑는다.
- 창 하나(`instance.py`)는 이름 있는 파이프로 JSON 바이트만 주고받는다 (`send_bytes`·`recv_bytes`). pickle 을 쓰는 `send`·`recv` 로 바꾸지 않는다 — 받은 바이트로 코드가 돌 수 있다. 파이프 이름이 설정 폴더를 따르므로 점검 스크립트는 `LECTERN_CONFIG_DIR` 을 바꿔 설치된 Lectern 창과 섞이지 않게 한다.
- 터미널 API(`/api/term/*`)는 `X-Term` 헤더(= 페이지의 `meta lec-term`, 실행마다 새 비밀값)를 검사한다 — 토큰이 없는 브라우저 모드에서도. 셸에 글자를 보내는 길은 사용자의 키 입력(`/api/term/input`) 하나로 둔다. 문서·링크·다른 기능에서 셸로 명령을 보내는 API 를 만들지 않는다 (D38).
- `/` 의 CSP 는 `script-src 'self' 'unsafe-eval'` 이다 (D38 — 문서에 끼어든 스크립트가 터미널 비밀값을 읽지 못하게). `index.html` 에 인라인 `<script>`·`onclick=` 을 넣으면 돌지 않는다. vendor 를 더할 때 인라인 스크립트를 끼워 넣는 라이브러리인지 본다.
- 터미널 화면(`tab.term.box`)은 탭마다 하나이고, 터미널 모음(`gather.js`)이 오른쪽 패널에서 모음 칸으로 옮겼다가 닫을 때 되돌린다 (`returnTerminals`). 모으는 동안(`gathered()`) `terminal.js` 는 화면을 옮기거나 감추지 않는다. 화면을 만들 곳이 따로 생기면 같은 방식(상자를 옮기고 `fitTerminal`)을 쓴다 — xterm 을 새로 만들면 셸 출력이 이어지지 않는다.
- 셸을 띄우기 전에 `conpty.py` 가 이 프로세스의 'Ctrl+C 무시' 표시를 끈다 (`SetConsoleCtrlHandler(NULL, FALSE)`). 이 표시는 자식에게 물려져서, Lectern 을 새 프로세스 그룹으로 띄운 쪽(일부 실행기·자동화 도구)에서 켜진 채로 오면 셸에서 띄운 프로그램이 Ctrl+C 로 멈추지 않는다 (v0.12.0 에서 고침, `test_ctrl_c_stops_child_program`).
- 의사 콘솔은 pywinpty 가 아니라 `conpty.py`(ctypes)다 — pywinpty 3.1 에 든 OpenConsole 은 PowerShell 5.1 의 한글 출력을 cp949 로 깨뜨렸다 (D38). `STARTF_USESTDHANDLES` 와 빈 표준 핸들을 지우지 않는다 (지우면 창 없는 앱에서 셸 입출력이 의사 콘솔을 거치지 않는다). 셸은 멈춘 채 만들어 작업 개체에 넣은 뒤 시작한다 — 그래야 탭을 닫거나 앱이 끝날 때(강제 종료 포함) 셸에서 띄운 프로그램까지 끝난다.
- 터미널 안의 키는 셸 것이다 (Ctrl+C·Ctrl+W·Esc 등 — Claude Code 가 쓴다). `main.js` 의 keydown 은 `#lec-term` 안에서는 `` Ctrl+` ``·Ctrl+Tab 만 다룬다 (터미널 모음이 열려 있으면 칸 안에서 `` Ctrl+` ``·`` Ctrl+Shift+` ``·Ctrl+Tab 만, 칸 밖에서도 몇 가지만 — 문서 화면이 가려져 있다). 새 앱 단축키를 터미널 안에서도 쓰게 하려면 `main.js` 와 `terminal.js` 의 `keyFor`(xterm 이 셸로 보내기 전에 거르는 곳)를 함께 고친다.
- `.bat` 파일은 CRLF여야 한다 (`.gitattributes` 에 지정됨). `run.bat`·`dev.bat` 은 스크립트 폴더로 `cd` 하지 않고 `%~dp0` 로 경로를 잡는다. 폴더 인자(`run.bat .`)는 실행한 곳 기준이어야 하기 때문이다.
