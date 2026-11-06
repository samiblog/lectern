# Lectern slide deck guide (for AI)

When the user asks for slides, write one `.md` file by this guide. People view it in Lectern's slide window and edit the text in the cells one line at a time.

It starts from Marp but is Lectern's own format. Other apps show the cells as plain text. Do not make presentations in HTML.

## 1. Skeleton

```markdown
---
marp: true
title: Copper market outlook 2026
paginate: true
footer: Commodity research · 2026-11
---

<!-- _class: lead -->
<!-- _paginate: false -->

# Copper market outlook 2026

Between slower demand and supply disruption

---

<!-- layout: two -->

## Stocks fell and prices rose

::: a card
### Stocks

Exchange stocks are **192 kt**.
:::

::: b
| Quarter | Price |
|---|---:|
| Q1 | 8,650 |
| Q2 | 9,120 |
:::
```

- `marp: true` in the front matter makes it a deck.
- Separate slides with a `---` line, with blank lines around it.
- A slide is 1280×720. For 4:3 add `size: 4:3` to the front matter. It is then 960×720 with 848 of usable width, so scale the widths in section 5 by 0.7.
- Put the title (`#`, `##`) outside the cells, one per slide.
- Write directives as HTML comments at the top of the slide.
- Any other HTML comment is a speaker note. It can go anywhere on the slide and does not count as text outside the cells. After the last cell reads well. A colon is fine (`<!-- Source: statistics office -->`); only a directive name (`layout`, `text`, `class` and so on) makes it a directive. Comments in code blocks are code.
- Write `lead` slides such as covers and section slides without cells. `footer` and `header` from the front matter also show on `lead` slides. To drop one on a slide, write `<!-- _footer: '' -->`.
- Do not use footnotes. Put sources briefly in a cell or in the notes.

## 2. Cells

A cell runs from a `::: name words…` line to a `:::` line. Inside is ordinary Markdown.

- Tables, lists, callouts, images, math, Mermaid and charts all work.
- Never leave out the head or the closing line. Do not nest cells.
- On a slide with a layout, everything except the title goes in a cell.

Style words:

| Word | Look |
|---|---|
| `card` | Bordered card |
| `accent` | Accent box |
| `dark` | Dark box |
| `note` | Yellow note |
| `kpi` | Big number card; the first `**number**` line is large |
| `center` | Center the text vertically |
| `text-center` · `text-right` | Center or right-align the text |
| `cols-2` · `cols-3` | Set the text in 2 or 3 columns |

Words combine (`::: b card center`, `::: a kpi accent`). Use `center` when a cell has little text.

A KPI cell looks like this.

```markdown
::: a kpi
**9,120**
LME price ($/t)
:::
```

The number uses the style's accent color. To change it, add `.word strong { color: #… }` to your own word. For a bigger number use a cell size (`::: a kpi 28`). The number is about twice the cell size and the label is the cell size. The default is 18pt with a 34pt number. Word order does not matter (`::: a kpi accent center 24`, `::: b card at 100 200 300 120 16`).

## 3. Layouts

Write `<!-- layout: name -->` on each slide. It does not carry over to the next slide.

| Name | Cells | Shape |
|---|---|---|
| `two` | a b | Two halves |
| `two-left` | a b | Left 2 : right 1 |
| `two-right` | a b | Left 1 : right 2 |
| `three` | a b c | Three columns |
| `quad` | a b c d | 2×2 |
| `left-stack` | a b c | Big a on the left, b over c on the right |
| `right-stack` | a b c | a over c on the left, big b on the right |
| `kpi` | a b c d e | Four small cells on top, wide e below |
| `kpi-two` | a b c d e | Three small cells on top, wide d and small e below |
| `stack` | a b | One above the other |

Leaving a card out of `kpi` leaves a gap. With three cards, use `kpi-two` or a grid (`<!-- grid: t t t / a b c / e e e -->`, `<!-- rows: auto auto 1fr -->`).

For anything else use a grid. Draw it with cell names; `/` separates rows.

```markdown
<!-- grid: a a b / c d b -->
<!-- cols: 1fr 1fr 1.2fr -->
<!-- rows: 1fr 1fr -->
```

