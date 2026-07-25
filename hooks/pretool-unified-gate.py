#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PreToolUse Hook: Unified Gate (ADR-068)

Consolidates 5 PreToolUse gate hooks into a single entry point:
1. block-gitignore-bypass   — Bash: blocks git add -f on gitignored paths & .gitignore edits
2. pretool-git-submission-gate — Bash: blocks raw git push, gh pr create/merge
3. pretool-dangerous-command-guard — Bash: blocks destructive commands
4. pretool-creation-gate    — Write: blocks new agent/skill file creation;
                              a registered ADR named for the component
                              (scripts/adr-query.py register) unlocks the
                              path — the handshake worktree agents without
                              the Task tool can perform (see section 4)
5. pretool-sensitive-file-guard — Write+Edit: blocks writes to .env, credentials, SSH keys, etc.
                              Read: warns (does not block) on the same patterns.
6. public-dev-server-guard     — Bash: blocks dev servers bound to non-loopback interfaces
                                  (python http.server binds 0.0.0.0 by default; php -S, vite --host, etc.)
                                  Supersedes the narrow, dormant prevent-homedir-server.py.

Attribution blocking removed: use settings.json {"attribution": {"commit": "", "pr": ""}} instead.
Each check preserves its original stderr prefix and bypass mechanism.
Exit 0 always. Blocks emit JSON permissionDecision:deny to stdout. Entire main() wrapped in try/except to fail OPEN.

Creation-gate allowlist: see _CREATION_PATH_ALLOWLIST. Path shapes produced
by named non-skill-creator skills (e.g. create-voice → skills/voice-*/SKILL.md)
pass through. Without this, those skills had to bypass via /tmp + cp.

