# Lectern: my diagram styles and color sets — a guide for AI

When a person right-clicks a diagram in Lectern and chooses **'Make my diagram style from this look…'** (for a chart, **'Make my color set from these colors…'**), you get a request with the diagram's place (`@path 3~9`), a number, and the folder to save in. Turn that diagram's look into values Lectern knows and write **one file**. Lectern only reads that folder; within three seconds the new number shows up in the picker and in Settings. How to write numbers and names is in `diagrams.en.md` in the same folder.

## 1. Steps

1. Read the diagram block in the request. Find what sets its look — `fill`, `stroke`, `stroke-width`, `stroke-dasharray` and `rx` in `classDef` and `style` lines, `curve` and `nodeSpacing` in `%%{init: …}%%`, widths in `linkStyle`, line breaks in box text (title and content), groups (`subgraph`). If there is a marker line (`%% style: 8 …`), that number is the base.
2. Pick the closest built-in number 1–10 as `base` and write only the values that differ (section 2). Do not repeat values the base already has.
3. Before saving, show the name and values as a table and ask — with one line on what carries over and what does not (colors, fonts, arrow shapes and so on).
4. When allowed, write one `name.json` in the folder from the request. Create the folder if it does not exist. If a file with the same name exists, do not overwrite it — ask. Use the number from the request (never a number another file uses — look at the other files first).
5. After writing, tell the person: it shows up in the picker and in Settings under that number; to use it, put `%% style: 11 Our company` in a block. If they want, replace that block's lines with the marker and drop the `classDef`/`style` lines that are no longer needed — do not edit the document before asking.

## 2. Look file

```json
{
  "kind": "style",
  "number": 11,
  "name": "Our company",
  "tip": "Navy title band, right-angle lines — weekly report",
  "base": 8,
  "corner": 4,
  "line": "step",
  "bold": true
}
```

| Key | Value | Meaning |
|---|---|---|
| `kind` | `"style"` | A look file (required) |
| `number` | whole number 11–99 | The number (required — the one in the request) |
| `name` | up to 24 characters | The name (required). Does not start with a digit and has no `·` `,` `;` `:`. Not the same as a built-in name (Card, Title band and so on) |
| `tip` | up to 80 characters | One line in the picker — what is different and when to use it |
| `base` | 1–10 | The base number (1 if missing). Anything not given below comes from it |
| `corner` | 0–24 | Box corner radius (px). In Graphviz, 0 is square and anything else is rounded |
| `border` | 0–4 | Box border width (px) |
| `line` | `"curve"`, `"step"`, `"straight"` | Line shape — curved, right-angle steps, straight |
| `line_width` | 0.5–4 | Line width (px) |
| `dash` | `true`, `false` | Dashed lines |
| `shadow` | `true`, `false` | Box shadow |
| `fill` | `"none"`, `"light"`, `"solid"` | Box fill — background color, light, dark (with light text) |
| `spacing` | `"tight"`, `"normal"`, `"wide"` | Space between boxes |
| `bold` | `true`, `false` | Bold box text |
| `title` | `"none"`, `"band"`, `"tint"`, `"rule"` | Title boxes — none, dark band, light band, rule under the title. In a box with a line break, the first line is the title |
| `zones` | `true`, `false` | A light color per group, in turn |
| `sketch` | `true`, `false` | Hand-drawn lines (Mermaid only) |

- Do not put colors in a look file. Box, emphasis and band colors come from the document style and the color set number — to carry colors over too, also make a color set file (section 3), after asking.
- Emphasis marks `:::key`, `:::warn` and `:::muted` are painted as in the base number (with `fill: "solid"`, as in 4 Solid; with title boxes, the band color).
- Mermaid draws on the classic look (hand-drawn with `sketch`), not the rounded neo look of 1 Default.

## 3. Color set file

```json
{
  "kind": "colors",
  "number": 9,
  "name": "Company colors",
  "tip": "The navy and orange of the company logo",
  "series": ["#17304f", "#2f5d8a", "#5b8db8", "#c2410c", "#6b7280"],
  "strong": "#17304f",
  "accent": "#c2410c"
}
```

| Key | Value | Meaning |
|---|---|---|
| `kind` | `"colors"` | A color set file (required) |
| `number` | whole number 9–99 | The number (required) |
| `name`, `tip` | as above | |
| `series` | 2–12 `"#rrggbb"` | Chart series colors, in order. Required |
| `strong` | `"#rrggbb"` | The default diagram box color (first series color if missing) |
| `accent` | `"#rrggbb"` | The key (`key`) emphasis color (second series color if missing) |
| `zones` | 1–12 `"#rrggbb"` | Colors for zones (per group) (series if missing) |

- Carry over, in order, the colors the diagram set with `classDef`/`style` or the chart set with `"scale": {"range": …}` or ECharts `color`. With a dark document style Lectern lightens dark colors.
- Pick colors so text stays readable on them and series colors are easy to tell apart.

## 4. Don't

- Don't write keys not in the tables (CSS, Mermaid settings, fonts, image addresses) — Lectern leaves unknown keys out and lists them under 'to fix' in Settings.
- Don't write numbers outside the ranges or colors other than `#rrggbb` (`red`, `rgb(…)`) — those values are left out.
- Don't put more than one style in a file (one file, one style). Don't use built-in numbers (looks 1–10, colors 1–8).
- Don't change the person's other files (other styles, Lectern's `config.json`).

## 5. Using it (tell the person)

- One diagram: `%% style: 11 Our company` in the block (Graphviz and charts use `//`); colors: `%% colors: 9 Company colors`. The 'Diagram style…' window shows a card for 11 too.
- One document: `<!-- diagram: style 11 Our company · colors 9 Company colors -->`. Every diagram without a marker: 'mine' under 'Diagram style · color set' in Settings.
- On a PC without the file (a document sent to a colleague, say) the number is unknown, so the default look and colors are drawn — hand over the file too and it looks the same.
