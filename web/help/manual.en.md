# Lectern User Guide

Lectern is a viewer for people to skim and read the documents that Claude Code or Claude writes into a project folder. It shows Markdown (`.md`) and HTML (`.html`) documents in a readable layout, and shows code in a read-only code view.

- **Made for reading.** Lectern never deletes or creates documents; the only files it writes are its settings file and files you save yourself in **edit mode**. Commands you type yourself in the right-hand terminal are also an exception.
- **It does not connect to the internet on its own.** Only web images inside documents are loaded, and you can turn that off in Settings.
- **It only looks inside the folder you open.** Hidden files and folders (`.git`, `.claude` and so on) are not shown. Excluded folders such as `node_modules` and `dist` stay out of the document tree and search, and appear dimmed only in the 'Other files' list.

> [!TIP]
> Press F1 to open and close this guide (Esc also closes it). Click an entry in the contents on the left to jump to it, and press Ctrl+F to search the guide. For just the keyboard shortcuts, click the **?** button in the toolbar or press Ctrl+/.

## Getting started

### Opening a folder

- Click **+** in the tab bar (Ctrl+O) and choose a project folder; it opens in a new tab. If the folder is already open, Lectern switches to its tab.
- The arrow next to **+** lists recent folders and **Open samples**.
- **Open samples** (also on the start screen) opens a sample project with a tour of Lectern and how to write documents. It is set up like a research project done with Claude Code, so you can try the tree, code, files and charts right away. The samples live inside Lectern's program folder, so they are **view-only** — their tab has no terminal, edit mode, new documents or renaming (so that no commands run and no files change next to the program files). To try editing or Claude Code with them, copy the samples folder elsewhere (for example to Documents) and open the copy — 'Show this folder in Explorer' in the terminal area finds the folder.
- You can also right-click a folder in Explorer and choose **Open with Lectern**. If Lectern is already running, the folder opens as a tab in that window instead of a new window.
- When you start Lectern again, the tabs you had open come back, each at the document and position you were reading.

### The window

| Area | What it does |
|---|---|
| Toolbar (top) | Sidebar, back, forward, **Quick open** (Ctrl+P), text size − 100% +, style, section focus, settings, **?** (keyboard shortcuts), all terminals |
| Tab bar | One tab per open project, open folder (+), and the **Contents** and **Terminal** buttons at the right end |
| Document tab row | Just above the document — the documents open in this project (up to 20), open a document in a new tab (+), the list of open document tabs at the right end (∨) |
| Sidebar (left) | The **Files**, **Recent**, **Search**, **Elements** and **Clip** tabs. Drag its edge to resize (double-click to reset) |
| Main area (center) | Documents, folder overviews and the code view |
| Contents (right) | The current document's headings and elements such as tables and figures. When the terminal is open, it takes this place |
| Status bar (bottom) | Document path and modified time, the changes button, and the watching status |

## Project tabs

- Each folder gets its own tab (up to 10). Clicking a tab switches the sidebar and main area to that project, and every tab keeps its own document and scroll position.
- When a document in a background tab changes, a dot appears next to the tab name.
- Folders with the same name also show their parent folder's name.
- To close a tab, click its ×, middle-click it, or press Ctrl+W. Right-click a tab for Close other tabs, Copy full path and Show in Explorer.
- To move between tabs: Ctrl+1~8 (tab by position), Ctrl+9 (last tab), Ctrl+Tab / Ctrl+Shift+Tab (next / previous tab).

## Document tabs

Keep up to 20 documents of a project open as tabs and switch between them. They appear in the document tab row just above the document.

