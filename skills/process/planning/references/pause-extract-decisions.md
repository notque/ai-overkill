# Pause-Work Extract Decisions

Verbatim Phase 3 (EXTRACT DECISIONS) detail. Take the decisions this session made, filter for the ones that warrant ADRs, and draft ADR skeletons for each candidate. This phase runs before WRITE so that ADR data is available for inclusion in both handoff files — passing extracted data downstream is cheaper than appending to files after the fact.

## Step 1: Collect this session's decisions

Use the `decisions` field synthesized in Phase 2, plus any choice made in this session that changed the approach: a tool or library picked over an alternative, a contract fixed between components, a process rule adopted. The session transcript is the source. Record each as one sentence stating the choice and its reason.

## Step 2: Filter for ADR candidates

Apply this heuristic to determine which decisions warrant an ADR vs. which are incidental tips:

| Decision pattern | ADR candidate? |
|-----------------|----------------|
| "After X, always do Y" | Yes — process decision |
| "X depends on Y" | Yes — contract/coupling |
| "Use A instead of B because C" | Yes — architectural choice |
| "X is faster than Y" | Maybe — only if it changes approach |
| "Use --flag for better output" | No — tip, not decision |

Keep only entries that describe process changes, tooling contracts, or architectural choices. Tips and incidental observations don't warrant ADRs because they don't reflect decisions that constrain future work — capturing them as ADRs would dilute the ADR corpus and create noise in architecture documentation.

## Step 3: Draft ADR skeletons (only if candidates found)

Get the next safe ADR number once, then increment for subsequent candidates:
```bash
python3 ~/.claude/scripts/adr-query.py next-number 2>/dev/null || echo "manual"
```

Call `next-number` once for the first candidate. For additional candidates, increment the number manually (e.g., if first returns 132, use 133 for the second) because the script checks existing files on disk and the first skeleton has not been committed yet.

If `adr-query.py` returns "manual", use placeholder numbers and note that the user should assign them before merging.

Draft to `adr/{number}-{slug}.md`:

```markdown
# ADR-{number}: {Title from the decision}

**Status**: Proposed
**Date**: {today}
**Source**: Drafted during a session pause; review before accepting

## Context
{Context that forced the decision}

## Decision
{The choice made, and the reason}

## Validation Criteria
- [ ] {Criterion derived from the decision}
```

Write the file to disk so it is visible in the next session even if Phase 4 fails.

## Step 4: Pass ADR data to Phase 4

Construct a `drafted_adrs` list in memory for use during the WRITE phase:
- If candidates were found: list of `{"number": N, "path": "adr/N-slug.md", "title": "..."}` entries
- If no candidates found: empty list — skip silently, no empty sections in output files
