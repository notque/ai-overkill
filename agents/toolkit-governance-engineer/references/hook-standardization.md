# Hook Standardization Reference

> **Scope**: Hook event types, settings.json registration format, exit code conventions, output protocols, timeout configuration, and common hook failure modes. Does not cover frontmatter compliance (see frontmatter-compliance.md).
> **Version range**: Claude Code hooks system (all current versions)
> **Generated**: 2026-04-15

---

## Overview

Hooks are shell commands registered in `settings.json` that execute in response to Claude Code lifecycle events. The most common failure modes are: wrong exit code (non-zero blocks Claude unexpectedly), missing `timeout` (hooks that hang stall the session indefinitely), and using `sys.stdin.isatty()` to detect TTY state (always False in hook context — hooks run with piped stdin).

---

## Event Type Reference

| Event | When Fires | `once` Default | Typical Timeout |
|-------|------------|---------------|-----------------|
| `SessionStart` | Session begins | `true` | 1000–5000ms |
| `UserPromptSubmit` | Before prompt is processed | — | 500–2000ms |
| `PreToolUse` | Before a tool executes | — | 500ms |
| `PostToolUse` | After a tool returns | — | 500–2000ms |
| `PreCompact` | Before context compression | `true` | 2000ms |
| `PostCompact` | After context compression | — | 1000ms |
| `TaskCompleted` | After task completion | — | 1000ms |
| `SubagentStop` | After subagent finishes | — | 500ms |
| `StopFailure` | Session ends with error | — | 1000ms |
| `Stop` | Session ends cleanly | — | 2000ms |

---

## settings.json Registration Format

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/my-hook.py\"",
            "description": "One-line description of what the hook does",
            "timeout": 2000,
            "once": true
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/posttool-lint-hint.py\"",
            "description": "Emit lint hints after file edits",
            "timeout": 1000
          }
        ]
      }
    ]
  }
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `type` | yes | `"command"` | Only `"command"` is currently supported |
| `command` | yes | string | Shell command; always quote paths with spaces |
| `description` | yes | string | Shown in session startup output |
| `timeout` | recommended | integer (ms) | Omitting allows hooks to hang indefinitely |
| `once` | no | boolean | `true` = run only once per session (SessionStart default) |

---

## Two-File Architecture (settings.json)

Hook registrations exist in **two** settings.json files. Editing the wrong one is the most common hook registration failure.

| File | Role | Persistence |
|------|------|-------------|
| `.claude/settings.json` (repo) | **Source of truth.** Version-controlled. All hook registrations go here. | Permanent — survives sessions, commits, deploys |
| `~/.claude/settings.json` (user home) | **Runtime copy.** Rebuilt by `sync-to-user-claude.py` at every SessionStart. | Ephemeral — overwritten on next session start |

**Rule:** Register hooks in the repo file only. Edits to `~/.claude/settings.json` are overwritten by the sync hook within seconds of the next session starting.

**Sync mechanism:** `hooks/sync-to-user-claude.py` runs as the first SessionStart hook. It copies `agents/`, `skills/`, `hooks/`, and merges `.claude/settings.json` into `~/.claude/settings.json`. This enables hooks to work from any working directory, not just the toolkit repo.

---

## Correct Patterns

### Always Exit 0

All hooks must exit 0. Non-zero exit codes block Claude from proceeding.

```python
#!/usr/bin/env python3
"""Hook docstring explaining purpose and advisory/blocking intent."""

import sys

def main():
    # ... hook logic ...
    pass

if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Never let exceptions propagate as non-zero exit
    sys.exit(0)  # Explicit exit 0
```

**Why**: Hooks that exit non-zero act as blockers — Claude cannot continue until the user resolves the exit. Advisory hooks (the vast majority) must always exit 0, even on internal error, to avoid stalling the session.

---

### Read Event JSON from stdin

Hooks receive the triggering event as JSON on stdin.

```python
import json
import sys

def read_event() -> dict:
    """Read hook event from stdin. Returns empty dict on parse failure."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}

event = read_event()
tool_name = event.get("tool_name", "")
tool_result = event.get("tool_result", {})
```

**Why**: Hooks that skip stdin reading miss the event context. For `PostToolUse`, the tool name and result are in the event — without reading them, the hook cannot inspect what just happened.

---

### Inject Context via stdout

Hooks inject context into Claude's prompt by printing structured output to stdout.

```python
# Inject a context block (appears as system-reminder in Claude's context)
print(json.dumps({"type": "context", "content": "Important context here"}))

# Print a plain string (simpler, appears as hook output)
print("[hook-name] Action suggested: fix the broken reference")

# Silent hook — print nothing when there's nothing to report
# (preferred: hooks should be silent when they have no signal)
```

