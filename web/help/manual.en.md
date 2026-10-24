# Lectern User Guide

Lectern is a viewer for people to skim and read the documents that Claude Code or Claude writes into a project folder. It shows Markdown (`.md`) and HTML (`.html`) documents in a readable layout, and shows code in a read-only code view.

- **View only.** Lectern never edits or deletes your documents; the only file it writes is its settings file. The one exception is commands you type yourself in the right-hand terminal.
- **It does not connect to the internet on its own.** Only web images inside documents are loaded, and you can turn that off in Settings.
- **It only looks inside the folder you open.** Hidden files and folders (`.git`, `.claude` and so on) are not shown. Excluded folders such as `node_modules` and `dist` stay out of the document tree and search, and appear dimmed only in the 'Other files' list.

> [!TIP]
> Press F1 to open and close this guide (Esc also closes it). Click an entry in the contents on the left to jump to it, and press Ctrl+F to search the guide. For just the keyboard shortcuts, click the **?** button in the toolbar or press Ctrl+/.

## Getting started

### Opening a folder

- Click **+** in the tab bar (Ctrl+O) and choose a project folder; it opens in a new tab. If the folder is already open, Lectern switches to its tab.
- The arrow next to **+** lists recent folders.
- You can also right-click a folder in Explorer and choose **Open with Lectern**. If Lectern is already running, the folder opens as a tab in that window instead of a new window.
- When you start Lectern again, the tabs you had open come back, each at the document and position you were reading.

### The window

| Area | What it does |
|---|---|
| Toolbar (top) | Sidebar, back, forward, **Quick open** (Ctrl+P), text size − 100% +, style, section focus, settings, **?** (keyboard shortcuts), all terminals |
| Tab bar | One tab per open project, open folder (+), and the **Contents** and **Terminal** buttons at the right end |
| Sidebar (left) | The **Files**, **Recent**, **Search** and **Elements** tabs. Drag its edge to resize (double-click to reset) |
| Main area (center) | Documents, folder overviews and the code view |
| Contents (right) | The current document's headings and elements such as tables and figures. When the terminal is open, it takes this place |
| Status bar (bottom) | Document path and modified time, the changes button, and the watching status |

## Project tabs

- Each folder gets its own tab (up to 10). Clicking a tab switches the sidebar and main area to that project, and every tab keeps its own document and scroll position.
- When a document in a background tab changes, a dot appears next to the tab name.
- Folders with the same name also show their parent folder's name.
- To close a tab, click its ×, middle-click it, or press Ctrl+W. Right-click a tab for Close other tabs, Copy full path and Show in Explorer.
- To move between tabs: Ctrl+1~8 (tab by position), Ctrl+9 (last tab), Ctrl+Tab / Ctrl+Shift+Tab (next / previous tab).

## Sidebar

### Files — documents, code and other files

The **Files** tab is split into three groups.

| Group | What it holds | Clicking |
|---|---|---|
| Documents | Markdown and HTML documents (a folder tree) | Click once to open in the main area |
| Code | Source (py, js, ts…), scripts (ps1, bat), web (css) and config (json, yaml, toml) | Click once for the code view, double-click for the editor |
| Other files | Anything that is neither a document nor code — PDF, Office, images, data, archives, programs and so on | Double-click to open in the default app (programs and archives are never run; they are only selected in Explorer) |

- Click a group header ('Documents 10', 'Code 3', 'Other files 4') to collapse that group. Drag the divider between groups to resize them, and double-click it to reset.
- The box at the top filters by name or title. Turn on **Titles** to show document titles instead of file names (when off, file names are shown and the title appears on hover).
- Turn on **Folders** to see everything in one tree that follows the real folder structure, instead of three groups.
- Documents that changed since you last looked get an amber dot.
- The 'Code' and 'Other files' lists work like Explorer: arrow keys (→ expand, ← collapse) and Enter, and typing a letter jumps to the item starting with it.
- **Excluded folders** such as `node_modules`, `dist`, `build`, `venv` and `__pycache__` appear dimmed and collapsed in 'Other files'. They can hold a great many files, so their contents are read when you expand them, and everything inside is listed there whatever its type (code still opens in the code view with one click). Changes inside are not followed automatically — collapse and expand the folder again, or press F5, to read it afresh. They are not counted in the group header or matched by the filter.
- Right-click menu: `Copy @path` (for pasting into a Claude Code prompt), Copy full path, Open in editor, Show in Explorer. Right-click a folder to collect the elements in just that folder.

