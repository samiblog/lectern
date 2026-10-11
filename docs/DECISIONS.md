# 설계 결정 기록

결정마다 무엇을 골랐고 왜 그랬는지 남긴다. 결정을 바꿀 때는 항목을 지우지 말고 "변경" 줄을 덧붙인다.
새 결정은 맨 아래에 번호를 이어서 쓴다.

---

## D1. 용도: Claude가 만든 프로젝트 문서를 보기만 한다

- **결정**: 편집 기능, DRM·클라우드 드라이브(OneDrive 등) 대응, cp949 인코딩 대응을 넣지 않는다. 프로젝트 폴더와 그 하위만 본다.
- **이유**: 사용자는 Claude Code / Claude가 쓴 리서치·계획·설계 문서를 일목요연하게 읽으려고 한다. Claude가 쓰는 파일은 UTF-8이고 로컬 프로젝트 폴더에 있다.
- **영향**: 요구가 바뀌지 않는 한 위 기능은 다시 넣지 않는다.

## D2. Python + pywebview(WebView2) + 순수 JS

- **결정**: 창은 pywebview, 렌더링은 웹 기술. C#/WebView2, Tauri, Electron은 쓰지 않는다.
- **이유**: 사용자가 Python·JS에 익숙하고 사내망에서 Rust·.NET 개발 환경을 갖추기 어렵다. Electron은 무겁다. pywebview는 Windows에서 Edge WebView2(Chromium)를 써서 최신 CSS·JS 기능을 그대로 쓸 수 있다.
- **대가**: 배포본이 수십 MB(PyInstaller). 실행 파일 첫 기동이 Python 앱보다 약간 느리다.

## D3. 자체 HTTP 서버(werkzeug)를 띄우고 창에 URL을 넘긴다

- **결정**: `create_window(url=<WSGI 앱>)` 대신 `werkzeug.serving.make_server('127.0.0.1', port, app, threaded=True)` 를 스레드로 돌리고 `http://127.0.0.1:<포트>/` 를 창에 연다.
- **이유**: 창 모드와 브라우저 개발 모드(`--browser`)가 완전히 같은 서버를 쓴다. 바인딩 주소·스레딩·포트를 직접 통제한다.
- **처음 제안과 다름**: 초기 구상은 pywebview에 Flask 앱을 직접 넘기는 방식이었다.

## D4. 네이티브 기능만 js_api, 나머지는 HTTP API

- **결정**: `js_api` 에는 폴더 선택 대화상자와 창 제목만 둔다.
- **이유**: 브라우저 모드에서 UI 전체를 확인·자동 테스트(playwright)할 수 있다. 문서 상대경로(`./img/a.png`)를 브라우저의 URL 해석에 그대로 맡길 수 있다.

## D5. Markdown은 프런트엔드(markdown-it)에서 렌더링

- **결정**: 서버는 원문만 주고, 변환·후처리는 JS가 한다.
- **이유**: 테마 전환·다시 그리기가 즉시 되고, Mermaid·KaTeX·highlight.js 같은 웹 라이브러리를 그대로 쓴다. 서버는 파일 전달과 경로 검사만 맡아 단순해진다.

## D6. 외부 라이브러리는 web/vendor 에 번들, 빌드 단계 없음

- **결정**: npm 패키지에서 배포용 파일만 복사해 저장소에 넣는다 (`tools/update_vendor.py`). 번들러·트랜스파일러 없이 ES modules로 쓴다.
- **이유**: 사내망 PC에서 npm이 필요 없다. 실행 중 외부 요청이 없다. 빌드 도구가 없어 Claude Code가 고치고 바로 확인하기 쉽다.
- **버전**: `web/vendor/VERSIONS.json`. 올릴 때는 `tools/ui_smoke.py` 를 다시 돌린다.

## D7. 레이아웃은 왼쪽 트리 하나

- **결정**: 처음 구상한 3종(왼쪽 트리 / 상단+왼쪽 / 탭)과 자동 추천을 버리고 접을 수 있는 왼쪽 트리 하나로 간다. 열린 문서 탭 대신 뒤로/앞으로 기록.
- **이유**: Claude 프로젝트 폴더는 트리 하나로 충분하다. 레이아웃 3종은 만드는 비용에 비해 '보기'에 기여가 작다. 대신 폴더 개요 화면과 최근 변경으로 한눈에 보기를 해결한다.

