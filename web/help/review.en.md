# Polish check — a guide for AI (Lectern)

Read writing that a person wrote or edited, find wording that is wrong or hard to read, and propose fixes. Keep the writer's voice and fix only the places where a reader stumbles. This is not a rewrite. Lectern's document right-click item "Ask for a polish check" sends a request with the path of this guide and the document (or the picked lines).

## Steps

1. Read the whole document. Check the folder's CLAUDE.md or AGENTS.md for tone, notation and quoting rules and for the kind of document (narrative, bullet-point, official letter, review comments and so on). If you were given a line range, check only those lines and read around them only for meaning.
2. Sort what you find into the groups below and show a table. **Do not change the file at this step.**
3. Apply what the person picks ("errors only", "1, 3 and 7", "everything but preferences"). Change only the picked spots and not one other character. Say how many spots you changed.
4. If the same habit came up more than twice, mention it in a line or two at the end under "Came up often". It is there to help next time, not to scold. If the person keeps a style note, ask whether to add the habit to its "Do not copy" list.

If the request already says to apply ("just fix it"), show the table briefly, then fix errors and hard-to-read spots only and leave preferences and to-check items in the table.

## Groups

**Error**: wording with only one right fix. Recommend fixing.
- Spelling, punctuation and agreement ("it's" for "its", "affect" for "effect")
- Words used in the wrong sense ("principle" for "principal")
- Sentences whose subject and verb do not fit
- A word that says the opposite of what the text means: propose a fix but mark it "check meaning"

**Hard to read**: not wrong, but the reader stumbles. Propose a fix and let the person choose.
- Long sentences with several tangled conditions: propose splitting into two or three
- "This", "it" or "the said" whose referent is unclear: if your fix guesses the meaning, say so
- Unexplained abbreviations and jargon ("QoQ" → "on the previous quarter")
- Redundancy ("past history", "advance planning", "repeat again")
- Nominalisations and stacked passives ("conduct a review of", "it was decided by the team that")
- The same value in different units or notations ("230 kt" and "0.23 Mt", "$" and "USD"): keep the value, align the notation
- Register that changes within one piece (formal and casual mixed)

**Preference**: correct and readable, but could be written differently. List three or four at most.
- Two acceptable spellings or forms
- Bureaucratic set phrases are convention in official letters and institutional reports. Judge by the kind of document and the reader, and do not list them where they are the convention.

**To check**: not wording but whether the content is right; the person has to look. Do not propose a fix.
- Numbers that disagree (3.9% in section 1, 4.9% in section 3): even if you can guess which is right, do not change the value; say only what it disagrees with
- Claims without visible support, facts the material cannot confirm, two sentences that contradict each other
- Do not apply this group even if the person says "all". Change it only when the person gives the value or decides the content.

## Leave alone

- **Quotations**: text in quotation marks or quote blocks (`>`), and sentences taken from laws, regulations or institutional documents. They may look wrong, but they are the original. If something in them is off, write only "quotation, left as is".
- **Values of numbers**: when you align notation, keep the value (230 kt → 0.23 Mt).
- **Names and industry terms**: names of institutions, laws, products and people, and terms the industry itself uses.
- **Correct words**: words with two valid meanings are decided by context. Do not "fix" what is right.
- **The writer's style**: if sentence length, register and structure read well, do not swap them for your taste.
- **Content**: claims, judgements and numbers are not what a polish check changes. Note visible problems under "To check" only. Do not add or delete sentences.

## Table

| No. | Group | Where | Original | Proposed | Why |
|---|---|---|---|---|---|
| 1 | Error | Section 3 | the principle reason | the principal reason | "principal" means main |
| 2 | To check | Section 3 | Q2 growth of 4.9% | — | Section 1 says 3.9% |

- Order by group (error → hard to read → preference → to check), and within a group by position in the text.
- "Where" is a section name or line number, "Original" just long enough to find it, "Why" one line.
- Above the table, one line with how many you found per group; below it, one line on what to pick ("I recommend fixing all errors. Tell me the numbers to fix.").
- Below the table, list briefly what you left alone (quotations, correct words), so the person does not wonder why.
- With more than 30 items, show all errors and to-check items, show the rest by frequency, and ask whether to show more.
