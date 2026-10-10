# 샘플 프로젝트

Lectern의 기능을 확인하기 위한 예시 문서 모음입니다. `python app.py samples` 로 열어 보세요.

| 폴더 | 확인할 것 |
|---|---|
| `docs/` | 표·체크리스트·코드·콜아웃·각주·링크, 수식과 달러 표기, Mermaid |
| `research/` | 리서치 문서 형식, 상대경로 이미지 |
| `plans/` | frontmatter, 자연 정렬(2 → 10) |

트리에 **보이면 안 되는** 것도 들어 있습니다.

- `.hidden-note.md`, `.claude/` — 점으로 시작하는 이름
- `node_modules/` — 제외 폴더
- `empty-folder/` — md 파일이 없는 폴더

Windows 숨김 속성 확인은 `attrib +h samples\docs\03-다이어그램.md` 처럼 속성을 붙여 확인합니다 (docs/TESTING.md 참고).
