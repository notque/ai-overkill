#!/usr/bin/env python3
# hook-version: 1.0.1
"""
Local Security Review Hook (ADR: adr/local-security-review.md)

Single-file hook that dispatches on the `hook_event_name` field of the JSON it
reads from stdin. Two paths, no Agent SDK, no API key, no network calls:

| Event       | Condition                       | Behavior                                            |
|-------------|---------------------------------|-----------------------------------------------------|
| PreToolUse  | Bash command contains git commit| Scan STAGED files via scripts/security-review-scan. |
|             |                                 | HIGH/CRITICAL -> JSON permissionDecision:deny.      |
| PostToolUse | Edit / Write / MultiEdit        | Scan the just-edited file via the same scanner rules|
|             |                                 | and inject findings as ADVISORY additionalContext.  |
|             |                                 | Never blocks (PostToolUse runs after the edit) —    |
|             |                                 | matches Anthropic's edit-time firing.               |
| Stop        | (always)                        | asyncRewake the session agent with the working-tree |
|             |                                 | diff + instruction to run the security-review skill.|

The commit gate (PreToolUse) is the ONLY blocking path. PostToolUse and Stop are
advisory — they inform but never deny, mirroring the ADR's "Stop is advisory" rule
and Anthropic's edit-time PostToolUse reminders.

The deterministic regex layer is `scripts/security-review-scan.py` (the single
source of detection rules — called as a subprocess with `--staged --format json`).
The LLM-depth layer is the CURRENT Claude session: the Stop hook injects the diff
as rewake context and the session agent performs the parallel-code-review Security
pass itself. There is no separate model call.

Contracts:
- PreToolUse deny mirrors `hooks/pretool-branch-safety.py` /
  `hooks/pretool-config-protection.py`: stdout JSON
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "deny", "permissionDecisionReason": ...}}`, exit 0.
- Stop asyncRewake mirrors the official security-guidance plugin's
  security_reminder_hook.py: the rewake context is written to stderr, the hook
  exits 2 (the asyncRewake signal), and a stdout JSON line carries a per-run
  `rewakeSummary`. The `asyncRewake`/`rewakeMessage`/`rewakeSummary` config keys
  live in .claude/settings.json. Stop is ADVISORY — it never blocks a commit.

Bypass / kill switches:
- VEXJOY_SECURITY_REVIEW_SKIP=1     disables the commit BLOCK (deliberate override).
- VEXJOY_SECURITY_REVIEW_DISABLE=1  disables the hook entirely (both events).
- VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS=N  Opt-in TTL for Stop dedup. Unset or
                                              0 = no TTL (permanent until the diff
                                              changes). Positive int = old TTL
                                              behavior with that window in seconds.

Stop dedup: byte-identical working-tree diffs (under the same cwd) short-circuit
instead of triggering another rewake. By default, dedup is permanent — same diff
means same diff. The state file self-heals: a non-matching hash overwrites the old
one, so a stale record is a no-op. State persists to
~/.claude/state/security-review-hook/last-diff-hash.json via atomic write.

Fail-open: any internal error allows the commit / skips the rewake and prints a
warning to stderr. A crashed hook never blocks a tool and never stalls a session.
"""

import importlib.util
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
    context_output,
    deny_tool_use,
    empty_output,
    has_reviewable_content,
    hook_error,
    working_tree_diff,
)
from stdin_timeout import read_stdin

_SKIP_ENV = "VEXJOY_SECURITY_REVIEW_SKIP"
_DISABLE_ENV = "VEXJOY_SECURITY_REVIEW_DISABLE"
_DEDUP_TTL_ENV = "VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS"

# Stop-event dedup state. Absolute path so it works from any cwd the harness fires in.
_STATE_DIR = Path.home() / ".claude" / "state" / "security-review-hook"
_STATE_FILE = _STATE_DIR / "last-diff-hash.json"

# Matches a `git commit` invocation anywhere in the Bash command string.
_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit(?:\s|$)")


