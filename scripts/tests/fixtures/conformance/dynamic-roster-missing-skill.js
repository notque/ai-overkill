// dynamic-roster-missing-skill.js — fixture: a FULLY-DYNAMIC-roster workflow that
// dispatches agentType from a roster variable but never emits a Skill-tool call.
// The contract declares roster:{dynamic:true}, so the validator asserts the
// STRUCTURAL invariant — and must FAIL here because the per-roster call-from-
// variable directive (the proven per-agent methodology attach) is missing.
export const meta = {
  name: "fixture-dynamic-roster-missing-skill",
  description: "fully-dynamic roster missing the Skill-call-from-roster invariant",
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

export default async function run({ scope, roster, synthAgentType } = {}) {
  enterPhase("fan-out");
  const workers = await parallel(
    roster.map((r) => () =>
      agent({
        // No Skill-tool call — the per-agent methodology attach is missing.
        prompt: `You are a ${r.lens} specialist. Scope: ${JSON.stringify(scope)}`,
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
