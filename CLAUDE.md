# Lectern — Claude Code 작업 지침

Lectern(렉턴, 독서대)은 Windows용 로컬 문서 뷰어다. Claude Code·Claude가 프로젝트 폴더에 만든 문서를 **기계가 아닌 사람이** 한눈에 훑어보고 읽는 것이 목적이고, **보기 전용**이다.
Markdown(`.md`)과 HTML(`.html`) 문서를 본다. HTML은 문서로 보기만 하고 스크립트는 돌리지 않는다 (D27). 문서 형식은 `scanner.DOC_TYPES` 가 정한다.
구성: Python(pywebview 창 + Flask 로컬 서버) + 빌드 단계 없는 순수 JS(ES modules).

현재 버전 0.2.0 (MVP, 외부 이미지, 검토 후 수정, 제목 접기, 본문 우클릭 메뉴, 스타일 12종, 설치 파일). 다음 할 일은 `docs/ROADMAP.md` 의 "다음 단계"에서 고른다.

## 반드시 지킬 원칙

1. **보기 전용.** 사용자 파일을 만들거나 고치거나 지우는 기능을 넣지 않는다. 디스크에 쓰는 것은 `%APPDATA%\Lectern\config.json` 하나뿐이다.
2. **로컬 전용.** 앱이 스스로 외부에 요청하지 않는다 (CDN·웹폰트·분석·업데이트 확인 모두 금지). html 문서도 같다 — 서버가 `/doc/*.html` 에 붙이는 CSP가 스크립트·연결·인터넷 CSS·글꼴을 막고 그림만 `external_images` 를 따르게 한다 (D27). JS 라이브러리는 `web/vendor/` 에 들어 있다. **예외는 문서 속 외부 이미지 하나뿐**이다: 설정 `external_images`(기본 켜짐)가 켜져 있으면 `http(s)` 이미지를 referrer 없이 불러오고, 실패·15초 초과면 링크로 바꾼다 (D19). `doc.js` 의 DOMPurify 훅이 모든 `src` 를 떼어 두었다가 허용된 이미지에만 다시 주고, 그 밖에 그림을 부르는 길(`srcset`·`poster`·표의 `background`·SVG `image` 의 href·style 과 SVG 속성의 `url()`·`image-set()`)은 지운다. 놓친 길은 서버가 `/` 에 붙이는 CSP(`img-src`, D20)가 막는다. `tools/ui_smoke.py` 가 외부 요청이 `<img>` 뿐인지 확인한다.
3. **선택한 폴더와 그 하위만.** 서버는 프로젝트 밖 경로와 숨김 경로를 404로 막는다. 경로 검사는 반드시 `lectern/scanner.py` 의 `resolve_inside()` 를 거친다.
4. **숨김 제외.** 이름이 `.`으로 시작 / Windows 숨김·시스템 속성 / 심볼릭 링크·정션 / 제외 폴더(`node_modules` 등) / 문서가 없는 폴더는 트리에 나오지 않는다. html 은 앱 소스·빌드 폴더(`src`·`public`·`static`·`templates`·`web`·`www`·`frontend`·`out`) 안에서는 문서로 보지 않는다.
5. **코드 파일을 실행하지 않는다.** `os.startfile` 은 `.py`, `.js`, `.bat` 등을 실행해 버린다. 문서 속 링크는 `lectern/osutil.py` 의 `open_path()` 만 쓴다 (안전한 형식만 기본 앱, 나머지는 편집기나 탐색기).
6. **단순함 유지.** 레이아웃은 왼쪽 트리 하나. 번들러·프레임워크(React, Vite 등)를 들이지 않는다. `docs/ROADMAP.md` 의 "하지 않기로 한 것"은 사용자가 다시 요청하기 전에는 넣지 않는다.

## 실행과 확인

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt

