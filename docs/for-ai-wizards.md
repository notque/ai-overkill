---
summary: "Architecture deep-dive: router internals, hook lifecycle, learning database."
read_when:
  - "studying how routing, hooks, and learning wire together"
---

# Architecture Deep-Dive

You know Claude Code. You've written agents, maybe built a skill or two. This document covers how this specific toolkit wires everything together: the routing that connects plain-English requests to the right agent and skill, the hook lifecycle that enforces gates for free, the learning database that gets smarter across sessions. The point of all this wiring is that a harness with a bare skill list under-routes; this one routes eagerly and correctly. Skip what you know. Dig into what you don't.

## The Router

Every `/do` request runs through the `/do` skill itself (`skills/meta/do/SKILL.md`). Phase 1 classifies complexity. Phase 2 runs `scripts/pre-route.py` as a deterministic safety net (guards plus a high-confidence force-route fast path), then `scripts/routing-manifest.py` to generate the routing manifest; the orchestrator reads the manifest and selects the agent + skill combination in-session.

A `skill-evaluator` hook exists but is disabled. Its routing cheat sheet became redundant once the `/do` skill got its own routing tables.

### Complexity Classification

The evaluator (in `skill-evaluator.py`'s `classify_complexity` function, also mirrored in the `/do` skill's Phase 1) classifies every prompt into four tiers:

| Tier | Heuristic | What Gets Injected |
|------|-----------|-------------------|
| **Trivial** | <10 words + has `?` | Nothing. No routing. |
| **Simple** | 0 signals AND <=20 words (fallback) | `UNDERSTAND -> EXECUTE -> VERIFY` |
| **Medium** | 1+ signal OR >20 words | `UNDERSTAND -> PLAN -> EXECUTE -> VERIFY` |
| **Complex** | 2+ signals OR >50 words | Full 4-phase with requirements, risks, criteria |

Complex signals: verbs like `implement`, `create`, `build`, `refactor`, `review`, `analyze`, `debug`, `fix`, `add feature`. Multi-step indicators like `and also`, `then`, `first`, `after that`. Word count is a rough proxy for scope.

The `auto-plan-detector` hook was removed. Plan detection lives in the `/do` skill's Phase 1 (CLASSIFY) and Phase 4 Step 1, making per-prompt injection redundant. The `pretool-plan-gate` hook (PreToolUse) enforces the plan requirement by blocking Write/Edit without a `task_plan.md`.

### Agent Selection

Agents are matched by keyword triggers from `routing.triggers` in their frontmatter:

```yaml
routing:
  triggers:
    - go
    - golang
    - ".go files"
    - goroutine
    - gopls
  retro-topics:
    - go-patterns
    - concurrency
```

The `skill-evaluator` maintains a hardcoded `AGENT_ROUTING` dict that maps agent names to one-line descriptions, grouped by domain. Language/Framework Experts, Infrastructure, Data & Docs, UI/Performance, Meta/Creation, Coordination, consolidated Reviewers. In practice this dict is unused since the hook is disabled. Routing now runs through `scripts/index-router.py` and the `/do` skill's routing tables. Claude reads the routing decision, matches the request, dispatches via `Task` tool with `subagent_type`.

### Force-Route Triggers

Some skills must be invoked when their triggers appear. These are mandatory, not suggestions. CLAUDE.md declares them:

- Go test, `_test.go`, table-driven, goroutine, channel, `sync.Mutex`, error handling, `fmt.Errorf`, sapcc, make check -> `go-patterns`

Force-routes override the evaluator's recommendation. If someone says "add a goroutine pool" and the evaluator would have suggested `workflow`, the force-route to `go-patterns` wins.

## Agent Architecture

An agent is a markdown file in `agents/` with YAML frontmatter. Full schema in practice:

```yaml
---
name: golang-general-engineer
version: 3.0.0
description: |
  Use this agent when you need expert assistance with Go development...
color: blue
memory: project
hooks:
  PostToolUse:
    - type: command
      command: |
        python3 -c "
        import sys, json
        data = json.loads(sys.stdin.read())
        # agent-specific hook logic
        "
      timeout: 3000
routing:
  triggers: [go, golang, goroutine, gopls]
  retro-topics: [go-patterns, concurrency]
---
```

