# Lectern

Lectern(렉턴, 독서대)은 Claude Code나 Claude가 프로젝트 폴더에 만든 문서를 **사람이 한눈에 훑어보고 읽는** Windows용 로컬 뷰어입니다.
문서를 고치지 않고, 스스로 인터넷에 연결하지 않으며(문서 속 인터넷 그림만 예외, 설정으로 끌 수 있음), 고른 프로젝트 폴더 안만 봅니다.
지금은 Markdown 문서만 보고, HTML 문서는 다음 단계에서 지원할 예정입니다.

## 무엇을 하나

- **폴더 개요**: 방금 바뀐 문서(시간 레일), 하위 폴더, 문서마다 제목·요약·수정 시각
- **왼쪽 트리**: 파일명 대신 문서 제목, 필터, 열어 보기 전에 바뀐 문서에 호박색 점
- **자동 새로고침**: Claude가 문서를 쓰는 동안 1초 안에 반영, 보던 위치 유지
- **읽기 좋은 본문**: 숫자 열이 정렬된 표, 코드 하이라이트·복사, 콜아웃, 각주, 수식(`$105` 같은 달러 표기는 그대로), Mermaid 다이어그램, 이미지(프로젝트 안 그림과 인터넷 그림, 클릭하면 확대), 목차, 제목을 눌러 절 접기·펴기
- **스타일 3종**: 기본, 보고서(명조 본문), 다크 — '자동'은 Windows 다크 모드를 따름
- **빠른 이동**: Ctrl+P 빠른 열기, Ctrl+F 문서 안 찾기, 뒤로/앞으로, 트리 우클릭으로 `@경로` 복사(Claude Code 프롬프트용)
- 숨김 파일·폴더(`.claude`, `.git` 등), `node_modules` 같은 폴더, md가 없는 폴더는 보이지 않습니다.

## 설치

Python 3.10 이상(3.12 권장)과 Windows 10/11(WebView2 기본 포함)이 필요합니다. JS 라이브러리는 `web/vendor/` 에 들어 있어 npm은 필요 없습니다.

```bat
cd lectern
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 사내망(인터넷 차단) PC에 설치할 때

인터넷이 되는 Windows PC에서 같은 Python 버전으로 wheel을 받아 옮깁니다.

```bat
:: 인터넷 되는 PC
pip download -r requirements-dev.txt -d wheels

