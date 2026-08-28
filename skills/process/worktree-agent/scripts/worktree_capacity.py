#!/usr/bin/env python3
"""Report task-worktree capacity without deleting any checkout or branch."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_SOFT_PERCENT = 80
DEFAULT_HARD_PERCENT = 85


def capacity_status(used_percent: float, *, soft_percent: int, hard_percent: int) -> str:
    """Classify disk pressure for task-worktree creation."""
    if not 0 <= soft_percent < hard_percent <= 100:
        raise ValueError("thresholds require 0 <= soft < hard <= 100")
    if used_percent >= hard_percent:
        return "blocked"
    if used_percent >= soft_percent:
        return "cleanup-soon"
    return "ready"


def usable_disk_percent(stats: os.statvfs_result) -> float:
    """Match `df` capacity by excluding filesystem-reserved blocks."""
    used_blocks = stats.f_blocks - stats.f_bfree
    usable_blocks = used_blocks + stats.f_bavail
    if usable_blocks <= 0:
        return 100.0
    return round(used_blocks * 100 / usable_blocks, 1)


def _porcelain_worktree_paths(porcelain: str) -> Iterable[Path]:
    for record in porcelain.split("\n\n"):
        for line in record.splitlines():
            if line.startswith("worktree "):
                yield Path(line.removeprefix("worktree "))
                break


def agent_worktree_paths(porcelain: str, agent_root: Path) -> list[Path]:
    """Return only registered worktrees below the designated agent root."""
    root = agent_root.resolve()
    result: list[Path] = []
    for path in _porcelain_worktree_paths(porcelain):
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        result.append(resolved)
    return sorted(result)


def _git_output(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout


def clean_worktree_paths(paths: Iterable[Path]) -> set[Path]:
    """Return checkouts with no tracked or untracked changes.

    This does not establish whether a task is still active. Dispatchers review
    these candidates before calling `git worktree remove`.
    """
    clean: set[Path] = set()
    for path in paths:
        try:
            if not _git_output(path, "status", "--porcelain"):
                clean.add(path)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return clean


def capacity_report(
    *,
    used_percent: float,
    paths: Iterable[Path],
    clean_paths: set[Path],
    soft_percent: int,
    hard_percent: int,
) -> dict[str, object]:
    """Build the stable, machine-readable capacity report."""
    ordered_paths = sorted(paths)
    return {
        "status": capacity_status(used_percent, soft_percent=soft_percent, hard_percent=hard_percent),
        "disk": {"used_percent": round(used_percent, 1), "soft_percent": soft_percent, "hard_percent": hard_percent},
        "worktrees": {
            "count": len(ordered_paths),
            "clean_candidates": [str(path) for path in ordered_paths if path in clean_paths],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="repository root")
    parser.add_argument(
        "--worktree-root",
        type=Path,
        default=Path(".claude/worktrees"),
        help="agent checkout root, relative to --repo unless absolute",
    )
    parser.add_argument("--soft-percent", type=int, default=DEFAULT_SOFT_PERCENT)
    parser.add_argument("--hard-percent", type=int, default=DEFAULT_HARD_PERCENT)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 2 when hard capacity is reached; default mode reports only",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    agent_root = args.worktree_root if args.worktree_root.is_absolute() else repo / args.worktree_root
    used_percent = usable_disk_percent(os.statvfs(repo))
    try:
        paths = agent_worktree_paths(_git_output(repo, "worktree", "list", "--porcelain"), agent_root)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"worktree-capacity: cannot inspect {repo}: {exc}", file=sys.stderr)
        return 1

    report = capacity_report(
        used_percent=used_percent,
        paths=paths,
        clean_paths=clean_worktree_paths(paths),
        soft_percent=args.soft_percent,
        hard_percent=args.hard_percent,
    )
    print(json.dumps(report, sort_keys=True))
    return 2 if args.strict and report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
