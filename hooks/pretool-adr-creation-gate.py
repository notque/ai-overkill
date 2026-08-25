#!/usr/bin/env python3
# hook-version: 1.2.1
"""
PreToolUse:Write Hook: ADR Creation Gate

Blocks creation of new agent/skill/pipeline/hook component files when no ADR
exists for that component.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Write tool.

ADR lookup order (first match wins):
1. ~/.vexjoy-agent/{repo_name}/adrs/{component_name}.md  (centralized, preferred)
2. {project_root}/adr/{component_name}.md                (legacy, backwards-compat)

repo_name is derived from: git remote origin URL → repo basename, or failing
that, the directory basename of the project root.

Detection logic:
- Tool is Write (edits to existing files pass through)
- Target path matches /agents/<name>.md, /skills/<name>/SKILL.md,
  /pipelines/<name>/SKILL.md, or /hooks/<name>.py (top level; lib/ and
  tests/ never match; hook gating applies only in toolkit-shaped repos —
  agents/ and skills/ dirs beside the hooks/ dir)
- The target file does not already exist on disk (new creation only)
- ADR not found in either lookup path

Allow-through conditions:
- Tool is not Write
- Target file does not match a component path pattern
- Target file already exists on disk (update, not creation)
- Target path matches _ADR_PATH_ALLOWLIST (producer-allowlisted skills like create-voice)
- ADR exists in centralized or project-root location
- ADR_CREATION_GATE_BYPASS=1 env var
"""

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "ADR_CREATION_GATE_BYPASS"

# Match agents/foo-bar.md → "foo-bar"
_AGENT_RE = re.compile(r"/agents/([^/]+)\.md$")
# Match skills/foo-bar/SKILL.md or skills/category/foo-bar/SKILL.md → "foo-bar"
_SKILL_RE = re.compile(r"/skills/(?:[^/]+/)?([^/]+)/SKILL\.md$")
# Match pipelines/foo-bar/SKILL.md → "foo-bar"
_PIPELINE_RE = re.compile(r"/pipelines/([^/]+)/SKILL\.md$")
# Match hooks/foo-bar.py → "foo-bar". Top-level hook files only: lib/ and
# tests/ paths carry an extra segment so [^/]+ never matches them. Hooks are
# the component class PHILOSOPHY.md calls hardest to govern — same
# ADR-before-creation rule as agents/skills/pipelines. UNLIKE the sibling
# patterns, this rule is scoped to toolkit-shaped repos (_is_toolkit_repo):
# the gate runs user-level in every repo, and a random project's hooks/ dir
# (git hooks, cookiecutter layouts) must not be denied with toolkit-specific
# ADR guidance.
_HOOK_RE = re.compile(r"/hooks/([^/]+)\.py$")


def _is_toolkit_repo(root: Path) -> bool:
    """Toolkit marker: agents/ AND skills/ dirs at the repo root.

    Same detection convention as sync-to-user-claude.py and the PR pipeline's
    toolkit-only phases. ``root`` is the directory CONTAINING the matched
    hooks/ dir, derived from the target path itself (not cwd), so a Write
    into another repo is judged by that repo's own shape.
    """
    try:
        return (root / "agents").is_dir() and (root / "skills").is_dir()
    except OSError:
        return False


# Path-shape allowlist for components whose creation is governed by an upstream
# skill's own methodology, not by a per-component ADR. Mirrors the allowlist in
# pretool-unified-gate.py:_CREATION_PATH_ALLOWLIST. Keep these two in sync —
# anything that bypasses the creation-gate also bypasses the ADR gate, because
# the upstream skill's methodology *is* the architectural justification.
#
# Maintainer note: do NOT broaden these patterns. Each entry must point to a
# path shape produced by exactly one well-known upstream skill. If a new
# component type wants in, write the producer skill first, then add the entry.
_ADR_PATH_ALLOWLIST: list[tuple[re.Pattern[str], str]] = [
    # voice-* skills are produced by `create-voice` (skills/content/create-voice/
    # SKILL.md Step 5: GENERATE). The create-voice skill itself documents the
    # voice-creation methodology; a per-voice ADR would be redundant.
    (re.compile(r"/skills/(?:[^/]+/)?voice-[^/]+/SKILL\.md$"), "create-voice"),
]


