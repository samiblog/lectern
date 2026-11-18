# Lectern User Guide

Lectern is a workspace for Markdown-centered research with AI. You read, review and fix in place the documents and data that Claude Code or Claude writes into a project folder. It shows Markdown (`.md`) and HTML (`.html`) documents in a readable layout, and shows code in a read-only code view.

- **Files change only when you choose.** Lectern never creates, edits or deletes documents on its own; it writes only to its settings folder (the settings file and remembered titles) and to the files that change or appear because of something you chose (see 'Good to know'). Commands you type yourself in the right-hand terminal are also an exception.
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
| Toolbar (top) | Sidebar, back, forward, **Quick open** (Ctrl+P), text size − 100% +, document width, **line numbers**, style, section focus, settings, **?** (keyboard shortcuts), **Work** (Alt+W), all terminals |
| Tab bar | One tab per open project, open folder (+), and the **Edit**, **Contents**, **Print**, **Notes** and **Terminal** buttons at the right end |
| Document tab row | Just above the document — the documents open in this project (up to 40), open a document in a new tab (+), the list of open document tabs (∨) and Spread all (▦) at the right end |
| Sidebar (left) | The **Files**, **Recent**, **Search**, **Elements** and **Clip** tabs. Drag its edge to resize (double-click to reset) |
| Main area (center) | Documents, folder overviews and the code view |
| Contents (right) | The current document's headings and elements such as tables and figures. When the terminal is open, it takes this place |
| Status bar (bottom) | Document path and modified time, the changes button, and the watching status |

## Project tabs

- Each folder gets its own tab (up to 10). Clicking a tab switches the sidebar and main area to that project, and every tab keeps its own document and scroll position.
- Clicking the tab that is already selected shows that project's overview. Right-clicking a tab also offers the project overview, a new document in the top folder and the project's Elements.
- When a document in a background tab changes, a dot appears next to the tab name.
- Folders with the same name also show their parent folder's name.
- To close a tab, click its ×, middle-click it, or press Ctrl+Shift+W. Right-click a tab for Close other tabs, Copy full path and Show in Explorer. To keep the project but clear the documents open in it, right-click its tab and choose **Close all open documents** (see 'Document tabs' below).
- To move between tabs: Ctrl+1~8 (tab by position), Ctrl+9 (last tab), Alt+PageDown / Alt+PageUp (next / previous tab).
- **Reordering**: drag a tab sideways and drop it where you want it. A vertical bar shows where it will land, and Esc cancels. The new order is kept for the next start and Ctrl+1~9 follow it. Tabs move with the mouse only — there is no shortcut.

## Document tabs

Keep up to 40 documents of a project open as tabs and switch between them. They appear in the document tab row just above the document.

- **Clicking a document in the sidebar opens it in a new document tab**, and the document you were reading stays open — the tree, the Code and Other files lists, folder view, Recent, search results, Elements and Open document (Ctrl+P) all work this way. If the current tab shows a folder overview, it opens there.
- **Ctrl+click** or **middle-click** opens a new document tab behind the current one (as in a browser — the tab is drawn when you click it). **Alt+click** opens in the current tab. In quick open, Enter, Ctrl+Enter and Alt+Enter do the same.
- Links and paths in a document open in the current tab (Alt+← comes back). Use Ctrl+click, the middle button or **Open in new tab** in the right-click menu for a new document tab.
- Clicking a document that is already open in another tab goes to that tab (a document is not opened twice).
- When all 40 are in use, the tab you looked at least recently is reused (tabs with unsaved edits are left alone).
- **Back and forward** (Alt+← →, the mouse back and forward buttons) also undo jumps within a document — after going somewhere from the contents, a section link, a footnote, find, Elements or search results, they return you to where you were reading (scroll and current line), unfolding the section if needed. However many find results you step through, one press returns to where you started. Moves by scrolling or ↑ ↓ are not recorded.
- Each tab keeps its own reading position, back/forward history and edit-mode changes. A tab with unsaved edits shows **●**. So you can edit a document in one tab while reading material in another, and Send from the Clip tab opens the receiving document in its own tab.
- To switch, click a tab or press **Alt+1~8** (by position) or **Alt+9** (last tab). When there are more tabs than fit, scroll the row with the mouse wheel or click **∨** at its right end (the number beside it is how many are open) and pick from the list of open document tabs. **Ctrl+Tab** and **Ctrl+Shift+Tab** (or Ctrl+PageDown, PageUp) go to the next and previous document tab. To close, click its ×, middle-click it or press **Ctrl+W** (or Ctrl+F4 — the last tab is not closed); **Ctrl+Shift+T** reopens a closed document tab. **Ctrl+T** opens a document in a new document tab. Right-click a tab for Close other document tabs and copying its path.
- **Reordering**: drag a document tab sideways within the row (as with project tabs — a vertical bar where it lands, Esc cancels). When the row overflows, dragging to its end scrolls it. The selected tab stays selected, and Alt+1~9 and the order restored at the next start follow the new order.
- **Close all open documents**: choose it by right-clicking a document tab or the project tab (or from **∨** at the end of the document tab row) and every document tab of that project closes, leaving the folder overview. If there are unsaved edits you are asked once, and cancelling closes nothing. **Ctrl+Shift+T** reopens the closed documents one at a time. Documents in separate windows stay (close those windows instead).
- When you close every document tab, the folder overview appears — the screen you see when a project is first opened. The last remaining document tab closes too, with **×**, **Ctrl+W** or the middle button. With only the folder overview left, press **Ctrl+Shift+W** to close the project.
- The next time Lectern opens, your document tabs come back (when Settings → Start where I left off is on — only the selected tab is drawn at once, the others when you click them). If you closed every document tab and left only the folder overview, it opens with the folder overview next time too.

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
- In a separate window, **Send to Claude**, the **Terminal** buttons and **Send to new note** go to the terminal and notes in the main window. Enter is not pressed, and the main window comes to the front. **Shift+→** sends while you stay in the separate window. **Shift+number** and holding a number key in a menu (see 'Terminal' below) also go to that terminal in the main window.
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

- **Only one group is open at a time.** Click a group header ('Documents 10', 'Code 3', 'Other files 4') to open it; the others shrink to their headers and the open group takes all the remaining height. Closed headers still show counts, and while you type in the filter box they show how many match. Each project tab remembers which group was open.
- **Sub-groups inside Documents**: when Documents is open, its sub-groups are stacked under it, indented. Only one opens at a time, and the tree appears right below the open one. Kinds with no documents, or the same as All, are hidden (Highlights and To-dos show whenever there are md documents, even at 0).

  | Sub-group | Shows |
  |---|---|
  | All | Every document |
  | Documents | Markdown documents (without slides) |
  | Slides | Lectern slides |
  | HTML | HTML documents |
  | Work | The `WORK.md` of each folder |
  | Highlights | Documents with highlighted text — the highlighted text listed under each document, with its color |
  | To-dos | Documents with open to-dos — the to-dos listed under each document |

  Highlights and To-dos read the documents' text, so they take a moment the first time you open them (afterwards only changed documents are read again). Their counts appear then. Code blocks are skipped. Click a line to go to that place in the document; right-click it to add a note or remove it (see 'Highlighting to come back later' below).
