# Lectern User Guide

Lectern is a workspace for Markdown-centered research with AI. You read, review and fix in place the documents and data that Claude Code or Claude writes into a project folder. It shows Markdown (`.md`) and HTML (`.html`) documents in a readable layout, and shows code in a read-only code view.

- **Files change only when you choose.** Lectern never creates, edits or deletes documents on its own; it writes only its settings file and the files you choose to save, create or rename. Commands you type yourself in the right-hand terminal are also an exception.
- **It does not connect to the internet on its own.** Only web images inside documents are loaded, and you can turn that off in Settings.
- **It only looks inside the folder you open.** Hidden files and folders (`.git`, `.claude` and so on) are not shown. Excluded folders such as `node_modules` and `dist` stay out of the document tree and search, and appear dimmed only in the 'Other files' list.

> [!TIP]
> Press F1 to open and close this guide (Esc also closes it). Click an entry in the contents on the left to jump to it, and press Ctrl+F to search the guide. For just the keyboard shortcuts, click the **?** button in the toolbar or press Ctrl+/.

## Getting started

If you are new, press **Shift+F1** to open the sample project and follow its usage guide in order — [the first page of the samples](../../samples/README.en.md). Chapters of this guide link to matching samples with 'Sample —'; clicking one opens that document in the samples tab. The usage guide is in Korean.

### Opening a folder

- Click **+** in the tab bar (Ctrl+O) and choose a project folder; it opens in a new tab. If the folder is already open, Lectern switches to its tab.
- The arrow next to **+** lists recent folders and **Open samples**.
- **Open samples** (also on the start screen) opens a sample project with a tour of Lectern and how to write documents. It is set up like a research project done with Claude Code, so you can try the tree, code, files and charts right away. The samples live inside Lectern's program folder, so they are **view-only** — their tab has no terminal, edit mode, new documents or renaming (so that no commands run and no files change next to the program files). To try editing or Claude Code with them, copy the samples folder elsewhere (for example to Documents) and open the copy — 'Show this folder in Explorer' in the terminal area finds the folder.
- You can also right-click a folder in Explorer and choose **Open with Lectern**. If Lectern is already running, the folder opens as a tab in that window instead of a new window.
- When you start Lectern again, the tabs you had open come back, each at the document and position you were reading.

### The window

Sample — [guide 01, first look](../../samples/guide/01-처음-둘러보기.md): the window, the tree and folder overview, opening documents, going back.

| Area | What it does |
|---|---|
| Toolbar (top) | Sidebar, back, forward, **Quick open** (Ctrl+P), text size − 100% +, document width, **line numbers**, style, section focus, settings, **?** (keyboard shortcuts), all terminals |
| Tab bar | One tab per open project, open folder (+), and the **Contents** and **Terminal** buttons at the right end |
| Document tab row | Just above the document — the documents open in this project (up to 20), open a document in a new tab (+), the list of open document tabs (∨) and Spread all (▦) at the right end |
| Sidebar (left) | The **Files**, **Recent**, **Search**, **Elements** and **Clip** tabs. Drag its edge to resize (double-click to reset) |
| Main area (center) | Documents, folder overviews and the code view |
| Contents (right) | The current document's headings and elements such as tables and figures. When the terminal is open, it takes this place |
| Status bar (bottom) | Document path and modified time, the changes button, and the watching status |

## Project tabs

- Each folder gets its own tab (up to 10). Clicking a tab switches the sidebar and main area to that project, and every tab keeps its own document and scroll position.
- Clicking the tab that is already selected shows that project's overview. Right-clicking a tab also offers the project overview, a new document in the top folder and the project's Elements.
- When a document in a background tab changes, a dot appears next to the tab name.
- Folders with the same name also show their parent folder's name.
- To close a tab, click its ×, middle-click it, or press Ctrl+Shift+W. Right-click a tab for Close other tabs, Copy full path and Show in Explorer.
- To move between tabs: Ctrl+1~8 (tab by position), Ctrl+9 (last tab), Alt+PageDown / Alt+PageUp (next / previous tab).

## Document tabs

Keep up to 20 documents of a project open as tabs and switch between them. They appear in the document tab row just above the document.

- **Clicking a document in the sidebar opens it in a new document tab**, and the document you were reading stays open — the tree, the Code and Other files lists, folder view, Recent, search results, Elements and Open document (Ctrl+P) all work this way. If the current tab shows a folder overview, it opens there.
- **Ctrl+click** or **middle-click** opens a new document tab behind the current one (as in a browser — the tab is drawn when you click it). **Alt+click** opens in the current tab. In quick open, Enter, Ctrl+Enter and Alt+Enter do the same.
- Links and paths in a document open in the current tab (Alt+← comes back). Use Ctrl+click, the middle button or **Open in new tab** in the right-click menu for a new document tab.
- Clicking a document that is already open in another tab goes to that tab (a document is not opened twice).
- When all 20 are in use, the tab you looked at least recently is reused (tabs with unsaved edits are left alone).
- **Back and forward** (Alt+← →, the mouse back and forward buttons) also undo jumps within a document — after going somewhere from the contents, a section link, a footnote, find, Elements or search results, they return you to where you were reading (scroll and current line), unfolding the section if needed. However many find results you step through, one press returns to where you started. Moves by scrolling or ↑ ↓ are not recorded.
- Each tab keeps its own reading position, back/forward history and edit-mode changes. A tab with unsaved edits shows **●**. So you can edit a document in one tab while reading material in another, and Send from the Clip tab opens the receiving document in its own tab.
- To switch, click a tab or press **Alt+1~8** (by position) or **Alt+9** (last tab). When there are more tabs than fit, scroll the row with the mouse wheel or click **∨** at its right end (the number beside it is how many are open) and pick from the list of open document tabs. **Ctrl+Tab** and **Ctrl+Shift+Tab** (or Ctrl+PageDown, PageUp) go to the next and previous document tab. To close, click its ×, middle-click it or press **Ctrl+W** (or Ctrl+F4 — the last tab is not closed); **Ctrl+Shift+T** reopens a closed document tab. **Ctrl+T** opens a document in a new document tab. Right-click a tab for Close other document tabs and copying its path.
- The next time Lectern opens, your document tabs come back (when Settings → Start where I left off is on — only the selected tab is drawn at once, the others when you click them).

### Spread all

Click **▦** next to ∨ at the right end of the document tab row to spread this project's document tabs over the whole window as a grid — like All terminals. Click it again to go back.

- One cell per document tab (in tab order), and **the bottom-right cell is this project's terminal** — hand work to Claude Code and watch several documents change at a glance. If the terminal was closed it opens (starting a shell if there is none) and is hidden again when you end the spread (the shell keeps running).
- When the cells do not fill the grid, a document cell next to or above the gap widens to fill it. The sidebar and table of contents are hidden.
- Clicking a cell selects that document tab (highlighted border) — the status bar, Find in document (Ctrl+F), right-click menus and Alt+1~9 work on the selected cell. A document that changes is redrawn at once in whichever cell it is.
- **⤢** in a cell's header (or double-clicking the header) ends the spread showing only that document. The sidebar and contents buttons (Ctrl+B) also end it and show what you asked for.
- Selecting another project tab while spread spreads that project's document tabs. View-only projects (the samples) have no terminal cell.

### Separate windows

You can move a document into its own window and read side by side. With two monitors, keep the report on one and the source material on the other.

- Move: right-click a document tab and choose **Move to new window**, or press **Ctrl+Shift+N**. The tab leaves the original window and opens at the same position in the new one.
- Open and keep the tab: right-click a document in the sidebar or a link in the text and choose **Open in new window**.
- Send between windows: right-click a document tab in a separate window and choose **Send to main window**. When other separate windows are open, any window offers **Send to window: (document name)**. About a second later it opens in a new document tab at the same position, and that window comes to the front.
- Sending the last document out of a separate window closes that window.
- A separate window can hold several document tabs too. The sidebar starts hidden; press **Ctrl+B** to show it. **Ctrl+T** and **Ctrl+P** also open documents.
- A separate window belongs to its project. When you pick another project in the main window it hides, and it comes back with its tabs and scroll position when you return. Closing the project tab closes it.
- In a separate window, **Send to Claude**, the **Terminal** buttons and **Send to new note** go to the terminal and notes in the main window. Enter is not pressed, and the main window comes to the front. **Shift+→** sends while you stay in the separate window.
- Project tabs, the terminal, notes, settings and styles stay in the main window. A style changed in the main window applies when you reopen the separate window.
- Display changes such as text size apply to that window only and are not saved.
- Closing the last document tab with **Ctrl+W** closes the window. Closing the main window closes them all. Separate windows do not reopen on the next start.
- You can open up to 8 windows.

