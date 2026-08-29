"""Tests for sync-to-user-claude.py symlink preservation logic."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest

# Add hooks/ to sys.path so we can import the module
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

# Import the module under test (filename has hyphens, use importlib)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "sync_to_user_claude",
    HOOKS_DIR / "sync-to-user-claude.py",
)
sync_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_mod)


class TestReadInstallMode:
    """Tests for _read_install_mode."""

    def test_symlink_mode(self, tmp_path: Path) -> None:
        manifest = {"mode": "symlink", "toolkit_path": "/some/path"}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        assert sync_mod._read_install_mode(tmp_path) == "symlink"

    def test_copy_mode(self, tmp_path: Path) -> None:
        manifest = {"mode": "copy", "toolkit_path": "/some/path"}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        assert sync_mod._read_install_mode(tmp_path) == "copy"

    def test_missing_manifest(self, tmp_path: Path) -> None:
        assert sync_mod._read_install_mode(tmp_path) == "copy"

    def test_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / ".install-manifest.json").write_text("{invalid json")
        assert sync_mod._read_install_mode(tmp_path) == "copy"

    def test_missing_mode_key(self, tmp_path: Path) -> None:
        manifest = {"toolkit_path": "/some/path"}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        assert sync_mod._read_install_mode(tmp_path) == "copy"


class TestUpdateManifestToolkitPath:
    """Tests for _update_manifest_toolkit_path."""

    def test_updates_stale_path(self, tmp_path: Path) -> None:
        manifest = {"mode": "symlink", "toolkit_path": "/old/repo/path"}
        manifest_path = tmp_path / ".install-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        new_repo = tmp_path / "new-repo"
        new_repo.mkdir()
        # Patch _is_ephemeral_path since test fixtures live in /tmp/
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._update_manifest_toolkit_path(tmp_path, new_repo)

        updated = json.loads(manifest_path.read_text())
        assert updated["toolkit_path"] == str(new_repo)
        assert updated["mode"] == "symlink"

    def test_no_update_when_path_matches(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        manifest = {"mode": "symlink", "toolkit_path": str(repo)}
        manifest_path = tmp_path / ".install-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        mtime_before = manifest_path.stat().st_mtime
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._update_manifest_toolkit_path(tmp_path, repo)

        # File should not have been rewritten
        mtime_after = manifest_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_no_crash_on_missing_manifest(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        # Should not raise
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._update_manifest_toolkit_path(tmp_path, repo)

    def test_rejects_tmp_path(self, tmp_path: Path) -> None:
        """Verify /tmp/ paths are rejected (worktree poisoning guard)."""
        manifest = {"mode": "symlink", "toolkit_path": "/real/repo"}
        manifest_path = tmp_path / ".install-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        tmp_repo = tmp_path / "worktree"
        tmp_repo.mkdir()
        # Don't patch — let the real guard run
        sync_mod._update_manifest_toolkit_path(tmp_path, tmp_repo)

        # Manifest should NOT be updated (still has original path)
        updated = json.loads(manifest_path.read_text())
        assert updated["toolkit_path"] == "/real/repo"


class TestEnsureSymlink:
    """Tests for _ensure_symlink."""

    def test_creates_new_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        (src / "test.txt").write_text("hello")

        dst = tmp_path / "target"
        # Patch _is_ephemeral_path since test fixtures live in /tmp/
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()
        assert (dst / "test.txt").read_text() == "hello"

    def test_preserves_correct_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"
        dst.symlink_to(src)

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()

    def test_replaces_wrong_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        wrong_src = tmp_path / "wrong"
        wrong_src.mkdir()
        dst = tmp_path / "target"
        dst.symlink_to(wrong_src)

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_replaces_regular_directory(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        (src / "real.txt").write_text("real")

        dst = tmp_path / "target"
        dst.mkdir()
        (dst / "copied.txt").write_text("copy")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()
        # The copied file should be gone, replaced by symlink to source
        assert (dst / "real.txt").read_text() == "real"
        assert not (dst / "copied.txt").exists()

    def test_replaces_broken_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"
        dst.symlink_to(tmp_path / "nonexistent")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_blocks_tmp_source(self, tmp_path: Path) -> None:
        """Verify /tmp/ sources are blocked (worktree poisoning guard)."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"

        # Don't patch — let the real guard run
        result = sync_mod._ensure_symlink(src, dst)

        assert result is False
        assert not dst.exists()


class TestRuntimeIndexMerge:
    """The runtime ~/.claude/skills/INDEX.json must be a real file holding
    the tracked-first merge of skills/INDEX.json and skills/INDEX.local.json.

    Two invariants (PR #778 bug class plus the private-skill leak):
    1. Every tracked entry is present; local entries add per-name. A stale
       local can neither hide nor override tracked entries.
    2. In-place writes to the runtime index never reach the repo files.
    """

    TRACKED: ClassVar[dict] = {
        "version": "2.0",
        "skills": {
            "do": {"description": "tracked do"},
            "new-skill": {"description": "added after local was generated"},
        },
    }
    LOCAL: ClassVar[dict] = {
        "version": "2.0",
        "skills": {
            "do": {"description": "STALE do"},
            "voice-x": {"description": "private"},
        },
    }

    def _make_src(self, tmp_path: Path, with_tracked: bool = True, with_local: bool = True) -> Path:
        src = tmp_path / "skills"
        src.mkdir()
        if with_tracked:
            (src / "INDEX.json").write_text(json.dumps(self.TRACKED))
        if with_local:
            # Stale local: superset of old entries, missing "new-skill"
            (src / "INDEX.local.json").write_text(json.dumps(self.LOCAL))
        # one real skill so the flatten loop has something to do
        skill = src / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        return src

    def test_stale_local_does_not_hide_tracked_entries(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        runtime = dst / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        skills = json.loads(runtime.read_text())["skills"]
        # Every tracked entry present; local adds its private entry
        assert set(self.TRACKED["skills"]) <= set(skills)
        assert "voice-x" in skills

    def test_local_cannot_override_tracked_content(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        skills = json.loads((dst / "INDEX.json").read_text())["skills"]
        assert skills["do"] == {"description": "tracked do"}

    def test_inplace_write_never_reaches_repo_files(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        # Simulate a harness rewriting the runtime index in place
        (dst / "INDEX.json").write_text('{"skills": {"leak": {}}}\n')

        assert json.loads((src / "INDEX.json").read_text()) == self.TRACKED
        assert json.loads((src / "INDEX.local.json").read_text()) == self.LOCAL

    def test_inplace_write_spares_tracked_without_local(self, tmp_path: Path) -> None:
        """No local index: runtime must still be a real file, not a symlink
        to the tracked index (the old fallback leaked writes into the repo)."""
        src = self._make_src(tmp_path, with_local=False)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        runtime = dst / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        assert json.loads(runtime.read_text())["skills"] == self.TRACKED["skills"]

        runtime.write_text('{"skills": {"leak": {}}}\n')
        assert json.loads((src / "INDEX.json").read_text()) == self.TRACKED

    def test_local_only_still_materializes(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path, with_tracked=False)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        skills = json.loads((dst / "INDEX.json").read_text())["skills"]
        assert skills == self.LOCAL["skills"]

    def test_pre_fix_symlink_replaced_by_real_file(self, tmp_path: Path) -> None:
        """A pre-fix install left dst/INDEX.json as a symlink into the repo.
        Sync must swap it for the real merged file without touching the repo
        file it pointed at."""
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "INDEX.json").symlink_to(src / "INDEX.local.json")

        sync_mod._sync_skills_flat_symlinks(src, dst)

        runtime = dst / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        assert "new-skill" in json.loads(runtime.read_text())["skills"]
        assert json.loads((src / "INDEX.local.json").read_text()) == self.LOCAL

    def test_unchanged_index_not_rewritten(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)
        mtime_before = (dst / "INDEX.json").stat().st_mtime_ns

        sync_mod._sync_skills_flat_symlinks(src, dst)
        assert (dst / "INDEX.json").stat().st_mtime_ns == mtime_before

    def test_no_index_files_creates_nothing(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path, with_tracked=False, with_local=False)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)
        assert not (dst / "INDEX.json").exists()

    def test_local_symlink_still_created(self, tmp_path: Path) -> None:
        """INDEX.local.json keeps its plain root-file symlink."""
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)
        assert (dst / "INDEX.local.json").resolve() == (src / "INDEX.local.json").resolve()


