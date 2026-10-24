# Lectern 내 스타일 만드는 법

이 글은 Claude Code 같은 AI 가 Lectern(Windows 용 문서 뷰어)의 **내 스타일**을 만들 때 읽는 설명서입니다. 사람이 읽어도 됩니다.
내 스타일은 CSS 파일 하나입니다. Lectern 이 Markdown·HTML 문서를 보여 줄 때 글꼴·색·간격을 정합니다.

## 1. 저장할 곳과 반영

- 저장할 폴더: `%APPDATA%\Lectern\styles` (설정 창의 '스타일 폴더 열기'가 여는 곳 — 요청 글에 전체 경로가 적혀 있습니다). 폴더가 없으면 만듭니다.
- 파일 하나 = 스타일 하나. 이름은 `<아무 이름>.css` (예: `company-report.css`). 하위 폴더, `.` 으로 시작하는 이름, 1MB 넘는 파일은 읽지 않습니다.
- UTF-8 로 저장합니다.
- 저장하면 3초 안에 툴바 스타일 목록 맨 아래 **내 스타일** 묶음에 나옵니다. 그 스타일을 고른 채 파일을 고치면 바로 다시 입혀집니다 — 앱을 다시 켤 필요가 없습니다.
- Lectern 은 이 파일을 읽기만 합니다. 앱이 스타일 파일을 만들거나 고치지 않습니다.

## 2. 머리 주석 (파일 맨 앞)

파일은 반드시 이 주석으로 시작합니다. 한 줄에 `이름: 값` 하나씩 적습니다.

```css
/* lectern-style
   name: 회사 보고서
   dark: no
   base: report
*/
```

| 항목 | 뜻 | 없으면 |
|---|---|---|
| `name` | 스타일 목록에 보일 이름 (60자까지) | 파일 이름 |
| `dark` | 어두운 스타일이면 `yes`. 앱 화면(툴바·사이드바), 코드 색(highlight.js), 터미널 색, 다이어그램이 어두운 쪽으로 맞춰집니다 | `no` |
| `base` | 바탕으로 깔 기본 스타일의 id. Lectern 은 이 스타일을 먼저 입히고 그 위에 이 파일을 얹습니다 — 바꿀 것만 적으면 됩니다 | 밝으면 `default`, 어두우면 `dark` |

`base` 로 쓸 수 있는 id: `default` 기본, `report` 보고서, `office` 사내 문서, `consulting` 컨설팅, `notion` 노션풍, `contrast` 고대비, `paper` 종이(세피아), `book` 책, `academic` 논문, `newsprint` 신문, `magazine` 잡지, `manuscript` 원고(타자기), `github` GitHub, `docsite` 문서 사이트, `solarized-light`, `gruvbox-light`, `dark` 다크, `github-dark`, `nord`, `solarized-dark`, `dracula`, `one-dark`, `night` 밤 종이, `ink` 먹(완전 검정).
`dark: yes` 이면 어두운 바탕(`dark`·`nord` 등)을 고르세요.

## 3. 먼저 변수를 바꾸세요

대부분의 모양은 `:root` 의 CSS 변수로 정해집니다. 변수만 바꾸면 본문은 물론 앱 화면(툴바·사이드바·목차·메뉴 색 — 앱이 이 변수에서 색을 만듭니다)과 터미널 바탕·글자, 다이어그램 색까지 함께 따라옵니다. 아래 표에 없는 변수를 새로 만들 필요는 거의 없습니다.

