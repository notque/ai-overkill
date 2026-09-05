---
name: do
description: "Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work."
user-invocable: true
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  triggers:
    - "route task"
    - "classify request"
    - "which agent"
    - "delegate to skill"
    - "smart router"
  category: meta-tooling
---

# /do - Smart Router

ROUTER, not worker. Classify → agent+skill → dispatch. All execution goes to agents. Catching yourself reading/writing code or analyzing — pause and route to an agent. Exception: reading to fill the Task Spec is routing work — up to 5 files as excerpts; more → one read-only Explore dispatch whose deliverable is the excerpt list. Main: Classify→Select→Dispatch→Evaluate→Re-route→Report.

Do the whole thing (tests+docs). Product, not plan. Permanent solve over workaround. Search before building; test before shipping. Decompose into agent-sized tasks. The result reads as "that's done," not "that's a start." Partial → follow-up. Inject Simple+. Confidence in handling directly is a signal to route.

Dense-Complete Writing (`build-dispatch.py` injects; `skills/shared-patterns/dense-complete-writing.md`). User: banners+summary. Internal: JSON/reasoning/stacking (Verbose overrides).

Google Developer Documentation Style (`build-dispatch.py` injects; `skills/shared-patterns/google-devdocs-style.md`), alongside Dense-Complete. Precedence: completeness floor (never drop a required point) > Google construction (active voice, second person, context-before-instruction, formatting) > Dense-Complete length.

## Instructions

### Phase Banners

Every phase: `/do > Phase N: PHASE_NAME — description...`
After Phase 2: `===` routing banner. Both required.

---

### Phase 1: CLASSIFY

Read CLAUDE.md first.

| Complexity | Agent | Skill | Direct |
|---|---|---|---|
| Trivial | No | No | ONLY user-named file by path |
| Simple | Yes | Yes | Route |
| Medium | Required | Required | Route |
| Complex | 2+ | 2+ | Route |

Beyond user-named file = Simple+, must route. Uncertain → UP. Depth: `references/progressive-depth.md`. NOT Trivial: repos/URLs, opinions, git, codebase Qs, retro, comparisons.

Parallel FIRST: 2+ failures / 3+ subtasks → multiple Agent tools. Research→research-coordinator-engineer; coord→project-coordinator-engineer; plan+exec→subagent-driven-development; feature→feature-lifecycle (.feature/→feature-state.py status). Force Direct: OFF.

**Creation Detection**: create/scaffold/build/"add new"/"new [component]" targeting agent/skill/pipeline/hook/feature/plugin/workflow/voice. Any of these + Simple+ → `is_creation=true`, Phase 4 Step 0. Not: debug/review/fix/refactor/explain/audit.

**Gate**: Complexity set. Creation → `[CREATION REQUEST DETECTED]`. Trivial: direct. Simple+: Phase 2.

---

### Phase 2: ROUTE

**Goal**: fill every slot the request earns — agent(s), skill, pipeline. The semantic self-route is PRIMARY and runs FIRST — the orchestrator reads the manifest in-session and decides for itself, with no routing sub-dispatch (self-route beat the Haiku hop by +8.1 accuracy points, zero new safety misses: `scripts/routing-ab-results/self-route-v1/VERDICT.md`). `pre-route.py` is a guardrail that runs AFTER the semantic decision and never short-circuits it.

**Contract: read for INTENT.** Route on what the user MEANS. Trigger keywords are hints, never gates. Plain or non-native phrasing routes as well as jargon: "send my commits to the server" routes like "git push". Cost: one manifest read per request — measured and accepted.

**Step 0: Semantic self-route (PRIMARY — runs first)**

The routing manifest (`scripts/routing-manifest.py`) is the runtime form; `docs/routing-map.md` is the human-readable committed form of the same data. Both are generated from frontmatter, so frontmatter is the single source of truth. CI checks staleness via `scripts/generate-routing-map.py --check`.

