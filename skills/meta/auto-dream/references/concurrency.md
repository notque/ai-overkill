# Concurrency Reference

> **Scope**: Patterns for preventing concurrent dream runs, handling interrupted cycles, managing atomic file writes, and safe SQLite access when multiple processes share the learning database. Does NOT cover memory file content or the cron schedule itself.
> **Version range**: All toolkit versions using `flock`-based wrapper scripts and `sqlite3` learning DB
> **Generated**: 2026-04-16 — verify `flock` flags against your OS man page (Linux vs macOS differ)

---

## Overview

The auto-dream cycle modifies shared state: `MEMORY.md`, `last-dream.md`, the learning database, and occasionally git branches. Two concurrent dream runs would produce interleaved writes that corrupt the index and leave phase state inconsistent. Three mechanisms protect against this: `flock` prevents concurrent cron invocations, POSIX atomic rename prevents partial `MEMORY.md` writes, and SQLite WAL mode prevents database corruption under concurrent reads. Understanding each layer helps diagnose failures when any of them breaks down.

---

## Pattern Table

| Problem | Mechanism | Signal that it's broken |
|---------|-----------|------------------------|
| Concurrent cron runs | `flock -n` on lockfile | Two `auto-dream` PIDs visible simultaneously |
| Partial MEMORY.md write | `mv .tmp → .md` atomic rename | `.tmp` file left behind after cycle, index truncated |
| SQLite contention | WAL mode + `PRAGMA busy_timeout` | `sqlite3: database is locked` in cron log |
| Interrupted cycle | REPORT written before CONSOLIDATE | No `last-dream.md` but scan/analysis files exist |
| Git working tree dirty before GRADUATE | `git stash` before branch switch | Graduate fails with `error: Your local changes would be overwritten` |

---

## Correct Patterns

### Exclusive lockfile with `flock`

The wrapper script acquires a non-blocking exclusive lock before invoking Claude. If another run holds the lock, the new invocation exits immediately (exit code 1) rather than waiting and queuing.

```bash
LOCKFILE="/tmp/auto-dream.lock"

# -n: non-blocking (fail immediately if locked)
# -E 1: exit code 1 if lock not acquired
# exec 9> opens file descriptor 9 on the lockfile
(
  flock -n -E 1 9 || { echo "[dream] Already running (lockfile held), exiting"; exit 1; }
  # --- dream logic runs here ---
) 9>"$LOCKFILE"
```

**Why**: Cron fires at wall-clock intervals. If a run takes longer than the interval (network latency, large memory set), the next scheduled run must not overlap. Non-blocking (`-n`) is safer than waiting — queued runs pile up and the subsequent run inherits stale context from the previous one.

**Linux vs macOS note**: On macOS, use `flock` from `brew install util-linux` or substitute with `lockfile` from `procmail`. The flag syntax is identical on Linux.

---

### POSIX atomic rename for MEMORY.md

Never write `MEMORY.md` directly. The session-start hook reads this file at startup — a partial write during an interrupted cycle produces an invalid index that silently excludes all memories.

```bash
# Phase 3 / Phase 4 MEMORY.md updates — always via tmp
python3 - <<'EOF'
import os

new_content = build_updated_index()  # your index generation

tmp_path = "memory/MEMORY.md.tmp"
final_path = "memory/MEMORY.md"

with open(tmp_path, "w") as f:
    f.write(new_content)

# os.rename is atomic on POSIX (same filesystem)
os.rename(tmp_path, final_path)
EOF
```

**Why**: On POSIX filesystems (Linux ext4, macOS APFS), `rename(2)` is atomic — the old `MEMORY.md` is visible until the exact moment the new one replaces it. There is no window where neither file exists. Direct `open(..., "w")` truncates the file before writing, creating a window where `MEMORY.md` is empty.

---

### SQLite WAL mode and busy timeout

The learning database (`learning.db`) is accessed by hooks (which fire on every tool call) AND by the dream cycle during Phase 1 SCAN and Phase 5 GRADUATE. Without WAL mode, a long dream read blocks all hook writes.

```bash
# Set WAL mode once (persists in the database file)
sqlite3 "${DREAM_LEARNING_DB}" "PRAGMA journal_mode=WAL;"

# Set busy timeout for dream-cycle queries (5 seconds)
sqlite3 "${DREAM_LEARNING_DB}" \
  "PRAGMA busy_timeout=5000; SELECT session_id FROM sessions LIMIT 1;"
```

```python
# In Python (hooks/lib/learning_db_v2.py style)
import sqlite3

def get_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
```

