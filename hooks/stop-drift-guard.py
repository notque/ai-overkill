#!/usr/bin/env python3
# hook-version: 1.1.0
"""
Stop-event drift guard (ADR: adr/stop-event-drift-guards.md)

Advisory Stop hook that catches three classes of self-inflicted toolkit
regression the moment they're introduced — at Stop, not at CI. It computes the
session's working-tree diff, decides which component classes changed, runs ONLY
the relevant existing check script, and re-wakes the session ADVISORY- only (it
never blocks) when a check actually REPORTS drift.

Toolkit-repo identity gate:
  - The whole hook no-ops unless the session cwd IS the toolkit repo itself,
    identified intrinsically by cwd/pyproject.toml declaring [project] name ==
    "vexjoy-agent" (clone-portable: not a path, remote, or env var). In any
    other repo the hook silently exits 0 before any check runs.

Relevance gate (diff file paths -> which check to run):
  - hooks/** changed                          -> smoke-test-hooks.py --ci
  - a component file ADDED/REMOVED under
    hooks/|skills/|agents/|scripts/, OR a
    count-claim doc touched (README.md,
    CLAUDE.md, docs/**)                        -> validate-doc-counts.py --json
  - skills/** or agents/** frontmatter changed -> check-routing-drift.py

Only checks whose component class actually changed run, and a check surfaces
output ONLY when it REPORTS drift — a clean session stays silent.

Correctness properties (this is security-adjacent self-improvement infra):
  - NEVER blocks. Drift surfaces via hook_utils.async_rewake (exit 2 +
    rewakeSummary on stdout, context on stderr). There is no
    permissionDecision:deny path anywhere in this hook.
  - Fail-open. ANY internal error -> exit 0, skip. A crashed guard never stalls
    a session.
  - Dedup. A byte-identical working-tree diff short-circuits via
    hook_utils.DiffDedup with its own state dir, so an unchanged diff doesn't
    re-nag across consecutive Stop events.
  - Recursion guard. stop_hook_active (CC sets it while a rewake is in flight)
    short-circuits so the rewake itself can't loop.

Kill switch:
  - VEXJOY_DRIFT_GUARD_DISABLE=1  disables the hook entirely (and ONLY "1";
    "0" / anything else does not disable).

The hook owns no detection logic of its own — it delegates to the three existing
scripts (scripts/smoke-test-hooks.py, scripts/validate-doc-counts.py,
scripts/check-routing-drift.py). A script that errors or can't run is treated as
"no drift" (fail-open), never as drift.

Module seams (patched by hooks/tests/test_stop_drift_guard.py):
  - read_stdin(timeout=...)         (imported from stdin_timeout)
  - _working_tree_diff(cwd) -> str  (thin wrapper over hook_utils.working_tree_diff)
  - _has_reviewable_content(diff)   (front gate; True if the diff has any signal)
  - _run_check(name, cwd) -> {"drift": bool, "detail": str, "fix": str}
                                     | {"drift": False} | None
  - _STATE_DIR, _STATE_FILE         (Path constants for DiffDedup)
  - main()                          (stdin -> dispatch on hook_event_name == "Stop")
"""

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import (
    DiffDedup,
    async_rewake,
    hook_error,
    working_tree_diff,
)
from stdin_timeout import read_stdin

_DISABLE_ENV = "VEXJOY_DRIFT_GUARD_DISABLE"
_TRUSTED_ROOT = Path(__file__).resolve().parent.parent

# Stop-event dedup state. Absolute path so it works from any cwd the harness
# fires in. Own state dir so this guard's dedup never collides with another hook.
_STATE_DIR = Path.home() / ".claude" / "state" / "stop-drift-guard"
_STATE_FILE = _STATE_DIR / "last-diff-hash.json"

# Canonical check names — these are the keys _run_check dispatches on and the
# keys the test-suite patches against.
SMOKE = "smoke-test-hooks"
DOC_COUNTS = "validate-doc-counts"
ROUTING = "check-routing-drift"

# Component class roots. A file ADDED or REMOVED under any of these flips a
# count claim -> doc-counts. (Modifying an existing file does not change counts.)
_COMPONENT_ROOTS = ("hooks/", "skills/", "agents/", "scripts/")

# Count-claim docs: touching any of these can stale a "N agents/skills/..." claim.
_COUNT_CLAIM_DOCS = ("README.md", "CLAUDE.md")
_COUNT_CLAIM_DIRS = ("docs/",)


