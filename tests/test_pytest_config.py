"""Contract tests for repository-wide pytest collection settings."""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Full-repo mirrors. Their test_*.py copies share basenames with the real
# tests, so collecting one aborts the whole run with import errors.
MIRROR_DIRS = [".claude", ".codex"]


def test_local_tmp_tree_is_not_collected(pytestconfig):
    assert "tmp" in pytestconfig.getini("norecursedirs"), (
        "tmp/ holds local scratch projects, so collecting it makes the suite depend on untracked artifacts"
    )


@pytest.mark.parametrize("mirror", MIRROR_DIRS)
def test_repo_mirror_dir_is_not_collected(pytestconfig, mirror):
    assert mirror in pytestconfig.getini("norecursedirs"), (
        f"{mirror}/ mirrors the whole repo, so collecting it aborts the run with duplicate-basename errors"
    )


def test_install_e2e_and_performance_tests_are_deselected_by_default(pytestconfig):
    """The default run must skip the install.sh e2e files and the benchmarks."""
    addopts = " ".join(pytestconfig.getini("addopts"))
    assert "not (slow and integration)" in addopts, "the install.sh e2e files must stay out of the default run"
    assert "not performance" in addopts, "the timing benchmarks must stay out of the default run"


def test_ci_clears_the_default_marker_filter():
    """CI must run the full set, including whatever the default filter drops."""
    workflow = (_REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    assert '- run: python -m pytest --tb=short -q -m ""' in workflow, (
        'CI lost `-m ""`, so it silently stopped running the slow install and performance tests'
    )
