#!/usr/bin/env python3
"""Tests for the shared learning-injection confidence floor.

The floor must sit strictly below the birth confidence of every injectable
category. Confidence rises only for learnings that get injected, so a floor at
or above birth confidence is a one-way ratchet: a new learning never injects,
so it never gets boosted, so it never crosses the floor -- while decay pulls it
further down. That ratchet starved the injectable pool (activations fell from
9,755 rows in one month to 1 in the next).

Covers:
- the floor sits strictly below the lowest injectable birth confidence;
- neither injector hardcodes its own floor literal;
- both injectors return a learning seeded at the error birth confidence.

Run with: python3 -m pytest hooks/tests/test_injection_floor.py -v
"""

import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import learning_db_v2 as db

_HOOKS_DIR = Path(__file__).resolve().parent.parent
PRETOOL_PATH = _HOOKS_DIR / "pretool-learning-injector.py"
SESSION_CONTEXT_PATH = _HOOKS_DIR / "session-context.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pretool = _load("pretool_learning_injector", PRETOOL_PATH)
session_context = _load("session_context", SESSION_CONTEXT_PATH)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Use a fresh temp learning.db for each test -- never the real one."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    db._initialized = False
    yield tmp_path
    db._initialized = False


def _additional_context(output: str) -> str:
    if not output.strip():
        return ""
    parsed = json.loads(output.strip())
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "") or ""


# ---------------------------------------------------------------------------
# The invariant
# ---------------------------------------------------------------------------


class TestFloorInvariant:
    def test_floor_sits_below_every_injectable_birth_confidence(self):
        """The bug that starved the pool. Keep this assertion strict."""
        # session-context injects category "error"; the pretool injector adds
        # the rest of its allowlist.
        injectable = set(pretool.INJECTABLE_CATEGORIES) | {"error"}
        lowest_birth = min(db.CATEGORY_DEFAULTS[c] for c in injectable)
        assert lowest_birth > db.INJECTION_MIN_CONFIDENCE, (
            f"injection floor {db.INJECTION_MIN_CONFIDENCE} is not below the lowest "
            f"injectable birth confidence {lowest_birth}; newly captured learnings "
            "can never enter the loop that would raise them"
        )

    def test_every_injectable_category_has_a_birth_confidence(self):
        for category in set(pretool.INJECTABLE_CATEGORIES) | {"error"}:
            assert category in db.CATEGORY_DEFAULTS

    @pytest.mark.parametrize("path", [PRETOOL_PATH, SESSION_CONTEXT_PATH])
    def test_injector_does_not_hardcode_a_floor(self, path):
        """Both injectors must read the shared constant, not a local literal."""
        source = path.read_text()
        hardcoded = re.search(r"min_confidence\s*=\s*[0-9]", source, re.IGNORECASE)
        assert hardcoded is None, f"{path.name} hardcodes a confidence floor: {hardcoded.group(0)!r}"
        assert "INJECTION_MIN_CONFIDENCE" in source


# ---------------------------------------------------------------------------
# Both injectors surface a learning born at the error default
# ---------------------------------------------------------------------------


class TestInjectorsSeeBirthConfidenceLearnings:
    def test_pretool_injector_returns_hint_for_birth_confidence_learning(self, tmp_path):
        db.record_learning(
            topic="import_error",
            key="pytest-missing-plugin",
            value="pytest fails on a missing plugin -> pip install the plugin first",
            category="error",
            confidence=db.CATEGORY_DEFAULTS["error"],
            tags=["python", "pytest"],
            source="hook:error-learner",
            project_path=str(tmp_path),
        )

        event = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest hooks/tests"},
                "cwd": str(tmp_path),
            }
        )
        stdout = io.StringIO()
        with (
            patch.object(pretool, "read_stdin", return_value=event),
            patch("sys.stdout", stdout),
        ):
            try:
                pretool.main()
            except SystemExit:
                pass

        context = _additional_context(stdout.getvalue())
        assert "learning-hint" in context
        assert "pip install the plugin" in context

    def test_session_context_returns_birth_confidence_learning(self, tmp_path, monkeypatch):
        project = tmp_path / "project"
        project.mkdir()
        db.record_learning(
            topic="missing_file",
            key="config-not-found",
            value="config.yaml missing -> create it from config.yaml.example",
            category="error",
            confidence=db.CATEGORY_DEFAULTS["error"],
            source="hook:error-learner",
            project_path=str(project),
        )

        monkeypatch.chdir(project)
        stdout = io.StringIO()
        with (
            patch.object(session_context, "inject_dream_payload", return_value=""),
            patch.object(session_context, "surface_dream_report", return_value=""),
            patch("sys.stdout", stdout),
        ):
            try:
                session_context.main()
            except SystemExit:
                pass

        context = _additional_context(stdout.getvalue())
        assert "[learned-context] Loaded 1 high-confidence patterns" in context

    def test_session_context_activation_is_recorded(self, tmp_path, monkeypatch):
        """Injection must land a row in activations -- the ROI signal that went to zero."""
        project = tmp_path / "project"
        project.mkdir()
        db.record_learning(
            topic="permissions",
            key="denied-on-write",
            value="permission denied -> check the directory mode before writing",
            category="error",
            confidence=db.CATEGORY_DEFAULTS["error"],
            source="hook:error-learner",
            project_path=str(project),
        )

        monkeypatch.chdir(project)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        stdout = io.StringIO()
        with (
            patch.object(session_context, "inject_dream_payload", return_value=""),
            patch.object(session_context, "surface_dream_report", return_value=""),
            patch("sys.stdout", stdout),
        ):
            try:
                session_context.main()
            except SystemExit:
                pass

        with db.get_connection() as conn:
            rows = conn.execute("SELECT topic, key FROM activations").fetchall()
        assert [(r["topic"], r["key"]) for r in rows] == [("permissions", "denied-on-write")]


# ---------------------------------------------------------------------------
# Non-blocking contract
# ---------------------------------------------------------------------------


class TestNonBlocking:
    @pytest.mark.parametrize("hook", [PRETOOL_PATH, SESSION_CONTEXT_PATH])
    def test_hook_exits_zero_on_empty_stdin(self, hook, tmp_path):
        import subprocess

        env = dict(os.environ, CLAUDE_LEARNING_DIR=str(tmp_path))
        result = subprocess.run(
            [sys.executable, str(hook)],
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
