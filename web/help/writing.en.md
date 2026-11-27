# Writing documents that read well in Lectern — guide for AI

This guide is for AI tools such as Claude Code, Codex, Antigravity and OpenCode. People read and edit in place the project folder's documents with **Lectern** (an Integrated Research Work Environment for Windows, centred on Markdown, where people work together with AI). Follow these rules and tables, contents, diagrams and charts show correctly, and the locations people pick in Lectern (`@path lines 12-20`) can be handed back to the AI.

**Formatting makes writing visible; the quality of the writing comes first.** The rules below only make documents show correctly in Lectern — they do not make good writing. Before writing, decide who reads it and what they must judge after reading. Do not stop at the folder: look for background and counter-evidence in earlier material and on the web, and keep the sources. Write to the kind of document (narrative or bullet-point; even bullets must each carry their evidence and meaning), keep developer habits such as file paths and code formatting out of the body, and when done, reread from the start as the reader and revise. For people who write reports often, the 'Writing style' in Lectern's settings (a Claude Code output style — the one chosen from Research writing, Business report, Academic writing and Plain explanation) keeps this on for the whole session.

If the task is to put these rules somewhere, it is one of two things, depending on where the person chose (the request from Lectern's settings window says which — D159).

- **All folders (personal folder)**: put the **Summary** at the end into the person's personal rules — for Claude Code the one file `~/.claude/rules/lectern.md` (do not change the person's own `~/.claude/CLAUDE.md`), for Codex a section of `~/.codex/AGENTS.md`, for Antigravity of `~/.gemini/AGENTS.md`, for OpenCode of `~/.config/opencode/AGENTS.md`. Write down this guide's full path with it so it is read again when writing tables, charts or slides. Leave out what differs by project (readers, purpose, tone).
- **One folder**: in that project's instruction file (`CLAUDE.md` for Claude Code and `AGENTS.md` for Codex, Antigravity and OpenCode — if the project uses both, put it in `AGENTS.md` and leave just the line `@AGENTS.md` in `CLAUDE.md`), write that project's readers, purpose and tone. If the personal rules already have the Lectern summary, leave out the formatting rules; if not, trim the summary to fit the project and add it too. Keep the project's instruction file from becoming a formatting rulebook: put readers, purpose and tone before the formatting rules.

Either way, before writing, say whether the file exists now and whether it already has the Lectern summary, show the text you will add, and ask. For examples, see `samples` in Lectern's install folder ('Open samples' in Lectern) — especially `samples/CLAUDE.en.md` and `samples/guide/04-문서-쓰는-법.md`.

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

