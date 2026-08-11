"""Behavior and protocol tests for the implementation plan gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "pretool-plan-gate.py"
ADAPTER = ROOT / "hooks" / "codex-hook-adapter.py"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    _init_repository(root)
    (root / "agents" / "example").mkdir(parents=True)
    (root / "skills" / "example").mkdir(parents=True)
    return root


def _git_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("GIT_COMMON_DIR", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
    )
    return env


def _run_git(*args: str, cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_git_environment(),
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _init_repository(root: Path) -> None:
    root.parent.mkdir(parents=True, exist_ok=True)
    _run_git("init", "--quiet", str(root), cwd=root.parent)


def _write_linked_metadata(marker: Path, common: Path) -> None:
    admin = common / "worktrees" / "forged"
    (common / "objects").mkdir(parents=True)
    (common / "refs").mkdir()
    admin.mkdir(parents=True)
    (common / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (common / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    (admin / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (admin / "gitdir").write_text(f"{marker}\n", encoding="utf-8")
    marker.write_text(f"gitdir: {admin}\n", encoding="utf-8")


def _run_hook(
    file_path: object,
    *,
    event_cwd: object | None,
    project_dir: object | None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    event: dict[str, object] = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
    }
    if event_cwd is not None:
        event["cwd"] = event_cwd

    env = dict(os.environ)
    for key in (
        "CLAUDE_HOOKS_DEBUG",
        "CLAUDE_PROJECT_DIR",
        "PLAN_GATE_BYPASS",
    ):
        env.pop(key, None)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd="/",
        env=env,
        timeout=10,
        check=False,
    )


def _run_adapter(file_path: str, *, event_cwd: Path) -> subprocess.CompletedProcess[str]:
    event = {
        "hook_event_name": "PreToolUse",
        "session_id": "plan-gate-test",
        "cwd": str(event_cwd),
        "tool_name": "apply_patch",
        "tool_input": {"command": f"*** Begin Patch\n*** Add File: {file_path}\n+content\n*** End Patch"},
    }
    return subprocess.run(
        [
            sys.executable,
            str(ADAPTER),
            "--hook",
            str(HOOK),
            "--event",
            "PreToolUse",
            "--matcher",
            "Write|Edit",
            "--mode",
            "patch",
            "--failure-policy",
            "closed",
            "--timeout",
            "2",
        ],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=event_cwd,
        timeout=10,
        check=False,
    )


def _decision(result: subprocess.CompletedProcess[str]) -> str | None:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    inner = output.get("hookSpecificOutput")
    if not isinstance(inner, dict):
        return None
    decision = inner.get("permissionDecision")
    return decision if isinstance(decision, str) else None


def _assert_allowed(result: subprocess.CompletedProcess[str]) -> None:
    assert _decision(result) is None
    assert result.stdout == ""
    assert result.stderr == ""


def _assert_denied(result: subprocess.CompletedProcess[str]) -> None:
    assert _decision(result) == "deny"
    assert "permissionDecisionReason" in json.loads(result.stdout)["hookSpecificOutput"]


def test_missing_root_plan_denies_absolute_gated_path(project: Path) -> None:
    result = _run_hook(
        str(project / "skills" / "example" / "SKILL.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_root_plan_allows_absolute_path_from_nested_cwd(project: Path) -> None:
    nested = project / "skills" / "example"
    (project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")

    result = _run_hook(
        str(nested / "SKILL.md"),
        event_cwd=str(nested),
        project_dir=str(project),
    )

    _assert_allowed(result)


def test_nested_plan_does_not_replace_root_plan(project: Path) -> None:
    nested = project / "skills" / "example"
    (nested / "task_plan.md").write_text("# Wrong plan\n", encoding="utf-8")

    result = _run_hook(
        str(nested / "SKILL.md"),
        event_cwd=str(nested),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_environment_root_without_git_is_supported(tmp_path: Path) -> None:
    project = tmp_path / "non-git-project"
    nested = project / "skills" / "example"
    nested.mkdir(parents=True)
    (project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")

    result = _run_hook(
        str(nested / "SKILL.md"),
        event_cwd=str(nested),
        project_dir=str(project),
    )

    _assert_allowed(result)


def test_worktree_git_file_anchors_nested_codex_cwd(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    worktree = tmp_path / "linked-worktree"
    _init_repository(repository)
    _run_git(
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "user.name=Plan Gate Test",
        "-c",
        "user.email=plan-gate@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "fixture",
        cwd=repository,
    )
    _run_git(
        "-c",
        "core.hooksPath=/dev/null",
        "worktree",
        "add",
        "--quiet",
        "--detach",
        str(worktree),
        "HEAD",
        cwd=repository,
    )
    nested = worktree / "skills" / "example"
    nested.mkdir(parents=True)
    (worktree / "task_plan.md").write_text("# Plan\n", encoding="utf-8")

    result = _run_hook(
        "SKILL.md",
        event_cwd=str(nested),
        project_dir=str(nested),
    )

    _assert_allowed(result)


def test_valid_repository_directory_anchors_nested_codex_cwd(project: Path) -> None:
    nested = project / "skills" / "example"
    (project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")

    result = _run_hook(
        "SKILL.md",
        event_cwd=str(nested),
        project_dir=str(nested),
    )

    _assert_allowed(result)


def test_invalid_nested_git_file_cannot_reanchor_adapter(project: Path) -> None:
    nested = project / "skills" / "example"
    (nested / ".git").write_text("not valid git metadata\n", encoding="utf-8")

    result = _run_adapter("SKILL.md", event_cwd=nested)

    _assert_denied(result)


def test_nested_gitdir_file_with_missing_target_cannot_reanchor_adapter(project: Path) -> None:
    nested = project / "skills" / "example"
    (nested / ".git").write_text(
        "gitdir: /missing/git/worktree/metadata\n",
        encoding="utf-8",
    )

    result = _run_adapter("SKILL.md", event_cwd=nested)

    _assert_denied(result)


def test_empty_nested_git_directory_cannot_reanchor_adapter(project: Path) -> None:
    nested = project / "skills" / "example"
    (nested / ".git").mkdir()

    result = _run_adapter("SKILL.md", event_cwd=nested)

    _assert_denied(result)


def test_plausible_nested_git_directory_is_ambiguous_and_denied(project: Path) -> None:
    nested = project / "skills" / "example"
    marker = nested / ".git"
    (marker / "objects").mkdir(parents=True)
    (marker / "refs").mkdir()
    (marker / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (marker / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n",
        encoding="utf-8",
    )

    result = _run_adapter("SKILL.md", event_cwd=nested)

    _assert_denied(result)


def test_forged_linked_worktree_cannot_override_outer_repository(project: Path, tmp_path: Path) -> None:
    nested = project / "skills" / "example"
    marker = nested / ".git"
    common = tmp_path / "forged-common"
    _write_linked_metadata(marker, common)

    result = _run_adapter("SKILL.md", event_cwd=nested)

    _assert_denied(result)


def test_linked_marker_with_inaccessible_outer_marker_fails_closed(project: Path, tmp_path: Path) -> None:
    nested = project / "skills" / "example"
    _write_linked_metadata(nested / ".git", tmp_path / "forged-common")
    outer_marker = project / ".git"
    outer_marker.chmod(0)
    try:
        result = _run_adapter("SKILL.md", event_cwd=nested)
    finally:
        outer_marker.chmod(0o700)

    _assert_denied(result)


def test_unreadable_nested_git_file_cannot_reanchor_adapter(project: Path) -> None:
    nested = project / "skills" / "example"
    marker = nested / ".git"
    marker.write_text("gitdir: /untrusted/location\n", encoding="utf-8")
    marker.chmod(0)

    result = _run_adapter("SKILL.md", event_cwd=nested)

    _assert_denied(result)


def test_relative_path_without_repository_marker_fails_closed(tmp_path: Path) -> None:
    nested = tmp_path / "non-repository" / "skills" / "example"
    nested.mkdir(parents=True)

    result = _run_hook(
        "SKILL.md",
        event_cwd=str(nested),
        project_dir=str(nested),
    )

    _assert_denied(result)


def test_cwd_git_ancestor_is_used_when_project_environment_is_missing(project: Path) -> None:
    nested = project / "skills" / "example"
    (project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")

    result = _run_hook(
        str(nested / "SKILL.md"),
        event_cwd=str(nested),
        project_dir=None,
    )

    _assert_allowed(result)


def test_non_git_cwd_without_project_environment_fails_closed(tmp_path: Path) -> None:
    nested = tmp_path / "non-git-project" / "skills" / "example"
    nested.mkdir(parents=True)

    result = _run_hook(
        str(nested / "SKILL.md"),
        event_cwd=str(nested),
        project_dir=None,
    )

    _assert_denied(result)


@pytest.mark.parametrize(
    "file_path",
    [
        "skills/example/SKILL.md",
        "skills\\example\\SKILL.md",
    ],
)
def test_relative_codex_paths_are_gated(project: Path, file_path: str) -> None:
    result = _run_hook(
        file_path,
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_relative_traversal_into_gated_directory_is_gated(project: Path) -> None:
    scratch = project / "scratch"
    scratch.mkdir()

    result = _run_hook(
        "../skills/example/SKILL.md",
        event_cwd=str(scratch),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_relative_traversal_outside_project_fails_closed(project: Path) -> None:
    result = _run_hook(
        "../outside/skills/example/SKILL.md",
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_symlink_escape_from_gated_directory_fails_closed(project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / "skills" / "escape").symlink_to(outside, target_is_directory=True)

    result = _run_hook(
        str(project / "skills" / "escape" / "SKILL.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_symlink_into_gated_directory_cannot_hide_target(project: Path) -> None:
    docs = project / "docs"
    docs.mkdir()
    (docs / "skill-link").symlink_to(project / "skills" / "example", target_is_directory=True)

    result = _run_hook(
        str(docs / "skill-link" / "SKILL.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_absolute_skills_segment_outside_project_is_not_gated(project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside" / "skills" / "example"
    outside.mkdir(parents=True)

    result = _run_hook(
        str(outside / "SKILL.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_allowed(result)


@pytest.mark.parametrize(
    ("event_cwd", "project_dir"),
    [
        (None, None),
        ("/path/that/does/not/exist", "/also/missing"),
        ("bad\x00cwd", None),
    ],
)
def test_missing_or_invalid_root_fails_closed_for_gated_path(
    event_cwd: str | None,
    project_dir: str | None,
) -> None:
    result = _run_hook(
        "skills/example/SKILL.md",
        event_cwd=event_cwd,
        project_dir=project_dir,
    )

    _assert_denied(result)


def test_missing_root_fails_closed_for_unclassifiable_relative_path() -> None:
    result = _run_hook(
        "docs/example.md",
        event_cwd=None,
        project_dir=None,
    )

    _assert_denied(result)


def test_relative_path_without_cwd_fails_closed_with_known_root(project: Path) -> None:
    result = _run_hook(
        "docs/example.md",
        event_cwd=None,
        project_dir=str(project),
    )

    _assert_denied(result)


def test_exact_root_plan_creation_is_allowed(project: Path) -> None:
    result = _run_hook(
        str(project / "task_plan.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_allowed(result)


def test_nested_task_plan_name_does_not_bypass_gate(project: Path) -> None:
    result = _run_hook(
        str(project / "skills" / "example" / "task_plan.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_plan_symlink_outside_root_does_not_satisfy_gate(project: Path, tmp_path: Path) -> None:
    outside_plan = tmp_path / "outside-plan.md"
    outside_plan.write_text("# Not the root plan\n", encoding="utf-8")
    (project / "task_plan.md").symlink_to(outside_plan)

    result = _run_hook(
        str(project / "skills" / "example" / "SKILL.md"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_denied(result)


def test_non_gated_project_file_is_allowed_without_plan(project: Path) -> None:
    result = _run_hook(
        str(project / "hooks" / "example.py"),
        event_cwd=str(project),
        project_dir=str(project),
    )

    _assert_allowed(result)


def test_explicit_bypass_preserves_no_output_protocol(project: Path) -> None:
    result = _run_hook(
        "skills/example/SKILL.md",
        event_cwd=str(project),
        project_dir=str(project),
        extra_env={"PLAN_GATE_BYPASS": "1"},
    )

    _assert_allowed(result)


def test_invalid_json_preserves_no_output_protocol() -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not-json",
        capture_output=True,
        text=True,
        cwd="/",
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_codex_adapter_denies_relative_patch_without_plan(project: Path) -> None:
    result = _run_adapter("skills/example/SKILL.md", event_cwd=project)

    assert result.returncode == 0, result.stderr
    assert _decision(result) == "deny"
