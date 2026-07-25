---
name: codex
description: "Run benchmark-selected GPT-5.6 work through the Codex CLI."
user-invocable: false
compatibility: "Requires codex CLI on PATH; /do supplies the selected GPT-5.6 model and reasoning effort."
routing:
  force_route: true
  triggers:
    - through codex
    - codex exec
    - dispatch to codex
    - run on codex
    - codex analysis
    - gpt-5.6
  pairs_with:
    - data-analysis
    - pr-workflow
  complexity: Medium
  category: meta
---

# Codex — the GPT-5.6 Execution Lane

Run a benchmark-selected GPT-5.6 task through the Codex CLI (`codex exec`) and return the result. This is the OpenAI execution lane — the general-purpose lane for work the model-selection policy sends to GPT-5.6, and the **canonical owner of general `codex exec` mechanics** — when the CLI changes, update here first. GPT selections are reachable only through this CLI; the Agent tool's `model` parameter covers Claude models only.

**Under Claude Code, this skill runs only on explicit invocation or cross-provider escalation, never as the automatic default.** The harness-native model lane under Claude Code is the Anthropic lane (Opus 5). This skill is a deliberate cross-provider tool — codex review as a second-opinion, codex exec for a GPT-specific constraint — not a routing default.

Two flows keep their own specialized codex integration — route to them instead of re-implementing here:

| Existing flow | Owns | Where |
|---|---|---|
| PR / code review via codex | `codex exec review`, finding triage, report synthesis | `skills/process/pr-workflow/references/codex-review.md` |
| Sprite/image generation backend | codex image backend selection and invocation | `skills/game/game-sprite-pipeline/references/backend-chain.md` |

## Phase 1: DECIDE — does this task belong on GPT-5.6?

Policy mirror — canonical copy: `/do` SKILL.md, Model Selection (edit there first, then here). Rankings, higher = better; cost = avg USD per task, written as a plain number (slash-command templating corrupts dollar-digit sequences in injected skill bodies), what the owner actually pays.

| Task class | Model / effort | DeepSWE Pass@1 / cost / output tokens / steps |
|---|---|---|
| Low-risk assistance | `gpt-5.6-terra` / `high` | 54 / 1.13 / 22k / 34 |
| Standard implementation | `gpt-5.6-sol` / `high` | 69 / 3.47 / 28k / 37 |
| High-risk implementation or review | `gpt-5.6-sol` / `xhigh` | 71 / 4.70 / 41k / 44 |
| Exceptional explicit escalation | `gpt-5.6-sol` / `max` | 73 / 8.39 / 60k / 61 |

Run deterministic work as scripts, not through Codex. The `/do` model policy selects the lane and passes model plus effort. Legacy GPT-5.5, all Luna choices, and the other non-default GPT-5.6 settings are manual-only; do not substitute them automatically. Luna `max`, for example, saves 0.44 USD versus Sol `high` but consumes 45k more output tokens and 65 more steps for two fewer Pass@1 points. Consult the canonical table in `/do` SKILL.md.

These are defaults, not limits. Standing permission to escalate when output misses the bar applies within the policy; `max` still needs an explicit override. For anything that ships, intelligence > taste > cost; cost is a tie-breaker only.

**Gate**: task has a GPT-5.6 policy selection. Otherwise route to scripts or the policy's Claude pick and stop here.

## Phase 2: WRAP — how GPT-5.6 runs from this harness

**Wrapper symmetry**: the wrapper is needed for whichever model family is NOT the current harness.

- **Under Claude Code** (current default): GPT-5.6 runs through a wrapper — either the dispatched agent runs `codex exec` via Bash with a self-contained prompt, or a thin Claude wrapper agent (`model: "sonnet"`, low effort) writes the self-contained codex prompt, runs it, and returns the result.
- **Under the Codex harness**: Claude models require the wrapper instead.
- Claude models under Claude Code need no wrapper — just the Agent/Workflow `model` parameter.

