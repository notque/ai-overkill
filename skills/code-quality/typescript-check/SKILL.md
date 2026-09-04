---
name: typescript-check
description: "TypeScript type checking via tsc --noEmit with actionable error output."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
agent: typescript-frontend-engineer
routing:
  triggers:
    - "TypeScript check"
    - "tsc noEmit"
    - "type check TypeScript"
    - "tsc errors"
    - "TypeScript type validation"
  category: code-quality
  pairs_with:
    - vitest-runner
    - code-linting
---

# TypeScript check

Read-only type validation. Follow repository instructions and package scripts; preserve project compiler settings. Do not fix code, change configuration, or install dependencies for a check-only request.

## Run

1. Locate `tsconfig.json`, including `src/`, `app/`, and `packages/`. In a monorepo, use the package affected by the task or the repository's aggregate check. Ask only when the target cannot be inferred. If no config exists, report the missing configuration and stop.
2. Confirm TypeScript is installed locally before using npx; do not allow an implicit package download.
3. Run `npx tsc --noEmit 2>&1`, or `npx tsc --noEmit --project path/to/tsconfig.json 2>&1` for a selected config. Capture output and exit code. Zero means pass; nonzero may mean type errors or a tool/configuration failure—report which.
4. Report status and error count. Group diagnostics by file and line, retaining `file:line:column`, `TS####`, and the message. Retain complete logs; show useful failure details instead of all successful output.

## Recovery and flags

- **TypeScript missing:** report it; suggest `npm install typescript --save-dev` within dependency setup.
- **npx missing:** check `node --version`; when Node/npm and local TypeScript exist, use `npm exec tsc -- --noEmit`. Otherwise report the missing toolchain.
- **Multiple configs:** list the checked configs and any omitted packages. A single-package pass is not a whole-repository pass.
- **`--skipLibCheck`:** skips declaration-file checking; use only when configured or requested, not to hide failures.
- **`--strict`:** adds strict checks; enable only when requested or configured.
- **`--incremental`:** may write build-info cache files; enable only when permitted, not for a strictly read-only run.
- **Named files:** passing files directly bypasses project config. Prefer `--project`; do not claim equivalent coverage from a narrower check.

When running the full JavaScript/TypeScript check sequence, lint first, type-check next, then run tests with `vitest-runner` or the repository test command.
