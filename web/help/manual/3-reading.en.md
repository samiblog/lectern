# Reading

> Pick a document in the folder overview, then read the body as you pick lines, find, fold, mark and collect.

| What you want to do | Document in this chapter |
|---|---|
| Moving the reading position, picking lines and copying | [Current line and picking](3.1-current-line-and-picking.en.md) |
| Finding in a document · across the project · changes | [Find and search](3.2-find-and-search.en.md) |
| Folding sections and seeing one section clearly | [Folding and focus](3.3-folding-and-focus.en.md) |
| Opening links · paths · files | [Links and opening files](3.4-links-and-opening-files.en.md) |
| Marking places to come back to · notes · collecting pieces | [Highlights, notes and clip](3.5-highlights-notes-clip.en.md) |
| Viewing code · CSV · Excel, tables as charts | [Code and data files](3.6-code-and-data-files.en.md) |
| The project's tables · images · to-dos · links in one place | [Elements](3.7-elements.en.md) |
| View PDFs page by page, find in them and clip | [Viewing PDFs](3.8-pdf.en.md) |

## Folder overview

This is the first screen when you open a folder.

| What | How |
|---|---|
| What it shows | Recently changed documents · subfolders · each document's title · summary · modified time |
| That folder's overview | Click the folder name in the sidebar tree (or **Enter** on a folder in the 'Documents' list) |
| The project's overview | Click the project tab that is already selected once more |
| Elements of just that folder | **Elements** in the overview — [Elements](3.7-elements.en.md) |
| Filtering the tree | **Ctrl+F** in the overview |
| Work board | At the top of the common folder's overview — [Work management](8-work-management.en.md) |

## What the body shows

