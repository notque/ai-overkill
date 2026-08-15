#!/usr/bin/env python3
"""Deterministic /do Phase 4 dispatch-preamble builder (ADR: router-improvement-program, C4).

Takes one routing decision as JSON and prints the complete dispatch-prompt
preamble the router prepends to the agent prompt. Hand-assembly of these
blocks dropped mandatory injections; this script is the single source of
truth for every one of them ("LLMs orchestrate, programs execute"):

  1. `[do-route]` marker line — full grammar: agent/skill/complexity/model,
     health gate inputs (`health= n= fail= action=` or `health=-`),
     optional `alts={...}`, optional `stack={...}`, optional `fallback=<slug>`.
     model= is required for medium/complex (errors on omission); trivial/simple
     get `model=-`. skill is required for simple/medium/complex (errors on
     omission). An agent absent from agents/INDEX.json is coerced to
     general-purpose with `fallback=invalid-agent:<name>` (never raises).
     Emitted in the exact shape hooks/routing-decision-recorder.py parses.
  2. Thinking directive by complexity, with slow/fast category overrides.
  3. Token-budget line (input value, else `orchestration.token_budget`
     from .claude/settings.json, default 500000).
  4. Task Specification block from the provided fields.
  5. The four MANDATORY verbatim injections: reference loading,
     completeness, Dense-Complete Writing, base instructions.
  6. Optional worktree rules and LOCAL-ONLY block, on flags.

Input schema (missing optional fields degrade gracefully — block omitted):

    {
      "agent": "python-general-engineer",          // required; unknown => coerced
      "fallback_reason": "no-specialist-match",    // required when the agent is
                                                   // general-purpose; slugified
      "skill": "test-driven-development",          // required for simple/medium/
                                                   // complex; trivial => skill=-
      "complexity": "medium",                      // required enum, case-insensitive:
                                                   // trivial|simple|medium|complex
      "model": "opus",                             // required for medium/complex;
                                                   // optional for trivial/simple
      "model_policy": "standard",                  // optional GPT-5.6 auto lane
      "model_effort": "high",                      // required for explicit GPT-5.6 picks
      "manual_model_override": false,               // required for non-default GPT picks
      "health": {"confidence": 0.72, "n": 6,       // optional; absent/blank
                 "failure": 0, "action": "keep",   // confidence => health=-
                 "alts": ["a:b", "c:d"]},
      "stack": ["s1", "s2"],                       // optional
      "task_spec": {"intent": "...", "constraints": "...", "acceptance": "...",
                    "files": "...", "operator_context": "..."},
      "flags": {"worktree": false, "local_only": false,
                "thinking_override": "slow"|"fast"|null},
      "token_remaining": 480000                    // optional
    }

Usage:
    python3 scripts/build-dispatch.py --json '<routing decision JSON>'
    python3 scripts/build-dispatch.py --json-file /tmp/route.json   # "-" = stdin

Exit codes:
    0 — preamble printed to stdout
    2 — invalid input (message on stderr, nothing on stdout)

Stdlib only. Deterministic: same input, same output, byte for byte.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
DEFAULT_TOKEN_BUDGET = 500000

# ---------------------------------------------------------------------------
# Verbatim injection texts — the ONE place they live. skills/meta/do/SKILL.md
# Phase 4 Step 2 points here instead of quoting them. Changing a word here
# changes every dispatched prompt; keep in lockstep with the files each cites.
# ---------------------------------------------------------------------------

INJ_REFERENCE_LOADING = (
    "Before starting work, consult the Reference Loading Table in your agent .md file "
    "and read the references that match this task."
)

INJ_COMPLETENESS = "Deliver the finished product. Ship the complete thing."

INJ_DENSE_COMPLETE = (
    "Write to the Dense-Complete Writing standard — your structural guide for everything you do. "
    "It governs your output, code comments, any skill or reference files you write, "
    "AND every one of your thinking turns: "
    "(1) shortest accurate word; "
    "(2) cut every word that carries no instruction, rule, or decision; "
    "(3) plain English, not jargon; "
    "(4) concrete over abstract; "
    "(5) heavy qualifications in separate short sentences; "
    "(6) Completeness: treat content as fixed and wording as negotiable: "
    "carry every required point through the draft, then choose the shortest plain words "
    "that say those points exactly. "
    "Say everything the task needs and not one word more. Report what changed, not how. "
    "Full rules: `skills/shared-patterns/dense-complete-writing.md`."
)

INJ_BASE_INSTRUCTIONS = "Before starting work, also load `agents/base-instructions.md` for universal operational rules."

# Route-fit banner. The router has no outcome signal today: 285 of 287 recorded
# dispatches carry a NULL outcome and success is inferred from the absence of a
# complaint, so a timid fallback scores like a correct specialist. This asks the
# one party that knows — the agent that read the task — to say whether the pick
# fit. Kept to one short imperative line: it is paid for on EVERY dispatch.
# Read back by hooks/routing-decision-recorder.py (parse_route_fit); negatives
# decay the route, `ok` never boosts it.
INJ_ROUTE_FIT = (
    "End your reply with this exact final line, nothing after it: "
    "`route-fit: <ok|wrong-agent|wrong-skill|needs-coordinator|underspecified>` — "
    "your honest read of whether this agent and skill fit the task."
)

THINKING_FAST = "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly."

THINKING_SLOW = "Think carefully and step-by-step before responding; this problem is harder than it looks."

WORKTREE_RULES = (
    "Worktree rules: Verify CWD contains .claude/worktrees/. Create feature branch before edits. "
    "Skip task_plan.md. Stage specific files only."
)

# Injection template from skills/shared-patterns/local-only.md.
LOCAL_ONLY_BLOCK = (
    "**LOCAL-ONLY MODE.** Do not push, commit, create PRs, or deploy. "
    "All work stays on disk. Read-only git is fine. The user will decide when to commit."
)

# ---------------------------------------------------------------------------
# Marker grammar. Charsets mirror hooks/routing-decision-recorder.py exactly,
# so every emitted marker is parseable by the real recorder — the round-trip
# tests (scripts/tests/test_build_dispatch.py) assert it against that parser.
# ---------------------------------------------------------------------------

VALID_COMPLEXITY = ("trivial", "simple", "medium", "complex")
# Claude lanes remain supported by the native Agent tool. OpenAI selections
# run through the Codex wrapper lane; their effort is explicit so route events
# retain the actual benchmark choice rather than only a model family.
GPT_56_MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
GPT_56_EFFORTS = ("low", "medium", "high", "xhigh", "max")
LEGACY_GPT_55 = "gpt-5.5"
VALID_MODELS = ("sonnet", "opus", "codex", LEGACY_GPT_55, *GPT_56_MODELS)
VALID_PROVIDERS = ("anthropic", "openai", "other")
ANTHROPIC_MODELS = ("opus", "sonnet")

# DeepSWE Pass@1 / cost benchmark defaults per provider lane.
# `deterministic` deliberately has no model: use scripts.
OPENAI_AUTO_POLICIES = {
    "low-risk": ("gpt-5.6-terra", "high"),  # 54 / $1.13
    "standard": ("gpt-5.6-sol", "high"),  # 69 / $3.47
    "high-risk": ("gpt-5.6-sol", "xhigh"),  # 71 / $4.70
    "max-power": ("gpt-5.6-sol", "max"),  # 73 / $8.39, explicit only
}
# Anthropic lane: Opus 5 is the owner-directed default at every task class
# (it is the model the harness runs). It has no DeepSWE run yet, so these
# points carry no Pass@1/cost annotation — effort still follows
# start-low-escalate-on-miss.
ANTHROPIC_AUTO_POLICIES = {
    "low-risk": ("opus", "low"),
    "standard": ("opus", "medium"),
    "high-risk": ("opus", "high"),
    "max-power": ("opus", "xhigh"),  # explicit only
}
AUTO_POLICIES_BY_PROVIDER = {
    "anthropic": ANTHROPIC_AUTO_POLICIES,
    "openai": OPENAI_AUTO_POLICIES,
}
# Backward compat: tests and the OpenAI-only path reference this name.
AUTO_MODEL_POLICIES = OPENAI_AUTO_POLICIES
VALID_MODEL_POLICIES = ("deterministic", *AUTO_MODEL_POLICIES)
# Complexities that REQUIRE an explicit model pick (omission inherits the
# session main-loop model — a silent cost leak when an expensive model
# orchestrates). Trivial/simple may omit (inheritance risk is acceptable).
_MODEL_REQUIRED_COMPLEXITY = frozenset({"medium", "complex"})
VALID_ACTIONS = ("keep", "demote", "tiebreak")

_AGENT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SKILL_RE = re.compile(r"^[a-z0-9-]+$")
_KEY_RE = re.compile(r"^[a-z0-9:_-]+$")  # alts= / stack= items (comma is the separator)

# Fallback accounting. 128 of 287 recorded dispatches (44.6%) fell back to
# general-purpose with no recorded reason, so the regression was invisible for
# six weeks. Every fallback now carries a reason token on the marker line.
FALLBACK_AGENT = "general-purpose"
AGENT_INDEX_PATH = REPO_ROOT / "agents" / "INDEX.json"
AGENT_INDEX_LOCAL = "INDEX.local.json"
# Harness-provided agents that exist outside agents/INDEX.json. Superset of
# validate-do-references.py's set: the Agent tool accepts these names, so
# coercing them would MANUFACTURE fallbacks instead of catching them.
BUILTIN_AGENTS = frozenset({"general-purpose", "claude", "explore", "plan", "statusline-setup"})
# Reason slug charset — same shape as alts=/stack= items, so the token can never
# grow a space and split the marker line into two tokens.
_FALLBACK_REASON_RE = re.compile(r"^[a-z0-9][a-z0-9:_-]*$")
_FALLBACK_SLUG_SUB = re.compile(r"[^a-z0-9:_-]+")
_FALLBACK_REASON_MAX = 80
# Complexities where a skill is mandatory. do/SKILL.md already states this as
# the "Skill-greediness gate (HARD — non-negotiable for Simple+)"; 23 of the 128
# recorded fallbacks violated it because nothing enforced it. Trivial dispatches
# stay exempt (they carry no skill by design).
_SKILL_REQUIRED_COMPLEXITY = frozenset({"simple", "medium", "complex"})

# Complexity -> thinking directive. Trivial never dispatches; medium is
# adaptive (no directive). Overrides: "slow" => THINKING_SLOW, "fast" =>
# THINKING_FAST, regardless of complexity.
_THINKING_BY_COMPLEXITY = {"simple": THINKING_FAST, "complex": THINKING_SLOW}

# task_spec input key -> Task Specification block label, in emit order.
_TASK_SPEC_FIELDS = (
    ("intent", "Intent"),
    ("constraints", "Constraints"),
    ("acceptance", "Acceptance criteria"),
    ("files", "Relevant file locations"),
    ("operator_context", "Operator context"),
)


class InputError(ValueError):
    """Invalid routing decision — message tells the caller what to fix."""


def _optional_model(value: object) -> str | None:
    """Normalize an optional model value, treating blank and '-' as absent."""
    if value is None:
        return None
    model = str(value).strip().lower()
    return model if model and model != "-" else None


def _optional_effort(value: object) -> str | None:
    """Normalize and validate an optional reasoning-effort value."""
    if value is None:
        return None
    effort = str(value).strip().lower()
    if not effort or effort == "-":
        return None
    if effort not in GPT_56_EFFORTS:
        raise InputError(f"'model_effort' {effort!r} — must be one of {'/'.join(GPT_56_EFFORTS)}")
    return effort


def _resolve_provider(decision: dict) -> str:
    """Extract and validate the provider field; default 'anthropic' (Claude Code)."""
    raw = decision.get("provider")
    if raw is None:
        return "anthropic"
    provider = str(raw).strip().lower()
    if not provider or provider == "-":
        return "anthropic"
    if provider not in VALID_PROVIDERS:
        raise InputError(f"'provider' {provider!r} — must be one of {'/'.join(VALID_PROVIDERS)}")
    return provider


def resolve_model_selection(decision: dict, provider: str = "anthropic") -> tuple[str | None, str | None]:
    """Return the validated ``(model, effort)`` for one dispatch decision.

    Harness-aware: ``provider`` selects the automatic policy table.
    Anthropic lane defaults select Opus 5 at every task class (owner
    directive + current session model); sonnet is manual-only, kept for
    cost, context-window, and latency constraints.
    OpenAI lane defaults select GPT-5.6 Sol/Terra.  Effort is recorded in
    the marker for all models; for Claude lanes it is advisory (the harness
    Agent tool does not accept per-call effort).
    """
    manual = decision.get("manual_model_override", False)
    if not isinstance(manual, bool):
        raise InputError("'manual_model_override' must be a boolean")

    policy_raw = decision.get("model_policy")
    policy = str(policy_raw).strip().lower() if policy_raw is not None else ""
    model = _optional_model(decision.get("model"))
    effort = _optional_effort(decision.get("model_effort"))

    if policy:
        if policy not in VALID_MODEL_POLICIES:
            raise InputError(f"'model_policy' {policy!r} — must be one of {'/'.join(VALID_MODEL_POLICIES)}")
        if policy == "deterministic":
            raise InputError("model_policy='deterministic' requires a script, not an LLM dispatch")

        policies = AUTO_POLICIES_BY_PROVIDER.get(provider)
        if policies is None:
            raise InputError(
                f"model_policy requires provider 'anthropic' or 'openai', got {provider!r}; "
                "use an explicit model for other harnesses"
            )

        expected_model, expected_effort = policies[policy]
        if policy == "max-power" and not manual:
            raise InputError("model_policy='max-power' requires manual_model_override=true")
        if (model is not None and model != expected_model) or (effort is not None and effort != expected_effort):
            if not manual:
                raise InputError(
                    f"model_policy={policy!r} selects {expected_model}/{expected_effort}; "
                    "use manual_model_override=true for another choice"
                )
            override_model = model or expected_model
            if provider == "openai" and override_model not in GPT_56_MODELS:
                raise InputError("OpenAI model_policy overrides must use a GPT-5.6 model")
            if provider == "anthropic" and override_model not in ANTHROPIC_MODELS:
                raise InputError("Anthropic model_policy overrides must use a Claude model")
            if model is not None and model != expected_model and effort is None:
                raise InputError("manual model overrides require 'model_effort'")
            return override_model, effort or expected_effort
        return expected_model, expected_effort

    if model is None:
        if effort is not None:
            raise InputError("'model_effort' requires an explicit model")
        return None, None
    if model not in VALID_MODELS:
        raise InputError(f"'model' {model!r} — must be one of {'/'.join(VALID_MODELS)}")

    if model in GPT_56_MODELS:
        if effort is None:
            raise InputError("GPT-5.6 selections require 'model_effort'")
        if not manual:
            raise InputError("explicit GPT-5.6 selections require model_policy or manual_model_override=true")
        return model, effort

    if model == LEGACY_GPT_55:
        if not manual:
            raise InputError("legacy gpt-5.5 requires manual_model_override=true")
        return model, effort

    # Claude models (opus, sonnet) and codex wrapper.
    # Effort is optional and advisory for Claude lanes — recorded in the
    # marker (model@effort) for telemetry but not passed to the Agent tool.
    if model == "sonnet":
        if not manual:
            raise InputError(
                f"'{model}' requires manual_model_override=true "
                "(Opus 5 is the Anthropic-lane default; off-policy picks stay explicit)"
            )
    if model == "opus" and effort == "max" and not manual:
        raise InputError("opus/max requires manual_model_override=true (unmeasured top tier; escalate on a miss)")
    return model, effort


def _fmt_confidence(value: float) -> str:
    """Canonical health= float: 0.72 -> '0.72', 0.5 -> '0.5', 1.0 -> '1'.

    Must match the recorder's `\\d+(\\.\\d+)?` — never scientific notation,
    never a sign, never a trailing dot.
    """
    if not 0 <= value <= 1:
        raise InputError(f"health.confidence must be within [0, 1], got {value}")
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _require_str(decision: dict, key: str) -> str:
    value = decision.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"'{key}' is required and must be a non-empty string")
    return value.strip()


def _key_list(raw: object, field: str) -> list[str]:
    """Validate an alts=/stack= item list; items carry no commas or spaces."""
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise InputError(f"'{field}' must be a list of strings")
    items = [item.strip().lower() for item in raw if item.strip()]
    for item in items:
        if not _KEY_RE.match(item):
            raise InputError(f"'{field}' item {item!r} — allowed chars: a-z 0-9 : _ -")
    return items


def load_known_agents(index_path: Path = AGENT_INDEX_PATH) -> frozenset[str]:
    """Dispatchable agent names: agents/INDEX.json + INDEX.local.json + built-ins.

    Add-only merge of the tracked index and the gitignored local overlay — the
    same semantics as scripts/routing_index_merge.py, inlined (names only) to
    keep this script import-free and deterministic.

    Returns an EMPTY set when neither file is readable. Callers treat empty as
    "cannot validate" and keep the agent as given: a missing index must never
    coerce a valid pick into a fallback.
    """
    names: set[str] = set()
    for path in (index_path, index_path.parent / AGENT_INDEX_LOCAL):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        agents = raw.get("agents")
        if isinstance(agents, dict):
            names.update(str(name).strip().lower() for name in agents if str(name).strip())
    if not names:
        return frozenset()
    return frozenset(names | BUILTIN_AGENTS)


def slugify_fallback_reason(value: object) -> str:
    """Normalize a fallback reason into ONE marker token; "" when absent.

    The marker is space-separated, so the reason must never contain a space:
    prose is lowercased and slugified to the alts=/stack= charset.
    """
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text == "-":
        return ""
    slug = _FALLBACK_SLUG_SUB.sub("-", text).strip("-:_")[:_FALLBACK_REASON_MAX].strip("-:_")
    if not slug or not _FALLBACK_REASON_RE.match(slug):
        raise InputError(f"'fallback_reason' {text!r} — needs at least one letter or digit")
    return slug


def resolve_agent(decision: dict) -> tuple[str, str]:
    """Return the validated ``(agent, fallback_reason)`` for one dispatch.

    Two rules the router already had but nothing enforced:

    1. UNKNOWN AGENT — an agent absent from agents/INDEX.json cannot be
       dispatched, so it is coerced to general-purpose with
       ``fallback_reason=invalid-agent:<name>``. Deliberately NOT an exception:
       raising mid-session would stall real work, and a phantom agent name is
       the router's bug to see in the data, not the user's task to lose.
    2. FALLBACK JUSTIFICATION — general-purpose (however reached) REQUIRES a
       non-empty reason, so every fallback is justified and countable instead
       of being an invisible default.
    """
    agent = _require_str(decision, "agent").lower()
    if not _AGENT_RE.match(agent):
        raise InputError(f"'agent' {agent!r} — must match [a-z0-9][a-z0-9-]*")

    reason = slugify_fallback_reason(decision.get("fallback_reason"))
    known = load_known_agents()
    if known and agent not in known:
        reason = f"invalid-agent:{agent}"
        agent = FALLBACK_AGENT

    if agent == FALLBACK_AGENT and not reason:
        raise InputError(
            "'fallback_reason' is required when agent='general-purpose' "
            "(a non-empty slug, e.g. 'no-specialist-match'). "
            "An unjustified fallback is the failure mode this field exists to make countable."
        )
    return agent, reason


def build_marker(decision: dict) -> str:
    """Build the `[do-route]` marker line from one routing decision."""
    agent, fallback_reason = resolve_agent(decision)

    skill = str(decision.get("skill") or "").strip().lower()
    if skill and skill != "-" and not _SKILL_RE.match(skill):
        raise InputError(f"'skill' {skill!r} — must match [a-z0-9-]+")
    skill = skill or "-"

    complexity = _require_str(decision, "complexity").lower()
    if complexity not in VALID_COMPLEXITY:
        raise InputError(f"'complexity' {complexity!r} — must be one of {'/'.join(VALID_COMPLEXITY)}")

    # Skill enforcement: mandatory for simple/medium/complex (do/SKILL.md
    # skill-greediness gate), exempt for trivial. Same hard-fail style as the
    # model rule below — a skill-less Simple+ dispatch is a routing defect, and
    # silently coercing it to `-` is what hid 23 of the 128 fallbacks.
    if skill == "-" and complexity in _SKILL_REQUIRED_COMPLEXITY:
        raise InputError(
            f"'skill' is required for complexity={complexity} "
            f"(skill-greediness gate: HARD, non-negotiable for Simple+). "
            f"Name the skill the agent must load, or route as trivial."
        )

    parts = [f"[do-route] agent={agent}", f"skill={skill}", f"complexity={complexity}"]

    # Model enforcement: required for medium/complex, optional for trivial/simple.
    # Effort token included for all models so telemetry can distinguish each
    # benchmarked point; advisory for Claude lanes (Agent tool has no effort param).
    provider = _resolve_provider(decision)
    model, effort = resolve_model_selection(decision, provider)
    if model is not None:
        parts.append(f"model={model}")
        if effort is not None:
            parts.append(f"effort={effort}")
    if model is None:
        if complexity in _MODEL_REQUIRED_COMPLEXITY:
            raise InputError(
                f"'model' is required for complexity={complexity} "
                f"(allowed: {'/'.join(VALID_MODELS)}). "
                f"Omitting model inherits the session main-loop model — "
                f"set it explicitly per the Model Selection table."
            )
        parts.append("model=-")

    health = decision.get("health")
    if not isinstance(health, dict):
        health = {}  # "-" sentinel or absent → no health data
    confidence = health.get("confidence")
    if confidence is None:
        # No weight row for the pick — the recorder writes null but marks the
        # gate inputs present (instrumented, state b).
        parts.append("health=-")
    else:
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise InputError("'health.confidence' must be a number or null")
        parts.append(f"health={_fmt_confidence(float(confidence))}")
        for key, token in (("n", "n"), ("failure", "fail")):
            value = health.get(key)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise InputError(f"'health.{key}' must be a non-negative integer")
            parts.append(f"{token}={value}")
        action = health.get("action")
        if action is not None:
            if str(action).lower() not in VALID_ACTIONS:
                raise InputError(f"'health.action' {action!r} — must be one of {'/'.join(VALID_ACTIONS)}")
            parts.append(f"action={str(action).lower()}")
        alts = _key_list(health.get("alts") or [], "health.alts")
        if alts:
            parts.append(f"alts={','.join(alts)}")

    stack = _key_list(decision.get("stack") or [], "stack")
    if stack:
        parts.append(f"stack={{{','.join(stack)}}}")

    # `fallback=<slug>` last: an independent \b-delimited token, appended after
    # every existing one so no recorder regex shifts. Verified round-trip
    # against the real recorder in scripts/tests/test_build_dispatch.py.
    if fallback_reason:
        parts.append(f"fallback={fallback_reason}")

    return " ".join(parts)


def build_thinking(decision: dict) -> str:
    """Thinking directive for the dispatch, or "" when adaptive/none."""
    override = (decision.get("flags") or {}).get("thinking_override")
    if override is not None:
        directive = {"slow": THINKING_SLOW, "fast": THINKING_FAST}.get(str(override).lower())
        if directive is None:
            raise InputError(f"'flags.thinking_override' {override!r} — must be 'slow', 'fast', or null")
        return directive
    complexity = str(decision.get("complexity") or "").lower()
    return _THINKING_BY_COMPLEXITY.get(complexity, "")


def read_token_budget(settings_path: Path = SETTINGS_PATH) -> int:
    """`orchestration.token_budget` from settings.json; 500000 on any miss."""
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        budget = settings.get("orchestration", {}).get("token_budget", DEFAULT_TOKEN_BUDGET)
        return int(budget)
    except Exception:
        return DEFAULT_TOKEN_BUDGET


def build_token_line(decision: dict, settings_path: Path = SETTINGS_PATH) -> str:
    remaining = decision.get("token_remaining")
    if remaining is None:
        remaining = read_token_budget(settings_path)
    if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
        raise InputError("'token_remaining' must be a non-negative integer")
    return f"~{remaining} tokens available for this task; prioritize accordingly."


def build_task_spec(decision: dict) -> str:
    """Task Specification block from provided fields, or "" when none given."""
    spec = decision.get("task_spec") or {}
    if not isinstance(spec, dict):
        raise InputError("'task_spec' must be an object")
    lines = []
    for key, label in _TASK_SPEC_FIELDS:
        value = spec.get(key)
        if value is None or not str(value).strip():
            continue
        lines.append(f"**{label}:** {str(value).strip()}")
    if not lines:
        return ""
    return "## Task Specification (auto-extracted)\n\n" + "\n".join(lines)


def build_preamble(decision: dict, settings_path: Path = SETTINGS_PATH) -> str:
    """Complete dispatch preamble, blocks in dispatch order, blank-line separated."""
    if not isinstance(decision, dict):
        raise InputError("routing decision must be a JSON object")
    flags = decision.get("flags") or {}
    if not isinstance(flags, dict):
        raise InputError("'flags' must be an object")

    blocks = [
        build_marker(decision),
        build_thinking(decision),
        build_token_line(decision, settings_path),
        build_task_spec(decision),
        INJ_REFERENCE_LOADING,
        INJ_COMPLETENESS,
        INJ_DENSE_COMPLETE,
        INJ_BASE_INSTRUCTIONS,
        INJ_ROUTE_FIT,
        WORKTREE_RULES if flags.get("worktree") else "",
        LOCAL_ONLY_BLOCK if flags.get("local_only") else "",
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the /do Phase 4 dispatch preamble from a routing decision.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="Routing decision as a JSON string")
    source.add_argument("--json-file", help="Path to a routing-decision JSON file ('-' = stdin)")
    args = parser.parse_args(argv)

    try:
        if args.json is not None:
            raw = args.json
        elif args.json_file == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.json_file).read_text(encoding="utf-8")
        decision = json.loads(raw)
    except OSError as exc:
        print(f"build-dispatch: cannot read input: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"build-dispatch: invalid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        sys.stdout.write(build_preamble(decision))
    except InputError as exc:
        print(f"build-dispatch: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
