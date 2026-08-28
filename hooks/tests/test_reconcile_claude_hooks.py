#!/usr/bin/env python3
"""Tests for scripts/reconcile-claude-hooks.py.

Covers the incident: retiring a hook left ~/.claude/settings.json wiring a
deleted file, so every session fired a missing hook.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "reconcile-claude-hooks.py"

_spec = importlib.util.spec_from_file_location("reconcile_claude_hooks", SCRIPT)
rch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rch)


def _entry(name: str) -> dict:
    return {"type": "command", "command": f'python3 "$HOME/.claude/hooks/{name}"'}


def _settings(*names: str) -> dict:
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [_entry(n) for n in names]}]}}


def _wired(settings: dict) -> set[str]:
    return {rch.basename_of(e.get("command", "")) for _ev, _g, e in rch.iter_entries(settings)}


@pytest.fixture
def env(tmp_path):
    """A fake ~/.claude with a hooks dir, plus a fake repo settings.json."""
    home = tmp_path / "home"
    claude = home / ".claude"
    hooks = claude / "hooks"
    hooks.mkdir(parents=True)
    repo_settings = tmp_path / "repo-settings.json"
    return {
        "home": home,
        "claude": claude,
        "hooks": hooks,
        "settings": claude / "settings.json",
        "repo_settings": repo_settings,
        "manifest": claude / rch.MANIFEST_NAME,
    }


def _install(env, *names: str) -> None:
    for name in names:
        (env["hooks"] / name).write_text("#!/usr/bin/env python3\n")


def _run(env, dry_run: bool = False, repo_settings=True):
    return rch.run(
        settings_path=env["settings"],
        repo_settings_path=env["repo_settings"] if repo_settings else None,
        hooks_dir=env["hooks"],
        manifest_path=env["manifest"],
        home=env["home"],
        project_dir=None,
        dry_run=dry_run,
    )


def test_retired_toolkit_hook_is_pruned(env):
    """A hook the toolkit stopped shipping loses its settings.json entry."""
    env["settings"].write_text(json.dumps(_settings("kept.py", "retired.py")))
    env["repo_settings"].write_text(json.dumps(_settings("kept.py")))
    env["manifest"].write_text("kept.py\nretired.py\n")
    _install(env, "kept.py")

    pruned, _problems, changed = _run(env)

    assert changed
    assert [p["hook"] for p in pruned] == ["retired.py"]
    assert _wired(json.loads(env["settings"].read_text())) == {"kept.py"}


def test_user_added_hook_survives(env):
    """An entry the toolkit never owned is left alone, file present or not."""
    user_hook = env["home"] / "my-hooks" / "mine.py"
    user_hook.parent.mkdir(parents=True)
    user_hook.write_text("#\n")
    settings = _settings("kept.py")
    settings["hooks"]["PreToolUse"][0]["hooks"].append({"type": "command", "command": f'python3 "{user_hook}"'})
    settings["hooks"]["PreToolUse"][0]["hooks"].append(
        {"type": "command", "command": 'python3 "$HOME/my-hooks/gone.py"'}
    )
    settings["myCustomKey"] = {"keep": True}
    env["settings"].write_text(json.dumps(settings))
    env["repo_settings"].write_text(json.dumps(_settings("kept.py")))
    _install(env, "kept.py")

    pruned, problems, _changed = _run(env)

    assert pruned == []
    after = json.loads(env["settings"].read_text())
    assert _wired(after) == {"kept.py", "mine.py", "gone.py"}
    assert after["myCustomKey"] == {"keep": True}
    assert any("user-owned" in p for p in problems)


def test_safety_hook_is_never_pruned(env):
    """A safety hook stays wired even with no file and no shipped entry."""
    safety = sorted(rch.SAFETY_HOOKS)[0]
    env["settings"].write_text(json.dumps(_settings(safety, "retired.py")))
    env["repo_settings"].write_text(json.dumps({"hooks": {}}))
    env["manifest"].write_text(f"{safety}\nretired.py\n")

    pruned, problems, _changed = _run(env)

    assert [p["hook"] for p in pruned] == ["retired.py"]
    assert safety in _wired(json.loads(env["settings"].read_text()))
    assert any("SAFETY HOOK MISSING" in p for p in problems)


def test_broken_settings_self_heals_without_a_manifest(env):
    """Already-broken installs heal: missing file under hooks/ is pruned."""
    env["settings"].write_text(json.dumps(_settings("kept.py", "vanished.py")))
    _install(env, "kept.py")
    assert not env["manifest"].exists()

    pruned, _problems, changed = _run(env, repo_settings=False)

    assert changed
    assert [p["hook"] for p in pruned] == ["vanished.py"]
    assert _wired(json.loads(env["settings"].read_text())) == {"kept.py"}


def test_backup_is_written_before_pruning(env):
    """settings.json is backed up with the install.sh timestamp convention."""
    original = json.dumps(_settings("kept.py", "retired.py"))
    env["settings"].write_text(original)
    env["repo_settings"].write_text(json.dumps(_settings("kept.py")))
    env["manifest"].write_text("kept.py\nretired.py\n")
    _install(env, "kept.py")

    _run(env)

    backups = list(env["claude"].glob("settings.json.backup.*"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == json.loads(original)


def test_dry_run_changes_nothing(env):
    """--dry-run reports the prune without touching settings.json."""
    original = json.dumps(_settings("kept.py", "retired.py"))
    env["settings"].write_text(original)
    env["repo_settings"].write_text(json.dumps(_settings("kept.py")))
    env["manifest"].write_text("kept.py\nretired.py\n")
    _install(env, "kept.py")

    pruned, _problems, _changed = _run(env, dry_run=True)

    assert [p["hook"] for p in pruned] == ["retired.py"]
    assert env["settings"].read_text() == original
    assert list(env["claude"].glob("settings.json.backup.*")) == []


def test_healthy_settings_is_left_byte_identical(env):
    """Nothing to prune means no write, no backup — proves it is not destructive."""
    original = json.dumps(_settings("kept.py"), indent=4)
    env["settings"].write_text(original)
    env["repo_settings"].write_text(json.dumps(_settings("kept.py")))
    _install(env, "kept.py")

    pruned, _problems, changed = _run(env)

    assert pruned == [] and not changed
    assert env["settings"].read_text() == original
    assert env["manifest"].exists()


def test_manifest_records_the_shipped_set(env):
    env["settings"].write_text(json.dumps(_settings("kept.py")))
    env["repo_settings"].write_text(json.dumps(_settings("kept.py", "other.py")))
    _install(env, "kept.py")

    _run(env)

    assert rch.read_manifest(env["manifest"]) == {"kept.py", "other.py"}


def test_emptied_event_groups_are_removed(env):
    env["settings"].write_text(json.dumps(_settings("retired.py")))
    env["repo_settings"].write_text(json.dumps({"hooks": {}}))
    env["manifest"].write_text("retired.py\n")

    _run(env)

    assert json.loads(env["settings"].read_text())["hooks"] == {}


def test_expand_command_path_handles_variables(tmp_path):
    home = tmp_path / "h"
    project = tmp_path / "p"
    assert rch.expand_command_path('python3 "$HOME/.claude/hooks/a.py"', home, project) == (home / ".claude/hooks/a.py")
    assert rch.expand_command_path('python3 "${HOME}/.claude/hooks/a.py"', home, project) == (
        home / ".claude/hooks/a.py"
    )
    assert rch.expand_command_path('python3 "$CLAUDE_PROJECT_DIR/hooks/b.py"', home, project) == (
        project / "hooks/b.py"
    )
    # An unresolvable variable must not be reported as a missing file.
    assert rch.expand_command_path('python3 "$SOMETHING_ELSE/b.py"', home, None) is None
    assert rch.expand_command_path("echo hello", home, project) is None


# --- CI guard: the repo must never ship settings.json wiring a missing hook ---


def _repo_hook_path(cmd: str) -> Path | None:
    """Resolve a repo settings.json command to the repo file it wires.

    Commands use `$HOME`/`$CLAUDE_PROJECT_DIR`, so expand them before testing
    existence. `$HOME/.claude/hooks/X.py` is the deployed copy of `hooks/X.py`.
    """
    path = rch.expand_command_path(cmd, REPO_ROOT, REPO_ROOT)
    if path is None:
        return None
    text = str(path)
    marker = "/.claude/hooks/"
    if marker in text:
        return REPO_ROOT / "hooks" / text.split(marker, 1)[1]
    return path


def test_repo_settings_wires_only_hooks_that_exist():
    """CI gate: every hook wired in .claude/settings.json exists in the repo.

    This is the class of breakage that shipped: a hook was deleted but its
    settings.json entry stayed, so every user session fired a missing file.
    """
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    missing = []
    for event, _group, entry in rch.iter_entries(settings):
        cmd = entry.get("command", "")
        if not rch.basename_of(cmd):
            continue
        path = _repo_hook_path(cmd)
        if path is not None and not path.exists():
            missing.append(f"{event}: {cmd} -> {path} does not exist")
    assert not missing, ".claude/settings.json wires missing hook files:\n" + "\n".join(missing)


# --- sync-to-user-claude.py integration: every session, in or out of the repo ---

_sync_spec = importlib.util.spec_from_file_location(
    "sync_to_user_claude", REPO_ROOT / "hooks" / "sync-to-user-claude.py"
)
sync = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(sync)


def test_sync_self_heals_a_broken_install(env, monkeypatch):
    """A `git pull` that retires a hook cannot leave a session firing it."""
    env["settings"].write_text(json.dumps(_settings("kept.py", "vanished.py")))
    _install(env, "kept.py")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: env["home"]))

    sync.reconcile_installed_hooks(env["claude"], None)

    assert _wired(json.loads(env["settings"].read_text())) == {"kept.py"}


def test_sync_skips_reconcile_when_most_hooks_are_missing(env, monkeypatch):
    """A detached install (broken symlink) is not mistaken for mass retirement."""
    original = json.dumps(_settings("a.py", "b.py", "c.py", "d.py"))
    env["settings"].write_text(original)
    _install(env, "a.py")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: env["home"]))

    sync.reconcile_installed_hooks(env["claude"], None)

    assert env["settings"].read_text() == original
