# Ruff Rules Reference

> **Scope**: Common ruff rule categories, violation patterns, detection commands, and fixes for Python code. Focuses on the violations that appear most often in real codebases — not an exhaustive catalog of all 800+ rules.
> **Version range**: ruff 0.1.0+; `ruff format` command available since ruff 0.3.0
> **Generated**: 2026-04-16 — verify rule codes against current ruff release notes

---

## Overview

Ruff is a fast Python linter and formatter replacing flake8, isort, and black. Rules are grouped by category prefix. Auto-fixable rules respond to `ruff check --fix`; others require manual edits. The most common CI failure: passing `ruff check` but failing `ruff format --check` — they are separate commands with separate output. Always run both.

---

## Rule Category Table

| Prefix | Category | Auto-fixable | Common rules |
|--------|----------|-------------|--------------|
| `E` | pycodestyle errors | Some | E501 (line length), E711 (== None), E712 (== True/False) |
| `W` | pycodestyle warnings | Most | W291 (trailing whitespace), W293 (whitespace blank line) |
| `F` | pyflakes | Partial | F401 (unused import), F811 (redefined unused), F841 (unused var) |
| `I` | isort | Yes | I001 (import order) |
| `UP` | pyupgrade | Yes | UP007 (use `X \| Y` unions), UP006 (use `list` not `List`) |
| `B` | bugbear | No | B006 (mutable default arg), B007 (unused loop var), B023 (lambda in loop) |
| `N` | pep8-naming | No | N802 (function not lowercase), N803 (argument not lowercase) |
| `T` | flake8-print | No | T201 (print statement), T203 (pprint) |
| `ANN` | annotations | No | ANN001 (missing arg annotation), ANN201 (missing return type) |
| `C` | complexity | No | C901 (McCabe complexity > threshold) |
| `RUF` | ruff-specific | Some | RUF100 (unused noqa directive), RUF010 (explicit string conversion) |

---

## Correct Patterns

### Running check and format together

```bash
# Check violations (read-only)
ruff check . --config pyproject.toml

# Check formatting without applying changes
ruff format --check . --config pyproject.toml

# Apply all safe auto-fixes
ruff check --fix . --config pyproject.toml
ruff format . --config pyproject.toml
```

**Why**: CI typically gates on both commands. Passing `ruff check` but failing `ruff format --check` is the most common cause of green-locally-but-red-CI.

---

### Per-file ignores for generated or test code

```toml
# pyproject.toml
[tool.ruff.lint.per-file-ignores]
"migrations/*.py" = ["E501", "F401"]
"tests/*.py" = ["ANN001", "ANN201", "T201"]
"**/conftest.py" = ["F401"]
```

**Why**: Generated migration files have intentional long lines and unused imports. Test files legitimately use print for debugging and don't need return type annotations.

---

### Suppressing a single line with specific codes

```python
# Correct: specific rule code on the line that needs it
result = some_func()  # noqa: F841
import os, sys        # noqa: E401, F401

# Wrong: blanket noqa with no code
result = some_func()  # noqa
```

**Why**: Blanket `# noqa` hides future violations on that line. Rule-specific suppression is auditable with `ruff check --select RUF100` which flags unused noqa directives.

---

## Pattern Catalog

### Use Identity Checks for None and Boolean Comparisons (E711/E712)

**Detection**:
```bash
grep -rn '== None\|== True\|== False\|!= None' --include="*.py"
rg '(==|!=)\s+(None|True|False)' --type py
```

**Signal**:
```python
if result == None:
    return
if flag == True:
    process()
if items != None and len(items) == 0:
    return []
```

**Why this matters**: `== None` uses equality comparison for an identity check. Works in CPython but `is None` is correct and triggers no E711. `== True` triggers E712 and fails for truthy non-bool values.

**Preferred action**:
```python
if result is None:
    return
if flag:
    process()
if not items:
    return []
```

---

### Use Immutable Default Arguments (B006)

**Detection**:
```bash
rg 'def \w+\([^)]*=\s*(\[\]|\{\}|\(\))' --type py
grep -rn 'def .*=\s*\[\|def .*=\s*{' --include="*.py"
```

**Signal**:
```python
def append_item(item, container=[]):   # B006
    container.append(item)
    return container

def merge_config(opts={}):  # B006
    opts.update({"debug": False})
    return opts
```

**Why this matters**: Default argument is evaluated once at function definition time. All callers share the same list/dict object. State leaks between calls — a debugging nightmare.

**Preferred action**:
```python
def append_item(item, container=None):
    if container is None:
        container = []
    container.append(item)
    return container
```

---

### Use Modern Type Annotations (UP006/UP007/UP035)

**Detection**:
```bash
grep -rn 'from typing import.*List\|from typing import.*Dict\|from typing import.*Optional' --include="*.py"
rg 'typing\.(List|Dict|Optional|Tuple|Set|FrozenSet)\[' --type py
```

**Signal**:
```python
from typing import List, Dict, Optional, Tuple

def process(items: List[str], config: Dict[str, int]) -> Optional[Tuple[int, str]]:
    ...
```

