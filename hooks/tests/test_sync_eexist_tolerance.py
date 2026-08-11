"""Tests for EEXIST race tolerance in sync-to-user-claude.py.

Three bug classes:
1. Concurrent SessionStart race: no inter-process lock, second process's
   symlink_to raises FileExistsError.
2. EEXIST-intolerant mkdir: Path.mkdir(parents=True, exist_ok=True) over
   a broken symlink raises FileExistsError.
3. Per-component blast radius: one file failure aborts the rest of that
   component's loop and stale cleanup.

TDD: tests written before fixes. Each test must fail on the unfixed code
and pass after the fix.
"""

import fcntl
import json
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "sync_to_user_claude",
    HOOKS_DIR / "sync-to-user-claude.py",
)
sync_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_mod)


# ---------------------------------------------------------------------------
# 1. Concurrent SessionStart race — flock at main() entry
# ---------------------------------------------------------------------------


class TestConcurrentSyncLock:
    """Two concurrent main() calls must not race. The second should skip
    (non-blocking flock) because the first sync makes its work redundant."""

    def _setup_repo(self, tmp_path: Path) -> tuple[Path, Path]:
        """Minimal repo + user_claude for main()."""
        repo = tmp_path / "repo"
        repo.mkdir()
        for comp in ["agents", "skills", "hooks", "commands", "scripts"]:
            d = repo / comp
            d.mkdir()
            (d / "sample.md").write_text(f"# {comp}")
        skill = repo / "skills" / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        (repo_claude / "settings.json").write_text(json.dumps({"hooks": {}}))

        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {"mode": "symlink", "toolkit_path": str(repo)}
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return repo, user_claude

    def test_second_process_skips_when_lock_held(self, tmp_path: Path) -> None:
        """Simulate: process A holds the lock, process B should skip (not block)."""
        repo, user_claude = self._setup_repo(tmp_path)
        lock_path = user_claude / ".sync.lock"

        # Pre-acquire the lock (simulating process A)
        lock_path.touch()
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        results = {"skipped": False}

        def run_main_b():
            with (
                patch.object(Path, "home", return_value=tmp_path / "home"),
                patch.object(Path, "cwd", return_value=repo),
                patch.object(sync_mod, "_is_git_worktree", return_value=False),
                patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
            ):
                sync_mod.main()
            # If main() returned quickly without syncing, the lock skip worked.
            # Check that no components were synced (agents dir should not exist
            # as a symlink since process B skipped).
            results["skipped"] = not (user_claude / "agents").exists()

        t = threading.Thread(target=run_main_b)
        t.start()
        t.join(timeout=3)  # Should complete very fast (non-blocking skip)

        # Release process A's lock
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

        assert not t.is_alive(), "Process B should not block waiting for lock"
        assert results["skipped"], "Process B should have skipped sync"

    def test_lock_file_created_at_sync(self, tmp_path: Path) -> None:
        """main() should create the lock file in ~/.claude/."""
        repo, user_claude = self._setup_repo(tmp_path)
        lock_path = user_claude / ".sync.lock"

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Lock file should exist (may or may not be held; main() has returned)
        assert lock_path.exists(), "Lock file should be created by main()"


# ---------------------------------------------------------------------------
# 2. EEXIST-intolerant mkdir — broken symlink causes FileExistsError
# ---------------------------------------------------------------------------


class TestTolerantMkdir:
    """Path.mkdir(parents=True, exist_ok=True) raises FileExistsError when
    the path is a broken symlink. A tolerant helper should handle this."""

    def test_mkdir_over_broken_symlink(self, tmp_path: Path) -> None:
        """mkdir on a broken-symlink path must succeed (unlink + retry)."""
        target = tmp_path / "dst"
        target.symlink_to(tmp_path / "nonexistent")
        assert target.is_symlink() and not target.exists()

        # The tolerant helper should handle this
        sync_mod._tolerant_mkdir(target)
        assert target.is_dir()

    def test_mkdir_over_existing_dir_noop(self, tmp_path: Path) -> None:
        """Existing real directory: no-op."""
        target = tmp_path / "dst"
        target.mkdir()
        sync_mod._tolerant_mkdir(target)
        assert target.is_dir()

    def test_mkdir_creates_parents(self, tmp_path: Path) -> None:
        """Creates parent directories like parents=True."""
        target = tmp_path / "a" / "b" / "c"
        sync_mod._tolerant_mkdir(target)
        assert target.is_dir()

    def test_mkdir_broken_symlink_in_parent(self, tmp_path: Path) -> None:
        """Broken symlink in a parent path must be fixed too."""
        # Create parent as broken symlink
        parent = tmp_path / "parent"
        parent.symlink_to(tmp_path / "gone")
        target = parent / "child"

        sync_mod._tolerant_mkdir(target)
        assert target.is_dir()


