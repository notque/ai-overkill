# Dream Cycle Testing Reference

> **Scope**: Patterns for safely testing the auto-dream cycle — dry-run validation, output verification, and phase isolation. Does NOT cover production execution or memory file authoring.
> **Version range**: All toolkit versions with `scripts/auto-dream-cron.sh` and the 6-phase dream prompt
> **Generated**: 2026-04-16 — verify script flags against `./scripts/auto-dream-cron.sh --help`

---

## Overview

Testing the dream cycle is high-stakes: a mis-run writes to real memory files and archives active memories. The safe testing model is dry-run first, inspect outputs in `~/.claude/state/`, then run a live cycle against a snapshot copy of your memory directory. Read the dry-run report before running `--execute` against your live memory directory.

---

## Pattern Table

| Test Goal | Command | Safe? |
|-----------|---------|-------|
| Full dry-run (no mutations) | `./scripts/auto-dream-cron.sh` | Yes — default mode |
| Read what would be consolidated | `cat ~/.claude/state/last-dream.md` | Yes |
| Live cycle against a snapshot | `DREAM_MEMORY_DIR=/tmp/test-memory ./scripts/auto-dream-cron.sh --execute` | Yes, safe |
| Live cycle against real memory | `./scripts/auto-dream-cron.sh --execute` | Use with caution |
| Check cron registration | `python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream` | Yes |

---

## Correct Patterns

### Dry-run validation — verifying scan and analysis

The default invocation is always read-only:

```bash
# Run dry-run (no --execute = no filesystem mutations to memory files)
./scripts/auto-dream-cron.sh

# Verify the scan document was written
ls -la ~/.claude/state/dream-scan-*.md | tail -1

# Verify the analysis document was written
ls -la ~/.claude/state/dream-analysis-*.md | tail -1

# Read the consolidated report (written in all modes)
cat ~/.claude/state/last-dream.md
```

**Why**: Dry-run still executes SCAN and ANALYZE phases fully — reading memory files and the git log — but CONSOLIDATE and SYNTHESIZE only describe proposed changes without writing them. The report file (`last-dream.md`) is always written, so you see exactly what a live run would do.

---

### Safe live testing with a memory snapshot

To test CONSOLIDATE and SYNTHESIZE without risk to real memories:

```bash
# 1. Copy your real memory directory to a temp location
SNAP="/tmp/test-dream-memory-$(date +%Y%m%d)"
cp -r ~/.claude/projects/-home-feedgen-vexjoy-agent/memory/ "${SNAP}/"

# 2. Run a live cycle against the snapshot only
DREAM_MEMORY_DIR="${SNAP}" ./scripts/auto-dream-cron.sh --execute

# 3. Inspect what changed in the snapshot
diff -r ~/.claude/projects/-home-feedgen-vexjoy-agent/memory/ "${SNAP}/"

# 4. Read the report (always written to ~/.claude/state/)
cat ~/.claude/state/last-dream.md
```

**Why**: `DREAM_MEMORY_DIR` overrides the default memory path set by the wrapper script via `envsubst`. All CONSOLIDATE and SYNTHESIZE operations happen in the snapshot, leaving real memories untouched. The state directory (`~/.claude/state/`) still receives report files — this is expected and safe.

---

### Verifying output file structure after a run

```bash
DATE=$(date +%Y-%m-%d)
STATE_DIR="${HOME}/.claude/state"

# Scan document (SCAN phase, all modes)
[ -f "${STATE_DIR}/dream-scan-${DATE}.md" ] && echo "PASS: scan doc" || echo "FAIL: scan doc missing"

# Analysis document (ANALYZE phase, all modes)
[ -f "${STATE_DIR}/dream-analysis-${DATE}.md" ] && echo "PASS: analysis doc" || echo "FAIL: analysis doc missing"

# Report (REPORT phase, all modes)
[ -f "${STATE_DIR}/last-dream.md" ] && echo "PASS: report" || echo "FAIL: report missing"

# Injection payload (SELECT phase, all modes — read-only)
HASH=$(echo "/home/feedgen/vexjoy-agent" | md5sum | cut -c1-8)
[ -f "${STATE_DIR}/dream-injection-${HASH}.md" ] && echo "PASS: injection payload" || echo "FAIL: injection payload missing"
```

**Why**: A dry-run that produces no output files means something failed silently. SCAN and ANALYZE always produce their dated documents. A missing `last-dream.md` means REPORT did not complete — check the cron log for the error. A missing injection payload means SELECT failed, and the next session will start without memory context.

---

## Pattern Catalog
<!-- no-pair-required: section heading only, paired Do instead blocks appear in each sub-entry below -->

### Read Dry-Run Report Before Running --execute

**Detection**:
```bash
# Look for --execute runs in cron logs without a preceding dry-run same day
grep -l 'execute' cron-logs/auto-dream/run-*.log | while read f; do
  date=$(basename "$f" | grep -oP '\d{4}-\d{2}-\d{2}')
  grep -l "dry" cron-logs/auto-dream/run-*${date}*.log 2>/dev/null || echo "No dry-run: $f"
done
```

