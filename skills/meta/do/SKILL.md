---
name: do
promoted_to: native-router
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

ROUTER, not worker. Classify → agent+skill → dispatch. All execution goes to agents. Catching yourself reading/writing code or analyzing — pause and route to an agent. Main: Classify→Select→Dispatch→Evaluate→Re-route→Report.

Do the whole thing (tests+docs). Product, not plan. Permanent solve over workaround. Search before building; test before shipping. Decompose into agent-sized tasks. The result reads as "that's done," not "that's a start." Partial → follow-up. Inject Simple+. Confidence in handling directly is a signal to route.

Dense-Complete Writing (`build-dispatch.py` injects; `skills/shared-patterns/dense-complete-writing.md`). User: banners+summary. Internal: JSON/reasoning/stacking (Verbose overrides).

## Instructions

### Phase Banners (MANDATORY)

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

Beyond user-named file = Simple+, MUST route. Uncertain → UP. Depth: `references/progressive-depth.md`. NOT Trivial: repos/URLs, opinions, git, codebase Qs, retro, comparisons.

Parallel FIRST: 2+ failures / 3+ subtasks → multiple Agent tools. Research→research-coordinator-engineer; coord→project-coordinator-engineer; plan+exec→subagent-driven-development; feature→feature-lifecycle (.feature/→feature-state.py status). Force Direct: OFF.

**Creation Detection** (MANDATORY): create/scaffold/build/"add new"/"new [component]" targeting agent/skill/pipeline/hook/feature/plugin/workflow/voice. ANY + Simple+ → `is_creation=true`, Phase 4 Step 0. Not: debug/review/fix/refactor/explain/audit.

**Gate**: Complexity set. Creation → `[CREATION REQUEST DETECTED]`. Trivial: direct. Simple+: Phase 2.

---

### Phase 2: ROUTE

Semantic intent. Prefer FORCE. Keywords hint, never gate. "send my commits to the server" = "git push".

**Pre-route (ONCE, before fast-path)**

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

→`PRE_ROUTE_RESULT` (once). Force-route guard only: high-conf force_route match or fallthrough — the semantic route owns the long tail.

**Fast path:** PRE_ROUTE_RESULT high-conf force_route + pr-workflow/security → skip 0/1, dispatch direct. Keep banner+overrides+P3+P4. `[do-route]` `health=-`. Agent: pre-route→domain→general-purpose.

**Step 0: Self-route**

Read the manifest (hash-gated cache or regenerate):

```bash
bash "$SDIR/get-routing-manifest.sh"
```

Use `bash` explicitly so routing does not depend on the script's executable bit.

Internal JSON; `[do-route]` = sole trace.

**Routing rules (ALL apply):**

```
SECTION-INTEGRITY (HARD — never violate):
agent∈AGENTS|null, skill∈SKILLS|null, pipeline∈PIPELINES|null.
No fit→null→general-purpose. Never skill→agent. FORCE skills: skill slot only.

FORCE-ROUTE — select when domain matches SEMANTICALLY (meaning, not words):
- "push my changes" → pr-workflow (FORCE) ✓ (git push)
- "push back on this design" → NOT pr-workflow (resist/argue)
- "configure my fish shell" → shell-config (FORCE) ✓
- "fish for bugs" → NOT shell-config (search for bugs)
- "quick fix to the login page" → quick (FORCE) ✓
- "quick overview of the architecture" → NOT quick (exploration)

PIPELINE — both: triggers match + multi-phase benefit. Mostly null.
"vexjoy voice article"→voice-writer ✓ | "research+sources"→research-pipeline ✓ | "fix typo"→null
Comprehensive-review outranked by right-size-review when real diff exists.

GENERAL: most specific. Agent=domain, skill=method. GENUINE git/version-control ops (actually pushing code, committing files, opening/merging a PR) → ALWAYS pr-workflow. Metaphorical uses ("commit to a decision", "merge ideas/branches in your head", "push back on a proposal") → NEVER pr-workflow.
```

