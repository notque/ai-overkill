---
name: planning
description: "Planning lifecycle: specs, requirements, ambiguity triage, human-source elicitation, evidence prototypes, file-backed plans, validation, pause/resume, and context boundaries."
user-invocable: true
agent: general-purpose
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Skill
routing:
  force_route: true
  not_for: "city/financial/meeting/travel planning; and personal prioritization like 'what should I work on next' — that is productivity. Not for packaging inline agent-to-agent session state (working tree, PR/CI, live processes) — that is session-handoff; planning's pause/resume owns plan-artifact handoff via HANDOFF.json plus pause.md/resume.md. Only for software task planning, specs, and plan-lifecycle management."
  triggers:
    - "write spec"
    - "user stories"
    - "define requirements"
    - "scope this"
    - "what should this do"
    - "acceptance criteria"
    - "define scope"
    - "spec out"
    - "discuss ambiguities"
    - "resolve gray areas"
    - "clarify before planning"
    - "assumptions mode"
    - "what are the gray areas"
    - "before we plan"
    - "pre-planning discussion"
    - "interview me"
    - "grill me"
    - "depth-first review"
    - "depth-first interview"
    - "not sure"
    - "i'm not sure"
    - "not exactly sure"
    - "where do i start"
    - "where do i even start"
    - "want clarity on"
    - "need clarity on"
    - "what am i missing"
    - "poke holes in"
    - "challenge my assumptions"
    - "think this through with me"
    - "lots of moving parts"
    - "many decisions"
    - "questions for a stakeholder"
    - "questions for an expert"
    - "what should i ask them"
    - "get requirements from the team"
    - "knowledge is in their head"
    - "test this assumption"
    - "prototype to decide"
    - "spike to answer"
    - "create plan"
    - "task plan"
    - "working memory"
    - "persistent plan"
    - "file-backed planning"
    - "check plan"
    - "validate plan"
    - "plan checker"
    - "review plan"
    - "is this plan ready"
    - "plan-checker"
    - "pre-execution check"
    - "list plans"
    - "show plan"
    - "complete plan"
    - "plan status"
    - "manage plans"
    - "pause plan"
    - "save progress"
    - "stopping for now"
    - "end session"
    - "pick this up later"
    - "session handoff"
    - "wrap up session"
    - "resume plan"
    - "continue plan"
    - "resume where we left off"
    - "pick up where I left off"
    - "what was I doing"
    - "continue work"
    - "where did I leave off"
    - "what's next"
  category: process
  complexity: medium
  pairs_with:
    - workflow
    - feature-lifecycle
    - decision-helper
---

# Planning Skill

Select the planning method below. `/do` owns capability routing; these references are internal methods. Planning owns specs, saved plans, and plan pause/resume. `subagent-driven-development` owns execution; `session-handoff` owns inline transfers, including live processes. Use `verification-before-completion` for outcome checks.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| "write spec", "user stories", "define requirements", "scope this", "acceptance criteria", "define scope", "spec out" | `${CLAUDE_SKILL_DIR}/references/spec.md` | **Spec** |
| "discuss ambiguities", "resolve gray areas", "clarify before planning", "assumptions mode", "before we plan", "pre-planning discussion" | `${CLAUDE_SKILL_DIR}/references/pre-plan.md` | **Pre-plan** |
| "interview me", "grill me", "depth-first review", "depth-first interview", "not sure", "i'm not sure", "where do i start", "want clarity on", "need clarity on", "what am i missing", "poke holes in", "challenge my assumptions", "think this through with me", "lots of moving parts", "many decisions" | `${CLAUDE_SKILL_DIR}/references/depth-first-interview.md` | **Interview** |
| implicit ambiguity or unclear implementation choices | `${CLAUDE_SKILL_DIR}/references/ambiguity-triage.md` | Decide whether questions earn their interruption cost |
| another person holds needed facts, preferences, constraints, or approval | `${CLAUDE_SKILL_DIR}/references/human-source-elicitation.md` | Create a targeted, sendable question artifact |
| observation can settle a disputed or unknown choice | `${CLAUDE_SKILL_DIR}/references/empirical-prototype.md` | Turn uncertainty into bounded evidence |
| a phase, worker, or session transition is near | `${CLAUDE_SKILL_DIR}/references/context-boundary.md` | Preserve only the state the receiver needs |
| "create plan", "task plan", "working memory", "persistent plan", "file-backed planning" | `${CLAUDE_SKILL_DIR}/references/plan-files.md` (+ `${CLAUDE_SKILL_DIR}/references/executor-ready-plan-template.md` when plan targets SDD execution) | **Plan-files** |
| "check plan", "validate plan", "plan checker", "review plan", "is this plan ready", "pre-execution check" | `${CLAUDE_SKILL_DIR}/references/check.md` | **Check** |
| "list plans", "show plan", "complete plan", "plan status", "manage plans" | `${CLAUDE_SKILL_DIR}/references/manage.md` | **Manage** |
| "pause", "save progress", "handoff", "stopping for now", "end session", "session handoff", "wrap up session" | `${CLAUDE_SKILL_DIR}/references/pause.md` | **Pause** |
| "resume", "continue", "pick up where I left off", "what was I doing", "continue work", "where did I leave off", "what's next" | `${CLAUDE_SKILL_DIR}/references/resume.md` | **Resume** |

For interviews, use independent questions batched into frontier rounds, dependent questions asked sequentially, and a recommendation per question.

## Instructions

1. Identify the planning intent and inspect available evidence.
2. For implicit ambiguity, load `${CLAUDE_SKILL_DIR}/references/ambiguity-triage.md` before choosing an interview.
3. Load the matching reference. Compose references when the task crosses sources or context boundaries.
4. Follow the selected reference and return to execution as soon as its gate clears.
