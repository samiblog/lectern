# marimo 화면 — 0.50.0 에서 걷은 까닭과 다시 넣을 때

v0.50.0 은 터미널에서 띄운 marimo 화면을 문서 탭에 보였다. 사용자가 써 보고 '여러 가지로 불안정하다'고 해서 걷었고, 내지 않았다 (2026-10-27, [D70](DECISIONS.md), ROADMAP '하지 않기로 한 것').
이 문서는 2026-10-28 사용자가 겪은 문제를 하나씩 원인까지 확인한 기록이다. 다음에 marimo 기능을 다시 넣을 때 쓴다.
확인은 이 PC 에 `uv tool` 로 설치된 **marimo 0.25.2**(`%APPDATA%\uv\tools\marimo`)의 소스와 실험으로 했다.

## 0.50.0 이 한 것

- **코드**: 커밋 `7bc81d2` "터미널 여러 개와 marimo (v0.50.0)". 어느 브랜치에도 없고 git reflog 에만 남아 있다. 보려면 `git show 7bc81d2:web/js/marimo.js`, 바뀐 파일 목록은 `git show 7bc81d2 --stat`. reflog 는 시간이 지나면 지워지므로 오래 둘 것이면 태그를 단다.
- **알아보기** (`terminal.js` 의 `watchMarimo`): 터미널 출력에서 색·커서 제어 문자를 걷는다. 그다음 'Edit 이름 in your browser'(marimo edit) 또는 'Running 이름'(marimo run) 뒤의 `URL: http://localhost:포트…` 를 찾아 'marimo' 이벤트를 보낸다.
- **보이기** (`marimo.js`): 화면 종류 `'web'` 으로 새 문서 탭에서 칸을 채우는 iframe 을 연다.
  - `sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-downloads"`, `allow="clipboard-read; clipboard-write"`.
  - 다른 포트라 출처가 달라 marimo 의 스크립트가 앱의 API·토큰에 닿지 못한다. 앱 CSP 에 `frame-src http://127.0.0.1:*` 를 더했다.
  - 주소의 `localhost` 는 `127.0.0.1` 로 바꿨다. marimo 로그인 쿠키가 SameSite=Lax 라 앱과 같은 사이트여야 산다.
- **'이 노트북을 marimo 로 열기'**: '코드' 목록의 .py 우클릭. 새 터미널에 `marimo edit --headless --skip-update-check '경로'` 를 Enter 없이 넣는다 (Enter 는 사용자가).
- **색**: 칸 바탕만 문서 스타일을 따랐다. marimo 안은 marimo 설정의 테마에 맡겼다.

## 문제 1. 브라우저가 따로 뜨고, marimo 는 그쪽에서 동작했다

**현상**: Lectern 터미널에서 `marimo edit` 를 실행하면 Lectern 에 marimo 화면이 뜬다. 그런데 동시에 기본 웹브라우저가 새로 뜨고, marimo 는 실제로 그 브라우저에서 동작했다.

**원인**: marimo 화면이 두 곳(Lectern iframe·브라우저)에 함께 붙었고, marimo 는 노트북 하나에 편집하는 화면을 하나만 둔다.

1. **브라우저를 여는 것은 marimo 다.** `--headless` 가 없으면 marimo 는 시작하면서 주소를 찍고, 0.02초 뒤 `webbrowser.open(url)` 으로 기본 브라우저를 연다.
   - `marimo/_server/start.py` 의 lifespan 차례가 `logging`(주소 찍기) → `open_browser` 다.
   - `marimo/_server/api/lifespans.py` 의 `open_browser` 가 `call_later(0.02, launch)` 하고, `_server/api/utils.py` 의 `open_url_in_browser` 가 브라우저를 연다.
