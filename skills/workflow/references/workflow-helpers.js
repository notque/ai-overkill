// workflow-helpers.js
//
// Shared prompt-builder helpers for native .js workflows (fan-out-workflow.js,
// comprehensive-review-workflow.js). Both workflows attach the FULL /do skill
// stack to every dispatched agent and embed the /do mandatory injection block,
// so a dispatched workflow agent receives the SAME context it would have gotten
// from a direct /do dispatch — not a single bare skill.
//
// Two builders, used identically by both workflows:
//   - skillDirectives(skills): emit one exact Skill-tool call for EVERY skill
//     in the roster entry's skills list (the Phase-3 enhancement stack: primary
//     skill + test-driven-development/verification-before-completion + the
//     per-task-type anti-rationalization patterns the caller stacked).
//   - mandatoryInjections(): the /do Phase 4 Step 2 MANDATORY block — completeness
//     standard, density standard, base-instructions load, reference-loading
//     instruction. Verbatim from skills/meta/do/SKILL.md Phase 4 Step 2.
//
// Determinism: no Date.now()/Math.random(); pure string composition only.

import agentIndex from "../../../agents/INDEX.json" with { type: "json" };
import skillIndex from "../../INDEX.json" with { type: "json" };

const NAME_RE = /^[a-z0-9][a-z0-9-]*$/;

function indexNames(index, key, label) {
  const entries = index && index[key];
  if (!entries || typeof entries !== "object" || Array.isArray(entries)) {
    throw new Error(`Trusted ${label} index is unreadable or empty.`);
  }
  const names = Object.keys(entries);
  if (names.length === 0) {
    throw new Error(`Trusted ${label} index is unreadable or empty.`);
  }
  return new Set(names);
}

const KNOWN_AGENTS = indexNames(agentIndex, "agents", "agent");
const KNOWN_SKILLS = indexNames(skillIndex, "skills", "skill");

export function validateAgentName(name, label = "agentType") {
  if (typeof name !== "string") {
    throw new TypeError(`${label}: agent name must be a string.`);
  }
  if (!NAME_RE.test(name)) {
    throw new TypeError(`${label}: invalid agent name ${JSON.stringify(name)}.`);
  }
  if (KNOWN_SKILLS.has(name)) {
    throw new TypeError(`${label}: ${name} is a skill, not an agent.`);
  }
  if (!KNOWN_AGENTS.has(name)) {
    throw new TypeError(`${label}: unknown agent ${name}.`);
  }
  return name;
}

export function validateSkillNames(skills, label = "skills") {
  if (!Array.isArray(skills)) {
    throw new TypeError(`${label}: skills must be an array.`);
  }
  if (skills.length === 0) {
    throw new TypeError(`${label}: expected at least one skill.`);
  }

  const names = [];
  const seen = new Set();
  for (const name of skills) {
    if (typeof name !== "string") {
      throw new TypeError(`${label}: skill name must be a string.`);
    }
    if (!NAME_RE.test(name)) {
      throw new TypeError(`${label}: invalid skill name ${JSON.stringify(name)}.`);
    }
    if (KNOWN_AGENTS.has(name)) {
      throw new TypeError(`${label}: ${name} is an agent, not a skill.`);
    }
    if (!KNOWN_SKILLS.has(name)) {
      throw new TypeError(`${label}: unknown skill ${name}.`);
    }
    if (!seen.has(name)) {
      seen.add(name);
      names.push(name);
    }
  }
  return names;
}

export function validateRoster(roster, label = "roster") {
  if (!Array.isArray(roster)) {
    throw new TypeError(`${label}: roster must be an array.`);
  }
  if (roster.length === 0) {
    throw new TypeError(`${label}: expected at least one roster entry.`);
  }
  return roster.map((entry, index) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new TypeError(`${label}[${index}]: roster entry must be an object.`);
    }
    return {
      ...entry,
      agentType: validateAgentName(entry.agentType, `${label}[${index}].agentType`),
      skills: validateSkillNames(entry.skills, `${label}[${index}].skills`),
    };
  });
}

// Emit the A/B-winning action contract for every validated skill in the list.
export function skillDirectives(skills) {
  const list = validateSkillNames(skills);
  return `\n${list.map((s) => `Call the Skill tool with \`${s}\`.`).join("\n")}`;
}

// The /do Phase 4 Step 2 MANDATORY injection block, verbatim. Every dispatched
// workflow agent gets the same completeness/density/base-instructions/reference-
// loading context a direct /do dispatch injects. Static string (cacheable).
export function mandatoryInjections() {
  return (
    `\n\n## Operating standards (injected)\n` +
    `- Deliver the finished product. Ship the complete thing.\n` +
    `- Write dense: high fidelity, minimum words. Cut filler, prefer tables over ` +
    `paragraphs, report what changed — not how.\n` +
    `- Before starting work, also load \`agents/base-instructions.md\` for ` +
    `universal operational rules.\n` +
    `- Before starting work, read your agent .md file to find the Reference ` +
    `Loading Table. Load EVERY reference file whose signal matches this task. ` +
    `Load greedily — if multiple signals match, load all matching references.`
  );
}
