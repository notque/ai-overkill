#!/usr/bin/env python3
# hook-version: 1.4.0
"""
PostToolUse Hook: Routing Decision Recorder (action A, formerly /do Phase 5)

Records the routing-decision row for every Agent dispatch so the routing
feedback loop (`learning-db.py route-health`) keeps receiving the rows it
needs. Replaces the hand-run `learning-db.py record routing ...` step that
lived in /do Phase 2 Step 4 + Phase 5 action A.

WORKFLOW DISPATCHES (v1.1.0): /do Complex dispatches run through the Workflow
tool. Its inner agent() calls fire NO PostToolUse:Agent event — the harness
emits ONE PostToolUse with tool_name "Workflow", carrying every worker prompt
(marker included) inside tool_input.script. So this hook also matches
"Workflow": it reads tool_input.script, finds ALL line-start [do-route]
markers (same anchored regex as the Agent path), and records one decision per
marker. Idempotency is keyed per marker LINE so a resubmitted script (workflow
resume) is a no-op. Pending outcomes are still appended per marker: Workflow
inner agents fire no SubagentStop, but resolution never needed one — the
UserPromptSubmit finalizer / Stop fallback resolve pendings on their normal
paths, and a SubagentStop from any other dispatch merely revalidates them
(their decision rows exist, written here first).

SCOPING — record ONLY /do-routed dispatches.
Every Agent dispatch fires PostToolUse:Agent, including pr-review's reviewer
sub-agents (code-reviewer, security-reviewer, reviewer-*) and any other
nested fan-out. Recording all of them would inflate route-health's denominator
with dispatches /do never routed. So /do stamps a machine-readable marker on
the prompts IT routes (Phase 4 Step 2):

    [do-route] agent={agent} skill={skill} complexity={complexity}

This hook records ONLY when that marker is present, and reads the agent + skill
directly FROM the marker (structured intent emitted by the router — not fragile
prompt-sniffing). No marker → not a /do routing decision → skip. This is the
sole scoping mechanism (no reviewer-name denylist).

PostToolUse:Agent fires AFTER the subagent completes, so the event carries
both the dispatch metadata (tool_input.subagent_type / .prompt / .description)
and the subagent's tool_result. From these we:
  1. Read the routing key {agent}:{skill} from the [do-route] marker
     (agent-only "{agent}:" when the marker carries no skill).
  2. Record topic="routing", category="effectiveness" with observable fields
     (tool_errors, request/description snippet).
  3. (C) Parse a `rightsizing:tier{N}` banner from the subagent output and
     record a separate rightsizing row, parse-only and silent when absent.
  4. (D, v1.3.0) Parse the `route-fit:` banner from the subagent output and
     score it ASYMMETRICALLY: a negative verdict decays the route, `ok` is a
     no-op that boosts nothing. Parse-only and silent when absent. See
     record_route_fit for why a self-report may only move against the router.
  5. Write a pending-outcome entry to a per-session file so the SubagentStop
     hook (routing-outcome-recorder.py) can recover the full key + the error
     verdict and apply boost/decay. PostToolUse:Agent fires before
     SubagentStop, so the decision row is committed before the outcome runs —
     the ordering dependency is honored structurally.

Idempotency: a per-session state file keyed by a dispatch signature stops the
same dispatch being recorded twice (e.g. on retries). The DB upsert on
(topic, key) is also idempotent.

Design Principles:
- SILENT (records to DB, no context injection)
- Non-blocking (always exits 0)
- Fast execution (<50ms target); lazy imports
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
from hook_utils import hook_error
from route_types import HealthGateInputs
from routing_outcome_state import append_pending_outcome, claim_dispatch
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# The /do routing marker. /do (SKILL.md Phase 4 Step 2) prepends this to every
# agent prompt IT routes. Its presence is the SOLE signal that a dispatch is a
# /do routing decision; agent + skill are read straight from it. Sub-agent
# fan-out (pr-review reviewers, nested dispatches) carries no marker → skipped.
#   [do-route] agent=python-general-engineer skill=test-driven-development complexity=Medium
# skill may be empty/"-"/absent (agent-only routing). The same line may carry
# optional tokens: health=/n=/fail=/action=/alts= (Step 1.5 gate inputs) and
# stack={s1,s2} (the composed skill stack, instrumentation only).
# Anchored to line start (^\s*, MULTILINE) so a quoted/forwarded marker
# mid-prose (e.g. a user pasting "...the [do-route] line...") doesn't get
# recorded — only a marker /do itself emitted at the head of a line counts.
_DO_ROUTE_RE = re.compile(
    r"^\s*\[do-route\]\s+agent=([a-z0-9][a-z0-9-]*)(?:\s+skill=([a-z0-9-]*|-)?)?",
    re.IGNORECASE | re.MULTILINE,
)

# Optional complexity field on the same marker line, recorded into the T3 event
# log for replay. Absent => "".
_COMPLEXITY_RE = re.compile(r"\bcomplexity=([a-z0-9-]+)", re.IGNORECASE)

# The router's complexity enum (do/SKILL.md Phase 1). Marker values are
# lowercased and validated against it: production events carried both case
# splits ("medium" vs "Medium") and invalid values ("Low"), which fragmented
# per-complexity aggregation. Valid => store normalized; invalid => store ""
# and keep the raw value in the event's complexity_invalid field for audit.
_VALID_COMPLEXITY = frozenset({"trivial", "simple", "medium", "complex"})

# Optional stack token on the marker line: ` stack={s1,s2}` — the skill stack
# the router composed for this dispatch. Instrumentation only: parsed onto the
# decision event as a list; absent token => no field. Same charset as alts=.
_STACK_RE = re.compile(r"\bstack=\{([a-z0-9:_,-]*)\}", re.IGNORECASE)

# Pipeline token on the marker line: ` pipeline=<name>` — the workflow pipeline
# the router picked (build-dispatch.py resolve_pipeline, validated against
# pipeline-index.json before it is emitted). Absent or `-` => None. Every
# pipeline pick was invisible until this parser existed: the router emitted the
# token, nothing read it, so evidence_route_decisions.pipeline stayed NULL.
_PIPELINE_RE = re.compile(r"\bpipeline=([a-z0-9-]+)", re.IGNORECASE)

# Model token on the marker line: `model=opus` or `model=-`. GPT-5.6 selections
# carry an additional `effort=` token. Valid values match build-dispatch.py;
# `model=-` or absent => null. Old markers remain readable.
_MODEL_RE = re.compile(r"\bmodel=([a-z0-9.-]+|-)", re.IGNORECASE)
_EFFORT_RE = re.compile(r"\beffort=(low|medium|high|xhigh|max)", re.IGNORECASE)
_VALID_MODELS = frozenset(
    {
        "sonnet",
        "opus",
        "codex",
        "gpt-5.5",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    }
)

# Step 1.5 health gate inputs on the same marker line (do/SKILL.md Phase 4 Step 2).
# Each is an independent \b token. `health=-` => null (no weight row); else float.
# n=/fail= are the other demote-floor inputs; action= is keep|demote|tiebreak;
# alts= is a comma-separated key list. All optional; absent => null.
# health= is a float (digits with one optional decimal part) or "-". The value
# is anchored on BOTH ends: a trailing `(?![\d.])` rejects `1.2.3` (and `1.2.`)
# as a whole — it must NOT match as `1.2`, which would slip a bad token past
# float() / drop the event. A malformed value stays a non-match => state (c).
_HEALTH_RE = re.compile(r"\bhealth=(\d+(?:\.\d+)?|-)(?![\d.])", re.IGNORECASE)
_N_RE = re.compile(r"\bn=(\d+)", re.IGNORECASE)
_FAIL_RE = re.compile(r"\bfail=(\d+)", re.IGNORECASE)
_ACTION_RE = re.compile(r"\baction=(keep|demote|tiebreak)", re.IGNORECASE)
_ALTS_RE = re.compile(r"\balts=([a-z0-9:_,-]+)", re.IGNORECASE)

# Fallback justification on the marker line: ` fallback=<slug>` (build-dispatch.py
# emits it whenever the router picked general-purpose or coerced an unknown agent).
# Independent \b token, same charset as alts= items. Absent => None.
_FALLBACK_RE = re.compile(r"\bfallback=([a-z0-9][a-z0-9:_-]*)", re.IGNORECASE)


def _line_containing(text: str, pos: int) -> str:
    """Return the full line of ``text`` that contains char offset ``pos``."""
    start = text.rfind("\n", 0, pos) + 1  # -1 -> 0 for the first line
    end = text.find("\n", pos)
    return text[start:] if end == -1 else text[start:end]


def _marker_line(prompt: str) -> str:
    """Return the single line that carries the [do-route] marker, or "".

    The gate inputs (health=/n=/fail=/action=/alts=) live on the marker line
    ONLY. Scanning the whole prompt let a task body that merely mentions
    `health=0.9` or `fail=3` poison gate_inputs_present and the decommission
    clock. Isolating the marker line first means body text can never match.
    Uses the SAME matcher as parse_do_route_marker so "marker line" is one
    definition; returns the full line containing that match.
    """
    if not prompt or "[do-route]" not in prompt.lower():
        return ""
    m = _DO_ROUTE_RE.search(prompt)
    if not m:
        return ""
    return _line_containing(prompt, m.start())


def parse_health_inputs(prompt: str) -> HealthGateInputs:
    """Read the Step-1.5 gate inputs off the marker LINE. Three instrumentation states.

    Inputs are read from the marker line only (`_marker_line`), never the whole
    prompt — a task body mentioning `health=`/`fail=` must not be read as a gate
    input. `gate_inputs_present` is the instrumentation signal the decommission
    clock reads — NOT non-null health. Three states the event must distinguish:
      (a) numeric  `health=<float>` => health float, gate_inputs_present True.
      (b) no-row   `health=-`       => health null,  gate_inputs_present True.
          The pick has no weight row — valid, expected data. Most live picks are
          state (b), so reading it as missing would keep the clock unreachable
          forever (the soundness gap this fixes).
      (c) legacy   no `health=` token => health null, gate_inputs_present False.
          The marker never carried a gate input (pre-fix / missing wiring).
          A malformed `health=` value (e.g. `1.2.3`) also lands here: the regex
          won't match it, so it reads as absent — honest "not instrumented",
          never a dropped event.
    n/failure/action/alternates stay null unless a real `health=<float>` is read.
    Snapshotted at decision time; replay never re-derives.
    """
    null = {
        "health": None,
        "n": None,
        "failure": None,
        "action": None,
        "alternates": None,
        "gate_inputs_present": False,
    }
    line = _marker_line(prompt)
    if not line:
        return null  # no marker line => nothing to read
    hm = _HEALTH_RE.search(line)
    if not hm:
        return null  # state (c): no (well-formed) gate input on the marker
    if hm.group(1) == "-":
        # state (b): marker carried the gate input; the pick had no weight row.
        return {**null, "gate_inputs_present": True}
    try:
        health = float(hm.group(1))  # state (a)
    except ValueError:
        # Defensive: the regex already bars malformed values, but never let a
        # float() raise drop the whole event — treat as field-absent (state c).
        return null
    nm = _N_RE.search(line)
    fm = _FAIL_RE.search(line)
    am = _ACTION_RE.search(line)
    altm = _ALTS_RE.search(line)
    return {
        "health": health,
        "n": int(nm.group(1)) if nm else None,
        "failure": int(fm.group(1)) if fm else None,
        "action": am.group(1).lower() if am else None,
        "alternates": [k for k in altm.group(1).split(",") if k] if altm else None,
        "gate_inputs_present": True,
    }


def parse_marker_complexity(marker_text: str) -> tuple[str, str]:
    """Read complexity off the marker LINE: (normalized, invalid_raw).

    Scoped to the marker line (same rationale as parse_health_inputs, Finding
    70): a task body mentioning `complexity=...` must not be read as the
    router's value. Returns:
      valid value   => ("medium", "")   — lowercased, in _VALID_COMPLEXITY
      invalid value => ("", "Low")      — raw kept for the complexity_invalid
                                          event field, never silently dropped
      absent        => ("", "")
    """
    line = _marker_line(marker_text)
    m = _COMPLEXITY_RE.search(line)
    if not m:
        return "", ""
    raw = m.group(1)
    normalized = raw.lower()
    if normalized in _VALID_COMPLEXITY:
        return normalized, ""
    return "", raw


def parse_stack(marker_text: str) -> list[str] | None:
    """Read the optional ` stack={s1,s2}` token off the marker LINE, or None.

    None when the token is absent (or empty) => the decision event carries no
    stack field. Instrumentation only — the router spec change that EMITS the
    token lands separately; this parser is forward-tolerant of it.
    """
    line = _marker_line(marker_text)
    m = _STACK_RE.search(line)
    if not m:
        return None
    items = [s for s in m.group(1).split(",") if s]
    return items or None


def parse_pipeline(marker_text: str) -> str | None:
    """Read the optional ` pipeline=<name>` token off the marker LINE, or None.

    None when the token is absent (the majority of dispatches) or `pipeline=-`.
    Scoped to the marker line (same rationale as parse_stack): task prose
    mentioning `pipeline=` must never be read as the router's pick.
    """
    line = _marker_line(marker_text)
    m = _PIPELINE_RE.search(line)
    if not m:
        return None
    name = m.group(1).lower()
    return None if name == "-" else name


def parse_model(marker_text: str) -> str | None:
    """Read the `model=` token off the marker LINE, or None.

    None when the token is absent (old markers) or `model=-` (trivial/simple
    with no explicit pick). A valid model name => that string. An unrecognized
    value => None (not silently accepted). Backward-compatible: old markers
    without `model=` return None.
    """
    line = _marker_line(marker_text)
    m = _MODEL_RE.search(line)
    if not m:
        return None
    raw = m.group(1).lower()
    if raw == "-":
        return None
    return raw if raw in _VALID_MODELS else None


def parse_fallback_reason(marker_text: str) -> str | None:
    """Read the optional ` fallback=<slug>` token off the marker LINE, or None.

    Scoped to the marker line (same rationale as parse_health_inputs): task
    prose mentioning `fallback=` must never be read as the router's reason.
    """
    line = _marker_line(marker_text)
    m = _FALLBACK_RE.search(line)
    return m.group(1).lower() if m else None


def parse_model_effort(marker_text: str) -> str | None:
    """Read a valid ``effort=`` token from the marker line, if present.

    Returns effort for any recognized model (Claude or OpenAI).  Effort is
    advisory for Claude lanes but recorded for telemetry (model@effort).
    """
    line = _marker_line(marker_text)
    model = parse_model(line)
    if model is None:
        return None
    match = _EFFORT_RE.search(line)
    return match.group(1).lower() if match else None


# Right-sizing banner. The first four fields are required; findings= and the
# cost fields (tokens=, wall_clock_s=) are optional, additive extensions
# (ADR: review-tier-roi). Legacy four-field banners still match.
#   rightsizing: tier=3 files=15 packages=4 agents_dispatched=17 findings=2C/3H/5M tokens=84000 wall_clock_s=312
_RIGHTSIZING_RE = re.compile(
    r"rightsizing:\s*tier=(\d+)\s+files=(\d+)\s+packages=(\d+)\s+agents_dispatched=(\d+)"
    r"(?:\s+findings=(\d+)C/(\d+)H/(\d+)M)?"
    r"(?:\s+tokens=(\d+))?"
    r"(?:\s+wall_clock_s=(\d+))?",
    re.IGNORECASE,
)


# Route-fit banner (D). Every dispatched agent is asked (build-dispatch.py
# INJ_ROUTE_FIT) to close its reply with:
#   route-fit: ok
#   route-fit: wrong-agent | wrong-skill | needs-coordinator | underspecified
# Anchored to a WHOLE line (^...$, MULTILINE) so the banner spec quoted mid-prose
# is not a verdict; the LAST match wins because the banner is the final line.
_ROUTE_FIT_NEGATIVE = ("wrong-agent", "wrong-skill", "needs-coordinator", "underspecified")
_ROUTE_FIT_RE = re.compile(
    r"^\s*(?:[-*>`\s]*)route-fit:\s*(ok|wrong-agent|wrong-skill|needs-coordinator|underspecified)\s*`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_route_fit(output: str) -> str | None:
    """Read the route-fit verdict off the agent's output, or None.

    None means "no verdict": banner absent, or malformed (a value outside the
    enum, or trailing prose on the line). Parse-only and silent, exactly like
    the rightsizing banner — a missing or broken banner must never affect a
    dispatch, and must never be guessed at.
    """
    if not output or "route-fit:" not in output.lower():
        return None
    verdicts = _ROUTE_FIT_RE.findall(output)
    return verdicts[-1].lower() if verdicts else None


def record_route_fit(output: str, key: str, session_id: str | None = None) -> str | None:
    """(D) Score one route-fit verdict for ``key``. Returns the verdict, or None.

    ASYMMETRIC BY DESIGN — the whole point of the signal.

      negative verdict => STRONG evidence: apply_outcome(FAILURE) decays the
        route's confidence, exactly as a tool error or a user rejection does.
      `ok`             => WEAK evidence: apply_outcome(NEUTRAL) is a no-op on
        confidence. It records the basis counter (so the verdict is countable)
        and boosts NOTHING.

    Rationale: the agent grading the fit was handed the wrong domain
    instructions in precisely the case we care about, and an agent that has
    just spent a session on a task will rationalize that it was the right one
    to do it. A self-report is therefore credible when it says "this was not
    mine" and worthless when it says "this was mine". So the signal is wired to
    move only AGAINST the router, never to flatter it. Under the old metric —
    success inferred from the absence of a complaint — a timid general-purpose
    fallback scored identically to a correct specialist; a signal that could
    boost on self-declared `ok` would reproduce that exact failure.

    Caller MUST have written the decision row for ``key`` first (apply_outcome
    is a no-op on a missing row); main() calls this only for a key it just
    recorded.
    """
    verdict = parse_route_fit(output)
    if verdict is None:
        return None

    from routing_outcome_score import FAILURE, NEUTRAL, apply_outcome

    negative = verdict in _ROUTE_FIT_NEGATIVE
    basis = f"route_fit:{verdict}"
    apply_outcome(key, FAILURE if negative else NEUTRAL, basis=basis)

    if negative:
        # Surface the verdict on the decision row so `evidence-route-context`
        # shows WHY a route decayed. NEGATIVES ONLY: this is a second commit
        # (~3ms) and it buys diagnosis of the cases you actually investigate.
        # On the common `ok` path it would cost every dispatch for a row that
        # says nothing happened. Best-effort — the basis counter above is the
        # durable record, and a later finalizer may overwrite this column.
        try:
            from learning_db_v2 import update_evidence_route_outcome

            update_evidence_route_outcome(
                route_key=key,
                session_id=session_id or None,
                outcome="failure",
                outcome_basis=basis,
            )
        except Exception:
            pass
    return verdict


_FALLBACK_REASON_KEY_PREFIX = "fallback-reason:"


def record_fallback_reason(reason: str | None, session_id: str | None = None) -> None:
    """Bump the aggregate row for one fallback reason. Silent when absent.

    Mirrors record_stack_usage: one `learnings` row per reason slug
    (topic="routing", category="effectiveness", key "fallback-reason:{slug}"),
    reusing record_learning's upsert so observation_count = times that reason
    was used. 128 of 287 dispatches fell back with no recorded reason; this is
    what makes the reason countable rather than merely printed.
    """
    if not reason:
        return
    from learning_db_v2 import record_learning

    record_learning(
        topic="routing",
        key=f"{_FALLBACK_REASON_KEY_PREFIX}{reason}",
        value=f"fallback-reason: {reason}",
        category="effectiveness",
        tags=["fallback-reason"],
        source="hook:routing-decision-recorder",
        session_id=session_id or None,
    )


def parse_do_route_marker(prompt: str) -> tuple[str, str] | None:
    """Read (agent, skill) from the [do-route] marker, or None when absent.

    None means this dispatch was not routed by /do (no marker) → the caller
    skips recording. skill is "" when the marker carries no skill or "-".
    """
    if not prompt or "[do-route]" not in prompt.lower():
        return None
    m = _DO_ROUTE_RE.search(prompt)
    if not m:
        return None
    agent = m.group(1).strip().lower()
    skill = (m.group(2) or "").strip().lower()
    if skill == "-":
        skill = ""
    return agent, skill


def parse_workflow_markers(script: str) -> list[tuple[str, str, str]]:
    """All line-start [do-route] markers in a Workflow script: [(agent, skill, marker line)].

    A Workflow tool_input.script carries every worker prompt of a /do Complex
    dispatch, so ONE script holds N markers — one routing decision each.
    finditer with the SAME line-start-anchored regex as the Agent path keeps
    the anchor semantics: a marker quoted mid-line never counts. skill is ""
    when the marker carries no skill or "-".
    """
    if not script or "[do-route]" not in script.lower():
        return []
    markers: list[tuple[str, str, str]] = []
    for m in _DO_ROUTE_RE.finditer(script):
        agent = m.group(1).strip().lower()
        if not agent:
            continue  # malformed marker => nothing to key on
        skill = (m.group(2) or "").strip().lower()
        if skill == "-":
            skill = ""
        markers.append((agent, skill, _line_containing(script, m.start())))
    return markers


def build_routing_key(agent: str, skill: str) -> str:
    """Build the {agent}:{skill} key; agent-only "{agent}:" when skill unknown."""
    return f"{agent}:{skill}" if skill else f"{agent}:"


_STACK_USAGE_KEY_PREFIX = "stack-usage:"


def record_stack_usage(stack: list[str] | None, session_id: str | None) -> None:
    """Bump the per-skill stack-usage row for every skill in ``stack``.

    Mirrors the rightsizing accumulation convention: one `learnings` row per
    enhancement skill (topic="routing", category="effectiveness", key
    "stack-usage:{skill}"), reusing record_learning's built-in upsert so
    observation_count = times stacked and last_seen = last stacked — no
    parallel store. Deduplicated per dispatch so a marker listing the same
    skill twice counts once. No-op when stack is None/empty (absent token).
    """
    if not stack:
        return
    from learning_db_v2 import record_learning

    for skill in dict.fromkeys(stack):  # de-dup, preserve order
        if not skill:
            continue
        record_learning(
            topic="routing",
            key=f"{_STACK_USAGE_KEY_PREFIX}{skill}",
            value=f"stack-usage: skill={skill}",
            category="effectiveness",
            tags=["stack-usage", skill],
            source="hook:routing-decision-recorder",
            session_id=session_id or None,
        )


def dispatch_signature(agent: str, skill: str, description: str, prompt: str) -> str:
    """Stable signature for one dispatch, used for idempotency."""
    raw = f"{agent}|{skill}|{description}|{prompt[:200]}"
    return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def workflow_dispatch_signature(occurrence: int, marker_line: str) -> str:
    """Idempotency signature for ONE marker in a Workflow script.

    Keyed on the marker LINE, not the script: a workflow resume resubmits the
    same script (possibly with step state changed AROUND the markers), and
    every marker must re-derive the SAME signature so the re-run claims
    nothing and records nothing. ``occurrence`` is this line's index among
    IDENTICAL marker lines in the script, so two duplicate worker lines stay
    two distinct dispatches while unrelated script edits shift no signature.
    """
    raw = f"workflow|{occurrence}|{marker_line.strip()}"
    return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def detect_errors(event: dict) -> bool:
    """Return True if the subagent's tool_result shows an error. Best-effort.

    Uses hook_utils.is_tool_error as the intended detector. (The earlier
    `from error_learner import detect_error` branch was dead code: the module
    file is hooks/error-learner.py — hyphenated, so the import always raised
    ImportError and silently fell through to is_tool_error. Removed to make the
    real detector explicit.)
    """
    try:
        from hook_utils import get_tool_result, is_tool_error

        return is_tool_error(get_tool_result(event))
    except Exception:
        return False


def extract_output_text(result: object) -> str:
    """Flatten a PostToolUse tool_result/tool_response into searchable text.

    The shipped tests simulate the Bash-style ``{"output": "..."}`` shape, but a
    LIVE Agent (Task) dispatch returns its final message as the Anthropic
    message-content shape: a LIST of content blocks
    ``[{"type": "text", "text": "...banner..."}]`` (or a dict carrying that list
    under ``content``). ``get_tool_output`` only reads the ``output``/``stdout``
    string keys, so it returned "" for the live shape and the rightsizing banner
    was never seen (decision + telemetry rows still recorded — they don't read
    output). This handles every shape and keeps the plain-string path:

      - str                              -> itself
      - {"output"/"stdout": str}         -> that string (via get_tool_output)
      - {"text": str}                    -> that string
      - {"content": <blocks or str>}     -> recurse into content
      - [block, ...] / content blocks    -> concat each block's text
    """
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        # A list of content blocks (or nested lists). Concat each block's text.
        return "\n".join(extract_output_text(block) for block in result)
    if isinstance(result, dict):
        # Bash-style output/stdout first (preserves the existing path).
        from hook_utils import get_tool_output

        out = get_tool_output(result)
        if out:
            return out
        # Content-block dict: {"type": "text", "text": "..."} or {"content": ...}.
        text = result.get("text")
        if isinstance(text, str) and text:
            return text
        if "content" in result:
            return extract_output_text(result["content"])
        return ""
    return ""


def record_rightsizing(output: str, session_id: str | None = None) -> None:
    """(C) Add one rightsizing review to the tier's running sums. Silent when no banner.

    Per-review findings and cost are accumulated into running sums in the
    rightsizing:tier{N} row (`accumulate_rightsizing`) so `learning-db.py
    review-roi` reports a TRUE per-tier mean (sum / count), not the last
    review's sample. findings= and the cost fields are optional: a legacy
    banner (no findings=) bumps the review count only; a "-" cost never enters
    its sum (ADR: review-tier-roi).
    """
    if not output or "rightsizing:" not in output.lower():
        return
    m = _RIGHTSIZING_RE.search(output)
    if not m:
        return

    def _int_or_none(s: str | None) -> int | None:
        return int(s) if s is not None and s != "" else None

    from learning_db_v2 import accumulate_rightsizing

    accumulate_rightsizing(
        int(m.group(1)),
        critical=_int_or_none(m.group(5)),
        high=_int_or_none(m.group(6)),
        medium=_int_or_none(m.group(7)),
        tokens=_int_or_none(m.group(8)),
        wall_clock_s=_int_or_none(m.group(9)),
        source="hook:routing-decision-recorder",
        session_id=session_id or None,
    )


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            return
        event = json.loads(raw)

        # matcher "Agent|Workflow" in settings.json scopes this hook; guard
        # defensively.
        tool_name = event.get("tool_name") or event.get("tool", "")
        if tool_name not in ("Agent", "Workflow"):
            return

        tool_input = event.get("tool_input") or event.get("input") or {}
        description = tool_input.get("description") or ""
        session_id = event.get("session_id") or ""

        # SCOPING: record ONLY /do-routed dispatches. No [do-route] marker =>
        # this is a sub-agent fan-out (pr-review reviewers, nested dispatch),
        # not a /do routing decision — skip so route-health's denominator stays
        # clean. agent + skill are read straight from the marker.
        #
        # Build one decision per marker: (agent, skill, signature, marker_text).
        # Agent carries ONE marker in tool_input.prompt (marker_text = whole
        # prompt, unchanged semantics). Workflow carries N worker prompts in
        # tool_input.script — one decision per line-start marker, marker_text =
        # that marker's line so complexity/health parse per marker.
        if tool_name == "Agent":
            prompt = tool_input.get("prompt") or ""
            routed = parse_do_route_marker(prompt)
            if routed is None:
                return
            agent, skill = routed
            if not agent:
                return  # malformed marker => nothing to key on
            decisions = [(agent, skill, dispatch_signature(agent, skill, description, prompt), prompt)]
        else:
            script = tool_input.get("script") or ""
            occurrence: dict[str, int] = {}  # nth sighting of each identical marker line
            decisions = []
            for agent, skill, line in parse_workflow_markers(script):
                nth = occurrence.get(line.strip(), 0)
                occurrence[line.strip()] = nth + 1
                decisions.append((agent, skill, workflow_dispatch_signature(nth, line), line))
        if not decisions:
            return

        has_errors = None  # computed once, on the first claimed marker
        recorded_keys: list[str] = []  # routing keys this event actually recorded
        for agent, skill, sig, marker_text in decisions:
            # Idempotency (atomic, MEDIUM/TOCTOU): claim this dispatch signature.
            # claim_dispatch performs check-and-set under one flock, so N concurrent
            # duplicate deliveries record exactly once. False => already claimed.
            # For Workflow, the signature is keyed per marker line, so a resumed
            # workflow resubmitting the same script re-claims nothing (no-op).
            if not claim_dispatch(session_id, sig):
                continue
            if has_errors is None:
                # One Workflow event carries one tool result for ALL inner
                # agents — per-marker error attribution is not observable here,
                # so every marker shares the event-level flag (best available).
                has_errors = detect_errors(event)
            key = build_routing_key(agent, skill)
            request_snippet = (description or marker_text)[:200].replace("\n", " ").strip()

            from learning_db_v2 import record_learning

            record_learning(
                topic="routing",
                key=key,
                value=(
                    f"routing-decision: agent={agent} skill={skill or '-'} "
                    f"tool_errors={1 if has_errors else 0} user_rerouted=0 "
                    f"request: {request_snippet}"
                ),
                category="effectiveness",
                tags=["routing", agent] + ([skill] if skill else []),
                source="hook:routing-decision-recorder",
                session_id=session_id or None,
            )
            recorded_keys.append(key)

            # T3: per-dispatch DECISION event (JSONL), append-only + failure-safe.
            # Auxiliary to the aggregate row above — never blocks; route_events
            # swallows write errors so the hook stays non-blocking.
            complexity, complexity_invalid = parse_marker_complexity(marker_text)
            stack = parse_stack(marker_text)
            pipeline = parse_pipeline(marker_text)
            health = parse_health_inputs(marker_text)
            model = parse_model(marker_text)
            effort = parse_model_effort(marker_text)
            recorded_model = f"{model}@{effort}" if model and effort else model

            # Stack-usage telemetry: one aggregate row per enhancement skill in
            # the marker's ` stack={...}` token (routing-table utilization audit).
            # No-op when stack is None (token absent) — never blocks the hook.
            record_stack_usage(stack, session_id)

            # Fallback accounting: one aggregate row per ` fallback=<slug>` reason
            # so every fallback is countable, not just visible in the prompt.
            # No-op when the token is absent (the non-fallback majority).
            record_fallback_reason(parse_fallback_reason(marker_text), session_id)

            from route_events import record_decision_event

            record_decision_event(
                session=session_id,
                request_snippet=request_snippet,
                agent=agent,
                skill=skill,
                complexity=complexity,
                complexity_invalid=complexity_invalid,
                stack=stack,
                pipeline=pipeline,
                model=recorded_model,
                health_at_decision=health["health"],  # real gate inputs from the marker (Step 1.5)
                n=health["n"],
                failure=health["failure"],
                action=health["action"],
                alternates=health["alternates"],
                gate_inputs_present=health["gate_inputs_present"],
            )

            # Per-run telemetry envelope (ADR: learning-telemetry-envelope). Append-only,
            # one row per dispatch, AFTER the decision row so both share (topic, key).
            # git_sha + session_id + run_id are always derivable, so this row is non-empty
            # even when the best-effort fields (token_count, wall_clock_ms, model_id) are NULL.
            import uuid

            from learning_db_v2 import record_telemetry_run
            from telemetry_capture import git_sha_cached, model_id_from, token_count_from, wall_clock_ms_from

            record_telemetry_run(
                topic="routing",
                key=key,
                run_id=str(uuid.uuid4()),
                source="hook:routing-decision-recorder",
                batch_id=os.environ.get("CLAUDE_TELEMETRY_BATCH") or session_id or None,
                session_id=session_id or None,
                git_sha=git_sha_cached(session_id),
                model_id=model_id_from(event),
                skill_version=None,  # PR-A: None (ADR Alternative D — populate when cheap)
                token_count=token_count_from(event),
                wall_clock_ms=wall_clock_ms_from(event),
                tool_errors=has_errors,
            )
            try:
                from learning_db_v2 import record_evidence_route_decision

                record_evidence_route_decision(
                    session_id=session_id or None,
                    agent=agent,
                    skill=skill or None,
                    complexity=complexity or None,
                    model=recorded_model,
                    request_snippet=request_snippet,
                    stack=stack,
                    pipeline=pipeline,
                    health=health["health"],
                    n=health["n"],
                    failure=bool(has_errors),
                    action=health["action"],
                    alternates=health["alternates"],
                    gate_inputs_present=bool(health["gate_inputs_present"]),
                    decision_id=f"{session_id or 'no-session'}:{sig}",
                )
            except Exception:
                pass

            # Bridge to the outcome resolvers. The dispatch was already claimed
            # (marked seen) atomically above, so no separate mark. Decision row
            # is written BEFORE this append (ordering: A-before-B). Workflow
            # inner agents fire no SubagentStop — that's fine: resolution lives
            # in the UserPromptSubmit finalizer / Stop fallback, and any other
            # dispatch's SubagentStop merely revalidates these entries (their
            # decision rows exist, written above).
            append_pending_outcome(session_id, key, has_errors)

        if not recorded_keys:
            return  # every marker already claimed (duplicate delivery / resume)

        # (C) right-sizing feedback, parse-only. extract_output_text flattens
        # the LIVE Agent content-block shape (list of {"type","text"} blocks)
        # as well as the Bash-style {"output": "..."} the tests simulate, so the
        # banner is found regardless of payload shape. Runs once per EVENT (not
        # per marker) and only when a decision was claimed, so a duplicate
        # delivery / resubmitted script never double-accumulates the tier sums.
        from hook_utils import get_tool_result

        output = extract_output_text(get_tool_result(event))
        if output:
            record_rightsizing(output, session_id)

            # (D) route-fit feedback, parse-only. Applied ONLY when this event
            # recorded exactly ONE decision: a Workflow script carries N worker
            # markers but ONE tool result, so a single banner cannot be
            # attributed per worker — and decaying N routes off one verdict
            # would be worse than recording nothing. Wrapped: a malformed
            # banner, a DB hiccup, or an unexpected verdict must never affect
            # the dispatch (fail open, same contract as the evidence row above).
            if len(recorded_keys) == 1:
                try:
                    record_route_fit(output, recorded_keys[0], session_id)
                except Exception:
                    pass

    except Exception as e:
        hook_error("routing-decision-recorder", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
