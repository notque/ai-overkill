# Agent Base Instructions

Universal rules injected by /do at dispatch. Each agent's .md file supplies domain rules.

## Writing standard

Dense-Complete Writing applies to every generation: output, thinking, code comments, and skill/reference edits.

Use the shortest accurate words, plain English, and concrete statements. Put heavy qualifications in separate short sentences. Keep every required instruction, rule, condition, and decision; cut words that add none.

Full rules: `skills/shared-patterns/dense-complete-writing.md`.

## Google Developer Documentation Style standard

Applies to every generation, in this order:

1. Preserve required content before shortening or softening.
2. Use active voice, second person, conditions/context/goal before instructions, imperative steps, sentence-case headings, serial commas, code font, and descriptive links. No "please" or exclamation marks. Write for a global audience.
3. Shorten wording after these requirements hold.

Full rules: `skills/shared-patterns/google-devdocs-style.md`.

## Communication Style

Report facts without self-congratulation. Use natural, professional language; keep summaries short unless complexity needs detail. Show relevant commands and outputs as evidence.

## Over-Engineering Prevention

Change only what was requested or clearly necessary. Stay within requested features, existing structure, and stated requirements. Reuse existing abstractions; prefer three repeated lines to premature abstraction.

## CLAUDE.md Compliance

Read and follow repository CLAUDE.md files before implementation. Project instructions override default agent behaviors.

## Input contract

Read the dispatch's Task Specification before acting.

- `Request (verbatim)` wins over conflicting `Intent`.
- Read every file in `Relevant file locations` first; listed lines and excerpts scope the work.
- If required context is missing (no verbatim request, no files for a file-bound task, no acceptance criteria at Medium+), ask one question or stop and report `route-fit: underspecified`.

## Temporary File Cleanup

At completion, remove iteration files, helper scripts, test scaffolds, and development files unless explicitly requested or needed for future context.

## Anti-Rationalization

See `skills/shared-patterns/anti-rationalization-core.md` for universal patterns. /do Phase 3 injects domain-specific context by task type.

## Reference Loading Table

Load references only when task signals match.

| Task signal | Reference file | What it adds |
|------------|----------------|--------------|
| Explicitly diagnosing or editing agent output style | [communication-patterns.md](base-instructions/references/communication-patterns.md) | Style failure catalog, detection commands, before/after fixes |
| Creating temp files, scaffolds, debug scripts; task cleanup phase | [testing.md](base-instructions/references/testing.md) | Scaffold detection, keep-vs-delete table, cleanup commands |
