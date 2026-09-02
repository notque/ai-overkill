---
name: go-patterns
version: 1.0.0
description: "Go development patterns: testing, concurrency, errors, review, and conventions."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
agent: golang-general-engineer
routing:
  category: language
  force_route: true
  not_for: "'go' as a verb (go ahead, here we go, go-live, let's go), Go (the board game), pidgin/cargo english 'go do X'; only fires for the Go programming language patterns/idioms/testing or edits to .go files; SAP Commerce Cloud PHP work (use php-general-engineer agent)"
  triggers:
    - .go
    # testing triggers
    - go test
    - "*_test.go"
    - table-driven
    - t.Run
    - t.Helper
    # concurrency triggers
    - goroutine
    - channel
    - sync.Mutex
    - sync.WaitGroup
    - worker pool
    - fan-in
    - context.Context
    - "goroutine fan-out"
    # error handling triggers
    - fmt.Errorf
    - errors.Is
    - errors.As
    - "%w"
    - sentinel error
    # review pattern triggers
    - "Go failure mode"
    - "Go code smell"
    # code review triggers
    - Go code review
    - Go PR
    - Go quality
    # sapcc conventions triggers
    - sapcc
    - sap-cloud-infrastructure
    - go-bits
    - keppel
    - go-api-declarations
    - go-makefile-maker
    # quality gate triggers
    - make check
    - Go lint
  pairs_with:
    - golang-general-engineer
    - systematic-code-review
---

# Go Patterns Skill

Umbrella skill for Go development: Google style, testing, concurrency, error handling,
failure modes, code review, SAP CC conventions, and quality gates. Every Go task starts
with the complete Google Go style baseline, then loads task-specific references.

## Mandatory Google Style Baseline (Every Go Task)

Before reading, writing, changing, generating, debugging, or reviewing Go code:

1. Read `${CLAUDE_SKILL_DIR}/references/google-style-guide/LOAD_ORDER.md`.
2. Read every file it lists, in order. Do not omit or sample parts.

Do not skip this baseline for small changes, tight context budgets, reviews, tests, or
generated code. The ordered files reconstruct all four complete pinned upstream
documents—overview, guide, decisions, and best practices—without excerpts.
Apply their guidance to all Go code produced by the agent.

Use this precedence when guidance differs:

1. The target repository's explicit rules and required compatibility constraints.
2. The Google Go Style Guide's canonical rules.
3. Google Go Style Decisions' normative guidance.
4. Google Go Style Best Practices' non-canonical recommendations.
5. Task-specific references below.

