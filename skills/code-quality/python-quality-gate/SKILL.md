---
name: python-quality-gate
description: "Python quality checks: ruff, pytest, mypy, bandit in deterministic order."
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
agent: python-general-engineer
routing:
  force_route: true
  not_for: "general Python coding (use python-general-engineer), data analysis scripts, or tutorials — fires when the user wants ruff/mypy/pytest/bandit quality checks run on existing code"
  triggers:
    - "Python quality"
    - "ruff check"
    - "bandit scan"
    - "mypy check"
    - "python lint"
    - "python quality gate"
    - "check python"
    - "pre-commit check"
  category: code-quality
  pairs_with:
    - code-linting
    - test-driven-development
---

# Python quality gate

Run Python checks in order: Ruff lint, Ruff format, mypy, pytest, Bandit. Read repository instructions and configuration first; project commands and thresholds override defaults.

## Detect

Find `pyproject.toml`, `setup.py`, `setup.cfg`, `mypy.ini`, and `.python-version`. Identify the Python target, tool settings, source directories (`src/`, `app/`, `lib/`, or root), and test discovery configuration.

Use the project environment. Check `ruff --version`, `pytest --version`, `mypy --version`, and `bandit --version`. Ruff and pytest are required; missing tools block execution (status 2). Mypy and Bandit are optional unless the project requires them. Report unavailable tools as skipped. Do not install tools or alter configuration for a check-only request; setup may require `pip install ruff pytest pytest-cov`.

## Execute

Capture each command's output and exit status. Use configured paths; replace `src` below with the actual source path. Preserve stricter project settings rather than overriding them with defaults.

| Order | Default command | Condition |
|---|---|---|
| 1 | `ruff check . --output-format=grouped` | Required |
| 2 | `ruff format --check .` | Required |
| 3 | `mypy . --ignore-missing-imports --show-error-codes` | If available; omit `--ignore-missing-imports` when it weakens project policy |
| 4 | `pytest -v --tb=short --cov=src --cov-report=term-missing` | Use coverage only when configured/requested and pytest-cov is installed |
| 5 | `bandit -r src/ -ll --format=screen` | If available |

Run all available checks even after one fails; a test failure is a result, not a tool crash. Do not skip tests to get a pass. If there are no discovered tests, report that coverage gap; tests may live outside a `tests/` directory.

## Assess and report

Repository gates take precedence. Legacy default failure thresholds are Ruff F errors, test failures, high-severity Bandit issues, more than 10 mypy errors, and coverage below 80% when enabled. Always report each nonzero tool result separately; an aggregate threshold must not be described as every tool passing. Formatting failures and repository-required checks remain failures.

Prioritize syntax/undefined-name errors, failing tests, and security findings before style. `ruff check . --statistics` identifies counts and `[*]` fixable rules. Report overall result, per-tool status, actionable file:line diagnostics, coverage when measured, skipped checks, and suggested fixes. Preserve full logs rather than pasting every result. Write a full report when requested, including to `--output {file}` when supplied.

## Fix and recover

When fixes are authorized, check first, run `ruff check . --fix` and `ruff format .`, inspect `git diff`, then rerun affected checks. Do not widen cleanup scope or change settings to hide failures.

- **Wrong directory/no Python files:** verify project root and configured source paths.
- **Mypy cache corruption:** confirm the project cache, remove `.mypy_cache`, and retry once. If it still fails, report an incomplete type check; do not call it passed.
- **Missing required tool:** report its name and setup command; do not continue as though the gate passed.

## Reference loading table

| Signal | Reference |
|---|---|
| Detailed rule severity, command options, output parsing | `references/tool-commands.md` |
| Full structured report requested | `references/report-template.md` |
| Tool configuration setup requested | `references/pyproject-template.toml` |
