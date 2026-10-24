# Making your own Lectern style

This guide is for an AI such as Claude Code that is asked to make a **custom style** for Lectern, a document viewer for Windows. People can read it too.
A custom style is one CSS file. It sets the fonts, colors and spacing Lectern uses to show Markdown and HTML documents.

## 1. Where to save it, and when it shows up

- Folder: `%APPDATA%\Lectern\styles` (the folder Settings → 'Open style folder' opens — the request text gives the full path). Create it if it does not exist.
- One file = one style, named `<any name>.css` (for example `company-report.css`). Subfolders, names starting with `.`, and files over 1 MB are ignored.
- Save it as UTF-8.
- Within three seconds of saving, it appears in the **My styles** group at the bottom of the style list in the toolbar. While that style is selected, saving the file again reapplies it at once — no restart needed.
- Lectern only reads these files. The app never creates or edits a style file.

## 2. Header comment (start of the file)

The file must begin with this comment, one `key: value` per line.

```css
/* lectern-style
   name: Company report
   dark: no
   base: report
*/
```

| Key | Meaning | Default |
|---|---|---|
| `name` | Name shown in the style list (up to 60 characters) | The file name |
| `dark` | `yes` for a dark style. The app UI (toolbar, sidebar), code colors (highlight.js), terminal colors and diagrams switch to dark | `no` |
| `base` | Id of a built-in style to lay down first. Lectern applies that style, then this file on top — write only what you change | `default` when light, `dark` when dark |

Built-in ids for `base`: `default`, `report`, `office`, `consulting`, `notion`, `contrast`, `paper` (sepia), `book`, `academic`, `newsprint`, `magazine`, `manuscript` (typewriter), `github`, `docsite`, `solarized-light`, `gruvbox-light`, `dark`, `github-dark`, `nord`, `solarized-dark`, `dracula`, `one-dark`, `night` (night paper), `ink` (pure black).
With `dark: yes`, pick a dark base (`dark`, `nord` and so on).

## 3. Change the variables first

Most of the look comes from CSS variables on `:root`. Changing only the variables updates the document and also the app UI (toolbar, sidebar, contents, menu colors — the app derives its colors from them), the terminal background and text, and diagram colors. You rarely need variables beyond this table.

| Variable | Used for |
|---|---|
| `--md-bg` | Document background (the app background comes from it too) |
| `--md-fg` | Body text |
| `--md-heading` | Headings (and selected items in the app) |
| `--md-muted` | Dim text — quotes, h5/h6, code language names |
| `--md-border` | Lines — table cells, code boxes, horizontal rules, h1/h2 underlines |
| `--md-link` | Links (also the app accent color and terminal cursor) |
| `--md-strong` | Bold text color (defaults to the body text color) |
| `--md-code-bg` | Code block, inline code and metadata background (also the terminal background) |
| `--md-quote-bar` | Bar to the left of quotes |
| `--md-th-bg` | Table header row background |
| `--md-th-fg` | Table header row text (white-ish when the header is dark — defaults to the heading color) |
| `--md-th-rule` | Thick line under the table header row |
| `--md-stripe` | Background of even table rows |
| `--md-alert-note` / `-tip` / `-important` / `-warning` / `-caution` | Bar, title and light background of callouts (`> [!NOTE]` and so on) |
| `--md-font` | Body font |
| `--md-heading-font` | Heading font |
| `--md-mono` | Code font |
| `--md-size` | Body font size (px — multiplied by the toolbar text size) |
| `--md-line` | Line height (for example `1.7`) |
| `--md-width` | Maximum text width (px) |
| `--md-h1-rule` / `--md-h2-rule` | Line under h1/h2 (`1px solid var(--md-border)`, or `0` for none) |

## 4. Add rules for anything else

The document lives inside `.md-body`. **Start every rule with `.md-body`** so the app UI (toolbar, sidebar, menus) is left alone. The structure you can style:

