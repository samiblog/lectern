# My style note — a guide for AI (Lectern)

Take writing the person wrote themselves as samples and sum up how they write in a short note. The note is used when you write or polish this person's writing. The aim is not imitation. Keep the conventions the reader expects of this person or organisation, keep their good habits, and do not copy the habits that make writing hard to read. Lectern's document right-click item "Send as a style sample" or the "My style" row in the settings window sends a request with the path of this guide and the samples.

## Steps

1. Read the samples. Read md and txt as they are; extract the text from docx, hwpx and pdf (if you cannot read a file, ask for a PDF). Leave out anything written by an AI or together with one. If you cannot tell, ask.
2. Sort the samples by kind (narrative report, bullet-point report, review comments, memo or briefing, other). Look at each kind separately.
3. Show a draft note in the three groups below in the chat, and let the person move or drop items ("this is how I write, follow it", "drop this"). **Do not write any file at this step.**
4. When the person agrees, save the note (see "Where").
5. If a note already exists, show only what the new samples change and change only what the person picks. As samples grow, items marked "seen in one sample only" are confirmed or dropped.

## What to look at

- Register: formal or plain, first person ("I", "we", "the team")
- Sentences and paragraphs: sentence length, whether the first sentence of a paragraph is the conclusion, conclusion first or last
- Structure: how sections are split, how headings are written, bullet symbols and levels
- Numbers: units and notation (m, bn, percentage points), how comparisons are stated, decimal places
- Terms: industry terms they use, how institutions are named, words they avoid on purpose
- Linking and emphasis: favourite connectives, how they emphasise (bold, notes)
- Habits: repeated phrases, spelling slips, redundancy, nominalisations, very long sentences

## Three groups

- **Keep**: conventions the reader (a manager, an institution, a client) expects of this person or organisation. Register, terms, notation of numbers and units, names of institutions, bullet symbols. Follow them when writing.
- **Lean towards**: what this person likes to do, but not a rule. Sentence length, paragraph shape, favourite openings and connectives, where the conclusion goes. Use only when the kind of document and the reader match, and when it clashes with the basics of report writing (conclusion first, the meaning of numbers, facts kept apart from inference) follow the basics.
- **Do not copy**: habits that make writing hard to read. Spelling slips, redundancy, nominalisations, very long sentences with tangled conditions, the same opening over and over, unsupported claims. Note them but do not copy them, and look for them first in a polish check. Word them as "this reads better", not as blame.

Rules for the note:

- Note only what shows up in two or more samples. Mark anything seen once "(seen in one sample only)".
- Keep each kind of document separate. Start each item with the kind it was seen in ("Memos:", "Narrative reports:"), and mark only what holds for any kind (terms, notation of numbers and dates, how sources are given) as "All:". Do not carry one kind's habits into another: not a memo's formal register into a report, not bullet-style endings into narrative. Do not write about kinds that are not in the samples; say they are missing.
- Keep the note within one page, about five lines per group.
- Do not copy sample sentences as examples; write new ones in the same style, so that figures and the names of people, institutions and projects do not leak from the samples. The note is used in every folder.

## Where

Keep the note once in the person's personal folder, so that every folder and every writing style reads the same note (D159).

- **Claude Code**: one file in the personal rules folder, `~/.claude/rules/my-voice.md` (read in every project). If, as in earlier versions, the writing style file (`~/.claude/output-styles/research-writing.en.md` or `research-writing.md`) ends with a `## My style` section, ask whether to move that section into this file — if so, remove it from the style file. After saving, tell them to restart Claude Code.
- **Codex, Antigravity, OpenCode**: add it as a `## My style` section to the personal instruction file the tool reads in every project (Codex `~/.codex/AGENTS.md`, Antigravity `~/.gemini/AGENTS.md`, OpenCode `~/.config/opencode/AGENTS.md`). If, as in earlier versions, it sits under the "Writing" section of the project's AGENTS.md, ask whether to move it.
- Rules that differ by folder (a different template for each institution, a different register) belong in that folder's CLAUDE.md or AGENTS.md, not in the note. Folder rules come before the note.

## Shape of the note

```markdown
## My style

Summed up from 4 pieces this person wrote (2 narrative reports, 2 bullet-point reports). When writing, follow "Keep", use "Lean towards" only when the kind of document and the reader match, and never use "Do not copy".

### Keep
- All: amounts in millions, changes in percentage points.
- Narrative reports: plain register. Memos: formal register for managers.

### Lean towards
- Narrative reports: conclusion in the first sentence, short paragraphs of two or three sentences.
- Bullet-point reports: two or three sub-points per heading, each a full clause.

### Do not copy
- Frequent "in terms of" and "with regard to" — plain prepositions read better.
- Sentences chaining more than three conditions — two sentences read better.

### Examples (newly written)
- Narrative: Costs rose 4% on the second quarter. Most of it came from raw materials; the exchange rate barely moved.
- Bullets: "Splitting purchases across the quarter is the safer option", with the sub-point "prices sit near the top of the forecast range, so buying everything now is expensive".
```

## Adding to the note

- You can add to the note from writing the person edited in Lectern, or from "Came up often" in a polish check. Only what repeats, and only after showing the change and asking.
- When the person reinstalls the writing style from a new Lectern version, move this section to the end of the new file (the install request in the settings window says so).