- Use `t` in a grid for the title area (`t t / a b`). A slide with a title needs `t`. Do not write a title on a grid without `t`.
- `cols` has one value per column, `rows` one per row. The `t` row counts (`t t / a b / c d` needs three `rows`). `1fr`, `auto` and `200px` all work.
- You may leave out `cols` and `rows`. Columns are then equal, and rows are equal except the `t` row, which fits its text.
- To fill a slide with one cell, use `<!-- grid: t / a -->`.
- `.` is an empty spot (`<!-- grid: t t t / a . b / . c . -->`). It needs no cell and the check stays quiet.
- Rows and columns have no limit. A 13-column Gantt or a 35-cell calendar works. Use `px`, `fr` and `repeat()`: `<!-- cols: 120px repeat(12, 1fr) -->`.
- Color a cell with your own word and CSS: `.risk { background: #c0392b; color: #fff; }`. Bold text follows the cell color. Add `.risk h3 { color: inherit; }` for headings.
- For vertical text use `writing-mode: vertical-rl; text-orientation: sideways; transform: rotate(180deg);`.

To place a cell yourself, write `at x y width height` in px, from the top left of the slide. Do not use `layout` with it.

```markdown
::: hub note at 460 250 300 120
### Product margin

The spread is the key
:::
```

- The usable area is x 56–1224, y 110–660. The title is above and the footer below. `eyebrow` does not change this.
- Cells that overlap each other or the title show up in Check.

Draw lines between cells with `links`. The text in the cells can still be edited line by line. Join cell names with commas.

```markdown
<!-- links: cost>hub, freight>hub, hub<>demand, hub--note -->
```

- `a>b` is an arrow, `a<>b` has two heads, `a--b` is a plain line. Lines cannot carry text.
- It works on `at` cells and grid cells. A line joins the cell centers and stops at the cell edges.
- There is one line per pair of cells. If two cells need several lines, keep the diagram as a picture.
- Change line color and width in the document CSS (`section { --lec-link-color: #c2410c; --lec-link-width: 3; }`).
- Leave some space between the cells, or the line will not show.

## 4. Text size

Defaults: title 30pt, subheading 20pt, body 18pt, table 14pt, callout 16pt, code 14pt. These match PowerPoint points and do not change with the style.

Change only what you need.

| Scope | How |
|---|---|
| Whole deck | `text: title 26, table 12` in the front matter |
| One slide | `<!-- text: table 12 -->` |
| One cell | A number in the cell head (`::: b card 14`) |

The kinds are `title` `sub` `body` `table` `box` `code`. A cell size also sets the tables and callouts in that cell.

**Do not go below 12pt for tables or 14pt for body text.** When something overflows, cut text or split the slide rather than only shrinking it. For a document that is read rather than shown, write `reading: true` in the front matter; the limits are then 10pt and 12pt. Anything below the limit shows up in Check.

## 5. How much fits

Text that overflows is cut, not shrunk. You cannot see the screen, so stay within these limits. If a cell goes over, split the slide.

A body line is 35px, a subheading line 50px and a table row 40px. At 18pt a line holds cell width ÷ 23 Korean characters, or about ÷ 14 Latin characters. These are rough.

| Layout | Cell | Size (px) | Body lines | Characters (Korean) | Table rows |
|---|---|---|---:|---:|---:|
| `two` | a b | 575×555 | 15 | 24 | 12 |
| `two-left` | a | 767×555 | 15 | 32 | 12 |
| `two-left` | b | 383×555 | 15 | 16 | 12 (up to 3 columns) |
| `two-right` | a | 383×555 | 15 | 16 | 12 (up to 3 columns) |
| `two-right` | b | 767×555 | 15 | 32 | 12 |
| `three` | a b c | 377×555 | 15 | 16 | 12 (up to 3 columns) |
| `quad` | a b c d | 575×270 | 7 | 24 | 5 |
| `left-stack` | a | 690×555 | 15 | 29 | 12 |
| `left-stack` | b c | 460×270 | 7 | 19 | 5 |
| `right-stack` | a c | 460×270 | 7 | 19 | 5 |
| `right-stack` | b | 690×555 | 15 | 29 | 12 |
| `kpi` | a b c d | 279×144 | Number + 1 line | 11 | Do not use |
| `kpi` | e | 1168×397 | 11 | 50 | 9 |
| `kpi-two` | a b c | 377×144 | Number + 1 line | 15 | Do not use |
| `kpi-two` | d | 773×397 | 11 | 33 | 9 |
| `kpi-two` | e | 377×397 | 11 | 16 | 9 (up to 3 columns) |
| `stack` | a b | 1168×270 | 7 | 50 | 5 |

