# /do Learning Capture (automatic)

Hooks capture everything. Router records one case manually: observed route failures (below).

| Capture | Hook | Event |
|---|---|---|
| Routing decision (`{agent}:{skill}`) + right-sizing feedback | `routing-decision-recorder` | PostToolUse:Agent |
| Outcome - validate pending | `routing-outcome-recorder` | SubagentStop |
| Outcome - finalize (boost/decay) | `routing-outcome-finalizer` | UserPromptSubmit |
| Outcome - session-end fallback | `session-learning-recorder` | Stop |
| Tool errors | `error-learner` | PostToolUse |
| Review findings | `review-capture` | PostToolUse:Agent |

Feeds the route health report in `learning-db.py`.

**Outcome fidelity.** Deterministic on next user turn, zero LLM cost, THREE-WAY: failure on errors/rejection (decay); success on explicit acceptance (boost); neutral otherwise. No complaint ≠ acceptance. Stop fallback: errors→failure, clean→neutral.

**Report route failures** (HIGH-CONFIDENCE only):

```bash
REASON_FILE=$(mktemp); printf '%s' "<cause>" > "$REASON_FILE"
python3 ~/.claude/scripts/learning-db.py route-failure AGENT:SKILL --reason-file "$REASON_FILE" --routing-relevant yes --session $SESSION --marker $DISPATCH_ID
rm -f "$REASON_FILE"
```

Triggers: re-route, lazy re-dispatch, validator misroute, harness reject. Right route + bad execution → `--routing-relevant no`. Ambiguous → skip. Decays one per dispatch key. Temp file avoids shell splicing.

**Optional:** curated insight via `retro`: `learning-db.py learn --skill <name> "insight"` or `--agent <name> "insight"`. Routing rows (`category=effectiveness`) excluded from `retro graduate`.

---

## Re-deriving the router's prose figures

SKILL.md quotes two telemetry figures in the Agent-greediness and Pairing rules. Each is a DATED observation, not an invariant: no test pins it, because pinning a live DB read would make CI depend on runtime data. Re-measure before editing either number — a swapped figure with no query behind it is how the earlier "82% carried a correct specialist skill" claim became unreproducible ("correct" is not a recorded column, so nothing could confirm or refute it).

Source: `evidence_route_decisions` in `~/.claude/learning/learning.db` (two other learning.db files exist and lack this table). Read-only:

```bash
DB=~/.claude/learning/learning.db
# general-purpose share  -> 128/301 = 42.5% (2026-08-15)
sqlite3 "$DB" "SELECT COUNT(*) FILTER (WHERE agent='general-purpose'), COUNT(*) FROM evidence_route_decisions;"
# named domain skill on those dispatches -> 92/128 = 72% (2026-08-15)
sqlite3 "$DB" "SELECT COUNT(*) FILTER (WHERE skill IS NOT NULL AND skill NOT IN ('','-','objective-loop')), COUNT(*) FROM evidence_route_decisions WHERE agent='general-purpose';"
```

State the metric as the query computes it. "Named domain skill, fallbacks excluded" is reproducible; "correct skill" is not.

**Combination depth — the definition decides the number.** Depth counts filled slots with fallbacks excluded: agent named and other than `general-purpose`, skill named and other than `objective-loop`, pipeline present, stack present. The exclusion IS the metric: `general-purpose` plus `objective-loop` is the impoverished route, so scoring those slots as filled would count the failure mode as a success. Counting any value present instead returns 2.48 and 10.3% on the same rows — a healthier number for identical data, and the reason a depth figure quoted without its definition is worthless.

```bash
sqlite3 "$DB" "SELECT ROUND(AVG(depth),2), ROUND(100.0*SUM(depth<=1)/COUNT(*),1) FROM (
  SELECT (agent IS NOT NULL AND agent NOT IN ('','-','general-purpose'))
       + (skill IS NOT NULL AND skill NOT IN ('','-','objective-loop'))
       + (pipeline IS NOT NULL AND pipeline NOT IN ('','-'))
       + (stack IS NOT NULL AND stack NOT IN ('','-','[]')) AS depth
  FROM evidence_route_decisions);"   # -> 2.01 | 29.2   (2026-08-15, n=301)
```

Report depth against a REACHABLE maximum. `pipeline` and `matched_components` are NULL on all 301 rows — both columns landed after those rows were written — so the ceiling on this data is 3, not 4. "Mean 2.01 of 4" overstates the shortfall, and "0% at depth 4" describes the schema rather than the router. SKILL.md therefore cites only the 29.2% half, which stays meaningful as the pipeline column fills because a new pipeline pick can only move a row up and out of that bucket. Confirm the ceiling before quoting the mean.
