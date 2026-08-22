# Game-design skill specification

## Purpose

Provide one repository-aware professional game-design skill that converts evidence about a playable game into accountable design decisions, detailed fixes, safe implemented improvements, and validation plans.

## Scope

The skill covers all 61 assessed capabilities in `references/capability-matrix.md`: design intent, loops, choices, cognition, player contexts, failure, pacing, social systems, progression, presentation, prototyping, production planning, and red-team review.

## Non-goals

- Implement gameplay code, generate final visual assets, operate live services, or replace licensed legal, financial, clinical, or moderation advice.
- Diagnose players or staff as people. Frameworks describe testable moment-level hypotheses only.
- Treat engagement, revenue, or a design framework as proof of player value.

## Invariants

1. Repository evidence precedes recommendation.
2. Claims are marked observed, documented, measured, or inferred.
3. A full diagnostic loads every domain module and disposes every matrix row.
4. Every material fix has player consequence, alternatives, owner, scope, risk, and validation.
5. Player welfare, informed choice, accessibility, and social trust constrain optimization.
6. Upstream material is never copied: this library is independently authored and carries source identifiers only for coverage maintenance.
7. Improvement requests trigger a greedy evidence-to-change loop: diagnose the actual player path, implement only safe reversible work within repository authority, and measure both player benefit and harm.

## Dependencies

- Local repository inspection tools for deterministic inventory.
- The routed implementation or game-engine skill when changes extend beyond diagnosis.
- Player research, telemetry, or playtests when a recommendation needs evidence unavailable in source.

## Success criteria

- Full diagnostics deliver a complete evidence and coverage ledger.
- A maintainer can trace every assessed source capability to a local card.
- Recommendations are concrete enough to plan and test without pretending certainty.
- Retention and broader improvement requests result in a sequenced implementation-ready improvement backlog, with low-risk fixes acted on when repository authority permits.
- Reference modules remain independently loadable and each stays below the progressive-disclosure budget.
