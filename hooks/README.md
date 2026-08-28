# Hooks

Event-driven automations that fire at Claude Code lifecycle boundaries. They enforce safety gates, inject context, record learnings, and automate quality checks — silent by default, only speaking when adding value.

## How Hooks Work

```
User prompt → UserPromptSubmit → Claude picks tool → PreToolUse → Tool runs → PostToolUse → Response → Stop
                                                                                                   ↓
                                                                                              StopFailure (on API error)
Context: PreCompact → compact → PostCompact
Subagent finishes: SubagentStop
Task completes: TaskCompleted
```

- **PreToolUse** hooks run before a tool executes. They can **block** (exit 2) or **warn** (exit 0 with stderr).
- **PostToolUse** hooks run after a tool completes. They observe output but never block.
- **UserPromptSubmit** hooks inject context before Claude processes a prompt.
- **SessionStart** hooks run once when a session begins.
- **Stop** hooks run after each Claude response.
- **StopFailure** hooks fire when a session ends due to an API error.
- **SubagentStop** hooks fire when a spawned subagent finishes.
- **TaskCompleted** hooks fire when a task is marked as completed.
- **PreCompact** hooks run before context compression.
- **PostCompact** hooks run after context compression.

---

## SessionStart Hooks

| Hook | Description |
|------|-------------|
| `afk-mode` | Injects autonomous behavioral posture for unattended sessions (SSH, tmux, or `CLAUDE_AFK_MODE=always`). See [AFK Mode docs](afk-mode/README.md) |
| `cross-repo-agents` | Discovers local `.claude/agents/` in the working directory and injects them for `/do` routing |
| `fish-shell-detector` | Detects Fish shell users and injects the `shell-config` skill |
| `hook-version-parity-check` | Warn-only: compares deployed `~/.claude/hooks/*.py` hook-version headers against the repo checkout; on drift names the hooks and the sync command |
| `session-github-briefing` | Injects GitHub monitoring briefing into session context (opt-in: `CLAUDE_KAIROS_ENABLED=true`) |
| `operator-context-detector` | Detects operator context (personal/work/ci/production) and injects behavioral profile |
| `retro-knowledge-injector` | Stub — previously injected retro knowledge; replaced by auto-dream via `session-context.py` |
| `rules-distill-injector` | Injects pending rules-distillation candidates from `learning/rules-distill-pending.json` |
| `sapcc-go-detector` | Detects SAP Converged Cloud Go projects and injects `go-patterns` skill |
| `session-context` | Loads high-confidence learned patterns (>0.7) from the learning DB and auto-dream payload into context |
| `sync-to-user-claude` | Syncs agents, skills, hooks, commands, and scripts from the repo to `~/.claude/` |
| `team-config-loader` | Discovers `team-config.yaml` from priority-ordered locations and injects team configuration into context |

---

## UserPromptSubmit Hooks

| Hook | Description |
|------|-------------|
| `adr-context-injector` | Stub — previously injected ADR session context; disabled pending redesign |
| `anti-rationalization-injector` | Stub — previously injected anti-rationalization warnings; now handled by `/do` Phase 3 |
| `creation-request-enforcer-userprompt` | Stub — previously detected creation requests; now handled by `/do` Phase 1 |
| `instruction-reminder` | Stub — previously re-injected CLAUDE.md; now handled natively by Claude Code |
| `pipeline-context-detector` | Detects pipeline creation requests and injects an environmental state snapshot |
| `skill-evaluator` | Discovers skills/agents and injects a targeted evaluation protocol |
| `user-correction-capture` | Records user corrections and capability-gap signals to `learning.db` |
| `userprompt-datetime-inject` | Stub — previously injected date/time; now handled natively by Claude Code |

---

## PreToolUse Hooks

### Safety Gates (exit 2 = block)

