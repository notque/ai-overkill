#!/usr/bin/env python3
"""
Generate ~/.codex/hooks.json from a curated allowlist file.

Current entries use:
    EVENT:filename [matcher=REGEX] class=native|adapted mode=MODE failure=open|closed

Comments (lines starting with #) and blank lines are ignored.

Usage:
    python3 scripts/generate-codex-hooks-json.py --allowlist scripts/codex-hooks-allowlist.txt
    python3 scripts/generate-codex-hooks-json.py --allowlist scripts/codex-hooks-allowlist.txt --dry-run
    python3 scripts/generate-codex-hooks-json.py --allowlist scripts/codex-hooks-allowlist.txt --output /tmp/hooks.json
"""

import argparse
import json
import os
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path

# Events that support a matcher in Codex 0.144.1.
EVENTS_SUPPORTING_MATCHER = {
    "SessionStart",
    "SubagentStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "SubagentStop",
}

# Events where matcher should default to "startup|resume" when omitted.
EVENTS_WITH_DEFAULT_MATCHER = {"SessionStart"}

# Events where matcher field is omitted entirely when not specified.
EVENTS_WITHOUT_MATCHER = {"UserPromptSubmit", "Stop"}

# All known Codex events, in the canonical output order.
EVENT_ORDER = [
    "SessionStart",
    "SubagentStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStop",
    "Stop",
]

ALL_KNOWN_EVENTS = set(EVENT_ORDER)
ADAPTER_MODES = {"native", "prompt", "patch", "precompact", "subagent-stop", "stop"}
FAILURE_POLICIES = {"open", "closed"}
CLASSIFICATIONS = {"native", "adapted"}
MODE_EVENTS = {
    "prompt": {"UserPromptSubmit"},
    "patch": {"PreToolUse", "PostToolUse"},
    "precompact": {"PreCompact"},
    "subagent-stop": {"SubagentStop"},
    "stop": {"Stop"},
}

# Registrations intentionally excluded from the Codex mirror. Keeping this in
# production code makes unsupported coverage machine-readable and forces every
# Claude registration to have a precise reviewed decision.
UNSUPPORTED_REGISTRATIONS = {
    ("PreToolUse", "reference-loading-enforcer.py"): (
        "Codex SubagentStart omits the Agent task prompt and tool input this reference injector requires."
    ),
    ("PreToolUse", "creation-protocol-enforcer.py"): (
        "Codex SubagentStart does not expose the Agent task text used to detect creation requests."
    ),
    ("PreToolUse", "pretool-section-integrity-validator.py"): (
        "Codex SubagentStart does not expose the Agent tool input whose routed sections this validator checks."
    ),
    ("PostToolUse", "usage-tracker.py"): (
        "Codex has no PostToolUse surface for Claude Skill or Agent tool invocations tracked here."
    ),
    ("PostToolUse", "review-capture.py"): (
        "Codex has no PostToolUse Agent result carrying the structured reviewer output this hook captures."
    ),
    ("PostToolUse", "routing-decision-recorder.py"): (
        "Codex has no PostToolUse Agent or Workflow result containing the routed decision marker."
    ),
    ("PostToolUse", "agent-grade-on-change.py"): (
        "Codex copy installs omit evals/harness.py, and this hook emits an ad hoc message object outside the hook schema."
    ),
    ("StopFailure", "stop-failure-handler.py"): ("Codex 0.144.1 does not publish a StopFailure lifecycle event."),
    ("PostCompact", "postcompact-handler.py"): (
        "Codex PostCompact cannot inject the model-visible plan context that is this hook's core behavior."
    ),
}