:: 사내 PC (wheels 폴더를 복사한 뒤)
pip install --no-index --find-links wheels -r requirements-dev.txt
```

`requirements-dev.txt` 에는 테스트·빌드 도구도 들어 있습니다. 실행만 할 거라면 `requirements.txt` 로 충분합니다.
버전은 확인한 판으로 고정되어 있어서(`==`), 언제 받아도 같은 판이 설치됩니다. 두 파일 첫 줄의 `coding: utf-8` 은 지우지 마세요. 오래된 pip가 한국어 Windows에서 파일을 읽지 못합니다.

## 실행

```bat
run.bat C:\work\my-project          :: 창으로 열기 (폴더 생략 시 마지막 폴더, run.bat . 은 지금 폴더)
python app.py C:\work\my-project    :: 같은 동작 (콘솔 창이 남음)
dev.bat                             :: 개발용: samples 를 브라우저 모드로 (http://127.0.0.1:8765)
```

Claude Code 터미널에서 지금 프로젝트를 바로 띄우려면 `Lectern.exe .` (exe를 PATH에 둔 경우).

## 실행 파일 만들기

```bat
pip install -r requirements-dev.txt
build.bat                           :: 테스트 후 dist\Lectern\Lectern.exe
python tools\context_menu.py        :: 탐색기 폴더 우클릭에 'Lectern으로 열기' 등록 (해제: --remove)
```

`dist\Lectern` 폴더째 복사하면 Python이 없는 PC에서도 실행됩니다.

## 사용법

### 폴더 열기
- 실행할 때 폴더를 주거나(위 '실행'), 창의 **폴더 열기**(Ctrl+O)로 고릅니다. 프로젝트 이름 옆 화살표에는 최근 연 폴더가 있습니다.
- 폴더 없이 실행하면 마지막에 연 폴더가 열립니다.

### 화면
- **폴더 개요**: 처음 화면입니다. 방금 바뀐 문서, 하위 폴더, 문서마다 제목·요약·수정 시각이 나옵니다. 트리에서 폴더 이름을 누르면 그 폴더의 개요가 나옵니다.
- **왼쪽 트리**: 파일명 대신 문서 제목을 보여 줍니다. 위 입력칸으로 거르고, '제목' 버튼을 끄면 파일명으로 보입니다. '최근 변경' 탭은 수정한 순서입니다.
- **본문**: 오른쪽 목차로 이동하고, 지금 읽는 위치가 목차에 표시됩니다. 제목을 누르면 그 절이 접히고 다시 누르면 펼쳐집니다. 그림을 누르면 크게 보이고, 코드 블록은 오른쪽 위 '복사' 버튼으로 복사합니다.
- **스타일**: 오른쪽 위 목록에서 기본·보고서(명조 본문)·다크를 고릅니다. '자동'은 Windows 다크 모드를 따릅니다.

### Claude Code와 함께 쓰기
1. Claude Code로 작업하는 프로젝트 폴더를 Lectern으로 열어 옆에 띄워 둡니다 (그 폴더의 명령 창에서 `<Lectern 폴더>\run.bat .`).
2. Claude가 문서를 만들거나 고치면 1초 안에 반영됩니다. 보던 문서는 읽던 위치와 접어 둔 절을 유지한 채 다시 그려지고, 아직 열어 보지 않은 바뀐 문서에는 트리에 호박색 점이 붙습니다.
3. 문서에 대해 Claude에게 물을 때는 트리에서 문서를 우클릭해 `@경로 복사`(메뉴에는 `@docs/보고서.md 복사` 처럼 실제 경로가 보임)를 고르고 프롬프트에 붙여 넣습니다. 예: `@docs/보고서.md 의 결론을 세 줄로 줄여 줘`. 같은 메뉴에 전체 경로 복사, 편집기로 열기, 탐색기에서 보기도 있습니다.

### 문서 속 링크
md 문서는 뷰어 안에서, 이미지·PDF·오피스 파일은 기본 앱으로, 코드·스크립트는 **실행하지 않고** 편집기로(`#L42` 를 붙이면 그 줄로, 편집기가 없으면 탐색기에서 선택), 웹 주소는 기본 브라우저로 열립니다. 프로젝트 폴더 밖을 가리키는 링크는 취소선으로 표시되고 열리지 않습니다.

### 알아 둘 점
- 보기 전용입니다. 문서를 고치거나 지우지 않고, 디스크에 쓰는 것은 설정 파일(`%APPDATA%\Lectern\config.json`) 하나뿐입니다.
- 접어 둔 절은 앱을 다시 실행하면 모두 펼쳐집니다.

## 단축키

| 키 | 동작 |
|---|---|
| Ctrl+P | 문서 빠르게 열기 |
| Ctrl+F | 문서 안 찾기 (개요 화면에서는 트리 필터) |
| Ctrl+O | 폴더 열기 |
| Ctrl+B | 사이드바 보이기/숨기기 |
| Alt+← / Alt+→ | 뒤로 / 앞으로 (마우스 뒤로·앞으로 버튼도 됨) |
| F5 | 다시 불러오기 |
| Ctrl+휠 | 확대/축소 |

## 설정

`%APPDATA%\Lectern\config.json` 에 저장됩니다. 화면에서 바꿀 수 없는 항목은 직접 고칩니다.

```json
{
  "exclude_dirs": ["data", "output"],
  "editor": "C:\\Users\\me\\AppData\\Local\\Programs\\Microsoft VS Code\\bin\\code.cmd",
  "math": true,
  "external_images": true
}
```

- `exclude_dirs`: 트리에서 뺄 폴더 이름 추가 (기본: node_modules, \_\_pycache\_\_, venv, env, dist, build, target, site-packages, htmlcov)
- `editor`: 코드 파일 링크를 열 편집기. 비워 두면 PATH의 `code` 를 씁니다. `-g 파일:줄` 형식을 받는 편집기(VS Code, Cursor)를 가정합니다.
- `math`: `false` 면 `$` 수식을 렌더링하지 않습니다.
- `external_images`: 문서 속 인터넷 이미지(`https://...`)를 보여 줍니다(기본 `true`). 불러오지 못하면(주소가 없거나 사내망에서 막힌 경우) 링크로 바뀝니다. `false` 면 처음부터 링크로만 보여 주고 인터넷에 요청하지 않습니다.

경로의 역슬래시는 `\\` 로 두 번 씁니다. 파일에 문법 오류가 있으면(역슬래시 하나, 마지막 쉼표 등) Lectern은 기본 설정으로 열리고 오류 위치를 알려 주며, 파일을 고칠 때까지 설정을 저장하지 않으므로 고친 내용이 지워지지 않습니다.

## 개발

Claude Code로 이어서 작업한다면 `CLAUDE.md` 부터 읽습니다. 구조는 `docs/ARCHITECTURE.md`, 설계 이유는 `docs/DECISIONS.md`, 할 일은 `docs/ROADMAP.md`, 점검 방법은 `docs/TESTING.md` 에 있습니다.

### Claude Code로 이어 가기

1. 압축을 풀고 `git init` 후 첫 커밋을 만듭니다 (`.gitattributes` 가 .bat 줄바꿈을 지켜 줍니다).
2. 프로젝트 폴더에서 Claude Code를 엽니다. `CLAUDE.md` 는 자동으로 읽힙니다.
3. 첫 요청 예시:
   - "docs/ROADMAP.md 의 2-1을 진행하자. Windows 수동 점검표를 같이 하면서 문제를 고쳐 줘."
   - "ROADMAP 2-3(바뀐 부분 강조)를 구현하고 ui_smoke 에 확인 항목을 추가해 줘."

작업 중에는 이 뷰어로 Claude Code가 만드는 문서를 같이 띄워 두면, 바뀐 문서가 호박색 점으로 표시됩니다.

```bat
python -m pytest -q
python tools\ui_smoke.py     :: playwright 필요: pip install playwright && python -m playwright install chromium
```

## 라이선스 참고

`web/vendor/` 의 라이브러리(markdown-it, highlight.js, KaTeX, Mermaid, DOMPurify 등)는 각자의 라이선스를 따릅니다. 원문은 `web/vendor/licenses/`, 버전은 `web/vendor/VERSIONS.json` 에 있습니다.
