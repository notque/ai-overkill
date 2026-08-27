# Empirical prototype

Use this when observation can settle a high-impact uncertainty faster than more discussion. This is an internal `/do` composition rule, not a user command.

## Contract

1. State one falsifiable question.
2. Name the evidence that would support or reject each option.
3. Build the smallest reversible prototype, spike, benchmark, or mock that can produce that evidence.
4. Time-box the work. Exclude production hardening unless the prototype becomes the chosen path.
5. Run the experiment and preserve the observed result.
6. Emit `Question → Evidence → Verdict → Next action`.

Do not prototype when repository inspection, documentation, or one low-cost human decision can answer the question. Do not treat prototype code as production code without normal implementation and verification gates.