def parse_allowlist(text: str) -> list[dict]:
    """Parse allowlist text into a list of entry dicts.

    Args:
        text: Contents of the allowlist file (not a path; the raw text).

    Returns:
        List of dicts with event, filename, matcher, mode, and failure_policy.

    Raises:
        ValueError: On malformed lines (includes line number in message).
    """
    entries: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            raise ValueError(f"Line {lineno}: missing ':' separator in {raw!r}. Expected EVENT:filename [matcher].")

        event_part, rest = line.split(":", 1)
        event = event_part.strip()
        rest_parts = rest.strip().split()

        if not rest_parts:
            raise ValueError(f"Line {lineno}: missing filename after ':' in {raw!r}.")

        filename = rest_parts[0]
        if event not in ALL_KNOWN_EVENTS:
            known = ", ".join(sorted(ALL_KNOWN_EVENTS))
            raise ValueError(f"Line {lineno}: unknown event {event!r}. Known events: {known}.")
        if not filename.endswith(".py") or "/" in filename or "\\" in filename:
            raise ValueError(f"Line {lineno}: filename must be a bare .py hook name, got {filename!r}.")

        matcher: str | None = None
        mode = "native"
        failure_policy = "open"
        classification = "native"

        metadata: dict[str, str] = {}
        for token in rest_parts[1:]:
            if "=" not in token:
                raise ValueError(f"Line {lineno}: current entries require explicit key=value metadata.")
            key, value = token.split("=", 1)
            if key not in {"matcher", "class", "mode", "failure"}:
                raise ValueError(f"Line {lineno}: unknown metadata key {key!r}.")
            if key in metadata:
                raise ValueError(f"Line {lineno}: duplicate metadata key {key!r}.")
            if not value:
                raise ValueError(f"Line {lineno}: metadata key {key!r} has an empty value.")
            metadata[key] = value
        required_metadata = {"class", "mode", "failure"}
        missing_metadata = sorted(required_metadata - metadata.keys())
        if missing_metadata:
            raise ValueError(f"Line {lineno}: missing required metadata: {', '.join(missing_metadata)}.")
        matcher = metadata.get("matcher")
        mode = metadata["mode"]
        failure_policy = metadata["failure"]
        classification = metadata["class"]

        if mode not in ADAPTER_MODES:
            raise ValueError(f"Line {lineno}: unknown adapter mode {mode!r}.")
        if failure_policy not in FAILURE_POLICIES:
            raise ValueError(f"Line {lineno}: unknown failure policy {failure_policy!r}.")
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"Line {lineno}: unknown compatibility class {classification!r}.")
        if classification == "native" and mode != "native":
            raise ValueError(f"Line {lineno}: class=native requires mode=native.")
        if event in EVENTS_WITHOUT_MATCHER and matcher is not None:
            raise ValueError(f"Line {lineno}: {event} does not support matcher metadata.")
        if event in EVENTS_SUPPORTING_MATCHER and matcher is None:
            raise ValueError(f"Line {lineno}: {event} requires explicit matcher=... metadata.")
        allowed_events = MODE_EVENTS.get(mode)
        if allowed_events is not None and event not in allowed_events:
            raise ValueError(f"Line {lineno}: mode={mode} is not valid for {event}.")
        if mode == "patch" and (matcher is None or re.search(r"Edit|Write|apply_patch", matcher) is None):
            raise ValueError(f"Line {lineno}: patch mode requires an Edit, Write, or apply_patch matcher.")

        entries.append(
            {
                "event": event,
                "filename": filename,
                "matcher": matcher,
                "mode": mode,
                "failure_policy": failure_policy,
                "classification": classification,
            }
        )

    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry["event"], entry["filename"])
        if key in seen:
            raise ValueError(f"Duplicate hook registration: {entry['event']}:{entry['filename']}.")
        seen.add(key)

    return entries


def validate_hook_files(entries: list[dict], source_hooks_dir: Path) -> None:
    """Reject commands whose adapter or target hook is absent."""
    required = {"codex-hook-adapter.py", *(entry["filename"] for entry in entries)}
    missing = sorted(filename for filename in required if not (source_hooks_dir / filename).is_file())
    if missing:
        raise ValueError(f"Missing Codex hook source files in {source_hooks_dir}: {', '.join(missing)}")


