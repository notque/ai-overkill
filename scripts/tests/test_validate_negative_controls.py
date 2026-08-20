#!/usr/bin/env python3
"""Tests for scripts/validate-negative-controls.py.

RED-first: each test proves the validator detects (or correctly skips) a
specific condition using synthetic fixtures in tmp_path.

Run with: python3 -m pytest scripts/tests/test_validate_negative_controls.py -v
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "validate-negative-controls.py"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _make_workflow(repo: Path, steps: list[dict], job_attrs: dict | None = None) -> Path:
    """Build a minimal workflow YAML with the given run steps.

    Each step dict: {run: str, name: str (opt), continue_on_error: bool (opt)}.
    job_attrs: extra keys merged into the job (e.g. continue-on-error at job level).
    """
    import yaml

    job: dict = {"runs-on": "ubuntu-latest", "steps": [{"uses": "actions/checkout@v6"}]}
    if job_attrs:
        job.update(job_attrs)

    for s in steps:
        step: dict = {"run": s["run"]}
        if "name" in s:
            step["name"] = s["name"]
        if s.get("continue_on_error"):
            step["continue-on-error"] = True
        job["steps"].append(step)

    data = {
        "name": "Tests",
        "on": {"push": {"branches": ["main"]}},
        "jobs": {"lint": job},
    }
    wf = repo / ".github" / "workflows" / "test.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return wf


def _make_test_file(tests_dir: Path, script_name: str, content: str) -> Path:
    """Write a test file matching script_name convention."""
    stem = script_name.removesuffix(".py").replace("-", "_")
    test_file = tests_dir / f"test_{stem}.py"
    _write(test_file, content.replace('"x.py"', f'"scripts/{script_name}"'))
    return test_file


def _make_allowlist(repo: Path, entries: list[str] | None = None) -> Path:
    """Write the allowlist. Each entry is a raw line."""
    path = repo / "scripts" / "negative-control-allowlist.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Negative-control allowlist\n"]
    if entries:
        lines.extend(e + "\n" for e in entries)
    path.write_text("".join(lines), encoding="utf-8")
    return path


def _run(repo: Path, *extra_flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
        ]
        + list(extra_flags),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# 1. Hard gate with only positive tests -> exit 1
# ---------------------------------------------------------------------------


def test_positive_only_test_exits_one(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-foo.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-foo.py",
        """\
        import subprocess, sys
        def test_passes():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode == 0
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "validate-foo.py" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# 2. Add a failing test -> exit 0
# ---------------------------------------------------------------------------


