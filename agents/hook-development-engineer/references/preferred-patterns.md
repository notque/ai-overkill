# Hook Development Preferred Patterns

> Loaded by hook-development-engineer when reviewing hook code for correctness, performance, or registration safety issues.

## Always Exit 0 From Hooks

Wrap the entire `main()` in `try/except/finally` and unconditionally call `sys.exit(0)`. A hook that exits non-zero blocks Claude Code operations. Exit code 2 in particular is interpreted as BLOCK, which deadlocks all tools for the session.

```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        debug_log(f"Fatal error: {e}")
    finally:
        sys.exit(0)  # ALWAYS exit 0 -- no exception reaches the OS
```

The `finally` block guarantees exit 0 even if `debug_log` itself raises. Log errors to a debug file for post-hoc diagnosis -- never let them propagate to an exit code.

**Why this matters**: Python's default exit code for unhandled exceptions is 1 or 2. Code 2 is the same value Claude Code uses for BLOCK. A single unhandled `FileNotFoundError` or `json.JSONDecodeError` in a PreToolUse hook deadlocks ALL tools for the entire session.

**Detection**: `grep -rn 'sys.exit' hooks/ --include="*.py" | grep -v 'sys.exit(0)'` finds non-zero exit calls. Also check: `grep -L 'finally' hooks/*.py` finds hooks without a finally guard.

---

## Stay Under the 50ms Performance Budget

Use lazy loading, early exit on irrelevant events, and streaming parsers. Never load entire databases or run complex regex across all patterns upfront. Check the event type first and return immediately if the hook does not handle it.

```python
# Correct: stream lines and exit early
for line in f:
    pattern = json.loads(line)
    if pattern['id'] == target_id:
        return pattern
        # Stops reading after finding the match -- O(1) best case
```

Parse only what is needed and exit as soon as the relevant data is found. Read files incrementally rather than loading entire contents into memory.

**Why this matters**: Hooks fire on every tool call. A hook that takes 200ms adds 200ms to every Read, Edit, Write, and Bash invocation. At 50+ tool calls per session, that is 10+ seconds of pure overhead.

**Detection**: Add timing instrumentation: `time python3 hooks/my-hook.py < test-input.json`. Anything above 50ms needs optimization.

---

## Use Atomic Writes for Database and State Files

Write to a temporary file first, then atomically rename it to the target path. Direct writes to the database file can corrupt it if the hook is interrupted (e.g., by a timeout or signal).

```python
temp_path = db_path.with_suffix('.tmp')
with open(temp_path, 'w') as f:
    json.dump(data, f)
temp_path.replace(db_path)  # Atomic on POSIX filesystems
```

**Why this matters**: `json.dump(data, open(db_path, 'w'))` truncates the file before writing. If the process is killed between truncation and write completion, the database is permanently lost -- zero bytes, no recovery.

**Detection**: `grep -rn "open.*'w'" hooks/ --include="*.py" | grep -v 'tmp\|temp'` finds direct writes that skip the atomic pattern.

---

## Deploy Hook Files Before Registering in settings.json

Follow strict deployment order: (1) write the hook `.py` file to the repo's `hooks/` directory, (2) copy or sync to `~/.claude/hooks/`, (3) verify it runs with `python3 ~/.claude/hooks/my-hook.py < /dev/null` (must exit 0), (4) only then register in `settings.json`. Use `scripts/register-hook.py` to enforce this order programmatically.

```bash
# Verification command -- must exit 0 before registration
python3 ~/.claude/hooks/my-hook.py < /dev/null
echo $?  # Must print 0
```

**Why this matters**: If a hook is registered in `settings.json` but the file does not exist at `~/.claude/hooks/`, Python raises `FileNotFoundError` with exit code 2. Exit code 2 = BLOCK. Every PreToolUse event triggers the missing file, blocking ALL tools. The session is deadlocked before you can fix it -- you cannot even use Bash to remove the registration.

**Detection**: Compare registered hooks against deployed files: `jq '.hooks' ~/.claude/settings.json` and `ls ~/.claude/hooks/` -- any registered hook without a matching file is a deadlock waiting to happen.

---

## Guard Against All Import and Runtime Errors

The entry-point guard must catch everything, including import errors that fire before `main()` is called. Structure the hook so that a missing dependency or malformed configuration file never produces a non-zero exit.

```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        debug_log(f"Fatal error: {e}")
    finally:
        sys.exit(0)  # ALWAYS exit 0 -- no exception reaches the OS
```

For import-time errors, ensure all non-stdlib imports are inside `main()` or wrapped in their own try/except at module level.

**Why this matters**: An `ImportError` for a missing package, a `FileNotFoundError` for a config file, or a `json.JSONDecodeError` in a module-level constant -- any of these exit with code 1 or 2 before the entry-point guard runs. The hook becomes a session-killer.

**Detection**: `grep -n 'import ' hooks/*.py | grep -v 'sys\|os\|json\|pathlib'` finds non-stdlib imports that should be guarded or moved inside `main()`.

---

## Keep Agent-Scoped Injection Out of UserPromptSubmit Hooks

Use `UserPromptSubmit` hooks only for session-wide, agent-agnostic concerns (error detection, performance logging, global context). Agent-scoped context injection belongs at routing time, inside the skill that the router invokes after selecting the agent.

**Why this matters**: `UserPromptSubmit` fires BEFORE `/do` selects an agent. The hook has no knowledge of which agent will be chosen. Any agent-scoped injection (e.g., "you are the go-engineer agent, apply TDD") is either wrong (targets the wrong agent), a no-op (overwritten by routing), or both. This timing mismatch makes the pattern unreliable by design.

**Detection**: `grep -rn 'agent\|engineer\|specialist' hooks/ --include="*.py" | grep -i 'userprompt\|user_prompt'` finds hooks that may be injecting agent-scoped context at the wrong lifecycle point.

---

## Error Handling Quick Reference

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| All tools blocked, session frozen | Hook exited non-zero or failed to exit | Wrap `main()` in try/except/finally, always `sys.exit(0)` |
| Session noticeably slower | Hook exceeds 50ms budget | Add early exit for irrelevant events, use streaming parsers |
| Learning database empty after crash | Direct file write interrupted | Use write-to-temp-then-rename pattern |
| Session deadlock on startup | Hook registered before file deployed | Deploy file first, verify exit 0, then register |
