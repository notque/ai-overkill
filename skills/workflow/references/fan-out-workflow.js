// fan-out-workflow.js
//
// Generic, parameterized native fan-out/synthesize Workflow. This is the
// default deterministic-runtime executor for Complex / tier-4 work that has NO
// named pipeline (a `pick=null` complexity-trigger from /do Phase 4 Step 1b).
// Unlike comprehensive-review-workflow.js (a STATIC Wave-1 roster + dynamic
// tail), this workflow's roster is supplied ENTIRELY by the caller — there are
// no fixed agent/skill literals in source. The prose `dispatching-parallel-
// agents` flow is the always-safe floor when the Workflow tool is absent.
//
// Runtime contract (see ../../../dynamic-workflows-vs-vexjoy-diff.md):
//   - meta is a pure object literal (name + description + contract) parsed
//     before the body.
//   - parallel(thunks) is a hard barrier; a failed agent resolves to null.
//   - agent({prompt, schema, model, agentType}) forces a StructuredOutput tool
//     call, validates against schema at the tool layer, and returns a typed
//     object — no markdown re-parse, no disk read.
//   - budget.remaining() returns run-wide tokens left; agent() throws when
//     exhausted. The synthesize pass is budget-aware (no unbounded loop).
//   - Wall-clock and randomness are unavailable by design (determinism is
//     bit-stable across replay). This script uses neither.

import {
  mandatoryInjections,
  skillDirectives,
  validateAgentName,
  validateRoster,
} from "./workflow-helpers.js";

export const meta = {
  name: "fan-out-workflow",
  description:
    "Generic native fan-out/synthesize Workflow for Complex / tier-4 work with no named pipeline: dispatch a caller-supplied roster of specialists in a single parallel barrier (each attaching its FULL skill stack by name via one exact Skill-tool call per skill, plus the /do mandatory injections), then synthesize the typed worker results in-memory with one budget-aware synthesizer. The roster, skills, lenses, and synthesizer are all caller-supplied — the floor is the prose dispatching-parallel-agents flow.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stage 2). This is a FULLY-DYNAMIC-roster contract: the roster is
  //     caller-supplied, so there are NO static agent/skill literals to pin.
  //     The gate asserts the STRUCTURAL invariant (source emits an exact Skill-tool
  //     call derived from a roster variable AND dispatches agentType from a
  //     roster variable), NOT specific names. name + description stay BEFORE this
  //     nested object so the non-greedy meta-name parser in workflow-registry.py
  //     still resolves meta.name.
  contract: {
    // Phase titles this script enters at runtime via enterPhase(). Order matters.
    phases: ["fan-out", "synthesize"],
    // Fully-dynamic roster: caller-supplied at run({roster}). No static names to
    // pin — the gate asserts the structural invariant instead.
    roster: { dynamic: true },
    // No static barrier to count: every dispatched agent comes from the runtime
    // roster (roster.length workers + 1 synthesizer).
    agents: { dynamic: true },
    // Data-driven fan-out: count + names are caller-supplied (honest limit — the
    // gate asserts SHAPE + the structural Skill-tool-call/agentType invariant, NOT COUNT).
    dynamic: true,
  },
};

// --- Schemas (mirror the STYLE of comprehensive-review-workflow.js / -----------
//     skills/shared-patterns/schemas/). Worker results and the synthesis are
//     schema-validated typed objects, not re-parsed markdown.

// One worker's typed output. `findings` mirrors the FINDING/WAVE_OUTPUT shape so
// downstream synthesis is uniform regardless of the worker's lens.
const FINDING_SCHEMA = {
  type: "object",
  required: ["title"],
  properties: {
    title: { type: "string" },
    location: { type: "string" },
    severity: { type: "string", enum: ["critical", "high", "medium", "low", "info"] },
    detail: { type: "string" },
  },
};

const WORKER_SCHEMA = {
  type: "object",
  required: ["verdict", "summary"],
  properties: {
    verdict: { type: "string", enum: ["PASS", "CONCERN", "BLOCK", "INFO"] },
    summary: { type: "string", minLength: 1 },
    findings: { type: "array", items: FINDING_SCHEMA },
    lens: { type: "string" },
  },
};

