// dynamic-roster.js — fixture: a FULLY-DYNAMIC-roster workflow. The roster is
// supplied entirely by the caller, so there are NO static agentType/Skill-call
// literals to pin. The contract declares roster:{dynamic:true} and agents:{dynamic
// :true}. The conformance validator must assert the STRUCTURAL invariant — the
// source emits an exact Skill-tool call derived from a roster variable AND dispatches
// agentType from a roster variable — and PASS this file (not vacuously).
export const meta = {
  name: "fixture-dynamic-roster",
  description: "fully-dynamic roster; structural invariant present",
  contract: {
    phases: ["fan-out", "synthesize"],
    roster: { dynamic: true },
    agents: { dynamic: true },
    dynamic: true,
  },
};

function enterPhase(title) {
  if (typeof phase === "function") phase(title);
}

// Emit one exact Skill-tool call per element of the skills list (mirrors the
// shared workflow-helpers.js skillDirectives()).
function skillDirectives(skills) {
  return (skills || []).map((s) => `Call the Skill tool with \`${s}\`.`).join("\n");
}

function validateRoster(roster) {
  return roster;
}

function validateRosterEntries(roster) {
  return validateRoster(roster);
}

export default async function run({ scope, roster, synthAgentType } = {}) {
  const workersToRun = validateRosterEntries(roster);
  enterPhase("fan-out");
  const workers = await parallel(
    workersToRun.map((r) => () =>
      agent({
        prompt:
          `You are a ${r.lens} specialist. ${skillDirectives(r.skills)} ` +
          `Scope: ${JSON.stringify(scope)}`,
        schema: { type: "object", required: ["summary"], properties: { summary: { type: "string" } } },
        agentType: r.agentType,
        phase: "fan-out",
      }),
    ),
  );
  enterPhase("synthesize");
  const synthesis = await agent({
    prompt: `Synthesize ${workers.length} worker outputs.`,
    schema: { type: "object", required: ["summary"], properties: { summary: { type: "string" } } },
    agentType: synthAgentType,
    phase: "synthesize",
  });
  return { workers_ran: workers.length, synthesis };
}
