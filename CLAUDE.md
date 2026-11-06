# Lectern — Claude Code 작업 지침

Lectern(렉턴, 독서대)은 Markdown 파일을 중심으로 사람과 AI가 함께 리서치하는 Windows용 로컬 통합 작업 환경(Integrated Research Work Environment)을 지향한다. 장기 지향점은 마름모형 리서치 방법의 구조화이고 지금은 구현하지 않는다 (`docs/VISION.md`, D87). 지금의 중심은 Claude Code·Claude가 프로젝트 폴더에 만든 문서와 자료를 **기계가 아닌 사람이** 읽고 살피고 그 자리에서 고치는 것이다.
Markdown(`.md`)과 HTML(`.html`) 문서를 본다. HTML은 문서로 보기만 하고 스크립트는 돌리지 않는다 (D27). 문서 형식은 서버가 `scanner.DOC_TYPES`, 화면이 `util.js` 의 `isMd`·`isHtml` 로 정한다 (형식을 더하면 둘 다).
구성: Python(pywebview 창 + Flask 로컬 서버, waitress 로 띄움 — D82) + 빌드 단계 없는 순수 JS(ES modules).

현재 버전 0.62.0. 판마다 바뀐 것은 `docs/HISTORY.md`, 방향은 `docs/VISION.md`, 다음 할 일은 `docs/ROADMAP.md` 에서 고른다.

## 반드시 지킬 원칙