Performance: <50ms. Early-exit for non-matching tools. Only gitignore bypass uses subprocess.
"""

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import record_governance
from stdin_timeout import read_stdin

# Module-level state set by main() so _block() can enrich governance events.
_CURRENT_EVENT: dict | None = None
_CURRENT_COMMAND: str = ""

# ═══════════════════════════════════════════════════════════════
# 1. GITIGNORE BYPASS (block-gitignore-bypass.py)
# ═══════════════════════════════════════════════════════════════

# (patterns are inline in check_gitignore_bypass function)

# ═══════════════════════════════════════════════════════════════
# 2. GIT SUBMISSION PATTERNS (pretool-git-submission-gate.py)
# ═══════════════════════════════════════════════════════════════

_GIT_SUBMISSION_BYPASS = "CLAUDE_GATE_BYPASS=1"

_GIT_PUSH_PATTERN = re.compile(r"^(?:\w+=\S+\s+)*git\s+push\b")

_GIT_SUBMISSION_PATTERNS = [
    (_GIT_PUSH_PATTERN, "pr-sync", "Use /pr-sync to push (runs review loop first)"),
    (
        re.compile(r"^(?:\w+=\S+\s+)*gh\s+pr\s+create\b"),
        "pr-pipeline",
        "Use /pr-pipeline to create PR (runs review loop first)",
    ),
    (
        re.compile(r"^(?:\w+=\S+\s+)*gh\s+pr\s+merge\b"),
        "pr-pipeline",
        "Use /pr-pipeline to merge (requires review to pass first)",
    ),
]

# ═══════════════════════════════════════════════════════════════
# 3. DANGEROUS COMMAND PATTERNS (pretool-dangerous-command-guard.py)
# ═══════════════════════════════════════════════════════════════

_DANGEROUS_BYPASS_ENV = "DANGEROUS_GUARD_BYPASS"

_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Filesystem destruction (rm) moved to _rm_destructive_target (audit S2):
    # the old four regexes matched four literal command shapes and were
    # end-anchored, so `rm -rf / --no-preserve-root`, `rm -rf / # cleanup`,
    # `rm -rf -- /`, `rm -rf //`, `rm -rf $HOME`, and `rm -rf /etc` all passed.
    # Database destruction
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "database", "DROP DATABASE"),
    (re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE), "database", "DROP SCHEMA"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "database", "TRUNCATE TABLE"),
    # Permission escalation
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "permissions", "chmod 777"),
    # Force-push to protected branches moved to _force_push_protected (audit
    # S2): the old regexes hardcoded flag-before-branch order, so `git push
    # origin main --force` and the `+main` force refspec both passed.
    # Container mass-kill
    (re.compile(r"\bdocker\s+system\s+prune\s+-af\b"), "container", "docker system prune -af"),
    (re.compile(r"\bkubectl\s+delete\s+namespace\b"), "container", "kubectl delete namespace"),
    (re.compile(r"\bkubectl\s+delete\s+ns\b"), "container", "kubectl delete ns"),
    # System-level danger
    (re.compile(r"\bmkfs\b"), "system", "mkfs (format disk)"),
    (re.compile(r"\bdd\s+if="), "system", "dd (raw disk write)"),
    # Cloud destructive
    (re.compile(r"\bterraform\s+destroy\b(?!.*-target)"), "cloud", "terraform destroy (no -target)"),
    (re.compile(r"\baws\s+s3\s+rb\s+.*--force\b"), "cloud", "aws s3 rb --force"),
]

# ── rm destructive-target walk (audit S2) ────────────────────────
#
# Free-text `rm` locator + per-occurrence token walk over the arguments.
# Matches protected TARGETS instead of literal command shapes, so trailing
# arguments (`--no-preserve-root`, `# cleanup`), `--` end-of-options, repeated
# slashes, variable homes (`$HOME`), and bare system dirs (`/etc`) cannot dodge
# an end anchor. Deliberately free-text (same posture as the old regexes): it
# fires inside quoted payloads (`sh -c "rm -rf /"`) and heredoc bodies —
# over-blocking preferred for destructive commands.

# `rm` as a word anywhere in the text: covers `xargs rm`, `env rm`, `\rm`,
# `/bin/rm` (the preceding char is a non-word char in all of them).
_RM_WORD_RE = re.compile(r"\brm(?=\s)")

# Cut an occurrence's argument slice at the first command separator so a later
# command's arguments never attach to this `rm` (`rm -rf build; ls /` must not
# see `/`). `#` cuts at a comment; quotes are NOT tracked — a separator inside
# a quoted filename truncates the slice early, which can only under-collect
# targets for exotic quoting while keeping every plain form exact.
_RM_ARGS_STOP_RE = re.compile(r"[;&|\n`)#]")

# Top-level directories whose recursive removal is unrecoverable system damage.
_TOP_LEVEL_SYSTEM_DIRS = frozenset(
    {
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/lib64",
        "/opt",
        "/proc",
        "/root",
        "/sbin",
        "/srv",
        "/sys",
        "/usr",
        "/var",
    }
)

_HOME_VAR_RE = re.compile(r"^\$(?:HOME|\{HOME\})/?$")
_PROJECT_VAR_RE = re.compile(r"^\$(?:CLAUDE_PROJECT_DIR|\{CLAUDE_PROJECT_DIR\})/?$")


def _protected_rm_target(tok: str) -> str | None:
    """Description of the protected path `tok` names, or None if unprotected.

    Protected: filesystem root (any slash run, `/*`), bare home (`~`, `$HOME`),
    the project root variable, current directory (`.`), top-level system dirs
    (with or without trailing `/` or `/*`), and whole user homes
    (`/home/NAME`). Deeper paths (`./build`, `~/proj`, `/home/u/proj`) are
    NOT protected — same allow posture as the old rules.
    """
    t = tok.strip("'\"")
    if not t:
        return None
    if set(t) == {"/"}:
        return "rm -rf / (filesystem root)"
    if t.startswith("/") and set(t.rstrip("*")) == {"/"} and t.endswith("*"):
        return "rm -rf /* (filesystem root glob)"
    if t in {"~", "~/"}:
        return "rm -rf ~ (home directory)"
    if t in {".", "./"}:
        return "rm -rf . (current directory)"
    if _HOME_VAR_RE.match(t):
        return "rm -rf $HOME (home directory)"
    if _PROJECT_VAR_RE.match(t):
        return "rm -rf $CLAUDE_PROJECT_DIR (project root)"
    if t.startswith("/"):
        norm = t.rstrip("/") or "/"
        if norm.endswith("/*"):  # `/etc/*` empties the dir — same damage
            norm = norm[:-2] or "/"
        if norm in _TOP_LEVEL_SYSTEM_DIRS:
            return f"rm -rf {norm} (top-level system dir)"
        parts = norm.split("/")
        if len(parts) == 3 and parts[1] == "home" and parts[2]:
            return f"rm -rf {norm} (user home directory)"
    return None


def _rm_destructive_target(command: str) -> str | None:
    """Description if any `rm` occurrence recursively force-removes a
    protected target, else None.

    Requires a recursive flag (`-r`/`-R`/`--recursive`) plus force
    (`-f`/`--force`) or `--no-preserve-root` — the flag posture of the old
    rules (`rm -r /` alone still refuses via coreutils preserve-root and stays
    allowed). Flags may appear before or after targets; `--` ends flag parsing
    so `rm -rf -- /` cannot hide the target behind end-of-options.
    """
    for m in _RM_WORD_RE.finditer(command):
        args = command[m.end() :]
        stop = _RM_ARGS_STOP_RE.search(args)
        if stop:
            args = args[: stop.start()]
        recursive = force = no_preserve = False
        targets: list[str] = []
        end_of_flags = False
        for raw in args.split():
            tok = raw.strip("'\"")
            if not tok:
                continue
            if not end_of_flags and tok.startswith("-") and len(tok) > 1:
                if tok == "--":
                    end_of_flags = True
                elif tok == "--no-preserve-root":
                    no_preserve = True
                elif tok == "--recursive":
                    recursive = True
                elif tok == "--force":
                    force = True
                elif not tok.startswith("--"):
                    body = tok[1:]
                    if "r" in body or "R" in body:
                        recursive = True
                    if "f" in body:
                        force = True
                continue
            targets.append(tok)
        if not (recursive and (force or no_preserve)):
            continue
        for tok in targets:
            desc = _protected_rm_target(tok)
            if desc:
                return desc
    return None


# ── force-push walk (audit S2) ───────────────────────────────────

_GIT_PUSH_WORD_RE = re.compile(r"\bgit\s+push\b")
_PROTECTED_REF_RE = re.compile(r"\b(?:main|master)\b")


def _force_push_protected(command: str) -> str | None:
    """Description if any `git push` occurrence force-pushes main/master,
    else None.

    Order-independent token walk: `--force`/`-f` anywhere in the push plus a
    main/master ref anywhere blocks (`git push origin main --force` dodged the
    old flag-before-branch regexes). A `+ref` refspec IS a force push, so
    `+main`/`+refs/heads/main` blocks without any flag. `--force-with-lease`
    stays allowed (safer primitive; old rules never matched it either).
    """
    for m in _GIT_PUSH_WORD_RE.finditer(command):
        args = command[m.end() :]
        stop = _RM_ARGS_STOP_RE.search(args)
        if stop:
            args = args[: stop.start()]
        toks = [t.strip("'\"") for t in args.split()]
        force = any(t in {"-f", "--force"} for t in toks)
        protected_ref = any(_PROTECTED_REF_RE.search(t) for t in toks if not t.startswith("-"))
        plus_refspec = any(t.startswith("+") and _PROTECTED_REF_RE.search(t) for t in toks)
        if plus_refspec:
            return "git push +ref (force refspec) to main/master"
        if force and protected_ref:
            return "git push --force main/master"
    return None


# ═══════════════════════════════════════════════════════════════
# 4. CREATION GATE PATTERNS (pretool-creation-gate.py)
# ═══════════════════════════════════════════════════════════════

# DEPRECATED bypass: superseded by the ADR-registration handshake below.
# Still functional for unforeseen cases; every use is audit-logged to stderr.
_CREATION_BYPASS_ENV = "CREATION_GATE_BYPASS"

_AGENT_PATTERN = re.compile(r"/agents/[^/]+\.md$")
_SKILL_PATTERN = re.compile(r"/(skills|pipelines)/(?:[^/]+/)?[^/]+/SKILL\.md$")
_WORKFLOW_REF_PATTERN = re.compile(r"/skills/workflow/references/[^/]+\.md$")

# Component-name capture variants of the patterns above (kebab-case name).
_AGENT_NAME_RE = re.compile(r"/agents/([^/]+)\.md$")
_SKILL_NAME_RE = re.compile(r"/(?:skills|pipelines)/(?:[^/]+/)?([^/]+)/SKILL\.md$")
_WORKFLOW_REF_NAME_RE = re.compile(r"/skills/workflow/references/([^/]+)\.md$")

# ADR-registration handshake (the worktree-observable creation path).
#
# Why this exists: the gate's named remedy — dispatch skill-creator via the
# Task tool — is unobservable from worktree agents, which lack the Task tool;
# the gate also cannot observe Skill-tool invocation of skill-creator. That
# structural gap forced annotated CREATION_GATE_BYPASS writes (PR #770).
#
# The handshake anchors on a step the legitimate flow already performs: ADR
# registration via `python3 scripts/adr-query.py register --adr adr/<name>.md`,
# which writes .adr-session.json (adr_path, sha256 adr_hash, domain) into the
# session/worktree root. The gate allows a new-component Write only when a
# session file in the event cwd or an ancestor of the write target records an
# ADR whose FILENAME-derived domain equals the new component's kebab-case name
# AND whose current content hash matches the registered hash. Forging that
# marker requires writing adr/<name>.md and recording its true hash — which is
# the registration flow in substance, and the separate pretool-adr-creation-gate
# independently requires that same ADR to exist. The session file is NOT
# consumed: pretool-synthesis-gate and other consumers read it, and deleting it
# would disarm the synthesis gate.
_ADR_SESSION_FILE = ".adr-session.json"
_ADR_SESSION_WALK_LIMIT = 20

# Path-shape allowlist for components produced by non-skill-creator paths.
#
# Why this exists: the creation gate's default policy is "all new skills must
# route through skill-creator." That is correct for general-purpose skills,
# but several specialised skills are themselves the documented authoring
# pipeline for a specific kind of component. Forcing those outputs through
# skill-creator would break their methodology and (as observed) silently
# pushes agents into bypass workarounds (Write to /tmp/, then `cp`).
#
# Each entry must point to a path shape produced by exactly one well-known
# upstream skill/pipeline whose methodology is the de-facto SOP for that
# component type. Add new entries sparingly and document the producer.
#
# Maintainer note: this allowlist is intentionally narrow. Do NOT add broad
# patterns like `/skills/.+/SKILL\.md$` — that would defeat the gate. The
# correct test for a new entry is: "Is there a single, named skill whose
# documented output is this path shape?" If not, route through skill-creator.
_CREATION_PATH_ALLOWLIST: list[tuple[re.Pattern[str], str]] = [
    # voice-* skills are produced by the `create-voice` skill (Step 5: GENERATE
    # in skills/content/create-voice/SKILL.md and skills/content/create-voice/references/
    # skill-generation.md). create-voice is the canonical SOP for voice
    # profiles; it scaffolds skills/voice-{name}/SKILL.md, config.json, and
    # profile.json directly via Write.
    (re.compile(r"/skills/(?:content/)?voice-[^/]+/SKILL\.md$"), "create-voice"),
]

# ═══════════════════════════════════════════════════════════════
# 5. SENSITIVE FILE PATTERNS (pretool-sensitive-file-guard.py)
# ═══════════════════════════════════════════════════════════════

_SENSITIVE_BYPASS_ENV = "SENSITIVE_FILE_GUARD_BYPASS"

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Environment files (except .env.example)
    (re.compile(r"/\.env$"), "env", ".env"),
    (re.compile(r"/\.env\.(local|production|staging|development|dev|prod)$"), "env", ".env.*"),
    # Credential files
    (re.compile(r"/credentials\.(json|yml|yaml)$"), "credentials", "credentials file"),
    (re.compile(r"/service-account[^/]*\.json$"), "credentials", "service account JSON"),
    # SSH keys
    (re.compile(r"/\.ssh/"), "ssh", "SSH directory"),
    (re.compile(r"/id_(rsa|ed25519|ecdsa|dsa)$"), "ssh", "SSH private key"),
    # Private key / certificate files
    (re.compile(r"\.p12$"), "certificate", ".p12 certificate"),
    (re.compile(r"\.pfx$"), "certificate", ".pfx certificate"),
    (re.compile(r"\.key$"), "certificate", ".key private key"),
    (re.compile(r"\.pem$"), "certificate", ".pem private key"),
    # Cloud configs
    (re.compile(r"\.aws/credentials$"), "cloud", "AWS credentials"),
    (re.compile(r"\.kube/config$"), "cloud", "kubeconfig"),
    (re.compile(r"\.gcloud/"), "cloud", "gcloud config directory"),
    # Token files
    (re.compile(r"/token\.json$"), "token", "token.json"),
    (re.compile(r"/\.tokens$"), "token", ".tokens file"),
    # Guard control plane (audit S1): .guard-whitelist/.guard-patterns configure
    # THIS gate's dangerous/sensitive checks — writing one IS the disarm act, and
    # no agent flow legitimately writes them (owner-authored config only).
    (re.compile(r"/\.guard-(?:whitelist|patterns)$"), "guard-config", ".guard-* guard config"),
    # Credential stores the home CLAUDE.md names but the list above missed
    # (audit S4). Each holds a live credential in plaintext.
    (re.compile(r"/\.git-credentials$"), "credentials", ".git-credentials"),
    (re.compile(r"/\.netrc$"), "credentials", ".netrc"),
    (re.compile(r"/\.config/gh/hosts\.yml$"), "token", "gh CLI hosts.yml (auth token)"),
    (re.compile(r"/\.envrc$"), "env", ".envrc (direnv)"),
]

# Suffix exceptions: safe ANYWHERE. These name a file that by convention holds
# placeholders, not secrets, so their location does not change the risk.
_SENSITIVE_EXCEPTIONS: list[re.Pattern[str]] = [
    re.compile(r"\.env\.example$"),
    re.compile(r"\.env\.sample$"),
    re.compile(r"\.env\.template$"),
]

# Directory exceptions: safe ONLY inside the repo worktree (audit S4). These say
# "this is test data", which is a claim about a project's own tree. Matched
# anywhere, `/fixtures/` excused `/home/feedgen/fixtures/.env` — a real
# credential file in the home directory — from every sensitive-file check.
_SENSITIVE_DIR_EXCEPTIONS: list[re.Pattern[str]] = [
    re.compile(r"/testdata/"),
    re.compile(r"/fixtures/"),
    re.compile(r"/__fixtures__/"),
    re.compile(r"/test_?data/"),
]

# ═══════════════════════════════════════════════════════════════
# 6. PUBLIC DEV SERVER GUARD (supersedes prevent-homedir-server.py)
# ═══════════════════════════════════════════════════════════════
#
# WHY: A raw dev server bound to a non-loopback interface exposes the served
# directory to the public internet. `python -m http.server` binds 0.0.0.0 BY
# DEFAULT (all interfaces). On a public VPS this silently publishes files. The
# old prevent-homedir-server.py only blocked serving the BARE home dir and
# explicitly allowed `cd ~/project && http.server` — i.e. it permitted the exact
# unsafe pattern. This check is block-by-default for python http.server unless
# an explicit loopback bind is present, and blocks any dev server given an
# explicit non-loopback bind/host.
#
# Bound to its own bypass var, consistent with the gate's per-check convention.
_PUBLIC_SERVER_BYPASS_ENV = "PUBLIC_SERVER_GUARD_BYPASS"

# Loopback / local-only host values (lowercased).
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

# python -m http.server / SimpleHTTPServer module names (lowercased). Resolved by
# walking shlex tokens (see _python_m_module), NOT a free-text regex: a literal
# `python -m http.server` sitting inside a commit message, grep pattern, or a
# `-c "..."` payload is NOT a command invocation and must NOT match. Handles
# python / python2 / python3 / python3.11 / the `py` launcher, a space or no space
# after -m (`-m http.server`, `-mhttp.server`), and an optionally quoted module
# (`-m 'http.server'`, `-m "http.server"`).
#
# Residual (accepted, shared limit of every check in this gate): a variable-
# expanded interpreter (`p=python3; $p -m http.server`) is NOT caught because the
# command token is `$p`, not a python interpreter.
#
# Known FALSE-NEGATIVE follow-up gaps (OUT of scope for PR #719, tracked for a
# separate round — do NOT "fix" by loosening detection):
#   * bare `http-server` / `npx http-server` (binds 0.0.0.0 by default)
#   * bare `vite --host` / `next dev --host` / `vite --host --strictPort`
#   * env-var-expanded interpreter residual above
_PY_HTTP_SERVER_MODULES = frozenset({"http.server", "simplehttpserver"})

# `FOO=bar` env-assignment prefix (transparent: the real executable follows).
# Tokenized via shlex, so the value (quotes already removed) may contain spaces;
# match the assignment prefix and accept any value content.
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Transparent command wrappers — the real executable is the next NON-OPTION token.
# Their own option flags (e.g. `sudo -u nobody`, `env -i`) are stripped so they do
# not become the command token (which would hide the wrapped server). `-u`/`-g`/
# etc. that take a value: the value (a non-option token) is consumed by the normal
# "skip options" loop only if it is itself an option; a bare value token is treated
# as the next executable candidate, so we conservatively skip one token after a
# known value-taking wrapper flag.
_WRAPPERS = frozenset(
    {"sudo", "env", "exec", "command", "nohup", "time", "nice", "setsid", "stdbuf", "ionice", "doas", "timeout"}
)
# Wrappers that take a mandatory POSITIONAL value before the command, after any
# options: `timeout [opts] DURATION cmd …`. Its duration token is skipped (unless
# it is itself an executable, guarded like flag values).
_POSITIONAL_VALUE_WRAPPERS = frozenset({"timeout"})
# Exec-style runners that launch an INNER command (`npx vite`, `npm exec next`,
# `yarn dlx astro`, `pnpm dlx vite`, `bun x next`). The inner command is the real
# server, so these prefixes are stripped to expose it as the command token.
_EXEC_RUNNER_PREFIXES = (
    ("npx",),
    ("npm", "exec"),
    ("pnpm", "exec"),
    ("pnpm", "dlx"),
    ("yarn", "exec"),
    ("yarn", "dlx"),
    ("bun", "x"),
    # Python launchers that run an INNER interpreter/command. `<launcher> run
    # python3 -m http.server` must expose the inner `python3` as the command token
    # so token-anchored detection still fires (codex-found regression in PR #719:
    # token-anchoring otherwise let these real public binds slip past, where the
    # prior free-text scan blocked them). Covers the common task-runners.
    ("uv", "run"),
    ("poetry", "run"),
    ("pipx", "run"),
    ("pdm", "run"),
    ("hatch", "run"),
    ("rye", "run"),
    ("conda", "run"),
)
# Wrapper short flags that consume a following value token (so we skip that token
# too): sudo -u/-g/-C/-h/-p/-r/-t/-U; env -u NAME / -C dir; nice -n N; ionice -c
# CLASS / -n N; stdbuf -i/-o/-e. NOTE: these letters mean different things across
# wrappers (env -i is valueless; stdbuf -i takes a value), so a value token is
# NEVER consumed when it is itself a known server/runner/interpreter name (see
# _is_executable_token) — that prevents `env -i vite …` from eating `vite`.
_WRAPPER_VALUE_FLAGS = frozenset(
    {"-u", "-g", "-C", "-p", "-r", "-t", "-U", "-i", "-o", "-e", "-h", "-n", "-c", "-s", "-k"}
)
# Long wrapper value-flags in space-separated form (`sudo --user nobody`,
# `nice --adjustment 5`, `timeout --signal KILL`). The `--key=value` form is a
# single token (no value skip); this set covers `--key value`.
_WRAPPER_LONG_VALUE_FLAGS = frozenset(
    {
        "--user",
        "--group",
        "--chdir",
        "--prompt",
        "--role",
        "--type",
        "--adjustment",
        "--class",
        "--signal",
        "--kill-after",
    }
)
# Exec-runner option flags that take a VALUE (the following token is the flag's
# value — a package/env/path name — NOT the wrapped command, so it is consumed so
# the real inner command surfaces). Covers the documented value-taking options of
# every runner in _EXEC_RUNNER_PREFIXES:
#   npx:      -p/--package <pkg>, -c/--call <cmd>
#   uv run:   --with/--with-requirements <pkg>, --python/-p <ver>, --project <dir>,
#             --directory <dir>, --index <url>, --extra <name>
#   pdm run:  --venv <name>, -p/--project <dir>
#   pipx run: --spec <pkg>, --python <ver>
#   conda run: -n/--name <env>, -p/--prefix <path>
# Enumeration (not a generic skip) is required: a generic "skip non-executable
# tokens" loop desyncs when a value happens to be an executable NAME (codex-found
# PR #719: `uv run --with uvicorn python3 …` and `uv run --with flask echo …`).
# Residual (documented follow-up gap): an UNKNOWN value-taking runner flag leaves
# its value as the command token → resolves to a non-server → ALLOW (a miss, never
# a false positive). The `--key=value` form is a single token and needs no skip.
_EXEC_RUNNER_VALUE_FLAGS = frozenset(
    {
        "-p",
        "--package",
        "-c",
        "--call",
        "-n",
        "--name",
        "--prefix",
        "--with",
        "--with-requirements",
        "--python",
        "--project",
        "--directory",
        "--index",
        "--extra",
        "--spec",
        "--venv",
    }
)


def _is_executable_token(tok: str) -> bool:
    """True if `tok` (basename, lowercased) names a server/runner/interpreter.

    Used as a guard so a wrapper/runner flag's VALUE is never consumed when it is
    actually the wrapped command: `env -i vite …` must not eat `vite` as the value
    of `-i`. A real flag value (a username, niceness, fd, package) is never one of
    these executable names.
    """
    base = tok.rsplit("/", 1)[-1].lower()
    at = base.find("@", 1)  # drop a version spec (vite@latest) before matching
    if at != -1:
        base = base[:at]
    return (
        base in _JS_DEV_SERVERS
        or base in _NODE_RUNNERS
        or base in _PY_WEB_SERVERS
        or base in _SHELL_LAUNCHERS  # `env -i bash -c …` must not eat `bash`
        or base in {"php", "py"}
        or base.startswith("python")
    )


# How much of a segment `_command_token` tokenizes to find the executable.
_COMMAND_TOKEN_HEAD_BYTES = 4096

# Above this command size the per-segment walks are skipped (audit S5).
#
# The hook fails OPEN by design: a crash or a harness timeout means the tool
# runs unguarded. So scan cost is a security property, not just latency — a
# command large enough to blow the 3000ms budget gets NO deny emitted at all,
# and every check is silently disabled. This cap bounds the expensive phase so
# an oversized command degrades to the cheap whole-line patterns instead of
# degrading to nothing.
#
# 64 KB is far above any legitimate command (the largest in this repo's own
# corpus is under 4 KB) and far below the size where cost approaches the
# budget. Cheap linear patterns still run at any size; only the per-segment
# tokenizing walks are skipped, and the skip is announced on stderr so it is
# visible rather than silent.
_MAX_SEGMENT_SCAN_BYTES = 64 * 1024


def _oversized_for_segment_scan(command: str, check: str) -> bool:
    """True if `command` is too large for per-segment scanning; warns once."""
    if len(command) <= _MAX_SEGMENT_SCAN_BYTES:
        return False
    print(
        f"[{check}] ADVISORY: command is {len(command)} bytes (cap {_MAX_SEGMENT_SCAN_BYTES}); "
        f"per-segment scanning skipped to stay inside the hook timeout. "
        f"Cheap whole-command patterns still applied.",
        file=sys.stderr,
    )
    return True


# Shell keywords that precede a real command inside a compound statement.
# Stripped so the command-token walk sees the executable, not the keyword.
_COMPOUND_KEYWORDS = frozenset({"then", "do", "else", "elif"})


def _strip_compound_syntax(seg: str) -> str:
    """Strip compound-statement syntax wrapping a single command.

    Removes leading subshell/group openers and the keywords that introduce a
    command inside a conditional or loop body, plus the matching trailing
    closers. Both ends matter: `(python3 -m http.server)` needs the `(` gone so
    the command token resolves to `python3`, AND the `)` gone so the `-m` value
    resolves to `http.server` rather than `http.server)`.

    Loops because openers stack (`( { python3 …`, `then (python3 …`). Only the
    outer syntax is removed; the command body is left intact for the tokenizer.
    """
    for _ in range(8):  # bounded: stacked openers past this depth are not real usage
        stripped = seg.strip(" \t").lstrip("(){").rstrip(")};")
        head = stripped.split(None, 1)
        if head and head[0].lower() in _COMPOUND_KEYWORDS:
            stripped = head[1] if len(head) > 1 else ""
        if stripped == seg:
            return seg
        seg = stripped
    return seg


def _strip_leading_prefixes(segment: str) -> str:
    """Strip leading env-assignments, transparent wrappers, and exec-runner
    prefixes so the real executable is at the front.

    Handles `FOO=bar`, wrappers and THEIR option flags (`sudo -u nobody`, `env -i`,
    `nice -n 5`, `sudo --user nobody`), path-qualified wrappers (`/usr/bin/env`),
    and exec-style runners launching an inner command (`npx vite`, `npm exec next`,
    `yarn dlx astro`). Without this, a wrapped server (`sudo -u nobody php -S
    0.0.0.0`) or an exec-launched server (`npx vite --host 0.0.0.0`) would slip
    past command-token detection. A flag's value is not consumed when it is itself
    an executable name (guards `env -i vite …` against eating `vite`).

    Also strips leading compound-command syntax (audit S2): subshell/group
    openers `(` `{` and the shell keywords that introduce a command inside a
    conditional or loop body (`then`, `do`, `else`, `elif`). Without this,
    `(python3 -m http.server)`, `{ python3 -m http.server; }`, `if true; then
    … fi`, and `while :; do … done` all resolved to a non-executable token and
    slipped past every command-anchored guard.
    """
    seg = segment.strip().lstrip("'\"")
    seg = _strip_compound_syntax(seg)
    # shlex respects quotes so a quoted env value with spaces (`A='x y' vite …`)
    # stays one token; fall back to naive split on a parse error (unbalanced quote).
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()

    def base(tok: str) -> str:
        return tok.rsplit("/", 1)[-1].lower()

    i = 0
    changed = True
    while changed and i < len(toks):
        changed = False
        # env-assignment prefix: FOO=bar
        if i < len(toks) and _ENV_ASSIGN_RE.match(toks[i]):
            i += 1
            changed = True
            continue
        # transparent wrapper (basename-normalized) + its option flags
        if i < len(toks) and base(toks[i]) in _WRAPPERS:
            wrapper = base(toks[i])
            i += 1
            changed = True
            while i < len(toks) and toks[i].startswith("-"):
                flag = toks[i]
                i += 1
                # `-u nobody` / `--user nobody`: skip the value token too — unless it
                # is itself an executable (then it is the wrapped command, not a value).
                takes_value = flag in _WRAPPER_VALUE_FLAGS or flag in _WRAPPER_LONG_VALUE_FLAGS
                if takes_value and i < len(toks) and not toks[i].startswith("-") and not _is_executable_token(toks[i]):
                    i += 1
            # mandatory positional value (`timeout DURATION cmd`): skip it unless it
            # is itself an executable (guards against eating the wrapped command).
            if (
                wrapper in _POSITIONAL_VALUE_WRAPPERS
                and i < len(toks)
                and not toks[i].startswith("-")
                and not _is_executable_token(toks[i])
            ):
                i += 1
            continue
        # exec-style runner prefix (basename-normalized) + the runner's own option
        # flags (`npx --yes vite`, `npx -p pkg vite`), so the INNER command — not a
        # runner flag like `--yes` — becomes the executable token.
        matched = False
        for prefix in _EXEC_RUNNER_PREFIXES:
            n = len(prefix)
            if n and [base(t) for t in toks[i : i + n]] == list(prefix):
                i += n
                changed = True
                matched = True
                while i < len(toks) and toks[i].startswith("-"):
                    if toks[i] == "--":  # explicit end-of-options
                        i += 1
                        break
                    flag = toks[i]
                    i += 1
                    # `--key=value` is a single token (no value skip). For `--key
                    # value`, consume the value token EVEN when it looks like an
                    # executable name: a `--with uvicorn` / `--venv flask` value is a
                    # package/env name, NOT the wrapped command, so the
                    # _is_executable_token guard must NOT apply here (codex-found
                    # PR #719 desync: it both hid `uv run --with uvicorn python3 -m
                    # http.server` and falsely blocked `uv run --with flask echo …`).
                    if flag in _EXEC_RUNNER_VALUE_FLAGS and i < len(toks) and not toks[i].startswith("-"):
                        i += 1
                break
        if matched:
            continue
    return " ".join(toks[i:])


def _command_token(segment: str) -> str:
    """Return the lowercased executable token of a shell segment.

    Anchors server-name detection to the COMMAND, not a free-floating word in an
    argument (so `git commit -a -m next` does not match the `next` dev server).
    Returns the basename so `/usr/bin/vite` and `./node_modules/.bin/vite` match,
    and strips a trailing `@version` so `npx vite@latest` still resolves to `vite`.
    """
    # Only the LEADING prefix chain matters here, so tokenize just the head of
    # the segment (audit S5). `_strip_leading_prefixes` shlex-splits whatever it
    # is given, and shlex is super-linear: on a 600 KB command this single call
    # cost 5.7s of the hook's ~6s total. No real wrapper chain
    # (`sudo -u x env -i npx --yes …`) approaches this many characters.
    seg = _strip_leading_prefixes(segment[:_COMMAND_TOKEN_HEAD_BYTES])
    m = re.match(r"['\"]?([^\s'\"]+)", seg)
    if not m:
        return ""
    tok = m.group(1).rsplit("/", 1)[-1].lower()
    # Drop a package version spec (`vite@latest`, `http-server@14`). A leading `@`
    # (scoped pkg like `@angular/cli`) is preserved by only splitting after char 0.
    at = tok.find("@", 1)
    if at != -1:
        tok = tok[:at]
    return tok


def _is_python_interpreter(tok: str) -> bool:
    """True if `tok` (a raw command token) names a python interpreter.

    Matches `python`, `python2`, `python3`, `python3.11`, and the `py` launcher,
    path-qualified or not. Used to anchor `-m <module>` detection to a genuine
    interpreter command so a literal module string in an argument never matches.
    """
    base = tok.rsplit("/", 1)[-1].lower()
    return base == "py" or base.startswith("python")


def _python_m_module(segment: str) -> str | None:
    """Return the lowercased `-m <module>` module run by a python interpreter, else None.

    Walks shlex TOKENS (after leading wrappers/env-assignments are stripped
    upstream), not free text. This is the fix for PR #719's HIGH-1 false
    positives: a literal `python -m http.server` inside a commit message, a grep
    pattern, or a `-c "..."` payload is a single shlex token (or sits in one), so
    no real `-m` flag token is found and the function returns None → ALLOW.

    Mirrors the flask/uvicorn `-m` resolution but is token-anchored so it cannot
    fire on free-floating text. Handles `-m module`, `-mmodule` (no space), and an
    optionally quoted module (`-m 'http.server'`). Stops scanning a `-c <payload>`
    argument's value (the payload is its own token; any `-m` inside it is data).
    """
    seg = _strip_leading_prefixes(segment)
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()
    if not toks or not _is_python_interpreter(toks[0]):
        return None
    i = 1
    while i < len(toks):
        t = toks[i]
        if t == "-m":
            if i + 1 < len(toks):
                return toks[i + 1].strip("'\"").lower()
            return None
        if t.startswith("-m") and len(t) > 2 and not t.startswith("--"):
            return t[2:].strip("'\"").lower()  # combined `-mhttp.server`
        if t == "-c" or t == "--command":
            i += 2  # skip the payload value token; `-m` inside it is data
            continue
        i += 1
    return None


# Node task runners (npm/pnpm/yarn/bun) recognized as the COMMAND token. On their
# own they default to localhost (do NOT over-block), but `npm run dev -- --host
# 0.0.0.0` forwards an explicit public host flag, caught by the host-flag scan.
_NODE_RUNNERS = frozenset({"npm", "pnpm", "yarn", "bun"})

# Explicit bind flag value on a python http.server invocation (http.server uses
# --bind/-b). Captures bracketed IPv6 too: --bind [::1].
_PY_BIND_RE = re.compile(r"(?:--bind(?:\s+|=)|(?<![\w-])-b\s+)['\"]?(\[[^\]]+\]|[^\s'\"]+)")

# Long-form public-bind/host flags used by node/JS/go/python dev servers:
#   --bind/--host/--listen/--address <value>. Supports `=` form. Always scanned —
#   long flags do not collide with common non-server short flags.
_HOST_FLAG_RE = re.compile(r"(?:--(?:bind|host|listen|address)(?:\s+|=))['\"]?(\[[^\]]+\]|[^\s'\"]+)")

# Value-less `--host` / `-H` on a JS dev server (#720). In Vite/Nuxt/Next a bare
# `--host` (or `-H`) with no value — i.e. end of segment, or the next token is
# ANOTHER flag (`vite --host --strictPort`) — means "listen on ALL interfaces"
# (equivalent to 0.0.0.0). The host-flag scans above require a value token, so
# this slips through unless detected explicitly. Captures: `--host` / `-H` /
# `--host=` with nothing after, OR followed by a flag, OR end of string.
_VALUELESS_HOST_FLAG_RE = re.compile(r"(?:--host|(?<![\w-])-H)(?:=\s*)?(?=\s*$|\s+-)")


# Per-server SHORT bind/host flags. Each server uses a DIFFERENT short letter, and
# those letters collide with unrelated tools (git -a, curl -H, ssh -b) AND with
# other servers' unrelated flags (ng's passthrough -a is not a host). So a short
# flag is honored only for the specific server that uses it for binding:
#   next -H <host>;  http-server -a <addr>;  gunicorn -b <host:port>;  flask -h.
# Built once; compiled regexes capture the flag's value (bracketed IPv6 too).
def _short_flag_re(letter: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w-])-{letter}(?:\s+|=)?['\"]?(\[[^\]]+\]|[^\s'\"]+)")


_SERVER_SHORT_FLAGS: dict[str, re.Pattern[str]] = {
    "next": _short_flag_re("H"),
    "http-server": _short_flag_re("a"),
    "gunicorn": _short_flag_re("b"),
    "flask": _short_flag_re("h"),  # `flask run -h <host>` is short for --host
    # `serve -l <listen>` takes `tcp://HOST:PORT`, a bare port, or a unix socket
    # (audit S3). Scoped to the `serve` command token, never scanned globally:
    # `-l` is far too common an unrelated flag (`ls -l`) to put in _HOST_FLAG_RE.
    "serve": _short_flag_re("l"),
}

# php -S <host>:<port>  (built-in PHP dev server; binds exactly the given host).
_PHP_SERVER_RE = re.compile(r"\bphp\b[^|;&]*?\s-S\s+['\"]?(\[[^\]]+\]|[^\s'\":]+)")

# `php artisan serve` (Laravel dev server). Only THIS php subcommand exposes a
# server via --host; a plain `php script.php --host …` is an ordinary CLI script.
_PHP_ARTISAN_SERVE_RE = re.compile(r"\bartisan\s+serve\b")

# Client-side JS/static dev servers whose --host flag exposes the server publicly,
# matched as the COMMAND token (not a free-floating word).
_JS_DEV_SERVERS = frozenset(
    {
        "vite",
        "next",
        "nuxt",
        "http-server",
        "hugo",
        "webpack",
        "webpack-dev-server",
        "ng",
        "astro",
        "remix",
        "svelte-kit",
        "vue-cli-service",
        # `serve` (the npm static-file server). The home CLAUDE.md names
        # `npx serve -l tcp://0.0.0.0` as forbidden by default, but the command
        # was not recognized as a server at all, so it was ALLOWED (audit S3).
        "serve",
    }
)

# Python web servers (flask run, uvicorn, gunicorn) that expose a public host
# through a --host/--bind/-b flag. Caught by the long-flag scan (plus gunicorn's
# -b short flag). Recognized either as their own console-script command token or
# via `python -m <module>`, resolved by the token-anchored _python_m_module.
_PY_WEB_SERVERS = frozenset({"flask", "uvicorn", "gunicorn"})


# A `scheme://` prefix on a bind value (`serve -l tcp://0.0.0.0:3000`).
_HOST_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://")
# A trailing `:port` on an unbracketed host (`0.0.0.0:3000`). Not applied to a
# bare IPv6 address (`::`, `fe80::1`), which is why bracketing is required for
# IPv6-with-port and why a multi-colon value is left alone.
_HOST_PORT_RE = re.compile(r"^([^:]+):\d+$")


def _normalize_host_value(low: str) -> str:
    """Reduce a bind value to its bare host: drop `scheme://` and `:port`.

    Without this, `serve -l tcp://127.0.0.1:3000` reads as a non-loopback host
    and over-blocks, while the loopback checks below only ever saw bare
    addresses. `[::]:8080` keeps its brackets so the IPv6 wildcard still matches.
    """
    low = _HOST_SCHEME_RE.sub("", low)
    if low.startswith("["):  # `[::1]:8080` → `[::1]`
        end = low.find("]")
        if end != -1:
            return low[: end + 1]
        return low
    m = _HOST_PORT_RE.match(low)
    return m.group(1) if m else low


def _host_is_public(host: str) -> bool:
    """Return True if a host/bind value exposes a non-loopback interface.

    Bare `0` is the classic shorthand for 0.0.0.0. Empty/odd values fail safe
    (treated as public → block). IPv6 `::` / `[::]` is the wildcard. Any
    concrete non-loopback IP or hostname on an explicit bind flag is public.
    A value starting with `-` is another flag, not a host → NOT public.
    """
    h = host.strip().strip("'\"")
    if not h:
        return True  # flag present with no usable value — fail safe (block)
    if h.startswith("-"):
        return False  # captured token is a flag, not a host address
    low = _normalize_host_value(h.lower())
    if low in _LOCAL_HOSTS:
        return False
    if low.startswith("127."):  # IPv4 loopback range (127.x)
        return False
    if low in {"0.0.0.0", "0", "::", "[::]", "*", "[::0]", "::0"}:  # wildcards
        return True
    # Any other concrete host on an explicit public-bind flag → non-loopback.
    return True


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _load_guard_whitelist() -> list[str]:
    """Load per-project whitelist from .guard-whitelist if it exists."""
    whitelist_path = Path.cwd() / ".guard-whitelist"
    if not whitelist_path.is_file():
        return []
    try:
        entries = []
        for line in whitelist_path.read_text().splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#"):
                continue
            if len(entry) < 8:
                print(
                    f"[dangerous-command-guard] WARN: Skipping short whitelist entry (< 8 chars): {entry!r}",
                    file=sys.stderr,
                )
                continue
            entries.append(entry)
        print(
            f"[dangerous-command-guard] INFO: Loaded {len(entries)} whitelist entries ({whitelist_path})",
            file=sys.stderr,
        )
        return entries
    except OSError:
        return []


def _is_whitelisted(command: str, whitelist: list[str]) -> bool:
    """True if the FULL command exactly matches a whitelist entry.

    Full-command anchoring, not substring containment: substring matching let
    any command smuggle a whitelisted string past the guard (a `node_modules`
    entry allowed `echo node_modules && rm -rf /` — audit S1). One entry
    whitelists exactly one command, nothing more.
    """
    cmd = command.strip()
    return any(entry == cmd for entry in whitelist)


def _load_guard_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Load per-project sensitive patterns from .guard-patterns.

    Entries are treated as glob-like patterns: ``*`` matches any sequence,
    ``?`` matches a single character, and all other regex metacharacters
    are escaped.  Malformed entries that fail ``re.compile`` are logged to
    stderr and skipped so that a single bad line cannot disable the entire
    sensitive-file guard.
    """
    guard_path = Path.cwd() / ".guard-patterns"
    if not guard_path.is_file():
        return []
    extra: list[tuple[re.Pattern[str], str, str]] = []
    try:
        for line in guard_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Escape ALL regex metacharacters first, then selectively
                # convert glob wildcards back to their regex equivalents.
                regex = re.escape(line)
                regex = regex.replace(r"\*", ".*")  # glob * -> regex .*
                regex = regex.replace(r"\?", ".")  # glob ? -> regex .
                try:
                    extra.append((re.compile(regex), "custom", line))
                except re.error as exc:
                    print(
                        f"[sensitive-file-guard] WARN: Skipping malformed .guard-patterns entry {line!r}: {exc}",
                        file=sys.stderr,
                    )
    except OSError:
        pass
    return extra


