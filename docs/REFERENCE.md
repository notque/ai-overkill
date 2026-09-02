---
summary: "Hand-maintained catalog of every command, skill, and agent."
read_when:
  - "scanning the full command list"
---

# Quick Reference Card

**Everything in one place. Scan in 2 minutes.**

---

## Slash Commands

The primary entry point is `/do`, which routes your request to the appropriate agent and skill.

### Core Entry Point
| Command | Purpose | Example |
|---------|---------|---------|
| `/do` | **Smart router** - figures out what you need | `/do debug this failing test` |

### Other Slash Commands
| Command | Purpose |
|---------|---------|
| `/install` | Verify toolkit installation, diagnose issues, guide setup |
| `/pr-review` | Comprehensive PR review with review-findings capture |
| `/retro` | Session retrospective: negative-results registry, session audit |
| `/reddit-moderate` | Reddit moderation: modqueue, classification, actions |
| `/generate-claudemd` | Generate project-specific CLAUDE.md from repo analysis |
| `/github-notifications` | Triage GitHub notifications: fetch, classify, report |
| `/create-pipeline` | Create a new pipeline from a task description |
| `/system-upgrade` | Systematic upgrade of agents, skills, hooks |
| `/github-profile-rules` | Extract coding conventions from GitHub profiles |

### Available via `/do` Routing
These workflows are activated through `/do` with natural language:

| Want This? | Try This |
|------------|----------|
| Test-driven development | `/do write tests using TDD` |
| Systematic debugging | `/do debug authentication failure` |
| Verification | `/do verify before marking done` |
| Code linting | `/do lint src/` |
| Devil's advocate critique | `/do roast @README.md` |
| Evaluate agent/skill quality | `/do evaluate agents/my-agent.md` |
| Explore without modifying | `/do read-only how does auth work` |
| Multi-step task planning | `/do orchestrate add payment system` |
| Go quality checks | `/do run Go quality gate on this package` |
| Go code review | `/do review this Go code` |
| Check CI status | `/do check CI status` |
| Comment quality | `/do check comment quality` |
| Business communication | `/do make this professional` |

---

## Natural Language Triggers

Just say these phrases. The right skill activates automatically.

### High Reliability (Almost Always Works)
| Say This | Activates |
|----------|-----------|
| "TDD" | test-driven-development |
| "test first" | test-driven-development |
| "red green refactor" | test-driven-development |
| "lint" | code-linting |
| "format code" | code-linting |
| "read only" | read-only-ops |
| "don't modify" | read-only-ops |

### Medium Reliability (Usually Works)
| Say This | Activates |
|----------|-----------|
| "debug" | systematic-debugging |
| "investigate" | systematic-debugging |
| "verify" | verification-before-completion |
| "make sure it works" | verification-before-completion |
| "orchestrate" | workflow |
| "plan this out" | workflow |
| "research then write" | research-pipeline |
| "explore codebase" | codebase-overview |

### Use `/do` Instead (Triggers Unreliable)
| Intent | Use |
|--------|-----|
| Evaluate an agent | `/do evaluate agents/my-agent.md` |
| Check CI status | `/do check CI status` |
| Critique/roast something | `/do roast this design` |

---

## Agents

Request deep expertise: *"Use the [name] agent"*

### Core Engineering
| Agent | Domain |
|-------|--------|
| `golang-general-engineer` | Go 1.26+, debugging, code review, performance (with frontmatter hooks) |
| `python-general-engineer` | Python 3.12+, debugging, code review, performance (with frontmatter hooks) |
| `python-openstack-engineer` | OpenStack: Nova, Neutron, Cinder, Oslo libraries, WSGI middleware |
| `kotlin-general-engineer` | Kotlin: features, coroutines, debugging, code quality, multiplatform |
| `php-general-engineer` | PHP 8.x: features, debugging, code quality, security, modern patterns |
| `swift-general-engineer` | Swift: iOS, macOS, server-side Swift, SwiftUI, concurrency, testing |
| `typescript-frontend-engineer` | TypeScript frontend architecture: type-safe components, state management |
| `typescript-debugging-engineer` | TypeScript debugging: race conditions, async/await issues, type errors |
| `nodejs-api-engineer` | Node.js backends: Express APIs, REST endpoints, middleware |

### Infrastructure & Operations
| Agent | Domain |
|-------|--------|
| `kubernetes-helm-engineer` | Kubernetes and Helm: deployments, troubleshooting, cloud-native infrastructure |
| `opensearch-elasticsearch-engineer` | OpenSearch/Elasticsearch: cluster management, performance tuning |
| `prometheus-grafana-engineer` | Prometheus and Grafana: monitoring, alerting, dashboard design, PromQL |
| `rabbitmq-messaging-engineer` | RabbitMQ: message queue architecture, clustering, HA, routing patterns |
| `ansible-automation-engineer` | Ansible: playbooks, roles, collections, Molecule testing, Vault |