- The box at the top filters by name or title. Turn on **Titles** to show document titles instead of file names (when off, file names are shown and the title appears on hover).
- **Sort** picks the list order: by name, time or type. Folders always come first, then files. By time puts the newest on top, and a folder follows its newest file. By type goes by file extension.
- Turn on **Folders** to see everything in one tree that follows the real folder structure, instead of three groups.
- The **↕** button (expand or collapse all folders) does **Expand all folders**, **Collapse all folders** or **Expand first-level folders only** for the folders in the document, code and file lists at once. Excluded (dimmed) folders stay closed, because opening one reads what is inside.
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
- Click a result line (or press Enter in the search box for the first one) to go to that line of the document (or code) with the search text marked. That line becomes the current line and keyboard focus moves to the document, so you can press **/** (insert below), **F2** (line edit) or **F3** (next match) right away. To change the search, press **Ctrl+Shift+F** to go back to the search box.
- To open something by name or title, **Quick open** (Ctrl+P) in the toolbar is faster. Matching documents come first, then code.

### Elements

- Choose **In documents**, **Doc info** or **File types** at the top.
- In documents: collects the tables, figures, charts, boxes, callouts, diagrams, code, math, to-dos, links and sources across the project, by type and by document. Pick a type with the buttons (such as 'Tables 7').
  - **Charts** (Vega-Lite, ECharts, Plotly) are collected as thumbnails, like figures — each is drawn when it scrolls into view. Graphviz and Mermaid are diagrams.
  - **To-dos** are the checklists in documents (`- [ ]`, `- [x]`). The buttons below choose **Open** (the default), Done or All.
  - **Links** lists the links in documents and paths such as `src/x.py:42`, with their target (document, code, other file, folder or web). A link whose file does not exist is marked **Broken** in red — the **Broken** button below shows only those.
  - **Sources** are lines such as 'Source: …' under tables and figures (and their Korean equivalents), plus footnotes.
  - To-dos, links and sources are not shown in the contents (only here).
- When a table, figure or diagram has a **caption**, the caption is shown as its name, with the number and size below (such as 'Table 3 · 6 rows 2 columns'). A caption is a line such as 'Table 1. …', '<Table 2>' or '[Figure 1]' (or the same forms in Korean) directly above a table or below a picture, a short whole-bold line, or `<caption>`/`<figcaption>` in HTML. Without one, tables show their header row and pictures their alt text.
- Click an item to go to that place in its document; it is outlined briefly.
- **Right-click** an item for Show in document, **Copy location** (`@document lines 12-17 ('caption')`), **Copy source** (Markdown documents), **Clip**, **Send to a document…** and **Clip all shown** (see Clip below) and copying the document path. The **▣ Terminal** button next to a copy item puts that text into the terminal (Enter is not pressed).
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

- Tables align number columns to the right, and the header row stays visible as you scroll. Hover over a table and a **Copy** button appears at its top right — like 'Copy table' in the right-click menu, it splits into cells in Excel and pastes as a table in Word and mail.
- Code blocks are colored by language; the 'Copy' button at the top right copies them.
- Callouts (`> [!NOTE]` and so on — colored boxes without a title line), footnotes, checklists, math (`$…$`, `$$…$$`, and math/latex code blocks) and Mermaid diagrams are rendered. Dollar amounts such as `$105` are not turned into math.
- **Boxes**: a box holds text that is read apart from the main text — a side topic a report touches lightly. In the source, write ordinary text, tables and figures between a `<!-- box -->` line and a `<!-- /box -->` line; Lectern draws them as a bordered box with a title band. Other viewers do not show the two lines, so the text reads as ordinary text there. A first line written on one line becomes the title, and `Box 1. Title` is numbered like tables and figures, so `[Box 1](#box-1)` refers to it. The arrow at the right of the title band folds and unfolds the box (a folded box still prints in full). Without a closing line, the box ends before the next heading. Headings (`#`) and other boxes do not go inside a box.
- **Charts**: code blocks whose language is `vega-lite` (data charts), `echarts` (many chart types such as donuts and candlesticks), `plotly` (analysis charts such as box plots and sunbursts — the output of Python's `fig.to_json()` works too) or `dot`/`graphviz` (structure and dependency graphs) are drawn as pictures. Colors follow the document style; click to enlarge, and use 'Copy image' in the right-click menu to paste a PNG. Settings are JSON and functions are not allowed. Write the data in the document or point to a CSV/JSON file in the project with a relative path (internet addresses are not read). There is no hover or zoom, and Plotly map charts are not drawn because they need map data from the internet. The samples (**Open samples**) have an example of each kind in the chart guide (number 07 in the `guide` folder).
- **Chart data**: hover over a chart and **Table** and **Copy** buttons appear at its top right. **Table** opens the data the chart was drawn from as a table below the chart; press it again to close. Over 30 rows, only the first, the last and evenly spaced rows (30 in all) show, and **Show all** opens up to 5,000. **Copy** copies all the data so it splits into cells in Excel and pastes as a table in Word. The data is read from the chart's source — if the chart filters or combines values (transform, aggregate), the table shows them before that. A chart whose data is in a CSV file names the file instead and offers **Put data into the document**, which reads the CSV and writes the values into the chart's source — then the document alone shows the chart and table on other PCs (Ctrl+Z undoes it). Charts in Lectern slides and Graphviz have no buttons, and the buttons and tables are not printed.
- A line you break with Enter inside a paragraph also breaks on screen (like Shift+Enter in Word — outline-style writing shows as written). Two spaces at the end of a line and `<br>` do the same. Turn this off in Settings to join lines as standard Markdown does.
- Click an image to enlarge it.
- Paths in the text that point to real files, such as `src/app.py:42`, become links.

### Contents

- Click an entry in the contents on the right to jump to that heading; the place you are reading is marked.
- Under each heading, the section's tables, figures, boxes, callouts, diagrams, code and math are listed like 'Table 1 · Price comparison · 6 × 4'. Click one to jump to it.
- The buttons at the top of the contents, such as 'Tables 2' or 'Code 5', hide that type from the contents; click again to show it.
- The **Contents** button at the right end of the tab bar shows or hides the contents.
- Drag the border between the document and the contents to resize the contents. Double-click it to reset.
- **Moving sections**: in an md document you can edit, drag a heading in the contents onto another heading to move that section — with its body and subsections — in front of it. Drop on the lower half of the last heading to move it to the end. Levels stay the same; Ctrl+Z undoes it.

### Folding sections

Click the arrow in the margin left of a heading to fold its section, and click it again to unfold (the arrow shows when the mouse is over the heading). From the keyboard, **Ctrl+Shift+[** folds the section with the current line and **Ctrl+Shift+]** unfolds it — if it is already folded, Ctrl+Shift+[ folds the outer section, and if it is open, Ctrl+Shift+] unfolds the folded sections inside. Clicking the heading text does not fold; it makes that line the current line. Right-click the text for Fold all at this level and Fold all / Unfold all. Folded sections are unfolded again when Lectern restarts.

### Text size and style

- The − / + buttons in the toolbar set the document text size from 80% to 200% (100% is already set slightly large for comfortable reading). Click '100%' in the middle to reset. From the keyboard: **Ctrl+=**, **Ctrl+-** and **Ctrl+0** (100%). To zoom the whole app, use Ctrl+Wheel.
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

- **Current line**: the small triangle to the left of the line you are reading. Click or right-click the text to move it there; **↑ ↓** move it one line at a time and the view follows. **Home End** go to the first and last line, **PageUp PageDown** (Space, Shift+Space) move a screen at a time and keep the current line at the same height on screen, and **Ctrl+↑ ↓** go to the previous or next heading. If you scroll it off screen with the wheel, it follows to the nearest line on screen. Going somewhere with the contents, Find or Search moves it there too. The status bar shows it as `Current line 12`, and each document tab keeps its own.
- **Send to Claude**: **Shift+→** puts the location of the current line (or of the picked lines — while words are selected it widens the selection instead), `@path lines 12-20`, into the first terminal (usually terminal 1, where Claude Code runs). Enter is not pressed and focus moves to the terminal, so you can type your request straight away. To add several places in a row, press **Ctrl+Shift+→** — focus stays in the document. With several terminals, **Shift+number** (Ctrl+Shift+number) puts it into the terminal with that number. **Shift+←** copies the location and **Ctrl+C** copies the source of those lines (if you dragged to select text, Ctrl+C copies that text). After copying, 'Copied: …' shows briefly at the bottom of the window.
- **Section focus**: the **Focus** button in the toolbar or **Alt+H** keeps the section with the current line sharp. ↑ ↓, PageUp PageDown or the ∧ ∨ buttons next to it move to the previous or next section. Click a dimmed area to move the focus there. Shift+↑ ↓ turn the section into picked lines. Press Esc or the button to turn it off, or right-click the text and choose 'Focus this section'. In documents without sections and in the code view, the button works like Ctrl+Enter.
- **Enter on the line**: opens the current line for line editing — the same as F2. Editing comes first, on a heading or a line with a link too. Enter in the box saves and closes, so the file stays as it was if you changed nothing.
- **Alt+Enter on the line**: on a heading it folds or unfolds the section (Ctrl+Shift+[ ] too); on a line with a link it opens the link (a small menu if there are several). **Tab Shift+Tab** move focus to the next or previous link from the current line; open it there with **Alt+Enter** (Enter edits the line). **F3 Shift+F3** go to the next or previous match of the last search (even after the find bar is closed).
- Picking and editing lines are described in 'Writing and editing documents'.

### Find in document

- Ctrl+F finds text in the document or code you are viewing, even across formatting such as bold or code.
- Enter goes to the next result, Shift+Enter to the previous one, and Esc closes the find bar.
- **Find and replace** (Markdown documents): the **Replace** button on the find bar or **Ctrl+H** (also in the find box) opens the replace row — opened with the button, you type the replacement right away. Press it again to close the row. **Replace** (Enter) changes the first match after the current line, **Replace all** (Ctrl+Enter) the whole document; it is saved at once and **Ctrl+Z** undoes it. The button is not shown in the code view, HTML documents or view-only folders (find only).
- **Ctrl+G** goes to a line — type the line number and press Enter.

### HTML documents

HTML reports written by Claude appear in the tree marked `HTML`. Their own styles are kept, while scripts and stylesheets from the internet are blocked (so charts drawn by scripts do not appear). HTML files inside app source folders such as `src`, `public` or `web` are not treated as documents.

### Auto refresh

- While Claude writes a document, changes appear within a second and your reading position stays where it was.
- Changed paragraphs and tables are highlighted briefly. If the changes are off screen, the **changes** button in the status bar takes you through them.
- If the text is unchanged, the screen is not redrawn, so your selection stays. While you drag to select text, the refresh waits until you release the mouse.
- When the text really changes, the screen is redrawn and the selection is cleared.
- If a change was missed, press F5 to reload.

### Print, PDF, html and Word

Click **Print** at the right end of the tab bar (between Contents and Notes), or right-click the margin of a document and choose **Save as PDF…**, **Print…**, **Save as html…** or **Save as Word…**. Paper and PDF always use the same **report layout**, whatever the screen style — A4, margins 25 mm top, 22 mm bottom and sides, the title centred on the first page, the document title and date in the header from page 2 (the front matter's `date`, or today), and page numbers centred at the foot. Tables get heavy top and bottom rules, links print as plain text and addresses are added only in the lists of a 'Sources', 'References' or 'Data' section. The front matter table is left out. Choose the body font, serif (default) or sans-serif, under **Print and PDF font** in Settings.

All of them open the **Export** window. Under **Format** at the top, choose PDF and print, one html file, or Word. Choose options on the left and the preview on the right is made again with them — the preview is exactly the PDF that will be saved or printed (the bar above it has contents, zoom and page turning).

| Option | Choices |
|---|---|
| Font | Serif (HCR Batang, else Batang — sans-serif headings) or sans-serif (Malgun Gothic) |
| Margins | Normal (top 25, bottom 22, sides 22 mm), narrow (15 mm all round), wide (top 30, bottom 25, sides 30 mm) |
| Page header | Document title and date in the header from page 2 |
| Page numbers | '- 1 -' centred at the foot |

The options are kept for next time.

- **Save as PDF…**: writes the previewed PDF where you choose in the save dialog (it opens next to the document, with the document's name). There is no date and address header from the browser, and headings become PDF bookmarks. If the name exists, Windows asks whether to replace it. If a PDF viewer has the file open, close it and save again.
- **Print…**: sends the previewed PDF to the print dialog. Choose the printer, copies, pages and colour there. It prints the PDF, so no date and address header is added.
- Close the window with Esc or **Close** (after clicking inside the preview, move the mouse out of it first).
- HTML documents keep their own style and have only the print dialog (**Print / Save as PDF…**) — choose 'Microsoft Print to PDF' as the printer for a PDF.
- **Layout**: under Format, pick an output layout under **Layout** — government report, one-page brief, official letter, press release, minutes, research report, issue brief, journal paper (two columns), manuscript, white paper, equity research, consulting report, proposal, magazine, newsletter, book, long-form web article and manual. The text stays the same; the cover, headers, page size, fonts and colours change. PDF and html come out the same. **Report (default layout)** at the top is the report layout above (with the font and margin options).
  - Layouts use front matter values on the cover and in headers (`title`, `subtitle`, `author`, `date`, `org`, `dept` and so on). When you pick one, the window lists the keys it uses that the document lacks, and **Copy front matter sample** copies them to paste at the top of the document.
  - Write text that sits apart, such as a summary, key points or an abstract, as a **named box** — a box opened with <code translate="no">&lt;!-- box: 요약 --&gt;</code> moves into that layout's summary slot. If the layout has no such slot it stays an ordinary box in the body. The window shows the layout's box slots.
  - Write `layout: layout id` (for example `layout: research-report`) in the front matter and the window opens with that layout.
  - Your own layouts: open the layouts folder under **Page layouts** in Settings, paste **Copy request for Claude Code** into Claude Code and describe the layout you want; Claude reads the guide and saves one html file there. It appears under **My layouts** at the bottom of the list.
- **Save as html…**: saves an md document as one html file. It keeps the current screen style as one long page, and pictures, charts, diagrams and math go inside the file, so you can send just that file by e-mail. Folded sections and boxes are unfolded, app marks such as copy buttons and line numbers and the front matter table are left out, and contents, footnote and cross-reference links still work. Links to other documents stay as text. There are no scripts, so it opens safely in the recipient's browser, and printed there it comes out in the same report layout as the PDF. What you previewed is written where you choose in the save dialog (it opens next to the document, with its name). For Lectern slides, use **Convert to html** on the status bar.
- **Save as Word…**: saves an md document as a docx to keep editing in Word. Text stays text, tables become Word tables (header row repeated on each page), footnotes become Word footnotes, `Table 1.` and `Figure 1.` captions get Word's numbering fields, and cross-references such as `[Table 1](#table-1)` become links to those captions. Highlights, text colours, callouts and boxes come along; charts, diagrams and display math go in as pictures (inline math as text). There is no preview — the window shows what was made (pictures, size, notes), and Word lays out the pages. If the document has a `[toc]` line, Word asks whether to update fields when it opens — answer **Yes** to fill in the contents and page numbers.
  - **Word template**: the default is the Lectern default template (A4, serif body, the title in the header from page 2, page numbers centred at the foot). Below it are **18 Lectern templates** with the same names and groups as the page layouts — government report, one-page report, official letter, press release, minutes; research report, issue brief, academic paper (two columns), manuscript, white paper; equity research, consulting report, proposal; magazine, newsletter, book, long-form; manual. Export a document with a layout to PDF or html and with the template of the same name to Word, and the cover, summary box, sign-off boxes and running heads come out alike. A template fills its cover and information table from the front matter (`title`, `subtitle`, `author`, `org`, `date`, `number` …, Korean keys such as <code translate="no">기관</code> too) and drops the lines whose keys are empty. A named box (<code translate="no">&lt;!-- box: 요약 --&gt;</code>) goes to the template's slot of that name, sign-off boxes come from a list such as <code translate="no">결재: [Staff, Manager, Director]</code>, and the labels (Summary, Contents …) are in English with `lang: en`. Pick a template and its description, page size, box slots and the empty front-matter keys appear below; **Copy front matter sample** copies only the empty keys (nothing is written to the document — you paste and fill them in).
  - **The small ▪ left of section headings**: it is not a character but Word's mark for a paragraph set to 'Keep with next' — it shows when Word's **paragraph marks** are displayed (it does not print or appear in PDF, and Word's own heading styles show it too). Section headings and captions keep this setting so a page break does not separate them from what follows; the document title and subtitle at the top of the first page do not have it. To hide it, turn off 'Paragraph marks' under **File > Options > Display** in Word.
  - **My templates**: put your organization's Word templates (.dotx, .docx) in the folder that **Open templates folder** opens and they appear under 'My templates' at the bottom of the list; pick one and its styles, page size, margins, headers and footers are borrowed and only the body is written anew. If a template uses its own style names (such as '1.Heading' or 'Body2'), put `template-name.styles.json` (`{"heading 1": "1.Heading", "Normal": "Body2"}`) next to it. To give your template a cover, write placeholders such as `{{title}}`, `{{author}}` and `{{date:en}}` in its text in Word, and put a `{{body}}` line where the body goes (the full list is in the skill's SKILL.md and sample guide 13).
  - Write `docxStyle: template name` in the front matter and the window opens with that template. Otherwise the template with the same name as the `layout:` (page layout) — your own first, then the Lectern templates. Layouts and templates share names, so one line `layout: research-report` pairs PDF, html and Word.
  - Making the file takes a few seconds (more with many charts). Charts are drawn with Windows' Edge — nothing goes to the internet.

Lectern slides print one slide per slide-sized page (see 'Lectern slides'). A **Page break** line from the insert window starts a new page, and a **Contents** line prints as a table of contents in its place (see 'Adding components').

- Text size, document width, line numbers, find marks, highlights and the screen style do not reach the paper. Tables longer than 12 rows break across pages with the header row repeated, captions stay on the same page as their table or figure, and figures taller than a page are scaled to fit one page.
- If you are editing, save and close the editor first (the PDF uses the saved text). In Spread all, the PDF is of the pane you right-clicked.

Sample — [12 Reports and PDF](../../samples/guide/12-보고서와-PDF.md) (in Korean): example requests for the writing style, writing for the report layout, and a sample report written by Claude to try. [13 Exporting — html, page layouts and Word](../../samples/guide/13-내보내기-html-틀-Word.md) (in Korean): the 18 layouts with their front matter and named boxes, using a company Word template, and three sample documents to try.

## Writing and editing documents

Write and edit an md document from start to finish without opening the full editor.

Sample — [guide 08, line editing](../../samples/guide/08-한-줄-편집.md): picking lines and twenty-two cases to try.

**There is no separate save.** Enter in a cell, moving and deleting lines, changing line types and levels, table rows and columns, to-do checkboxes and pasted pictures are saved to the source file the moment you do them, and each one is undone with **Ctrl+Z** (picked lines and focus stay on the lines you undid). A new line is saved when you write in it, and Esc in a cell drops your change. Lectern slides work the same way. Only the full editor needs Ctrl+S to save (Ctrl+S in a cell works like Enter). Moving the current line, picking lines, focus and folding do not change the file.

**Notices appear only for changes you may not have seen.** Saving is not announced — the 'Modified' time in the status bar changes. The notice at the bottom appears only for things you may have missed on screen: something deleted, lines outside your pick that changed too (such as the numbers of following items), many places changed at once (Find and replace), and something that could not be done, with the reason. Undo is announced only when the line was off screen and the view had to move to it.

### Four states of a line

| State | What it is | Get there | Leave |
|---|---|---|---|
| **Current line** | One line — where you read, write and insert | Click, right-click, ↑ ↓, Home End, PageUp PageDown, Ctrl+↑ ↓ | — |
| **Picked lines** | Several lines — to delete, move or change together | **Shift+↑ ↓** from the current line, Shift+click or drag, Ctrl+A (all lines) | Esc, ↑ ↓, a click elsewhere, shrinking to one line |
| **Focus** | A light over the current line or the picked lines (selecting lines) — dims the rest | **Ctrl+Enter** | Ctrl+Enter, Esc or a click on a dimmed area |
| **Cell** | A text box that edits the line right where it is | **Enter**, **F2**, Shift+Enter (new line) | Enter saves and closes, Shift+Enter saves and opens a line below, Ctrl+Enter saves and selects that line, Esc cancels |

- **There is one selection**: one line is the current line; extend it with Shift+↑ ↓ or Shift+click and several lines are picked lines. The first line stays and the last one moves, so the range grows or shrinks, and back at one line it is the current line again. Shift+click picks from the current line (the line you last clicked or moved to — scrolling afterwards does not change it) to the line you click; Shift+drag picks from the line you press to the line you drag to. While lines are picked, the status bar shows `Picked lines 3-5 · 3 lines`.
- **Picking a lot at once**: **Shift+Home End** pick from the current line to the start or end of the document, **Shift+PageUp PageDown** a screen at a time, **Ctrl+Shift+↑ ↓** up to the section heading or the section end. **Ctrl+A** picks every line of the document without moving the view — then Ctrl+C copies the source or Shift+→ sends it to Claude.
- **The Enter keys mean the same everywhere**: **Shift+Enter** is a new line below (in reading and in a cell), **Ctrl+Enter** selects lines (focus — in a cell it saves and selects that line), **Enter** saves and closes a cell (in reading it folds a heading or opens a link). A new line above is **Ctrl+Shift+Enter**.
- **Writing and inserting happen at the current line**: editing the line (F2), a new line below or above (Shift+Enter, Ctrl+Shift+Enter), the insert box below (`/`), pasting a picture. They are off while several lines are picked — a note says to release them with Esc first.
- **Change keys take two presses on one line, one on several**: delete (Delete, Ctrl+X), move (Alt+↑ ↓), line type (one-letter keys, Ctrl+Alt+number) and level (Alt+Shift+← →). On the current line the first press only puts a band on the line and shows `Current line 12 · change` in the status bar — the file is untouched, so a stray key while reading never changes it (the notice at the bottom appears only the first time after Lectern starts). Press again to change it; while the band is there, further keys (Alt+↑ again, Tab) act at once. ↑ ↓, Esc or a click elsewhere cancels. Holding a key down counts as one press. Keys that do not change the file — copy, copy location, send to the terminal — act at once on the current line or the picked lines.
- **Writing ends picking**: opening a cell releases the band and a one-line focus.
- **Focus (selecting lines) goes on and off at any time**: **Ctrl+Enter** keeps the current line, or the picked lines, sharp and dims the rest. Focused lines are picked lines — delete, move, line types, copy and send work as usual (at once even on one line), and Shift+↑ ↓ grow and shrink them. Only ↑ ↓ differ: they scroll without releasing. Turning it off returns to the picked lines (or to the current line when it was one line). Clicking a dimmed area turns it off, and right-clicking there only offers to turn it off.
- **Right-click**: the line you right-click becomes the current line. Inside picked lines, right-clicking opens a selection box for that range — what only that block can do (such as Copy table), **Send to Claude**, copying, Clip and Send, **Change picked lines…**, release, and Delete lines at the bottom. Right-clicking outside them releases them and opens that line's menu. Hover over an item for its description.

### Selecting text and formatting

You can also select words in the reading view and format them straight away, without opening a cell.

Sample — [guide 08, line editing](../../samples/guide/08-한-줄-편집.md) (in Korean), cases 21 and 22: bold and highlight on key words, and formatting a whole line. The source of inline formats is in [guide 04, writing documents](../../samples/guide/04-문서-쓰는-법.md), 'Inline formatting'.

| Key | What it does |
|---|---|
| **Double-click** the body | Selects that word (the line-edit cell does not open) |
| **→** / **←** on the current line | Selects the first / last word of the line |
| **→** / **←** with a selection | Moves to the next / previous word |
| **Shift+→** / **Shift+←** with a selection | Extends or shrinks it word by word |
| **Home** / **End** with a selection | First / last word (with Shift, extends to it) |
| **B** · **I** · **S** · **M** · **F** | Bold · italic · strikethrough · highlight · text color on the selection (also Ctrl+B, Ctrl+I, Ctrl+Shift+X, Ctrl+Shift+H, Ctrl+Shift+C — plain H and C are line-type keys) |
| **F2** · **Enter** | Opens the line's cell with the same text selected |
| **Esc**, **↑ ↓** | Clear the selection (↑ ↓ also move the current line) |

- Words are split at spaces. Moving stays within the line (one source line); → on the last word does not go on to the next line. A selection made by dragging extends with the same keys.
- Formatting is saved as you press and shows right away. The selection stays. Pressing bold, italic or strikethrough again removes it. Highlight and text color step to the next color each press and come off after the last one (highlight: yellow → green → pink → blue → off). To take a color off at once, right-click and choose the same color again, or **Clear formatting**. **Ctrl+Z** undoes it.
- **B, I, S, M and F work only while text or lines are selected.** On the current line with nothing selected they do nothing, even pressed twice, so a stray key while reading never changes the file. Don't hold Shift. **Ctrl+B** with nothing selected still hides and shows the sidebar as usual.
- **A whole line**: **triple-click** a line to select all its text, then press B, M or another key to format the whole line (list and heading markers stay). For several lines, pick them with Shift+↑ ↓ first.
- Right-click selected text for its box — Copy selected text (the terminal button beside it puts it in the terminal), formats and colors, Clear formatting, Edit here, Clip selected text, Send selected text… and Send to new note. If the selection is inside a highlight, **Add a note** and **Remove this highlight** appear too (below). The block's usual menu (copy table and so on) is **Menu for this block…** at the bottom.
- While text is selected, Shift+→ extends it instead of sending to the terminal. Press Esc first to send.
- A note explains what cannot be done: a selection over several lines (pick the lines and format whole lines), across table cells, from the middle of a bold or colored part to outside it, or on a line with math or footnotes (press F2 and format inside the cell).

### Highlighting to come back later

A highlight is not only a look; it also marks places to come back to. To highlight, see 'Selecting text and formatting' above — double-click a word and press **M**.

Sample — [guide 02, reading](../../samples/guide/02-읽기-기능.md) (in Korean), 'Marking as you read': go back to highlighted places with the sidebar and F8.

- **Going back**: the **Highlights** sub-group under Documents in the sidebar lists highlighted text by document. Click one to go to that line. Typing in the filter box also matches the highlighted text. Inside a document, **F8** goes to the next highlight and **Shift+F8** to the previous one and selects it — press M to change its color, or right-click to add a note or remove it.
- **Adding a note**: right-click a highlight line in the sidebar, or the highlighted text in the document (selected with F8 or by double-clicking a word in it), and choose **Add a note**. A note titled with the highlighted text appears in the notes panel, ready for you to type. Its 'Go to source' brings you back, and finds the text even if lines have moved.
- **Removing**: right-click a highlight line in the sidebar, or the highlighted text in the document, for **Remove this highlight**, or a document row in the sidebar for **Remove all highlights in this document…** (and per color when there are several). Removing all asks first with the count. Only the highlighting goes; the text stays, and one **Ctrl+Z** undoes it. If the highlight is in another document, that document is opened first so you see the change. There is no way to remove highlights from many documents at once.

### New document

- To start: **Create** in the **Documents** header of the sidebar, **Ctrl+N**, **+** in the document tab row, or right-click a document, folder or empty space in the tree and choose **New document…**. It starts in that folder; Ctrl+N and **Create** start in the folder of the document or overview you are viewing.
- The **title** becomes the file name and starts as 'New document'. The most recent **style** is selected; change it with ↑ ↓. Choose **Lectern slides** to pick a template for the first slide.
- In **Location**, choose the top of the project or another folder, including empty ones. **New folder…** creates a folder inside the chosen location and selects it. **New folder…** in the right-click menus of the tree and project tab does the same. Empty folders do not show in the tree, so the new document box opens right away.
- It starts with one `# Title` line, and a cell opens under the title in a new tab so you can write right away. A numbered style adds two sample headings with the first one selected, so typing changes the text and keeps the number.
- It is created only if the name is free. If not, the reason is shown — change the title. Esc closes the box.
- The file stays even if you close it before writing. If you do not need it, right-click it in the tree and choose **Delete document…**.

### Line editing

You can edit a line right where it is. Press **Enter** or **F2** on the current line to open it. A double-click only selects a word and does not open the cell — press F2 with a word selected (or right-click it and choose **Edit here**) and the cell opens with that word selected. **Open in the full editor** (Ctrl+E) in the right-click menu of an ordinary line opens the full editor at that line (see 'Full editor' below). A heading keeps its heading size, a list item its bullet and a callout its callout look; markers such as `#`, `-`, `>`, `1.` and `[ ]` are locked so only the text changes. Inline formatting shows as source text, such as `**bold**` or `[link](url)`.

- **Enter** saves straight into the source file and **Esc** cancels. Clicking outside saves if you changed something. After saving, the view is redrawn and the change briefly highlighted.
- **↑ ↓** save and go on editing the line above or below. In text that wraps on screen they move inside it first, and go on from its top or bottom screen line. To send the line to Claude, close the cell with Enter (or Esc) and press **Shift+→**.
- **Tables**: F2 on a row opens its first cell; double-click a word in a cell and press F2 to open that cell. You edit cell by cell. **Tab** and Shift+Tab move between cells — Tab in the last cell of a row goes to the first cell of the next row and Shift+Tab in the first cell to the last cell of the row above, so you can fill a table row by row. ↑ ↓ go to the same cell in the row above or below. A `|` typed into a cell is saved as `\|` so the cell is not split.
- In a paragraph wrapped over several source lines only that line is edited; code blocks and the code view edit that line. F2 on a picture opens its source line. F2 on math, diagrams and charts opens the source to edit line by line. HTML and comments are edited in **Source lines** from the status bar. Data files like CSV, text and Excel are view only.
- Clicking outside a cell without changing anything ends without saving.
- Editing during section focus lifts the grey shading so the lines above and below read normally; it returns when you finish.
- **To-dos**: click a checkbox in the body to switch `[ ]` and `[x]` in the source and save it straight away. Nothing changes in view-only projects such as the samples.
- After saving, **Ctrl+Z** restores the line as it was and saves again; press it again for earlier edits. **Ctrl+Y** redoes what you undid. Undo is kept per file, so you can go back to a document and undo there after editing another one. Editing again after an undo clears the redo.

### Adding, moving and deleting lines

Change the structure in a cell or on picked lines (on the current line alone, press the key twice). Any text you changed in a cell is saved first, so undoing takes two steps. If something can't be done, nothing changes and a message says why.

- **New line**: **Shift+Enter** opens a new line below, **Ctrl+Shift+Enter** above. The same keys work on the current line without opening a cell (not while several lines are picked). It takes after the line it came from: the same marker in a list (after any sub-items), the next number in a numbered list, inside a quote or callout, a paragraph under a paragraph or heading. **A new line above follows the block above it** — above a paragraph or heading that sits right under a list, quote or callout, the new line continues that block at its end (for a paragraph instead, press Shift+Tab in the new line). Above a list item or quote line, the new line takes that line's form (above the first item, a new first item). If you pick List, Numbered list or To-do for an empty new line in the insert box (/), it joins a list of the same kind right above or below (the next number under a numbered list). In a table it is a new row, around a chart or math a paragraph. The file does not change until you write something.
- **Adding lines uses the same key everywhere**: **Shift+Enter** in the reading view and in a cell alike (Ctrl+Shift+Enter above), in the middle of a document and at its end. **↓** only moves; it stops on the last line and tells you the key for a new line. In an empty document F2 or ↓ opens the first line. **Enter** saves and closes, on a new line as on an existing one, and the current line stays there. To keep writing below, press **Shift+Enter** — it saves and opens a new line below. **Ctrl+Enter** saves, closes and selects that line (focus), ready to move or format it. Enter or Ctrl+Enter on an empty new line closes it without adding anything. To add a paragraph after a table or code block, press **/** on it — the insert box opens after the block (Shift+Enter there adds a row or a code line). With footnotes, a line added on the last line of the body goes before the notes.
- **Ending a list**: on an empty new item, **↓** or **Shift+Tab** moves out a level, and at the outermost level it becomes a paragraph and the list ends. **Tab** nests it under the item above.
- **Split and join**: **Shift+Enter** in the middle of the text splits the line there. **Backspace** at the start of a line joins it to the end of the line above — paragraphs with paragraphs, list items with list items, code within its block. Lines of different kinds, such as a heading and a paragraph, are not joined.
- **Move**: **Alt+↑ ↓** move lines. List items move with their sub-items within the same list, paragraphs swap with the block next to them, one line of a paragraph written over several lines stays inside that paragraph, code stays in its block, and table rows stay below the header. The picked lines follow, so you can keep moving them. The notes at the end of the document and the body never cross each other.
- **Delete**: pick lines and press **Delete** (or right-click 'Delete lines'); in a cell, **Ctrl+Shift+K**. **Ctrl+X** copies the source and deletes. You are asked first if it is more than 10 lines or includes a heading. Doubled blank lines left behind become one, and sub-items left behind move up to the deleted item's place.
- Deleting only a table's header or divider row would break the table, so it is blocked (pick the whole table to delete it). Deleting part of a code block together with lines outside it is blocked too; picking every code line deletes the block.
- **Duplicate**: **Ctrl+Shift+D** in a cell adds the same line below and goes on editing the copy. Table rows are not duplicated. In the full editor too, **Ctrl+Shift+D** duplicates and **Ctrl+Shift+K** deletes the line.
- App keys such as **F1**, **Ctrl+/**, **Ctrl+W**, **Ctrl+Tab**, **Alt+1–9** and **Ctrl+P** also work inside a cell — the cell is saved and closed first.
- Numbered lists are renumbered when you add, move or delete. A list written with `1.` throughout stays as it is. One **Ctrl+Z** brings the numbers back too.
- All of this also works in the code view and in slides. It is not available in HTML documents, data files (CSV, text, Excel) and view-only projects.
- Files that are not UTF-8 are view-only. Files in the Windows encoding, such as EViews programs (`prg`), show Korean correctly in the code view and in search, but line editing and edit mode don't change them. A `prg` written only in English can be edited; adding Korean to it is not saved, because the file would turn into UTF-8 and EViews would show broken characters.

### Line types and heading levels

Markers (`#`, `-`, `>`) are locked, so you change them with keys and menus. The keys work in a cell or on picked lines; on the current line alone, press them twice (the format keys B, I, S, M and F differ — see below).

- **One-letter keys**: pick lines (Shift+↑ ↓, Shift+click) and press a single key. On the current line alone, press it twice — **1–6** heading, **0** or **P** paragraph, **H** heading levels in turn (heading 2 → 3 → 1 → paragraph), **L** or **-** list, **N** numbered list, **T** to-do, **Q** quote, **C** callout (on a callout, the next kind — note → tip → important → warning → caution). Pressing the same key again goes back to a paragraph (a to-do goes back to a list item). The lines stay picked, so you can go on with **Tab** for the level. They work whatever the input language is, and they are the same keys as in Lectern mobile. On the current line the first press only holds the line, so a stray key while reading never changes the file.
- **Format keys**: **B** the whole text in bold, **I** italic, **S** strikethrough, **M** highlight, **F** text color (highlight and color step to the next color each press; B again removes the bold). These five work only on picked lines (for one line, Ctrl+Enter or a triple-click) and on selected text — on the current line they do nothing, even pressed twice. See 'Selecting text and formatting' above.
- In a cell the letters are typed, so use **Ctrl+Alt+1–6** (heading) and **Ctrl+Alt+0** (paragraph) there; they work on picked lines too, and like the number keys, the same level again makes a paragraph. Outside a cell, right-click **Change this line…** (key **.**) for lists, numbered lists, to-dos, quotes and callouts.
- **Change window**: press **.** (period) on the current line or picked lines outside a cell, or right-click **Change this line…**, and a board like the insert box opens (tables, callouts and code blocks have no such menu item — use **.** there). The current type is marked 'current' and picked. The first column, **For this line**, has changes that fit the spot — in a list **Whole list to numbers** (to bullets, to to-dos) and **List to table**, in a table **Table to list** and **Turn this table into a chart**, in a callout **Remove callout**, in a code block **Unwrap code**, outside tables and code blocks **Wrap as code**, and **Ask to rewrite**. Things that cannot be done are dimmed, and clicking one tells you why.
- **List to table** makes one row per item and splits cells at a tab, ' — ' or ': ' in the item (the header row says Item and Value — rename it). Lists with sub-items are not converted. **Table to list** makes one item per body row and joins the cells with ' — ' (the header row is left out). If the table has a caption, you are asked whether to remove it too. Wrapping and unwrapping code keeps the text as it is, markers and all.
- **Ask to rewrite** hands changes that need rewriting — 'make these three paragraphs a table', 'turn this table into prose' — to the AI. A request with the line location goes into the terminal (Enter is not pressed); type the form you want after 'New form:' and press Enter.
- **Alt+Shift+← →** change the level. Headings take their subsections along and lists take their sub-items. On list lines **Tab** and **Shift+Tab** do the same. **Tab** does not change headings (it tells you which keys do). To change just one heading's level, use the number keys or the vi keys `>>`·`<<`.
- When you pick several lines and change their level, they move from the top down, and sub-items or subsection headings already moved along with a line above are not moved again.
- **Neighbours change only when the meaning would break.** Turning a line of a numbered list into a paragraph, heading or other list continues the following items' numbers from the item before (a list written all as `1.` stays as it is). A line turned into a list joins a list of the same kind right above or below it, with that list's marker and next number (a to-do joins a bullet list too). Lines in a callout or quote change inside it, and the callout's first line stays. A sub-item turned into a paragraph becomes a paragraph inside its parent item. Caption lines (`Table 1. …`) keep their type. A quote line turned into a paragraph leaves the quote (like pressing Q again). Lines picked both inside and outside a quote or callout are not changed — you are told why.
- If lines outside your pick change too, you are told — 'Also moved 2 subsection headings', 'Renumbered 3 following items', in a document with numbered headings 'Renumbered 4 headings', and when a heading turned into a paragraph leaves links pointing at it, '1 link still points to a heading that is gone'. One Ctrl+Z undoes it all.
- Changing list items to another list kind (N, L, T) keeps their indentation. Turning an item that has sub-items into a heading or paragraph moves the sub-items up into its place.
- With several lines picked, a key changes all of them at once. Pick several paragraphs and press **L** for one list or **C** for one callout. With the mouse it is right-click **Change picked lines…** — each item shows its key.
- **Numbered headings**: if the document numbers its headings, adding, moving or deleting a heading renumbers them. One **Ctrl+Z** brings the numbers back too, and links to sections in this document follow. The number is locked in the cell. Sections such as `References`, `Appendix`, `Attachments` and `Summary` get no number.
- **Sections**: pick a heading line and press **Alt+↑ ↓** to swap the section with the one before or after it, text included. Right-click a heading and choose **Delete section** to delete it with its text and subsections. Moving or deleting the last section leaves the notes at the end of the document in place.

### Inserting elements

On the current line, press **/** (or the **Insert** button at the right end of the tab bar) to open a new line below it with the insert box. In a wide window the five groups — Text, Callout, Tables and figures, Notes and references, Page — are laid out as columns at once: ↑↓ move within a column and ←→ to the next one. **Date** and **Special character** in the Text group go inside the text — a special character goes at the end of the current line, not on a new line below (see 'Special characters'). The first column, **Recent**, holds the last five things you inserted with the first one picked, so inserting the same thing again is just / and Enter. Type to filter. Inside a cell it is **/** on an empty line and **Ctrl+Shift+/** on a line with text (that key also works on the current line, and with vi keys on `/` is Find, so use it there). With the mouse, right-click **Insert here…** — on a table it inserts below the table. Nothing is inserted while several lines are picked.

- **Text**: headings, paragraph, list, numbered list, to-do, quote. They reach the file when you write something. Typing `## ` or `- ` works too.
- **Table**: give the size like `3x4` (columns x rows). A `Table 1. Title` caption comes with the next number, with 'Title' selected so you can type it. Press ↓ to go into the table and fill cells with **Tab**. Tab in the last cell and **Shift+Enter** add a row, **Ctrl+Shift+Enter** adds one above. Right-click a cell to add, delete, move or align columns.
- **Callouts**: note, tip, important, warning, caution. On an empty new line, **↓** leaves the callout. Right-click to change the type, remove the callout or delete it.
- **Boxes**: choose **Box** in the insert box to insert the opening line, a title (`Box 1. Title`), one line of text and the closing line, with the title line open for editing. To box text you already wrote, pick the lines (for one line, just right-click it) and choose **Wrap in a box** — lines that include a heading are not wrapped. Lines inside are edited like any other line, and adding or moving a box renumbers the titles and the `[Box 1](#box-1)` links. Right-click inside a box for **Unwrap box** (removes only the two marker lines) and **Delete box**. To keep a conversation with Claude Code in the document, right-click a line (or picked lines) and choose **Ask Claude for a box**. A request — 'summarize the conversation so far and insert it as a box right after `@doc line 12`' — is pasted into the terminal, and when you press Enter Claude writes the box there: after the block that holds the line, or after the last picked line. Lectern only pastes the request; Claude edits the file. You can edit the request before sending it.
- **Notes**: **Ctrl+Alt+F** in the middle of text adds a mark there and asks for the note. The mark and the note are saved together. On a mark, the same key edits that note. Numbers follow the order of appearance and the notes gather at the end of the document. If you delete a mark, Lectern asks whether to delete the note too.
- **Figures**: pick an image file from the project; a `Figure 1. Title` caption comes with it. Copy a picture and paste it with **Ctrl+V**, or drag it in, and it is saved as a PNG in the `name-images` folder next to the document (after the current line — not while several lines are picked). Nothing is overwritten.
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

- **Inline formatting**: select text in a cell and press a key. The same key again removes it. It works in table cells too.

  | Format | Key in a cell | Whole line (outside a cell) | Source |
  |---|---|---|---|
  | Bold | **Ctrl+B** | **B** | `**text**` |
  | Italic | **Ctrl+I** | **I** | `*text*` |
  | Strikethrough | **Ctrl+Shift+X** | **S** | `~~text~~` |
  | Code | **Ctrl+\`** | — | `` `text` `` |
  | Highlight | **Ctrl+Shift+H** | **M** | `<mark>text</mark>` |
  | Text color | **Ctrl+Shift+C** | **F** | `<span style="color:red">text</span>` |

- **Highlight and text color step through their colors each time you press the key, and the last press removes them.** Highlight goes yellow → green → pink → sky blue; text color goes red → blue → green → yellow. These are the only colors, and each style shows them in a shade that reads well (dark styles included).
- **Formatting shows inside the cell.** The characters stay as the source and only their look changes — bold text looks bold, colored text takes its color, highlight gets a background, strikethrough gets a line, and markers such as `**` or `<mark>` are dimmed. Italic alone cannot be slanted there and shows as a wavy underline (it is slanted once saved).
- **With nothing selected**: the key puts the cursor between empty markers so you keep typing. If the cursor is already inside that format, the key removes it.
- **Right-click**: right-clicking in a cell opens a formatting box — formats and colors, link and footnote, **Clear formatting**, each with its key. It acts on the selected text, or on the whole text of the line when nothing is selected. The box closes and your selection stays, so you keep writing.
- **A whole line at once**: without opening a cell, pick lines (Shift+↑ ↓; for one line Ctrl+Enter or a triple-click) and press **B**, **I**, **S**, **M** or **F**. On the current line with nothing selected they do nothing. List and heading markers stay and only the text is wrapped. You can also choose them under 'Whole-line formatting' in right-click **Change this line…** / **Change picked lines…**.
- Highlight and text color carry over to PDF, print and pptx export.
- Pasting several lines puts them on separate lines. In a list they become items. One undo brings it back.
- Pasting an Excel range makes a table.

### Special characters

Insert characters you cannot type directly: the middle dot (·), dashes (— –), corner brackets (「」), the reference mark (※), arrows (→ ⇒), shapes (○ ● □ ■ ★), math (± × ≤ ≈), units and currency (℃ ㎡ ㎏ ₩ €), circled and Roman numerals (① ㉠ Ⅰ), super- and subscripts (² ₂) and Greek letters (α Σ).

- **Where**: **Ctrl+Shift+;** in a line-editing cell or in edit mode (next to Ctrl+; for a date) — it inserts at the cursor. **Special character…** in the cell's right-click menu does the same. In the reading view, **Ctrl+Shift+;** or **Special character** in the insert box (`/`) opens the current line's cell and inserts at its end (no new line is added below).
- **Choosing**: characters come in groups; the top row is the twelve you inserted most recently. Filter by name — 'arrow', 'circled', 'Celsius' (Korean names work too). Move with **← ↑ ↓ →** and the name shows on the bottom line; **Enter** inserts and **Esc** cancels. You can click as well. The names are in the language of the screen and the filter looks at both.
- The cell stays open so you can keep writing.
- **Only characters that keep the document sound**: characters Markdown reads as marks (`*` `_` `|` `#` and so on) are left out so an inserted character never becomes formatting. So are characters that look like a list or a task but are not (• ☐ ☑) and the minus sign (−), which a table does not read as a number — write lists with `-`, tasks with `- [ ]` and negatives with `-`. Characters missing from Malgun Gothic or Batang (✓ ✗ ⑯–⑳ ⁵–⁹ ☀ ✉ and so on) are left out too — they could look different on another PC, in PDF or in Word, or turn into emoji.

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

- To open it: the **Edit** button at the right end of the tab bar (left of Contents and Terminal — press it again to close; it is highlighted and underlined while on), **Edit** in the status bar, **Edit** in the code view header, **Edit this document** or **Open in the full editor** (at that block or line) in the right-click menu, or Ctrl+E. In the editor **Ctrl+Shift+K** deletes the line and **Ctrl+Shift+D** duplicates it (the same keys as in a cell — Ctrl+D is not used). It opens with the source of what you were reading at the same height.
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
- **.** opens the change window even with vi keys on (it is not vi's repeat).
- **Picking and changing**: `V` holds the current line (like the first press of a change key) and `j`·`k` extend it. On picked lines, `d` deletes, `y` copies the source, `>`·`<` change the level, `J` joins them into one line, `V` or Esc releases.
- **In one go**: `dd` deletes the line, `yy` (or `Y`) copies its source, `>>`·`<<` change its level — the same as picking it first. `>>`·`<<` change a heading's own level only (with its subsections: Alt+Shift+←·→). Lines you deleted or copied go back with `p`·`P` below / above the current line (they are kept inside the app, separate from the clipboard). Table rows go inside the table, and numbered lists are renumbered. Duplicate a line with `yyp` or `Yp`. `u` undoes; redo is Ctrl+Y.
- Two-letter commands wait one second for the next letter; meanwhile the status bar shows `vi d…`.
- One-letter line-type keys (L, N, T, Q, C and so on) are pressed after holding the line with `V` — a double press on the current line does not hold it. On picked lines numbers are counts, so 1–6 do not make headings — use **H** or **Ctrl+Alt+1~6**.
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

- Edit text on a slide with **line editing**. A line added with Shift+Enter at the end of a cell stays in the cell, and moving or deleting lines does not break cells or slides.
- **Sample text**: opening a template's sample text selects all of it, so typing replaces it.
- **Insert**: on an empty line in a cell, press **/** for headings, lists, callouts, tables, figures, charts, diagrams, math, code, a source line or a speaker note. Notes, attachments, appendices and dividers are not used on slides.
- **Formatting and pasting**: Ctrl+B, I, K and \`, pasting lines and Excel ranges, table rows and columns, and the callout menu work as in md documents and stay in the cell. Pasted pictures go in the cell, and **Ctrl+Shift+> <** change their width.
- **Source**: **F2** on math and diagrams opens a panel beside the slide to edit line by line. The cell keeps showing the result and it updates on each save. **Esc** folds it.
- **Chart values**: **F2** on a chart shows its values as a table. Edit cell by cell, add a row with **Shift+Enter** and delete one with **Ctrl+Shift+K**. The buttons below change it to bar, line, area or pie. Charts that read a file or are complex open as source.
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
- Right-click a slide and pick **Set layout…** to add that layout's empty cells. Existing cells only get new names, and text on a slide with no cells goes into the first cell. Fill them with F2.
- `<!-- links: a>b, c--d -->` draws arrows and lines between cells. The text in the cells stays editable.
- Lectern reads Marp's `paginate`, `header`, `footer`, `class: lead`, `invert`, background color, background images like `![bg right:40%](image)` and their filters, and CSS in `style:` and `<style scoped>`. It does not read `theme` (gaia and so on).

### Text size

- On the current line, **Ctrl+Shift+>** and **Ctrl+Shift+<** change that slide's tables, callouts, titles and so on by 1pt. A line like `<!-- text: table 14 -->` appears in the source, and Ctrl+Z brings it back.
- In a cell with its own size (`::: b 16`) the cell's size changes. Set the whole document with `text: title 26, table 12` in the front matter.
- The defaults are title 30, subtitle 20, body 18, table 14, box 16 (callouts). Changing style keeps these sizes. Text inside charts and diagrams follows the cell size.
- Tables below 12pt and body text below 14pt show up in Check. For slides that are read rather than shown, write `reading: true` in the front matter (limits 10pt and 12pt).

### Structure and Check

- **Structure** in the status bar shows cell head lines and directive and note lines as tags. Click a tag and press F2 to edit that line. This is how to change a cell's look or the layout.
- When content overflows, pictures and charts shrink to fit the cell. Text does not shrink; it is cut off and gets a red dotted line.
- Grammar slips are marked too: cell names, a missing `:::`, typos in directives and words, bad grids, unclosed comments and code blocks, text right above `---`, and unresolved `**`.
- Some things are measured on screen: text close to its background, code and tables cut off at the side, missing pictures, charts that could not be drawn. Text over a photo cannot be measured, so look at it yourself.
- **Check** in the status bar lists them, and picking one goes to that line. **Paste the list into the terminal** lets you ask Claude to fix them.

### Viewing and presenting

- Clicking Lectern slides opens a separate slide window. If it is already open, it comes to the front. The terminal is the main window's.
- The slide window has its own style, **Presentation** by default. This style is how the slides look on screen. It does not change the pptx style.
- **Present** in the status bar (Shift+F5) or ▶ on a slide shows one slide at a time across the window. Use → ← Space PageDown PageUp, click or the wheel; **N** shows speaker notes, **F** full screen, **Esc** ends.
- **View as document** in the status bar opens the cells and reads on like an ordinary document.
- In the slide window, right-click the margin and choose **Save as PDF…** for a PDF with one slide per slide-sized page in the screen's colors (hidden slides and speaker notes are left out). **Print…** also prints one slide per page.

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

### Convert to html

Press **Convert to html** in the status bar. An impress.js presentation html file appears next to the document. The reader opens it in a browser to present it. The slides sit on one canvas and the view moves between them.

- **Arrangement:** **Grid** starts a new row at each cover or section slide (`lead` slides) and wraps after 4 slides. You can also pick **One row**. The map in the window shows each slide number in its place. `impress: line` in the front matter makes that the first choice.
- **Placing a slide yourself:** Write `<!-- impress: x=0 y=2400 rotate=90 scale=2 -->` on a slide to place it there. Only the axes you write change. The slide window does not change. **Ask Claude to arrange** puts a request into the terminal to place the slides along the story (Enter is not pressed).
- **Overview:** When on, a last slide shows all slides on one screen.
- **Presenting:** → ← Space, PageDown and PageUp move; **Home** and **End** go to the first and last slide. **P** opens the presenter console (notes, next slide, clock) in a new window.
- **One file:** Images, styles, math fonts and impress.js all go inside the file. It opens without the internet and asks nothing from anywhere, so you can mail or message it. Only internet images stay as addresses, loaded by the reader's browser.
- **Left out:** Hidden slides, videos and sounds. Links to other documents in the project stay as text. `class="step"`, `notes` and `substep` in HTML slides are names impress reads as slides and notes, so they are removed in the file.
- **Safety:** Only impress.js and its start line may run in the file. Scripts in the document do not run in the reader's browser.
- **Open in browser:** After converting, **Open in browser** opens only the file Lectern just made, in your default browser.
- **In Lectern:** It shows in the document list as an html document. Lectern does not run a document's scripts, so the slides appear top to bottom like a document, with their notes.
- Colors and fonts follow the style you picked. An html of the same name is never overwritten; a new name like `Report 2.html` is used. The md is the source, so convert again after editing.

### Asking Claude

Sample — section 12 of [guide 09, Lectern slides](../../samples/guide/09-Lectern-슬라이드.md), 'Working with Claude Code': installing the skills, example requests, the request menus and the order of polishing together.

Claude Code skills move a pptx into Lectern slides and build slides from a pptx. They come with Lectern and are installed only when you ask. In Settings, under **PowerPoint and Word skills**, use **Copy request for Claude Code** (or the terminal button next to it). Claude explains the skills and asks before installing. The same request also installs the skill that makes Word files from md documents (`lectern-to-docx`) — the app's **Save as Word…** works without installing it.

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

More examples are in `_internal\skills\README.md` in the program folder. The guide Claude reads is `_internal\web\help\slides.en.md` there.

### Samples

[slides/README.md](../../samples/slides/README.md) in the project opened by **Open samples** (Shift+F1) is the way in ([slides/README.en.md](../../samples/slides/README.en.md) in English). If you are new to slides, read [guide 09](../../samples/guide/09-Lectern-슬라이드.md) before it (in Korean) — the content of the slide samples written out as a detailed plain md document, ending with links to the samples. Then go through them in this order.

| Order | Folder | What |
|---|---|---|
| 1 | <code translate="no">slides/기초/</code> | First look, cells and layouts, making slides from templates, key practice |
| 2 | <code translate="no">slides/상황별/</code> | Ten model decks for situations like an executive report, comparing options and market analysis. Each finished deck has a process document |
| 3 | <code translate="no">slides/복잡한-배치/</code> | Ten layouts with many cells, like dashboards, magazine pages, process maps and Gantt charts |

The installed samples are read-only, so follow along in your own project.

## Reading code

- Click a file once in the 'Code' list (or press Enter) to show it in the main area with line numbers and language colors. It is never run. To edit it, use F2 (line editing) or Ctrl+E (the full editor).
- The contents on the right list classes, functions, methods and divider comments such as `# ---- drawing ----`; click one to jump to that line. Config files list their keys and sections.
- The **Open in external editor** and **Copy all** buttons sit at the top. Right-click a line for Copy line, Copy location, Open in the full editor and Open this line in external editor.
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
- Row numbers are the source line numbers. Right-click a row for Copy line (the source line) and Copy location.
- CSV files saved by Excel (CP949) and 'Unicode text' (UTF-16) are read too (the encoding shows in the status bar). Lectern only shows them — to edit one, double-click it to open the default app.
- Up to 2,000 rows are shown; filter to narrow down larger files (counts and stats use all rows).