1. **파일은 사용자가 고를 때만, 그 파일만 바꾼다.** 앱이 스스로 사용자 파일을 만들거나 고치거나 지우지 않는다. 바꾸는 길은 아래의 것뿐이다 — **편집 모드(D54)**: 사용자가 저장할 때만 이미 있는 문서·코드 파일 하나를 고친다 (`lectern/editing.py` — UTF-8 글만, 줄바꿈·BOM 그대로, 그사이 바뀌었으면 묻기). 한 줄 편집(D76)과 줄 구조 편집(D83 — 줄 더하기·나누기·합치기·레벨·옮기기·지우기·복제)도 같은 저장 길(`/api/save`)로 사용자가 고른 줄과 그 번호 목록만 (할 일 체크 칸도 — `lineedit.replaceLines`). 새로 만드는 것은 새 Markdown 문서 하나뿐이다 (D63·D65 — 사용자가 새로 만들기·새 문서로 보내기에서 경로를 정할 때 `# 제목` 한 줄로, 새 발표 문서면 머리 설정과 표지 한 장으로 — D96. `.md`, 이미 있는 폴더에, 같은 이름이 있으면 만들지 않음). 프로젝트 메모는 사용자가 메모를 쓸 때만 그 프로젝트의 `.lectern/notes.md` 하나에 쓴다 (D92 — `lectern/notes.py`, 경로는 고정, 링크면 쓰지 않음). 이름 바꾸기는 사용자가 사이드바에서 고른 파일 하나를 같은 폴더 안에서만 (D66 — `editing.rename_file`, 덮어쓰지 않음). 지우기·옮기기·폴더 만들기는 여전히 없다. Lectern 프로그램 폴더 안(설치된 예제 등)의 파일은 이 예외로도 고치지 않고, 그 안을 프로젝트로 열면 터미널도 열지 않는다 (D71 — `paths.is_protected`). 디스크에 쓰는 것은 `%APPDATA%\Lectern\config.json` 하나뿐이다 (그 옆 `styles` 폴더는 '스타일 폴더 열기'가 비어 있을 때 만들기만 한다 — 내 스타일 파일은 읽기만, D53). **예외는 오른쪽 터미널(D38)이다**: 사용자가 직접 친 명령이 하는 일은 Lectern 이 한 것이 아니다. 대신 문서·링크·다른 기능이 셸로 명령을 보내는 길은 만들지 않는다 — 사용자가 우클릭 메뉴에서 고른 '터미널에 붙여 넣기'만 Ctrl+V 와 같은 길로, Enter 없이 넣는다 (D51).
2. **로컬 전용.** 앱이 스스로 외부에 요청하지 않는다 (CDN·웹폰트·분석·업데이트 확인 모두 금지). html 문서도 같다 — 서버가 `/doc/*.html` 에 붙이는 CSP가 스크립트·연결·인터넷 CSS·글꼴을 막고 그림만 `external_images` 를 따르게 한다 (D27). JS 라이브러리는 `web/vendor/` 에 들어 있다. **예외는 문서 속 외부 이미지 하나뿐**이다: 설정 `external_images`(기본 켜짐)가 켜져 있으면 `http(s)` 이미지를 referrer 없이 불러오고, 실패·15초 초과면 링크로 바꾼다 (D19). `doc.js` 의 DOMPurify 훅이 모든 `src` 를 떼어 두었다가 허용된 이미지에만 다시 주고, 그 밖에 그림을 부르는 길(`srcset`·`poster`·표의 `background`·SVG `image` 의 href·style 과 SVG 속성의 `url()`·`image-set()`)은 지운다. 놓친 길은 서버가 `/` 에 붙이는 CSP(`img-src`, D20)가 막는다. `tools/ui_smoke.py` 가 외부 요청이 `<img>` 뿐인지 확인한다.
3. **선택한 폴더와 그 하위만.** 서버는 프로젝트 밖 경로와 숨김 경로를 404로 막는다. 경로 검사는 반드시 `lectern/scanner.py` 의 `resolve_inside()` 를 거친다. 이 함수는 `resolve()` 전에 글자만으로 root 안인지 먼저 본다 — `\\서버\공유` 를 `resolve()` 하면 Windows 가 그 서버에 접속해 로그인 정보(NTLM)를 건넨다 (D29).
4. **숨김 제외.** 이름이 `.`으로 시작 / Windows 숨김·시스템 속성 / 심볼릭 링크·정션 / 제외 폴더(`node_modules` 등) / 문서가 없는 폴더는 트리에 나오지 않는다. 제외 폴더는 사이드바 '자료' 목록에만 흐린 접힌 폴더로 나오고 펼칠 때 안을 읽는다 (D49 — 숨김은 거기에도 없다). html 은 앱 소스·빌드 폴더(`src`·`public`·`static`·`templates`·`web`·`www`·`frontend`·`out`) 안에서는 문서로 보지 않는다.
5. **코드 파일을 실행하지 않는다.** `os.startfile` 은 `.py`, `.js`, `.bat` 등을 실행해 버린다. 문서 속 링크는 `lectern/osutil.py` 의 `open_path()` 만 쓴다 (안전한 형식만 기본 앱, 나머지는 편집기나 탐색기). 프로그램은 이름만으로 띄우지 않는다 — Windows 는 현재 폴더에서 먼저 찾는데, `run.bat .`·탐색기 우클릭으로 띄우면 현재 폴더가 열린 프로젝트다 (D29). 터미널은 사용자가 친 명령만 돌린다 (D38) — 셸은 전체 경로로 띄우고, 셸에 글자를 보내는 API 는 사용자의 키 입력을 받는 `POST /api/term/input` 하나뿐이다 (우클릭 메뉴의 '터미널에 붙여 넣기'도 이 길로, Enter 없이 — D51. 독립창의 것은 메인 창에 맡겨 이 길로 — D95).
6. **단순함 유지.** 레이아웃은 왼쪽 트리 하나 (툴바 아래 프로젝트 탭 막대, D34 — 문서 칸 위에는 그 프로젝트의 문서 탭 줄, 20개까지, D64·D67. 오른쪽 터미널은 열 때만, D38 — 창이 세로로 길면 문서 아래에, D52. 툴바의 '터미널 모음'은 탭이 아니라 화면을 덮는 보기다, D40. 문서 탭 줄의 '모두 펼치기'는 선택된 프로젝트의 문서 칸들과 터미널을 창 전체 격자에 놓는 보기다 — 칸을 옮기지 않고 CSS 만, D73. 사용설명서(F1)·발표 모드(D59)도 같은 방식, D45. 메모는 오른쪽에서 문서 위를 덮는 패널이다, D92. 독립창은 프로젝트에 속한 별도 창이고 문서 탭 줄과 문서가 기본이다, D95. 발표 문서는 독립창의 하나인 슬라이드 창에서 별도 스타일로 본다, D96. 탭 막대 오른쪽 끝에는 '편집'·'메모'와 오른쪽 패널을 보이고 감추는 '목차'·'터미널' 버튼 — 이 순서로). 번들러·프레임워크(React, Vite 등)를 들이지 않는다. `docs/ROADMAP.md` 의 "하지 않기로 한 것"은 사용자가 다시 요청하기 전에는 넣지 않는다.