**Why**: Hooks that always print output — even when silent — add noise to every interaction. Hooks should only print when they have a signal to communicate.

---

### Timeout Configuration by Event Type

```json
"SessionStart": { "timeout": 5000 }   // Sync operations, file reads: allow up to 5s
"UserPromptSubmit": { "timeout": 500 } // Must be fast — blocks prompt processing
"PreToolUse": { "timeout": 500 }       // Blocks tool execution — keep under 500ms
"PostToolUse": { "timeout": 2000 }     // Can be slower; runs after tool completes
"Stop": { "timeout": 3000 }            // Session ending — can afford more time
```

**Why**: `UserPromptSubmit` and `PreToolUse` hooks are on the critical path — they block user interaction. Slow hooks here cause noticeable latency. `Stop` and `SessionStart` hooks can afford longer timeouts since they don't block active work.

---

## Gate vs Advisory Classification

PreToolUse hooks split into **gates** (can block tool execution) and **advisory** (context injection only). This distinction matters for exit code behavior and testing.

### Gates (8 hooks — block on violation)

| Hook | Matcher | Blocking Mechanism |
|------|---------|-------------------|
| `pretool-unified-gate.py` | Bash\|Write\|Edit | JSON `permissionDecision: deny` (exit 0) |
| `pretool-branch-safety.py` | Bash | JSON `permissionDecision: deny` (exit 0) |
| `ci-merge-gate.py` | Bash | JSON `permissionDecision: deny` (exit 0) — **non-functional**: uses `gh pr checks --json conclusion` but `conclusion` is invalid; use `bucket` |
| `pretool-ruff-format-gate.py` | Bash | JSON `permissionDecision: deny` (exit 0) |
| `pretool-synthesis-gate.py` | Write\|Edit | JSON `permissionDecision: deny` (exit 0) |
| `pretool-plan-gate.py` | Write\|Edit | JSON `permissionDecision: deny` (exit 0) |
| `pretool-adr-creation-gate.py` | Write | JSON `permissionDecision: deny` (exit 0) |
| `pipeline-phase-gate.py` | Write\|Edit | **exit(2)** — inconsistent with other gates; should migrate to JSON `permissionDecision: deny` |

### Advisory (7 hooks — context injection only)

| Hook | Matcher | Purpose |
|------|---------|---------|
| `suggest-compact.py` | (all) | Suggest `/compact` at edit threshold |
| `pretool-learning-injector.py` | Bash\|Edit | Inject known error patterns |
| `pretool-prompt-injection-scanner.py` | Write\|Edit | Warn about prompt injection |
| `pretool-file-backup.py` | Edit | Backup files before modification |
| `reference-loading-enforcer.py` | Agent | Inject reference loading requirements |
| `pretool-subagent-warmstart.py` | Agent | Inject parent session context |
| `creation-protocol-enforcer.py` | Agent | Soft-warn on creation without ADR |

---

## Hook Output Conventions

Hooks use three stdout output patterns. All work, but new hooks should prefer JSON with `additionalContext` for advisory output and JSON with `permissionDecision` for gates.

| Pattern | When to Use | Example |
|---------|-------------|---------|
| JSON `additionalContext` | Advisory context injection — Claude sees it as system context | `{"additionalContext": "[hook-name] Warning: ..."}` |
| JSON `permissionDecision` | Gates that block tool execution | `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` |
| Plain text to stdout | Simple informational output | `print("[hook-name] 3 patterns loaded")` |

**Preferred pattern for new hooks:** Use `hooks/lib/hook_utils.py` helpers:
- `context_output(event, content)` — advisory context injection
- `user_message_output(event, msg)` — critical notifications that must reach the user verbatim
- `empty_output(event)` — silent exit when nothing to report

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### Set Timeout on Every Hook

**Detection**:
```bash
# Find hooks registered without timeout field
python3 -c "
import json
settings = json.load(open('$HOME/.claude/settings.json'))
for event, groups in settings.get('hooks', {}).items():
    for group in groups:
        for hook in group.get('hooks', []):
            if 'timeout' not in hook:
                print(f'NO TIMEOUT: [{event}] {hook.get(\"description\", hook.get(\"command\", \"?\"))}')
"
```

**Signal**:
```json
{
  "type": "command",
  "command": "python3 \"$HOME/.claude/hooks/my-hook.py\"",
  "description": "Does something"
}
```

**Why this matters**: Without `timeout`, a hook that hangs (network call, waiting for input) stalls the session indefinitely. Claude cannot proceed until the hook exits or the user kills it.

