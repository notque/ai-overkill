// explore-pipeline.js
//
// Native dynamic-Workflow variant of the systematic codebase-exploration
// pipeline. The markdown flow at ./explore-pipeline.md remains the cross-harness
// floor; this script is the deterministic-runtime FAST-PATH for Claude Code
// (+Factory) when the native Workflow tool is present. It mirrors the prose
// tiered flow SCAN -> MAP -> ANALYZE -> (COMPILE -> ASSESS -> SYNTHESIZE ->
// REFINE) -> REPORT, replacing the per-phase *.md disk artifacts with schema-
// validated typed agent() returns and a real parallel() barrier for the SCAN
// fan-out. It is READ-ONLY (the dispatched specialists explore, never modify).
//
// Tiered depth (the prose Quick/Standard/Deep model) maps to the right-size
// review tier carried in by /do: tier <= 3 runs the Standard set (SCAN, MAP,
// ANALYZE, REPORT — 4 phases); tier 4 runs the Deep set (all 8 phases, adding
// COMPILE, ASSESS, SYNTHESIZE, REFINE for quality assessment + false-positive
// verification before REPORT). Phases within the selected tier are not skipped.
//
// SCAN is a FIXED barrier of 3 read-only scanner specialists (Structure, Entry
// Point, Pattern — the prose Phase 1), the static-roster shape (like
// comprehensive-review-workflow.js Wave 1). MAP/ANALYZE/.../REPORT are single
// coordinator passes; their presence is tier-gated (data-driven), so the tail is
// declared dynamic:true (honest limit).
//
// Runtime contract (see ./comprehensive-review-workflow.js for the canonical
// description of the native primitives): meta is a pure object literal parsed
// before the body; parallel(thunks) is a hard barrier (failed slot -> null);
// agent({prompt, schema, model, agentType}) returns a typed object; budget.
// remaining() bounds the tail. No Date.now()/Math.random()/new Date().

import { skillDirectives, mandatoryInjections } from "./workflow-helpers.js";

export const meta = {
  name: "explore-pipeline",
  description:
    "Systematic codebase-exploration pipeline as a deterministic native Workflow: tiered SCAN -> MAP -> ANALYZE -> (COMPILE -> ASSESS -> SYNTHESIZE -> REFINE) -> REPORT. SCAN is a fixed parallel barrier of 3 read-only scanner specialists (Structure, Entry Point, Pattern); a codebase coordinator then maps architecture, analyzes core abstractions, and (at deep tier) compiles, assesses quality, synthesizes ranked findings, and verifies them against source before REPORT. Each agent attaches its full skill stack (one exact Skill-tool call per skill) plus the /do mandatory injections. Read-only. Mirrors explore-pipeline.md; that markdown flow stays the cross-harness floor.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stage 3). STATIC validation pins the phases + the FIXED 3-scanner SCAN
  //     barrier (countable). DYNAMIC validation records the real dispatch trace
  //     and asserts SHAPE + SKILLS, NOT count, where dynamic:true (the tier-gated
  //     tail phases run conditionally). name + description stay BEFORE this nested
  //     object so the non-greedy meta-name parser in workflow-registry.py still
  //     resolves meta.name.
  contract: {
    // All phase titles entered at runtime via enterPhase(). SCAN (the barrier) is
    // the first entered phase. Tier-gated phases still have a literal enterPhase()
    // call-site in source (the STATIC check is set-equality of titles), but only
    // run at the selected tier (the DYNAMIC check is per-tier subset).
    phases: ["scan", "map", "analyze", "compile", "assess", "synthesize", "refine", "report"],
    // SCAN is a FIXED barrier: 3 read-only scanner specialists on every run (the
    // prose Phase 1 Structure/Entry-Point/Pattern scanners). Each carries a
    // `skills` LIST (the full read-only-exploration stack attached via one exact Skill-tool call
    // per element). The distinct scanner lens is a RUNTIME property of the prompt,
    // so the static roster is three identical-type entries (type + skills + count).
    roster: [
      { agentType: "research-subagent-executor", skills: ["codebase-overview"] },
      { agentType: "research-subagent-executor", skills: ["codebase-overview"] },
      { agentType: "research-subagent-executor", skills: ["codebase-overview"] },
    ],
    // The SCAN barrier dispatches exactly the fixed 3 on every run (static).
    agents: { static: 3, dynamic: false },
    // MAP/ANALYZE/.../REPORT are single coordinator passes whose PRESENCE is
    // tier-gated (Standard = 4 phases, Deep = 8). The tail count is data-driven.
    // Honest limit: the gate asserts SHAPE + SKILLS for the tail, not COUNT.
    dynamic: true,
  },
};