## D8. 폴더 개요 화면이 첫 화면

- **결정**: 폴더를 누르거나 프로젝트를 열면 개요(최근 변경 레일, 하위 폴더, 문서별 제목·요약·수정 시각)를 보여 준다.
- **이유**: 문서를 하나씩 열지 않고 무엇이 있는지, 무엇이 방금 바뀌었는지 파악하는 것이 이 도구의 핵심 가치다.
- **보류**: 마지막에 본 문서로 시작하는 옵션은 ROADMAP에 있다.

## D9. 변경 반영은 1초 폴링 (`/api/changes?since=seq`)

- **결정**: 서버는 watchdog 이벤트를 순번 붙여 기록하고, 프런트가 1초마다 새 기록만 가져간다.
- **이유**: `window.state` 푸시(pywebview)는 브라우저 모드에서 동작하지 않는다. SSE는 서버 스레드를 오래 잡는다. 로컬 1초 폴링은 비용이 거의 없고 두 모드에서 똑같이 동작한다. 창이 가려지면(`document.hidden`) 쉰다.
- **대체**: watchdog가 없으면 서버가 2초 간격 스캔 비교로 같은 기록을 만든다.

## D10. 자동 새로고침 때 화면 밖에서 먼저 그린다

- **결정**: 문서를 `.lec-stage`(화면 밖, visibility:hidden)에 그린 뒤 한 번에 바꿔 끼우고 스크롤을 복원한다.
- **이유**: Claude가 문서를 쓰는 동안 여러 번 다시 그려도 깜박임·스크롤 튐이 없어야 한다. Mermaid는 DOM에 붙어 있어야 크기를 잴 수 있어 분리된 노드에서는 그릴 수 없다.

## D11. 코드 파일 링크는 실행하지 않는다

- **결정**: 이미지·PDF·오피스 등 안전한 형식만 기본 앱으로 열고, 코드·스크립트·그 밖의 파일은 편집기(`code -g 파일:줄`)로, 편집기가 없으면 탐색기에서 선택만 한다.
- **이유**: Windows에서 `.py`·`.js`·`.bat`·`.ps1` 의 기본 동작은 실행이다. 문서 링크를 누르다가 스크립트가 실행되면 안 된다. 뷰어 안에 코드 보기 화면은 만들지 않는다 (D7과 같은 이유).
- `code.cmd` 는 배치 파일이라 `&` 같은 문자가 명령으로 해석될 수 있어, 그런 문자가 든 경로는 탐색기로 보낸다.

## D12. 수식의 `$` 는 pandoc 규칙

- **결정**: 여는 `$` 뒤와 닫는 `$` 앞에 공백이 없어야 하고, 닫는 `$` 바로 뒤가 숫자가 아니어야 하며, 첫 번째 닫는 후보만 본다.
- **이유**: 원자재 리서치 문서에는 `$105/t`, `$95~$110` 같은 달러 표기가 많다. 일반적인 `$…$` 규칙은 이것을 수식으로 망가뜨린다.
- **보완**: 전체 끄기는 설정 `math: false`.

## D13. Ctrl+F 찾기는 직접 구현 (CSS Custom Highlight API)

- **결정**: `find.js` 가 텍스트 노드를 훑어 Range를 만들고 `CSS.highlights` 로 표시한다.
- **이유**: pywebview는 디버그가 아닐 때 `AreBrowserAcceleratorKeysEnabled=False` 로 WebView2의 기본 찾기를 끈다 (pywebview 6.2 `edgechromium.py` 확인). Highlight API는 DOM을 바꾸지 않아 다시 그리기와 충돌하지 않는다.
- **한계**: 여러 텍스트 노드에 걸친 검색어(예: 굵은 글씨 경계)는 찾지 못한다.

## D14. CSP를 걸지 않는다

- **결정**: `index.html` 에 Content-Security-Policy를 두지 않는다.
- **이유**: pywebview가 js_api 결과를 돌려줄 때 `eval` 계열을 쓸 수 있어 `unsafe-eval` 없는 CSP와 충돌할 위험이 있다. 대신 DOMPurify 정화, 로컬 바인딩, 토큰, Host 검사로 막는다.
- **재검토 조건**: 창 모드에서 CSP를 걸고 js_api·Mermaid가 모두 동작하는지 확인되면 추가한다.
- **변경 (v0.1.3)**: 스크립트·스타일 지시어를 뺀 CSP는 eval 문제와 부딪치지 않으므로 건다. 이미지·연결·글꼴 출처만 제한한다 (D20). `script-src` 는 여전히 두지 않는다.

