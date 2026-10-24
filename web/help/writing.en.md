# Writing documents that read well in Lectern — guide for AI

This guide is for AI such as Claude Code. People read the project folder's documents with **Lectern** (a Windows document viewer). Follow these rules and tables, contents, diagrams and charts show correctly, and the locations people pick in Lectern (`@path lines 12-20`) can be handed back to the AI.

If the task is "put these rules into this project's CLAUDE.md", trim the **Summary for CLAUDE.md** at the end to fit that project. For examples, see `samples` in Lectern's install folder ('Open samples' in Lectern) — especially `samples/CLAUDE.en.md` and `samples/guide/04-문서-쓰는-법.md`.

## 1. What Lectern shows

- Documents: Markdown (`.md`) and HTML (`.html`). Other files appear in the sidebar's 'Code' list (source and settings) or 'Files' list (CSV, PDF, Excel, images and so on); code is shown read-only with line numbers and language colors.
- Hidden: files and folders whose names start with `.`, Windows hidden and system files, symbolic links and junctions, folders without documents, and excluded folders (`node_modules`, `__pycache__`, `venv`, `env`, `dist`, `build`, `target`, `site-packages`, `htmlcov`).
- HTML inside app source folders (`src`, `public`, `static`, `templates`, `web`, `www`, `frontend`, `out`) is not treated as a document — those are web app screens, not reports. Put HTML reports for people in another folder such as `reports/`.
- Lectern is a viewer. It does not create or delete documents. In edit mode people can change UTF-8 text files up to 2 MB.
- When a file changes, Lectern redraws within a second or two and briefly marks the changed blocks. Editing the same document in small steps is fine.

## 2. Files and titles

- Document title: frontmatter `title`, otherwise the first `# Title`. Use one `#` heading per document (it becomes the title and is left out of the contents).
- Summary (shown in the folder overview): frontmatter `description`, otherwise the first paragraph (160 characters). Write the first paragraph as a one- or two-sentence summary.
- Prefix ordered documents with numbers such as `01-`, `02-`. Numbers sort as numbers (`2-` before `10-`).
- File names may use any language. Use `-` instead of spaces.
- Frontmatter is YAML between `---` lines at the very top. It shows as a 'Metadata' box above the document.

```markdown
---
title: Research automation plan
description: Three steps from collecting prices to publishing the report
status: in progress
---

# Research automation plan
```

## 3. Markdown

### Headings

Go `##` → `###` → `####` without skipping levels. The contents panel, section folding (click a heading to fold) and section focus (one `##` section at a time) follow them. Split long sections with `###`.

### Tables

- Put only values in cells and units in the header: `| Price (USD/t) |`.
- Columns that read as numbers are right-aligned automatically. Cells that read as numbers: `1,234`, `-3.5%`, `+3.2%p`, `$105`, `1.2x`, `30bp`, and `-` for empty.
- Long tables keep their header row stuck to the top, so there is no need to split them.

### Callouts

Put the kind on the first line of a quote. There are exactly five.

```markdown
> [!NOTE]
> Something worth knowing.
```

`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`. Any other `>` is a plain quote.

### Other blocks