## 실행과 확인

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt

python app.py samples              :: 창으로 실행 (Lectern 창이 떠 있으면 그 창에 탭으로 넘기고 끝남)
python app.py --browser samples    :: 개발용: http://127.0.0.1:8765 를 일반 브라우저로 (dev.bat)
python app.py --debug samples      :: 창 + 개발자 도구 (F12, 기본 Ctrl+F 등도 켜짐). --browser 와 함께 떠 있는 창에 넘기지 않고 따로 뜬다
python -m pytest -q                :: 단위 테스트 (Windows가 아니어도 돎)
python tools/ui_smoke.py           :: 화면 회귀 점검 (playwright 필요, 캡처는 ui-shots/)
python tools/ui_edges.py           :: 가장자리 점검 (tools/edges/, 이름을 주면 그 묶음만, --changed 면 고친 파일에 닿는 것만)
node tools/rules_check.mjs         :: 규칙 시험만 (브라우저 없이 1초 — pytest 에도 들어 있다)
build.bat                          :: 테스트 후 dist\Lectern\Lectern.exe, Inno Setup 이 있으면 dist\Lectern-버전-setup.exe
```

변경을 마치면 `pytest`(규칙 시험·JS 형 점검 포함, 약 15초)와 `python tools/ui_edges.py --changed`(고친 파일에 닿는 묶음만)를 돌린다. 판을 내기 전에는 `tools/ui_smoke.py` 와 `tools/ui_edges.py` 전체를 돌린다. 새 화면 점검은 `ui_smoke` 가 아니라 `tools/edges/` 에 더한다.
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
  search.py             전체 본문 검색 — 문서·코드 (/api/search)
  sheet.py              엑셀 보기 — xlsx·xlsm 의 시트 목록과 값을 zipfile·ElementTree 로 (/api/sheet, D77 — 보기만)
  editing.py            편집 모드 — 원문 주기·저장 (/api/source, /api/save, D54), 새 문서 만들기 (create, /api/new-doc, D63·D65)
  notes.py              프로젝트 메모 — .lectern/notes.md 하나 (/api/notes, D92)
  styles.py             내 스타일 — 설정 폴더 styles\*.css 목록·머리 주석·인터넷 길 지우기 (/api/styles, /userstyle/*, D53)
  i18n.py               서버 문구의 언어 — t()·N_()·EN 사전, 설정 language(auto 는 Windows 표시 언어)
  osutil.py             링크 대상 열기 (기본 앱 / 편집기 / 탐색기)
  native.py             pywebview js_api — 폴더 대화상자, 창 제목, 독립창 열고 닫기, 발표 모드의 전체 화면만
  windows.py            독립창 — 창 목록, 프로젝트를 고를 때 숨기고 보이기, 함께 닫기 (D95)
  terminal.py           오른쪽 터미널: 탭마다 셸 하나, 출력 버퍼·긴 폴링 (/api/term/*)
  conpty.py             Windows 의사 콘솔(ConPTY)을 ctypes 로 — 셸 하나를 작업 개체 안에서
  paths.py              리소스·설정 경로 (PyInstaller 대응)
web/
  index.html            앱 뼈대. vendor 스크립트 로드 후 js/main.js
  js/                   ES modules (아래 표)
  css/app.css           앱 UI 스타일
  css/frame.css         html 문서(iframe) 안에 넣는 찾기·바뀐 곳·우클릭 표시
  themes/               문서 본문 스타일: base.css + 스타일마다 <id>.css (목록은 theme.js 의 THEMES)
  help/manual.md        사용설명서 (F1 — help.js 가 그린다). 영어판은 manual.en.md
  help/styles.md        내 스타일을 만드는 AI 용 설명서 (D53 — 설정 창의 요청 글이 이 파일의 경로를 준다). 영어판은 styles.en.md
  help/slides.md        발표 문서를 쓰는 AI 용 작성 안내 (D96 — 문법·배치·분량 기준. 영어판은 slides.en.md)
  help/writing.md       Lectern 에서 잘 보이는 문서를 쓰는 AI 용 작성 안내 (D57 — 설정 창 'Claude Code 에 Lectern 알려 주기'의 요청 글이 경로를 준다). 영어판은 writing.en.md
  js/lang/en.js         영어 사전 (한국어 문구 → 영어, JSON)
  vendor/               외부 라이브러리 (tools/update_vendor.py 로만 갱신, 직접 수정 금지)
samples/                사람·AI 용 예제 프로젝트 (D57 — 설치 파일에 들어가고 '예제 열기'로 연다. 점검용 함정은 넣지 않는다. slides/ 는 슬라이드 모범 예제 10개와 만드는 과정 — D96)
assets/                 앱 아이콘 (lectern.svg → tools/make_icon.py → lectern.ico)
installer/              lectern.iss — Inno Setup 설치 파일 스크립트 (build.bat 이 씀)
tests/                  pytest. tests/corpus/ 는 표 읽기의 기준 자료, tests/fixture/ 는 화면 점검(ui_smoke)이 쓰는 점검용 프로젝트 (숨김·제외 케이스 포함 — 파일 이름·문장을 점검이 확인한다)
tools/                  update_vendor.py, ui_smoke.py, ui_edges.py(+ edges/ — 묶음마다 임시 프로젝트로 띄우는 가장자리 점검), rules_check.mjs(규칙 시험), types/(JS 형 — lectern.d.ts, 설정은 맨 위의 tsconfig.json), context_menu.py, make_icon.py, vendor-licenses/(패키지에 없는 라이선스 전문 — Viz.js 와 안에 든 Graphviz·Expat, zrender, d3)
docs/                   VISION(방향 — 마름모형 리서치 방법), ARCHITECTURE, MODULES, PITFALLS, DECISIONS, ROADMAP, HISTORY, TESTING, MARIMO(걷은 marimo 화면의 원인 기록 — D70), images/(README 화면)
LICENSE                 MIT (공개 저장소 github.com/samiblog/lectern — 설치 파일은 Releases)
THIRD-PARTY-NOTICES.md  설치 파일에 든 오픈소스의 라이선스 전문. Python 의존성·web/vendor 를 바꾸면 함께 고친다
```

