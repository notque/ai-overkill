---
summary: "Architecture deep-dive: router internals, hook lifecycle, telemetry database."
read_when:
  - "studying how routing, hooks, and telemetry wire together"
---

# Architecture Deep-Dive

You know Claude Code. You've written agents, maybe built a skill or two. This document covers how this specific toolkit wires everything together: the routing that connects plain-English requests to the right agent and skill, the hook lifecycle that enforces gates for free, the telemetry database that records where every request went and what came back. The point of all this wiring is that a harness with a bare skill list under-routes; this one routes eagerly and correctly. Skip what you know. Dig into what you don't.

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

Key fields. `name` identifies it in routing. `hooks` lets agents register their own PostToolUse handlers. The Go agent reminds you to run `gofmt` after editing `.go` files. `routing.triggers` feeds the evaluator. `routing.retro-topics` names the knowledge topics this agent covers; `scripts/feature-state.py` reads them to match agents to a feature. `memory: project` scopes remembered context to the current project.

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

Every skill phase ends with a gate. A condition that must be true before proceeding. The `/do` skill's gates:

- Phase 1 (CLASSIFY): "Complexity set"
- Phase 2 (ROUTE): "Agent+skill set, banner shown"
- Phase 3 (ENHANCE): "Enhancements applied"
- Phase 4 (EXECUTE): "Agent invoked, results delivered"

Gates prevent the LLM from racing ahead. Without them, Claude will happily "complete" a phase by assuming the script worked without checking exit codes.

## Hook System

Hooks are Python scripts registered in `~/.claude/settings.json` under event type keys. They fire on lifecycle events and can inject context, block tools, or stay silent.

### Event Types

Ten event types, registered in settings.json:

| Event | When | Hooks Registered |
|-------|------|-----------------|
| `SessionStart` | Session begins | sync-to-user-claude, afk-mode, session-context, cross-repo-agents, fish-shell-detector, zsh-shell-detector, sapcc-go-detector, operator-context-detector, session-github-briefing, session-adr-health-check, team-config-loader, rules-distill-injector, hook-version-parity-check, session-manifest-cache |
| `UserPromptSubmit` | Before processing each prompt | pipeline-context-detector, review-false-positive-capture, codex-auto-review, prompt-capture, routing-outcome-finalizer |
| `PreToolUse` | Before tool execution | suggest-compact, pretool-unified-gate, pretool-worktree-edit-guard, pretool-branch-safety, ci-merge-gate, pretool-ruff-format-gate, pretool-private-name-leak-gate, security-review-hook, pretool-synthesis-gate, pretool-plan-gate, pretool-prompt-injection-scanner, pipeline-phase-gate, pretool-adr-creation-gate, pretool-file-backup, reference-loading-enforcer, creation-protocol-enforcer, pretool-section-integrity-validator, pretool-dispatch-spec-gate |
| `PostToolUse` | After tool execution | adr-enforcement, posttool-security-scan, posttool-skill-frontmatter-check, posttooluse-joy-check-warn, posttooluse-sync-skill-index, posttooluse-sync-agent-index, posttool-docs-drift-alert, security-review-hook, adr-lifecycle-on-merge, posttool-rename-sweep, posttool-bash-injection-scan, posttool-session-reads, usage-tracker, review-capture, routing-decision-recorder |
| `PreCompact` | Before context compression | precompact-archive |
| `PostCompact` | After context compression | postcompact-handler |
| `SubagentStart` | When a subagent starts | subagent-start-warmstart |
| `SubagentStop` | When a subagent exits | subagent-completion-guard, routing-outcome-recorder |
| `Stop` | Session ends | session-summary, routing-outcome-stop-fallback, rules-distill-trigger, stop-drift-guard |
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

**routing-decision-recorder** (PostToolUse): Fires on every Agent dispatch and on the Workflow tool. Reads the `[do-route]` marker out of the dispatch prompt and writes one routing-decision row per marker, keyed per marker line so a resubmitted script is a no-op. This is the write side of the routing feedback loop that `learning-db.py route-health` reads.

**routing-outcome-finalizer** (UserPromptSubmit): Resolves each pending dispatch at the one point where the signal exists, the user's next prompt. Scores three ways: failure on a recorded tool error or a clear rejection, success on explicit acceptance, neutral otherwise. Neutral is a no-op, so an unrelated next prompt never moves a route weight. Each pending is drained atomically and scored once.

**session-context** (SessionStart): Reads the pre-built dream payload from `~/.claude/state/dream-injection-{project-hash}.md` and injects it, plus a one-line notice when the nightly cycle ran in the last 24 hours. A pure file read: no database queries, silent when no fresh payload exists.

**pretool-unified-gate** (PreToolUse): Consolidates five blocking checks into one hook. Gitignore-bypass detection, raw git submission blocking (push, PR create/merge), dangerous command guard, creation gate (new agent/skill blocked unless an ADR named for the component is registered via `scripts/adr-query.py register` — the handshake worktree agents perform; `CREATION_GATE_BYPASS` is deprecated and audit-logged), sensitive file guard (.env, credentials, SSH keys). Exits 2 to block when violations are detected. AI attribution blocking was removed from hooks and is now handled declaratively via `settings.json` `attribution` config.

## Telemetry Database