// Map each dispatched agent to the FULL skill stack it invokes by name (one exact
// Skill-tool call per element). The read-only scanners + the coordinator both run the
// codebase-overview methodology: structure/architecture plus its promoted
// pattern/quality analysis references. The literal skill names live in
// these `skills: [...]` arrays so the conformance gate resolves them; the body
// emits the directives by delegating each entry's list to skillDirectives().
const AGENT_SKILLS = {
  "research-subagent-executor": ["codebase-overview"],
  "research-coordinator-engineer": ["codebase-overview"],
};

const COORDINATOR_AGENT = "research-coordinator-engineer";

// The three fixed SCAN scanners (the prose Phase 1). Each is a distinct read-only
// lens dispatched in one parallel barrier; minimum 2-of-3 is the prose gate, but
// all 3 are dispatched (failed slots resolve to null and are filtered).
const SCANNERS = [
  { lens: "Structure: top-level directories + purposes, languages/frameworks, config (build/CI/lint/env), test layout, infra files" },
  { lens: "Entry points: main executables, CLI arg parsers, API route definitions + server startup, worker/queue entry points (file paths + brief descriptions)" },
  { lens: "Patterns: naming conventions, directory organization, import/dependency patterns, error-handling approach, testing patterns + coverage strategy" },
];

// --- Schemas (mirror the STYLE of comprehensive-review-workflow.js) -----------

// One scanner's typed output (mirrors a raw scan finding-set).
const SCAN_SCHEMA = {
  type: "object",
  required: ["lens", "observations"],
  properties: {
    lens: { type: "string" },
    observations: { type: "array", items: { type: "string" } },
    file_paths: { type: "array", items: { type: "string" } },
  },
};

// MAP output: the architecture map (layers + component relationships + data flow).
const MAP_SCHEMA = {
  type: "object",
  required: ["layers"],
  properties: {
    layers: { type: "array", items: { type: "string" } },
    components: {
      type: "array",
      items: {
        type: "object",
        required: ["name"],
        properties: {
          name: { type: "string" },
          depends_on: { type: "array", items: { type: "string" } },
          dependents: { type: "array", items: { type: "string" } },
        },
      },
    },
    data_flow: { type: "string" },
  },
};

// ANALYZE output: core abstractions, critical paths, conventions.
const ANALYZE_SCHEMA = {
  type: "object",
  required: ["abstractions"],
  properties: {
    abstractions: { type: "array", items: { type: "string" } },
    critical_paths: { type: "array", items: { type: "string" } },
    conventions: { type: "array", items: { type: "string" } },
  },
};

