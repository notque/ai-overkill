#!/usr/bin/env python3
"""Tests for the five learning-loop defect fixes.

TDD: each test was written BEFORE its fix and verified to FAIL on the
unfixed code, then PASS after the fix. Grouped by defect number.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Resolve paths
REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"
LIB_DIR = HOOKS_DIR / "lib"

# Add lib to path so we can import hook modules
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOKS_DIR))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_learning_dir(tmp_path):
    """Isolated learning directory for DB tests."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(db_dir)}):
        # Reset the module-level _initialized flag so init_db() runs fresh
        import learning_db_v2

        learning_db_v2._initialized = False
        yield db_dir
        learning_db_v2._initialized = False


@pytest.fixture()
def seeded_db(tmp_learning_dir):
    """Learning DB with a seeded high-confidence error pattern.

    source="manual-seed" (not "test*") -- search_learnings() defaults to
    excluding source LIKE 'test%' rows (ADR: pretool-injector-scoping,
    parity with query_learnings()'s ADR-191 exclude_test_sources), and this
    row is meant to exercise the real end-to-end injection path, not that
    filter.
    """
    import learning_db_v2

    learning_db_v2.init_db()
    learning_db_v2.record_learning(
        topic="python",
        key="test-import-error",
        value="ModuleNotFoundError: No module named 'foo' -> pip install foo",
        category="error",
        confidence=0.9,
        tags=["python", "import_error"],
        source="manual-seed",
        error_type="import_error",
        error_signature="test-sig-001",
    )
    return tmp_learning_dir


# ===========================================================================
# DEFECT 1: Dead injector (NameError on sanitize_for_context)
# ===========================================================================