def _repo_worktree_root() -> Path | None:
    """Nearest ancestor of cwd containing `.git`, or None outside a repo.

    Walks the filesystem instead of shelling out to git: this runs on every
    sensitive-file check and the hook has a hard latency budget.
    """
    try:
        here = Path.cwd().resolve()
    except OSError:
        return None
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _is_sensitive_exception(file_path: str) -> bool:
    """Check if `file_path` matches a sensitive-file exception.

    Suffix exceptions (`.env.example` and friends) apply anywhere. Directory
    exceptions (`/fixtures/`, `/testdata/`, …) apply ONLY inside the repo
    worktree — a "this is test data" claim is only meaningful about a
    project's own tree, and honoring it anywhere excused real credential
    files elsewhere on the box (audit S4).
    """
    if any(p.search(file_path) for p in _SENSITIVE_EXCEPTIONS):
        return True
    if not any(p.search(file_path) for p in _SENSITIVE_DIR_EXCEPTIONS):
        return False
    root = _repo_worktree_root()
    if root is None:
        return False
    try:
        resolved = Path(file_path).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == root or root in resolved.parents


def _block(message: str, tool_name: str = "", reason: str = "") -> None:
    """Emit a structured deny decision and exit 0.

    Keeps the stderr message for debug visibility (Ctrl+O verbose mode)
    and emits JSON permissionDecision to stdout so Claude Code surfaces
    the reason to the model rather than a generic error.
    """
    print(message, file=sys.stderr)
    try:
        record_governance(
            "hook_blocked",
            hook_name="pretool-unified-gate",
            tool_name=tool_name,
            hook_phase="pre",
            severity="high",
            blocked=True,
            event=_CURRENT_EVENT,
            command=_CURRENT_COMMAND,
        )
    except Exception:
        pass  # Never let recording prevent a block
    deny_reason = reason if reason else message
    deny_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    print(json.dumps(deny_output))
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════
# CHECK FUNCTIONS — each returns normally (allow) or calls _block (JSON deny + exit 0)
# ═══════════════════════════════════════════════════════════════


def check_gitignore_bypass(command: str) -> None:
    """Block git add -f on gitignored paths and .gitignore edits."""
    # Block 1: .gitignore modification attempts
    cmd_part = command.split("<<")[0] if "<<" in command else command
    if (
        re.search(r"(>|>>)\s*\.gitignore", cmd_part)
        or re.search(r"(sed|awk|tee)\b.*\.gitignore", cmd_part)
        or re.search(r"mv\s+\S+\s+\.gitignore", cmd_part)
    ):
        _block(
            "[gitignore-bypass] BLOCKED: Agents must not modify .gitignore.\n"
            "[gitignore-bypass] This file controls repository safety boundaries.",
            reason="Agents must not modify .gitignore. This file controls repository safety boundaries.",
        )

    # Fast path: no git add in command
    if "git add" not in command:
        return

    # Block 2: git add with force flags
    if not re.search(r"git\s+add\s+.*(-f|--force)", command):
        return

    # Extract paths being force-added
    parts = command.split()
    try:
        add_idx = parts.index("add")
    except ValueError:
        return

    paths = []
    past_separator = False
    for part in parts[add_idx + 1 :]:
        if part == "--":
            past_separator = True
            continue
        if part.startswith("-") and not past_separator:
            continue
        paths.append(part)

    if not paths:
        return

    # Check which paths are gitignored
    try:
        result = subprocess.run(
            ["git", "check-ignore"] + paths,
            capture_output=True,
            text=True,
            timeout=3,
        )
        ignored = [p for p in result.stdout.strip().split("\n") if p]
    except (subprocess.TimeoutExpired, OSError):
        return  # Don't block on check failure

    if ignored:
        _block(
            f"[gitignore-bypass] BLOCKED: git add -f on gitignored paths: {', '.join(ignored)}\n"
            "[gitignore-bypass] These paths are gitignored for a reason. Do not force-add them.",
            reason=f"Cannot force-add gitignored paths: {', '.join(ignored)}. These paths are gitignored for a reason. Stage only tracked files.",
        )


def _extract_effective_cwd(command: str, default_cwd: str | None = None) -> str | None:
    """Extract the effective working directory from a command string.

    Detects two patterns:
    - ``cd <path> && ...`` or ``cd <path> ; ...`` prefix
    - ``git -C <path> ...`` flag

    Returns the extracted path if found, otherwise default_cwd.
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


def _is_worktree_on_feature_branch(cwd: str) -> bool:
    """Return True if cwd is a worktree directory on a non-protected branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return bool(branch) and branch not in {"main", "master"}
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


def check_git_submission(command: str) -> None:
    """Block raw git push, gh pr create, gh pr merge unless bypassed or personal profile."""
    # Skills prefix blocked commands with CLAUDE_GATE_BYPASS=1 to pass through
    if command.lstrip().startswith(_GIT_SUBMISSION_BYPASS):
        return

    # Personal operator profile: full autonomy, no approval gates
    operator = os.environ.get("CLAUDE_OPERATOR_PROFILE", "personal")
    if operator == "personal":
        return

    cmd = command.lstrip()
    for pattern, skill_name, message in _GIT_SUBMISSION_PATTERNS:
        if pattern.search(cmd):
            # Allow git push from worktree directories on feature branches
            if pattern is _GIT_PUSH_PATTERN:
                effective_cwd = _extract_effective_cwd(command)
                project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
                if effective_cwd and effective_cwd != project_dir and _is_worktree_on_feature_branch(effective_cwd):
                    return
            _block(
                f"[git-submission-gate] BLOCKED: {message}\n[fix-with-skill] {skill_name}",
                reason=f"{message} Use the {skill_name} skill instead.",
            )


def check_dangerous_command(command: str) -> None:
    """Block destructive commands unless bypassed or whitelisted."""
    if os.environ.get(_DANGEROUS_BYPASS_ENV) == "1":
        return

    # Load whitelist once before scanning rather than on each match.
    whitelist = _load_guard_whitelist()

    # Functional walks (audit S2) share the regex rules' whitelist contract:
    # a full-command whitelist entry skips the rule, nothing else does.
    for check, category in ((_rm_destructive_target, "filesystem"), (_force_push_protected, "git")):
        description = check(command)
        if description and not _is_whitelisted(command, whitelist):
            _block(
                f"[dangerous-command] BLOCKED: {description} ({category})\n"
                f"[dangerous-command] Command: {command}\n"
                f"[dangerous-command] To allow: add pattern to .guard-whitelist",
                reason=f"Dangerous command blocked: {description} (category: {category}). To allow, add a pattern to .guard-whitelist.",
            )

    # Intentionally scans full command including heredoc bodies.
    # Over-blocking preferred for destructive commands.
    for pattern, category, description in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            if _is_whitelisted(command, whitelist):
                # Skip THIS rule only — a whitelist hit must never end the whole
                # scan (`return` here let one hit disarm every later rule, audit S1).
                continue
            _block(
                f"[dangerous-command] BLOCKED: {description} ({category})\n"
                f"[dangerous-command] Command: {command}\n"
                f"[dangerous-command] To allow: add pattern to .guard-whitelist",
                reason=f"Dangerous command blocked: {description} (category: {category}). To allow, add a pattern to .guard-whitelist.",
            )


