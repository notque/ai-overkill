# GM brilliant implementation evaluation

## Routing cases

| Case | Prompt shape | Expected |
| --- | --- | --- |
| Large feature | “Implement a large GM feature across booking, results, and relationships” | Select this skill and full DAG |
| Multi-wave | “Run a multi-wave GM overhaul through release and feedback” | Select this skill |
| CPU program | “Improve Auto Book, promises, staff policy, and shared attention together” | Select this skill; CPU predicate true |
| Small bug | “Fix the GM title link” | Do not select; focused route |
| Copy fix | “Change one Decision Desk sentence” | Do not select |
| Focused test | “Fix this one GM harness failure” | Do not select |
| Ordinary context | “Explain 5 Star Booker GM mode” | Use the target project-context skill, not this skill |

## Contract cases

1. Parse the spec and assert exactly 34 IDs S01-S34.
2. Topologically sort dependencies and require S34 as sole terminal.
3. Assert every node has one canonical phase, owner, method owner, artifact,
   applicability, and consumer impact.
4. Assert only S10-S14, S24, and S25 are conditional.
5. Assert every `always` node rejects skip.
6. Evaluate CPU true/false/invalid fixtures from identical registry inputs.
7. Evaluate backend/frontend true/false/invalid fixtures from identical flow
   maps and reject both false.
8. Reject each missing, extra, malformed, owner-mismatch, hash-mismatch,
   consumer-impact, result/status, and skip-reason fixture.
9. Validate every method owner against the runtime routing manifest.
10. Validate canonical-chain types with `scripts/artifact-utils.py`.

## Behavioral cases

| Case | Required behavior | Failure |
| --- | --- | --- |
| No CPU scope | S09 completes; S10-S14 create valid audited skips | Free-form skip or missing evidence |
| CPU improvement | All CPU stages run; ten obligations pass | CPU lane skipped or partial checklist |
| Frontend-only | S24 skips from S16 map, S25 runs | Inferred skip without predicate |
| Resume | Identical checkpoints reuse; changed input invalidates descendants | Session-bound restart or stale reuse |
| Authorization | Valid scoped record avoids repeat pause but all deploy guards run | Record bypasses test/health/rollback |
| Domain conflict | Stop and name target authority | Silent override or copied doctrine |
| Release | Exact live SHA/assets/routes/services recorded | “Deployed” without proof |
| Feedback | Privacy-safe delta and valid unfinished items retained | Only positive/top feedback reported |

## Pass checks

- No unresolved blocking or important ADR concern.
- All deterministic validations pass.
- Structural score is at least 75 percent and grade B.
- Positive and negative routing fixtures behave as specified.
- Canonical tracked source and `.claude`/`.codex` mirrors match.
- No placeholder text or broken internal reference remains.