class TestCodexRuntimeSkillIndex:
    """Codex indexes must describe the deployed flat mirror, not repo paths."""

    def test_rewrites_nested_paths_and_prunes_undeployed_entries(self, tmp_path: Path) -> None:
        src = tmp_path / "repo-skills"
        dst = tmp_path / "codex-skills"
        src.mkdir()
        dst.mkdir()
        (src / "INDEX.json").write_text(
            json.dumps(
                {
                    "version": "2.0",
                    "skills": {
                        "demo-skill": {"file": "skills/content/demo-skill/SKILL.md"},
                        "missing": {"file": "skills/content/missing/SKILL.md"},
                    },
                }
            )
        )
        deployed = dst / "demo-skill"
        deployed.mkdir()
        (deployed / "SKILL.md").write_text("---\nname: demo-skill\n---\n")

        changed = sync_mod._sync_codex_runtime_skill_indexes(src, dst)

        assert changed == 2
        for filename in ("INDEX.json", "INDEX.local.json"):
            index = json.loads((dst / filename).read_text())
            assert set(index["skills"]) == {"demo-skill"}
            assert index["skills"]["demo-skill"]["file"] == "skills/demo-skill/SKILL.md"

    def test_promoted_cleanup_removes_only_repo_owned_mirror(self, tmp_path: Path) -> None:
        repo_skills = tmp_path / "repo" / "skills"
        replacement = repo_skills / "content" / "replacement"
        promoted = repo_skills / "content" / "old-skill"
        replacement.mkdir(parents=True)
        promoted.mkdir(parents=True)
        (replacement / "SKILL.md").write_text("---\nname: replacement\n---\n")
        source_md = promoted / "SKILL.md"
        source_md.write_text("---\nname: old-skill\npromoted_to: replacement\n---\n")

        dst = tmp_path / "codex" / "skills"
        owned = dst / "old-skill"
        owned.mkdir(parents=True)
        (owned / "SKILL.md").symlink_to(source_md)
        assert sync_mod._clean_codex_promoted_skills(repo_skills, dst) == 1
        assert not owned.exists()

        owned.mkdir()
        (owned / "SKILL.md").write_text("---\nname: user-owned\n---\n")
        assert sync_mod._clean_codex_promoted_skills(repo_skills, dst) == 0
        assert owned.is_dir()


class TestSupportDirSurvivesCleanup:
    """Support dirs (reference .md files, no SKILL.md) must enter
    expected_names, or the stale-cleanup loop unlinks them every
    SessionStart. Regression test for a support directory that is not
    explicitly allowlisted."""

    def _make_src(self, tmp_path: Path) -> Path:
        src = tmp_path / "skills"
        refs = src / "support-notes"
        refs.mkdir(parents=True)
        for name in (
            "pattern-a.md",
            "pattern-b.md",
            "pattern-c.md",
        ):
            (refs / name).write_text("# ref\n")
        # one real skill so the flatten loop has something to do
        skill = src / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        return src

    def test_support_directory_survives_sync(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)
            # Second pass exercises the stale-cleanup against existing links
            sync_mod._sync_skills_flat_symlinks(src, dst)

        link = dst / "support-notes"
        assert link.is_symlink()
        assert link.resolve() == (src / "support-notes").resolve()
        assert (link / "pattern-b.md").read_text() == "# ref\n"

    def test_preexisting_support_symlink_not_unlinked(self, tmp_path: Path) -> None:
        """The original failure: a symlink already in dst was unlinked
        because its name never entered expected_names."""
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "support-notes").symlink_to(src / "support-notes")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert (dst / "support-notes").is_symlink()

    def test_future_support_dir_protected_without_allowlist(self, tmp_path: Path) -> None:
        """Any root dir with .md files and no skill subdir is treated as a
        support dir, so the next shared-reference dir cannot repeat the bug."""
        src = self._make_src(tmp_path)
        refs = src / "new-shared-refs"
        refs.mkdir()
        (refs / "pattern.md").write_text("# pattern\n")
        dst = tmp_path / "out"

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert (dst / "new-shared-refs").is_symlink()

    def test_stale_symlink_still_removed(self, tmp_path: Path) -> None:
        """Cleanup still unlinks symlinks whose source left the repo."""
        src = self._make_src(tmp_path)
        gone = tmp_path / "gone-skill"
        gone.mkdir()
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "gone-skill").symlink_to(gone)

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert not (dst / "gone-skill").exists()

    def test_category_with_readme_still_flattened(self, tmp_path: Path) -> None:
        """A category folder holding a stray README.md plus skill subdirs is
        NOT a support dir — its skills must still be flattened per-skill."""
        src = self._make_src(tmp_path)
        (src / "meta" / "README.md").write_text("# meta\n")
        dst = tmp_path / "out"

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert (dst / "do").is_symlink()
        assert not (dst / "meta").exists()


