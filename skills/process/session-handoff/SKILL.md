---
name: session-handoff
description: "Package session state for the next agent, or rehydrate it at start."
user_invocable: false  # default -- router-dispatched, not user-typed
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "hand off this session"
    - "hand off to the next agent"
    - "package session state"
    - "state package for the next agent"
    - "session pickup"
    - "rehydrate session state"
  not_for: "plan-artifact pause/resume (HANDOFF.json plus pause.md/resume.md) — that is planning. This skill packages inline agent-to-agent state: working tree, PR/CI, live processes, checks."
  category: process
  pairs_with:
    - pr-workflow
---

# Session Handoff

Two modes sharing one state contract. HANDOFF packages current work so the next agent (or future session) resumes without re-discovery. PICKUP rehydrates from that package at session start. Pick the mode from intent: ending or pausing work = HANDOFF; starting on existing work = PICKUP.

## Mode: HANDOFF

Produce a concise bullet package with these sections, in order. Use observed state and linked evidence. Label inherited results with their source; refresh mutable state before relying on it. Preserve every section, using “not applicable” when needed, without running irrelevant commands.

1. **Scope/status** — the task in one line, finished vs. remaining work, blockers.
2. **Working tree** — `git status -sb` summary; note local commits not yet pushed and the worktree path (`git worktree list`; do not infer it from a directory name).
3. **Branch/PR** — current branch, PR number/URL, CI status (`gh pr checks <num>` when a PR exists).
4. **Live processes** — long-running jobs the next agent must know about: summarize `ps auxww | grep -E '<your-process>'`, plus a copy-paste attach or log-tail command (`tail -f <logfile>`, `jobs -l`). Redact secrets in command lines.
5. **Tests/checks** — commands, results, checked revision or file state, relevant configuration/environment, log paths, and remaining checks.
6. **Next steps** — remaining actions in execution order, most urgent first.
7. **Risks/gotchas** — flaky tests, feature flags, brittle areas, approvals still needed.

**Gate:** every live process has a copy-paste command; every pending step is ordered. Output format: bullet list, Dense-Complete — short enough to paste into a PR comment or session note.

## Mode: PICKUP

Rehydrate in this order, then act.

1. **Read the handoff** — the prior package and applicable repository instructions. Load named documents needed for the next action; a linked archive does not require a full reread.
2. **Repo state** — `git status -sb`; confirm branch, local commits, worktree path.
3. **CI/PR** — `gh pr view <num> --comments` (derive the PR from the branch when unnumbered); note failing checks.
4. **Processes** — check for live jobs named in the handoff; attach or tail logs using its commands.
5. **Tests/checks** — apply the evidence-reuse rules in `verification-before-completion`. Check that inherited results cover the current files and relevant environment; rerun only invalidated or missing checks, plus required release/CI checks.
6. **Plan** — write the next 2–3 actions as bullets, then execute them.

**Gate:** branch, PR state, and first action are confirmed before any edit. Report discrepancies between the handoff and observed state; observed state wins.

## Constraints

- Separate directly observed results from inherited evidence. Name the source and any unverified conditions; never present another worker's run as your own.
- Scale detail to the next action. Keep the request, authority, ownership, acceptance checks, unresolved decisions, and live-process recovery commands. Link full logs and prior investigation instead of copying them. The dispatch builder owns Task Spec fields; this skill owns transfer state.
- In worktrees, follow worktree rules (`skills/meta/do/references/worktree-rules.md`): verify CWD, feature branch first.
- Keep secrets out of the package: redact tokens and credential paths as `<redacted>`.

## Error handling

### Handoff references a process that is gone
Cause: job exited between sessions.
Solution: check its log file for exit status, record the finding, drop the attach step.

### Branch in handoff differs from checked-out branch
Cause: another agent or the user moved the worktree.
Solution: report the difference and proceed from observed state.