**Preferred action:**

Always add `"timeout"` to every hook entry in `settings.json`. Use 1000ms for informational hooks, 500ms for `PreToolUse` and `UserPromptSubmit` hooks, and up to 5000ms for `SessionStart` hooks doing file reads. Run the detection script above to find any hooks currently missing this field.

**Preferred action**: Always set `"timeout"` in milliseconds. Use 1000ms as a safe default for informational hooks; 500ms for `PreToolUse`/`UserPromptSubmit`.

---

### Detect Session Type via Environment Variables

**Detection**:
```bash
grep -rn "stdin.isatty\|stdout.isatty" ~/.claude/hooks/*.py
```

**Signal**: <!-- no-pair-required: sub-block split by code-comment heading; Do instead is inline below -->
```python
# In a hook — WRONG
if sys.stdin.isatty():
    print("Interactive session")
else:
    print("Non-interactive — activating AFK mode")
```

**Why this matters**: Claude Code pipes stdin (the event JSON) into hooks and captures stdout (the hook output). Both are always non-TTY in hook context, so `isatty()` always returns False — every session is classified as non-interactive regardless of actual session type.

**Preferred action:**

Detect session type using environment variables: check `SSH_CONNECTION` or `SSH_TTY` for SSH sessions, `TMUX` for tmux sessions, and `TERM_PROGRAM` for terminal type. Replace any `isatty()` call with an environment variable check as shown in the Fix code below.

**Preferred action**: Detect session type via environment variables instead.
```python
import os
is_ssh = bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))
is_tmux = bool(os.environ.get("TMUX"))
is_afk = is_ssh or is_tmux
```

---

### Exit 0 in Advisory Hooks

**Detection**:
```bash
# Find hooks that call sys.exit with non-zero values
grep -rn "sys.exit([^0)]" ~/.claude/hooks/*.py
grep -rn "exit(1\|exit(2\|exit(-" ~/.claude/hooks/*.py
```

**Signal**:
```python
def main():
    if not validate_something():
        print("Validation failed")
        sys.exit(1)  # WRONG for advisory hook
```

**Why this matters**: Exit code 1 signals Claude to block and surface the error to the user. For advisory hooks (lint hints, context injection, learning), this is almost always wrong — the hook should report its finding and exit 0 so Claude can continue.

**Preferred action:**

Wrap all hook logic in a `try/except` block and call `sys.exit(0)` unconditionally at the end. Only use non-zero exit codes in deliberately blocking hooks (e.g., branch safety gates, ADR creation guards) where preventing Claude from proceeding is the intended behavior.

**Preferred action**: Wrap all hook logic in try/except and always exit 0. Only use non-zero exit for deliberately blocking hooks (branch safety gates, ADR creation guards).
```python
try:
    main()
except Exception:
    pass
sys.exit(0)
```

---

### Deploy Hook File Before Registering in settings.json

**Detection**:
```bash
# Check that all registered hook commands reference files that exist
python3 -c "
import json, os, re
settings = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for event, groups in settings.get('hooks', {}).items():
    for group in groups:
        for hook in group.get('hooks', []):
            cmd = hook.get('command', '')
            m = re.search(r'[\"\047]([^\"\047]+\.py)[\"\047]', cmd)
            if m:
                path = os.path.expandvars(m.group(1))
                if not os.path.exists(path):
                    print(f'MISSING: [{event}] {path}')
"
```

**Why this matters**: Registering a hook before deploying the file causes a startup error on every session. The hook runs, finds no file, and exits non-zero — blocking or noising every session until fixed.

**Preferred action:**

Deploy the hook Python file to `~/.claude/hooks/` first, verify it exists with `ls ~/.claude/hooks/my-hook.py`, and only then add its entry to `settings.json`. Use `scripts/register-hook.py` to enforce this ordering mechanically rather than relying on memory.

