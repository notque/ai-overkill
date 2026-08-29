# handoff-context-v1 — thin vs rich Task Spec

Date: 2026-08-29. Base: 97a8fc91. Question: does a schema-shaped handoff (verbatim request, scoped files, excerpts with line numbers, decisions, acceptance-as-commands) change agent output versus today's `build-dispatch.py` echo of five router strings?

Design: 3 tasks × 2 arms. Same agent type, same model, same session, parallel dispatch, worktree isolation for edit tasks. Agents were not told an experiment was running. Grading is deterministic and was rerun by the router in each worktree, not taken from agent reports.

| Task | Arm | Result | Errors |
|---|---|---|---|
| T2 enumerate hooks calling `context_output(` (truth: 25) | thin | 14 listed | 11 missed, 4 false positives; guessed from README, never grepped |
| | rich | 25/25 exact | none; 1 tool call |
| T3 reject empty `task_spec` at medium/complex, keep trivial/simple | thin | 4/5 acceptance | `{}` at simple exits 2 (breaks simple); acceptance-only spec at medium rejected (invented an intent-required rule) |
| | rich | 5/5 | none |
| T1 add `request_verbatim`, label exactly `Request (verbatim)`, first position | thin | 1/3 | key `request`, label `Verbatim request` — a downstream hook grep would match 0 lines; edited `skills/meta/do/SKILL.md` out of scope |
| | rich | 3/3 | none |

Tool calls: thin 4/35/23, rich 1/19/17. Rich arms were cheaper on every task.

Verdict: 0/3 thin arms met acceptance; 3/3 rich arms did. Every thin-arm failure is a fact the router already knew and did not hand over (the exact term, the exact label, the trivial/simple carve-out, the scope). This is the mechanism the plan in `adr/handoff-context-plan.md` fixes; P0/P1 (schema + verbatim + gathered excerpts) is the change under test.

Limits: n=3 pairs, one model, one repo, tasks chosen to depend on router-held facts. It proves the mechanism, not a rate. Baseline the `spec_score` telemetry (P5) before claiming a fleet-wide number.

Worktrees kept for inspection: `.claude/worktrees/agent-aa8b8a1e69b9d1691` (T1-rich, mergeable), `agent-a3f9884c0cfedd0e7` (T3-rich, mergeable), `agent-a7b31e7de48b8da4a` (T1-thin), `agent-a38bedc33ce12d0ca` (T3-thin).