The database is a SQLite file at `~/.claude/learning/learning.db`. WAL mode for concurrent reads across sessions. FTS5 for full-text search. Three subsystems share it: routing telemetry, safety governance, and the voice corpus. `hooks/lib/learning_db_v2.py` is the storage layer all three go through.

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
    source TEXT NOT NULL,           -- hook:routing-decision-recorder, hook:review-capture, hook:prompt-capture
    source_detail TEXT,             -- e.g. "Bash:golang-general-engineer"
    project_path TEXT,
    session_id TEXT,
    observation_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    graduated_to TEXT,              -- unused
    error_signature TEXT,
    error_type TEXT,
    fix_type TEXT,                  -- auto, skill, agent, manual
    fix_action TEXT,                -- create_file, systematic-debugging, use_replace_all, etc.
    UNIQUE(topic, key)
);
```

Additional tables: `telemetry_runs` (append-only per-run envelope: run id, git SHA, model, token count, wall clock, tool errors), `routing_outcome_basis` (per-route counters labelling how each outcome was decided, so route-health can report the silent-success share), `evidence_sessions` / `evidence_events` / `evidence_route_decisions` (the agent evidence read model), `governance_events` (security and policy event log, written through `record_governance_event()` by the branch-safety, config-protection, private-name-leak, worktree-edit, unified, and CI-merge gates), `route_failure_dedup` (idempotency keys for orchestrator-reported route failures), `sessions` and `session_stats` (per-session metrics), `learnings_fts` (FTS5 index), `schema_migrations` (version tracking).

### Who writes what

Two subsystems share the `learnings` table. Each owns a topic and never reads the other's:

| topic | category | Written by | Read by |
|-------|----------|------------|---------|
| `routing` | `effectiveness` | `routing-decision-recorder` inserts, `routing-outcome-finalizer` scores | `learning-db.py route-health`, `route-stats`, `route-weights`, `stack-usage` |
| `voice-sample` | `voice` | `prompt-capture` | no automated reader; the rows accumulate as a corpus for voice-profile work |

Two review paths are wired but near-dormant: `review-capture` writes `review-findings`, and `review-false-positive-capture` plus `learning-db.py record-review-fp` write `review-false-positive`, which `review-fps` reads. As of 2026-08-28 those topics hold 1 and 2 rows. `review-roi` reads review-tier cost from the rightsizing banner, not from this table.

Older rows in other categories are historical. Nothing writes them and nothing reads them.

### The Routing Feedback Loop

1. **Decide**: `/do` picks an agent and skill and stamps a `[do-route]` marker into the dispatch prompt.
2. **Record**: `routing-decision-recorder` reads the marker on `PostToolUse` and writes one decision row plus a pending outcome.
3. **Resolve**: `routing-outcome-finalizer` scores the pending on the user's next prompt. `routing-outcome-recorder` validates each pending at SubagentStop without scoring it, and `routing-outcome-stop-fallback` drains whatever is left when the session ends.
4. **Report**: `learning-db.py route-health` prints the loop's own correctness metrics; `route-stats` and `route-delta` compare cohorts across a change.
5. **Re-rank**: `route-weights` emits the weights as JSON for health-aware re-ranking.

### CLI

```bash
# Loop health: pending vs resolved, outcome basis, silent-success share
python3 scripts/learning-db.py route-health

# Routing decisions aggregated by agent, skill, week, or day
python3 scripts/learning-db.py route-stats --by week

# Did that change help? Compare two git-SHA or date cohorts
python3 scripts/learning-db.py route-delta --from SHA --to SHA

# Enhancement skills seen stacked, with times stacked and last seen
python3 scripts/learning-db.py stack-usage
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

Architectural Decision Records live in `adr/`. Numbered markdown files tracking major design decisions. Why routing telemetry uses SQLite instead of markdown files. Why hooks replace L1/L2 retro files. How the creation gate binds an ADR to a session.

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

### The Negative-Results Registry

The quality feedback loop that keeps the toolkit from rebuilding what already lost:

1. An experiment fails, weakens, or gets reverted.
2. You record it in `docs/what-didnt-work.md` under a dated heading with four fields: expectation, what happened, evidence, decision.
3. Evidence must be a location, a `file:line`, an eval path, a PR number, or a `learning.db` topic and key. A bare claim is not evidence.
4. `scripts/tests/test_negative_results_registry.py` enforces the format and the seed-entry count.
5. The next session greps the registry before re-running an experiment.

Knowledge reaches an agent or skill only by a human editing the file. Nothing writes to a skill on its own.

### Anti-AI Validation

`scripts/scan-ai-patterns.py` checks documentation against 397 banned patterns across 33 categories (pulled from `scripts/data/banned-patterns.json`). Run it as a CI gate or invoke it from a content workflow to catch flagged phrasing before publishing.

Banned words include the usual suspects: "delve", "leverage", "streamline", "foster", "spearheaded". Also structural patterns. The list-of-three. The "In conclusion" wrapper. The "It's important to note" throat-clearing.

## Anti-Rationalization

The toolkit's immune system against LLM self-deception. Claude does not lie on purpose. It constructs plausible-sounding reasons to skip steps. "The code looks correct" (looking is not being correct). "Simple change" (simple changes cause complex bugs). "Should work" (should is not does).

Three layers:

**CLAUDE.md table**: A hardcoded lookup of common rationalizations mapped to required actions. "Already done" -> "Actually verify." "I'm confident" -> "Verify regardless." These are in the global CLAUDE.md that every session reads.

**Re-injection via hooks**: SessionStart hooks reload the operator context and the distilled rule set every session, and `precompact-archive` re-anchors the active ADR before context compression. As conversations get long, early instructions fade from attention. Re-injection at those boundaries brings them back.

**Skill-level embedding**: Every agent and skill embeds anti-rationalization in its operator context. The `verification-before-completion` skill includes an anti-rationalization enforcement reference for maximum-rigor tasks. Gate enforcement in skills is itself an anti-rationalization mechanism. You cannot skip Phase 3 by claiming Phase 2 "probably" passed.

The pattern works because it does not trust the LLM to police itself. Structural enforcement (gates, hooks, exit codes) instead of behavioral instructions alone.