**Preferred action**: Always deploy the hook file to `~/.claude/hooks/` BEFORE adding its entry to `settings.json`.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Session startup fails or hangs | Hook missing `timeout` and hangs | Add `"timeout": 2000` to the hook config |
| Every session classified as AFK | `sys.stdin.isatty()` check in hook | Replace with `os.environ.get("SSH_CONNECTION")` check |
| Hook blocks Claude from proceeding | Advisory hook exits non-zero | Wrap in try/except, call `sys.exit(0)` unconditionally |
| Hook registered but errors on startup | Hook file not deployed to `~/.claude/hooks/` | Deploy file first, then register in settings.json |
| Hook runs multiple times per session | Missing `"once": true` on SessionStart hook | Add `"once": true` for one-time session initialization hooks |
| Hook output appears as noise every turn | Hook prints even when no signal | Add early-return guard: only print when there's something to report |
| Hook registration disappears after restart | Registered in `~/.claude/settings.json` (runtime copy) | Register in `.claude/settings.json` (repo) — see Two-File Architecture above |
| Hook depends on nonexistent file | Script imports or shells to a file that was removed/never created | Verify all dependencies exist before registering; known case: `agent-grade-on-change.py` depends on `evals/harness.py` which does not exist |
| Gate uses wrong `gh` API field | `gh pr checks --json conclusion` — `conclusion` is not a valid field | Use `bucket` field instead of `conclusion`; known case: `ci-merge-gate.py` |
| Duplicate detection across hooks | Multiple hooks scan for the same vulnerability class | `posttool-security-scan.py` and `sql-injection-detector.py` both detect SQL injection; consolidate or scope non-overlapping |
| Gate uses exit(2) instead of JSON deny | Inconsistent blocking mechanism across gate hooks | Migrate to `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` pattern; known case: `pipeline-phase-gate.py` |
| error-learner captures non-error output | Hook stdout parsed as "error" by error-learner | Ensure non-error hooks output structured JSON (not plain text that matches error patterns), or scope error-learner's detection |

## Hook Health Status (as of 2026-05-15)

**58/60 registered hooks functional.** 2 non-functional:

| Hook | Event | Issue | Status |
|------|-------|-------|--------|
| `ci-merge-gate.py` | PreToolUse (Bash) | Uses `gh pr checks --json conclusion` — `conclusion` is not a valid field name; should use `bucket` | Fix pending |
| `agent-grade-on-change.py` | PostToolUse (Write\|Edit) | Depends on `evals/harness.py` which does not exist in the repo | Fix pending |

### Registered Hook Inventory by Event

| Event | Count | Gate | Advisory | Notes |
|-------|-------|------|----------|-------|
| SessionStart | 9 | 0 | 9 | sync, context loading, environment detection |
| UserPromptSubmit | 4 | 0 | 4 | pipeline detection, correction capture, prompt capture |
| PreToolUse | 15 | 8 | 7 | branch safety, format gates, plan gates, context injection |
| PostToolUse | 22 | 0 | 22 | lint, security scan, learning, analytics, testing |
| PreCompact | 1 | 0 | 1 | archive learnings |
| PostCompact | 1 | 0 | 1 | re-inject plan context |
| TaskCompleted | 1 | 0 | 1 | completion metadata |
| SubagentStop | 1 | 0 | 1 | branch safety enforcement |
| StopFailure | 1 | 0 | 1 | failure recording |
| Stop | 5 | 0 | 5 | summary, decay, learning, graduation |
| **Total** | **60** | **8** | **52** | |

18 additional hook files exist in `hooks/` but are not registered in settings.json (retired, superseded by unified-gate, or feature-flagged).

---

## Detection Commands Reference

```bash
# List all registered hooks with their events and descriptions
python3 -c "
import json, os
settings = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for event, groups in settings.get('hooks', {}).items():
    for group in groups:
        for hook in group.get('hooks', []):
            timeout = hook.get('timeout', 'MISSING')
            once = hook.get('once', False)
            desc = hook.get('description', '?')
            print(f'[{event}] timeout={timeout} once={once} — {desc}')
"

# Find hooks with missing timeout
python3 -c "
import json, os
s = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for ev, groups in s.get('hooks', {}).items():
    for g in groups:
        for h in g.get('hooks', []):
            if 'timeout' not in h: print(f'NO TIMEOUT [{ev}]: {h.get(\"description\",\"?\")}')
"

# Find hook files with sys.exit non-zero
grep -rn "sys.exit([^0)]" ~/.claude/hooks/*.py

# Find hook files using isatty (TTY detection anti-pattern) <!-- no-pair-required: detection command label, not an anti-pattern block -->
grep -rn "isatty" ~/.claude/hooks/*.py

# Verify all registered hook files exist on disk
python3 -c "
import json, os, re
s = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for ev, groups in s.get('hooks', {}).items():
    for g in groups:
        for h in g.get('hooks', []):
            m = re.search(r'[\"\047]([^\"\047]+\.py)[\"\047]', h.get('command',''))
            if m:
                p = os.path.expandvars(m.group(1))
                if not os.path.exists(p): print(f'MISSING [{ev}]: {p}')
"
```

---

## See Also

- `frontmatter-compliance.md` — agent/skill YAML field standards
- `routing-table-patterns.md` — routing entry validation
- `skills/meta/do/references/hooks-guide.md` — hook event types overview
- `~/.claude/hooks/` — deployed hook files