**Why**: WAL (Write-Ahead Log) mode allows one writer and multiple concurrent readers without blocking. Without it, a `SELECT` from the dream cycle holds a shared lock that prevents hook `INSERT`s from completing, causing hooks to fail silently. The `busy_timeout` prevents immediate `SQLITE_BUSY` errors when brief lock contention occurs.

**Version note**: WAL mode available in SQLite 3.7.0+ (2010). All modern systems qualify. WAL setting persists in the database file — you only need to set it once per database, not per connection.

---

### Git stash before GRADUATE branch switch

Phase 5 GRADUATE switches to a `dream/graduate-*` branch. If any file was modified in an earlier phase without committing (e.g., a MEMORY.md write in Phase 3 was not committed to any branch), the checkout fails.

```bash
# In dream-prompt.md Phase 5 — before git checkout
GRAD_BRANCH="dream/graduate-${DREAM_DATE}"

# Stash any uncommitted changes before branch switch
if [ -n "$(git status --porcelain)" ]; then
    git stash --quiet
    STASHED=1
fi

# Now safe to switch branches
if git rev-parse --verify "$GRAD_BRANCH" >/dev/null 2>&1; then
    git checkout "$GRAD_BRANCH"
else
    git checkout -b "$GRAD_BRANCH" main
fi

# After all graduate commits and push:
git checkout main
[ "${STASHED:-0}" = "1" ] && git stash pop --quiet
```

**Why**: The dream cycle operates in the same working tree as active development. A user might have unstaged edits. The stash ensures GRADUATE does not fail or accidentally commit unrelated changes. The stash pop restores state cleanly after GRADUATE finishes.

---

## Pattern Catalog
<!-- no-pair-required: section heading only, paired Do instead blocks appear in each sub-entry below -->

### Use Non-Blocking flock to Skip Concurrent Runs

**Detection**:
```bash
# Find flock without -n (non-blocking) flag in wrapper scripts
grep -rn 'flock' scripts/ | grep -v '\-n\b'
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```bash
# Blocking flock — waits indefinitely for the lock
flock /tmp/auto-dream.lock claude -p "..."
```

**Why this matters**: If a dream run takes 8 minutes and cron fires every 5, the second invocation waits 3 minutes, then runs immediately after the first finishes. The second run's SCAN sees the same memory state as the first (before consolidation results are visible). The result is two consecutive consolidation cycles that produce conflicting MEMORY.md states.

**Preferred action**: Use `flock -n` so each cron tick either acquires the lock and proceeds or exits immediately with a logged skip message. A skipped tick is safe; back-to-back consolidation cycles are not.

**Preferred action**:
```bash
flock -n -E 1 /tmp/auto-dream.lock claude -p "..." || {
    echo "[dream] Already running, skipping this invocation"
    exit 0
}
```

---

### Complete Interrupted Renames Instead of Skipping

**Detection**:
```bash
# Find code that tests for .tmp existence before writing
grep -rn '\.tmp.*exist\|os\.path\.exists.*\.tmp' scripts/ hooks/
```

**Signal**:
```python
if os.path.exists("memory/MEMORY.md.tmp"):
    print("Previous write failed, skipping update")
    return  # Wrong: leaves the index stale
```

**Why this matters**: A `.tmp` file left behind means the rename failed — the `.tmp` file may contain a valid newer index. Skipping the update leaves the index pointing to files that were already archived in Phase 3. The session-start hook then references non-existent files.

**Preferred action**: Treat an existing `.tmp` file as a recovery signal, not a block. Complete the rename so the newer index becomes active, then continue with the update cycle normally.

**Preferred action**:
```python
# If .tmp exists, complete the rename rather than skipping
import os
tmp = "memory/MEMORY.md.tmp"
final = "memory/MEMORY.md"
if os.path.exists(tmp):
    # Previous cycle interrupted after write but before rename — complete it
    os.rename(tmp, final)
```

---

### Stash Before Branch Switch in GRADUATE

**Detection**:
```bash
# Check if graduate section in dream-prompt.md includes stash before checkout
grep -n 'git checkout.*dream/graduate' skills/meta/auto-dream/dream-prompt.md
grep -n 'git stash' skills/meta/auto-dream/dream-prompt.md
# Both lines should exist; if stash is missing, the pattern is broken
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```bash
# Switches branch without checking for dirty working tree
git checkout -b "dream/graduate-2026-04-16" main
# Error: Your local changes to the following files would be overwritten by checkout
```

**Why this matters**: Phase 3 CONSOLIDATE writes new memory files. If those writes are not tracked on any git branch (the dream cycle does not commit memory files to git), `git checkout` refuses to switch and GRADUATE fails entirely. All graduation candidates are deferred, and the missed cycle compounds on subsequent runs.

