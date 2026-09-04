---
name: code-linting
user-invocable: false
description: "Run Python (ruff) and JavaScript (Biome) linting."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
routing:
  triggers:
    - "lint code"
    - "run ruff"
    - "run biome"
    - "format code"
    - "lint errors"
  category: code-quality
  pairs_with:
    - code-cleanup
    - universal-quality-gate
    - python-quality-gate
---

# Code linting

Check or fix Python with Ruff and JavaScript/TypeScript with Biome. Use repository commands and configuration before these defaults. Read project instructions, `pyproject.toml`, and `biome.json`; preserve configured rules and line width.

## Check and fix

Use the project virtual environment (`./venv/bin/ruff` or `./env/bin/ruff`) and installed JavaScript tooling. For mixed projects, check both languages unless the task selects one. Adapt `src/` to the actual source directory.

| Task | Python | JavaScript/TypeScript |
|---|---|---|
| Check | `ruff check .` | `npx @biomejs/biome check src/` |
| Format check | `ruff format --check .` | Included in Biome check |
| Fix lint | `ruff check --fix .` | `npx @biomejs/biome check --write src/` |
| Format | `ruff format .` | `npx @biomejs/biome format --write src/` |

If configured, use `make lint` or `make lint-fix`. Check first; apply fixes only within the requested work. Review `git diff`, undo incorrect fixes, then rerun lint and format checks. Do not change rules, install new tooling, or expand cleanup scope merely to get a pass.

For remaining issues: F401 means remove or use the import; I001 needs import sorting; E501 needs shorter lines within existing settings. Biome `noVar` uses `let`/`const`, `useConst` marks unchanged bindings, and `noDoubleEquals` uses strict equality where semantics allow.

Report commands, exit status, and actionable rule/file:line diagnostics. Keep full logs available; summarize passing checks. Remove only temporary files created for this run, preserving useful failure logs.

## Recovery and optional modes

- **Ruff missing:** check the project virtual environment. Installation options are `pip install ruff` or `pipx run ruff check .`; install only within authorized dependency work.
- **Biome missing:** check package dependencies before npx execution; do not let a read-only check download tooling unexpectedly.
- **Config missing:** verify project root before running defaults.
- **Strict warnings, format-only, or rule exceptions:** use only when requested; do not weaken repository requirements.

## Reference loading table

| Signal | Reference |
|---|---|
| Ruff rules, configuration, versions, or F401/E711/B006/UP errors | `references/ruff-rules-reference.md` |
| Biome rules, configuration, ESLint migration, or noVar/useConst/noDoubleEquals | `references/biome-rules-reference.md` |
| Lint versus format CI failure | Relevant tool reference above |
