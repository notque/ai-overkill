"""
Shared utilities for Claude Code hooks.

Provides common functionality used across multiple hooks:
- JSON output formatting with proper escaping
- User message support
- Cascading fallback patterns
- Error handling with degraded modes

Inspired by shared/lib patterns.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


# =============================================================================
# JSON Utilities
# =============================================================================


def json_escape(text: str) -> str:
    """
    Escape a string for safe JSON embedding.

    RFC 8259 compliant - handles all control characters.

    Args:
        text: The string to escape

    Returns:
        JSON-safe escaped string (without surrounding quotes)
    """
    # json.dumps adds quotes, we strip them
    return json.dumps(text)[1:-1]


# =============================================================================
# Hook Output Formatting
# =============================================================================


@dataclass
class HookOutput:
    """
    Structured hook output with user message support.

    Attributes:
        event_name: The hook event name (SessionStart, UserPromptSubmit, etc.)
        additional_context: System context for Claude (not shown to user)
        user_message: User-facing message that MUST be shown verbatim
        metadata: Additional key-value pairs for the output
    """

    event_name: str
    additional_context: Optional[str] = None
    user_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Events that support hookSpecificOutput per Claude Code's schema.
    # All other events must emit top-level fields or an empty object.
    # Source: https://code.claude.com/docs/en/hooks (2026-03-26)
    _HOOK_SPECIFIC_OUTPUT_EVENTS = frozenset(
        {
            "PreToolUse",
            "PostToolUse",
            "PostToolUseFailure",
            "UserPromptSubmit",
            "SessionStart",
            "SubagentStart",
            "Notification",
            "CwdChanged",
            "FileChanged",
            "Elicitation",
            "ElicitationResult",
            "WorktreeCreate",
            "PermissionRequest",
        }
    )

    def to_json(self) -> str:
        """Convert to JSON string for hook output.

        Events in ``_HOOK_SPECIFIC_OUTPUT_EVENTS`` support the
        ``hookSpecificOutput`` wrapper (PreToolUse, PostToolUse,
        PostToolUseFailure, UserPromptSubmit, SessionStart, SubagentStart,
        Notification, CwdChanged, FileChanged, Elicitation,
        ElicitationResult, WorktreeCreate, PermissionRequest).

        All other events (Stop, SubagentStop, StopFailure, PreCompact,
        PostCompact, TaskCreated, TaskCompleted, TeammateIdle, ConfigChange,
        WorktreeRemove, SessionEnd, InstructionsLoaded) must emit top-level
        fields or ``{}`` — wrapping them causes a JSON validation error in
        Claude Code.
        """
        if self.event_name in self._HOOK_SPECIFIC_OUTPUT_EVENTS:
            inner: dict[str, Any] = {"hookEventName": self.event_name}

            if self.user_message:
                inner["userMessage"] = self.user_message

            if self.additional_context:
                inner["additionalContext"] = self.additional_context

            inner.update(self.metadata)
            return json.dumps({"hookSpecificOutput": inner})

        # Non-supported events: emit top-level fields or empty object.
        output: dict[str, Any] = {}
        output.update(self.metadata)
        return json.dumps(output)

    def print_and_exit(self, exit_code: int = 0) -> None:
        """Print JSON output and exit."""
        print(self.to_json())
        sys.exit(exit_code)


def empty_output(event_name: str) -> HookOutput:
    """Create an empty hook output (no injection)."""
    return HookOutput(event_name=event_name)


def context_output(event_name: str, context: str) -> HookOutput:
    """Create hook output with additional context."""
    return HookOutput(event_name=event_name, additional_context=context)


def user_message_output(event_name: str, message: str, context: Optional[str] = None) -> HookOutput:
    """
    Create hook output with a mandatory user message.

    User messages MUST be displayed verbatim by Claude at the start
    of the response. They are used for critical notifications,
    warnings, and action-required messages.

    Args:
        event_name: Hook event name
        message: User-facing message (displayed verbatim)
        context: Optional additional context (not shown to user)

    Returns:
        HookOutput with user_message set
    """
    return HookOutput(event_name=event_name, user_message=message, additional_context=context)


# =============================================================================
# Cascading Fallback Pattern
# =============================================================================


def with_fallback(
    primary: Callable[[], T],
    fallback: Callable[[], T],
    error_message: Optional[str] = None,
) -> T:
    """
    Execute primary function, fall back on failure.

    Args:
        primary: Primary function to try
        fallback: Fallback function if primary fails
        error_message: Optional message to log on fallback

    Returns:
        Result from primary or fallback
    """
    try:
        return primary()
    except Exception as e:
        if error_message:
            print(f"Warning: {error_message}: {e}", file=sys.stderr)
        return fallback()


def cascading_fallback(
    *funcs: Callable[[], T],
    default: T,
    error_prefix: str = "Fallback",
) -> T:
    """
    Try multiple functions in sequence, return first success.

    This implements a cascading fallback architecture:
    Priority: func1 → func2 → ... → default

    Args:
        *funcs: Functions to try in order
        default: Value to return if all fail
        error_prefix: Prefix for error messages

    Returns:
        First successful result or default

    Example:
        result = cascading_fallback(
            try_with_yaml,
            try_with_regex,
            try_with_basic,
            default="",
            error_prefix="YAML parsing"
        )
    """
    for i, func in enumerate(funcs):
        try:
            return func()
        except Exception as e:
            print(f"Warning: {error_prefix} attempt {i + 1} failed: {e}", file=sys.stderr)

    return default


# =============================================================================
# Environment Utilities
# =============================================================================


def get_project_dir() -> Path:
    """Get the Claude project directory from environment."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def get_session_id() -> str:
    """Get session ID from environment or generate a unique fallback.

    Falls back to PPID + timestamp hash if CLAUDE_SESSION_ID is not set.
    This handles container scenarios where PPID might be 1 (init).
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID")
    if session_id:
        return session_id

    # Generate more unique fallback: PPID + process start time hash
    import hashlib
    import time

    ppid = os.getppid()
    # Use current time truncated to session start (rough approximation)
    time_component = str(int(time.time() // 3600))  # Hour-based bucket
    unique_str = f"{ppid}-{time_component}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:12]


def get_state_file(prefix: str) -> Path:
    """
    Get a session-specific state file path.

    Args:
        prefix: Prefix for the state file name

    Returns:
        Path to state file in /tmp
    """
    session_id = get_session_id()
    return Path(f"/tmp/claude-{prefix}-{session_id}.state")


# =============================================================================
# File Discovery
# =============================================================================


# Common directories to exclude when scanning
EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def discover_files(
    root: Path,
    pattern: str,
    exclude_dirs: Optional[set[str]] = None,
) -> list[Path]:
    """
    Discover files matching a pattern, excluding common directories.

    Args:
        root: Root directory to search
        pattern: Glob pattern (e.g., "CLAUDE.md", "*.py")
        exclude_dirs: Additional directories to exclude

    Returns:
        List of matching file paths
    """
    excludes = EXCLUDE_DIRS | (exclude_dirs or set())
    found = []

    try:
        for path in root.rglob(pattern):
            # Skip if in excluded directory
            if any(part in excludes for part in path.parts):
                continue
            # Skip symlinks for security
            if path.is_symlink():
                continue
            if path.is_file():
                found.append(path)
    except OSError:
        # Best-effort discovery: if we hit a filesystem error while walking
        # (e.g., permission denied), return any files found so far rather
        # than failing the entire hook.
        pass

    return found


# =============================================================================
# YAML Frontmatter Parsing (with fallback)
# =============================================================================

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def parse_frontmatter(content: str) -> Optional[dict[str, Any]]:
    """
    Parse YAML frontmatter from markdown content.

    Implements cascading fallback:
    1. Try PyYAML if available (same block-scalar-aware behavior as
       scripts/lib/frontmatter.py's parser; kept independent here so hooks
       stay self-contained in hooks-only deployment mirrors).
    2. Fall back to a simple regex parser for common fields.

    Args:
        content: Markdown file content

    Returns:
        Parsed frontmatter dict or None
    """
    # Check for frontmatter markers
    if not content.startswith("---"):
        return None

    # Find end of frontmatter
    end_match = content.find("\n---", 3)
    if end_match == -1:
        return None

    frontmatter = content[4:end_match].strip()

    # Try YAML parser first
    if YAML_AVAILABLE:
        try:
            return yaml.safe_load(frontmatter)
        except yaml.YAMLError:
            pass

    # Fallback: simple regex parser for common fields
    return _parse_frontmatter_regex(frontmatter)


def _parse_frontmatter_regex(content: str) -> dict[str, Any]:
    """Simple regex-based frontmatter parser for common fields."""
    import re

    result: dict[str, Any] = {}

    # Match simple key: value patterns
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(r"^(\w+):\s*(.+)$", line)
        if match:
            key, value = match.groups()
            # Strip quotes if present
            value = value.strip().strip("\"'")
            result[key] = value

    return result


# =============================================================================
# Logging Utilities
# =============================================================================


def log_info(message: str) -> None:
    """Log info message to stderr (won't interfere with JSON output)."""
    print(f"[info] {message}", file=sys.stderr)


def log_warning(message: str) -> None:
    """Log warning message to stderr."""
    print(f"[warn] {message}", file=sys.stderr)


def log_error(message: str) -> None:
    """Log error message to stderr."""
    print(f"[error] {message}", file=sys.stderr)


# =============================================================================
# Loud Hook Error Helper
# =============================================================================

# JSONL log for hook errors — enables validate-hook-health to surface repeat
# offenders without needing CLAUDE_HOOKS_DEBUG set.
_DEFAULT_HOOK_ERRORS_PATH = Path.home() / ".claude" / "learning" / "hook-errors.jsonl"


def _hook_errors_path() -> Path:
    """Resolve the error log at call time so tests and operators can isolate it."""
    override = os.environ.get("CLAUDE_HOOK_ERRORS_PATH")
    return Path(override) if override else _DEFAULT_HOOK_ERRORS_PATH


# Path components that mark a file as credential-adjacent. Matched against
# whole path segments (never substrings), so "assh/" or "renv/" cannot match.
_SENSITIVE_PATH_DIRS = frozenset({".ssh", ".gnupg", ".aws", ".azure", ".kube", ".gcloud"})

# Basename patterns for credential-shaped files.
_SENSITIVE_BASENAME_RE = None


def _sensitive_basename_pattern():
    """Lazy-compile the sensitive-basename regex."""
    global _SENSITIVE_BASENAME_RE
    if _SENSITIVE_BASENAME_RE is None:
        import re

        _SENSITIVE_BASENAME_RE = re.compile(
            r"^(\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_[a-z0-9]+(\.pub)?"
            r"|.*credentials.*|.*secret.*|token\.json|\.tokens|\.netrc|\.npmrc|\.pypirc)$",
            re.IGNORECASE,
        )
    return _SENSITIVE_BASENAME_RE


def is_sensitive_path(path: str) -> bool:
    """True when a file path looks credential- or secret-bearing.

    Hooks that echo file paths into model-visible context (e.g. subagent
    warmstart) must drop these entirely — surfacing even the *path* of a key
    file to a subagent prompt leaks information and invites a follow-up read.

    Args:
        path: Absolute or relative file path string.

    Returns:
        True if any path segment is a credential directory (.ssh, .gnupg,
        .aws, ...) or the basename is credential-shaped (.env*, *.pem, *.key,
        id_*, *credentials*, *secret*, token.json, ...).
    """
    if not path:
        return False
    segments = [s for s in path.replace("\\", "/").split("/") if s]
    if any(seg in _SENSITIVE_PATH_DIRS for seg in segments):
        return True
    return bool(segments and _sensitive_basename_pattern().match(segments[-1]))


# Secrets pattern used to strip sensitive values from error messages.
_SECRETS_RE = None


def _secrets_pattern():
    """Lazy-compile secrets regex (avoids import-time re.compile cost)."""
    global _SECRETS_RE
    if _SECRETS_RE is None:
        import re

        _SECRETS_RE = re.compile(
            r"(Bearer\s+\S+|token[=:]\S+|key[=:]\S+|password[=:]\S+|secret[=:]\S+)",
            re.IGNORECASE,
        )
    return _SECRETS_RE


def _redact_secrets(text: str) -> str:
    """Strip obvious secret patterns from error text."""
    return _secrets_pattern().sub("<redacted>", text)


def hook_error(hook_name: str, exc: BaseException) -> None:
    """Unconditional one-liner to stderr + append to hook-errors.jsonl.

    Always called. Full traceback only under CLAUDE_HOOKS_DEBUG.
    Never raises — swallows all internal failures so hooks stay non-blocking.
    """
    exc_type = type(exc).__name__
    exc_msg = _redact_secrets(str(exc))
    # Unconditional one-liner — always visible.
    try:
        print(f"[{hook_name}] HOOK-ERROR: {exc_type}: {exc_msg}", file=sys.stderr)
    except Exception:
        pass

    # Full traceback only when debugging.
    if os.environ.get("CLAUDE_HOOKS_DEBUG"):
        try:
            import traceback

            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass

    # Append to JSONL log (best-effort, never blocks).
    try:
        entry = json.dumps(
            {
                "ts": datetime.now(tz=timezone.utc).isoformat(),
                "hook": hook_name,
                "type": exc_type,
                "msg": exc_msg[:500],
            }
        )
        path = _hook_errors_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# =============================================================================
# Governance Event Recording (enriched wrapper)
# =============================================================================

# Per-second dedup: suppress duplicate governance events within the same second.
_GOV_DEDUP: dict[str, float] = {}


def _redact_command_head(command: str, max_len: int = 80) -> str:
    """First ~80 chars of a command with secrets stripped."""
    head = command[:max_len]
    return _redact_secrets(head)


def record_governance(
    event_type: str,
    *,
    hook_name: str = "",
    tool_name: str = "",
    hook_phase: str = "",
    severity: str = "",
    blocked: bool = False,
    event: dict | None = None,
    command: str = "",
) -> str | None:
    """Enriched governance event recording with dedup and payload.

    Wraps learning_db_v2.record_governance_event with:
    - session_id extracted from event or environment
    - payload with hook name and redacted command head
    - per-second dedup (suppresses duplicate event_type+tool_name within 1s)

    Never raises. Returns event id on success, None on failure or dedup.
    """
    try:
        # Per-second dedup key
        now = time.time()
        dedup_key = f"{event_type}:{tool_name}:{hook_name}"
        last = _GOV_DEDUP.get(dedup_key, 0.0)
        if now - last < 1.0:
            return None  # suppressed
        _GOV_DEDUP[dedup_key] = now

        # Extract session_id
        session_id = None
        if event and isinstance(event, dict):
            session_id = event.get("session_id")
        if not session_id:
            session_id = os.environ.get("CLAUDE_SESSION_ID")

        # Build payload
        payload: dict[str, Any] = {}
        if hook_name:
            payload["hook"] = hook_name
        if command:
            payload["command_head"] = _redact_command_head(command)

        from learning_db_v2 import record_governance_event

        return record_governance_event(
            event_type,
            session_id=session_id,
            tool_name=tool_name,
            hook_phase=hook_phase,
            severity=severity,
            payload=payload if payload else None,
            blocked=blocked,
        )
    except Exception:
        return None


def deny_tool_use(event_name: str, reason: str) -> None:
    """Output a structured deny decision for PreToolUse/SubagentStop hooks.

    Public utility for simpler hooks that only need a deny decision without
    the governance recording and stderr logging that pretool-unified-gate's
    ``_block()`` provides.

    Prints the JSON permissionDecision format that Claude Code expects to stdout,
    then returns. The caller is responsible for calling sys.exit(0) afterwards.

    The reason is surfaced to the model so it can adapt its approach.

    Args:
        event_name: Hook event name (e.g. "PreToolUse", "SubagentStop").
        reason: Human-readable explanation shown to the model.
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))


# ===== Schema-Compatibility Helpers (PostToolUse) =====


def get_tool_result(event: dict) -> object:
    """Return the normalized tool result from a PostToolUse event.

    Handles both Claude/Codex ('tool_result') and Factory CLI
    ('tool_response') schemas. Returns {} if neither key is present.
    When the value is a string (observed in production), wraps it as
    {"output": value} so downstream callers like is_tool_error() and
    get_tool_output() work without isinstance guards.
    """
    for key in ("tool_result", "tool_response"):
        if key in event:
            val = event[key]
            if isinstance(val, (dict, list)):
                return val
            if isinstance(val, str):
                return {"output": val}
            if val is None:
                return {}
            return {}
    return {}


def get_tool_input(event: dict) -> dict:
    """Return the tool input as a dict from a hook event.

    Handles three observed payload shapes:
      1. dict  -- the normal case (returned as-is)
      2. JSON string -- the string is parsed and returned as a dict
      3. bare string -- returned as {"command": value} for Bash compat
      4. missing/None/other -- returns {}

    Callers can safely do ``get_tool_input(event).get("command", "")``
    without an isinstance guard.
    """
    raw: object = None
    for key in ("tool_input", "input"):
        candidate = event.get(key)
        if isinstance(candidate, (dict, str)):
            raw = candidate
            break
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        # Bare string (e.g. a command) -- wrap so .get("command") works
        return {"command": raw}
    return {}


def get_tool_output(result: object) -> str:
    """Return the tool's stdout/output string.

    Claude/Codex use 'output'; Factory uses 'stdout'.

    Note: key presence, not truthiness, determines the field — an empty
    'output' key returns '' without falling through to 'stdout'.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "\n".join(filter(None, (get_tool_output(item) for item in result)))
    if not isinstance(result, dict):
        return ""
    if "output" in result:
        return result["output"] or ""
    if "stdout" in result:
        return result["stdout"] or ""
    if isinstance(result.get("text"), str):
        return result["text"]
    if "content" in result:
        return get_tool_output(result["content"])
    return ""


def get_tool_error(result: object) -> str:
    """Return the tool's error/stderr string when an error occurred.

    Claude/Codex surface 'error'; Factory uses 'stderr' (and exitCode != 0
    indicates failure). Returns empty string when no error.
    """
    if not isinstance(result, dict):
        return ""
    if result.get("error"):
        return result["error"]
    if result.get("exitCode", 0) != 0:
        return result.get("stderr", "") or result.get("stdout", "")
    return ""


def is_tool_error(result: object) -> bool:
    """Detect tool failure across schemas.

    Claude/Codex set is_error=True; Factory exposes exitCode (non-zero = error).
    """
    if isinstance(result, list):
        return any(is_tool_error(item) for item in result)
    if not isinstance(result, dict):
        return False
    if "is_error" in result:
        return bool(result["is_error"])
    return result.get("exitCode", 0) != 0


# =============================================================================
# Activation Recording
# =============================================================================


def record_activations_safe(
    results: list[dict],
    session_id: str | None = None,
    *,
    debug: bool = False,
) -> None:
    """Record activations for injected learnings. Never blocks.

    Extracts (topic, key) pairs from result dicts and batch-records them.
    Swallows all exceptions so hook execution is never interrupted.

    Args:
        results: List of learning dicts with "topic" and "key" keys.
        session_id: Session identifier for activation tracking.
        debug: If True, log failures to stderr.
    """
    try:
        from learning_db_v2 import record_activations

        entries = [(r["topic"], r["key"]) for r in results]
        if entries:
            record_activations(entries, session_id)
    except Exception as e:
        if debug:
            print(f"[activation] Recording failed: {e}", file=sys.stderr)


# =============================================================================
# Working-tree diff / reviewable-content gating / async rewake
#
# Promoted from hooks/security-review-hook.py so any hook that needs to reason
# about the git working-tree diff (Stop rewake, security review, etc.) shares a
# single implementation. These are import-and-call utilities — not auto-applied.
# =============================================================================


def working_tree_diff(cwd: Optional[str], timeout: int = 15) -> str:
    """Return the working-tree diff (tracked changes vs HEAD) for `cwd`.

    Fails closed to an empty string on any error (non-repo, git missing,
    timeout) so callers can treat "no diff" and "couldn't diff" the same way.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--no-color", "HEAD"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or None,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def diff_post_image_ext(header_line: str) -> Optional[str]:
    """Extract the lowercased extension of a unified-diff post-image path.

    `header_line` is a ``+++ `` line. Returns None for ``/dev/null``
    (deletions) or when the post-image path has no extension.
    """
    path = header_line[4:].strip()
    if not path or path == "/dev/null":
        return None
    # Strip git's `b/` prefix (and the rare `i/`/`w/`/`c/`/`o/` prefixes).
    if len(path) > 2 and path[1] == "/" and path[0] in "abciwo":
        path = path[2:]
    dot = path.rfind(".")
    slash = path.rfind("/")
    if dot == -1 or dot < slash:
        return None
    return path[dot:].lower()


def has_reviewable_content(diff: str, scannable_exts: frozenset[str]) -> bool:
    """Return True only if `diff` is security-relevant.

    Security-relevant means: at least one file whose extension is in
    `scannable_exts` has at least one ADDED content line. The caller supplies
    `scannable_exts` (e.g. the scanner's SUPPORTED_EXTENSIONS minus doc types)
    so this helper stays decoupled from any particular rule engine.

    - Pure deletions (only ``-`` lines) cannot introduce a vulnerability → False.
    - Files whose extension is not in `scannable_exts` (docs/config) → ignored.
    - Mode-only / pure-rename diffs (no added content lines) → False.

    An added line in a scannable file (e.g. a new dangerous-eval call in a
    ``.py``) MUST pass this gate — true positives are preserved.
    """
    current_scannable = False  # is the file in the current diff block scannable?
    for line in diff.splitlines():
        if line.startswith("+++ "):
            ext = diff_post_image_ext(line)
            current_scannable = ext in scannable_exts if ext is not None else False
            continue
        if line.startswith("diff --git "):
            current_scannable = False
            continue
        if current_scannable and line.startswith("+") and not line.startswith("+++"):
            return True
    return False


def normalize_diff_for_fingerprint(diff: str) -> str:
    """Strip volatile-only noise from a unified diff before fingerprinting.

    The dedup fingerprint must be stable across re-fires that carry the SAME
    semantic change. Raw ``git diff`` output embeds a few volatile fields that
    churn even when the file paths and hunks are unchanged — most importantly
    the ``index <oldsha>..<newsha> <mode>`` line, whose blob SHAs change whenever
    a build artifact is regenerated (e.g. ``static/game/*`` rebuilds produce the
    same hunks but fresh blob SHAs). Hashing the raw bytes therefore misses the
    duplicate and re-reviews the identical change over and over.

    This normalizer removes ONLY those volatile lines, preserving everything
    that defines WHAT changed:

    Dropped (volatile, carry no review signal):
      - ``index <sha>..<sha>[ mode]`` — blob SHAs / churn on rebuild
      - ``old mode`` / ``new mode``   — bare permission churn
      - ``deleted file mode`` / ``new file mode`` — mode digits only
      - ``similarity index NN%`` / ``dissimilarity index NN%`` — rename heuristic noise

    Kept (load-bearing — ANY change here yields a new fingerprint → full review):
      - ``diff --git a/... b/...`` headers (file paths)
      - ``--- `` / ``+++ `` headers (file paths)
      - ``rename from`` / ``rename to`` (path moves are real changes)
      - every ``@@`` hunk header and every ``+``/``-``/context line

    Hardening-preserving: this only collapses byte-noise to a stable form; it
    never widens what counts as "the same diff" beyond identical paths + hunks.
    A new file, a changed hunk, or a renamed path all still differ here.
    """
    out = []
    for line in diff.split("\n"):
        if line.startswith("index "):
            continue
        if line.startswith("old mode ") or line.startswith("new mode "):
            continue
        if line.startswith("deleted file mode ") or line.startswith("new file mode "):
            continue
        if line.startswith("similarity index ") or line.startswith("dissimilarity index "):
            continue
        out.append(line)
    return "\n".join(out)


class DiffDedup:
    """Working-tree-diff dedup with atomic state + opt-in TTL.

    Hashes ``sha256(cwd, normalize_diff_for_fingerprint(diff))`` so different
    repos with identical diffs do not collide, and so re-fires of the SAME
    semantic change (same paths + same hunks) fingerprint identically even when
    git's volatile blob-SHA / mode noise churns underneath. State persists to a
    JSON file via atomic write (tempfile in the same dir + ``os.replace``). By
    default dedup is permanent — the same fingerprint means the same review until
    the diff actually changes; a non-matching hash overwrites the old record
    (self-healing).

    A positive ``ttl_seconds`` re-enables a time window: a hash match older than
    the TTL is treated as a miss.
    """

    def __init__(self, state_dir: Path, state_file: Path, ttl_seconds: int = 0):
        self.state_dir = Path(state_dir)
        self.state_file = Path(state_file)
        self.ttl_seconds = ttl_seconds if ttl_seconds and ttl_seconds > 0 else 0

    def signature(self, cwd: Optional[str], diff: str) -> str:
        """Hash (cwd, normalized-diff) so identical changes fingerprint stably.

        The diff is first run through ``normalize_diff_for_fingerprint`` to drop
        volatile-only noise (blob-SHA index lines, bare mode churn) while keeping
        file paths and hunks. ``cwd`` keeps different repos with identical diffs
        from colliding. Fails open: if normalization ever raises, fall back to
        hashing the raw diff (the original byte-identical behavior).
        """
        try:
            normalized = normalize_diff_for_fingerprint(diff)
        except Exception:
            normalized = diff
        h = hashlib.sha256()
        h.update((cwd or "").encode("utf-8", errors="replace"))
        h.update(b"\x00")
        h.update(normalized.encode("utf-8", errors="replace"))
        return h.hexdigest()

    def _load(self) -> dict:
        try:
            if self.state_file.exists():
                return json.loads(self.state_file.read_text())
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        return {}

    def is_duplicate(self, cwd: Optional[str], diff: str) -> tuple[bool, Optional[str]]:
        """Return (is_duplicate, last_seen_iso).

        A hash match is permanent unless ``ttl_seconds`` is positive, in which
        case a match older than the TTL is treated as a miss.
        """
        state = self._load()
        if state.get("hash") != self.signature(cwd, diff):
            return False, None
        if self.ttl_seconds > 0:
            try:
                last_ts = float(state.get("ts", 0))
            except (TypeError, ValueError):
                return False, None
            if (time.time() - last_ts) > self.ttl_seconds:
                return False, None
        return True, state.get("ts_iso")

    def record(self, cwd: Optional[str], diff: str) -> None:
        """Persist the current (cwd, diff) signature. Silent on failure —
        dedup persistence is best-effort and must never block a hook."""
        now = time.time()
        state = {
            "hash": self.signature(cwd, diff),
            "ts": now,
            "ts_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "cwd": cwd or "",
        }
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.state_dir), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(state, f)
                os.replace(tmp, str(self.state_file))
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception:
            # At worst we double-review on the next event — the existing behavior.
            pass


def async_rewake(message: str, summary: str) -> None:
    """Emit an asyncRewake signal: rewakeSummary on stdout, context on stderr,
    then exit 2 (the asyncRewake signal that mirrors the official plugin).

    Does not return — always raises SystemExit(2). `summary` is the one-liner
    shown to the user; `message` is the full rewake context for the agent.
    """
    print(json.dumps({"rewakeSummary": summary}), flush=True)
    sys.stderr.write(message)
    sys.exit(2)