### Excel files

Click an Excel file (`xlsx`, `xlsm`) once in the 'Other files' list, or right-click it and choose **Show in code view**, to view it in Lectern. Double-click opens it in Excel as before.

- It shows as a table like CSV — filter, sort, stats and the header option all work, and the **sheet tabs** under the header switch sheets (hidden sheets in italics).
- Column names start with Excel's column letters (A, B, C…) and row numbers are Excel's row numbers. Rows without values are left out.
- Cells show what Excel shows — number formats such as thousands separators, percentages, dates and decimals are followed, and formula cells show the calculated value (hover to see the formula). Colors, fonts and merged cells are not shown.
- Right-click a cell for **Copy this cell** (with its name, such as B3), **Copy this row** and **Copy location** (`@data/prices.xlsx sheet 'Q1' line 3`). **Copy all** copies the current sheet as tab-separated text that fills the cells when pasted into Excel. You can also focus rows and send them to Claude with Shift+→.
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
- **Copy location** copies something like `@docs/report.md lines 40-52`. Pasted into a Claude Code prompt, it points Claude at that exact part.
- If you right-click with text selected, 'Copy selected text' appears at the top. When the selection is within one line, the formats and the clip and send items come with it (see 'Selecting text and formatting'), and the block's usual menu is **Menu for this block…** at the bottom.
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
- Right-click a document and choose **Send to new note** to turn that text into a note, with where it came from (`@path lines 12-20`) below it. Click that to go back there. A note sent from selected text, and **Add a note** on a highlight (see 'Highlighting to come back later' above), find their text again even if lines have moved; a note sent from a block goes to its line number.
- Notes are stored as Markdown in one file in the project folder, `.lectern/notes.md`. It is created when you first write a note and does not appear in the tree or search. It moves with the folder, and Claude Code can read it as `@.lectern/notes.md`.
- To keep notes out of a git repository, especially a public one, add `.lectern/` to `.gitignore`.
- If the file changed elsewhere in the meantime, Lectern reads it again and merges. Notes are off in view-only projects such as the samples.

