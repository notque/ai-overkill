---
name: verification-before-completion
description: "Defense-in-depth verification before declaring any task complete."
user-invocable: false
success-criteria:
  - "Required and relevant tests pass"
  - "Required build succeeds; new warnings reviewed"
  - "Changed files validated against task requirements"
  - "No unfinished implementations in requested work"
  - "Artifacts exist at expected paths (4-level verification)"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "verify completion"
    - "run tests"
    - "check build"
    - "defense in depth"
    - "final verification"
  category: process
  pairs_with:
    - systematic-code-review
---

# Verification before completion

Verify the requested result using observed commands and actual artifacts. Match checks to the affected behavior and repository requirements.

## Instructions

1. Inspect `git status --short` and `git diff` to include modified, staged, and untracked files. Read the changed code; check imports, error handling, compatibility, and unintended edits.
2. Run the repository's required tests, build, lint, and format checks. Start with relevant tests; run the full affected suite when required or when shared behavior changed. Do not substitute syntax checks for behavior tests.
3. Check generated artifacts at their expected paths. For integrations, verify all four levels: **EXISTS** on disk, **SUBSTANTIVE** implementation, **WIRED** into callers, and real **DATA FLOWS** through it. Trace inputs and results; an unused file or hardcoded empty result is not a working feature.
4. Inspect the diff for accidental debug code, secrets, placeholders, and unfinished work. Review matches in context: an intentional `pass` or empty result is not automatically a stub. Resolve missing implementations and wiring before claiming completion.
5. Fix failures within the authorized task and rerun affected checks. A failed required build or test blocks a success claim. Do not repeat unchanged passing checks without a reason.
6. Report commands, observed status, relevant counts, and remaining limitations. Retain full logs; include actionable failure excerpts and log paths instead of every passing test name. Distinguish automated checks, manual checks, and checks not run.

Use project commands first. Defaults when no project command exists:

| Language | Tests | Build or syntax | Lint |
|---|---|---|---|
| Python | `pytest -v` | `python -m py_compile {files}` | `ruff check {files}` |
| Go | `go test ./... -v -race` | `go build ./...` | `golangci-lint run ./...` |
| JavaScript | `npm test` | `npm run build` | `npm run lint` |
| TypeScript | `npm test` | `npx tsc --noEmit` | `npm run lint` |
| Rust | `cargo test` | `cargo build` | `cargo clippy` |

## Recovery

- **No tests:** perform suitable manual checks and state the coverage gap. Add a regression test when the task warrants one; do not imply manual inspection proves behavior.
- **Missing dependencies:** use the repository environment; report the missing tool and any narrower checks performed. Unrun checks are not passes.
- **Build or test failure:** retain the failing command and diagnostic, identify the cause, fix it, and rerun. Separate unrelated failures with evidence.
- **Missing wiring or data flow:** name the caller or call site where integration stops and repair it.

## Reference loading table

Load only when the signal applies; files are under `references/`.

| Signal | Reference | Purpose |
|---|---|---|
| Stub detection or integration evidence | `adversarial-methodology.md` | Four-level checks and goal-backward verification |
| Domain checklist or database/schema change | `checklist.md` | Before/after schema, duplicate tables/columns, existing-query compatibility |
| Verification walkthrough needed | `verification-examples.md` | Bug fix, refactor, migration, config examples |
| Pressure to skip consequential checks | `anti-rationalization-enforcement.md` | Failure patterns and pressure checks |

For code-review artifacts, use `python3 scripts/validate-review-output.py --type {systematic|parallel|sapcc-review|sapcc-audit} <file.md>`. Exit codes: 0 valid, 1 schema errors, 2 unparseable, 3 missing `jsonschema` (`pip install jsonschema`). Systematic and parallel review validate on return and retry once before stopping. A valid schema verifies structure, not the truth of review findings.
