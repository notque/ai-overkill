# Dynamic Workflows: Native (Anthropic) vs VexJoy Homegrown Orchestration

> Generated 2026-05-28 by a native dynamic workflow (run `wf_a28e3be7-adb`): 7 parallel
> dimension-compare agents + 1 synthesis agent, 8 agents / ~222k tokens / ~2 min.

## TL;DR

The native tool makes orchestration a **deterministic JavaScript program a runtime executes**: the model writes inline JS where loops, conditionals, and fan-out (`parallel`/`pipeline`) are real code, `agent()` is the only point LLM judgment enters, every run is journaled, and resume replays the longest unchanged prefix of `agent()` calls from cache (same script+args = 100% cache hit). VexJoy makes orchestration **LLM-interpreted prose**: a `/do` router and ~46 markdown "pipelines" describe control flow in English ("dispatch all 10 in one message", "proceed if ≥3 of 10 returned"), honored by the model rather than enforced by a runtime, with deterministic Python sitting beside the spine for mechanical sub-tasks (routing safety-net, state files, FTS5 routing telemetry) but never driving dispatch. The split is structural: program-as-orchestrator with journaled replay and tool-layer schema enforcement vs prose-as-orchestrator with inferential resume and convention schemas.

## Comparison

| Dimension | Native | VexJoy | Verdict |
|---|---|---|---|
| **Execution substrate & determinism** | Control flow is JS a runtime executes; `parallel`/`pipeline` primitives; wall-clock/randomness removed for bit-stable replay; journaled, `resumeFromRunId` replays unchanged prefix | Control flow is markdown prose an LLM re-interprets each run; deterministic Python only for routing/state/telemetry, never dispatch | **Native stronger** — same spec can execute differently run-to-run in vexjoy; determinism real only inside standalone Python |
| **Parallelism model & limits** | Runtime scheduler: deterministic fan-out, auto-queue against `min(16,cores-2)`, 1000-agent backstop, barrier (`parallel`) vs no-barrier (`pipeline`), shared token budget | Multiple `Task` calls in one message; 10-agent cap + manual batching as prose; degradation tier table by judgment; no queue, no barrier/pipeline distinction | **Native stronger** — native enforces what vexjoy only describes |
| **Persistence & resume** | Runtime journal keyed by `runId`; unchanged-prefix of `agent()` returns from cache instantly; no LLM "where am I" reasoning; survives 11-day runs | Disk artifacts (`.feature` state, `HANDOFF.json`, `task_plan.md`); inferential priority-cascade resume; prior agent outputs never cached/replayed | **Native stronger** — native resume is free and lossless; vexjoy re-runs interrupted work |
| **Structured inter-agent output** | `agent({schema})` forces `StructuredOutput` tool; validated at tool-call layer; auto-retry on mismatch; returns typed object; non-conforming payload cannot reach caller | Real draft-2020-12 schemas + jsonschema validator exist but are **decoupled from dispatch** (grep: never referenced); validation = optional post-hoc markdown re-parse | **Native stronger** — native guarantees conformance; vexjoy's schemas are unwired |
| **Verification & adversarial checking** | No built-in verification content; you author it, but gating is enforceable — schema-validated verdicts, auto-retry, deterministic JS so a reject mechanically blocks next stage; cross-model via `opts.model` | Richest ready-made content: two-stage review gate, 4-level goal-backward audit (EXISTS/SUBSTANTIVE/WIRED/DATA-FLOW), live Playwright validation, cross-model Codex; but all prose-honored | **Complementary** — vexjoy = methodology out of the box (trust LLM to honor); native = author it yourself but gate is a hard program |
| **Cost control & scale ceiling** | First-class `budget` global; `agent()` throws when exhausted; enables `while(budget.remaining()>0)` loop-until-budget; cached re-runs near-zero token cost; hours-to-days, hundreds of agents | No token-budget primitive anywhere in the spine; bounded only by 10-cap + human retry counts; ceiling ≈ single-session burst (~25 agents); re-runs re-spend | **Native stronger** — native is the only one that bounds unattended spend |
| **Activation & governance** | Opt-in only (explicit or `ultracode`); first-run confirmation preview; admin kill-switch via managed settings; guardrails baked into runtime | Always-on: `/do` routes every prompt, parallelism auto-fires (2+ items / 3+ subtasks); ~65 edge hooks (hard branch-safety deny, ADR/config gates) + `PROTECTED_ORGS` per-action policy | **Complementary** — native = launch-time consent gate; vexjoy = per-action policy gates |

## What the native tool gives you that vexjoy doesn't

