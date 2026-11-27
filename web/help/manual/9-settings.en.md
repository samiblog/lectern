# Settings

> What you choose in each section of Settings (Ctrl+,), where to change settings that are not in the window, and where settings are kept.

## Settings window

| To do this | How | Result |
|---|---|---|
| Open Settings | Gear in the toolbar · **Ctrl+,** | Opens at the section you chose last |
| Go to a section | Click a section on the left | The right side moves to it. As you scroll, the current section is highlighted |
| Choose one of several | One-line buttons | The chosen one's description shows below |
| Turn on or off | Switch at the right end | Applies the moment you choose — there is no save button |
| Open it from where you use it | Right-click the terminal header for **Terminal settings…** · **Style settings…** at the bottom of the toolbar style list · **Work settings…** on the work board · the **vi** sign in the status bar · **Font and layout settings…** in the export window | Opens at that section (Terminal · View · Work · Edit · Print and export) |

## Where settings apply

| Setting | Where it applies |
|---|---|
| Settings in the settings window | All of Lectern — every folder and window. They are not kept per folder |
| Other windows | Open separate windows and slide windows follow within a second or two. The same happens when you edit the settings file in an editor and save it |
| View settings changed only in a separate window (text size and so on) | Stay in that window only. They follow when another window changes that setting |
| md document style · notes · work cards · the last place you read | Belong to that folder or document |
| **What you hand to the AI tool** under 'AI tool' | Not Lectern settings but files of the AI tool (Claude Code and others) |

## General

| Setting | What you choose |
|---|---|
| Language (the title reads `언어 · Language` in both languages) | Auto (Windows display language) · 한국어 · English. Changing it reloads the window (open tabs and terminals stay) |
| Resume where I left off | Opening a folder returns to the document and position you last viewed |
| Expand top-level folders | Expands the first level of folders in the tree when a folder opens |
| Show document titles in lists | Off (default): md documents show their file names, and the title when you point at them. Same as the sidebar 'Titles' button; document tabs, Open document, Recent changes, Search and folder overviews follow it |
| Subgroups under 'Documents' in the sidebar | Which of PDF, Word, PowerPoint, Excel·CSV and Hangul (HWP) to move under 'Documents' — none at first ('Documents' holds only md and html; the rest stay in 'Other files'). Kinds turned on leave 'Other files' ([Sidebar](2.4-sidebar.en.md)) |

## View