Key fields. `name` identifies it in routing. `hooks` lets agents register their own PostToolUse handlers. The Go agent reminds you to run `gofmt` after editing `.go` files. `routing.triggers` feeds the evaluator. `routing.retro-topics` tells the dream system which learning DB topics are relevant when this agent runs (used during nightly auto-dream curation). `memory: project` scopes learned context to the current project.

### The Operator Context Pattern

Every agent body follows the same three-tier structure:

1. **Hardcoded Behaviors** always apply, no exceptions. "Read CLAUDE.md before starting." "Never commit to main."
2. **Default Behaviors** on unless explicitly disabled. "Use conventional commits." "Run tests after changes."
3. **Optional Behaviors** off unless enabled. "Multi-language examples." "Interactive playground."

The pattern gives Claude a clear decision framework. Hardcoded behaviors cannot be argued with. Defaults can be overridden by the user. Optionals need explicit activation. It prevents the rationalization problem where Claude talks itself into skipping steps.

### Reviewer Agents

Reviewer agents: `reviewer-code`, `reviewer-system`, `reviewer-domain`, `reviewer-perspectives`. They get dispatched by the `parallel-code-review` and `roast` skills. Each umbrella agent loads the relevant reference file for its review dimension. They never modify code.

## Skill System

A skill is `skills/{category}/{name}/SKILL.md`. A workflow methodology, not a domain expert. Where agents know *what*, skills know *how*.

```yaml
---
name: workflow
version: 2.0.0
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Write
  - Bash
  - Task
  - Skill
routing:
  triggers: [research then write, article with research]
  pairs_with: [voice-writer]
  complexity: complex
  category: content-pipeline
---
```

`context: fork` means the skill runs in an isolated sub-agent context. It cannot accidentally corrupt the parent's state. `user-invocable: false` hides it from the slash menu; it gets invoked by the router or other skills. `allowed-tools` is a whitelist. If a skill doesn't list `Edit`, it cannot edit files.

### Progressive Disclosure

Skills can have a `references/` directory with supporting files. The main SKILL.md stays focused. Instructions, phases, gates. Heavy reference material (step menus, spec formats, voice profiles) lives in `references/` and gets loaded on demand. This keeps the primary file parseable without bloating context.

### Gate Enforcement

Every skill phase ends with a gate. A condition that must be true before proceeding. The learn skill's gates:

- Phase 1 (PARSE): "Both error_pattern and solution are non-empty strings"
- Phase 2 (CLASSIFY): "fix_type and fix_action are determined"
- Phase 3 (STORE): "Script exits 0 and prints confirmation"
- Phase 4 (CONFIRM): "User sees confirmation"

Gates prevent the LLM from racing ahead. Without them, Claude will happily "complete" Phase 3 by assuming the script worked without checking exit codes.

## Hook System

Hooks are Python scripts registered in `~/.claude/settings.json` under event type keys. They fire on lifecycle events and can inject context, block tools, or stay silent.

### Event Types

Ten event types, registered in settings.json:

| Event | When | Hooks Registered |
|-------|------|-----------------|
| `SessionStart` | Session begins | sync-to-user-claude, afk-mode, session-context, cross-repo-agents, fish-shell-detector, sapcc-go-detector, operator-context-detector, session-github-briefing, session-adr-health-check, hook-version-parity-check |
| `UserPromptSubmit` | Before processing each prompt | pipeline-context-detector, user-correction-capture, codex-auto-review, prompt-capture |
| `PreToolUse` | Before tool execution | suggest-compact, pretool-unified-gate, pretool-branch-safety, ci-merge-gate, pretool-ruff-format-gate, pretool-index-sync-check, pretool-learning-injector, pretool-synthesis-gate, pretool-plan-gate, pretool-prompt-injection-scanner, pipeline-phase-gate, reference-loading-gate, pretool-adr-creation-gate, pretool-file-backup, reference-loading-enforcer, pretool-subagent-warmstart, creation-protocol-enforcer |
| `PostToolUse` | After tool execution | posttool-lint-hint, agent-grade-on-change, adr-enforcement, posttool-security-scan, posttool-skill-frontmatter-check, posttooluse-joy-check-warn, posttooluse-sync-skill-index, posttool-docs-drift-alert, retro-graduation-gate, adr-lifecycle-on-merge, posttool-rename-sweep, record-activation, posttool-session-reads, usage-tracker, review-capture, instruction-compliance, error-learner, record-waste, posttool-auto-test |
| `PreCompact` | Before context compression | precompact-archive |
| `PostCompact` | After context compression | postcompact-handler |
| `TaskCompleted` | After a Task tool finishes | task-completed-learner |
| `SubagentStop` | When a subagent exits | subagent-completion-guard |
| `Stop` | Session ends | session-summary, confidence-decay, session-learning-recorder, knowledge-graduation-proposer, rules-distill-trigger |
| `StopFailure` | Session ends abnormally | stop-failure-handler |