# Resolve the scanner relative to this file so the hook works from any cwd
# (deployed copies live under ~/.claude/hooks/ alongside scripts/).
def _scanner_path() -> Path | None:
    """Locate scripts/security-review-scan.py from known deploy layouts."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "scripts" / "security-review-scan.py",  # repo: hooks/ -> scripts/
        here.parent / "scripts" / "security-review-scan.py",
        Path(os.path.expanduser("~/.claude/scripts/security-review-scan.py")),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _extract_effective_cwd(command: str, default_cwd: str | None) -> str | None:
    """Extract the effective working directory from a command string.

    Mirrors hooks/pretool-branch-safety.py so `cd <path> && git commit` and
    `git -C <path> commit` scan the right repository.
    """
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p
    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)
    return default_cwd


def _run_scanner(cwd: str | None, staged: bool = True) -> dict | None:
    """Run the deterministic scanner over staged files; return parsed JSON.

    Returns None on any failure (scanner missing, subprocess error, malformed
    output) so callers fail open. The scanner exits 1 on HIGH/CRITICAL, which
    is expected — findings are read from the JSON, not the exit code.
    """
    scanner = _scanner_path()
    if scanner is None:
        return None
    args = [sys.executable, str(scanner), "--format", "json"]
    if staged:
        args.append("--staged")
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or None,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def _format_findings(findings: list[dict], cap: int = 20) -> str:
    """Render HIGH/CRITICAL findings as a compact, file:line list."""
    lines = []
    for f in findings[:cap]:
        lines.append(
            f"  [{f.get('severity', '?')}] {f.get('file', '?')}:{f.get('line', '?')}"
            f" — {f.get('rule', '?')}: {f.get('match', '')}"
        )
    if len(findings) > cap:
        lines.append(f"  ... and {len(findings) - cap} more")
    return "\n".join(lines)


def handle_pre_tool_use(event: dict) -> None:
    """PreToolUse: block `git commit` when staged files have HIGH/CRITICAL findings."""
    command = (event.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not _GIT_COMMIT_RE.search(command):
        sys.exit(0)

    # Deliberate per-commit override — let the commit through.
    if os.environ.get(_SKIP_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[security-review] Bypassed via {_SKIP_ENV}=1", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = _extract_effective_cwd(command, default_cwd)

    report = _run_scanner(cwd, staged=True)
    if report is None:
        # Fail open — the scanner is unavailable or crashed.
        print(
            "[security-review] WARNING: scanner unavailable — allowing commit (fail-open)",
            file=sys.stderr,
        )
        sys.exit(0)

    findings = report.get("findings", [])
    blocking = [f for f in findings if f.get("severity") in ("HIGH", "CRITICAL")]
    if not blocking:
        sys.exit(0)

    summary = report.get("summary", {})
    reason = (
        f"Security review BLOCKED this commit: "
        f"{summary.get('critical', 0)} critical, {summary.get('high', 0)} high finding(s) "
        f"in staged files.\n"
        f"{_format_findings(blocking)}\n"
        f"Fix the findings, or set {_SKIP_ENV}=1 to override deliberately."  # nosec: "set" = plain English, not SQL
    )
    print("[security-review] BLOCKED commit — HIGH/CRITICAL staged findings:", file=sys.stderr)
    print(_format_findings(blocking), file=sys.stderr)
    deny_tool_use("PreToolUse", reason)
    sys.exit(0)


def _load_scanner_module():
    """Load scripts/security-review-scan.py as a module (single source of rules).

    Returns the module or None on any failure (callers fail open / silent).
    """
    scanner = _scanner_path()
    if scanner is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("security_review_scan", scanner)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _edited_file_path(event: dict) -> str | None:
    """Extract the file path the Edit/Write/MultiEdit tool just wrote."""
    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    if isinstance(path, str) and path.strip():
        return path
    return None


def handle_post_tool_use(event: dict) -> None:
    """PostToolUse (Edit|Write|MultiEdit): advisory scan of the just-edited file.

    Mirrors Anthropic's edit-time firing so we surface the same findings at the
    same place. ADVISORY ONLY: PostToolUse runs after the tool, so it cannot block;
    it injects findings as additionalContext. The commit gate stays the only blocker.
    """
    tool_name = event.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        empty_output("PostToolUse").print_and_exit()

    path = _edited_file_path(event)
    if not path:
        empty_output("PostToolUse").print_and_exit()

    # Only scan supported source files; skip everything else silently.
    scanner = _load_scanner_module()
    if scanner is None:
        empty_output("PostToolUse").print_and_exit()

    if scanner._ext(path) not in scanner.SUPPORTED_EXTENSIONS:
        empty_output("PostToolUse").print_and_exit()

    # Resolve the file against the session cwd so relative tool paths scan correctly.
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    abs_path = path if os.path.isabs(path) else os.path.join(cwd or os.getcwd(), path)
    if not os.path.isfile(abs_path):
        empty_output("PostToolUse").print_and_exit()

    try:
        rules = scanner._build_rules()
        rules.extend(scanner._load_custom_rules(cwd or os.getcwd()))
        findings = scanner._scan_file(abs_path, rules)
    except Exception:
        # Fail open — never crash the session over an advisory scan.
        empty_output("PostToolUse").print_and_exit()

    if not findings:
        empty_output("PostToolUse").print_and_exit()

    header = (
        f"[security-review] {len(findings)} potential security finding(s) in {path} "
        f"(advisory — review or document; the commit gate blocks only HIGH/CRITICAL):"
    )
    body = _format_findings(findings)
    context_output("PostToolUse", header + "\n" + body).print_and_exit()


def _working_tree_diff(cwd: str | None) -> str:
    """Return the working-tree diff (tracked changes) for the Stop rewake context.

    Thin wrapper over hook_utils.working_tree_diff (the shared implementation).
    Kept as a module-level name so the test-suite can patch it.
    """
    return working_tree_diff(cwd)


def _scannable_extensions() -> frozenset[str]:
    """Return the scanner's *source* extensions (its supported set minus doc types).

    Derived from the scanner's own constants so the Stop gate and the scanner can't
    drift: SUPPORTED_EXTENSIONS is the superset the scanner opens, and _DOC_EXTS is
    the doc/data subset (.md/.txt/.rst/.json/.mdx) where only anchored secret rules
    fire. The Stop rewake is the heavy LLM-depth pass, so it gates on real code
    files; doc-only changes are non-triggering here (their secret leaks are still
    caught by the edit-time advisory and the commit-block gate, which scan docs).

    Falls back to common source extensions if the scanner can't load. The
    over-broad fallback is safe because the added-line gate still applies.
    """
    scanner = _load_scanner_module()
    if scanner is not None:
        supported = getattr(scanner, "SUPPORTED_EXTENSIONS", None)
        if supported:
            doc_exts = frozenset(getattr(scanner, "_DOC_EXTS", ()))
            return frozenset(supported) - doc_exts
    return frozenset({".py", ".go", ".js", ".ts", ".rb", ".java", ".php", ".kt", ".swift"})


def _has_reviewable_content(diff: str) -> bool:
    """Return True only if the diff is security-relevant for the Stop rewake.

    Thin wrapper over hook_utils.has_reviewable_content with this hook's scanner-
    derived scannable extension set (SUPPORTED_EXTENSIONS minus doc types). Kept
    as a module-level name so the test-suite can reason about it directly.

    Security-relevant means: at least one scannable source file has at least one
    ADDED line. Pure deletions, doc/config-only diffs, mode-only and pure-rename
    diffs are all non-triggering. An added line in a real source file (a new
    `eval(...)` in a `.py`) MUST still pass — true positives are preserved. (nosec: doc example, not a real eval call)
    """
    return has_reviewable_content(diff, _scannable_extensions())


def _dedup_ttl_seconds() -> int:
    """Read TTL override from env. Default 0 = no TTL (permanent dedup until diff changes).

    A positive integer re-enables the old time-window behavior. Anything else
    (unset, 0, negative, malformed) means no TTL.
    """
    raw = os.environ.get(_DEDUP_TTL_ENV)
    if not raw:
        return 0
    try:
        ttl = int(raw)
    except (ValueError, TypeError):
        return 0
    return ttl if ttl > 0 else 0


def _dedup() -> DiffDedup:
    """Build a DiffDedup bound to the current state paths + TTL.

    Reads _STATE_DIR / _STATE_FILE / _dedup_ttl_seconds() at call time so the
    test-suite's patching of those module-level names keeps working.
    """
    return DiffDedup(_STATE_DIR, _STATE_FILE, ttl_seconds=_dedup_ttl_seconds())


def _diff_signature(cwd: str | None, diff: str) -> str:
    """Hash (cwd, diff) so different repos with identical diffs don't collide."""
    return _dedup().signature(cwd, diff)