def build_hooks_json(
    entries: list[dict],
    codex_hooks_dir: str | None = None,
    source_hooks_dir: Path | None = None,
) -> dict:
    """Build the Codex hooks.json structure from parsed allowlist entries.

    Args:
        entries: List of entry dicts from parse_allowlist().
        codex_hooks_dir: Directory where hooks will reside. Defaults to $HOME/.codex/hooks.
        source_hooks_dir: Source directory used to prove every generated hook exists.

    Returns:
        Dict representing the full hooks.json structure.
    """
    if codex_hooks_dir is None:
        codex_hooks_dir = os.path.join(os.environ.get("HOME", "~"), ".codex", "hooks")
    if source_hooks_dir is None:
        source_hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
    validate_hook_files(entries, source_hooks_dir)

    # Group by (event, effective_matcher) so shared matchers collapse into one block.
    # Key: (event, effective_matcher_or_None)
    groups: dict[tuple[str, str | None], list[dict]] = {}

    for entry in entries:
        event = entry["event"]
        raw_matcher = entry["matcher"]

        # Determine the effective matcher for grouping and output.
        if event in EVENTS_WITH_DEFAULT_MATCHER and raw_matcher is None:
            effective_matcher: str | None = "startup|resume"
        elif event in EVENTS_WITHOUT_MATCHER:
            effective_matcher = None  # Omit matcher field entirely.
        else:
            effective_matcher = raw_matcher  # Already validated non-None for requiring events.

        key = (event, effective_matcher)
        groups.setdefault(key, [])
        groups[key].append(entry)

    if not groups:
        return {"hooks": {}}

    # Build output dict with events in canonical order.
    hooks_by_event: dict[str, list[dict]] = {}

    for event in EVENT_ORDER:
        # Collect all matcher groups for this event, sorted by matcher for determinism.
        event_groups = {k: v for k, v in groups.items() if k[0] == event}
        if not event_groups:
            continue

        sorted_keys = sorted(event_groups.keys(), key=lambda k: (k[1] is None, k[1] or ""))
        event_blocks: list[dict] = []

        for key in sorted_keys:
            _, matcher = key
            group_entries = event_groups[key]

            hook_entries = [
                {
                    "type": "command",
                    "command": " ".join(
                        [
                            "python3",
                            shlex.quote(f"{codex_hooks_dir}/codex-hook-adapter.py"),
                            "--hook",
                            shlex.quote(f"{codex_hooks_dir}/{entry['filename']}"),
                            "--event",
                            shlex.quote(entry["event"]),
                            "--matcher",
                            shlex.quote(entry["matcher"] or "*"),
                            "--mode",
                            shlex.quote(entry["mode"]),
                            "--failure-policy",
                            shlex.quote(entry["failure_policy"]),
                        ]
                    ),
                    "timeout": 600,
                }
                for entry in group_entries
            ]

            block: dict = {}
            if matcher is not None:
                block["matcher"] = matcher
            block["hooks"] = hook_entries

            event_blocks.append(block)

        hooks_by_event[event] = event_blocks

    return {"hooks": hooks_by_event}


def main() -> None:
    """Parse CLI arguments, read the allowlist, and write or print hooks.json.

    Exits with code 0 on success, 1 on any error.
    """
    parser = argparse.ArgumentParser(
        description="Generate ~/.codex/hooks.json from a curated allowlist file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--allowlist", required=True, help="Path to the allowlist file.")
    parser.add_argument(
        "--output",
        default=os.path.join(os.environ.get("HOME", "~"), ".codex", "hooks.json"),
        help="Path to write hooks.json (default: ~/.codex/hooks.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout instead of writing to disk.",
    )
    parser.add_argument(
        "--codex-hooks-dir",
        default=None,
        help="Directory where hooks will live (default: $HOME/.codex/hooks).",
    )
    parser.add_argument(
        "--source-hooks-dir",
        default=str(Path(__file__).resolve().parent.parent / "hooks"),
        help="Source hooks directory used to reject missing adapter/target files.",
    )

    args = parser.parse_args()

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.exists():
        print(f"Error: allowlist file not found: {allowlist_path}", file=sys.stderr)
        sys.exit(1)

    try:
        text = allowlist_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading allowlist: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        entries = parse_allowlist(text)
    except ValueError as exc:
        print(f"Error parsing allowlist: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        result = build_hooks_json(
            entries,
            codex_hooks_dir=args.codex_hooks_dir,
            source_hooks_dir=Path(args.source_hooks_dir),
        )
    except Exception as exc:
        print(f"Error building hooks JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    output_json = json.dumps(result, indent=2)

    if args.dry_run:
        print(output_json)
        return

    output_path = Path(args.output)

    # Back up existing file before overwriting.
    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = output_path.with_suffix(f".bak.{timestamp}")
        try:
            backup_path.write_bytes(output_path.read_bytes())
        except OSError as exc:
            print(f"Warning: could not create backup {backup_path}: {exc}", file=sys.stderr)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Error writing {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
