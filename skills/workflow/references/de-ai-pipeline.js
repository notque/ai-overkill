// de-ai-pipeline.js
//
// Native dynamic-Workflow variant of the de-AI scan-fix-verify loop. The
// markdown flow at ./de-ai-pipeline.md remains the cross-harness floor; this
// script is the deterministic-runtime FAST-PATH for Claude Code (+Factory) when
// the native Workflow tool is present. It mirrors the prose 4-phase flow SCAN ->
// FIX -> VERIFY -> REPORT, replacing the ad-hoc per-file dispatch with a real
// parallel() barrier over the files that have errors and schema-validated typed
// agent() returns.
//
// The prose pipeline is DETERMINISTIC-FIRST: a scanner script
// (scan-ai-patterns.py) detects AI patterns; the LLM only fixes (PHILOSOPHY:
// everything deterministic should be). So SCAN runs the scanner OUT-OF-BAND (the
// /do caller passes the scan result in as `scope.scanHits`) — no LLM round-trip
// for detection. FIX is a DATA-DRIVEN parallel barrier: one de-AI fix agent
// per file with errors (the prose "one Agent per file" mandate), so the roster is
// FULLY-DYNAMIC (caller-/data-supplied, no fixed count). VERIFY re-scans and
// loops back to FIX up to a max-3-iteration bound (the prose anti-infinite-loop
// guard). REPORT summarizes and stages.
//
// Runtime contract (see ./fan-out-workflow.js for the canonical fully-dynamic-
// roster description, and ./comprehensive-review-workflow.js for the native
// primitives): meta is a pure object literal parsed before the body;
// parallel(thunks) is a hard barrier (failed slot -> null); agent({prompt,
// schema, model, agentType}) returns a typed object; budget.remaining() bounds
// the loop. No Date.now()/Math.random()/new Date().

import {
  mandatoryInjections,
  skillDirectives,
  validateAgentName,
  validateRoster,
} from "./workflow-helpers.js";

export const meta = {
  name: "de-ai-pipeline",
  description:
    "De-AI scan-fix-verify loop as a deterministic native Workflow: SCAN -> FIX -> VERIFY -> REPORT. Detection is deterministic (scan-ai-patterns.py, run out-of-band; results passed in), so no LLM scans. FIX is a data-driven parallel barrier of one de-AI fix agent per file with errors (each attaching its full skill stack via one exact Skill-tool call per skill plus the /do mandatory injections); VERIFY re-scans and loops back up to 3 iterations; REPORT summarizes and stages. The fix roster is caller-/data-supplied (fully dynamic). Mirrors de-ai-pipeline.md; that markdown flow stays the cross-harness floor.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stage 3). This is a FULLY-DYNAMIC-roster contract: the FIX fan-out is one
  //     agent per error file (data-driven count), so there are NO static
  //     agent/skill literals to pin. The gate asserts the STRUCTURAL invariant
  //     (source emits an exact Skill-tool call from a roster variable AND dispatches
  //     agentType from a roster variable), NOT specific names. name + description
  //     stay BEFORE this nested object so the non-greedy meta-name parser in
  //     workflow-registry.py still resolves meta.name.
  contract: {
    // Phase titles entered at runtime via enterPhase(). FIX (the data-driven
    // barrier) is the first entered phase; the deterministic SCAN step precedes
    // it in-body (the scanner runs out-of-band; results passed in via scope).
    phases: ["fix", "verify", "report"],
    // Fully-dynamic roster: one de-AI fix agent per file with errors, built
    // from the scan results at runtime. No static names/count to pin — the gate
    // asserts the structural invariant instead.
    roster: { dynamic: true },
    // No static barrier to count: every dispatched agent comes from the runtime
    // per-file roster (errorFiles.length workers across up to 3 iterations).
    agents: { dynamic: true },
    // Data-driven fan-out + bounded re-scan loop: count is the number of files
    // with errors (and the iteration count), both runtime data. Honest limit: the
    // gate asserts SHAPE + the structural Skill-tool-call/agentType invariant, NOT COUNT.
    dynamic: true,
  },
};

// The single fix agent type + its full skill stack. Every FIX worker dispatches
// this agent running the anti-ai methodology + the verification gate. The roster
// is built per-file at runtime (one entry per error file), and agentType is
// dispatched FROM that roster variable — the fully-dynamic structural invariant.
// Use public indexed components so the workflow remains portable. voice-writer
// carries the anti-AI editing workflow through its loaded voice references.
const FIX_AGENT = "technical-journalist-writer";
const FIX_SKILLS = ["voice-writer", "verification-before-completion"];
const MAX_ITERATIONS = 3;