| Element | Source | On screen |
|---|---|---|
| Table | Markdown table | Number columns on the right, the header row stays at the top as you scroll — see 'Tables' below |
| Code block | Code block with a language name | Language colors · **Copy** at the top right |
| Callout | A callout such as `> [!NOTE]` | In the kind's color, without a title line |
| Box | `<!-- box -->` ~ `<!-- /box -->` | A box with a border and a title band — see 'Boxes' below |
| Math | `$…$` · `$$…$$` · math · latex code blocks | As math. Dollar amounts such as `$105` stay as they are |
| Diagram | mermaid code block | As a picture — pick its look by number, see 'Diagram styles' below |
| Chart | `vega-lite` · `echarts` · `plotly` · `dot` code block | As a picture — see 'Charts' below |
| Footnotes · checklists | `[^1]` · `- [ ]` | Footnotes · checkboxes |
| Image | `![description](path)` | Click to enlarge |
| File path | `src/app.py:42` | A link if the file really exists — [Links and opening files](3.4-links-and-opening-files.en.md) |
| Line breaks inside a paragraph | Enter in the source · two spaces at the end of a line · `<br>` | The line breaks on screen too (like Shift+Enter in Word — outline-style writing shows as written) |
| Lines starting with a number or bullet mark | Headings, paragraphs and list items starting with `1. Summary` · `1.2` · `A.` · `(1)` · `①` · `□` · `○` · `-` · `※` | When the line wraps on screen, the following lines line up after the mark — lines after a line break start as usual. Paper and exported html use the average width of the mark. The source is not changed |
| Bullet-mark lists (Korean outline style) | Lines starting with `□` · `○` · `-` · `·` (and the two Korean keyboard letters used for `□` and `○`) — from a line starting with `□` · `○` · `·` up to a blank line or heading (a line starting with `-` is a Markdown list) | Each line becomes a list item. Lower levels are indented — the level follows the order `□` > `○` > `-` > `·` among the marks the document uses (leading spaces in the source are ignored). `①` · `1.` · `※` lines go one level below the item above; a line without a mark continues the item above. The source is not changed |
| List levels | Lists with sub-items — both Markdown lists and bullet-mark lists | Top items are bold and slightly larger, with a little space between them (like printed reports). From the third level on, slightly smaller. Lists without sub-items, task lists, lists inside quotes and Lectern slides stay as they are, and the GitHub styles turn it off. Paper, PDF and Word look the same. Change the weight and size with the 'Lists' fields of [Make my style](2.1-toolbar.en.md#making-your-own-styles) |

To join the lines as standard Markdown does, turn off **Show line breaks inside paragraphs** in the 'View' part of Settings.

## Tables

| What you want to do | How | Result |
|---|---|---|
| Copying a table | Hover and click **Copy** at the top right · right-click **Copy table** | Splits into cells in Excel, pastes as a table in Word and mail |
| Choosing cell alignment | **Table cell alignment** in the 'View' part of Settings | **Default**: text left · numbers right · top of the cell. **Report style**: the header row and short columns (every cell ten characters or fewer — categories · statuses · ○×) centered, numbers right, long text left, vertically centered in the cell |
| Setting one column differently | Right-click a cell: **Align column left** · **Align column center** · **Align column right** | Writes `:---` · `:---:` · `---:` in the source's separator row — this comes before the setting |
| Clearing a column's alignment mark | Right-click in that column: **Clear this column's alignment mark** | Follows the setting again |
| Viewing as a chart | Right-click **View as chart** | [Viewing a table as a chart](3.6-code-and-data-files.en.md#viewing-a-table-as-a-chart) |

The alignment setting changes only the look; the file stays the same. It carries over to printing, PDF and Save as html too.

## Boxes

A box is a text box read apart from the main text. In a report, use it for a side topic that the main flow touches only lightly.

| What you want to do | Source · how | Result |
|---|---|---|
| Making a box | Text · tables · images between a `<!-- box -->` line and a `<!-- /box -->` line | A box with a border and a title band. Other viewers don't show the two lines, so it reads as ordinary text there |
| Adding a title | Write the first line as a single line | In the title band |
| Numbering | `Box 1. Title` | Numbered like tables and images — refer to it with `[Box 1](#box-1)` |
| Folding and unfolding | The arrow at the right of the title band | A folded box still prints in full |
| If you leave out the closing line | — | It ends before the next heading |
| What doesn't go inside | Headings (`#`) · other boxes | — |

The `> [!NOTE]` kind that used to be called a box is now a callout.

## Charts

| Code block language | What |
|---|---|
| `vega-lite` | Data charts |
| `echarts` | Many kinds of chart, such as donuts and candlesticks |
| `plotly` | Analysis charts such as box plots and sunbursts — the output of Python's `fig.to_json()` too |
| `dot` · `graphviz` | Structure and dependency graphs |

Colors follow the document style. Settings are JSON and functions can't be used. Write the data in the document or point to a CSV or JSON file in the project with a relative path (internet addresses are not read). There is no movement such as showing values on hover, and Plotly map charts are not drawn because they need map data from the internet.

## Diagram styles

Pick the look of Mermaid and Graphviz diagrams by number. Colors follow the document style and the number sets only the shape — so it fits dark styles and print too.

| No. | Name | Look |
|---:|---|---|
| 1 | Default | as before (every diagram unless you change the setting) |
| 2 | Report lines | white boxes · dark borders · right-angle connectors — for black-and-white print |
| 3 | Card | rounded corners · soft shadow — for screens and presentations |
| 4 | Solid | dark boxes with light text |
| 5 | Line only | thin lines without fill — for papers and books |
| 6 | Sketch | hand-drawn lines — for drafts (Graphviz uses 1) |
| 7 | Zones | a different pale color for each group (subgraph) |
| 8 | Title band | a dark title band on top, content below |
| 9 | Light title band | a pale band with a dark title, content below |
| 10 | Title rule | bold title, a thin rule, muted content below |

| To do | How | Result |
|---|---|---|
| Change one diagram's look | Right-click the diagram, **Diagram style…** — a window draws that diagram in every number; click one, or use the arrow keys and **Enter** | One `%% style: 3 Card` line in the diagram block (Graphviz `// style: 3 Card`) — replaced if there is one. **Ctrl+Z** undoes it |
| Change one diagram's or chart's colors | Right-click, **Color set…** — a window draws it in all eight color sets (see 'Color sets' below) | `%% colors: 2 Report navy` (Graphviz and charts `// colors: 2 Report navy`) — on the same line as a look marker if there is one: `%% style: 3 Card · colors: 2 Report navy` |
| Make it follow the default | **Follow the setting** in the same window (**Follow the document default** when the document has a default line) — only when the block has a marker | Removes it from the marker line |
| See what a number looks like | The text on the right of the right-click menu (`3 Card`), **See all look samples** in the picker, **Look samples** · **Color set samples** in Settings | The name after the number in a marker line is for people — Lectern reads only the number |
| Horizontal ↔ vertical | Right-click the diagram, **Make it vertical** · **Make it horizontal** | Only the diagram's direction word (`flowchart LR` ↔ `TD`, Graphviz `rankdir`). With more than four boxes, vertical reads better — six boxes side by side shrink the text to about 60% of the body |
| Every diagram in one document | One line near the top: `<!-- diagram: style 8 · colors 2 -->` | Not shown on screen. Order: the block's marker line → the document line → settings |
| Every diagram without a marker | **Diagram style · color set** in Settings 'View' (also **Change the default diagram style…** in the picker) | Pick the default numbers while watching the preview |
| Ask Claude | "Draw it in Mermaid style 3 with colors 2" | It reads `diagrams.en.md` next to the writing guide (`writing.en.md`) and writes the line |
| Emphasis | Add `:::key` (key) · `:::warn` (caution) · `:::muted` (secondary) to a box — Graphviz `[class="key"]` | Painted in the colors the number sets |
| Boxes split into title and content (8 · 9 · 10) | Break the box text — Mermaid `<br>`, Graphviz `\n` | The first line is the title, the rest is the content. A one-line box is title only |

### Color sets

A color number picked separately from the look. It changes chart series colors (Vega-Lite, ECharts, Plotly, Mermaid pie and xy charts) and diagram boxes, the key accent, zone colors and title bands; text, background and lines stay with the document style. A single-series bar or line takes the set's first color, a heatmap takes shades of it. Colors a chart sets itself win, and the up/down colors of candlestick and waterfall charts do not change either. For such charts every tile in the picker looks the same and the window says why (remove the colors from the source and the chart follows).

| No. | Name | Colors |
|---:|---|---|
| 1 | Document style | as now (every diagram unless you change the setting) |
| 2 | Report navy | shades of navy + one orange accent |
| 3 | Gray + accent | only the first series in color, the rest gray |
| 4 | Vivid | ten colors that tell apart well |
| 5 | Colorblind safe | the Okabe-Ito palette |
| 6 | Warm | orange and rust |
| 7 | Cool | navy, teal and violet |
| 8 | Pastel | pale colors |

Marker lines are comments, so other places (GitHub and so on) draw the default look and colors (a chart's `//` line is read only by Lectern — remove it before pasting the block into another tool). The picker changes no file until you pick — **Esc** or a click outside closes it as is. If the diagram changed elsewhere after you opened the picker, nothing is written and you are told. Flowcharts in this manual always use the defaults. Diagrams exported to Word or pptx still use the default look and colors. Examples: the diagram style and color set samples in `guide/도해-스타일-예제/`.

### My diagram styles · my color sets

Keep a look or colors you like as a number and use them on other diagrams. Looks start at 11, colors at 9.

| What you want to do | How | Result |
|---|---|---|
| Make this diagram's look your own style | Right-click the diagram, **Make my diagram style from this look…** (also at the bottom of the picker) | A request with the diagram's place, the next number and the folder to save in goes into the terminal (Enter is not pressed). Claude shows the name and values, asks, then writes one file |
| Make this chart's colors your own color set | Right-click the chart, **Make my color set from these colors…** | The same way — colors from 9 |
| Use it | The 'mine' cards in the picker, or `%% style: 11 Our company` · `%% colors: 9 Company colors` | When a file is made or changed, diagrams follow within seconds (no reload) |
| Make it the default | 'mine' under **Diagram style · color set** in Settings 'View' | Every diagram without a marker line |
| See the files · what to fix | **Open my diagram styles folder** in the same place, and the red lines below it | `diagram-styles` in the settings folder — one file per style. Wrong values, duplicate numbers and unknown keys are left out, with the reason for each file |

- Files take only set values (base number, corner, border, line shape, line width, dashes, shadow, fill, spacing, bold text, title boxes, zones, hand-drawn; color sets take series colors). No CSS. Lectern only reads this folder.
- On a PC without the file (a colleague who got the document), the default look and colors are drawn — the name stays in the marker line. A default number in Settings also falls back to 1 when its file is gone.
- The guide Claude reads: `web/help/diagram-styles.en.md` in the install folder.

## Chart data

| What you want to do | How | Result |
|---|---|---|
| Enlarging | Click the chart | Larger |
| Copying as an image | Right-click **Copy image** | PNG |
| Seeing the data drawn | Hover and click **Table** (click again to close) | A table below the chart. Over 30 rows, the first, the last and evenly spaced rows, 30 in all — **Show all** opens up to 5,000 rows |
| Copying the data | Hover and click **Copy** | All the data — Excel (split into cells) · Word (a table) |
| Bringing CSV data into the document | **Put data into the document** | Reads the CSV and writes the values into the chart's source — the document alone then shows the chart and table on other PCs (**Ctrl+Z** undoes it) |

The table is read from the chart's source — if the chart filters or combines the values as it draws (transform, aggregate), the table shows the values before that. A chart whose data is in a CSV file names the file instead of showing a table. Charts in Lectern slides and Graphviz have no buttons, and the buttons and tables don't appear in print or PDF.

## HTML documents

HTML reports made by AI tools (Claude Code and others) are viewed as documents too.

| Situation | Behavior |
|---|---|
| Tree | Shown with an `HTML` mark |
| The document's style | Shown as it is |
| Scripts · internet CSS | Blocked — charts drawn by scripts don't appear |
| html in app source folders (`src` · `public` · `web` and so on) | Not treated as documents |
| Editing | Only in the full editor — [Choosing how to edit](4.1-choosing-how-to-edit.en.md) |
| Clip | Not available — there are no source lines |

## Documents in this chapter

<!-- 하위 문서 -->
