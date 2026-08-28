"""Regression tests for the deterministic worktree-capacity guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "worktree_capacity.py"
TOOLKIT_ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location("worktree_capacity", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
worktree_capacity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worktree_capacity)


def test_capacity_status_reserves_hard_stop_for_new_worktrees():
    assert worktree_capacity.capacity_status(79, soft_percent=80, hard_percent=85) == "ready"
    assert worktree_capacity.capacity_status(80, soft_percent=80, hard_percent=85) == "cleanup-soon"
    assert worktree_capacity.capacity_status(85, soft_percent=80, hard_percent=85) == "blocked"


def test_usable_disk_percent_counts_filesystem_reserved_space_as_unavailable():
    stats = SimpleNamespace(f_blocks=100, f_bfree=30, f_bavail=20)

    assert worktree_capacity.usable_disk_percent(stats) == 77.8


def test_parse_worktree_porcelain_keeps_only_paths_under_agent_root(tmp_path):
    agent_root = tmp_path / ".claude" / "worktrees"
    kept = agent_root / "active"
    outside = tmp_path / "manual-checkout"
    payload = (
        f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"
        f"worktree {kept}\nHEAD def\nbranch refs/heads/fix/active\n\n"
        f"worktree {outside}\nHEAD ghi\ndetached\n"
    )

    assert worktree_capacity.agent_worktree_paths(payload, agent_root) == [kept]


def test_capacity_report_marks_clean_checkouts_for_dispatcher_review(tmp_path):
    report = worktree_capacity.capacity_report(
        used_percent=81,
        paths=[tmp_path / "clean", tmp_path / "dirty"],
        clean_paths={tmp_path / "clean"},
        soft_percent=80,
        hard_percent=85,
    )

    assert report["status"] == "cleanup-soon"
    assert report["worktrees"] == {"count": 2, "clean_candidates": [str(tmp_path / "clean")]}


def test_dispatch_rules_require_capacity_preflight_and_checkout_roles():
    canonical_rules = (TOOLKIT_ROOT / "skills/meta/do/references/worktree-rules.md").read_text()
    quality_loop = (TOOLKIT_ROOT / "skills/meta/do/references/quality-loop.md").read_text()

    assert "worktree_capacity.py" in canonical_rules
    assert "allocate no checkout" in canonical_rules
    assert "sparse-checkout" in canonical_rules
    assert "git worktree remove -- <accepted-worktree-path>" in canonical_rules
    assert "read-only reviewers" in quality_loop