Resolve SDIR to locate installed scripts, then read the manifest (hash-gated cache or regenerate). This probe does not identify the active session model or provider:

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
bash "$SDIR/get-routing-manifest.sh"
```

Use `bash` explicitly so routing does not depend on the script's executable bit.

Hold the decision internally as JSON. It stays unprinted; the `[do-route]` marker is its sole external trace:

```
{
  "agent": "primary agent-name or null",
  "agents": ["extra agent names for parallel fan-out; [] when one agent covers it"],
  "skill": "skill-name or null",
  "pipeline": "pipeline-name or null",
  "reasoning": "one sentence why",
  "confidence": "high/medium/low"
}
```

**Routing rules (ALL apply):**

```
SECTION-INTEGRITY RULE (HARD CONSTRAINT — never violate):
- `agent` must be a name listed in the manifest's AGENTS: section, or null. Do not put a skill name in `agent`.
- `skill` must be a name listed in the SKILLS: section, or null. Do not put an agent name in `skill`.
- `pipeline` must be a name listed in the PIPELINES: section, or null.
- If no agent fits, return `"agent": null` — DO NOT promote a skill into the `agent` slot. The router falls back to a default agent (e.g. `general-purpose`) and pairs it with your chosen skill.
- Skills marked FORCE are still skills, not agents. They fill the `skill` slot only. Example: `shell-config` is a SKILL — on a match set `"skill": "shell-config"` and pick a separate agent (or null) for `agent`.
- Pipelines marked FORCE are still pipelines. They fill the `pipeline` slot only, and the run still needs its own `agent` and `skill`.
- Every name in `agents` must also be an AGENTS: name, and distinct from `agent`.

FORCE-ROUTE RULE: manifest entries marked FORCE — in SKILLS: or in PIPELINES: — are selected when their domain clearly matches the user's intent. FORCE matching is semantic, not keyword-based — match what the user means, not individual words:
- "push my changes" → pr-workflow ✓ (git push) | "push back on this design" → NOT pr-workflow (means resist)
- "configure my fish shell" → shell-config ✓ (the Fish shell) | "fish for bugs" → NOT shell-config (means search)
- "quick fix to the login page" → quick ✓ (small edit) | "quick overview of the architecture" → NOT quick (means explore)
A FORCE pipeline (5 of the 29) binds the `pipeline` slot exactly as a FORCE skill binds `skill`. `pre-route.py` reads FORCE pipelines and applies their semantic guard policy; the semantic route still owns intent and must apply the same MEANS-not-words test above.

PIPELINE-SELECTION RULE: pick a pipeline whenever the work has REAL PHASES. The PIPELINES: section ships in every manifest and 29 pipelines are available; reach for one on ANY of:
(1) the intent semantically matches a pipeline's description or its `t:` triggers, OR
(2) the shape is multi-phase — 3+ distinct steps, gather-then-synthesize, mixed script+LLM work, or intermediate artifacts worth keeping, OR
(3) Phase 1 classified the request Complex.
The user saying the word "pipeline" is one signal among these, never the gate. Examples:
- "write an article in vexjoy voice about X" → voice-writer ✓ | "research X with artifacts and sources" → research-pipeline ✓
- "comprehensive review of these 8 files" → comprehensive-review ✓ (outranked by `right-size-review.py` when a real diff exists)
- "add caching to the API and update the docs" → feature-pipeline ✓ (design → implement → document; nobody said "pipeline")
- "help me understand how auth works across this repo" → explore-pipeline ✓ (parallel exploration; a plain pipeline earns the pick on shape, no FORCE flag needed)
Return null when the whole job is one step for one agent: "fix the typo on line 42 of foo.py", "debug this failing test", "review this 10-line function".