### Execution Model

Every hook receives JSON on stdin, emits JSON on stdout. The contract:

**Input** (varies by event):
```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_result": {"output": "..."},
  "cwd": "/path/to/project"
}
```

**Output** (via `hook_utils.py`):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "injected text for Claude's system prompt",
    "userMessage": "text that MUST be shown to the user verbatim"
  }
}
```

**Exit codes**: `0` = pass (always for non-blocking hooks). `2` = block the tool (PreToolUse only). Several PreToolUse hooks use exit 2: `pretool-unified-gate` blocks gitignore bypass, raw git push/merge, dangerous commands, and sensitive file writes; `pretool-branch-safety` blocks git commits on main/master; `ci-merge-gate` blocks merges when CI checks are red. AI attribution is handled via `settings.json` `attribution` config (empty strings suppress all AI watermarks).

All hooks target sub-50ms execution. `once: true` in settings means the hook fires only on the first event of that type per session. Every hook wraps its main logic in try/except and exits 0 in `finally`. A crashed hook must never block Claude.

### Key Hooks

**error-learner** (PostToolUse): Detects errors in tool output by scanning for indicators like "permission denied", "not found", "traceback". Classifies the error type, generates a signature, checks learning.db for known solutions. If found, emits `[auto-fix]`, `[fix-with-skill]`, or `[fix-with-agent]` directives. Sets pending feedback so the next PostToolUse can check whether the fix worked. Automatic reinforcement learning without human intervention.

**session-context** (SessionStart): At session start, reads the pre-built dream payload from `~/.claude/state/dream-injection-{project-hash}.md` and injects it as a `<retro-knowledge>` block. The payload was LLM-curated during the nightly auto-dream cycle. Top memories selected by relevance, ~2000 token budget. Also loads high-confidence patterns directly from learning.db as fallback. Win rate: 67% in A/B testing when retro knowledge is relevant.

**pretool-unified-gate** (PreToolUse): Consolidates five blocking checks into one hook. Gitignore-bypass detection, raw git submission blocking (push, PR create/merge), dangerous command guard, creation gate (new agent/skill blocked unless an ADR named for the component is registered via `scripts/adr-query.py register` — the handshake worktree agents perform; `CREATION_GATE_BYPASS` is deprecated and audit-logged), sensitive file guard (.env, credentials, SSH keys). Exits 2 to block when violations are detected. AI attribution blocking was removed from hooks and is now handled declaratively via `settings.json` `attribution` config.

**retro-graduation-gate** (PostToolUse): Fires after `gh pr create`. Checks learning.db for ungraduated high-confidence entries from the current session. Emits an advisory warning. Does not block, but nags you to graduate findings before merging.

## Learning System

The learning database is a SQLite file at `~/.claude/learning/learning.db`. WAL mode for concurrent reads across sessions. FTS5 for full-text search. One table does everything.

### Schema

```sql
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL,        -- error, pivot, review, design, debug, gotcha, effectiveness, misroute (8 categories)
    confidence REAL DEFAULT 0.5,
    tags TEXT,
    source TEXT NOT NULL,           -- hook:error-learner, hook:review-capture, skill:learn
    source_detail TEXT,             -- e.g. "Bash:golang-general-engineer"
    project_path TEXT,
    session_id TEXT,
    observation_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    graduated_to TEXT,              -- NULL until embedded in an agent/skill file
    error_signature TEXT,
    error_type TEXT,
    fix_type TEXT,                  -- auto, skill, agent, manual
    fix_action TEXT,                -- create_file, systematic-debugging, use_replace_all, etc.
    UNIQUE(topic, key)
);
```

Additional tables: sessions (per-session metrics), activations (learning activation tracking), session_stats (per-session ROI cohort data), governance_events (security/policy event log), learnings_fts (FTS5 full-text search index), schema_migrations (version tracking). The `learning_archive` table is created on demand by `scripts/learning-db.py stale-prune`.

### Confidence Scoring

Entries start at category-specific defaults (errors: 0.55, pivots: 0.60, reviews: 0.70, design: 0.65, debug: 0.60, gotchas: 0.70, effectiveness: 0.50, misroutes: 0.80). The error-learner boosts confidence by 0.15 when a fix works, decays by 0.10 when it doesn't. The `confidence-decay` hook runs at session end. Entries untouched for 30+ days decay by 0.05, entries below 0.3 and older than 90 days get pruned.

Manually taught patterns (via `/learn`) enter at 0.9 confidence. The dream system only surfaces entries above 0.5 confidence and excludes graduated entries when building the nightly injection payload.

### The Retro Cycle

1. **Capture**: Hooks record learnings automatically. `error-learner` captures error patterns. `review-capture` captures PR review findings. `task-completed-learner` records effectiveness data. `user-correction-capture` records when you correct Claude.
2. **Accumulate**: Entries gain confidence through repeated observation and successful fixes.
3. **Inject**: `session-context` injects the pre-built dream payload at session start. Falls back to direct learning.db queries for high-confidence patterns.
4. **Graduate**: When an entry is mature (high confidence, multiple observations), the `/retro graduate` command embeds it directly into an agent or skill file. The `graduated_to` column records where it went.
5. **Decay**: Unused knowledge fades. The confidence-decay hook ensures the DB doesn't fill with stale advice.

### The /learn Command

`/learn "Edit tool fails with 'found N matches'" -> "Use replace_all=True"` parses the input, classifies the fix type (auto/skill/agent/manual), and stores it at 0.9 confidence via `scripts/learning-db.py record`. For pre-loading knowledge you already have, not for debugging live issues.

### CLI

```bash
# ROI report: cohort comparison of sessions with/without retro knowledge
python3 scripts/learning-db.py roi [--json]

