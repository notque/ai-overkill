// mismatch-phase.js — fixture: meta.contract declares a phase ("synthesis") the
// source never enters, and the source enters a phase ("verify") the contract
// omits. The conformance validator must FAIL this file on the STATIC phase check.
export const meta = {
  name: "fixture-mismatch-phase",
  description: "phases declared do not match phases entered",
  contract: {
    phases: ["wave-1", "synthesis"],
    roster: [{ agentType: "reviewer-system", skill: "systematic-code-review" }],
    agents: { static: 1, dynamic: false },
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
  enterPhase("verify"); // entered but NOT in contract.phases -> mismatch
  return {};
}
