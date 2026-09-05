# Quality Loop

For Medium+ code changes, use the agent and skill already selected by `/do`.
Do not change routing or replace domain instructions. Trivial, Simple, review-only,
research, debugging-only, and content tasks keep their existing workflows.

Work in four stages: implement, check, review, deliver. The phase numbers below
retain the 0–13 identifiers used by `/do` and `hooks/pipeline-phase-gate.py`;
they are checkpoints, not fourteen mandatory agent calls or tracking tasks.

## Implement: ADR, PLAN, IMPLEMENT (0–2)

- **0 — ADR:** For creation requests, write `adr/{kebab-case-name}.md` with
  Context, Decision, Consequences, and Implementation Checklist. Register it:
  `python3 ~/.claude/scripts/adr-query.py register adr/{name}.md`.
  For other changes, read an active `.adr-session.json` and its ADR when present;
  do not create an unrelated ADR.
- **1 — Plan:** Keep `task_plan.md` brief: original request, acceptance criteria,
  approach, affected files, and material risks. Use it to resume longer work and
  check the result against the request. Do not create a separate task for every
  checkpoint.
- **2 — Implement:** Use one feature branch and worktree. Before creating it, run
  `worktree_capacity.py --strict` as described in `references/worktree-rules.md`.
  Reuse the checkout for fixes; preserve unrelated work. Give the selected agent
  the task, domain references, worktree rules, and instruction to commit its changes.

Before checks, commit the candidate and write `quality-loop-state.md` in the
worktree root. Keep the original request intact and record acceptance criteria,
selected agent/skill, branch, decisions, and relevant prior results. This is the
handoff for review or resumed work, not a second plan. Phase 2 requires
`task_plan.md`; phases 3, 4, 7, and 9 require `quality-loop-state.md` under the
existing phase gate.

## Check: TEST, INTENT VERIFY, LIVE VALIDATE (3, 5–6)

- **3 — Tests:** Run the project's required checks and checks relevant to the
  changed behavior. Use repository commands/configuration first. When applicable:

  | Scope | Commands |
  |---|---|
  | Go | `go test ./...`, `go vet ./...` from the module root |
  | TypeScript | Installed `tsc --noEmit`; installed Vitest runner when configured |
  | Python | `ruff check . --config pyproject.toml`, `ruff format --check . --config pyproject.toml`; `python -m pytest` when configured |
  | Project checks | `make check` when required by the project; configured build and integration checks |
  | Agent references | `python3 scripts/validate-references.py --agent {name}` for each changed agent; `python3 -m pytest scripts/tests/test_reference_loading.py -k {name}` for its loading tests |

  Check skill references and routing contracts when those files change. Cover all
  affected languages. Do not install dependencies implicitly or treat a missing
  required tool as a passing check. Record actual exit codes and relevant failures;
  keep full logs available without pasting them into every update.
- **5 — Intent:** Compare the diff and observed behavior with the original request
  and acceptance criteria. Identify omissions and unintended changes. This check
  is required; a separate verifier is optional unless the project requires one.
- **6 — Live behavior:** For changed web behavior, use installed Playwright and the
  configured dev server when needed to verify rendering or interactions. Follow
  `e2e-testing` or `wordpress-live-validation`. Allow 60 seconds for startup and
  30 seconds per page. Run required browser suites even when unit tests pass.
  If unavailable, report the unverified behavior; a required failed or unavailable
  check blocks completion. Do not downgrade a reproduced correctness failure to
  a suggestion merely because a browser found it.

## Review and fix: REVIEW, FIX, RETEST, optional CODEX REVIEW (4, 7–8, 10)

Review the diff for correctness, scope, security, and domain constraints. Scale
independent review to the change: authentication, sensitive data, migrations,
concurrency, public contracts, or uncertain architecture merit focused expertise.
Routine changes can use direct review. No default quota of three reviewers or
cross-model review applies.

When delegating, give read-only reviewers the committed candidate, original
request, acceptance criteria, and relevant decisions/results. Use the repository
root; reviewers do not need additional checkouts. Select `reviewer-system`,
`reviewer-domain`, or `reviewer-perspectives` for the actual risk. Phase 10 remains
available through `pr-workflow`'s codex-review intent when requested or useful;
perform it before merge if its findings could block delivery.

Fix blocking findings in the implementation worktree. Keep related corrections
in clear commits. Reuse the implementing agent unless independent context would
help resolve a specific problem. Re-run affected checks after fixes, plus any
required full suite. Do not repeat unchanged passing checks without a reason.
If stuck, investigate the cause or report the concrete blocker; there is no
arbitrary three-round approval loop. Unresolved correctness/security failures or
required failed checks block merge. A draft may document unfinished work honestly.

## Deliver: PR, ADR RECONCILE, REPORT, CLEANUP (9, 11–13)

- **9 — PR:** Use `pr-workflow` to push and create the PR. Describe the resulting
  behavior, relevant validation, and unresolved limitations. Follow existing
  authorization; do not request approval again for an authorized action. Merge
  only the reviewed revision after all required GitHub checks pass. Report pending
  work if merge is outside the authorized scope.
- **11 — Reconcile:** Compare the actual PR/merge diff with the ADR checklist or
  plan acceptance criteria. Use the PR's base and head or recorded merge commit,
  not an assumed `main~1`. Document deviations in the ADR's Implementation Notes
  and mark checklist items completed, partial, or deviated.
- **12 — Report:** State what changed, what checks ran, and any material limits.
  Record reusable lessons in their owning skill/agent through a reviewed edit;
  refuted experiments belong in `docs/what-didnt-work.md`.
- **13 — Cleanup:** After completion, mark the applicable ADR Accepted, move it
  to `adr/completed/{name}.md`, and clear its `.adr-session.json`. Remove this
  task's temporary plan/state artifacts only when no longer needed for resumption.
  Confirm the task is inactive and the checkout clean before
  `git worktree remove -- <accepted-worktree-path>`, then run
  `bash scripts/worktree-cleanup.sh --force`. Preserve recoverable branches and
  other tasks' worktrees and artifacts.
