#!/usr/bin/env python3
"""
Tests for the codex-auto-review UserPromptSubmit hook.

Run with: python3 -m pytest scripts/tests/test_codex_auto_review_hook.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).resolve().parent.parent.parent / "hooks" / "codex-auto-review.py"

spec = importlib.util.spec_from_file_location("codex_auto_review", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook subprocess with a JSON event on stdin."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.stderr, result.returncode


def make_event(prompt: str) -> dict:
    """Build a minimal UserPromptSubmit event."""
    return {
        "tool_name": "UserPromptSubmit",
        "tool_input": {"prompt": prompt},
    }


def parse_hook_output(stdout: str) -> dict:
    """Parse hook stdout as JSON, return {} on empty/invalid."""
    if not stdout.strip():
        return {}
    return json.loads(stdout)


# ---------------------------------------------------------------------------
# Detection logic unit tests (fast, no subprocess)
# ---------------------------------------------------------------------------


class TestIsReviewRequest:
    """Unit tests for is_review_request() detection logic."""

    def test_non_review_prompt_not_detected(self):
        assert not mod.is_review_request("fix the bug in main.py")

    def test_review_my_changes_detected(self):
        assert mod.is_review_request("review my changes")

    def test_code_review_detected(self):
        assert mod.is_review_request("can you do a code review")

    def test_review_the_pr_detected(self):
        assert mod.is_review_request("review the pr")

    def test_review_this_pr_detected(self):
        assert mod.is_review_request("review this pr")

    def test_pr_review_detected(self):
        assert mod.is_review_request("pr review please")

    def test_systematic_code_review_skill_detected(self):
        assert mod.is_review_request("/systematic-code-review")

    def test_parallel_code_review_skill_detected(self):
        assert mod.is_review_request("/parallel-code-review")

    def test_full_repo_review_skill_detected(self):
        assert mod.is_review_request("/full-repo-review")

    def test_pr_review_skill_detected(self):
        assert mod.is_review_request("/pr-review")

    def test_case_insensitive(self):
        assert mod.is_review_request("CODE REVIEW please")

    def test_skill_with_args_detected(self):
        assert mod.is_review_request("/systematic-code-review --depth=full")


class TestIsAlreadyHandled:
    """Unit tests for is_already_handled() exclusion logic."""

    def test_pr_workflow_excluded(self):
        assert mod.is_already_handled("/pr-workflow push")

    def test_pr_workflow_codex_review_excluded(self):
        assert mod.is_already_handled("/pr-workflow codex-review")

    def test_regular_review_not_excluded(self):
        assert not mod.is_already_handled("/systematic-code-review")

    def test_review_phrase_not_excluded(self):
        assert not mod.is_already_handled("review my changes")

    def test_unrelated_not_excluded(self):
        assert not mod.is_already_handled("fix the tests")

    def test_pr_workflow_case_insensitive(self):
        assert mod.is_already_handled("/PR-WORKFLOW")


# ---------------------------------------------------------------------------
# Integration tests via subprocess
# ---------------------------------------------------------------------------


class TestNonReviewPrompt:
    """Non-review prompts should produce empty output."""

    def test_fix_bug_returns_empty(self):
        stdout, stderr, code = run_hook(make_event("fix the bug in main.py"))
        assert code == 0
        output = parse_hook_output(stdout)
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" not in hook_out

    def test_write_tests_returns_empty(self):
        stdout, stderr, code = run_hook(make_event("write unit tests for auth.py"))
        assert code == 0
        output = parse_hook_output(stdout)
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" not in hook_out


class TestReviewPromptWithCodexInstalled:
    """Review prompts when codex is installed should inject context."""

    def _run_with_codex(self, prompt: str) -> dict:
        """Run hook with mocked codex availability."""
        with patch.object(mod, "codex_is_available", return_value=True):
            event = make_event(prompt)
            # Run inline via the module's main logic to use our mock
            # We need to test via subprocess with env trick or via direct import
            # Use direct module invocation path
            import io
            from contextlib import redirect_stdout

            sys_stdin_backup = sys.stdin
            sys.stdin = io.StringIO(json.dumps(event))
            captured = io.StringIO()

            try:
                with redirect_stdout(captured):
                    try:
                        mod.main()
                    except SystemExit:
                        pass
            finally:
                sys.stdin = sys_stdin_backup

            output_text = captured.getvalue()
            if not output_text.strip():
                return {}
            return json.loads(output_text)

    def test_review_my_changes_injects_context(self):
        output = self._run_with_codex("review my changes")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" in hook_out
        assert "codex-auto-review" in hook_out["additionalContext"]
        assert "pr-workflow" in hook_out["additionalContext"]

    def test_systematic_code_review_skill_injects_context(self):
        output = self._run_with_codex("/systematic-code-review")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" in hook_out

    def test_pr_review_skill_injects_context(self):
        output = self._run_with_codex("/pr-review")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" in hook_out

    def test_code_review_phrase_injects_context(self):
        output = self._run_with_codex("do a code review of the auth module")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" in hook_out

    def test_injection_mentions_skill_not_raw_command(self):
        """Injection should tell Claude to invoke the skill, not run codex directly."""
        output = self._run_with_codex("review my changes")
        hook_out = output.get("hookSpecificOutput", {})
        context = hook_out.get("additionalContext", "")
        assert "Call the Skill tool with `pr-workflow`." in context
        # Should NOT contain a raw shell command
        assert "codex run" not in context
        assert "$ codex" not in context


class TestDirectCodexInvocation:
    """Prompts that already invoke pr-workflow should NOT inject."""

    def _run_with_codex(self, prompt: str) -> dict:
        with patch.object(mod, "codex_is_available", return_value=True):
            import io
            from contextlib import redirect_stdout

            sys_stdin_backup = sys.stdin
            sys.stdin = io.StringIO(json.dumps(make_event(prompt)))
            captured = io.StringIO()

            try:
                with redirect_stdout(captured):
                    try:
                        mod.main()
                    except SystemExit:
                        pass
            finally:
                sys.stdin = sys_stdin_backup

            output_text = captured.getvalue()
            if not output_text.strip():
                return {}
            return json.loads(output_text)

    def test_pr_workflow_not_injected(self):
        output = self._run_with_codex("/pr-workflow push")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" not in hook_out

    def test_pr_workflow_codex_review_not_injected(self):
        output = self._run_with_codex("/pr-workflow codex-review")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" not in hook_out


class TestCodexNotInstalled:
    """When codex is not installed, even review prompts should produce empty output."""

    def _run_without_codex(self, prompt: str) -> dict:
        with patch.object(mod, "codex_is_available", return_value=False):
            import io
            from contextlib import redirect_stdout

            sys_stdin_backup = sys.stdin
            sys.stdin = io.StringIO(json.dumps(make_event(prompt)))
            captured = io.StringIO()

            try:
                with redirect_stdout(captured):
                    try:
                        mod.main()
                    except SystemExit:
                        pass
            finally:
                sys.stdin = sys_stdin_backup

            output_text = captured.getvalue()
            if not output_text.strip():
                return {}
            return json.loads(output_text)

    def test_review_prompt_no_injection_when_codex_missing(self):
        output = self._run_without_codex("review my changes")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" not in hook_out

    def test_skill_invocation_no_injection_when_codex_missing(self):
        output = self._run_without_codex("/systematic-code-review")
        hook_out = output.get("hookSpecificOutput", {})
        assert "additionalContext" not in hook_out


# ---------------------------------------------------------------------------
# Non-blocking guarantee
# ---------------------------------------------------------------------------


class TestNonBlocking:
    """Hook must always exit 0 regardless of errors."""

    def test_exits_zero_on_empty_input(self):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_malformed_json(self):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json{{{",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_missing_tool_input(self):
        event = {"tool_name": "UserPromptSubmit"}
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_empty_prompt(self):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(make_event("")),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