### Frontend & UI
| Agent | Domain |
|-------|--------|
| `react-portfolio-engineer` | React portfolio/gallery sites for creatives: React 18+, Next.js App Router |
| `nextjs-ecommerce-engineer` | Next.js e-commerce: shopping cart, Stripe payments, checkout flows |
| `ui-design-engineer` | UI/UX design: design systems, responsive layouts, accessibility, animations |
| `react-native-engineer` | React Native and Expo: performance, animations, navigation, native UI patterns |

### Game & Animation
| Agent | Domain |
|-------|--------|
| `pixijs-combat-renderer` | PixiJS v8 2D WebGL combat rendering: @pixi/react hybrid canvas, GPU particles |
| `rive-skeletal-animator` | Rive skeletal animation: state machines, character pipelines, combat integration |
| `combat-effects-upgrade` | Zero-dependency combat visual upgrades: CSS particles, Framer Motion, 3D card transforms |

### Quality & Testing
| Agent | Domain |
|-------|--------|
| `testing-automation-engineer` | Testing strategy, E2E setup, Playwright tests, test infrastructure |
| `performance-optimization-engineer` | Web performance: Core Web Vitals, rendering, bundle analysis |
| `database-engineer` | Database design, optimization, query performance, migrations, indexing |
| `data-engineer` | Data pipelines, ETL/ELT, warehouse design, dimensional modeling |
| `reviewer-code` | Code quality: conventions, naming, dead code, performance, types, tests |
| `reviewer-system` | System review: security, concurrency, errors, observability, APIs |
| `reviewer-domain` | Domain-specific: ADR compliance, business logic, SAP CC structural |
| `reviewer-perspectives` | Multi-perspective: newcomer, senior, pedant, contrarian, user advocate |

### Specialized
| Agent | Domain |
|-------|--------|
| `perses-engineer` | Perses observability platform: dashboards, plugins, operator, core |
| `technical-documentation-engineer` | Technical documentation: API docs, architecture, runbooks |
| `technical-journalist-writer` | Technical journalism: explainers, opinion pieces, analysis articles |
| `hook-development-engineer` | Python hook development for Claude Code event-driven system |
| `project-coordinator-engineer` | Multi-agent project coordination: task breakdown, progress tracking |
| `research-coordinator-engineer` | Research coordination: systematic investigation, multi-source analysis |
| `research-subagent-executor` | Research subagent execution: OODA-loop investigation, source evaluation |
| `mcp-local-docs-engineer` | MCP server development for local documentation access |
| `sqlite-peewee-engineer` | SQLite with Peewee ORM: model definition, query optimization |
| `pipeline-orchestrator-engineer` | Pipeline orchestration: scaffold multi-component workflows |
| `system-upgrade-engineer` | Systematic toolkit upgrades: adapt agents, skills, hooks after updates |
| `toolkit-governance-engineer` | Toolkit governance: edit skills, update routing tables, manage ADRs |
| `github-profile-rules-engineer` | Extract coding conventions and style rules from GitHub user profiles |

### Voice Writers
| Agent | Domain |
|-------|--------|
| private `voice-*` profile skills | Pre-calibrated voice profiles, installed from `~/private-skills` when present |

### Reviewer Personas (via `reviewer-perspectives`)
| Persona | Perspective |
|---------|-------------|
| newcomer | Accessibility critique, fresh eyes |
| skeptical-senior | Production readiness, sustainability |
| pedant | Precision, terminology, spec compliance |
| contrarian | Challenge assumptions, alternatives |
| user-advocate | User impact, complexity vs benefit |
| meta-process | System design health, single points of failure |

These personas are loaded on demand as reference files within the `reviewer-perspectives` umbrella agent.

---

## Skills

Loaded automatically or by the exact action contract: `Call the Skill tool with \`skill-name\`.`

### Workflow Automation
| Skill | Purpose |
|-------|---------|
| `test-driven-development` | RED-GREEN-REFACTOR enforcement |
| `verification-before-completion` | Never done without verification |
| `planning` | Planning lifecycle umbrella: spec, pre-plan, plan-files, check, manage, pause, resume |
| `pr-workflow` | Pull request lifecycle umbrella: commit, codex-review, sync, review, fix, status, cleanup, PR mining, branch-name, ci-check |

### Workflows (formerly Pipelines)
| Skill | Purpose |
|-------|---------|
| `workflow` | Structured multi-phase workflows: review, debug, refactor, deploy, create, research, and more. References in `skills/workflow/references/` contain workflow definitions including systematic-debugging, systematic-refactoring, research-to-article, explore-pipeline, pr-pipeline, doc-pipeline, etc. |
| `research-pipeline` | Formal 5-phase research pipeline with artifact saving and source quality gates |

