// toolkit-improvement.js
//
// Native dynamic-Workflow variant of the toolkit continuous-improvement pipeline.
// The markdown flow at ./toolkit-improvement.md remains the cross-harness floor;
// this script is the deterministic-runtime FAST-PATH for Claude Code (+Factory)
// when the native Workflow tool is present. It mirrors the prose 10-phase flow
// EVALUATE -> RESEARCH -> SYNTHESIZE -> CRITIQUE -> REPORT -> ADR -> IMPLEMENT ->
// VALIDATE -> REMEDIATE -> RECORD, replacing the $IMPROVE_DIR/*.md disk
// round-trips with schema-validated typed agent() returns and a real parallel()
// barrier for the mandatory multi-wave evaluation.
//
// The prose pipeline MANDATES that all agents within an evaluation wave dispatch
// in a single message for true parallelism, with Wave 1 = 10 foundation
// evaluators (the prose agent-roster.md). This workflow honors that as a FIXED
// 10-agent EVALUATE barrier of research-subagent-executor specialists (the
// static-roster shape, like comprehensive-review-workflow.js Wave 1), then runs a
// dynamic tail (research/synthesize/critique/report/adr/implement/validate/
// remediate/record) through the research-coordinator-engineer (the synthesis +
// governance owner). The prose deep-dive Wave 2 + adversarial Wave 3 scale ABOVE
// the fixed-10 floor and run as additional barriers; the ADR + IMPLEMENT fan-outs
// are one-agent-per-cluster (data-driven). REMEDIATE runs only on a validation
// regression (tier-/data-gated).
//
// Runtime contract (see ./comprehensive-review-workflow.js for the canonical
// description of the native primitives): meta is a pure object literal parsed
// before the body; parallel(thunks) is a hard barrier (failed slot -> null);
// agent({prompt, schema, model, agentType}) returns a typed object; budget.
// remaining() bounds the tail. No Date.now()/Math.random()/new Date().

import { skillDirectives, mandatoryInjections } from "./workflow-helpers.js";

export const meta = {
  name: "toolkit-improvement",
  description:
    "Toolkit continuous-improvement pipeline as a deterministic native Workflow: EVALUATE -> RESEARCH -> SYNTHESIZE -> CRITIQUE -> REPORT -> ADR -> IMPLEMENT -> VALIDATE -> REMEDIATE -> RECORD. EVALUATE is a mandatory parallel barrier of 10 research-subagent-executor foundation evaluators (distinct dimensions), scaling above the floor with tier-gated deep-dive + adversarial waves; the research-coordinator-engineer then researches ecosystem practice, synthesizes + de-dupes findings, applies skeptical critique, reports the decision surface, writes one ADR per cluster, dispatches domain implementers, validates skills against baseline, remediates regressions, and records learnings. Each agent attaches its full skill stack (one exact Skill-tool call per skill) plus the /do mandatory injections. Mirrors toolkit-improvement.md; that markdown flow stays the cross-harness floor.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stage 3). STATIC validation pins the phases + the FIXED 10-agent EVALUATE
  //     barrier (the parallel-wave mandate, countable). DYNAMIC validation records
  //     the real dispatch trace and asserts SHAPE + SKILLS, NOT count, where
  //     dynamic:true. name + description stay BEFORE this nested object so the
  //     non-greedy meta-name parser in workflow-registry.py still resolves meta.name.
  contract: {
    // Phase titles entered at runtime via enterPhase(). EVALUATE (the fixed 10-
    // agent barrier) is the first entered phase; the prose deep-dive (Wave 2) and
    // adversarial (Wave 3) evaluation waves are tier-gated phases of their own
    // (like comprehensive-review wave-2/wave-3), so the fixed-10 EVALUATE barrier
    // stays count-pinnable. The deterministic flag/scope step precedes EVALUATE.
    phases: [
      "evaluate",
      "deep-dive",
      "adversarial",
      "research",
      "synthesize",
      "critique",
      "report",
      "adr",
      "implement",
      "validate",
      "remediate",
      "record",
    ],
    // EVALUATE is a FIXED barrier: 10 research-subagent-executor foundation
    // evaluators on every run (the prose Wave 1 of 10 dimensions). Each carries a
    // `skills` LIST (the full evaluation stack attached via one exact Skill-tool call per
    // element). The distinct evaluation dimension is a RUNTIME property of the
    // prompt, not the roster shape, so the static roster is ten identical-type
    // entries (the gate pins the type + skills + count).
    roster: [
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["agent-evaluation", "verification-before-completion"] },
    ],
    // The EVALUATE barrier dispatches at least the fixed 10 on every run (static).
    agents: { static: 10, dynamic: false },
    // The deep-dive (Wave 2) + adversarial (Wave 3) waves scale the evaluation
    // ABOVE the fixed-10 floor; RESEARCH/SYNTHESIZE/CRITIQUE/REPORT/VALIDATE/
    // RECORD are single coordinator passes; ADR + IMPLEMENT fan out one agent per
    // cluster (data-driven); REMEDIATE runs only on a regression. Honest limit:
    // the gate asserts SHAPE + SKILLS for the tail, not COUNT.
    dynamic: true,
  },
};