- `card`, `accent`, `dark`, `note` and `kpi` cells have padding that takes 32px of width and 24px of height.
- A heading or text in the same cell leaves fewer table rows.
- For grid, `at` and `cols-2` cells, estimate from the cell size. A grid has 1168 of width and 555 of height below the title. The gap between cells is 18px across and 14px down.
- A title fits about 30 Korean characters per line, and a subheading fits cell width ÷ 26. Lists lose about 40px of width to the indent.
- Latin text fits about 1.6 times as much (at 18pt, cell width ÷ 14). A word longer than the cell breaks in the middle.
- Code lines do not wrap. At 14pt a line holds cell width ÷ 11 characters and is 29px high. Overflow shows in the check, so split the line.
- Table rows include the header row.
- Cells share the slide height. For a cell with little text or a short table, use `center`.
- On dark slides (`invert`, `lead`) cells, tables and code follow the slide colors. Only `note` stays a yellow box.
- `eyebrow` sits in the empty space above the title and does not reduce the cell height.
- Changing the text size changes these in proportion. At 12pt a table row is 35px.
- Keep slides short. Short lists beat paragraphs.
- Charts, diagrams and images shrink to fit the cell. Text does not.

## 6. Charts and images

Write charts as code blocks: `vega-lite`, `echarts`, `plotly`, `dot`, `mermaid`. Charts in a cell fit its width and the height left. A heading or text in the same cell is fine.

- `vega-lite`: use `"width": "container"` and leave out `height`. Give values with `data.url` or `data.values` in the document.
- `echarts`: an ECharts option as JSON. Leave out `height` and `width`.
- `plotly`: `{"data": […], "layout": {…}}` as JSON. No map types.
- Settings are JSON values only. Functions do not work.
- In a `vega-lite` `layer`, repeat the axis `scale` and `sort` on every layer. On one layer alone they do not apply. Give the order as an array (`"sort": ["Jan", "Feb"]`).
- Only `vega-lite` reads `data.url`. For `echarts` and `plotly`, put the values in the settings.
- The ECharts legend defaults to the bottom. Move it up with `"legend": {"top": 0}` or keep `grid.bottom` at 56 or more.
- A donut's `innerRadius` is in px. In a small cell it turns into a thin ring, so keep it near a sixth of the cell height.
- Inside a cell, `vega-lite` draws axes and legends to fit the cell. Lots of text in the same cell makes the chart shorter.
- In `vega-lite`, write the axis number format as `",d"`. A bare `","` gives `1.5e+4`.
- `center` on a cell also works for charts and diagrams.
- Chart values cannot be edited line by line; people use Ctrl+E. Put values that change often in a CSV. The CSV view in Lectern is read-only, so edit it in a spreadsheet or ask Claude. Press F5 afterwards to redraw the chart.

```vega-lite
{
  "width": "container",
  "data": {"url": "data/monthly.csv"},
  "mark": "line",
  "encoding": {
    "x": {"field": "month", "type": "ordinal", "sort": null},
    "y": {"field": "price", "type": "quantitative", "scale": {"zero": false}}
  }
}
```

- Paths in `data` and images are relative to **the folder of this md file**.
- When converting a document from another folder, check the paths. Put the new file next to the original.
- Data from the internet is not read.
- Write `$` in amounts as is (`$11,220`, `$/t`). Math needs `$x$` with no space just inside the `$` signs and no digit after the closing `$`.

Image syntax:

- `![w:300 alt text](images/a.png)` image size; alt text may follow. An image wider than its cell shrinks and keeps its proportions.
- Images in a cell shrink to fit. Text in the same cell takes its space first.
- `![bg right:40%](images/a.png)` background on the right 40%. Use `left` for the left. Cells and grids shrink to the width left. Add `contain` to keep the whole image.
- Several `![bg](a.png)` lines split the background side by side. They do not overlap. `![bg vertical](a.png)` splits top to bottom.
- `![bg sepia](a.png)` filter: `blur`, `brightness:.6`, `contrast`, `grayscale`, `hue-rotate`, `invert`, `opacity`, `saturate`, `sepia:50%`.
- Wrap file names with spaces or brackets: `![Flow](<images/process flow (final).svg>)`.
- The check cannot measure text over a photo. Darken the photo and use `invert` (`![bg brightness:.5](a.png)`). For longer text use a `dark` cell. On a dark slide it is a translucent black backing.
- When bold text ends in punctuation, do not attach a letter right after the closing `**`. Add a space.

## 7. Directives

