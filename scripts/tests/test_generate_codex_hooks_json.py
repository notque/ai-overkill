"""Tests for scripts/generate-codex-hooks-json.py."""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module import helper (hyphen in filename requires importlib)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parent.parent / "generate-codex-hooks-json.py"


def _load_module():
    """Load generate-codex-hooks-json.py as a module."""
    spec = importlib.util.spec_from_file_location("generate_codex_hooks_json", _SCRIPT_PATH)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
parse_allowlist = _mod.parse_allowlist
build_hooks_json = _mod.build_hooks_json


# ---------------------------------------------------------------------------
# Test 1: Empty allowlist
# ---------------------------------------------------------------------------


def test_empty_allowlist_produces_empty_hooks():
    """Empty allowlist text produces {'hooks': {}}."""
    entries = parse_allowlist("")
    result = build_hooks_json(entries)
    assert result == {"hooks": {}}


def test_comments_and_blanks_only_produces_empty():
    """Allowlist with only comments and blank lines produces empty hooks."""
    text = "# This is a comment\n\n# Another comment\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries)
    assert result == {"hooks": {}}


# ---------------------------------------------------------------------------
# Test 2: Single SessionStart with no matcher
# ---------------------------------------------------------------------------


def test_single_session_start_no_matcher():
    """SessionStart entry with no matcher gets default matcher 'startup|resume'."""
    text = "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/home/user/.codex/hooks")

    assert "SessionStart" in result["hooks"]
    blocks = result["hooks"]["SessionStart"]
    assert len(blocks) == 1
    block = blocks[0]
    assert block["matcher"] == "startup|resume"
    assert len(block["hooks"]) == 1
    hook = block["hooks"][0]
    assert hook["type"] == "command"
    assert "session-github-briefing.py" in hook["command"]
    assert hook["timeout"] == 600


# ---------------------------------------------------------------------------
# Test 3: Multiple SessionStart entries grouped into one matcher block
# ---------------------------------------------------------------------------


