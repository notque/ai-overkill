#!/usr/bin/env node
// conformance-harness.mjs — dynamic dispatch recorder for native .js workflows.
//
// LOCAL/DEV TOOL (not a CI gate). CI does not provide node (see
// .github/workflows/test.yml — setup-python only). The CI conformance gate is
// scripts/validate-workflow-conformance.py (STATIC). This harness is the DYNAMIC
// half: it runs a target workflow's default() with RECORDING mocks so the
// data-driven branches (tier-gated waves, per-finding verify, budget-bounded fix
// loop) actually execute, and records the real dispatch trace — WITHOUT spending
// tokens, hitting the network, or needing an API key. validate-workflow-
// conformance.py shells to this harness when node is available and asserts the
// recorded trace against meta.contract. See adr/native-fast-path-portable-floor.md
// Stages 0-1.
//
// Contract with the runtime it mocks (matches dynamic-workflows-vs-vexjoy-diff.md):
//   - agent({prompt, schema, model, agentType}) -> records {agentType, skills, phase}
//     and returns a minimal schema-shaped stub so the workflow body can proceed.
//   - parallel(thunks) -> Promise.all(thunks.map(t => t()))  (hard barrier)
//   - pipeline(items, ...stages) -> sequential stage application per item
//   - phase(title) -> records the entered phase (and tags subsequent agent records)
//   - budget -> {remaining: () => 1e9, spent: () => 0, total: null}  (never exhausts)
//   - log(...) -> no-op recorder
//
// The harness calls run({scope, tier, fixThreshold, roster, synthAgentType}). The
// roster + synthAgentType keys let a FULLY-DYNAMIC workflow (caller-supplied
// roster, e.g. fan-out-workflow) execute its fan-out; static-roster workflows
// (e.g. comprehensive-review) ignore the extra keys.
//
// Usage:
//   node scripts/conformance-harness.mjs <path-to-workflow.js> [--tiers 2,3,4]
// Emits to stdout: JSON { workflow, traces: { "<tier>": <trace> }, errors: [...] }
// where each trace = { phases_entered, agent_count, rosters: [{agentType, skills}] }.
// Exit 0 on success, 2 on a harness/import error (so the caller can distinguish a
// recording failure from a conformance mismatch).

import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

// --- Skill-tool call extraction ----------------------------------------------
// The workflow embeds the exact action contract in the agent prompt. Extract
// every called skill name from that sentence, preserving order, de-duped.
const SKILL_RE = /Call the Skill tool with `([a-z0-9][a-z0-9-]*)`\./g;
function extractSkills(prompt) {
  if (typeof prompt !== "string") return [];
  const out = [];
  let m;
  while ((m = SKILL_RE.exec(prompt)) !== null) {
    if (!out.includes(m[1])) out.push(m[1]);
  }
  return out;
}

// --- Minimal schema-shaped stub -----------------------------------------------
// agent() returns a typed object in the real runtime. The workflow body reads
// fields like .findings / .disposition / .severity. Produce the smallest object
// that lets every branch proceed deterministically without inventing findings
// (so the verify/fix loops are entered but terminate — recording the dispatch
// shape, not simulating a full review).
function stubForSchema(schema) {
  const out = {};
  const props = (schema && schema.properties) || {};
  const required = (schema && schema.required) || [];
  for (const key of required) {
    const spec = props[key] || {};
    if (spec.type === "array") out[key] = [];
    else if (spec.type === "object") out[key] = {};
    else if (spec.enum && spec.enum.length) out[key] = spec.enum[0];
    else if (spec.type === "number") out[key] = 0;
    else out[key] = "";
  }
  return out;
}