| 변수 | 쓰이는 곳 |
|---|---|
| `--md-bg` | 본문 바탕 (앱 화면 바탕도 여기서) |
| `--md-fg` | 본문 글자 |
| `--md-heading` | 제목 글자 (앱의 고른 항목 글자도) |
| `--md-muted` | 흐린 글자 — 인용문, h5·h6, 코드 언어 이름 |
| `--md-border` | 선 — 표 칸, 코드 상자, 가로줄, h1·h2 밑줄 |
| `--md-link` | 링크 (앱의 강조색·터미널 커서도) |
| `--md-strong` | 굵은 글자 색 (없으면 본문 글자와 같음) |
| `--md-code-bg` | 코드 블록·인라인 코드·메타데이터 바탕 (터미널 바탕도) |
| `--md-quote-bar` | 인용문 왼쪽 막대 |
| `--md-th-bg` | 표 머리행 바탕 |
| `--md-th-fg` | 표 머리행 글자 (머리행을 짙게 칠할 때 흰 글자로 — 없으면 제목 색) |
| `--md-th-rule` | 표 머리행 아래 굵은 선 |
| `--md-stripe` | 표의 짝수 행 바탕 |
| `--md-alert-note` / `-tip` / `-important` / `-warning` / `-caution` | 박스글(`> [!NOTE]` 등)의 막대·제목·옅은 바탕 색 |
| `--md-font` | 본문 글꼴 |
| `--md-heading-font` | 제목 글꼴 |
| `--md-mono` | 코드 글꼴 |
| `--md-size` | 본문 글자 크기 (px — 툴바의 글자 크기 배율이 곱해집니다) |
| `--md-line` | 줄 간격 (예: `1.7`) |
| `--md-width` | 본문 최대 폭 (px) |
| `--md-h1-rule` / `--md-h2-rule` | h1·h2 아래 선 (`1px solid var(--md-border)`, 없애려면 `0`) |

## 4. 더 바꾸고 싶으면 규칙을 적으세요

본문은 `.md-body` 안에 있습니다. **규칙은 반드시 `.md-body` 로 시작**하세요 — 앱 화면(툴바·사이드바·메뉴)을 바꾸지 않게. 쓸 수 있는 구조:

| 무엇 | 선택자 |
|---|---|
| 제목 | `.md-body h1` ~ `h6` |
| 단락·목록 | `.md-body p`, `ul`, `ol`, `li` |
| 체크리스트 | `.md-body .task-list-item`, `.task-list-item-checkbox` |
| 링크 | `.md-body a` (인터넷 링크 `a.ext` — 뒤에 ↗ 표시, 프로젝트 파일 `a.file-link`, 본문 속 경로 `a.path-link`, 열 수 없는 링크 `a.link-off`) |
| 굵게·강조·표시 | `.md-body strong`, `em`, `mark`, `kbd` |
| 인용문 | `.md-body blockquote` (박스글은 `blockquote.alert` — 아래) |
| 박스글 | `.md-body blockquote.alert.alert-note` (`-tip`·`-important`·`-warning`·`-caution`), 그 안 첫 줄 제목 `.alert-title`. 색은 그 박스의 `--alert` 변수 |
| 코드 블록 | `.md-body .code-block` > `.code-tools`(언어 이름 `.code-lang`, 복사 단추 `.code-copy`) + `pre` > `code.hljs` |
| 인라인 코드 | `.md-body :not(pre) > code` |
| 표 | `.md-body .table-wrap`(테두리·스크롤 상자) > `table` > `thead th`, `tbody td`. 숫자 열은 `th.num`·`td.num` (오른쪽 정렬) |
| 그림 | `.md-body img`, 불러오지 못한 그림 자리 `.image-off` |
| 수식 | 블록 `.md-body .math-block`(안에 `.katex-display`), 문장 속 `.katex` |
| 다이어그램 | `.md-body pre.mermaid` (그린 뒤 `.mermaid-ok`, 안에 `svg`) |
| 차트 (Vega-Lite·ECharts·Plotly·Graphviz) | `.md-body pre.lec-chart` (`data-chart` 가 `vega-lite`·`vega`·`echarts`·`plotly`·`dot`, 그린 뒤 `.chart-ok`, 안에 `svg`). 차트의 색은 CSS 가 아니라 다이어그램과 같은 스타일 색표에서 정해집니다 |
| 그리지 못한 다이어그램·차트 | `.md-body .diagram-error` (까닭 `p` 와 원문 `pre`) |
| 메타데이터 | `.md-body .front-matter` (`details` — `summary`, `table`) |
| 각주 | `.md-body .footnotes-sep`, `.footnotes`, `.footnote-ref` |
| 가로줄 | `.md-body hr` |