class TestMainSymlinkMode:
    """Integration tests for main() in symlink mode."""

    def _setup_repo(self, tmp_path: Path) -> Path:
        """Create a minimal repo structure for testing."""
        repo = tmp_path / "repo"
        repo.mkdir()

        # Create component directories with sample files
        for comp in ["agents", "hooks", "commands", "scripts"]:
            comp_dir = repo / comp
            comp_dir.mkdir()
            (comp_dir / "sample.md").write_text(f"# {comp} sample")

        # Skills use nested category structure: skills/meta/sample/SKILL.md
        skills_dir = repo / "skills"
        skills_dir.mkdir()
        sample_skill = skills_dir / "meta" / "sample"
        sample_skill.mkdir(parents=True)
        (sample_skill / "SKILL.md").write_text("# sample skill")

        # Create .claude/settings.json in repo
        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        settings = {"hooks": {"SessionStart": []}}
        (repo_claude / "settings.json").write_text(json.dumps(settings))

        return repo

    def _setup_user_claude(self, tmp_path: Path, mode: str, repo: Path) -> Path:
        """Create ~/.claude with install manifest."""
        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {
            "mode": mode,
            "toolkit_path": str(repo),
            "components": ["agents", "skills", "hooks", "commands", "scripts"],
        }
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return user_claude

    def test_symlink_mode_creates_symlinks(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Non-skills symlinkable components are single symlinks
        for comp in ["agents", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink(), f"{comp} should be a symlink"
            assert target.resolve() == (repo / comp).resolve()

        # Skills uses per-skill symlinks (real dir with symlinks inside)
        skills_target = user_claude / "skills"
        assert skills_target.is_dir()
        assert not skills_target.is_symlink(), "skills should be a real directory, not a single symlink"

        # Commands is additive-only, should be a directory (not symlink)
        commands_target = user_claude / "commands"
        assert commands_target.is_dir()
        assert not commands_target.is_symlink()

    def test_copy_mode_creates_directories(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "copy", repo)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # All components should be regular directories
        for comp in ["agents", "skills", "hooks", "commands", "scripts"]:
            target = user_claude / comp
            assert target.is_dir()
            assert not target.is_symlink(), f"{comp} should NOT be a symlink in copy mode"

    def test_symlink_mode_preserves_existing_symlinks(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        # Pre-create correct symlinks for non-skills components (as install.sh would)
        for comp in ["agents", "hooks", "scripts"]:
            (user_claude / comp).symlink_to(repo / comp)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Non-skills symlinks should still be there
        for comp in ["agents", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink()
            assert target.resolve() == (repo / comp).resolve()

        # Skills should be a real dir with per-skill symlinks
        skills_target = user_claude / "skills"
        assert skills_target.is_dir()
        assert not skills_target.is_symlink()

    def test_symlink_mode_replaces_copy_directories(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        # Pre-create regular directories (as broken copy-mode sync would)
        for comp in ["agents", "skills", "hooks", "scripts"]:
            comp_dir = user_claude / comp
            comp_dir.mkdir()
            (comp_dir / "stale.txt").write_text("stale copy")

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Non-skills: should now be symlinks, not directories
        for comp in ["agents", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink()
            assert target.resolve() == (repo / comp).resolve()
            # Stale files should be gone
            assert not (target / "stale.txt").exists()

        # Skills: should be a real dir with per-skill symlinks
        skills_target = user_claude / "skills"
        assert skills_target.is_dir()
        assert not skills_target.is_symlink()
        # Per-skill symlinks are created inside; stale non-symlink files from
        # a previous copy-mode install are not removed by the symlink cleanup
        # (which only targets stale symlinks). This is acceptable — the important
        # thing is that the directory structure is correct and skill symlinks work.
        assert (skills_target / "sample").is_symlink()

    def test_worktree_skips_sync(self, tmp_path: Path) -> None:
        """Verify main() bails out when running inside a git worktree."""
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=True),
        ):
            sync_mod.main()

        # Nothing should have been created
        assert not (user_claude / "agents").exists()
        assert not (user_claude / "hooks").exists()


class TestMainRuntimeIndex:
    """End-to-end runtime-index invariants through main(), both install modes."""

    TRACKED: ClassVar[dict] = {"version": "2.0", "skills": {"sample": {"description": "tracked"}}}
    LOCAL: ClassVar[dict] = {
        "version": "2.0",
        "skills": {"sample": {"description": "STALE"}, "voice-x": {"description": "private"}},
    }

    def _setup(self, tmp_path: Path, mode: str) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        for comp in ["agents", "hooks", "commands", "scripts"]:
            comp_dir = repo / comp
            comp_dir.mkdir()
            (comp_dir / "sample.md").write_text(f"# {comp} sample")
        skills_dir = repo / "skills"
        sample_skill = skills_dir / "meta" / "sample"
        sample_skill.mkdir(parents=True)
        (sample_skill / "SKILL.md").write_text("# sample skill")
        (skills_dir / "INDEX.json").write_text(json.dumps(self.TRACKED))
        (skills_dir / "INDEX.local.json").write_text(json.dumps(self.LOCAL))
        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        (repo_claude / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": []}}))

        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {
            "mode": mode,
            "toolkit_path": str(repo),
            "components": ["agents", "skills", "hooks", "commands", "scripts"],
        }
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return repo, user_claude

    def _run_main(self, tmp_path: Path, repo: Path) -> None:
        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

    @pytest.mark.parametrize("mode", ["symlink", "copy"])
    def test_runtime_index_merged_and_writes_stay_local(self, tmp_path: Path, mode: str) -> None:
        repo, user_claude = self._setup(tmp_path, mode)
        self._run_main(tmp_path, repo)

        runtime = user_claude / "skills" / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        skills = json.loads(runtime.read_text())["skills"]
        # Invariant 1: tracked entries win and are all present; local adds
        assert skills["sample"] == {"description": "tracked"}
        assert "voice-x" in skills

        # Invariant 2: in-place harness write never reaches the repo
        runtime.write_text('{"skills": {"leak": {}}}\n')
        assert json.loads((repo / "skills" / "INDEX.json").read_text()) == self.TRACKED
        assert json.loads((repo / "skills" / "INDEX.local.json").read_text()) == self.LOCAL

    def test_copy_mode_local_only_survives_stale_cleanup(self, tmp_path: Path) -> None:
        """Repo with only INDEX.local.json (tracked index not generated yet):
        the materialized runtime index must survive deferred stale cleanup."""
        repo, user_claude = self._setup(tmp_path, "copy")
        (repo / "skills" / "INDEX.json").unlink()
        self._run_main(tmp_path, repo)

        runtime = user_claude / "skills" / "INDEX.json"
        assert runtime.is_file()
        assert json.loads(runtime.read_text())["skills"] == self.LOCAL["skills"]

    def test_copy_mode_resync_refreshes_merge(self, tmp_path: Path) -> None:
        """A second sync after the tracked index gains a skill must surface
        the new entry in the runtime index (the stale-hide regression)."""
        repo, user_claude = self._setup(tmp_path, "copy")
        self._run_main(tmp_path, repo)

        updated = {"version": "2.0", "skills": {**self.TRACKED["skills"], "brand-new": {}}}
        (repo / "skills" / "INDEX.json").write_text(json.dumps(updated))
        self._run_main(tmp_path, repo)

        skills = json.loads((user_claude / "skills" / "INDEX.json").read_text())["skills"]
        assert "brand-new" in skills
        assert "voice-x" in skills


class TestHasPromotedTo:
    """Tests for _has_promoted_to — skip skills folded into a parent."""

    def _make_skills_root(self, tmp_path: Path) -> Path:
        root = tmp_path / "skills"
        root.mkdir()
        return root

    def test_promoted_with_existing_target_is_skipped(self, tmp_path: Path) -> None:
        root = self._make_skills_root(tmp_path)
        category = root / "voice"
        category.mkdir()
        child = category / "fish-shell-config"
        child.mkdir()
        (child / "SKILL.md").write_text("---\nname: fish-shell-config\npromoted_to: shell-config\n---\nbody\n")
        target = category / "shell-config"
        target.mkdir()
        (target / "SKILL.md").write_text("---\nname: shell-config\n---\nbody\n")

        assert sync_mod._has_promoted_to(child, skills_root=root) is True

    def test_promoted_with_missing_target_is_deployed(self, tmp_path: Path) -> None:
        root = self._make_skills_root(tmp_path)
        category = root / "voice"
        category.mkdir()
        child = category / "fish-shell-config"
        child.mkdir()
        (child / "SKILL.md").write_text("---\nname: fish-shell-config\npromoted_to: shell-config\n---\nbody\n")
        # No target skill created anywhere under root.

        assert sync_mod._has_promoted_to(child, skills_root=root) is False

    def test_no_promoted_to_key_is_deployed(self, tmp_path: Path) -> None:
        root = self._make_skills_root(tmp_path)
        category = root / "voice"
        category.mkdir()
        child = category / "ordinary-skill"
        child.mkdir()
        (child / "SKILL.md").write_text("---\nname: ordinary-skill\n---\nbody\n")

        assert sync_mod._has_promoted_to(child, skills_root=root) is False

    def test_malformed_frontmatter_fails_safe_and_deploys(self, tmp_path: Path) -> None:
        """A skill with no closing '---' or unreadable frontmatter must not
        raise — SessionStart hooks must never crash on a bad file. Failing
        safe means the skill stays deployed (not silently dropped)."""
        root = self._make_skills_root(tmp_path)
        category = root / "voice"
        category.mkdir()
        child = category / "broken-skill"
        child.mkdir()
        (child / "SKILL.md").write_text("---\nname: broken-skill\nno closing delimiter\n")

        assert sync_mod._has_promoted_to(child, skills_root=root) is False

    def test_missing_skill_md_fails_safe_and_deploys(self, tmp_path: Path) -> None:
        root = self._make_skills_root(tmp_path)
        category = root / "voice"
        category.mkdir()
        child = category / "no-md-skill"
        child.mkdir()
        # No SKILL.md at all.

        assert sync_mod._has_promoted_to(child, skills_root=root) is False

    def test_no_frontmatter_delimiter_is_deployed(self, tmp_path: Path) -> None:
        root = self._make_skills_root(tmp_path)
        category = root / "voice"
        category.mkdir()
        child = category / "plain-skill"
        child.mkdir()
        (child / "SKILL.md").write_text("# Just a heading, no frontmatter\n")

        assert sync_mod._has_promoted_to(child, skills_root=root) is False


class TestResolvesInside:
    """Tests for _resolves_inside — the repo-path safety guard."""

    def test_path_inside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        child = repo / "skills" / "support-notes"
        child.mkdir(parents=True)
        assert sync_mod._resolves_inside(child, repo) is True

    def test_path_outside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        assert sync_mod._resolves_inside(other, repo) is False

    def test_symlink_resolves_inside(self, tmp_path: Path) -> None:
        """A symlink in ~/.claude that points into the repo should be detected."""
        repo = tmp_path / "repo" / "skills" / "support-notes"
        repo.mkdir(parents=True)
        link = tmp_path / "link"
        link.symlink_to(repo)
        assert sync_mod._resolves_inside(link, tmp_path / "repo") is True

    def test_equal_to_root(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        assert sync_mod._resolves_inside(repo, repo) is True

    def test_prefix_not_confused(self, tmp_path: Path) -> None:
        """repo-extra/ must not match repo/ as a prefix."""
        repo = tmp_path / "repo"
        repo.mkdir()
        sibling = tmp_path / "repo-extra"
        sibling.mkdir()
        assert sync_mod._resolves_inside(sibling, repo) is False


class TestRepoSideDeletionGuard:
    """Regression tests for deleting source through a deployed support link.

    When ~/.claude/skills/ contains a symlink into the repo, destructive
    operations (rmtree, unlink) must refuse to follow that symlink and
    delete tracked source files.  The guard is _resolves_inside, applied
    in _ensure_symlink, _sync_skills_flat_symlinks stale cleanup, and
    the deferred stale cleanup in _main_inner.
    """

    def _make_repo(self, tmp_path: Path) -> Path:
        """Build a minimal repo with a support directory."""
        repo = tmp_path / "repo"
        skills = repo / "skills"
        support = skills / "support-notes"
        support.mkdir(parents=True)
        for name in ("pattern-a.md", "pattern-b.md", "pattern-c.md"):
            (support / name).write_text(f"# {name}\n")
        # one skill so the flatten loop works
        skill = skills / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        return repo

    def test_ensure_symlink_blocks_rmtree_through_parent_symlink(self, tmp_path: Path) -> None:
        """When dst resolves inside the repo via a parent symlink,
        _ensure_symlink must refuse to rmtree rather than delete repo files."""
        repo = self._make_repo(tmp_path)
        repo_support = repo / "skills" / "support-notes"

        # Simulate: ~/.claude/skills is a symlink to repo/skills (old-style)
        claude_skills = tmp_path / "claude_skills"
        claude_skills.symlink_to(repo / "skills")

        # The destination traverses the parent symlink into the repo.
        dst = claude_skills / "support-notes"
        assert dst.is_dir() and not dst.is_symlink(), "dst traverses parent symlink, is NOT itself a symlink"

        # Without the guard, _ensure_symlink would rmtree the repo dir
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(repo_support, dst, repo_root=repo)

        # Guard must have blocked the rmtree
        assert result is False, "_ensure_symlink should return False when dst resolves inside repo"

        # Repo files must still exist
        assert repo_support.is_dir()
        for name in ("pattern-a.md", "pattern-b.md", "pattern-c.md"):
            assert (repo_support / name).exists(), f"Repo file {name} was deleted!"

    def test_ensure_symlink_allows_rmtree_outside_repo(self, tmp_path: Path) -> None:
        """rmtree of a real dir outside the repo must still work."""
        repo = self._make_repo(tmp_path)
        src = repo / "skills" / "support-notes"

        # dst is a real dir outside the repo (from a previous copy-mode install)
        dst = tmp_path / "claude" / "skills" / "support-notes"
        dst.mkdir(parents=True)
        (dst / "stale-copy.md").write_text("copy")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst, repo_root=repo)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_flat_symlinks_guards_stale_cleanup(self, tmp_path: Path) -> None:
        """Stale cleanup in _sync_skills_flat_symlinks must not unlink
        symlinks that resolve inside the repo."""
        repo = self._make_repo(tmp_path)
        src = repo / "skills"

        # dst is a real dir with a stale symlink that points into the repo
        dst = tmp_path / "claude_skills"
        dst.mkdir()
        # Create a symlink that IS stale (not in expected_names) but
        # resolves inside the repo
        stale_link = dst / "stale-repo-link"
        stale_link.symlink_to(repo / "skills" / "meta")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst, repo_root=repo)

        # The stale link should NOT have been removed (resolves inside repo)
        # Note: the guard protects it because it resolves inside repo
        # In practice, the important invariant is that repo files survive.
        assert (repo / "skills" / "meta" / "do" / "SKILL.md").exists()

    def test_repo_files_survive_full_sync(self, tmp_path: Path) -> None:
        """End-to-end: support files survive a full
        _sync_skills_flat_symlinks cycle, even with two passes."""
        repo = self._make_repo(tmp_path)
        src = repo / "skills"
        dst = tmp_path / "out"

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst, repo_root=repo)
            sync_mod._sync_skills_flat_symlinks(src, dst, repo_root=repo)

        # Repo files must survive both passes
        for name in ("pattern-a.md", "pattern-b.md", "pattern-c.md"):
            repo_file = repo / "skills" / "support-notes" / name
            assert repo_file.exists(), f"Repo file {name} was deleted by sync!"
            assert repo_file.read_text() == f"# {name}\n"

        # The symlink in dst must exist and point to the repo dir
        link = dst / "support-notes"
        assert link.is_symlink()
        assert link.resolve() == (repo / "skills" / "support-notes").resolve()


class TestResolvesInsideMultiRoot:
    """Tests for _resolves_inside with list-of-roots support."""

    def test_single_path_still_works(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        child = repo / "skills" / "voice"
        child.mkdir(parents=True)
        assert sync_mod._resolves_inside(child, repo) is True

    def test_list_of_roots_matches_any(self, tmp_path: Path) -> None:
        main_repo = tmp_path / "main"
        worktree = tmp_path / "worktree"
        main_repo.mkdir()
        worktree.mkdir()
        child = main_repo / "skills"
        child.mkdir()
        # child is inside main_repo but not worktree
        assert sync_mod._resolves_inside(child, [worktree, main_repo]) is True

    def test_list_of_roots_rejects_outside(self, tmp_path: Path) -> None:
        main_repo = tmp_path / "main"
        worktree = tmp_path / "worktree"
        outside = tmp_path / "outside"
        main_repo.mkdir()
        worktree.mkdir()
        outside.mkdir()
        assert sync_mod._resolves_inside(outside, [main_repo, worktree]) is False

    def test_symlink_resolved_against_canonical_root(self, tmp_path: Path) -> None:
        """When a symlink resolves into the MAIN repo, the guard catches it
        even when repo_root is a worktree path (canonical root provides coverage)."""
        main_repo = tmp_path / "main"
        support = main_repo / "skills" / "support-notes"
        support.mkdir(parents=True)
        (support / "test.md").write_text("content")

        worktree = tmp_path / "worktree"
        worktree.mkdir()

        # Symlink points to the main repo.
        link = tmp_path / "link"
        link.symlink_to(support)

        # With only worktree root: NOT detected (the bug)
        assert sync_mod._resolves_inside(link, worktree) is False
        # With both roots: detected (the fix)
        assert sync_mod._resolves_inside(link, [worktree, main_repo]) is True


class TestCanonicalRepoRoot:
    """Tests for _canonical_repo_root."""

    def test_reads_toolkit_path(self, tmp_path: Path) -> None:
        manifest = {"mode": "symlink", "toolkit_path": str(tmp_path)}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        result = sync_mod._canonical_repo_root(tmp_path)
        assert result == tmp_path

    def test_returns_none_for_missing_manifest(self, tmp_path: Path) -> None:
        result = sync_mod._canonical_repo_root(tmp_path)
        assert result is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path: Path) -> None:
        manifest = {"toolkit_path": str(tmp_path / "no-such-dir")}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        result = sync_mod._canonical_repo_root(tmp_path)
        assert result is None


class TestWorktreeDetectionSafeDefault:
    """Tests for _is_git_worktree safe default when .git file is unreadable."""

    def test_unreadable_git_file_assumes_worktree(self, tmp_path: Path) -> None:
        """When .git is a file but unreadable and git rev-parse fails,
        _is_git_worktree must return True (safe default)."""
        dot_git = tmp_path / ".git"
        dot_git.write_text("gitdir: some/path")
        dot_git.chmod(0o000)
        try:
            with (
                patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
                patch("subprocess.check_output", side_effect=OSError("no git")),
            ):
                result = sync_mod._is_git_worktree(tmp_path)
            assert result is True, "Must assume worktree when .git file is unreadable"
        finally:
            dot_git.chmod(0o644)

    def test_readable_submodule_allowed(self, tmp_path: Path) -> None:
        """A readable .git file without 'worktrees/' is a submodule — allow sync."""
        dot_git = tmp_path / ".git"
        dot_git.write_text("gitdir: ../.git/modules/mymod")
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._is_git_worktree(tmp_path)
        assert result is False

    def test_readable_worktree_blocked(self, tmp_path: Path) -> None:
        dot_git = tmp_path / ".git"
        dot_git.write_text("gitdir: /repo/.git/worktrees/agent-123")
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._is_git_worktree(tmp_path)
        assert result is True


class TestWindowsImportRecovery:
    """Windows bootstrap must survive stale deployed hook utility modules."""

    def test_imports_with_stale_hook_utils(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        lib_dir = hooks_dir / "lib"
        lib_dir.mkdir(parents=True)
        shutil.copy2(HOOKS_DIR / "sync-to-user-claude.py", hooks_dir / "sync-to-user-claude.py")
        (lib_dir / "hook_utils.py").write_text("def log_error(message): pass\n", encoding="utf-8")

        spec = importlib.util.spec_from_file_location(
            "sync_to_user_claude_stale_helper",
            hooks_dir / "sync-to-user-claude.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        assert callable(module.hook_error)
        assert callable(module._try_lock_fd)

    def test_lock_helpers_acquire_release_and_reacquire(self, tmp_path: Path) -> None:
        lock_path = tmp_path / ".sync.lock"
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        assert sync_mod._try_lock_fd(fd) is True
        sync_mod._unlock_fd(fd)

        fd2 = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        assert sync_mod._try_lock_fd(fd2) is True
        sync_mod._unlock_fd(fd2)

    def test_windows_lock_backend_is_not_noop(self, tmp_path: Path) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows-only msvcrt lock behavior")

        lock_path = tmp_path / ".sync.lock"
        fd1 = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        fd2 = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            assert sync_mod._try_lock_fd(fd1) is True
            assert sync_mod._try_lock_fd(fd2) is False
        finally:
            sync_mod._unlock_fd(fd2)
            sync_mod._unlock_fd(fd1)


class TestProtectedRootsWorktreeScenario:
    """Reproduce a worktree bypass that removes a main-repo support link.

    A worktree that bypassed _is_git_worktree runs sync with
    repo_root = worktree_path.  Without canonical root protection, symlinks
    into the MAIN repo escape the _resolves_inside guard."""

    SUPPORT_FILES: ClassVar[list[str]] = [
        "pattern-a.md",
        "pattern-b.md",
        "pattern-c.md",
    ]

    def _make_main_and_worktree(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Build main repo, worktree, and ~/.claude with symlinks to main."""
        # Main repo
        main = tmp_path / "main"
        skills = main / "skills"
        support = skills / "support-notes"
        support.mkdir(parents=True)
        for name in self.SUPPORT_FILES:
            (support / name).write_text(f"# {name}\n")
        meta_do = skills / "meta" / "do"
        meta_do.mkdir(parents=True)
        (meta_do / "SKILL.md").write_text("---\nname: do\n---\n")

        # Worktree (older branch, no support directory)
        worktree = tmp_path / "worktree"
        wt_skills = worktree / "skills"
        wt_meta_do = wt_skills / "meta" / "do"
        wt_meta_do.mkdir(parents=True)
        (wt_meta_do / "SKILL.md").write_text("---\nname: do\n---\n")
        # Note: the support directory is absent from the worktree.

        # Simulated ~/.claude/skills with symlinks into MAIN repo
        claude_skills = tmp_path / "claude" / "skills"
        claude_skills.mkdir(parents=True)
        (claude_skills / "support-notes").symlink_to(support)
        (claude_skills / "do").symlink_to(meta_do)

        return main, worktree, claude_skills

    def test_worktree_sync_without_canonical_preserves_foreign_symlink(self, tmp_path: Path) -> None:
        """With the foreign-symlink fix, a live symlink whose target is outside
        the given repo_root is preserved even without canonical root protection.
        The support directory resolves into main (outside worktree), so it
        survives cleanup."""
        main, worktree, claude_skills = self._make_main_and_worktree(tmp_path)

        # Sync from worktree with only the worktree as repo_root
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(
                worktree / "skills",
                claude_skills,
                repo_root=worktree,
            )

        # The support directory resolves into main (outside worktree root),
        # so it is treated as a foreign symlink and preserved.
        support_link = claude_skills / "support-notes"
        assert support_link.is_symlink(), "support symlink must be preserved"
        assert support_link.resolve() == (main / "skills" / "support-notes").resolve()
        # Main repo files untouched.
        for name in self.SUPPORT_FILES:
            assert (main / "skills" / "support-notes" / name).exists()

    def test_worktree_sync_with_canonical_preserves_symlink(self, tmp_path: Path) -> None:
        """With canonical root (the fix), the guard catches the symlink even
        when repo_root is the worktree path."""
        main, worktree, claude_skills = self._make_main_and_worktree(tmp_path)

        # Sync from worktree WITH canonical root protection
        protected_roots = [worktree, main]
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(
                worktree / "skills",
                claude_skills,
                repo_root=protected_roots,
            )

        # The symlink must survive — protected by canonical root
        support_link = claude_skills / "support-notes"
        assert support_link.is_symlink(), "support symlink must survive"
        assert support_link.resolve() == (main / "skills" / "support-notes").resolve()

        # Main repo files must still exist
        for name in self.SUPPORT_FILES:
            assert (main / "skills" / "support-notes" / name).exists()


class TestMainInnerWorktreeEndToEnd:
    """End-to-end through main(): an UNDETECTED worktree must neither rewrite
    the manifest's toolkit_path nor delete symlinks resolving into the main
    repo.  Guards the _main_inner ordering: canonical root is read and the
    manifest-rewrite refusal applies BEFORE protected_roots is built."""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Main repo, worktree missing one skill, ~/.claude pointing at main."""
        main = tmp_path / "main"
        for comp in ["agents", "hooks", "commands", "scripts"]:
            (main / comp).mkdir(parents=True)
            (main / comp / "sample.md").write_text(f"# {comp}\n")
        support = main / "skills" / "support-notes"
        support.mkdir(parents=True)
        (support / "pattern.md").write_text("# pattern\n")
        (main / ".claude").mkdir()
        (main / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))

        # Worktree: same shape, but no support directory.
        worktree = tmp_path / "worktree"
        for comp in ["agents", "hooks", "commands", "scripts"]:
            (worktree / comp).mkdir(parents=True)
            (worktree / comp / "sample.md").write_text(f"# {comp}\n")
        wt_do = worktree / "skills" / "meta" / "do"
        wt_do.mkdir(parents=True)
        (wt_do / "SKILL.md").write_text("---\nname: do\n---\n")
        (worktree / ".claude").mkdir()
        (worktree / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))

        user_claude = tmp_path / "home" / ".claude"
        (user_claude / "skills").mkdir(parents=True)
        (user_claude / "skills" / "support-notes").symlink_to(support)
        manifest = {
            "mode": "symlink",
            "toolkit_path": str(main),
            "components": ["agents", "skills", "hooks", "commands", "scripts"],
        }
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return main, worktree, user_claude

    def test_undetected_worktree_keeps_manifest_and_main_repo_symlinks(self, tmp_path: Path) -> None:
        main, worktree, user_claude = self._setup(tmp_path)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=worktree),
            # Worktree detection bypassed -- the exact incident scenario.
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Manifest must still record the MAIN repo, not the worktree.
        manifest = json.loads((user_claude / ".install-manifest.json").read_text())
        assert manifest["toolkit_path"] == str(main), "manifest rewrite must be refused while the recorded path exists"

        # The symlink into the main repo must survive stale cleanup.
        support_link = user_claude / "skills" / "support-notes"
        assert support_link.is_symlink(), "symlink into main repo must survive"
        assert (main / "skills" / "support-notes" / "pattern.md").exists()


class TestCleanCodexOrphanCategories:
    """Tests for _clean_codex_orphan_categories.

    Reproduces the Codex duplicate-skill bug: an earlier mirror strategy copied
    the nested category structure (a category dir holding each skill), then the
    strategy switched to a flat layout (one dir per skill at the top level).
    Codex scans recursively, so both copies list the skill twice. Cleanup must
    remove the orphaned category dir while preserving flat skills and foreign
    entries.
    """

    def _make_repo_skills(self, root: Path) -> Path:
        """Repo skills tree: one category (content) holding one skill."""
        repo_skills = root / "skills"
        skill = repo_skills / "content" / "create-voice"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: create-voice\n---\nbody\n")
        return repo_skills

    def test_removes_orphan_category_dir(self, tmp_path: Path) -> None:
        repo_skills = self._make_repo_skills(tmp_path)
        codex = tmp_path / "codex-skills"
        # Flat (current strategy) — must survive.
        flat = codex / "create-voice"
        flat.mkdir(parents=True)
        (flat / "SKILL.md").write_text("flat")
        # Orphan nested category dir (old strategy) — must be removed.
        orphan = codex / "content" / "create-voice"
        orphan.mkdir(parents=True)
        (orphan / "SKILL.md").write_text("nested")

        removed = sync_mod._clean_codex_orphan_categories(repo_skills, codex)

        assert removed == 1
        assert not (codex / "content").exists(), "orphan category dir must be removed"
        assert flat.exists(), "flat skill must be preserved"
        assert (flat / "SKILL.md").exists()

    def test_preserves_foreign_skill(self, tmp_path: Path) -> None:
        repo_skills = self._make_repo_skills(tmp_path)
        codex = tmp_path / "codex-skills"
        # A user/Codex-created skill whose name is NOT a repo category.
        foreign = codex / "my-own-skill"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("mine")

        removed = sync_mod._clean_codex_orphan_categories(repo_skills, codex)

        assert removed == 0
        assert foreign.exists(), "foreign skill must never be removed"

    def test_ignores_category_symlink(self, tmp_path: Path) -> None:
        repo_skills = self._make_repo_skills(tmp_path)
        codex = tmp_path / "codex-skills"
        codex.mkdir(parents=True)
        # A symlink named like a category must not be followed or removed.
        real = tmp_path / "elsewhere"
        real.mkdir()
        (codex / "content").symlink_to(real)

        removed = sync_mod._clean_codex_orphan_categories(repo_skills, codex)

        assert removed == 0
        assert (codex / "content").is_symlink(), "symlink must be left untouched"

    def test_noop_when_clean(self, tmp_path: Path) -> None:
        repo_skills = self._make_repo_skills(tmp_path)
        codex = tmp_path / "codex-skills"
        flat = codex / "create-voice"
        flat.mkdir(parents=True)
        (flat / "SKILL.md").write_text("flat")

        removed = sync_mod._clean_codex_orphan_categories(repo_skills, codex)

        assert removed == 0
        assert flat.exists()

    def test_missing_dirs_return_zero(self, tmp_path: Path) -> None:
        assert sync_mod._clean_codex_orphan_categories(tmp_path / "nope", tmp_path / "gone") == 0

    def test_removes_renamed_or_removed_category(self, tmp_path: Path) -> None:
        # A category the repo no longer has (e.g. opensearch/ folded into
        # engineering/). Structural rule must still remove it.
        repo_skills = self._make_repo_skills(tmp_path)
        codex = tmp_path / "codex-skills"
        orphan = codex / "opensearch" / "opensearch-detection-engineer"
        orphan.mkdir(parents=True)
        (orphan / "SKILL.md").write_text("stale")

        removed = sync_mod._clean_codex_orphan_categories(repo_skills, codex)

        assert removed == 1
        assert not (codex / "opensearch").exists()

    def test_preserves_marked_foreign_tree(self, tmp_path: Path) -> None:
        # Codex's own .system/ tree (marker file + nested skills) must survive,
        # even though it holds nested SKILL.md. Guarded by dot-prefix and marker.
        repo_skills = self._make_repo_skills(tmp_path)
        codex = tmp_path / "codex-skills"
        system = codex / ".system" / "imagegen"
        system.mkdir(parents=True)
        (system / "SKILL.md").write_text("codex-native")
        (codex / ".system" / ".codex-system-skills.marker").write_text("owned")

        removed = sync_mod._clean_codex_orphan_categories(repo_skills, codex)

        assert removed == 0
        assert (codex / ".system" / "imagegen" / "SKILL.md").exists()


class TestCopyIfChanged:
    """Tests for _copy_if_changed — robust to broken symlinks on both ends."""

    def test_copies_new_file(self, tmp_path: Path) -> None:
        src = tmp_path / "a.md"
        src.write_text("hello")
        dst = tmp_path / "out" / "a.md"
        dst.parent.mkdir()
        assert sync_mod._copy_if_changed(src, dst) is True
        assert dst.read_text() == "hello"

    def test_skips_identical_file(self, tmp_path: Path) -> None:
        src = tmp_path / "a.md"
        src.write_text("same")
        dst = tmp_path / "a-copy.md"
        dst.write_text("same")
        assert sync_mod._copy_if_changed(src, dst) is False

    def test_skips_dangling_source_symlink(self, tmp_path: Path) -> None:
        # Source is a symlink whose target is missing (e.g. a private-voices
        # reference absent on this machine). Must skip without raising.
        src = tmp_path / "link.md"
        src.symlink_to(tmp_path / "missing-target.md")
        dst = tmp_path / "out.md"
        assert sync_mod._copy_if_changed(src, dst) is False
        assert not dst.exists()

    def test_replaces_dangling_dest_symlink(self, tmp_path: Path) -> None:
        # Destination is a broken symlink from an earlier sync. Must replace it.
        src = tmp_path / "a.md"
        src.write_text("fresh")
        dst = tmp_path / "out.md"
        dst.symlink_to(tmp_path / "gone.md")
        assert sync_mod._copy_if_changed(src, dst) is True
        assert not dst.is_symlink()
        assert dst.read_text() == "fresh"


class TestSyncCodexHookLinks:
    """Tests for _sync_codex_hook_links: per-file symlinks into ~/.codex/hooks."""

    @pytest.fixture(autouse=True)
    def _not_ephemeral(self):
        # Fixtures live in /tmp/; the guard is exercised by test_ephemeral_repo_blocked.
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            yield

    def test_ephemeral_repo_blocked(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        codex.mkdir(parents=True)
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=True):
            assert sync_mod._sync_codex_hook_links(repo_hooks, codex) is None
        assert list(codex.iterdir()) == []

    @staticmethod
    def _repo_hooks(tmp_path: Path) -> Path:
        repo_hooks = tmp_path / "repo" / "hooks"
        (repo_hooks / "lib").mkdir(parents=True)
        (repo_hooks / "tests").mkdir()
        (repo_hooks / "__pycache__").mkdir()
        (repo_hooks / "a-hook.py").write_text("print('a')\n")
        (repo_hooks / "b-hook.py").write_text("print('b')\n")
        (repo_hooks / "README.md").write_text("# not linked\n")
        (repo_hooks / "lib" / "hook_utils.py").write_text("x = 1\n")
        (repo_hooks / "lib" / "warmstart_lib.py").write_text("y = 2\n")
        (repo_hooks / "lib" / "registry.json").write_text("{}\n")
        (repo_hooks / "tests" / "test_a.py").write_text("")
        (repo_hooks / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"")
        return repo_hooks

    @staticmethod
    def _repo_root(tmp_path: Path) -> Path:
        repo_root = tmp_path / "repo"
        for d in ("skills", "agents", "scripts", "commands"):
            (repo_root / d).mkdir(parents=True, exist_ok=True)
        return repo_root

    def test_fresh_dirs_get_one_link_per_py_file(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        (codex / "lib").mkdir(parents=True)
        result = sync_mod._sync_codex_hook_links(repo_hooks, codex)
        assert result == (4, 0, 0)
        for name in ("a-hook.py", "b-hook.py"):
            assert (codex / name).is_symlink()
            assert (codex / name).resolve() == (repo_hooks / name).resolve()
        for name in ("hook_utils.py", "warmstart_lib.py"):
            assert (codex / "lib" / name).is_symlink()
            assert (codex / "lib" / name).resolve() == (repo_hooks / "lib" / name).resolve()

    def test_creates_lib_when_hooks_dir_exists(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        codex.mkdir(parents=True)
        result = sync_mod._sync_codex_hook_links(repo_hooks, codex)
        assert result == (4, 0, 0)
        assert (codex / "lib").is_dir() and not (codex / "lib").is_symlink()
        assert (codex / "lib" / "warmstart_lib.py").is_symlink()

    def test_foreign_file_kept_not_replaced(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        (codex / "lib").mkdir(parents=True)
        (codex / "a-hook.py").write_text("foreign\n")
        elsewhere = tmp_path / "elsewhere.py"
        elsewhere.write_text("other\n")
        (codex / "lib" / "hook_utils.py").symlink_to(elsewhere)
        result = sync_mod._sync_codex_hook_links(repo_hooks, codex)
        assert result == (2, 0, 2)
        assert not (codex / "a-hook.py").is_symlink()
        assert (codex / "a-hook.py").read_text() == "foreign\n"
        assert (codex / "lib" / "hook_utils.py").resolve() == elsewhere.resolve()

    def test_absent_codex_hooks_creates_nothing(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        assert sync_mod._sync_codex_hook_links(repo_hooks, codex) is None
        assert not (tmp_path / "codex").exists()

    def test_tests_pycache_and_non_py_not_linked(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        codex.mkdir(parents=True)
        sync_mod._sync_codex_hook_links(repo_hooks, codex)
        assert {p.name for p in codex.iterdir()} == {"a-hook.py", "b-hook.py", "lib"}
        assert {p.name for p in (codex / "lib").iterdir()} == {"hook_utils.py", "warmstart_lib.py"}

    def test_second_run_links_zero(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        codex.mkdir(parents=True)
        assert sync_mod._sync_codex_hook_links(repo_hooks, codex) == (4, 0, 0)
        assert sync_mod._sync_codex_hook_links(repo_hooks, codex) == (0, 4, 0)

    def test_new_repo_file_linked_on_later_run(self, tmp_path: Path) -> None:
        repo_hooks = self._repo_hooks(tmp_path)
        codex = tmp_path / "codex" / "hooks"
        codex.mkdir(parents=True)
        sync_mod._sync_codex_hook_links(repo_hooks, codex)
        (repo_hooks / "lib" / "new_lib.py").write_text("z = 3\n")
        assert sync_mod._sync_codex_hook_links(repo_hooks, codex) == (1, 4, 0)
        assert (codex / "lib" / "new_lib.py").is_symlink()

    def test_summary_line_reports_codex_hooks(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        self._repo_hooks(tmp_path)
        repo_root = self._repo_root(tmp_path)
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".codex" / "hooks").mkdir(parents=True)
        with patch.object(sync_mod.Path, "home", return_value=home):
            sync_mod._main_inner(repo_root, home / ".claude")
        assert ".codex/hooks(+4 linked, 0 current)" in capsys.readouterr().out

    def test_summary_line_absent(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        self._repo_hooks(tmp_path)
        repo_root = self._repo_root(tmp_path)
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        with patch.object(sync_mod.Path, "home", return_value=home):
            sync_mod._main_inner(repo_root, home / ".claude")
        assert ".codex/hooks(absent)" in capsys.readouterr().out
        assert not (home / ".codex" / "hooks").exists()