2. **0.50 은 같은 주소를 출력에서 읽어 Lectern 에도 열었다.** 그래서 한 marimo 에 화면이 둘 붙었다.
3. **편집은 먼저 붙은 화면 하나만 한다.** 이미 편집 중인 화면이 있으면 다음 연결은 읽기 전용(INTERACTOR — kiosk mode)으로 붙는다.
   - `marimo/_server/api/endpoints/ws/ws_session_connector.py` 의 `_connect` 3b 와 `marimo/_session/consumer_policy.py` 의 `initial_capabilities` 가 이렇게 정한다.
   - 나중에 붙은 화면 위에는 "You are currently connected as a reader. [Take over]" 띠가 뜬다. Take over 를 누르면 편집 자리를 가져온다 (`POST …/takeover`).
4. **보통 브라우저가 먼저 붙는다** (추론 — 사용자가 본 현상과 맞음). 브라우저는 주소를 바로 받는다. Lectern 은 터미널 출력을 받고, 문서 탭을 열고, marimo 화면 파일을 iframe 에 불러온 뒤에야 붙는다. 그래서 Lectern 화면이 읽기 전용이 됐다.

**실험** (2026-10-28): `marimo edit --headless` 하나에 playwright 로 페이지 둘을 차례로 붙였다.
- 먼저 붙은 페이지는 보통 편집 화면이다.
- 두 번째 페이지는 "You are currently connected as a reader. [Take over]" 와 'kiosk mode' 로 나왔다.

**점검에서 놓친 까닭**: 0.50 에서 진짜 marimo 로 확인한 것은 우클릭 '이 노트북을 marimo 로 열기'뿐이었다. 이 길은 명령에 `--headless` 를 넣어 브라우저가 뜨지 않는다. 사용자가 터미널에 `marimo edit` 를 직접 치는 길은 가짜 주소로만 점검했다 (`ui_smoke`).

**다시 넣는다면**
- **화면은 한 곳에만 연다.** Lectern 은 사용자가 친 명령을 고칠 수 없다 (원칙 5, D38 — `--headless` 를 붙여 줄 수 없다).
  - 출력에서 주소를 보자마자 열지 않는다. 셸 아래에서 도는 marimo 프로세스의 명령줄을 읽어 `--headless` 일 때만 Lectern 에서 연다. 읽기만 하는 것이다 — `conpty.stuck_children` 처럼 작업 개체 안의 프로세스를 읽는 길이 이미 있다. 명령줄 읽기는 `NtQueryInformationProcess` 로 되는지 확인할 것.
  - `--headless` 가 아니면 '브라우저에서 열렸습니다 — Lectern 안에서 보려면 marimo edit --headless 로 실행하세요' 정도로 알린다.
- Lectern 은 다른 출처라 iframe 안을 읽지 못한다. Lectern 화면이 reader 가 됐는지 알 길이 없으니, 두 화면이 붙지 않게 하는 쪽으로 막는다.
- 사용자가 직접 치는 `marimo edit`(headless 없이)·`marimo edit --headless`·`marimo run` 을 모두 진짜 marimo 로 점검한다.

## 문제 2. marimo 화면이 흰 바탕이라 스타일이 전혀 맞지 않았다

**현상**: Lectern 을 어두운 스타일로 써도 marimo 화면은 흰 바탕(라이트 모드)으로 나왔다.

**원인**
- **marimo 설정이 light 였다.** 사용자의 marimo 설정 `C:\Users\samis\.config\marimo\marimo.toml` 은 `[display] theme = "light"` 다 (marimo 기본값).
- **0.50 은 marimo 안의 색을 marimo 설정에 맡겼다.** D70 에 "marimo 테마를 system 으로 두면 Windows 밝기를 따른다, Lectern 은 바꿀 수 없다"고 적었다. 그래서 Lectern 스타일과 상관없이 늘 흰 화면이었다.
  - system 테마는 iframe 안의 `prefers-color-scheme` 을 본다. 이것은 Windows(WebView2) 밝기를 따르고 Lectern 스타일은 따르지 않는다. 앱이 iframe 에 주는 `color-scheme` 으로도 바뀌지 않는다 (0.50 때 확인).