**Signal**:
```bash
./scripts/auto-dream-cron.sh --execute  # What will it consolidate? Unknown.
```

**Why this matters**: The dream cycle can archive active memories if it mis-classifies them as stale. Without reading the dry-run report, you don't know which memories are flagged for archiving until they're already moved. New memory files that haven't appeared in recent sessions yet may have all three staleness signals trip at once.

**Preferred action**: Always run the cron script without `--execute` first and read `~/.claude/state/last-dream.md` to confirm which memories would be consolidated or archived. Only pass `--execute` once the report shows the expected operations.

**Preferred action**:
```bash
./scripts/auto-dream-cron.sh              # Step 1: dry run
cat ~/.claude/state/last-dream.md         # Step 2: read what would happen
./scripts/auto-dream-cron.sh --execute    # Step 3: proceed if report looks correct
```

---

### Verify the memory directory has content before testing

**Detection**:
```bash
ls -la "${DREAM_MEMORY_DIR:-$HOME/.claude/memory}"/MEMORY.md 2>/dev/null || echo "MISSING: MEMORY.md"

# Check whether the last dream report scanned anything
grep -i 'memories scanned\|no-op\|failed' ~/.claude/state/last-dream.md | head -5
```

**Signal**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing failure mode entry -->
```
## Dream Report: 2026-04-16

SCAN: Read 0 memory files.
ANALYZE: Recurring patterns: none (no memory data available)
```

**Why this matters**: When `MEMORY.md` is missing or empty, SCAN reads nothing and the cycle still exits 0. ANALYZE then has no input, so SYNTHESIZE produces no insights and SELECT writes an empty injection payload. An empty-input run looks identical to a healthy no-op run.

**Preferred action**: Confirm the memory directory holds `MEMORY.md` and at least one memory file before running a test cycle. A run against an empty directory tests the wrapper, not the cycle.

```bash
# Verify the memory directory before testing
MEM="${DREAM_MEMORY_DIR:-$HOME/.claude/memory}"
[ -f "$MEM/MEMORY.md" ] || echo "Create MEMORY.md before testing the dream cycle"

# Count memory files available to dream
ls "$MEM"/*.md 2>/dev/null | wc -l
```

---

### Capture PIPESTATUS After Piped Cron Output

**Detection**:
```bash
# In any custom test scripts that pipe auto-dream-cron.sh output:
grep -n '\$?' test*.sh 2>/dev/null | grep -v 'PIPESTATUS'
```

**Signal**:
```bash
./scripts/auto-dream-cron.sh --execute | tee test-output.log
echo "Exit: $?"  # Always 0 — tee's exit code, not claude's
```

**Why this matters**: The wrapper script handles `PIPESTATUS[0]` internally, but a custom test wrapper that pipes the cron script inherits the same problem. `$?` after a pipe reflects the last command (`tee`), not the cron script. A Claude session that errors mid-run silently appears as success.

**Preferred action**: Capture `${PIPESTATUS[0]}` immediately after any pipe from the cron script. Treat any non-zero exit code as a test failure regardless of what the log file contains.

**Preferred action**:
```bash
./scripts/auto-dream-cron.sh --execute 2>&1 | tee test-output.log
CRON_EXIT="${PIPESTATUS[0]}"
echo "Dream exit code: ${CRON_EXIT}"
[ "${CRON_EXIT}" -eq 0 ] && echo "PASS" || echo "FAIL"
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| No scan document after dry-run | SCAN phase failed; check cron log | `ls -t cron-logs/auto-dream/run-*.log \| head -1 \| xargs tail -50` |
| No injection payload file | SELECT phase skipped or DREAM_PROJECT_HASH wrong | Verify `DREAM_PROJECT_HASH`; check state dir path |
| `last-dream.md` unchanged from prior run | Lockfile blocked the run (prior run still active) | `rm /tmp/auto-dream.lock` then retry |
| Dry-run shows 0 memories scanned | `DREAM_MEMORY_DIR` path wrong | Check envsubst output; verify memory dir exists with `ls` |

---

## Detection Commands Reference

```bash
# Check all expected output files exist after a run
ls ~/.claude/state/dream-{scan,analysis}-$(date +%Y-%m-%d).md 2>/dev/null

# Read the last dream report
cat ~/.claude/state/last-dream.md

# Read the most recent cron run log
ls -t cron-logs/auto-dream/run-*.log | head -1 | xargs tail -50

# Verify cron is registered
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```

---

## See Also

- `skills/meta/auto-dream/references/headless-cron-patterns.md` — wrapper script, lockfile, budget cap, dry-run toggle
- `skills/meta/auto-dream/references/memory-file-operations.md` — what CONSOLIDATE and SYNTHESIZE write
- `skills/meta/auto-dream/dream-prompt.md` — the full 7-phase prompt with safety constraints
