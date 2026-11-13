# Document rules for this project (for Claude Code)

People read and edit in place this project's documents with **Lectern** (an Integrated Research Work Environment for Windows, centred on Markdown, where people work together with AI). Follow these rules when writing or editing documents. The full rules are in Lectern's writing guide (`web/help/writing.en.md` — 'Teach Claude Code about Lectern' in Lectern's settings shows the path).

## Writing first

- In this sample, the research notes and the weekly report are read by a buyer at a company that purchases copper, who uses them to decide when and how much to buy next quarter (the sample's assumption — if a request names another reader, follow that reader). Before writing, decide what that reader must judge.
- Write in paragraphs rather than bullet lists, conclusion first. Give every number its comparison (against what, by how much), and keep sources (document path or URL) for facts you bring in.
- When done, reread from the start as the reader and fix paragraphs that only list and repeated sentence endings. The formatting below comes after that.

## Files

- Write documents in Markdown (`.md`). HTML works when the look matters, as for reports, but **scripts do not run** — make charts with Markdown chart code blocks instead of JavaScript in HTML.
- Start each document with a single `# Title` line. The tree (Titles button), folder overview and window title use it (a frontmatter `title` wins if present).
- Prefix ordered documents with numbers such as `01-`, `02-` (`2-` sorts before `10-`).
- Make the first paragraph a one- or two-sentence summary — it becomes the summary in the folder overview. Plans and decisions may set it with a frontmatter `description` instead.
- Documents in folders starting with `.` and in `node_modules`, `dist` or `build` are hidden. HTML files in app source folders such as `src/` and `web/` are not treated as documents.

## Writing

- Do not skip heading levels (`##` → `###`). The contents panel, section folding and section focus follow them.
- Put only numbers in table cells and units in the header (`Price (USD/t)`). Number columns are right-aligned automatically.
- Use callouts for emphasis: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`.
- Put a side topic read apart from the main text in a box: between a `<!-- box -->` line and a `<!-- /box -->` line, with `**Box 1. Title**` as the first line. No headings (`#`) inside.
- When the person says 'summarize the conversation into a box right after `@path line 12`': insert exactly one box after that line. Do not transcribe the conversation — keep the conclusions, reasons and open questions, and change no other line.
- Write code locations as `src/report.py:14` — clicking jumps to that line (not inside code blocks).
- Link images and other documents with paths relative to the document. Section links are `doc.md#heading-text`.
- Table captions go above the table as `Table 1. Title`, figure captions below the figure as `Figure 1. Title`. Refer to them in the text with links like `[Table 1](#table-1)` — when people add or move a table, Lectern renumbers the captions and fixes the links.
- Diagrams are ```` ```mermaid ```` code blocks; charts are ```` ```vega-lite ````, ```` ```echarts ````, ```` ```plotly ```` or ```` ```dot ```` code blocks.
  - Settings are JSON values only — functions (`formatter: function…`) are not allowed.
  - Put data in the document, or point to a CSV/JSON file in the project with a path relative to the document (Vega-Lite `data.url`). Data and images at internet addresses are not read.
  - To fit the document width, use `"width": "container"` in Vega-Lite, and only `"height"` in ECharts or `layout.height` in Plotly.
- For new Lectern slides, pick the matching example in `slides/README.en.md` and follow its process document in `slides/상황별/과정/`.
- Write presentations as Lectern slides: put `marp: true` in the front matter and separate slides with `---`. Keep one heading and five or six short bullets per slide — anything longer is cut off at the bottom (pictures, diagrams and charts are shrunk to fit). Speaker notes go in `<!-- … -->`; `paginate: true` adds page numbers.
- Math is `$…$` and `$$…$$`. Dollar amounts such as `$105` stay as they are (a closing `$` after a space is not math).
- The `<!-- from: path lines a-b -->` comment before a piece a person inserted with Lectern's Clip records its source — do not remove it.

## This project

- `src/collect.py` appends monthly prices to `data/월별-가격.csv`, and `src/report.py` writes the summary sentence.
- Research documents go in `research/`, plans in `plans/`, reports in `reports/`.
- When numbers change, update the research tables and the report numbers together.
- This task's status, due date, to-dos and events are in `WORK.md` at the top (the work card). Front matter `status`, `priority`, `due` only; to-dos `- [ ] what (YYYY-MM-DD)`; events `- YYYY-MM-DD HH:MM what` (absolute dates). When work is done, add one line under today's date in the log section.