class TestTolerantMkdirInCopyMode:
    """End-to-end: broken symlinks at mkdir sites in copy-mode sync."""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        for comp in ["agents", "skills", "hooks", "commands", "scripts"]:
            d = repo / comp
            d.mkdir()
            (d / "sample.md").write_text(f"# {comp}")
        skill = repo / "skills" / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        (repo_claude / "settings.json").write_text(json.dumps({"hooks": {}}))

        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {"mode": "copy", "toolkit_path": str(repo)}
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return repo, user_claude, tmp_path

    def test_broken_symlink_dst_in_copy_mode(self, tmp_path: Path) -> None:
        """dst directory is a broken symlink: main() must not crash."""
        repo, user_claude, base = self._setup(tmp_path)

        # Sabotage: make agents dir a broken symlink
        agents_dst = user_claude / "agents"
        agents_dst.symlink_to(tmp_path / "vanished-repo" / "agents")

        with (
            patch.object(Path, "home", return_value=base / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()  # Should not raise

        # Agents should have been synced despite the broken symlink
        assert (user_claude / "agents" / "sample.md").exists()


# ---------------------------------------------------------------------------
# 3. Per-file error handling — single file failure must not abort component
# ---------------------------------------------------------------------------


class TestPerFileErrorHandling:
    """A single file copy failure must not abort the remaining files in that
    component. The error should be logged but the loop continues."""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        for comp in ["agents", "skills", "hooks", "commands", "scripts"]:
            d = repo / comp
            d.mkdir()
        # Multiple agent files: failure on one should not skip the rest
        agents = repo / "agents"
        (agents / "a.md").write_text("# agent a")
        (agents / "b.md").write_text("# agent b")
        (agents / "c.md").write_text("# agent c")

        skill = repo / "skills" / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")

        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        (repo_claude / "settings.json").write_text(json.dumps({"hooks": {}}))

        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {"mode": "copy", "toolkit_path": str(repo)}
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return repo, user_claude, tmp_path

    def test_single_file_failure_continues_loop(self, tmp_path: Path) -> None:
        """If copying one file fails, other files must still be synced."""
        repo, user_claude, base = self._setup(tmp_path)

        original_copy2 = __import__("shutil").copy2
        call_count = {"total": 0, "failed": 0}

        def failing_copy2(src, dst, **kwargs):
            if str(src).endswith("b.md") and "agents" in str(src):
                call_count["failed"] += 1
                raise PermissionError("simulated permission error on b.md")
            call_count["total"] += 1
            return original_copy2(src, dst, **kwargs)

        with (
            patch.object(Path, "home", return_value=base / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
            patch("shutil.copy2", side_effect=failing_copy2),
        ):
            sync_mod.main()  # Should not raise

        # a.md and c.md should still be synced despite b.md failure
        assert (user_claude / "agents" / "a.md").exists(), "a.md should be synced"
        assert (user_claude / "agents" / "c.md").exists(), "c.md should be synced"

    def test_error_logged_to_stderr(self, tmp_path: Path, capsys) -> None:
        """Per-file errors should produce a stderr warning line."""
        repo, user_claude, base = self._setup(tmp_path)

        original_copy = sync_mod._copy_file_contents

        def failing_copy(src):
            if str(src).endswith("b.md") and "agents" in str(src):
                raise PermissionError("simulated")
            return original_copy(src)

        with (
            patch.object(Path, "home", return_value=base / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
            patch.object(sync_mod, "_copy_file_contents", side_effect=failing_copy),
        ):
            sync_mod.main()

        stderr = capsys.readouterr().err
        assert "b.md" in stderr, "Per-file error should mention the failed file"


# ---------------------------------------------------------------------------
# 4. _ensure_symlink EEXIST race — concurrent symlink_to
# ---------------------------------------------------------------------------


class TestEnsureSymlinkRace:
    """_ensure_symlink has a check-then-act race: between unlink/check and
    symlink_to, another process can create the symlink. Must handle EEXIST."""

    def test_concurrent_symlink_creation(self, tmp_path: Path) -> None:
        """If symlink_to raises FileExistsError, _ensure_symlink must
        handle it gracefully (the other process already created it)."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"

        original_symlink_to = Path.symlink_to

        def racing_symlink_to(self_path, target, **kwargs):
            # Simulate race: another process already created the symlink
            if str(self_path) == str(dst) and not self_path.exists():
                original_symlink_to(self_path, target, **kwargs)
                # Now raise as if another process did it first
                raise FileExistsError(f"[Errno 17] File exists: '{self_path}'")
            return original_symlink_to(self_path, target, **kwargs)

        with (
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
            patch.object(Path, "symlink_to", racing_symlink_to),
        ):
            result = sync_mod._ensure_symlink(src, dst)

        # Should succeed: the symlink exists (created by "other process")
        assert result is True

    def test_symlink_to_eexist_correct_target(self, tmp_path: Path) -> None:
        """When EEXIST is raised and the existing symlink points to the
        correct target, _ensure_symlink should return True."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"

        # Pre-create correct symlink (simulating concurrent creation)
        dst.symlink_to(src)

        original_symlink_to = Path.symlink_to

        def always_eexist(self_path, target, **kwargs):
            raise FileExistsError(f"[Errno 17] File exists: '{self_path}'")

        with (
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
            patch.object(Path, "symlink_to", always_eexist),
        ):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True


# ---------------------------------------------------------------------------
# 5. _sync_skills_flat_symlinks root-file symlink EEXIST
# ---------------------------------------------------------------------------


class TestSkillsFlatSymlinkEEXIST:
    """Root-level file symlinks in _sync_skills_flat_symlinks (line ~448)
    also call symlink_to without EEXIST guard."""

    def test_broken_symlink_at_skills_dst(self, tmp_path: Path) -> None:
        """Skills dst is a broken symlink: must be handled by _tolerant_mkdir."""
        src = tmp_path / "skills"
        src.mkdir()
        skill = src / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        (src / "README.md").write_text("# skills\n")

        dst = tmp_path / "out"
        # Make dst a broken symlink
        dst.symlink_to(tmp_path / "gone")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert dst.is_dir()
        assert (dst / "do").is_symlink()