// --- Schemas (mirror the STYLE of comprehensive-review-workflow.js / -----------
//     fan-out-workflow.js). Fix results + the report are schema-validated typed
//     objects, not re-parsed markdown.

// One file's typed fix result (mirrors a per-file fix log).
const FIX_SCHEMA = {
  type: "object",
  required: ["file", "outcome"],
  properties: {
    file: { type: "string" },
    outcome: { type: "string", enum: ["fixed", "partial", "skipped"] },
    fixes_applied: { type: "number" },
    skipped_hits: { type: "array", items: { type: "string" } },
    false_positives: { type: "array", items: { type: "string" } },
  },
};

// VERIFY output: the re-scan verdict (the prose Phase 3 gate).
const VERIFY_SCHEMA = {
  type: "object",
  required: ["verdict", "errors_remaining"],
  properties: {
    verdict: { type: "string", enum: ["clean", "errors_remain"] },
    errors_remaining: { type: "number" },
    files_with_errors: { type: "array", items: { type: "string" } },
  },
};

// REPORT output: the final pipeline report (the prose Phase 4).
const REPORT_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["CLEAN", "PARTIAL", "FAILED"] },
    iterations: { type: "number" },
    files_scanned: { type: "number" },
    files_fixed: { type: "number" },
    errors_initial: { type: "number" },
    errors_final: { type: "number" },
    false_positives: { type: "array", items: { type: "string" } },
    staged_files: { type: "array", items: { type: "string" } },
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

// Build the per-file FIX roster from the current error-file list: one entry per
// file, each dispatching the de-AI fix agent with its full skill stack. The
// roster is DATA-DRIVEN (one worker per error file) — the fully-dynamic shape.
// A caller-supplied `roster` override (each entry already {agentType, skills})
// takes precedence: the /do caller can hand in a pre-built fix roster, and the
// conformance harness exercises this path. Each override entry still carries its
// FULL skill stack so every worker emits its per-roster exact Skill-tool call.
function fixRoster(errorFiles, hitsByFile, override) {
  if (Array.isArray(override) && override.length > 0) {
    return validateRoster(override, "roster").map((r) => ({
      agentType: r.agentType,
      skills: r.skills,
      file: r.file || "",
      hits: r.hits || [],
    }));
  }
  return validateRoster(
    errorFiles.map((file) => ({
      agentType: FIX_AGENT,
      skills: FIX_SKILLS,
      file,
      hits: (hitsByFile && hitsByFile[file]) || [],
    })),
    "scan roster",
  );
}

// Build one FIX worker's prompt from its per-file roster entry. skillDirectives
// emits one exact Skill-tool call per element of r.skills (built FROM the roster variable —
// the fully-dynamic structural invariant the conformance gate asserts; resolves
// path-independent inside a native Workflow agent() dispatch). mandatoryInjections()
// embeds the /do completeness/density/base-instructions/reference-loading block.
function fixPrompt(r) {
  return (
    `You are ${r.agentType}, fixing AI writing patterns in one file.` +
    skillDirectives(r.skills) +
    `\nFile: ${r.file}\nDetected pattern hits (typed):\n${JSON.stringify(r.hits)}\n` +
    `Rephrase each genuine AI tell while preserving ALL factual content — never ` +
    `remove information to dodge a pattern. Leave protected zones unchanged (code ` +
    `blocks, inline code, YAML frontmatter, blockquotes); their hits are false ` +
    `positives. If a fix is hard, skip the hit and note it. Return a typed result: ` +
    `outcome (fixed|partial|skipped), fixes applied, skipped hits, and false positives.` +
    mandatoryInjections()
  );
}

// --- Workflow body ------------------------------------------------------------
//
// run({scope, tier, roster}):
//   - scope.scanHits: the deterministic scanner output (scan-ai-patterns.py),
//     run OUT-OF-BAND by the /do caller (detection is deterministic — no LLM).
//     Shape: { files_with_errors: [...], hits_by_file: {file: [hit,...]},
//              total_errors: N, files_scanned: N }.
//   - roster: optional caller-supplied FIX roster ([{agentType, skills, file,
//     hits}]) that overrides the scan-derived per-file roster. The /do caller may
//     pre-build it; the conformance harness exercises this path.
//   - tier: right-size tier (carried through; this pipeline loops on the re-scan
//     verdict, not the review tier).

