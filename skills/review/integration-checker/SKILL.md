---
name: integration-checker
description: "Verify cross-component wiring and data flow."
user-invocable: false
command: /integration-checker
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - integration check
    - check integration
    - verify wiring
    - are components connected
    - check connections
    - integration-checker
    - wiring check
  pairs_with:
    - feature-lifecycle
    - systematic-code-review
  complexity: Medium
  category: process
---

# Integration checker

Check that components are connected and receive real data. A function can pass unit tests yet never be called; an endpoint can exist without being registered.

This skill reads and reports. Return fixes to the active implementation task or `feature-lifecycle`; do not create another approval round when fixes are already authorized.

## Reference loading

Load `references/wiring-checks.md` for language detection, export exclusions, wiring states, data-flow failures, contract patterns, and the requirements map.

## Phase 0: PRIME

Read repository instructions. In a feature pipeline, use `.feature/state/implement/` to scope changed and added files. Otherwise use the requested path or diff; a requested full audit covers all source files. If the implementation artifact is missing, use the diff and state the gap.

Detect every language in scope. Reuse existing integration evidence for unchanged connections; trace affected producers and consumers beyond the diff where needed.

**Gate:** Scope and languages are known.

## Phase 1: EXPORT/IMPORT MAP

Inventory public symbols using language-aware searches:

- Go: exported package functions, types, constants, variables, and methods.
- Python: module definitions, `__all__`, and `__init__.py` re-exports.
- TypeScript/JavaScript: named/default exports and barrel re-exports.

Exclude dependencies, generated files, build output, fixtures, and repository metadata. Apply the reference's exceptions for public library APIs, plugin contracts, framework entrypoints, and other legitimate external consumers before calling a symbol orphaned.

For each symbol, record file, name, kind, and line. Find imports and actual usage; an import alone does not establish wiring. Classify as ORPHANED, IMPORTED_NOT_USED, or WIRED using the reference. Report failures first; show successful connections only in verbose mode.

**Gate:** Every in-scope symbol has a status or an explicit unresolved limitation.

## Phase 2: DATA FLOW AND CONTRACT CHECK

Trace WIRED connections for real inputs and compatible contracts. Check hardcoded empty data, placeholders, dead parameters, mock remnants, shape/type mismatches, and event/message names using the reference.

Static inspection establishes structure and likely compatibility, not runtime correctness. Use existing runtime evidence where available; distinguish observed failures from uncertain dynamic-language matches. Low-confidence contract findings warn rather than fail.

**Gate:** Data-flow and contract findings include locations, evidence, and confidence.

## Phase 3: REPORT

Report component counts, wiring failures, data-flow issues, contract mismatches, and concrete fixes. In pipeline mode, use `.feature/state/plan/` to map each requirement from entrypoint to implementation as WIRED, PARTIAL, or UNWIRED.

Compute integration score as `100 * WIRED / (WIRED + IMPORTED_NOT_USED + ORPHANED)`; report N/A when the denominator is zero.

| Verdict | Condition | Next action |
|---|---|---|
| PASS | No wiring, flow, or contract issues | Continue validation |
| WARN | Unused imports or low-confidence contract findings only | Resolve or explain warnings |
| FAIL | Orphaned components, data-flow defects, or high-confidence contract mismatches | Return concrete fixes to implementation |

State incomplete coverage separately; missing source or unresolved scope cannot establish a PASS. Include circular imports as integration findings. For a large monorepo, narrow to affected connections unless the user requested a full audit; split a full audit into bounded scopes without silently omitting files.

**Gate:** Findings, limitations, and next actions are clear. After fixes, recheck affected connections rather than repeating unchanged analysis.

## References

- [Feature state conventions](../../process/feature-lifecycle/references/shared.md)
