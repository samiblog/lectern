# 테스트

## 1. 자동 테스트

```bat
python -m pytest -q          :: 단위·API 테스트 (Windows가 아니어도 됨)
python tools/ui_smoke.py     :: 화면 회귀 점검 (playwright + chromium 필요)
```

| 파일 | 다루는 것 |
|---|---|
| `tests/test_scanner.py` | 숨김·제외·빈 폴더, 자연 정렬, 심볼릭 링크·정션 제외(정션은 Windows에서만), `resolve_inside` 경로 차단 |
| `tests/test_search.py` | 전체 검색: 대소문자 무시, 줄 번호(frontmatter·`\r\n`), 숨김·제외 안 찾음, 제목 일치 먼저, 개수 제한·잘라 보이기 |
| `tests/test_docinfo.py` | 제목·요약 추출 규칙, 캐시 |
| `tests/test_changes.py` | ChangeLog 순번, 이벤트 필터, 폴링·watchdog 감지 |
| `tests/test_server.py` | 모든 API, 토큰, Host 검사, 설정 키 제한, 숨김·밖 경로 404, `/` 의 CSP, 레지스트리와 상관없는 정적 파일 형식 |
| `tests/test_config.py` | 설정 파일을 읽지 못하면 덮어쓰지 않음(고치면 다시 저장), BOM 허용, 실행 중 밖에서 고친 값 유지, 마지막 위치 개수 제한 |
| `tests/test_osutil.py` | 링크 대상 열기 방식 (코드 파일은 실행하지 않음) |
| `tests/test_app.py` | 설정의 창 크기 읽기 (형식이 틀리거나 너무 작을 때) |
| `tools/ui_smoke.py` | 트리, 렌더링(표·콜아웃·코드·각주·수식·달러·Mermaid, `## Mermaid` 제목 충돌), 제목·표 머리행 색, 제목 접기(하위 절, 각주 제외, 목차·찾기로 펴기, 두 번 누름·Shift+클릭은 접지 않음, 새로고침 뒤 유지), 본문 우클릭 메뉴(원문 줄 범위, 원문·절·표·그림·선택한 글 복사, Claude용 위치, 문서 메뉴, 다이어그램 글자, 인터넷 그림은 주소만 — 복사 결과는 headless 클립보드에서 읽음), 바뀐 부분 강조(바뀐 블록만, '바뀐 곳' 버튼), 전체 검색(Ctrl+Shift+F, 줄 번호, 결과로 이동), 설정 창(Ctrl+,)과 마지막 위치 복원, 스타일 12종(글자 대비 4.5:1, 제목 색·표 머리행 구분, Mermaid 색, 다음 실행에도 유지), Ctrl+P, Ctrl+F, 자동 새로고침, 문서 속 원시 HTML(SVG 링크·이미지 맵·`img name` 이 앱을 망가뜨리지 않음), 외부 이미지(표시·실패 대체·끄기, 표 배경·SVG·`image-set` 으로 새지 않음), 보안, 외부 요청은 이미지뿐 |

`ui_smoke.py` 는 `samples/` 를 임시 폴더에 복사해 브라우저 모드 서버를 띄우고 headless Chromium으로 확인한다. 화면 캡처는 `ui-shots/` 에 저장되니, UI를 고친 뒤 캡처를 직접 열어 보는 것도 점검의 일부다.

새 기능을 넣을 때:
- 서버·스캔 쪽은 `tests/` 에 테스트를 추가한다.
- 화면 쪽은 `samples/` 에 확인용 내용을 넣고 `ui_smoke.py` 에 `check(...)` 를 추가한다. 무언가를 기다릴 때는 `wait_for_timeout(고정 시간)` 대신 `wait_until(page, '조건')` 을 쓴다 (느린 PC에서 간헐적으로 실패하지 않게). 실패 메시지에는 실제 값을 붙인다.

## 2. Windows 수동 점검표

자동 테스트로 확인할 수 없는 Windows 고유 동작이다. 릴리스 전, 그리고 관련 코드를 고쳤을 때 수행한다.
`samples` 폴더를 다른 곳에 복사해서 쓴다 (원본을 바꾸지 않도록).

### 준비
```bat
xcopy /E /I samples %TEMP%\lec-check
attrib +h %TEMP%\lec-check\docs\03-다이어그램.md
mkdir %TEMP%\lec-target & echo # far > %TEMP%\lec-target\far.md
mklink /J %TEMP%\lec-check\junction %TEMP%\lec-target
python app.py %TEMP%\lec-check
```

### 점검 항목