| What | Selector |
|---|---|
| Headings | `.md-body h1` … `h6` |
| Paragraphs and lists | `.md-body p`, `ul`, `ol`, `li` |
| Checklists | `.md-body .task-list-item`, `.task-list-item-checkbox` |
| Links | `.md-body a` (web links `a.ext` — with a ↗ mark, project files `a.file-link`, paths in the text `a.path-link`, links that cannot open `a.link-off`) |
| Bold, emphasis, highlight | `.md-body strong`, `em`, `mark`, `kbd` |
| Quotes | `.md-body blockquote` (callouts are `blockquote.alert` — below) |
| Callouts | `.md-body blockquote.alert.alert-note` (`-tip`, `-important`, `-warning`, `-caution`), with the title line `.alert-title`. Their color is the box's `--alert` variable |
| Code blocks | `.md-body .code-block` > `.code-tools` (language `.code-lang`, copy button `.code-copy`) + `pre` > `code.hljs` |
| Inline code | `.md-body :not(pre) > code` |
| Tables | `.md-body .table-wrap` (border and scroll box) > `table` > `thead th`, `tbody td`. Number columns are `th.num` / `td.num` (right-aligned) |
| Images | `.md-body img`; an image that failed to load is `.image-off` |
| Math | Blocks `.md-body .math-block` (with `.katex-display` inside), inline `.katex` |
| Diagrams | `.md-body pre.mermaid` (`.mermaid-ok` once drawn, with an `svg` inside) |
| Charts (Vega-Lite, ECharts, Plotly, Graphviz) | `.md-body pre.lec-chart` (`data-chart` is `vega-lite`, `vega`, `echarts`, `plotly` or `dot`; `.chart-ok` once drawn, with an `svg` inside). Chart colors come from the same style palette as diagrams, not from CSS |
| Diagrams or charts that could not be drawn | `.md-body .diagram-error` (a `p` with the reason and a `pre` with the source) |
| Metadata | `.md-body .front-matter` (`details` — `summary`, `table`) |
| Footnotes | `.md-body .footnotes-sep`, `.footnotes`, `.footnote-ref` |
| Horizontal rules | `.md-body hr` |

**Leave alone**: classes starting with `lec-` (`.lec-fold`, `.lec-changed`, `.lec-target`, `.lec-spotlight`, `.lec-picked` and so on — fold arrows, change and find marks, section focus) and the `max-width`, `padding` and `font-size` formulas of `.md-body`. Change the width with `--md-width` and the size with `--md-size`.

## 5. Rules to follow

- **Load nothing from the internet.** Lectern removes `@import`, `url(https://…)` and web fonts (they do not work). To include an image, embed it with `url(data:…)`.
- **Use only fonts installed on the PC.** List a Latin font, then a Korean font, then a Windows default, ending with `"Malgun Gothic"` (sans) or `"Batang"` (serif) and `sans-serif` / `serif` — so Korean text still shows on a PC without the first fonts.
  Example: `--md-font: "Segoe UI", "Pretendard", "Malgun Gothic", sans-serif;`
- **Sizes through variables**: a px size in a new rule does not follow the toolbar text size − and +. Use `em`, or write `calc(13px * var(--md-scale, 1))`.
- **Contrast of at least 4.5:1** between text and background (WCAG) — body text, headings, links, dim text and table header text. If the header row is dark, set `--md-th-fg` to a light color.
- Make headings look different from body text, and the table header row different from body rows.
- For a dark style, put `dark: yes` in the header so the app UI and code colors turn dark too.
- Printing and PDF always switch to black text on white paper (nothing to do).

## 6. Examples

### A light style that only changes variables

```css
/* lectern-style
   name: Company report (navy)
   dark: no
   base: report
*/
:root {
  --md-heading: #14306b;
  --md-link: #1d4fbf;
  --md-th-bg: #14306b;
  --md-th-fg: #ffffff;
  --md-th-rule: #0b1d44;
  --md-font: "Segoe UI", "Pretendard", "Malgun Gothic", sans-serif;
  --md-size: 15px;
  --md-width: 920px;
}
```

### A dark style with a few rules

```css
/* lectern-style
   name: Night sea
   dark: yes
   base: dark
*/
:root {
  --md-bg: #0f1b2a;
  --md-fg: #d6e2ee;
  --md-heading: #9fd3ff;
  --md-muted: #8fa3b8;
  --md-border: #24384f;
  --md-link: #6cc0ff;
  --md-code-bg: #15263a;
  --md-th-bg: #1b3149;
  --md-stripe: #12223a;
}
.md-body h1 { border-bottom: 2px solid var(--md-link); }
.md-body h2 { color: var(--md-link); }
.md-body blockquote:not(.alert) { border-left-color: var(--md-link); font-style: italic; }
```

## 7. Check it

1. Pick it from 'My styles' at the bottom of the style list in the toolbar.
2. Open a document with headings, a table (header row, even rows, number columns), code blocks, inline code, all five callouts, quotes, a checklist, links, math and a diagram. `samples\docs\01-기능-점검.md` in the Lectern repository is a good one.
3. Change the text size with − and + in the toolbar (everything should scale).
4. For a dark style, check that the sidebar, menus and code colors are dark and the terminal text is readable.
5. To fix something, edit and save the file — it is reapplied at once.
