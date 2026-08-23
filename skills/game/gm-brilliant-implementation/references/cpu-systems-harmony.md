# CPU Systems Harmony

Use this contract whenever S09 finds a delegated or automatic system in scope.
The pipeline stores one versioned `cpu-harmony` artifact and shows the operator
only unresolved obligations.

## Artifact shape

```json
{
  "version": 1,
  "systems": [],
  "obligations": [
    {"id": "CPU01", "applicability": true, "evidence": [], "verdict": "pass", "owner": "name"}
  ],
  "simulation_seed": "stable seed",
  "verdict": "pass"
}
```

Each obligation is `pass`, `fail`, or `not_applicable`. Non-applicability needs
evidence. Any applicable `fail` blocks S14 and implementation.

## Ten canonical obligations

| ID | Obligation | Pass evidence | Hard failure |
| --- | --- | --- | --- |
| CPU01 | Inventory every delegated/automatic system | Every writer, trigger, authority, output, and change scope registered | Unknown writer or incomplete registry |
| CPU02 | Shared-resource conflicts | Ownership, reservation, capacity, and overspend scenarios | Double spend or unowned resource |
| CPU03 | Commitments, deadlines, and attention | One conflict graph covers promises, dates, and scarce attention | Orphan or impossible commitment |
| CPU04 | One-brain/two-hands parity | Player and CPU use the same legality, cost, and result oracle | Divergent rule or hidden CPU advantage |
| CPU05 | Deterministic precedence | Total order and stable tie break for simultaneous intent | Undefined or unstable winner |
| CPU06 | Promise and policy preservation | Before/after proof preserves owned promises and standing policies | Silent cancellation or policy breach |
| CPU07 | Soft failure | Bounded no-op/degrade path preserves draft/book/run/results | Unattended system blocks the core loop |
| CPU08 | Truthful bounded receipts | Receipt separates attempted, applied, skipped, and failed actions | Overclaim, missing failure, or unbounded summary |
| CPU09 | Take-control and give-back | Idempotent takeover/return loses or duplicates no action | Duplicate, loss, or split ownership |
| CPU10 | Cross-system fairness and cognition | Deterministic simulations plus burden/fairness/player-feeling review | Unresolved unfairness, confusion, or attention overload |

## Precedence record

Every shared decision defines source intents, owned facts, resource reservations,
promise/policy constraints, deadline, attention cost, total precedence order,
stable tie breaker, chosen action, rejected actions, and receipt. Randomness may
choose among already-legal equal options only through the save's deterministic
RNG stream.

## CPU-ignore path

Ignoring CPU assistance must preserve the canonical player loop and all player
authority. No CPU-only initialization may be required to draft, book, run,
score, continue, or share. Test both CPU-enabled and CPU-ignored paths against
the same oracle.

## Control transfer

Take control checkpoints pending intent and stops new automatic writes. Give
back transfers one authoritative state and resumes from the next uncommitted
action. A retry reuses the same operation identity. Receipts never claim work
outside their recorded scope.

## Cross-system scenarios

At minimum simulate competing bookings, staff policy plus promise, deadline plus
resource shortage, attention overload, takeover during pending work, give-back
after partial success, retry after failure, and CPU-ignore from a fresh save.
Use historical facts only as seeds; post-start events remain fictional save
state.