JS 모듈이 하는 일은 `docs/MODULES.md` 의 표에 있다.

## 코딩 규칙

- Python 3.10+ (3.12+ 권장), 타입 힌트, 표준 라이브러리 우선. 정션은 `DirEntry.is_junction`(3.12+) 대신 `st_reparse_tag` 로 판정하므로 3.10·3.11에서도 걸러진다.
- 새 Python 의존성은 꼭 필요할 때만. 넣으면 `requirements.txt` 와 `docs/DECISIONS.md` 에 이유를 남긴다. 사내망 설치는 wheel 반입이 필요하다는 점을 잊지 않는다. 버전은 `==` 로 고정하고, 요구사항 파일 첫 줄의 `coding: utf-8` 선언은 지우지 않는다 (D22: 없으면 한국어 Windows의 pip 24 이하가 한글 주석을 못 읽는다).
- JS는 전역을 쓰지 않는다. 예외는 vendor 전역(`markdownit`, `markdownItAnchor`, `markdownitFootnote`, `markdownitTaskLists`, `hljs`, `katex`, `DOMPurify`, `mermaid`, 터미널을 처음 열 때 불러오는 `Terminal`·`FitAddon`·`Unicode11Addon`, 처음 편집할 때 불러오는 `CodeMirror`, 차트가 있는 문서를 처음 그릴 때 불러오는 `vega`·`vegaLite`·`echarts`·`Plotly`·`Viz`)과 `window.pywebview`.
- 화면에 HTML 을 넣을 때는 `html.js` 의 `html` 태그와 `setHtml`·`addHtml` 을 쓴다 (D89 — 값은 저절로 이스케이프된다, `innerHTML` 을 바로 쓰면 시험이 잡는다). 조각을 `+`·`.join('')` 으로 잇지 않고 배열로 넘긴다. `raw()` 는 정화를 거친 HTML 에만.
- 앱의 데이터 모양은 `tools/types/lectern.d.ts` 에 적는다 (`tsc` 가 개발할 때만 읽는다). 새 import 순환을 만들지 않는다 (시험이 잡는다).
- 앱 DOM id는 `lec-` 접두사를 붙인다. 문서 제목 앵커 id와 겹치지 않게 하기 위해서다. 문서 안 요소는 `#lec-view` 범위 안에서만 찾는다.
- UI 문구는 한국어로 쓰고 `t()` 로 감싼다 (JS 는 `t('…')`, 템플릿 글자 안이면 `${t('…')}`, 값은 `t('문서 {n}개', { n })` — Python 은 `i18n.t`). 영어는 `web/js/lang/en.js`·`lectern/i18n.py` 의 `EN` 에 같이 넣는다 (`tests/test_i18n.py` 가 감싸지 않은 한국어와 빠진 영어를 잡는다, D46). 한국어 문구는 짧은 평서문. 오류 메시지는 무엇이 안 됐고 어떻게 하면 되는지 말한다 ('F5 를 누르면 다시 불러옵니다'처럼 — 'F5 로 다시 불러옵니다'는 저절로 되는 것처럼 읽힌다).
- 같은 것은 같은 이름으로 (v0.13.1 점검): 그림(이미지 아님 — 인터넷 그림), 박스글(콜아웃·인용 상자), 누르기(클릭 아님), 거르기, 장 하이라이트·하이라이트 해제, '자료' 목록(사이드바 '파일' 탭 안의 문서도 코드도 아닌 파일 — D48, 안쪽 이름은 others·files), 터미널 모음, 모아 보기. 툴바의 Ctrl+P 버튼은 '문서 열기'(이름·제목으로 열기)이고, '검색'은 본문 검색, '문서에서 찾기'는 Ctrl+F 다. 말줄임은 '…' 한 글자.
- API를 추가·변경하면 `docs/ARCHITECTURE.md` 의 API 표를 같이 고친다. 설계 판단은 `docs/DECISIONS.md` 에 한 항목으로 남긴다.
- 단축키는 `help.js` 의 `SHORTCUTS` 하나에 적는다 (단축키 표와 설명서의 '단축키' 장이 이것으로 만들어진다).