- A normal click opens in the current tab. To open in a **new tab**, **Ctrl+click** or **middle-click** in the tree, the Code and Other files lists, links and paths in documents, the folder overview, search results or Elements. In the sidebar lists (tree, folder view, Recent, search results, Elements) simply **double-click** a document: the document the first click opened in the current tab moves to a new tab and the current tab goes back to what you were reading. (Files in the Code and Other files lists still open in your editor or default app on double-click — Ctrl+click them to view them in a new tab.) **Open in new tab** in right-click menus and **+** in the document tab row (the quick open box then opens in a new tab — Ctrl+Enter in quick open does too) work as well. **New document…** at the top of the **+** box makes a new document and opens it in a new tab (see New document below).
- Clicking a document that is already open in another tab goes to that tab (a document is not opened twice).
- When all 20 are in use, the tab you looked at least recently is reused (tabs with unsaved edits are left alone).
- Each tab keeps its own reading position, back/forward history and edit-mode changes. A tab with unsaved edits shows **●**. So you can edit a document in one tab while reading material in another, and Send from the Clip tab opens the receiving document in its own tab.
- To switch, click a tab or press **Alt+1~8** (by position) or **Alt+9** (last tab). When there are more tabs than fit, scroll the row with the mouse wheel or click **∨** at its right end (the number beside it is how many are open) and pick from the list of open document tabs. To close, click its ×, middle-click it or press **Ctrl+F4** (the last tab is not closed). Right-click a tab for Close other document tabs and copying its path.
- The next time Lectern opens, your document tabs come back (when Settings → Start where I left off is on — only the selected tab is drawn at once, the others when you click them).

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
- Right-click menu: `Copy @path` (for pasting into a Claude Code prompt), Copy full path, Open in editor, Show in Explorer, **Rename…**. Right-click a folder to collect the elements in just that folder.
- **Renaming**: right-click a file in the document tree, Code or Other files list (or in Recent and search results) and choose **Rename…**, or select its row and press **F2**. The current name is selected up to the extension — type the new name and press Enter (Esc leaves it as is). Only the name changes; the file stays in its folder.
  - If a file with that name exists or the name cannot be used (starting with a dot, containing `\ / : * ? " < > |` and so on), the reason is shown and nothing changes. Changing the extension asks once more.
  - A document tab showing the file follows the new name (and edit mode reopens if it was on), and so do the back history and clips. A file with unsaved edits must be saved or closed first.
  - Links to this document from other documents are not changed. Folders and files inside excluded folders are not renamed, and there is no delete or move.

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

- Choose **In documents**, **Doc info** or **File types** at the top.
- In documents: collects the tables, figures, charts, callouts, diagrams, code, math, to-dos, links and sources across the project, by type and by document. Pick a type with the buttons (such as 'Tables 7').
  - **Charts** (Vega-Lite, ECharts, Plotly) are collected as thumbnails, like figures — each is drawn when it scrolls into view. Graphviz and Mermaid are diagrams.
  - **To-dos** are the checklists in documents (`- [ ]`, `- [x]`). The buttons below choose **Open** (the default), Done or All.
  - **Links** lists the links in documents and paths such as `src/x.py:42`, with their target (document, code, other file, folder or web). A link whose file does not exist is marked **Broken** in red — the **Broken** button below shows only those.
  - **Sources** are lines such as 'Source: …' under tables and figures (and their Korean equivalents), plus footnotes.
  - To-dos, links and sources are not shown in the contents (only here).
- When a table, figure or diagram has a **caption**, the caption is shown as its name, with the number and size below (such as 'Table 3 · 6 rows 2 columns'). A caption is a line such as 'Table 1. …', '<Table 2>' or '[Figure 1]' (or the same forms in Korean) directly above a table or below a picture, a short whole-bold line, or `<caption>`/`<figcaption>` in HTML. Without one, tables show their header row and pictures their alt text.
- Click an item to go to that place in its document; it is outlined briefly.
- **Right-click** an item for Show in document, **Copy location for Claude** (`@document lines 12-17 ('caption')`), **Copy source** (Markdown documents), **Clip**, **Send…** and **Clip all shown** (see Clip below) and copying the document path. The **▣ Terminal** button next to a copy item puts that text into the terminal (Enter is not pressed).
- The 'Elements' buttons on a folder overview, or right-clicking a folder in the tree, collect just that folder ('All' switches back to the whole project).
- The first time it opens, it takes a moment to read the documents.
- Doc info: a button for each key in the documents' front matter (such as `status: review`, `owner: research`, `tags: [a, b]`); documents are grouped by the values of the chosen key (dates newest first). Indented sub-keys appear joined with a dot, such as `author.name`. Documents without that key are under 'No value' at the end. Click a document to open it; right-click to copy its `@path` or put it into the terminal.
- File types: each group — documents, code and other files — gets a button per format, such as 'PDF 2', 'Excel 3', 'PNG 10', 'PY 12' or 'IPYNB 2', and the files of the chosen format are collected. Excel, PowerPoint, Word and Hangul files count as one format whatever their extension. Image files appear as thumbnails. The 'Tree order' button switches to the most recently changed files first.
- Right-click a folder in the 'Code' or 'Other files' list and choose **Collect the files in this folder by type** to collect just that folder.