## Sidebar

### Files — documents, code and other files

The **Files** tab is split into three groups.

| Group | What it holds | Clicking |
|---|---|---|
| Documents | Markdown and HTML documents (a folder tree) | Click once to open in the main area |
| Code | Source (py, js, ts…), scripts (ps1, bat, EViews prg), web (css) and config (json, yaml, toml) | Click once for the code view, double-click for the editor |
| Other files | Anything that is neither a document nor code — PDF, Office, images, data, archives, programs and so on | Double-click to open in the default app (programs and archives are never run; they are only selected in Explorer) |

- Click a group header ('Documents 10', 'Code 3', 'Other files 4') to collapse that group. Drag the divider between groups to resize them, and double-click it to reset.
- The box at the top filters by name or title. Turn on **Titles** to show document titles instead of file names (when off, file names are shown and the title appears on hover).
- **Sort** picks the list order: by name, time or type. Folders always come first, then files. By time puts the newest on top, and a folder follows its newest file. By type goes by file extension.
- Turn on **Folders** to see everything in one tree that follows the real folder structure, instead of three groups.
- Documents that changed since you last looked get an amber dot.
- The 'Code' and 'Other files' lists work like Explorer: arrow keys (→ expand, ← collapse) and Enter, and typing a letter jumps to the item starting with it.
- **Excluded folders** such as `node_modules`, `dist`, `build`, `venv` and `__pycache__` appear dimmed and collapsed in 'Other files'. They can hold a great many files, so their contents are read when you expand them, and everything inside is listed there whatever its type (code still opens in the code view with one click). Changes inside are not followed automatically — collapse and expand the folder again, or press F5, to read it afresh. They are not counted in the group header or matched by the filter.
- Right-click menu: `Copy @path` (for pasting into a Claude Code prompt), Copy full path, Open in external editor, Show in Explorer, **Rename…**. Right-click a folder to collect the elements in just that folder.
- **Renaming**: right-click a file in the document tree, Code or Other files list (or in Recent and search results) and choose **Rename…**, or select its row and press **F2**. The current name is selected up to the extension — type the new name and press Enter (Esc leaves it as is). Only the name changes; the file stays in its folder.
  - If a file with that name exists or the name cannot be used (starting with a dot, containing `\ / : * ? " < > |` and so on), the reason is shown and nothing changes. Changing the extension asks once more.
  - A document tab showing the file follows the new name (and edit mode reopens if it was on), and so do the back history and clips. A file with unsaved edits must be saved or closed first.
  - Links to this document from other documents are not changed. Folders and files inside excluded folders are not renamed, and there is no move.
- **Deleting documents**: right-click a document in the document tree and choose **Delete document…**. Lectern always asks first and **sends it to the Recycle Bin**, where you can restore it. Code and other files are not deleted. Places without a Recycle Bin, such as network drives, are left alone with a message. Documents with unsaved edits are not deleted.

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
- **Send to a document…** (above the clips — all of them, in order) or **Send to a document…** in a right-click menu (just that piece) asks where: where you are editing (at the cursor), **New document…**, or **a document open in a document tab** → **At the end**, **At the beginning** or **End of section '…'**.
- Only documents open in document tabs and new documents can receive. To send to another document, open it in a document tab first (Ctrl+click it in the tree — see Document tabs above).
- The text goes straight into that document and is saved. One **Ctrl+Z** undoes it. If the receiving document is open in edit mode, it goes into the editor and you save with **Ctrl+S**.
- For **New document…**, type a path and press Enter: the document is created right away with a title line (see New document below) and the clips go to its end in a new document tab.
- When sending, Lectern rewrites relative paths of pictures, links and chart data for the receiving document, brings the footnote definitions along (renaming them if the names clash) and fits heading levels to the place (under the section for 'End of section'). Each piece gets a hidden `<!-- from: research/a.md lines 12-19 -->` comment, so Claude Code can tell where it came from.
- While another document is open in edit mode, **Send** on an item in the Clip tab puts it right after the block the cursor is in.
- **Ask Claude** makes a Claude Code request listing the clips' locations (`@doc lines 12-19 ('name')`) and asking for a new document from them — copy it or put it into the terminal with ▣ (Enter is not pressed).
- Lines in the code view and blocks of HTML documents cannot be clipped (they have no source lines), and clips can be sent only to Markdown documents.

## Reading documents

Sample — [guide 02, reading](../../samples/guide/02-읽기-기능.md): folding, section focus, text size and styles, find and search, gathered view.

### Folder overview

This is the first screen when a folder opens. It shows recently changed documents, subfolders, and each document's title, summary and modified time. Click a folder name in the tree to see that folder's overview.

### Document view

Samples — [guide 04, writing documents](../../samples/guide/04-문서-쓰는-법.md) (source and result of tables, callouts, footnotes, links and figures), [guide 05, math](../../samples/guide/05-수식.md), [guide 06, diagrams](../../samples/guide/06-다이어그램.md), [guide 07, charts](../../samples/guide/07-차트.md).