MULTI-AGENT RULE: `agents` holds EXTRA agents beyond `agent`; `[]` when one agent covers the work. Fan out when the parts run at once against separate files: 2+ independent failures, 3+ independent subtasks, per-package or per-language review, gather from several domains. Keep a single agent when the parts touch the same files or each step consumes the previous step's output. Complex (Phase 1) starts from fan-out and justifies staying single.

SPECIFICITY RULES:
- Pick the most specific match. "Go tests" → golang-general-engineer + go-patterns, not general-purpose.
- Agent handles the domain. Skill handles the methodology. Pick both when possible.
- Prefer entries whose description semantically matches the request, not just keyword overlap.
- A task verb in the request (review, debug, refactor, test) prefers the skill matching that verb.
- GENUINE git / version-control operations — actually pushing code, committing files, opening or merging a pull request — select pr-workflow. Metaphorical uses ("commit to a decision", "merge ideas in your head", "push back on a proposal") do not route to pr-workflow.
- Return a single skill name as a string, not an array. Multiple candidates → pick the primary one.
```

**COMBINATION DOCTRINE.** Four surfaces compose; they do not compete. Fill every slot the request earns.

| Surface | Answers | Slot |
|---|---|---|
| Agent | who owns the domain | `agent`, plus `agents` for fan-out |
| Skill | which methodology runs | `skill` |
| Pipeline | which phase structure holds the work | `pipeline` |
| Stack | which extra rigor rides along | Phase 3 `stack` |

One surface filled is the FLOOR, not the ceiling — and 29.2% of dispatches sit at or below it (`evidence_route_decisions` 2026-08-15; a fallback agent or fallback skill counts as unfilled). Combine upward: Simple = agent+skill. Medium = agent+skill+stack. Complex = 2+ agents (`agent` plus `agents`), 2+ skills (`skill` plus Phase 3 `stack`), and a pipeline unless one phase truly covers the work — which is how Phase 1's "2+/2+" row is satisfied with one `skill` string.

Composition rules:
- A pipeline names the phases; the agent and skill still fill their slots and run inside those phases. Picking a pipeline replaces neither.
- Stack always composes: anti-rationalization-core rides every route, and Phase 3 adds the rest.
- A FORCE skill and a FORCE pipeline matching together is legal — different slots, both get filled.
- Contradictory pairs, keep one: `quick` with any pipeline (quick means one step — drop the pipeline); comprehensive-review with `right-size-review.py` (a real diff wins); `objective-loop` as fallback beside a real domain skill (the fallback yields); two pipelines (pick the outer one, nest the other through Step 1c).

**Step 0b: Apply the routing decision**

Use the `agent` and `skill` fields directly. Low confidence → verify against the INDEX files.

**Skill-greediness gate (HARD — non-negotiable for Simple+).** Null skill → pick: review→systematic-code-review, debug→workflow (systematic-debugging), refactor→workflow (systematic-refactoring), audit→systematic-code-review (whole-repo→full-repo-review), explain→codebase-overview, compare→decision-helper (agent A/Bs→agent-comparison), plan→planning, loop→objective-loop. Fallback: `objective-loop`.

**Agent-greediness gate (HARD — non-negotiable for Simple+).** `general-purpose` is the last resort, not the default. Measured share of dispatches: 42.5% (128/301, `evidence_route_decisions` 2026-08-15). Target band: unmeasured -- see the `learning-db.py` route health report for the current band and its provenance. A null `agent` works this table before `general-purpose` is permitted:

| Domain signal in the request | Agent |
|---|---|
| Go | golang-general-engineer |
| Python | python-general-engineer |
| TypeScript UI, React, bundling, state | typescript-frontend-engineer |
| TypeScript runtime bug, async race, type error | typescript-debugging-engineer |
| Node backend, REST, auth, webhooks | nodejs-api-engineer |
| Swift, Kotlin, PHP | swift-general-engineer, kotlin-general-engineer, php-general-engineer |
| SQL schema, query plans, migrations | database-engineer (SQLite + Peewee → sqlite-peewee-engineer) |
| ETL, warehouse, stream processing | data-engineer |
| Kubernetes, Helm, Ansible | kubernetes-helm-engineer, ansible-automation-engineer |
| Metrics and dashboards, search clusters, message queues | prometheus-grafana-engineer, opensearch-elasticsearch-engineer, rabbitmq-messaging-engineer |
| This toolkit: Python hooks | hook-development-engineer |
| This toolkit: skills, agents, routing tables, ADRs, INDEX files | toolkit-governance-engineer |
| Harness or toolkit upgrade sweep | system-upgrade-engineer |
| Tests, coverage, E2E | testing-automation-engineer |
| Web performance; design system and accessibility | performance-optimization-engineer, ui-design-engineer |
| React Native, Expo | react-native-engineer |
| API docs and runbooks; explainers and articles | technical-documentation-engineer, technical-journalist-writer |
| Review: quality / system + security / ADR + business logic / perspectives | reviewer-code, reviewer-system, reviewer-domain, reviewer-perspectives |
| Broad investigation; agent coordination; pipeline scaffolding | research-coordinator-engineer, project-coordinator-engineer, pipeline-orchestrator-engineer |
| MCP servers | mcp-local-docs-engineer |

No row fits → read the manifest's AGENTS: section again and match on description before falling back.

**Pairing rule (the measured defect).** 72% of those 128 (92) carried a named domain skill, fallbacks excluded: the router read the domain and had no slot to say so. A specific domain skill therefore obliges a matching domain agent — or a stated reason no agent covers it.

**Fallback reason.** Every `general-purpose` pick carries a written reason, one line, in both places the dispatch records it: the Step 3 banner's `-> Agent:` why field, and `task_spec.constraints` handed to `build-dispatch.py`. Shape: `general-purpose: <why no listed agent covers this domain>`. A pick with no reason is a routing bug — return to the table.

**Section validator (before dispatch):**

```
agents = tokens(manifest, "AGENTS:", "SKILLS:")
skills = tokens(manifest, "SKILLS:", "PIPELINES:")
if route.agent not in agents:
    if route.agent in skills: route.skill ||= route.agent
    route.agent = None; record_misroute(...)
