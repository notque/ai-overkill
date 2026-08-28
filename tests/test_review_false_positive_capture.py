#!/usr/bin/env python3
"""Tests for the review false-positive capture hook and learning-db surface.

Covers:
- Hook pattern matching (FP_PATTERNS fire on review disputes)
- Hook silent exit on non-matching prompts
- Hook exit 0 on malformed/empty input
- Reviewer and source-file extraction from prompt text
- learning-db record-review-fp subcommand
- learning-db review-fps subcommand (grouping by reviewer)
"""

from __future__ import annotations

import importlib.util
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
SCRIPTS_DIR = REPO_ROOT / "scripts"

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
        import learning_db_v2

        learning_db_v2._initialized = False
        yield db_dir
        learning_db_v2._initialized = False


def _run_hook(event: dict, env_override: dict | None = None) -> subprocess.CompletedProcess:
    """Run the review-false-positive-capture hook as a subprocess."""
    env = {**os.environ, **(env_override or {})}
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / "review-false-positive-capture.py")],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _load_hook_module():
    """Load the hook as a module for direct function testing."""
    spec = importlib.util.spec_from_file_location(
        "review_false_positive_capture",
        HOOKS_DIR / "review-false-positive-capture.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Hook: Pattern Matching
# ---------------------------------------------------------------------------


class TestFPPatternMatching:
    """Hook detects review-dispute patterns in user prompts."""

    @pytest.mark.parametrize(
        "prompt",
        [
            "that's a false positive",
            "This is a false positive from the review",
            "that finding is wrong",
            "that finding is incorrect",
            "reviewer was wrong about this",
            "the reviewer is wrong here",
            "disagree with the review on this point",
            "that's not a bug, it's intended",
            "that's not an issue",
            "not actually a bug",
            "not a real issue",
            "review finding about imports doesn't apply here",
        ],
    )
    def test_matching_prompts_record_learning(self, prompt, tmp_learning_dir):
        """Each FP pattern triggers a learning record."""
        result = _run_hook(
            {"prompt": prompt, "cwd": "/tmp", "session_id": "test-fp"},
            {"CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
        )
        assert result.returncode == 0
        assert "[review-fp] captured" in result.stderr

    @pytest.mark.parametrize(
        "prompt",
        [
            "please fix the bug in main.py",
            "run the tests",
            "what does this function do?",
            "review this code for me",
            "the code looks good",
            "",
        ],
    )
    def test_non_matching_prompts_silent(self, prompt, tmp_learning_dir):
        """Non-dispute prompts produce no capture output."""
        result = _run_hook(
            {"prompt": prompt, "cwd": "/tmp", "session_id": "test-fp"},
            {"CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
        )
        assert result.returncode == 0
        assert "[review-fp] captured" not in result.stderr


# ---------------------------------------------------------------------------
# Hook: Reviewer and Source Extraction
# ---------------------------------------------------------------------------


class TestExtraction:
    """Best-effort extraction of reviewer agent and source file."""

    def test_extract_reviewer_known_agent(self):
        mod = _load_hook_module()
        assert mod.extract_reviewer("the reviewer-code was wrong") == "reviewer-code"
        assert mod.extract_reviewer("reviewer-system flagged this") == "reviewer-system"

    def test_extract_reviewer_unknown(self):
        mod = _load_hook_module()
        assert mod.extract_reviewer("that finding is wrong") == "unknown"

    def test_extract_source_file(self):
        mod = _load_hook_module()
        assert mod.extract_source_file("the issue in main.py is fine") == "main.py"
        assert mod.extract_source_file("handler.go error handling") == "handler.go"
        assert mod.extract_source_file("hooks/lib/utils.py import") == "hooks/lib/utils.py"

    def test_extract_source_file_unknown(self):
        mod = _load_hook_module()
        assert mod.extract_source_file("that's wrong") == "unknown"


# ---------------------------------------------------------------------------
# Hook: Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Hook always exits 0, even on bad input."""

    def test_empty_stdin_exits_0(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "review-false-positive-capture.py")],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    @pytest.mark.parametrize("payload", ["", "   ", "\n"])
    def test_empty_stdin_logs_no_error(self, payload, isolate_hook_error_log):
        """Empty stdin is an expected input, not a hook failure.

        read_stdin returns "" on a closed pipe or its 2s timeout, and the hook
        used to hand that straight to json.loads. The resulting JSONDecodeError
        was logged to hook-errors.jsonl on every such invocation.
        """
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "review-false-positive-capture.py")],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "HOOK-ERROR" not in result.stderr
        assert not isolate_hook_error_log.exists(), isolate_hook_error_log.read_text()

    def test_non_object_json_logs_no_error(self, isolate_hook_error_log):
        """A bare JSON scalar carries no prompt; treat it as nothing to do."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "review-false-positive-capture.py")],
            input='"just a string"',
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "HOOK-ERROR" not in result.stderr
        assert not isolate_hook_error_log.exists()

    def test_valid_input_still_captures_after_the_empty_guard(self, tmp_learning_dir):
        """The empty-input guard must not short-circuit a real capture."""
        result = _run_hook(
            {
                "prompt": "that is a false positive, reviewer-code was wrong about hooks/foo.py",
                "cwd": "/tmp",
                "session_id": "guard-test",
            },
            {"CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
        )

        assert result.returncode == 0
        assert "[review-fp] captured:" in result.stderr

    def test_malformed_json_exits_0(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "review-false-positive-capture.py")],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_missing_prompt_field_exits_0(self, tmp_learning_dir):
        result = _run_hook(
            {"cwd": "/tmp"},
            {"CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Hook: Learning DB Integration
# ---------------------------------------------------------------------------


class TestLearningDBIntegration:
    """Hook records to learning.db with correct schema."""

    def test_records_with_correct_topic_and_category(self, tmp_learning_dir):
        import learning_db_v2

        learning_db_v2.init_db()

        _run_hook(
            {
                "prompt": "false positive from reviewer-code about utils.py",
                "cwd": "/tmp/project",
                "session_id": "test-integration",
            },
            {"CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
        )

        results = learning_db_v2.query_learnings(
            topic="review-false-positive",
            category="review",
        )
        assert len(results) >= 1
        entry = results[0]
        assert entry["topic"] == "review-false-positive"
        assert entry["category"] == "review"
        assert "reviewer-code" in entry["value"]
        assert "utils.py" in entry["value"]
        assert "false-positive" in entry["tags"]
        assert "reviewer-code" in entry["tags"]


# ---------------------------------------------------------------------------
# CLI: record-review-fp
# ---------------------------------------------------------------------------


class TestRecordReviewFPCLI:
    """The record-review-fp subcommand records structured FPs."""

    def test_records_structured_fp(self, tmp_learning_dir):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "learning-db.py"),
                "record-review-fp",
                "--reviewer",
                "reviewer-code",
                "--finding",
                "unused import os",
                "--reason",
                "used in test via conftest",
                "--source-file",
                "main.py",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
            timeout=10,
        )
        assert result.returncode == 0
        assert "Recorded" in result.stdout
        assert "reviewer-code" in result.stdout

    def test_requires_reviewer_finding_reason(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "learning-db.py"),
                "record-review-fp",
                "--reviewer",
                "reviewer-code",
                # Missing --finding and --reason
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# CLI: review-fps
# ---------------------------------------------------------------------------


class TestReviewFPsCLI:
    """The review-fps subcommand lists FPs grouped by reviewer."""

    def test_empty_db_shows_no_fps(self, tmp_learning_dir):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "learning-db.py"),
                "review-fps",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
            timeout=10,
        )
        assert result.returncode == 0
        assert "No review false positives" in result.stdout

    def test_groups_by_reviewer(self, tmp_learning_dir):
        import learning_db_v2

        learning_db_v2.init_db()

        # Seed two FPs from different reviewers
        learning_db_v2.record_learning(
            topic="review-false-positive",
            key="fp-1",
            value="finding: unused var | reviewer: reviewer-code | reason: used later | source: a.py",
            category="review",
            confidence=0.70,
            tags=["false-positive", "reviewer-code"],
            source="cli:record-review-fp",
        )
        learning_db_v2.record_learning(
            topic="review-false-positive",
            key="fp-2",
            value="finding: missing lock | reviewer: reviewer-system | reason: single-threaded | source: b.go",
            category="review",
            confidence=0.70,
            tags=["false-positive", "reviewer-system"],
            source="cli:record-review-fp",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "learning-db.py"),
                "review-fps",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
            timeout=10,
        )
        assert result.returncode == 0
        assert "reviewer-code" in result.stdout
        assert "reviewer-system" in result.stdout
        assert "1 false positive(s)" in result.stdout

    def test_json_output(self, tmp_learning_dir):
        import learning_db_v2

        learning_db_v2.init_db()

        learning_db_v2.record_learning(
            topic="review-false-positive",
            key="fp-json",
            value="finding: bad pattern | reviewer: reviewer-domain | reason: intentional | source: c.ts",
            category="review",
            confidence=0.70,
            tags=["false-positive", "reviewer-domain"],
            source="cli:record-review-fp",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "learning-db.py"),
                "review-fps",
                "--json",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_learning_dir)},
            timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "reviewer-domain" in data
        assert len(data["reviewer-domain"]) == 1
