"""Verify isolation from Git metadata, including non-harness checkout paths."""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "worktree-preflight.sh"


def test_linked_worktree_and_branch_ownership(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init")
    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial")
    linked = tmp_path / "external checkout"
    git("worktree", "add", "-b", "task/assigned", str(linked))

    def check(cwd, branch):
        return subprocess.run(["bash", str(SCRIPT), branch], cwd=cwd, capture_output=True, text=True)

    assert check(linked, "task/assigned").returncode == 0
    assert check(linked, "task/new").returncode == 0
    assert check(repo, "task/new").returncode == 1
    misleading = repo / ".claude" / "worktrees" / "not-linked"
    misleading.mkdir(parents=True)
    assert check(misleading, "task/new").returncode == 1
    other = tmp_path / "other"
    git("worktree", "add", "-b", "task/other", str(other))
    assert check(other, "task/assigned").returncode == 1
    assert "task/assigned" in git("branch", "--list").stdout.decode()