python app.py samples              :: 창으로 실행
python app.py --browser samples    :: 개발용: http://127.0.0.1:8765 를 일반 브라우저로 (dev.bat)
python app.py --debug samples      :: 창 + 개발자 도구 (F12, 기본 Ctrl+F 등도 켜짐)
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
  state.py              열린 폴더·감시·설정을 묶는 AppState
  server.py             Flask 라우트 (/api/*, /doc/*, /static/*)
  scanner.py            폴더 스캔, 숨김·제외 판정, resolve_inside()
  docinfo.py            제목·요약 추출 (트리 제목, 폴더 개요)
  changes.py            ChangeLog(변경 순번 기록) + Watcher(watchdog / 폴링 대체)
  config.py             config.json 읽기·쓰기, 프런트에서 바꿀 수 있는 키 제한
  search.py             전체 본문 검색 (/api/search)
  osutil.py             링크 대상 열기 (기본 앱 / 편집기 / 탐색기)
  native.py             pywebview js_api — 폴더 대화상자, 창 제목만
  paths.py              리소스·설정 경로 (PyInstaller 대응)
web/
  index.html            앱 뼈대. vendor 스크립트 로드 후 js/main.js
  js/                   ES modules (아래 표)
  css/app.css           앱 UI 스타일
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
| main.js | 초기화, 툴바, 단축키, 프로젝트 열기 |
| store.js | 상태 `S` 와 이벤트 버스 (`on`/`emit`). 이벤트 목록이 파일 머리에 있음 |
| nav.js | 화면 이동, 뒤로/앞으로, 다시 그리기 |
| doc.js | 문서 렌더링 후처리 (링크·이미지·표·코드·콜아웃·frontmatter) |
| markdown.js | markdown-it 설정, 수식 규칙, mermaid 코드 블록 |
| overview.js | 폴더 개요 화면 |
| tree.js | 사이드바 트리·필터·최근 변경·우클릭 메뉴 |
| watch.js | 1초 폴링으로 변경 반영 |
| toc.js / find.js / palette.js | 목차 / 문서 안 찾기 / Ctrl+P |
| fold.js | 제목을 눌러 절 접기·펴기 |
| diffmark.js | 자동 새로고침 때 바뀐 블록 강조, 상태줄 '바뀐 곳' 버튼 |
| search.js | 사이드바 '검색' 탭 — 전체 본문 검색 (서버는 lectern/search.py) |
| settings.js / position.js | 설정 창 (톱니, Ctrl+,) / 마지막 문서·스크롤 위치 기록 |
| pathlink.js | 본문 속 경로 표기(`src/app.py:42`) 자동 링크 |
| resize.js | 사이드바 폭 조절 (경계 끌기, 두 번 누르면 기본) |
| htmldoc.js | html 문서 보기 — 스크립트 없는 같은 출처 iframe (css/frame.css 를 넣는다) |
| docmenu.js | 본문 우클릭 메뉴 (텍스트·원문·표·그림 복사, Claude용 위치) |
| theme.js | 문서 스타일 목록(THEMES)과 전환. 스타일 선택 목록도 이 표로 만든다 |
| mermaid.js / ui.js / status.js / util.js / api.js / project.js | 보조 |

## 코딩 규칙

- Python 3.10+ (3.12+ 권장), 타입 힌트, 표준 라이브러리 우선. 정션은 `DirEntry.is_junction`(3.12+) 대신 `st_reparse_tag` 로 판정하므로 3.10·3.11에서도 걸러진다.
- 새 Python 의존성은 꼭 필요할 때만. 넣으면 `requirements.txt` 와 `docs/DECISIONS.md` 에 이유를 남긴다. 사내망 설치는 wheel 반입이 필요하다는 점을 잊지 않는다. 버전은 `==` 로 고정하고, 요구사항 파일 첫 줄의 `coding: utf-8` 선언은 지우지 않는다 (D22: 없으면 한국어 Windows의 pip 24 이하가 한글 주석을 못 읽는다).
- JS는 전역을 쓰지 않는다. 예외는 vendor 전역(`markdownit`, `markdownItAnchor`, `markdownitFootnote`, `markdownitTaskLists`, `hljs`, `katex`, `DOMPurify`, `mermaid`)과 `window.pywebview`.
- 앱 DOM id는 `lec-` 접두사를 붙인다. 문서 제목 앵커 id와 겹치지 않게 하기 위해서다. 문서 안 요소는 `#lec-view` 범위 안에서만 찾는다.
- UI 문구는 한국어, 짧은 평서문. 오류 메시지는 무엇이 안 됐고 어떻게 하면 되는지 말한다.
- API를 추가·변경하면 `docs/ARCHITECTURE.md` 의 API 표를 같이 고친다. 설계 판단은 `docs/DECISIONS.md` 에 한 항목으로 남긴다.
- 기능을 끝내면 `docs/ROADMAP.md` 의 체크 상태를 갱신한다.

## 알아 둘 함정

- pywebview는 디버그 모드가 아니면 WebView2의 기본 단축키(Ctrl+F, F5, Ctrl+P 인쇄 등)와 기본 우클릭 메뉴를 끈다. 필요한 기능은 직접 구현한다 (`find.js`, F5 처리 참고).
- `/api/*` 는 창 모드에서 `X-Token` 헤더(= `window.pywebview.token`)를 검사한다. `<img>` 가 써야 하는 `/doc/*` 는 토큰 없이 열려 있다 (127.0.0.1 전용).
- DOMPurify는 `SANITIZE_DOM: false` 로 쓴다. 기본값이면 'title', 'images' 같은 제목 앵커 id가 지워진다. 대신 `document.querySelector` 같은 이름을 가릴 수 있는 `img` 의 `name` 은 정화 훅이 지운다 (D15).
- 블록의 원문 줄 범위는 `data-lines="시작-끝"` 이다 (`markdown.js` 의 `sourceLines`). `data-src` 는 정화 훅이 그림 주소를 떼어 두는 데 쓰므로 다른 뜻으로 쓰지 않는다. 블록을 그리는 렌더러 규칙을 새로 만들면 `self.renderAttrs(token)` 으로 `data-lines` 를 내보낸다 (수식 블록·Mermaid 참고). 안 그러면 그 블록은 원문 복사가 안 된다.
- 문서 속 절대경로(`C:\...`, `file:///...`)는 프로젝트 안일 때만 열린다 (`doc.js` 의 `absoluteRef`). DOMPurify 설정의 `ALLOWED_URI_REGEXP` 를 좁히면 이 기능이 조용히 깨진다 (`ui_smoke` 의 [절대경로]가 잡는다).
- 문서 속 링크는 `a[href], area[href]` 를 모두 `bindLink` 가 다룬다. 다루지 않은 링크를 누르면 앱 창이 그 주소로 떠난다. SVG `<a>` 는 `target` 등이 읽기 전용 속성이라 `setAttribute` 로 준다.
- 접힌 절의 블록은 `display:none`(`lec-fold-hidden`)이라 위치가 0이다. 문서 속 요소로 스크롤하는 코드는 먼저 `fold.js` 의 `unfoldTo(el)` 을 부른다 (목차·앵커 링크·찾기가 그렇게 한다).
- 문서는 화면 밖 무대(`.lec-stage`)에서 그린 뒤 바꿔 끼운다. Mermaid는 DOM에 붙어 있어야 크기를 잴 수 있기 때문이다. 무대를 `display:none` 으로 바꾸면 다이어그램 크기가 0이 된다.
- 앱 아이콘용 SVG 스타일은 `button > svg` 로 한정되어 있다. 전역 `svg` 규칙을 만들면 Mermaid 그림이 깨진다.
- 수식의 `$` 규칙은 달러 표기(`$105/t`)를 보호하도록 pandoc 규칙을 따른다 (`markdown.js` 주석). 규칙을 넓히지 않는다.
- 렌더링은 `S.renderId` 로 순번을 매긴다. 늦게 끝난 렌더링은 결과를 버린다. 비동기 렌더링 함수를 새로 만들 때 같은 방식을 쓴다.
- 문서 속 요소의 id는 같은 이름의 전역이 없으면 `window.<id>` 로 잡힌다. 그래서 `## Mermaid` 제목(id `mermaid`)이 있으면 라이브러리를 불러오기 전의 `window.mermaid` 는 그 제목이다. 늦게 불러오는 전역은 있는지가 아니라 진짜 라이브러리인지 확인한다 (`mermaid.js` 의 `loaded()`).
- `config.json` 을 읽지 못하면(`Config.load_error`) 파일이 고쳐질 때까지 저장하지 않는다 (D21). 사용자가 실행 중에 파일을 고칠 수 있으므로, 설정을 바꾸는 코드는 반드시 `Config._update(change)` 를 거친다 (밖에서 고친 값을 다시 읽은 뒤 바꾸고 저장).
- Windows에서 Python `mimetypes` 는 레지스트리 값을 기본값보다 우선한다. 레지스트리에 `.js` 가 `text/plain` 으로 잡힌 PC에서는 모듈 스크립트가 거부되어 화면이 빈다. 그래서 `server.py` 의 `FIXED_TYPES` 가 `.js`·`.css`·`.svg`·`.woff2` 의 형식을 정한다. 앱이 새 확장자의 파일을 내보내면 여기에 넣을지 본다.
- 문서 스타일은 PC에 있는 글꼴만 쓴다 (웹 글꼴 금지, 내장도 안 함 — D26). 글꼴 목록은 영문 글꼴 → 한글 글꼴 → `Malgun Gothic`·`Batang` 같은 Windows 기본 글꼴 순으로 끝내서, 그 글꼴이 없는 PC에서도 한글이 보이게 한다. 새 스타일은 `ui_smoke.py` 가 글자 대비(WCAG 4.5:1)와 제목 색·표 머리행 구분을 확인한다.
- `installer/lectern.iss` 는 UTF-8(BOM)이어야 한다 (BOM이 없으면 한글이 깨진다). `AppId` 는 바꾸지 않는다 — 바꾸면 새 버전이 덮어 설치되지 않고 따로 설치된다.
- html 문서는 `<iframe sandbox="allow-same-origin">` 이다. **`allow-scripts` 를 더하지 않는다** — 같은 출처라서 스크립트가 돌면 앱의 `/api/*`·토큰에 닿는다. 서버 CSP(`html_doc_policy`)도 함께 막는다.
- iframe 안의 키·마우스 이벤트는 앱 문서로 올라오지 않는다. `htmldoc.js` 가 keydown·mouseup·mousedown 을 앱으로 넘기므로, 새 단축키는 `main.js` 에만 넣으면 html 문서에서도 된다. 문서 속 요소를 찾을 때는 `util.docRoot()`, 화면 좌표는 `util.screenRect()` 를 쓴다 (iframe 위치를 더함).
- 트리 스캔은 `AppState.scan()` 을 거친다 — 변경 기록(seq)이 그대로면 마지막 결과를 다시 쓰므로 돌려받은 노드 목록을 고치지 않는다 (복사해서 쓴다). 감시가 놓치는 변경은 F5(`fresh`)로 새로 훑는다.
- `.bat` 파일은 CRLF여야 한다 (`.gitattributes` 에 지정됨). `run.bat`·`dev.bat` 은 스크립트 폴더로 `cd` 하지 않고 `%~dp0` 로 경로를 잡는다. 폴더 인자(`run.bat .`)는 실행한 곳 기준이어야 하기 때문이다.