route.agent ||= "general-purpose"
```

No pair→general-purpose+objective-loop. `[cross-repo]`→`.claude/agents/`. Code→domain agents.

**Step 1: Deterministic safety-net** (`pre-route.py` — runs AFTER the semantic decision, never short-circuits it)

Use its result ONLY as a guardrail. Run once per /do; Phase 3 reads its `stack`:

```bash
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

→ `PRE_ROUTE_RESULT`.

- **(a) Safety-critical force-route override — the one case that beats Step 0.** `"confidence": "high"` with a `force_route` match for `pr-workflow` or a security skill overrides a disagreeing semantic pick: genuine push, commit, create-PR, and merge work, and security work, must hit the quality gates (lint, tests, CI). Record `match_type`. The agent stays the Step 0 pick, or the Agent-greediness table result when Step 0 returned null.
- **(b) Every other result keeps the Step 0 decision.** Phrase and unigram guards inside `pre-route.py` already suppress idiom false positives ("fish out", metaphorical commit/merge), so a guarded or non-matching result leaves the semantic pick standing. Matching only force-routes is by design — the semantic route owns the long tail.

**Step 2: Apply skill override** — "review"→systematic-code-review, "debug"→workflow (systematic-debugging pipeline), "refactor"→workflow (systematic-refactoring pipeline), "TDD"→test-driven-development. Full table in INDEX.

**Step 3: Routing banner** (first visible output)

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from skills/workflow/references/pipeline-index.json)
   -> Extra Rigor: [verification patterns for code/security/testing when needed]
 Invoking...