## 알아 둘 함정

`docs/PITFALLS.md` 에 영역별로 모았다. **그 영역을 고치기 전에 해당 절을 읽는다.**

| 고치는 곳 | 읽을 절 |
|---|---|
| 터미널·셸·`/api/term` | 터미널 |
| `lineedit`·`lineops`·`slideops`·`spotlight`·`editor`·`basket`·`notes`·뒤로 기록 | 한 줄 편집·줄 구조·편집 모드·보내기 |
| `csvview`·`tabledata`·`codeview`·`others`·`sheet.py` | 데이터 보기·코드 화면·파일 목록 |
| `panes`·`doctabs`·`tabs`·`spread`·`nav` | 화면 구조·칸·탭 |
| `doc`·`markdown`·`toc`·`parts`·`charts`·`slides`·`slidelint`·`csssafe`·`slidetools`·`htmldoc` | 문서 그리기 |
| 스타일·`t()`·`writing.md`·예제 | 스타일·문구·예제 |
| `server.py`·`scanner.py`·`config.py`·`app.py`·`index.html`·설치 | 서버·설정·설치 |

## 기능을 마칠 때

고칠 문서는 이것뿐이다. 그 밖의 문서는 그 내용이 틀려졌을 때만 고친다.

- 설계 판단이 있으면 `docs/DECISIONS.md` 에 한 항목.
- 사용자가 보는 것이 바뀌면 `web/help/manual.md`·`manual.en.md`. 새 문구는 `web/js/lang/en.js` (시험이 잡는다).
- API 가 바뀌면 `docs/ARCHITECTURE.md` 의 API 표. 새 JS 모듈이면 `docs/MODULES.md` 의 한 행 (시험이 잡는다).
- 판을 낼 때만: `lectern/__init__.py` 의 버전, 이 파일의 현재 버전, `docs/HISTORY.md` 맨 위에 한 줄.
- 새 기능은 `docs/VISION.md` 의 어느 단계·구간을 돕는지 DECISIONS 항목에 적는다.