**Step 0b: Apply the routing decision**

Low conf → verify INDEX.

**Skill-greediness gate (HARD — non-negotiable for Simple+).** Null skill → pick: review→systematic-code-review, debug→workflow (systematic-debugging), refactor→workflow (systematic-refactoring), audit→systematic-code-review (whole-repo→full-repo-review), explain→codebase-overview, compare→decision-helper (agent A/Bs→agent-comparison), plan→planning, loop→objective-loop. Fallback: `objective-loop`.

**Section validator (MANDATORY before dispatch):**

```
agents = tokens(manifest, "AGENTS:", "SKILLS:")
skills = tokens(manifest, "SKILLS:", "PIPELINES:")
if route.agent not in agents:
    if route.agent in skills: route.skill ||= route.agent
    route.agent = None; record_misroute(...)
route.agent ||= "general-purpose"
```

No pair→general-purpose+objective-loop. `[cross-repo]`→`.claude/agents/`. Code→domain agents.

**Step 1: Safety-net** (reads PRE_ROUTE_RESULT)

(a) force_route pr-workflow/security disagrees → override. Git/security MUST hit quality gates. (b) Fallthrough (guards pre-applied in pre-route) → Step 0 decision stands.

**Step 2: Apply skill override** — "review"→systematic-code-review, "debug"→workflow (systematic-debugging pipeline), "refactor"→workflow (systematic-refactoring pipeline), "TDD"→test-driven-development. Full table in INDEX.

**Step 3: Routing banner** (MANDATORY — first visible output)

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

Learning: hooks below.

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
| Interview-mode heuristic | `planning` — `depth-first-interview.md` |
| Objective with done-criteria / "loop until done" | Stack `objective-loop` |

Review overlap: real-diff row wins; fallback only without diff.

**Interview heuristic.** Short, no file/symbol, ambiguous. Spec:

| Example | ? | Why |
|---|---|---|
| "i'm not sure how to approach this complex build" | Y | Vague+no target |
| "fix the typo on line 42 of foo.py" | N | File+loc |
| "build a thing that does X" | Y | No file |
| "add a test for `parseConfig` in src/config.go" | N | Symbol+file |
| "where do i even start with this rewrite" | Y | No subject |
| "rename `cfg` to `config` in `internal/`" | N | Mechanical |

Check `pairs_with` before stacking. Skills with built-in verification gates may suffice.

anti-rationalization-core always + verification-checklist (code/debug) + anti-rationalization-review + anti-rationalization-security + anti-rationalization-testing; external: **untrusted-content-handling**. Max: load `verification-before-completion` references/anti-rationalization-enforcement.md.

**Gate**: Enhancements applied. Phase 4.

---

### Phase 4: EXECUTE

**Step 0: Creation** — ADR at `adr/{name}.md`, `adr-query.py register`, plan.

**Step 1: Plan** (Simple+) — `task_plan.md`; skip Trivial.

**Step 1b: Quality-loop** (Medium+ code mod) — `references/quality-loop.md` 14 phases. P2 agent=implementation. Force-route in loop. Skip non-code/Trivial/Simple.

**Step 1c: Workflow** — Pipeline pick or Complex no pick or explicit → `${CLAUDE_SKILL_DIR}/references/workflow-dispatch.md`. Both 1b+1c → quality-loop OUTER, workflow in IMPLEMENT.

**Step 2: Invoke agent**

**`build-dispatch.py` (MANDATORY)** — source for `[do-route]`, thinking, budget, Task Spec, injections, worktree/local-only. Never hand-assemble.