// Map each dispatched agent to the FULL skill stack it invokes by name (one exact
// Skill-tool call per element). The foundation/deep-dive/adversarial evaluators run the
// evaluation methodology + earn the verification gate; the coordinator
// synthesizes, critiques, governs ADRs, and validates with the agent-evaluation
// + skill-eval stack. The literal skill names live in these `skills: [...]`
// arrays so the conformance gate resolves them; the body emits the directives by
// delegating each entry's list to skillDirectives().
const AGENT_SKILLS = {
  "research-subagent-executor": ["agent-evaluation", "verification-before-completion"],
  "research-coordinator-engineer": ["agent-evaluation", "skill-eval", "verification-before-completion"],
};

// The mandated minimum EVALUATE size: the prose Wave 1 of 10 foundation
// dimensions, all dispatched in one parallel barrier. Deeper runs scale ABOVE
// this floor with the deep-dive + adversarial waves, never below it.
const MIN_EVALUATE_AGENTS = 10;
const COORDINATOR_AGENT = "research-coordinator-engineer";

// The prose Wave 1 foundation dimensions (agent-roster.md). One distinct
// evaluation lens per EVALUATE agent; the fixed-10 barrier covers all of them.
const FOUNDATION_DIMENSIONS = [
  "security: injection vectors, credential exposure, path traversal, unsafe subprocess",
  "architecture: PHILOSOPHY.md adherence — determinism, progressive disclosure, router-as-orchestrator",
  "performance: hook latency (<50ms), unnecessary I/O, token-efficiency of skill/agent design",
  "testing: coverage gaps on critical paths (hooks, security scripts), test quality",
  "documentation: stale docs, references to missing files, descriptions that mismatch behavior",
  "naming: kebab-case, group-prefix consistency, inconsistent verbs across components",
  "dependencies: missing-but-used packages, broad version pins, stdlib-replaceable deps",
  "error-handling: bare except, silent swallowing, hooks that exit 2 on unexpected errors",
  "observability: stderr usefulness, CLAUDE_HOOKS_DEBUG support, meaningful exit codes",
  "type-design: missing annotations on public functions, Any overuse, TypedDict vs dict",
];

// The prose Wave 2 deep-dive lenses (scale ABOVE the fixed-10 floor).
const DEEPDIVE_DIMENSIONS = [
  "dead code: unused functions, zero-trigger skills, orphaned reference files, unreferenced agents",
  "ADR compliance: components without ADRs, Proposed-but-unimplemented, overridden decisions",
  "concurrency: unlocked shared-state access, race conditions in the hook system, learning.db access",
  "migration safety: settings.json schema breaks, skill renames, removed skills without deprecation",
  "python quality: mixed os.path/pathlib, deprecated patterns, oversized functions",
  "hook reliability: malformed-stdin handling, missing stdin timeout, exit-2-on-error fail-open",
  "script quality: missing --help, positional args, stdout/stderr misuse, missing __main__ guards",
  "pipeline coherence: artifact-over-memory, phase gates, missing interactive gates, hardcoded paths",
  "skill coverage gaps: common workflows with no skill, partial coverage, agents without skills",
  "routing correctness: dead force_routing key, missing INDEX entries, broad/narrow triggers, bad pairs_with",
];

// The prose Wave 3 adversarial lenses (challenge Wave 1+2 consensus, don't pile on).
const ADVERSARIAL_DIMENSIONS = [
  "contrarian: which findings are fine and don't need fixing; which fixes make things worse",
  "skeptical senior: which findings have concrete file:line evidence vs speculation; which risk regressions",
  "user advocate: which findings improve UX vs internal details users never see",
  "newcomer: what is confusing or undocumented; what trips up a first-time contributor",
  "meta-process auditor: are ADR creation, skill eval, learning capture actually being followed",
];