def _creation_component_name(file_path: str) -> str | None:
    """Return the kebab-case component name for a gated creation path."""
    for pattern in (_AGENT_NAME_RE, _WORKFLOW_REF_NAME_RE, _SKILL_NAME_RE):
        match = pattern.search(file_path)
        if match:
            return match.group(1)
    return None


def _iter_adr_session_files(file_path: str, cwd: str):
    """Yield existing .adr-session.json files: event cwd first, then ancestors
    of the write target (covers worktree roots without a usable cwd)."""
    candidates: list[Path] = []
    if cwd:
        candidates.append(Path(cwd))
    parent = Path(file_path).parent
    for _ in range(_ADR_SESSION_WALK_LIMIT):
        candidates.append(parent)
        if parent == parent.parent:
            break
        parent = parent.parent
    seen: set[Path] = set()
    for directory in candidates:
        if directory in seen:
            continue
        seen.add(directory)
        session_file = directory / _ADR_SESSION_FILE
        try:
            if session_file.is_file():
                yield session_file
        except OSError:
            continue


def _adr_registration_allows(component: str, file_path: str, cwd: str) -> str | None:
    """Return the registered ADR path that unlocks `component`, or None.

    Allows only when a session file records an ADR that (a) lives in an adr/
    directory, (b) derives the same kebab-case domain as the component from
    its FILENAME (the session's domain field is a prefilter, never trusted
    alone), and (c) still hashes to the registered sha256 — the artifact
    `scripts/adr-query.py register` produces. Anything less stays blocked.
    """
    for session_file in _iter_adr_session_files(file_path, cwd):
        try:
            session = json.loads(session_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(session, dict) or session.get("domain") != component:
            continue
        adr_path = Path(str(session.get("adr_path", "")))
        if not adr_path.name:
            continue
        if not adr_path.is_absolute():
            base = str(session.get("cwd") or "") or str(session_file.parent)
            adr_path = Path(base) / adr_path
        try:
            adr_path = adr_path.resolve()
        except OSError:
            continue
        # Registration enforces the ADR lives under the repo's adr/ directory.
        if "adr" not in adr_path.parent.parts:
            continue
        # Re-derive the domain from the ADR filename (adr-query.py rule:
        # stem, minus a "pipeline-" prefix) — a forged session JSON cannot
        # just claim the component's name.
        stem = adr_path.stem
        derived = stem[len("pipeline-") :] if stem.startswith("pipeline-") else stem
        if derived != component:
            continue
        try:
            digest = "sha256:" + hashlib.sha256(adr_path.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest == session.get("adr_hash"):
            return str(adr_path)
    return None


def check_creation_gate(file_path: str, cwd: str = "") -> None:
    """Block new agent/skill creation without a registered ADR handshake.

    Allow order: non-component path → existing file (update) → producer
    allowlist → DEPRECATED bypass env (audit-logged) → ADR-registration
    handshake (audit-logged). Everything else blocks.
    """
    is_agent = bool(_AGENT_PATTERN.search(file_path))
    is_skill = bool(_SKILL_PATTERN.search(file_path))
    is_workflow_ref = bool(_WORKFLOW_REF_PATTERN.search(file_path))
    if not is_agent and not is_skill and not is_workflow_ref:
        return

    # Allow overwrites of existing files (update, not creation)
    if os.path.exists(file_path):
        return

    # Allow creation paths produced by named upstream skills (see
    # _CREATION_PATH_ALLOWLIST docstring).
    for allowed_pattern, _producer in _CREATION_PATH_ALLOWLIST:
        if allowed_pattern.search(file_path):
            return

    # DEPRECATED bypass — kept functional for unforeseen cases, always audited.
    if os.environ.get(_CREATION_BYPASS_ENV) == "1":
        print(
            f"[creation-gate] DEPRECATED: {_CREATION_BYPASS_ENV}=1 bypass used for {file_path}. "
            "Prefer the ADR handshake: python3 scripts/adr-query.py register --adr adr/<name>.md",
            file=sys.stderr,
        )
        return

    component_type = "agent" if is_agent else "workflow reference" if is_workflow_ref else "skill"
    component = _creation_component_name(file_path)
    if component:
        adr_path = _adr_registration_allows(component, file_path, cwd)
        if adr_path:
            # Audit line: every handshake allow is visible in verbose mode.
            print(
                f"[creation-gate] ALLOW: registered ADR {adr_path} unlocks new {component_type} '{component}'.",
                file=sys.stderr,
            )
            return

    component_label = component or "<name>"
    _block(
        f"[creation-gate] BLOCKED: New {component_type} must be created via skill-creator or skill-creation-pipeline.\n"
        f"[creation-gate] Path: {file_path}\n"
        f"[creation-gate] No Task tool (worktree agent)? Invoke the skill-creator skill, write the ADR, register it:\n"
        f"[creation-gate]   python3 scripts/adr-query.py register --adr adr/{component_label}.md\n"
        f"[creation-gate] A registered ADR named '{component_label}' unlocks this path; retry the Write after registering.\n"
        f"[fix-with-agent] skill-creator",
        reason=(
            f"New {component_type} files must be created via the skill-creator agent "
            f"([fix-with-agent] skill-creator). Worktree agents without the Task tool: invoke "
            f"skill-creator as a skill, write adr/{component_label}.md, run "
            f"`python3 scripts/adr-query.py register --adr adr/{component_label}.md`, then retry this Write."
        ),
    )


def check_sensitive_file(file_path: str, *, deny: bool = True) -> None:
    """Flag access to sensitive files unless bypassed or excepted.

    Write/Edit (deny=True, default): hard block. Creating or changing a
    credential file is the act CLAUDE.md's secret rules exist to stop, and
    this file already denies equivalent-risk write-adjacent acts (chmod
    loosening a key, git-add staging one). Deny keeps Write/Edit consistent.

    Read (deny=False): warn/log only, no block. A Read does not mutate, and
    agents here routinely read a project's own .env during ordinary
    debugging — blocking that breaks common legitimate work for less
    benefit than Write's block gives. Warn matches this file's existing
    posture for other context-dependent, non-mutating risks (see the
    sysadmin-guard WARN-only patterns, _check_sysadmin_segment).
    """
    if os.environ.get(_SENSITIVE_BYPASS_ENV) == "1":
        return

    if _is_sensitive_exception(file_path):
        return

    all_patterns = _SENSITIVE_PATTERNS + _load_guard_patterns()
    for pattern, category, description in all_patterns:
        if pattern.search(file_path):
            if not deny:
                print(
                    f"[sensitive-file-guard] ADVISORY: Read of sensitive file ({category})\n"
                    f"[sensitive-file-guard] Path: {file_path}\n"
                    f"[sensitive-file-guard] Pattern: {description}\n"
                    f"[sensitive-file-guard] Reading credential files needs owner approval "
                    f"(OWNER-APPROVED-SECRET-READ) per CLAUDE.md. Not blocked — flagged for review.",
                    file=sys.stderr,
                )
                return
            _block(
                f"[sensitive-file-guard] BLOCKED: Write to sensitive file ({category})\n"
                f"[sensitive-file-guard] Path: {file_path}\n"
                f"[sensitive-file-guard] Pattern: {description}\n"
                # The bypass env is honored but deliberately NOT advertised
                # here (audit S5). Printing it taught the operator to disarm
                # the guard as the first response to a block — and this file
                # already made the opposite choice for the guard-integrity and
                # sysadmin denies, whose messages withhold the same hint.
                f"[sensitive-file-guard] Writing a credential file needs explicit owner approval per CLAUDE.md.",
                reason=(
                    f"Write to sensitive file blocked ({category}: {description}). Path: {file_path}. "
                    f"Creating or changing a credential file needs explicit owner approval per CLAUDE.md."
                ),
            )


# ── sensitive files reached via Bash (audit S4) ──────────────────
#
# `check_sensitive_file` ran only in the Write/Edit/Read tool branches, so the
# identical acts spelled as a shell command were never examined at all:
# `cat ~/.ssh/id_ed25519`, `cp ~/.env /var/www/html/`, and `cat > ~/.env` all
# passed while the Write-tool equivalents were denied.
#
# Posture deliberately mirrors the tool branches rather than inventing a
# stricter one for Bash:
#   * COPY/WRITE verbs and redirect targets DENY — they duplicate a secret to a
#     new location or mutate a credential file, which is what Write/Edit deny.
#   * READ verbs WARN only — same as the Read tool, and for the same reason
#     documented there: agents routinely read a project's own .env while
#     debugging, and blocking that breaks common legitimate work.

# Verbs that duplicate or mutate a file → deny on a sensitive path in any
# argument position (source OR destination: copying a secret out is the
# exfiltration shape the home CLAUDE.md forbids).
_SENSITIVE_COPY_VERBS = frozenset({"cp", "mv", "scp", "rsync", "install", "tee", "dd", "rclone"})

# Verbs that only display a file → warn.
_SENSITIVE_READ_VERBS = frozenset(
    {
        "cat",
        "bat",
        "less",
        "more",
        "head",
        "tail",
        "od",
        "xxd",
        "hexdump",
        "strings",
        "base64",
        "nl",
        "cut",
        "sort",
        "uniq",
        "wc",
    }
)

# An output redirect target (`> path`, `>> path`, `2> path`). Writing here
# creates or truncates the named file, so it is a write regardless of verb.
_REDIRECT_TARGET_RE = re.compile(r"(?<!<)>>?\s*['\"]?([^\s'\"|;&<>]+)")


def _sensitive_bash_paths(segment: str) -> tuple[list[str], list[str]]:
    """Return (deny_paths, warn_paths) for one shell segment.

    Redirect targets are always write paths. Otherwise the segment's command
    token picks the posture; a segment led by neither kind of verb yields
    nothing (an unrecognized command's arguments are not assumed to be files).
    """
    deny_paths = [m.group(1) for m in _REDIRECT_TARGET_RE.finditer(segment)]

    verb = _command_token(segment)
    if verb not in _SENSITIVE_COPY_VERBS and verb not in _SENSITIVE_READ_VERBS:
        return deny_paths, []

    try:
        toks = shlex.split(_strip_leading_prefixes(segment), posix=True)
    except ValueError:
        toks = _strip_leading_prefixes(segment).split()
    args = [t for t in toks[1:] if not t.startswith("-")]
    if verb in _SENSITIVE_COPY_VERBS:
        return deny_paths + args, []
    return deny_paths, args


def _matches_sensitive(path: str) -> tuple[str, str] | None:
    """Return (category, description) if `path` is sensitive, else None.

    Normalizes `~` so `~/.env` matches the same anchored patterns an absolute
    path does — the patterns are rooted at `/`, so an un-expanded `~` never
    matched anything.
    """
    expanded = os.path.expanduser(path)
    if not expanded.startswith("/"):
        expanded = str(Path.cwd() / expanded)
    if _is_sensitive_exception(expanded):
        return None
    for pattern, category, description in _SENSITIVE_PATTERNS + _load_guard_patterns():
        if pattern.search(expanded):
            return category, description
    return None


def check_sensitive_bash(command: str) -> None:
    """Deny/warn when a Bash command reads, copies, or overwrites a secret."""
    if os.environ.get(_SENSITIVE_BYPASS_ENV) == "1":
        return

    if _oversized_for_segment_scan(command, "sensitive-file-guard"):
        return

    for line in _non_heredoc_lines(command):
        for segment in _SEGMENT_SPLIT_RE.split(line):
            if not segment.strip():
                continue
            deny_paths, warn_paths = _sensitive_bash_paths(segment)
            for path in deny_paths:
                hit = _matches_sensitive(path)
                if hit:
                    category, description = hit
                    _block(
                        f"[sensitive-file-guard] BLOCKED: shell command writes or copies a sensitive file ({category})\n"
                        f"[sensitive-file-guard] Path: {path}\n"
                        f"[sensitive-file-guard] Pattern: {description}\n"
                        f"[sensitive-file-guard] Command: {command}",
                        reason=(
                            f"Shell command writes or copies a sensitive file ({category}: {description}). "
                            f"Path: {path}. Duplicating or overwriting a credential file needs explicit owner "
                            f"approval per CLAUDE.md."
                        ),
                    )
            for path in warn_paths:
                hit = _matches_sensitive(path)
                if hit:
                    category, description = hit
                    print(
                        f"[sensitive-file-guard] ADVISORY: shell command reads a sensitive file ({category})\n"
                        f"[sensitive-file-guard] Path: {path}\n"
                        f"[sensitive-file-guard] Pattern: {description}\n"
                        f"[sensitive-file-guard] Reading credential files needs owner approval "
                        f"(OWNER-APPROVED-SECRET-READ) per CLAUDE.md. Not blocked — flagged for review.",
                        file=sys.stderr,
                    )


# ═══════════════════════════════════════════════════════════════
# 5b. GUARD SELF-PROTECTION (audit S1)
# ═══════════════════════════════════════════════════════════════
#
# ~/.claude/hooks symlinks into this repo, so a Write/Edit to hooks/<hook>.py —
# via EITHER path — changes LIVE enforcement code mid-session, and an edit to
# settings.json can plant *_BYPASS=1 in the env block and disarm every guard.
# Deny Write/Edit to those files unless the edit happens on a feature branch:
# the repo's documented development flow (branch → PR → review → merge). Direct
# edits on main/master, or outside any git repo (the deployed
# ~/.claude/settings.json), are the disarm shape and are denied.
#
# Residual (accepted): a feature-branch edit is still live immediately (same
# file). This check is a speed bump against casual self-disarm, not a sandbox —
# the gate fails open by design, so a determined actor is stopped by review and
# telemetry, not by this check. Every allowed guard edit emits an audit line.
# The bypass env is honored but deliberately NOT advertised in the deny message
# (same posture as the sysadmin/public-server guards).
_GUARD_INTEGRITY_BYPASS_ENV = "GUARD_INTEGRITY_BYPASS"
_SETTINGS_BASENAMES = frozenset({"settings.json", "settings.local.json"})


def _live_hooks_dir() -> Path | None:
    """Resolved deployed-hooks directory (~/.claude/hooks), or None.

    resolve() follows the deployment symlink into the repo, so a write addressed
    via either the deployed path or the repo working copy maps to the same
    protected directory.
    """
    try:
        live = Path.home() / ".claude" / "hooks"
        return live.resolve() if live.is_dir() else None
    except OSError:
        return None


def check_guard_integrity(file_path: str) -> None:
    """Deny Write/Edit to live enforcement files except on a feature branch."""
    if os.environ.get(_GUARD_INTEGRITY_BYPASS_ENV) == "1":
        return
    try:
        resolved = Path(file_path).resolve()
    except OSError:
        resolved = Path(file_path)
    live = _live_hooks_dir()
    in_live_hooks = live is not None and (resolved == live or live in resolved.parents)
    is_settings = resolved.name in _SETTINGS_BASENAMES and resolved.parent.name == ".claude"
    if not in_live_hooks and not is_settings:
        return
    if _is_worktree_on_feature_branch(str(resolved.parent)):
        # Audit line: every guard-file edit is visible in verbose mode/telemetry.
        print(
            f"[guard-integrity] AUDIT: feature-branch edit of enforcement file allowed: {file_path}",
            file=sys.stderr,
        )
        return
    target_kind = "live hook code" if in_live_hooks else "Claude settings"
    _block(
        f"[guard-integrity] BLOCKED: direct edit of {target_kind}: {file_path}\n"
        f"[guard-integrity] Deployed hooks and settings.json are live enforcement controls.\n"
        f"[guard-integrity] Edit them on a feature branch (git checkout -b) and land via a reviewed PR.",
        reason=(
            f"Editing {target_kind} ({file_path}) outside a feature branch is blocked — "
            f"deployed hooks and settings.json are live enforcement controls. "
            f"Create a feature branch (git checkout -b fix/<slug>) and land the change via a reviewed PR."
        ),
    )


_PUBLIC_SERVER_DENY_MSG = (
    "BLOCKED: this command would expose a dev server on a PUBLIC network interface.\n\n"
    "`python -m http.server` (and many dev servers) bind 0.0.0.0 — ALL interfaces — "
    "by default, publishing the served directory to the internet on a public host.\n\n"
    "For LOCAL preview, bind loopback explicitly:\n"
    "  python3 -m http.server 8080 --bind 127.0.0.1\n"
    "  php -S 127.0.0.1:8000\n"
    "  vite --host 127.0.0.1\n\n"
    "For PUBLIC hosting, do NOT expose a raw dev server. Put it behind a real web "
    "server / tunnel (nginx, Caddy, Cloudflare Tunnel) — see the public-web-deploy skill."
)
# LOW-1 (PR #719): the deny message deliberately does NOT advertise the bypass
# env var. Surfacing the disarm switch in user-facing block output hands a novice
# (or a coerced agent) the exact escape hatch on any false positive. The bypass
# remains FUNCTIONAL via PUBLIC_SERVER_GUARD_BYPASS=1 (checked in
# check_public_dev_server) for the rare intentional case — documented here in code
# only, not in the block reason.


# Commands that merely DISPLAY or SEARCH text — a server string in their args is
# data, not an executed invocation. Used to suppress false positives like
# `echo 'python3 -m http.server'` and `grep -r 'vite --host 0.0.0.0' .`.
_DISPLAY_CMD_RE = re.compile(
    r"^(?:#|:|echo\b|printf\b|grep\b|egrep\b|fgrep\b|rg\b|cat\b|less\b|more\b|head\b|tail\b|comm\b)"
)

# Shell separators that start a new command segment. Splitting on these lets us
# evaluate each segment independently: `echo foo && python3 -m http.server`
# still blocks the real invocation while `echo 'python3 -m http.server'` does not.
# Deliberately does NOT split on newline: heredoc bodies and quoted multiline
# args contain literal newlines that must stay attached to their leading command
# (e.g. `printf '%s\n' '...'`, `cat <<'EOF' ... EOF`) — splitting them produced
# false positives (codex-found). Chaining is still caught via ; && || | &.
_SEGMENT_SPLIT_RE = re.compile(r"(?:&&|\|\||[;|&])")

# Command-substitution bodies: $(...), `...`, and <(...) / >(...) process subs.
# A server launched inside a substitution is a real invocation even when the
# outer command is a display command (`echo $(python3 -m http.server)`), so the
# body is evaluated independently before display-command suppression. Single
# level (no recursive $( $( ) ) nesting) — an accepted regex-on-text residual.
_SUBSTITUTION_RE = re.compile(r"\$\((?P<dollar>[^()]*)\)|`(?P<back>[^`]*)`|[<>]\((?P<proc>[^()]*)\)")


def _single_quoted_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of LITERAL single-quoted regions in `text`.

    In POSIX shells single quotes are literal — `$(...)`/backticks inside them are
    NOT substitutions — so a substitution inside such a span is data, not an
    invocation (`echo '$(python3 -m …)'` must NOT block). Three subtleties this
    scanner honors so the suppression cannot be abused to hide a real server:
      * A `'` inside a DOUBLE-quoted region is an ordinary char, NOT a span opener
        (`echo "'$(…)'"` still executes the substitution → must block).
      * A backslash-escaped `\\'` outside quotes is a literal `'`, NOT a span
        opener (`echo \\'$(…)\\'` still executes → must block).
      * Inside a single-quoted span, backslash is NOT special (POSIX) — the span
        ends at the next raw `'`.
    """
    spans: list[tuple[int, int]] = []
    in_double = False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and not in_double:
            i += 2  # backslash escapes the next char outside double quotes
            continue
        if c == '"':
            in_double = not in_double
        elif c == "'" and not in_double:
            close = text.find("'", i + 1)
            if close == -1:
                break  # unterminated single quote — no literal span
            spans.append((i, close + 1))
            i = close + 1
            continue
        i += 1
    return spans


def _quoted_spans_all(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of BOTH single- and double-quoted regions.

    Used to suppress whole-line footgun matches that are merely DISPLAYED/searched
    data (`grep -R "curl … | sh" docs/`, codex round-8 FP). A real execution inside
    double quotes only happens via `$(...)`, which is recursed into separately
    (that recursion skips single-quoted spans but evaluates double-quoted ones), so
    excluding literal double-quoted text from the whole-line scan does not hide a
    real invocation. Honors backslash escapes outside quotes.
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            # Single quotes are literal: no escapes inside; span ends at next `'`.
            close = text.find("'", i + 1)
            if close == -1:
                break
            spans.append((i, close + 1))
            i = close + 1
            continue
        if c == '"':
            # Double quotes honor `\"` escapes inside the span (codex round-9 FP).
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            if j >= n:
                break  # unterminated double quote
            spans.append((i, j + 1))
            i = j + 1
            continue
        i += 1
    return spans


def _has_unquoted_shell_op(text: str) -> bool:
    """True if `text` contains a shell operator (| ; & && ||) OUTSIDE any quotes.

    Walks the string honoring single- AND double-quote spans and backslash escapes,
    so an operator inside a quoted argument (a `git commit -m "a | b"` message) is
    not counted. Used to tell a single real `git` command apart from a git chained
    to another command (`git commit -m wip && curl … | sh`).
    """
    i, n = 0, len(text)
    in_single = in_double = False
    while i < n:
        c = text[i]
        if in_single:
            if c == "'":
                in_single = False
        elif in_double:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_double = False
        else:
            if c == "\\":
                i += 2
                continue
            if c == "'":
                in_single = True
            elif c == '"':
                in_double = True
            elif c in "|;&":
                return True
        i += 1
    return False


# Shell launchers whose `-c <payload>` argument is the real command to evaluate.
_SHELL_LAUNCHERS = frozenset({"sh", "bash", "zsh", "dash", "ash", "ksh"})


def _shell_c_payload(seg: str) -> str:
    """Return the `-c <payload>` argument of a shell launcher segment, or "".

    Handles `-c payload`, combined short flags `-lc payload` (the `c` may be the
    last letter of a short-flag cluster), and `--command payload`. Quotes are
    removed by shlex so the payload is the inner command string.
    """
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()
    for j, t in enumerate(toks):
        is_c = t == "-c" or t == "--command" or (t.startswith("-") and not t.startswith("--") and t.endswith("c"))
        if is_c and j + 1 < len(toks):
            return toks[j + 1]
    return ""


def _block_public_server() -> None:
    """Emit the public-server deny decision and exit 0."""
    _block(
        f"[public-server-guard] {_PUBLIC_SERVER_DENY_MSG}",
        tool_name="Bash",
        reason=_PUBLIC_SERVER_DENY_MSG,
    )


def _scan_host_flags(seg: str, short_re: re.Pattern[str] | None = None) -> bool:
    """Return True if any host/bind flag in `seg` resolves to a public host.

    Always scans long flags (--bind/--host/--listen/--address). Additionally
    scans `short_re` (the specific short bind flag this server uses) when given.

    LAST flag wins (audit S3). Every one of these servers takes the final
    occurrence when a bind flag is repeated, so `--bind 127.0.0.1 --bind
    0.0.0.0` binds ALL interfaces. Scanning for any public match would be
    right there but wrong in reverse; short-circuiting on the first match was
    wrong in exactly the dangerous direction (that command was ALLOWED). Both
    flag families are collected and ordered by position so the decision
    reflects what the server will actually do.
    """
    matches = list(_HOST_FLAG_RE.finditer(seg))
    if short_re is not None:
        matches += list(short_re.finditer(seg))
    if not matches:
        return False
    last = max(matches, key=lambda m: m.start())
    return _host_is_public(last.group(1))


def _check_public_dev_server_segment(segment: str, _depth: int = 0) -> None:
    """Evaluate one shell command segment; _block on a public dev-server bind."""
    seg = segment.strip()
    if not seg:
        return
    if _depth > 4:  # death-loop guard for pathological nesting (fail open: stop)
        return

    # Multiline input (audit S3): a newline separates shell commands, but
    # `_SEGMENT_SPLIT_RE` deliberately does NOT split on it (heredoc/quoted-
    # multiline safety, #719). So the display-command suppression below saw a
    # leading `echo`/`cat`/`#` on line 1 and silently discarded every later
    # line — one newline disabled this entire guard (`echo hi\npython3 -m
    # http.server` was ALLOWED). Scan each NON-heredoc line independently.
    # This mirrors the identical fix already applied in
    # `_check_sysadmin_segment` for the codex round-9 bypass.
    if "\n" in seg:
        lines = [ln for ln in _non_heredoc_lines(seg) if ln.strip()]
        # Only recurse when the split actually produced something different.
        # A newline that lives entirely inside a quoted argument yields the
        # segment back unchanged, and recursing on it would never terminate.
        if lines != [seg]:
            for line in lines:
                _check_public_dev_server_segment(line, _depth + 1)
            return

    # MEDIUM-1: evaluate command-substitution bodies ($(...), `...`, <(...))
    # independently FIRST. A display command (echo/grep/…) suppresses its OWN
    # text, but a server launched inside a substitution is a real invocation
    # (`echo $(python3 -m http.server 8080)`) and must still be caught.
    sq_spans = _single_quoted_spans(seg)
    for sub in _SUBSTITUTION_RE.finditer(seg):
        # `$(...)` inside SINGLE quotes is literal data, not a real substitution
        # (`echo '$(python3 -m http.server)'`) — skip it to avoid a false positive.
        if any(start <= sub.start() < end for start, end in sq_spans):
            continue
        body = sub.group("dollar") or sub.group("back") or sub.group("proc") or ""
        if body.strip():
            for sub_seg in _SEGMENT_SPLIT_RE.split(body):
                _check_public_dev_server_segment(sub_seg, _depth + 1)

    cmd = _command_token(seg)

    # Shell launcher (`bash -c '<cmd>'`, `sh -lc '…'`): the real invocation is the
    # `-c` payload. Recurse into it (split into segments) so a server launched via
    # a shell wrapper is still caught. The payload was a quoted token, so shlex
    # tokenization reconstructs it; the launcher itself is then not a server.
    if cmd in _SHELL_LAUNCHERS:
        payload = _shell_c_payload(seg)
        if payload:
            for sub_seg in _SEGMENT_SPLIT_RE.split(payload):
                _check_public_dev_server_segment(sub_seg, _depth + 1)
        return

    # A pure display/search command quoting a server string is data, not an
    # invocation — suppress the outer text (substitutions were already handled).
    if _DISPLAY_CMD_RE.match(seg.lstrip("'\"")):
        return

    # Resolve `python -m <module>` once, anchored to the interpreter COMMAND token
    # (token-walk, not free text). None when the segment is not a real `python -m`
    # invocation (e.g. the literal string lives in a commit message / grep pattern
    # / `-c "..."` payload) — that is the HIGH-1 false-positive fix.
    py_module = _python_m_module(seg)

    # python http.server: block by default unless an explicit loopback --bind.
    # Only fires when the COMMAND is a python interpreter running `-m http.server`.
    if py_module in _PY_HTTP_SERVER_MODULES:
        # LAST `--bind` wins (audit S3): `--bind 127.0.0.1 --bind 0.0.0.0`
        # binds all interfaces, but a first-match `.search()` saw the loopback
        # and allowed it.
        found = list(_PY_BIND_RE.finditer(seg))
        m = found[-1] if found else None
        if m is None or _host_is_public(m.group(1)):
            _block_public_server()
        return  # explicit loopback bind → allow

    # php: two server forms only. `php -S <host>` (built-in server; block on a
    # non-loopback host) and `php artisan serve --host=…` (Laravel dev server).
    # A plain `php script.php --host …` CLI script is NOT a server — its --host is
    # the script's own arg, so host flags are scanned ONLY for `artisan serve`.
    if cmd == "php":
        m = _PHP_SERVER_RE.search(seg)
        if m and _host_is_public(m.group(1)):
            _block_public_server()
            return
        if _PHP_ARTISAN_SERVE_RE.search(seg) and _scan_host_flags(seg):
            _block_public_server()
        return

    # Resolve the effective server name. A python web server may be launched via
    # its own console script (`flask run`, `uvicorn`, `gunicorn`) OR as a module
    # (`python3 -m flask run`); the module form maps the interpreter token to the
    # module name so it is still anchored to a real invocation.
    server = cmd
    if py_module in _PY_WEB_SERVERS:
        server = py_module

    # Known servers anchored at the COMMAND token (or `-m <module>` for python web
    # servers): client-side JS/static dev servers, node task runners
    # (npm/pnpm/yarn/bun run), and python web servers (flask/uvicorn/gunicorn).
    # Block ONLY on an EXPLICIT public bind/host flag — bare `vite` / `npm run dev`
    # default to localhost → allow (no false positive).
    is_known_server = server in _JS_DEV_SERVERS or server in _NODE_RUNNERS or server in _PY_WEB_SERVERS
    if not is_known_server:
        return

    # #720: the `http-server` npm package binds 0.0.0.0 by DEFAULT (publishes the
    # served directory). Block-by-default — like python http.server — unless an
    # explicit loopback `-a 127.0.0.1|localhost|::1` is present. A non-loopback
    # `-a` is caught by the short-flag scan below; a bare `http-server` (no `-a`)
    # would otherwise slip through, so it must block here.
    if server == "http-server":
        # LAST `-a` wins (audit S3): `http-server -a 127.0.0.1 -a 0.0.0.0`
        # binds all interfaces, but a first-match `.search()` saw the loopback
        # and allowed it.
        found = list(_SERVER_SHORT_FLAGS["http-server"].finditer(seg))
        m = found[-1] if found else None
        if m is None or _host_is_public(m.group(1)):
            _block_public_server()
        return  # explicit loopback `-a` → allow

    # #720: value-less `--host` / `-H` on a JS dev server (`vite --host`,
    # `next dev --host`, `vite --host --strictPort`) means "all interfaces".
    # The value-bearing scan below requires a value token, so a bare flag would
    # slip through — detect it explicitly here. Only JS dev servers use this
    # all-interfaces shorthand (python web servers require a value).
    if server in _JS_DEV_SERVERS and _VALUELESS_HOST_FLAG_RE.search(seg):
        _block_public_server()
        return

    # Command token is a known server, so this server's specific short bind flag
    # (if any) is safe to scan — the collision cases (git -a, curl -H, ssh -b)
    # never reach this point, and another server's short flag is not honored
    # (e.g. ng has no host short flag, so `ng build -- -a foo` is not a bind).
    if _scan_host_flags(seg, _SERVER_SHORT_FLAGS.get(server)):
        _block_public_server()
        return

    # Residual (accepted): a node runner forwarding a SHORT host flag to an unknown
    # inner dev server (`npm run dev -- -H 0.0.0.0`). The inner server is unknown,
    # so the short letter (-H/-a/-b) is ambiguous — `-a src` is a non-host arg on a
    # build script. Scanning it generically over-blocks routine `npm run … -- -a`,
    # which would re-introduce the very false positives this PR removes. The LONG
    # form (`-- --host 0.0.0.0`, the documented case) IS caught above, as is the
    # direct server form (`next dev -H 0.0.0.0`). Left as a documented residual.


def check_public_dev_server(command: str) -> None:
    """Block raw dev servers bound to non-loopback interfaces.

    Block-by-default for `python -m http.server` / SimpleHTTPServer (which bind
    0.0.0.0 by default) unless an explicit loopback --bind is present. Also block
    any dev server given an explicit public --bind/--host/--listen/--address/-H/
    -b/-a, and `php -S` on a non-loopback host. Allow loopback binds, deployment
    tooling (nginx/caddy/etc.), display/search commands that merely quote a
    server string, and commands with no dev-server invocation.

    The command is split on shell separators and each segment is evaluated
    independently, so chained invocations are caught while quoted-string data is
    not. Detection is regex-on-text (a shared limit of every check in this gate).
    """
    if os.environ.get(_PUBLIC_SERVER_BYPASS_ENV) == "1":
        return

    if _oversized_for_segment_scan(command, "public-server-guard"):
        return

    for segment in _SEGMENT_SPLIT_RE.split(command):
        _check_public_dev_server_segment(segment)


# ═══════════════════════════════════════════════════════════════
# 7. SYSADMIN-SECURITY GUARD  (issue #720)
# ═══════════════════════════════════════════════════════════════
#
# Catch first-time-Linux-user footguns that leak secrets or open the host, and
# either BLOCK (clear footgun) with an EDUCATIONAL message that names the correct
# safe way, or WARN (context-dependent) without denying. Mirrors #719's machinery:
# regex-on-text, display-suppression (`echo`/`grep` of a footgun string is data),
# segment-split tokenizer, one bypass env var, fail-open / exit-0.
#
# Pipe-spanning shapes (curl|sh, reverse shells) are checked on the WHOLE line —
# `_SEGMENT_SPLIT_RE` splits on `|`, which would tear `curl … | sh` apart.
#
# Single shared bypass for the whole group (per the gate's per-check convention).
# Setting SYSADMIN_GUARD_BYPASS=1 in the environment skips this whole guard (see
# check_sysadmin_security). The escape hatch is intentionally NOT advertised in the
# user-facing deny message: a deny that is itself a FALSE POSITIVE would otherwise
# teach the operator to disable the guard on the next benign command. Mirrors the
# #719 LOW-1 fix for the public-dev-server guard. Documented here in code only.
_SYSADMIN_GUARD_BYPASS_ENV = "SYSADMIN_GUARD_BYPASS"

# --- remote-download piped into an executing sink (audit S5) -------------------
#
# The pipe-to-shell pattern below deny-lists shell names, so `curl http://x |
# python3` — and `| node`, `| perl`, `| ruby` — all passed. A deny-list of
# interpreters can never be complete; the safe set is the small one.
#
# So: any `curl`/`wget` piped into a command that is NOT a known-safe sink is
# treated as executing remote code. Safe sinks are read-only text/archive tools
# that do not execute their input.
_SAFE_PIPE_SINKS = frozenset(
    {
        # pagers / display
        "cat",
        "bat",
        "less",
        "more",
        "head",
        "tail",
        "nl",
        "tee",
        # text processing
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "ag",
        "sed",
        "awk",
        "cut",
        "tr",
        "sort",
        "uniq",
        "wc",
        "column",
        "fold",
        "rev",
        "strings",
        "diff",
        "comm",
        "join",
        "paste",
        "expand",
        "unexpand",
        "tac",
        # structured data
        "jq",
        "yq",
        "xmllint",
        "csvlook",
        "json_pp",
        # hashing / encoding — the "verify a checksum" flow the deny message teaches
        "sha256sum",
        "sha512sum",
        "sha1sum",
        "md5sum",
        "shasum",
        "cksum",
        "base64",
        "xxd",
        "od",
        "hexdump",
        # compression / archives (decompress to stdout or extract; do not exec)
        "gunzip",
        "zcat",
        "gzip",
        "bunzip2",
        "bzcat",
        "unzip",
        "xz",
        "unxz",
        "zstd",
        "tar",
        "cpio",
        "funzip",
        # misc non-executing sinks
        "file",
        "dd",
        "split",
        "pv",
        "sponge",
        "true",
        "cmp",
    }
)

# `curl`/`wget` followed by a pipe. The sink is resolved from the text after the
# pipe by the normal command-token walk, so wrappers (`sudo`, `env -i`, `xargs`)
# and path-qualified names (`/usr/bin/python3`) resolve correctly.
_REMOTE_FETCH_PIPE_RE = re.compile(r"\b(?:curl|wget)\b[^|;&\n]*\|")


def _remote_fetch_pipes_to_executor(line: str) -> bool:
    """True if a `curl`/`wget` on `line` pipes into a non-safe sink.

    Allow-list, not deny-list: an unrecognized sink is treated as executing.
    Only the FIRST stage after each fetch is checked — a safe sink's own output
    piped onward (`curl … | jq . | less`) is local data by then.
    """
    for m in _REMOTE_FETCH_PIPE_RE.finditer(line):
        rest = line[m.end() :]
        sink_text = _SEGMENT_SPLIT_RE.split(rest)[0]
        if not sink_text.strip():
            return True  # pipe into nothing parseable — fail safe
        sink = _command_token(sink_text)
        if sink and sink not in _SAFE_PIPE_SINKS:
            return True
    return False


# --- WHOLE-LINE BLOCK patterns (pipe-spanning / multi-segment shapes) ----------
# Each tuple: (compiled pattern, category, educational deny message naming the fix).
_SYSADMIN_WHOLELINE_BLOCK_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        # Remote-script-to-shell footguns, all forms:
        #   curl … | sh            pipe to shell (optional sudo/env wrappers)
        #   sh <(curl …)           process substitution (and `sh < <(curl …)`)
        #   source <(curl …)       source/`.` of a downloaded script
        #   sh -c "$(curl …)"      the Homebrew-installer shape (codex round-11)
        re.compile(
            r"(?:\b(?:curl|wget)\b[^|]*\|\s*(?:(?:/\S*/)?(?:sudo|env|command|exec|nohup|setsid|time|nice|stdbuf|ionice|doas|timeout)\s+(?:-\S+\s+|\w+=\S+\s+|\d\S*\s+|[a-z][\w.-]*\s+(?=-|\w|/))*)*(?:/\S*/)?(?:ba|z|d|a|k)?sh\b)"
            r"|(?:(?:sudo|env|command|exec)\s+)*(?:(?:/\S*/)?(?:ba|z|d|a|k)?sh\b|source\b|\.(?=\s))\s+(?:<\s*)?<\(\s*(?:curl|wget)\b"
            r"|(?:(?:/\S*/)?(?:ba|z|d|a|k)?sh\b[^|;&]*-c\b|\beval\b)[^|;&]*\$\(\s*(?:curl|wget)\b",
        ),
        "pipe-to-shell",
        "Piping a remote script straight to a shell runs unreviewed, possibly-MITM'd "
        "code as you. Download it, read it, verify a checksum, then run it:\n"
        "  curl -fsSLo install.sh https://… && less install.sh && bash install.sh",
    ),
    (
        # Reverse-shell one-liners: bash /dev/tcp, nc -e, socat EXEC, mkfifo backpipe.
        # The mkfifo backpipe is detected by co-occurrence of `mkfifo` + a shell +
        # `nc`/`ncat`/`netcat` on the line (both the `… | sh | nc …` and the
        # `sh </fifo | nc … >/fifo` one-pipe forms, codex round-19), since the named
        # FIFO is the shared signal — benign `mkfifo` use rarely pairs with nc+sh.
        re.compile(
            r"(?:>\s*&?\s*/dev/(?:tcp|udp)/)"
            r"|(?:\b(?:nc|ncat|netcat)\b[^|;&]*\s-e\b)"
            r"|(?:\bsocat\b[^|;&]*\bEXEC:)"
            r"|(?:\bmkfifo\b[\s\S]*\b(?:ba|z|d|a|k)?sh\b[\s\S]*\b(?:nc|ncat|netcat)\b)"
            r"|(?:\bmkfifo\b[\s\S]*\b(?:nc|ncat|netcat)\b[\s\S]*\b(?:ba|z|d|a|k)?sh\b)",
        ),
        "reverse-shell",
        "This is a reverse-shell shape — it hands a remote host a shell on this "
        "machine. Don't run remote shell one-liners on a server; use SSH or a "
        "bastion for legitimate remote access.",
    ),
]

# --- PER-SEGMENT BLOCK patterns ------------------------------------------------
# Sensitive chmod targets come in TWO tiers (codex round-13): the correct mode
# differs, so the loosening test differs.
#
# OWNER-ONLY tier — private keys, secrets, .env, .aws/credentials. Correct mode is
# owner-only (600/400/700); ANY group OR other access is a leak (SSH rejects a
# group-readable key, secrets must not be group-readable).
_SYSADMIN_OWNER_ONLY_TARGET_RE = re.compile(
    r"(?:\.ssh/id_[a-z0-9]+(?!\.pub)\b"  # private keys; exclude `.pub`. authorized_keys
    # is intentionally NOT here — it is public-key material and 0644 is a common valid
    # mode; SSH only rejects it when group/world-WRITABLE (codex round-16 FP).
    r"|(?<![\w/.])/etc/ssh/\S*key(?!\.pub)\b"  # private host keys (system path); exclude `.pub`
    r"|\.(?:pem|key|p12|pfx)(?!\.pub)\b"  # private material anywhere; exclude `*.key.pub`
    r"|(?:^|/|\s)\.env(?!\.(?:example|sample|template|dist)\b)\b"  # exclude safe templates
    r"|\.aws/credentials\b)",
)
# GROUP-OK tier — system auth files & docker socket whose correct mode IS group-
# readable (`/etc/shadow` → 640 root:shadow, `/etc/sudoers` → 440 root:root). Only
# WORLD access (other bit set) or world-writable is a footgun here. The system paths
# are root-anchored `(?<![\w/.])` so a fixture path like `./fixtures/etc/sudoers`
# does not match the live system file (codex round-19 FP).
_SYSADMIN_GROUP_OK_TARGET_RE = re.compile(
    r"(?<![\w/.])(?:/etc/(?:shadow|gshadow|sudoers)\b|/etc/sudoers\.d/"
    r"|/var/run/docker\.sock\b|/run/docker\.sock\b)",
)

# Loosen test for OWNER-ONLY targets: symbolic g/o/a grant, bare +r/+w, OR an octal
# with a non-zero GROUP or OTHER digit. (600/400/700 → no match → allowed.)
_SYSADMIN_CHMOD_LOOSEN_OWNER_RE = re.compile(
    r"(?:[ugoa]*[goa][ugoa]*[+=][rwxstugo]"  # g+r, o=r, go=rw, a+r
    r"|(?<![\w-])\+[rw]"  # bare +r/+w
    r"|(?<![\w-])[0-7]?[0-7][1-7][0-7]\b"  # non-zero GROUP digit (640, 660, 750)
    r"|(?<![\w-])[0-7]?[0-7][0-7][1-7]\b)"  # non-zero OTHER digit (604, 777)
)
# Loosen test for GROUP-OK targets: only WORLD access — symbolic `o+`/`o=`/`a+`,
# bare +r/+w, OR an octal with a non-zero OTHER (last) digit. (640/440 → allowed.)
_SYSADMIN_CHMOD_LOOSEN_WORLD_RE = re.compile(
    r"(?:[ugoa]*[oa][ugoa]*[+=][rwxstugo]"  # o+r, o=rw, a+r (world grant)
    r"|(?<![\w-])\+[rw]"  # bare +r/+w (applies to all incl. other)
    r"|(?<![\w-])[0-7]?[0-7][0-7][1-7]\b)"  # non-zero OTHER digit (646, 666, 777)
)
# A real `chmod` command verb (word-boundaried). Required to fire OUTSIDE quotes
# alongside the target+mode so the secret-chmod rule only triggers on an actual
# chmod invocation, not chmod TEXT inside a quoted argument of another command.
_CHMOD_VERB_RE = re.compile(r"\bchmod\b")

# redis is handled by a dedicated helper (_redis_is_unsafe) rather than a single
# regex: `--protected-mode no` is only a footgun WITHOUT a `--requirepass` and
# without a loopback bind (codex round-6 FP: a loopback + requirepass redis is safe).
# Each flag accepts both `--flag value` and `--flag=value` syntax (codex round-8).
# `::` matches the IPv6 wildcard but NOT loopback `::1` (codex round-18 FP): require
# the `::` to be followed by a non-hex-digit (end/space) so `::1` falls through to
# the loopback check.
# `redis-server` as an executed COMMAND token (command position), used with the
# quoted-span-excluding `_fires` so the redis text inside a quoted argument of an
# unrelated command is data, not a server (#724 FP) — yet a real invocation behind
# a launcher (`systemd-run redis-server …`, `sudo redis-server …`) is still caught
# (a pure `_command_token=="redis-server"` test would miss those launchers). Command
# position = start of segment OR right after a shell op / launcher boundary (space).
_REDIS_SERVER_CMD_RE = re.compile(r"(?:^|[\s;&|])(?:[^\s'\"]*/)?redis-server\b")
# Each flag tolerates an OPTIONAL quote on its VALUE (`--bind "0.0.0.0"`,
# `--protected-mode 'no'`): bash strips those quotes before redis sees argv, so a
# quoted value is a REAL footgun. The FLAG-position guard in `_redis_is_unsafe`
# (offset must be outside quoted spans) is what distinguishes this from a `--bind`
# keyword buried INSIDE a quoted value (`--logfile "--bind 0.0.0.0"` → flag start is
# inside the quote → ignored). `\s+` after the flag also matches across the opening
# quote position since the value may be `["']`-prefixed.
_REDIS_PUBLIC_BIND_RE = re.compile(
    r"--bind(?:\s+|=)['\"]?(?:0\.0\.0\.0\b|::(?![0-9a-fA-F])|\[::\]|\*|0(?=['\"]?(?:\s|$)))"
)
_REDIS_LOOPBACK_BIND_RE = re.compile(r"--bind(?:\s+|=)['\"]?(?:127\.|localhost|::1|\[::1\])")
_REDIS_PROTECTED_OFF_RE = re.compile(r"--protected-mode(?:\s+|=)['\"]?no\b")
_REDIS_REQUIREPASS_RE = re.compile(r"--requirepass(?:\s+|=)['\"]?\S")
_SYSADMIN_REDIS_MSG = (
    "Binding redis to 0.0.0.0 (or protected-mode off with no password) publishes "
    "your data unauthenticated — these get ransomware-scanned within minutes. Bind "
    "loopback and require a password:\n"
    "  redis-server --bind 127.0.0.1 --protected-mode yes --requirepass <pw>\n"
    "For remote access use an SSH tunnel, a private network/VPN, or redis TLS "
    "plus firewall rules — never a raw public bind."
)


def _redis_flag_fires(pat: re.Pattern[str], seg: str, quoted: list[tuple[int, int]]) -> bool:
    """True if `pat` matches `seg` with the FLAG KEYWORD starting OUTSIDE quotes.

    A match whose start offset is inside a quoted span means the flag keyword (e.g.
    `--bind`) is literal text inside another argument's quoted value
    (`--logfile "--bind 0.0.0.0"`) — not a real flag — so it is ignored. A real flag
    with a quoted VALUE (`--bind "0.0.0.0"`) has its keyword OUTSIDE quotes and fires.
    """
    return any(not any(start <= m.start() < end for start, end in quoted) for m in pat.finditer(seg))


def _redis_is_unsafe(seg: str) -> bool:
    """True if a `redis-server` segment exposes data unauthenticated.

    Unsafe when: bound to a public interface (any --bind 0.0.0.0/*/::), OR
    protected-mode is off AND there is no --requirepass AND it is not loopback-
    bound. A loopback bind with a password is safe (codex round-6 FP fix).

    Each flag is matched only when its KEYWORD sits OUTSIDE quotes (codex #724
    round-2/3): a quoted VALUE (`--bind "0.0.0.0"`) is a real footgun and fires,
    while a `--bind`/`--protected-mode` keyword buried inside another flag's quoted
    value (`--logfile "--bind 0.0.0.0"`) is data and is ignored.
    """
    quoted = _quoted_spans_all(seg)
    if _redis_flag_fires(_REDIS_PUBLIC_BIND_RE, seg, quoted):
        return True
    if _redis_flag_fires(_REDIS_PROTECTED_OFF_RE, seg, quoted):
        return not (
            _redis_flag_fires(_REDIS_REQUIREPASS_RE, seg, quoted)
            or _redis_flag_fires(_REDIS_LOOPBACK_BIND_RE, seg, quoted)
        )
    return False


_SYSADMIN_SEGMENT_BLOCK_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        # mongod with auth disabled.
        re.compile(r"\bmongod\b(?=[^|;&]*--noauth\b)"),
        "mongod-noauth",
        "`mongod --noauth` disables all authentication. Run with auth enabled and "
        "bind loopback:\n  mongod --bind_ip 127.0.0.1 --auth\n"
        "Create users with `db.createUser(...)` before exposing it anywhere.",
    ),
    (
        # mysqld / mariadbd / mysqld_safe with the grant-tables auth check bypassed.
        re.compile(r"\b(?:mysqld_safe|mysqld|mariadbd)\b(?=[^|;&]*--skip-grant-tables\b)"),
        "mysql-skip-grant",
        "`--skip-grant-tables` disables MySQL/MariaDB privilege checks — anyone who "
        "connects is root. Use it only offline for password recovery, never on a "
        "running/exposed server. Reset a password via `ALTER USER … IDENTIFIED BY` "
        "with normal auth instead.",
    ),
    (
        # docker/podman run with isolation removed.
        re.compile(
            r"\b(?:docker|podman)\b[^|;&]*\brun\b"
            r"(?=[^|;&]*(?:--privileged\b|--cap-add[= ]ALL\b|--security-opt[= ]\S*(?:seccomp|apparmor)=unconfined))",
        ),
        "container-privileged",
        "These flags remove container isolation — a compromise becomes host root. "
        "Grant only the one capability you need instead:\n"
        "  docker run --cap-add=NET_BIND_SERVICE …  (never --privileged)",
    ),
    (
        # docker/podman run mounting the docker socket or host root, via the
        # `-v/--volume host:container` form OR the `--mount type=bind,src=…` form.
        re.compile(
            r"\b(?:docker|podman)\b[^|;&]*\brun\b"
            r"(?=[^|;&]*(?:"
            r"(?:-v|--volume)(?:[= ]\s*|)(?:/var/run/docker\.sock|/run/docker\.sock|/):"  # -v host:ctr (incl. attached -v/:/…)
            r"|--mount\b[^|;&]*(?:src|source)=(?:/var/run/docker\.sock|/run/docker\.sock|/)(?:[,\s]|$)"  # --mount src=…
            r"))",
        ),
        "docker-sock-mount",
        "Mounting the docker socket (or host `/`) gives the container full root "
        "control of this host. Mount only the subpath you need, read-only:\n"
        "  docker run -v /srv/data:/data:ro …\n"
        "For Docker API access use a scoped proxy, not the raw socket.",
    ),
    (
        # iptables flush / default-ACCEPT (`-P` or `--policy`), or nft flush ruleset.
        re.compile(
            # `-F`/`--flush` blocks when it flushes everything or a built-in chain:
            # bare (`-F` then end/another flag like `-t nat` = whole-table flush) or
            # `-F INPUT|FORWARD|OUTPUT`. Flushing ONE custom chain (`-F DOCKER-USER`,
            # next token is a non-flag chain name) is a normal targeted op → allowed
            # (codex round-11 FP, round-20 `-t nat` bypass).
            r"\biptables\b[^|;&]*\s(?:-F|--flush)(?:\s+(?:INPUT|FORWARD|OUTPUT|PREROUTING|POSTROUTING)\b|\s*(?=[|;&]|$)|\s+-)"
            r"|\biptables\b[^|;&]*\s(?:-P|--policy)\s+(?:INPUT|FORWARD|OUTPUT)\s+ACCEPT\b"
            r"|\bnft\b[^|;&]*\bflush\s+ruleset\b",
        ),
        "firewall-flush",
        "Flushing rules / setting the default policy to ACCEPT removes all network "
        "filtering. Snapshot first, then change only the one rule you need:\n"
        "  iptables-save > rules.v4 ; iptables -A INPUT -p tcp --dport 443 -j ACCEPT\n"
        "  nft (nftables): nft list ruleset > rules.nft ; nft add rule inet filter input tcp dport 443 accept",
    ),
    (
        # ufw disable (allow intervening flags like `ufw --force disable`).
        re.compile(r"\bufw\b(?:\s+--?\S+)*\s+disable\b"),
        "ufw-disable",
        "`ufw disable` turns the whole host firewall off. Keep it on and open only "
        "the port you need:\n  sudo ufw allow 443/tcp",
    ),
    (
        # stop/disable/mask firewalld — both `systemctl stop firewalld` (action-first)
        # and the SysV `service firewalld stop` (unit-first) forms.
        re.compile(
            r"\bsystemctl\b[^|;&]*\b(?:stop|disable|mask)\b[^|;&]*\bfirewalld\b"
            r"|\bservice\b[^|;&]*\bfirewalld\b[^|;&]*\b(?:stop|disable)\b"
            r"|\bsystemctl\b[^|;&]*\bfirewalld\b[^|;&]*\b(?:stop|disable|mask)\b"
        ),
        "firewalld-stop",
        "Stopping/disabling firewalld removes host filtering. Keep it running and "
        "open the port instead:\n"
        "  firewall-cmd --add-port=443/tcp --permanent && firewall-cmd --reload",
    ),
    (
        # backdoor uid-0 account, or password removal.
        re.compile(
            r"\buseradd\b[^|;&]*-o\b[^|;&]*-u\s*0\b|\buseradd\b[^|;&]*-u\s*0\b[^|;&]*-o\b"
            r"|\busermod\b[^|;&]*-u\s*0\b"
            r"|\bpasswd\b\s+-d\b|\busermod\b[^|;&]*-p\s*(?:''|\"\")",
        ),
        "backdoor-account",
        "Creating a second UID-0 account or removing a password is a backdoor. Use "
        "named accounts with sudo, and lock an account with `passwd -l <user>` "
        "rather than blanking its password.",
    ),
]

# Recursive chown/chmod targeting bare `/` — extends (does not duplicate) the
# existing bare `chmod -R 777` rule by catching `chown -R user /`. Anchored so
# `chown -R me:me ./build` and `chmod -R 755 /srv/app` do NOT match.
_SYSADMIN_RECURSIVE_ROOT_RE = re.compile(
    r"\b(?:chown|chmod)\b[^|;&]*\s(?:-[a-zA-Z]*R[a-zA-Z]*|--recursive)\b[^|;&]*?\s/(?=\s|$)"
)
_SYSADMIN_RECURSIVE_ROOT_MSG = (
    "Recursive ownership/permission changes on `/` break the OS and are near-"
    "unrecoverable. Target the exact path you mean (never `/`):\n"
    "  chown -R user:user /srv/app\n"
    "  chmod -R 755 /srv/app"
)

# A bare path TOKEN that names a secret file (.env, id_rsa, *.pem, *.key, …).
# Applied to individual shlex tokens (not free text) so a secret name inside a
# `-m "…"` commit message is data, never matched (codex finding). Safe template
# and public-material suffixes are excluded: `.env.example` / `.sample` /
# `.template` (the recommended safe file) and `*.pub` (public keys).
#
# Accepted residual (codex round-3, NOT fixed by design): a wildcard stage such as
# `git add -A` / `git add .` / `git commit -a` does NOT name the secret file on the
# command line, so regex-on-text cannot see it. Detecting that would require running
# `git` (subprocess) on every commit — outside this gate's regex-only/perf model and
# outside the stated BLOCK scope ("git commit that stages a NAMED secret"). The
# Write/Edit-side sensitive-file guard already blocks CREATING such files.
# Matches literal secret path tokens AND ordinary git glob pathspecs that stage
# secrets (`*.env`, `.env.*`, `config/.env.*`, `*.pem`, `id_rsa*` — codex round-22).
# A trailing `*`/`.*` glob or a leading `*` is permitted. Template suffixes
# (.example/.sample/.template/.dist) are still exempt.
_SYSADMIN_GIT_SECRET_TOKEN_RE = re.compile(
    r"(?:^|/)\*?"  # optional path prefix and a leading glob (`*.env`)
    r"(?!.*\.(?:example|sample|template|dist)$)"  # exempt ANY *.example/.sample/.template/.dist
    r"(?:"
    r"\.env(?:\.[\w.*]+)?"  # .env, .env.local, .env.*, .env.production.local
    r"|id_rsa\*?|id_ed25519\*?|id_ecdsa\*?|id_dsa\*?"
    r"|[^/\s]*\.(?:pem|key|p12|pfx)"  # *.pem, server.key, *.key
    r"|credentials\.json"
    r")\*?$",  # optional trailing glob (`*.env.*` etc.)
)
# git options whose VALUE is the next token and is NOT a path (so a secret name in
# a commit message, author, or template value is data, not a staged secret).
_GIT_VALUE_OPTS = frozenset(
    {"-m", "--message", "-F", "--file", "--author", "-c", "-C", "--reuse-message", "--template", "-t"}
)


def _git_stages_secret(seg: str) -> bool:
    """True if a `git add`/`git commit` segment stages a secret file as a PATH arg.

    Token-walks the segment so a secret filename inside a `-m "…"` message (or any
    option value) is treated as data, not a staged path. Returns False for non-git
    or non-add/commit segments.
    """
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()
    # Skip leading wrapper/env-assignment tokens (`sudo git add …`, codex round-14)
    # WITHOUT re-joining (which would lose quoting and mis-tokenize a `-m "…"`
    # message). Consume `FOO=bar`, `sudo`/`env`/… and their option flags + values.
    w = 0
    while w < len(toks):
        base = toks[w].rsplit("/", 1)[-1]
        if _ENV_ASSIGN_RE.match(toks[w]):
            w += 1
        elif base in {"sudo", "env", "command", "exec", "nice", "nohup", "setsid", "doas", "time", "timeout", "stdbuf"}:
            w += 1
            # Skip wrapper option flags AND value-taking ones (`sudo -u deploy`,
            # `nice -n 5`) so the inner `git` is still found (codex round-15).
            while w < len(toks) and toks[w].startswith("-"):
                takes_value = (
                    toks[w] in {"-u", "--user", "-g", "--group", "-n", "--adjustment", "-C", "--chdir"}
                    and "=" not in toks[w]
                )
                w += 2 if takes_value else 1
        else:
            break
    toks = toks[w:]
    if len(toks) < 2 or toks[0].rsplit("/", 1)[-1] != "git":
        return False
    # Skip global git options before the subcommand (`git -C /tmp add …`,
    # `git -c k=v commit …`). `-C`/`-c` take a value token (codex round-6 bypass).
    i = 1
    while i < len(toks) and toks[i].startswith("-"):
        if toks[i] in {"-C", "-c"}:
            i += 2
        else:
            i += 1
    if i >= len(toks) or toks[i] not in {"add", "commit"}:
        return False
    subcmd = toks[i]
    i += 1
    # `git add --dry-run`/`-n` stages nothing (codex round-12 FP). For `add`, a
    # dry-run flag anywhere means no secret is actually staged.
    if subcmd == "add" and ("--dry-run" in toks or "-n" in toks):
        return False
    while i < len(toks):
        t = toks[i]
        if t in _GIT_VALUE_OPTS:
            i += 2  # skip the option AND its value token (message/author/etc.)
            continue
        if t.startswith("-"):
            # `-m"msg"` / `--message=msg` glued forms carry their value inline → data.
            i += 1
            continue
        if _SYSADMIN_GIT_SECRET_TOKEN_RE.search(t):
            return True
        i += 1
    return False


_SYSADMIN_GIT_SECRET_MSG = (
    "Committing a secret to git usually becomes permanent (history + every remote "
    "and clone). Don't stage it:\n"
    "  git restore --staged <path>     # unstage it now\n"
    "  git rm --cached <path>          # if already tracked\n"
    "Add the path to `.gitignore`, commit only a redacted `.env.example`, and "
    "rotate anything already exposed."
)

# NOPASSWD:ALL written into a sudoers file. Checked on the WHOLE line and NOT
# display-suppressed: here `echo`/`printf`/`tee` is the WRITE vector (the string is
# redirected/piped INTO /etc/sudoers), so it is action, not mere display. Requires
# both the literal `NOPASSWD:ALL` and a sudoers target on the line.
_SYSADMIN_NOPASSWD_SUDOERS_RE = re.compile(
    r"NOPASSWD\s*:\s*ALL\b.*?(?:/etc/sudoers|sudoers\.d)|(?:/etc/sudoers|sudoers\.d)\S*.*?\bNOPASSWD\s*:\s*ALL\b",
    re.DOTALL,
)
# A WRITE vector into a SUDOERS file specifically: redirect to sudoers, `tee`/`dd`
# whose target is a sudoers file, in-place `sed` on sudoers, or `visudo`. Required
# alongside the NOPASSWD:ALL match so read-only audits do NOT block — including
# `grep NOPASSWD:ALL /etc/sudoers.d | tee findings.txt` (tee targets a benign file,
# not sudoers; codex round-2 finding).
# A real sudoers path target (the canonical files / drop-in dir), used to confirm
# a write VECTOR actually targets sudoers — not just any token containing the word
# (`tee /tmp/sudoers-findings.txt` is a benign audit dump, codex round-4 finding).
# A real sudoers path. The `/etc/sudoers` form must NOT be preceded by another path
# char (so `/tmp/etc/sudoers.d/test` — a benign temp file — does not match the
# canonical system path, codex round-5 finding).
# Only the ABSOLUTE system path counts — a bare relative `sudoers.d/me` in a repo or
# fixtures dir is NOT the live system file (codex round-23 FP).
_SUDOERS_PATH = r"(?<![\w/])/etc/sudoers(?:\.d/\S*)?\b"
_SYSADMIN_SUDOERS_WRITE_RE = re.compile(
    rf">>?\s*(?:{_SUDOERS_PATH})"  # redirect into a sudoers path
    rf"|\b(?:tee|dd|install)\b[^|;&]*(?:{_SUDOERS_PATH})"  # tee/dd/install writing a sudoers path
    rf"|\bsed\b[^|;&]*-i[^|;&]*(?:{_SUDOERS_PATH})"  # in-place sed on sudoers
    r"|\bvisudo\b(?![^|;&]*(?:--check\b|-[a-z]*c[a-z]*\b))",  # visudo edits; `-c`/`-cf`/`--check` is read-only
)
_SYSADMIN_NOPASSWD_MSG = (
    "`NOPASSWD:ALL` is silent passwordless root for that user. If you truly need "
    "non-interactive sudo, scope it to one command via `visudo`:\n"
    "  user ALL=(root) NOPASSWD:/usr/bin/systemctl restart app"
)

_SYSADMIN_CHMOD_SECRET_MSG = (
    "Loosening permissions on a key, secret, or auth file leaks it: world-readable "
    "password hashes enable offline cracking, and SSH refuses group/world-readable "
    "keys. Keep least privilege:\n"
    "  chmod 600 ~/.ssh/id_ed25519   (700 on ~/.ssh)\n"
    "  /etc/shadow → 640 root:shadow ; /etc/sudoers → 440 root:root (edit via visudo)"
)

# --- WARN-only patterns (advise, do NOT deny) ----------------------------------
# Each tuple: (compiled pattern, advice message). Context-dependent footguns with
# common legitimate uses — too noisy to block, so teach without obstructing.
_SYSADMIN_WARN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\blisten_addresses\s*=\s*['\"]?\*|--bind-address\s*=\s*0\.0\.0\.0"
            r"|\bnetwork\.host\s*=\s*0\.0\.0\.0|\bmongod\b[^|;&]*(?:--bind_ip_all|--bind_ip\s+0\.0\.0\.0)",
        ),
        "A database listening on 0.0.0.0/all interfaces is reachable from every "
        "network. Prefer 127.0.0.1 or a private IP, require real accounts + TLS, "
        "and restrict with firewall rules.",
    ),
    (
        re.compile(r"\bPermitRootLogin\s+yes\b|\bPasswordAuthentication\s+yes\b|\bPubkeyAuthentication\s+no\b"),
        "Root login / password auth are the first brute-force targets. Prefer a "
        "named sudo user with PermitRootLogin no, PasswordAuthentication no, and "
        "key-only auth.",
    ),
    (
        re.compile(r"\bStrictHostKeyChecking[= ]no\b|\bUserKnownHostsFile[= ]/dev/null\b"),
        "Disabling host-key checks removes server-identity verification (MITM risk). "
        "Enroll the key once: `ssh-keyscan host >> ~/.ssh/known_hosts`, then connect "
        "normally.",
    ),
    (
        # `-p<pw>` is only flagged for DB clients where `-p` means password (mysql,
        # mariadb, redis-cli, mongosh) — NOT for `ssh -p2222` / `tar -pxf` where `-p`
        # is a port/preserve flag (codex round-20 warn-noise). Plus explicit
        # `--password=`, a `user:pass@` creds URL, and inline secret env exports.
        re.compile(
            r"\b(?:mysql|mariadb|redis-cli|mongosh)\b[^|;&]*(?<![\w-])-p\S"
            r"|--password[= ]\S"
            r"|://\w+:[^@\s/]+@"
            r"|\bexport\s+\w*(?:TOKEN|SECRET|PASSWORD|API_KEY)\w*="
            r"|(?:-e\s+)\w*(?:SECRET|TOKEN|PASSWORD)\w*="
        ),
        "Secrets on the command line or in env exports leak to shell history and "
        "`ps`. Use a prompt, a 0600 config file (~/.my.cnf, ~/.pgpass), or a secret "
        "store.",
    ),
    (
        re.compile(r"\b(?:usermod|gpasswd)\b[^|;&]*(?:-aG\s+docker\b|-a\s+docker\b)"),
        "The `docker` group is root-equivalent on the host. Add a user only if they "
        "should have root-equivalent control; otherwise use rootless Docker or "
        "scoped sudo.",
    ),
    (
        re.compile(
            r"\bsysctl\b[^|;&]*(?:kernel\.randomize_va_space\s*=\s*0|kernel\.kptr_restrict\s*=\s*0|fs\.protected_(?:hardlinks|symlinks)\s*=\s*0)"
        ),
        "These sysctls turn off kernel hardening (ASLR, kptr restriction, symlink "
        "protection). Change them only for a short, documented diagnostic window and "
        "restore immediately.",
    ),
    (
        re.compile(r"\bsshpass\s+-p\S"),
        "`sshpass -p <pw>` leaks the password to history and `ps`. Use key auth, or "
        "at minimum `sshpass -f <file>` / the SSHPASS env var.",
    ),
    (
        re.compile(
            r"\bsetenforce\s+0\b|\baa-disable\b|\b(?:systemctl|service)\b[^|;&]*\b(?:stop|disable|mask)\b[^|;&]*\bapparmor\b|\bapparmor_parser\s+-R\b|SELINUX\s*=\s*disabled"
        ),
        "Disabling SELinux/AppArmor removes a system-wide containment layer. Put the "
        "one offending profile into permissive/complain mode instead "
        "(`semanage`/`audit2allow`, or `aa-complain /etc/apparmor.d/<profile>`).",
    ),
]


_HEREDOC_START_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")


def _strip_unquoted_comment(line: str) -> str:
    """Drop a POSIX shell comment (`# …` to end of line) that starts OUTSIDE quotes.

    A `#` begins a comment only at WORD START — preceded by start-of-line or an
    unquoted blank/operator (`;`, `&`, `|`, `(`). So `curl http://x#frag` (mid-word)
    and a `#` inside quotes (`echo "a#b"`) are NOT comments and are preserved.
    Footgun text living in a comment is shell-ignored DATA, so scanning it produced
    false positives (`true # ufw disable`, codex #724 round-1). Mirrors heredoc-body
    stripping. Quote tracking matches `_quoted_spans_all` (backslash escapes honored
    outside quotes; single quotes literal; double quotes honor `\\"`).
    """
    i, n = 0, len(line)
    prev_is_word_boundary = True  # start-of-line counts as a boundary
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
            prev_is_word_boundary = False
            continue
        if c == "'":
            close = line.find("'", i + 1)
            if close == -1:
                return line  # unterminated quote — do not strip (treat as-is)
            i = close + 1
            prev_is_word_boundary = False
            continue
        if c == '"':
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
            if j >= n:
                return line  # unterminated quote
            i = j + 1
            prev_is_word_boundary = False
            continue
        if c == "#" and prev_is_word_boundary:
            return line[:i].rstrip()
        # Comment-start boundary is whitespace / `;` / `&` / `|` only. `(` is
        # deliberately EXCLUDED: in bash with extglob, `@(#…)` / `?(#…)` is real
        # pattern syntax, not a comment, so treating `#` after `(` as a comment
        # would truncate a live command before a `| sh` (codex #724 round-2 bypass).
        prev_is_word_boundary = c in " \t;&|"
        i += 1
    return line


def _unquoted_line_split(text: str) -> list[str]:
    """Split `text` on newlines that are NOT inside a quoted string.

    A newline inside a quoted argument is DATA, not a command separator
    (`printf '%s\\n' 'python3 -m http.server'` is one command). Splitting on it
    naively manufactures a fake second command out of the quoted tail — a false
    positive. Only an unquoted newline actually starts a new command.
    """
    lines: list[str] = []
    buf: list[str] = []
    in_single = in_double = False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and not in_single and i + 1 < n:
            buf.append(c)
            buf.append(text[i + 1])  # escaped char is literal, never a delimiter
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "\n" and not in_single and not in_double:
            lines.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    lines.append("".join(buf))
    return lines


def _non_heredoc_lines(text: str) -> list[str]:
    """Split `text` into command lines, dropping heredoc BODY lines.

    A heredoc body (`cmd <<EOF\\n…\\nEOF`) is literal data passed to the command's
    stdin, not a sequence of commands, so its lines must not be scanned as footguns.
    The line that OPENS the heredoc is kept (it is a real command); body lines up to
    and including the terminator are skipped.

    Lines are split quote-aware (`_unquoted_line_split`) so a newline inside a
    quoted argument does not manufacture a fake command line.
    """
    out: list[str] = []
    pending_terms: list[str] = []
    for line in _unquoted_line_split(text):
        if pending_terms:
            if line.strip() == pending_terms[-1]:
                pending_terms.pop()  # heredoc terminator — body ends here
            continue  # inside a heredoc body — skip
        out.append(line)
        for m in _HEREDOC_START_RE.finditer(line):
            pending_terms.append(m.group(1))
    return out


def _warn(message: str) -> None:
    """Emit an educational advisory to stderr WITHOUT denying (fail-open).

    Symmetric to `_block` but prints no JSON permissionDecision and does not
    exit — the tool proceeds. Visible in Ctrl+O verbose mode. Used for
    context-dependent footguns that are too noisy to block outright.
    """
    print(f"[sysadmin-guard] ADVISORY: {message}", file=sys.stderr)


def _block_sysadmin(category: str, message: str) -> None:
    """Emit the sysadmin-guard deny decision and exit 0.

    The deny text deliberately does NOT mention SYSADMIN_GUARD_BYPASS (the env var
    is still honored in check_sysadmin_security). Advertising the bypass in a
    message that could be a false positive trains the operator to disable the
    guard — the exact anti-pattern the #719 LOW-1 fix removed for the dev-server
    guard. The message names the correct SAFE alternative instead.
    """
    _block(
        f"[sysadmin-guard] BLOCKED ({category}): {message}",
        tool_name="Bash",
        reason=message,
    )


def _check_sysadmin_segment(segment: str) -> None:
    """Evaluate one shell segment for per-segment sysadmin footguns."""
    seg = segment.strip()
    if not seg:
        return

    # Multiline input: a newline separates shell commands, but `_SEGMENT_SPLIT_RE`
    # deliberately does NOT split on it (heredoc/quoted-multiline safety, #719). So a
    # display command on line 1 would otherwise suppress a real footgun on line 2
    # (`echo "x"\nufw disable`, codex round-9 bypass). Scan each NON-heredoc line
    # independently. Heredoc bodies (`cmd <<EOF … EOF`) are skipped so their text is
    # not misread as commands. Only recurse when there is a real extra command line.
    if "\n" in seg:
        lines = [ln for ln in _non_heredoc_lines(seg) if ln.strip()]
        # `_non_heredoc_lines` is quote-aware, so a newline inside a quoted
        # argument leaves the segment intact — recursing on that identical
        # segment would never terminate (this function has no depth guard).
        if lines != [seg]:
            for line in lines:
                _check_sysadmin_segment(line)
            return

    # Drop a trailing unquoted shell comment: `true # ufw disable` ignores the
    # footgun text, so scanning it produced a false positive (codex #724 round-1).
    seg = _strip_unquoted_comment(seg)
    if not seg.strip():
        return

    # A pure display/search command quoting a footgun string is data, not an
    # invocation (`echo 'ufw disable'`, `grep -r 'curl x | sh' .`) → suppress.
    if _DISPLAY_CMD_RE.match(seg.lstrip("'\"")):
        return

    # `git` segments: git cannot EXECUTE iptables/curl|sh/chmod/etc. — a footgun
    # string in a `git commit -m "…"` message or any git argument is documentation,
    # not an invocation (codex round-7 FPs). The ONLY git footgun is staging a
    # secret file, handled by the token-walking _git_stages_secret below. So for a
    # git command, check ONLY that and skip every generic footgun/warn pattern.
    if _command_token(seg) == "git":
        if _git_stages_secret(seg):
            _block_sysadmin("commit-secret", _SYSADMIN_GIT_SECRET_MSG)
        return

    # Quoted-span exclusion: a footgun matched ENTIRELY inside a quoted argument is
    # data, not an invocation (`sed -n '/ufw disable/p' README.md`, `awk '/curl|sh/'`,
    # codex round-17 FP). A real command never has its verb inside quotes.
    quoted = _quoted_spans_all(seg)

    def _fires(pat: re.Pattern[str]) -> bool:
        for m in pat.finditer(seg):
            if not any(start <= m.start() < end for start, end in quoted):
                return True
        return False

    # redis exposed unauthenticated (dedicated helper — see _redis_is_unsafe).
    # `redis-server` must be the EXECUTED command, not free text in a quoted arg of
    # an unrelated command (`gh pr edit --body "redis-server --bind 0.0.0.0 is bad"`,
    # a recursed `python3 -c "print('redis-server …')"` payload) — that was the #724
    # free-text FP. Two complementary anchors:
    #   * `_fires(_REDIS_SERVER_CMD_RE)` — command-position match OUTSIDE quotes; also
    #     catches a launcher form (`systemd-run redis-server …`, `sudo redis-server`).
    #   * `_command_token(seg) == "redis-server"` — covers a quoted EXEC NAME
    #     (`"redis-server" --bind …`, which bash still runs as redis-server; codex
    #     #724 round-2 bypass). `_command_token` of `gh …`/`python3 -c …` is the
    #     outer command, so this adds no FP.
    # `_redis_is_unsafe` does its own quoted-span handling: a `--bind`/`--protected-
    # mode` keyword buried in another flag's quoted value (`--logfile "--bind
    # 0.0.0.0"`) is ignored (round-2 FP), while a real flag with a quoted VALUE
    # (`--bind "0.0.0.0"`) still fires (round-3 footgun).
    if (_fires(_REDIS_SERVER_CMD_RE) or _command_token(seg) == "redis-server") and _redis_is_unsafe(seg):
        _block_sysadmin("redis-no-auth", _SYSADMIN_REDIS_MSG)

    for pattern, category, message in _SYSADMIN_SEGMENT_BLOCK_PATTERNS:
        if _fires(pattern):
            _block_sysadmin(category, message)

    # Recursive chown/chmod on bare `/`.
    if _fires(_SYSADMIN_RECURSIVE_ROOT_RE):
        _block_sysadmin("recursive-root", _SYSADMIN_RECURSIVE_ROOT_MSG)

    # git add/commit staging a secret file (token-walked: a secret name inside a
    # `-m "…"` message or other option value is data, not a staged path).
    if _git_stages_secret(seg):
        _block_sysadmin("commit-secret", _SYSADMIN_GIT_SECRET_MSG)

    # chmod loosening permissions on a key/secret/auth file. Two tiers (round-13):
    #   owner-only targets (keys/secrets/.env) → block ANY group/other access;
    #   group-ok targets (/etc/shadow=640, /etc/sudoers=440, docker.sock) → block
    #   only WORLD access. So `chmod 644 app.py`, `chmod 600 ~/.ssh/id_rsa`,
    #   `chmod 640 /etc/shadow`, and `chmod 440 /etc/sudoers` are all allowed, while
    #   `chmod 640 ~/.ssh/id_rsa` and `chmod o+r /etc/shadow` block.
    # Every part of the rule must fire OUTSIDE quotes via `_fires` (the chmod verb,
    # the secret-file target, AND the loosening mode). Otherwise the whole pattern
    # free-text-matched inside a quoted argument of an unrelated command
    # (`gh pr create --body "do not chmod 777 ~/.ssh/id_rsa"`, a `python3 -c
    # "print('chmod 644 id_rsa.pem')"` payload) and blocked (#724 free-text FP).
    # `_fires` also keeps real invocations — `chmod 644 server.key`,
    # `sudo chmod o+r /etc/shadow`, `find . -exec chmod 777 id_rsa {} +` — because
    # their verb/target/mode sit outside any quoted span.
    if _fires(_CHMOD_VERB_RE) and (
        (_fires(_SYSADMIN_OWNER_ONLY_TARGET_RE) and _fires(_SYSADMIN_CHMOD_LOOSEN_OWNER_RE))
        or (_fires(_SYSADMIN_GROUP_OK_TARGET_RE) and _fires(_SYSADMIN_CHMOD_LOOSEN_WORLD_RE))
    ):
        _block_sysadmin("secret-chmod", _SYSADMIN_CHMOD_SECRET_MSG)

    # WARN-only patterns: advise, do not deny.
    for pattern, advice in _SYSADMIN_WARN_PATTERNS:
        if _fires(pattern):
            _warn(advice)


def check_sysadmin_security(command: str) -> None:
    """Block sysadmin footguns with educational fixes; warn on context-dependent ones.

    Two layers:
      * Whole-line BLOCK patterns for pipe-spanning shapes (curl|sh, reverse
        shells) that `_SEGMENT_SPLIT_RE` would otherwise tear apart.
      * Per-segment BLOCK/WARN patterns evaluated after segment-splitting and
        display-command suppression (so `echo 'ufw disable'` is data, not action).

    Every BLOCK message names the correct safe alternative. WARN messages advise
    via stderr without denying. One shared bypass: SYSADMIN_GUARD_BYPASS=1.
    Fail-open / exit-0 contract preserved (raised inside the gate's try/finally).
    """
    if os.environ.get(_SYSADMIN_GUARD_BYPASS_ENV) == "1":
        return

    # For the whole-line scans, drop heredoc BODY lines: their text is literal stdin
    # data, not commands (`bash -lc "cat <<EOF … curl|sh … EOF"`, codex round-13 FP).
    # Per-segment scanning does its own heredoc stripping; this covers the recursed
    # `-c` payload path where the heredoc reaches the whole-line patterns. Also drop
    # trailing unquoted shell comments per line so a commented footgun does not fire
    # the whole-line pipe-to-shell / reverse-shell patterns (`true # curl … | sh`,
    # codex #724 round-1 FP).
    _scan_src_lines = _non_heredoc_lines(command) if "\n" in command else [command]
    scan_line = "\n".join(_strip_unquoted_comment(ln) for ln in _scan_src_lines)

    # A single `git …` command cannot EXECUTE a pipe-to-shell, reverse shell, or
    # sudoers write — a footgun string in its commit message/args is documentation
    # (codex round-7 FPs). It is "pure git" when the first token is `git` and every
    # shell operator (`| ; & && ||`) on the line sits INSIDE a quoted span (e.g. a
    # `-m "…|…"` message), so the line is one real command. A git chained to a real
    # footgun has an UNQUOTED operator → not pure → the footgun segment is scanned.
    # Multiline (`\n` = a command separator) is never "pure git": a later line may be
    # a real footgun (`git status\ntee /etc/sudoers.d/x <<EOF…NOPASSWD:ALL…EOF`, codex
    # round-20). Only a single-line git command with no unquoted `| ; &` is pure git.
    line_is_pure_git = _command_token(command) == "git" and "\n" not in command and not _has_unquoted_shell_op(command)

    # NOPASSWD:ALL → sudoers: checked unconditionally (NOT display-suppressed)
    # because echo/printf/tee + redirect IS the write vector into the privileged
    # file. The string is action here, not display.
    # Scan the FULL command (incl. heredoc bodies): a heredoc piped to `tee
    # /etc/sudoers.d/…` IS the write payload (`tee /etc/sudoers.d/dev <<EOF …
    # NOPASSWD:ALL … EOF`, codex round-14) — the body is action here, not data.
    if (
        not line_is_pure_git
        and _SYSADMIN_NOPASSWD_SUDOERS_RE.search(command)
        and _SYSADMIN_SUDOERS_WRITE_RE.search(command)
    ):
        _block_sysadmin("nopasswd-all", _SYSADMIN_NOPASSWD_MSG)

    # Whole-line shapes first (pipe-spanning). A leading display command suppresses
    # the OUTER text (`echo 'curl x | sh'` is data), but a substitution body is a
    # real invocation (`echo $(curl x | sh)`) and is evaluated independently — same
    # treatment the public-server guard gives `$(...)` (codex bypass finding).
    sq_spans = _single_quoted_spans(command)
    for sub in _SUBSTITUTION_RE.finditer(command):
        if any(start <= sub.start() < end for start, end in sq_spans):
            continue  # `$(...)` inside single quotes is literal data
        body = sub.group("dollar") or sub.group("back") or sub.group("proc") or ""
        if body.strip():
            check_sysadmin_security(body)

    # Shell launcher (`bash -c '<payload>'`, `sh -lc '…'`) OR `su -c '<payload>'`:
    # the real command is the `-c` payload — recurse into it so a footgun wrapped in
    # a `-c` is still caught (`bash -lc 'curl … | sh'` round-5; `su -c 'ufw disable'`
    # round-18). Evaluated on the UN-split command: the payload's own `|`/`;` live
    # inside the quoted token, so segment-splitting first would tear it apart.
    if _command_token(command) in _SHELL_LAUNCHERS or _command_token(command) == "su":
        payload = _shell_c_payload(command)
        if payload.strip() and payload.strip() != command.strip():
            check_sysadmin_security(payload)

    # Whole-line pipe-spanning patterns. A match that lies ENTIRELY inside a single-
    # quoted span is literal data (`echo 'curl x | sh'`) and is suppressed; a match
    # outside quotes is a real invocation (`cat <(curl …) | sh`, codex round-4
    # finding) and blocks. Quote-span exclusion is more precise than a leading-
    # display-command heuristic, which a reader-then-pipe shape (`cat <(…) | sh`)
    # would have bypassed.
    if not line_is_pure_git:
        # Exclude matches inside ANY quoted span (single OR double): displayed/
        # searched footgun text is data (`grep -R "curl … | sh" docs/`, codex
        # round-8 FP). A real execution inside double quotes is a `$(...)`, already
        # recursed above. Scan ALL matches so a quoted decoy does not mask a later
        # real match (`echo 'curl x | sh' && curl … | sh`, round-5).
        quoted = _quoted_spans_all(scan_line)
        for pattern, category, message in _SYSADMIN_WHOLELINE_BLOCK_PATTERNS:
            for m in pattern.finditer(scan_line):
                if not any(start <= m.start() < end for start, end in quoted):
                    _block_sysadmin(category, message)

        # Allow-listed sinks (audit S5): the pattern above deny-lists shell
        # names, so `curl … | python3` (and node/perl/ruby) executed remote
        # code and passed. Checked per line, and only outside quoted spans so
        # displayed footgun text stays data.
        # Blank quoted spans over the WHOLE scan text before splitting into
        # lines: a quoted region can span newlines (a heredoc body inside a
        # `-c` payload), and recomputing spans per line would read its second
        # line as unquoted code (round-13 FP).
        blanked = "".join(" " if any(s <= i < e for s, e in quoted) else c for i, c in enumerate(scan_line))
        for raw_line in blanked.split("\n"):
            if not raw_line.strip() or _DISPLAY_CMD_RE.match(raw_line.strip().lstrip("'\"")):
                continue
            if _remote_fetch_pipes_to_executor(raw_line):
                _block_sysadmin(
                    "pipe-to-shell",
                    "Piping a remote download into an interpreter runs unreviewed, "
                    "possibly-MITM'd code as you. Download it, read it, verify a checksum, "
                    "then run it:\n"
                    "  curl -fsSLo install.sh https://… && less install.sh && bash install.sh",
                )

    if _oversized_for_segment_scan(command, "sysadmin-guard"):
        return

    for segment in _SEGMENT_SPLIT_RE.split(command):
        _check_sysadmin_segment(segment)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    global _CURRENT_EVENT, _CURRENT_COMMAND
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    _CURRENT_EVENT = event

    # Field name compatibility: try new names first, fall back to old
    tool = event.get("tool_name") or event.get("tool", "")
    tool_input = event.get("tool_input", event.get("input", {}))

    if tool == "Bash":
        command = tool_input.get("command", "")
        _CURRENT_COMMAND = command
        if not command:
            return
        check_gitignore_bypass(command)
        check_git_submission(command)
        check_dangerous_command(command)
        check_public_dev_server(command)
        check_sysadmin_security(command)
        check_sensitive_bash(command)

    elif tool == "Write":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", "")
        check_creation_gate(file_path, cwd=cwd)
        check_guard_integrity(file_path)
        check_sensitive_file(file_path)

    elif tool == "Edit":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_guard_integrity(file_path)
        check_sensitive_file(file_path)

    elif tool == "Read":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_sensitive_file(file_path, deny=False)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        # Fail OPEN — a crashed hook must never block tools.
        print(f"[unified-gate] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
