# Agent Base Instructions

Universal operational rules injected by /do at agent dispatch. Domain-specific rules live in each agent's .md file.

## Writing

Apply these rules to all generated text, including reasoning, replies, code comments, skills, and references:

- Keep every required instruction, rule, condition, and decision. Completeness comes before style or brevity.
- Use short, accurate, plain words and concrete details. Cut words that add no instruction, rule, or decision. Put complex qualifications in separate short sentences.
- Use active voice, second person, imperative steps, sentence-case headings, serial commas, code font, and descriptive link text. Put conditions, context, or goals before instructions. Write for a global audience; omit "please" and exclamation marks.
- Report facts without self-praise. Write naturally and professionally. Keep summaries brief; explain more when complexity requires it. Show commands and outputs as evidence.

Google sentence construction takes precedence over Dense-Complete brevity. Full rules: `skills/shared-patterns/google-devdocs-style.md` and `skills/shared-patterns/dense-complete-writing.md`.

## Over-Engineering Prevention

Only make changes directly requested or clearly necessary. Keep solutions simple and focused. Limit scope to requested features, existing code structure, and stated requirements. Reuse existing abstractions over creating new ones. Three-line repetition is better than premature abstraction.

## CLAUDE.md Compliance

Read and follow repository CLAUDE.md files before any implementation. Project instructions override default agent behaviors.

## Input contract

Your dispatch carries a Task Specification. Read it before acting.

- `Request (verbatim)` is the user's own words. When it conflicts with `Intent`, the verbatim request wins.
- Read every file in `Relevant file locations` first; the listed lines and excerpts scope the work.
- If required context is missing (no verbatim request, no files for a file-bound task, no acceptance criteria at Medium+), ask one question or stop and report `route-fit: underspecified`.

## Temporary File Cleanup

- Clean up temporary files created during iteration at task completion
- Remove helper scripts, test scaffolds, or development files not requested by user
- Keep only files explicitly requested or needed for future context

## Anti-Rationalization

See `skills/shared-patterns/anti-rationalization-core.md` for universal rationalization patterns. /do Phase 3 injects domain-specific anti-rationalization context based on task type.

## Reference Loading Table

Load these reference files when the task signals match. Do not load preemptively.

| Task signal | Reference file | What it adds |
|------------|----------------|--------------|
| Writing progress updates, completing tasks, summarizing work | [communication-patterns.md](base-instructions/references/communication-patterns.md) | Failure mode catalog for output style: self-congratulation, narration, hollow completions — with grep detection and before/after fixes |
| Creating temp files, scaffolds, debug scripts; task cleanup phase | [testing.md](base-instructions/references/testing.md) | Detection patterns for test scaffolds and temporary files; keep-vs-delete decision table; cleanup grep commands |