def test_negative_test_present_exits_zero(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-foo.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-foo.py",
        """\
        import subprocess, sys
        def test_passes():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode == 0

        def test_fails():
            result = subprocess.run([sys.executable, "x.py", "--bad"], capture_output=True)
            assert result.returncode == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 3. Stale allowlist entry -> exit 1
# ---------------------------------------------------------------------------


def test_stale_allowlist_exits_one(tmp_path):
    """Gate has a negative test AND appears in allowlist -> stale -> exit 1."""
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-foo.py"}])
    _make_allowlist(repo, ["validate-foo.py: legacy gate, no negative test yet"])
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-foo.py",
        """\
        import subprocess, sys
        def test_fails():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "stale" in (result.stdout + result.stderr).lower()


def test_stale_allowlist_script_not_in_ci(tmp_path):
    """Allowlisted script no longer in CI -> stale -> exit 1."""
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-bar.py"}])
    _make_allowlist(repo, ["validate-gone.py: was removed from CI"])
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-bar.py",
        """\
        import subprocess, sys
        def test_fails():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "validate-gone.py" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# 4. Advisory step skipped correctly
# ---------------------------------------------------------------------------


def test_advisory_continue_on_error_skipped(tmp_path):
    """A step with continue-on-error: true should not require negative tests."""
    repo = tmp_path / "repo"
    _make_workflow(
        repo,
        [{"run": "python scripts/validate-advisory.py", "continue_on_error": True}],
    )
    _make_allowlist(repo)
    # No test file at all — should still pass because the step is advisory.

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "advisory" in result.stdout.lower()


def test_advisory_or_true_skipped(tmp_path):
    """A step with || true should not require negative tests."""
    repo = tmp_path / "repo"
    _make_workflow(
        repo,
        [{"run": "python scripts/check-advisory.py --json || true"}],
    )
    _make_allowlist(repo)

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "advisory" in result.stdout.lower()


def test_advisory_job_level_continue_on_error(tmp_path):
    """A job with continue-on-error: true makes all its steps advisory."""
    repo = tmp_path / "repo"
    _make_workflow(
        repo,
        [{"run": "python scripts/validate-jobadv.py"}],
        job_attrs={"continue-on-error": True},
    )
    _make_allowlist(repo)

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "advisory" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 5. Missing test file entirely -> exit 1
# ---------------------------------------------------------------------------


def test_missing_test_file_exits_one(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-notest.py"}])
    _make_allowlist(repo)
    # No test file created.
    (repo / "scripts" / "tests").mkdir(parents=True, exist_ok=True)

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "validate-notest.py" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# 6. Clean state -> exit 0
# ---------------------------------------------------------------------------


def test_clean_state_exits_zero(tmp_path):
    """All hard gates have negative tests, no stale allowlist entries."""
    repo = tmp_path / "repo"
    _make_workflow(
        repo,
        [
            {"run": "python scripts/validate-alpha.py"},
            {"run": "python scripts/check-beta.py"},
        ],
    )
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-alpha.py",
        """\
        import subprocess, sys
        def test_rejects_bad():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode == 1
        """,
    )
    _make_test_file(
        repo / "scripts" / "tests",
        "check-beta.py",
        """\
        import subprocess, sys
        def test_rejects_bad():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode != 0
        """,
    )

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 finding(s)" in result.stdout


# ---------------------------------------------------------------------------
# 7. `assert rc == 1` pattern detected
# ---------------------------------------------------------------------------


def test_assert_rc_equals_one_detected(tmp_path):
    """The `assert rc == 1` pattern (main() returns int) should be detected."""
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-rcstyle.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-rcstyle.py",
        """\
        import subprocess, sys
        def test_rejects():
            rc = subprocess.run([sys.executable, "scripts/validate-rcstyle.py"]).returncode
            assert rc == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 8. `pytest.raises(SystemExit)` must constrain the code to non-zero
# ---------------------------------------------------------------------------


def test_pytest_raises_nonzero_systemexit_detected(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-sysexit.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-sysexit.py",
        """\
        import pytest
        def test_exits_nonzero():
            with pytest.raises(SystemExit, match="1"):
                import validate_sysexit
                validate_sysexit.main()
        """,
    )

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unconstrained_pytest_raises_systemexit_not_detected(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-sysexit.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-sysexit.py",
        """\
        import pytest
        def test_exits():
            with pytest.raises(SystemExit):
                raise SystemExit(0)
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr


def test_bare_returncode_comparison_not_detected(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-bare.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-bare.py",
        """\
        def helper(result):
            return result.returncode == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 9. JSON output mode
# ---------------------------------------------------------------------------


def test_json_output(tmp_path):
    import json

    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-jtest.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-jtest.py",
        """\
        import subprocess, sys
        def test_fails():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode == 1
        """,
    )

    result = _run(repo, "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["pass"] is True
    assert isinstance(data["gates"], list)
    assert len(data["findings"]) == 0


# ---------------------------------------------------------------------------
# 10. Allowlist properly suppresses a finding
# ---------------------------------------------------------------------------


def test_allowlist_suppresses_finding(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-allowed.py"}])
    _make_allowlist(repo, ["validate-allowed.py: intentionally no negative test, legacy"])
    # No test file -> would fail without allowlist.
    (repo / "scripts" / "tests").mkdir(parents=True, exist_ok=True)

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "allowlisted" in result.stdout


def test_strict_mode_rejects_allowlisted_debt(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-allowed.py"}])
    _make_allowlist(repo, ["validate-allowed.py: CLI negative control pending"])
    (repo / "scripts" / "tests").mkdir(parents=True, exist_ok=True)

    result = _run(repo, "--strict")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "validate-allowed.py" in result.stdout


# ---------------------------------------------------------------------------
# 11. returncode != 0 pattern detected
# ---------------------------------------------------------------------------


def test_returncode_not_equal_zero_detected(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-neq.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-neq.py",
        """\
        import subprocess, sys
        def test_rejects():
            result = subprocess.run([sys.executable, "x.py"], capture_output=True)
            assert result.returncode != 0
        """,
    )

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 12. check-*.py scripts are also detected
# ---------------------------------------------------------------------------


def test_check_script_detected(tmp_path):
    """Scripts named check-*.py should be treated the same as validate-*.py."""
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/check-drift.py --verbose"}])
    _make_allowlist(repo)
    (repo / "scripts" / "tests").mkdir(parents=True, exist_ok=True)
    # No test file -> should fail.

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "check-drift.py" in (result.stdout + result.stderr)


def test_unrelated_rc_assertion_not_detected(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-unrelated.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-unrelated.py",
        """\
        def test_unrelated():
            rc = 1
            assert rc == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr


def test_skipped_negative_control_not_detected(tmp_path):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-skipped.py"}])
    _make_allowlist(repo)
    _make_test_file(
        repo / "scripts" / "tests",
        "validate-skipped.py",
        """\
        import pytest, subprocess, sys
        @pytest.mark.skip(reason="not collected")
        def test_rejects():
            result = subprocess.run([sys.executable, "scripts/validate-skipped.py"])
            assert result.returncode == 1
        """,
    )

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize(
    "body",
    [
        """\
        SCRIPT = "scripts/validate-fake.py"
        def fake_runner(_target):
            class Result: returncode = 1
            return Result()
        def test_fake():
            result = fake_runner(SCRIPT)
            assert result.returncode == 1
        """,
        """\
        import subprocess, sys
        SCRIPT = "scripts/validate-other.py"
        def test_mismatch():
            result = subprocess.run([sys.executable, SCRIPT])
            assert result.returncode == 1
        """,
        """\
        def fake_runner(_target):
            class Result: returncode = 1
            return Result()
        def test_literal_fake():
            result = fake_runner("scripts/validate-fake.py")
            assert result.returncode == 1
        """,
    ],
)
def test_fake_or_mismatched_execution_not_detected(tmp_path, body):
    repo = tmp_path / "repo"
    _make_workflow(repo, [{"run": "python scripts/validate-fake.py"}])
    _make_allowlist(repo)
    _make_test_file(repo / "scripts" / "tests", "validate-fake.py", body)

    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