// The single synthesizer's typed output over the worker results.
const SYNTH_SCHEMA = {
  type: "object",
  required: ["verdict", "summary"],
  properties: {
    verdict: { type: "string", enum: ["PASS", "CONCERN", "BLOCK", "INFO"] },
    summary: { type: "string", minLength: 1 },
    key_findings: { type: "array", items: FINDING_SCHEMA },
    recommendations: { type: "array", items: { type: "string" } },
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

// Build one worker's prompt from its roster entry. The roster entry supplies the
// dispatched specialist (agentType), the FULL skill stack it attaches by name
// (one exact Skill-tool call per element of r.skills — resolves path-independent inside a
// native Workflow agent() dispatch, proven this session), and the lens that
// focuses its pass. `scope` is the shared diff/task descriptor. The Skill
// directives are built FROM the roster variable r.skills — this is the fully-
// dynamic structural invariant the conformance gate asserts. Every prompt also
// embeds the /do mandatory injections (completeness/density/base-instructions/
// reference-loading) so a workflow agent gets the same context as a direct /do
// dispatch.
function workerPrompt(r, scope) {
  const lens = r.lens ? `Apply this lens: ${r.lens}.` : "Apply your specialist lens.";
  return (
    `You are ${r.agentType}. ${lens}` +
    skillDirectives(r.skills) +
    `\nWork this scope:\n${JSON.stringify(scope)}\n` +
    `Return a typed result: verdict (PASS|CONCERN|BLOCK|INFO), a summary, and any ` +
    `findings within your lens. Stay within your lens — the synthesizer merges across workers.` +
    mandatoryInjections()
  );
}

// --- Workflow body ------------------------------------------------------------
//
// run({scope, tier, roster, synthAgentType, fixThreshold}):
//   - scope: the shared task/diff descriptor passed to every worker.
//   - tier: right-size-review tier (carried into scope for the workers; this
//     workflow does not gate phases on tier — the CALLER sizes the roster).
//   - roster: [{agentType, skills, lens}] — caller-supplied; the fan-out set.
//     `skills` is a LIST (the full /do Phase-3 stack), one exact Skill-tool call per element.
//   - synthAgentType: the synthesizer agent (default a general synthesizer).
//   - fixThreshold: min budget to attempt the synthesis pass (default 8000).

export default async function run({ scope, tier, roster, synthAgentType, fixThreshold } = {}) {
  // Validate the complete caller-supplied dispatch plan before entering a phase
  // or invoking agent(), so one bad name rejects the whole fan-out.
  const workers = validateRoster(roster, "roster");
  // Default general synthesizer: research-coordinator-engineer (its role is
  // multi-source synthesis). The caller overrides via synthAgentType.
  const synthesizer = validateAgentName(
    synthAgentType || "research-coordinator-engineer",
    "synthAgentType",
  );
  const minSynthBudget = typeof fixThreshold === "number" ? fixThreshold : 8000;

  // Phase fan-out: one hard barrier over the caller-supplied roster. Each slot
  // dispatches the roster's specialist via agentType (a runtime variable) and
  // embeds one exact Skill-tool call per element of r.skills (the full stack) plus
  // the /do mandatory injections. A failed slot resolves to null; nulls are
  // filtered before synthesis.
  enterPhase("fan-out");
  const rawResults = await parallel(
    workers.map((r) => () =>
      agent({
        prompt: workerPrompt(r, scope),
        schema: WORKER_SCHEMA,
        model: "sonnet",
        agentType: r.agentType,
        phase: "fan-out",
      }),
    ),
  );
  const results = rawResults.filter((x) => x != null);

  // Phase synthesize: one synthesizer over the typed worker results in-memory
  // (no disk). Budget-aware — skip the pass if the run can no longer afford it,
  // and report the workers directly rather than looping unboundedly.
  enterPhase("synthesize");
  let synthesis = null;
  if (results.length > 0 && budget.remaining() >= minSynthBudget) {
    synthesis = await agent({
      prompt:
        `Synthesize these ${results.length} typed specialist results into one ` +
        `verdict + summary. Merge overlapping findings, keep the highest severity, ` +
        `and list concrete recommendations. Results (typed, in-memory):\n` +
        `${JSON.stringify(results)}`,
      schema: SYNTH_SCHEMA,
      model: "sonnet",
      agentType: synthesizer,
      phase: "synthesize",
    });
  }

  return {
    tier: typeof tier === "number" ? tier : null,
    workers_ran: results.length,
    roster: workers.map((r) => ({ agentType: r.agentType, skills: r.skills, lens: r.lens })),
    synthesis,
    budget_remaining: budget.remaining(),
  };
}