// --- Recording runtime --------------------------------------------------------
function makeRuntime() {
  const records = []; // [{agentType, skills, phase}]
  const phasesEntered = []; // ordered, de-duped
  let currentPhase = null;

  globalThis.phase = (title) => {
    currentPhase = title;
    if (!phasesEntered.includes(title)) phasesEntered.push(title);
  };
  globalThis.log = () => {};
  globalThis.budget = {
    remaining: () => 1e9,
    spent: () => 0,
    total: null,
  };
  globalThis.agent = async ({ prompt, schema, agentType } = {}) => {
    records.push({
      agentType: agentType || null,
      skills: extractSkills(prompt),
      phase: currentPhase,
    });
    return stubForSchema(schema);
  };
  globalThis.parallel = (thunks) => Promise.all(thunks.map((t) => t()));
  globalThis.pipeline = async (items, ...stages) => {
    const results = [];
    for (const item of items) {
      let acc = item;
      for (const stage of stages) acc = await stage(acc);
      results.push(acc);
    }
    return results;
  };

  return { records, phasesEntered };
}

// --- Trace builder ------------------------------------------------------------
// Roster = the Wave-1 static barrier dispatches, identified as the agent records
// whose phase is the FIRST entered phase. (Wave-1 is the fixed barrier the
// contract pins; later phases are dynamic.) Falls back to all agentType-tagged
// records when no phase was entered.
function buildTrace(records, phasesEntered) {
  const firstPhase = phasesEntered[0] || null;
  const rosterRecords = firstPhase
    ? records.filter((r) => r.phase === firstPhase && r.agentType)
    : records.filter((r) => r.agentType);
  const rosters = rosterRecords.map((r) => ({
    agentType: r.agentType,
    skills: r.skills,
  }));
  return {
    phases_entered: phasesEntered,
    agent_count: records.length,
    rosters,
  };
}

async function recordTier(modUrl, tier) {
  const { records, phasesEntered } = makeRuntime();
  const mod = await import(modUrl);
  const run = mod.default;
  if (typeof run !== "function") {
    throw new Error("workflow has no default export function");
  }
  // Minimal mock args that exercise the data-driven branches at this tier.
  // A sample roster + synthAgentType lets a FULLY-DYNAMIC workflow (caller-supplied
  // roster, e.g. fan-out-workflow) run its fan-out; static-roster workflows ignore
  // these extra keys. fixThreshold bounds any budget loop. Each roster entry
  // carries a `skills` LIST (Stage 2.5: the full /do skill stack) so the workflow
  // emits one exact Skill-tool call per element, so the trace shows every skill.
  await run({
    scope: { files: ["src/a.py", "src/b.py"], packages: ["pkg"], tier },
    tier,
    fixThreshold: 8000,
    roster: [
      { agentType: "reviewer-system", skills: ["systematic-code-review", "verification-before-completion"], lens: "security" },
      { agentType: "reviewer-code", skills: ["systematic-code-review", "verification-before-completion"], lens: "quality" },
    ],
    synthAgentType: "research-coordinator-engineer",
  });
  return buildTrace(records, phasesEntered);
}

async function main() {
  const args = process.argv.slice(2);
  const target = args.find((a) => !a.startsWith("--"));
  if (!target) {
    process.stderr.write("usage: conformance-harness.mjs <workflow.js> [--tiers 2,3,4]\n");
    process.exit(2);
  }
  const tiersArg = args.find((a) => a.startsWith("--tiers"));
  let tiers = [2, 3, 4];
  if (tiersArg) {
    const val = tiersArg.includes("=") ? tiersArg.split("=")[1] : args[args.indexOf(tiersArg) + 1];
    if (val) tiers = val.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => !Number.isNaN(n));
  }

  const modUrl = pathToFileURL(resolve(target)).href;
  const traces = {};
  const errors = [];
  for (const tier of tiers) {
    try {
      // Fresh module URL per tier so each run re-imports with clean globals.
      traces[String(tier)] = await recordTier(`${modUrl}?tier=${tier}`, tier);
    } catch (e) {
      errors.push({ tier, error: String(e && e.message ? e.message : e) });
    }
  }

  process.stdout.write(
    JSON.stringify({ workflow: resolve(target), traces, errors }, null, 2) + "\n",
  );
  process.exit(errors.length > 0 && Object.keys(traces).length === 0 ? 2 : 0);
}

main().catch((e) => {
  process.stderr.write(`conformance-harness fatal: ${e && e.stack ? e.stack : e}\n`);
  process.exit(2);
});