```bash
python3 "$SDIR/build-dispatch.py" --json '{
  "agent": "<agent>", "skill": "<skill; omit when agent-only>",
  "complexity": "<trivial|simple|medium|complex>",
  "model": "<fable|sonnet|opus|codex|gpt-5.6-sol|gpt-5.6-terra|gpt-5.6-luna>",
  "model_policy": "<low-risk|standard|high-risk|max-power>",
  "model_effort": "<low|medium|high|xhigh|max>",
  "provider": "<anthropic|openai|other>",
  "manual_model_override": false,
  "health": "-",
  "stack": ["s1","s2"],
  "task_spec": {"intent": "...", "constraints": "...", "acceptance": "...",
                "files": "...", "operator_context": "..."},
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}'
```

`agent`/`skill`/`complexity`: Phase 2 (null→`-`). `model`: **required Medium+** (`-` trivial/simple). Use `model_policy` for automatic selection — resolves via the harness-native provider lane. `model_effort` identifies the benchmark point; advisory for Claude lanes (Agent tool has no per-call effort). `provider`: harness detection (anthropic|openai|other, default anthropic). A manual model change must set both `manual_model_override=true` and `model_effort`; never inherit the policy effort silently. `health`: `-` (in-context weights read retired — `docs/route-loop-validation.md`). `stack`: Phase 3. `task_spec`: mandatory Medium+; creation+"match ADR". `thinking_override`: slow=security/arch/5+files; fast=lookups.

`[do-route]` = SOLE signal for `routing-decision-recorder`. Sub-agents excluded.

**Fallback:** `[do-route] agent={a} skill={s|-} complexity={c} health=- model={m|-}`, Task Spec inline, dispatch.

**Model Selection (ADR `model-selection-policy`).**

**Harness-native routing.** The SDIR probe (Phase 2 pre-route) identifies the harness: `~/.claude` → provider `anthropic`, `~/.codex` → provider `openai`, `~/.hermes`/`.factory`/`.reasonix` → provider `other`. Default when absent: `anthropic` (Claude Code is primary). Each provider lane has its own automatic policy table; cross-provider dispatch is manual-only (explicit tool invocation, never a silent default).

Run deterministic work with scripts, not an LLM. Three decision axes: (1) the current session model — the harness runs Opus 5, and the owner directs Opus 5 as the Anthropic-lane default for every task class. (2) DeepSWE Pass@1 / cost / tokens / steps — agentic task completion rate, the quantitative source for models that have been measured. (3) Owner-observed felt quality — fable > sol (noticeable gap despite similar Pass@1), opus > gpt-5.5 (marginal). Benchmark ties or near-ties resolve in favor of felt quality. Cells: `Pass@1 / cost / output tokens / steps`; cost = avg USD per task, written as a plain number — slash-command templating substitutes dollar-digit positional parameters in this injected body, so a literal dollar sign before a digit corrupts on every argful invocation. Higher Pass@1 better, other three lower-is-better. Opus 5 has no DeepSWE run yet, so its cells read `n/a — not yet benchmarked` and its pts/USD cannot be computed until it is measured; it is selected on the session-model and owner-directive grounds above, not on a benchmark figure.

**Start low, escalate on miss.** Task-class tables are ceilings by risk class, not starting points. Default = lowest tier whose risk class matches; escalate one tier only when output misses the acceptance bar. High tiers cost 3-6x per Pass@1 point where measured (see the OpenAI lane's pts/$ column; the Anthropic lane's is pending an Opus 5 benchmark) — pre-paying for xhigh/max "to be safe" wastes the 200 USD/month plan budget. Fan-out rule: parallel readers use the lane's low-risk point; one synthesis agent may run one tier higher. User-facing output (docs, prose, reviews the owner reads, design) leans opus one tier up from the task class; bulk/mechanical/parse-heavy work is where the OpenAI lane's cheaper points earn their keep (under Codex harness or explicit cross-provider call).

**Anthropic lane** (automatic under Claude Code). Effort is advisory — recorded in marker as model@effort for telemetry; the Agent tool has no per-call effort parameter.