**Preferred action**: Before every branch switch in Phase 5 GRADUATE, check `git status --porcelain`. Stash any uncommitted changes, switch branches, complete all graduation commits, then pop the stash before returning to the original branch.

**Preferred action**: Always check `git status --porcelain` before any branch switch in Phase 5. Stash if non-empty; pop after returning to the original state.

---

### Set busy_timeout on All Learning DB Queries

**Detection**:
```bash
# Find sqlite3 calls without PRAGMA busy_timeout
grep -rn 'sqlite3.*DREAM_LEARNING_DB\|sqlite3.*learning\.db' scripts/ skills/ | grep -v busy_timeout
# Also check Python DB access
grep -rn 'sqlite3.connect' hooks/lib/ | head -20
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```bash
# No timeout — fails immediately on contention
sqlite3 "${DREAM_LEARNING_DB}" "SELECT count(*) FROM sessions;"
# Returns: Error: database is locked
```

**Why this matters**: During active development sessions, the learning hook fires on every tool call and holds brief write locks. A dream SCAN that queries graduation candidates without a timeout fails with `SQLITE_BUSY` if a hook write happens to coincide. The scan aborts Phase 1, which means Phase 5 GRADUATE has no candidates to evaluate — silent data loss.

**Preferred action**: Set `PRAGMA busy_timeout=5000;` before every dream-cycle SQLite query so brief hook-write contention resolves within 5 seconds rather than failing immediately. For Python connections, pass `timeout=5.0` to `sqlite3.connect()`.

**Preferred action**: Add `PRAGMA busy_timeout=5000;` before every dream-cycle query. For Python, pass `timeout=5.0` to `sqlite3.connect()`.

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `[dream] Already running (lockfile held)` in cron log | Previous run still active OR lockfile stale from a crash | Check `ps aux \| grep claude` — if no process, delete `/tmp/auto-dream.lock` manually |
| `MEMORY.md.tmp` left in memory/ after cycle | `mv` rename failed (disk full, permission error) | `mv memory/MEMORY.md.tmp memory/MEMORY.md` after resolving disk/permission issue |
| `Error: database is locked` in Phase 1 SCAN | SQLite busy timeout not set; hook holds write lock | Add `PRAGMA busy_timeout=5000;` before dream-cycle queries |
| `error: Your local changes would be overwritten by checkout` in Phase 5 | Dirty working tree before branch switch | `git stash` before `git checkout`, `git stash pop` after |
| `last-dream.md` is yesterday's date but cron log shows today's run | Phase 7 REPORT was not written (cycle aborted before completion) | Check scan/analysis files in `state/` — if they exist, re-run from Phase 3 with `--execute` |
| Session start shows no memory context despite memories existing | MEMORY.md was partially written (missing entries) | Run `wc -l memory/MEMORY.md` — if smaller than expected, restore from `archive/` and re-run |
| Graduate phase skipped with "No graduation candidates" every cycle | `busy_timeout` missing causing Phase 1 SQLite query to fail silently | Add timeout, then re-run dry-run to verify SCAN actually reads graduation candidates |

---

## Detection Commands Reference

```bash
# Find non-blocking flock usage (should use -n flag)
grep -rn 'flock' scripts/ | grep -v '\-n\b'

# Find direct MEMORY.md writes (missing tmp/rename pattern)
grep -rn 'open.*MEMORY\.md.*w\|write.*MEMORY\.md' scripts/ hooks/ | grep -v '\.tmp'

# Find sqlite3 calls missing busy_timeout
grep -rn 'sqlite3.*learning' scripts/ skills/ | grep -v busy_timeout

# Find git checkout in dream prompt without preceding stash
grep -n 'git checkout\|git stash' skills/meta/auto-dream/dream-prompt.md

# Verify lockfile is not stale (no active dream process)
ls -la /tmp/auto-dream.lock 2>/dev/null && ps aux | grep '[c]laude.*dream'

# Check for leftover .tmp files from interrupted cycles
ls ~/.claude/projects/*/memory/MEMORY.md.tmp 2>/dev/null
ls ~/.claude/state/*.tmp 2>/dev/null
```

---

## See Also

- `skills/meta/auto-dream/references/headless-cron-patterns.md` — full wrapper script pattern including `flock` wiring
- `skills/meta/auto-dream/references/memory-file-operations.md` — atomic MEMORY.md write details
- `skills/meta/auto-dream/dream-prompt.md` — Phase 3 CONSOLIDATE and Phase 5 GRADUATE for git stash context