| Hook | Matcher | Description |
|------|---------|-------------|
| `pretool-unified-gate` | Bash, Write, Edit | Consolidated gate (ADR-068): gitignore bypass, git submission, dangerous commands, creation gate, sensitive file guard |
| `ci-merge-gate` | Bash | Blocks `gh pr merge` when CI checks have not passed |
| `mcp-health-check` | MCP tools | Probes MCP servers before tool calls; blocks (exit 2) if unhealthy and within backoff window. Also records failures in PostToolUse |
| `pretool-adr-creation-gate` | Write | Blocks new agent/skill/pipeline/hook creation when no corresponding ADR exists |
| `pretool-branch-safety` | Bash | Blocks `git commit` when on `main` or `master` branch |
| `pretool-config-protection` | Write, Edit, MultiEdit | Blocks modifications to linter/formatter config files (ESLint, Prettier, Biome, Ruff, golangci-lint, etc.) |
| `pretool-plan-gate` | Write, Edit | Blocks implementation in `agents/`, `skills/` when `task_plan.md` does not exist |
| `pretool-private-name-leak-gate` | Bash | Blocks `git commit`/`git push` and `gh pr` text that names a private component from `~/private-skills`. Name set derived at runtime from LEAF components only (dirs with SKILL.md, agents/*.md stems), minus public-skill and public-tracked-tree homonyms — local-only by design (no private tree = graceful no-op, so CI cannot host it). Block messages redact the matched name. Bypass `PRIVATE_NAME_GATE_BYPASS=1` works as env var or inline command prefix (logged) |
| `pretool-synthesis-gate` | Write, Edit | Blocks feature implementation when ADR consultation synthesis is missing or blocked |

### Advisory Hooks (exit 0 = warn)

| Hook | Matcher | Description |
|------|---------|-------------|
| `creation-protocol-enforcer` | Agent | Soft-warns when an Agent dispatch appears to be a creation request without a recent ADR session |
| `pretool-file-backup` | Edit | Silently copies edited files to `/tmp/.claude-backups/{session_id}/` before each edit |
| `pretool-learning-injector` | Bash, Edit | Injects high-confidence error patterns from `learning.db` before tools run |
| `pretool-prompt-injection-scanner` | Write, Edit | Scans agent context files for LLM-level prompt injection patterns (advisory only) |
| `pretool-subagent-warmstart` | Agent | Enriches subagent prompts with parent session context (files seen, plan status, key decisions) |
| `suggest-compact` | Edit, Write | Suggests `/compact` after a configurable threshold of edit/write tool calls |

---

## PostToolUse Hooks

| Hook | Matcher | Description |
|------|---------|-------------|
| `adr-enforcement` | Write, Edit | Runs ADR compliance check after pipeline component files are written |
| `agent-grade-on-change` | Edit, Write | Automatically grades agent files when they are created or modified |
| `error-learner` | Any | Detects tool errors, learns patterns, and injects fix suggestions via SQLite |
| `posttool-bash-injection-scan` | Bash | Scans files written by Bash commands for LLM-level prompt injection patterns |
| `posttool-lint-hint` | Write, Edit | Suggests available linters after file writes (silent when no linter applies) |
| `posttool-rename-sweep` | Bash | After `git mv`, scans for stale references to the old filename and warns |
| `posttool-security-scan` | Write, Edit | Scans edited code for hardcoded credentials, injection risks, and path traversal |
| `posttool-session-reads` | Read | Tracks files read during the session to `.claude/session-reads.txt` for subagent warmstart |
| `record-activation` | Edit, Write, Bash | Records retro knowledge activation for ROI cohort tracking (batched, silent) |
| `record-waste` | Any (failures) | Estimates token waste on tool failures and records to `learning.db` |
| `retro-graduation-gate` | Bash | Warns after `gh pr create` if ungraduated retro entries exist in the toolkit repo |
| `review-capture` | Agent | Captures severity-tagged review findings from subagent output to `learning.db` |
| `usage-tracker` | Skill, Agent | Tracks Skill and Agent invocations to SQLite for usage analytics |

---

## Stop Hooks

| Hook | Description |
|------|-------------|
| `confidence-decay` | Decays stale learning entries and prunes low-confidence dead entries from `learning.db` |
| `knowledge-graduation-proposer` | Proposes graduation of high-confidence learnings into agent/skill files for human review |
| `rules-distill-trigger` | Auto-triggers rules distillation when last run was >7 days ago |
| `session-learning-recorder` | Warns if a substantive session recorded zero learnings; summarizes captured count |
| `session-summary` | Generates session summary and persists metrics to the unified learning database |

---

## StopFailure Hooks

| Hook | Description |
|------|-------------|
| `stop-failure-handler` | Records session failure metadata to `~/.claude/state/session-failures.jsonl` for pattern analysis |

---

## TaskCompleted Hooks

| Hook | Description |
|------|-------------|
| `task-completed-learner` | Captures subagent/task completion metadata for routing effectiveness tracking |

---

## SubagentStop Hooks

| Hook | Description |
|------|-------------|
| `subagent-completion-guard` | Captures worktree metadata, blocks direct commits to main/master, enforces read-only mode for reviewer agents |

---

## PreCompact Hooks

| Hook | Description |
|------|-------------|
| `precompact-archive` | Extracts and archives key learnings before context compression |

---

## PostCompact Hooks

| Hook | Description |
|------|-------------|
| `postcompact-handler` | Re-injects plan context and ADR session info after context compaction |

---

## Development

Tests live in `hooks/tests/` and cover the major hooks:

```
hooks/tests/
├── test_config_protection.py        test_pretool_subagent_warmstart.py
├── test_cross_repo_agents.py        test_pretool_unified_gate.py
├── test_do_routing.py               test_record_activation.py
├── test_feedback_tracker.py         test_record_waste.py
├── test_fts5_search.py              test_record_activations_safe.py
├── test_integration.py              test_skill_evaluator.py
├── test_learning_system.py          test_sql_injection_detector.py
├── test_mcp_health_check.py         test_stale_pruner.py
├── test_post_tool_lint.py           test_subagent_completion_guard.py
├── test_posttool_rename_sweep.py    test_suggest_compact.py
└── test_posttool_session_reads.py
```

Shared utilities in `hooks/lib/` include `hook_utils.py` (output formatting helpers `context_output()` / `empty_output()`), `stdin_timeout.py` (safe stdin reading), the unified learning database interface (`learning_db_v2.py`), `injection_patterns.py` (shared prompt injection detection patterns), and `usage_db.py` (SQLite-based skill/agent invocation tracking).

### Writing a New Hook

All hooks read JSON from stdin, write JSON to stdout, and must exit 0 (advisory) or 2 (block). Performance target: **sub-50ms**. Use the `hook-development-pipeline` for new hooks with full quality gates.

---

