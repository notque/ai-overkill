# Hooks System

## Event Types

| Event | When Fires | Use Case |
|-------|------------|----------|
| `SessionStart` | Session begins | Load context, sync files |
| `UserPromptSubmit` | Before processing prompt | Inject context, score the pending routing outcome |
| `PreToolUse` | Before tool execution | Gate dangerous ops, warm-start subagents |
| `PostToolUse` | After tool execution | Record routing decisions, lint, security scan |
| `PreCompact` | Before context compression | Archive the session transcript |
| `PostCompact` | After context compression | Re-inject plan context |
| `TaskCompleted` | After task completion | Record completion metadata |
| `SubagentStop` | After subagent finishes | Enforce branch safety, reviewer contracts |
| `StopFailure` | Session ends with error | Record the failure as a routing outcome |
| `Stop` | Session ends | Generate summary, score any unresolved routing outcome |

## Key Hook Features

| Feature | Description |
|---------|-------------|
| `once: true` | Hook runs only once per session |
| `timeout` | Maximum execution time in ms |
| Cascading output | Hooks can inject context into prompts |

## Routing outcome capture

The routing hooks automatically:
1. Record each dispatch as `{agent}:{skill}` at PostToolUse:Agent
2. Mark the outcome pending at SubagentStop
3. Score it on the next user turn: failure on errors or rejection, success on explicit acceptance, neutral otherwise
4. Fall back to a Stop-time score when no user turn follows