===================================================================
```

Trivial: `Classification: Trivial - [reason]`, `Handling directly`.

**Gate**: Agent+skill set, banner shown. Phase 3.

---

### Phase 3: ENHANCE

Stack on signals.

| Signal | Enhancement |
|---|---|
| Substantive | Retro knowledge when material |
| "with tests"/"production ready" | test-driven-development+verification-before-completion |
| "research needed"/"investigate first" | research-coordinator-engineer |
| Comprehensive/thorough/full review or 5+ files, no diff | parallel-code-review (Security, BizLogic, Arch) |
| Multi-file review, real diff | `right-size-review.py`; T1→3,T2→12,T3→17,T4→27. CRITICAL+1. Outranks comprehensive-review. |
| Complex implementation | Offer subagent-driven-development |
| "local only"/"no push"/"keep it local"/"stay local" | Inject `shared-patterns/local-only.md` |
| Voice profile (e.g. voice-example-profile) | Stack `voice-writer`; voice-*=profile |
| Material unresolved choices | `planning` — `ambiguity-triage.md`; ask only when question value is high |
| Needed knowledge or approval exists with another person | `planning` — `human-source-elicitation.md` |
| Observation can settle a high impact uncertainty | `planning` — `empirical-prototype.md` |
| Phase, worker, or session transition | `planning` — `context-boundary.md` |
| Objective with done-criteria / "loop until done" | Stack `objective-loop` |
| Protected PR/security intent with a Go source operand | Keep `pr-workflow`/`security-review` primary and stack `go-patterns` from `PRE_ROUTE_RESULT.stack` or router `pairs_with` |

Review overlap: real-diff row wins; fallback only without diff.

**Question-value policy.** Complexity alone never forces questions. Inspect the request, repository, supplied material, and prior decisions first. Load `planning/references/ambiguity-triage.md`, then choose:

| Unresolved state | Action |
|---|---|
| Low impact, reversible, or covered by a safe convention | State the assumption and execute. |
| One high impact decision owned by the current user | Ask one question with a recommendation, then execute. |
| Two or more high impact decisions owned by the current user | Use `depth-first-interview.md`: batch the independent frontier, then traverse genuine dependencies; interviews initiated by the router cap at five questions and three decision rounds. |
| Facts, constraints, preferences, or approval exist with another person | Use `human-source-elicitation.md`; draft the artifact and never send without authorization. |
| Evidence can settle the choice faster than discussion | Use `empirical-prototype.md`: Question → Evidence → Verdict → Next action. |

Explicit "interview me" or "grill me" opts into exhaustive material coverage until shared understanding or a user stop; it has no arbitrary question or round cap. An implicit interview must earn its interruption cost through likely avoided rework and remains bounded. "Just build it," "skip questions," and equivalents use recommended defaults and continue.

An interview is not terminal when it suspends an active delivery objective. Compile the decisions and automatically resume the originating build, fix, install, validation, or other execution flow; never report the decision artifact as completion of the original objective. Stop after compilation only when the user explicitly requested only an interview artifact or excluded implementation.

Ask the current independent frontier in one logical round. In Markdown, include the full frontier with a recommendation for each and wait once. A harness native structured question UI may chunk the frontier only at its capacity per call; do not recompute between chunks unless an answer invalidates a pending question. Single question turns are reserved for true dependency branches. Interviews initiated by the router cap at five questions and three decision rounds, plus at most one concise confirmation response; explicit grills construct and exhaust the material decision tree, with the kinds and number of questions determined by what shared understanding requires. Do not add ceremonial questions. Answering the last frontier does not authorize execution by itself: ask one concise shared understanding confirmation. Skip that extra confirmation only when the same response explicitly says "proceed", "build it", "looks right, continue", or equivalent. Resume nested execution only after explicit proceed or confirmation; a request for only an interview stops at the artifact.

At each pipeline or worker boundary, apply `planning/references/context-boundary.md`: continue while live context is evidence; use a fresh worker with a complete Task Spec when durable artifacts are sufficient; use `pause.md` only for plan or session lifecycle; use the Task Spec for inline worker or agent transfer, adding `session-handoff` only for live process or PR state; compact only under context pressure.

Check `pairs_with` before stacking. Skills with built-in verification gates may suffice.

anti-rationalization-core always + verification-checklist (code/debug) + anti-rationalization-review + anti-rationalization-security + anti-rationalization-testing; external: **untrusted-content-handling**. Max: load `verification-before-completion` references/anti-rationalization-enforcement.md.

**Step G: GATHER (Simple+)** — fill the Task Spec before the Gate.

1. Keep `request_verbatim` unchanged. State this worker's `intent`, `constraints` (including authority), `files`, ownership, and `acceptance`.
2. Include decisions, prior results, and gaps when they affect this assignment. Summarize findings and link durable evidence; quote exact text only when its wording matters. Do not copy the whole investigation into every handoff.
3. Verify named paths. Add excerpts only when they explain a decision or let the worker act; the builder validates paths even when gathering is off.
4. Use `context_mode: "summary"` for current git status, diff stat, and recent commits. Use `files` when initial excerpts help, or `none` when the worker already has valid context. The legacy default is `files`. Mode `none` retains a notice that no fresh state was gathered, so the handoff envelope stays complete. Legacy `--no-gather` removes that envelope too; use `none` for Medium+ handoffs. Context modes never omit the supplied Task Spec or required injections.

Reuse reads only while their source and task context remain unchanged; a fresh worker needs access to the relevant content or references. For worker transitions, use `session-handoff`. Verification evidence follows `verification-before-completion`; repeat checks when their inputs or relevant environment change, not just because a new phase starts.

**Gate**: Enhancements applied, Task Spec filled. Phase 4.

---

### Phase 4: EXECUTE

**Step 0: Creation** — ADR at `adr/{name}.md`, `adr-query.py register`, plan.

**Step 1: Plan** (Simple+) — `task_plan.md`; skip Trivial.

**Step 1b: Quality-loop** (Medium+ code mod) — `references/quality-loop.md` 14 phases. P2 agent=implementation. Force-route in loop. Skip non-code/Trivial/Simple.

**Step 1c: Workflow** — Pipeline pick or Complex no pick or explicit → `${CLAUDE_SKILL_DIR}/references/workflow-dispatch.md`. Both 1b+1c → quality-loop OUTER, workflow in IMPLEMENT.

**Step 2: Invoke agent**

**`build-dispatch.py`** — source for `[do-route]`, exact Skill-tool calls, thinking, budget, Task Spec, injections, worktree/local-only. Do not hand-assemble it.

```bash
python3 "$SDIR/build-dispatch.py" --json '{
  "agent": "<agent>", "skill": "<skill; omit when agent-only>",
  "pipeline": "<pipeline; omit when Phase 2 returned null>",
  "complexity": "<trivial|simple|medium|complex>",
  "model": "inherit",
  "context_mode": "summary",
  "provider": "<anthropic|openai|other>",
  "manual_model_override": false,
  "health": "-",
  "fallback_reason": "<REQUIRED when agent=general-purpose; omit otherwise>",
  "stack": ["s1","s2"],
  "task_spec": {"request_verbatim": "<user message, unchanged>", "intent": "...",
                "constraints": "<applicable rules, limits, and authorization>",
                "decisions": "...", "prior_results": "...", "gaps": "...",
                "acceptance": "<command> → <expected>",
                "files": "<owned paths; optional line ranges>", "ownership": "<worker scope>",
                "operator_context": "..."},
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}'
```

`agent`/`skill`/`complexity`: Phase 2 (null→`-`). `pipeline`: the Phase 2 pick, passed so the marker carries it; omit when null. The builder validates each name against its index, then emits this exact action contract once per callable skill, primary first with ordered stack de-duplication: `Call the Skill tool with \`skill-name\`.` Shared-pattern stack entries remain prompt injections. Agents and pipelines stay out of Skill-tool calls. Fan-out: one call per agent, same `skill`/`pipeline`. `model`: **required Medium+**; use `inherit` by default. Explicit overrides follow `references/model-selection.md`. `provider` describes the active harness (anthropic|openai|other), not an installed directory. `health`: `-` (in-context weights read retired — `docs/route-loop-validation.md`). `fallback_reason`: **required when `agent=general-purpose`** — the one-line reason from the Agent-greediness gate, any prose; `build-dispatch.py` slugifies it and appends `fallback=<slug>` to the marker so every fallback is countable. Dispatch fails without it. `stack`: Phase 3. `task_spec`: mandatory Simple+ (Phase 3 Step G); the script rejects an empty spec at Medium+; creation+"match ADR". `thinking_override`: slow=security/arch/5+files; fast=lookups.

