# Making your own writing style — guide for AI (Lectern)

Read this when the person asks for a writing style (a Claude Code output style) that fits their own writing. The request from Lectern's settings window ("Choose a writing style" → "Make a new style") gives this guide's path, and the person adds what they want to write.

## Steps

1. Confirm what the person wants to write — who reads what kind of text, and how it must differ from the styles Lectern includes. Ask briefly only when you really cannot tell.
2. Pick the closest of the four styles Lectern includes as the base. They are in the same folder as this guide: `research-writing.en.md` (reports, review comments, analysis memos), `business-report.en.md` (one-page reports for approval), `academic-writing.en.md` (papers, research reports), `plain-explainer.en.md` (manuals, guides, training material). The Korean versions have no `.en`. Say which one you picked and why.
3. Build the new style by changing the base.
   - In the settings at the top (between `---`) keep only `name` (the name shown in lists — not the same as a Lectern style's name) and `description` (one line). Do not add `keep-coding-instructions` — the style is for writing, not code.
   - Adapt the first paragraph (who you are and what you write), "What comes first", "Before writing", the standard section for that kind of text, "While writing" and "After writing".
   - Keep the four sections "When you carry over or edit someone else's writing", "Do not write like a developer", "Do not write like an AI" and "When answering" exactly as in the base. Anything that must differ for that kind of text (such as the citation style of academic writing) goes into its standard section, saying that on this point that section comes first.
   - Do not copy the person's voice note (`~/.claude/rules/my-voice.md`) into the style — the fourth line of "What comes first" makes the note be read.
   - If the person gave sample writing, reflect its structure, length and tone in the standard, but do not copy its numbers, names or sentences.
4. Show the whole draft in the chat and take changes. Do not write a file at this stage.
5. When the person agrees, save it in `~/.claude/output-styles/` with a file name in lower-case English letters and `-` (for example `weekly-brief.md`). If a file with that name exists, ask again before replacing it. That folder is inside `.claude`, so Claude Code asks once more before writing.
6. After saving, tell the person: Claude Code must be restarted to read it; to turn it on, open Lectern's settings window again, choose it under "My writing styles" in "Choose a writing style" and send the request, or use `/output-style` in Claude Code; and since this style drops Claude Code's development guidance, it should not be turned on in folders where they write code.

## Other AI tools

Codex, Antigravity and OpenCode have no output styles. Build the style the same way, then ask whether to put the body, without the settings at the top, as a "Writing" section in that tool's personal instruction file (Codex `~/.codex/AGENTS.md`, Antigravity `~/.gemini/AGENTS.md`, OpenCode `~/.config/opencode/AGENTS.md`) or in the project's `AGENTS.md`. Lower the body's `##` headings to `###`. Keep only one writing section per file — if one exists, ask before replacing it and keep any "My voice" part in it — or the older "My style" — as it is.