- Tables align number columns to the right, and the header row stays visible as you scroll.
- Code blocks are colored by language; the 'Copy' button at the top right copies them.
- Callouts (`> [!NOTE]` and so on — colored boxes without a title line), footnotes, checklists, math (`$…$`, `$$…$$`, and math/latex code blocks) and Mermaid diagrams are rendered. Dollar amounts such as `$105` are not turned into math.
- **Charts**: code blocks whose language is `vega-lite` (data charts), `echarts` (many chart types such as donuts and candlesticks), `plotly` (analysis charts such as box plots and sunbursts — the output of Python's `fig.to_json()` works too) or `dot`/`graphviz` (structure and dependency graphs) are drawn as pictures. Colors follow the document style; click to enlarge, and use 'Copy image' in the right-click menu to paste a PNG. Settings are JSON and functions are not allowed. Write the data in the document or point to a CSV/JSON file in the project with a relative path (internet addresses are not read). There is no hover or zoom, and Plotly map charts are not drawn because they need map data from the internet. The samples (**Open samples**) have an example of each kind in the chart guide (number 07 in the `guide` folder).
- A line you break with Enter inside a paragraph also breaks on screen (like Shift+Enter in Word — outline-style writing shows as written). Two spaces at the end of a line and `<br>` do the same. Turn this off in Settings to join lines as standard Markdown does.
- Click an image to enlarge it.
- Paths in the text that point to real files, such as `src/app.py:42`, become links.

### Contents

- Click an entry in the contents on the right to jump to that heading; the place you are reading is marked.
- Under each heading, the section's tables, figures, callouts, diagrams, code and math are listed like 'Table 1 · Price comparison · 6 × 4'. Click one to jump to it.
- The buttons at the top of the contents, such as 'Tables 2' or 'Code 5', hide that type from the contents; click again to show it.
- The **Contents** button at the right end of the tab bar shows or hides the contents.
- Drag the border between the document and the contents to resize the contents. Double-click it to reset.
- **Moving sections**: in an md document you can edit, drag a heading in the contents onto another heading to move that section — with its body and subsections — in front of it. Drop on the lower half of the last heading to move it to the end. Levels stay the same; Ctrl+Z undoes it.

### Folding sections

Click the arrow in the margin left of a heading to fold its section, and click it again to unfold (the arrow shows when the mouse is over the heading). From the keyboard, **Ctrl+Shift+[** folds the section with the current line and **Ctrl+Shift+]** unfolds it — if it is already folded, Ctrl+Shift+[ folds the outer section, and if it is open, Ctrl+Shift+] unfolds the folded sections inside. Clicking the heading text does not fold; it makes that line the current line. Right-click the text for Fold all at this level and Fold all / Unfold all. Folded sections are unfolded again when Lectern restarts.

### Text size and style

- The − / + buttons in the toolbar set the document text size from 80% to 200% (100% is already set slightly large for comfortable reading). Click '100%' in the middle to reset. To zoom the whole app, use Ctrl+Wheel.
- The **document width** buttons next to them (narrower · Width 100% · wider) set how wide the body of a Markdown document is, from 80% to 200%, and finally **Full width** (the whole document pane). The text size stays the same; lines just get longer or shorter. Click the middle to reset; the width you pick is kept for next time. If the window is narrow and the pane is narrower than the document, it only widens up to the pane. Code views, slide decks and HTML documents with their own style are not affected.
- In tables, the header row and the leftmost column are not broken in the middle of a word (they wrap at spaces; if a long word would make the table overflow sideways, that table breaks words as before).
- The **line numbers** button in the toolbar, or **Alt+L**, shows and hides source line numbers in the left margin of a Markdown document. They are the same lines as the `@path line 12` you send to Claude. Lines that do not appear on screen, such as blank ones, are skipped, and text that wraps on screen is numbered on its first line only. The code view always has numbers. Line numbers are not printed.
- When **the leftmost column of a table wraps onto more lines than the other columns** and makes rows tall, Lectern widens that column automatically. The extra width is taken only from the widest column, and nothing changes if widening would make the table taller. It is fitted again when you change the window or sidebar width, the text size or the document width (the file is not changed).
- The **Style** list has 24 styles; picking one changes the document and the toolbar and sidebar colors together. The ∧ ∨ buttons next to the list step through the styles so you can compare them. 'Auto' follows the Windows dark mode.
- How the style list is grouped (by use, by mood or by brightness) is chosen in Settings.

### My styles

- You can make styles of your own. Each CSS file is one style; put it in the `%APPDATA%\Lectern\styles` folder and it appears under **My styles** at the bottom of the style list.
- You do not have to write CSS yourself. Click **Copy request for Claude Code** in Settings, paste it into Claude Code, and add the look you want (for example 'navy headings, a dark navy table header with white text, serif body text'). The request gives the location of the style guide that comes with the app and the folder to save in, so the AI reads the guide and makes the file. The terminal button next to it puts the request straight into the terminal.
- While that style is selected, changes to its file are applied again within a few seconds — so you can keep asking ('make the headings larger') and see the result right away.
- **Open style folder** in Settings opens the folder. Deleting a file removes it from the list.
- Anything that would load fonts or images from the internet is removed by the app; only fonts installed on the PC are used.

### Current line

In Markdown documents and the code view (including csv and txt), lines are counted as lines of the source file — a paragraph, list item, heading or table row written on one line is one line, a paragraph wrapped over several lines goes line by line, and code goes line by line. So the `@path lines 12-20` sent to Claude matches what you picked on screen.

- **Current line**: the small triangle to the left of the line you are reading. Click or right-click the text to move it there; **↑ ↓** move it one line at a time and the view follows. If you scroll it off screen with the wheel or PageUp PageDown, it follows to the nearest line on screen. Going somewhere with the contents, Find or Search moves it there too. The status bar shows it as `Current line 12`, and each document tab keeps its own.
- **Send to Claude**: **Shift+→** puts the location of the current line (or of the picked lines), `@path lines 12-20`, into the first terminal (usually terminal 1, where Claude Code runs). Enter is not pressed and focus moves to the terminal, so you can type your request straight away. To add several places in a row, press **Ctrl+Shift+→** — focus stays in the document. **Shift+←** copies the location and **Ctrl+C** copies the source of those lines (if you dragged to select text, Ctrl+C copies that text).
- **Section focus**: the **Focus** button in the toolbar or **Alt+H** keeps the section with the current line sharp. ↑ ↓, PageUp PageDown or the ∧ ∨ buttons next to it move to the previous or next section. Click a dimmed area to move the focus there. Shift+↑ ↓ turn the section into picked lines. Press Esc or the button to turn it off, or right-click the text and choose 'Focus this section'. In documents without sections and in the code view, the button works like Shift+Enter.
- Picking and editing lines are described in 'Writing and editing documents'.

### Find in document

- Ctrl+F finds text in the document or code you are viewing, even across formatting such as bold or code.
- Enter goes to the next result, Shift+Enter to the previous one, and Esc closes the find bar.

### HTML documents

HTML reports written by Claude appear in the tree marked `HTML`. Their own styles are kept, while scripts and stylesheets from the internet are blocked (so charts drawn by scripts do not appear). HTML files inside app source folders such as `src`, `public` or `web` are not treated as documents.

### Auto refresh

- While Claude writes a document, changes appear within a second and your reading position stays where it was.
- Changed paragraphs and tables are highlighted briefly. If the changes are off screen, the **changes** button in the status bar takes you through them.
- If the text is unchanged, the screen is not redrawn, so your selection stays. While you drag to select text, the refresh waits until you release the mouse.
- When the text really changes, the screen is redrawn and the selection is cleared.
- If a change was missed, press F5 to reload.

### Print and PDF

Right-click the margin of a document and choose **Print / Save as PDF**. To save a PDF, choose 'Microsoft Print to PDF' as the printer. Slide decks print one slide per page. A **Page break** line from the insert window starts a new page, and a **Contents** line prints as a table of contents in its place (see 'Adding components').

## Writing and editing documents

Write and edit an md document from start to finish without opening the full editor.

Sample — [guide 08, line editing](../../samples/guide/08-한-줄-편집.md): picking lines and twenty cases to try.

**There is no separate save.** Enter in a cell, moving and deleting lines, changing line types and levels, table rows and columns, to-do checkboxes and pasted pictures are saved to the source file the moment you do them, and each one is undone with **Ctrl+Z**. A new line is saved when you write in it, and Esc in a cell drops your change. Lectern slides work the same way. Only the full editor saves with Ctrl+S. Moving the current line, picking lines, focus and folding do not change the file.

### Four states of a line

| State | What it is | Get there | Leave |
|---|---|---|---|
| **Current line** | The place — where you write and insert | Click, right-click, ↑ ↓ | — |
| **Picked lines** | The target — lines to delete, move or change. One line or many | **Insert**, **Ctrl+L**, **Shift+Enter**, Shift+↑ ↓, Shift+click or drag | Esc, ↑ ↓, a click elsewhere, opening a cell |
| **Focus** | A light over picked lines — dims the rest, view only | **Shift+Enter** on picked lines, the toolbar button | Shift+Enter, Esc, the toolbar button or a click on a dimmed area — back to the picked lines |
| **Cell** | A text box that edits the line right where it is | **F2**, double-click, Ctrl+Enter | Enter saves, Esc cancels |

- **The current line says where, picked lines say what.** New lines, pictures and elements go at the current line (below the last line when lines are picked); deleting, moving, line types and levels act on the picked lines.
- **Keys that change the file work only in a cell or on picked lines**: on the current line, Delete, Ctrl+X, Alt+↑ ↓, Ctrl+Alt+number and Alt+Shift+← → only show 'Pick lines first', so reading never changes the file. Keys that do not change the file — copy, copy location, send to the terminal — act on the current line when no lines are picked.
- **Writing ends picking**: opening a cell releases the picked lines. F2 with several lines picked opens the current position (the last line).
- **Grow and shrink**: **Shift+↑ ↓** move the last picked line up or down — the first line stays, so the range grows or shrinks. Without picked lines they pick two lines from the current line. Insert and Ctrl+L extend downward when pressed again, and Shift+click extends picked lines to that line. While lines are picked, the status bar shows `Picked lines 3-5 · 3 lines`.
- **Focus is view only**: while it is on, the keys for picked lines, copying, sending and opening a cell do nothing, ↑ ↓ just scroll, and the right-click menu only turns it off. Turn it off to edit.
- **Right-click**: the line you right-click becomes the current line. Inside picked lines, right-clicking opens a selection box for that range — what only that block can do (such as Copy table), **Send to Claude**, copying, Clip and Send, **Insert below…**, **Change picked lines…**, Edit here (for one line), release, and Delete lines at the bottom. Right-clicking outside them releases them and opens that line's menu. Hover over an item for its description.

### New document

- To start: **Create** in the **Documents** header of the sidebar, **Ctrl+N**, **+** in the document tab row, or right-click a document, folder or empty space in the tree and choose **New document…**. It starts in that folder; Ctrl+N and **Create** start in the folder of the document or overview you are viewing.
- The **title** becomes the file name and starts as 'New document'. The most recent **style** is selected; change it with ↑ ↓. Choose **Lectern slides** to pick a template for the first slide.
- In **Location**, choose the top of the project or another folder, including empty ones. **New folder…** creates a folder inside the chosen location and selects it. **New folder…** in the right-click menus of the tree and project tab does the same. Empty folders do not show in the tree, so the new document box opens right away.
- It starts with one `# Title` line, and a cell opens under the title in a new tab so you can write right away. A numbered style adds two sample headings with the first one selected, so typing changes the text and keeps the number.
- It is created only if the name is free. If not, the reason is shown — change the title. Esc closes the box.
- The file stays even if you close it before writing. If you do not need it, right-click it in the tree and choose **Delete document…**.

### Line editing

You can edit a line right where it is. Press **F2** on the current line, or **double-click** the body to open that line with the cursor where you clicked. A heading keeps its heading size, a list item its bullet and a callout its box; markers such as `#`, `-`, `>`, `1.` and `[ ]` are locked so only the text changes. Inline formatting shows as source text, such as `**bold**` or `[link](url)`.

- **Enter** saves straight into the source file and **Esc** cancels. Clicking outside saves if you changed something. After saving, the view is redrawn and the change briefly highlighted.
- **↑ ↓** save and go on editing the line above or below. In text that wraps on screen they move inside it first, and go on from its top or bottom screen line. At the end of the line, **Shift+→** saves and puts the line's location into Claude Code in the terminal.
- **Tables**: press F2 on a row or double-click a cell to edit it cell by cell. **Tab** and Shift+Tab move between cells — Tab in the last cell of a row goes to the first cell of the next row and Shift+Tab in the first cell to the last cell of the row above, so you can fill a table row by row. ↑ ↓ go to the same cell in the row above or below. A `|` typed into a cell is saved as `\|` so the cell is not split.
- In a paragraph wrapped over several source lines only that line is edited; code blocks and the code view edit that line. F2 on a picture opens its source line. F2 on math, diagrams and charts opens the source to edit line by line. HTML and comments are edited in **Source lines** from the status bar. Data files like CSV, text and Excel are view only.
- Links, pictures, diagrams, charts and math do not open on a double-click, and a triple-click still selects the paragraph. To copy a word, double-click it again inside the box — clicking outside without changing anything ends without saving.
- Editing during section focus lifts the grey shading so the lines above and below read normally; it returns when you finish.
- **To-dos**: click a checkbox in the body to switch `[ ]` and `[x]` in the source and save it straight away. Nothing changes in view-only projects such as the samples.
- After saving, **Ctrl+Z** restores the line as it was and saves again; press it again for earlier edits. **Ctrl+Y** redoes what you undid. Undo is kept per file, so you can go back to a document and undo there after editing another one. Editing again after an undo clears the redo.

### Adding, moving and deleting lines

Change the structure in a cell or on picked lines. Any text you changed in a cell is saved first, so undoing takes two steps. If something can't be done, nothing changes and a message says why.

- **New line**: **Ctrl+Enter** opens a new line below, **Ctrl+Shift+Enter** above. The same keys work on the current line without opening a cell, and with lines picked they open below the last line or above the first. It takes after the line it came from: the same marker in a list (after any sub-items), the next number in a numbered list, a paragraph under a paragraph or heading. In a table it is a new row, around a chart or math a paragraph. The file does not change until you write something.
- **Keep writing**: on the last line, **↓** moves the arrow down and opens a new line. On a new line, **Enter** saves and opens the next new line; on an empty one it stops. On an existing line, Enter saves and closes. After a table or code block at the end, a paragraph opens. With footnotes, ↓ on the last line of the body opens a new line instead of going into the notes, and new text goes before the notes.
- **Ending a list**: on an empty new item, **↓** or **Shift+Tab** moves out a level, and at the outermost level it becomes a paragraph and the list ends. **Tab** nests it under the item above.
- **Split and join**: **Ctrl+Enter** in the middle of the text splits the line there. **Backspace** at the start of a line joins it to the end of the line above — paragraphs with paragraphs, list items with list items, code within its block. Lines of different kinds, such as a heading and a paragraph, are not joined.
- **Move**: **Alt+↑ ↓** move lines. List items move with their sub-items within the same list, paragraphs swap with the block next to them, one line of a paragraph written over several lines stays inside that paragraph, code stays in its block, and table rows stay below the header. The picked lines follow, so you can keep moving them. The notes at the end of the document and the body never cross each other.
- **Delete**: pick lines and press **Delete** (or right-click 'Delete lines'); in a cell, **Ctrl+Shift+K**. **Ctrl+X** copies the source and deletes. You are asked first if it is more than 10 lines or includes a heading. Doubled blank lines left behind become one, and sub-items left behind move up to the deleted item's place.
- Deleting only a table's header or divider row would break the table, so it is blocked (pick the whole table to delete it). Deleting part of a code block together with lines outside it is blocked too; picking every code line deletes the block.
- **Duplicate**: **Ctrl+Shift+D** in a cell adds the same line below and goes on editing the copy. Table rows are not duplicated.
- Numbered lists are renumbered when you add, move or delete. A list written with `1.` throughout stays as it is. One **Ctrl+Z** brings the numbers back too.
- All of this also works in the code view and in slides. It is not available in HTML documents, data files (CSV, text, Excel) and view-only projects.
- Files that are not UTF-8 are view-only. Files in the Windows encoding, such as EViews programs (`prg`), show Korean correctly in the code view and in search, but line editing and edit mode don't change them. A `prg` written only in English can be edited; adding Korean to it is not saved, because the file would turn into UTF-8 and EViews would show broken characters.

### Line types and heading levels

Markers (`#`, `-`, `>`) are locked, so you change them with keys and menus. The keys work in a cell or on picked lines.

- **Ctrl+Alt+1–6** turn a line into a heading and **Ctrl+Alt+0** into a paragraph. Right-click **Change this line…** for lists, numbered lists, to-dos, quotes and callouts.
- **Alt+Shift+← →** change the level. Headings take their subsections along and lists take their sub-items. On list lines **Tab** and **Shift+Tab** do the same. **Tab** does not change headings.
- With several lines picked, the same keys change all of them at once. To turn several paragraphs into one list or callout, right-click **Change picked lines…**.
- **Numbered headings**: if the document numbers its headings, adding, moving or deleting a heading renumbers them. One **Ctrl+Z** brings the numbers back too, and links to sections in this document follow. The number is locked in the cell. Sections such as `References`, `Appendix`, `Attachments` and `Summary` get no number.
- **Sections**: pick a heading line and press **Alt+↑ ↓** to swap the section with the one before or after it, text included. Right-click a heading and choose **Delete section** to delete it with its text and subsections. Moving or deleting the last section leaves the notes at the end of the document in place.

### Inserting elements

On an empty line, press **/** to open the insert box. Type to filter. On a line with text use **Ctrl+Shift+/**; with the mouse, right-click **Insert here…** — on a table it inserts below the table, and on picked lines **Insert below…** inserts below the last line.

- **Text**: headings, paragraph, list, numbered list, to-do, quote. They reach the file when you write something. Typing `## ` or `- ` works too.
- **Table**: give the size like `3x4` (columns x rows). A `Table 1. Title` caption comes with the next number, with 'Title' selected so you can type it. Press ↓ to go into the table and fill cells with **Tab**. Tab in the last cell and **Ctrl+Enter** add a row, **Ctrl+Shift+Enter** adds one above. Right-click a cell to add, delete, move or align columns.
- **Callouts**: note, tip, important, warning, caution. On an empty new line, **↓** leaves the callout. Right-click to change the type, remove the callout or delete it.
- **Notes**: **Ctrl+Alt+F** in the middle of text adds a mark there and asks for the note. The mark and the note are saved together. On a mark, the same key edits that note. Numbers follow the order of appearance and the notes gather at the end of the document. If you delete a mark, Lectern asks whether to delete the note too.
- **Figures**: pick an image file from the project; a `Figure 1. Title` caption comes with it. Copy a picture and paste it with **Ctrl+V**, or drag it in, and it is saved as a PNG in the `name-images` folder next to the document (after the current line, or below the last picked line). Nothing is overwritten.
- **Math, diagrams, charts**: insert a sample and a panel opens beside the document. For existing ones press **F2**. Edit math and diagrams line by line; charts with their values in the document show a table. The result stays in place. Press **Esc** to fold it.
- **Source line, table note**: opens a line starting with `Source: ` or `Note: `. Such lines right under a table show in small type.
- **Links**: **Ctrl+K** picks a project file or takes an address. If text is selected, the link goes on that text.
- **Attachments**: pick a project file and it is added with a number and a link to the `## Attachments` section at the end (before the notes), which is created if needed. The file is not copied.
- **Appendix**: adds `## Appendix A. Title` with the next letter. It stays out of the body numbering.
- **Cross-reference**: pick a table or figure caption, or a section, to insert a link like `[Table 3](#table-3)`. Clicking it jumps there. In the middle of a sentence, open it with **Ctrl+Shift+/**.
- **Citation**: pick a source from the list under `## References` (or the Korean heading for references) to insert `(Kim & Lee, 2024)`. The window shows how often each source is cited and how many are not cited yet. Ask Claude to format the list (APA and so on).
- **Contents, list of tables, list of figures**: a `[TOC]` line draws a table of contents of the headings in its place (without the document title, three levels deep). The lists of tables and figures collect numbered captions. They are for printing and PDF; the contents on the right stays as it is.
- **Page break**: shows as a dashed line with 'Page break' on screen and starts a new page when printed. Other viewers don't show it.

**Caption numbers**: in a document whose table or figure captions are numbered 1, 2, 3… in order, adding, moving or deleting a table or figure renumbers them and fixes the cross-reference links to them. It is one save, so one Ctrl+Z undoes it. Plain text like 'Table 3' that is not a link may point to another document, so it is left as is and Lectern tells you how many there are — check them with Ctrl+F. A single caption number you changed by hand and chapter-style captions like 'Table 2-1' are left alone.
- **Document info**: right-click the info at the top and choose **Edit document info**. Keys are locked and you edit the values.

### Formatting and pasting

- In a cell, **Ctrl+B** is bold, **Ctrl+I** italic and **Ctrl+\`** code. They wrap the selected text in `**`, `*` or `` ` ``.
- Pasting several lines puts them on separate lines. In a list they become items. One undo brings it back.
- Pasting an Excel range makes a table.

### Editing alongside Claude

While Claude Code edits the same document, your changes and Claude's do not overwrite each other.

- **Text in a cell** is not lost when the file changes meanwhile. If lines were added above so only the line number moved, Lectern finds the same line and saves there. If that line itself changed, or the same line appears more than once, it is not saved; your edited line is copied to the clipboard instead.
- **Picked lines** follow their text. If lines are added above, the same text stays picked; if that text changes or disappears, the lines are released — so another line is never deleted by mistake.
- **Undo**: if the file has changed meanwhile, Ctrl+Z does not undo and tells you so, so it does not overwrite someone else's changes.
- The screen is redrawn within a second and your reading position stays (see Auto refresh).

### Source lines

**Source lines** in the status bar shows the md document as a code view with line numbers. Every line can be edited in a cell, including blank lines, comments and HTML. **View as md document** comes back.

### md document style

Open it from **md document style** in the status bar or the right-click menu. Pick a **document type** and a **heading shape**.

- The **document type** is how the body is written: prose in sentences, outline in short items. The current type is read from the body.
- The **heading shape** is the numbers and symbols. A preview appears, and applying it really changes the heading lines in the md file.

| Type | Heading shape | Level 1 | Level 2 | Level 3 |
|---|---|---|---|---|
| Prose | No numbers (articles, columns) | Overview | Market | Prices |
| Prose | Paper (humanities, social science) | Ⅰ. Overview | 1. Market | 1) Prices |
| Prose | Numbers (science papers, technical docs) | 1. Overview | 1.1 Market | 1.1.1 Prices |
| Prose | Chapters (theses, books) | <span translate="no">제1장</span> Overview | <span translate="no">제1절</span> Market | 1. Prices |
| Prose | Rules (regulations, guidelines) | <span translate="no">제1장</span> Overview | <span translate="no">제1조</span> Market | ① Prices |
| Outline | Report (reports) | Ⅰ. Overview | 1. Market | <span translate="no">가.</span> Prices |
| Outline | Numbers (plans) | 1. Overview | 1.1 Market | 1.1.1 Prices |
| Outline | Symbols (official notices, summaries) | □ Overview | ○ Market | - Prices |
| Outline | No numbers (minutes, memos) | Overview | Market | Prices |

- Heading shapes within a type change straight away. Ctrl+Z undoes it.
- **Changing the document type always asks first**, because Lectern changes the headings but the body takes judgment. **Headings, and ask Claude about the body** puts a request in the terminal and you press Enter yourself. **Headings only** leaves the body as it is, so the type does not change.
- The document title (a single `#`) gets no number. Body text and code blocks stay as they are.
- Existing numbers are removed and counted again. A number in a title like `2026 outlook` is not treated as numbering.
- Section links inside this document are updated too. Links from other documents to this section stay as they are.
- **Make a style from this document:** In a document with numbered headings, this saves the numbering as **My styles**, under the type you are looking at (prose or outline), shared by all of Lectern. The files are in `%APPDATA%\Lectern\md-styles`; **Open styles folder** opens it so you can delete them.
- If the numbering is too complex to pick up, use **Ask Claude for a style**. A request goes into the terminal; add a name and press Enter, and Claude makes it from the document.
- With many styles, type a name, a use (`paper`) or a number form in the search box. Styles you used lately come first.

### Full editor (edit mode)

For what line editing does not cover — reworking many places at once or editing an HTML document — open the whole file in the editor. Most work is done with line editing above.

- To open it: the **Edit** button at the right end of the tab bar (left of Contents and Terminal — press it again to close; it is highlighted and underlined while on), **Edit** in the status bar, **Edit** in the code view header, **Edit this document** or **Edit here** (at that block or line) in the right-click menu, or Ctrl+E. It opens with the source of what you were reading at the same height.
- **It stays in step with the reading position**: while you edit, the contents on the right marks the section the cursor is in (the section at the top of the screen if the cursor is off screen). Clicking a place in this file in the contents, the Elements tab or search results moves the editor to that line. When you close the editor, the document view is where you were editing (a folded section is unfolded). HTML documents follow by headings.
- It has line numbers and language colors; use Ctrl+F to find, Ctrl+H to replace, Ctrl+G to go to a line, and F3 / Shift+F3 to find next and previous. Tab indents with spaces.
- **Ctrl+S** saves. The file's original line endings (CRLF/LF — the more common one if they are mixed), BOM and file attributes are kept. Read-only files are not saved. After saving, the document underneath is redrawn with your changes; close the editor with Esc (or ✕, Ctrl+E) to see it.
- If another program such as Claude Code changed the same file while you were editing, Lectern asks before overwriting it. Cancel to keep editing without saving.
- With unsaved edits, Lectern asks before closing the editor, going to another document, or closing the tab or window.
- Only UTF-8 text files up to 2 MB can be edited. The only file Lectern creates is a new Markdown document (see New document above), and files are renamed from the sidebar (see Files above). It does not edit other files (PDF, Excel and so on).
- Choose **vi** under **Full editor keys** in Settings to use the editor like vim. Esc goes to Normal mode instead of closing the editor; `:w` saves, `:q` closes, `:wq` and `:x` save and close. Ctrl+E and ✕ also close it. The default is **Default**, and it is set separately from the vi keys for reading (below). Normal-mode keys may type characters while Korean input is on, so switch to English there.

### vi keys

Turn on **vi keys** in Settings (Ctrl+,) to move and edit documents with letter keys. They are off by default; when on, `vi` shows in the status bar. The line states match vi's modes — the current line is Normal, picked lines are Visual (V), and a cell is Insert. The mouse and the usual keys keep working.

- **Moving**: `j`·`k` line below / above, `gg`·`G` first / last line, `[[`·`]]` previous / next heading, `zz` center the current line. Type a number first to repeat (`3j`, `12G` goes to line 12).
- **Folding and finding**: `zc`·`zo`·`za` fold / unfold / toggle the section, `zM`·`zR` fold / unfold all, `/` find, `n`·`N` next / previous, `:` go to line.
- **Writing**: `i`·`a` open the cell (caret at the start / end of the line), `o`·`O` new line below / above. In a cell, **Esc** saves and leaves (with vi keys off, Esc cancels).
- **Picking and changing**: `V` picks the current line and `j`·`k` extend it. On picked lines, `d` deletes, `y` copies the source, `>`·`<` change the level, `J` joins them into one line, `V` or Esc releases.
- **In one go**: `dd` deletes the line, `yy` copies its source, `>>`·`<<` change its level — the same as picking it first. Lines you deleted or copied go back with `p`·`P` below / above the current line (they are kept inside the app, separate from the clipboard). `u` undoes; redo is Ctrl+Y.
- Two-letter commands wait one second for the next letter; meanwhile the status bar shows `vi d…`.
- Keys with Ctrl are not changed (Ctrl+D still duplicates a slide, Ctrl+F still finds). Page with PageUp and PageDown.
- They work whether the keyboard is in Korean or English mode.
- The full editor is set separately — **Full editor keys** in Settings (see 'Full editor' above).
- Sample — [guide 10, vi keys](../../samples/guide/10-vi-키.md): practice steps, a side-by-side key table, and the vi mode of the full editor.

## Lectern slides

Samples — [guide 09, Lectern slides](../../samples/guide/09-Lectern-슬라이드.md) (this chapter written out as a detailed md document) and [the slide samples](../../samples/slides/README.en.md) (basics, by situation, complex layouts).

Lectern tells three things apart.

| Term | What it is |
|---|---|
| **md document** | An ordinary Markdown document |
| **Lectern slides** | Markdown with `marp: true` in the front matter. It shows as slides with a different layout on each one, and has an orange icon in the sidebar |
| **pptx** | A PowerPoint file |

The work goes in this order.

1. In **New**, pick a template to make the first slide.
2. Replace the placeholder text, and press **Ctrl+M** to pick the next slide's template.
3. Present, or pick a pptx style and **Convert to pptx**.

### Creating

- In **New document** (Ctrl+N), write a title and choose **Lectern slides** as the type. Pick the first slide in the template gallery and the document is made.
- For an existing md document, right-click it in the sidebar and pick **Ask Claude to make Lectern slides**. A request goes into the terminal; press Enter and Claude makes a new file in the same folder.
- Moving a pptx into Lectern slides is in [Asking Claude](#asking-claude).

### Templates

A template is a slide skeleton with a title, text, boxes and chart spots. All of Lectern shares them, not one project. One Lectern slides file is a **set**, and each slide in it is a template.

- **Gallery:** Preview and pick a template. Pick a set on the left (PageUp and PageDown), then click, type a number, or move with the arrows and press Enter. Numbers follow the slide order in the set. Type letters to search all sets. Templates you used lately collect in **Recently used**. The basic set has twelve templates.
- **New slide:** **Ctrl+M** opens the gallery and puts the template after this slide. The title opens for typing.
- **Change template:** Right-click a slide and pick **Change template…**. Your text moves into the new cells, and text that does not fit stays in the last cell. Placeholder text you did not change does not move. Ctrl+Z undoes it.
- **Your own templates:** Right-click a slide, pick **Save this slide as a template…** and type a name. It joins the **My templates** set. The slide's text is saved as it is, so you may want to turn it into placeholder text.
- **Editing sets:** **Open templates folder** in the gallery opens the folder (`%APPDATA%\Lectern\templates`) in a Lectern tab. Edit sets as usual with line editing and Check. Slide order is the number, and the name is `<!-- template: name -->`.
- **Asking Claude:** **Ask Claude for a template** puts a request in the terminal. Add what you want and press Enter.
- **Remembering the set:** A document started from your own set gets `templates: Company report` in the front matter, and that set opens first for the next slide.

A slide saved with a picture keeps the picture's path. A document in another folder may not find the picture.

### Writing and managing slides

- Edit text on a slide with **line editing**. A line added with Ctrl+Enter at the end of a cell stays in the cell, and moving or deleting lines does not break cells or slides.
- **Sample text**: opening a template's sample text selects all of it, so typing replaces it.
- **Insert**: on an empty line in a cell, press **/** for headings, lists, callouts, tables, figures, charts, diagrams, math, code, a source line or a speaker note. Notes, attachments, appendices and dividers are not used on slides.
- **Formatting and pasting**: Ctrl+B, I, K and \`, pasting lines and Excel ranges, table rows and columns, and the callout menu work as in md documents and stay in the cell. Pasted pictures go in the cell, and **Ctrl+Shift+> <** change their width.
- **Source**: **F2** on math and diagrams opens a panel beside the slide to edit line by line. The cell keeps showing the result and it updates on each save. **Esc** folds it.
- **Chart values**: **F2** on a chart shows its values as a table. Edit cell by cell, add a row with **Ctrl+Enter** and delete one with **Ctrl+Shift+K**. The buttons below change it to bar, line, area or pie. Charts that read a file or are complex open as source.
- **Table to chart**: right-click a table and choose **Turn this table into a chart**. The first column is the item, the next columns are values. These charts become PowerPoint charts in pptx, where the values can be edited too.
- **Cells**: right-click the text of a cell for **Cell look…** (box, accent, note and so on), **Move this cell back / forward** (swaps the text) and **Empty this cell**.
- **When text overflows**: right-click the cell for **Move overflow to a new slide** (a new slide with the same layout) and **Ask to shorten this cell** (a request in the terminal). Lectern never shrinks text on its own.
- **Speaker notes**: right-click **Write speaker note…**. It goes in as a comment line at the end of the slide and becomes the pptx notes.
- Right-click a slide to add, duplicate, move or delete it. The keys are Ctrl+M, Ctrl+D, Ctrl+Shift+PageUp and PageDown. **Alt+↑ ↓** on the slide title also move the slide. Ctrl+Z undoes them all.
- The right panel is a slide list. Slides to check are marked.
- Pressing a checkbox on a slide changes `[ ]` or `[x]` in the source. It does nothing during a presentation.
- A slide with `<!-- hidden: true -->` is hidden. It shows faded on screen and is left out of presentations and PDF.

### Cells and layouts

When the templates are not enough, build the cells yourself.

- Each `---` starts a slide. The size is 1280×720.
- `::: a card` to `:::` is a cell. Put text, tables, charts and pictures in cells.
- Pick a layout like `<!-- layout: quad -->` or draw one with `<!-- grid: a a b / c d b -->`. `::: a at 100 200 300 120` places a cell directly.
- Right-click a slide and pick **Insert layout…** to add that layout's empty cells. Existing cells only get new names, and text on a slide with no cells goes into the first cell. Fill them with F2.
- `<!-- links: a>b, c--d -->` draws arrows and lines between cells. The text in the cells stays editable.
- Lectern reads Marp's `paginate`, `header`, `footer`, `class: lead`, `invert`, background color, background images like `![bg right:40%](image)` and their filters, and CSS in `style:` and `<style scoped>`. It does not read `theme` (gaia and so on).

### Text size

- On the current line, **Ctrl+Shift+>** and **Ctrl+Shift+<** change that slide's tables, boxes, titles and so on by 1pt. A line like `<!-- text: table 14 -->` appears in the source, and Ctrl+Z brings it back.
- In a cell with its own size (`::: b 16`) the cell's size changes. Set the whole document with `text: title 26, table 12` in the front matter.
- The defaults are title 30, subtitle 20, body 18, table 14, box 16. Changing style keeps these sizes. Text inside charts and diagrams follows the cell size.
- Tables below 12pt and body text below 14pt show up in Check. For slides that are read rather than shown, write `reading: true` in the front matter (limits 10pt and 12pt).

### Structure and Check

- **Structure** in the status bar shows cell head lines and directive and note lines as tags. Press F2 on a tag or double-click it to edit that line. This is how to change a cell's look or the layout.
- When content overflows, pictures and charts shrink to fit the cell. Text does not shrink; it is cut off and gets a red dotted line.
- Grammar slips are marked too: cell names, a missing `:::`, typos in directives and words, bad grids, unclosed comments and code blocks, text right above `---`, and unresolved `**`.
- Some things are measured on screen: text close to its background, code and tables cut off at the side, missing pictures, charts that could not be drawn. Text over a photo cannot be measured, so look at it yourself.
- **Check** in the status bar lists them, and picking one goes to that line. **Paste the list into the terminal** lets you ask Claude to fix them.

### Viewing and presenting

- Clicking Lectern slides opens a separate slide window. If it is already open, it comes to the front. The terminal is the main window's.
- The slide window has its own style, **Presentation** by default. This style is how the slides look on screen. It does not change the pptx style.
- **Present** in the status bar (Shift+F5) or ▶ on a slide shows one slide at a time across the window. Use → ← Space PageDown PageUp, click or the wheel; **N** shows speaker notes, **F** full screen, **Esc** ends.
- **View as document** in the status bar opens the cells and reads on like an ordinary document.
- Printing or saving as PDF gives one slide per page in the screen's colors. Speaker notes are left out.

### Convert to pptx

Press **Convert to pptx** in the status bar and pick a pptx style. A pptx file appears next to the document. You do not need Claude or Python.

- **pptx styles:** Shared by all of Lectern. **Open library folder** opens the folder (`%APPDATA%\Lectern\pptx-styles`); put your company's pptx there and it shows in the list. With **Ask Claude for a style**, add the pptx path and Claude makes the style, a template set of the same name and preview pictures.
- **Pairs:** A template set and a pptx style with the same name are a pair. A document made from the 'Company report' set picks the 'Company report' style first.
- **Memory:** The style's name goes into the front matter as `pptxStyle: Company report`, and that style comes first next time. If you move only the document to another PC, the style may be missing; Lectern tells you and you pick again.
- **Default style:** Turn on **Make this the default** when converting, and documents with no style use it.
- **Order:** The style picked now, the document's style (including its pair), the original pptx, the default style, then the Lectern style.
- **The model's content:** Slides and pictures of the model pptx do not go into the result. Its slide titles and cover thumbnail are removed from the file properties too. A logo and footer in the layouts are part of the style, so they stay.
- **Result:** Cell positions follow the Lectern slides; colors, fonts, logo and footer follow the pptx style. Text stays text, tables stay tables, charts stay charts you can edit, and lines become connectors. Complex charts and Mermaid become pictures.
- **Documents moved from a pptx:** If you pick no style, slides you did not change reuse the original slide, and where you only edited text, just that text changes in the original slide. Design and animations stay. Only slides whose cells or layout changed are rebuilt. Keep the conversion record (the `.json` file next to the document) and the `.pptx-work` folder for that.
- A pptx of the same name is never overwritten. A new name like `Report 2.pptx` is used.

### Asking Claude

Sample — section 12 of [guide 09, Lectern slides](../../samples/guide/09-Lectern-슬라이드.md), 'Working with Claude Code': installing the skills, example requests, the request menus and the order of polishing together.

Claude Code skills move a pptx into Lectern slides and build slides from a pptx. They come with Lectern and are installed only when you ask. In Settings, under **PowerPoint skills**, use **Copy request for Claude Code** (or the terminal button next to it). Claude explains the skills and asks before installing.

Lectern does not run Claude. You talk to Claude Code in the terminal yourself. Here is how to ask. `@document.md` is **Copy @path** from a right-click in the tree.

**pptx to Lectern slides**

```text
Move this pptx into Lectern slides: D:\project\report.pptx
Move the presentation open in PowerPoint into Lectern slides. Put the result in D:\project\slides.
Quickly pull D:\project\report.pptx into md for now. I'll polish it later.
```

**An md document into Lectern slides, using a pptx as a model**

```text
Use D:\templates\company.pptx as a model and make @market.md into Lectern slides.
Use the pptx open on screen as a model and make @market.md into Lectern slides.
Use only the colors and cover of D:\templates\company.pptx and make @weekly.md into at most 10 Lectern slides. Keep the numbers.
```

**Making pptx styles and templates**

```text
Make a 'Company report' pptx style and template set from D:\templates\company.pptx.
Add the presentation open in PowerPoint as the 'Company report' pptx style.
Add a template with a table and a box to the 'Company report' set.
```

**Lectern slides to pptx**

```text
Make @deck.md into a pptx, keeping the style as much as you can.
I edited @report.md, which came from a pptx. Make the pptx again with just my changes.
Make @deck.md into a pptx using D:\templates\company.pptx.
```

- Moving keeps all the text and every slide. Text-centered slides are rebuilt as cells, and diagrams where position matters stay as pictures with their text in the notes. Animations and exact fonts are not moved.
- The original pptx is not changed. An open presentation is not saved or closed.
- You do not need to install Python. The skills run on `lectern-skill.exe` in the program folder.
- `.pptx` files can be moved and exported without PowerPoint. An open presentation, `.ppt` files and DRM files need PowerPoint.
- Remove the password from a protected file first. For a DRM file, open it in PowerPoint and move it from there.

More examples are in `skills\README.md` in the program folder. The guide Claude reads is `web/help/slides.en.md` there.

### Samples

[slides/README.md](../../samples/slides/README.md) in the project opened by **Open samples** (Shift+F1) is the way in ([slides/README.en.md](../../samples/slides/README.en.md) in English). If you are new to slides, read [guide 09](../../samples/guide/09-Lectern-슬라이드.md) before it (in Korean) — the content of the slide samples written out as a detailed plain md document, ending with links to the samples. Then go through them in this order.

| Order | Folder | What |
|---|---|---|
| 1 | <code translate="no">slides/기초/</code> | First look, cells and layouts, making slides from templates, key practice |
| 2 | <code translate="no">slides/상황별/</code> | Ten model decks for situations like an executive report, comparing options and market analysis. Each finished deck has a process document |
| 3 | <code translate="no">slides/복잡한-배치/</code> | Ten layouts with many cells, like dashboards, magazine pages, process maps and Gantt charts |

The installed samples are read-only, so follow along in your own project.

## Reading code

- Click a file once in the 'Code' list (or press Enter) to show it in the main area with line numbers and language colors. It is never edited or run.
- The contents on the right list classes, functions, methods and divider comments such as `# ---- drawing ----`; click one to jump to that line. Config files list their keys and sections.
- The **Open in external editor** and **Copy all** buttons sit at the top. Right-click a line for Copy line, Copy location for Claude and Open this line in the editor.
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

### Excel files

Click an Excel file (`xlsx`, `xlsm`) once in the 'Other files' list, or right-click it and choose **Show in code view**, to view it in Lectern. Double-click opens it in Excel as before.

- It shows as a table like CSV — filter, sort, stats and the header option all work, and the **sheet tabs** under the header switch sheets (hidden sheets in italics).
- Column names start with Excel's column letters (A, B, C…) and row numbers are Excel's row numbers. Rows without values are left out.
- Cells show what Excel shows — number formats such as thousands separators, percentages, dates and decimals are followed, and formula cells show the calculated value (hover to see the formula). Colors, fonts and merged cells are not shown.
- Right-click a cell for **Copy this cell** (with its name, such as B3), **Copy this row** and **Copy location for Claude** (`@data/prices.xlsx sheet 'Q1' line 3`). **Copy all** copies the current sheet as tab-separated text that fills the cells when pasted into Excel. You can also focus rows and send them to Claude with Shift+→.
- It is read-only — open the file in Excel to change it. The old `xls` and `xlsb` formats open in Excel. Up to 50,000 rows and 1,000,000 cells per sheet are shown; the bar says so when a sheet is longer.

### Viewing a table as a chart

See a table as a line or bar chart on the spot. This only views — documents and files don't change.

- **Where to open it**: right-click a table in a document and choose **View as chart**; right-click picked table rows for just those rows; use the **View as chart** button in the CSV and Excel views (filtered rows as they are) or right-click a column header.
- Time is recognised automatically — `2026`, `2026-03`, `2026.3`, `202603`, `2026M03`, `2026-03-15`, `3/31/2026`, `2026Q1`, `1Q26`, `Mar-26`, `2026H1`, `FY2026`, `2026E` and Korean forms. Tables with the latest row on top are put in time order, and a header row of periods (`2024 | 2025 | 2026`) swaps rows and columns by itself. Text columns before the periods become series names and units.
- Units come from brackets in the header (`Price (USD/t)`), or from the table caption. When levels and rates (`%`, `YoY` and so on) are mixed they go on two axes, and **Level / Growth rate / Both** choose what to show. Two axes at most.
- Blank cells, `-`, `n.a.`, `x` and `#DIV/0!` are gaps, not zero. `(1,234)` is negative, and the provisional mark in `1,234p` is dropped.
- Outside a time axis, `Total` and `Average` rows are left out of the chart so they don't flatten the bars; a note above says so.
- **Auto** draws levels as bars and rates as lines (levels become lines past 36 points). Switch to **Line** or **Bar**, and turn series on and off in the list on the left. Up to 6 start on.
- If the guess is wrong, fix it with **Rows↔Columns** and the series list. Hover to see values; with many points, zoom with the bar below. **Esc** closes.

### Data analysis (CSV and Excel)

- **Summary**: a line above the table such as `Monthly · 2015-01 ~ 2026-09 · 6 numeric columns · 2 blanks`, counted again when you filter.
- **Calculated columns**: right-click a numeric column header to add % vs previous period, % vs same period last year (12 back for months, 4 for quarters), difference, cumulative, moving average or an index with first value = 100. They have their own colour, and filters, sorting, statistics and charts all work on them.
- Calculated columns are on screen only. They are never written to the file; they stay when the file changes and redraws, and are gone when you open the file again. Remove one with the **×** in its header.
- Calculations use the filtered rows. A table stacked by item has several rows per period, so it isn't calculated and a note says why — filter by item first to get that item's series. After a missing month, the % vs previous period is blank.
- **Copy shown table** copies filtered rows and calculated columns (pastes into separate cells in Excel). **Send to a document…** puts it into another document as a Markdown table (up to 500 rows).

### Sheets with several tables

Tables from Excel often have title rows above them, several header rows, or several tables on one sheet. Such a sheet is split into tables, the largest one is shown, and buttons appear above it. Clean sheets have no buttons and look as before. CSV works the same way.

- Pick a table with **Table 1**, **Table 2**, or see everything as received with **Whole sheet** (**Whole file** for CSV). Row numbers stay as they are in the file.
- Tables are split at blank rows and columns. A spacer column inside a table and blank rows inside the body stay in the same table.
- A single-cell row above a table is its title (a line like `Unit: kt` gives the chart its unit). `Source:` and `Note:` rows below it are left out.
- Rows above the first numeric row are the header. Several rows are combined, like `Imports · Copper` — merged cells carry their value across the merged range.
- If the guess is wrong, change the number of rows with **Header rows − +**, or pick rows in the whole sheet and right-click **Use this range as a table**.
- The chosen table and header rows are remembered until you quit. The file doesn't change.

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
- Menus keep the same order everywhere: what only that item can do → Claude → copying → Clip and Send → edit and open → view → delete. Only shortcuts appear on the right; hover over an item for its description.
- From the keyboard, **Shift+F10** opens the menu for the focused item or the current line.
- **Clip** and **Send to a document…** in block and heading menus send that piece to a document open in a document tab, or to a new one (see Clip above).
- The **terminal button** to the right of a copy item puts the same text into the terminal (Enter is not pressed). It is there for selected text, the location for Claude, the source, code, `@path`, the full path and so on, including in the right-click menus of the tree and the 'Code' and 'Other files' lists. See 'Terminal' below.

## Notes

Each project has its own notes. The **Notes** button in the tab bar or **Alt+M** opens and closes a panel on the right (Esc closes it too). It covers the document, so you can write while reading.

- Press **New note** and type; notes save themselves. You can add a title, a color and a pin; pinned notes come first. Type in the box at the top to show only matching notes.
- **To to-do** adds a checkbox to each line. Finished items move down, and you add items in the box at the bottom. Writing `- [ ] item` in the text works too.
- **Copy** copies Markdown text, **Terminal** pastes into the terminal (Enter is not pressed), and **To document** sends to a document in a document tab or a new one.
- After **Delete**, **Undo** appears at the top for a moment.
- Right-click a document and choose **Send to new note** to turn that text into a note, with where it came from (`@path lines 12-20`) below it. Click that to go back there.
- Notes are stored as Markdown in one file in the project folder, `.lectern/notes.md`. It is created when you first write a note and does not appear in the tree or search. It moves with the folder, and Claude Code can read it as `@.lectern/notes.md`.
- To keep notes out of a git repository, especially a public one, add `.lectern/` to `.gitignore`.
- If the file changed elsewhere in the meantime, Lectern reads it again and merges. Notes are off in view-only projects such as the samples.

## Terminal

- The **Terminal** button at the right end of the tab bar, or Ctrl+\`, opens a terminal to the right of the main area. Windows PowerShell starts in the current tab's project folder, and each tab has its own shell.
- **Several terminals**: **+** in the terminal header opens another terminal for the same project (up to 5 per project — for example terminal 1 for Claude Code and terminal 2 for other commands). Click [1 PowerShell] [2 PowerShell] in the header to switch. Reloading the window keeps the running terminals.
- **Ending a terminal**: when you no longer need a terminal, click the × on its tab (or middle-click the tab). This ends its shell and the programs started from it, asking first if a program is running. It works even when there is only one terminal; ending the last one hides the panel, and opening it again starts a new shell as terminal 1. In a narrow panel, the other tabs get shorter names and their × appears when you point at them.
- The × at the right end of the header (or Ctrl+\`) only hides the panel — the shell keeps running, so reopening it continues where you left off. The ↻ button in its header restarts the shell.
- Keys typed in the terminal go to the shell. Use app shortcuts such as Ctrl+P, Ctrl+F or F1 after clicking the main area (Ctrl+Tab moves to the next tab even inside the terminal).
- **F6** (Shift+F6 the other way) moves keyboard focus between the document and the terminal — also from inside the terminal. A closed terminal opens on the way, and coming back returns to the document you were reading (the editor in edit mode; the same spot in the box while line editing — the box stays open and unsaved). From the sidebar F6 goes to the document. While the terminal is open, an accent line shows where keys go (the terminal header, or the document tab row).
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

Sample — [guide 03, Claude Code](../../samples/guide/03-Claude-Code와-함께.md): the terminal, copying locations, change marks, reading code.

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
| vi keys | Move and edit documents with letter keys (see 'vi keys' above). Off by default |
| Full editor keys | Default (Esc closes) or vi (like vim — `:w`, `:q`). Default by default |
| Show web images | Load https images in documents. When off, they show as links |
| Teach Claude Code about Lectern | Copy, or paste into the terminal, a request to read the writing guide and add its rules to CLAUDE.md; open the samples |
| PowerPoint skills | Copy, or paste into the terminal, a request to install the skills (see 'Asking Claude') |
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

You can bring up this table at any time with the **?** button in the toolbar or Ctrl+/. **Shift+F1** opens the sample project.

<!-- 단축키 표 -->

## Good to know

- Lectern changes files only when you save in edit mode. The right-hand terminal, however, is an ordinary PowerShell, so commands typed there run as usual.
- The terminal needs Windows 10 (1809) or later. A shell's history is gone once Lectern closes.
- Document titles in the tree are read from the beginning of each document. If a document starts with a very long frontmatter, its file name is shown instead.
- Web images that cannot be loaded (blocked on a company network, or taking more than 15 seconds) turn into links.
