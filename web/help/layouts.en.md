# Writing Lectern page layouts

This guide is for AI tools (Claude Code and others) that make a Lectern **page layout**. A page layout is the output template applied when an md document is exported as PDF or html. The text stays in the md document; the layout decides the cover, headers, page size, fonts and colours (D145).

People pick one from the **Layout** list in the Export window (right-click a document, 'Save as PDF…' or 'Save as html…'). Writing `layout: layout id` in the document's front matter selects it from the start.

## One file is one layout

- Save your layouts as `name.html` in the `layouts` folder of the settings folder (`%APPDATA%\Lectern\layouts`). The file name is the layout id (`user/name`). Names must not start with `.` or `_`.
- Read the built-in layouts (`web/layouts/*.html`) as examples. Copying the closest one and changing it is the fastest way. Do not edit the built-in files.
- A file has three parts — a head comment, `<style>`, and the skeleton html.

~~~html
<!--lectern-layout
name: 분기 보고
name_en: Quarterly report
group: 업무·공공
group_en: Office and public sector
pages: A4
fields: title, date, dept, author
slots: summary
description: One line in Korean — shown in the Export window
description_en: One line in English
-->
<style>
:root { --md-font: "Segoe UI", "Malgun Gothic", sans-serif; --md-size: 13.5px; }
@page { size: A4; margin: 20mm; @bottom-center { content: counter(page); } }
.lay-quarterly .cover h1 { font-size: 24pt; }
</style>
<header class="cover"><h1>{{title}}</h1><p data-if="dept">{{dept}} · {{date:long}}</p></header>
<section data-if="slot:summary"><div class="lay-slot">{{slot:summary}}</div></section>
<main class="md-body">{{body}}</main>
~~~

### Head comment

| Key | Meaning |
|---|---|
| `name`, `name_en` | The name in the list |
| `group`, `group_en` | Group — one of the built-in groups or a new name |
| `pages` | Page size shown, such as `A4`, `Letter`, `152×225mm`; `continuous` for a layout without pages |
| `fields` | Front matter keys the layout uses (comma-separated) — the window says which are empty and copies a sample |
| `slots` | Named box slots (comma-separated) |
| `description`, `description_en` | One line |

Never write `-->` inside the head comment — the comment would end there. Refer to boxes as "the box named summary".

## Slots

Lectern fills the `{{…}}` placeholders of the skeleton. Values go in as text only (never read as html).

| Placeholder | What goes in |
|---|---|
| `{{body}}` | The document body — without the front matter table, without the leading `# title` when the layout uses `{{title}}`, and without boxes moved to slots. Use once |
| `{{title}}` | Front matter `title`, else the document's `# title`, else the file name |
| `{{date}}` | Front matter `date` as written, else today. `{{date:long}}` November 15, 2026, `{{date:dot}}` 2026. 11. 15., `{{date:iso}}` 2026-11-15 |
| `{{key}}` | That front matter value (lists joined with commas) |
| `{{a\|b\|'text'}}` | The next one if the first is empty; quoted text as is |
| `{{t:한국어\|English}}` | Chosen by document language — English if front matter `lang` starts with `en` |
| `{{toc}}` | Contents — the body's `##` and `###` (`<nav class="lay-toc">`, `li.lv2`, `li.lv3`). No page numbers |
| `{{slot:name}}` | Moves the named box here (below). Without one, the front matter key of the same name, or a default like `{{slot:disclaimer\|'text'}}` |

Korean front matter keys also work; see the Korean guide for the list of equivalents (제목 title, 작성자 author, 날짜 date, 기관 org and so on).

### Attributes

- `data-if="key"` — removes the element when the value is empty. `data-if="!key"` removes it when present. `data-if="slot:name"` keeps it only when the slot has content.
- `data-each="key"` — repeats the element for each list item (`approvers: [Staff, Lead, Head]`, or comma-separated text). `{{.}}` is the item inside.

### Named boxes

A box opened with a `<!-- box: summary -->` line in the document moves into the layout's `{{slot:summary}}`. If the layout has no such slot, it stays an ordinary box in the body — no text is lost. A bold first line (`**…**`) or `Box 1.` title is dropped in the slot (the layout gives the slot its own label). Wrap a slot in `<div class="lay-slot">` to drop the box border.

## CSS

- The skeleton goes inside `<div class="lec-layout lay-filename lay-paged">` (`lay-flow` for layouts without pages). Characters other than letters, digits and `-` in the file name become `-`. Write rules as `.lay-filename …` so layouts don't mix.
- Lectern's document styles (base.css) shape the body elements. Change them with CSS variables on `:root`: `--md-font`, `--md-heading-font`, `--md-size` (px), `--md-line`, `--md-fg`, `--md-heading`, `--md-muted`, `--md-border`, `--md-link`, `--md-th-bg`, `--md-th-fg`, `--md-th-rule`, `--md-stripe`, `--md-code-bg`.
- Body elements: `h2`, `h3`, `p`, `ul`, `ol`, `table` (inside `.table-wrap`), caption paragraphs `p.caption` (table, figure and box numbers — Lectern adds the class), source lines `p.lec-source`, callouts `blockquote.alert` (`--alert` is the kind colour), quotes `blockquote:not(.alert)`, boxes `aside.lec-textbox` (title `.lec-textbox-title`), charts `.lec-chart`, Mermaid `pre.mermaid`, math `.katex`, footnotes `.footnotes`.
- **Pages**: `@page { size: A4; margin: …; }`, headers and footers in margin boxes such as `@top-left`, `@top-right`, `@bottom-center` with `content: counter(page)` or `counter(pages)`. For the document title in a header use `content: {{css:title}};` — inside `<style>` only `{{css:expression}}` is allowed (inserted as a safe CSS string). For a separate cover page use `@page cover { margin: 0; }` and `.cover { page: cover; }` — a change of named page starts a new page. `@page :first` for the first page only, `@page :left` and `:right` for book spreads.
- **Two columns**: `.md-body { columns: 2; }`, with `column-span: all` for wide tables, charts and captions.
- **Screen**: an exported html opened in a browser shows paged layouts as paper on a grey background (_base.css). Use `@media screen` or `@media print` for one or the other.
- **Fonts**: list only font names installed on the PC (Segoe UI, Calibri, Georgia, Malgun Gothic and so on — the next is used if one is missing). Do not embed font files.

## Not allowed

Lectern removes these so the file opens safely in anyone's browser:

- `<script>`, `on…=` event attributes, `javascript:` addresses, `<iframe>`, `<object>`, `<form>`, `<link>`, `<meta>`
- CSS that loads from the internet: `@import`, `url(…)` other than `data:`, `image-set(…)`. Background images only as `data:`
- Internet images (`src="https://…"`)

## After writing it

1. In Lectern, open a document, right-click its margin and choose 'Save as html…'. Pick the new layout under **Layout** in the Export window to preview it.
2. Switch the format to PDF to check page breaks, headers and page numbers.
3. After editing the file, pick the layout again or reopen the window to see the change.