Current default: **Opus 5** (`opus`) at every task class. It is the model this session runs and the owner's directed default; it replaced fable across the lane on 2026-07-24.

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| Opus-5 (current default, unmeasured) | n/a — not yet benchmarked | n/a — not yet benchmarked | n/a — not yet benchmarked | n/a — not yet benchmarked | n/a — not yet benchmarked |
| Fable-5 (prior measurement) | 70 / 21.63 / 119k / 88 | 70 / 13.41 / 80k / 68 | 69 / 9.18 / 57k / 59 | 65 / 6.09 / 40k / 48 | 60 / 3.76 / 25k / 38 |
| Opus-4.8 (prior measurement) | 59 / 13.22 / 135k / 120 | 54 / 8.01 / 86k / 95 | 52 / 4.28 / 50k / 73 | 49 / 3.44 / 41k / 66 | 41 / 2.29 / 29k / 54 |
| Sonnet-5 (prior measurement) | 54 / 26.40 / 214k / 268 | 50 / 11.89 / 121k / 186 | 48 / 7.43 / 87k / 147 | 40 / 4.08 / 57k / 108 | 31 / 2.19 / 36k / 77 |

The Fable-5 / Opus-4.8 / Sonnet-5 rows are recorded DeepSWE measurements from the 2026-07-09 policy, kept as history for manual picks. Opus 5 has no DeepSWE run, so every cell reads `n/a — not yet benchmarked` and its pts/USD stays uncomputable until it is measured.

| Task class | Selection | pts/$ | Why |
|---|---|---|---|
| deterministic | no LLM | — | Run the script directly. |
| low-risk | `opus` / `low` | n/a | Current session model, owner-directed default; effort floor per start-low. |
| standard | `opus` / `medium` | n/a | Current session model, owner-directed default; one tier up for standard work. |
| high-risk | `opus` / `high` | n/a | Current session model, owner-directed default; high effort for risk-bearing work. |
| max-power | `opus` / `xhigh` | n/a | Current session model, owner-directed default; `manual_model_override=true`; state justification in task_spec intent. |

Effort selection still follows **start low, escalate on miss** — the effort column is a ceiling by risk class, and a miss against the acceptance bar is what buys the next tier. Opus 5 at `max` stays manual-only pending measurement. Fable-5, Sonnet-5, and Opus-4.8 points are now the manual-only ones: they need `manual_model_override=true` plus `model_effort`, and stay available for felt-quality escalation (fable), context-window, latency, and fan-out breadth constraints the benchmark does not measure. Haiku is retired.

**OpenAI lane** (automatic under Codex CLI).

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| GPT-5.6 Sol | 73 / 8.39 / 60k / 61 | 71 / 4.70 / 41k / 44 | 69 / 3.47 / 28k / 37 | 61 / 1.86 / 18k / 31 | 45 / 1.07 / 11k / 23 |
| GPT-5.6 Terra | 70 / 4.95 / 72k / 76 | 60 / 2.13 / 40k / 43 | 54 / 1.13 / 22k / 34 | 35 / 0.58 / 12k / 25 | 24 / 0.43 / 8.6k / 21 |
| GPT-5.6 Luna | 67 / 3.03 / 73k / 102 | 57 / 1.54 / 45k / 71 | 44 / 0.78 / 26k / 49 | 11 / 0.22 / 8.2k / 24 | 2 / 0.07 / 3.1k / 12 |
| GPT-5.5 legacy | n/a | 67 / 7.23 / 46k / 82 | 64 / 5.10 / 31k / 62 | 54 / 2.75 / 20k / 46 | 27 / 1.20 / 9.4k / 28 |