### Clip

Collect pieces of documents and send them to a document open in a document tab, or to a new one.

- **To clip**: right-click a heading for **Clip this section** (the heading and everything under it), or a table, figure, chart, diagram, math, code or paragraph for **Clip** — tables, figures and charts take their caption and the 'Source:' line right below with them. With text selected, right-click for **Clip selected text**. In Elements, right-click an item for **Clip**, or **Clip all shown** (the list as filtered — all the tables in the project, for example).
- Clips pile up in order in the sidebar **Clip** tab (with a count next to it). Reorder them with ↑ and ↓, remove one with ✕, and click one to go to its place in the original document. A clip keeps the text as it was when clipped, even if the document changes later. Each project tab has its own clips, and they are cleared when Lectern closes.
- **Send to a document…** (above the clips — all of them, in order) or **Send…** in a right-click menu (just that piece) asks where: where you are editing (at the cursor), **New document…**, or **a document open in a document tab** → **At the end**, **At the beginning** or **End of section '…'**.
- Only documents open in document tabs and new documents can receive. To send to another document, open it in a document tab first (Ctrl+click it in the tree — see Document tabs above).
- That document **opens in edit mode** with the sent text lightly shaded. Check it and save with **Ctrl+S** — the file does not change until you save.
- For **New document…**, type a path and press Enter: the document is created right away with a title line (see New document below) and the clips go to its end in a new document tab.
- When sending, Lectern rewrites relative paths of pictures, links and chart data for the receiving document, brings the footnote definitions along (renaming them if the names clash) and fits heading levels to the place (under the section for 'End of section'). Each piece gets a hidden `<!-- from: research/a.md lines 12-19 -->` comment, so Claude Code can tell where it came from.
- While another document is open in edit mode, **Send** on an item in the Clip tab puts it right after the block the cursor is in.
- **Ask Claude** makes a Claude Code request listing the clips' locations (`@doc lines 12-19 ('name')`) and asking for a new document from them — copy it or put it into the terminal with ▣ (Enter is not pressed).
- Lines in the code view and blocks of HTML documents cannot be clipped (they have no source lines), and clips can be sent only to Markdown documents.

## Reading documents

### Folder overview

This is the first screen when a folder opens. It shows recently changed documents, subfolders, and each document's title, summary and modified time. Click a folder name in the tree to see that folder's overview.

### Document view