### Recent

- Files in the order they were changed. The **Documents**, **Code** and **Other files** buttons at the top choose what to show (with all on, they are mixed, newest first).
- Click a document or code file once to open it; double-click an other file or press Enter to open it. Right-click for the same menu as in the 'Code' and 'Other files' lists.
- The number next to the 'Recent' tab is the number of changed documents you have not opened yet.

### Search

- Searches the text of all documents and code, and file names (Ctrl+Shift+F). Case does not matter.
- The **Documents**, **Code** and **Other files** buttons under the search box choose where to search. **Matching file names** (titles too, for documents) come first, then text results — documents first, followed by a 'Code' group. Other files (PDF, Excel and so on) are searched by name only.
- Click a result line to go to that line of the document (or code) with the search text marked.
- To open something by name or title, **Quick open** (Ctrl+P) in the toolbar is faster. Matching documents come first, then code.

### Elements

- Choose **In documents** or **File types** at the top.
- In documents: collects the tables, figures, callouts, diagrams, code and math across the project, by type and by document. Pick a type with the buttons (such as 'Tables 7').
- Click an item to go to that place in its document; it is outlined briefly.
- The 'Elements' buttons on a folder overview, or right-clicking a folder in the tree, collect just that folder ('All' switches back to the whole project).
- The first time it opens, it takes a moment to read the documents.
- File types: each group — documents, code and other files — gets a button per format, such as 'PDF 2', 'Excel 3', 'PNG 10', 'PY 12' or 'IPYNB 2', and the files of the chosen format are collected. Excel, PowerPoint, Word and Hangul files count as one format whatever their extension. Image files appear as thumbnails. The 'Tree order' button switches to the most recently changed files first.
- Right-click a folder in the 'Code' or 'Other files' list and choose **Collect the files in this folder by type** to collect just that folder.

## Reading documents

### Folder overview

This is the first screen when a folder opens. It shows recently changed documents, subfolders, and each document's title, summary and modified time. Click a folder name in the tree to see that folder's overview.

### Document view

- Tables align number columns to the right, and the header row stays visible as you scroll.
- Code blocks are colored by language; the 'Copy' button at the top right copies them.
- Callouts (`> [!NOTE]` and so on), footnotes, checklists, math (`$…$`, `$$…$$`, and math/latex code blocks) and Mermaid diagrams are rendered. Dollar amounts such as `$105` are not turned into math.
- Click an image to enlarge it.
- Paths in the text that point to real files, such as `src/app.py:42`, become links.

### Contents

- Click an entry in the contents on the right to jump to that heading; the place you are reading is marked.
- Under each heading, the section's tables, figures, callouts, diagrams, code and math are listed like 'Table 1 · Price comparison · 6 × 4'. Click one to jump to it.
- The buttons at the top of the contents, such as 'Tables 2' or 'Code 5', hide that type from the contents; click again to show it.
- The **Contents** button at the right end of the tab bar shows or hides the contents.
- Drag the border between the document and the contents to resize the contents. Double-click it to reset.

### Folding sections

Click a heading to fold its section, and click it again to unfold. Right-click the text for Fold all at this level and Fold all / Unfold all. Folded sections are unfolded again when Lectern restarts.

### Text size and style

- The − / + buttons in the toolbar set the document text size from 80% to 200% (100% is already set slightly large for comfortable reading). Click '100%' in the middle to reset. To zoom the whole app, use Ctrl+Wheel.
- The **Style** list has 24 styles; picking one changes the document and the toolbar and sidebar colors together. The ∧ ∨ buttons next to the list step through the styles so you can compare them. 'Auto' follows the Windows dark mode.
- How the style list is grouped (by use, by mood or by brightness) is chosen in Settings.

### My styles

