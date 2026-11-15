# Lectern 지면 틀 작성 안내

이 문서는 AI 도구(Claude Code 등)가 Lectern 의 **지면 틀**을 만들 때 읽는 안내다. 지면 틀은 md 문서를 PDF·html 로 내보낼 때 입히는 출력 양식이다. 글은 md 문서 그대로 두고 틀이 표지·머리·쪽 크기·글꼴·색 같은 모양을 정한다 (D145).

사람은 내보내기 창(문서 우클릭 'PDF로 저장…'·'html로 저장…')의 **틀** 목록에서 고른다. 문서 맨 앞 설정에 `layout: 틀 id` 를 적으면 그 틀이 처음부터 골라진다.

## 파일 하나가 틀 하나

- 내 틀은 설정 폴더의 `layouts` 폴더(`%APPDATA%\Lectern\layouts`)에 `이름.html` 로 저장한다. 파일 이름이 틀 id 다 (`user/이름`). 이름은 `.` 나 `_` 로 시작하지 않는다.
- 앱에 든 틀(`web/layouts/*.html`)을 견본으로 읽는다. 가까운 것을 복사해 고치는 것이 가장 빠르다. 앱의 틀 파일은 고치지 않는다.
- 파일은 세 부분이다 — 머리 주석, `<style>`, 뼈대 html.

~~~html
<!--lectern-layout
name: 분기 보고
name_en: Quarterly report
group: 업무·공공
group_en: Office and public sector
pages: A4
fields: title, date, dept, author
slots: 요약
description: 한 줄 설명 — 내보내기 창에 보인다
description_en: One line in English
-->
<style>
:root { --md-font: "맑은 고딕", "Malgun Gothic", sans-serif; --md-size: 13.5px; }
@page { size: A4; margin: 20mm; @bottom-center { content: counter(page); } }
.lay-분기-보고 .cover h1 { font-size: 24pt; }
</style>
<header class="cover"><h1>{{title}}</h1><p data-if="dept">{{dept}} · {{date:dot}}</p></header>
<section data-if="slot:요약"><div class="lay-slot">{{slot:요약}}</div></section>
<main class="md-body">{{body}}</main>
~~~

### 머리 주석

| 키 | 뜻 |
|---|---|
| `name`, `name_en` | 목록에 보일 이름 |
| `group`, `group_en` | 묶음 — 업무·공공, 연구, 금융·컨설팅, 매체·출판, 안내 가운데 하나, 또는 새 이름 |
| `pages` | `A4`·`Letter`·`152×225mm` 같은 쪽 크기 표시, 쪽 없이 길게 읽는 틀이면 `continuous` |
| `fields` | 틀이 쓰는 맨 앞 설정 키 (쉼표로) — 비어 있으면 창이 알리고 견본을 복사해 준다 |
| `slots` | 이름이 있는 박스글 자리 (쉼표로) |
| `description`, `description_en` | 한 줄 설명 |

머리 주석 안에는 `-->` 를 쓰지 않는다 — 주석이 거기서 끝나 버린다. 박스글을 말할 때는 "이름이 '요약'인 박스글" 처럼 쓴다.

## 자리

뼈대의 `{{…}}` 를 Lectern 이 채운다. 값은 글자로만 들어간다 (html 로 읽지 않는다).

| 자리 | 들어가는 것 |
|---|---|
| `{{body}}` | 문서 본문 — 맨 앞 설정 표는 빠지고, 틀이 `{{title}}` 을 쓰면 맨 앞 `# 제목` 도 빠지고, 자리로 옮긴 박스글도 빠진다. 한 번만 쓴다 |
| `{{title}}` | 맨 앞 설정 `title`, 없으면 문서의 `# 제목`, 파일 이름 |
| `{{date}}` | 맨 앞 설정 `date` 그대로, 없으면 오늘. `{{date:long}}` 2026년 11월 15일, `{{date:dot}}` 2026. 11. 15., `{{date:iso}}` 2026-11-15 |
| `{{키}}` | 맨 앞 설정의 그 값 (목록이면 쉼표로 이음) |
| `{{a\|b\|'글'}}` | 앞의 것이 비면 다음 것, 따옴표는 그 글 그대로 |
| `{{t:한국어\|English}}` | 문서 언어로 고른다 — 맨 앞 설정 `lang` 이 `en…` 이면 영어 |
| `{{toc}}` | 차례 — 본문의 `##`·`###` (`<nav class="lay-toc">`, `li.lv2`·`li.lv3`). 쪽 번호는 없다 |
| `{{slot:이름}}` | 이름이 있는 박스글을 옮겨 온다 (아래). 없으면 맨 앞 설정의 같은 키, `{{slot:면책\|'기본 글'}}` 처럼 기본 글도 |

맨 앞 설정은 한국어 키로 써도 된다. 같은 것으로 읽는 키: 제목 title, 부제 subtitle, 작성자·저자·지은이·연구진 author, 날짜·일자 date, 기관 org, 부서·담당부서 dept, 번호·보고서번호·호수 number, 시리즈 series, 고객·발주처 client, 소속 affiliation, 주제어·키워드 keywords, 판·버전 version, 회사·기업 company, 종목코드 ticker, 업종 sector, 장 chapter, 책 book, 꼬리표 kicker, 짧은제목 short_title. 그 밖의 키(`결재`, `투자의견` 등)는 적은 그대로 쓴다.