- **놓친 것 — 주소로 테마를 줄 수 있다.** marimo 화면은 주소의 `theme` 값(`light`·`dark`·`system`)을 설정 파일보다 먼저 본다.
  - `marimo/_static/assets/useTheme-*.js` 의 테마 = `?theme=` 값 ?? `config.display.theme`. `system` 이면 `prefers-color-scheme`.
  - 0.50 은 이것을 몰라 바꿀 수 없다고 판단했다.

**실험** (2026-10-28, 설정은 `theme = "light"` 그대로)

| 연 주소 | 결과 |
|---|---|
| `http://127.0.0.1:포트?access_token=…&theme=dark` | 어두운 화면 (`body.dark-theme`, 바탕 `#181c1a`). marimo 가 주소에서 `access_token` 은 지우지만 `?theme=dark` 는 남긴다. 10초 뒤에도 어두움 |
| 덧붙이지 않음 | 흰 바탕 (`body.light-theme`, `#ffffff`) |

**맞출 수 있는 것과 없는 것**
- **밝기는 맞출 수 있다.** iframe 주소에 지금 Lectern 스타일의 밝기를 `theme=dark` / `theme=light` 로 붙인다. 사용자 파일(marimo 설정)은 건드리지 않는다.
- **색표와 글꼴은 맞출 수 없다.** marimo 에는 자기 밝은·어두운 색표 두 가지뿐이다.
  - 출처가 달라 Lectern 이 CSS 를 넣지 못한다.
  - 주소로 받는 값은 `show-code`·`include-code`·`session_id`·`kiosk`·`vscode`·`file`·`access_token`·`view-as`·`show-chrome`·`theme` 뿐이고 (`_static/assets/utils-*.js`), CSS 를 넘기는 값은 없다.
  - 세부 색까지 맞추려면 marimo 의 custom CSS(설정 `[display] custom_css`, 노트북 `marimo.App(css_file=…)`)가 필요하다. 이것은 사용자 파일을 쓰는 일이라 Lectern 은 하지 않는다 (원칙 1). 사용자가 직접 할 수는 있다.

**다시 넣는다면**
- iframe 주소에 `theme=` 를 붙인다. 밝기는 지금 스타일에서 (`:root[data-ui="dark"]` — `theme.js` 의 밝기).
- 칸 바탕은 문서 스타일 바탕보다 marimo 바탕(어두우면 `#181c1a`, 밝으면 `#ffffff`)에 맞추는 편이 불러오는 동안 이음매가 덜 보인다.
- 스타일을 바꾸면 iframe 을 새 `theme` 로 다시 불러와야 한다. 그때 marimo 가 같은 세션(실행 결과)을 이어 받는지 확인할 것. marimo 는 끊긴 세션을 되잇는 길(`maybe_resume_session`)이 있다.

## VS Code marimo 확장에서 볼 것

