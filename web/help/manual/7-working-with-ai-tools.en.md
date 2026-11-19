# Working with AI tools

> Send document locations and requests to an AI tool (Claude Code and others) running in the terminal, and see its edits right away.

Lectern does not run AI tools. You start one in the terminal yourself; Lectern only puts locations and requests in, without pressing Enter.

## One round

| Step | What to do | Key · menu | More |
|---|---|---|---|
| 1 | Open the project folder you work on with the AI tool in Lectern | **Ctrl+O** | [Project tabs](2.2-project-tabs.en.md) |
| 2 | Open the terminal and start the AI tool — `claude` | **Ctrl+\`** | [Terminal](7.1-terminal.en.md) |
| 3 | Send the place to look at — the location of the current line · picked lines, `@path lines 12-20` | **Shift+→** · right-click **Copy location** | [Sending and requests](7.2-sending-and-requests.en.md) |
| 4 | Point at a whole document — for example `@docs/report.md summarize the conclusion in three lines` | Tree right-click **Copy @path** | [Sending and requests](7.2-sending-and-requests.en.md) |
| 5 | See the edits — they show within a second, and changed documents you have not opened yet get an amber dot in the tree | **F7** · **Shift+F7** | [Find and search](3.2-find-and-search.en.md) |
| 6 | Have it write documents that read well in Lectern | Settings **Teach Claude Code about Lectern** | [Requests in the settings window](7.2-sending-and-requests.en.md#requests-in-the-settings-window) |
| 7 | Leave writing that people read, such as reports and review comments, to it | Settings **Writing style** | [Writing styles and polish](7.4-writing-styles-and-polish.en.md) |

## Who does what

| Who | What they do |
|---|---|
| Lectern | Puts locations · requests into the terminal (Enter is not pressed). To show how things stand, it only reads a few fixed files of the AI tool |
| AI tool | Works as the request says. Before changing or installing files, it tells you how things stand and asks |
| You | Press Enter, and when the AI tool asks, say yes or choose |

## What differs by tool

The terminal runs any program, so you can start `codex` (OpenAI Codex CLI), `agy` (Google Antigravity CLI) or `opencode` (OpenCode) instead of `claude`. Sending locations (**Shift+→** · **Shift+number**) and seeing edits right away work the same. Choose the tool under **AI tool** in Settings and the names on screen ('Send to Codex', 'Copy request for Codex') and the files and folders named in requests change to match. This guide writes menu names as they are for Claude Code.

| | Claude Code | Codex | Antigravity | OpenCode |
|---|---|---|---|---|
| In the terminal | `claude` | `codex` | `agy` | `opencode` |
| Project instruction file | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| Personal skills folder | `~/.claude/skills` | `~/.agents/skills` | `~/.gemini/config/skills` | `~/.config/opencode/skills` |
| Project skills folder | `.claude/skills` | `.agents/skills` | `.agents/skills` | `.agents/skills` |
| Lectern summary (all folders) | `~/.claude/rules/lectern.md` | A section of `~/.codex/AGENTS.md` | A section of `~/.gemini/AGENTS.md` | A section of `~/.config/opencode/AGENTS.md` |
| Writing style | Output style (choose where it is on) | A 'Writing' section in the personal instruction file or `AGENTS.md` | Same | Same |
| My voice note | `~/.claude/rules/my-voice.md` | A 'My voice' section in the personal instruction file | Same | Same |
| Continue a conversation | `claude --continue` | `codex resume --last` | `agy --continue` | `opencode --continue` |

| Case | What happens |
|---|---|
| Choosing **Several** | The name on screen becomes 'AI', and requests list each tool's files and folders together |
| Using several tools in one project | Keep the rules in `AGENTS.md` and leave only the line `@AGENTS.md` in `CLAUDE.md` — you edit one place |
| Several tools side by side | Stack terminals, Claude Code in 1 and Codex in 2, and pick where to send with **Shift+number** |
| When Codex has `~/.codex/AGENTS.override.md` | It reads only that instead of the personal instruction file `~/.codex/AGENTS.md` — Files that change in the settings window tells you so |
| When Antigravity · Codex read outside the working folder | They may ask whether they may read Lectern's writing guide · skills folder — allow it and they carry on |

## Documents in this chapter

<!-- 하위 문서 -->