def test_multiple_session_start_entries_grouped():
    """Multiple SessionStart entries are grouped into one matcher block."""
    text = (
        "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
        "SessionStart:operator-context-detector.py matcher=startup|resume class=native mode=native failure=open\n"
        "SessionStart:team-config-loader.py matcher=startup|resume class=native mode=native failure=open\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    blocks = result["hooks"]["SessionStart"]
    assert len(blocks) == 1, "All SessionStart entries share the same default matcher, so only one block."
    hook_list = blocks[0]["hooks"]
    assert len(hook_list) == 3
    names = [h["command"] for h in hook_list]
    assert any("session-github-briefing.py" in n for n in names)
    assert any("operator-context-detector.py" in n for n in names)
    assert any("team-config-loader.py" in n for n in names)


# ---------------------------------------------------------------------------
# Test 4: PreToolUse without matcher raises ValueError
# ---------------------------------------------------------------------------


def test_pretooluse_without_matcher_raises():
    """PreToolUse entry without matcher raises ValueError mentioning 'Bash'."""
    text = "PreToolUse:pretool-branch-safety.py class=native mode=native failure=closed\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "matcher" in str(exc_info.value)


def test_posttooluse_without_matcher_raises():
    """PostToolUse entry without matcher raises ValueError mentioning 'Bash'."""
    text = "PostToolUse:posttool-bash-injection-scan.py class=native mode=native failure=open\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "matcher" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 5: PreToolUse+PostToolUse with Bash matcher produce separate event keys
# ---------------------------------------------------------------------------


def test_pretooluse_and_posttooluse_with_bash_matcher():
    """PreToolUse and PostToolUse with Bash matcher produce separate event keys."""
    text = (
        "PreToolUse:pretool-branch-safety.py matcher=Bash class=native mode=native failure=closed\n"
        "PostToolUse:posttool-bash-injection-scan.py matcher=Bash class=native mode=native failure=open\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    assert "PreToolUse" in result["hooks"]
    assert "PostToolUse" in result["hooks"]

    pre_blocks = result["hooks"]["PreToolUse"]
    assert len(pre_blocks) == 1
    assert pre_blocks[0]["matcher"] == "Bash"
    assert len(pre_blocks[0]["hooks"]) == 1

    post_blocks = result["hooks"]["PostToolUse"]
    assert len(post_blocks) == 1
    assert post_blocks[0]["matcher"] == "Bash"
    assert len(post_blocks[0]["hooks"]) == 1


# ---------------------------------------------------------------------------
# Test 6: Comments and blank lines are ignored
# ---------------------------------------------------------------------------


def test_comments_and_blank_lines_ignored():
    """Lines starting with # and empty lines do not become entries."""
    text = (
        "# Phase 1: safe on Codex v0.114.0+\n"
        "\n"
        "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
        "\n"
        "# Another comment\n"
        "Stop:session-summary.py class=native mode=native failure=open\n"
    )
    entries = parse_allowlist(text)
    assert len(entries) == 2
    events = [e["event"] for e in entries]
    assert "SessionStart" in events
    assert "Stop" in events


# ---------------------------------------------------------------------------
# Test 7: Malformed line raises ValueError with line number
# ---------------------------------------------------------------------------


def test_malformed_line_raises_with_line_number():
    """A line without ':' raises ValueError that includes the line number."""
    text = "# comment\n\nbadline-no-colon\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    msg = str(exc_info.value)
    assert "3" in msg, f"Expected line number 3 in error: {msg}"


def test_malformed_unknown_event_raises():
    """An unknown event name raises ValueError."""
    text = "UnknownEvent:some-hook.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "UnknownEvent" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 8: UserPromptSubmit entry has no matcher field in output
# ---------------------------------------------------------------------------


def test_user_prompt_submit_no_matcher_field():
    """UserPromptSubmit entry produces a block without a 'matcher' key."""
    text = "UserPromptSubmit:prompt-capture.py class=native mode=native failure=open\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    assert "UserPromptSubmit" in result["hooks"]
    blocks = result["hooks"]["UserPromptSubmit"]
    assert len(blocks) == 1
    assert "matcher" not in blocks[0], "UserPromptSubmit blocks must not have a 'matcher' field."
    assert "hooks" in blocks[0]


def test_stop_entry_no_matcher_field():
    """Stop entry produces a block without a 'matcher' key."""
    text = "Stop:session-summary.py class=native mode=native failure=open\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    blocks = result["hooks"]["Stop"]
    assert len(blocks) == 1
    assert "matcher" not in blocks[0]


def test_adapted_stop_command_preserves_stop_mode_for_block_translation():
    """Stop hooks that exit 2 must run through stop mode for Codex continuation."""
    entries = parse_allowlist("Stop:stop-drift-guard.py class=adapted mode=stop failure=open\n")
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    command = result["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "--event Stop" in command
    assert "--mode stop" in command
    assert "--failure-policy open" in command


# ---------------------------------------------------------------------------
# Test 9: End-to-end CLI with --dry-run produces valid JSON
# ---------------------------------------------------------------------------


def test_cli_dry_run_produces_valid_json():
    """CLI invocation with --dry-run prints valid JSON to stdout."""
    allowlist_text = (
        "# Phase 1 hooks\n"
        "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
        "UserPromptSubmit:prompt-capture.py class=native mode=native failure=open\n"
        "PreToolUse:pretool-branch-safety.py matcher=Bash class=native mode=native failure=closed\n"
        "Stop:session-summary.py class=native mode=native failure=open\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        allowlist_path = Path(tmpdir) / "allowlist.txt"
        allowlist_path.write_text(allowlist_text, encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_PATH),
                "--allowlist",
                str(allowlist_path),
                "--dry-run",
                "--codex-hooks-dir",
                "/fake/hooks",
            ],
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, f"CLI exited non-zero: {result.stderr}"
    parsed = json.loads(result.stdout)

    assert "hooks" in parsed
    assert "SessionStart" in parsed["hooks"]
    assert "UserPromptSubmit" in parsed["hooks"]
    assert "PreToolUse" in parsed["hooks"]
    assert "Stop" in parsed["hooks"]

    # Verify structure depth: hooks.SessionStart[0].hooks[0].command
    session_hook = parsed["hooks"]["SessionStart"][0]["hooks"][0]
    assert session_hook["type"] == "command"
    assert "session-github-briefing.py" in session_hook["command"]
    assert session_hook["timeout"] == 600


# ---------------------------------------------------------------------------
# Test 10: Event ordering is canonical
# ---------------------------------------------------------------------------


def test_event_ordering():
    """Present events retain their relative order from the current release."""
    text = (
        "Stop:session-summary.py class=native mode=native failure=open\n"
        "PostToolUse:posttool-bash-injection-scan.py matcher=Bash class=native mode=native failure=open\n"
        "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
        "PreToolUse:pretool-branch-safety.py matcher=Bash class=native mode=native failure=closed\n"
        "UserPromptSubmit:prompt-capture.py class=native mode=native failure=open\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    keys = list(result["hooks"].keys())
    expected_order = ["SessionStart", "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop"]
    assert keys == expected_order, f"Got order: {keys}"


# ---------------------------------------------------------------------------
# Test 11: Command shape uses python3 and the configured hooks dir
# ---------------------------------------------------------------------------


def test_command_shape_uses_configured_dir():
    """Hook command uses python3 and the codex-hooks-dir path."""
    text = "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/home/testuser/.codex/hooks")

    hook = result["hooks"]["SessionStart"][0]["hooks"][0]
    cmd = hook["command"]
    assert cmd.startswith("python3 "), f"Command should start with 'python3 ': {cmd}"
    assert "/home/testuser/.codex/hooks/session-github-briefing.py" in cmd


def test_command_shape_default_dir_uses_home():
    """Hook command uses $HOME/.codex/hooks when codex_hooks_dir is not specified."""
    import os

    home = os.environ.get("HOME", "~")
    text = "SessionStart:session-github-briefing.py matcher=startup|resume class=native mode=native failure=open\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries)

    hook = result["hooks"]["SessionStart"][0]["hooks"][0]
    cmd = hook["command"]
    assert f"{home}/.codex/hooks/session-github-briefing.py" in cmd


# ---------------------------------------------------------------------------
# Current Codex hook surface and adapter contract (0.144.1)
# ---------------------------------------------------------------------------


def test_current_codex_event_surface_is_complete():
    """Generator recognizes all ten command-hook events in release order."""
    assert _mod.EVENT_ORDER == [
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


def test_explicit_adapter_metadata_is_parsed():
    """Allowlist entries carry explicit matcher, adapter mode, and failure policy."""
    entries = parse_allowlist(
        "PreToolUse:pretool-plan-gate.py matcher=Edit|Write class=adapted mode=patch failure=closed\n"
    )
    assert entries == [
        {
            "event": "PreToolUse",
            "filename": "pretool-plan-gate.py",
            "matcher": "Edit|Write",
            "mode": "patch",
            "failure_policy": "closed",
            "classification": "adapted",
        }
    ]


def test_explicit_metadata_requires_classification():
    """Current entries cannot infer native/adapted classification."""
    with pytest.raises(ValueError, match="class"):
        parse_allowlist("Stop:session-summary.py mode=native failure=open")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Stop:session-summary.py class=native mode=bogus failure=open", "mode"),
        ("Stop:session-summary.py class=adapted mode=stop failure=bogus", "failure"),
        ("Stop:session-summary.py matcher=* class=adapted mode=stop failure=open", "matcher"),
        ("PreCompact:precompact-archive.py matcher=manual|auto class=adapted mode=patch failure=open", "PreCompact"),
        ("PreToolUse:pretool-plan-gate.py matcher=Bash class=adapted mode=patch failure=closed", "patch"),
    ],
)
def test_invalid_adapter_metadata_is_rejected(line, expected):
    """Impossible event/matcher/mode combinations fail before installation."""
    with pytest.raises(ValueError, match=expected):
        parse_allowlist(line)


def test_generated_command_uses_adapter_cli_contract():
    """Every explicit entry runs its target through the shared adapter."""
    entries = parse_allowlist(
        "PreToolUse:pretool-plan-gate.py matcher=Edit|Write class=adapted mode=patch failure=closed\n"
    )
    result = build_hooks_json(entries, codex_hooks_dir="/fake hooks")
    hook = result["hooks"]["PreToolUse"][0]["hooks"][0]
    command = hook["command"]
    assert command == (
        "python3 '/fake hooks/codex-hook-adapter.py' "
        "--hook '/fake hooks/pretool-plan-gate.py' "
        "--event PreToolUse --matcher 'Edit|Write' --mode patch --failure-policy closed"
    )


def test_all_ten_events_build_in_canonical_order():
    """Generated JSON keeps the release event order regardless of allowlist order."""
    text = "\n".join(
        [
            "Stop:session-summary.py class=native mode=native failure=open",
            "SubagentStop:routing-outcome-recorder.py matcher=* class=native mode=native failure=open",
            "UserPromptSubmit:prompt-capture.py class=native mode=native failure=open",
            "PostCompact:postcompact-handler.py matcher=manual|auto class=native mode=native failure=open",
            "PreCompact:precompact-archive.py matcher=manual|auto class=adapted mode=precompact failure=open",
            "PostToolUse:posttool-bash-injection-scan.py matcher=Bash class=native mode=native failure=open",
            "PermissionRequest:security-review-hook.py matcher=Bash class=native mode=native failure=closed",
            "PreToolUse:pretool-branch-safety.py matcher=Bash class=native mode=native failure=closed",
            "SubagentStart:team-config-loader.py matcher=* class=native mode=native failure=open",
            "SessionStart:session-context.py matcher=startup|resume class=native mode=native failure=open",
        ]
    )
    result = build_hooks_json(parse_allowlist(text), codex_hooks_dir="/fake/hooks")
    assert list(result["hooks"]) == _mod.EVENT_ORDER


@pytest.mark.parametrize("matcher", ["Edit|Write", "apply_patch", "^apply_patch$"])
def test_patch_mode_accepts_documented_apply_patch_aliases(matcher):
    """Codex documents both canonical and Claude-compatible edit matchers."""
    entries = parse_allowlist(
        f"PreToolUse:pretool-plan-gate.py matcher={matcher} class=adapted mode=patch failure=closed"
    )
    assert entries[0]["matcher"] == matcher


def test_native_tool_events_accept_mcp_regex_matchers():
    """Current Codex tool hooks can target MCP tool names as well as Bash."""
    entries = parse_allowlist(
        "PermissionRequest:security-review-hook.py matcher=mcp__filesystem__.* class=native mode=native failure=closed"
    )
    assert entries[0]["matcher"] == "mcp__filesystem__.*"


def test_build_rejects_missing_target_hook(tmp_path):
    """hooks.json is never built with a command pointing at a missing source file."""
    entries = parse_allowlist("Stop:missing-hook.py class=native mode=native failure=open")
    with pytest.raises(ValueError, match=r"missing-hook\.py"):
        build_hooks_json(entries, codex_hooks_dir="/fake/hooks", source_hooks_dir=tmp_path)


def test_cli_rejects_allowlist_with_missing_target_hook(tmp_path):
    """CLI generation fails before replacing hooks.json when a target is absent."""
    allowlist = tmp_path / "allowlist.txt"
    output = tmp_path / "hooks.json"
    allowlist.write_text("Stop:missing-hook.py class=native mode=native failure=open\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--allowlist",
            str(allowlist),
            "--source-hooks-dir",
            str(tmp_path / "hooks"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "missing-hook.py" in result.stderr
    assert not output.exists()