## D15. DOMPurify `SANITIZE_DOM: false`

- **결정**: DOM clobbering 보호를 끈다.
- **이유**: 기본값이면 `id="title"`, `id="images"` 처럼 `document` 속성과 이름이 같은 제목 앵커가 지워져 목차·앵커 링크가 깨진다. 문서는 사용자 자신의 로컬 파일이고, 앱 코드는 문서 영역 밖에서 `document.<이름>` 전역 참조를 쓰지 않으며 앱 id는 `lec-` 접두사를 쓴다.
- **재검토 필요 (v0.1.3 검토)**: 위 이유의 일부가 사실과 다르다. 앱은 `document.querySelector`·`createElement`·`body`·`title` 을 쓰고, 문서 속 `<img name="querySelector">` 가 이것을 가린다 (화면이 멈춤). 제목 id(`<h2 id="title">`)는 `document` 속성을 가리지 않으므로, `SANITIZE_DOM` 을 끈 채 `img` 의 `name` 만 지우는 방안을 검토한다. ROADMAP '알려진 문제' 참고.
- **변경 (v0.1.3)**: 위 방안대로 한다. `SANITIZE_DOM: false` 는 그대로 두고, 정화 훅이 `img` 의 `name` 을 지운다. `document` 의 이름을 가릴 수 있는 요소 가운데 DOMPurify가 허용하는 것은 `img` 뿐이다 (`form` 은 금지, `embed`·`object`·`iframe` 은 DOMPurify가 막음). `window.<id>` 는 진짜 전역을 가리지 못하므로, 늦게 불러오는 전역(mermaid)만 조심한다 (CLAUDE.md 함정).

## D16. 제목 앵커는 GitHub 규칙

- **결정**: slug = 소문자, 글자·숫자·`_`·공백·`-` 외 제거, 공백 → `-`. 한글은 유지.
- **이유**: Claude가 문서에 쓰는 목차 링크(`[개요](#1-개요)`)가 GitHub 규칙을 따른다.

## D17. 로컬 서버는 Host 헤더를 검사한다

- **결정**: `Host` 가 `127.0.0.1`·`localhost` 가 아닌 요청은 403.
- **이유**: 토큰이 없는 `/doc/*` 를 DNS 리바인딩으로 읽어 가는 것을 막는다.

## D18. 이름은 Lectern (렉턴)

- **결정**: 프로젝트·실행 파일·패키지 이름을 'MD Viewer'에서 **Lectern** 으로 바꾼다 (v0.1.1). 코드 이름 `lectern`, 실행 파일 `Lectern.exe`, 설정 폴더 `%APPDATA%\Lectern`, 앱 DOM 접두사 `lec-`.
- **이유**: 나중에 HTML 문서도 볼 예정이라 형식(md)이 이름에 들어가면 안 된다. 목적은 프로젝트 문서를 '기계가 아닌 사람이' 일목요연하게 보는 것이다. 독서대(lectern)는 사람이 문서를 펼쳐 놓고 읽는 받침대라 형식과 무관하게 이 목적을 담는다. 짧은 영문이라 터미널에서 `lectern .` 으로 치기 쉽다.
- **검토한 다른 이름**: 열람실(Readroom), 일람(Illam), Glance(같은 이름이 흔함). Docent(도슨트)는 뜻이 가장 잘 맞았지만 AI 에이전트 기록 분석 도구(Transluce Docent)가 이미 쓰고 있어 뺐다.
- **영향**: 새 코드·문서에 'md 전용'을 전제로 한 이름을 새로 만들지 않는다. 기존 `is_md`·`MD_EXT` 같은 이름은 HTML을 붙일 때(ROADMAP 4단계) 형식 표로 바꾼다.

## D19. 문서 속 외부 이미지는 보여 준다 (설정으로 끌 수 있음)

