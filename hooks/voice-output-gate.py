#!/usr/bin/env python3
# hook-version: 1.0.1
"""
UserPromptSubmit hook — inject voice output gate for external text actions.

When the user prompt indicates external text production (PR reviews, standup
updates, README edits, comments), this hook injects a mandatory validation
block requiring scan-ai-patterns.py and joy-check before posting.

Lives in private-skills/hooks/ and gets symlinked into vexjoy-agent/private-hooks/.
The installer places it in ~/.claude/hooks/ and registers it in settings.json.
"""

import json
import os
import re
import sys
from pathlib import Path

# Add hook lib to path — use the installed location (~/.claude/hooks/lib),
# not the resolved symlink target (which lives in private-skills)
HOOKS_DIR = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR / "lib"))
# The tracked copy runs from this repository before deployment. A private
# symlink target has no sibling lib, so the installed path remains its fallback.
LOCAL_LIB = Path(__file__).resolve().parent / "lib"
if LOCAL_LIB.is_dir():
    sys.path.insert(0, str(LOCAL_LIB))

try:
    from hook_utils import HookOutput, empty_output, hook_error
    from skill_directives import skill_call_directive
except ImportError:
    # Graceful degradation if hook_utils not available
    def _noop():
        print(json.dumps({}))
        sys.exit(0)

    _noop()

# Patterns that indicate external text production
EXTERNAL_TEXT_PATTERNS = [
    r"\bpr\s+review\b",
    r"\bpr\s+comment\b",
    r"\bgh\s+pr\b",
    r"\breview\s+(this|the)\s+pr\b",
    r"\bcreate\s+(a\s+)?pr\b",
    r"\bopen\s+(a\s+)?pr\b",
    r"\bsubmit\s+(a\s+)?pr\b",
    r"\bpull\s+request\b",
    r"\bstandup\b",
    r"\bweekly\s+update\b",
    r"\bhedgedoc\b",
    r"\bscrum\b",
    r"\bpost\s+(a\s+)?comment\b",
    r"\bwrite\s+(an?\s+)?(review|comment|article|post|blog)\b",
    r"\bupdate\s+(the\s+)?(readme|doc)\b",
]

# Voice-specific patterns (adds voice profile validation on top).
# Profile-name triggers live in the private-skills copy of this hook;
# the tracked copy keeps generic triggers only.
VOICE_PATTERNS = [
    r"\bvoice\b",
    r"\bvexjoy\b",
    r"\bjoy\s*check\b",
    r"\banti[\s-]?ai\b",
]

SCAN_SCRIPT = Path.home() / "pgh/vexjoy-agent/scripts/scan-ai-patterns.py"
JOY_CHECK_RUBRIC = Path(__file__).resolve().parent.parent / "skills/code-quality/joy-check/references/writing-rubric.md"


def detect_external_text(prompt: str) -> bool:
    """Check if prompt indicates external text production."""
    prompt_lower = prompt.lower()
    return any(re.search(p, prompt_lower) for p in EXTERNAL_TEXT_PATTERNS)


def detect_voice_mode(prompt: str) -> bool:
    """Check if prompt requests voice-specific validation."""
    prompt_lower = prompt.lower()
    return any(re.search(p, prompt_lower) for p in VOICE_PATTERNS)


def requested_voice_skill(prompt: str) -> str | None:
    """Return the first indexed voice skill named in untrusted prompt text."""
    for match in re.finditer(r"\bvoice-[a-z0-9][a-z0-9-]*\b", prompt.lower()):
        name = match.group(0)
        if skill_call_directive(name):
            return name
    return None


def build_gate_instruction(voice_mode: bool, prompt: str = "") -> str:
    """Build the validation gate instruction block."""
    lines = [
        "[voice-output-gate: active]",
        "Before posting any external text (PR comment, standup update, doc edit):",
        "",
        "1. Write draft to /tmp/voice-gate-draft.md",
        f"2. Run: python3 {SCAN_SCRIPT} /tmp/voice-gate-draft.md --errors-only",
        "3. Fix all hits:",
        "   - em-dashes: replace with colons, commas, or periods",
        "   - corporate verbs: use plain verbs (use, help, improve)",
        "   - throat-clearing: delete, start with the point",
        "   - abstract nouns: name the specific thing",
        "4. Call the Skill tool with `joy-check`.",
        "5. Post the cleaned version only after step 2 returns zero errors",
        "",
        "This gate is mandatory. Do not skip it. Do not self-assess as clean.",
        "Run the script.",
    ]

    if voice_mode:
        voice_skill = requested_voice_skill(prompt)
        lines.extend(
            [
                "",
                "Voice mode active: validate the draft against the requested profile before posting.",
            ]
        )
        if voice_skill and voice_skill != "voice-validator":
            lines.append(f"Call the Skill tool with `{voice_skill}`.")
        lines.append("Call the Skill tool with `voice-validator`.")

    lines.append("[/voice-output-gate]")
    return "\n".join(lines)


def main():
    # Read the user prompt from stdin (Claude Code passes it as JSON)
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "") or input_data.get("message", "")
    except (json.JSONDecodeError, KeyError):
        empty_output("UserPromptSubmit").print_and_exit()
        return

    if not prompt:
        empty_output("UserPromptSubmit").print_and_exit()
        return

    is_external = detect_external_text(prompt)
    is_voice = detect_voice_mode(prompt)

    if not is_external and not is_voice:
        empty_output("UserPromptSubmit").print_and_exit()
        return

    # Build and inject the gate
    gate_text = build_gate_instruction(voice_mode=is_voice, prompt=prompt)

    output = HookOutput(
        event_name="UserPromptSubmit",
        additional_context=gate_text,
    )
    output.print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("voice-output-gate", e)
    finally:
        sys.exit(0)