**Why this matters**: Python 3.9+ supports `list[str]`, `dict[str, int]` directly. Python 3.10+ supports `str | None` instead of `Optional[str]`. Using old forms in 3.9+ codebases triggers UP006/UP007 and signals pre-3.9 vintage code.

**Preferred action**:
```python
# Python 3.9+
def process(items: list[str], config: dict[str, int]) -> tuple[int, str] | None:
    ...
```

**Version note**: UP006 requires `target-version = "py39"` in pyproject.toml. UP007 requires `target-version = "py310"`. Set `target-version` to match the project's minimum Python version.

```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
```

---

### Capture Loop Variables by Value in Lambdas (B023)

**Detection**:
```bash
rg 'lambda.*:\s*.*\b\w+\b' --type py -A2 | grep -B2 'for .* in'
grep -rn 'lambda' --include="*.py"
```

**Signal**:
```python
handlers = [lambda x: x + i for i in range(5)]   # all lambdas use i=4
callbacks = []
for name in names:
    callbacks.append(lambda: process(name))  # all use final name
```

**Why this matters**: Lambda captures the variable by reference, not value. By execution time, the loop variable holds its final value. All lambdas behave identically regardless of which iteration created them.

**Preferred action**:
```python
handlers = [lambda x, i=i: x + i for i in range(5)]  # default arg captures value
callbacks = []
for name in names:
    callbacks.append(lambda n=name: process(n))
```

---

### Remove Unused Imports (F401)

**Detection**:
```bash
ruff check --select F401 . --config pyproject.toml
rg '^import |^from .* import' --type py
```

**Signal**:
```python
import os       # never used below
import sys      # never used below
from pathlib import Path  # used
```

**Why this matters**: Dead imports slow startup, confuse readers, and fail CI. Common culprit: imports used in removed code, or imports that were only in type comments.

**Preferred action**:
```bash
ruff check --fix --select F401 . --config pyproject.toml
git diff  # review: --fix can remove imports used in __all__ or TYPE_CHECKING blocks
```

**Version note**: ruff 0.1.0+ auto-fixes F401. Review diff when `__all__` exports are present — ruff may remove an import that's only used in `__all__`.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `E501 Line too long (N > 88)` | Line exceeds configured `line-length` | Break expression, implicit string concat, or raise `line-length` in pyproject.toml |
| `F401 'X' imported but unused` | Import not referenced | Remove or add to `__all__`; run `ruff check --fix --select F401` |
| `I001 Import block is un-sorted` | Imports not in isort order | `ruff check --fix --select I .` |
| `E711 Comparison to None (==)` | Using `==` for identity check | Replace `== None` → `is None` |
| `E712 Comparison to True/False` | Using `==` for boolean check | Replace `== True` → `if x:`, `== False` → `if not x:` |
| `B006 Do not use mutable data structures for argument defaults` | `=[]` or `={}` in signature | Use `=None` with `if x is None: x = []` pattern |
| `UP007 Use 'X \| Y' for union type annotation` | `Optional[X]` in 3.10+ code | Replace `Optional[str]` → `str \| None` |
| `ruff: command not found` | Not installed or venv not active | `./venv/bin/ruff` or `pip install ruff` |
| `No pyproject.toml found` | Running from wrong directory | cd to project root where pyproject.toml lives |
| `RUF100 Unused 'noqa' directive` | noqa suppresses a rule that doesn't fire | Remove the noqa comment or update the rule code |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| ruff 0.1.0 | Initial release; new `[tool.ruff.lint]` section in pyproject.toml | Old `[tool.ruff]` rule config must move to `[tool.ruff.lint]` |
| ruff 0.3.0 | `ruff format` added (replaces black) | Must run separately from `ruff check`; separate CI step required |
| ruff 0.4.0 | `preview = true` enables upcoming rules | Don't enable `preview` in CI without pinning ruff version |
| ruff 0.6.0 | `--output-format=github` for CI annotations | Use in GitHub Actions for inline PR comments on violations |

---

## Detection Commands Reference

```bash
# Unused imports
ruff check --select F401 . --config pyproject.toml

# Type annotation upgrade opportunities
ruff check --select UP . --config pyproject.toml

# Mutable default arguments
rg 'def \w+\([^)]*=\s*(\[\]|\{\}|\(\))' --type py

# print() statements
ruff check --select T201 . --config pyproject.toml

# Lambda in loop (potential variable capture bug)
rg 'lambda' --type py

# Check only formatting (no changes applied)
ruff format --check . --config pyproject.toml

# Preview what auto-fix would change
ruff check --diff . --config pyproject.toml

# Count violations by rule
ruff check . --config pyproject.toml --output-format=json | python3 -c "
import json,sys
from collections import Counter
data=json.load(sys.stdin)
print(Counter(d['code'] for d in data).most_common(10))
"
```

---

## See Also

- `biome-rules-reference.md` — JavaScript/TypeScript linting with Biome
- [ruff documentation](https://docs.astral.sh/ruff/)
- [ruff rules index](https://docs.astral.sh/ruff/rules/)