**건드리지 말 것**: 이름이 `lec-` 로 시작하는 클래스(`.lec-fold`·`.lec-changed`·`.lec-target`·`.lec-spotlight`·`.lec-picked` 등 — 접기 화살표, 바뀐 곳·찾은 곳 표시, 장 하이라이트)와 `.md-body` 의 `max-width`·`padding`·`font-size` 계산식. 폭은 `--md-width`, 크기는 `--md-size` 로 바꿉니다.

## 5. 지킬 것

- **인터넷에서 아무것도 불러오지 않습니다.** `@import`, `url(https://…)`, 웹 글꼴은 Lectern 이 지웁니다 (안 됩니다). 그림을 꼭 넣으려면 `url(data:…)` 로 파일 안에 넣습니다.
- **글꼴은 PC 에 있는 것만** 씁니다. 목록은 영문 글꼴 → 한글 글꼴 → Windows 기본 글꼴 순으로, 마지막에 `"Malgun Gothic"`(고딕) 이나 `"Batang"`(명조) 와 `sans-serif`/`serif` 를 둡니다 — 그 글꼴이 없는 PC 에서도 한글이 보이게.
  예: `--md-font: "Segoe UI", "Pretendard", "Malgun Gothic", sans-serif;`
- **글자 크기는 변수로**: 새 규칙에 px 로 크기를 적으면 툴바의 글자 크기 −·+ 를 따라가지 않습니다. `em` 을 쓰거나 `calc(13px * var(--md-scale, 1))` 처럼 씁니다.
- **글자와 바탕의 대비 4.5:1 이상** (WCAG). 본문 글자·제목·링크·흐린 글자·표 머리행 글자 모두. 표 머리행을 짙게 칠하면 `--md-th-fg` 를 흰색 계열로.
- 제목 색은 본문 글자와 달라 보이게, 표 머리행은 본문 행과 구분되게 합니다.
- 어두운 스타일이면 머리 주석에 `dark: yes` 를 적어야 앱 화면·코드 색이 어둡게 맞춰집니다.
- 인쇄·PDF 는 어느 스타일이든 흰 종이에 검은 글자로 바뀝니다 (따로 손댈 필요 없음).

## 6. 예시

### 변수만 바꾼 밝은 스타일

```css
/* lectern-style
   name: 회사 보고서 (남색)
   dark: no
   base: report
*/
:root {
  --md-heading: #14306b;
  --md-link: #1d4fbf;
  --md-th-bg: #14306b;
  --md-th-fg: #ffffff;
  --md-th-rule: #0b1d44;
  --md-font: "Segoe UI", "Pretendard", "Malgun Gothic", sans-serif;
  --md-size: 15px;
  --md-width: 920px;
}
```

### 규칙도 바꾼 어두운 스타일

```css
/* lectern-style
   name: 밤 바다
   dark: yes
   base: dark
*/
:root {
  --md-bg: #0f1b2a;
  --md-fg: #d6e2ee;
  --md-heading: #9fd3ff;
  --md-muted: #8fa3b8;
  --md-border: #24384f;
  --md-link: #6cc0ff;
  --md-code-bg: #15263a;
  --md-th-bg: #1b3149;
  --md-stripe: #12223a;
}
.md-body h1 { border-bottom: 2px solid var(--md-link); }
.md-body h2 { color: var(--md-link); }
.md-body blockquote:not(.alert) { border-left-color: var(--md-link); font-style: italic; }
```

## 7. 만든 뒤 확인

1. 툴바 스타일 목록 맨 아래 '내 스타일'에서 고릅니다.
2. 제목·표(머리행·짝수 행·숫자 열)·코드 블록·인라인 코드·박스글 다섯 가지·인용문·체크리스트·링크·수식·다이어그램이 든 문서를 열어 봅니다. 예제(**예제 열기**)의 `guide/04-문서-쓰는-법.md` 가 좋은 예입니다.
3. 툴바의 글자 크기 −·+ 로 크기를 바꿔 봅니다 (함께 커지고 작아져야 합니다).
4. 어두운 스타일이면 사이드바·메뉴·코드 색이 어두운지, 터미널 글자가 읽히는지 봅니다.
5. 고칠 것이 있으면 파일을 고쳐 저장합니다 — 바로 다시 입혀집니다.
