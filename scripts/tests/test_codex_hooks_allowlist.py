#!/usr/bin/env python3
"""Current Codex 0.144.1 hook compatibility inventory tests.

ADR-182's six-hook Bash-only allowlist was correct for the older Codex hook
surface. Codex now supports apply_patch aliases and more lifecycle events.
These tests pin the reviewed 76-registration accounting so a new Claude hook
cannot silently create or remove Codex coverage.
"""

import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate-codex-hooks-json.py"
HOOK_HEALTH_PATH = REPO_ROOT / "scripts" / "validate-hook-health.py"
HOOKS_DIR = REPO_ROOT / "hooks"
CLAUDE_SETTINGS = REPO_ROOT / ".claude" / "settings.json"

_COMMAND_HOOK_RE = re.compile(r"(?:^|/)hooks/([A-Za-z0-9_-]+\.py)(?:['\" ]|$)")


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_codex_hooks_json", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()
UNSUPPORTED_REGISTRATIONS = set(getattr(GENERATOR, "UNSUPPORTED_REGISTRATIONS", {}))


def _load_hook_health():
    spec = importlib.util.spec_from_file_location("validate_hook_health", HOOK_HEALTH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entries() -> list[dict]:
    return GENERATOR.parse_allowlist(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def _claude_registrations() -> set[tuple[str, str]]:
    settings = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    registrations: set[tuple[str, str]] = set()
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                match = _COMMAND_HOOK_RE.search(hook.get("command", ""))
                if match:
                    registrations.add((event, match.group(1)))
    return registrations


def test_inventory_accounting_is_74_equals_26_plus_35_plus_13() -> None:
    """Every Claude registration has one reviewed current Codex decision."""
    entries = _entries()
    classes = Counter(entry["classification"] for entry in entries)
    assert len(entries) == 61
    assert classes == {"native": 26, "adapted": 35}
    assert len(UNSUPPORTED_REGISTRATIONS) == 13
    assert len(entries) + len(UNSUPPORTED_REGISTRATIONS) == 74


def test_supported_and_unsupported_sets_partition_claude_settings() -> None:
    """Coverage drift fails until a new registration is classified."""
    supported = {(entry["event"], entry["filename"]) for entry in _entries()}
    assert not supported & UNSUPPORTED_REGISTRATIONS
    assert supported | UNSUPPORTED_REGISTRATIONS == _claude_registrations()


def test_every_current_entry_has_explicit_compatibility_metadata() -> None:
    """Production entries never rely on legacy mode or matcher inference."""
    for raw in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assert " class=" in line, line
        assert " mode=" in line, line
        assert " failure=" in line, line
        event = line.split(":", 1)[0]
        if event not in {"UserPromptSubmit", "Stop"}:
            assert " matcher=" in line, line


def test_all_supported_hook_files_exist() -> None:
    """Generated commands never point to a missing target hook."""
    missing = [entry["filename"] for entry in _entries() if not (HOOKS_DIR / entry["filename"]).is_file()]
    assert not missing


def test_apply_patch_entries_use_patch_mode_and_alias_matcher() -> None:
    """Edit/Write guards are promoted only through deterministic patch adaptation."""
    patch_entries = [entry for entry in _entries() if entry["mode"] == "patch"]
    assert len(patch_entries) == 23
    assert {entry["event"] for entry in patch_entries} == {"PreToolUse", "PostToolUse"}
    assert {entry["matcher"] for entry in patch_entries} == {"Edit|Write"}
    assert all(entry["classification"] == "adapted" for entry in patch_entries)


def test_failure_closed_is_limited_to_pretool_enforcement() -> None:
    """Observers continue on adapter failure; only pre-action gates fail closed."""
    closed = [entry for entry in _entries() if entry["failure_policy"] == "closed"]
    assert closed
    assert all(entry["event"] == "PreToolUse" for entry in closed)


def test_unsupported_boundaries_are_exact() -> None:
    """Absent and semantically incomplete paths remain visibly unsupported."""
    assert {
        ("PreToolUse", "reference-loading-enforcer.py"),
        ("PreToolUse", "pretool-subagent-warmstart.py"),
        ("PreToolUse", "creation-protocol-enforcer.py"),
        ("PreToolUse", "pretool-section-integrity-validator.py"),
        ("PostToolUse", "posttool-session-reads.py"),
        ("PostToolUse", "usage-tracker.py"),
        ("PostToolUse", "review-capture.py"),
        ("PostToolUse", "instruction-compliance.py"),
        ("PostToolUse", "routing-decision-recorder.py"),
        ("PostToolUse", "agent-grade-on-change.py"),
        ("TaskCompleted", "task-completed-learner.py"),
        ("StopFailure", "stop-failure-handler.py"),
        ("PostCompact", "postcompact-handler.py"),
    } == UNSUPPORTED_REGISTRATIONS


def test_unsupported_inventory_has_machine_owned_precise_reasons() -> None:
    """Every excluded registration carries a reviewable production reason."""
    reasons = GENERATOR.UNSUPPORTED_REGISTRATIONS
    assert len(reasons) == 13
    assert all(isinstance(reason, str) and len(reason.split()) >= 6 for reason in reasons.values())
    assert all("unsupported" not in reason.lower() for reason in reasons.values())


def test_codex_adapter_is_accounted_as_a_generated_dispatch_target() -> None:
    """The wrapper is active via hooks.json, not dormant Claude registration."""
    hook_health = _load_hook_health()
    assert "codex-hook-adapter.py" in hook_health.dispatched_basenames()


def test_semantic_reclassifications_match_the_runtime_contracts() -> None:
    """Bash rename detection is native; the drift rewake needs Stop adaptation."""
    entries = {(entry["event"], entry["filename"]): entry for entry in _entries()}
    rename = entries[("PostToolUse", "posttool-rename-sweep.py")]
    assert rename["matcher"] == "Bash"
    assert rename["classification"] == "native"
    assert rename["mode"] == "native"

    drift = entries[("Stop", "stop-drift-guard.py")]
    assert drift["classification"] == "adapted"
    assert drift["mode"] == "stop"


def test_adr_enforcement_empty_posttool_payload_emits_valid_json() -> None:
    """The newly promoted PostToolUse hook uses its declared event constant."""
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "adr-enforcement.py")],
        input="",
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "NameError" not in result.stderr
