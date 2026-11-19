# AI 도구와 함께

> 터미널에 띄운 AI 도구(Claude Code 등)에게 문서의 위치와 요청 글을 보내고, 고친 것을 바로 본다.

Lectern 은 AI 도구를 실행하지 않는다. 터미널에서 사람이 직접 띄우고, Lectern 은 위치와 요청 글을 Enter 없이 넣기까지만 한다.

## 한 바퀴

| 차례 | 할 일 | 키·메뉴 | 자세히 |
|---|---|---|---|
| 1 | AI 도구로 작업하는 프로젝트 폴더를 Lectern 으로 연다 | **Ctrl+O** | [프로젝트 탭](2.2-프로젝트-탭.md) |
| 2 | 터미널을 열고 AI 도구를 띄운다 — `claude` | **Ctrl+\`** | [터미널](7.1-터미널.md) |
| 3 | 짚을 곳을 보낸다 — 현재 줄·고른 줄의 위치 `@경로 12~20행` | **Shift+→** · 우클릭 **위치 복사** | [보내기와 요청 글](7.2-보내기와-요청-글.md) |
| 4 | 문서 하나를 통째로 짚는다 — 예: `@docs/보고서.md 의 결론을 세 줄로 줄여 줘` | 트리 우클릭 **@경로 복사** | [보내기와 요청 글](7.2-보내기와-요청-글.md) |
| 5 | 고친 것을 본다 — 1초 안에 반영, 아직 열어 보지 않은 바뀐 문서는 트리에 호박색 점 | **F7** · **Shift+F7** | [찾기와 검색](3.2-찾기와-검색.md) |
| 6 | Lectern 에서 잘 보이는 문서를 쓰게 한다 | 설정 창 **Claude Code 에 Lectern 알려 주기** | [설정 창의 요청 글](7.2-보내기와-요청-글.md#설정-창의-요청-글) |
| 7 | 보고서·검토 의견처럼 사람이 읽을 글을 맡긴다 | 설정 창 **글쓰기 스타일** | [글쓰기 스타일과 다듬기](7.4-글쓰기-스타일과-다듬기.md) |

## 누가 무엇을 하나

| 누가 | 하는 일 |
|---|---|
| Lectern | 위치·요청 글을 터미널에 넣는다 (Enter 는 누르지 않음). 지금 상태를 보이려고 AI 도구의 정해진 파일 몇 개를 읽기만 한다 |
| AI 도구 | 요청 글대로 일한다. 파일을 고치거나 설치하기 전에 지금 상태를 알리고 묻는다 |
| 사람 | Enter 를 누르고, AI 도구가 물으면 그렇다고 하거나 고른다 |

## 도구마다 다른 것

터미널은 어떤 프로그램이든 돌리므로 `claude` 대신 `codex`(OpenAI Codex CLI)·`agy`(Google Antigravity CLI)·`opencode`(OpenCode)를 띄워도 된다. 위치를 보내고(**Shift+→** · **Shift+숫자**) 고친 것이 바로 보이는 것은 같다. 설정 창의 **쓰는 AI 도구**에서 고르면 화면의 이름('Codex로 보내기', 'Codex용 요청 복사')과 요청 글이 말하는 파일·폴더가 따라 바뀐다. 이 설명서는 메뉴 이름을 Claude Code 기준으로 적는다.

| | Claude Code | Codex | Antigravity | OpenCode |
|---|---|---|---|---|
| 터미널에서 | `claude` | `codex` | `agy` | `opencode` |
| 프로젝트의 지시 파일 | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| 개인 스킬 폴더 | `~/.claude/skills` | `~/.agents/skills` | `~/.gemini/config/skills` | `~/.config/opencode/skills` |
| 프로젝트 스킬 폴더 | `.claude/skills` | `.agents/skills` | `.agents/skills` | `.agents/skills` |
| Lectern 요약 (모든 폴더) | `~/.claude/rules/lectern.md` | `~/.codex/AGENTS.md` 의 한 절 | `~/.gemini/AGENTS.md` 의 한 절 | `~/.config/opencode/AGENTS.md` 의 한 절 |
| 글쓰기 스타일 | 출력 스타일 (켤 곳을 고름) | 개인 지시 파일이나 `AGENTS.md` 의 '글쓰기' 절 | 같음 | 같음 |
| 내 문체 노트 | `~/.claude/rules/내-문체.md` | 개인 지시 파일의 '내 문체' 절 | 같음 | 같음 |
| 하던 대화 잇기 | `claude --continue` | `codex resume --last` | `agy --continue` | `opencode --continue` |

| 경우 | 어떻게 되나 |
|---|---|
| **여럿**을 고르면 | 화면의 이름이 'AI' 가 되고, 요청 글이 도구마다의 파일과 폴더를 함께 적는다 |
| 한 프로젝트에서 여러 도구를 쓰면 | 규칙은 `AGENTS.md` 에 두고 `CLAUDE.md` 에는 `@AGENTS.md` 한 줄만 — 한 곳만 고친다 |
| 여러 도구를 나란히 | 터미널을 쌓아 1번은 Claude Code, 2번은 Codex 처럼 두고 **Shift+숫자**로 골라 보낸다 |
| Codex 에 `~/.codex/AGENTS.override.md` 가 있으면 | 개인 지시 파일 `~/.codex/AGENTS.md` 대신 그것만 읽는다 — 설정 창의 바뀌는 파일이 알려 준다 |
| Antigravity·Codex 가 작업 폴더 밖을 읽을 때 | Lectern 의 작성 안내·스킬 폴더를 읽어도 되는지 물을 수 있다 — 허용하면 이어서 한다 |

## 이 장의 문서

<!-- 하위 문서 -->
