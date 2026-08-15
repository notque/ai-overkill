# Test Scaffold and Temporary File Patterns

> **Scope**: Identifying and cleaning up test scaffolds, development helpers, and temporary files created during task iteration. Does not cover test framework usage or test writing.
> **Version range**: all versions
> **Generated**: 2026-05-11 — applies to all languages and project types

---

## Overview

Agents routinely create throwaway files during exploration: debug scripts, one-off validators, test scaffolds, and helper stubs. These must be removed at task completion. The challenge is distinguishing files that were *requested by the user* or *needed for future context* from purely ephemeral development artifacts. Leaving scaffolding behind clutters repos and creates false signals in future code searches.

---

## Pattern Table: File Categories

| Category | Characteristics | Action |
|----------|-----------------|--------|
| Test scaffold | `test_`, `_test`, `debug_`, `temp_` prefix/suffix; no imports from main code | Delete at task completion |
| Development helper | Single-use scripts (`check_something.py`, `validate_once.sh`) | Delete after confirming task done |
| Requested artifact | Explicitly mentioned in user prompt; committed to repo | Keep |
| Future-context file | Contains state needed for next task step | Keep until that step completes |
| Framework test file | In `tests/`, `__tests__/`, `spec/` dirs; follows project conventions | Always keep |

---

## Correct Patterns

### Identifying Temporary Files Before Cleanup

Scan the working directory for common scaffold naming patterns before closing a task.

```bash
# Find likely test scaffolds by naming pattern
find . -name "test_*.py" -not -path "*/tests/*" -not -path "*/__tests__/*"
find . -name "*_test.sh" -not -path "*/test/*"
find . -name "debug_*.py" -o -name "temp_*.py" -o -name "check_*.py"
find . -name "validate_*.sh" -newer CLAUDE.md  # files created this session
```

**Why**: Without active cleanup, repos accumulate orphan scripts that break `grep` searches and confuse future agents reading the codebase.

---

### Distinguishing Scaffold from Framework Test

Project test frameworks use specific directory conventions — files *inside* those dirs are permanent; files *outside* with test-like names are scaffolding.

```bash
# Files that are definitely framework tests (keep):
find . -path "*/tests/*.py" -o -path "*/__tests__/*.ts" -o -path "*/spec/*.rb"

# Files that are likely scaffolding (verify before deleting):
find . -maxdepth 3 -name "test_*.py" -not -path "*/tests/*"
find . -maxdepth 3 -name "*.test.ts" -not -path "*/__tests__/*"
find . -maxdepth 3 -name "*_spec.rb" -not -path "*/spec/*"
```

---

## Pattern Catalog: Detection and Fixes

### Orphaned Debug Scripts

**Detection**:
```bash
grep -rn "import pdb\|breakpoint()\|console\.log.*debug\|print.*DEBUG" \
  --include="*.py" --include="*.js" --include="*.ts"
rg 'pp\s+\w+|pry\s+binding|debugger;' --type rb --type js
```

**Signal**:
```python
# debug_invoice.py — created to test a hypothesis
import pdb
from app.models import Invoice

inv = Invoice.objects.first()
pdb.set_trace()
print(inv.__dict__)
```

**Why it matters**: Debug files checked in accidentally expose internal data structures in diffs and can introduce interactive debugger calls that halt production processes if a branch is merged.

**Preferred action**: Delete before committing. If the exploration revealed something useful, extract the finding into a comment in the relevant source file, not into a standalone script.

---

### One-off Validation Scripts

**Detection**:
```bash
find . -maxdepth 2 -name "validate_*.py" -o -name "check_*.py" -o -name "verify_*.sh"
rg '^#!/.+(python|bash|sh)' --files-with-matches | xargs grep -l "TODO: remove\|one.time\|temp\|temporary"
```

**Signal**:
```python
# validate_migration.py — written to check if data migration ran correctly
import psycopg2
conn = psycopg2.connect(...)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM users WHERE migrated_at IS NULL")
print(cur.fetchone())
```

**Why it matters**: Validation scripts left in repos get run by other engineers thinking they're part of the toolchain. If they connect to production databases or mutate state, this causes incidents.

**Preferred action**: Run the script, record the output in the PR description or a comment, then delete the file.

---

### Unimplemented Stubs

**Detection**:
```bash
grep -rn "pass$\|raise NotImplementedError\|throw new Error.*not implemented" \
  --include="*.py" --include="*.ts" --include="*.go"
rg '^\s+pass$' --type py -l
rg 'panic\("not implemented"\)' --type go -l
```

**Signal**:
```typescript
// stub created to unblock a dependent feature
export function sendEmail(to: string, body: string): void {
  // TODO: implement
  throw new Error('not implemented')
}
```

**Why it matters**: Stub functions look like real functions to callers and automated tools. If the stub gets imported but the implementation never arrives, the failure appears at call time (often in production) not at definition time.

**Preferred action**: If the stub is permanent scaffolding (intentional), mark it with the owning ticket. If it was a development convenience, delete it and remove the import.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| `grep` finds duplicate function names | Scaffold defines same function as real source | Delete scaffold file, verify real source has the implementation |
| CI fails on import of deleted module | Scaffold was imported elsewhere during development | Audit imports with `rg 'from.*scaffold\|import.*temp'` and remove |
| "file already exists" on scaffold creation | Previous session left a scaffold | Delete the stale file before creating new one |
| Test runner picks up scaffold | Scaffold filename matches test discovery pattern | Rename with non-test prefix or move outside test dirs |

---

## Detection Commands Reference

```bash
# Files newer than CLAUDE.md (created this session)
find . -newer CLAUDE.md \( -name "*.py" -o -name "*.sh" -o -name "*.ts" \) \
  | grep -v __pycache__ | grep -v node_modules

# Common scaffold naming patterns (outside framework dirs)
find . -maxdepth 3 \( \
  -name "test_*.py" -o -name "debug_*.py" -o -name "temp_*.py" \
  -o -name "check_*.py" -o -name "validate_*.py" -o -name "scratch_*.py" \
  \) -not -path "*/tests/*" -not -path "*/__tests__/*"

# Scripts with shebang and temporary markers
rg '#!/.+(python|bash)' --files-with-matches \
  | xargs grep -l -i "temp\|scaffold\|remove after\|one.time"

# Python stubs (empty body)
rg '^\s+pass$' --type py -l

# TypeScript/Go unimplemented stubs
rg 'throw new Error.*not implemented|panic\("not implemented"\)' \
  --type ts --type go -l
```