- Lists, numbered lists, checklists (`- [ ]`, `- [x]` — display only, not clickable).
- Footnotes: `[^1]` in the text and `[^1]: note` anywhere; they gather at the end.
- Code blocks: give the language (```` ```python ````) for colors and a copy button.
- HTML fragments: `<details><summary>…</summary>…</details>` for folded content. `<script>`, `<style>`, `<form>` and event attributes (`onclick` and so on) are removed.

### Links and locations

- Link documents, images and files with **paths relative to the document**: `[Plan](../plans/plan.md)`, `![Figure](images/x.svg)`.
- Section links: `doc.md#heading-text` — the heading in lower case, spaces as `-`, punctuation removed (`## Price range` → `#price-range`).
- Code locations: writing `src/report.py:14` (or `src/report.py#L14`, `src/report.py`) in the text becomes a link when that file exists in the project, and clicking jumps to that line in the code view. Inline code (`` `src/report.py:14` ``) is linked when its whole content is a path. Nothing inside code blocks is linked.
- Absolute paths (`C:\…`, `file:///…`) open only inside the project. Use relative paths.
- Internet links open in the default browser. People can turn internet images off in the settings, so keep must-see images as files in the project.

### Math

- Inline: `$…$` or `\(…\)`. Display: `$$…$$` or `\[…\]`. ```` ```math ```` and ```` ```latex ```` code blocks become math too.
- Dollar amounts are not math: if the character right after the opening `$` or right before the closing `$` is a space, or a digit follows the closing `$`, it stays text (`$105 to $110`, `$95~$110/t`).

## 4. Diagrams and charts

The code block language decides. All become static pictures (SVG) whose colors follow the document style people picked. If one cannot be drawn, its source and the reason appear in its place.

| Language | Library | Use for |
|---|---|---|
| `mermaid` | Mermaid 12 | flowcharts, sequence, state, Gantt, mind maps, timelines, ER, simple charts (`xychart-beta`, `pie`, `sankey-beta`) |
| `vega-lite` (`vega`) | Vega-Lite 6 | data charts — bar, line, area, scatter, heatmap, layered charts, reading the project's CSV/JSON |
| `echarts` | ECharts 6 | many chart types — donut, candlestick, gauge, radar, sankey |
| `plotly` | Plotly 4 | analysis charts — box plots, histograms, sunbursts, waterfalls. Python's `fig.to_json()` output works as is |
| `dot` (`graphviz`) | Graphviz | automatic layout of structure and dependency graphs with many nodes |

Rules:

- **Settings are JSON values only.** Functions (`formatter: function…`, `=>`) are not run, so they are errors. Use string templates such as `'{b}\n{d}%'` for ECharts `formatter`. `option = { … }`, unquoted keys, single quotes, comments and trailing commas (as in ECharts examples) are read.
- **Nothing goes to the internet.** Put data in the document or point to a file in the project with a path relative to the document (Vega-Lite `"data": {"url": "../data/x.csv"}`). Do not use data at internet addresses, internet images inside charts, or Plotly map types (scattergeo, choropleth, mapbox). Links inside charts are removed.
- **Size.** To fit the document width, give Vega-Lite `"width": "container"` and a `"height"`, ECharts only `"height"` (a key only Lectern reads, default 360), and Plotly only `layout.height` (default 400). A numeric width draws at that size.
- **Colors.** Without colors, the style's colors are used (readable in light and dark styles). Colors you set are kept. Plotly follows `layout.template` when there is one.
- **Titles.** Vega-Lite and ECharts `title`, Plotly `layout.title` and the Graphviz graph name (`digraph name {`) label the chart in the contents and Elements tab.
- **Mermaid**: quote non-ASCII axis labels and text (`x-axis ["Jan", "Feb"]`). Use ASCII aliases for participants: `participant U as 사람`.
- **Graphviz**: the app fits box widths for non-Latin text. Better not to set `fontname`.

```vega-lite
{
  "title": "Monthly average price (USD/t)",
  "width": "container",
  "height": 220,
  "data": { "url": "../data/월별-가격.csv" },
  "mark": { "type": "line", "point": true },
  "encoding": {
    "x": { "field": "월", "type": "temporal", "title": null },
    "y": { "field": "가격", "type": "quantitative", "title": null, "scale": { "zero": false } }
  }
}
```

## 5. HTML documents

- Their own styles (`<style>`) show as they are. Without styles, Lectern applies its document style.
- **Scripts do not run.** JavaScript charts (Chart.js, Plotly HTML exports and so on) stay blank. Draw charts as static SVG, or make them with chart code blocks in a Markdown document.
- Internet CSS, fonts and scripts are blocked. Keep styles inside the document.
- `<title>` is the title, `<meta name="description">` the summary, and `h1`–`h4` the contents. An `id` on `h2` makes a section link.
- Link documents and images with relative paths (`../research/x.md#outlook`) — they open inside Lectern.

## 6. What people hand to the AI

- **Location for Claude**: people right-click a block and paste `@research/report.md lines 12-17` into the terminal (in the Korean UI: `@research/report.md 12~17행`). The first part is the file, the rest is the source line range. Read those lines and work on them.
- From a heading it carries the section name, such as `@research/report.md lines 10-19 (section 'Summary')` — the whole section.
- From the code view it looks like `@src/report.py lines 14-19`.

## 7. Don't

- Don't put JavaScript charts in HTML reports (they do not show).
- Don't put functions or internet addresses in chart settings.
- Don't put documents in `node_modules`, `dist`, `build` or `.` folders (they are hidden).
- Don't put HTML for people in app source folders such as `src` or `web`.
- Don't use several `#` headings in one document or skip heading levels.
- Don't mix units or notes into table cells (it breaks number alignment).

## Summary for CLAUDE.md

```markdown
## Documents (read with Lectern)
- Write Markdown. HTML reports run no scripts, so make charts with chart code blocks in md.
- One `# Title` first, then a one- or two-sentence summary paragraph. Number ordered documents `01-`.
- Don't skip heading levels (## → ###). Only numbers in table cells, units in the header.
- Callouts: `> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`.
- Code locations as `src/x.py:14`; links and images relative to the document.
- Diagrams in ```mermaid; charts in ```vega-lite, ```echarts, ```plotly, ```dot — JSON values only (no functions), data in the document or a project CSV by relative path, no internet addresses.
- `@path lines 12-17` (Korean UI: `@path 12~17행`) from people means those lines of that file.
```
