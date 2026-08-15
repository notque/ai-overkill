# Claude Code Learning System - Quick Start Guide

## What is this?

A self-improving hook system that learns from errors across Claude Code sessions and suggests fixes based on accumulated knowledge.

## How it works

1. **You encounter an error** (e.g., "Found 3 matches, use replace_all")
2. **System learns the pattern** (stores in unified learning database with initial confidence 0.55)
3. **You fix it and it works** (automatic feedback: confidence increases by +0.15 to 0.70)
4. **After reaching 0.7 threshold** (typically 1-2 successes from initial 0.55)
5. **System auto-suggests solution** next time you encounter similar error
6. **Automatic feedback continues** (success +0.15, failure -0.10)

## Quick Commands

### View Statistics
```bash
python3 scripts/learning-db.py stats
```

### List All Learnings
```bash
python3 scripts/learning-db.py query --category error
```

### View High-Confidence Patterns (Ready to Use)
```bash
python3 scripts/learning-db.py query --category error --min-confidence 0.7
```

### Run Tests
```bash
cd tests
python3 test_learning_system.py
```

## File Locations

| File | Purpose |
|------|---------|
| `~/.claude/learning/learning.db` | Unified SQLite learning database |
| `~/.claude/learning/learning.db-shm` | SQLite shared memory file |
| `~/.claude/learning/learning.db-wal` | SQLite write-ahead log |
| `~/.claude/learning/pending_feedback.json` | Automatic feedback state (60s expiry) |
| stderr (when `CLAUDE_HOOKS_DEBUG=1`) | Debug output from hooks |

**Note**: The database format is SQLite, not JSON. Use `sqlite3` to query.

## What Gets Learned?

The system automatically learns from these error types:

- **missing_file** - File not found errors
- **permissions** - Permission denied errors
- **multiple_matches** - Edit tool ambiguous matches
- **syntax_error** - Code syntax errors
- **type_error** - Python type errors
- **import_error** - Module import errors
- **timeout** - Timeout errors
- **connection** - Connection refused / network errors
- **memory** - Out of memory errors

## Confidence Levels

| Confidence | Meaning | Action |
|------------|---------|--------|
| 0.0 - 0.3 | Low | Pattern tracked, not applied |
| 0.3 - 0.7 | Developing | Building confidence through feedback |
| 0.7 - 1.0 | High-Confidence | Auto-suggested on errors |

**Confidence Adjustments**:
- Success: +0.15 (capped at 1.0)
- Failure: -0.10 (floored at 0.0)
- Initial: 0.55 (error category default from CATEGORY_DEFAULTS)

## Example Session

```
Session Start:
[learned-context] Loaded 12 high-confidence patterns from previous sessions
[learned-context]   Edit: multiple_matches(3), missing_file(2)
[learned-context] Overall success rate: 84.2%

... work happens ...

Error Occurs:
[learned-solution] Use replace_all or provide unique context
[learned-solution] → Add replace_all=true to Edit parameters

Session End:
[session-summary] Session completed
[session-summary]   Tool uses: 47
[session-summary]   Files modified: 8
[session-summary]   Success rate: 93.6%
[session-summary] Learning database: 45 patterns, 28 high-confidence
```

## Debugging

Enable debug logging via environment variable:

```bash
export CLAUDE_HOOKS_DEBUG=1
```

Then view debug output on stderr during hook execution.

## Database Schema (SQLite)

Each learning entry contains:
- **id**: Auto-incrementing primary key
- **topic**: Category grouping (e.g., error type or domain)
- **key**: Unique identifier within topic (e.g., error signature)
- **value**: Human-readable description and solution
- **category**: Learning type (error, pivot, review, design, debug, gotcha, effectiveness, misroute)
- **confidence**: Reliability score (0.0 - 1.0, category-specific defaults)
- **tags**: Comma-separated tags for search
- **source**: Origin (error-learner, manual, migrated, etc.)
- **observation_count**: Times this pattern was observed
- **success_count**: Times the solution worked
- **failure_count**: Times the solution failed
- **error_signature**: MD5 hash for error pattern matching
- **fix_type**: Type of fix (manual, auto, skill, agent)
- **fix_action**: Specific action/command/skill/agent name
- **graduated_to**: Target when knowledge is embedded into an agent

## Confidence Evolution Example