| Task class | Selection | pts/$ | Why |
|---|---|---|---|
| deterministic | no LLM | — | Run the script directly. |
| low-risk | `gpt-5.6-terra` / `high` | 47.8 | 54 Pass@1 at 1.13, 22k tokens, 34 steps. |
| standard | `gpt-5.6-sol` / `high` | 19.9 | 69 Pass@1 at 3.47, 28k tokens, 37 steps. |
| high-risk | `gpt-5.6-sol` / `xhigh` | 15.1 | 71 Pass@1 at 4.70, 41k tokens, 44 steps. |
| max-power | `gpt-5.6-sol` / `max` | 8.7 | 73 Pass@1 at 8.39, 60k tokens, 61 steps; `manual_model_override=true`; state justification in task_spec intent. |

All GPT-5.5 choices are manual-only. Off-policy GPT-5.6 points (Sol medium/low, Terra max/xhigh/medium/low, all Luna) are manual-only — some are cost trade-offs, not dominated; use with `manual_model_override=true` for a stated constraint.

**Other harnesses** (provider=`other`): `model_policy` is unavailable — choose the highest non-dominated Pass@1 point among models the harness exposes, applying the same start-low-escalate-on-miss discipline. Set model explicitly.

**Cross-provider escalation** — manual only, never automatic. Escalating anthropic → sol is a cost/limits lever or independent-second-opinion lever, not a quality upgrade. Under Claude Code, codex-wrapper dispatches (`codex` skill, pr-workflow codex second-opinion review) remain valid as EXPLICIT tools — deliberate cross-provider calls, not defaults. Escalation targets: anthropic max-power miss → sol/xhigh or sol/max (second opinion, cheaper per point); openai max-power miss → opus/xhigh (the Anthropic-lane default), or fable/xhigh as a manual felt-quality pick. Manual-pick ordering among legacy/manual points: fable above opus-4.8 above gpt-5.5 where they otherwise tie.

**Coordinator model.** The main-thread coordinator routes and evaluates but never executes; its cost is input-dominated (largest context, short outputs), and DeepSWE Pass@1 measures execution it never does. Picks: anthropic harness → `opus` (Opus 5, the session model — it replaces the prior sonnet pick); openai harness → `gpt-5.6-terra`/`high`. Safe because deterministic scripts (pre-route, manifest, build-dispatch, health weights) absorb routing complexity and the learning loop bounds misroute cost. Downgrade the anthropic coordinator to `sonnet` only as a deliberate plan-limit measure. Session model is set via harness config (`/model`), not per-turn.

**Medium+ MUST set a model or policy.** Codex prompts stay read-only and public unless a task requires otherwise.

**Complex (3+ sources):**

| Verbs | Mode |
|---|---|
| list/count/extract/inventory/search/check/find/grep | Scripts when deterministic; otherwise harness-native low-risk readers → harness-native high-risk synth |
| review/audit/assess/analyze/debug/investigate/evaluate | Single harness-native high-risk agent |

Simple/Medium: direct. Feature-branch; mods commit. `isolation:"worktree"`→`flags.worktree`. Non-org: 3 reviews→fix→PR. Org: confirm git.

**Step 3: Multi-part** — deps sequential; independent parallel (max 10).

**Step 4: Auto-Pipeline Fallback** (no match, Simple+) — `auto-pipeline`. None → closest+`objective-loop`. Never empty skill.

**Lazy-completion check.** "Done" on enumerable → compare scope; short → reject, re-dispatch (`references/lazy-completion-detector.md`). Re-dispatch → route failure.

**Gate**: Agent invoked, results delivered.

---

### Learning Capture (automatic)

Hooks capture all. On observed route failure or learning question → load `${CLAUDE_SKILL_DIR}/references/learning-capture.md` (hooks table, outcome fidelity, route-failure protocol).

---

## Error Handling

On any routing error → load `${CLAUDE_SKILL_DIR}/references/error-handling.md`.

## References

- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`
- `agents/INDEX.json`, `skills/INDEX.json`
- `skills/workflow/SKILL.md`, `skills/workflow/references/pipeline-index.json`
- `scripts/routing-manifest.py`