| Directive | Meaning |
|---|---|
| `<!-- _class: lead -->` | Center this slide like a cover; also for section slides |
| `<!-- _class: invert -->` | Make this slide dark |
| `<!-- _color: #ffd27f -->` | Text color of this slide, including the title, bold text and links |
| `<!-- _footer: '' -->` | Drop the footer on this slide (`_header` too) |
| `<!-- _backgroundColor: #17293d -->` | This slide's background |
| `<!-- _paginate: false -->` | No page number on this slide |
| `<!-- eyebrow: Market summary -->` | Small label above the title |
| `<!-- hidden: true -->` | Hidden slide: left out of the presentation and PDF, and hidden in an exported pptx |

A leading `_` means this slide only. `class` and `backgroundColor` without `_` carry over. `layout`, `grid`, `text` and `eyebrow` are always this slide only.

## 8. HTML slides

Use HTML and SVG only for what cells cannot do. **People cannot edit such slides line by line**, and chart values are hard to change. First see whether cells and `at` can do it.

- Write per-slide CSS as `<style scoped>`. `section` is the slide.
- `<style>` applies to the whole deck, as does `style: |` in the front matter.
- Slide content is centered vertically by default. To start at the top, use `section { justify-content: flex-start; }`.
- Scripts do not run. `@import`, `@font-face`, `@keyframes`, nested rules, `position: fixed` and `url()` (except data images) are removed. A shorthand that holds both `url()` and a variable removes the whole rule.

## 9. After writing

Lectern collects overflow and mistakes under 'Check' in the status bar. When the user pastes that list into the terminal, fix it like this.

| Message | Fix |
|---|---|
| Cell a overflows by 120px | Cut text or split the slide; for a table, reduce the table size on that slide |
| Cell a overflows sideways by 80px | Use fewer table columns or a wider cell |
| Cell a overlaps the title | Set the `at` y to 110 or more |
| Cells a and b overlap | Move the `at` position |
| Cell a runs off the slide | Keep x+width within 1224 and y+height within 660 |
| The table is small at 10pt (limit 12pt) | Cut text or split the slide; for a reading document use `reading: true` |
| There is no cell x for this link | Fix the cell name in `links` |
| Cell z is not in the layout | Use a cell name from the layout |
| Cell c is empty | Fill it or change the layout |
| Cell a has no closing ::: | Add the closing line |
| Could not read this as a cell mark | Start the line with `::: name`: three colons and a space |
| Cell a appears twice | Use each cell name once per slide |
| Cell a has an unknown word 'x' | Fix the word. For your own CSS word, write a `.x` rule |
| 'x' is not a directive, so it was read as a note | Fix the directive name |
| Every grid row needs the same number of cells | Use the same count in each row |
| Could not read the grid | Use letters and numbers for names and a dot for an empty spot |
| Grid cell a is not a rectangle | Keep each name in one rectangle |
| A comment is not closed | Add `-->` |
| A code block is not closed | Add the closing line |
| Text sits right above --- | Add a blank line above `---` |
| Text is too close to its background | Change the text color or the background |
| Code is cut off at the side | Split the line |
| Image not found | Fix the path. It is relative to this md file |
| Could not draw a chart or diagram | Fix the settings or the data path. The reason is in the text |
| Asterisks were not read as bold | Add a space after the closing `**` |
| There is text outside the cells | Move it into a cell |
| There is no layout 'x' | Use a name from the table above |

For `Cell a overflows by 120px (cell height 300px)`, cut four body lines or three table rows.

The sample project has ten model decks and how each was built, in `slides/README.md` (`samples/slides/` in the install folder). In a similar situation, follow how that example uses cells. Twenty complex layouts such as dashboards, Gantt charts and risk matrices are in `slides/복잡한-배치/README.en.md`.

## 10. Good slides

- Make the title the conclusion, not the topic (`Stocks fell and prices rose`).
- One point per slide. Pick the layout that fits the content.
- Four numbers: `kpi`. Comparisons: `two`, `three`. Picture with notes: `left-stack`.
- Start with a `lead` slide, and add one when the topic changes.
- Put explanations in speaker notes.

## 11. Working with PowerPoint

When the user asks to move a pptx into Lectern slides, to build slides from a md document using a pptx as a reference, or to export slides to pptx, use the Claude Code skills `pptx-to-lectern` and `lectern-to-pptx`. They are in `skills/` in the Lectern program folder (`_internal\skills` when installed).

If the skills are not installed yet, ask the user first. If they agree, copy both folders to `~/.claude/skills/`. If not, read `SKILL.md` in that folder and run its scripts from there.