def _derive_repo_name(base_dir: Path) -> str:
    """Derive the repository name from git remote or directory basename.

    Tries `git remote get-url origin` first; falls back to the directory
    basename if git is unavailable or no remote is configured.

    NOTE: This logic is duplicated in scripts/vexjoy-adr.py (_derive_repo_name).
    Keep both in sync when modifying.

    Args:
        base_dir: The resolved project root directory.

    Returns:
        Repository name string (e.g., "vexjoy-agent", "openstack-mcp-server").
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=3,
            cwd=str(base_dir),
        )
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            # Handle both HTTPS and SSH URLs:
            # https://github.com/user/repo.git → repo
            # git@github.com:user/repo.git → repo
            name = url.rstrip("/").rsplit("/", 1)[-1]
            if name.endswith(".git"):
                name = name[:-4]
            if name:  # Guard against malformed URLs yielding empty name
                return name
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return base_dir.name


_VEXJOY_STATE_DIR = Path.home() / ".vexjoy-agent"


def _find_adr(component_name: str, base_dir: Path, debug: bool = False) -> Path | None:
    """Look up an ADR in centralized then project-root locations.

    Lookup order:
    1. ~/.vexjoy-agent/{repo_name}/adrs/{component_name}.md
    2. {base_dir}/adr/{component_name}.md

    Args:
        component_name: The component to look up.
        base_dir: Resolved project root directory.
        debug: Whether to emit debug output.

    Returns:
        Path to the ADR if found, None otherwise.
    """
    repo_name = _derive_repo_name(base_dir)

    # Preferred: centralized location
    centralized = _VEXJOY_STATE_DIR / repo_name / "adrs" / f"{component_name}.md"
    if centralized.is_file():
        if debug:
            print(f"[adr-creation-gate] ADR found (centralized): {centralized}", file=sys.stderr)
        return centralized

    # Fallback: project-root adr/ directory
    project_local = base_dir / "adr" / f"{component_name}.md"
    if project_local.is_file():
        if debug:
            print(f"[adr-creation-gate] ADR found (project-root): {project_local}", file=sys.stderr)
        return project_local

    if debug:
        print(
            f"[adr-creation-gate] ADR not found in:\n  - {centralized}\n  - {project_local}",
            file=sys.stderr,
        )
    return None


def _extract_component_name(file_path: str) -> str | None:
    """Return the component name if the path is a new agent/skill/pipeline file.

    Args:
        file_path: Absolute or relative path from the tool input.

    Returns:
        Component name string, or None if the path is not a component file.
    """
    normalised = file_path.replace("\\", "/")
    for pattern in (_AGENT_RE, _SKILL_RE, _PIPELINE_RE):
        match = pattern.search(normalised)
        if match:
            return match.group(1)
    # Hooks: match the lexically resolved path so hooks/sub/../new.py cannot
    # skip the pattern. Normalization is scoped to the hook rule so sibling
    # pattern behavior is unchanged.
    resolved = os.path.normpath(normalised).replace("\\", "/")
    match = _HOOK_RE.search(resolved)
    if match is None or match.group(1) == "__init__":
        # __init__.py is packaging, not a hook component.
        return None
    # Opt-in scoping: gate hooks only in toolkit-shaped repos (see _HOOK_RE).
    repo_root = Path(resolved[: match.start()] or "/")
    if not _is_toolkit_repo(repo_root):
        return None
    return match.group(1)


def main() -> None:
    """Run the ADR creation gate check."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Write" in settings.json prevents
    # this hook from spawning for non-Write tools.

    # Bypass env var.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[adr-creation-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check if the path matches a component pattern.
    component_name = _extract_component_name(file_path)
    if component_name is None:
        if debug:
            print(f"[adr-creation-gate] Not a component path, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # If the file already exists this is an update, not a creation — allow through.
    if Path(file_path).exists():
        if debug:
            print(
                f"[adr-creation-gate] File already exists (update), allowing: {file_path}",  # nosec: plain English
                file=sys.stderr,
            )
        sys.exit(0)

    # Path-shape allowlist: skills produced by named upstream pipelines whose
    # own methodology is the architectural justification.
    normalised = file_path.replace("\\", "/")
    for allowed_pattern, producer in _ADR_PATH_ALLOWLIST:
        if allowed_pattern.search(normalised):
            if debug:
                print(
                    f"[adr-creation-gate] Producer-allowlisted ({producer}), allowing: {file_path}",
                    file=sys.stderr,
                )
            sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    adr_path = _find_adr(component_name, base_dir, debug=bool(debug))
    if adr_path:
        sys.exit(0)

    # ADR is missing — block.
    repo_name = _derive_repo_name(base_dir)
    centralized_hint = f"~/.vexjoy-agent/{repo_name}/adrs/{component_name}.md"
    print(
        f"[adr-creation-gate] BLOCKED: Create ADR before creating new component.\n"
        f"  Preferred: {centralized_hint}\n"
        f"  Alternative: adr/{component_name}.md (project root)",
        file=sys.stderr,
    )
    print("[fix-with-skill] planning", file=sys.stderr)
    deny_tool_use(
        "PreToolUse",
        f"Create ADR at {centralized_hint} (or adr/{component_name}.md in project root) "
        "before creating this new component. [fix-with-skill] planning\n"
        "Call the Skill tool with `planning`.",
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-adr-creation-gate", e)
    finally:
        sys.exit(0)
