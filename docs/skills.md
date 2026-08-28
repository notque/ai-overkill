---
summary: "Catalog of all skills by category."
read_when:
  - "browsing the skill catalog"
  - "documenting a new skill"
---

# Skills

Skills are workflow methodologies — reusable process guides that tell Claude Code *how* to approach a task. Each skill lives in its own directory with a `SKILL.md` file.

Skills are invoked via `/do [request]` (routed automatically) or directly as `/skill-name`. Skills marked **user-invocable: false** are internal and used by agents or other skills.

---

## Routing & Execution

| Skill | Description |
|-------|-------------|
| `do` | Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work. |
| `quick` | Tracked lightweight execution with composable rigor flags: --trivial, --discuss, --research, --full |
| `workflow` | Structured multi-phase workflows: review, debug, refactor, deploy, create, research, and more |
| `workflow-help` | Interactive guide to workflow system: agents, skills, routing, execution patterns |
| `install` | Verify VexJoy Agent installation, diagnose issues, and guide first-time setup |

---

## Feature Lifecycle

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `feature-lifecycle` | no | Feature lifecycle: design, plan, implement, validate, release. Phase-gated workflow. |

---

## Planning & Task Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `planning` | yes | Planning lifecycle umbrella: spec, pre-plan, plan-files, check, manage, pause, resume intents |
| `decision-helper` | no | Weighted decision scoring for architectural choices |
| `business-ops` | no | Business operations: strategy, technology, growth, support, finance, HR, legal, operations, sales, productivity, product management |
| `plant-seed` | no | Capture forward-looking idea as a seed for future feature design |

---

## Code Implementation

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `test-driven-development` | no | RED-GREEN-REFACTOR cycle with strict phase gates for TDD |
| `socratic-debugging` | no | Question-only debugging: guide users to find root causes themselves |
| `pair-programming` | no | Collaborative coding with enforced micro-steps and user-paced control |
| `subagent-driven-development` | no | Fresh-subagent-per-task execution with two-stage review gates |
| `condition-based-waiting` | no | Polling, retry, and backoff patterns |

---

## Code Review & Quality

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `systematic-code-review` | no | 4-phase code review: UNDERSTAND, VERIFY, ASSESS risks, DOCUMENT findings |
| `parallel-code-review` | no | Parallel 3-reviewer code review: Security, Business-Logic, Architecture |
| `full-repo-review` | yes | Comprehensive 3-wave review of all repo source files, producing a prioritized issue backlog |
| `code-cleanup` | no | Detect stale TODOs, unused imports, and dead code |
| `code-linting` | no | Run Python (ruff) and JavaScript (Biome) linting |
| `comment-quality` | no | Review and fix temporal references in code comments |
| `universal-quality-gate` | no | Multi-language code quality gate with auto-detection and linters |
| `python-quality-gate` | no | Python quality checks: ruff, pytest, mypy, bandit in deterministic order |
| `verification-before-completion` | no | Defense-in-depth verification before declaring any task complete |
| `with-anti-rationalization` | no | _(demoted to verification-before-completion)_ Anti-rationalization enforcement for maximum-rigor task execution |
| `testing-preferred-patterns` | no | Identify and fix testing mistakes: flaky, brittle, over-mocked tests |
| `condense` | yes | Maximize information density: preserve all instructions, remove prose filler. |
| `security-review` | yes | Local security review of git changes: deterministic scan + Security reviewer over the diff. |

---

## Git & PR Workflows

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `pr-workflow` | yes | PR lifecycle umbrella: commit, codex-review, sync, review, fix, status, cleanup, feedback, PR mining, branch-name, ci-check |
| `github-notification-triage` | no | Triage GitHub notifications and report actions needed |

---

## Go Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `go-patterns` | no | Go development patterns: testing, concurrency, errors, review, and conventions |
| `sapcc-audit` | no | Full-repo SAP CC Go compliance audit against review standards |
| `sapcc-review` | no | Gold-standard SAP CC Go code review: 10 parallel domain specialists |
| `codebase-analyzer` | no | _(demoted to codebase-overview)_ Statistical rule discovery from Go codebase patterns |

