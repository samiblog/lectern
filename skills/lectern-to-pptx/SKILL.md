---
name: lectern-to-pptx
description: Lectern 발표 문서(marp: true 인 Markdown 슬라이드)를 PowerPoint pptx 로 만든다. 사용자가 Lectern 슬라이드를 pptx·ppt·파워포인트로 내보내거나 바꿔 달라고 하거나, md 슬라이드를 회사 양식 pptx 로 만들어 달라고 하거나, pptx 에서 옮겨 온 문서를 고친 뒤 다시 pptx 로 돌려 달라고 할 때 반드시 쓴다. 일반 문서를 pptx 로 새로 기획하는 일에는 쓰지 않는다.
---

# Lectern 슬라이드 → pptx

Lectern 에서 보던 모습을 최대한 유지한 채, PowerPoint 에서 고칠 수 있는 pptx 를 만든다. 글은 글로, 표는 표로, 차트는 차트로, 선은 연결선으로 넣는다. 그림으로 뭉개는 것은 마지막 수단이다.

## 세 가지 길

스크립트가 알아서 고른다. 무엇이 일어날지 사용자에게 알리려고 적는다.

| 경우 | 하는 일 | 결과 |
|---|---|---|
| pptx 에서 옮겨 온 문서 (`-변환기록.json` 이 있다) | 원본 사본을 바탕으로 쓴다. 고치지 않은 쪽은 **원본 쪽을 그대로** 쓰고, 글만 고친 쪽은 **원본 쪽의 글만** 바꾸고, 칸이나 배치를 바꾼 쪽만 원본 레이아웃으로 새로 만든다 | 애니메이션과 원본 디자인이 살아 있다 |
| `--template 양식.pptx` 를 줬다 | 그 양식의 마스터·레이아웃 위에 모든 쪽을 만든다 | 양식의 색·글꼴을 따른다 |
| 둘 다 아니다 | Lectern 슬라이드 스타일을 살린 새 pptx 를 만든다 | 색, 상자, 표, 표지가 Lectern 과 같다 |

사용자가 "회사 양식으로", "이 pptx 양식으로"라고 하면 `--template` 이다. 양식을 pptx-to-lectern 의 참고 길로 읽었으면 `.pptx-work/<이름>-양식/source.pptx` 가 그 양식이다.

## 순서

### 1. 만든다

```bash
python <이 스킬>/scripts/build_pptx.py 문서.md [--out 결과.pptx] [--template 양식.pptx] [--style 스타일id]
```

- 결과는 문서 옆의 `문서.pptx` 다. 이미 있으면 멈춘다. 덮어써도 되는지 사용자에게 물은 뒤 `--force` 를 준다. 원본 pptx 와 경로가 같으면 스크립트가 `문서-수정.pptx` 로 바꾼다. 원본을 덮어쓰지 않기 위해서다.
- 스타일은 사용자가 슬라이드 창에서 고른 것을 설정에서 읽는다. 다른 스타일로 내려면 `--style consulting` 처럼 준다.
- 고치지 않은 쪽까지 Lectern 모습으로 다시 만들고 싶다고 하면 `--rebuild-all` 을 쓴다. 이때 애니메이션은 사라진다.

Python 표준 라이브러리만 쓴다. PowerPoint 는 없어도 된다. SVG 그림을 넣을 때만 PowerPoint 와 `pywin32` 가 필요하다. 복잡한 차트와 다이어그램을 그림으로 그릴 때는 Windows 의 Edge 와 Lectern 의 라이브러리를 쓴다. 인터넷에는 나가지 않는다.

### 2. 확인한다

```bash
python <이 스킬>/scripts/check_pptx.py 문서.md 결과.pptx --render 쪽그림폴더
```

`broken_xml`, `slides_missing_text`, `low_contrast` 가 비어야 한다. `powerpoint.opened` 가 true 면 PowerPoint 가 파일을 열었다는 뜻이다. PowerPoint 가 없으면 null 이다.

`low_contrast` 가 있으면 문서의 맨 앞 설정에서 그 색을 정한다 (`section { --md-th-bg: #…; --md-link: #…; }`, 칸의 큰 숫자는 `.낱말 strong { color: #…; }`). 스크립트는 문서가 정한 색을 먼저 쓴다.

`--render` 로 뽑은 쪽 그림을 몇 장 읽어 본다. 표지, 칸이 많은 쪽, 차트가 있는 쪽, 표가 있는 쪽을 먼저 본다. 글이 상자를 넘으면 문서 쪽을 고치지 말고 사용자에게 알린다. PowerPoint 와 Lectern 의 글꼴 폭이 조금 달라서 생기는 일이고, PowerPoint 에서 상자를 누르면 글자가 맞춰진다.

### 3. 보고한다

출력의 수와 `notes` 로 짧게 알린다.

- 쪽 수, 원본을 그대로 쓴 쪽(`reused`), 원본에서 글만 고친 쪽(`patched`), 새로 만든 쪽(`rebuilt`), 새 쪽(`new`)
- 그림으로 넣은 차트와 다이어그램 (값을 PowerPoint 에서 고칠 수 없다)
- 옮기지 못한 것 (`notes` 의 항목)
- `rebuilt` 쪽은 애니메이션이 없고 원본 도형이 칸으로 바뀌었다는 것

## 어떻게 옮겨지나

| Lectern | pptx |
|---|---|
| 제목 | 제목 자리 표시자 (개요 보기에 나온다) |
| 칸의 글 | 글상자. 목록은 진짜 목록이다 |
| `card`·`kpi`·`accent`·`dark`·`note`, 내 낱말의 색 | 같은 색의 상자 |
| `clip-path` 다각형, `border-radius: 50%` | 도형 |
| 표 | 표. 머리행과 줄무늬 색이 같다 |
| `vega-lite`·`echarts`·`plotly` 의 막대·선·영역·원·도넛·산점도·레이더, 값 라벨, 조건 색, 가로 기준선 | 네이티브 차트. '데이터 편집'이 된다 |
| 복잡한 차트 (계산 변환, 겹친 표식), Mermaid, Graphviz | 그림 |
| `links` | 칸에 붙은 연결선 |
| `![bg]`, 나눈 배경 | 그림. `brightness`·`grayscale` 만 옮긴다 |
| 노트 | 발표자 노트 |
| `hidden` | 숨긴 슬라이드 |
| 꼬리말·쪽 번호·머리글 | 글상자와 쪽 번호 필드 |

표지의 왼쪽 정렬, 칸의 테두리와 모서리, 표의 행·열 강조(`tr:last-child td`, `tr:nth-child(n+4) td`, `td:nth-child(4)`)는 문서 CSS 에서 읽어 옮긴다. 그 밖의 CSS 효과(그림자, 글자 간격, 다른 선택자)는 옮기지 않는다. 수식은 글 그대로 들어간다.

그림으로 들어가는 차트는 Edge 로 그린다. 값을 PowerPoint 에서 고칠 수 없으니 보고에 적는다.
