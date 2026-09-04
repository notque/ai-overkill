---
name: universal-quality-gate
description: "Multi-language code quality gate with auto-detection and linters."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "quality gate"
    - "lint check"
    - "multi-language lint"
    - "code quality check"
    - "language-agnostic lint"
  category: code-quality
  pairs_with:
    - code-linting
    - verification-before-completion
---

# Universal quality gate

Run configured lint, format, type, and security checks across project languages. Tests and builds remain separate checks.

## Run

Read repository instructions and configuration first. Use the repository's prescribed checks when present; the adapter below supplies multi-language detection through `hooks/lib/language_registry.json` and `hooks/lib/quality_gate.py`.

```bash
python3 ~/.claude/skills/code-quality/universal-quality-gate/scripts/run_quality_gate.py
```

| Option | Use |
|---|---|
| `--staged` | Check staged files before commit |
| `--lang python` | Focus on one language |
| `--fix` | Apply configured fixes within authorized scope |
| `-v` | Expanded diagnostics |
| `--no-patterns` | Skip informational pattern scanning |

Check before fixing, review `git diff` afterward, and rerun affected checks. Do not add tools, change rules, or make required tools optional to get a pass.

## Detection

The registry is authoritative; these are its language families:

| Language | Markers | Tools |
|---|---|---|
| Python | pyproject.toml, requirements.txt | ruff, mypy, bandit |
| Go | go.mod | gofmt, golangci-lint, go vet |
| JavaScript | package.json | eslint, biome |
| TypeScript | tsconfig.json | tsc, eslint, biome |
| Rust | Cargo.toml | clippy, cargo fmt |
| Ruby | Gemfile | rubocop |
| Java | pom.xml, build.gradle | PMD |
| Shell | *.sh, *.bash | shellcheck |
| YAML | *.yml, *.yaml | yamllint |
| Markdown | *.md | markdownlint |

## Results and recovery

Capture output and exit status. Report checked scope, required failures, optional skips, and useful file:line diagnostics. Keep full logs available without pasting every successful result. A gate pass means required tools passed; it does not prove tests, builds, or business behavior passed.

- **Required tool missing or failed:** report a blocked or failed check. Use the project environment and declared dependency setup; do not downgrade the requirement.
- **Optional tool unavailable:** report it as skipped, not passed. `[WARNING]` pattern matches are informational; inspect them for actual defects.
- **No files:** check project root, marker files, and `git diff --cached --name-only` for staged mode. Empty scope is not evidence of code quality; do not stage unrelated work to populate it.
- **Timeout:** inspect generated or large files and I/O. Use `--staged` or `--lang` for diagnosis, but state reduced coverage and complete required checks before claiming a full pass.
- **Conflicting configuration:** read project instructions and package scripts to identify the intended tool. Do not silently remove checks or edit the registry.

When explicitly adding a language, extend `hooks/lib/language_registry.json` with `extensions`, `markers`, and `tools`; each tool declares `cmd`, optional `fix_cmd`, `description`, and `required`. The adapter reads the registry on the next run.
