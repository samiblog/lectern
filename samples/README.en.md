# Lectern samples — start here

An example project for looking around Lectern. Think of it as a **copper market research automation** project done together with Claude Code: code (`src/`), data (`data/`), research documents (`research/`), plans (`plans/`) and reports (`reports/`). The `guide/` folder explains how to use Lectern (in Korean).

> [!TIP]
> Click a document in the tree on the left to read it here. Click an entry in the contents on the right to jump to that section. **F1** opens the user guide (in English when the language is English) and **Ctrl+/** the keyboard shortcuts.

## What to try

1. Click the `plans` folder name — the folder overview lists each document with its title, summary and modified time.
2. Press **Ctrl+P**, type `동향` and press Enter — quick open by name, title or path.
3. Open [the research document](research/구리-시장-동향.md): tables with right-aligned numbers, a figure, callouts, a footnote and a chart that reads `data/월별-가격.csv`.
4. In the sidebar's **Code** group, click `src/report.py` — line numbers, language colors, and functions in the contents.
5. Right-click a table and choose **Copy location for Claude** — paste it into Claude Code in the terminal (**Ctrl+`**).
6. Open [Later tasks](plans/10-후속-과제.md), press **Ctrl+E**, add a line, **Ctrl+S**, then **Esc** — edit mode.
7. Look at the chart guide [guide/07-차트.md](guide/07-차트.md) — Vega-Lite, ECharts, Plotly and Graphviz code blocks.

## For AI (Claude Code)

[CLAUDE.en.md](CLAUDE.en.md) is the set of rules Claude Code follows when writing documents here (Korean: [CLAUDE.md](CLAUDE.md)). To give your own project the same rules, use **Teach Claude Code about Lectern** → **Copy request for Claude Code** in the settings (Ctrl+,) and paste it into Claude Code.

> [!NOTE]
> These samples live in Lectern's install folder. You can edit them, but reinstalling Lectern restores them. All numbers are examples. To reopen them, use **∨** (recent folders) on the tab bar → **Open samples**, or **Open samples** on the start screen.
