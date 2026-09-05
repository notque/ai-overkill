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

## Shared rule owners

Use each procedure where it applies; do not load every owner at dispatch or repeat its work at each phase.

| Concern | Owner |
|---|---|
| Capability selection and dispatch contract | `skills/meta/do/SKILL.md` and `scripts/build-dispatch.py` |
| Scope, decisions, and plan lifecycle | `skills/process/planning/SKILL.md` |
| Implementation | Selected domain agent and task skill |
| Check evidence and completion claims | `skills/process/verification-before-completion/SKILL.md` |
| Review scope and reuse | `skills/process/pr-workflow/references/pr-risk-policy.md` |
| Commit, PR, CI, and merge | `skills/process/pr-workflow/SKILL.md` |
| Context transfer | `skills/process/planning/references/context-boundary.md` and `skills/process/session-handoff/SKILL.md` |

Keep domain exceptions with their domain. Follow higher-priority instructions and existing user authorization when defaults conflict; do not add another approval round.

Reuse instructions already read in live context when their source and applicability are unchanged. Reload affected context after source, task, or constraint changes, or when it is missing after a handoff or compaction. Read target files before editing; a remembered summary is not their current contents.

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
