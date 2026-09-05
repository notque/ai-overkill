---
name: parallel-code-review
description: "Parallel 3-reviewer code review: Security, Business-Logic, Architecture."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Task
routing:
  not_for: "security-specific review — use security-review. NOT: security-focused review of git changes (use security-review)"
  triggers:
    - "parallel review"
    - "3-reviewer review"
    - "multi-reviewer"
    - "concurrent review"
  category: code-review
  pairs_with:
    - systematic-code-review
    - verification-before-completion
---

# Parallel code review

Divide a review among Security, Business Logic, and Architecture reviewers, then combine their findings. Use the shared procedure in `../systematic-code-review/SKILL.md` for evidence, finding verification, and review reuse.

## Reference loading

| Task | Reference |
|---|---|
| Select PR review scope and roster | `../../process/pr-workflow/references/pr-risk-policy.md` |
| Brief the Architecture reviewer | `references/architecture-smell-baseline.md` |

## Phase 1: IDENTIFY SCOPE

Read repository instructions and identify the requested diff or files:

```bash
git diff --name-only HEAD~1
gh pr view --json files -q '.files[].path'
```

Use the actual requested base, not `HEAD~1`, for a multi-commit change. Record the reviewed revision and relevant existing checks.

Honor an explicit user or `/do` roster. For this skill's three-reviewer mode, keep all three roles. Do not start another trio when this skill is used inside an already selected roster. Automatic PR review selection belongs to the risk policy, including its high-risk requirements.

Select the Architecture reviewer by language: Go → `golang-general-engineer`; Python → `python-general-engineer`; TypeScript → `typescript-frontend-engineer`; mixed or other → `Explore`. Add threat modeling, git bisect, or benchmarks when explicitly requested.

**Gate:** Scope, roster, and review evidence are known.

## Phase 2: DISPATCH PARALLEL REVIEWERS

Dispatch the selected independent reviewers together. Reviewers read and report; they do not edit code. Supply the same task intent, diff base/head, constraints, and relevant check results, with a distinct focus:

| Role | Focus |
|---|---|
| Security | Authentication, authorization, input validation, secrets, relevant OWASP risks |
| Business Logic | Requirements, edge cases, state transitions, validation, failure modes, documentation accuracy |
| Architecture | Design, structure, performance, maintainability, scope, simplicity |

All reviewers can flag documentation errors and scope creep. Give the Architecture reviewer `references/architecture-smell-baseline.md` verbatim; it contains the 12 smells, language counter-examples, and severity cap.

Require concrete findings with `[Reviewer]`, `file:line`, severity, and consequence. Reuse valid checks rather than having each worker run the same suite.

**Gate:** Every selected reviewer returned, or the report explicitly identifies incomplete coverage without claiming approval.

## Phase 3: AGGREGATE

Combine duplicate findings, retaining evidence and resolving severity disagreements against the code. Use the shared procedure's finding verification step; group uncertain related findings for independent checking when warranted. Do not automatically spawn a verifier for each finding.

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Security vulnerability or data loss | Block merge |
| HIGH | Significant bug or logic error | Fix before merge |
| MEDIUM | Material quality issue or potential problem | Should fix |
| LOW | Minor issue or preference | Optional |

Report supported findings at their final severity. Record material refutations and severity changes; unresolved consequential disagreement remains visible.

**Gate:** Findings are deduplicated and checked against evidence.

## Phase 4: VERDICT

CRITICAL → **BLOCK**. HIGH without CRITICAL → **FIX**. Only MEDIUM/LOW or no findings → **APPROVE**, provided required coverage and checks are complete.

Use this structure for each reviewer's output and the combined report:

```markdown
## Parallel Review Complete

### Severity Matrix
| Severity | Count | Summary |
|----------|-------|---------|
| Critical | 0 | None |
| High | 0 | None |
| Medium | 0 | None |
| Low | 0 | None |

### Combined Findings
[Findings grouped by severity; each has [Reviewer] and path/file.ext:42.]

### Recommendation
**APPROVE** - Scope, evidence, and limitations.
```

Update counts from the final findings. Include reviewer coverage and material unresolved questions. Keep a single combined report instead of pasting three raw reports.

Validate each reviewer output before aggregation; use separate paths:

```bash
python3 scripts/validate-review-output.py --type parallel /tmp/reviewer-security.md
```

Exit `0` means valid structure; `1` means schema errors; `2` means unparseable; `3` means `jsonschema` is missing (`pip install jsonschema`). Repair the affected output once using the diagnostics and revalidate. If it still fails, report incomplete review rather than accepting malformed data.

The validator checks verdict, severity buckets, reviewer tags, and parsed locations. It does not prove completeness or match matrix counts to findings; check those yourself.

After fixes, review the changed paths and affected domains. Keep unaffected results when their code and assumptions remain valid. Repeat the full roster only when changes invalidate that coverage or an explicit review requirement demands it.

**Gate:** Required reviewers returned valid reports; the combined verdict matches the evidence.

## Recovery

If a reviewer fails, report available findings and missing coverage, then retry that reviewer after fixing the cause. Check paths and permissions; split oversized input into bounded scopes. If parallel execution is unavailable, run the selected roles sequentially with the shared procedure. Never label partial coverage as a completed required review.
