# Lectern slides samples

The order for learning Lectern slides, from the top. The full guide is the 'Lectern slides' chapter of the **F1** manual.

New to slides? Read the guide [guide/09-Lectern-슬라이드.md](../guide/09-Lectern-슬라이드.md) first (in Korean) — the content of these samples written out as a plain md document: skeleton, cells, layouts, text size, amount per slide and directives, then editing, presenting and converting to pptx. It ends with links back to these samples. The full order of the samples is on [the first page](../README.en.md).

> [!TIP]
> The installed samples are read-only. To follow along, make new Lectern slides in your own project with **New** (Ctrl+N), or copy this folder and open the copy.

The samples are in Korean. The folders are `기초` (basics), `상황별` (by situation) and `복잡한-배치` (complex layouts).

## 1. Basics

Start here.

| Order | Document | What it teaches |
|---|---|---|
| 1 | [First look](기초/01-처음-보기.md) | The slide window, presenting, front matter |
| 2 | [Cells and layouts](기초/02-칸과-배치.md) | Cells, layouts, Structure |
| 3 | [Making slides from templates](기초/03-템플릿으로-만들기.md) | Picking templates slide by slide, then converting to pptx |
| 4 | [Key practice](기초/04-키-연습장.md) | Lines, text size and slides by keyboard |
| 5 | [A grid made by keyboard](기초/05-키보드로-만든-격자.md) | Building a grid without the mouse |
| 6 | [Text size chart](기초/06-글자-크기-기준표.md) | Cell sizes and default sizes |
| 7 | [html presentation](기초/07-html-발표.md) | Convert to html, slide positions (`impress:`) — `07-html-발표.html` next to it is the result |

## 2. Model decks by situation

Pick the one that fits. View the finished deck in the slide window, then follow its process document from the start.

| Situation | Finished deck | Process | What it teaches |
|---|---|---|---|
| Report to executives at once | [01 Executive summary](상황별/01-경영-요약.md) | [Process](상황별/과정/01-경영-요약-과정.md) | Conclusion first, `kpi`, ending on a decision |
| Choose among three options | [02 Comparing options](상황별/02-대안-비교.md) | [Process](상황별/과정/02-대안-비교-과정.md) | Criteria first, `three`, a highlighted table row |
| Explain a market with data | [03 Market analysis](상황별/03-시장-분석.md) | [Process](상황별/과정/03-시장-분석-과정.md) | CSV charts, `left-stack`, titles that say what the chart shows |
| Draw causes and effects on one slide | [04 Cause map](상황별/04-원인-지도.md) | [Process](상황별/과정/04-원인-지도-과정.md) | `at`, `links`, diagrams you can edit |
| Plan an uncertain year | [05 Scenarios](상황별/05-시나리오.md) | [Process](상황별/과정/05-시나리오-과정.md) | Summing probabilities, weighted averages, signals and responses |
| Hand in a report people read at their desk | [06 Monthly report](상황별/06-월간-보고.md) | [Process](상황별/과정/06-월간-보고-과정.md) | `reading: true`, 4:3, a fixed source line |
| Explain technology to developers | [07 Tech seminar](상황별/07-기술-세미나.md) | [Process](상황별/과정/07-기술-세미나-과정.md) | Code length, formulas, sequence diagrams |
| Tell a story in pictures | [08 Photo record](상황별/08-사진-기록.md) | [Process](상황별/과정/08-사진-기록-과정.md) | Backgrounds and filters, text over pictures, what Check cannot see |
| Show a year's schedule | [09 Roadmap](상황별/09-로드맵.md) | [Process](상황별/과정/09-로드맵-과정.md) | A hand-drawn `grid`, dependencies, checkboxes |
| Turn an md document into Lectern slides | [10 From document to slides](상황별/10-문서에서-발표로.md) | [Process](상황별/과정/10-문서에서-발표로-과정.md) | Picking the message, cutting the source, linking sources |

Every process document has the same seven steps.

1. **Decide first.** Who is listening, what they decide, how many slides.
2. **Ask Claude.** Put the request in the terminal and tell it to follow the guide (`web/help/slides.en.md`).
3. **Write the titles first.** The titles alone should read as a story.
4. **Fill the cells.** Pick a layout that fits how much you have to say.
5. **Fix what Check finds.** Paste the **Check** list into the terminal and Claude fixes it.
6. **Polish by hand.** Fix things in place with F2.
7. **Present and share.** Present with Shift+F5, then **Convert to pptx**, **Convert to html** (an impress.js presentation that opens in a browser) or use **Print / Save as PDF…**.

## 3. Complex layouts

For slides with many uneven cells, see [ten complex layouts](복잡한-배치/README.en.md): dashboards, magazine pages, process maps, Gantt charts and analysis frames.

## What makes a good slide

- Titles state the conclusion, not the topic.
- One point per slide. Long explanations go in the speaker notes.
- Write in cells. People cannot edit an HTML slide.
- If values change often, keep them in a CSV.
- Numbers must agree across slides. Check totals and ratios.
- Look even when Check finds nothing. It cannot see text over photos or empty space.