# =============================================================================
# Diff parsing
# =============================================================================


def _strip_git_prefix(path: str) -> str:
    """Strip git's a/ b/ (and rare i/w/c/o/) one-char path prefix."""
    if len(path) > 2 and path[1] == "/" and path[0] in "abciwo":
        return path[2:]
    return path


def _parse_diff(diff: str) -> list[dict]:
    """Parse a unified working-tree diff into per-file change records.

    Returns a list of {"path": str, "added": bool, "removed": bool,
    "modified": bool, "has_added_lines": bool}. `path` is the post-image path
    for adds/modifies and the pre-image path for deletions. Best-effort and
    forgiving: any header it can't classify is simply skipped.
    """
    files: list[dict] = []
    cur: dict | None = None

    def _flush() -> None:
        if cur is not None:
            files.append(cur)

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            _flush()
            # `diff --git a/<p> b/<p>` — take the b/ path as the working name.
            parts = line.split(" ")
            path = _strip_git_prefix(parts[-1]) if len(parts) >= 4 else ""
            cur = {
                "path": path,
                "added": False,
                "removed": False,
                "modified": True,
                "has_added_lines": False,
            }
            continue
        if cur is None:
            continue
        if line.startswith("new file mode"):
            cur["added"] = True
            cur["modified"] = False
        elif line.startswith("deleted file mode"):
            cur["removed"] = True
            cur["modified"] = False
        elif line.startswith("+++ "):
            post = line[4:].strip()
            if post and post != "/dev/null":
                cur["path"] = _strip_git_prefix(post)
        elif line.startswith("--- "):
            pre = line[4:].strip()
            # For deletions the +++ is /dev/null, so anchor on the pre-image path.
            if cur["removed"] and pre and pre != "/dev/null":
                cur["path"] = _strip_git_prefix(pre)
        elif line.startswith("+") and not line.startswith("+++"):
            cur["has_added_lines"] = True

    _flush()
    return [f for f in files if f["path"]]


def _is_count_claim_doc(path: str) -> bool:
    """Is `path` a doc whose count claims this guard cares about?"""
    if path in _COUNT_CLAIM_DOCS:
        return True
    return any(path.startswith(d) for d in _COUNT_CLAIM_DIRS)


def _is_frontmatter_relevant(path: str) -> bool:
    """skills/** or agents/** markdown — routing keys off their frontmatter."""
    return (path.startswith("skills/") or path.startswith("agents/")) and path.endswith(".md")


def _has_reviewable_content(diff: str) -> bool:
    """Front gate: True if the diff carries ANY signal this guard acts on.

    Reviewable means at least one changed file is something this guard would
    inspect: a component file (added/removed/modified under a component root),
    a count-claim doc, or a skills/agents frontmatter file. A diff with no such
    file (or an empty diff) short-circuits before any check runs.

    Note: pure deletions ARE reviewable here (a removed component changes counts),
    so this gate is broader than hook_utils.has_reviewable_content's added-line-
    only contract — it keys on file class, not on added lines.
    """
    for f in _parse_diff(diff):
        path = f["path"]
        if any(path.startswith(root) for root in _COMPONENT_ROOTS):
            return True
        if _is_count_claim_doc(path):
            return True
        if _is_frontmatter_relevant(path):
            return True
    return False


def _relevant_checks(diff: str) -> list[str]:
    """Map a diff to the set of checks to run, in a stable order.

    Relevance gate (exclusive — only classes that actually changed run):
      - any file under hooks/                        -> smoke-test-hooks
      - any component add/remove under a root, OR a
        count-claim doc touched                       -> validate-doc-counts
      - any skills/** or agents/** frontmatter file   -> check-routing-drift
    """
    checks: list[str] = []
    run_smoke = False
    run_doc_counts = False
    run_routing = False

    for f in _parse_diff(diff):
        path = f["path"]
        if path.startswith("hooks/"):
            run_smoke = True
        if (f["added"] or f["removed"]) and any(path.startswith(root) for root in _COMPONENT_ROOTS):
            run_doc_counts = True
        if _is_count_claim_doc(path):
            run_doc_counts = True
        if _is_frontmatter_relevant(path):
            run_routing = True

    # Stable order: smoke, doc-counts, routing.
    if run_smoke:
        checks.append(SMOKE)
    if run_doc_counts:
        checks.append(DOC_COUNTS)
    if run_routing:
        checks.append(ROUTING)
    return checks


