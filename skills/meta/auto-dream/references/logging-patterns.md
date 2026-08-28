# Dream Logging Patterns Reference

> **Scope**: Log structure, output interpretation, and rotation patterns for the auto-dream cron process. Covers `cron-logs/auto-dream/`, the `~/.claude/state/` report files, and common failure signatures in log output. Does NOT cover the memory file format or wrapper script invocation.
> **Version range**: All toolkit versions using `scripts/auto-dream-cron.sh` with `tee` dual-logging
> **Generated**: 2026-04-16 — verify log paths against `scripts/auto-dream-cron.sh`

---

## Overview

The dream cycle writes to two places: timestamped per-run logs in `cron-logs/auto-dream/` (raw Claude output via `tee`) and structured state files in `~/.claude/state/` (scan, analysis, report, injection payload). Diagnosing a failed dream run requires reading both: the cron log shows what Claude said; the state files show what it wrote. Silent failures — where the cron log is empty but the cycle shows success — are the most common and most dangerous failure mode.

---

## Log Directory Structure

```
cron-logs/auto-dream/
  run-2026-04-16-020712.log   # timestamped per-run (tee output)
  run-2026-04-15-020708.log
  ...

~/.claude/state/
  dream-scan-2026-04-16.md        # SCAN phase output (all modes)
  dream-analysis-2026-04-16.md    # ANALYZE phase output (all modes)
  last-dream.md                   # REPORT phase — most recent run (overwritten each cycle)
  dream-injection-{hash}.md       # SELECT phase — session-start payload
```

The `run-*.log` files are the raw Claude output stream. The `~/.claude/state/` files are structured artifacts written by the dream prompt itself. Both must exist for a run to be considered successful.

---

## Pattern Table

| Log Scenario | What it means | Where to look |
|-------------|---------------|---------------|
| Log file exists, has content, exit 0 | Normal successful run | Check `last-dream.md` for summary |
| Log file exists, empty, exit 0 | Silent failure — Claude did not emit output | `cron-logs/auto-dream/` + check lockfile |
| Log file exists, has content, exit non-zero | Claude ran but errored | Check log for "error" or "budget exceeded" |
| Log file missing entirely | Cron job did not fire or PATH issue | `crontab -l` + `crontab-manager.py verify` |
| `last-dream.md` is stale (old date) | Cycle did not complete REPORT phase | Check run log for interruption |

---

## Correct Patterns

### Reading the most recent run log

```bash
# Find and tail the most recent per-run log
ls -t cron-logs/auto-dream/run-*.log | head -1 | xargs tail -100

# Or stream it interactively during a manual run
./scripts/auto-dream-cron.sh 2>&1 | tee /tmp/dream-watch.log
tail -f /tmp/dream-watch.log
```

**Why**: The `run-*.log` files are sorted by filename timestamp. The most recent is always `ls -t ... | head -1`. During manual testing, piping to both `/tmp` and the screen lets you read output in real-time without waiting for the full cycle.

---

### Reading the structured dream report

```bash
# The report is always written to the same path (overwritten each cycle)
cat ~/.claude/state/last-dream.md

# Check the date in the report header to confirm it's from today
head -3 ~/.claude/state/last-dream.md

# Count memories processed vs deferred
grep -E 'consolidated|archived|deferred|synthesized' ~/.claude/state/last-dream.md
```

**Why**: `last-dream.md` is overwritten each cycle, not versioned. It's the authoritative summary of what the most recent cycle did. The dated `dream-scan-` and `dream-analysis-` files preserve the per-cycle audit trail but require matching by date.

---

### Detecting a silent failure (empty log)

```bash
# Check the most recent log file size
LAST_LOG=$(ls -t cron-logs/auto-dream/run-*.log | head -1)
LOG_SIZE=$(wc -c < "${LAST_LOG}")
echo "Log size: ${LOG_SIZE} bytes"
[ "${LOG_SIZE}" -lt 100 ] && echo "WARNING: log is suspiciously small — possible silent failure"

# Check the lockfile — is a prior run still holding it?
flock -n /tmp/auto-dream.lock echo "Lock is free" 2>/dev/null || echo "LOCKED — prior run may still be active"

# Verify the exit code was recorded in the log (some wrappers log it)
grep -i 'exit\|budget\|error\|fail' "${LAST_LOG}" | tail -10
```