# Show stale entries (low confidence, old, not graduated)
python3 scripts/learning-db.py stale [--min-age-days 30]

# Archive stale entries
python3 scripts/learning-db.py stale-prune --dry-run
python3 scripts/learning-db.py stale-prune --confirm
```

## Pipeline Architecture

Pipeline skills follow a standard template. Not all use every phase, but the shape is consistent:

```
PHASE 1: GATHER    -> Launch parallel agents for research/analysis
PHASE 2: COMPILE   -> Structure findings into coherent format
PHASE 3: GROUND    -> Establish context (audience, tone, mode)
PHASE 4: GENERATE  -> Load skill/agent, create content
PHASE 5: VALIDATE  -> Run deterministic validation scripts
PHASE 6: REFINE    -> Fix validation errors (max 3 iterations)
PHASE 7: OUTPUT    -> Final content with validation report
```

The `research-to-article` workflow reference (now in `skills/workflow/references/`) uses all seven phases. It launches 5 parallel research agents in GATHER (primary domain, narrative arcs, external context, community reaction, business context), compiles findings with story arc emphasis in COMPILE, selects voice mode in GROUND, generates via voice-writer in GENERATE, validates with `voice-validator.py` in VALIDATE, iterates in REFINE, outputs with a validation report.

`parallel-code-review` uses a compressed version: IDENTIFY SCOPE -> DISPATCH (3 reviewers in parallel) -> AGGREGATE -> VERDICT. The fan-out/fan-in pattern. Dispatch independent subagents, collect results, merge by severity.

Pipeline skills differ from standard skills:
- Almost always set `context: fork` to isolate execution
- List `Task` in `allowed-tools` because they dispatch subagents
- Enforce timeouts per phase (5 minutes default per agent)
- Save artifacts to disk at each phase boundary. Context is ephemeral, files persist.

## ADR System

Architectural Decision Records live in `adr/`. Numbered markdown files tracking major design decisions. Why the learning system uses SQLite instead of markdown files. Why hooks replace L1/L2 retro files. How graduation works.

### The session-adr-health-check Hook

When you start a pipeline session, you create `.adr-session.json` in the project root:

```json
{
  "adr_path": "adr/011-choose-your-adventure-docs.md",
  "adr_hash": "abc123",
  "domain": "documentation"
}
```

The `session-adr-health-check` hook (SessionStart) detects this file and surfaces the active ADR as context at session start. The `adr-enforcement` hook (PostToolUse) then verifies written files comply with the active ADR after every Write/Edit, including:

- Mandatory `adr-query.py context` command before creating components
- Compliance check command after writing files
- ADR integrity verification via hash

Every subagent in a pipeline session knows about the governing ADR, because the active session context propagates from the orchestrator.

### ADR Enforcement

The `adr-enforcement` hook (PostToolUse) verifies that written files comply with the active ADR after every Write/Edit. Advisory, not blocking. But it is in your face about compliance failures.

## MCP Integration

Four MCP servers are configured:

| Server | Purpose | Key Tools |
|--------|---------|-----------|
| **gopls** | Go workspace intelligence | `go_diagnostics`, `go_search`, `go_file_context`, `go_symbol_references`, `go_vulncheck` |
| **Context7** | Library documentation lookup | `resolve-library-id`, `query-docs` |
| **Playwright** | Browser automation | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form` |
| **Chrome DevTools** | Chrome debugging | Network inspection, console access |