Prefer local consistency only where the Google guide allows judgment. Do not create
unrelated churn merely to restyle existing code. For new and nearby changed code,
follow the current pinned guidance. Record a conscious exception when repository rules,
generated-code constraints, or compatibility requirements require one.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Every Go task | `google-style-guide/LOAD_ORDER.md`, then every file it lists | Complete Google style baseline; always load every part of all four upstream documents |
| Testing | `testing.md` | Writing, fixing, or reviewing Go tests |
| Concurrency | `concurrency.md` | Goroutines, channels, sync primitives, race conditions |
| Error handling | `error-handling.md` | Error wrapping, sentinels, custom types, errors.Is/As |
| Review patterns | `preferred-patterns.md` | Detecting code smells, over-engineering, bad Go patterns |
| Code review | `code-review.md` | Reviewing Go code or PRs for quality |
| SAP CC conventions | `sapcc-conventions.md` | Working in sapcc/* repos with go-bits |
| Quality gate | `quality-gate.md` | Running make check, linting, pre-commit validation |

## Instructions

### Step 1: Load the Google Style Baseline

Read the load-order manifest and every file it names. This gate is complete only after
every part of all four upstream documents has been read in the current task.

### Step 2: Identify the Go Domain

Classify the task into one or more domains, then load the corresponding reference files.
Only load what is needed -- do not load all references for every task.

| Domain | Load Reference | When |
|--------|---------------|------|
| Testing | `references/testing.md` | Writing, fixing, or reviewing Go tests |
| Concurrency | `references/concurrency.md` | Goroutines, channels, sync primitives, race conditions |
| Error handling | `references/error-handling.md` | Error wrapping, sentinels, custom types, errors.Is/As |
| Review patterns | `references/preferred-patterns.md` | Detecting code smells, over-engineering, bad Go patterns |
| Code review | `references/code-review.md` | Reviewing Go code or PRs for quality |
| SAP CC conventions | `references/sapcc-conventions.md` | Working in sapcc/* repos with go-bits |
| Quality gate | `references/quality-gate.md` | Running make check, linting, pre-commit validation |

Multiple domains may apply. For example, reviewing a PR that includes concurrency code
should load both `code-review.md` and `concurrency.md`.

### Step 3: Load and Follow the Reference

Read the selected reference file(s) using `${CLAUDE_SKILL_DIR}/references/<name>.md`.
Each reference contains the full methodology, phases, code examples, and error handling
for that domain. Follow the instructions in the reference as if they were this skill's
instructions.

### Step 4: Use Domain-Specific Sub-References

Some references point to their own sub-reference files for extended patterns:

**Testing** sub-references:
- `${CLAUDE_SKILL_DIR}/references/testing/go-test-patterns.md` -- Full table-driven test, helper, mock examples
- `${CLAUDE_SKILL_DIR}/references/testing/go-benchmark-and-concurrency.md` -- b.Loop() benchmarks, synctest

**Concurrency** sub-references:
- `${CLAUDE_SKILL_DIR}/references/concurrency/concurrency-patterns.md` -- Worker pool, fan-out/fan-in, pipeline, rate limiter, graceful shutdown

**Error handling** sub-references:
- `${CLAUDE_SKILL_DIR}/references/error-handling/patterns.md` -- gopls tracing, HTTP handler patterns, error wrapping in middleware

**Review-pattern** sub-references:
- `${CLAUDE_SKILL_DIR}/references/preferred-patterns/code-examples.md` -- Extended before/after for all 7 failure modes

**Code review** sub-references:
- `${CLAUDE_SKILL_DIR}/references/code-review/common-review-comments.md` -- Go code patterns with good/bad examples

**SAP CC conventions** sub-references:
- `${CLAUDE_SKILL_DIR}/references/sapcc-conventions/sapcc-code-patterns.md` -- Primary reference: code patterns, testing patterns, failure modes (merged from testing-patterns-detailed.md and preferred-patterns.md)
- `${CLAUDE_SKILL_DIR}/references/sapcc-conventions/library-reference.md` -- Complete approved/restricted library table
- `${CLAUDE_SKILL_DIR}/references/sapcc-conventions/architecture-patterns.md` -- Full 102-rule architecture spec
- `${CLAUDE_SKILL_DIR}/references/sapcc-conventions/review-standards.md` -- Lead + secondary review standards (merged)
- `${CLAUDE_SKILL_DIR}/references/sapcc-conventions/extended-patterns.md` -- Security, K8s, PR hygiene patterns
- Plus: `api-design-detailed.md`, `build-ci-detailed.md`, `error-handling-detailed.md`,
  `go-bits-philosophy-detailed.md`, `pr-mining-insights.md`

**Quality gate** sub-references:
- `${CLAUDE_SKILL_DIR}/references/quality-gate/common-lint-errors.json` -- Linter descriptions and fix suggestions
- `${CLAUDE_SKILL_DIR}/references/quality-gate/makefile-targets.json` -- Available make targets
- `${CLAUDE_SKILL_DIR}/references/quality-gate/expert-review-patterns.md` -- Manual review patterns
- `${CLAUDE_SKILL_DIR}/references/quality-gate/examples.md` -- Detailed usage examples

### Step 5: Execute

Follow the loaded reference methodology. Each reference has its own phases, gates,
and completion criteria. Apply them as written.

## Available Scripts

Scripts are organized by domain in sub-directories:

- **Testing**: `scripts/gen-table-test.sh`, `scripts/bench-compare.sh`
- **Error handling**: `scripts/check-errors.sh`
- **Code review**: `scripts/check-interface-compliance.sh`
- **SAP CC conventions**: `scripts/check-sapcc-identify-endpoint.sh`, `scripts/check-sapcc-auth-ordering.sh`,
  `scripts/check-sapcc-json-strict.sh`, `scripts/check-sapcc-time-now.sh`, `scripts/check-sapcc-httptest.sh`,
  `scripts/check-sapcc-todo-format.sh`
- **Quality gate**: `scripts/quality_checker.py`, `scripts/validate.py`
- **Google style snapshot**: `scripts/sync-google-style-guide.py` (pinned upstream refresh; requires review before revision changes)

## Error Handling

Errors are domain-specific. Load the relevant reference file and check its Error Handling
section for troubleshooting guidance.