## Work management

Put one `WORK.md` at the top of a folder, and Lectern remembers that folder and gathers the status, due dates, to-dos and events of many folders in one **work board**. While Lectern is running it also shows alerts inside the window. WORK.md is plain Markdown that you can write and edit without Claude, and Claude may read and write it too.

Sample — [11 Work management](../../samples/guide/11-업무-관리.md) (in Korean): the sample WORK.md at the top of the samples and a walkthrough, asking to fold in the planning notes (6-1), the work tree, changing from the top, kanban and the calendar (7–10), and trying them on the work tree sample (11).

### WORK.md

| Part | What goes there | Read by the work board |
|---|---|---|
| Front matter | `status` (planned, active, at-risk, blocked, on-hold, done, dropped), `priority` (high, medium, low), `due` (YYYY-MM-DD), `start` (YYYY-MM-DD — the start in the Gantt chart and calendar) | Yes — status, priority, due date, start |
| `# Title` | The task name | Yes |
| To-dos | `- [ ] Draft chapter 3 (11/14)` — the parentheses at the end are the due date | Yes — checkbox and due date |
| Events | `- 2026-11-12 14:00-15:00 Report to the lead`, `- 2026-11-20 all-day Workshop` | Yes — today's events and alerts |
| Planning notes | Whatever comes to mind — to-dos and dates too | No — moved out when you tidy up |
| Current state, decisions, log, materials | Anything | No |

