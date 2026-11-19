# Work management

> Put one `WORK.md` at the top of each folder, and the status, due dates, to-dos and events of many folders are gathered in one place, the work board, with alerts.

WORK.md is plain Markdown that you write and edit without an AI tool. When an AI tool reads and writes it, the same rules apply.

| To do | Keys · menu | Document in this chapter |
|---|---|---|
| See many tasks in one place | **Alt+W** · **Work** in the toolbar | [Work board](#work-board) below |
| Make a work card in a folder · fill in its parts | Right-click, **Make work card…** | [Work cards](8.1-work-cards.en.md) |
| See sub-tasks together and change them in place | List · Kanban · Gantt · Calendar | [Work tree, kanban and Gantt](8.2-work-tree-kanban-gantt.en.md) |
| Add events · get alerts | **Alt+S** · bottom right of the window | [Schedule and alerts](8.3-schedule-and-alerts.en.md) |

## Work board

Press **Work** in the toolbar or **Alt+W** to open the common folder as a tab; the work board shows at the top of that folder's overview.

| Part | What | Click it to |
|---|---|---|
| Needs attention | Blocked · at risk, overdue or due within 3 days, active but WORK.md unchanged for over 14 days, mismatches in the tree — at the top with their path, at any depth | — |
| Work tree | One row per remembered task — status · task (title and folder name, sub-task summary) · priority · due date (D-n) · open to-dos · updated | Title opens the WORK.md; cells are changed in place |
| To-dos with a due date | Overdue · today · this week. Those from the common WORK.md are marked 'Common' | Go to that line |
| Today's events | Today's events. Those from the common WORK.md are marked 'Common' | Go to that line |
| Lines to check | Lines that could not be read because of a typo or something deleted — [Work cards](8.1-work-cards.en.md#lines-to-check) | Go to that line of that WORK.md |
| Folders that could not be read | The folder moved or was deleted, or its drive is not connected; WORK.md is not UTF-8 (for example ANSI from an old Notepad); over 2MB | **Remove from list** (the files stay) |

Lines to check, to-dos with a due date and today's events show up to 50 items; the rest is given as a count. The rows and views of the work tree are in [Work tree, kanban and Gantt](8.2-work-tree-kanban-gantt.en.md). **Work settings…** on the work board opens work management in the settings window.

## Common folder

| Situation | What happens |
|---|---|
| What it is | An ordinary folder for a WORK.md with events and to-dos outside any task, and for weekly and monthly reviews |
| The first time you open the work board | You choose it (for example `Documents\Lectern work` — you can make a new folder in the picker) |
| The common WORK.md | Make it with **Make the common WORK.md** on the work board |
| If the common folder moves or is deleted | Opening the work board asks you to choose it again — the list of task folders stays as it is |
| Changing · clearing | **Work management** in the settings window |

## Remembered folders

| Situation | What happens |
|---|---|
| Opening a folder with a WORK.md | It is remembered automatically. WORK.md files in subfolders are found and added too (not inside hidden or excluded folders) |
| Adding without opening | **Add folder** on the work board — if the chosen folder has no WORK.md, Lectern asks whether to open it and make one |
| Making a work card | That folder joins the list |
| Closing the tab | It stays on the work board |
| What is read | Only the one `WORK.md` file of a remembered folder — no other files in that folder |
| Inside the Lectern program folder (the samples) | Not remembered |
| Removing from the list | **Remove from list** on a folder that could not be read · **Work management** in the settings window |

## Planning notes

The `## Planning notes` section of a work card is where you jot things down as they come. In the templates it sits right under the one-line summary. Lectern does not read this section — a `- [ ] …` or `- 2026-11-25 draft meeting?` written there does not show on the work board, in alerts or among the lines to check. The section runs to the next heading of the same or a higher level (such as `## To do`), and `## 기획 메모` · `## 자유 서술` (the Korean names) work the same.

| Way to tidy up | How | Result |
|---|---|---|
| Yourself | Read the notes and move items to the to-do, schedule and decision sections | Delete the notes you moved |
| With an AI tool | Right-click a WORK.md's margin, **Ask to fold in the planning notes** — the request goes into the first terminal (Enter is not pressed) | Following the writing guide, it moves items to the to-dos, schedule, decisions and current state. It skips lines already there, asks when a date is unclear, and adds one line to the log saying what it folded in. It does not edit or delete the notes — removing them is up to you |

## With AI tools

Give the AI tool the writing guide with **Teach Claude Code about Lectern** in the settings window and it writes WORK.md in the same format.

| Task to hand over | Example request |
|---|---|
| Make a work card | "Make a WORK.md for this folder" |
| Pull out to-dos | "Take the to-dos from the meeting notes and add them to WORK.md" |
| Log | "Write what I did today in the log section" |
| Tidy up planning notes | Right-click the document, **Ask to fold in the planning notes** |

## Documents in this chapter

<!-- 하위 문서 -->
