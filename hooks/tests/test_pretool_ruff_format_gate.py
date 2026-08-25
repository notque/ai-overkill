#!/usr/bin/env python3
"""
Tests for the pretool-ruff-format-gate hook.

Run with: python3 -m pytest hooks/tests/test_pretool_ruff_format_gate.py -v
"""

import importlib.util
import io
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-ruff-format-gate.py"

spec = importlib.util.spec_from_file_location("pretool_ruff_format_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bash_event(command: str, cwd: str | None = None) -> str:
    event = {"tool_input": {"command": command}}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _run_main(stdin_payload: str, env: dict | None = None) -> tuple[int, dict | None]:
    """Invoke mod.main() in-process.

    Returns (logical_exit_code, parsed_stdout_json).
    logical_exit_code is 2 if permissionDecision:deny was emitted, 0 otherwise.
    """
    base_env = dict(os.environ)
    base_env.pop("RUFF_FORMAT_GATE_BYPASS", None)
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    parsed = None
    if output:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            pass

    if parsed:
        hook_out = parsed.get("hookSpecificOutput", {})
        if hook_out.get("permissionDecision") == "deny":
            return 2, parsed
    return 0, parsed


# ---------------------------------------------------------------------------
# Non-push commands pass through
# ---------------------------------------------------------------------------


class TestNonPushCommandsPassThrough:
    def test_git_status_allowed(self):
        code, _ = _run_main(_make_bash_event("git status"))
        assert code == 0

    def test_git_commit_allowed(self):
        code, _ = _run_main(_make_bash_event("git commit -m 'feat: something'"))
        assert code == 0

    def test_git_fetch_allowed(self):
        code, _ = _run_main(_make_bash_event("git fetch origin"))
        assert code == 0

    def test_empty_command_allowed(self):
        code, _ = _run_main(_make_bash_event(""))
        assert code == 0

    def test_non_git_command_allowed(self):
        code, _ = _run_main(_make_bash_event("echo 'hello'"))
        assert code == 0

    def test_search_argument_mentioning_git_push_is_not_a_push(self):
        code, _ = _run_main(_make_bash_event("rg -n 'git push' docs/"))
        assert code == 0


class TestPushShellParsing:
    def test_wrappers_and_grouping_cannot_bypass(self, tmp_path):
        for command in (
            "command git push",
            "env FOO=1 git push",
            "(git push)",
            "{ git push; }",
            "echo $(git push)",
        ):
            assert mod._push_cwd(command, str(tmp_path)) == tmp_path

    def test_push_segment_owns_cwd(self, tmp_path):
        a = tmp_path / "A"
        b = tmp_path / "B"
        assert mod._push_cwd("echo ok && cd B && git push", str(tmp_path)) == b
        assert mod._push_cwd("cd 'B' && git push", str(tmp_path)) == b
        assert mod._push_cwd("git -C A status && git -C B push", str(tmp_path)) == b

    def test_wrapped_pushes_still_block_changed_malformed_python(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        failed = type("R", (), {"returncode": 1, "stdout": "Would reformat: bad.py\n", "stderr": ""})()
        for command in (
            "command git push",
            "env FOO=1 git push",
            "(git push)",
            "{ git push; }",
            "echo $(git push)",
        ):
            with (
                patch.object(mod, "_changed_python_files", return_value=[Path("bad.py")]),
                patch("subprocess.run", return_value=failed),
            ):
                code, _ = _run_main(_make_bash_event(command, cwd=str(tmp_path)))
            assert code == 2, command

    def test_standard_wrapper_and_git_global_options_cannot_bypass(self, tmp_path):
        commands = (
            "git -c color.ui=false push",
            "git --git-dir .git push",
            "command -p git push",
            "command -- git push",
        )
        for command in commands:
            assert mod._push_cwds(command, str(tmp_path)) == [tmp_path], command

    def test_multiple_pushes_return_every_context(self, tmp_path):
        assert mod._push_cwds("git -C cleanA push; git -C malformedB push", str(tmp_path)) == [
            tmp_path / "cleanA",
            tmp_path / "malformedB",
        ]

    def test_later_malformed_push_blocks_after_clean_first_push(self, tmp_path):
        clean = tmp_path / "cleanA"
        malformed = tmp_path / "malformedB"
        for repo in (clean, malformed):
            repo.mkdir()
            (repo / "pyproject.toml").write_text("[tool.ruff]\n")
        failed = type("R", (), {"returncode": 1, "stdout": "Would reformat: bad.py\n", "stderr": ""})()

        def changed(root):
            return [] if root == clean else [Path("bad.py")]

        with (
            patch.object(mod, "_changed_python_files", side_effect=changed) as discovery,
            patch("subprocess.run", return_value=failed),
        ):
            code, _ = _run_main(_make_bash_event("git -C cleanA push; git -C malformedB push", cwd=str(tmp_path)))

        assert code == 2
        assert [call.args[0] for call in discovery.call_args_list] == [clean, malformed]

    def test_subshell_cd_does_not_leak(self, tmp_path):
        assert mod._push_cwds("(cd cleanA); git push", str(tmp_path)) == [tmp_path]


# ---------------------------------------------------------------------------
# No pyproject.toml — pass through
# ---------------------------------------------------------------------------


class TestNoRuffConfig:
    def test_no_pyproject_passes_through(self, tmp_path):
        """No pyproject.toml means the gate is dormant (non-Python project)."""
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))
        code, _ = _run_main(payload)
        assert code == 0

    def test_pyproject_without_ruff_section_passes_through(self, tmp_path):
        """pyproject.toml without [tool.ruff] is treated as non-Python project."""
        (tmp_path / "pyproject.toml").write_text("[build-system]\nrequires = []\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))
        code, _ = _run_main(payload)
        assert code == 0


# ---------------------------------------------------------------------------
# Bypass env var
# ---------------------------------------------------------------------------


class TestBypassEnv:
    def test_bypass_allows_push_through(self, tmp_path):
        """RUFF_FORMAT_GATE_BYPASS=1 skips the check entirely."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))
        code, _ = _run_main(payload, env={"RUFF_FORMAT_GATE_BYPASS": "1"})
        assert code == 0


# ---------------------------------------------------------------------------
# Ruff check outcomes
# ---------------------------------------------------------------------------


class TestRuffCheckOutcomes:
    def test_only_changed_python_files_are_formatted(self, tmp_path):
        """The formatter receives explicit changed Python paths, never the repository dot."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin feature", cwd=str(tmp_path))
        changed = [Path("src/changed.py"), Path("types/changed.pyi")]

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with (
            patch.object(mod, "_changed_python_files", return_value=changed),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            code, _ = _run_main(payload)

        assert code == 0
        ruff_call = mock_run.call_args_list[-1]
        assert ruff_call.args[0] == [
            "ruff",
            "format",
            "--check",
            "src/changed.py",
            "types/changed.pyi",
            "--config",
            "pyproject.toml",
        ]
        assert "." not in ruff_call.args[0]

    def test_no_changed_python_files_allows_clean_feature_push(self, tmp_path):
        """A feature push with no changed Python must not invoke Ruff at all."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin feature", cwd=str(tmp_path))

        with (
            patch.object(mod, "_changed_python_files", return_value=[]),
            patch("subprocess.run") as mock_run,
        ):
            code, _ = _run_main(payload)

        assert code == 0
        mock_run.assert_not_called()

    def test_unrelated_dirty_markdown_is_ignored(self, tmp_path):
        """Fenced Python in Markdown can never be passed to Ruff."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        (tmp_path / "notes.md").write_text("```python\nx={'bad':1}\n```\n")
        payload = _make_bash_event("git push origin feature", cwd=str(tmp_path))

        with (
            patch.object(mod, "_changed_python_files", return_value=[]),
            patch("subprocess.run") as mock_run,
        ):
            code, _ = _run_main(payload)

        assert code == 0
        mock_run.assert_not_called()

    def test_ruff_check_passes_allows_push(self, tmp_path):
        """When ruff format --check exits 0, the push is allowed."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with (
            patch.object(mod, "_changed_python_files", return_value=[Path("foo.py")]),
            patch("subprocess.run", return_value=mock_result),
        ):
            code, _ = _run_main(payload)
        assert code == 0

    def test_ruff_check_fails_blocks_push(self, tmp_path):
        """When ruff format --check exits non-zero, the push is blocked."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        mock_result = type("R", (), {"returncode": 1, "stdout": "Would reformat: foo.py\n", "stderr": ""})()
        with (
            patch.object(mod, "_changed_python_files", return_value=[Path("src/app.py")]),
            patch("subprocess.run", return_value=mock_result),
        ):
            code, parsed = _run_main(payload)
        assert code == 2
        assert parsed is not None
        hook_out = parsed["hookSpecificOutput"]
        assert hook_out["permissionDecision"] == "deny"
        assert "ruff format" in hook_out["permissionDecisionReason"]

    def test_ruff_not_installed_allows_push(self, tmp_path):
        """FileNotFoundError (ruff not installed) fails open — push allowed."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        with patch("subprocess.run", side_effect=FileNotFoundError("ruff not found")):
            code, _ = _run_main(payload)
        assert code == 0

    def test_ruff_timeout_allows_push(self, tmp_path):
        """Timeout in ruff invocation fails open — push allowed."""
        import subprocess

        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["ruff"], 15)):
            code, _ = _run_main(payload)
        assert code == 0

    def test_deny_reason_includes_ruff_output(self, tmp_path):
        """Ruff violation output is included in the deny reason for visibility."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        violation_msg = "Would reformat: src/app.py\n1 file would be reformatted"
        mock_result = type("R", (), {"returncode": 1, "stdout": violation_msg, "stderr": ""})()
        with (
            patch.object(mod, "_changed_python_files", return_value=[Path("src/app.py")]),
            patch("subprocess.run", return_value=mock_result),
        ):
            code, parsed = _run_main(payload)
        assert code == 2
        reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
        assert "ruff output" in reason
        assert "src/app.py" in reason


# ---------------------------------------------------------------------------
# CWD extraction
# ---------------------------------------------------------------------------


class TestCwdExtraction:
    def test_cd_prefix_extracts_cwd(self, tmp_path):
        """cd /path && git push correctly uses /path as project root."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        command = f"cd {tmp_path} && git push origin main"
        payload = _make_bash_event(command)

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            code, _ = _run_main(payload)
        assert code == 0
        # Verify ruff was invoked in the extracted directory
        if mock_run.called:
            call_kwargs = mock_run.call_args
            assert str(tmp_path) in str(call_kwargs)

    def test_git_C_flag_extracts_cwd(self, tmp_path):
        """git -C /path push correctly uses /path as project root."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        command = f"git -C {tmp_path} push origin main"
        payload = _make_bash_event(command)

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            code, _ = _run_main(payload)
        assert code == 0

    def test_relative_cd_resolves_from_event_cwd(self, tmp_path):
        """A relative cd prefix is resolved against the Bash event's actual cwd."""
        worktree = tmp_path / "trees" / "feature"
        worktree.mkdir(parents=True)
        (worktree / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("cd trees/feature && git push origin feature", cwd=str(tmp_path))

        with patch.object(mod, "_changed_python_files", return_value=[]) as changed:
            code, _ = _run_main(payload)

        assert code == 0
        changed.assert_called_once_with(worktree)


class TestChangedPythonDiscovery:
    def test_changed_malformed_python_is_selected_but_markdown_is_not(self, tmp_path):
        """Discovery fail-closes on changed Python while excluding every non-Python path."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "bad.py").write_text("x={'bad':1}\n")
        (tmp_path / "src" / "types.pyi").write_text("x:int\n")
        files = "src/bad.py\0docs/example.md\0src/types.pyi\0assets/app.js\0"
        result = type("R", (), {"returncode": 0, "stdout": files, "stderr": ""})()

        with patch("subprocess.run", return_value=result):
            selected = mod._changed_python_files(tmp_path)

        assert selected == [Path("src/bad.py"), Path("src/types.pyi")]

    def test_empty_integration_diff_does_not_fall_back_to_stale_history(self, tmp_path):
        """A valid empty origin/dev comparison is final, not a reason to try HEAD^."""
        calls = []

        def fake_paths(_root, args):
            calls.append(args)
            if args[:2] == ["merge-base", "HEAD"] and args[-1] == "origin/dev":
                return ["base-sha"]
            if args[:2] == ["diff", "--name-only"]:
                return []
            return []

        with patch.object(mod, "_git_paths", side_effect=fake_paths):
            assert mod._changed_python_files(tmp_path) == []

        assert not any("HEAD^...HEAD" in arg for call in calls for arg in call)


class TestEndToEndWorktreeScope:
    @staticmethod
    def _init_repo(path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "hook@example.test"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Hook Test"], cwd=path, check=True)
        (path / "pyproject.toml").write_text("[tool.ruff]\n")
        (path / "baseline.py").write_text("BASELINE = 1\n")
        subprocess.run(["git", "add", "."], cwd=path, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=path, check=True)

    def test_real_changed_malformed_python_is_blocked(self, tmp_path):
        self._init_repo(tmp_path)
        (tmp_path / "changed.py").write_text("result={'bad':1}\n")

        code, parsed = _run_main(_make_bash_event("git push origin feature", cwd=str(tmp_path)))

        assert code == 2
        assert "changed.py" in parsed["hookSpecificOutput"]["permissionDecisionReason"]

    def test_real_dirty_fenced_markdown_is_allowed(self, tmp_path):
        self._init_repo(tmp_path)
        (tmp_path / "notes.md").write_text("```python\nresult={'bad':1}\n```\n")

        code, parsed = _run_main(_make_bash_event("git push origin feature", cwd=str(tmp_path)))

        assert code == 0
        assert parsed is None


# ---------------------------------------------------------------------------
# Fail open on malformed input
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_malformed_json_exits_0(self):
        code, _ = _run_main("not valid json {{{")
        assert code == 0

    def test_empty_stdin_exits_0(self):
        code, _ = _run_main("")
        assert code == 0

    def test_null_json_exits_0(self):
        code, _ = _run_main("null")
        assert code == 0