- You can make styles of your own. Each CSS file is one style; put it in the `%APPDATA%\Lectern\styles` folder and it appears under **My styles** at the bottom of the style list.
- You do not have to write CSS yourself. Click **Copy request for Claude Code** in Settings, paste it into Claude Code, and add the look you want (for example 'navy headings, a dark navy table header with white text, serif body text'). The request gives the location of the style guide that comes with the app and the folder to save in, so the AI reads the guide and makes the file. The terminal button next to it puts the request straight into the terminal.
- While that style is selected, changes to its file are applied again within a few seconds — so you can keep asking ('make the headings larger') and see the result right away.
- **Open style folder** in Settings opens the folder. Deleting a file removes it from the list.
- Anything that would load fonts or images from the internet is removed by the app; only fonts installed on the PC are used.

### Section focus

- The **Focus** button in the toolbar keeps the section you are reading sharp and dims the rest.
- ↑ ↓, PageUp PageDown or the ∧ ∨ buttons next to it move to the previous or next section. Click a dimmed area to move the focus there.
- Press Esc or click the button again to turn it off. You can also right-click the text and choose 'Focus this section' or 'Clear focus'.
- It works in Markdown documents.

### Find in document

- Ctrl+F finds text in the document or code you are viewing, even across formatting such as bold or code.
- Enter goes to the next result, Shift+Enter to the previous one, and Esc closes the find bar.

### HTML documents

HTML reports written by Claude appear in the tree marked `HTML`. Their own styles are kept, while scripts and stylesheets from the internet are blocked (so charts drawn by scripts do not appear). HTML files inside app source folders such as `src`, `public` or `web` are not treated as documents.

### Auto refresh

- While Claude writes a document, changes appear within a second and your reading position stays where it was.
- Changed paragraphs and tables are highlighted briefly. If the changes are off screen, the **changes** button in the status bar takes you through them.
- If a change was missed, press F5 to reload.

### Print and PDF

Right-click the margin of a document and choose **Print / Save as PDF**. To save a PDF, choose 'Microsoft Print to PDF' as the printer.

## Reading code

- Click a file once in the 'Code' list (or press Enter) to show it in the main area with line numbers and language colors. It is never edited or run.
- The contents on the right list classes, functions, methods and divider comments such as `# ---- drawing ----`; click one to jump to that line. Config files list their keys and sections.
- The **Open in editor** and **Copy all** buttons sit at the top. Right-click a line for Copy line, Copy location for Claude and Open this line in the editor.
- When the code you are viewing changes, it is redrawn within two seconds and the changed lines are highlighted briefly.
- Clicking a path such as `src/app.py:42` or a link to a code file in a document jumps to that line. Go back (Alt+←) to return to the document.
- Files over 4 MB, or files that are not text, show a note to open them in an editor instead.

## Links and opening files

| Link target | Opens in |
|---|---|
| Markdown and HTML documents shown in the tree | Lectern |
| Code files | The code view (add `#L42` to jump to a line) |
| Images, PDF and Office files | The default app |
| Other text files | The editor (or selected in Explorer if there is no editor) |
| Web addresses | The default browser |
| Anything outside the project folder | Not opened (shown struck through) |

Programs and scripts are never run. Absolute paths in documents (`C:\...\chart.png`) also work when they point inside the project.

## Right-click menus and copying

- Right-clicking a heading, paragraph, table or image outlines it and opens a copy menu.
- You can copy the text or the Markdown source. For a heading, copy the whole section or a link to it. Tables copy in a form that pastes into Excel and Word, and images copy as PNG.
- **Copy location for Claude** copies something like `@docs/report.md lines 40-52`. Pasted into a Claude Code prompt, it points Claude at that exact part.
- If you right-click with text selected, 'Copy selected text' appears at the top.
- The **terminal button** to the right of a copy item puts the same text into the terminal (Enter is not pressed). It is there for selected text, the location for Claude, the source, code, `@path`, the full path and so on, including in the right-click menus of the tree and the 'Code' and 'Other files' lists. See 'Terminal' below.

## Terminal

