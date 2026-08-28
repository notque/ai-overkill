# Concurrency Reference

> **Scope**: Patterns for preventing concurrent dream runs, handling interrupted cycles, and managing atomic file writes. Does NOT cover memory file content or the cron schedule itself.
> **Version range**: All toolkit versions using `flock`-based wrapper scripts
> **Generated**: 2026-04-16 — verify `flock` flags against your OS man page (Linux vs macOS differ)

---

## Overview

The auto-dream cycle modifies shared state: `MEMORY.md`, the memory files it indexes, and `last-dream.md`. Two concurrent dream runs would produce interleaved writes that corrupt the index and leave phase state inconsistent. Two mechanisms protect against this: `flock` prevents concurrent cron invocations, and POSIX atomic rename prevents partial `MEMORY.md` writes. Understanding each layer helps diagnose failures when either breaks down.

---

## Pattern Table

| Problem | Mechanism | Signal that it's broken |
|---------|-----------|------------------------|
| Concurrent cron runs | `flock -n` on lockfile | Two `auto-dream` PIDs visible simultaneously |
| Partial MEMORY.md write | `mv .tmp → .md` atomic rename | `.tmp` file left behind after cycle, index truncated |
| Interrupted cycle | REPORT written before CONSOLIDATE | No `last-dream.md` but scan/analysis files exist |

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

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `[dream] Already running (lockfile held)` in cron log | Previous run still active OR lockfile stale from a crash | Check `ps aux \| grep claude` — if no process, delete `/tmp/auto-dream.lock` manually |
| `MEMORY.md.tmp` left in memory/ after cycle | `mv` rename failed (disk full, permission error) | `mv memory/MEMORY.md.tmp memory/MEMORY.md` after resolving disk/permission issue |
| `last-dream.md` is yesterday's date but cron log shows today's run | Phase 6 REPORT was not written (cycle aborted before completion) | Check scan/analysis files in `state/` — if they exist, re-run from Phase 3 with `--execute` |
| Session start shows no memory context despite memories existing | MEMORY.md was partially written (missing entries) | Run `wc -l memory/MEMORY.md` — if smaller than expected, restore from `archive/` and re-run |

---

## Detection Commands Reference

```bash
# Find non-blocking flock usage (should use -n flag)
grep -rn 'flock' scripts/ | grep -v '\-n\b'

# Find direct MEMORY.md writes (missing tmp/rename pattern)
grep -rn 'open.*MEMORY\.md.*w\|write.*MEMORY\.md' scripts/ hooks/ | grep -v '\.tmp'

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
- `skills/meta/auto-dream/dream-prompt.md` — Phase 3 CONSOLIDATE for the atomic MEMORY.md write sequence