### 요소에 다는 속성

- `data-if="키"` — 값이 없으면 그 요소를 뺀다. `data-if="!키"` 는 있으면 뺀다. `data-if="slot:이름"` 은 그 자리에 들어갈 것이 있을 때만.
- `data-each="키"` — 목록 값(`결재: [담당, 팀장, 본부장]`, 또는 쉼표로 쓴 글)마다 그 요소를 되풀이한다. 안에서 `{{.}}` 가 그 항목.

### 이름이 있는 박스글

문서에서 `<!-- box: 요약 -->` 줄로 연 박스글은 틀의 `{{slot:요약}}` 자리로 옮겨진다. 틀이 그 자리를 모르면 본문의 보통 박스글로 남는다 — 글이 사라지지 않는다. 박스글 첫 줄이 굵은 제목(`**…**`)이나 `박스 1.` 이면 자리에서는 빠진다 (자리의 제목을 틀이 단다). 자리는 `<div class="lay-slot">` 로 감싸면 박스 테두리 없이 들어간다.

## CSS

- 뼈대 전체는 `<div class="lec-layout lay-파일이름 lay-paged">` 안에 들어간다 (쪽 없는 틀은 `lay-flow`). 파일 이름의 글자·숫자·`-` 밖의 것은 `-` 가 된다. 규칙은 `.lay-파일이름 …` 으로 쓴다 — 다른 틀과 섞이지 않게.
- 본문 요소의 모양은 Lectern 의 문서 스타일(base.css)이 맡는다. 바꿀 것은 CSS 변수를 `:root` 에 적는다: `--md-font`(본문 글꼴), `--md-heading-font`, `--md-size`(본문 크기, px), `--md-line`(줄 간격), `--md-fg`, `--md-heading`, `--md-muted`, `--md-border`, `--md-link`, `--md-th-bg`·`--md-th-fg`(표 머리행), `--md-th-rule`, `--md-stripe`, `--md-code-bg`.
- 본문 요소: `h2`·`h3`, `p`, `ul`·`ol`, `table`(`.table-wrap` 안), 캡션 단락 `p.caption`(표·그림·박스 번호 — Lectern 이 class 를 단다), 출처 줄 `p.lec-source`, 강조글 `blockquote.alert`(`--alert` 가 종류 색), 인용 `blockquote:not(.alert)`, 박스글 `aside.lec-textbox`(제목 `.lec-textbox-title`), 차트 `.lec-chart`, Mermaid `pre.mermaid`, 수식 `.katex`, 각주 `.footnotes`.
- **쪽**: `@page { size: A4; margin: …; }`, 머리·바닥은 `@top-left`·`@top-right`·`@bottom-center` 같은 여백 상자에 `content: counter(page)` 나 `counter(pages)`. 문서 제목을 머리에 넣으려면 `content: {{css:title}};` — `<style>` 안에서는 `{{css:식}}` 만 쓸 수 있다 (CSS 글자로 막아 넣는다). 표지처럼 따로 쪽을 쓰려면 `@page cover { margin: 0; }` 와 `.cover { page: cover; }` — 이름 붙은 쪽이 바뀌면 쪽이 새로 시작한다. 첫 쪽만 다르게는 `@page :first`, 책의 왼쪽·오른쪽 쪽은 `@page :left`·`:right`.
- **두 단**: `.md-body { columns: 2; }` — 한글이 가운데 벌어지지 않게 `word-break: normal; line-break: strict;`, 넓은 표·차트·캡션은 `column-span: all`.
- **화면**: 내보낸 html 을 브라우저로 열면 쪽 틀은 회색 바탕 위 종이처럼 보인다(_base.css). 화면에서만 다르게 할 것은 `@media screen`, 종이에서만은 `@media print`.
- **글꼴**: PC 에 있는 글꼴 이름만 차례로 적는다 (함초롬바탕·바탕·맑은 고딕·HY헤드라인M 등 — 없으면 다음 것). 글꼴 파일은 넣지 않는다.

## 하지 않는 것

Lectern 이 지운다 — 받은 사람의 브라우저에서 안전하게 열리게.

- `<script>`, `on…=` 이벤트 속성, `javascript:` 주소, `<iframe>`·`<object>`·`<form>`·`<link>`·`<meta>`
- 인터넷에서 불러오는 CSS: `@import`, `data:` 가 아닌 `url(…)`, `image-set(…)`. 배경 그림은 `data:` 로만
- 인터넷 그림 (`src="https://…"`)

## 만든 뒤

1. Lectern 에서 문서를 열고 여백을 우클릭해 'html로 저장…' 을 고른다. 내보내기 창의 **틀**에서 새 틀을 고르면 미리보기에 나온다.
2. 형식을 PDF 로 바꿔 쪽 나눔·머리·쪽 번호를 본다.
3. 틀 파일을 고치면 창의 틀을 다시 고르거나 창을 다시 열면 반영된다.
