#!/usr/bin/env python3
# hook-version: 1.0.1
"""
UserPromptSubmit hook — auto-inject Codex cross-model review for PR review operations.

Detects when the user invokes a review skill or phrases a review request,
and injects a nudge to also run the pr-workflow skill's codex-review intent
for cross-model second-opinion findings — but only when the codex CLI is
actually installed.

Detection triggers:
  Skill invocations: /systematic-code-review, /parallel-code-review,
                     /full-repo-review, /pr-review
  Intent phrases: "review this pr", "review my changes", "code review",
                  "review the pr", "pr review"

Non-triggers (already covered):
  /pr-workflow   — umbrella skill handles Codex via codex-review intent

Design decisions:
  - DON'T inject the raw codex command; tell Claude to invoke the skill
  - DON'T inject if the user already asked for /pr-workflow directly
  - DON'T block if codex is missing — silently skip
  - Keep injection short — it's a nudge, not a manual

Note on UserPromptSubmit timing: this hook fires BEFORE /do selects an agent,
so it only injects session-wide, agent-agnostic context. Agent-scoped context
injection belongs at routing time, inside the skill.
"""

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# Skill invocations that trigger cross-model review injection.
# /pr-workflow is excluded — it already handles Codex via codex-review intent.
REVIEW_SKILL_PATTERN = re.compile(
    r"/(?:systematic-code-review|parallel-code-review|full-repo-review|pr-review)\b",
    re.IGNORECASE,
)

# Natural-language intent phrases that indicate a review request.
REVIEW_INTENT_PATTERN = re.compile(
    r"(?:review\s+(?:this\s+)?(?:pr|the\s+pr|my\s+changes)|code\s+review|pr\s+review)",
    re.IGNORECASE,
)

# Patterns that indicate the user is already requesting pr-workflow.
# The umbrella takes care of Codex via its codex-review intent; no need to inject.
ALREADY_HANDLED_PATTERN = re.compile(
    r"/pr-workflow\b",
    re.IGNORECASE,
)

CODEX_INJECTION = (
    "[codex-auto-review] Codex CLI detected. After completing the primary review, "
    "use the codex-review intent to get cross-model "
    "findings from OpenAI Codex (GPT-5.4 xhigh reasoning). If the codex-review intent "
    "has already been invoked or is part of the current pipeline, skip this step. "
    "Call the Skill tool with `pr-workflow`."
)


def extract_prompt(event: dict) -> str:
    """Extract the user's prompt text from the hook event.

    Claude Code UserPromptSubmit events deliver the text in tool_input.prompt.
    Returns empty string if the field is absent or not a string.
    """
    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    prompt = tool_input.get("prompt", "")
    return prompt if isinstance(prompt, str) else ""


def is_review_request(prompt: str) -> bool:
    """Return True if the prompt contains a review trigger."""
    return bool(REVIEW_SKILL_PATTERN.search(prompt) or REVIEW_INTENT_PATTERN.search(prompt))


def is_already_handled(prompt: str) -> bool:
    """Return True if the prompt already requests pr-workflow directly."""
    return bool(ALREADY_HANDLED_PATTERN.search(prompt))


def codex_is_available() -> bool:
    """Return True if the codex CLI is installed and reachable.

    Uses `which codex` with a 2-second timeout to avoid blocking.
    """
    try:
        result = subprocess.run(
            ["which", "codex"],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=5)
    if not raw or not raw.strip():
        empty_output(EVENT_NAME).print_and_exit()

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        if debug:
            print(f"[codex-auto-review] JSON parse error: {exc}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    prompt = extract_prompt(event)

    if not prompt:
        empty_output(EVENT_NAME).print_and_exit()

    if is_already_handled(prompt):
        if debug:
            print("[codex-auto-review] Already handled by pr-workflow — skipping", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    if not is_review_request(prompt):
        if debug:
            print("[codex-auto-review] No review trigger detected — skipping", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    if not codex_is_available():
        if debug:
            print("[codex-auto-review] codex CLI not found — skipping injection", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    if debug:
        print("[codex-auto-review] Review trigger detected and codex available — injecting", file=sys.stderr)

    context_output(EVENT_NAME, CODEX_INJECTION).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        hook_error("codex-auto-review", exc)
    finally:
        sys.exit(0)
