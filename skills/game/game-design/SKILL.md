---
name: game-design
version: 2.1.0
description: "Repository-aware game design diagnosis, decisions, and validation."
agent: ui-design-engineer
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
routing:
  triggers: [game design, improve this game, game improvement, game design audit, game design report, core loop, game feel, player motivation, game balance, game economy, game onboarding, first-time experience, game pitch, game design document, game prototype, game scope, game progression, game fairness, game diagnostic, retention, churn, engagement]
  not_for: "Implementing a game in Phaser or Three.js, generating game art, or QA automation without a design question."
  pairs_with: [game-pipeline, phaser-gamedev, threejs-builder, decision-helper]
  complexity: Medium
  category: game-design
---

# Game design

Convert a concept, game repository, playable build, player finding, or design document into a professional, evidence-led design decision. This skill carries a complete original reconstruction of the assessed game-design capability set; use its references as operational expertise, not as a menu of shallow lenses.

## Discovery and help mode

When the request is bare `game design`, asks what game-design help is available, or asks which review to run, read `references/capability-catalog.md`. Present the complete domain-organized catalog, offer the packet(s) that match the stated player moment, and state that `full audit`, `health check`, or `design report` runs the all-packet repository diagnostic. Do not return a partial topical menu: the catalog is the user-facing inventory of all 61 runnable capabilities.

## Autonomous improvement mode

When asked to improve a game, its retention, churn, engagement, or player experience, read `references/autonomous-improvement.md` and follow it as the default operating mode. This is a greedy, repo-first improvement cycle: inspect the real game, run every relevant capability (all 61 for systemic retention or whole-game requests), make the smallest safe and reversible improvement that evidence supports, verify it, and leave a measurement plan for the next cycle. Never wait for a feature request when the evidence itself identifies a material player harm or opportunity.

## 1. Intake and deterministic evidence inventory

Start from repository evidence. Read the target repository's governing instruction files first. Search its installed skills and agents for game, product, UI, implementation, analytics, and research guidance; load every applicable local instruction and record its authority before drawing conclusions. Then use file search and code inspection to find design documents, player-facing copy, rules and state, UI, configuration and tables, tests, analytics schemas, issues, ownership, and recent changes. Separate facts into `observed`, `documented`, `measured`, and `inferred`.

Ask only what the repository cannot answer:

1. Which player context and concrete play moment matter?
2. What external player evidence exists: playtest recordings, support patterns, telemetry, reviews, or community reports?
3. Which constraints are binding: platform, release phase, team, accessibility, legal, trust, time, or cost?
4. Does the user need a diagnosis, options, specification, priority decision, prototype plan, or full report?

## 2. Greedy reference routing

Load every module that could materially change the recommendation, its player-risk assessment, or validation plan. Do not stop at the smallest topical match. Add adjacent modules when the player path crosses their domain.

| Signal | Load modules |
|---|---|
| Promise, fantasy, loops, goals, feature coherence | `core-loop-and-pillars.md`, `capabilities/08-game-design-craft-critique.md` where relevant, `audit-and-red-team.md` |
| Ideation, novelty, removal, reuse, blocked choice | `creative-and-options.md`, `core-loop-and-pillars.md`, `planning-and-production.md` |
| Player motives, personas, values, inclusion | `player-and-social.md`, `cognition-and-choice.md`, `social-and-competitive.md` when others matter |
| Information, prompts, bias, causality, randomness | `cognition-and-choice.md`, `fairness-and-failure.md`, `pacing-and-return.md` |
| Failure, difficulty, fairness, recovery | `fairness-and-failure.md`, `core-loop-and-pillars.md`, `pacing-and-return.md` |
| First-time experience, flow, friction, goals, session close, return | `pacing-and-return.md`, `fairness-and-failure.md`, `cognition-and-choice.md` |
| Co-op, competition, guilds, social sessions, rank | `social-and-competitive.md`, `player-and-social.md`, `progression-and-economy.md` |
| Rewards, currencies, battle passes, KPIs | `progression-and-economy.md`, `player-and-social.md`, `fairness-and-failure.md` |
| Pitch, mood, emotional direction, prototype, design doc | `emotion-and-presentation.md`, `artifacts-and-prototyping.md`, `planning-and-production.md` |
| Scope, sequence, estimates, staffing, decisions | `planning-and-production.md`, `core-loop-and-pillars.md`, `audit-and-red-team.md` |
| Full game/repository health report | **Read `capability-matrix.md`, every domain module, then `full-diagnostic.md`.** |

The module contains card-level protocols. Read all cards within each selected module. Full diagnostic mode is intentionally greedy: every card is mandatory.

## 3. Diagnose the player path

Trace: cue → interpretation → choice → system response → cost/reward → feedback → next intention. For a failure path, include expectation, information, retry, and learning. For social play, include invitation, coordination, conflict, absence, rejoin, recognition, and abuse recovery.

For every material finding, state the player consequence, evidence, competing explanations, confidence, severity, and the smallest change that would distinguish the leading explanations. Do not replace a player outcome with a framework label, funnel metric, or author preference.

## 4. Decide and specify

Offer two to five genuinely distinct options where a choice remains. For each option state:

- player-visible change and promised outcome;
- pillar/loop fit, affected player contexts, accessibility and trust effects;
- rule, content, UI, data, analytics, or production scope;
- dependencies, effort range, reversibility, owner, and risk;
- prototype or implementation task, success metric, quality guard, and stop rule.

Prefer reversible experiments when evidence is weak. Reject dark patterns: hidden costs, coercive scarcity, shame, forced social exposure, punitive absence, harassment incentives, or confusion used as retention.

## 5. Full diagnostic mode

For a full review, follow `references/full-diagnostic.md` exactly. The output must include an evidence inventory, full matrix coverage ledger, severity-ranked findings, detailed fixes, ownership, validation, unknowns, and a sequenced 30/60/90-day plan. A missing artifact is a finding; it does not excuse skipping a module.

## 6. Completion gate

Before returning, verify that every finding has repository/player evidence or is explicitly an inference, every recommendation has a validation plan and owner, and the reference coverage matches the request. State what would change the recommendation.

## Error handling

| Failure | Recovery |
|---|---|
| Repository contains no player evidence | Report the evidence gap; propose a bounded observation or instrumentation plan. |
| Framework conflicts with player evidence | Keep the evidence; use the framework only to generate competing hypotheses. |
| Scope is too broad to implement | Sequence cuts and reversible tests; do not hide the risk in a single priority score. |
| User asks for a full report but the game is not runnable | Audit available intent and system evidence, label limits, and prioritize a playable proof. |

## Provenance

This is an independent, original synthesis informed by an assessment of `Stanestane/game-design-skills-bundle` at commit `85d5c6545afd0988de5ef1ee7d95e67edd8f5a7b`. The assessed repository declares no license. No upstream files or wording are included. `references/capability-matrix.md` records capability coverage for maintenance.