**Why**: A silent failure occurs when the lockfile blocks the run (exits immediately with code 0), when the Claude session is killed by the OS before emitting output, or when `--max-budget-usd` is hit before SCAN completes. An empty log with exit 0 is always suspicious — budget cap exits non-zero, but lockfile skip exits 0.

---

### Log rotation to prevent unbounded growth

The cron job creates one log file per run. At nightly frequency, this is ~365 files/year. Without rotation, the directory grows indefinitely.

```bash
# Check current log count and disk usage
ls cron-logs/auto-dream/run-*.log | wc -l
du -sh cron-logs/auto-dream/

# Manual cleanup: keep last 30 days of logs
find cron-logs/auto-dream/ -name 'run-*.log' -mtime +30 -delete

# Add to crontab-manager.py as a separate weekly cleanup job, or add to the wrapper:
# At the end of scripts/auto-dream-cron.sh:
find "${LOG_DIR}" -name 'run-*.log' -mtime +30 -delete
```

**Why**: Each log file is typically 5-50KB (one Claude session's output). At 365 files, this is 2-18MB — not critical but untidy. The `find -mtime +30 -delete` pattern keeps the last 30 days, which is sufficient for debugging any recurring issue. Run this as part of the wrapper script after the dream cycle exits.

---

## Pattern Catalog
<!-- no-pair-required: section heading only, paired Do instead blocks appear in each sub-entry below -->

### Cross-Check Cron Log and Report Date

**Detection**:
```bash
# Check if last-dream.md date matches today's cron log
grep '^# Dream Report' ~/.claude/state/last-dream.md
ls -t cron-logs/auto-dream/run-*.log | head -1
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```bash
head -1 ~/.claude/state/last-dream.md
# Dream Report: 2026-04-15   ← yesterday's date, today's cron supposedly ran
```

**Why this matters**: `last-dream.md` is written by the REPORT phase. If today's run was blocked by the lockfile (prior run still active) or crashed before REPORT, the file retains yesterday's content. The file date confirms the *last successful* cycle, not whether *today's* cycle ran.

**Preferred action**: Cross-check the cron log file timestamp against the date in the report header. Both must reflect today for the cycle to be considered confirmed. The cron log exists even when the run is skipped by the lockfile; the report date tells you whether REPORT actually ran.

**Preferred action**:
```bash
# Cross-check the cron log timestamp with the report date
echo "Cron log: $(ls -t cron-logs/auto-dream/run-*.log | head -1)"
echo "Report date: $(head -1 ~/.claude/state/last-dream.md)"
```

---

### Verify All Phase Markers, Not Just Any

**Detection**:
```bash
# Scanning run log for "success" when the report might tell a different story
grep 'success\|complete\|done' "$(ls -t cron-logs/auto-dream/run-*.log | head -1)"
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```bash
# Cron log says "SCAN complete" but CONSOLIDATE crashed halfway through
grep 'complete' run-2026-04-16-020712.log
# → "SCAN complete: 28 files read"
# → "ANALYZE complete: 3 consolidation candidates"
# (CONSOLIDATE then crashed — but grep found "complete" so we thought it worked)
```

**Why this matters**: The dream cycle writes "phase X complete" at the end of each phase. If CONSOLIDATE crashes mid-write, the log contains "ANALYZE complete" but no "CONSOLIDATE complete". Grepping for any "complete" produces a false positive.

**Preferred action**: Check for every phase marker (SCAN, ANALYZE, CONSOLIDATE, SYNTHESIZE, SELECT, REPORT) individually, or rely on `last-dream.md` as the canonical success signal — it is only written when REPORT completes, so its presence confirms all prior phases ran.

**Preferred action**:
```bash
# Check for ALL phase completions, not just any
for phase in SCAN ANALYZE CONSOLIDATE SYNTHESIZE SELECT REPORT; do
  grep -q "${phase}" "${LAST_LOG}" && echo "PASS: ${phase}" || echo "MISSING: ${phase}"
done
# Or simply read last-dream.md which only gets written if REPORT runs
cat ~/.claude/state/last-dream.md | head -20
```

---

### Rotate Logs to Keep Last 30 Days

**Detection**:
```bash
# Log directory growing without bounds
ls cron-logs/auto-dream/run-*.log | wc -l
# > 100 files suggests no rotation policy
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```bash
# Wrapper script creates new log each run but never deletes old ones
RUN_LOG="${LOG_DIR}/run-$(date +%Y-%m-%d-%H%M%S).log"
claude ... | tee "${RUN_LOG}"
# No cleanup step — files accumulate forever
```

**Why this matters**: At nightly frequency, 365 log files/year is manageable, but after a few years the directory becomes hard to navigate and the disk usage is non-trivial. More importantly, missing a rotation policy means the first time you actually need to debug a failure, you have to scroll through hundreds of files to find the relevant one.

**Preferred action**: Add a `find -mtime +30 -delete` rotation step to the end of the wrapper script so each run cleans up logs older than 30 days. The last 30 days is sufficient for debugging any recurring issue and keeps the directory navigable.

**Preferred action**: Add to the end of the wrapper script:
```bash
# Rotate: keep last 30 days of logs
find "${LOG_DIR}" -name 'run-*.log' -mtime +30 -delete
```

---

## Error-Fix Mappings

| Log Symptom | Root Cause | Fix |
|-------------|------------|-----|
| Log file empty, exit 0 | Lockfile skip (prior run active) | `flock -n /tmp/auto-dream.lock echo ok` — if locked, wait or remove stale lock |
| Log file empty, exit non-zero | Claude failed to start (bad PATH, missing claude binary) | `which claude` in cron environment; add PATH to wrapper |
| `last-dream.md` not updated today | REPORT phase did not run (cycle crashed earlier) | Read the dated cron log; look for last phase completion marker |
| Log shows budget cap hit | `--max-budget-usd` reached before cycle completed | Check memory directory size; reduce scope or increase cap |
| `dream-scan-YYYY-MM-DD.md` missing | SCAN phase failed or state dir doesn't exist | Verify `mkdir -p ${DREAM_STATE_DIR}` runs before SCAN |
| Injection payload stale (old hash) | Repo path changed; `DREAM_PROJECT_HASH` changed | Re-run to regenerate; old payload is ignored after hash changes |

---

## Detection Commands Reference

```bash
# Most recent run log
ls -t cron-logs/auto-dream/run-*.log | head -1 | xargs tail -100

# Last dream report
cat ~/.claude/state/last-dream.md

# Check all phase markers in the last run
LAST=$(ls -t cron-logs/auto-dream/run-*.log | head -1)
for p in SCAN ANALYZE CONSOLIDATE SYNTHESIZE SELECT REPORT; do
  grep -q "$p" "$LAST" && echo "OK: $p" || echo "MISSING: $p"
done

# Log directory size and count
ls cron-logs/auto-dream/run-*.log | wc -l && du -sh cron-logs/auto-dream/

# Lockfile state
flock -n /tmp/auto-dream.lock echo "Lock free" 2>/dev/null || echo "LOCKED"

# State files for today
ls ~/.claude/state/dream-*-$(date +%Y-%m-%d).md 2>/dev/null
```

---

## See Also

- `skills/meta/auto-dream/references/headless-cron-patterns.md` — PIPESTATUS capture, tee dual-logging, budget cap
- `skills/meta/auto-dream/references/dream-cycle-testing.md` — test patterns, dry-run validation
- `scripts/auto-dream-cron.sh` — the wrapper script that produces the `run-*.log` files