- The **Terminal** button at the right end of the tab bar, or Ctrl+\`, opens a terminal to the right of the main area. Windows PowerShell starts in the current tab's project folder, and each tab has its own shell.
- Closing the terminal leaves the shell running, so reopening it continues where you left off. The ↻ button in its header restarts the shell.
- Keys typed in the terminal go to the shell. Use app shortcuts such as Ctrl+P, Ctrl+F or F1 after clicking the main area (Ctrl+Tab moves to the next tab even inside the terminal).
- Select text with the mouse, then press Ctrl+C or right-click to copy; press Ctrl+V or right-click to paste. With nothing selected, Ctrl+C stops the running command.
- Drag the edge to resize the terminal (double-click to reset).
- **Position**: in a wide window the terminal opens to the right of the document; in a tall window (a portrait monitor, a window snapped to half the screen and so on) it opens below the document. When it is below, drag the edge to change its height. The position button in the terminal header switches between right and below and keeps it there; set 'Terminal position' back to 'Auto' in Settings.
- **Paste into the terminal**: in a right-click menu, the terminal button next to a copy item puts that text into the current tab's terminal, opening the terminal if needed. Enter is not pressed — check the text and press Enter yourself. For several lines Lectern asks first, because at a PowerShell prompt each line may run as a command (programs that turn on paste mode, such as Claude Code, are not asked about).
- The terminal colors follow the document style. For an always-dark terminal, turn off 'Match terminal colors to style' in Settings.
- Closing a tab ends its shell. If a program started from the shell is still running, Lectern asks first. Closing Lectern ends all shells.

### All terminals

- The **All terminals** button in the toolbar, or Ctrl+Shift+\`, gathers the terminals of all open projects on one screen in a grid.
- Each pane's header shows 'Running' or 'Idle', so you can watch Claude Code across several projects at a glance.
- Inside a pane, Ctrl+Tab moves to the next pane. Double-click a pane's header to maximize it.
- A pane's → button goes to that project and opens its right-hand terminal. Clicking a project tab returns to the documents.

## Working with Claude Code

1. Open the project folder you work on with Claude Code in Lectern.
2. Run `claude` in the terminal (Ctrl+\`) to work with Claude Code right next to your documents.
3. When Claude creates or edits a document, the change appears within a second, and changed documents you have not opened yet get an amber dot in the tree.
4. To ask about a document, right-click it in the tree, choose `Copy @path` and paste it into your prompt. For example: `@docs/report.md summarize the conclusion in three lines`
5. To point at one part of a document, right-click the text and choose **Copy location for Claude**.

## Settings

The gear button in the toolbar (Ctrl+,) opens Settings.

| Setting | What it does |
|---|---|
| Language | Auto (Windows display language), 한국어 or English. Changing it reloads the window |
| Group styles | Group the style list by use, by mood or by brightness |
| Resume where I left off | Opening a folder returns to the last document and position |
| Expand top-level folders | Expand the first level of folders in the tree when a folder opens |
| Render math | Render `$…$`, `$$…$$` and math code blocks as equations |
| Show web images | Load https images in documents. When off, they show as links |
| My styles | Open style folder, Copy request for Claude Code (see 'My styles' above) |
| Terminal position | Auto (below the document when the window is taller than wide), Right or Below |
| Match terminal colors to style | When off, the terminal is always dark |

Settings that are not in the window are edited with **Open settings file** in your editor (`%APPDATA%\Lectern\config.json`). Changes apply when you save; settings that affect the tree take effect when you press F5.

| Key | What it does |
|---|---|
| `language` | `auto`, `ko` or `en` |
| `editor` | Full path of the editor for code files. When empty, VS Code (`code`) is used |
| `exclude_dirs` | Folder names to leave out of the tree (for example `["data", "output"]`) — they still appear collapsed in 'Other files' |
| `terminal_shell` | Full path of the terminal shell (for example PowerShell 7). When empty, Windows PowerShell is used |

Write backslashes in paths twice (`\\`). If the file has a syntax error, Lectern starts with the default settings and tells you where the error is.

## Keyboard shortcuts

You can bring up this table at any time with the **?** button in the toolbar or Ctrl+/.

<!-- 단축키 표 -->

## Good to know

- Lectern is view only. The right-hand terminal, however, is an ordinary PowerShell, so commands typed there run as usual.
- The terminal needs Windows 10 (1809) or later. A shell's history is gone once Lectern closes.
- Document titles in the tree are read from the beginning of each document. If a document starts with a very long frontmatter, its file name is shown instead.
- Web images that cannot be loaded (blocked on a company network, or taking more than 15 seconds) turn into links.
