# Lectern samples — start here

An example project for looking around Lectern. Think of it as a **copper market research automation** project done together with Claude Code: code (`src/`), data (`data/`), research documents (`research/`), plans (`plans/`) and reports (`reports/`). The `guide/` folder explains how to use Lectern (in Korean).

> [!TIP]
> Click a document in the tree on the left to read it here. Click an entry in the contents on the right to jump to that section. **F1** opens the user guide (in English when the language is English), **Ctrl+/** the keyboard shortcuts, and **Shift+F1** brings you back to these samples from anywhere. Chapters of the user guide link to the matching sample documents.

## What to try

1. Click the `plans` folder name — the folder overview lists each document with its title, summary and modified time.
2. Press **Ctrl+P**, type `동향` and press Enter — quick open by name, title or path.
3. Open [the research document](research/구리-시장-동향.md): tables with right-aligned numbers, a figure, callouts, a footnote and a chart that reads `data/월별-가격.csv`.
4. In the sidebar's **Code** group, click `src/report.py` — line numbers, language colors, and functions in the contents.
5. Right-click a table and choose **Copy location for Claude** — in your own project, paste it into Claude Code in the terminal (**Ctrl+\`** — the key left of 1).
6. Edit mode (**Ctrl+E**, then **Ctrl+S** to save and **Esc** to close) works in your own projects and in a copy of this folder — the samples themselves are view-only (see the note below).
7. Look at the chart guide [guide/07-차트.md](guide/07-차트.md) — Vega-Lite, ECharts, Plotly and Graphviz code blocks.
8. Line editing [guide/08-한-줄-편집.md](guide/08-한-줄-편집.md) — fix lines in place and save at once: pick lines with **Insert**, move and delete them, insert elements with **/**, keep writing past the last line
9. Lectern slides: start with the guide [guide/09-Lectern-슬라이드.md](guide/09-Lectern-슬라이드.md), a detailed plain md document (in Korean) — skeleton, cells, layouts, text size, directives, editing, checking, presenting and converting to pptx — then the samples [slides/README.en.md](slides/README.en.md): basics, model decks by situation and complex layouts
10. vi keys [guide/10-vi-키.md](guide/10-vi-키.md) (in Korean) — optional: vi keys for reading (j·k·V·dd·yy·p·o·i·u) and the vi mode of the full editor (:w·:q)

## For AI (Claude Code)

[CLAUDE.en.md](CLAUDE.en.md) is the set of rules Claude Code follows when writing documents here (Korean: [CLAUDE.md](CLAUDE.md)). To give your own project the same rules, use **Teach Claude Code about Lectern** → **Copy request for Claude Code** in the settings (Ctrl+,) and paste it into Claude Code.

> [!NOTE]
> These samples live inside Lectern's program folder, so they are **view-only** — this tab has no terminal, edit mode, new documents or renaming (so that no commands run and no files change next to the program files). To edit them or try Claude Code with them, copy this folder elsewhere (for example to Documents) and open the copy. All numbers are examples. To reopen them, use **∨** (recent folders) on the tab bar → **Open samples**, or **Open samples** on the start screen.