class TestDeadInjector:
    """pretool-learning-injector.py calls sanitize_for_context at line 124,
    but the import lives inside main() at line 181. format_hints() at module
    scope cannot see it -> NameError swallowed by catch-all -> feature dead.

    Fix: module-level import of sanitize_for_context from learning_db_v2.
    """

    def test_format_hints_calls_sanitize(self, seeded_db):
        """format_hints must call sanitize_for_context without NameError."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "pretool_learning_injector",
            str(HOOKS_DIR / "pretool-learning-injector.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Build a fake result matching what search_learnings returns
        results = [
            {
                "value": "ModuleNotFoundError -> pip install foo",
                "category": "error",
                "error_type": "import_error",
                "topic": "python",
            }
        ]
        # This must NOT raise NameError
        output = mod.format_hints(results)
        assert output, "format_hints returned empty string for valid results"
        assert "import_error" in output or "pip install" in output

    def test_injector_emits_hint_for_seeded_row(self, seeded_db):
        """End-to-end: the hook must emit non-empty JSON output for a Bash
        command matching a seeded DB pattern (python/import_error).
        """
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pip install something"},
        }
        env = os.environ.copy()
        env["CLAUDE_LEARNING_DIR"] = str(seeded_db)
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "pretool-learning-injector.py")],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
        # Must produce non-empty JSON with additionalContext or description
        stdout = result.stdout.strip()
        assert stdout, f"Hook produced no output. stderr: {result.stderr}"
        parsed = json.loads(stdout)
        # The output should have context (additionalContext or description)
        # Check all possible nesting levels for context
        hso = parsed.get("hookSpecificOutput", {})
        has_content = bool(
            parsed.get("additionalContext")
            or parsed.get("description")
            or parsed.get("result", {}).get("additionalContext")
            or parsed.get("result", {}).get("description")
            or hso.get("additionalContext")
            or hso.get("description")
        )
        assert has_content, f"Hook output has no context/description: {parsed}"


# ===========================================================================
# DEFECT 2: Case-sensitive sanitizer + untested
# ===========================================================================


class TestSanitizerCaseInsensitive:
    """sanitize_for_context replaces only lowercase <system> etc.
    <SYSTEM> passes through. Fix: case-insensitive replacement.
    """

    @pytest.mark.parametrize(
        "tag",
        ["system", "SYSTEM", "System", "SyStEm", "user", "USER", "User", "assistant", "ASSISTANT", "human", "HUMAN"],
    )
    def test_role_tag_neutralized(self, tag):
        from learning_db_v2 import sanitize_for_context

        text = f"before <{tag}> middle </{tag}> after"
        result = sanitize_for_context(text)
        # The tag must be gone regardless of case
        lower_result = result.lower()
        assert f"<{tag.lower()}>" not in lower_result, f"<{tag}> was NOT neutralized"
        assert f"</{tag.lower()}>" not in lower_result, f"</{tag}> was NOT neutralized"

    def test_zero_width_chars_stripped(self):
        from learning_db_v2 import sanitize_for_context

        text = "hello​world‍﻿"
        result = sanitize_for_context(text)
        assert "​" not in result
        assert "‍" not in result
        assert "﻿" not in result
        assert "helloworld" in result

    def test_empty_and_none(self):
        from learning_db_v2 import sanitize_for_context

        assert sanitize_for_context("") == ""
        assert sanitize_for_context(None) is None


class TestSanitizeFtsQuery:
    """sanitize_fts_query must strip FTS5 operators."""

    @pytest.mark.parametrize(
        "input_term,expected_absent",
        [
            ('"quoted"', '"'),
            ("term*", "*"),
            ("NOT term", "NOT"),
            ("col:value", ":"),
            ("a AND b", "AND"),
            ("a OR b", "OR"),
            ("NEAR(a b)", "NEAR"),
            ("(grouped)", "("),
        ],
    )
    def test_operators_stripped(self, input_term, expected_absent):
        from learning_db_v2 import sanitize_fts_query

        result = sanitize_fts_query(input_term)
        assert expected_absent not in result


# ===========================================================================
# DEFECT 3: Untrusted replay in error-learner
# ===========================================================================


class TestUntrustedReplay:
    """error-learner.py replays stored solutions verbatim. They must be
    wrapped in <untrusted-content> + SECURITY preamble.
    """

    def test_existing_solution_wrapped(self, seeded_db):
        """When error-learner replays a stored solution, the output must
        contain the untrusted-content wrapper.
        """
        import learning_db_v2

        # Seed with the EXACT signature that lookup_error_solution will
        # generate from the error message, so the lookup finds the row.
        error_msg = "ModuleNotFoundError: No module named 'bar'"
        error_type = learning_db_v2.classify_error(error_msg)
        sig = learning_db_v2.generate_signature(error_msg, error_type)

        learning_db_v2.record_learning(
            topic=error_type,
            key=sig,
            value=f"{error_msg[:200]} -> pip install bar",
            category="error",
            confidence=0.9,
            source="test-seed",
            error_signature=sig,
            error_type=error_type,
            fix_type="auto",
            fix_action="install_module",
        )

        event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "python3 test.py"},
            "tool_result": {
                "error": error_msg,
                "is_error": True,
            },
        }
        env = os.environ.copy()
        env["CLAUDE_LEARNING_DIR"] = str(seeded_db)
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "error-learner.py")],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        # The replayed solution must be wrapped
        assert "<untrusted-content>" in combined or "SECURITY:" in combined, (
            f"Replayed solution not wrapped as untrusted. Output: {combined[:500]}"
        )


# ===========================================================================
# DEFECT 4: Open outcome loop (coverage, not sensitivity)
# ===========================================================================


class TestOutcomeFinalizerCoverage:
    """567 decisions vs 41 outcomes. Every pending decision must reach a
    terminal state (failure/success/neutral) by session end. The Stop
    fallback must resolve whatever UserPromptSubmit did not.
    """

    @pytest.fixture()
    def routing_state_dir(self, tmp_path):
        """Isolated routing state dir."""
        state_dir = tmp_path / "routing_state"
        state_dir.mkdir()
        with patch.dict(os.environ, {"CLAUDE_ROUTING_STATE_DIR": str(state_dir)}):
            yield state_dir

    def test_stop_resolves_all_pending(self, tmp_learning_dir, routing_state_dir):
        """After Stop fires, no pending outcomes remain."""
        import learning_db_v2

        learning_db_v2._initialized = False
        learning_db_v2.init_db()

        # Seed a decision row
        learning_db_v2.record_learning(
            topic="routing",
            key="test-agent:test-skill",
            value="test route",
            category="effectiveness",
            confidence=0.5,
            source="test-seed",
        )

        from routing_outcome_state import append_pending_outcome, peek_pending_outcomes

        session_id = "test-session-stop"
        append_pending_outcome(session_id, "test-agent:test-skill", errors=False)

        # Verify pending exists
        pending = peek_pending_outcomes(session_id)
        assert len(pending) == 1, "Pre-condition: one pending outcome"

        # Fire the Stop fallback
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_learning_recorder",
            str(HOOKS_DIR / "session-learning-recorder.py"),
        )
        slr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(slr)
        slr.finalize_routing_outcomes(session_id)

        # After Stop: pending must be empty
        remaining = peek_pending_outcomes(session_id)
        assert len(remaining) == 0, f"Stop left {len(remaining)} pending outcomes unresolved"

    def test_fixture_replay_three_decisions(self, tmp_learning_dir, routing_state_dir):
        """Three decisions (error, clean, clean) -> finalizer resolves all three.
        Outcome: 1 failure + 2 neutral.
        """
        import learning_db_v2

        learning_db_v2._initialized = False
        learning_db_v2.init_db()

        keys = ["a:s1", "b:s2", "c:s3"]
        for k in keys:
            learning_db_v2.record_learning(
                topic="routing",
                key=k,
                value=f"route {k}",
                category="effectiveness",
                confidence=0.5,
                source="test-seed",
            )

        from routing_outcome_state import (
            append_pending_outcome,
            peek_pending_outcomes,
        )

        session_id = "test-session-fixture"
        # a:s1 has errors, b:s2 and c:s3 are clean
        append_pending_outcome(session_id, "a:s1", errors=True)
        append_pending_outcome(session_id, "b:s2", errors=False)
        append_pending_outcome(session_id, "c:s3", errors=False)

        pending = peek_pending_outcomes(session_id)
        assert len(pending) == 3

        # Simulate the Stop fallback
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_learning_recorder",
            str(HOOKS_DIR / "session-learning-recorder.py"),
        )
        slr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(slr)
        slr.finalize_routing_outcomes(session_id)

        # All resolved
        remaining = peek_pending_outcomes(session_id)
        assert len(remaining) == 0, f"Left {len(remaining)} pending"

        # Verify the error key was decayed
        from routing_outcome_score import _current_confidence

        conf_a = _current_confidence("a:s1")
        assert conf_a < 0.5, f"Error key not decayed: {conf_a}"

    def test_userprompt_resolves_single_pending(self, tmp_learning_dir, routing_state_dir):
        """A single pending dispatch + acceptance prompt -> success outcome."""
        import learning_db_v2

        learning_db_v2._initialized = False
        learning_db_v2.init_db()

        learning_db_v2.record_learning(
            topic="routing",
            key="agent:skill",
            value="test route",
            category="effectiveness",
            confidence=0.5,
            source="test-seed",
        )

        from routing_outcome_state import append_pending_outcome, peek_pending_outcomes

        session_id = "test-session-accept"
        append_pending_outcome(session_id, "agent:skill", errors=False)

        # Simulate UserPromptSubmit with acceptance
        event = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": session_id,
            "prompt": "thanks, that worked",
        }
        env = os.environ.copy()
        env["CLAUDE_LEARNING_DIR"] = str(tmp_learning_dir)
        env["CLAUDE_ROUTING_STATE_DIR"] = str(routing_state_dir)
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "routing-outcome-finalizer.py")],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 0

        # After finalizer: pending must be empty
        remaining = peek_pending_outcomes(session_id)
        assert len(remaining) == 0, f"Finalizer left {len(remaining)} pending"


# ===========================================================================
# DEFECT 5: DB-path dedup (get_db_dir exported)
# ===========================================================================


class TestGetDbDirExported:
    """get_db_dir() must be a public export of learning_db_v2, keeping
    ADR-122 chmod hardening, and the 4 copy sites must use it.
    """

    def test_get_db_dir_exists(self):
        """learning_db_v2 exports get_db_dir as a public function."""
        from learning_db_v2 import get_db_dir

        assert callable(get_db_dir)

    def test_get_db_dir_honors_env(self, tmp_path):
        from learning_db_v2 import get_db_dir

        custom = tmp_path / "custom_learning"
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(custom)}):
            result = get_db_dir()
            assert result == custom

    def test_get_db_dir_falls_back_to_the_module_default(self, monkeypatch):
        """With CLAUDE_LEARNING_DIR unset, get_db_dir() returns _DEFAULT_DB_DIR."""
        import learning_db_v2

        monkeypatch.delenv("CLAUDE_LEARNING_DIR", raising=False)
        assert learning_db_v2.get_db_dir() == learning_db_v2._DEFAULT_DB_DIR

    def test_module_default_is_the_claude_learning_dir(self):
        """That default is ~/.claude/learning.

        Asserted against the source, not the live constant: the repo-wide
        conftest fixture repoints the constant at a tmp dir so that no test can
        reach production data.
        """
        source = (HOOKS_DIR / "lib" / "learning_db_v2.py").read_text()
        assert '_DEFAULT_DB_DIR = Path.home() / ".claude" / "learning"' in source

    def test_graduation_proposer_uses_get_db_dir(self):
        """knowledge-graduation-proposer.py must import get_db_dir, not
        inline the path logic.
        """
        source = (HOOKS_DIR / "knowledge-graduation-proposer.py").read_text()
        assert "get_db_dir" in source, "graduation-proposer does not use get_db_dir"
        # Must NOT contain the inline path pattern
        assert 'Path.home() / ".claude" / "learning"' not in source

    def test_retro_gate_uses_get_db_dir(self):
        source = (HOOKS_DIR / "retro-graduation-gate.py").read_text()
        assert "get_db_dir" in source, "retro-graduation-gate does not use get_db_dir"
        assert 'Path.home() / ".claude" / "learning"' not in source

    def test_route_signal_uses_get_db_dir(self):
        source = (REPO_ROOT / "scripts" / "route-signal-check.py").read_text()
        assert "get_db_dir" in source, "route-signal-check does not use get_db_dir"
        assert 'Path.home() / ".claude" / "learning"' not in source

    def test_routing_manifest_uses_get_db_dir(self):
        source = (REPO_ROOT / "scripts" / "routing-manifest.py").read_text()
        assert "get_db_dir" in source, "routing-manifest does not use get_db_dir"
        assert 'Path.home() / ".claude" / "learning"' not in source
