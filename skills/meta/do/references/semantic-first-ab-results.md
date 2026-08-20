# Semantic-First Routing: Unrun A/B Protocol

**Status: UNRUN.** `scripts/routing-ab-results/answers/README.md` states that the live routing run was never executed. No accuracy, cost, bucket, regression, or prompt-fix result from this protocol is evidence.

## Hypothesis

Test whether model-first intent routing with deterministic force-route safeguards performs at least as well as deterministic-first routing while reducing false positives from metaphorical git language.

## Planned protocol

- Corpus: 49 benchmark and paraphrase cases.
- Arm A: deterministic pre-router first, semantic router on fallthrough.
- Arm B: semantic router first, deterministic safety-critical override second.
- Blind scoring: de-identify arms, judge each route against the registered expected route, and record strict and partial accuracy.
- Safety gate: no new misses in force-route, false-positive-guard, git paraphrase, or security paraphrase cases.
- Artifacts expected after execution: answer files for both arms, judge output, scoreboard, and a gate verdict.

## Current decision basis

The shipped semantic-first structure is an architectural choice grounded in the toolkit's plain-English interface and deterministic safety-net design. This unrun protocol does not validate that choice. Use completed experiments in `docs/router-ab-runbook.md` for measured routing claims.

## Execution requirement

Do not add numeric results to this file until both arm outputs and the blind scoreboard exist under `scripts/routing-ab-results/`. When executed, preserve this protocol, link the immutable run directory, and report observed results separately from hypotheses.
