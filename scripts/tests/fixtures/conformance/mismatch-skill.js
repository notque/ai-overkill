// mismatch-skill.js — fixture: meta.contract.roster declares reviewer-system uses
// skills ["systematic-code-review", "verification-before-completion"], but the
// source emits an exact Skill-tool call for only ONE of them — the second skill is
// declared but unbacked. The conformance validator must FAIL on the STATIC
// roster/skills check (a declared skill has no corresponding exact call).
export const meta = {
  name: "fixture-mismatch-skill",
  description: "a declared roster skill is not present in source",
  contract: {
    phases: ["wave-1"],
    roster: [{ agentType: "reviewer-system", skills: ["systematic-code-review", "verification-before-completion"] }],
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
    // Only systematic-code-review is emitted; verification-before-completion is
    // declared in the contract but never emitted as an exact Skill-tool call.
    prompt: `You are reviewer-system. Call the Skill tool with \`systematic-code-review\`. Review scope: ${JSON.stringify(scope)}`,
    schema: { type: "object", required: ["verdict"], properties: { verdict: { type: "string", enum: ["APPROVE"] } } },
    agentType: "reviewer-system",
  });
  return {};
}
