// mismatch-agentcount.js — fixture: meta.contract.agents.static declares 3 static
// Wave-1 agents and the roster lists 3, but the source's static Wave-1 barrier
// only dispatches 1 distinct agentType. The conformance validator must FAIL on
// the STATIC agent-count / roster-coverage check (declared static count does not
// match the roster length / source agentTypes).
export const meta = {
  name: "fixture-mismatch-agentcount",
  description: "declared static agent count exceeds the actual static roster",
  contract: {
    phases: ["wave-1"],
    roster: [
      { agentType: "reviewer-system", skills: ["systematic-code-review"] },
      { agentType: "reviewer-domain", skills: ["systematic-code-review"] },
      { agentType: "reviewer-code", skills: ["systematic-code-review"] },
    ],
    // Declares 3 static agents but the body only dispatches reviewer-system.
    agents: { static: 3, dynamic: false },
    dynamic: false,
  },
};

function enterPhase(title) {
  if (typeof phase === "function") phase(title);
}

export default async function run({ scope } = {}) {
  enterPhase("wave-1");
  await agent({
    prompt: `You are reviewer-system. Call the Skill tool with \`systematic-code-review\`. ${JSON.stringify(scope)}`,
    schema: { type: "object", required: ["verdict"], properties: { verdict: { type: "string", enum: ["APPROVE"] } } },
    agentType: "reviewer-system",
  });
  return {};
}