export default async function run({ scope, tier, roster } = {}) {
  const fixAgent = validateAgentName(FIX_AGENT, "FIX_AGENT");
  const scanHits = (scope && scope.scanHits) || {};
  const initialErrors = typeof scanHits.total_errors === "number" ? scanHits.total_errors : 0;
  const filesScanned = typeof scanHits.files_scanned === "number" ? scanHits.files_scanned : 0;
  const hitsByFile = scanHits.hits_by_file || {};
  const rosterOverride = Array.isArray(roster) ? roster : null;
  const minTailBudget = 8000;

  // SCAN (deterministic, out-of-band): the scanner already ran; its results are
  // in scope.scanHits. No LLM detection round-trip (PHILOSOPHY: deterministic
  // detection belongs in the script). Seed the loop from the scanned error files,
  // or from the caller-supplied roster's files when an override is provided.
  let errorFiles = Array.isArray(scanHits.files_with_errors) ? scanHits.files_with_errors.slice() : [];
  if (errorFiles.length === 0 && rosterOverride) {
    errorFiles = rosterOverride.map((r, i) => r.file || `roster-file-${i}`);
  }
  let iteration = 0;
  let lastVerify = null;
  const allFixes = [];

  // FIX <-> VERIFY loop, bounded by max 3 iterations (the prose anti-infinite-
  // loop guard) AND the token budget. Each iteration: a data-driven FIX barrier
  // (one agent per error file) then a VERIFY re-scan that updates the error set.
  while (errorFiles.length > 0 && iteration < MAX_ITERATIONS && budget.remaining() >= minTailBudget) {
    iteration += 1;

    // Phase FIX: one hard barrier over the per-file roster. Each slot dispatches
    // the de-AI fix agent via agentType (a runtime variable) and embeds one
    // exact Skill-tool call per element of r.skills (the full stack) plus the /do
    // mandatory injections. Failed slots resolve to null and are filtered.
    enterPhase("fix");
    // First iteration may use a caller-supplied roster override; later iterations
    // rebuild from the re-scan error set (no override — fix the remaining files).
    const fixWorkers = fixRoster(errorFiles, hitsByFile, iteration === 1 ? rosterOverride : null);
    const rawFixes = await parallel(
      fixWorkers.map((r) => () =>
        agent({
          prompt: fixPrompt(r),
          schema: FIX_SCHEMA,
          model: "sonnet",
          agentType: r.agentType,
        }),
      ),
    );
    allFixes.push(...rawFixes.filter((x) => x != null));

    // Phase VERIFY: one re-scan pass over the fixed files; updates the error set.
    // verdict clean -> exit the loop; errors_remain -> loop again (<=3 total).
    enterPhase("verify");
    if (budget.remaining() < minTailBudget) break;
    lastVerify = await agent({
      prompt:
        `Re-scan these just-fixed files for remaining AI writing patterns (run the ` +
        `deterministic scanner over them). Return verdict clean|errors_remain, the ` +
        `count of errors remaining, and the files that still have errors. Fixed ` +
        `files (typed):\n${JSON.stringify(errorFiles)}`,
      schema: VERIFY_SCHEMA,
      model: "sonnet",
      agentType: fixAgent,
    });
    if (!lastVerify || lastVerify.verdict === "clean") {
      errorFiles = [];
      break;
    }
    errorFiles = Array.isArray(lastVerify.files_with_errors) ? lastVerify.files_with_errors : [];
  }

  // Phase REPORT: the final pipeline report (the prose Phase 4). One pass — does
  // NOT commit (the user owns the commit decision); it stages and summarizes.
  enterPhase("report");
  let report = null;
  if (budget.remaining() >= minTailBudget) {
    report = await agent({
      prompt:
        `Produce the de-AI pipeline report from these results: status ` +
        `(CLEAN|PARTIAL|FAILED), iterations run, files scanned/fixed, errors ` +
        `initial->final, false positives (for pattern refinement), and the staged ` +
        `files. Stage the fixed files but do NOT commit. Results (typed):\n` +
        JSON.stringify({ iteration, initialErrors, filesScanned, allFixes, lastVerify }),
      schema: REPORT_SCHEMA,
      model: "sonnet",
      agentType: fixAgent,
    });
  }

  return {
    tier: typeof tier === "number" ? tier : null,
    iterations: iteration,
    files_scanned: filesScanned,
    errors_initial: initialErrors,
    files_fixed: allFixes.filter((f) => f.outcome === "fixed").length,
    errors_remaining: lastVerify && typeof lastVerify.errors_remaining === "number" ? lastVerify.errors_remaining : 0,
    report,
    budget_remaining: budget.remaining(),
  };
}