# =============================================================================
# Check execution — map each existing script to a {drift, detail, fix} result
# =============================================================================


def _script_path(name: str) -> Path | None:
    """Locate a validator only in the hook's canonical trusted install."""
    scripts_dir = _TRUSTED_ROOT / "scripts"
    candidate = scripts_dir / name
    return candidate if candidate.is_file() else None


def _target_is_trusted_root(cwd: str | None) -> bool:
    """Whether a validator may safely execute project-owned hook/tool code."""
    if not cwd:
        return False
    try:
        return Path(cwd).resolve() == _TRUSTED_ROOT.resolve()
    except OSError:
        return False


# Intrinsic toolkit-repo marker: pyproject.toml declaring [project] name.
# A minimal line scan (Python 3.10 here — no tomllib, no 3rd-party toml lib).
_TOOLKIT_NAME_RE = re.compile(r"""^\s*name\s*=\s*["']vexjoy-agent["']\s*$""", re.MULTILINE)


def _is_toolkit_repo(cwd: str | None) -> bool:
    """Is `cwd` the toolkit repo itself?

    True IFF `cwd` is non-empty AND `cwd/pyproject.toml` exists AND that file
    declares a project name of "vexjoy-agent". Clone-portable: keys on an
    intrinsic committed marker, not a path/remote/env var. Fail-open: ANY
    IOError / parse issue -> False (treated as "not the toolkit repo" -> no-op).
    """
    if not cwd:
        return False
    try:
        text = (Path(cwd) / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return False
    return _TOOLKIT_NAME_RE.search(text) is not None


def _run_script(script: str, args: list[str], cwd: str | None, timeout: int = 30):
    """Run scripts/<script> with args; return CompletedProcess or None on failure."""
    path = _script_path(script)
    if path is None:
        return None
    try:
        return subprocess.run(
            [sys.executable, str(path), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_TRUSTED_ROOT),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _check_smoke(cwd: str | None) -> dict | None:
    """smoke-test-hooks.py --ci: exit 0 = clean, exit 1 = FAIL/MISSING."""
    if not cwd:
        return None
    target_root = str(Path(cwd).resolve())
    proc = _run_script(
        "smoke-test-hooks.py",
        ["--ci", "--repo-root", target_root, "--hooks-dir", str(_TRUSTED_ROOT / "hooks")],
        cwd,
    )
    if proc is None:
        return None
    if proc.returncode == 0:
        return {"drift": False}
    detail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = detail[-1] if detail else "one or more hooks FAIL/MISSING"
    return {
        "drift": True,
        "detail": f"hook smoke test failed: {summary}",
        "fix": "python3 scripts/smoke-test-hooks.py --ci",
    }


def _check_doc_counts(cwd: str | None) -> dict | None:
    """validate-doc-counts.py --json: drift when the `drifts` array is non-empty."""
    if not cwd:
        return None
    proc = _run_script("validate-doc-counts.py", ["--json", "--repo-root", str(Path(cwd).resolve())], cwd)
    if proc is None:
        return None
    try:
        report = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    drifts = report.get("drifts") or []
    if not drifts:
        return {"drift": False}
    lines = ["doc count claims no longer match the filesystem:"]
    for d in drifts[:10]:
        lines.append(
            f"  {d.get('source', '?')}:{d.get('line', '?')} "
            f"claims {d.get('claim', '?')!r} (actual {d.get('actual', '?')})"
        )
    if len(drifts) > 10:
        lines.append(f"  ... and {len(drifts) - 10} more")
    return {
        "drift": True,
        "detail": "\n".join(lines),
        "fix": "python3 scripts/validate-doc-counts.py --json",
    }


def _check_routing(cwd: str | None) -> dict | None:
    """check-routing-drift.py: exit 0 = clean, exit 1 = a skill missing from manifest."""
    if not _target_is_trusted_root(cwd):
        return None
    proc = _run_script("check-routing-drift.py", [], cwd)
    if proc is None:
        return None
    if proc.returncode == 0:
        return {"drift": False}
    detail = (proc.stdout or proc.stderr or "").strip()
    summary = detail or "one or more skills are absent from the routing manifest"
    return {
        "drift": True,
        "detail": f"routing manifest drift: {summary}",
        "fix": "python3 scripts/check-routing-drift.py --verbose",
    }


_CHECK_RUNNERS = {
    SMOKE: _check_smoke,
    DOC_COUNTS: _check_doc_counts,
    ROUTING: _check_routing,
}


def _run_check(name: str, cwd: str | None) -> dict | None:
    """Run ONE check by canonical name; return a structured result.

    Returns {"drift": True, "detail": str, "fix": str} when the underlying
    script reports drift, {"drift": False} when it's clean, or None when the
    script is missing / errored / unparseable (fail-open: callers treat None
    as "no drift").
    """
    runner = _CHECK_RUNNERS.get(name)
    if runner is None:
        return None
    return runner(cwd)


# =============================================================================
# Dedup
# =============================================================================


def _dedup() -> DiffDedup:
    """Build a DiffDedup bound to the current state paths.

    Reads _STATE_DIR / _STATE_FILE at call time so the test-suite's patching of
    those module-level names keeps working.
    """
    return DiffDedup(_STATE_DIR, _STATE_FILE)


# =============================================================================
# Stop handler
# =============================================================================


def _working_tree_diff(cwd: str | None) -> str:
    """Working-tree diff for the relevance gate / dedup.

    Thin wrapper over hook_utils.working_tree_diff (the shared implementation),
    kept as a module-level name so the test-suite can patch it.
    """
    return working_tree_diff(cwd)


def handle_stop(event: dict) -> None:
    """Stop: run the relevant drift checks and ADVISORY re-wake on real drift."""
    # asyncRewake recursion guard: CC sets stop_hook_active while a rewake is in
    # flight — don't re-fire.
    if event.get("stop_hook_active"):
        sys.exit(0)

    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")

    # Toolkit-repo identity gate: run drift checks ONLY when the session's repo
    # IS the toolkit itself. Any other repo (or an unreadable/absent marker)
    # short-circuits before diff parsing or any check runs. Clone-portable.
    if not _is_toolkit_repo(cwd):
        sys.exit(0)

    diff = _working_tree_diff(cwd)

    # Front gate: nothing reviewable -> short-circuit before any check runs.
    if not diff.strip() or not _has_reviewable_content(diff):
        sys.exit(0)

    checks = _relevant_checks(diff)
    if not checks:
        sys.exit(0)

    # Run only the relevant checks; collect those that REPORT drift.
    drifting: list[dict] = []
    for name in checks:
        result = _run_check(name, cwd)
        # None (couldn't run) and {"drift": False} both mean "no drift" (fail-open).
        if result and result.get("drift"):
            drifting.append(result)

    if not drifting:
        # Files changed but every relevant check is clean -> stay silent.
        sys.exit(0)

    # Dedup: a byte-identical diff already surfaced -> don't re-nag.
    dedup = _dedup()
    is_dup, last_iso = dedup.is_duplicate(cwd, diff)
    if is_dup:
        ts_msg = f" since {last_iso}" if last_iso else ""
        print(f"[stop-drift-guard] diff unchanged{ts_msg} — skipping", file=sys.stderr)
        sys.exit(0)

    # Record BEFORE the rewake (exit 2) so the rewake itself won't loop.
    dedup.record(cwd, diff)

    # Compose the advisory. List each drifting check's detail + one-line fix.
    lines = ["[stop-drift-guard] Toolkit drift detected in this session's changes:\n"]
    for d in drifting:
        lines.append(f"- {d.get('detail', 'drift detected')}")
        lines.append(f"    fix: {d.get('fix', '(see the relevant check script)')}")
    lines.append(
        "\nThis is advisory — fix the drift above (or acknowledge it), then continue with the user's original request."
    )
    message = "\n".join(lines) + "\n"

    # async_rewake: rewakeSummary on stdout, context on stderr, exit 2. Advisory —
    # never a permissionDecision:deny, never blocks.
    async_rewake(message, "Toolkit drift guard found drift to review")


def main() -> None:
    # Full kill switch — disables the hook entirely. ONLY exact "1" disables.
    if os.environ.get(_DISABLE_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[stop-drift-guard] Disabled via {_DISABLE_ENV}=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)

    if event.get("hook_event_name") == "Stop":
        # Fail-open at the dispatch boundary too: tests drive main() directly
        # (bypassing the __main__ guard), and a crashed check / diff helper must
        # never escape as a non-zero, non-asyncRewake exit. async_rewake raises
        # SystemExit(2) — that is the intended signal and must propagate.
        try:
            handle_stop(event)
        except SystemExit:
            raise
        except Exception as e:
            hook_error("stop-drift-guard", e)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0/2) propagate normally.
    except Exception as e:
        hook_error("stop-drift-guard", e)