def _is_duplicate_diff(cwd: str | None, diff: str) -> tuple[bool, str | None]:
    """Return (is_duplicate, last_seen_iso). Hash match is permanent by default.

    Delegates to the shared DiffDedup state machine. Same (cwd, diff) hash means
    same review unless VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS is a positive int.
    """
    return _dedup().is_duplicate(cwd, diff)


def _record_diff_seen(cwd: str | None, diff: str) -> None:
    """Persist the current diff signature so a byte-identical re-fire short-circuits."""
    _dedup().record(cwd, diff)


def handle_stop(event: dict) -> None:
    """Stop: asyncRewake the session agent to run the security-review pipeline.

    ADVISORY only. Re-wakes the session with the working-tree diff and an
    instruction to run the security-review skill. The session agent (not an SDK
    call) performs the LLM-depth review. Exit 2 is the asyncRewake signal that
    mirrors the official plugin; it does not block any tool or commit.
    """
    # Guard against the asyncRewake loop re-firing endlessly: CC sets
    # stop_hook_active while a rewake is in flight.
    if event.get("stop_hook_active"):
        sys.exit(0)

    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    diff = _working_tree_diff(cwd)
    if not diff.strip() or not _has_reviewable_content(diff):
        # Nothing reviewable (empty or mode-only changes) — skip.
        sys.exit(0)

    # Dedup: short-circuit if this exact diff (under this cwd) was already reviewed.
    # By default the match is permanent — same diff means same diff. The state file
    # self-heals when the diff actually changes (the new hash overwrites the old).
    is_dup, last_iso = _is_duplicate_diff(cwd, diff)
    if is_dup:
        ts_msg = f" since {last_iso}" if last_iso else ""
        print(
            f"[security-review] diff unchanged{ts_msg} — skipping",
            file=sys.stderr,
        )
        sys.exit(0)

    # Cap the injected diff so the rewake context stays bounded.
    max_chars = 60_000
    truncated = len(diff) > max_chars
    diff_excerpt = diff[:max_chars]

    instruction = (
        "Call the Skill tool with `security-review`. "
        "Review the working-tree changes below. "
        "Scope to the changed files, run the deterministic scanner "
        "(scripts/security-review-scan.py), compose the parallel-code-review "
        "Security reviewer over the diff, and report BLOCK/FIX/APPROVE. This "
        "review runs inside the current session — no API key, no SDK. "
        "This is supplementary feedback; after addressing or acknowledging it, "
        "continue with the user's original request."
    )
    if truncated:
        instruction += f"\n\n(diff truncated to {max_chars} chars)"

    # Record the diff signature so a byte-identical re-fire short-circuits cleanly.
    # Recorded BEFORE the rewake (exit 2) so the rewake itself won't loop.
    _record_diff_seen(cwd, diff)

    # async_rewake (shared helper) emits the per-run rewakeSummary one-liner on
    # stdout, writes the rewake context to stderr, and exits 2 (the asyncRewake
    # signal). Mirrors the official plugin; advisory — never blocks.
    message = (
        "[security-review] Session security review\n\n"
        + instruction
        + "\n\n=== working-tree diff ===\n"
        + diff_excerpt
        + "\n"
    )
    async_rewake(message, "Local security review of session changes")


def main() -> None:
    # Full kill switch — disables both events.
    if os.environ.get(_DISABLE_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[security-review] Disabled via {_DISABLE_ENV}=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)

    hook_event_name = event.get("hook_event_name", "")
    if hook_event_name == "PreToolUse":
        handle_pre_tool_use(event)
    elif hook_event_name == "PostToolUse":
        handle_post_tool_use(event)
    elif hook_event_name == "Stop":
        handle_stop(event)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0/2) propagate normally
    except Exception as e:
        hook_error("security-review-hook", e)
