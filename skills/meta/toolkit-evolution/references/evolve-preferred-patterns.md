# Toolkit Evolution — Patterns, Errors, and Cost

Reference for Phase 3 CRITIQUE (fallback), failure modes, error handling, and cost estimates.

---

## Patterns to Detect and Fix

- **Improving without measuring** -- every change must have a baseline and A/B result. "It looks better" is not evidence.
- **Merging without validation** -- every winner must pass multi-persona critique (STRONG consensus) AND A/B testing (WIN status) before merge. The validation gates are the review.
- **Ignoring negative results** -- failed experiments are valuable data. Record them in the learning DB so the same idea is not re-proposed.
- **Improving everything at once** -- max 3 implementations per cycle. Focus compounds; scatter dissipates.
- **Running without diagnosis** -- do not propose solutions without evidence of problems first. Solutions looking for problems create phantom work.
- **Proposing duplicates** -- always check INDEX.json before proposing a new skill or capability. Extend existing skills when possible.
- **Discovery without evidence** -- the DISCOVER phase requires concrete data points (routing misses, manual workflows, community requests), not speculation. "It might be useful" is not a valid justification.
- **Discovering too often** -- discovery runs monthly, not nightly. Running it every cycle wastes budget on perspective agents that will produce the same gaps repeatedly.

---

## Error Handling

### Error: "learning-db.py not found"
Cause: Telemetry scripts not installed.
Solution: The CLI is at `~/.claude/scripts/learning-db.py`. If missing, skip the telemetry queries and diagnose from git log and dream reports. Record this gap as an improvement opportunity.

### Error: "No dream reports found"
Cause: Auto-dream has not run yet or state directory is empty.
Solution: Proceed without dream insights. Use git log and routing telemetry as primary data sources. Note that enabling auto-dream would improve future evolution cycles.

### Error: "No STRONG proposals after critique"
Cause: All proposals received MODERATE or WEAK consensus.
Solution: Report to the user that no high-confidence improvements were found this cycle. Record the proposals and critique feedback in the evolution report for future reference.

### Error: "A/B test inconclusive"
Cause: Test cases don't discriminate between baseline and candidate.
Solution: Review test case quality. Non-discriminating tests ("file exists") provide false signal. Write tests that exercise the specific behavior the proposal changes. If still inconclusive after better tests, shelve the proposal.

### Error: "Feature branch conflicts"
Cause: Multiple evolution implementations touch the same files.
Solution: Reduce to 1 implementation per cycle when conflicts arise. Alternatively, sequence implementations so later ones branch from earlier ones.

---

## Cost Estimate

A full evolution cycle runs all 7 phases and may dispatch multiple subagents. Estimated cost:
- Discovery (Phase 0, monthly): ~$0.50-0.75 (5 parallel perspective agents + dedup)
- Diagnosis + Proposal: ~$0.15 (reading files, querying DBs)
- Critique: ~$0.30 (3 persona agents evaluating proposals)
- Build: ~$0.50-1.50 (1-3 implementation agents)
- Validate: ~$0.50-1.50 (A/B test runs)
- Evolve: ~$0.10 (PR creation, learning DB writes)

Total without discovery: ~$1.50-3.50 per cycle. With discovery: ~$2.00-4.25.
Budget capped at $5.00 via wrapper script.
Nightly cost at full utilization: ~$45-105/month. Discovery adds ~$0.50-0.75/month (runs monthly, not nightly). Cycles with no STRONG proposals exit early (diagnosis + proposal only: ~$0.45).

---

## Phase 3 Inline Critique Fallback

Use this when `multi-persona-critique` skill is NOT available. Dispatch 3 parallel agents:

**Pragmatist**: "You are a pragmatist engineer. Evaluate each proposal on: implementation feasibility, time-to-value, and risk of unintended side effects. Rate each STRONG/MODERATE/WEAK with one sentence of justification."

**Purist**: "You are an architecture purist. Evaluate each proposal on: design coherence with existing toolkit patterns, long-term maintainability, and whether it solves a root cause vs a symptom. Rate each STRONG/MODERATE/WEAK with one sentence of justification."

**User Advocate**: "You are a user advocate. Evaluate each proposal on: how often real users hit this problem, whether the solution reduces friction, and whether it introduces new complexity users must learn. Rate each STRONG/MODERATE/WEAK with one sentence of justification."

Scoring: STRONG = 3, MODERATE = 2, WEAK = 1. Average across personas.
- Score >= 2.5 = STRONG consensus
- Score 1.5-2.4 = MODERATE consensus
- Score < 1.5 = WEAK consensus (shelve)

---

## Phase 0 DISCOVER — Perspective Agents

Brief all 5 agents with the same baseline data from `references/diagnose-scripts.md` § DISCOVER Step 1. Dispatch all 5 simultaneously:

| Agent | Perspective | What it looks for |
|-------|------------|-------------------|
| **The User** | Reads routing telemetry for weak and error-prone routes (`python3 scripts/learning-db.py route-health`, then `route-stats --by errors`) and requests that landed on `general-purpose` with no specialist. "What did users ask for that we couldn't handle?" |
| **The Operator** | Examines the active projects (check git repos in `~/`) for repeated manual workflows that could be skills. "What am I doing by hand that should be automated?" |
| **The Strategist** | Uses the business-ops skill's (formerly csuite) EVALUATION mode thinking: what decision-support, content, or process skills would make the owner more effective? Reads `skills/business/business-ops/SKILL.md` for framework. "What high-leverage skills are we missing?" |
| **The Community** | Web-searches for what people are building and requesting in AI coding communities (Claude Code GitHub issues, Reddit, X/Twitter). "What does the market want?" |
| **The Architect** | Examines current skill categories (from `skills/INDEX.json`) for structural gaps. Cross-references with `agents/INDEX.json`. "Where are the architectural blind spots?" E.g., "we have 23 process skills but 0 decision skills." |

Each agent produces 2-3 skill proposals in this format:

```
PROPOSAL: {skill-name}
Category: {category}
Triggers: {3-5 routing triggers}
Justification: {1-2 sentences on why this is needed}
Evidence: {what data supports this -- routing gaps, user patterns, market signals}
```

---

## Scheduling (Cron Setup)

Runs nightly at 3:07 AM, after auto-dream (2:07 AM) finishes consolidating learnings:

```bash
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "toolkit-evolution" \
  --schedule "7 3 * * *" \
  --command "/home/feedgen/vexjoy-agent/scripts/toolkit-evolution-cron.sh --execute >> /home/feedgen/vexjoy-agent/cron-logs/toolkit-evolution/cron.log 2>&1"
```

Schedule uses 3:07 AM (off-minute per cron best practice, 1 hour after auto-dream). Budget set to $5.00 per run.

Manual invocation:
```
/evolve
/evolve routing
/do evolve toolkit
/do evolve hooks
```