| Setting | What you choose |
|---|---|
| Group styles | Groups the toolbar style list By use · By mood · By brightness |
| My styles | **Make on screen…** ([Make my style](2.1-toolbar.en.md#making-your-own-styles)) · **Open style folder** · **Copy request for Claude Code** · ▣ (puts that request into the terminal). One CSS file is one style, and it appears under 'My styles' at the bottom of the style list |
| Diagram style · color set | The default look of Mermaid and Graphviz diagrams (numbers 1–10) and the default color set of charts and diagrams (1–8), with a preview and color chips. **Look samples** · **Color set samples** open the example documents that draw every number. The 'mine' group in the lists holds your own diagram styles and color sets (`diagram-styles` in the settings folder — **Open my diagram styles folder**; problem files are listed below it with the reason). Diagrams with a marker line (`%% style: 3 Card · colors: 2 Report navy`) or a document default line (`<!-- diagram: … -->`) follow it ([Diagram styles](3-reading.en.md#diagram-styles)) |
| Table cell alignment | Default (text left · numbers right · top of the cell) · Report style (header row and short columns centered, numbers right, long text left, vertically centered). Columns with an alignment mark in the source (`:---:`) follow the mark |
| Render math | `$…$` · `$$…$$` · math and latex code blocks as equations |
| Show line breaks inside paragraphs | Lines you break with Enter in the source break on screen too (like Shift+Enter in Word). When off, they run on as in standard Markdown |
| Show web images | Loads https images in documents. When off, they show only as links and nothing is requested from the internet. Changing it reloads the window |

## Edit

| Setting | What you choose |
|---|---|
| vi keys | Move and edit in documents with letter keys — j·k move between lines, V picks, dd deletes, i writes, u undoes. Off by default; when on, the status bar shows `vi` |
| Full editor keys | Default (Esc closes, Ctrl+S saves) · vi (like vim — Esc goes to Normal mode, `:w` saves, `:q` closes). Chosen separately from the vi keys of the reading view |

## Print and export

| Setting | What you choose |
|---|---|
| Print and PDF font | Body font of 'Save as PDF…' and 'Print…' — Serif (Cambria, with Korean text in HCR Batang, or Batang if it is missing · headings in sans-serif) · Sans-serif (Calibri, with Korean text in Malgun Gothic) |
| Page layouts | **Open layouts folder** · **Copy request for Claude Code** · ▣. One html file is one layout, and it appears under 'My layouts' in 'Layout' of the export window |

Paper and PDF come out in a report format regardless of the screen style. Margins, page headers and page numbers are chosen in the export window and stay the same next time.

## Terminal

| Setting | What you choose |
|---|---|
| Terminal position | Auto (below the document when the window is taller than wide, otherwise on the right) · Right · Below. Changing it with the position button in the terminal header fixes it there; set it back to Auto here |
| Match terminal colors to style | Matches the background and text colors to the document style. When off, always dark |
| Terminal text size | 10–24 (default 14) — **−** · **+** · **Default size** · a number. Applies at once to open terminals and All terminals |

## AI tool

The upper part, **Lectern settings**, belongs to Lectern; the lower part, **What you hand to the AI tool**, is the AI tool's files. The names of buttons and requests follow the AI tool you use.

| Setting | What you choose | More |
|---|---|---|
| AI tool | Claude Code (default) · Codex · Antigravity · OpenCode · Several. Names on screen ('Send to Codex') and the instruction file and skill folder that requests mention follow it. Lectern does not run the tool | [Working with AI tools](7-working-with-ai-tools.en.md) |
| Teach Claude Code about Lectern | Where it goes (All folders (personal) · Only the ○○ folder) → copy a request to read the writing guide and write up its rules · ▣ · **Open samples** | [Sending and requests](7.2-sending-and-requests.en.md) |
| PowerPoint and Word skills | Where they go → a request to install only the ones that are missing or different | [Skills](7.3-skills.en.md) |
| Writing style | **Choose a style…** → where it is on (Turn on in ○○ · Turn on in all folders · Turn off in ○○) → a request to install it and turn it on. Codex · Antigravity · OpenCode get it as a 'Writing' section in the personal instruction file or that folder's AGENTS.md | [Writing styles and polish](7.4-writing-styles-and-polish.en.md) |
| My voice | A request to make your voice note (one in your personal folder) from writing you wrote yourself — add the samples as `@paths` at the end | [Writing styles and polish](7.4-writing-styles-and-polish.en.md) |

| What you hand to the AI tool | What happens |
|---|---|
| When you choose where it goes | **Files that change** below shows the full path and what will happen (Create · Change · Unchanged · Add section · Write one value · Move) |
| How things stand | Lectern only reads a few fixed files in your personal folder (`~/.claude` and others) and the open folder — from a settings file, only the `outputStyle` value |
| Who writes the files | The AI tool that gets the request, after it tells you how things stand and asks |
| Writing inside `.claude` | Claude Code asks permission once more — allow it if it matches what Files that change showed |

## Work

| Setting | What you choose |
|---|---|
| Work management | **Choose common folder…** · **Clear**, and removing folders from the work folder list |
| Work alerts | At the bottom right of the window while Lectern is running — today's summary at start, events 10 minutes ahead, and at 17:30 active tasks with no record today. On by default |

## Advanced — settings changed only in the file

**Open settings file** opens `%APPDATA%\Lectern\config.json` in your editor. Changes apply when you save; for settings that affect the tree, press **F5** to reload. Below the Advanced section, the current values of the editor path, excluded folders and terminal shell are shown.

| Key | What it does |
|---|---|
| `editor` | Full path of the editor that opens code files. When empty, VS Code (`code`) |
| `exclude_dirs` | Folder names to leave out of the tree (for example `["data", "output"]`) — added to the default excluded folders (`node_modules` · `dist` · `build` · `venv` and others). They still appear collapsed in the 'Other files' list |
| `html_exclude_dirs` | html inside folders with these names is not treated as documents — added to the defaults (`src` · `public` · `web` and others) |
| `terminal_shell` | Full path of the terminal shell (for example PowerShell 7). When empty, Windows PowerShell. After changing it, restart the terminal with its ↻ for it to apply |
| `ref_windows` | Open the User guide and the Example guide in their own windows — `auto` (default) · `on` · `off` (covering the main window instead) |

Write backslashes in paths twice (`\\`). If the file has a syntax error, Lectern opens with the default settings and tells you where the error is.

## View settings source

**View settings source** under Advanced, and **View source** on each 'AI tool' item, show files as they are without changing them — Lectern settings, the writing guide summary, the voice note, Claude Code settings (personal · this folder), writing styles (installed and included in Lectern) and skills (SKILL.md and the files in its folder).

| What you see | Meaning |
|---|---|
| Numbered lines | The file's source |
| Faint `//` lines without numbers | Explanations Lectern adds — they are not in the file. For each key: its meaning, default value and where it is changed (which Settings section · 'Recorded by Lectern' · 'this file only') |
| Notices | Values with the wrong form, keys Lectern does not use |

Claude Code's personal settings may hold secret values, so take care when sharing your screen.

## Settings folder

Settings are kept in `%APPDATA%\Lectern`. They stay when you uninstall Lectern, so after reinstalling, your recent folders and styles are as they were.

| Name | What | Opened from |
|---|---|---|
| `config.json` | Lectern's settings — Lectern writes it when you change things in Settings or the toolbar | Advanced **Open settings file** |
| `cache` | Remembered titles — for each project, the titles of documents and whether each is slides | Rebuilt if you delete it |
| `styles` | My styles (CSS) | View **Open style folder** |
| `md-styles` | My styles for md documents | **Open style folder** in the md document style window |
| `templates` | My template sets for Lectern slides | **Open templates folder** in the template gallery — opens in a Lectern tab |
| `pptx-styles` | pptx styles | **Open library folder** in the 'Convert to pptx' window |
| `layouts` | My page layouts | Print and export **Open layouts folder** |
| `docx-styles` | My Word templates | **Open Word templates folder** in the export window |

## Related

| Document | What |
|---|---|
| [When files change](10.2-when-files-change.en.md) | The only place Lectern writes on its own is the settings folder |
| [Working with AI tools](7-working-with-ai-tools.en.md) | What you hand to the AI tool · what differs per tool |
| [Troubleshooting](10.3-troubleshooting.en.md) | Settings file errors · when web images do not show |
