## Legacy Documentation

The sections below cover the learning system internals, shared library API, and permission patterns in depth.

---

## Available Hooks

| Hook | Event | Purpose |
|------|-------|---------|
| [`sync-to-user-claude.py`](#sync-hook) | SessionStart | Sync repo to ~/.claude (bootstrap) |
| [`error-learner.py`](#error-learning-system) | PostToolUse | Learn from errors, suggest fixes |
| [`instruction-reminder.py`](#instruction-reminder) | UserPromptSubmit | Stub — previously re-injected CLAUDE.md (now handled natively) |
| [`skill-evaluator.py`](#skill-evaluation) | UserPromptSubmit | Inject skill/agent evaluation |
| [`session-context.py`](#session-context) | SessionStart | Load learned patterns |
| [`session-summary.py`](#session-summary) | Stop | Generate session metrics |
| [`precompact-archive.py`](#precompact-archive) | PreCompact | Archive learnings |
| [`posttool-lint-hint.py`](#lint-hints) | PostToolUse | Suggest linting |

---

## Sync Hook

The `sync-to-user-claude.py` hook is responsible for bootstrapping the hooks system. It copies agents, skills, hooks, and commands from the repo to `~/.claude/` for global access.

### Bootstrap Requirement

**Important:** The sync hook must be run from the agents repository directory on first use. This is because:

1. The sync hook command uses `$CLAUDE_PROJECT_DIR/hooks/sync-to-user-claude.py` (repo path)
2. The script copies hooks to `~/.claude/hooks/`
3. After initial sync, other hooks run from `$HOME/.claude/hooks/` (global path)

```bash
# First time setup - run Claude from the agents repo
cd /path/to/agents
claude
# Sync happens automatically on SessionStart

# After that, hooks work from anywhere
cd ~/any-other-project
claude
# Hooks loaded from ~/.claude/hooks/
```

### What Gets Synced

| Source | Destination | Description |
|--------|-------------|-------------|
| `agents/` | `~/.claude/agents/` | Agent definitions |
| `skills/` | `~/.claude/skills/` | Skill methodologies |
| `hooks/` | `~/.claude/hooks/` | Hook scripts |
| `.claude/settings.json` | `~/.claude/settings.json` | Hook registrations (merged) |

### Alternative: Use install.sh

Instead of bootstrapping via Claude, you can run the installer directly:

```bash
cd /path/to/agents
./install.sh --symlink  # For development (changes reflect immediately)
./install.sh --copy     # For stability (manual re-run to update)
```

---

## Error Learning System

The crown jewel. A self-improving system that learns from errors and automatically suggests fixes.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code Session                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  PostToolUse Event                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                error-learner.py                             │
├─────────────────────────────────────────────────────────────┤
│  1. Check pending feedback (automatic!)                     │
│  2. Detect errors in tool result                            │
│  3. Lookup/record patterns in unified learning database      │
│  4. Emit fix instructions if confidence ≥ 0.7               │
│  5. Set pending feedback for next iteration                 │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           Unified Learning Database (SQLite)                │
│           ~/.claude/learning/learning.db                    │
└─────────────────────────────────────────────────────────────┘
```

### Automatic Feedback Loop

The system **automatically** tracks whether fixes work:

1. **Fix Suggested**: Hook emits `[auto-fix]` instruction, sets pending feedback state
2. **Next Tool Use**: Hook checks if error is gone (within 60 seconds)
3. **Confidence Updated**:
   - Success: +0.12 confidence (up to maximum 1.0)
   - Failure: -0.18 confidence (down to minimum 0.0)
4. **Feedback Logged**: `[auto-feedback] ✓` or `[auto-feedback] ✗`

State tracked in `~/.claude/learning/pending_feedback.json`, expires after 60 seconds.
No manual commands needed - it's fully automatic.

### Fix Types

| Type | Action | Example |
|------|--------|---------|
| `auto` | Execute automatically | `install_module`, `use_replace_all`, `retry` |
| `skill` | Invoke skill | `systematic-debugging` |
| `agent` | Spawn agent | `golang-general-engineer` |
| `manual` | Show suggestion | User decides |

### Error Classification

| Type | Patterns |
|------|----------|
| `missing_file` | "no such file", "file not found", "does not exist" |
| `permissions` | "permission denied", "access denied" |
| `syntax_error` | "syntax error", "unexpected token" |
| `type_error` | "type error", "cannot convert" |
| `import_error` | "import error", "no module named" |
| `timeout` | "timeout", "timed out" |
| `connection` | "connection refused", "network error" |
| `multiple_matches` | "multiple matches", "found N matches" |

### Manual Pattern Teaching

Use `/learn` to teach high-quality patterns:

```
/learn "Edit found multiple matches" → "Use replace_all=true or provide more unique context"
```

---

## Instruction Reminder

The `instruction-reminder.py` hook combats context drift in long sessions by periodically re-injecting instruction files.

### How It Works

Every 3 prompts (configurable via `THROTTLE_INTERVAL`), the hook:
1. Discovers all CLAUDE.md, AGENTS.md, and RULES.md files (global + project)
2. Injects their full content into the context
3. Adds agent usage reminders and duplication prevention guards

### Files Discovered

| Location | Priority | Example |
|----------|----------|---------|
| Global | Highest | `~/.claude/CLAUDE.md` |
| Project root | High | `./CLAUDE.md` |
| Subdirectories | Normal | `./subdir/CLAUDE.md` |

Excludes: `.git`, `node_modules`, `vendor`, `.venv`, `dist`, `build`

### Output

When triggered (every 3rd prompt):
```
<instruction-files-reminder>
Re-reading instruction files to combat context drift (prompt 6):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ~/.claude/CLAUDE.md (global)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[file content...]

</instruction-files-reminder>

<agent-usage-reminder>
[Agent routing suggestions]
</agent-usage-reminder>

<duplication-prevention-guard>
[Duplication prevention rules]
</duplication-prevention-guard>
```

### Configuration

Edit the constants at the top of `instruction-reminder.py`:
- `THROTTLE_INTERVAL = 3` - Re-inject every N prompts
- `INSTRUCTION_FILES = ["CLAUDE.md", "AGENTS.md", "RULES.md"]` - Files to discover

### Context Drift Prevention

Long Claude sessions lose early instructions as new content fills the context window. This hook re-injects them on a schedule.

Inspired by the `claude-md-reminder.sh` pattern.

---

## Skill Evaluation

The `skill-evaluator.py` hook injects skill/agent options before substantive prompts.

### Complexity Classification

| Level | Criteria | Phase Injection |
|-------|----------|-----------------|
| Trivial | <10 words + question mark | None |
| Simple | <20 words, 1 signal | UNDERSTAND→EXECUTE→VERIFY |
| Medium | 20-50 words, 1-2 signals | Full 4-phase |
| Complex | >50 words, 2+ signals | Full 4-phase with explicit output |

### Complex Signals

Keywords that indicate complexity:
- `implement`, `create`, `build`
- `refactor`, `review`, `analyze`
- `debug`, `fix`, `add feature`
- `and also`, `then`, `first`, `after that`

### Injection Protocol

For medium/complex prompts:

```
<skill-evaluation-protocol>
BEFORE responding, complete these steps IN ORDER:

**Complexity Classification**: MEDIUM

## Systematic Phases
1. UNDERSTAND: Restate the request
2. PLAN: List steps, identify tools
3. EXECUTE: Perform with progress
4. VERIFY: Confirm criteria met

## Step 1: EVALUATE Available Tools
**Skills to consider:**
- systematic-debugging: 4-phase debugging
- test-driven-development: RED→GREEN→REFACTOR
...

**Agents to consider:**
- golang-general-engineer: Go expertise
- database-engineer: PostgreSQL, Prisma
...

## Step 2: ACTIVATE Relevant Tools
## Step 3: IMPLEMENT with Systematic Phases
</skill-evaluation-protocol>
```

---

## Session Context

The `session-context.py` hook loads relevant patterns at session start.

### Output Example

```
[learned-context] Loaded 12 high-confidence patterns
  Edit: multiple_matches(3), missing_file(2)
  Bash: permissions(4), timeout(3)
  Success rate: 84.2%
```

---

## Session Summary

The `session-summary.py` hook generates metrics when Claude Code stops.

### Output Example

```
[session-summary] Session completed
  Tool uses: 47
    Edit(23), Bash(15), Read(9)
  Files modified: 8
  Errors encountered: 3
    multiple_matches(2), missing_file(1)
  Success rate: 93.6%
  Learning database: 45 patterns, 28 high-confidence
```

---

## Supporting Libraries

### `lib/learning_db_v2.py`

Unified learning database. Replaces both `patterns.db` and retro L2 markdown files:
- **SQLite database** with WAL mode for concurrent access
- FTS5 full-text search with porter stemming
- Error classification (8 types) and MD5 signature generation
- Confidence tracking with category-specific defaults
- Project-aware learnings (global and project-specific)
- Auto-fix metadata (fix_type, fix_action)
- Import/export and legacy patterns.db migration

### `lib/feedback_tracker.py`

Automatic feedback tracking:
- State file (`~/.claude/learning/pending_feedback.json`) for pending feedback
- 60-second expiry - state cleared after timeout
- Automatic success/failure determination:
  - No error after fix = success (+0.12)
  - Same error persists = failure (-0.18)
  - Different error = failure (conservative approach)

### `lib/quality_gate.py`

Quality gate utilities:
- Check functions for code quality
- Used by the universal-quality-gate skill

### `lib/builtin_checks.py`

Built-in quality checks:
- Pre-defined code quality validators
- Used by quality gate skill

### `lib/injection_patterns.py`

Shared prompt injection detection patterns:
- Compiled regex list for LLM-level injection (instruction overrides, role hijacking, prompt extraction, fake message boundaries)
- Invisible Unicode codepoint detection
- Used by `pretool-prompt-injection-scanner` and `posttool-bash-injection-scan`

### `lib/usage_db.py`

Usage database for skill and agent invocation tracking:
- SQLite-based concurrent access
- Records which skills and agents are invoked across sessions
- Used by `usage-tracker`

### `lib/hook_utils.py`

Shared utilities for all hooks (documented in detail [below](#shared-utilities-library)):
- JSON output formatting (`context_output()`, `empty_output()`, `user_message_output()`)
- Cascading fallback patterns
- Environment utilities, file discovery, YAML frontmatter parsing

### `lib/stdin_timeout.py`

Safe stdin reading with timeout:
- Prevents hook deadlocks when the parent process pipe hangs
- Uses `signal.alarm` on Unix
- Returns empty string on timeout for clean hook exit

---

## Design Principles

### 1. Silent by Default

Hooks only output when adding value:
- No errors? Silent.
- Low confidence? Silent.
- Empty session? Silent.
- High confidence fix? Output.

### 2. Non-Blocking

All hooks **always** exit 0:
- Never block user interaction
- Graceful degradation on errors
- Silent failure modes

### 3. Fast Execution

Target: **<50ms** per hook execution:
- Lazy loading
- Efficient patterns
- Pre-compiled regex

### 4. Atomic Operations

SQLite provides ACID guarantees:
1. BEGIN TRANSACTION
2. Execute SQL statements
3. COMMIT (atomic)
4. Automatic journaling for crash recovery
5. 5-second timeout for lock acquisition

---

## File Locations

```
~/.claude/
├── learning/
│   ├── learning.db           # Unified SQLite learning database
│   ├── learning.db-shm       # SQLite shared memory file
│   ├── learning.db-wal       # SQLite write-ahead log
│   └── pending_feedback.json # Automatic feedback state (60s expiry)

hooks/
├── error-learner.py          # PostToolUse: Error learning
├── skill-evaluator.py        # UserPromptSubmit: Skill injection
├── session-context.py        # SessionStart: Load patterns
├── session-summary.py        # Stop: Generate metrics
├── precompact-archive.py     # PreCompact: Archive learnings
├── posttool-lint-hint.py     # PostToolUse: Lint hints
├── lib/
│   ├── learning_db_v2.py     # Unified learning database library
│   ├── feedback_tracker.py   # Automatic feedback tracking
│   ├── quality_gate.py       # Quality gate utilities
│   ├── builtin_checks.py     # Built-in quality checks
│   ├── injection_patterns.py # Shared prompt injection detection patterns
│   ├── usage_db.py           # SQLite-based skill/agent invocation tracking
│   ├── hook_utils.py         # Output formatting, env utilities, file discovery
│   └── stdin_timeout.py      # Safe stdin reading with timeout
└── tests/
    └── test_learning_system.py
```

---

## Inspecting the Database

Use SQLite directly to inspect the learning database:

```bash
sqlite3 ~/.claude/learning/learning.db "SELECT * FROM patterns WHERE confidence >= 0.7"
sqlite3 ~/.claude/learning/learning.db "SELECT error_type, COUNT(*) FROM patterns GROUP BY error_type"
```

---

## Testing

```bash
cd hooks/tests
python3 test_learning_system.py
```

Expected output:
```
✓ Error normalizer tests passed
✓ Error classifier tests passed
✓ Signature generation tests passed
✓ Database operations tests passed
✓ Statistics tests passed
✓ Project filtering tests passed

✅ All tests passed!
```

---

## Shared Utilities Library

The `hooks/lib/hook_utils.py` module provides reusable utilities for all hooks.

### HookOutput Class

Structured hook output with user message support:

```python
from hook_utils import HookOutput, empty_output, context_output, user_message_output

# Empty output (no injection)
empty_output("SessionStart").print_and_exit()

# With additional context (system-only)
context_output("UserPromptSubmit", "<context>Info for Claude</context>").print_and_exit()

# With user message (MUST be displayed verbatim)
user_message_output("SessionStart", "⚠️ **ACTION REQUIRED:** Restart session").print_and_exit()
```

### User Message Contract

When a hook returns a `userMessage` field, Claude **MUST**:
1. Display it **verbatim** in the FIRST response
2. Place it at the **START** of the message
3. **NOT paraphrase, summarize, or modify** it
4. **NOT wait** for "relevant context" to mention it

Use `user_message_output()` for critical notifications that must reach the user.

### Cascading Fallback Pattern

Execute multiple approaches in priority order:

```python
from hook_utils import cascading_fallback, with_fallback

# Single fallback
result = with_fallback(
    try_primary,
    try_fallback,
    error_message="Primary failed"
)

# Multiple fallbacks (cascading pattern)
result = cascading_fallback(
    try_with_yaml,      # Priority 1
    try_with_regex,     # Priority 2
    try_with_basic,     # Priority 3
    default="",         # If all fail
    error_prefix="Parse"
)
```

### Environment Utilities

```python
from hook_utils import get_project_dir, get_session_id, get_state_file

project_dir = get_project_dir()  # Path from CLAUDE_PROJECT_DIR
session_id = get_session_id()    # From CLAUDE_SESSION_ID or PPID
state_file = get_state_file("my-hook")  # /tmp/claude-my-hook-{session}.state
```

### File Discovery

```python
from hook_utils import discover_files, EXCLUDE_DIRS

# Find all CLAUDE.md files, excluding common dirs
files = discover_files(project_dir, "CLAUDE.md")
```

### YAML Frontmatter Parsing

```python
from hook_utils import parse_frontmatter

content = Path("skill/SKILL.md").read_text()
frontmatter = parse_frontmatter(content)  # Uses PyYAML if available, regex fallback
```

---

## Creating New Hooks

Use the `/do` router to create hooks — it dispatches the `hook-development-engineer` agent which handles the full lifecycle:

```
/do create a hook for [your purpose]
```

Describe the event type (PostToolUse, PreToolUse, UserPromptSubmit, SessionStart, Stop, PreCompact), what it should detect or inject, and any constraints. The creator agent handles file creation, `hooks/lib/` integration, settings.json registration, and testing.

**Example prompts:**
- `/do create a PostToolUse hook that detects failed SQL queries and suggests index improvements`
- `/do create a PreToolUse hook that blocks writes to files matching a custom pattern list`

Key constraints for all hooks:
- **50ms performance target** — hooks fire on every tool call
- **JSON in, JSON out** — read from stdin, write to stdout
- **Never block unexpectedly** — exit 0 unless intentionally gating (exit 2 to block PreToolUse)
- **Use `hooks/lib/`** — shared utilities for output formatting, learning database, feedback tracking

---

## Debugging Hooks

Hooks fail silently by default to avoid blocking Claude Code. To see error messages when hooks fail, set the `CLAUDE_HOOKS_DEBUG` environment variable:

```bash
export CLAUDE_HOOKS_DEBUG=1
claude
```

Debug output goes to stderr, so you'll see errors without disrupting normal hook output.

---

## Disabling Hooks

To disable specific hooks, edit `~/.claude/settings.json` and remove the hook entry:

```json
{
  "hooks": {
    "PostToolUse": [
      // Remove or comment out unwanted hooks
      {"type": "command", "command": "python3 hooks/error-learner.py"}
    ]
  }
}
```

To disable all hooks of a specific type, set an empty array:

```json
{
  "hooks": {
    "PostToolUse": [],
    "UserPromptSubmit": []
  }
}
```

To disable hooks entirely, remove the `hooks` key from settings.json.

---

## Wildcard Bash Permissions

Claude Code supports wildcard patterns for Bash tool permissions. This allows more flexible command approval without listing every variant.

### Syntax

| Pattern | Description | Examples |
|---------|-------------|----------|
| `Bash(npm *)` | Any npm command | npm install, npm test, npm run build |
| `Bash(go *)` | Any go command | go build, go test, go mod tidy |
| `Bash(* test)` | Any test command | npm test, go test, pytest |
| `Bash(git * main)` | Git commands on main | git push main, git merge main |

### Usage in settings.json

```json
{
  "permissions": {
    "allow": [
      "Bash(go *)",
      "Bash(npm *)",
      "Bash(make *)",
      "Bash(git status)",
      "Bash(git diff)",
      "Bash(git log *)"
    ]
  }
}
```

### Common Permission Sets

**Go Development:**
```json
["Bash(go *)", "Bash(make *)", "Bash(golangci-lint *)"]
```

**Python Development:**
```json
["Bash(python *)", "Bash(pip *)", "Bash(pytest *)", "Bash(ruff *)"]
```

**Node.js Development:**
```json
["Bash(npm *)", "Bash(node *)", "Bash(npx *)"]
```

### Notes

- Wildcards can appear anywhere in the pattern: prefix (`* install`), suffix (`npm *`), or both
- More specific patterns take precedence over wildcards
- Use sparingly - overly permissive patterns reduce security benefits