// --- Schemas (mirror the STYLE of comprehensive-review-workflow.js) -----------

// One evaluation dimension's typed finding set (mirrors a wave{N}-raw.md report).
const FINDING_SCHEMA = {
  type: "object",
  required: ["id", "severity", "description"],
  properties: {
    id: { type: "string" },
    severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
    location: { type: "string" },
    description: { type: "string" },
    proposed_fix: { type: "string" },
    confidence: { type: "string", enum: ["high", "medium", "low"] },
  },
};

const EVALUATION_SCHEMA = {
  type: "object",
  required: ["dimension", "findings"],
  properties: {
    dimension: { type: "string" },
    findings: { type: "array", items: FINDING_SCHEMA },
    clean_areas: { type: "array", items: { type: "string" } },
  },
};

// RESEARCH output: ecosystem best-practice signal (the prose research-raw.md).
const RESEARCH_SCHEMA = {
  type: "object",
  required: ["practices"],
  properties: {
    practices: {
      type: "array",
      items: {
        type: "object",
        required: ["practice", "priority"],
        properties: {
          practice: { type: "string" },
          priority: { type: "string", enum: ["high", "medium", "low"] },
          gap_vs_toolkit: { type: "string" },
        },
      },
    },
  },
};

// SYNTHESIZE output: de-duped, ranked, clustered findings (the prose
// evaluation_report.md). Each cluster becomes one ADR candidate.
const SYNTHESIS_SCHEMA = {
  type: "object",
  required: ["clusters"],
  properties: {
    clusters: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "severity"],
        properties: {
          title: { type: "string" },
          severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          agreement_count: { type: "number" },
          findings: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
};

// CRITIQUE output: a disposition per cluster (the prose critique_report.md).
const CRITIQUE_SCHEMA = {
  type: "object",
  required: ["dispositions"],
  properties: {
    dispositions: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "disposition"],
        properties: {
          title: { type: "string" },
          disposition: { type: "string", enum: ["confirm", "downgrade", "dismiss", "elevate"] },
          corrected_severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          reasoning: { type: "string" },
        },
      },
    },
  },
};

// REPORT output: the dual-column decision surface (the prose comparison_report.md).
const REPORT_SCHEMA = {
  type: "object",
  required: ["rows"],
  properties: {
    rows: {
      type: "array",
      items: {
        type: "object",
        required: ["finding", "final_severity"],
        properties: {
          finding: { type: "string" },
          original_severity: { type: "string" },
          critique_disposition: { type: "string" },
          final_severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          contested: { type: "boolean" },
        },
      },
    },
    statistics: { type: "string" },
    top_adr_candidates: { type: "array", items: { type: "string" } },
  },
};

// ADR output: one ADR descriptor per cluster (the prose adr/NNN-*.md).
const ADR_SCHEMA = {
  type: "object",
  required: ["title", "decision"],
  properties: {
    title: { type: "string" },
    context: { type: "string" },
    decision: { type: "string" },
    validation_requirements: { type: "array", items: { type: "string" } },
    components: { type: "array", items: { type: "string" } },
  },
};

// IMPLEMENT output: one implementation log per ADR (the prose impl-adr-NNN.md).
const IMPLEMENT_SCHEMA = {
  type: "object",
  required: ["adr_title", "outcome"],
  properties: {
    adr_title: { type: "string" },
    outcome: { type: "string", enum: ["implemented", "partial", "blocked"] },
    changes: { type: "array", items: { type: "string" } },
    test_results: { type: "string" },
    blocked_tasks: { type: "array", items: { type: "string" } },
  },
};

// VALIDATE output: the skill-evaluator regression gate (validation-results.md).
const VALIDATE_SCHEMA = {
  type: "object",
  required: ["verdict"],
  properties: {
    verdict: { type: "string", enum: ["pass", "regressed"] },
    results: { type: "array", items: { type: "string" } },
    regressed_skills: { type: "array", items: { type: "string" } },
  },
};

// REMEDIATE output: regression recovery (the prose remediation-*.md).
const REMEDIATE_SCHEMA = {
  type: "object",
  required: ["outcome"],
  properties: {
    outcome: { type: "string", enum: ["resolved", "escalated"] },
    fixes_applied: { type: "array", items: { type: "string" } },
    escalation_reason: { type: "string" },
  },
};