- Tables align number columns to the right, and the header row stays visible as you scroll.
- Code blocks are colored by language; the 'Copy' button at the top right copies them.
- Callouts (`> [!NOTE]` and so on), footnotes, checklists, math (`$…$`, `$$…$$`, and math/latex code blocks) and Mermaid diagrams are rendered. Dollar amounts such as `$105` are not turned into math.
- **Charts**: code blocks whose language is `vega-lite` (data charts), `echarts` (many chart types such as donuts and candlesticks), `plotly` (analysis charts such as box plots and sunbursts — the output of Python's `fig.to_json()` works too) or `dot`/`graphviz` (structure and dependency graphs) are drawn as pictures. Colors follow the document style; click to enlarge, and use 'Copy image' in the right-click menu to paste a PNG. Settings are JSON and functions are not allowed. Write the data in the document or point to a CSV/JSON file in the project with a relative path (internet addresses are not read). There is no hover or zoom, and Plotly map charts are not drawn because they need map data from the internet. The samples (**Open samples**) have an example of each kind in the chart guide (number 07 in the `guide` folder).
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
- The **document width** buttons next to them (narrower · Width 100% · wider) set how wide the body of a Markdown document is, from 80% to 200%, and finally **Full width** (the whole document pane). The text size stays the same; lines just get longer or shorter. Click the middle to reset; the width you pick is kept for next time. If the window is narrow and the pane is narrower than the document, it only widens up to the pane. Code views, slide decks and HTML documents with their own style are not affected.
- In tables, the header row and the leftmost column are not broken in the middle of a word (they wrap at spaces; if a long word would make the table overflow sideways, that table breaks words as before).
- When **the leftmost column of a table wraps onto more lines than the other columns** and makes rows tall, Lectern widens that column automatically. The extra width is taken only from the widest column, and nothing changes if widening would make the table taller. It is fitted again when you change the window or sidebar width, the text size or the document width (the file is not changed).
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

### Slide decks

Markdown with `marp: true` in the front matter shows as **slides** — the [Marp](https://marp.app) format Claude Code often uses for presentations. To try it, open the samples and the deck in the `guide` folder whose name starts with `08-`.

- Each `---` starts a slide, shown in a 16:9 frame. Mermaid, charts, math, code and tables are drawn as in any document, and colors and fonts follow the current style. Pick a slide in the contents on the right; with section focus on, ↑ and ↓ move one slide at a time.
- When a slide's content is too long, pictures, diagrams and charts shrink to the remaining height; if it still does not fit, the bottom is cut off and the frame is marked **Overflow**.
- Speaker notes (HTML comments `<!-- … -->` that are not directives) appear under the slide.
- **Present** in the status bar (Shift+F5), or the ▶ that appears when you point at a slide, shows one slide at a time in the whole window (full screen). Move with → ← Space, PageDown, PageUp, a click or the wheel; **N** shows speaker notes, **F** toggles full screen and **Esc** ends. When you end, the view returns to that slide.
- **View as document** in the status bar shows the deck as one ordinary document (press it again for slides).
- Printing or saving as PDF gives one slide per page (at slide size).
- Lectern reads Marp's `paginate`, `header`, `footer`, `class: lead` (centered), `invert` (dark slide) and background color, background pictures such as `![bg right:40%](picture)`, and the CSS in `style:`. `theme` (gaia and so on) is not read; slides use the Lectern style.

### Auto refresh

- While Claude writes a document, changes appear within a second and your reading position stays where it was.
- Changed paragraphs and tables are highlighted briefly. If the changes are off screen, the **changes** button in the status bar takes you through them.
- If a change was missed, press F5 to reload.

### Print and PDF

Right-click the margin of a document and choose **Print / Save as PDF**. To save a PDF, choose 'Microsoft Print to PDF' as the printer. Slide decks print one slide per page.

## Edit mode

Edit the document (Markdown or HTML) or code you are reading, right where it is.

- To open it: the **Edit** button at the right end of the tab bar (left of Contents and Terminal — press it again to close; it is highlighted and underlined while on), **Edit** in the status bar, **Edit** in the code view header, **Edit this document** or **Edit here** (at that block or line) in the right-click menu, or Ctrl+E. It opens with the source of what you were reading at the same height.
- **It stays in step with the reading position**: while you edit, the contents on the right marks the section the cursor is in (the section at the top of the screen if the cursor is off screen). Clicking a place in this file in the contents, the Elements tab or search results moves the editor to that line. When you close the editor, the document view is where you were editing (a folded section is unfolded). HTML documents follow by headings.
- It has line numbers and language colors; use Ctrl+F to find, Ctrl+H to replace and Alt+G to go to a line. Tab indents with spaces.
- **Ctrl+S** saves. The file's original line endings (CRLF/LF — the more common one if they are mixed), BOM and file attributes are kept. Read-only files are not saved. After saving, the document underneath is redrawn with your changes; close the editor with Esc (or ✕, Ctrl+E) to see it.
- If another program such as Claude Code changed the same file while you were editing, Lectern asks before overwriting it. Cancel to keep editing without saving.
- With unsaved edits, Lectern asks before closing the editor, going to another document, or closing the tab or window.
- Only UTF-8 text files up to 2 MB can be edited. The only file Lectern creates is a new Markdown document (see New document below), and files are renamed from the sidebar (see Files above); it does not delete files, and does not edit other files (PDF, Excel and so on).

### New document

- To start: **New document…** at the top of the quick open box that **+** in the document tab row opens, **Ctrl+N** (also while editing), or right-click a folder (or the project row at the top) in the tree, Code or Other files list and choose **New document in this folder…**.
- Type a path and press Enter — **it is created right away**. It starts as 'New document.md' in that folder (for Ctrl+N and +, the folder of the document you are viewing) with the name part selected, so you can just type over it. `.md` is added if missing.
- The file starts with one `# Title` line made from its name and opens in edit mode in a new document tab (the cursor below the title). Save with **Ctrl+S** when you have written something.
- It is created only in a folder that already exists and only if the name is free. If it cannot be created, the reason is shown — fix the path and press Enter again. Esc closes the box.
- The file stays even if you close it without saving (Lectern never deletes files — delete it in File Explorer if you do not need it).

## Reading code

- Click a file once in the 'Code' list (or press Enter) to show it in the main area with line numbers and language colors. It is never edited or run.
- The contents on the right list classes, functions, methods and divider comments such as `# ---- drawing ----`; click one to jump to that line. Config files list their keys and sections.
- The **Open in editor** and **Copy all** buttons sit at the top. Right-click a line for Copy line, Copy location for Claude and Open this line in the editor.
- When the code you are viewing changes, it is redrawn within two seconds and the changed lines are highlighted briefly.
- Clicking a path such as `src/app.py:42` or a link to a code file in a document jumps to that line. Go back (Alt+←) to return to the document.
- Files over 4 MB, or files that are not text, show a note to open them in an editor instead.

### CSV and text files

Click a `csv`, `tsv`, `txt` or `log` file once in the 'Other files' list (also in Recent, Search names and Elements) to view it in Lectern. Double-click opens it in the default app (Excel, Notepad) as before. Links in documents and paths such as `data/x.csv:5` also open in Lectern.

- **Text** (`txt`, `log`) shows like code, with line numbers.
- **CSV** (`csv`, `tsv`) shows as a table. The separator (comma, semicolon or tab) and the header row are detected; change the header with **First row is the header** in the bar.
- **Filter**: type in the box under a column header to keep only rows containing that text. `!text` excludes, `=text` matches exactly, and numbers take `>100`, `<=5` or `10..20`. Filters on several columns combine; **Clear filters** resets them.
- **Sort**: click a column header for ascending → descending → original order.
- **Stats**: a row above the table shows, per column — count, sum, mean, min, max and median for numbers; count, distinct values and the most common value for text. Filtering recounts them. The **Stats** button in the bar hides the row.
- Row numbers are the source line numbers. Right-click a row for Copy line (the source line) and Copy location for Claude.
- CSV files saved by Excel (CP949) and 'Unicode text' (UTF-16) are read too (the encoding shows in the status bar). Edit mode works only on UTF-8 files.
- Up to 2,000 rows are shown; filter to narrow down larger files (counts and stats use all rows).

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
- If you right-click with text selected, 'Copy selected text' and 'Clip selected text' appear at the top.
- **Clip** and **Send…** in block and heading menus send that piece to a document open in a document tab, or to a new one (see Clip above).
- The **terminal button** to the right of a copy item puts the same text into the terminal (Enter is not pressed). It is there for selected text, the location for Claude, the source, code, `@path`, the full path and so on, including in the right-click menus of the tree and the 'Code' and 'Other files' lists. See 'Terminal' below.

## Terminal

- The **Terminal** button at the right end of the tab bar, or Ctrl+\`, opens a terminal to the right of the main area. Windows PowerShell starts in the current tab's project folder, and each tab has its own shell.
- **Several terminals**: **+** in the terminal header opens another terminal for the same project (up to 5 per project — for example terminal 1 for Claude Code and terminal 2 for other commands). Click [1 PowerShell] [2 PowerShell] in the header to switch. Reloading the window keeps the running terminals.
- **Ending a terminal**: when you no longer need a terminal, click the × on its tab (or middle-click the tab). This ends its shell and the programs started from it, asking first if a program is running. It works even when there is only one terminal; ending the last one hides the panel, and opening it again starts a new shell as terminal 1. In a narrow panel, the other tabs get shorter names and their × appears when you point at them.
- The × at the right end of the header (or Ctrl+\`) only hides the panel — the shell keeps running, so reopening it continues where you left off. The ↻ button in its header restarts the shell.
- Keys typed in the terminal go to the shell. Use app shortcuts such as Ctrl+P, Ctrl+F or F1 after clicking the main area (Ctrl+Tab moves to the next tab even inside the terminal).
- Select text with the mouse, then press Ctrl+C or right-click to copy; press Ctrl+V or right-click to paste. With nothing selected, Ctrl+C stops the running command.
- Drag the edge to resize the terminal (double-click to reset).
- **Position**: in a wide window the terminal opens to the right of the document; in a tall window (a portrait monitor, a window snapped to half the screen and so on) it opens below the document. When it is below, drag the edge to change its height. The position button in the terminal header switches between right and below and keeps it there; set 'Terminal position' back to 'Auto' in Settings.
- **Paste into the terminal**: in a right-click menu, the **▣ Terminal** button on the right of a copy item puts that text into the current tab's terminal and shows a notice such as 'Put into terminal 1' (clicking the item name only copies). The terminal opens if needed. With several terminals the text always goes to the first one (the lowest number — usually terminal 1, the one opened first), which is then shown, so run Claude Code in terminal 1. Enter is not pressed — check the text and press Enter yourself. For several lines Lectern asks first, because at a PowerShell prompt each line may run as a command (programs that turn on paste mode, such as Claude Code, are not asked about).
- The terminal colors follow the document style. For an always-dark terminal, turn off 'Match terminal colors to style' in Settings.
- Closing a tab ends its shell. If a program started from the shell is still running, Lectern asks first. Closing Lectern ends all shells.
- **Stuck program warning**: if a program started from the shell gets stuck while starting (this happens when security software on a company PC, such as DRM, blocks programs from starting — Claude Code calls git and then stops responding to any input), a red strip appears under the terminal header after about 10 seconds and the ↻ button is highlighted. Ctrl+C does not end such a program, and often neither does Task Manager, so press **Restart** in the strip. It ends the shell and the stuck program and opens a new shell. In Claude Code, run `claude --continue` in the new shell to pick up the conversation. If the terminal belongs to a tab you are not looking at, a notice appears once.

### All terminals

- The **All terminals** button in the toolbar, or Ctrl+Shift+\`, gathers the terminals of all open projects on one screen in a grid.
- Each pane's header shows 'Running' or 'Idle', so you can watch Claude Code across several projects at a glance. A pane where a program got stuck while starting shows 'Stuck' in red — press that pane's ↻.
- Inside a pane, Ctrl+Tab moves to the next pane. Double-click a pane's header to maximize it.
- A pane's → button goes to that project and opens its right-hand terminal. Clicking a project tab returns to the documents.

## Working with Claude Code

1. Open the project folder you work on with Claude Code in Lectern.
2. Run `claude` in the terminal (Ctrl+\`) to work with Claude Code right next to your documents.
3. When Claude creates or edits a document, the change appears within a second, and changed documents you have not opened yet get an amber dot in the tree.
4. To ask about a document, right-click it in the tree, choose `Copy @path` and paste it into your prompt. For example: `@docs/report.md summarize the conclusion in three lines`
5. To point at one part of a document, right-click the text and choose **Copy location for Claude**.
6. To have Claude Code write documents that read well in Lectern, paste **Teach Claude Code about Lectern** → **Copy request for Claude Code** from the settings into Claude Code (the terminal button next to it pastes into the current tab's terminal). Claude Code reads Lectern's writing guide (`web/help/writing.en.md`) and adds the rules to that project's `CLAUDE.md`. The samples' `CLAUDE.en.md` shows the result.

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
| Teach Claude Code about Lectern | Copy, or paste into the terminal, a request to read the writing guide and add its rules to CLAUDE.md; open the samples |
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

- Lectern changes files only when you save in edit mode. The right-hand terminal, however, is an ordinary PowerShell, so commands typed there run as usual.
- The terminal needs Windows 10 (1809) or later. A shell's history is gone once Lectern closes.
- Document titles in the tree are read from the beginning of each document. If a document starts with a very long frontmatter, its file name is shown instead.
- Web images that cannot be loaded (blocked on a company network, or taking more than 15 seconds) turn into links.
