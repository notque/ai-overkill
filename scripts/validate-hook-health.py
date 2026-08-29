#!/usr/bin/env python3
"""Composing hook-health validator — permanent defense against dormant/broken hooks.

Read-only. Reads repo `hooks/` and repo `.claude/settings.json` directly, so the
dormancy / schema / mirror checks need NO sync to ~/.claude. Only the liveness
check (--with-liveness) shells out to smoke-test-hooks.py, which reads the
deployed hooks at ~/.claude/hooks.

Checks (ADR hook-health-gate):
  (a) Zero dormant: disk hooks/*.py - __init__.py - lib/ - tests/ - registered
      - dispatched - allowlist  MUST be empty.
  (b) Every registered command resolves to a repo hooks/ file (existence, not +x).
  (c) Liveness: delegate to smoke-test-hooks.py --ci (opt-in via --with-liveness;
      always on under --ci).
  (d) Schema: settings.json parses; event names ∈ known set; matcher is a string;
      each command matches the canonical python3 "$HOME/.claude/hooks/<file>.py" form.
  (e) Mirror sanity: every file named in codex-hooks-allowlist.txt exists
      AND is registered in .claude/settings.json (no phantom mirror entries).
      Mirrors are intentional subsets — full coverage is NOT required.

Usage:
    python3 scripts/validate-hook-health.py            # report, exit 0
    python3 scripts/validate-hook-health.py --ci       # exit 1 on any failure (incl liveness)
    python3 scripts/validate-hook-health.py --with-liveness
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
HOOKS_DIR = REPO_ROOT / "hooks"
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "hook-health-allowlist.txt"
CODEX_MIRROR = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"

KNOWN_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "Stop",
    "StopFailure",
    "SubagentStart",
    "SubagentStop",
    "TaskCompleted",
}

# Canonical command form: python3 "$HOME/.claude/hooks/<file>.py"
CANONICAL_CMD = re.compile(r'^python3\s+"\$HOME/\.claude/hooks/([A-Za-z0-9._-]+\.py)"$')
# Extract a hooks/<file>.py basename from any command (looser, for registered set)
CMD_BASENAME = re.compile(r"hooks/([A-Za-z0-9._-]+\.py)")


def load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def iter_hook_entries(settings: dict):
    """Yield (event, matcher, command) for each registered hook entry."""
    for event, groups in settings.get("hooks", {}).items():
        if not isinstance(groups, list):
            groups = [groups]
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher", "")
            for entry in group.get("hooks", []):
                if isinstance(entry, dict):
                    yield event, matcher, entry.get("command", "")


def registered_basenames(settings: dict) -> set[str]:
    out: set[str] = set()
    for _event, _matcher, cmd in iter_hook_entries(settings):
        m = CMD_BASENAME.search(cmd)
        if m:
            out.add(m.group(1))
    return out


def disk_hooks() -> set[str]:
    """Top-level hooks/*.py basenames, excluding __init__.py (lib/ and tests/
    are subdirs, so glob('*.py') already excludes them)."""
    return {p.name for p in HOOKS_DIR.glob("*.py") if p.name != "__init__.py"}


_SUBPROCESS_FUNCS = {"run", "call", "check_call", "check_output", "Popen"}


def _is_subprocess_call(node: ast.Call, popen_imported: bool = False) -> bool:
    """True if `node` is subprocess.run/.Popen/... or os.system / os.popen.

    A bare `Popen(...)` counts ONLY when `popen_imported` is True (i.e. the file
    actually did `from subprocess import Popen`), so a locally-defined function
    named Popen is not mistaken for subprocess dispatch."""
    func = node.func
    if isinstance(func, ast.Attribute):
        attr = func.attr
        base = func.value
        if attr in _SUBPROCESS_FUNCS and isinstance(base, ast.Name) and base.id == "subprocess":
            return True
        if attr in {"system", "popen"} and isinstance(base, ast.Name) and base.id == "os":
            return True
    if popen_imported and isinstance(func, ast.Name) and func.id == "Popen":
        return True
    return False


def _lone_path_basename(value: str) -> str | None:
    """If `value` is a SINGLE path token ending in .py (no whitespace, so not a
    shell payload like 'echo hooks/x.py'), return its basename; else None."""
    if not value or any(c.isspace() for c in value):
        return None
    base = value.rsplit("/", 1)[-1]
    return base if base.endswith(".py") else None


def _hookish_basename(path: str) -> str | None:
    """Return the .py basename of `path` ONLY if the path's DIRECTORY is the
    hooks dir — using an ALLOWLIST (not a denylist), so an unrelated repo dir
    (evals/, scripts/, /tmp/, ...) can never alias onto a same-named hook.

    Accepted directories:
      - empty (a bare basename like "x.py" — real hooks dispatch builds these
        via `Path(__file__).parent / "x.py"`, whose left resolves to nothing),
      - a relative path whose LAST segment is "hooks" (e.g. "hooks/x.py"),
      - an absolute path containing a ".claude/hooks" segment.
    Anything else yields None. Whitespace-bearing strings (shell payloads) are
    already rejected by _lone_path_basename."""
    base = _lone_path_basename(path)
    if not base:
        return None
    head = path[: -len(base)].rstrip("/")
    if head == "":
        return base  # bare basename
    segs = [s for s in head.split("/") if s not in ("", ".")]
    if not head.startswith("/") and segs and segs[-1] == "hooks":
        return base  # relative .../hooks/<base>
    if head.startswith("/") and ".claude/hooks" in head:
        return base  # absolute .../.claude/hooks/<base>
    return None


def _is_file_relative_dir(node: ast.AST) -> bool:
    """True if `node` denotes the CURRENT hook file's own directory — i.e.
    `Path(__file__).parent` (optionally `.resolve()` before `.parent`). This is
    the one unresolvable left-side `/` operand we trust as the hooks dir; any
    other unresolvable directory is rejected (fail-safe), so `repo_root /
    "scripts" / "x.py"`, `some_dir / "x.py"`, etc. never alias onto a hook."""
    # Walk down through .parent / .resolve() attribute chains.
    cur = node
    saw_parent = False
    while isinstance(cur, ast.Attribute):
        if cur.attr == "parent":
            saw_parent = True
        elif cur.attr not in {"resolve", "absolute"}:
            return False
        cur = cur.value
    # A .resolve() / .parent chain ends at a call: Path(__file__) or
    # Path(__file__).resolve().
    if isinstance(cur, ast.Call):
        func = cur.func
        is_path = isinstance(func, ast.Name) and func.id in {"Path", "PurePath"}
        is_path_attr = isinstance(func, ast.Attribute) and func.attr in {"Path", "PurePath", "resolve"}
        if (is_path or is_path_attr) and cur.args:
            arg = cur.args[0]
            if isinstance(arg, ast.Name) and arg.id == "__file__":
                return saw_parent
    return False


def _resolve_path_strings(node: ast.AST, str_paths: dict[str, set[str]]) -> set[str]:
    """Resolve an expression to the set of concrete PATH STRINGS it can denote,
    composing `a + b` and `a / b` so the FINAL path is evaluated (not each
    operand independently). Recognizes only simple static forms; anything else
    (calls returning values, subscripts, attributes, f-strings) yields NOTHING
    — fail-safe, so an unresolved path never silently exempts a hook."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Name):
        return set(str_paths.get(node.id, set()))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_path_strings(node.left, str_paths)
        right = _resolve_path_strings(node.right, str_paths)
        return {a + b for a in left for b in right} if left and right else set()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        # pathlib join: the final component (basename) comes from the RIGHT
        # operand. The left is the directory; it may be an unresolvable
        # `Path(__file__).parent` (the hooks dir) — fine, the script name is on
        # the right. BUT if the left names a DIFFERENT dir (e.g.
        # `repo_root / "scripts" / "x.py"`), the script lives in scripts/, not
        # hooks/, so it must NOT be reported as a hook dispatch.
        right = _resolve_path_strings(node.right, str_paths)
        if not right:
            return set()
        left = _resolve_path_strings(node.left, str_paths)
        if not left:
            # Left unresolved. Trust it as the hooks dir ONLY when it is
            # `Path(__file__).parent` (the current hook's own directory); any
            # other unresolvable directory is rejected (fail-safe) so a script
            # outside hooks/ never aliases onto a same-named hook. We emit a
            # bare basename (the right component) so _hookish_basename accepts it
            # as a hooks-dir script.
            if _is_file_relative_dir(node.left):
                return {b for b in right}
            return set()
        return {a.rstrip("/") + "/" + b for a in left for b in right}
    # NOTE: ast.Attribute (e.g. `<expr>.parent`, `<expr>.upper`) is deliberately
    # NOT resolved as a path. A standalone attribute does not denote a script,
    # and as the left side of a `/` join its value is irrelevant (the basename
    # comes from the right operand — see the Div branch, which falls back to the
    # right component when the left is unresolvable). Resolving attributes would
    # produce silent false positives like `Path("hooks/x.py").parent` -> x.py.
    if isinstance(node, ast.Call):
        func = node.func
        is_str = isinstance(func, ast.Name) and func.id in {"str", "Path", "PurePath"}
        is_fspath = isinstance(func, ast.Attribute) and func.attr == "fspath"
        is_pathctor = isinstance(func, ast.Attribute) and func.attr in {"Path", "PurePath"}
        if (is_str or is_fspath or is_pathctor) and node.args:
            out: set[str] = set()
            for a in node.args:
                out |= _resolve_path_strings(a, str_paths)
            return out
    return set()


def _py_basenames_in_expr(node: ast.AST, str_paths: dict[str, set[str]]) -> set[str]:
    """Resolve an expression to the *.py hook SCRIPT basename(s) it denotes,
    STRUCTURALLY and FAIL-SAFE. Composes path arithmetic first (so
    "hooks/x.py" + ".bak" -> x.py.bak, not x.py), then keeps only hook-plausible
    .py basenames (see _hookish_basename). Unresolvable forms yield nothing."""
    bases: set[str] = set()
    for path in _resolve_path_strings(node, str_paths):
        base = _hookish_basename(path)
        if base:
            bases.add(base)
    return bases


_INTERPRETERS = {"python", "python3", "python2"}


def _is_interpreter_elt(elt: ast.AST) -> bool:
    """True if an argv element denotes a python interpreter — a literal
    'python3' etc., or `sys.executable`."""
    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
        return elt.value.rsplit("/", 1)[-1] in _INTERPRETERS
    if isinstance(elt, ast.Attribute) and elt.attr == "executable":
        return isinstance(elt.value, ast.Name) and elt.value.id == "sys"
    return False


def _executed_py_basename(cmd: ast.AST, str_bindings: dict[str, set[str]], shell: bool = False) -> set[str]:
    """Return the EXECUTED script basename from a command expression.

    The executed script is a SINGLE path token ending in .py at an EXECUTABLE
    position. This excludes:
      - later argv slots that hold another hook path (data, not the script),
      - a .py arg passed to a non-python program (e.g. ['echo', 'hooks/x.py']),
      - shell payloads ('echo hooks/x.py' to bash -c / a shell), which contain
        whitespace and are not a lone path token.

    For an argv list/tuple, a .py element is the script only if it is slot 0 or
    a preceding slot is a python interpreter (literal or sys.executable). For a
    bare command STRING, a multi-token string is only shell-parsed when
    shell mode; with the default (no shell) the whole string is one program
    name (a multi-token string like "python3 hooks/x.py" raises FileNotFound and
    runs nothing), so only a single-token string command can name a script.
    """
    if isinstance(cmd, (ast.List, ast.Tuple)):
        seen_interpreter = False
        for i, elt in enumerate(cmd.elts):
            # A python flag like -c / -m / -X puts the interpreter in code/module
            # mode: subsequent .py tokens are DATA, not the executed script.
            if (
                seen_interpreter
                and isinstance(elt, ast.Constant)
                and isinstance(elt.value, str)
                and elt.value.startswith("-")
            ):
                return set()
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                base = _hookish_basename(elt.value)
                if base:
                    return {base} if (i == 0 or seen_interpreter) else set()
            else:
                # Name/BinOp (a bound var, or Path(...) / "x.py"): resolves to a
                # single constructed path — the script if at slot 0 or post-interp.
                bases = _py_basenames_in_expr(elt, str_bindings)
                if bases:
                    return bases if (i == 0 or seen_interpreter) else set()
            if _is_interpreter_elt(elt):
                seen_interpreter = True
        return set()
    # Bare command string. With the default shell=False, the WHOLE string is one
    # program name — a multi-token string ("python3 hooks/x.py") is not parsed
    # and runs nothing, so only a single-token string can name a script. With
    # shell mode the string is shell-parsed: a .py is the script only at the
    # program position or directly after a python interpreter token (a -c/-m
    # flag switches to code/module mode -> no script).
    if isinstance(cmd, ast.Constant) and isinstance(cmd.value, str):
        toks = cmd.value.split()
        if not shell:
            return {b for b in [_hookish_basename(cmd.value)] if b} if len(toks) == 1 else set()
        interp = {"python", "python3", "python2"}
        for i, tok in enumerate(toks):
            if i > 0 and toks[i - 1].rsplit("/", 1)[-1] in interp and tok.startswith("-"):
                return set()
            prog = _hookish_basename(tok)
            if not prog:
                continue
            prev = toks[i - 1].rsplit("/", 1)[-1] if i > 0 else ""
            if i == 0 or prev in interp:
                return {prog}
            return set()  # first .py is a non-program arg => not a dispatch
        return set()
    # A variable/expression holding a single path (e.g. a bound _TRACKER var).
    return _py_basenames_in_expr(cmd, str_bindings)


def dispatched_targets_in_source(source: str, candidates: set[str], self_name: str = "") -> set[str]:
    """Return the subset of `candidates` (*.py basenames) that `source` passes
    into an ACTUAL subprocess/os.system call as the COMMAND argument.

    A basename qualifies only if it appears (directly, via a bound variable, or
    via `Path(...) / "x.py"`) in the first positional arg or the
    `args=`/`executable=` kwargs of a subprocess/os.system call. Dead literals
    and strings buried in env=/input=/cwd= are data, NOT dispatch targets —
    counting them would be a silent-dormancy escape hatch. Importable so the
    coverage test exercises the exact production logic.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    # Detect `from subprocess import Popen` so a bare Popen(...) call is only
    # treated as dispatch when it is the real subprocess.Popen.
    popen_imported = False
    for sub in ast.walk(tree):
        if isinstance(sub, ast.ImportFrom) and sub.module == "subprocess":
            if any(alias.name == "Popen" for alias in sub.names):
                popen_imported = True

    # Pass 1: resolve variables that hold a PATH STRING, FAIL-SAFE on ambiguity.
    # A name is usable only if it is assigned EXACTLY ONCE in the whole module
    # and that one assignment resolves (structurally) to one or more path
    # strings. A name assigned more than once (rebinding, or a different value
    # in another scope) is dropped — we cannot statically know which value
    # reaches the call, and a wrong guess would silently exempt a dormant hook.
    # Path strings (not basenames) are stored so `+`/`/` compose correctly.
    assign_counts: dict[str, int] = {}
    assign_paths: dict[str, set[str]] = {}
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Assign):
            paths = _resolve_path_strings(sub.value, {})
            for tgt in sub.targets:
                if isinstance(tgt, ast.Name):
                    assign_counts[tgt.id] = assign_counts.get(tgt.id, 0) + 1
                    assign_paths[tgt.id] = paths
    str_bindings: dict[str, set[str]] = {
        name: paths for name, paths in assign_paths.items() if paths and assign_counts[name] == 1
    }

    # Pass 2: subprocess/os.system calls — inspect only the command argument.
    out: set[str] = set()
    for sub in ast.walk(tree):
        if not (isinstance(sub, ast.Call) and _is_subprocess_call(sub, popen_imported)):
            continue
        kw_names = {kw.arg for kw in sub.keywords}
        # `executable=` overrides which program actually runs, so argv[0] is no
        # longer the executed script. Fail-safe: skip such calls (do not claim a
        # dispatch we cannot statically verify).
        if "executable" in kw_names:
            continue
        # A bare string command is only shell-parsed in shell mode; os.system /
        # os.popen always run through a shell.
        func = sub.func
        is_os_shell = isinstance(func, ast.Attribute) and func.attr in {"system", "popen"}
        shell = is_os_shell or any(
            kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in sub.keywords
        )
        cmd_exprs: list[ast.AST] = []
        if sub.args:
            cmd_exprs.append(sub.args[0])
        for kw in sub.keywords:
            if kw.arg == "args":
                cmd_exprs.append(kw.value)
        for expr in cmd_exprs:
            for base in _executed_py_basename(expr, str_bindings, shell=shell):
                if base in candidates and base != self_name:
                    out.add(base)
    return out


def dispatched_basenames() -> set[str]:
    """Hooks dispatched (subprocess-invoked) by another hook, via AST analysis.

    A hook X is 'dispatched' only if some OTHER hook passes a "X.py" path into
    an ACTUAL subprocess/os.system command. A bare/dead string literal that
    never reaches such a call does NOT count — a dispatched false-positive is a
    silent-dormancy escape hatch.
    """
    files = list(HOOKS_DIR.glob("*.py"))
    names = {p.name for p in files if p.name != "__init__.py"}
    dispatched: set[str] = set()
    for src in files:
        if src.name == "__init__.py":
            continue
        try:
            raw = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        dispatched |= dispatched_targets_in_source(raw, names, self_name=src.name)

    # Codex hooks.json invokes this wrapper before every allowlisted target.
    # It is generated from the mirror inventory rather than registered in
    # Claude settings or subprocess-dispatched by another hook source.
    codex_adapter = "codex-hook-adapter.py"
    if codex_adapter in names and parse_mirror(CODEX_MIRROR):
        dispatched.add(codex_adapter)
    return dispatched


# Zero-width / invisible code points that must NOT count toward a "reason"
# (built from code points so the source file stays free of ambiguous Unicode).
_INVISIBLE = {
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM
    0x00A0,  # NO-BREAK SPACE
    0x180E,  # MONGOLIAN VOWEL SEPARATOR
    0x2061,  # FUNCTION APPLICATION
    0x2062,  # INVISIBLE TIMES
    0x2063,  # INVISIBLE SEPARATOR
    0x2064,  # INVISIBLE PLUS
}


# Minimum substance for an allowlist reason. This is a SYNTACTIC floor, not a
# semantic check: it guarantees every allowlist entry carries a visible,
# non-trivial justification that a PR reviewer will see in the diff. Detecting
# whether that justification is *truthful* is a code-review responsibility, by
# design — the gate's job is to make silent dormancy impossible, not to grade
# prose. The floor is tuned so all real reasons (>=51 letters here) pass while
# placeholders ('', '___', '123', 'aaa', 'aa bb', invisible-Unicode) fail.
_MIN_REASON_WORDS = 2
_MIN_REASON_LETTERS = 12


def _meaningful_reason(reason: str) -> bool:
    """True if `reason` clears the syntactic substance floor (see above):
    >=2 distinct alphabetic words AND >=12 total alphabetic characters, after
    stripping zero-width/invisible code points."""
    cleaned = "".join(ch for ch in reason if ord(ch) not in _INVISIBLE)
    words = re.findall(r"[A-Za-z]{2,}", cleaned)
    total_letters = sum(len(w) for w in words)
    return len({w.lower() for w in words}) >= _MIN_REASON_WORDS and total_letters >= _MIN_REASON_LETTERS


def parse_allowlist(path: Path) -> dict[str, str]:
    """Parse 'filename.py  # reason' manifest. Returns {filename: reason} ONLY
    for entries with a MEANINGFUL reason (see _meaningful_reason).

    A bare filename or an invisible/whitespace-only "reason" is intentionally
    NOT returned, so it cannot silence the dormancy gate: such a file stays
    dormant AND is flagged by check_allowlist_entries_have_reasons(). This
    closes the bare-filename and hidden-Unicode bypasses — every allowlisted
    hook must carry an explicit, human-readable justification.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            name, reason = line.split("#", 1)
            name, reason = name.strip(), reason.strip()
            if name and _meaningful_reason(reason):
                out[name] = reason
    return out


def allowlist_entries_missing_reason(path: Path) -> list[str]:
    """Return allowlist filenames present without a meaningful '# reason'."""
    bad: list[str] = []
    if not path.exists():
        return bad
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            name, reason = line.split("#", 1)
            if name.strip() and not _meaningful_reason(reason):
                bad.append(name.strip())
        else:
            bad.append(line)
    return bad


def parse_mirror(path: Path) -> list[tuple[str, str]]:
    """Parse mirror allowlist lines 'EVENT:filename [matcher]'. Returns
    list of (event, filename)."""
    out: list[tuple[str, str]] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        spec = line.split()[0]  # drop trailing matcher token
        if ":" not in spec:
            continue
        event, fname = spec.split(":", 1)
        out.append((event.strip(), fname.strip()))
    return out


# --------------------------------------------------------------------------- #
# Individual checks: each returns list[str] of failure messages (empty == pass)
# --------------------------------------------------------------------------- #


def check_no_dormant(settings: dict) -> list[str]:
    disk = disk_hooks()
    registered = registered_basenames(settings)
    dispatched = dispatched_basenames()
    allowlist = set(parse_allowlist(ALLOWLIST_PATH))
    dormant = disk - registered - dispatched - allowlist
    if not dormant:
        return []
    msgs = []
    for f in sorted(dormant):
        msgs.append(
            f"DORMANT hook: hooks/{f} is on disk but not registered, not dispatched, "
            f"not allowlisted. Register it (scripts/register-hook.py) or add it to "
            f"scripts/hook-health-allowlist.txt with a reason."
        )
    return msgs


def check_registered_files_exist(settings: dict) -> list[str]:
    msgs = []
    for event, _matcher, cmd in iter_hook_entries(settings):
        m = CMD_BASENAME.search(cmd)
        if not m:
            continue
        fname = m.group(1)
        if not (HOOKS_DIR / fname).exists():
            msgs.append(
                f"MISSING FILE: {event} registers hooks/{fname} but no repo file exists "
                f"(would deadlock: Python exit 2 = BLOCK)."
            )
    return msgs


def check_schema(settings: dict) -> list[str]:
    msgs = []
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return ["SCHEMA: settings.json 'hooks' is not an object."]
    for event, groups in hooks.items():
        if event not in KNOWN_EVENTS:
            msgs.append(f"SCHEMA: unknown event name '{event}' (not in {sorted(KNOWN_EVENTS)}).")
        if not isinstance(groups, list):
            msgs.append(f"SCHEMA: hooks['{event}'] is not a list.")
            continue
        for group in groups:
            if not isinstance(group, dict):
                msgs.append(f"SCHEMA: {event} group is not an object.")
                continue
            if "matcher" in group and not isinstance(group["matcher"], str):
                msgs.append(f"SCHEMA: {event} matcher is not a string: {group['matcher']!r}.")
            for entry in group.get("hooks", []):
                if not isinstance(entry, dict):
                    msgs.append(f"SCHEMA: {event} hook entry is not an object.")
                    continue
                cmd = entry.get("command", "")
                if not CANONICAL_CMD.match(cmd):
                    msgs.append(
                        f"SCHEMA: {event} command not in canonical form "
                        f'python3 "$HOME/.claude/hooks/<file>.py": {cmd!r}.'
                    )
    return msgs


def check_mirror(settings: dict) -> list[str]:
    registered = registered_basenames(settings)
    msgs = []
    for path in (CODEX_MIRROR,):
        for event, fname in parse_mirror(path):
            if not (HOOKS_DIR / fname).exists():
                msgs.append(f"MIRROR: {path.name} names hooks/{fname} but no repo file exists (phantom).")
            elif fname not in registered:
                msgs.append(
                    f"MIRROR: {path.name} names {fname} (event {event}) but it is NOT registered "
                    f"in .claude/settings.json (phantom mirror entry)."
                )
    return msgs


def check_allowlist_not_stale() -> list[str]:
    msgs = []
    for fname in parse_allowlist(ALLOWLIST_PATH):
        if not (HOOKS_DIR / fname).exists():
            msgs.append(
                f"STALE ALLOWLIST: scripts/hook-health-allowlist.txt lists hooks/{fname} "
                f"but no repo file exists — remove the entry."
            )
    return msgs


def check_allowlist_entries_have_reasons() -> list[str]:
    """Every allowlist entry must carry a non-empty '# reason'. A bare filename
    must not be able to silence the dormancy gate."""
    return [
        f"ALLOWLIST: hooks/{fname} is listed without a '# reason' in "
        f"scripts/hook-health-allowlist.txt — add an explicit justification "
        f"(a bare filename cannot silence the gate)."
        for fname in allowlist_entries_missing_reason(ALLOWLIST_PATH)
    ]


# Per-event base payloads; matcher selects a representative tool_name so the
# hook actually enters its registered code path (smoke-test uses a single
# generic mock and ignores the matcher, which can mark a matcher-gated hook
# "live" without ever exercising its real path).
_EVENT_BASE = {
    "SessionStart": {"hook_event_name": "SessionStart", "session_id": "hh"},
    "UserPromptSubmit": {"hook_event_name": "UserPromptSubmit", "prompt": "hello", "session_id": "hh"},
    "PreToolUse": {"hook_event_name": "PreToolUse", "session_id": "hh"},
    "PostToolUse": {
        "hook_event_name": "PostToolUse",
        "tool_result": {"output": "ok", "is_error": False},
        "session_id": "hh",
    },
    "PreCompact": {"hook_event_name": "PreCompact", "summary": "x"},
    "PostCompact": {"hook_event_name": "PostCompact"},
    # Stop hooks may inspect the working tree and launch nested validators. A
    # neutral directory keeps this probe about hook liveness, not repo state.
    "Stop": {
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "session_id": "hh",
        "cwd": tempfile.gettempdir(),
    },
    "StopFailure": {"hook_event_name": "StopFailure"},
    "SubagentStart": {
        "hook_event_name": "SubagentStart",
        "agent_id": "hh-agent",
        "agent_type": "hh",
        "session_id": "hh",
    },
    "SubagentStop": {"hook_event_name": "SubagentStop", "tool_name": "Agent", "tool_result": "ok", "session_id": "hh"},
    "TaskCompleted": {"hook_event_name": "TaskCompleted", "task": "x", "session_id": "hh"},
}


def _matcher_tool(matcher: str) -> str | None:
    """Pick a representative tool_name from a pipe-delimited matcher string."""
    if not matcher:
        return None
    return matcher.split("|")[0].strip()


def check_matcher_liveness() -> list[str]:
    """Run each registered hook against a payload whose tool_name matches its
    group matcher, asserting exit code in {0,2}. Proves every registered hook
    RUNS on its real registered path (closes the smoke-test matcher gap)."""
    import os

    settings = load_settings()
    msgs: list[str] = []
    deployed = Path.home() / ".claude" / "hooks"
    env = {**os.environ, "REF_GATE_BYPASS": "1", "CLAUDE_HOOKS_DEBUG": ""}
    for event, matcher, cmd in iter_hook_entries(settings):
        m = CMD_BASENAME.search(cmd)
        if not m:
            continue
        fname = m.group(1)
        script = deployed / fname
        if not script.exists():
            # registered-files-exist + register-hook validate cover deployment;
            # skip here so this check is purely about runtime behavior.
            continue
        payload = dict(_EVENT_BASE.get(event, _EVENT_BASE["PostToolUse"]))
        tool = _matcher_tool(matcher)
        if tool and "tool_name" not in payload:
            payload["tool_name"] = tool
            payload.setdefault("tool_input", {"file_path": "/tmp/hh-probe.txt", "command": "ls"})
        elif tool:
            payload["tool_name"] = tool
            payload["tool_input"] = {"file_path": "/tmp/hh-probe.txt", "command": "ls"}
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(REPO_ROOT),
                env=env,
            )
        except subprocess.TimeoutExpired:
            msgs.append(f"MATCHER-LIVENESS: {event}/{fname} timed out on matcher '{matcher}'.")
            continue
        except Exception as e:
            msgs.append(f"MATCHER-LIVENESS: {event}/{fname} crashed: {e}.")
            continue
        if result.returncode not in (0, 2):
            msgs.append(
                f"MATCHER-LIVENESS: {event}/{fname} exited {result.returncode} on matcher "
                f"'{matcher}' (tool={tool}) — expected 0 or 2."
            )
    return msgs


def check_liveness() -> list[str]:
    """Delegate to smoke-test-hooks.py --ci. Returns failure msgs if it exits nonzero."""
    smoke = REPO_ROOT / "scripts" / "smoke-test-hooks.py"
    if not smoke.exists():
        return ["LIVENESS: scripts/smoke-test-hooks.py not found."]
    result = subprocess.run(
        [sys.executable, str(smoke), "--ci"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        tail = (result.stdout or result.stderr).strip().splitlines()[-5:]
        return ["LIVENESS: smoke-test-hooks.py --ci failed:"] + [f"  {ln}" for ln in tail]
    return []


DEFAULT_HOOK_ERRORS_JSONL = Path.home() / ".claude" / "learning" / "hook-errors.jsonl"
# 7 days: a 24-hour window missed adr-enforcement's 1,795-crash streak (spread
# over 8 days) while flagging only small same-day offenders. A week of lookback
# surfaces sustained crash loops without keeping long-fixed hooks failing forever.
DEFAULT_HOOK_ERROR_LOOKBACK_HOURS = 168.0

# A hook that errors more than this many times is a repeat offender.
_REPEAT_THRESHOLD = 5


def _hook_errors_path() -> Path:
    override = os.environ.get("CLAUDE_HOOK_ERRORS_PATH")
    return Path(override) if override else DEFAULT_HOOK_ERRORS_JSONL


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _count_hook_errors(
    *,
    lookback_hours: float,
    now: datetime | None,
) -> dict[str, int]:
    """Count errors per hook name inside the lookback window."""
    path = _hook_errors_path()
    if not path.is_file():
        return {}
    current = now or datetime.now(tz=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current.astimezone(timezone.utc) - timedelta(hours=lookback_hours)
    counts: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                timestamp = _parse_timestamp(entry.get("ts"))
                if timestamp is None or timestamp < cutoff:
                    continue
                hook = entry.get("hook", "unknown")
                if not isinstance(hook, str) or not hook:
                    hook = "unknown"
                counts[hook] = counts.get(hook, 0) + 1
            except (AttributeError, json.JSONDecodeError, TypeError):
                continue
    except OSError:
        return {}
    return counts


def _hook_file_exists(hook: str) -> bool:
    """True when `hooks/<hook>.py` is still present in the repo."""
    if not hook or "/" in hook or "\\" in hook or hook.startswith("."):
        return False
    return (HOOKS_DIR / f"{hook}.py").is_file()


def check_hook_error_repeat_offenders(
    *,
    lookback_hours: float = DEFAULT_HOOK_ERROR_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> list[str]:
    """Fail on hooks that repeatedly errored and still exist in the repo.

    A retired hook keeps its historical errors inside the lookback window for up
    to a week after deletion, and no maintainer action can clear them. Those are
    reported by `hook_error_repeat_offender_notes` as informational lines
    instead of being dropped, so an unrecognised hook name stays visible.
    """
    counts = _count_hook_errors(lookback_hours=lookback_hours, now=now)
    msgs: list[str] = []
    for hook, count in sorted(counts.items(), key=lambda x: -x[1]):
        if count >= _REPEAT_THRESHOLD and _hook_file_exists(hook):
            msgs.append(
                f"REPEAT-OFFENDER: hooks/{hook}.py has {count} errors in hook-errors.jsonl "
                f"in the last {lookback_hours:g} hours (threshold: {_REPEAT_THRESHOLD}). "
                "Investigate and fix the root cause."
            )
    return msgs


def hook_error_repeat_offender_notes(
    *,
    lookback_hours: float = DEFAULT_HOOK_ERROR_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> list[str]:
    """Informational lines for repeat offenders with no hook file on disk."""
    counts = _count_hook_errors(lookback_hours=lookback_hours, now=now)
    notes: list[str] = []
    for hook, count in sorted(counts.items(), key=lambda x: -x[1]):
        if count >= _REPEAT_THRESHOLD and not _hook_file_exists(hook):
            notes.append(
                f"RETIRED-HOOK: hooks/{hook}.py has {count} historical errors in "
                f"hook-errors.jsonl in the last {lookback_hours:g} hours but no longer "
                "exists in the repo. No action needed; the entries age out of the window."
            )
    return notes


def run_all(
    with_liveness: bool,
    hook_error_lookback_hours: float = DEFAULT_HOOK_ERROR_LOOKBACK_HOURS,
) -> list[str]:
    settings = load_settings()
    failures: list[str] = []
    failures += check_schema(settings)
    failures += check_no_dormant(settings)
    failures += check_registered_files_exist(settings)
    failures += check_mirror(settings)
    failures += check_allowlist_not_stale()
    failures += check_allowlist_entries_have_reasons()
    failures += check_hook_error_repeat_offenders(lookback_hours=hook_error_lookback_hours)
    if with_liveness:
        failures += check_matcher_liveness()
        failures += check_liveness()
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Composing hook-health validator")
    parser.add_argument("--ci", action="store_true", help="Exit 1 on any failure; runs liveness too")
    parser.add_argument("--with-liveness", action="store_true", help="Also run smoke-test liveness")
    parser.add_argument(
        "--hook-error-lookback-hours",
        type=float,
        default=DEFAULT_HOOK_ERROR_LOOKBACK_HOURS,
        help="Repeat-offender lookback window (default: 168 hours / 7 days)",
    )
    args = parser.parse_args()
    if args.hook_error_lookback_hours <= 0:
        parser.error("--hook-error-lookback-hours must be greater than zero")

    with_liveness = args.ci or args.with_liveness
    failures = run_all(
        with_liveness=with_liveness,
        hook_error_lookback_hours=args.hook_error_lookback_hours,
    )

    checks = [
        "schema",
        "no-dormant",
        "registered-files-exist",
        "mirror-sanity",
        "allowlist-not-stale",
        "allowlist-reasons",
        "repeat-offenders",
    ]
    if with_liveness:
        checks.append("matcher-liveness")
        checks.append("liveness")
    print(f"hook-health: ran {len(checks)} checks ({', '.join(checks)})")

    for note in hook_error_repeat_offender_notes(lookback_hours=args.hook_error_lookback_hours):
        print(f"hook-health: note: {note}")

    if failures:
        print(f"\n{len(failures)} FAILURE(S):", file=sys.stderr)
        for f in failures:
            print(f"  FAIL: {f}", file=sys.stderr)
        if args.ci:
            return 1
        return 0
    print("hook-health: ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
