---
name: quick
description: "Tracked lightweight execution with composable rigor flags: --trivial, --discuss, --research, --full. Covers zero-ceremony inline fixes (typo, spelling fix, small mistake in a single file, ≤3 edits) through contained multi-file changes."
user-invocable: true
argument-hint: "[--trivial] [--discuss] [--research] [--full] <task>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  force_route: true
  triggers:
    - quick task
    - small change
    - ad hoc task
    - add a flag
    - small refactor
    - targeted fix
    - quick fix
    - typo fix
    - fix typo
    - fix the typo
    - one-line change
    - trivial fix
    - rename variable
    - rename this variable
    - update value
    - fix import
    - small mistake
    - small mistake in
    - mistake in spelling
    - spelling mistake
    - spelling fix
    - fix the spelling
    - typo in
    - small fix in
    - small fix
    - tiny fix
  not_for: "'quick' as speed preference, general bug diagnosis requiring investigation"
  complexity: Simple
  category: process
---

# /quick

Make contained changes in one execution thread. Use `/do` for multiple components, architectural changes, or parallel work. Keep plans inline; do not create `task_plan.md`.

## Flags

All flags default off. Combine discussion, research, and verification as needed.

| Flag | Effect |
|---|---|
| `--trivial` | Mechanical fix: at most 3 edits across at most 3 files; no displayed plan, task ID, or subagents. |
| `--discuss` | Resolve independent ambiguities together before planning. |
| `--interview` | Resolve dependent decisions one question at a time, with a recommendation. |
| `--research` | Investigate unfamiliar code before planning. |
| `--full` | Verify the plan, then run affected tests, configured lint, and diff review. |
| `--no-branch` | Stay on the current branch if repository branch rules permit it. |
| `--no-commit` | Leave edits uncommitted, including in trivial mode. |

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| usage examples, task ID format, error handling | `examples.md` | Examples and recovery. |
| emitting banners, commit format, or STATE.md entries | `templates.md` | Output and tracking contracts. |

## Setup

Read repository `CLAUDE.md` unless already loaded and current. Parse flags; the remaining text is the task. Follow existing authorization and repository constraints throughout.

Before editing, check the branch. Never let `--trivial` or `--no-branch` bypass branch safety. For trivial work on main/master, create `quick/<brief-description>`; for standard work, create `quick/<task-id>-<brief-kebab-description>` unless `--no-branch` is allowed. Preserve unrelated changes.

## Trivial mode

Use for `--trivial` or a clearly mechanical one-line change identified by the router.

1. Read the targets and check scope. Investigation or unfamiliar behavior requires `/quick --research`; more than 3 files, new package imports, or dependency-file changes require standard `/quick`. For ambiguity, ask one clarifying question; if unresolved, use `/quick --discuss`.
2. Edit directly and count edits. If more than 3 are needed, preserve completed work and continue standard `/quick`. Explain the scope change and carry forward the original request and completed edits.
3. Review the diff and run applicable repository checks. Stage only intended files with `git add <specific-files>` and commit using `references/templates.md`, unless `--no-commit` applies.
4. Emit the trivial summary and stop. Report an omitted commit as skipped, never as successful.

## Standard procedure

### 1. Resolve decisions and investigate

Use discussion for `--discuss` or material uncertainty about the requested change, approach, or acceptance criteria. Batch independent questions using the DISCUSS template. Wait for answers needed to proceed; do not ask again about decisions or actions already authorized.

For `--interview`, load `planning/references/depth-first-interview.md`. The explicit flag skips its opt-out question. Follow PRIME → ENUMERATE BRANCHES → TRAVERSE → COMPILE OUTPUT, with at most 5 questions and 3 recursion levels per branch. Keep Resolved Decisions / Carried Forward / Scope Boundary / Mode Used inline for the plan.

For `--research` or unfamiliar code, read relevant source, tests, and configuration. Establish current behavior, where the change fits, and what could break. Summarize findings and their effect on the plan in 3–5 lines.

### 2. Plan and assign an ID

Use `YYMMDD-xxx`, with a Base36 sequence: `001` through `009`, `00a` through `00z`, then `010`.

```bash
date_prefix=$(date +%y%m%d)
```

Increment today's highest sequence in root `STATE.md`, starting at `001` if absent. If corrupted, recover the sequence from git log entries matching `Quick task YYMMDD-`. Increment again on branch-name collision.

Display the inline plan from `references/templates.md`: intended edits, files, rationale, and estimated edit count. Create the branch under the setup rules. With `--full`, verify that the plan meets acceptance criteria before editing. Recommend `--full` for security, payments, or data migration.

### 3. Execute and watch scope

Make the planned edits and track their count. Above 15 estimated edits, suggest `/do`. Warn at 10 actual edits and reassess at 15. These standard-mode thresholds are advisory; continue within established authorization when the work remains contained. Ask only when a scope decision is unresolved. Trivial mode's 3-edit limit remains strict.

For base verification, run an appropriate syntax/build check, such as `python3 -m py_compile <files>`, `go build ./...`, or `tsc --noEmit`, plus required repository checks.

With `--full`, run tests for affected packages/modules, configured lint on changed files, and `git diff` review for unintended changes, missing error handling, and broken imports. Run the full suite when required by the repository or requested by the user. Fix relevant failures before claiming completion; report unrelated blockers accurately.

### 4. Commit and log

Unless `--no-commit`, stage specific intended files with `git add <specific-files>`, use the conventional commit format from `references/templates.md`, and include `Quick task <task-id>` in the body. Verify with `git log -1 --oneline`.

Create or append to root `STATE.md` using the reference schema. Use tier `trivial->quick` after escalation; otherwise `quick`. Record skipped commits explicitly. Emit the completion summary with changes, checks, commit or skipped status, branch, flags, and log location. Continue any already-authorized delivery steps.