---

## TypeScript / Frontend

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `typescript-check` | no | TypeScript type checking via tsc --noEmit with actionable error output |
| `vitest-runner` | no | Run Vitest tests and parse results into actionable output |
| `e2e-testing` | no | Playwright-based end-to-end testing workflow |
| `distinctive-frontend-design` | no | Frontend design: aesthetic exploration, text animation, card effects, HTML slides |
| `threejs-builder` | no | Three.js app builder: Design, Build, Animate, Polish in 4 phases |
| `nano-banana-builder` | no | Image generation and post-processing via Gemini Nano Banana APIs |

---

## Testing Infrastructure

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `integration-checker` | no | Verify cross-component wiring and data flow |
| `testing-agents-with-subagents` | no | Test agents via subagents: known inputs, captured outputs, verification |

---

## Perses (Observability)

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `perses` | no | Perses platform operations: dashboards, plugins, deployment, migration, and quality |

---

## Security

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `security-threat-model` | no | Security threat model: scan toolkit for attack surface, supply-chain risks |

---

## Content & Voice

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `voice-writer` | yes | Unified voice content generation pipeline with mandatory validation and joy-check |
| `voice-validator` | no | Critique-and-rewrite loop for voice fidelity validation |
| `create-voice` | no | Create voice profiles from writing samples |
| `publish` | no | Content-publishing umbrella: outline, pre-publish check, SEO, batch-edit, link/image/taxonomy audits, WordPress upload |
| `content-calendar` | no | Content pipeline: editorial calendar, brainstorming, headlines, repurposing, news collection |
| `joy-check` | no | Validate content framing on joy-grievance spectrum |
| `professional-communication` | no | Transform technical communication into structured business formats |
| `video-editing` | no | Video pipeline: editing, image-to-video, transcript extraction |
| `image-gen` | no | AI image generation: Gemini and Nano Banana backends; single/series/batch workflows with prompt-to-disk. |
| `translate` | yes | Document translation: quick/normal/refined modes with chunked parallel subagents and glossary support. |

---

## Social & APIs

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `x-api` | no | Post tweets, build threads, upload media via the X API |
| `bluesky-reader` | no | Read public Bluesky feeds via AT Protocol API |
| `reddit-moderate` | no | Reddit moderation via PRAW: fetch modqueue, classify reports, take actions |

---

## Codebase Analysis & Research

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `codebase-overview` | no | Systematic codebase exploration and architecture mapping |
| `repo-value-analysis` | no | Analyze external repositories for adoptable ideas and patterns |
| `research-pipeline` | yes | Formal 5-phase research pipeline with artifact saving and source quality gates |
| `forensics` | no | Post-mortem diagnostic analysis of failed workflows |
| `data-analysis` | no | Decision-first data analysis with statistical rigor gates |
| `docs-sync-checker` | no | Detect documentation drift against filesystem state |
| `architecture-deepening` | yes | Proactive architecture improvement: find shallow modules, propose deepening opportunities, design conversation. |
| `explanation-traces` | yes | Query and display structured decision traces from routing, agent selection, and skill execution. |
| `multi-persona-critique` | yes | Critique a written proposal or design artifact via 5 philosophical personas in parallel, with consensus synthesis. |
| `fact-check` | no | Verify factual claims against sources before publish. |
| `markdown-converter` | no | Convert PDF, Office, HTML, data, media, ZIP to Markdown. |

---

