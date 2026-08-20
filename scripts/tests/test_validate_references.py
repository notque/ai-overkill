"""Tests for scripts/validate-references.py — agent reference file integrity.

Covers the path-existence check (the strongest check in the toolkit, line 343:
``ref_path.exists()``), the --all mode, and negative controls: a reference
table pointing at a missing file must exit non-zero.

The script hardcodes AGENTS_DIR from its own filesystem location, so tests
import the module and test functions directly rather than using subprocess
with a tmp_path tree.

Run with: python3 -m pytest scripts/tests/test_validate_references.py -v
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate-references.py"

# Load the hyphenated script as a module.
_spec = importlib.util.spec_from_file_location("validate_references", SCRIPT)
assert _spec is not None and _spec.loader is not None
vr = importlib.util.module_from_spec(_spec)
sys.modules["validate_references"] = vr
_spec.loader.exec_module(vr)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Negative control: a reference that does not exist must be flagged
# ---------------------------------------------------------------------------


def test_validate_agent_flags_missing_reference(tmp_path: Path) -> None:
    """An agent declaring a reference that does not exist is flagged as MISSING."""
    # Create a fake agent file that declares a reference link.
    agents_dir = REPO_ROOT / "agents"
    agent_dir = agents_dir / "negtest-phantom-agent"
    refs_dir = agent_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    agent_file = agents_dir / "negtest-phantom-agent.md"
    try:
        agent_file.write_text(
            "# Negative Test Agent\n\nLoad [patterns](references/nonexistent-patterns.md) on signal.\n",
            encoding="utf-8",
        )

        result = vr.validate_agent(agent_file, check_structure=True)
        assert len(result.missing) >= 1, f"expected at least 1 missing reference, got {result.missing}"
        assert not result.ok, "result should not be ok when references are missing"
        assert any("nonexistent-patterns.md" in m for m in result.missing), (
            f"expected 'nonexistent-patterns.md' in missing list: {result.missing}"
        )
    finally:
        # Clean up: remove the test agent file and directory
        agent_file.unlink(missing_ok=True)
        if refs_dir.exists():
            refs_dir.rmdir()
        if agent_dir.exists():
            agent_dir.rmdir()


def test_validate_agent_passes_when_references_exist() -> None:
    """An agent with all references present reports ok=True."""
    # Use a real agent that has references (testing-automation-engineer has 5).
    agent_file = REPO_ROOT / "agents" / "testing-automation-engineer.md"
    if not agent_file.exists():
        pytest.skip("testing-automation-engineer.md not found")

    result = vr.validate_agent(agent_file, check_structure=False)
    assert result.ok, (
        f"expected ok=True for agent with all references present; missing={result.missing}, issues={result.issues}"
    )


# ---------------------------------------------------------------------------
# Negative control: --all mode must exit 1 when a reference is missing
# ---------------------------------------------------------------------------


def test_all_mode_exits_nonzero_on_missing_reference(tmp_path: Path) -> None:
    """--all mode exit code is 1 when any agent has a missing reference."""
    agents_dir = REPO_ROOT / "agents"
    agent_dir = agents_dir / "negtest-missing-ref"
    refs_dir = agent_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    agent_file = agents_dir / "negtest-missing-ref.md"
    try:
        agent_file.write_text(
            "# Negative Test Missing Ref\n\nLoad [check](references/does-not-exist-zzzz.md) on signal.\n",
            encoding="utf-8",
        )

        result = _run("--agent", "negtest-missing-ref")
        assert result.returncode == 1, (
            f"expected exit 1 for missing reference, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "MISSING" in result.stdout, f"expected 'MISSING' in output\nstdout: {result.stdout}"
    finally:
        agent_file.unlink(missing_ok=True)
        if refs_dir.exists():
            refs_dir.rmdir()
        if agent_dir.exists():
            agent_dir.rmdir()


# ---------------------------------------------------------------------------
# Scoped modes that CI already uses
# ---------------------------------------------------------------------------


def test_check_do_framing_exits_zero_on_shipped_repo() -> None:
    """The repo's own files pass the do-framing check (CI gate)."""
    result = _run("--check-do-framing")
    assert result.returncode == 0, (
        f"shipped repo fails --check-do-framing\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_check_placeholders_exits_zero_on_shipped_repo() -> None:
    """The repo's own files pass the placeholder-signals check (CI gate)."""
    result = _run("--check-placeholders")
    assert result.returncode == 0, (
        f"shipped repo fails --check-placeholders\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
