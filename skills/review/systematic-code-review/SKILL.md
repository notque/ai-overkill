---
name: systematic-code-review
description: "4-phase code review: UNDERSTAND, VERIFY, ASSESS risks, DOCUMENT findings."
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  triggers:
    - "review code"
    - "code review methodology"
    - "structured review"
    - "code audit"
    - "review methodology"
    - "comprehensive review"
  not_for: "vague no-target requests like 'make this better' — those are interview-mode, where the agent asks what to improve; reviewing ALL source files in the repo for a health check (use full-repo-review); security-only review of git changes (use security-review). Only for reviewing a named file, diff, or PR."
  category: code-review
  pairs_with:
    - forensics
    - verification-before-completion
    - parallel-code-review
---

# Systematic code review

Review the change, verify its claims, assess risk, and report actionable findings. This is the shared review procedure. Parallel review divides its scope among reviewers; it does not add another full review afterward.

## Reference loading

| Task | Reference |
|---|---|
| Select PR review scope and roster | `../../process/pr-workflow/references/pr-risk-policy.md` |
| Review Go exports, concurrency, resources, metrics, or tests | `references/go-review-patterns.md` |
| Classify a finding | `references/severity-classification.md` |
| Respond to feedback | `references/receiving-feedback.md` |

## Phase 1: UNDERSTAND

Read applicable repository instructions and the complete diff. Read enough surrounding code to understand each changed path and its consumers; load whole files when their structure matters. Check the requested outcome, compatibility requirements, and affected dependencies.

When signatures, parameter meanings, or sentinel values change, find all callers and interface implementations. Search receiver syntax such as `.GetEvents(`; use type-aware references such as gopls when available. Trace each parameter to its source:

- Query parameters can contain any user-supplied string, including `"*"`.
- Token fields may be server-issued IDs; verify that boundary rather than assuming it.
- Constants and enums have a bounded value set.

Check validation at each caller. A reachable user input that bypasses a security filter is blocking. Verify the caller set yourself; the PR description may omit callers.

Record the reviewed base/head or working diff, scope, and material unknowns. Ask only when missing information prevents a sound review; continue independent checks.

**Gate:** Every changed path is accounted for, with affected callers traced where needed.

## Phase 2: VERIFY

Reuse observed test and review results when they cover the current code, dependencies, configuration, and environment. Record their source and scope. A prior verdict alone is not evidence. After a fix, check the changed paths and affected consumers; repeat broader checks only when the fix invalidates their evidence or repository policy requires it.

Run relevant tests for uncovered behavior and all required repository checks. Inspect actual output and retain logs; report commands, results, and limitations without pasting full logs. Missing tools, skipped checks, and inferred outcomes are not passes. Identify whether a test failure is caused by this change or is unrelated; required failing checks still prevent merge.

Check material claims in comments and the PR description against code, callers, tests, or observed behavior. Verify edge cases and coverage of changed paths. Source inspection can establish structure, but cannot substitute for a runtime result when that is the claim.

**Gate:** Claims have supporting evidence; required checks passed or the review records the gap without approving it away.

## Phase 3: ASSESS

Assess the risks the change can introduce:

- Security: authentication, authorization, validation, injection, and secrets. Trace reachable paths; explain material exclusions without reciting unrelated vulnerability checklists.
- Performance: N+1 queries, unbounded work, allocations, and resource use on affected hot paths. Benchmark when the request or uncertainty warrants it.
- Architecture: repository conventions, compatibility, scope, and unnecessary abstractions.
- Extraction: a new reusable helper may need guards that its former single caller supplied. Recheck its contract and callers; raise severity when the new reachability warrants it.

Use the severity reference. Blocking findings concern security, correctness, or reliability; SHOULD FIX covers material pattern, test, or debugging problems; SUGGESTIONS are optional. Resolve uncertainty with evidence. Document unresolved consequential uncertainty instead of presenting speculation as a confirmed defect.

**Gate:** Relevant risks and remaining uncertainty are explicit.

## Phase 3.5: VERIFY FINDINGS

Before reporting a finding, check its input or call sequence, existing guards, and proposed fix. Drop unreachable, already-handled, or non-actionable claims. Cite evidence for material severity changes and disputed findings.

The reviewer normally does this check directly. Use an independent check when a consequential claim remains uncertain or the user requests one. Group related findings for that check; do not create a worker per finding or recursively review the verifier. A finding that survives refutation is supported, not proven correct.

When combining reviews, deduplicate findings and resolve conflicting severity from evidence. Retain unresolved high-impact disagreements in the report. After fixes, revisit the findings and affected domains; reuse unaffected review evidence. Preserve explicitly requested rosters and repository review requirements.

**Gate:** Reported findings have concrete evidence, locations, and an actionable consequence.

## Phase 4: DOCUMENT

Report issues introduced or exposed by the change, including fixes that must touch consumers outside the diff. Keep speculative features out of the review.

```text
PHASE 4: DOCUMENT
Review Summary:
  Files Reviewed: N
  Lines Changed: +X/-Y
  Test Status: PASS | FAIL | SKIPPED
  Risk Level: LOW | MEDIUM | HIGH | CRITICAL

BLOCKING:
  1. Issue and consequence — path/file.ext:42
SHOULD FIX:
  1. Issue and consequence — path/file.ext:52
SUGGESTIONS:
  1. Optional improvement — path/file.ext:62

Verdict: APPROVE | REQUEST-CHANGES | NEEDS-DISCUSSION
Rationale: Evidence, review scope, and remaining limitations.
```

Omit empty findings rather than inventing them. Include reused checks and review scope, material refutations, severity changes, and unverified areas when they affect the decision. Blocking defects or required failing checks prevent approval. Use NEEDS-DISCUSSION for unresolved consequential questions.

Validate the report:

```bash
python3 scripts/validate-review-output.py --type systematic /tmp/review-output.md
```

Exit `0` means structurally valid; `1` means schema errors; `2` means unparseable; `3` means `jsonschema` is missing (`pip install jsonschema`). Repair schema or parse errors once using the diagnostics, then validate again. If still invalid, report the failure without claiming review completion.

The validator checks verdict, risk level, and parsed finding locations. It cannot establish review completeness or catch every parser-dropped finding; compare the rendered report with the findings before accepting it.

**Gate:** The report passes the schema check and states the verdict and evidence accurately.