// COMPILE output: findings grouped by evaluation dimension (deep tier).
const COMPILE_SCHEMA = {
  type: "object",
  required: ["dimensions"],
  properties: {
    dimensions: {
      type: "array",
      items: {
        type: "object",
        required: ["dimension"],
        properties: {
          dimension: { type: "string", enum: ["consistency", "quality", "coverage", "patterns"] },
          findings: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
};

// ASSESS output: scored dimensions + cataloged deviations (deep tier).
const ASSESS_SCHEMA = {
  type: "object",
  required: ["scores"],
  properties: {
    scores: { type: "array", items: { type: "string" } },
    deviations: {
      type: "array",
      items: {
        type: "object",
        required: ["description", "severity"],
        properties: {
          description: { type: "string" },
          severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          root_cause: { type: "string" },
        },
      },
    },
  },
};

// SYNTHESIZE output: ranked, theme-grouped recommendations (deep tier).
const SYNTHESIZE_SCHEMA = {
  type: "object",
  required: ["recommendations"],
  properties: {
    recommendations: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "severity"],
        properties: {
          title: { type: "string" },
          severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          theme: { type: "string" },
        },
      },
    },
  },
};

// REFINE output: verified findings with false positives removed (deep tier).
const REFINE_SCHEMA = {
  type: "object",
  required: ["verified"],
  properties: {
    verified: { type: "array", items: { type: "string" } },
    removed_false_positives: { type: "array", items: { type: "string" } },
  },
};

// REPORT output: the final exploration report descriptor.
const REPORT_SCHEMA = {
  type: "object",
  required: ["executive_summary"],
  properties: {
    executive_summary: { type: "string", minLength: 1 },
    quick_facts: { type: "array", items: { type: "string" } },
    key_components: { type: "array", items: { type: "string" } },
    next_steps: { type: "array", items: { type: "string" } },
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

// Build one SCAN scanner's prompt for its read-only lens. skillDirectives emits
// one exact Skill-tool call per element of the scanner skill stack (resolves path-
// independent inside a native Workflow agent() dispatch). mandatoryInjections()
// embeds the /do completeness/density/base-instructions/reference-loading block.
// Each scanner gets a DISTINCT lens and returns its own typed result.
function scanPrompt(lens, scope) {
  return (
    `You are a read-only codebase scanner (research-subagent-executor). Explore ` +
    `and report only; leave all files unchanged.` +
    skillDirectives(AGENT_SKILLS["research-subagent-executor"]) +
    `\nYour scanner lens: ${lens}.\nExplore this scope:\n${JSON.stringify(scope)}\n` +
    `Return typed observations with concrete file paths as evidence. Stay within ` +
    `your lens — the coordinator maps and analyzes across scanners.` +
    mandatoryInjections()
  );
}

// Build a coordinator prompt (MAP/ANALYZE/COMPILE/ASSESS/SYNTHESIZE/REFINE/
// REPORT). Same skill stack + mandatory injections as a direct /do dispatch of
// the coordinator. Read-only: the coordinator reasons over evidence, never edits.
function coordinatorPrompt(task, payload) {
  return (
    task +
    skillDirectives(AGENT_SKILLS[COORDINATOR_AGENT]) +
    `\n${JSON.stringify(payload)}` +
    mandatoryInjections()
  );
}

// --- Workflow body ------------------------------------------------------------
//
// run({scope, tier, deep}):
//   - scope: the exploration descriptor (target repo/subsystem + focus).
//   - tier: right-size tier from /do. tier <= 3 -> Standard (4 phases); tier 4 ->
//     Deep (all 8). The prose Quick/Standard/Deep model mapped onto the tier dial.
//   - deep: explicit override — force the Deep 8-phase set regardless of tier.

export default async function run({ scope, tier, deep } = {}) {
  const effectiveTier = typeof tier === "number" ? tier : 2;
  const runDeep = deep === true || effectiveTier >= 4;
  const minTailBudget = 8000;

  // Phase SCAN: the fixed parallel barrier of 3 read-only scanners (Structure,
  // Entry Point, Pattern). Dispatched in one parallel() call; failed slots resolve
  // to null and are filtered (the prose minimum-2-of-3 gate). This is the static
  // barrier the contract pins.
  enterPhase("scan");
  const rawScans = await parallel(
    SCANNERS.map((s) => () =>
      agent({
        prompt: scanPrompt(s.lens, scope),
        schema: SCAN_SCHEMA,
        model: "sonnet",
        agentType: "research-subagent-executor",
      }),
    ),
  );
  const scans = rawScans.filter((x) => x != null);

  // Phase MAP: one coordinator builds the architecture map from the scan findings.
  enterPhase("map");
  let architectureMap = null;
  if (scans.length > 0 && budget.remaining() >= minTailBudget) {
    architectureMap = await agent({
      prompt: coordinatorPrompt(
        `Build an architecture map from these parallel scanner findings: identify ` +
          `layers, component relationships (depends_on/dependents), and data flow. ` +
          `Scanner findings (typed, in-memory):\n`,
        scans,
      ),
      schema: MAP_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase ANALYZE: deep investigation of core abstractions + critical paths +
  // conventions, grounded in the architecture map.
  enterPhase("analyze");
  let analysis = null;
  if (architectureMap && budget.remaining() >= minTailBudget) {
    analysis = await agent({
      prompt: coordinatorPrompt(
        `Analyze the key components from this architecture map: single ` +
          `responsibility + patterns per abstraction, trace the critical execution ` +
          `paths end-to-end, and document the implicit conventions. Map + scans ` +
          `(typed):\n`,
        { architectureMap, scans },
      ),
      schema: ANALYZE_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  // Deep-tier quality limb: COMPILE -> ASSESS -> SYNTHESIZE -> REFINE. These run
  // ONLY at the Deep tier (the prose Phases 4-7). Their presence is tier-gated, so
  // the contract declares the tail dynamic:true (honest limit — not count-checked).
  let compilation = null;
  let assessment = null;
  let synthesis = null;
  let refinement = null;
  if (runDeep && analysis) {
    // Phase COMPILE: structure raw findings into evaluation dimensions.
    enterPhase("compile");
    if (budget.remaining() >= minTailBudget) {
      compilation = await agent({
        prompt: coordinatorPrompt(
          `Compile the exploration findings into the evaluation dimensions ` +
            `(consistency, quality, coverage, patterns) with per-component data. ` +
            `Analysis + map (typed):\n`,
          { analysis, architectureMap },
        ),
        schema: COMPILE_SCHEMA,
        model: "sonnet",
        agentType: COORDINATOR_AGENT,
      });
    }

    // Phase ASSESS: score each dimension; catalog deviations with root causes.
    enterPhase("assess");
    if (compilation && budget.remaining() >= minTailBudget) {
      assessment = await agent({
        prompt: coordinatorPrompt(
          `Score each evaluation dimension (compliance %, outliers), and catalog ` +
            `each deviation with severity (critical|high|medium|low) and root ` +
            `cause (intentional vs drift). Compiled dimensions (typed):\n`,
          compilation,
        ),
        schema: ASSESS_SCHEMA,
        model: "sonnet",
        agentType: COORDINATOR_AGENT,
      });
    }

    // Phase SYNTHESIZE: rank findings by impact; group by theme.
    enterPhase("synthesize");
    if (assessment && budget.remaining() >= minTailBudget) {
      synthesis = await agent({
        prompt: coordinatorPrompt(
          `Rank the assessed deviations by severity and group them into themes ` +
            `(e.g. error-handling consistency, test-coverage gaps, naming drift). ` +
            `Assessment (typed):\n`,
          assessment,
        ),
        schema: SYNTHESIZE_SCHEMA,
        model: "sonnet",
        agentType: COORDINATOR_AGENT,
      });
    }

    // Phase REFINE: verify top findings against actual source; drop false positives.
    enterPhase("refine");
    if (synthesis && budget.remaining() >= minTailBudget) {
      refinement = await agent({
        prompt: coordinatorPrompt(
          `Verify the top-ranked findings against the actual source code; remove ` +
            `any that turn out to be intentional (false positives). Ranked ` +
            `recommendations (typed):\n`,
          synthesis,
        ),
        schema: REFINE_SCHEMA,
        model: "sonnet",
        agentType: COORDINATOR_AGENT,
      });
    }
  }

  // Phase REPORT: the final exploration report (the prose exploration-report.md),
  // built from everything gathered. One coordinator pass (runs for all tiers).
  enterPhase("report");
  let report = null;
  if (scans.length > 0 && budget.remaining() >= minTailBudget) {
    report = await agent({
      prompt: coordinatorPrompt(
        `Produce the final exploration report: executive summary, quick facts ` +
          `(language/framework/architecture/test-strategy), key components, and ` +
          `next steps for understanding. Include the quality assessment + ranked ` +
          `recommendations when present (deep tier). All findings (typed):\n`,
        { scans, architectureMap, analysis, compilation, assessment, synthesis, refinement },
      ),
      schema: REPORT_SCHEMA,
      model: "sonnet",
      agentType: COORDINATOR_AGENT,
    });
  }

  return {
    tier: effectiveTier,
    deep: runDeep,
    scanners_ran: scans.length,
    architecture_mapped: architectureMap != null,
    analyzed: analysis != null,
    quality_limb_ran: runDeep,
    report,
    budget_remaining: budget.remaining(),
  };
}