Go `##` → `###` → `####` without skipping levels. The contents panel, section folding (the arrow left of a heading, Ctrl+Shift+[) and section focus (one `##` section at a time) follow them. Split long sections with `###`.

### Paragraphs and line breaks

- A line you break with Enter inside a paragraph also breaks on screen (like Shift+Enter in Word). For outline-style writing, just break the line.
- A heading, paragraph or item that starts with a number or bullet mark (`1.` · `1.2` · `A.` · `(1)` · `①` · `□` · `○` · `-` · `※`) lines up its wrapped lines after the mark on screen. Put one space after a bullet mark (`□ Background` — `□Background` is not read as a bullet; `①` and `※` may be written without the space).
- For Korean outline style, start lines with `□` · `○` · `-` · `·` in that order and Lectern shows them as a list with lower levels indented — the level comes from the mark, so leading spaces are not needed. Such a list starts at a line beginning with `□` · `○` · `·` and runs to a blank line or heading (a line starting with `-` is a Markdown list). Other Markdown viewers and Save as Word only show the line breaks — if those matter, use a Markdown list (`-` and indentation).
- So do not wrap one sentence across several lines to fit a width — keep a sentence on one line.

### Tables

- Put only values in cells and units in the header: `| Price (USD/t) |`.
- Columns that read as numbers are right-aligned automatically. Cells that read as numbers: `1,234`, `-3.5%`, `+3.2%p`, `$105`, `1.2x`, `30bp`, and `-` for empty.
- Long tables keep their header row stuck to the top, so there is no need to split them.
- **The writer shapes the table.** Lectern fits the column widths (each column first gets room for its longest word, and the rest goes to the columns with long text). Still, with too many columns or too much text in one cell, cells grow tall, and as a last resort the table scrolls sideways and can no longer be read at a glance:
  - **About six columns at most.** If more than seven columns hold text, split the table (by topic or period), swap rows and columns, or move the less important columns into a list below the table. Columns holding only numbers are narrow, so more of them are fine (about ten).
  - **One or two lines per cell (about 60 characters).** Move explanations longer than two or three sentences out of the table — into a list or paragraph below it — and keep only the gist in the table. Have at most one long-text column, at the far right.
  - **Keep the cells in a row about the same length.** One very long cell makes the whole row tall.
  - Keep the first column (item, category) a short label.
- **Use alignment marks only when needed.** Without marks (`:---`, `:---:`, `---:`) Lectern aligns the cells — number columns to the right, and if the reader picks 'Report style' in the settings, the header row and short columns to the center. A marked column overrides the reader's choice, so mark only columns that must look that way (for example, centering a column of ○ and × only).
- **Captions above, notes and sources below**: a line `Table 1. Title` · `Figure 1. Title` (or a whole-bold line) directly above a table, picture, diagram or chart becomes its name in the contents and in Elements. `<Table 3>`, `[Figure 2]` and `Table 3-1.` work too (and the Korean 표·그림 forms). Directly below go `Note: …` · `Source: organization (year)` lines — each shows on its own line even without blank lines between them. Lectern draws the caption centered, larger and bold, and the notes and sources small on the left below it (in print and Word too).

### To-dos, sources and document info

- Write to-dos as checklists (`- [ ] task`, `- [x]` when done) — Lectern's Elements collects the open ones across the project.
- Put a table's, figure's or chart's source on the line just below it as `Source: organization (year)`, with any caveat above it as `Note: …` — it shows under Elements → Sources. Footnotes (`[^1]`) are collected there too.
- Give plan, decision and report documents the same front matter keys, such as `status`, `owner`, `updated` (YYYY-MM-DD) and `tags: [a, b]` — Elements → Doc info groups documents by each key's values.
- When a person inserts pieces of other documents with Lectern's Clip, each piece is preceded by a `<!-- from: path lines a-b -->` comment (in a Korean interface, `<!-- 담은 곳: … -->`). A clip from a PDF reads `<!-- from: path p. 12 -->`. It records the source — keep it when editing (it is not shown on screen), and leave the same kind of comment when asked to bring pieces over. When a person sends `@data/report.pdf p. 12`, read page 12 of that PDF.

### Callouts

Put the kind on the first line of a quote. There are exactly five.

```markdown
> [!NOTE]
> Something worth knowing.
```

`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`. Any other `>` is a plain quote.

Lectern does not add a title line (such as 'Note' or 'Tip') to callouts — the kind shows only as a color. If a callout needs a title, write its first line in bold:

```markdown
> [!TIP]
> **Numbers only in tables**
> Put units in the header row.
```

### Boxes

Use a box for a side topic that stands apart from the flow of the main text — the 'Box' of a report. Write ordinary Markdown between two comment lines.

```markdown
<!-- box -->
**Box 1. Copper stocks and prices**

The rule that prices rise when stocks fall has weakened since 2020.

| Year | Stocks (10k t) | Price (USD/t) |
|---|---|---|
| 2023 | 12 | 8,500 |

Source: LME
<!-- /box -->
```

- Lectern draws a bordered box with a title band. Other viewers do not show the comments, so it reads as a bold title and ordinary text — which is why no visible marker such as `:::` is used.
- The opening line `<!-- box -->` and the closing line `<!-- /box -->` each take a whole line (no other text on that line). Without a closing line, the box ends before the next heading.
- The first line is the title — write it on one line. With a number, as in `**Box 1. Title**`, `[Box 1](#box-1)` refers to it, and when a person adds or moves a box Lectern renumbers the titles and the links. Number from 1 in order.
- Inside, write paragraphs, lists, tables, figures, charts, math, callouts and footnotes. Do not put headings (`#`) or another box inside — a box is a component, not a section, and stays within one section.
- Tables and figures inside continue the document's numbering (after Table 3, a table inside a box is Table 4).
- A box is not a callout (`> [!NOTE]`): a callout makes a sentence or two stand out; a box holds enough to be read on its own. Lectern slides have no boxes.
- When a person uses Lectern's box request ('Ask Claude for a box' — the name follows the tool the person uses) — 'summarize the conversation into a box right after `@path line 12`' — insert exactly one box after that line, with a blank line before and after. Use the number given in the request and change no other line. Do not transcribe the conversation: keep only the conclusions, the reasons and the open questions worth leaving in the document.

### Other blocks

- Lists, numbered lists, checklists (`- [ ]`, `- [x]` — clicking a box switches the marker in the source and saves it).
- Footnotes: `[^1]` in the text and `[^1]: note` anywhere; they gather at the end.
- Refer to tables and figures with links: `[Table 3](#table-3)`, `[Figure 2](#figure-2)` (the caption paragraph is the target). When people add or move a table, Lectern renumbers the captions and fixes these links — plain text like 'Table 3' is not changed.
- Put sources in a list under `## References` and cite them in the text as `(Author, year)`. People pick citations from that list.
- A `[TOC]` line is a table of contents in the document (also `[List of Tables]`, `[List of Figures]`), and a page break is the line `<div style="page-break-after: always;"></div>` — both are for printing and PDF.
- Code blocks: give the language (```` ```python ````) for colors and a copy button.
- HTML fragments: `<details><summary>…</summary>…</details>` for folded content. `<script>`, `<style>`, `<form>` and event attributes (`onclick` and so on) are removed.

### Emphasis inside text

- Bold `**text**`, italic `*text*`, strikethrough `~~text~~`, code `` `text` ``.
- Highlight is `<mark>text</mark>` (yellow). The only other colors are `<mark class="green">`, `<mark class="pink">` and `<mark class="blue">`.
- Text color is `<span style="color:red">text</span>` — only `red`, `blue`, `green` and `goldenrod`. Do not use other color names or `#rrggbb` (these four are the ones each style redraws in a readable shade).
- Use color sparingly. People mark text themselves in Lectern, and color all over an AI-written document buries what they marked.

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
- **Data goes inside the chart.** Write the data in the chart as `"data": {"values": [...]}` by default — the document alone then draws the chart on other PCs, and people see the values as a table and copy them to Excel with the chart's [Table] button. Point to a CSV in the project (`"data": {"url": "../data/x.csv"}`, relative to the document) only for working data with hundreds of rows or more, or data another program updates — a CSV may not travel with the document.
- **Nothing goes to the internet.** Do not use data at internet addresses, internet images inside charts, or Plotly map types (scattergeo, choropleth, mapbox). Links inside charts are removed.
- **Size.** To fit the document width, give Vega-Lite `"width": "container"` and a `"height"`, ECharts only `"height"` (a key only Lectern reads, default 360), and Plotly only `layout.height` (default 400). A numeric width draws at that size.
- **Colors.** Without colors, the style's colors are used (readable in light and dark styles). Colors you set are kept. Plotly follows `layout.template` when there is one.
- **Titles.** Vega-Lite and ECharts `title`, Plotly `layout.title` and the Graphviz graph name (`digraph name {`) label the chart in the contents and Elements tab.
- **Mermaid**: quote non-ASCII axis labels and text (`x-axis ["Jan", "Feb"]`). Use ASCII aliases for participants: `participant U as 사람`.
- **Graphviz**: the app fits box widths for non-Latin text. Better not to set `fontname`.
- **Diagram styles and color sets**: pick the look of Mermaid and Graphviz diagrams (1–10) and the colors of charts and diagrams (color sets 1–8) by number — one line inside the block, `%% style: 3 · colors: 2` (Graphviz and charts use `//`), or one line for the whole document, `<!-- diagram: style 3 · colors 2 -->`. Write them only when the person names a number or name; write no colors, and mark emphasis with `:::key`, `:::warn`, `:::muted`. With more than four boxes side by side, go vertical (`TD`). The numbers, title boxes (8–10) and direction are in `diagrams.en.md` next to this file.

~~~~md
```vega-lite
{
  "title": "Monthly average price (USD/t)",
  "width": "container",
  "height": 220,
  "data": { "values": [
    { "월": "2026-01", "가격": 9120 },
    { "월": "2026-02", "가격": 9340 },
    { "월": "2026-03", "가격": 9285 }
  ] },
  "mark": { "type": "line", "point": true },
  "encoding": {
    "x": { "field": "월", "type": "temporal", "title": null },
    "y": { "field": "가격", "type": "quantitative", "title": null, "scale": { "zero": false } }
  }
}
```
~~~~

## md document style

When asked to make an md document style, write one `name.json` file to `md-styles` in the Lectern settings folder (`%APPDATA%\\Lectern\\md-styles`). Never overwrite a file. All of Lectern shares it.

```json
{"kind": "prose", "marks": ["제{1}장", "제{1}절", "{1}.", "{가}.", "{1})", "{가})"]}
```

- `kind` is `prose` or `outline`.
- `marks` has one form per heading level, up to six, up to 16 characters each. The first is the level below the document title. Use an empty string for a level without a number.
- Forms: `{1}` number, `{I}` Roman, `{가}` Korean letter, `{①}` circled number, `{path}` 1.1.1. Anything else is written as it is.

## 5. Lectern slides

Markdown with `marp: true` in the front matter shows as **slides** — Lectern's presentation format, which starts from Marp. Cells (`::: a card`) and layouts (`<!-- layout: quad -->`) give each slide its own arrangement. People edit the text on a slide line by line.

**Before making or changing a deck, read `slides.en.md` next to this file.** It has the syntax, layouts, text sizes and how much fits. Do not make presentations in HTML.

### Data (CSV and text)

- Keep tabular data as CSV — clicked in Lectern it shows as a table (filter, sort and stats per column), and charts can read it with `data.url`. **Make the first row the header** (column names), put only values in cells and units in the header (`price (USD/t)`). Save as UTF-8 (Excel's CP949 can be read and edited too, but UTF-8 is better for sharing with other programs).
- To point at data from a document, use a link (`[monthly prices](../data/월별-가격.csv)`) or a path such as `data/월별-가격.csv:5` — clicking goes to that row of the table.

## Clip boxes — .lectern/clips/

Pieces a person clips in Lectern pile up in one md file per clip box (`.lectern/clips/name.md`). Read it as is when asked — it holds the box's title and description, and for each clip where it came from, its title and note, and the text as it was when clipped. Add or change clips **only when the person asks**, and leave the others as they are.

To add a clip, append this to the end of the file:

```markdown
<!-- lectern-clip path=research/stocks.md line=3 end=3 kind=block -->
## Clip title (leave this line out if none)
A note on why it was picked (may be empty)
<!-- lectern-clip-text -->
Lines 3-3 of that document, exactly as they are
<!-- /lectern-clip -->
```

- `path` is relative to the project (write spaces as `%20`), `line` and `end` are the first and last source lines, and `kind` is one of `table`, `image`, `chart`, `section` or `block`. Lectern adds the `id`.
- Do not reword the clipped text — if it differs from the document, Lectern says 'The source document changed'. Put interpretation in the note.

## Work card — WORK.md

A folder's `WORK.md` is that folder's **work card** — the one at the top of a project covers the whole task, one in a subfolder covers a piece of work inside it. Lectern gathers the WORK.md of many folders into a work board (status, due date, to-dos, events) and alerts. People write and edit this file without AI — when an AI tool writes it, keep the same format so people can carry on editing it.

```markdown
---
status: active
priority: high
due: 2026-12-15
---

# Market analysis report

This task in one line.

## Planning notes

- Ask the team lead whether to widen the scope to Southeast Asia
- First-draft meeting around next Wednesday?

## Current state

## To do

- [ ] Draft chapter 3 (2026-11-14)

## Schedule

- 2026-11-12 14:00-15:00 First report to the team lead
- 2026-11-20 all-day Commodities seminar

## Decisions

## Log

### 2026-11-10

- First report to the team lead. Scope narrowed to the home market

## Materials
```

- **Only four front-matter keys are read**: `status` (`planned`, `active`, `at-risk`, `blocked`, `on-hold`, `done`, `dropped` — the Korean values 예정·진행·지연위험·막힘·보류·완료·중단 work too), `priority` (high, medium, low), `due` (`YYYY-MM-DD`), `start` (`YYYY-MM-DD` — the start in the Gantt chart and calendar; may be left empty). Don't rename the keys or decorate the values. Adding other keys is fine (they group in Gather view's 'Document info').
- **To-dos**: `- [ ] what (YYYY-MM-DD)` — the date in parentheses at the end is the due date (`(11/14)` works too). Mark done with `[x]`.
- **Events**: `- YYYY-MM-DD HH:MM what`, an end time as `HH:MM-HH:MM`, a whole day as `all-day`. Always write absolute dates — not 'tomorrow' or 'Friday'. Events with a time are announced 10 minutes before.
- **Log**: a `### YYYY-MM-DD` per day, newest first, one line each under it. Don't rewrite past entries.
- **Planning notes**: a section where people jot things down as they come (`## Planning notes`, Korean `## 기획 메모`). Lectern does not read it — checkboxes and dates there do not reach the work board. When people ask you to fold the notes in:
  - Move to-dos to 'To do', appointments with a set date and time to 'Schedule', things decided to 'Decisions', and how things stand to 'Current state', in the formats above.
  - Skip anything already there.
  - When a date is unclear ('around next Wednesday'), ask rather than guess — proposing a date counted from today is fine.
  - Don't edit or delete the notes. They are the person's writing — removing notes that have been folded in is up to them.
  - Afterwards add one line under today's date in the log — 'Folded in from planning notes: 2 to-dos, 1 event'.
- **Sub-tasks**: a subfolder can have its own WORK.md. Its parent is the WORK.md of the nearest folder above. Write a sub-task's to-dos and events only in its own file and don't copy them into the parent — Lectern gathers them there. A WORK.md that groups several sub-tasks can leave `status:` empty to have it worked out from them.
- Section names and order are a recommendation. Lectern reads only the front matter and the shape of to-do and event lines. Keep event lines in the 'Schedule' section (where people add events with Add event).
- Events and to-dos outside any task (meetings, admin) go in the common folder's `WORK.md`. Facts of one task (status, due date, to-dos, events) live only in that task's WORK.md — don't repeat them in review documents.
- The work board is a view. Don't write the board out as a file.
- 'Lines to check' on the work board are lines outside this format (an unknown status, a misspelled key, an unreadable date or time, a checkbox like `- []`, unclosed front matter). When people hand you such a line, fix it to the format.

## 6. HTML documents

- Their own styles (`<style>`) show as they are. Without styles, Lectern applies its document style.
- **Scripts do not run.** JavaScript charts (Chart.js, Plotly HTML exports and so on) stay blank. Draw charts as static SVG, or make them with chart code blocks in a Markdown document.
- Internet CSS, fonts and scripts are blocked. Keep styles inside the document.
- `<title>` is the title, `<meta name="description">` the summary, and `h1`–`h4` the contents. An `id` on `h2` makes a section link.
- Link documents and images with relative paths (`../research/x.md#outlook`) — they open inside Lectern.

## 7. What people hand to the AI

- **Location (@path lines)**: people right-click a block and paste `@research/report.md lines 12-17` into the terminal (in the Korean UI: `@research/report.md 12~17행`). The first part is the file, the rest is the source line range. Read those lines and work on them.
- From a heading it carries the section name, such as `@research/report.md lines 10-19 (section 'Summary')` — the whole section.
- From the code view it looks like `@src/report.py lines 14-19`.

## 8. Don't

- Don't put JavaScript charts in HTML reports (they do not show).
- Don't put functions or internet addresses in chart settings.
- Don't put documents in `node_modules`, `dist`, `build` or `.` folders (they are hidden).
- Don't put HTML for people in app source folders such as `src` or `web`.
- Don't use several `#` headings in one document or skip heading levels.
- Don't mix units or notes into table cells (it breaks number alignment).
- Don't put long text on one slide (the bottom is cut off).

## Summary — what goes into the personal rules or the instruction file

```markdown
## Documents (read with Lectern)
- Writing before formatting: decide the reader and the purpose first, write to the kind of document (narrative or bullet-point), and reread as the reader when done. No file paths or code formatting in the body; keep sources for facts you bring in.
- Detailed formatting is in the Lectern writing guide `<full path of this guide>` — read the section when writing tables, charts, boxes, slides or work cards.
- Write Markdown. One `# Title` first, then a one- or two-sentence summary paragraph. Don't skip heading levels (## → ###).
- Only values in table cells, units in the header. About six columns and one or two lines per cell (long explanations go outside the table); alignment marks (`:---:`) only when needed. Captions as `Table 1. Title` · `Figure 1. Title` right above a table, figure or chart, the source right below as `Source: organization (year)`; refer with `[Table 1](#table-1)`.
- Callouts as `> [!NOTE]` and so on; boxes between `<!-- box -->` and `<!-- /box -->` (first line `**Box 1. Title**`).
- Charts in ```vega-lite, ```echarts, ```plotly, ```dot (JSON values only, no internet addresses, data inside the chart as values — CSV only for large working data); diagrams in ```mermaid. HTML reports run no scripts.
- `@path lines 12-17` (Korean UI: `@path 12~17행`) from people means those lines of that file. Asked to summarize into a box after that line, insert exactly one box there.
- Slides are Lectern slides (read `slides.en.md` first); pptx goes through the skills `pptx-to-lectern` and `lectern-to-pptx`, and Word (docx) through the skill `lectern-to-docx` (a company Word template with `--template`). `WORK.md` at the top of a folder is the work card.
```