### Code Quality
| Skill | Purpose |
|-------|---------|
| `code-linting` | Python (ruff) + JS (Biome) |
| `go-patterns` | Go testing, concurrency, errors, review, conventions |
| `python-quality-gate` | Python quality checks |
| `universal-quality-gate` | Multi-language quality checking |
| `comment-quality` | Timeless documentation |
| `roast` | Devil's advocate critique via HN personas |

### Voice System
| Skill | Purpose |
|-------|---------|
| `voice-writer` | Unified voice content generation with validation |

### Knowledge Extraction
| Skill | Purpose |
|-------|---------|
| `codebase-overview` | Rapid context building + statistical pattern extraction |

### Domain-Specific
| Skill | Purpose |
|-------|---------|
| `professional-communication` | Tech → Business transformation |
| `read-only-ops` | Exploration without modification |
| `agent-evaluation` | Evaluate agents/skills |
| `condition-based-waiting` | Retry patterns, backoff, polling |

---

## New Claude Code Features (2026)

| Feature | In Frontmatter | Purpose |
|---------|----------------|---------|
| `once: true` | Hook config | Run hook only once per session |
| `user-invocable: false` | Skill | Hide from slash menu |
| `context: fork` | Skill | Run in isolated sub-agent |
| `agent: name` | Skill | Declare executor agent |
| `hooks:` | Agent | Define agent-specific lifecycle hooks |
| YAML tool lists | Skill | Cleaner `allowed-tools` format |

---

## Decision Cheat Sheet

```
What do you need?
│
├─ "Just get it done" ──────────► /do [describe task]
│
├─ Specific workflow ───────────► /do [describe workflow]
│   ├─ TDD ─────────────────────► /do write tests using TDD
│   ├─ Debug ───────────────────► /do debug this failure
│   ├─ Lint ────────────────────► /do lint this project
│   └─ Verify ──────────────────► /do verify this is correct
│
├─ Deep domain expertise ───────► "Use the [X] agent"
│   ├─ Go code ─────────────────► golang-general-engineer
│   ├─ Kubernetes ──────────────► kubernetes-helm-engineer
│   └─ React ───────────────────► react-portfolio-engineer
│
├─ Complex multi-step task ─────► Triggers auto-planning
│   └─ Creates task_plan.md automatically
│
└─ Don't know ──────────────────► Just describe what you want
                                  Claude figures it out
```

---

## File Locations

```
agents/            ← Specialized agents (one .md per agent, optional references/)
skills/            ← Skills (one directory per skill, each with SKILL.md and optional references/)
  └─ workflow/     ← Structured multi-phase workflows (formerly pipelines/)
      └─ references/  ← Workflow definitions loaded on demand
commands/          ← Slash commands (one .md per command)
hooks/             ← Python hooks and utility scripts
  └─ lib/          ← Shared libraries
scripts/           ← Deterministic Python scripts
docs/              ← This documentation
```

---

## Recommended Settings

Environment variables set in `.claude/settings.json` under `"env"`:

| Variable | Recommended Value | Why |
|----------|-------------------|-----|
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | `400000` | Prompt cache TTL is 5 minutes (not 1 hour). Larger conversations miss cache frequently, making each turn reprocess the full context at full cost. Compacting at 400k keeps conversations in the cache-friendly zone. ([anthropics/claude-code#45756](https://github.com/anthropics/claude-code/issues/45756#issuecomment-4231739206)) |
| `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` | `1` | **Deprecated (no-op).** The fixed-budget option no longer exists; this variable has no effect. Safe to leave set — harmless but inactive. |

**Context on `AUTO_COMPACT_WINDOW`:** Anthropic's prompt caching currently uses a 5-minute TTL. When conversations grow large and cache entries expire between turns, each API call re-processes the full conversation at uncached token prices. Even though Claude supports a 1M token context window, using the full window without cache hits is prohibitively expensive. Setting `AUTO_COMPACT_WINDOW=400000` triggers compaction earlier, keeping the active context within a size that cache hits can cover. Anthropic is aware of this issue and exploring improvements. Credit: [@bcherny](https://github.com/bcherny).

### Orchestration (optional)

Keys under `"orchestration"` in `.claude/settings.json` tune how `/do` sizes dispatched work.

| Key | Default | Why |
|-----|---------|-----|
| `orchestration.token_budget` | `500000` | Advisory token budget for a single `/do` task. `/do` Phase 4 prepends "~{remaining} tokens available for this task; prioritize accordingly." to each dispatched agent prompt so agents right-size their own work. A documented signal, not a hard runtime cap — absent the key, the default applies and behavior is unchanged. |

---

## Getting Help

- **Don't know what to use?** → `/do [what you want]`
- **Want to see commands?** → Check this file
- **Building new tools?** → [../CLAUDE.md](../CLAUDE.md)