- Section names and order are up to you. Lectern reads only the front matter and the shape of to-do and event lines.
- A due date without a year, `(11/14)`, is read as the nearest such date to today. The Korean values work too.
- Dates are normally written `2026-11-14`, but `2026.11.14`, `2026/11/14` and `2026-11-5` are read too. Upper-case keys (`Status`) and a space before the colon also work.
- Change status and due date by right-clicking the front matter and choosing **Edit document info**, tick to-dos with their checkboxes, and add log lines with line editing.
- Subfolders can have their own `WORK.md` too. See 'The work tree' below.

### Planning notes

The `## Planning notes` section of a work card is where you jot things down as they come. In the templates it sits right under the one-line summary. Lectern does not read this section, so a `- [ ] …` or `- 2026-11-25 draft meeting?` written there does not show on the work board, in alerts or among the lines to check. The section runs to the next heading of the same or a higher level (such as `## To do`). The Korean section names used by the Korean templates work the same way.

There are two ways to tidy it up.

- **Yourself**: read the notes, move items to the to-do, schedule and decision sections, and delete the notes you moved.
- **With AI**: open the WORK.md, right-click the margin and choose **Ask to fold in the planning notes** — the request goes into the front terminal (Enter is not pressed). Following the writing guide, the AI moves items to the to-dos, schedule, decisions and current state, skips anything already there, asks when a date is unclear, and adds one line to the log saying what it folded in. It does not edit or delete the notes — removing notes that have been folded in is up to you.