```
Error: "Found 5 matches of the string to replace"

First encounter: Recorded with confidence = 0.55 (error category default)
Attempt 1: Fix it → Success (+0.15) → confidence = 0.70 ✓ HIGH-CONFIDENCE
Attempt 2: Fix it → Failure (-0.10) → confidence = 0.60
Attempt 3: Fix it → Success (+0.15) → confidence = 0.75 ✓ HIGH-CONFIDENCE

Next error → System auto-suggests: "Use replace_all=true or provide more unique context"
           → Automatic feedback tracks if fix works
```

**Automatic Feedback Loop**:
1. Error occurs, system suggests fix
2. Pending feedback set (`~/.claude/learning/pending_feedback.json`)
3. Next PostToolUse checks: error gone? (success) or persists? (failure)
4. Confidence updated automatically
5. Feedback state cleared

## Reset Database

If you want to start fresh:

```bash
# Backup first
sqlite3 ~/.claude/learning/learning.db .dump > learning_backup.sql

# Delete to start fresh
rm ~/.claude/learning/learning.db
```

## Tips

1. **Let it learn gradually** - New error patterns start at 0.55 confidence
2. **1-2 successes** typically needed to reach 0.7 auto-suggestion threshold
3. **Successes boost more** (+0.15) than failures decay (-0.10) - progressive learning
4. **Global patterns** (NULL project_path) work everywhere
5. **Project patterns** only suggest in relevant directories
6. **Automatic feedback** tracks fix outcomes - no manual intervention needed
7. **60-second window** - feedback must occur within 60s of fix suggestion

## Architecture

```
SessionStart → Load learned patterns
     ↓
PostToolUse → Detect errors, update patterns
     ↓
PreCompact → Archive before context compression
     ↓
Stop → Save session summary and metrics
```

## Performance

- **Target**: Sub-50ms execution per hook
- **Storage**: ~1KB per pattern
- **Database**: Atomic writes, file locking
- **Non-blocking**: Always exits 0, never blocks Claude

## Advanced Usage

### Manual Pattern Creation

Use the CLI:
```bash
python3 scripts/learning-db.py record \
  "multiple_matches" \
  "edit-tool-multiple-matches" \
  "Edit tool fails with 'found N matches' → Use replace_all=True parameter" \
  --category error \
  --confidence 0.9
```

Or use the `/learn` skill:
```
/learn "Edit found multiple matches" → "Use replace_all=true or provide more unique context"
```

### Querying Learnings

```bash
# Query by category
python3 scripts/learning-db.py query --category error --min-confidence 0.7

# Full-text search
python3 scripts/learning-db.py search "multiple matches"

# Get statistics
python3 scripts/learning-db.py stats
```

Or via Python:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "hooks" / "lib"))

from learning_db_v2 import query_learnings, lookup_error_solution, get_stats

# Find solution for specific error
solution = lookup_error_solution("Found 3 matches")
if solution:
    print(f"Solution: {solution['value']}")
    print(f"Confidence: {solution['confidence']}")

# Get all high-confidence error patterns
patterns = query_learnings(category="error", min_confidence=0.7, limit=10)
for p in patterns:
    print(f"{p['topic']}: {p['value']} ({p['confidence']:.2f})")
```

## Troubleshooting

**Q: Hooks not running?**
- Check `.claude/settings.json` has hooks registered
- Verify Python files are executable: `chmod +x *.py`
- Check Claude Code supports hook events

**Q: No patterns being learned?**
- Set `CLAUDE_HOOKS_DEBUG=1` environment variable
- Check stderr output from hook execution
- Verify errors are being detected in tool output

**Q: Database corrupted?**
- SQLite has automatic recovery via write-ahead log
- Manual backup: `sqlite3 ~/.claude/learning/learning.db .dump > backup.sql`
- Restore: `sqlite3 ~/.claude/learning/learning.db < backup.sql`
- Or reset by removing the database file: `rm ~/.claude/learning/learning.db`

**Q: Hooks too slow?**
- Check debug logs for execution times
- Consider reducing pattern count
- Verify database isn't too large (>1MB)

## Next Steps

1. Let it learn from your normal workflow
2. Watch high-confidence patterns appear
3. Enjoy auto-suggestions on future errors!

---

For detailed documentation, see [README.md](README.md)