// RECORD output: captured learnings + session summary (the prose session-summary.md).
const RECORD_SCHEMA = {
  type: "object",
  required: ["summary"],
  properties: {
    summary: { type: "string" },
    learnings: { type: "array", items: { type: "string" } },
    adrs_created: { type: "number" },
    adrs_implemented: { type: "number" },
  },
};

// --- Helpers ------------------------------------------------------------------

// Defensive phase marker: the native runtime guarantees agent/parallel/budget,
// but does NOT document a phase() global. Guard the call so the real runtime
// never throws if phase is absent, while the conformance harness's mock records
// the entered phase. Phase titles match meta.contract.phases.
function enterPhase(title) {
  if (typeof phase === "function") {
    phase(title);
  }
}

// Build one evaluator's prompt for its assigned dimension + wave. skillDirectives
// emits one exact Skill-tool call per element of the research-subagent-executor stack
// (resolves path-independent inside a native Workflow agent() dispatch).
// mandatoryInjections() embeds the /do completeness/density/base-instructions/
// reference-loading block. Each evaluator gets a DISTINCT dimension and writes
// its own typed result (no shared file), mirroring the prose wave-raw.md isolation.
function evaluatorPrompt(dimension, wave, scope, priorFindings) {
  const prior = priorFindings
    ? `\nPrior-wave findings (do not duplicate; ${wave === "adversarial" ? "challenge these" : "focus on what they missed"}):\n${JSON.stringify(priorFindings)}`
    : "";
  return (
    `You are a ${wave} toolkit evaluator (research-subagent-executor).` +
    skillDirectives(AGENT_SKILLS["research-subagent-executor"]) +
    `\nYour evaluation dimension: ${dimension}.\nEvaluate this toolkit scope:\n` +
    `${JSON.stringify(scope)}\n` +
    `Report only findings you have verified by reading the actual source file. ` +
    `Each finding needs an id, severity (critical|high|medium|low), file:line ` +
    `location, description, a concrete proposed fix, and a confidence rating. ` +
    `Stay within your dimension — the coordinator synthesizes across dimensions.` +
    prior +
    mandatoryInjections()
  );
}

// Build a coordinator prompt (RESEARCH/SYNTHESIZE/CRITIQUE/REPORT/VALIDATE/
// RECORD + the ADR/IMPLEMENT/REMEDIATE fan-out tasks). Same skill stack +
// mandatory injections as a direct /do dispatch of the coordinator.
function coordinatorPrompt(task, payload) {
  return (
    task +
    skillDirectives(AGENT_SKILLS[COORDINATOR_AGENT]) +
    `\n${JSON.stringify(payload)}` +
    mandatoryInjections()
  );
}

// Dispatch one fixed-roster evaluation wave in a single parallel() barrier. The
// CALLER enters the wave's phase (with a literal title, so the static gate sees
// it) before invoking this; the harness then attributes each wave's agents to its
// own phase, keeping the fixed-10 EVALUATE barrier count-pinnable. Each dimension
// is a DISTINCT lens; failed slots resolve to null and are filtered.
async function runWave(dimensions, wave, scope, priorFindings) {
  const raw = await parallel(
    dimensions.map((dimension) => () =>
      agent({
        prompt: evaluatorPrompt(dimension, wave, scope, priorFindings),
        schema: EVALUATION_SCHEMA,
        model: "sonnet",
        agentType: "research-subagent-executor",
      }),
    ),
  );
  return raw.filter((x) => x != null);
}

// --- Workflow body ------------------------------------------------------------
//
// run({scope, tier, depth, evaluateOnly}):
//   - scope: the toolkit evaluation descriptor (target dirs + focus).
//   - tier: right-size tier from /do. tier <= 2 -> foundation wave only; tier 3
//     adds the deep-dive wave; tier 4 (or explicit deep) adds the adversarial wave.
//   - depth: explicit override — "deep" forces all three evaluation waves.
//   - evaluateOnly: stop after REPORT (the prose --evaluate-only flag).