### Making a work card

Right-click a project tab or an empty spot of the document tree and choose **Make work card…**. For a subfolder, right-click that folder in the sidebar and choose **Make a work card in this folder…**. A folder without documents is not in the document tree, so right-click it in the Other files or Code list instead. Set the kind (table below), title (the folder name at first), due date and priority and press **Create**: `WORK.md` is created from the template and opened. If it already exists the menu says **Open work card**. The folder joins the work folder list.

| Kind | Template | Chosen by default |
|---|---|---|
| Task | Planning notes, current state, to-dos, schedule, decisions, log, materials; status 'planned' | Top of a project |
| Group · overview | Same sections, status left empty — worked out from the sub-tasks | (when you pick it) |
| Small task | Only planning notes, to-dos, schedule and log; status 'planned' — something like one issue report | Subfolders |

Write the due date as `YYYY-MM-DD` (`2026.11.20` is read too) or pick it with the calendar button next to it or **Ctrl+;**.

### The work tree — folders inside folders

The WORK.md of a project folder oversees everything, and the WORK.md of a subfolder covers one piece of work in it (for example one issue report). In between you can have a group folder (for example 'Issue reports' — several sub-tasks working as one).

```text
2026 metals research/      WORK.md   overview
├─ issue-reports/          WORK.md   group
│  ├─ 01-copper/           WORK.md   small task
│  └─ 02-lithium/          WORK.md   small task
└─ regular/                (no WORK.md — skipped)
   └─ weekly/              WORK.md   directly under the overview
```

- **The parent is the WORK.md of the nearest folder above.** Folders without a WORK.md are skipped.
- **Gathered at the top.** Each file holds only its own work; Lectern gathers them in three places — the work board, the folder overview of an overview or group folder ('Work in this folder'), and the **Sub-tasks** panel below a parent WORK.md when you open it (a panel that is not in the file and does not print).
- **An empty status is worked out from the sub-tasks.** If any sub-task is blocked the group is blocked, then at risk, active, planned and on hold in that order; when all are finished it is done. Worked-out values carry a `*`. A status written in the file wins.
- **What comes up**: rows show a summary such as '5 sub-tasks · active 3 · blocked 1' and the earliest due date among open sub-tasks ('next 11-20'). Sub-tasks' to-dos, events and alerts come with their path, such as 'Overview › Issue reports › 02 Lithium'.
- **Needs attention**: the top of the work board gathers items needing attention at any depth of the tree, including mismatches in the tree — a parent marked done while sub-tasks are open ('Sub-tasks still open'), and a sub-task due later than its parent ('Sub-task due later').
- **Expanding**: three levels show at first; ▸ expands and folds. Finished sub-tasks fold behind 'Show n done or dropped'.
- **Clicking a sub-task** opens its WORK.md in the project tab that contains it, without opening the subfolder on its own.
- **Remembering**: opening a project finds the WORK.md files in its subfolders and adds them to the work folder list (not inside hidden or excluded folders). They stay on the board after the tab is closed, and while closed Lectern still reads only those WORK.md files. If you rename or move a subfolder while the project is open, the next reading follows it.

### Changing from the top

Choosing something on a row of the tree (work board, folder overview, Sub-tasks panel) changes **one line of that task's WORK.md**. The changed file gets an amber dot in the tree.

| Where you choose | Line that changes |
|---|---|
| Status cell → status menu (groups also have 'Clear — work out from sub-tasks') | `status:` in the front matter |
| Due cell → calendar | `due:` in the front matter |
| Priority cell → menu | `priority:` in the front matter |
| To-do cell (2 / 5) → checkbox in the expanded list | `[ ]` ↔ `[x]` on that to-do line |
| Due button in the expanded list → calendar | `(YYYY-MM-DD)` at the end of that to-do line |
| 'Add a to-do' field in the expanded list → Enter | One `- [ ] text (due)` line at the end of the 'To do' section |

- Right-click a row for **Open this task · Change status · Change due date · Change priority**.
- The text of a to-do or of the log is changed by opening that WORK.md (the 'line n' button in the expanded list).
- The file is read again right before the change. If that line or the file changed in the meantime (elsewhere, or by Claude), nothing is written; the view is redrawn and you are told — just choose again.
- Status values are written in the words the file uses — a file with English values such as `status: active` gets English.

### Kanban

Choose **Kanban** above the tree (**List · Kanban**) and the leaf tasks (tasks without sub-tasks) become cards in five status columns: planned · active · watch (blocked, at risk) · on hold · done, dropped. If a leaf task has an empty or unreadable status, a 'No status' column is added. Groups are not cards; they show as the path above each card.

- A card shows the path of the tasks above, the title, status, due date (D-n), priority, to-do progress (3/5) and the next to-do.
- **Drag a card to another column** to change the status in that task's WORK.md. The watch column asks for blocked or at risk, the done column for done or dropped.
- Click a card to open its WORK.md. With the keyboard: Enter or Space on a card opens it, the menu key opens its menu (open, change status, due date or priority).
- A column shows up to 40 cards; the rest is given as a count.


### Gantt chart and calendar

Choose from **List · Kanban · Gantt · Calendar** above the tree. Dates come from `start:` (start) and `due:` (due date) in each WORK.md's front matter.

- **Gantt**: the rows are the same work tree as the list (same expanded and collapsed rows). On the right are date bars — a bar from start to due, a point (◆) on the day when there is only one date, and a thin bar from the earliest to the latest day of the sub-tasks for a group. Colours match the kanban lanes, and the red vertical line is today. Ticks are weekly when the span is within 70 days, monthly otherwise.
- Click a bar or a name to open that WORK.md. Click the **Start** or **Due** cell to pick a day in the calendar; it is written to that work's front matter. Dragging to change dates is not supported — a wrong drag would change the file straight away.
- **Copy as Mermaid Gantt**: copies the work shown as Mermaid Gantt text. Paste it into a md document and a schedule chart is drawn there — handy for putting a schedule in a report. Each top-level work is a section; done work is faded, blocked and at-risk work is red, and active work is highlighted. Work without dates is left out and you are told how many.
- **Calendar**: a month grid (weeks start on Sunday) with work spanning more than a day drawn as multi-day bars, and below them each day's due dates (■), starts (▶), to-do due dates (☐) and events (•, with the time). Finished work shows events only, and the work board's calendar also shows the common WORK.md's events and to-dos. Move between months with ‹ · This month · ›.
- **Click a date number** to open Add event on that day. In a group's folder overview or the sub-tasks pane, that work is chosen as the target. Click an item to go to its line in the WORK.md.
- An unreadable `start:`, or a start after the due date, shows among the lines to check.
### Calendar

Wherever you enter a date — the due date of a work card, the date of an event, due dates in the tree — a calendar opens. While editing a document (the line-editing cell or edit mode), **Ctrl+;** puts the day picked in the calendar at the cursor as `YYYY-MM-DD`. **Date** in the insert menu (/) does the same.

| Key | Does |
|---|---|
| ← → | A day |
| ↑ ↓ | A week |
| PageUp · PageDown | A month |
| Home · End | Start · end of the week |
| T | Today |
| Enter | Pick |
| Esc | Cancel (closes only the calendar) |

There are buttons for today, tomorrow, this Friday and next Monday, plus **Clear** when changing a date. Days with due dates, to-do dates or events have a dot.

### Work board

The **Work** button in the toolbar or **Alt+W**. It opens the common folder as a tab and shows at the top of that folder's overview.

- **Common folder**: an ordinary folder for a WORK.md with events and to-dos outside any task, and for weekly and monthly reviews. Pick it the first time you open the work board (for example `Documents\Lectern work` — you can make a new folder in the picker). Make the common WORK.md with **Make the common WORK.md** on the board.
- **Needs attention**: blocked or at risk, overdue or due within 3 days, active but WORK.md unchanged for over 14 days, and mismatches in the tree — gathered at the top with their path, at any depth of the tree.
- **Work tree**: one row per remembered task — status, task (title, folder name and a sub-task summary), priority, due date (D-n), open to-dos, updated. Active and planned come first (earliest due first), then on hold, then done or dropped (folded); sub-tasks are indented below their parent. Click the status, due, priority or to-do cell to change it in place (see 'Changing from the top' above); click the title to open the WORK.md. **List · Kanban** above switches to the kanban.
- **To-dos with a due date** (overdue, today, this week) and **today's events**: those from the common WORK.md are marked 'Common'. Click one to go to its line.
- **Lines to check**: lines that could not be read because of a typo or something deleted are not dropped but gathered here. Click one to go to that line of that WORK.md. This covers a status that is not a known value, a misspelled key (`stauts` — the right key is shown), a due date or to-do date that cannot be read (`(11/31)`, a missing parenthesis), a mistyped checkbox (`- []`, `-[ ]`), an event on a date that does not exist (`2026-11-31`), an unreadable time (`25:00`, `14:00-1500` — kept as an event without a time), an event without a description, and front matter whose closing `---` is missing. The task row shows 'n lines to check', and the start summary mentions them.
- **Folders that could not be read**: listed when a folder moved, was deleted or its drive is not connected, or when WORK.md is not UTF-8 (for example ANSI from an old Notepad) or is over 2MB. **Remove from list** removes it (the files stay).
- If the common folder moved or was deleted, opening the work board asks you to choose it again. The list of task folders stays as it is.
- Lines to check, to-dos with a due date and today's events show up to 50 items; the rest is given as a count.
- Closing a tab keeps the folder on the board. Lectern reads only the `WORK.md` of a remembered folder, not its other files.
- Opening a folder with a WORK.md remembers it. To add one without opening it, use **Add folder** — if the chosen folder has no WORK.md, Lectern asks whether to open it and make one. Folders inside the Lectern program folder (the samples) are not remembered.

### Adding events

**Add event** on the board or **Alt+S**. Set the date (today, tomorrow and weekday buttons, the calendar button or Ctrl+;), time (end time, all day), what, and where to add it (common or an unfinished task — in tree order, sub-tasks with the path of the tasks above), then press **Insert**. One line goes at the end of the 'Schedule' section of that WORK.md (the section is created at the end if missing). The target starts as the deepest task containing the document or folder you are looking at — a sub-task when you are reading a document in its subfolder. Enter adds and Esc cancels.

- An empty description or an end time before the start is not added; the reason is shown. Adding the same event twice is not prevented.
- **Undo** at the bottom right takes it out again. If the file was edited after that, it is not undone, to keep your edit, and you are told.
- If the file changed or was deleted while the window was open, nothing is added and you are told. If you were editing the same WORK.md in edit mode, saving in the editor tells you it changed and asks.
- The 'Schedule' section is a `## Schedule` or `### Schedule` heading (the Korean section name works too). Something after it in parentheses or after a colon is fine, as in `## Schedule (November)`; a task title such as `# Schedule cleanup` is not the section.

You can also write it in WORK.md — on the last line of the 'Schedule' section press Shift+Enter for a new line and type `- 2026-11-14 10:00 Team meeting`. Repeating events (every Monday) are not there yet; write one line per date.