- **A real runtime that executes control flow.** Loops, conditionals, and fan-out are JavaScript a deterministic engine runs — they behave identically every run, not "as the model chooses to interpret the markdown this time."
- **Journaled, cached-prefix replay.** `resumeFromRunId` returns the longest unchanged run of `agent()` calls instantly from cache; same script+args = 100% cache hit, bit-stable. No re-execution, no LLM reasoning about where it left off.
- **A true scheduler with auto-queueing.** Excess agents queue automatically against `min(16, cores-2)` with a 1000-agent lifetime backstop — no manual batching instruction the model must remember to honor.
- **Barrier vs pipeline as primitives.** `parallel(thunks)` (hard barrier, failures → null) vs `pipeline(items, ...stages)` (no barrier, item A at stage 3 while B at stage 1). VexJoy has no equivalent — sequential dev runs one agent at a time to dodge file conflicts.
- **Tool-layer schema enforcement.** `agent({schema})` forces a `StructuredOutput` tool call, validates at the tool layer, auto-retries on mismatch, and returns a typed object. A non-conforming inter-agent payload structurally cannot reach the caller.
- **A first-class token budget.** `budget.total` / `budget.remaining()` with `agent()` throwing on exhaustion enables loop-until-budget scaling and a hard, run-wide cost ceiling for unattended multi-day runs.
- **Launch-time consent + admin kill-switch.** Opt-in activation, a first-run preview of what will run, and disable-via-managed-settings — governance lives in the harness, not editable prose.

## What vexjoy has that the native tool doesn't (9 months of work, credited honestly)

- **Shipped adversarial verification methodology you get for free.** A two-stage per-task review gate (ADR-compliance reviewer gates code-quality reviewer, max 3 fix retries, then human escalation), a final integration reviewer over a captured `BASE_SHA` diff — native ships zero verification content.
- **A 4-level goal-backward audit** (`EXISTS` → `SUBSTANTIVE`-not-stub → `WIRED` → `DATA-FLOW`) explicitly built to counter an executor confirming its own narrative.
- **Live browser validation in the loop.** The 14-phase quality-loop chains REVIEW, INTENT-VERIFY, LIVE-VALIDATE (real-browser Playwright), and CODEX-REVIEW (cross-model GPT second opinion) as ready-made phases.
- **A semantic-first `/do` router** over ~46 pipelines with a deterministic Python regex/scoring safety-net classifier — an always-on dispatch layer the native tool has no analog for.
- **Real, well-formed schemas and a working validator.** Draft-2020-12 schemas (verdict, severity-bucketed findings, `file:line` regex) plus `scripts/validate-review-output.py` (jsonschema, exit 0/1/2) — built and correct, even if not wired into dispatch.
- **Persistent routing telemetry.** `learning-db.py` over SQLite + FTS5 records every route decision and the outcome it produced, then reports route health, route stats, and stack usage.
- **Dense, per-action governance at the harness edge.** ~65 hooks across PreToolUse/PostToolUse/SessionStart/UserPromptSubmit/Stop, a hard `permissionDecision:deny` branch-safety gate, ADR/config-protection gates, and a data-driven org-sensitivity policy (`classify-repo.py` + `PROTECTED_ORGS`) requiring confirmation before each git action on protected repos.
- **Structured pause/resume artifacts.** `HANDOFF.json` (decisions, next_action, context_notes) + `.continue-here.md` + `.feature` lifecycle state with a priority-cascade resume that builds a human-confirmable status dashboard.

## The core insight

The deepest difference is *what holds the orchestration*: native puts control flow inside a **deterministic program a runtime executes**, so loops, gates, and fan-out are mechanical, runs are journaled, resume is cached-prefix replay, and schemas are enforced at the tool-call layer with automatic retry. VexJoy puts control flow inside **prose an LLM re-interprets each run**, so the same gates ("proceed if ≥3 of 10", "dispatch all in one message") are honored by judgment, resume is inferential re-reading of disk state, and schemas are convention an agent is merely asked to follow. VexJoy's determinism is real but lives in standalone Python *beside* the spine; native's determinism *is* the spine — that one relocation is the entire architectural delta.

## Recommendation

| Reach for... | When |
|---|---|
| **Native** | You need reproducible, journaled runs; large/long-running fan-out (hours-to-days, hundreds of agents); guaranteed typed inter-agent payloads; a hard token-budget ceiling on unattended spend; lossless resume at the exact failure point; or you want to author verification yourself but have the gating be a hard, replayable program. |
| **VexJoy** | You want strong adversarial methodology *out of the box* (two-stage gates, goal-backward stub/wiring audit, live browser + cross-model review) without designing it; an always-on router that classifies and dispatches every request; and dense per-action governance (branch-safety, ADR, org-tier confirmation) — and you accept that an LLM honors the orchestration rather than a runtime enforcing it. |
| **Both** | Use VexJoy's verification *content* as the spec for what to build, and native's runtime as the *enforcement layer* — author vexjoy's two-stage gate and 4-level audit as deterministic JS `agent()` compositions with schema-validated verdicts, turning prose the model might rationalize past into a program that mechanically blocks the next stage. |
