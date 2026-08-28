#!/usr/bin/env python3
"""Tests for the shared learning-DB storage layer and routing-outcome telemetry.

Formerly test_learning_loop_fixes.py. The learning loop was retired; the
classes that covered its deleted hooks went with it. What remains covers
subsystems that survive on top of learning_db_v2: the context sanitizers,
routing-outcome finalization (next-turn finalizer plus the Stop fallback),
and the shared get_db_dir() path resolver.
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


# ===========================================================================
# Context sanitizers (learning_db_v2, consumed by session-context.py)
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
# Routing-outcome finalization: every pending dispatch reaches a terminal state
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
            "routing_outcome_stop_fallback",
            str(HOOKS_DIR / "routing-outcome-stop-fallback.py"),
        )
        stop_fallback = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stop_fallback)
        stop_fallback.finalize_routing_outcomes(session_id)

        # After Stop: pending must be empty
        remaining = peek_pending_outcomes(session_id)
        assert len(remaining) == 0, f"Stop left {len(remaining)} pending outcomes unresolved"

        # T4 deterministic floor: a CLEAN autonomous run carries no acceptance
        # evidence, so resolving it must be a no-op -- never a boost.
        from routing_outcome_score import _current_confidence

        conf = _current_confidence("test-agent:test-skill")
        assert conf == 0.5, f"clean Stop run must not change confidence, got {conf}"

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
            "routing_outcome_stop_fallback",
            str(HOOKS_DIR / "routing-outcome-stop-fallback.py"),
        )
        stop_fallback = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stop_fallback)
        stop_fallback.finalize_routing_outcomes(session_id)

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
# Shared DB-path resolution: get_db_dir() is the single exported path source
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

    def test_route_signal_uses_get_db_dir(self):
        source = (REPO_ROOT / "scripts" / "route-signal-check.py").read_text()
        assert "get_db_dir" in source, "route-signal-check does not use get_db_dir"
        assert 'Path.home() / ".claude" / "learning"' not in source

    def test_routing_manifest_uses_get_db_dir(self):
        source = (REPO_ROOT / "scripts" / "routing-manifest.py").read_text()
        assert "get_db_dir" in source, "routing-manifest does not use get_db_dir"
        assert 'Path.home() / ".claude" / "learning"' not in source
