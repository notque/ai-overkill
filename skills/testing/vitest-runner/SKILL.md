---
name: vitest-runner
description: "Run Vitest tests and parse results into actionable output."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "run vitest"
    - "JavaScript tests"
    - "TypeScript tests"
    - "vite tests"
    - "vitest output"
  category: testing
  pairs_with:
    - test-driven-development
    - typescript-check
    - e2e-testing
---

# Vitest runner

Run existing Vitest tests and report results. A check-only request does not authorize changing tests, assertions, dependencies, or configuration.

## Run

Read repository instructions and package scripts. Check `package.json`, `vitest.config.*`, and `vite.config.*` to confirm Vitest and its test configuration. Use the installed project version; avoid implicit npx downloads. If Vitest is unavailable, report setup needed rather than installing it.

Use the repository test command or these defaults. Always use `run`; bare `vitest` can enter watch mode.

| Scope | Command |
|---|---|
| Whole configured suite | `npx vitest run --reporter=verbose 2>&1` |
| File or directory | `npx vitest run path/to/test.ts 2>&1` |
| Test-name pattern | `npx vitest run -t "pattern" 2>&1` |
| Requested coverage | `npx vitest run --coverage 2>&1` |

Capture the process exit code and full output. Report pass/fail, checked scope, passed/failed/skipped counts, and duration. For failures retain the file, full test name, assertion difference, and relevant stack location. Keep complete logs available; show useful excerpts instead of every passing test. Nonzero exit is failure, including discovery or tool failures; partial output is not a passing run.

## Recovery

- **Vitest missing/node_modules absent:** inspect dependencies. Setup may require `npm install` or `npm install -D vitest`; use the repository package manager during authorized setup.
- **No test files:** check file naming (`*.test.ts`, `*.spec.ts`, `*.test.js`) and configured include/exclude globs. Report discovery failure; do not change config to mask it.
- **Missing DOM environment:** inspect `environment` for `jsdom` or `happy-dom`. Suggest the matching devDependency (`npm install -D jsdom` or `npm install -D happy-dom`); `@testing-library/jest-dom` adds matchers, not an environment.
- **Out of memory:** diagnose with directory batches such as `npx vitest run src/unit/`, `--pool=forks`, or `--shard=1/N` when supported by the installed version. A full-suite claim requires all batches/shards; a diagnostic subset is not full verification.
- **Failing assertions:** report the mismatch. When fixing is authorized, determine whether implementation or test is wrong; never weaken assertions merely to make the run green.
