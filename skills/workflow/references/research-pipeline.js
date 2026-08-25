// research-pipeline.js
//
// Native dynamic-Workflow variant of the formal research pipeline. The markdown
// flow at ./research-pipeline.md remains the cross-harness floor; this script is
// the deterministic-runtime FAST-PATH for Claude Code (+Factory) when the native
// Workflow tool is present. It mirrors the prose GATHER -> SYNTHESIZE -> VALIDATE
// -> DELIVER agent flow, replacing the research/{topic}/*.md disk round-trips
// with schema-validated typed agent() returns and a real parallel() barrier for
// the mandatory multi-agent gather.
//
// The prose pipeline MANDATES a minimum of 3 parallel research agents (sequential
// research is forbidden — A/B-validated). This workflow honors that as a FIXED
// 3-agent GATHER barrier of research-subagent-executor specialists (the
// static-roster shape, like comprehensive-review-workflow.js Wave 1), then runs a
// dynamic SYNTHESIZE/VALIDATE/DELIVER tail through the research-coordinator-
// engineer (the prose pipeline's owning agent). The prose SCOPE phase is a
// deterministic decision step (angle + depth selection from a fixed table), so it
// runs in-body before the barrier — no LLM round-trip (PHILOSOPHY: everything
// deterministic should be).
//
// Runtime contract (see ./comprehensive-review-workflow.js for the canonical
// description of the native primitives): meta is a pure object literal parsed
// before the body; parallel(thunks) is a hard barrier (failed slot -> null);
// agent({prompt, schema, model, agentType}) returns a typed object; budget.
// remaining() bounds the tail. No Date.now()/Math.random()/new Date().

import { skillDirectives, mandatoryInjections } from "./workflow-helpers.js";

export const meta = {
  name: "research-pipeline",
  description:
    "Formal research pipeline as a deterministic native Workflow: a deterministic scope step then GATHER -> SYNTHESIZE -> VALIDATE -> DELIVER. GATHER is a mandatory parallel barrier of >=3 research-subagent-executor specialists (distinct angles, no shared file), each attaching its full skill stack (one exact Skill-tool call per skill) plus the /do mandatory injections; the research-coordinator-engineer then synthesizes the typed findings in-memory, runs a source-quality VALIDATE gate, and DELIVERs the report. Mirrors research-pipeline.md; that markdown flow stays the cross-harness floor.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stage 3). STATIC validation pins the phases + the FIXED 3-agent GATHER
  //     barrier (the parallel-agents mandate, countable). DYNAMIC validation
  //     records the real dispatch trace and asserts SHAPE + SKILLS, NOT count,
  //     where dynamic:true. name + description stay BEFORE this nested object so
  //     the non-greedy meta-name parser in workflow-registry.py still resolves
  //     meta.name.
  contract: {
    // Phase titles entered at runtime via enterPhase(). GATHER (the barrier) is
    // the first entered phase; the deterministic scope step precedes it in-body.
    phases: ["gather", "synthesize", "validate", "deliver"],
    // GATHER is a FIXED barrier: 3 research-subagent-executor agents on every run
    // (the minimum-3 mandate from the prose pipeline). Each carries a `skills` LIST
    // (the full stack attached via one exact Skill-tool call per element). Distinct angles are a
    // RUNTIME property of the prompt, not the roster shape, so the static roster is
    // three identical-type entries (the gate pins the type + skills + count).
    roster: [
      { agentType: "research-subagent-executor", skills: ["research-pipeline", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["research-pipeline", "verification-before-completion"] },
      { agentType: "research-subagent-executor", skills: ["research-pipeline", "verification-before-completion"] },
    ],
    // The GATHER barrier dispatches at least the fixed 3 on every run (static).
    agents: { static: 3, dynamic: false },
    // SYNTHESIZE/VALIDATE/DELIVER are single coordinator passes, and GATHER can
    // scale ABOVE 3 angles for deeper requests (depth setting) — the count beyond
    // the fixed-3 floor is data-driven. Honest limit: the gate asserts SHAPE +
    // SKILLS for the tail, not COUNT.
    dynamic: true,
  },
};

// Map each dispatched agent to the FULL skill stack it invokes by name (one exact
// Skill-tool call per element). research-subagent-executor runs the research methodology
// and earns the source-quality verification gate; the coordinator synthesizes,
// validates, and delivers with the same stack. The literal skill names live in
// these `skills: [...]` arrays so the conformance gate resolves them; the body
// emits the directives by delegating each entry's list to skillDirectives().
const AGENT_SKILLS = {
  "research-subagent-executor": ["research-pipeline", "verification-before-completion"],
  "research-coordinator-engineer": ["research-pipeline", "verification-before-completion"],
};

// The mandated minimum gather size; a deeper request scales angles ABOVE this
// floor (the prose depth setting), never below it.
const MIN_GATHER_AGENTS = 3;
const COORDINATOR_AGENT = "research-coordinator-engineer";

// Default research angles (mirrors the prose angle table). One distinct angle per
// gather agent; deeper depth adds more from the tail of this list.
const DEFAULT_ANGLES = [
  "current-state",
  "tradeoffs",
  "expert-opinions",
  "alternatives",
  "technical-details",
];

// --- Schemas (mirror the STYLE of comprehensive-review-workflow.js) -----------

// One angle's raw research output. Findings carry an evidence-strength note so
// SYNTHESIZE can rate consensus vs single-source (the prose Strong/Moderate/Weak
// gate). Mirrors the raw-{angle}.md structure as a typed object.
const CLAIM_SCHEMA = {
  type: "object",
  required: ["claim", "evidence"],
  properties: {
    claim: { type: "string" },
    evidence: { type: "string", enum: ["strong", "moderate", "weak"] },
    source: { type: "string" },
  },
};

const RAW_RESEARCH_SCHEMA = {
  type: "object",
  required: ["angle", "claims"],
  properties: {
    angle: { type: "string" },
    claims: { type: "array", items: CLAIM_SCHEMA },
    gaps: { type: "array", items: { type: "string" } },
    sources: { type: "array", items: { type: "string" } },
  },
};

// SYNTHESIZE output: consensus findings, contradictions, open gaps — the prose
// synthesis.md as a typed object.
const SYNTHESIS_SCHEMA = {
  type: "object",
  required: ["findings"],
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "evidence_quality"],
        properties: {
          title: { type: "string" },
          evidence_quality: { type: "string", enum: ["strong", "moderate", "weak"] },
          summary: { type: "string" },
        },
      },
    },
    contradictions: { type: "array", items: { type: "string" } },
    open_gaps: { type: "array", items: { type: "string" } },
  },
};