**예전 확장 [marimo-team/vscode-marimo](https://github.com/marimo-team/vscode-marimo)** (2026-10-12 보관 — 아래는 보관 전 README 와 `src/launcher/controller.ts`·`src/browser/panel.ts`)
- **marimo 를 확장이 띄운다.** VS Code 터미널에 늘 `marimo edit --headless --port 2818 …` 로 넣는다 (토큰은 `marimo.enableToken`·`marimo.tokenPassword`). 그래서 브라우저가 따로 뜨지 않는다.
- **화면은 한 곳만.** 설정 `marimo.browserType` 이 `embedded`(기본 — VS Code 웹뷰 안의 iframe)면 거기, `system` 이면 기본 브라우저다. 둘을 함께 쓰지 않으니 문제 1 이 생길 수 없다.
- **`?vscode` 주소 값.** iframe 주소에 `vscode=true` 를 붙인다. 그러면 marimo 화면이 iframe 안일 때 몇 가지를 부모 창에 `postMessage` 로 넘긴다 (`_static/assets/useBoolean-*.js`, marimo 0.25.2 에도 있음).
  - 복사·잘라내기(`{command: 'copy'|'cut', text}`)
  - 붙여 넣기 요청(`{command: 'paste'}` — 부모가 클립보드를 읽어 `{command: 'paste', text}` 로 돌려준다)
  - 바깥 링크 누르기(`{command: 'external_link', url}` — iframe 안에서 떠나지 않는다)
  - 우클릭(`context_menu` — marimo 는 기본 메뉴를 막는다)
- **알려진 한계** (README): 끼워 넣은 브라우저에서는 PDF 보기, 녹음·녹화, 일부 복사·붙여 넣기가 안 된다.

**새 확장 [marimo-team/marimo-lsp](https://github.com/marimo-team/marimo-lsp)**
- marimo 웹 화면을 쓰지 않는다. VS Code 의 노트북 편집기(`notebooks` — `marimo-notebook`, `*.py`)에 marimo 커널을 돌리는 언어 서버와 UI 요소 렌더러(`application/vnd.marimo.ui+json`)를 붙인 것이다. 웹 서버·포트·iframe 이 없다.
- Lectern 에 노트북 편집기를 새로 만드는 일이라 보기 전용·단순함 원칙과 맞지 않는다. 가져올 것이 없다.

**Lectern 에 가져올 것**
- 늘 `--headless` 인 marimo 를 한 화면에서만 본다 (문제 1).
- `?vscode` 로 복사·붙여 넣기·바깥 링크를 받을지 볼 것.
  - WebView2 의 iframe 에 `allow="clipboard-read; clipboard-write"` 만으로 클립보드가 되면 필요 없다.
  - 쓴다면 부모(Lectern)가 메시지를 받는 곳에서 보낸 곳이 그 marimo 주소인지 확인한다.
  - 바깥 링크는 사용자가 누른 것이니 기본 브라우저로 열어도 원칙 2 에 맞는다.

## 다시 넣을 때 점검표

- 터미널에서 직접 `marimo edit`(headless 없이): 브라우저가 뜨는가, Lectern 화면은 어떻게 되는가 (열지 않고 알리기)
- `marimo edit --headless`·우클릭 '이 노트북을 marimo 로 열기': Lectern 화면 하나, 셀을 고치고 실행할 수 있는가 (reader 띠가 없는가)
- 밝은 스타일·어두운 스타일에서 marimo 밝기, 스타일을 바꾼 뒤
- 복사·붙여 넣기, 바깥 링크, 내보내기·다운로드
- marimo 를 Ctrl+C 로 끝낸 뒤의 화면, 터미널·탭을 닫은 뒤 남는 프로세스
  - 실험에서 uv 의 `marimo.exe`(실행기)만 끝내면 서버·커널 python 이 남았다. Lectern 터미널은 작업 개체째 끝내므로 남지 않아야 한다.
- 두 프로젝트 탭, 한 프로젝트의 여러 터미널, 터미널 모음

## 실험하는 법

- marimo 는 `uv tool` 의 python 으로 직접 띄운다: `%APPDATA%\uv\tools\marimo\Scripts\python.exe -m marimo edit --headless --skip-update-check --port 27191 nb.py`.
  - `%USERPROFILE%\.local\bin\marimo.exe` 는 uv 실행기라, 그것만 끝내면 서버·커널이 남는다. 끝낼 때는 `taskkill /T /F /PID <pid>` 로 나무째.
- 화면 둘·주소 값은 playwright(chromium)로 페이지를 열어 본다. 출력은 파일로 받는다 (파이프로 받으면 남은 자식 프로세스가 파이프를 잡아 기다림이 끝나지 않는다).
- marimo 소스: `%APPDATA%\uv\tools\marimo\Lib\site-packages\marimo` — 서버는 `_server/`, 화면은 `_static/assets/*.js`(빌드된 것 — 파일 이름의 해시는 판마다 다르다).

## 아직 확인하지 않은 문제

0.50.0 에서 사용자가 겪은 다른 문제가 더 있으면 같은 방식으로 원인을 확인해 여기에 더한다.