`[do-route]` = SOLE signal for `routing-decision-recorder`. Sub-agents excluded.

**Fallback:** `[do-route] agent={a} skill={s|-} complexity={c}[ pipeline={p}] health=- model={m|-}`, Task Spec inline, dispatch.

**Model selection.** Default to `model: "inherit"`. Omit `model_policy`, `model_effort`, and tool-level model/effort overrides. Do not pass the word `inherit` to an agent tool as a model name. This uses the current session model when the harness supports inheritance. If it cannot, report the limitation rather than silently selecting another model.

The marker records the requested selection, not an observed worker model. The actual model remains unknown unless the harness reports it. Do not infer session identity from installed script directories or historical model tables.

Medium+ must provide `model: "inherit"`, a supported explicit model, or a policy. For a deliberate override, load `references/model-selection.md`; existing provider policies and explicit choices remain supported. Use scripts for deterministic work. Change model or effort only for a concrete task need or a missed acceptance criterion. Session configuration stays under the user's control. Codex prompts stay read-only and public unless the task requires otherwise.

**Complex (3+ sources):**

| Verbs | Mode |
|---|---|
| list/count/extract/inventory/search/check/find/grep | Scripts when deterministic; otherwise readers → synthesis, inheriting the session model |
| review/audit/assess/analyze/debug/investigate/evaluate | Single agent, inheriting the session model |