Pick the direct-Bash form when the calling agent already holds the task context; pick the thin wrapper agent for fan-out (one wrapper per data source) so the orchestrator stays lean.

**Availability check first**: `command -v codex` — when absent, fall back to the policy's Claude pick (`model: "sonnet"` for mechanical work) and tell the user in one line which lane ran.

## Phase 3: PROMPT — write a self-contained prompt

Codex runs in its own process with no conversation history. The prompt must carry everything:

1. **Context** — one short paragraph: what the repo/data is, what state matters.
2. **Task** — the concrete operation, with file paths relative to the working directory. Let codex read files itself; embedding large content wastes tokens and loses formatting.
3. **Output format** — the exact structure to return (table, JSON, diff), so the wrapper can consume it without a second pass.

**Prompt hygiene (hard rule)**: codex prompts leave the machine. Send only public content — secrets, credentials, and private component names (anything sourced from `INDEX.local.json` or other local-only inventories) stay out. Run the deterministic scan on the prompt text before executing:

```bash
printf '%s' "$PROMPT" | rg -n "Bearer|Authorization|token|secret|api[_-]?key|password|PRIVATE KEY" && echo "HYGIENE VIOLATION"
```

On a hit or a private component name: scrub the flagged content when the task survives without it; otherwise reroute the task to a Claude model. A bare refusal is not an outcome.

## Phase 4: RUN

Pass the policy-selected model and effort explicitly. Do not rely on a local default that can silently select a deprecated model.

**Investigation / data analysis (default for anything that only reads):**

Set `CODEX_MODEL` and `CODEX_EFFORT` from the `/do` selection before invoking
the CLI; do not substitute a local default.

```bash
TMPFILE=$(mktemp)
codex exec -m "$CODEX_MODEL" -c "model_reasoning_effort=\"$CODEX_EFFORT\"" -s read-only --skip-git-repo-check -o "$TMPFILE" "$(cat <<'PROMPT'
[self-contained prompt]
PROMPT
)"
cat "$TMPFILE"
```

`-s read-only` sandboxes the run to reads — verified working on this host. Use it for every investigation or analysis prompt not covered by an existing codex flow, because a read-only task never needs write access and the sandbox makes that deterministic.

**Write tasks (clear-spec implementation, migrations):** drop `-s read-only`; run from the target repo's working directory; review the diff (`git status --short`, `git diff`) before committing anything.

**Reviews:** use `codex exec review` via the pr-workflow codex-review flow (table above), not a hand-rolled prompt.

**Gate**: exit code 0 AND output matches the requested format. Non-zero exit: report stderr and stop — codex failures are auth/API/prompt-length issues that a blind retry won't fix. Verify the output against a deterministic check where one exists (counts, file lists, test runs) before passing it upstream — GPT-5.6 output is evidence, not verdict. State the model and effort in the result so the caller can apply the escalation rule.

## Error handling

### `codex: command not found`
Cause: Codex CLI not installed on this host.
Solution: fall back to the policy's Claude pick (`model: "sonnet"` for mechanical work) and report which lane ran; install via the owner's codex setup when authorized.

### Sandbox error mentioning bwrap / `Failed RTM_NEWADDR`
Cause: the bwrap sandbox fails in some containerized/VM environments.
Solution: for read-only work, retry without `-s read-only` only if the environment already provides external sandboxing (Claude Code does); `-s read-only` and `--dangerously-bypass-approvals-and-sandbox` are mutually exclusive — use one.

### Output missing or truncated in `-o` file
Cause: prompt exceeded length limits or codex wrote to stdout only.
Solution: shorten the prompt (point codex at files instead of embedding content); capture stdout as fallback.

## References

- `/do` SKILL.md, Model Selection — canonical policy table and routing decision rules
- `skills/process/pr-workflow/references/codex-review.md` — review-specific codex flow
- `skills/game/game-sprite-pipeline/references/backend-chain.md` — codex image backend
