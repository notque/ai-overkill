---
name: retro
description: "Retrospective reader: the negative-results registry plus routing and review telemetry."
user-invocable: true
argument-hint: "[what-didnt-work|routing|reviews]"
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
routing:
  triggers:
    - "what didn't work"
    - "negative results"
    - "route health"
    - "routing telemetry"
    - "routing stats"
    - "review roi"
    - "review false positives"
  category: meta-tooling
  pairs_with:
    - do
---

# Retro Skill

## Overview

Read-only retrospective front door. Two things to read: `docs/what-didnt-work.md`, the negative-results registry that records which experiments lost; and the routing and review telemetry in `learning.db`, queried through `scripts/learning-db.py`. Both are stores this skill reports on — it records nothing itself. Hooks write the telemetry; humans write the registry.

---

## Instructions

Parse the user's argument to pick the subcommand. Default to `what-didnt-work` when no argument is given.

| Argument | Subcommand |
|----------|------------|
| (none), what-didnt-work, negative results | **what-didnt-work** |
| routing, route health, route stats | **routing** |
| reviews, review roi, false positives | **reviews** |

### Subcommand: what-didnt-work

Print the negative-results registry, the list of experiments that lost. Read it before re-running an experiment so a known-dead path is not retried.

The registry is a doc, not a DB table: `docs/what-didnt-work.md` is the capture, store, and query target.

**Step 1**: Read and print the registry.

Use the Read tool on `docs/what-didnt-work.md` and present it. Group by the dated `## YYYY-MM-DD` headings; show each entry's Decision verdict (rejected / deferred / revisit-if) up front so a scan answers "did we already reject this?".

```
NEGATIVE RESULTS (docs/what-didnt-work.md)
==========================================

## [date] [experiment]
  Decision: [rejected | deferred | revisit-if <condition>]
  What happened: [one line]
...
```

If the file is missing, report that no negative results are recorded yet and point the user at the format in `CONTRIBUTING.md`.

**Step 2**: To search the registry, grep the doc.

```bash
grep -n -i "TERM" docs/what-didnt-work.md
```

The doc is the single store. Keep a parallel copy nowhere — a second store drifts from the canonical one and answers stale.

### Subcommand: routing

Report routing feedback-loop health from the telemetry hooks write.

**Key constraint**: Present results as readable tables or sections, not raw JSON. Every command here is read-only.

**Step 1**: Run the health check.

```bash
python3 ~/.claude/scripts/learning-db.py route-health
```

**Step 2**: Add the dimension the user asked about. `--by` is required.

```bash
python3 ~/.claude/scripts/learning-db.py route-stats --by agent    # or skill, force-route, errors, override, week, day
python3 ~/.claude/scripts/learning-db.py route-weights             # health-aware re-rank input
python3 ~/.claude/scripts/learning-db.py stack-usage               # enhancement skills seen stacked
```

**Step 3**: To compare two cohorts before and after a change, name both refs.

```bash
python3 ~/.claude/scripts/learning-db.py route-delta --from SHA_OR_DATE --to SHA_OR_DATE [--key agent:skill] [--metric error|tokens]
```

**Step 4**: Present the report.

```
ROUTE HEALTH
============

Outcome basis:   [share scored from explicit signal vs neutral]
Silent success:  [share]
Top routes:      [key — dispatches, error rate]
Weakest routes:  [key — dispatches, error rate]
```

Read the outcome basis before reading the rates. A rate computed mostly from neutral outcomes describes the scorer, not the router.

### Subcommand: reviews

Report reviewer cost and precision.

```bash
python3 ~/.claude/scripts/learning-db.py review-roi                       # per-tier cost vs findings
python3 ~/.claude/scripts/learning-db.py review-fps [--limit N]           # false positives by reviewer agent
```

Present ROI per tier alongside the false-positive count for the same agent — a tier with high findings and high false positives is expensive twice.

---

## Examples

### Example 1: Check a settled question before re-running an experiment
User says: "/retro what-didnt-work"
Actions: Read `docs/what-didnt-work.md`, present entries newest first with each Decision verdict up front.

### Example 2: Routing health check
User says: "/retro routing"
Actions: Run `learning-db.py route-health`, then `route-stats --by agent`, present outcome basis first, then per-route rates.

### Example 3: Which reviewer tier earns its cost
User says: "/retro reviews"
Actions: Run `learning-db.py review-roi` and `review-fps`, present cost, findings, and false positives per agent in one table.

---

## Error Handling

### Error: "learning.db not found"
Cause: No routing telemetry recorded yet in this environment.
Solution: Report that no telemetry exists. The routing hooks populate it during normal dispatches; run a session with hooks synced, then re-check.

### Error: "route-stats: the following arguments are required: --by"
Cause: `route-stats` aggregates along one dimension and has no default.
Solution: Re-run with an explicit dimension: `--by agent`, `skill`, `force-route`, `errors`, `override`, `week`, or `day`.

### Error: `docs/what-didnt-work.md` missing
Cause: The registry has not been created in this checkout.
Solution: Report that no negative results are recorded and point at the six-field format in `CONTRIBUTING.md` (date, experiment, expectation, what happened, evidence, decision).

---

## References

- `~/.claude/scripts/learning-db.py` — read-only CLI for routing and review telemetry
- `docs/what-didnt-work.md` — negative-results registry; the doc is the canonical store
- `skills/meta/do/references/routing-telemetry.md` — which hook records what, and the route-failure protocol
- `hooks/session-context.py` — injects the overnight dream payload at session start