- **결정**: 문서에 들어 있는 `http(s)` 이미지를 불러와 표시한다 (v0.1.2). 설정 `external_images`(기본 `true`)로 끌 수 있다. referrer를 보내지 않고, 오류·15초 초과면 원래 주소로 가는 링크로 바꾼다.
- **변경**: v0.1.1까지는 로컬 전용 원칙에 따라 외부 이미지를 링크로만 보여 주었다. 사용자가 외부 이미지를 보기를 원해서 바꿨다.
- **유지하는 것**: 앱 자체의 외부 요청 금지(CDN·웹폰트 등), 프로젝트 밖 로컬 경로 차단, `srcset`·`poster`·CSS `url()` 제거. 외부 요청이 허용되는 길은 `<img>` 하나뿐이고 `tools/ui_smoke.py` 가 이를 확인한다.
- **감수하는 것**: 이미지 주소의 서버는 그 그림을 요청한 사실(IP, 시각)을 안다. 사내망에서 막힌 주소는 링크로 바뀐다.
- **HTML(ROADMAP 4단계)과의 관계**: 이 결정은 Markdown 속 이미지에 대한 것이다. HTML 문서의 스크립트·CDN 허용 여부는 4단계에서 따로 정한다.
- **변경 (v0.1.3)**: v0.1.2에서는 `<img>` 가 아닌 길 — 표의 `background`, SVG `image`·`feImage` 의 href, SVG `fill`·`mask`·`clip-path`·`marker` 의 `url()`, style 의 `image-set()` — 로 외부 그림을 불렀고, 설정을 꺼도 막히지 않았다. 정화 훅에서 이 길을 지우고 CSP로 한 번 더 막는다 (D20). 이제 외부 요청이 나가는 길은 정말 `<img>` 하나다.

## D20. 앱 페이지에 이미지·연결 출처만 제한하는 CSP를 건다

- **결정**: `GET /` 응답에 `img-src 'self' data: blob:`(설정 `external_images` 가 켜져 있으면 `http: https:` 추가), `media-src 'self'`, `font-src 'self' data:`, `connect-src 'self'`, `object-src 'none'`, `frame-src 'none'`, `base-uri 'none'`, `form-action 'none'` 을 붙이고, `Referrer-Policy: no-referrer` 를 함께 보낸다 (`server.py` `content_security_policy`).
- **이유**: 문서 HTML은 앱과 같은 출처에서 그려진다. DOMPurify 허용 목록은 넓어서 정화 훅만으로는 그림을 부르는 길을 다 막았다고 장담하기 어렵다 (v0.1.2에서 10가지가 새었다). 브라우저가 출처를 막으면 훅이 놓친 길도 막힌다.
- **두지 않는 것**: `default-src`·`script-src`·`style-src`. pywebview가 eval 계열을 쓸 수 있고 (D14), KaTeX·Mermaid는 인라인 스타일을 쓴다.
- **영향**: 설정 `external_images` 를 바꾸면 페이지를 다시 불러와야 CSP가 바뀐다 (설정 창을 만들 때 저장 후 다시 불러오기). ROADMAP 4단계에서 HTML 문서를 `<iframe>` 으로 보일 때는 `frame-src 'self'` 로 바꾼다.

## D21. 설정 파일을 읽지 못하면 그 실행 동안 저장하지 않는다

- **결정**: `config.json` 이 있는데 읽지 못하면(JSON 문법 오류, 맨 바깥이 객체가 아님, 읽기 오류) 기본 설정으로 실행하되 저장하지 않는다. 이유와 위치(몇 행 몇 열)를 화면 알림(`/api/state` 의 `config_error`)과 stderr로 알린다. UTF-8 BOM은 오류로 보지 않는다.
- **이유**: README는 `editor`·`exclude_dirs` 를 손으로 고치라고 안내한다. Windows 경로의 역슬래시를 하나만 쓰거나(`"C:\Tools"`), 마지막 쉼표를 남기거나, 메모장·PowerShell 5.1이 BOM을 붙이면 파싱에 실패한다. v0.1.2는 이때 기본값으로 시작한 뒤 폴더를 여는 순간 파일을 덮어써서 사용자가 고친 내용이 조용히 사라졌다.
- **고르지 않은 방안**: 깨진 파일을 `config.json.broken` 으로 옮기고 새로 쓰기. 디스크에 `config.json` 외의 파일을 만들어 보기 전용 원칙(디스크에 쓰는 것은 설정 파일 하나)과 어긋난다.
- **대가**: 파일을 고칠 때까지 최근 폴더·테마·창 크기가 저장되지 않는다.