// VALIDATE output: the prose Quality Assessment + research verdict gate.
const VALIDATION_SCHEMA = {
  type: "object",
  required: ["verdict"],
  properties: {
    verdict: { type: "string", enum: ["sufficient", "partial", "insufficient"] },
    coverage: { type: "string" },
    bias_flags: { type: "array", items: { type: "string" } },
    flagged_weak_findings: { type: "array", items: { type: "string" } },
  },
};

// DELIVER output: the final report descriptor (the prose report.md).
const REPORT_SCHEMA = {
  type: "object",
  required: ["executive_summary"],
  properties: {
    executive_summary: { type: "array", items: { type: "string" } },
    detailed_findings: { type: "string" },
    sources: { type: "array", items: { type: "string" } },
    limitations: { type: "array", items: { type: "string" } },
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

// Build one gather agent's prompt for its assigned angle. skillDirectives emits
// one exact Skill-tool call per element of the research-subagent-executor skill stack
// (resolves path-independent inside a native Workflow agent() dispatch).
// mandatoryInjections() embeds the /do completeness/density/base-instructions/
// reference-loading block so a workflow agent gets the same context as a direct
// /do dispatch. Each agent gets a DISTINCT angle and writes its own typed result
// (no shared file), mirroring the prose raw-{angle}.md isolation that preserves
// distinct perspectives.
function gatherPrompt(angle, scope) {
  return (
    `You are the "${angle}" research agent (research-subagent-executor).` +
    skillDirectives(AGENT_SKILLS["research-subagent-executor"]) +
    `\nYour angle: investigate the "${angle}" dimension of this research scope:\n` +
    `${JSON.stringify(scope)}\n` +
    `Return ONLY findings within your angle. Rate each claim's evidence strength ` +
    `(strong|moderate|weak); "strong" requires specific independent sources, not ` +
    `just agreement. List the gaps you could not fill and the sources you used. ` +
    `Stay within your angle — the coordinator synthesizes across angles.` +
    mandatoryInjections()
  );
}

// Build a coordinator prompt (SYNTHESIZE/VALIDATE/DELIVER). Same skill stack +
// mandatory injections as a direct /do dispatch of the coordinator.
function coordinatorPrompt(task, payload) {
  return (
    task +
    skillDirectives(AGENT_SKILLS[COORDINATOR_AGENT]) +
    `\n${JSON.stringify(payload)}` +
    mandatoryInjections()
  );
}

// Build the angle list for this run: the fixed-3 floor (quick/standard), scaled
// up only for `deep` (the prose depth setting allows 3-5 angles). Deterministic —
// no LLM round-trip needed to scope. The default/standard path dispatches exactly
// the mandated 3 (matching the static contract roster); `deep` scales above it
// (honestly covered by contract.dynamic:true).
function anglesForDepth(depth) {
  const count = depth === "deep" ? 5 : MIN_GATHER_AGENTS;
  return DEFAULT_ANGLES.slice(0, count);
}

// --- Workflow body ------------------------------------------------------------
//
// run({scope, tier, depth}):
//   - scope: the research descriptor (primary question + sub-questions + source
//     types). Passed to every gather agent and into synthesis.
//   - tier: right-size tier (carried through; this pipeline scales angles by
//     `depth`, the prose pipeline's own dial, not by review tier).
//   - depth: quick | standard | deep — scales the gather angle count ABOVE the
//     mandated 3. Default standard.

export default async function run({ scope, tier, depth } = {}) {
  const effectiveDepth = typeof depth === "string" ? depth : "standard";
  const minTailBudget = 8000;

  // SCOPE (deterministic, in-body): select the distinct angles + depth from the
  // prose decision table. No agent dispatch — scoping is a deterministic choice.
  const angles = anglesForDepth(effectiveDepth);

  // Phase GATHER: the mandatory parallel barrier. At LEAST 3 research-subagent-
  // executor agents, each on a DISTINCT angle, dispatched in one parallel() call
  // (sequential research is forbidden by the prose pipeline). Failed slots resolve
  // to null and are filtered; the barrier never drops below the mandated floor.
  enterPhase("gather");
  const rawResults = await parallel(
    angles.map((angle) => () =>
      agent({
        prompt: gatherPrompt(angle, scope),
        schema: RAW_RESEARCH_SCHEMA,
        model: "sonnet",
        agentType: "research-subagent-executor",
      }),
    ),
  );
  const raw = rawResults.filter((x) => x != null);

  // Phase SYNTHESIZE: one coordinator over the typed raw results in-memory (no
  // disk). Identifies consensus, contradictions, gaps; rates evidence quality.
  enterPhase("synthesize");
  let synthesis = null;
  if (raw.length > 0 && budget.remaining() >= minTailBudget) {
    synthesis = await agent({
      prompt: coordinatorPrompt(
        `Synthesize these ${raw.length} typed per-angle research results into ` +
          `consensus findings, contradictions, and open gaps. Rate each finding's ` +
          `evidence quality (strong only when backed by specific independent ` +
          `sources, not mere agreement). Raw results (typed, in-memory):\n`,
        raw,
      ),
      schema: SYNTHESIS_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase VALIDATE: source-quality + coverage + bias gate before delivery (the
  // prose Phase 4 quality assessment). One coordinator pass over the synthesis.
  enterPhase("validate");
  let validation = null;
  if (synthesis && budget.remaining() >= minTailBudget) {
    validation = await agent({
      prompt: coordinatorPrompt(
        `Run the research-quality gate over this synthesis: confirm "strong" ` +
          `findings are backed by specific independent sources (not shared bias), ` +
          `flag load-bearing weak findings, assess source diversity, and return a ` +
          `verdict (sufficient|partial|insufficient). Synthesis (typed):\n`,
        synthesis,
      ),
      schema: VALIDATION_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase DELIVER: the final formatted report (the prose report.md), built from
  // the validated synthesis. One coordinator pass.
  enterPhase("deliver");
  let report = null;
  if (synthesis && budget.remaining() >= minTailBudget) {
    report = await agent({
      prompt: coordinatorPrompt(
        `Produce the final research report from the validated synthesis: an ` +
          `executive summary (3-5 bullets), detailed findings per angle with ` +
          `sources, and explicit gaps/limitations. Synthesis + validation (typed):\n`,
        { synthesis, validation },
      ),
      schema: REPORT_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  return {
    depth: effectiveDepth,
    tier: typeof tier === "number" ? tier : null,
    angles,
    gather_agents_ran: raw.length,
    synthesis,
    validation,
    report,
    budget_remaining: budget.remaining(),
  };
}