export default async function run({ scope, tier, depth, evaluateOnly } = {}) {
  const effectiveTier = typeof tier === "number" ? tier : 4;
  const runDeepDive = depth === "deep" || effectiveTier >= 3;
  const runAdversarial = depth === "deep" || effectiveTier >= 4;
  const stopAfterReport = evaluateOnly === true;
  const minTailBudget = 8000;

  // Phase EVALUATE: the mandatory parallel barrier. The fixed 10 foundation
  // evaluators (the prose Wave 1) in one parallel() call, each on a DISTINCT
  // dimension (single-message dispatch is the prose parallelism mandate). The
  // deep-dive + adversarial waves run as their own tier-gated phases (scaling the
  // evaluation ABOVE the fixed-10 floor), so the EVALUATE barrier stays a clean
  // count-pinnable 10.
  enterPhase("evaluate");
  let findings = await runWave(FOUNDATION_DIMENSIONS, "foundation", scope, null);
  if (runDeepDive && budget.remaining() >= minTailBudget) {
    // Phase DEEP-DIVE: the prose Wave 2 — receives Wave 1 findings as context to
    // avoid duplication. Tier-gated, so its presence is honestly dynamic:true.
    enterPhase("deep-dive");
    const deep = await runWave(DEEPDIVE_DIMENSIONS, "deep-dive", scope, findings);
    findings = findings.concat(deep);
  }
  if (runAdversarial && budget.remaining() >= minTailBudget) {
    // Phase ADVERSARIAL: the prose Wave 3 — challenges Wave 1+2 consensus rather
    // than piling on. Tier-gated presence (dynamic:true).
    enterPhase("adversarial");
    const adversarial = await runWave(ADVERSARIAL_DIMENSIONS, "adversarial", scope, findings);
    findings = findings.concat(adversarial);
  }

  // Phase RESEARCH: one coordinator gathers ecosystem best-practice signal to
  // calibrate the internal findings (the prose Phase 2; advisory, never blocks).
  enterPhase("research");
  let research = null;
  if (budget.remaining() >= minTailBudget) {
    research = await agent({
      prompt: coordinatorPrompt(
        `Gather current best practices, architectural patterns, and common ` +
          `pitfalls in LLM agent frameworks and AI workflow automation. For each, ` +
          `note priority (high|medium|low) and the gap vs this toolkit. ` +
          `Evaluation scope (typed):\n`,
        scope,
      ),
      schema: RESEARCH_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase SYNTHESIZE: one coordinator de-dupes, ranks, and clusters the typed
  // findings + research into ADR candidates (the prose Phase 3).
  enterPhase("synthesize");
  let synthesis = null;
  if (findings.length > 0 && budget.remaining() >= minTailBudget) {
    synthesis = await agent({
      prompt: coordinatorPrompt(
        `De-duplicate these typed evaluation findings (merge same-issue, keep the ` +
          `most concrete description + agreement count), rank by severity then ` +
          `agreement, and group into logical clusters — each cluster is one ADR ` +
          `candidate. Integrate research-sourced gaps. Findings + research (typed):\n`,
        { findings, research },
      ),
      schema: SYNTHESIS_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase CRITIQUE: one skeptical coordinator pass — challenge every cluster
  // before any ADR is written; cut false positives, fix severity (the prose
  // Phase 4).
  enterPhase("critique");
  let critique = null;
  if (synthesis && budget.remaining() >= minTailBudget) {
    critique = await agent({
      prompt: coordinatorPrompt(
        `Challenge each finding cluster (do NOT validate). Assign one disposition ` +
          `per cluster: confirm | downgrade (corrected severity) | dismiss (cite ` +
          `evidence) | elevate (reasoning). Concrete file:line = real; "probably" = ` +
          `not. Re-rank by assessed severity. Synthesis (typed):\n`,
        synthesis,
      ),
      schema: CRITIQUE_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase REPORT: the dual-column decision surface — where evaluation + critique
  // agree and diverge (the prose Phase 5). Interactive gate: the prose pipeline
  // stops here for --evaluate-only / operator ADR approval.
  enterPhase("report");
  let report = null;
  if (synthesis && budget.remaining() >= minTailBudget) {
    report = await agent({
      prompt: coordinatorPrompt(
        `Produce the dual-column decision surface: per finding show original ` +
          `severity, critique disposition, final severity, and a contested flag ` +
          `where the critique changed the ranking. Add statistics (confirmed/` +
          `downgraded/dismissed/elevated) and the top ADR candidates. Synthesis + ` +
          `critique (typed):\n`,
        { synthesis, critique },
      ),
      schema: REPORT_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // The prose --evaluate-only flag + the Phase 5/6 interactive operator gate:
  // stop before any ADR is written when evaluateOnly is set or no report exists.
  if (stopAfterReport || report == null) {
    return {
      tier: effectiveTier,
      evaluate_only: stopAfterReport,
      evaluators_ran: findings.length,
      research,
      synthesis,
      critique,
      report,
      budget_remaining: budget.remaining(),
    };
  }

  // Phase ADR: one ADR per approved cluster, written in parallel (the prose
  // Phase 6 single-message dispatch). The cluster set is data-driven, so the
  // fan-out count is honestly covered by contract.dynamic:true.
  enterPhase("adr");
  const clusters = (synthesis && Array.isArray(synthesis.clusters)) ? synthesis.clusters : [];
  let adrs = [];
  if (clusters.length > 0 && budget.remaining() >= minTailBudget) {
    const rawAdrs = await parallel(
      clusters.map((cluster) => () =>
        agent({
          prompt: coordinatorPrompt(
            `Write one ADR for this finding cluster: context (original finding + ` +
              `critique disposition), a concrete decision/task list, concrete ` +
              `validation requirements (runnable commands + expected output), and ` +
              `the components touched. Read the referenced source before writing. ` +
              `Cluster (typed):\n`,
            cluster,
          ),
          schema: ADR_SCHEMA,
          model: "sonnet",
          agentType: COORDINATOR_AGENT,
        }),
      ),
    );
    adrs = rawAdrs.filter((x) => x != null);
  }

  // Phase IMPLEMENT: one implementer per ADR, fan out over the typed ADRs (the
  // prose Phase 7 — overlap-checked domain dispatch). Data-driven count.
  enterPhase("implement");
  let implementations = [];
  if (adrs.length > 0 && budget.remaining() >= minTailBudget) {
    const rawImpl = await parallel(
      adrs.map((adr) => () =>
        agent({
          prompt: coordinatorPrompt(
            `Implement this ADR end-to-end: read each component before editing, ` +
              `execute every decision task, run language-appropriate tests after ` +
              `each change, and report a log (outcome, changes, test results, any ` +
              `blocked tasks). Stay within the components section. ADR (typed):\n`,
            adr,
          ),
          schema: IMPLEMENT_SCHEMA,
          model: "sonnet",
          agentType: COORDINATOR_AGENT,
        }),
      ),
    );
    implementations = rawImpl.filter((x) => x != null);
  }

  // Phase VALIDATE: one coordinator runs the skill-evaluator regression gate —
  // every modified skill must meet or exceed baseline (the prose Phase 8).
  enterPhase("validate");
  let validation = null;
  if (implementations.length > 0 && budget.remaining() >= minTailBudget) {
    validation = await agent({
      prompt: coordinatorPrompt(
        `Run the skill-evaluator regression gate over the implemented changes: ` +
          `every modified skill/agent must meet or exceed its baseline score. ` +
          `Return verdict pass|regressed and the list of any regressed skills. ` +
          `Implementations (typed):\n`,
        implementations,
      ),
      schema: VALIDATE_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase REMEDIATE: regression recovery — runs ONLY when VALIDATE reports a
  // regression (the prose Phase 9, gated). Data-/tier-driven presence, so it is
  // honestly covered by contract.dynamic:true.
  enterPhase("remediate");
  let remediation = null;
  if (validation && validation.verdict === "regressed" && budget.remaining() >= minTailBudget) {
    remediation = await agent({
      prompt: coordinatorPrompt(
        `Diagnose and fix these skill regressions (max 3 cycles before escalation): ` +
          `challenge whether the change was necessary, diagnose why the score ` +
          `dropped, and recover discoverability without reverting the ADR intent. ` +
          `Return outcome resolved|escalated. Regressed skills (typed):\n`,
        validation.regressed_skills || [],
      ),
      schema: REMEDIATE_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase RECORD: capture reusable patterns into learning.db and write the
  // session summary (the prose Phase 10). One coordinator pass.
  enterPhase("record");
  let record = null;
  if (budget.remaining() >= minTailBudget) {
    record = await agent({
      prompt: coordinatorPrompt(
        `Capture the reusable patterns and successful remediations from this run ` +
          `as learning-db entries, and write a session summary (ADRs created/` +
          `implemented, validation outcome, learnings added). Run results (typed):\n`,
        { adrs, implementations, validation, remediation },
      ),
      schema: RECORD_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  return {
    tier: effectiveTier,
    evaluate_only: false,
    evaluators_ran: findings.length,
    deep_dive_ran: runDeepDive,
    adversarial_ran: runAdversarial,
    research,
    synthesis,
    critique,
    report,
    adrs_created: adrs.length,
    implementations_ran: implementations.length,
    validation,
    remediation,
    record,
    budget_remaining: budget.remaining(),
  };
}
