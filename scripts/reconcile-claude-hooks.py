#!/usr/bin/env python3
"""Reconcile installed hook wiring with what the toolkit actually ships.

Retiring a hook deletes `hooks/<name>.py`, but `~/.claude/settings.json` keeps
its entry. Every session then fires a command whose file is gone. This script
prunes those dead entries and leaves everything else alone.

Ownership is explicit, never guessed:

  shipped   basenames in the repo's `.claude/settings.json` (what we ship now)
  manifest  basenames a previous VexJoy install wrote to
            `~/.claude/.vexjoy-managed-hooks-settings` (what we used to ship)

Decision table, per registered entry:

  in shipped                      -> keep (warn if the file is missing)
  in manifest, not shipped        -> PRUNE (toolkit retired it)
  neither, file missing, and the
    command points inside the
    toolkit hooks dir             -> PRUNE (self-heal, no manifest needed)
  neither, anything else          -> keep (user-owned; never touched)

Safety hooks are never pruned. A missing safety-hook file is a broken install,
not a retirement: it is reported as an error and its entry is left wired.

Usage:
    python3 scripts/reconcile-claude-hooks.py                       # apply
    python3 scripts/reconcile-claude-hooks.py --dry-run             # report only
    python3 scripts/reconcile-claude-hooks.py --settings X --repo-settings Y
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

# Hooks that enforce safety policy. Never pruned, under any condition.
SAFETY_HOOKS = frozenset(
    {
        "pretool-branch-safety.py",
        "pretool-config-protection.py",
        "ci-merge-gate.py",
        "pretool-private-name-leak-gate.py",
        "pretool-unified-gate.py",
        "pretool-worktree-edit-guard.py",
        "security-review-hook.py",
        "pretool-prompt-injection-scanner.py",
    }
)

MANIFEST_NAME = ".vexjoy-managed-hooks-settings"
BACKUP_KEEP = 3

_PY_TOKEN = re.compile(r"[^\s\"']*\.py")


def iter_entries(settings: dict):
    """Yield (event, group, entry) for every registered hook entry."""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            groups = [groups]
        for group in groups:
            if not isinstance(group, dict):
                continue
            entries = group.get("hooks", [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict):
                    yield event, group, entry


def expand_command_path(cmd: str, home: Path, project_dir: Path | None) -> Path | None:
    """Extract the hook script path from a command and expand shell variables.

    `$HOME`, `${HOME}`, `~`, `$CLAUDE_PROJECT_DIR`, and `${CLAUDE_PROJECT_DIR}`
    are expanded before the path is returned, so callers can stat the result.
    """
    if not isinstance(cmd, str):
        return None
    match = _PY_TOKEN.search(cmd)
    if not match:
        return None
    raw = match.group(0)
    text = raw
    for var in ("${HOME}", "$HOME"):
        text = text.replace(var, str(home))
    if project_dir is not None:
        for var in ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR"):
            text = text.replace(var, str(project_dir))
    if text.startswith("~"):
        text = str(home) + text[1:]
    if "$" in text:
        # An unexpanded variable remains: we cannot prove the file is missing.
        return None
    return Path(text)


def basename_of(cmd: str) -> str:
    match = _PY_TOKEN.search(cmd or "")
    return Path(match.group(0)).name if match else ""


def read_manifest(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    out = set()
    for line in lines:
        name = line.strip()
        if name and not name.startswith("#") and "/" not in name:
            out.add(name)
    return out


def shipped_basenames(repo_settings: dict) -> set[str]:
    return {b for _e, _g, entry in iter_entries(repo_settings) if (b := basename_of(entry.get("command", "")))}


def _is_inside(path: Path, root: Path) -> bool:
    try:
        return root in path.parents or path.parent == root
    except (OSError, ValueError):
        return False


def reconcile(
    settings: dict,
    hooks_dir: Path,
    shipped: set[str] | None,
    manifest: set[str],
    home: Path,
    project_dir: Path | None = None,
) -> tuple[dict, list[dict], list[str]]:
    """Return (new_settings, pruned, problems). Pure: `settings` is not mutated."""
    result = json.loads(json.dumps(settings))
    pruned: list[dict] = []
    problems: list[str] = []

    for event, group, entry in list(iter_entries(result)):
        cmd = entry.get("command", "")
        name = basename_of(cmd)
        if not name:
            continue
        path = expand_command_path(cmd, home, project_dir)
        exists = path.exists() if path is not None else True

        if name in SAFETY_HOOKS:
            if not exists:
                problems.append(
                    f"SAFETY HOOK MISSING: {event} wires {name} but the file is absent. "
                    f"Entry kept (never pruned). Re-run install.sh to restore it."
                )
            continue

        if shipped is not None and name in shipped:
            if not exists:
                problems.append(f"{event}: {name} is shipped by the toolkit but not installed yet. Entry kept.")
            continue

        reason = None
        if name in manifest:
            reason = "toolkit no longer ships this hook"
        elif not exists and path is not None and _is_inside(path, hooks_dir):
            reason = "hook file missing from the toolkit hooks directory (self-heal)"
        elif not exists:
            problems.append(f"{event}: {name} is missing but not toolkit-owned. Entry kept (user-owned).")

        if reason:
            group["hooks"] = [e for e in group["hooks"] if e is not entry]
            pruned.append({"event": event, "hook": name, "command": cmd, "reason": reason})

    # Drop groups and events emptied by pruning.
    for event in list(result.get("hooks", {})):
        groups = result["hooks"][event]
        if not isinstance(groups, list):
            continue
        groups = [g for g in groups if not (isinstance(g, dict) and g.get("hooks") == [])]
        if groups:
            result["hooks"][event] = groups
        else:
            del result["hooks"][event]

    return result, pruned, problems


def backup_settings(settings_path: Path, keep: int = BACKUP_KEEP) -> Path | None:
    """Timestamped backup matching the install.sh convention."""
    if not settings_path.exists():
        return None
    parent = settings_path.parent
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = parent / f"{settings_path.name}.backup.{stamp}"
    try:
        shutil.copy2(settings_path, backup)
    except OSError:
        return None
    backups = sorted(parent.glob(f"{settings_path.name}.backup.*"))
    for old in backups[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass
    return backup


def write_manifest(path: Path, names: set[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    body = "".join(f"{n}\n" for n in sorted(names))
    tmp.write_text(f"# VexJoy-managed hook entries in settings.json. Do not edit.\n{body}", encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def run(
    settings_path: Path,
    repo_settings_path: Path | None,
    hooks_dir: Path,
    manifest_path: Path,
    home: Path,
    project_dir: Path | None,
    dry_run: bool,
) -> tuple[list[dict], list[str], bool]:
    """Reconcile one settings.json. Returns (pruned, problems, changed)."""
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"settings.json unreadable ({exc}); nothing reconciled."], False

    shipped: set[str] | None = None
    if repo_settings_path is not None and repo_settings_path.exists():
        try:
            shipped = shipped_basenames(json.loads(repo_settings_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            shipped = None

    manifest = read_manifest(manifest_path)
    new_settings, pruned, problems = reconcile(settings, hooks_dir, shipped, manifest, home, project_dir)

    if dry_run:
        return pruned, problems, bool(pruned)

    if pruned:
        backup_settings(settings_path)
        atomic_write_json(settings_path, new_settings)
        try:
            os.chmod(settings_path, 0o600)
        except OSError:
            pass
    if shipped is not None:
        try:
            write_manifest(manifest_path, shipped)
        except OSError as exc:
            problems.append(f"could not write managed-hooks manifest: {exc}")
    return pruned, problems, bool(pruned)


def main(argv: list[str] | None = None) -> int:
    home = Path(os.environ.get("HOME", str(Path.home())))
    repo_root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="Reconcile installed hook wiring with shipped hooks.")
    ap.add_argument("--settings", default=str(home / ".claude" / "settings.json"))
    ap.add_argument("--repo-settings", default=str(repo_root / ".claude" / "settings.json"))
    ap.add_argument("--hooks-dir", default=str(home / ".claude" / "hooks"))
    ap.add_argument("--manifest", default=None, help=f"default: <settings dir>/{MANIFEST_NAME}")
    ap.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR"))
    ap.add_argument("--dry-run", action="store_true", help="report what would be pruned, change nothing")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    settings_path = Path(args.settings)
    manifest_path = Path(args.manifest) if args.manifest else settings_path.parent / MANIFEST_NAME
    project_dir = Path(args.project_dir) if args.project_dir else None

    pruned, problems, _changed = run(
        settings_path=settings_path,
        repo_settings_path=Path(args.repo_settings) if args.repo_settings else None,
        hooks_dir=Path(args.hooks_dir),
        manifest_path=manifest_path,
        home=home,
        project_dir=project_dir,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps({"pruned": pruned, "problems": problems, "dry_run": args.dry_run}, indent=2))
        return 0

    verb = "Would prune" if args.dry_run else "Pruned"
    if pruned:
        for item in pruned:
            print(f"  {verb} {item['event']} -> {item['hook']} ({item['reason']})")
    else:
        print("  Hook wiring already matches the shipped hooks. No changes.")
    for problem in problems:
        print(f"  ! {problem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
