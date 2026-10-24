# Document rules for this project (for Claude Code)

People read this project's documents with **Lectern** (a Windows document viewer). Follow these rules when writing or editing documents. The full rules are in Lectern's writing guide (`web/help/writing.en.md` — 'Teach Claude Code about Lectern' in Lectern's settings shows the path).

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
- Write code locations as `src/report.py:14` — clicking jumps to that line (not inside code blocks).
- Link images and other documents with paths relative to the document. Section links are `doc.md#heading-text`.
- Diagrams are ```` ```mermaid ```` code blocks; charts are ```` ```vega-lite ````, ```` ```echarts ````, ```` ```plotly ```` or ```` ```dot ```` code blocks.
  - Settings are JSON values only — functions (`formatter: function…`) are not allowed.
  - Put data in the document, or point to a CSV/JSON file in the project with a path relative to the document (Vega-Lite `data.url`). Data and images at internet addresses are not read.
  - To fit the document width, use `"width": "container"` in Vega-Lite, and only `"height"` in ECharts or `layout.height` in Plotly.
- Write slide decks in Marp format: put `marp: true` in the front matter and separate slides with `---`. Keep one heading and five or six short bullets per slide — anything longer is cut off at the bottom (pictures, diagrams and charts are shrunk to fit). Speaker notes go in `<!-- … -->`; `paginate: true` adds page numbers.
- Math is `$…$` and `$$…$$`. Dollar amounts such as `$105` stay as they are (a closing `$` after a space is not math).
- The `<!-- from: path lines a-b -->` comment before a piece a person inserted with Lectern's Clip records its source — do not remove it.

## This project

- `src/collect.py` appends monthly prices to `data/월별-가격.csv`, and `src/report.py` writes the summary sentence.
- Research documents go in `research/`, plans in `plans/`, reports in `reports/`.
- When numbers change, update the research tables and the report numbers together.
