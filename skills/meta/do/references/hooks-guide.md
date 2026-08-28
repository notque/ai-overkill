# Hooks System

## Event Types

| Event | When Fires | Use Case |
|-------|------------|----------|
| `SessionStart` | Session begins | Load context, sync files |
| `UserPromptSubmit` | Before processing prompt | Inject context, detect corrections |
| `PreToolUse` | Before tool execution | Gate dangerous ops, inject learnings |
| `PostToolUse` | After tool execution | Learn from errors, lint, security scan |
| `PreCompact` | Before context compression | Archive learnings |
| `PostCompact` | After context compression | Re-inject plan context |
| `TaskCompleted` | After task completion | Record completion metadata |
| `SubagentStop` | After subagent finishes | Enforce branch safety, reviewer contracts |
| `StopFailure` | Session ends with error | Record failure for pattern analysis |
| `Stop` | Session ends | Generate summary, decay stale learnings |

## Key Hook Features

| Feature | Description |
|---------|-------------|
| `once: true` | Hook runs only once per session |
| `timeout` | Maximum execution time in ms |
| Cascading output | Hooks can inject context into prompts |
| Async rewake | Hand LLM-grade work back to the session model from a hook |

## Async Rewake

A hook that needs judgment rather than a pattern match re-wakes the session agent and lets it do the work. `async_rewake(message, summary)` in `hooks/lib/hook_utils.py` writes `{"rewakeSummary": ...}` to stdout, the full context to stderr, and exits 2.

This costs no SDK and no metered API key — the session model already running does the work. `hooks/security-review-hook.py` uses it on `Stop` to hand a working-tree diff back for review.

Reserve it for work a script cannot decide. A hook that re-wakes on every event turns one tool call into a full model turn.

## Error Learning

The error-learner hook automatically:
1. Detects errors in tool results
2. Looks up similar patterns in SQLite database
3. Suggests fixes if confidence ≥ 0.7
4. Adjusts confidence based on outcome