The catch: MCP tools are **deferred** in subagent contexts. When a pipeline dispatches a subagent via `Task`, that subagent cannot call `mcp__gopls__go_diagnostics` directly. It has to use `ToolSearch` first to fetch the schema:

```
ToolSearch("gopls")
```

Only after ToolSearch returns the full schema definition can the subagent invoke the tool. Easy to miss. Causes silent failures when subagents try MCP tools without the fetch step.

## Quality Gates

### The Wave Review Pattern

The `roast` skill dispatches 5 parallel reviewer personas. Contrarian, Newcomer, Pragmatic Builder, Skeptical Senior, Pedant. Each reads the same target from a different critical angle. The coordinator validates every claim against actual evidence (file contents, line numbers) and categorizes findings as VALID, PARTIAL, UNFOUNDED, or SUBJECTIVE. Only VALID and PARTIAL findings make the final report.

`parallel-code-review` does something similar with 3 reviewers: Security, Business Logic, Architecture. Each runs in a separate subagent. Findings are aggregated by severity into a BLOCK/FIX/APPROVE verdict.

### The Retro Graduation Cycle

The quality feedback loop that makes the toolkit self-improving:

1. Work happens. Hooks capture learnings.
2. PR gets created. `retro-graduation-gate` fires, warns about ungraduated entries.
3. Before merge, you run `/retro graduate`. The skill queries learning.db for high-confidence entries, proposes where to embed them (which agent or skill file), and waits for confirmation.
4. Approved entries get written into the actual agent/skill markdown. The `graduated_to` column in learning.db records the target file.
5. Next session, those patterns are baked into the agent itself instead of being injected from the DB.

### Anti-AI Validation

`scripts/scan-ai-patterns.py` checks documentation against 397 banned patterns across 33 categories (pulled from `scripts/data/banned-patterns.json`). Run it as a CI gate or invoke it from a content workflow to catch flagged phrasing before publishing.

Banned words include the usual suspects: "delve", "leverage", "streamline", "foster", "spearheaded". Also structural patterns. The list-of-three. The "In conclusion" wrapper. The "It's important to note" throat-clearing.

## Anti-Rationalization

The toolkit's immune system against LLM self-deception. Claude does not lie on purpose. It constructs plausible-sounding reasons to skip steps. "The code looks correct" (looking is not being correct). "Simple change" (simple changes cause complex bugs). "Should work" (should is not does).

Three layers:

**CLAUDE.md table**: A hardcoded lookup of common rationalizations mapped to required actions. "Already done" -> "Actually verify." "I'm confident" -> "Verify regardless." These are in the global CLAUDE.md that every session reads.

**Auto-injection via hooks**: The `instruction-compliance` hook (PostToolUse) flags drift from CLAUDE.md rules after each tool call, and SessionStart hooks reload the operator context every session. As conversations get long, early instructions fade from attention. Posttool reinforcement brings them back.

**Skill-level embedding**: Every agent and skill embeds anti-rationalization in its operator context. The `verification-before-completion` skill includes an anti-rationalization enforcement reference for maximum-rigor tasks. Gate enforcement in skills is itself an anti-rationalization mechanism. You cannot skip Phase 3 by claiming Phase 2 "probably" passed.

The pattern works because it does not trust the LLM to police itself. Structural enforcement (gates, hooks, exit codes) instead of behavioral instructions alone.
