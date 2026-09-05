# Explicit model selection

Use this reference only when choosing a model override or a legacy policy. The normal `/do` dispatch uses `model: "inherit"` and omits model and effort overrides from the agent tool call. The builder produces a prompt; the dispatcher must apply that instruction.

## Compatibility policies

`scripts/build-dispatch.py` owns accepted model names, provider policies, effort validation, and override rules. Existing explicit selections remain supported. Set `provider` from the actual harness, not the first installed scripts directory. `model_policy` selects the provider's existing table below; provider `other` requires a supported explicit model instead. `deterministic` means run a script, not an LLM dispatch.

- `max-power` requires `manual_model_override=true`.
- A model different from a policy's choice requires `manual_model_override=true` and an explicit `model_effort`.
- Explicit GPT-5.6 choices require effort and manual override. GPT-5.5 and Sonnet require manual override. Opus/max requires manual override.
- Claude effort is advisory when the agent tool has no effort parameter. Only pass options the tool supports.
- Cross-provider calls remain deliberate, explicit choices. Do not infer a cross-provider upgrade from historical scores.
- A route marker records a requested selection. It does not establish which model ran. Report actual identity only from harness execution metadata.

## Historical measurements and policy tables

These are the previously recorded DeepSWE measurements and compatibility policy choices, retained for reference. They are not measurements of the current session or proof of current model quality. Opus 5 was an owner-directed default without a DeepSWE run. The builder's named policies retain those choices for existing callers; inheritance does not use them.

Measurement cells: Pass@1 / average USD per task / output tokens / steps. Higher Pass@1 is better; the other values are lower-is-better. Policy tables show the historical rationale; “current session model” below refers to the original policy context, not the active session.

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| Opus-5 (current default, unmeasured) | n/a — not yet benchmarked | n/a — not yet benchmarked | n/a — not yet benchmarked | n/a — not yet benchmarked | n/a — not yet benchmarked |
| Opus-4.8 (prior measurement) | 59 / 13.22 / 135k / 120 | 54 / 8.01 / 86k / 95 | 52 / 4.28 / 50k / 73 | 49 / 3.44 / 41k / 66 | 41 / 2.29 / 29k / 54 |
| Sonnet-5 (prior measurement) | 54 / 26.40 / 214k / 268 | 50 / 11.89 / 121k / 186 | 48 / 7.43 / 87k / 147 | 40 / 4.08 / 57k / 108 | 31 / 2.19 / 36k / 77 |

| Task class | Selection | pts/$ | Why |
|---|---|---|---|
| deterministic | no LLM | — | Run the script directly. |
| low-risk | `opus` / `low` | n/a | Current session model, owner-directed default; effort floor per start-low. |
| standard | `opus` / `medium` | n/a | Current session model, owner-directed default; one tier up for standard work. |
| high-risk | `opus` / `high` | n/a | Current session model, owner-directed default; high effort for risk-bearing work. |
| max-power | `opus` / `xhigh` | n/a | Current session model, owner-directed default; `manual_model_override=true`; state justification in task_spec intent. |

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| GPT-5.6 Sol | 73 / 8.39 / 60k / 61 | 71 / 4.70 / 41k / 44 | 69 / 3.47 / 28k / 37 | 61 / 1.86 / 18k / 31 | 45 / 1.07 / 11k / 23 |
| GPT-5.6 Terra | 70 / 4.95 / 72k / 76 | 60 / 2.13 / 40k / 43 | 54 / 1.13 / 22k / 34 | 35 / 0.58 / 12k / 25 | 24 / 0.43 / 8.6k / 21 |
| GPT-5.6 Luna | 67 / 3.03 / 73k / 102 | 57 / 1.54 / 45k / 71 | 44 / 0.78 / 26k / 49 | 11 / 0.22 / 8.2k / 24 | 2 / 0.07 / 3.1k / 12 |
| GPT-5.5 legacy | n/a | 67 / 7.23 / 46k / 82 | 64 / 5.10 / 31k / 62 | 54 / 2.75 / 20k / 46 | 27 / 1.20 / 9.4k / 28 |

| Task class | Selection | pts/$ | Why |
|---|---|---|---|
| deterministic | no LLM | — | Run the script directly. |
| low-risk | `gpt-5.6-terra` / `high` | 47.8 | 54 Pass@1 at 1.13, 22k tokens, 34 steps. |
| standard | `gpt-5.6-sol` / `high` | 19.9 | 69 Pass@1 at 3.47, 28k tokens, 37 steps. |
| high-risk | `gpt-5.6-sol` / `xhigh` | 15.1 | 71 Pass@1 at 4.70, 41k tokens, 44 steps. |
| max-power | `gpt-5.6-sol` / `max` | 8.7 | 73 Pass@1 at 8.39, 60k tokens, 61 steps; `manual_model_override=true`; state justification in task_spec intent. |