## Toolkit Meta-Skills

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `adr-consultation` | no | Multi-agent consultation for architecture decisions |
| `retro` | yes | Session retrospective: prints the negative-results registry, reviews what a session changed. |
| `auto-dream` | yes | Background memory consolidation -- overnight cleanup of stale, duplicate, and conflicting memory entries |
| `kairos-lite` | yes | Proactive monitoring -- checks GitHub, CI, and toolkit health, produces briefings |
| `skill-eval` | no | Evaluate skills: trigger testing, A/B benchmarks, structure validation |
| `skill-creator` | no | Create and iteratively improve skills through eval-driven validation |
| `skill-composer` | no | _(demoted to workflow)_ DAG-based multi-skill orchestration with dependency resolution |
| `agent-evaluation` | no | Evaluate agents and skills for quality and standards compliance |
| `agent-comparison` | no | A/B test agent variants for quality and token cost |
| `routing-table-updater` | no | Maintain /do routing tables when skills or agents change |
| `generate-claudemd` | no | Generate project-specific CLAUDE.md from repo analysis |
| `agent-creator` | no | Scaffold vexjoy-agent operator .md files: frontmatter, routing block, operator context, reference loading table, phase/gate workflow. |
| `html-artifact` | no | Generate rich self-contained HTML artifacts instead of markdown. |
| `objective-loop` | no | Loop /do cycles until done-criteria verify or budget stops. |
| `toolkit-evolution` | yes | Closed-loop toolkit self-improvement: discover gaps, diagnose, propose, critique, build, test, evolve. |
| `reference-enrichment` | yes | Analyze agent/skill reference depth and generate missing domain-specific reference files. |

---

## Session Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `read-only-ops` | no | Read-only exploration, inspection, and reporting without modifications |
| `session-handoff` | no | Package session state for the next agent, or rehydrate it at start. |

---

## Infrastructure & DevOps

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `cron-automation` | no | Cron automation: audit and create scheduled jobs with safety |
| `service-health-check` | no | Service health: endpoint validation, CVE source auditing, process monitoring |
| `wordpress-live-validation` | no | Validate published WordPress posts in browser via Playwright |
| `public-web-deploy` | no | Publish a public website safely: DNS, web server, HTTPS, hardening, verify. |
| `shell-process-patterns` | no | Safely start, supervise, and terminate shell processes: background jobs, PID capture, signals, traps, cleanup verification. |
| `shell-config` | no | Shell configuration: Fish and Zsh setup, PATH, completions, plugins |

---

## Kotlin Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `kotlin` | no | Kotlin development: coroutines, Flow, testing with JUnit 5 and Kotest |

---

## PHP Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `php` | no | PHP development: code quality, PSR standards, testing with PHPUnit |

---

## Swift Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `swift` | no | Swift development: concurrency patterns, async/await, actors, testing with XCTest and Swift Testing framework |

---

## Kubernetes

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `kubernetes` | no | Kubernetes operations: debugging, security, RBAC, and infrastructure tooling |

---

## Engineering

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `cli-design` | no | Design a CLI interface: args, flags, help, output, errors, exit codes, config. |
| `enterprise-search` | yes | Enterprise search: relevance tuning, query understanding, index management, search quality, ranking optimization, schema design. |
| `opensearch-detection-engineer` | yes | OpenSearch SIEM detection: SIGMA, query DSL, MITRE ATT&CK mapping, anomaly/correlation rules, alert validation, SOC escalation. |

---

## Business & Operations

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `design` | yes | Design workflows — UX copy, design systems, design critique, accessibility review, design handoff, user research synthesis. |
| `marketing` | yes | Marketing: SEO audits, campaign planning, content strategy, email sequences, competitive analysis, brand review, performance reporting. |

---

## Game Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `game-pipeline` | no | Game lifecycle: scaffold, assets, audio, motion capture, QA, deploy |
| `game-sprite-pipeline` | no | AI sprite generation: portraits, idle loops, animated sheets via Codex/Nano Banana. |
| `phaser-gamedev` | no | Phaser 3 2D game dev: scenes, physics, tilemaps, sprites, polish. |

---

## Worktree Isolation

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `worktree-agent` | no | _(demoted to do references)_ Mandatory rules for agents in git worktree isolation |

---

## Shared / Internal

| Skill | Description |
|-------|-------------|
| `shared-patterns` | Reusable prompt patterns referenced by multiple skills |
