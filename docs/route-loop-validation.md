---
summary: "Evidence record: routing-health sensor kept, actuator dropped."
read_when:
  - "evaluating routing-health changes"
  - "checking why the route actuator was dropped"
---

# Route Loop Validation: Sensor Kept, Actuator Dropped

Branch: `feat/route-sensor`. Date: 2026-06-10. Audience: a skeptical reader
who wants proof, not prose.

## Update 2026-07-24: in-context weights read retired

The Step 1.5 read (`learning-db.py route-weights --json`) is removed from
`/do`. Cost: 42,659 bytes (~10,700 tokens) injected into the coordinator on
every routing decision. Yield across 1,037 routed dispatches: would-action
`keep` 81/81; `route-signal-check.py` NO-SIGNAL — 0 would-demote,
0 would-tiebreak. The actuator was already dropped (PR #755), so the read
bought telemetry the policy never used to change a route.

Still live: the route event log, three-way outcome finalization, the
orchestrator-reported `route-failure` channel, and the `[do-route]` marker
format — the marker now always carries `health=-`. The would-action leg of
the re-propose condition below cannot fire (no would-action is computed);
re-proposal now keys on the first routing-relevant failure event alone.
Re-proposing the actuator re-introduces the weights read with it.

Working notes: the `routing-loop-value-eval` ADR (local-only; the `adr/` directory is gitignored).

---

## Decision

The outcome-routing loop was split. The **sensor** merges; the **actuator**
was closed with PR #755.

**Kept (sensor, ~600 LOC):** route event log (`route-events.jsonl`), three-way
outcome finalization (failure / success / neutral), the orchestrator-reported
route-failure channel (`learning-db.py route-failure`), the pure policy lib
(`scripts/lib/route_policy.py`), and shadow instrumentation on every `/do`
dispatch. Step 1.5 is **shadow-only**: the policy's would-action is computed
and logged; the route is never altered.

**Dropped (actuator + oversized measurement):** active Step 1.5 re-rank,
`route-value-eval.py` (652 LOC), `route-decommission-check.py` (454 LOC),
`route-replay.py`, and their tests.

### Why

| Evidence | Finding |
|----------|---------|
| unknown_rate 0.98 | Only 2 of 101 recorded decisions ever joined an outcome. The decommission clock's validity gate (`unknown_rate <= 5%`) can never pass on this data; the kill switch was dead on arrival. |
| Demote floor unreachable | 133 routes in the weights table, minimum confidence 0.5, zero recorded failures ever. The floor (`conf < 0.30 AND fail >= 3 AND n >= 5`) matches no row and cannot until negative signal exists. |
| k=0 STRUCTURAL | In the live blind A/B, all 39 floor hits were force-route-exempt (39/39); the health arm never diverged. Value was structurally unmeasurable, not pending. |

An actuator whose trigger cannot fire and whose kill switch cannot validate is
dead weight. The sensor stays because it is the only path to the negative
signal that would justify re-proposing the actuator.

### Re-propose condition

Re-propose the actuator when `scripts/route-signal-check.py` exits 3 — that
is, on the **first routing-relevant failure event** OR the **first non-neutral
would-action** (would-demote or would-tiebreak) recorded on a decision. Exit 0
means no signal yet; keep waiting.

```bash
python3 scripts/route-signal-check.py   # exit 0 = no signal; exit 3 = re-propose
```

---

## Sensor mechanism

Every `/do` dispatch is scored, never altered:

1. The router reads route weights (`learning-db.py route-weights`) and calls
   `health_adjust(semantic_pick, alternates, weights, force_route_flags)`
   (`scripts/lib/route_policy.py`). The returned `action`
   (`keep | demote | tiebreak`) is the policy's would-action only.
2. Gate inputs ride the `[do-route]` marker
   (` health={confidence} n={n} fail={failure} action={...}`; ` health=-`
   when no weight row; ` alts=` when alternates were passed).
3. `routing-decision-recorder` snapshots them onto the per-dispatch DECISION
   event in `<CLAUDE_LEARNING_DIR>/route-events.jsonl`.
4. Outcomes finalize three-way: **failure** on tool errors or clear
   rejection/rework/re-route (decay); **success** only on an explicit
   acceptance marker (boost); **neutral** otherwise (no-op). No complaint is
   NOT acceptance.
5. **Weak-positive** (C6, ADR router-improvement-program): a would-be-neutral
   entry upgrades to **weak_success** when the same `agent:skill` pair was
   finalized non-failure earlier in the same session — a repeat dispatch with
   no intervening failure means the user kept re-using the route. Bounded:
   +0.02 per event, clamped so weak boosts never lift confidence past 0.65
   (strictly below the 0.70 high-confidence/injection threshold — crossing it
   requires explicit acceptance); `success_count`/n still accrue at the cap,
   so the n>=5 evidence gate becomes reachable. Guards: the entry must be
   clean (tool errors still decay, unchanged), and any rejection on the turn
   — even an unattributable multi-dispatch one — suppresses the upgrade. The
   upgrade reads dispatch history (per-key, per-session, in the bridge state
   file), never prompt text: the reaction detector is unchanged, and a first
   dispatch followed by an unrelated prompt stays a neutral no-op. Basis label
   `repeat_dispatch_weak`; event outcome `weak_success`, reason
   `repeat-dispatch-no-failure`. This closes the signal starvation that held
   every weight at 0.5/n<5 (success previously required an explicit acceptance
   marker that almost never appears).
6. The orchestrator reports routing failures it observes directly via
   `learning-db.py route-failure` (ADR orchestrator-reported-route-failures,
   local working document). `--routing-relevant yes` decays the pair;
   idempotent per (session, marker).

Force-route/security pairs are hard-exempt in the policy — checked first,
always `keep`. Exemption is by skill name and accepts bare skill names or full
`agent:skill` pairs.

---

## Evidence retained from the actuator evaluation

These results justified the split and are kept for the record. The harness
that produced them is dropped; the numbers are final, not reproducible here.

### Live blind A/B (2026-06-07, k=0 root cause)

97 scored picks over 117 live answers. The cause of k=0 is structural, not a
silent failure:

| Finding | Count |
|---------|-------|
| Picks on the demote floor (`conf<0.30, fail>=3, n>=5`, synthetic weights) | 39 |
| Of those, force-route exempt | 39 (all) |
| Low-confidence picks with an evidenced alternate (tie-break fuel) | 0 |
| Counterfactual demotes if exemption stripped | 26 / 39 |

Under fabricated failure data the loop refused to second-guess safety-critical
routes and had no evidenced alternate anywhere else. It fails safe, not
silent — but it also never acts, which is why the actuator is dropped.

### Live telemetry (post-fix)

| Metric | Value |
|--------|-------|
| non_null_health decisions | 5 |
| recorded routing-relevant failures | 0 |
| decisions joined to an outcome | 2 / 101 (unknown_rate 0.98) |

### Failure channel (temp-DB dogfood)

Proven mechanically; zero live signal yet. This code is kept.

| Property | Result |
|----------|--------|
| Decay per routing-relevant failure | 0.65 → 0.57 |
| Idempotency | per (session, marker) |
| Non-relevant failures | decay nothing |
| Live DB | untouched (`CLAUDE_LEARNING_DIR` temp dir) |

### Router worth-it dogfood

20 tasks, 3 arms, blind-evaluated. Justifies the Haiku router itself, not the
actuator.

| Arm | Exact-pair | Agent-level |
|-----|-----------|-------------|
| Haiku router | 80% (16/20) | 95% (19/20) |
| Codex | 80% (16/20) | 85% (17/20) |
| Deterministic pre-route alone | 30% (6/20) | 75% (15/20) |

---

## Review provenance

Dual-track review, 2026-06-07, covered the full branch including all sensor
code kept here.

| Track | Scope | Output |
|-------|-------|--------|
| Claude | 26 reviewers, 3 waves | 112 findings; 19 actionable Critical/High; 0 contested |
| Codex | codex-cli 0.135.0, read-only sandbox, 3 chunks | 16 distilled findings; 2 false positives caught by source verification |

All Critical/High findings were fixed on the original branch before the split.

---

## Reproduce (sensor)

```bash
# Signal check: expect exit 0 (NO-SIGNAL) today
python3 scripts/route-signal-check.py

# Test suite
python3 -m pytest hooks/tests scripts/tests -q
```

The sensor is read-instrumented only: tests isolate via `CLAUDE_LEARNING_DIR`;
the live learning directory is never written by the checks above.

---

## Limitations

1. **Production value is UNMEASURED and no longer being measured.** The eval
   harness is dropped; measurement resumes only if the actuator is
   re-proposed.
2. **Zero live negative signal.** The failure channel is proven mechanically
   but has recorded nothing live. The re-propose condition keys on this.
3. **Single-user corpus.** All retained evidence comes from one user's tasks.
4. **Synthetic weights.** The A/B floor-hit numbers were produced under
   fabricated failure data, labeled SYNTHETIC-WEIGHTS in the original runs.
5. **Outcome join rate was 0.02.** Until the three-way finalizer raises it,
   any future clock or value measurement inherits the same problem.