| # | 할 일 | 기대 결과 |
|---|---|---|
| 1 | 창이 뜨면 트리 확인 | '다이어그램'(숨김 속성), `junction`, `.claude`, `node_modules`, `empty-folder` 가 보이지 않음 |
| 2 | 주소창 대신 링크로 숨김 문서 접근: `01-기능-점검` 의 '다이어그램의 첫 예시' 링크 클릭 | '문서가 없거나(삭제·이동) 숨김 경로에 있습니다.' 화면 |
| 3 | 툴바 '폴더 열기' | Windows 폴더 선택 대화상자가 열리고, 고른 폴더가 열림 |
| 4 | '최근 연 폴더' 화살표 | 방금 연 폴더들이 목록에 있음 |
| 5 | `01-기능-점검` 의 'example.py 13번째 줄' 링크 | VS Code가 있으면 13번째 줄로 열림. 없으면 탐색기에서 파일이 선택됨. **파이썬으로 실행되면 안 됨** |
| 6 | 트리에서 파일 우클릭 → '@경로 복사' 후 메모장에 붙여넣기 | `@docs/01-기능-점검.md` |
| 7 | 우클릭 → '전체 경로 복사' | `C:\...\lec-check\docs\01-기능-점검.md` (역슬래시) |
| 8 | 우클릭 → '탐색기에서 보기' | 탐색기에서 해당 파일이 선택됨 |
| 9 | 편집기로 `plans\10-후속-과제.md` 를 고쳐 저장 | 1~2초 안에 트리 제목·개요가 바뀌고 호박색 점 표시. 그 문서를 보고 있었다면 스크롤 위치를 유지한 채 다시 그려짐 |
| 10 | 탐색기에서 새 md 파일을 만들고 이름 바꾸기 | 새 이름으로 트리에 나타남 |
| 11 | Windows 설정 → 개인 설정 → 색 → 앱 모드를 어둡게 (테마 '자동') | 뷰어가 다크로 바뀜 |
| 12 | Ctrl+F, Ctrl+P, Ctrl+B, Alt+←, F5, 마우스 뒤로 버튼 | 각각 찾기, 빠른 열기, 사이드바, 뒤로, 다시 불러오기, 뒤로 |
| 13 | Ctrl+휠 | 확대/축소 |
| 14 | 외부 링크(markdown-it) 클릭 | 기본 브라우저에서 열림 |
| 14a | 인터넷 이미지가 든 문서 (예: `![](https://upload.wikimedia.org/...png)`) | 사내망에서 허용된 주소면 그림이 보이고, 막힌 주소면 15초 안에 '외부 이미지를 불러오지 못했습니다' 링크로 바뀜 |
| 15 | 창 크기를 바꾸고 닫았다가 다시 실행 | 같은 크기로 열리고, 마지막 폴더가 열림 |
| 15a | 창을 최대화한 채 닫고 다시 실행 / 최소화한 채 작업 표시줄에서 닫고 다시 실행 | 둘 다 15에서 저장한 크기로 열림 (화면만 한 일반 창이나 아주 작은 창이 아님) |
| 15b | 다른 폴더의 명령 창에서 `<Lectern 폴더>\run.bat .` | 그 명령 창의 폴더가 열림 |
| 16 | 한글·공백·괄호가 든 폴더/파일 이름 (예: `분석 (최종)\결과 1.md`) | 트리 표시, 열기, 링크 이동 모두 정상 |
| 17 | `\\서버\공유` 같은 네트워크 폴더 (해당되면) | 열리고 변경 감시가 동작 (안 되면 상태줄이 '주기 확인'인지 확인) |
| 18 | `01-기능-점검` 의 표 우클릭 → '표 복사' 후 엑셀과 워드에 붙여넣기 / 그림 우클릭 → '그림 복사' 후 PPT·그림판에 붙여넣기 | 엑셀은 칸이 나뉘고 워드는 표 모양. 그림이 붙음 (`ui_smoke` 는 headless 클립보드만 보므로 실제 앱에 붙는지는 여기서 본다) |
| 19 | 제목 우클릭 → 'Claude용 위치 복사' 후 Claude Code 프롬프트에 붙여 묻기 | Claude가 그 파일의 해당 줄 범위를 읽고 답함 |

### 패키징 점검
```bat
build.bat                                  :: dist\Lectern\Lectern.exe + dist\Lectern-버전-setup.exe
dist\Lectern\Lectern.exe %TEMP%\lec-check
python tools\context_menu.py               :: 설치 파일 없이 쓸 때 (P2~P4)
```
| # | 할 일 | 기대 결과 |
|---|---|---|
| P1 | Python이 없는 PC에 `dist\Lectern` 폴더째 복사 후 실행 | 창이 뜨고 위 1~15가 동일하게 동작 |
| P2 | 폴더 우클릭 → (Windows 11: 더 많은 옵션 표시) → 'Lectern으로 열기' | 그 폴더로 열림 |
| P3 | 폴더 안 빈 곳 우클릭 → 'Lectern으로 열기' | 현재 폴더로 열림 |
| P4 | `python tools\context_menu.py --remove` | 메뉴가 사라짐 |

### 설치 파일 점검
| # | 할 일 | 기대 결과 |
|---|---|---|
| I1 | `dist\Lectern-버전-setup.exe` 실행 (기본 선택 그대로) | 관리자 권한 요청 없이 한국어 화면으로 설치되고, 마지막에 'Lectern 실행'을 고르면 창이 뜸 |
| I2 | 시작 메뉴에서 Lectern 실행 | 아이콘(독서대 위의 책)이 보이고, 마지막 폴더·스타일로 열림 |
| I3 | 폴더 우클릭 / 폴더 안 빈 곳 우클릭 → 'Lectern으로 열기' | 설치한 Lectern으로 그 폴더가 열림 |
| I4 | Lectern을 켜 둔 채 같은(또는 새) 버전 설치 파일을 다시 실행 | Lectern을 닫으라고 안내하고 덮어 설치됨 |
| I5 | Windows 설정 → 앱 → Lectern 제거 | 시작 메뉴·우클릭 메뉴·설치 폴더가 사라지고 `%APPDATA%\Lectern\config.json` 은 남음 |
| I6 | Python이 없는 PC에서 I1~I3 | 같게 동작 (P1과 함께) |

## 3. 정리
```bat
rmdir %TEMP%\lec-check\junction
rmdir /S /Q %TEMP%\lec-check %TEMP%\lec-target
```
