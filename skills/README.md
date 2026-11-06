# Lectern 의 PowerPoint 스킬

Claude Code 가 쓰는 스킬 두 개가 들어 있습니다. 설치하면 Claude Code 에게 말로 시킬 수 있습니다.

| 스킬 | 하는 일 |
|---|---|
| `pptx-to-lectern` | pptx 를 Lectern 슬라이드로 옮긴다. pptx 를 참고해서 md 문서를 슬라이드로 만든다 |
| `lectern-to-pptx` | Lectern 슬라이드를 스타일을 살려 pptx 로 만든다 |

## 설치

Lectern 이 저절로 설치하지 않습니다. 사용자가 시키면 Claude Code 가 먼저 묻고, 허락하면 두 폴더를 `~/.claude/skills/` 로 복사합니다.

Python 을 따로 설치하지 않아도 됩니다. Lectern 설치 폴더의 `lectern-skill.exe` 에 Python, pywin32, Pillow 가 들어 있고 스킬은 이것으로 실행됩니다. PowerPoint 가 있으면 `.ppt`, 띄워 둔 발표, 쪽 그림도 씁니다.

PowerPoint 가 없어도 `.pptx` 파일을 옮기고 내보낼 수 있습니다. 도식은 그림 대신 칸으로 옮겨지고, EMF 그림은 빠지고, 내보낼 때 SVG 그림이 빠집니다. 띄워 둔 발표, `.ppt`, DRM 파일은 PowerPoint 가 있어야 합니다.

`lectern-skill.exe` 를 못 찾으면 시스템의 `python`(3.10 이상)으로 실행됩니다. 이때는 `pip install pywin32 pillow` 까지 해야 위의 기능을 씁니다.

## 프롬프트 예제

### pptx → Lectern

```text
이 pptx 를 Lectern 슬라이드로 옮겨 줘: D:\자료\보고서.pptx
```

```text
지금 PowerPoint 에 띄워 둔 발표를 Lectern 슬라이드로 옮겨 줘. 결과는 D:\프로젝트\발표 폴더에 둬.
```

```text
D:\자료\보고서.pptx 를 일단 빨리 md 로만 뽑아 줘. 다듬는 건 나중에 할게.
```

```text
열어 둔 pptx 가 둘인데 '분기 보고' 쪽을 Lectern 슬라이드로 옮겨 줘.
```

```text
옮기면서 도식은 되도록 칸으로 살려 줘. 글을 고칠 수 있는 게 제일 중요해.
```

### pptx 를 참고해서 md 를 슬라이드로

```text
D:\양식\회사보고.pptx 를 참고해서 @시장-분석.md 내용을 Lectern 슬라이드로 만들어 줘.
```

```text
화면에 떠 있는 pptx 를 참고해서 @시장-분석.md 를 Lectern 슬라이드로 만들어 줘.
```

```text
D:\양식\회사보고.pptx 의 색과 표지만 참고해서 @주간보고.md 를 10장 안으로 슬라이드로 만들어 줘. 숫자는 그대로 써.
```

```text
화면의 pptx 양식으로 @시장-분석.md 를 슬라이드로 만들고, 다 되면 같은 양식의 pptx 로도 내보내 줘.
```

### Lectern → pptx (역변환)

```text
@발표.md 를 스타일을 최대한 유지해서 pptx 로 만들어 줘.
```

```text
pptx 에서 옮겨 온 @보고서.md 를 고쳤어. 고친 쪽만 반영해서 다시 pptx 로 만들어 줘.
```

```text
@발표.md 를 D:\양식\회사보고.pptx 양식으로 pptx 를 만들어 줘.
```

```text
@발표.md 를 슬라이드 스타일 consulting 으로 pptx 로 내보내 줘.
```

```text
@보고서.md 를 전부 Lectern 모습으로 다시 만들어서 pptx 로 내 줘. 원본 쪽을 쓰지 마.
```

### 고치기

상태줄의 **점검**에서 **목록을 터미널에 붙여 넣기**를 누르면 고쳐 달라는 글이 들어갑니다. Enter 만 누르면 됩니다.

```text
5쪽은 그림 대신 칸으로 다시 짜 줘.
```

```text
pptx 로 내보낸 7쪽 표가 넘쳐. @발표.md 는 두고 pptx 만 고칠 방법을 알려 줘.
```

## 알아 둘 점

- 원본 pptx 는 고치지 않습니다. 띄워 둔 발표도 저장하거나 닫지 않습니다.
- 애니메이션은 md 로 옮기지 않습니다. 고치지 않은 쪽은 pptx 로 되돌릴 때 원본 그대로 돌아오고, 글만 고친 쪽은 원본 쪽에서 그 글만 바뀝니다. 칸이나 배치를 바꾼 쪽만 새로 만듭니다.
- `문서-변환기록.json` 과 `.pptx-work` 폴더를 지우면 되돌릴 때 원본 쪽을 쓸 수 없습니다.
- 암호가 걸린 파일은 먼저 풀어 주세요. DRM 파일은 PowerPoint 로 열어 띄워 두고 옮기세요.