### Alerts

Shown at the bottom right of the window while Lectern is running. They stay until you close them.

| Alert | When |
|---|---|
| Today's work | Once at start (again when the date changes) — overdue, due today or within 3 days, to-dos overdue or due today, today's events, lines to check. Nothing is shown when there is nothing to report |
| Starting soon | Once, 10 minutes before an event with a time — events that already started are not announced (waking from sleep does not bring a pile of old alerts) |
| Today's record | Once after 17:30 — active tasks whose WORK.md did not change today |

- Windows notifications and the notification area are not used. If the window is hidden, the alerts are waiting when you come back. With Lectern closed there are no alerts.
- Turn them off with **Work alerts** in Settings. Shown alerts are not remembered, so Today's work appears again after a restart.

### With Claude

WORK.md works the same when Claude reads and writes it. Give Claude the writing guide with **Teach Claude Code about Lectern** in Settings and it writes the same format. For example: "Make a WORK.md for this folder", "Take the to-dos from the meeting notes and add them to WORK.md", "Write what I did today in the log section". Hand over planning notes with **Ask to fold in the planning notes** in the document's right-click menu (see 'Planning notes' above).

## Terminal

- The **Terminal** button at the right end of the tab bar, or Ctrl+\`, opens a terminal to the right of the main area. Windows PowerShell starts in the current tab's project folder, and each tab has its own shell.
- **Several terminals**: **+** in the terminal header opens another terminal for the same project (up to 5 per project — for example terminal 1 for Claude Code and terminal 2 for other commands). With the terminal below the document, click [1 PowerShell] [2 PowerShell] in the header to switch; on the right they are all shown as in 'Stacked terminals' below. Reloading the window keeps the running terminals.
- **Stacked terminals**: when the terminal is on the right of the document and there are two or more, they are stacked top to bottom instead of tabs, all visible. Terminal 1 is at the bottom and higher numbers go above it. The height is split evenly; drag the border between two terminals to change it (double-click the border to even them out again — adding or closing a terminal does too). Each one has a header with its number, shell name and ×, and clicking a terminal picks it (↻ restart uses it — F6 visits them all in order from terminal 1). With the terminal below the document they stay tabs as before.
- **Ending a terminal**: when you no longer need a terminal, click the × on its tab (or middle-click the tab). This ends its shell and the programs started from it, asking first if a program is running. It works even when there is only one terminal; ending the last one hides the panel, and opening it again starts a new shell as terminal 1. In a narrow panel, the other tabs get shorter names and their × appears when you point at them.
- The × at the right end of the header (or Ctrl+\`) only hides the panel — the shell keeps running, so reopening it continues where you left off. The ↻ button in its header restarts the shell.
- Keys typed in the terminal go to the shell. Use app shortcuts such as Ctrl+P, Ctrl+F or F1 after clicking the main area (Ctrl+Tab moves to the next tab even inside the terminal).
- **F6** moves keyboard focus one place at a time: **document → terminal 1 → 2 → 3 … → sidebar → document**. **Shift+F6** goes the other way. It works inside the terminal too.
  - It visits every terminal of the project in number order (stacked or as tabs). A closed terminal opens on the way, at terminal 1.
  - In the sidebar it goes back to where you last were there (the search box, the selected row). A hidden sidebar (Ctrl+B) is skipped. A view-only project (the samples) and a separate window have no terminal, so F6 moves between the document and the sidebar.
  - Coming back to the document returns to where you were — the editor in edit mode, the same spot in the box while line editing (the box stays open and unsaved). Focus left on the contents or the toolbar after clicking them counts as the document.
  - While the terminal is open, an accent line shows where keys go (the terminal header, or the document tab row).
- Select text with the mouse, then press Ctrl+C or right-click to copy; press Ctrl+V or right-click to paste. With nothing selected, Ctrl+C stops the running command.
- Drag the edge to resize the terminal (double-click to reset).
- **Position**: in a wide window the terminal opens to the right of the document; in a tall window (a portrait monitor, a window snapped to half the screen and so on) it opens below the document. When it is below, drag the edge to change its height. The position button in the terminal header switches between right and below and keeps it there; set 'Terminal position' back to 'Auto' in Settings.
- **Paste into the terminal**: in a right-click menu, the **▣ Terminal** button on the right of a copy item puts that text into the current tab's terminal and shows a notice such as 'Put into terminal 1' (clicking the item name only copies). The terminal opens if needed. With several terminals the default is the first one (the lowest number — usually terminal 1, the one opened first), which is then shown, so run Claude Code in terminal 1 (to send to another number, see 'Send by number' below). Enter is not pressed — check the text and press Enter yourself. For several lines Lectern asks first, because at a PowerShell prompt each line may run as a command (programs that turn on paste mode, such as Claude Code, Codex, Antigravity and OpenCode, are not asked about — the lines go into the input box without being sent).
- **Send by number**: to send to another terminal, open the menu and **hold a number key (1-5)** while clicking ▣ Terminal or 'Send to Claude' — '→ terminal 3' shows above the menu. On the keyboard, **Shift+number** (focus goes to the terminal) and **Ctrl+Shift+number** (focus stays in the document) put the location of the current line into that terminal. With stacked terminals the header of the one that got it lights up briefly. If there is no terminal with that number, nothing is sent and you are told (none is created). Inside a line-edit box or a terminal, Shift+number just types the character (! @ # …).
- The terminal colors follow the document style. For an always-dark terminal, turn off 'Match terminal colors to style' in Settings.
- Change the terminal's text size under 'Terminal text size' in Settings (10–24, default 14). Open terminals and the terminal grid change right away.
- Closing a tab ends its shell. If a program started from the shell is still running, Lectern asks first. Closing Lectern ends all shells.
- **Stuck program warning**: if a program started from the shell gets stuck while starting (this happens when security software on a company PC, such as DRM, blocks programs from starting — Claude Code calls git and then stops responding to any input), a red strip appears under the terminal header after about 10 seconds and the ↻ button is highlighted. Ctrl+C does not end such a program, and often neither does Task Manager, so press **Restart** in the strip. It ends the shell and the stuck program and opens a new shell. In Claude Code, run `claude --continue` in the new shell to pick up the conversation (`codex resume --last` in Codex, `agy --continue` in Antigravity, `opencode --continue` in OpenCode). If the terminal belongs to a tab you are not looking at, a notice appears once.

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
5. To point at one part of a document, right-click the text and choose **Copy location**.
6. To have Claude Code write documents that read well in Lectern, paste **Teach Claude Code about Lectern** → **Copy request for Claude Code** from the settings into Claude Code (the terminal button next to it pastes into the current tab's terminal). Claude Code reads Lectern's writing guide (`web/help/writing.en.md`) and writes the rules where you chose — with **All folders (personal)** (the default) the formatting rules go into one personal rule file, `~/.claude/rules/lectern.md`; with **Only this folder** that project's `CLAUDE.md` gets who reads that folder's writing and what for. Put it in all folders once, and send it again with Only this folder just for folders whose readers are clear. The samples' `CLAUDE.en.md` shows the folder side.
7. For writing people read — reports, review notes — see **Report writing** below: the writing style, the polish check and your style note.

### Report writing — writing style, polish check, my style

Sample — [14 Report writing](../../samples/guide/14-보고서-글쓰기.md) (in Korean): the same request written as bullet points and as narrative, a practice report for the polish check, and how a style note is made, with results from real runs.

Claude Code's default role is a developer. Even when it writes a report, developer habits creep in: file paths in the body, "**Bold label** — explanation" lists, arrows, "as follows:". Lectern helps in three ways.

| What | What it does | Where |
|---|---|---|
| Writing style | Claude writes like a practitioner of that kind of writing — choose Research writing, Business report, Academic writing or Plain explanation | Settings **Writing style** → **Choose a style…** (install once, choose where it is on) |
| Polish check | Shows errors and hard-to-read spots in your own writing as a table first, then fixes only what you pick | Right-click a document's margin → **Ask for a polish check** |
| My style | Keeps a note of what to keep and which habits not to copy, from writing you wrote yourself | Right-click a document's margin → **Send as a style sample**; Settings **My style** |

In all three, Lectern only puts a request into the terminal (Enter is not pressed). Files are changed or installed only after Claude shows what it will do, asks, and you say yes.

**Writing style — choose one, install once, choose where it is on**

Lectern includes four writing styles. All four drop developer and AI habits and reread when done; they differ in the standard they write to.

| Style | For | What is different |
|---|---|---|
| Research writing | Reports, review comments, analysis memos | The reader and the decision first, evidence beyond the folder and on the web, a standard for each kind of document |
| Business report | One-page reports for approval, meeting papers | Bullet points by default, the conclusion and what the approver must do at the top, numbers against plan or last year, who does what by when, attachments |
| Academic writing | Papers, research reports, conference papers | Cites only sources it has checked (never invented), matches the strength of a claim to the evidence, units and uncertainty, limits |
| Plain explanation | Manuals, guides, training material | What the reader will be able to do first, short sentences and plain words, one action per numbered step, common snags in advance |

1. Open the chooser with **Choose a style…** under **Writing style** in the settings (**Ctrl+,**). On the left are the four included styles, **Claude Code default** (no style), **My writing styles** (output styles in your personal folder `~/.claude/output-styles` that are not Lectern's) and **Make a new style** — Claude Code default and My writing styles appear only when the AI tool is Claude Code. On the right you see what the style is for, what changes, **samples** (the start of what Claude Code actually wrote for the same request with no style and with that style — written in Korean), whether it is installed, and the style that applies in this folder now. **View source** shows the whole style file. **Use this style** takes you back to the settings with the chosen style. **Claude Code default in this folder** under Claude Code default switches where it is on to "Turn off in …" (only when a folder is open); choosing a style afterwards switches it back to "Turn on".
2. With a folder where you write reports open (the buttons carry the open folder's name in place of "this folder"), choose where it is on under **Writing style** in the settings (**Ctrl+,**) — **Turn on in this folder** (the default), **Turn on in all folders** or **Turn off in this folder**. **Files that change** below shows, with full paths, the chosen style's file (in `~/.claude/output-styles/`) and the settings file that gets the value, and also the style that applies in this folder now.
3. Press the terminal button and Enter. Claude says how things stand and asks whether to install the style file (if it is missing or different) and turn it on. If you say yes it installs it and writes just the one value `"outputStyle"` in that settings file. Both files are inside a `.claude` folder, so Claude Code asks once more before writing — allow it if it matches what Files that change showed.
4. If the style file was newly installed, quit Claude Code (`/exit`) and start it again.
5. Do not turn it on in folders where you write code: all four of Lectern's writing styles drop the development instructions (stay in scope, check after changing) — your own writing style does unless its settings at the top have `keep-coding-instructions: true`. Choosing **Turn on in all folders** shows this warning. If you turned it on in all folders anyway, open a folder where you write code and send **Turn off in this folder**, or pick the default with `/output-style` in Claude Code (a folder's value comes before the all-folders value).
6. After updating Lectern, if Files that change shows 'Change — Different from Lectern's', install again with the same request.

One style applies in a folder. You can turn on different styles in different folders — Research writing in a reports folder, Business report in a folder of approval papers: the style files sit side by side in your personal folder and only the value that turns one on differs per folder. **My writing styles** are only turned on (they are already in your personal folder). The copy and terminal buttons of **Make a new style** put in a request for Claude to build a style from the closest of the four, show the draft, ask and save it in your personal folder — add what you write at the end. After saving, open the settings window again and it appears under My writing styles; restart Claude Code for it to use it.

With Research writing (the other three share the developer and AI habits and the reread):

- **It writes to the kind of document.** Narrative in paragraphs (the first sentence is the claim); bullet points with the conclusion in the top item and the evidence under it. Bullet points are not treated as bad writing. Add "as bullet points" or "as narrative" to the request and it writes that way.
- **It drops developer habits.** No file paths, code formatting, bold-label lists, arrows or task-report phrasing in the body; sources go by document name in a closing sources section.
- **It cuts AI habits.** Repeated frames ("First, ... Second, ..."), "Moreover" chains, a summary sentence at the end of every section, empty modifiers.
- **It writes headings as the section's claim** ("June prices sit at the top of the forecast range"), so the headings alone carry the argument.
- **It keeps to the length.** In the PDF layout one A4 page holds about 500 words of narrative, about 400 in bullet form.
- **It rewrites awkward wording from the material** and leaves quotations and the values of numbers as they are.

Adding the reader, the purpose, the kind of document and the length to the request changes the writing most. For example: "So the purchasing manager can decide when to buy in Q3 — bullet points, one A4 page. Write it straight away, no outline." For a long piece Claude first shows an outline of the key claims and page split, then stops.

**Polish check — fix your own writing, by choice**

1. Right-click the margin of a md document you wrote (or edited) and choose **Ask for a polish check**. For a few lines only, pick the lines (Shift+↓) or focus the section (Alt+H), right-click and choose **Ask for a polish check of this range**.
2. Press Enter in the terminal. Before changing anything Claude shows a table: number, group, where, original, proposed, why.
3. Say what to apply: "errors only", "1, 3 and 7", "everything but preferences". Only the picked spots change; every other character stays. The changes show in Lectern right away.

| Group | What | Examples |
|---|---|---|
| Error | Only one right fix | spelling, a word in the wrong sense, two words swapped so the sentence says the opposite |
| Hard to read | Not wrong, but the reader stumbles | redundancy, nominalisations, long sentences with tangled conditions, unexplained abbreviations |
| Preference | Both are fine | two accepted forms, set phrases that are convention in some kinds of document |
| To check | Content, not wording | numbers that disagree, claims without visible support — reported, never changed |

Quotations (in quotation marks or quote blocks, sentences taken from regulations), the values of numbers, names of institutions and laws, and words that are used correctly are left alone. Habits that keep coming back are listed at the end under "Came up often". If you just say "polish this", Claude tends to rewrite content as well without asking; the polish check request makes it show the table first.

In a view-only project such as the samples folder (inside Lectern's program folder) no terminal opens, so the request is not pasted. Copy the sample practice report into your own folder to try it.

**My style — a note of what to keep and which habits to drop**

1. Right-click the margin of something you wrote yourself (not with an AI) and choose **Send as a style sample**. To send several at once, add `@paths` after the request from **My style** in the settings (right-click a document → **Copy location**). Old reports written in Word or saved as PDF work too.
2. Claude shows a draft note in three groups. Nothing is saved yet.
   - **Keep**: conventions the reader expects — register, terms, how numbers, units and dates are written.
   - **Lean towards**: what you like to do — sentence length, where the conclusion goes. Used only when the kind of document and the reader match.
   - **Do not copy**: habits that make writing hard to read — redundancy, nominalisations, very long sentences. Not copied when writing, and looked for first in a polish check.
3. Tell it what to move or drop ("this is how I write, follow it", "drop this"), then say yes to save. Claude Code keeps it in one personal rule file, `~/.claude/rules/my-voice.md`, so every folder and every writing style uses the same note. If, as in earlier versions, the writing style file ends with a "My style" section, it asks whether to move it into this file. That file is inside the `.claude` folder, so Claude Code asks once more whether it may change it — allow it. Restart Claude Code so it reads the note.
4. Every new sample adds to the note. Only what shows up in two or more samples is noted, and examples are written fresh rather than copied, so figures and names from a confidential sample do not leak into the note.
5. Each item says which kind of document it was seen in ("Memos:", "Narrative reports:", "All:"), so a memo's register does not spill into a report, and for a kind the note does not cover only the "All:" items (terms, notation of numbers and dates, how sources are given) are used.

Your style does not override the basics of report writing. Conventions such as terms and register are kept, but habits that make writing hard to read are not copied. Rules that differ by folder (an institution's template, a register) belong in that folder's `CLAUDE.md`.

### Using Codex, Antigravity or OpenCode

The terminal runs any program, so you can start `codex` (OpenAI Codex CLI), `agy` (Google Antigravity CLI) or `opencode` (OpenCode) instead of `claude`. Sending locations while you read (Shift+→, Shift+number) and seeing edits at once work the same. This manual says 'Claude' for short, but it applies to all four tools.

- Choose Claude Code, Codex, Antigravity, OpenCode or Several under **AI tool** in the settings. Names on screen follow it ('Send to Codex', 'Copy request for Codex'), and requests name that tool's file and folder. Lectern does not run the tool — you start it in the terminal yourself.
- What differs by tool:

| | Claude Code | Codex | Antigravity | OpenCode |
|---|---|---|---|---|
| In the terminal | `claude` | `codex` | `agy` | `opencode` |
| Project instruction file | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| Personal skills folder | `~/.claude/skills` | `~/.agents/skills` | `~/.gemini/config/skills` | `~/.config/opencode/skills` |
| Project skills folder | `.claude/skills` | `.agents/skills` | `.agents/skills` | `.agents/skills` |
| Lectern summary (all folders) | `~/.claude/rules/lectern.md` | a section of `~/.codex/AGENTS.md` | a section of `~/.gemini/AGENTS.md` | a section of `~/.config/opencode/AGENTS.md` |
| Writing style | Output style (choose where it is on) | A 'Writing' section in the personal instruction file or `AGENTS.md` | Same | Same |
| Style note | `~/.claude/rules/my-voice.md` | A 'My style' section in the personal instruction file | Same | Same |
| Continue a conversation | `claude --continue` | `codex resume --last` | `agy --continue` | `opencode --continue` |

- With **Several**, the name becomes 'AI' and requests list each tool's file and folder. If one project uses several tools, keep the rules in `AGENTS.md` and leave just the line `@AGENTS.md` in `CLAUDE.md`, so there is one place to edit.
- The three PowerPoint and Word skills use the format the four tools share (SKILL.md), so they install as they are. OpenCode also reads `~/.claude/skills`, so skills installed for Claude Code show up without installing again. Codex's personal skills folder is `~/.agents/skills` — `~/.codex/skills`, which requests named up to 0.89, is the old place.
- If `~/.codex/AGENTS.override.md` exists, Codex reads only that instead of the personal instruction file `~/.codex/AGENTS.md`. Files that change tells you so.
- Pasting several lines into the terminal (▣ Terminal in a menu, Ctrl+V) leaves them in the input box of all four tools without sending. You press Enter yourself. Punctuation such as the middle dot (·), em dash (—) and ellipsis (…) goes in as it is.
- Antigravity and Codex may ask before reading files outside the working folder (Lectern's writing guide and skills folder). Allow it and they carry on.
- A tool that uses the whole screen, such as OpenCode, shows only its lower part when a stacked terminal is short. Drag the border to make it taller, or put the terminal below the document (tabs).
- With stacked terminals you can keep Claude Code in terminal 1 and Codex in terminal 2 side by side, and choose with Shift+number.

## Settings

The gear button in the toolbar (Ctrl+,) opens Settings. These settings apply to all of Lectern — they are not kept per folder. Open separate windows and slide windows follow within a second or two, and so do edits you save to the settings file (a view setting such as text size changed only in a separate window stays in that window, and follows when another window changes that setting). Things that belong to a folder or a document — a md document style (that document's header), notes, work cards, the last place you read — stay with that folder or document. Click a section on the left (General, View, Editing, Print and export, Terminal, AI tool, Work, Advanced) and the right side moves to it; as you scroll, the current section is highlighted. Next time Settings opens at the section you chose last. Choices are one-line buttons (the chosen one's description shows below), and on/off settings are switches at the right end. Changes apply at once; there is no save button.

**What you hand to the AI tool**, at the bottom of **AI tool** (the writing guide summary, skills, writing style, my style), are the AI tool's files, not Lectern settings. Choose where each goes (the default is **All folders (personal)** — your personal folder, which applies in every folder on this PC; for the writing style, where it is on) and **Files that change** below shows the full paths and what happens (create, change, unchanged, write one value). To show how things stand, Lectern only reads a few fixed files in your personal folder (`~/.claude` and the like) and the open folder — from a settings file, only the `outputStyle` value. The files are written by the AI tool that gets the request, after it tells you how things stand and asks. When writing in your personal folder (`~/.claude`) or a folder's `.claude`, Claude Code asks once more — allow it if it matches what Files that change showed.

You can also open a section straight from where you use it — right-click the terminal header for **Terminal settings…**, **Style settings…** at the bottom of the toolbar style list, **Work settings…** on the work board, the **vi** sign in the status bar, and **Font and layout settings…** in the export window. **Advanced** shows the current values of settings kept only in the file: the editor path, excluded folders and terminal shell.

| Setting | What it does |
|---|---|
| Language | Auto (Windows display language), 한국어 or English. Changing it reloads the window |
| Resume where I left off | Opening a folder returns to the last document and position |
| Expand top-level folders | Expand the first level of folders in the tree when a folder opens |
| Group styles | Group the style list by use, by mood or by brightness |
| My styles | Open style folder, Copy request for Claude Code (see 'My styles' above) |
| Render math | Render `$…$`, `$$…$$` and math code blocks as equations |
| Show line breaks inside paragraphs | Lines you break with Enter in the source break on screen too (like Shift+Enter in Word). When off, they run on as in standard Markdown |
| Show web images | Load https images in documents. When off, they show as links |
| vi keys | Move and edit documents with letter keys (see 'vi keys' above). Off by default |
| Full editor keys | Default (Esc closes) or vi (like vim — `:w`, `:q`). Default by default |
| Print and PDF font | Body font of 'Save as PDF…' and 'Print…' — serif (default) or sans-serif (see 'Print, PDF, html and Word') |
| Page layouts | Open layouts folder, Copy request for Claude Code (see your own layouts under 'Print, PDF, html and Word') |
| Terminal position | Auto (below the document when the window is taller than wide), Right or Below |
| Match terminal colors to style | When off, the terminal is always dark |
| Terminal text size | 10–24 (default 14), with the − · + · Default size buttons or a number |
| AI tool | Claude Code (default), Codex, Antigravity, OpenCode or Several — names on screen and requests follow it (see 'Using Codex, Antigravity or OpenCode') |
| Teach Claude Code about Lectern | Choose where it goes (All folders (personal) or Only this folder), then copy, or paste into the terminal, a request to read the writing guide and write its rules there; open the samples. The name follows the AI tool |
| PowerPoint and Word skills | Choose where they go (All folders (personal) or Only this folder), then copy, or paste into the terminal, a request to install only the missing and different ones (see 'Asking Claude') |
| Writing style | **Choose a style…** (Research writing, Business report, Academic writing, Plain explanation, Claude Code default, My writing styles, Make a new style — with samples), then choose where it is on (Turn on in this folder, Turn on in all folders, Turn off in this folder), then copy, or paste into the terminal, a request to install the Claude Code output style for writing and turn it on (see 'Report writing' above). For Codex, Antigravity and OpenCode the request adds it to the personal instruction file or that project's AGENTS.md |
| My style | Copy, or paste into the terminal, a request to make your style note (one in your personal folder) from writing you wrote yourself — add the samples as `@paths` at the end (see 'Report writing' above) |
| Work management | Choose or clear the common folder, remove folders from the work folder list (see 'Work management' above) |
| Work alerts | Work alerts inside the window while Lectern is running. On by default |

Settings that are not in the window are edited with **Open settings file** in your editor (`%APPDATA%\Lectern\config.json`). Changes apply when you save; settings that affect the tree take effect when you press F5.

**View settings source** (under 'Advanced', and **View source** on each AI item) shows files as they are without changing them — Lectern settings, the writing guide summary, the style note, Claude Code settings (personal and this folder), writing styles (installed and included in Lectern) and skills (SKILL.md and the files in that folder). The **faint // lines without numbers** between the source lines are Lectern's explanations and are not in the file — what each key means, its default and where it is changed (which Settings section, 'Recorded by Lectern', 'this file only'). Values with the wrong form and keys Lectern does not use are pointed out too. Claude Code's personal settings may hold secret values, so take care when sharing your screen.

| Key | What it does |
|---|---|
| `language` | `auto`, `ko` or `en` |
| `editor` | Full path of the editor for code files. When empty, VS Code (`code`) is used |
| `exclude_dirs` | Folder names to leave out of the tree (for example `["data", "output"]`) — they still appear collapsed in 'Other files' |
| `terminal_shell` | Full path of the terminal shell (for example PowerShell 7). When empty, Windows PowerShell is used |

Write backslashes in paths twice (`\\`). If the file has a syntax error, Lectern starts with the default settings and tells you where the error is.

## Keyboard shortcuts

You can bring up this table at any time with the **?** button in the toolbar or Ctrl+/. It is split into eight tabs and always opens on the first, **Most used** (the twenty keys to learn first). Switch tabs by clicking or with Ctrl+Tab, and type an action or key such as `table` or `Ctrl+K` in the search box at the top to search every tab. **Shift+F1** opens the sample project.

Sample — [15 Keyboard shortcuts, step by step](../../samples/guide/15-단축키-따라-하기.md) (in Korean): press the keys in order on a practice document, and the twenty keys to learn first.

<!-- 단축키 표 -->

## Good to know

- Lectern never changes files on its own; files change only when you choose — line editing, line structure, format keys and checkboxes (saved as you press), saving in the full editor, the work tree, kanban and Add event, new documents and folders, renaming and deleting (to the Recycle Bin), pasted pictures, notes and exports (PDF, html, Word, pptx). Apart from that it writes only settings and remembered titles in its settings folder (`%APPDATA%\Lectern`). The right-hand terminal, however, is an ordinary PowerShell, so commands typed there run as usual.
- The terminal needs Windows 10 (1809) or later. A shell's history is gone once Lectern closes.
- Document titles in the tree are read from the beginning of each document. If a document starts with a very long frontmatter, its file name is shown instead.
- Web images that cannot be loaded (blocked on a company network, or taking more than 15 seconds) turn into links.
- Lectern is MIT licensed. The copyright notices and full licenses of the open-source software it includes (Python, pywebview, the Markdown, chart and editor libraries and more) are in `THIRD-PARTY-NOTICES.md` in the installed program folder, and Lectern's own license is in `LICENSE.txt`.