Simple/Medium: direct. Feature-branch; mods commit. `isolation:"worktree"`→`flags.worktree`. Non-org: 3 reviews→fix→PR. Org: confirm git.

**Step 3: Multi-part / fan-out** — deps sequential; independent parallel (max 10). Phase 2 `agents` → ONE `build-dispatch.py` call and ONE Agent dispatch per agent: N agents = N calls = N markers, one marker each. Emit the parallel Agent calls in a single message. Each agent gets its own `files` and scope. Sequential stages pass relevant prior results and evidence locations; synthesis receives the findings and access to evidence from every required stage. Packing several markers into one Bash/Workflow script keeps them recorded but forfeits route-fit scoring, which reads a lone marker per event.

**Step 4: Auto-Pipeline Fallback** (no match, Simple+) — `auto-pipeline`. None → closest+`objective-loop`. Never empty skill.

**Lazy-completion check.** "Done" on enumerable → compare scope; short → reject, re-dispatch (`references/lazy-completion-detector.md`). Re-dispatch → route failure.

**Gate**: Agent invoked, results delivered.

---

### Routing telemetry (automatic)

Hooks record routing. On an observed route failure, or to re-derive a quoted telemetry figure → load `${CLAUDE_SKILL_DIR}/references/routing-telemetry.md` (hooks table, outcome fidelity, route-failure protocol, figure queries).

---

## Error Handling

On any routing error → load `${CLAUDE_SKILL_DIR}/references/error-handling.md`.

## References

- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`
- `agents/INDEX.json`, `skills/INDEX.json`
- `skills/workflow/SKILL.md`, `skills/workflow/references/pipeline-index.json`
- `scripts/routing-manifest.py`
