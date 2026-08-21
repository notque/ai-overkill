#!/usr/bin/env python3
"""
RED tests for the (not-yet-written) Stop-event drift guard.

Spec: adr/stop-event-drift-guards.md
Pattern: mirrors hooks/tests/test_security_review_hook.py (the established Stop-hook
test harness) — importlib-load the module under test, drive mod.main() in-process
with patched stdin/diff/check seams, assert on (exit_code, stdout, stderr).

These tests are written BEFORE hooks/stop-drift-guard.py exists (TDD RED phase).
They MUST fail at import/collection time with FileNotFoundError because the hook
file is absent — a clean "missing implementation" RED, not a syntax/assertion
slip. Once the GREEN implementation lands, the module import resolves and the
behavioral assertions take over.

Behaviors under test (ADR acceptance criteria 1-7):
  1. Relevance gate: only run a check when the diff touches that component class.
  2. Run ONLY the relevant existing check:
       - hooks/**                         -> smoke-test-hooks.py --ci
       - component add/remove OR a
         count-claim doc touched          -> validate-doc-counts.py --json
       - skills/** or agents/** frontmatter -> check-routing-drift.py
  3. Surface output ONLY on REAL drift; a clean session (checks pass) stays SILENT.
  4. Dedup via hook_utils.DiffDedup (module-level _STATE_DIR / _STATE_FILE).
  5. Fail-open on ANY internal error -> exit 0, never crash the session.
  6. Never blocks (advisory): drift surfaces via async_rewake (exit 2 + rewakeSummary),
     never a permissionDecision:deny.
  7. Honor VEXJOY_DRIFT_GUARD_DISABLE=1.

Run with: python3 -m pytest hooks/tests/test_stop_drift_guard.py -v

Expected module-level contract the GREEN implementation must expose (the seams
these tests patch):
  - read_stdin(timeout=...)            (imported from stdin_timeout; patched)
  - _working_tree_diff(cwd) -> str     (thin wrapper over hook_utils.working_tree_diff)
  - _run_check(name, cwd) -> dict      (runs ONE check script; returns a structured
                                        result {"drift": bool, "detail": str, "fix": str}
                                        or {"drift": False} / None on failure — patched)
  - _STATE_DIR, _STATE_FILE            (Path constants for DiffDedup; patched in dedup tests)
  - main()                             (stdin -> dispatch on hook_event_name == "Stop")
"""

import importlib.util
import io
import json
import os
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test.
#
# RED: hooks/stop-drift-guard.py does not exist yet. spec_from_file_location +
# exec_module raises FileNotFoundError here, so the whole module fails to collect
# and every test in it errors for the right reason: the implementation is missing.
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "stop-drift-guard.py"

spec = importlib.util.spec_from_file_location("stop_drift_guard", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stop_event(cwd: str | None = "/repo", stop_hook_active: bool = False) -> str:
    event = {"hook_event_name": "Stop", "stop_hook_active": stop_hook_active}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _diff_for(path: str, *, added: str = "x = 1", new_file: bool = False) -> str:
    """Build a unified diff that ADDS a line under `path`.

    `path` drives the relevance gate (the +++ b/<path> line). `new_file` emits a
    `new file mode` header so component-add detection has something to key on.
    """
    header = f"diff --git a/{path} b/{path}\n"
    if new_file:
        header += "new file mode 100644\nindex 0000000..1234567\n--- /dev/null\n"
    else:
        header += "index 1111111..2222222 100644\n--- a/" + path + "\n"
    return header + f"+++ b/{path}\n" + "@@ -0,0 +1,1 @@\n" + f"+{added}\n"


def _deletion_diff_for(path: str) -> str:
    """Whole-file deletion diff for `path` (drives component-remove detection)."""
    return (
        f"diff --git a/{path} b/{path}\n"
        "deleted file mode 100644\n"
        "index de98044..0000000\n"
        f"--- a/{path}\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-gone = True\n"
    )


# Structured check results the seam (_run_check) is expected to return.
def _drift(detail: str = "drift detected", fix: str = "run the fix") -> dict:
    return {"drift": True, "detail": detail, "fix": fix}


def _clean() -> dict:
    return {"drift": False}


def _clean_env(extra: dict | None = None) -> dict:
    base = {k: v for k, v in os.environ.items() if k != "VEXJOY_DRIFT_GUARD_DISABLE"}
    if extra:
        base.update(extra)
    return base


def _run(stdin_payload: str, *, env: dict | None = None, diff=None, check_results=None, toolkit_repo: bool = True):
    """Invoke mod.main() in-process.

    Returns (exit_code, stdout_str, stderr_str).

    diff:          if not None, patches _working_tree_diff to return it.
    check_results: if not None, patches _run_check. May be:
                     - a dict mapping check-name -> result dict (per-check control), or
                     - a single result dict applied to whatever check is invoked, or
                     - a list capturing call order (see _CheckSpy below).
    toolkit_repo:  patches _is_toolkit_repo to this value (default True) so the
                   toolkit-repo identity gate lets the event through. Set False to
                   exercise the non-toolkit no-op path.
    """
    out, err = io.StringIO(), io.StringIO()
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, _clean_env(env), clear=True))
        stack.enter_context(patch.object(mod, "read_stdin", return_value=stdin_payload))
        stack.enter_context(patch.object(mod, "_is_toolkit_repo", return_value=toolkit_repo))
        stack.enter_context(redirect_stdout(out))
        stack.enter_context(redirect_stderr(err))
        if diff is not None:
            stack.enter_context(patch.object(mod, "_working_tree_diff", return_value=diff))
        if check_results is not None:
            if isinstance(check_results, dict) and not _looks_like_result(check_results):
                # name -> result mapping
                def fake(name, cwd, _map=check_results):
                    return _map.get(name, _clean())

                stack.enter_context(patch.object(mod, "_run_check", side_effect=fake))
            elif callable(check_results):
                stack.enter_context(patch.object(mod, "_run_check", side_effect=check_results))
            else:
                stack.enter_context(patch.object(mod, "_run_check", return_value=check_results))
        code = 0
        try:
            mod.main()
        except SystemExit as e:
            code = int(e.code) if e.code is not None else 0
    return code, out.getvalue(), err.getvalue()


def _looks_like_result(d: dict) -> bool:
    """Distinguish a single result dict from a name->result mapping."""
    return "drift" in d


class _CheckSpy:
    """Records which checks _run_check was asked to run (relevance-gate assertions)."""

    def __init__(self, results: dict | None = None):
        self.calls: list[str] = []
        self.results = results or {}

    def __call__(self, name, cwd):
        self.calls.append(name)
        return self.results.get(name, _clean())


def _rewake_summary(stdout_str: str) -> str | None:
    for line in stdout_str.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "rewakeSummary" in data:
            return data["rewakeSummary"]
    return None


def _is_deny(stdout_str: str) -> bool:
    for line in stdout_str.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
            return True
    return False


# Canonical check names the hook is expected to use as _run_check(name, cwd) keys.
SMOKE = "smoke-test-hooks"
DOC_COUNTS = "validate-doc-counts"
ROUTING = "check-routing-drift"


# ---------------------------------------------------------------------------
# 1 + 2. Relevance gate: which check runs for which changed path class
# ---------------------------------------------------------------------------


class TestRelevanceGate:
    def test_hooks_change_runs_only_smoke_test(self):
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            _run(_stop_event(), diff=_diff_for("hooks/foo.py"))
        assert SMOKE in spy.calls
        assert ROUTING not in spy.calls

    def test_skills_frontmatter_change_runs_routing_check(self):
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            _run(_stop_event(), diff=_diff_for("skills/foo/SKILL.md", added="name: foo"))
        assert ROUTING in spy.calls
        assert SMOKE not in spy.calls

    def test_agents_frontmatter_change_runs_routing_check(self):
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            _run(_stop_event(), diff=_diff_for("agents/bar.md", added="description: x"))
        assert ROUTING in spy.calls
        # Relevance gate is exclusive: an agents-only modification (no add/remove,
        # no count-claim) must NOT drag in the other checks.
        assert SMOKE not in spy.calls
        assert DOC_COUNTS not in spy.calls

    def test_new_hook_file_runs_doc_counts(self):
        """Adding a component file (new hook) flips the count claims -> doc-counts."""
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            _run(_stop_event(), diff=_diff_for("hooks/new_hook.py", new_file=True))
        assert DOC_COUNTS in spy.calls
        # A new hook file is under hooks/, so smoke-test is also legitimately
        # relevant — but routing (skills/agents frontmatter) must NOT run.
        assert ROUTING not in spy.calls

    def test_removed_component_runs_doc_counts(self):
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            _run(_stop_event(), diff=_deletion_diff_for("scripts/old.py"))
        assert DOC_COUNTS in spy.calls
        # A scripts/ removal touches neither the hooks/ smoke surface nor
        # skills/agents frontmatter — those checks must NOT run.
        assert SMOKE not in spy.calls
        assert ROUTING not in spy.calls

    def test_count_claim_doc_touched_runs_doc_counts(self):
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            _run(_stop_event(), diff=_diff_for("README.md", added="The toolkit ships 80 hooks."))
        assert DOC_COUNTS in spy.calls
        # A count-claim doc touch is doc-counts ONLY — no component file changed,
        # so neither smoke-test nor routing should run.
        assert SMOKE not in spy.calls
        assert ROUTING not in spy.calls

    def test_unrelated_change_runs_no_checks(self):
        """A diff touching none of the component classes runs nothing and stays silent."""
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            code, out, _ = _run(_stop_event(), diff=_diff_for("notes/scratch.txt"))
        assert spy.calls == []
        assert code == 0
        assert _rewake_summary(out) is None

    def test_empty_diff_runs_no_checks_and_is_silent(self):
        spy = _CheckSpy()
        with patch.object(mod, "_run_check", side_effect=spy):
            code, out, _ = _run(_stop_event(), diff="")
        assert spy.calls == []
        assert code == 0
        assert _rewake_summary(out) is None


# ---------------------------------------------------------------------------
# 3. Surface output ONLY on REAL drift — clean session stays silent
# ---------------------------------------------------------------------------


class TestSurfaceOnlyOnRealDrift:
    def test_clean_check_stays_silent(self):
        """Relevant files changed, but the check reports NO drift -> exit 0, silent."""
        code, out, err = _run(
            _stop_event(),
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: _clean()},
        )
        assert code == 0
        assert _rewake_summary(out) is None

    def test_real_drift_triggers_rewake(self):
        code, out, err = _run(
            _stop_event(),
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: _drift("hook crashed", "python3 scripts/smoke-test-hooks.py --ci")},
        )
        assert code == 2
        assert _rewake_summary(out) is not None

    def test_rewake_message_names_drift_and_fix_command(self):
        code, out, err = _run(
            _stop_event(),
            diff=_diff_for("README.md", added="80 hooks"),
            check_results={DOC_COUNTS: _drift("README.md count claim stale", "validate-doc-counts.py --json")},
        )
        assert code == 2
        assert "README.md count claim stale" in err
        assert "validate-doc-counts.py --json" in err

    def test_changed_files_alone_do_not_trigger(self):
        """ADR criterion 3: drift surfaces because a check REPORTS drift, not merely
        because files changed. All relevant checks clean -> silent even with edits."""
        code, out, _ = _run(
            _stop_event(),
            diff=_diff_for("skills/x/SKILL.md", added="name: x"),
            check_results={ROUTING: _clean()},
        )
        assert code == 0
        assert _rewake_summary(out) is None

    def test_one_drift_among_several_checks_surfaces(self):
        """A diff that triggers two checks where exactly one reports drift -> rewake,
        and the surfaced message reflects the drifting check only."""
        # New hook file under hooks/ triggers BOTH smoke-test and doc-counts.
        diff = _diff_for("hooks/new_hook.py", new_file=True)
        results = {SMOKE: _clean(), DOC_COUNTS: _drift("80 vs 79 hooks", "fix the count")}
        code, out, err = _run(_stop_event(), diff=diff, check_results=results)
        assert code == 2
        assert "80 vs 79 hooks" in err


# ---------------------------------------------------------------------------
# 6. Advisory only — never a blocking permissionDecision
# ---------------------------------------------------------------------------


class TestAdvisoryNeverBlocks:
    def test_drift_emits_rewake_not_deny(self):
        code, out, _ = _run(
            _stop_event(),
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: _drift()},
        )
        assert not _is_deny(out)
        # async_rewake contract: exit 2 + a rewakeSummary line, context on stderr.
        assert code == 2
        assert _rewake_summary(out) is not None

    def test_stop_hook_active_skips(self):
        """asyncRewake recursion guard: an in-flight rewake must not re-fire."""
        code, out, _ = _run(
            _stop_event(stop_hook_active=True),
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: _drift()},
        )
        assert code == 0
        assert _rewake_summary(out) is None


# ---------------------------------------------------------------------------
# 4. Dedup via DiffDedup (module-level _STATE_DIR / _STATE_FILE)
# ---------------------------------------------------------------------------


class TestDedup:
    def test_identical_diff_short_circuits(self, tmp_path):
        state_file = tmp_path / "last-diff-hash.json"
        diff = _diff_for("hooks/foo.py")
        results = {SMOKE: _drift()}
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            code1, out1, _ = _run(_stop_event(), diff=diff, check_results=results)
            assert code1 == 2
            assert state_file.exists()
            code2, out2, _ = _run(_stop_event(), diff=diff, check_results=results)
            assert code2 == 0
            assert _rewake_summary(out2) is None

    def test_changed_diff_re_triggers(self, tmp_path):
        state_file = tmp_path / "last-diff-hash.json"
        results = {SMOKE: _drift()}
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            code1, _, _ = _run(_stop_event(), diff=_diff_for("hooks/a.py"), check_results=results)
            code2, out2, _ = _run(_stop_event(), diff=_diff_for("hooks/b.py"), check_results=results)
            assert code1 == 2
            assert code2 == 2
            assert _rewake_summary(out2) is not None


# ---------------------------------------------------------------------------
# 7. Disable switch
# ---------------------------------------------------------------------------


class TestDisableSwitch:
    def test_disable_env_suppresses_everything(self):
        """VEXJOY_DRIFT_GUARD_DISABLE=1 wins even over a drift-reporting check."""
        spy = _CheckSpy(results={SMOKE: _drift()})
        with patch.object(mod, "_run_check", side_effect=spy):
            code, out, _ = _run(
                _stop_event(),
                env={"VEXJOY_DRIFT_GUARD_DISABLE": "1"},
                diff=_diff_for("hooks/foo.py"),
            )
        assert code == 0
        assert _rewake_summary(out) is None
        # Disabled -> short-circuits before running any check.
        assert spy.calls == []

    def test_disable_value_zero_does_not_disable(self):
        code, out, _ = _run(
            _stop_event(),
            env={"VEXJOY_DRIFT_GUARD_DISABLE": "0"},
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: _drift()},
        )
        assert code == 2
        assert _rewake_summary(out) is not None


# ---------------------------------------------------------------------------
# 5. Fail-open on any error / malformed input / unrelated events
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_malformed_stdin_exits_0(self):
        code, out, _ = _run("not valid json {{{")
        assert code == 0
        assert _rewake_summary(out) is None

    def test_empty_stdin_exits_0(self):
        code, out, _ = _run("")
        assert code == 0

    def test_non_dict_json_exits_0(self):
        code, out, _ = _run("[1, 2, 3]")
        assert code == 0

    def test_non_stop_event_exits_0_silently(self):
        code, out, _ = _run(json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write"}))
        assert code == 0
        assert _rewake_summary(out) is None

    def test_check_raising_fails_open(self):
        """If a check seam raises, the hook swallows it and exits 0 (never crash)."""

        def boom(name, cwd):
            raise RuntimeError("scanner exploded")

        code, out, _ = _run(_stop_event(), diff=_diff_for("hooks/foo.py"), check_results=boom)
        assert code == 0
        assert _rewake_summary(out) is None

    def test_diff_helper_raising_fails_open(self):
        with patch.object(mod, "_working_tree_diff", side_effect=OSError("git gone")):
            code, out, _ = _run(_stop_event())
        assert code == 0
        assert _rewake_summary(out) is None

    def test_check_returns_none_treated_as_no_drift(self):
        """A check that returns None (couldn't run) fails open: no drift surfaced."""
        code, out, _ = _run(
            _stop_event(),
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: None},
        )
        assert code == 0
        assert _rewake_summary(out) is None

    def test_doc_count_check_uses_trusted_script_with_target_root_data(self, tmp_path):
        trusted = tmp_path / "trusted"
        target = tmp_path / "target"
        trusted_scripts = trusted / "scripts"
        target_scripts = target / "scripts"
        trusted_scripts.mkdir(parents=True)
        target_scripts.mkdir(parents=True)
        sentinel = tmp_path / "malicious-stop-ran"
        for name in ("smoke-test-hooks.py", "validate-doc-counts.py", "check-routing-drift.py"):
            (target_scripts / name).write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('owned')\n",
                encoding="utf-8",
            )
        argv_record = tmp_path / "trusted-doc-count-argv.json"
        (trusted_scripts / "validate-doc-counts.py").write_text(
            "import json, sys\n"
            "from pathlib import Path\n"
            f"Path({str(argv_record)!r}).write_text(json.dumps(sys.argv[1:]))\n"
            "print(json.dumps({'drifts': [{'source': 'README.md', 'line': 1, "
            "'claim': '1 hook', 'actual': 2}]}))\n",
            encoding="utf-8",
        )

        with patch.object(mod, "_TRUSTED_ROOT", trusted, create=True):
            result = mod._run_check(DOC_COUNTS, str(target))

        assert result is not None and result["drift"] is True
        assert not sentinel.exists()
        argv = json.loads(argv_record.read_text(encoding="utf-8"))
        assert argv == ["--json", "--repo-root", str(target)]

    def test_smoke_check_uses_trusted_validator_for_untrusted_target(self, tmp_path):
        trusted = tmp_path / "trusted"
        target = tmp_path / "target"
        (trusted / "scripts").mkdir(parents=True)
        (target / "scripts").mkdir(parents=True)
        sentinel = tmp_path / "malicious-smoke-ran"
        (target / "scripts" / "smoke-test-hooks.py").write_text(
            f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('owned')\n",
            encoding="utf-8",
        )
        argv_record = tmp_path / "trusted-smoke-argv.json"
        (trusted / "scripts" / "smoke-test-hooks.py").write_text(
            "import json, sys\n"
            "from pathlib import Path\n"
            f"Path({str(argv_record)!r}).write_text(json.dumps(sys.argv[1:]))\n"
            "print('trusted smoke drift')\nraise SystemExit(1)\n",
            encoding="utf-8",
        )

        with patch.object(mod, "_TRUSTED_ROOT", trusted, create=True):
            result = mod._run_check(SMOKE, str(target))

        assert result is not None and result["drift"] is True
        assert not sentinel.exists()
        argv = json.loads(argv_record.read_text(encoding="utf-8"))
        assert argv == [
            "--ci",
            "--repo-root",
            str(target),
            "--hooks-dir",
            str(trusted / "hooks"),
        ]

    def test_smoke_reports_missing_target_settings_without_executing_target(self, tmp_path):
        result = mod._run_check(SMOKE, str(tmp_path))
        assert result is not None and result["drift"] is True
        assert "No registered hooks found" in result["detail"]


# ---------------------------------------------------------------------------
# Fix (3): the has_reviewable_content gate is honored.
#
# A relevant diff (added content in a component class) must PASS the gate so the
# relevant check runs. A diff with no reviewable content must SHORT-CIRCUIT the
# hook before any check is invoked. The hook exposes `_has_reviewable_content`
# (its own gate over hook_utils.has_reviewable_content); these tests pin both
# directions of that gate.
# ---------------------------------------------------------------------------


class TestReviewableContentGate:
    def test_relevant_diff_passes_reviewable_gate_and_runs_check(self):
        """A real diff with reviewable content clears the gate and reaches a check."""
        spy = _CheckSpy()
        seen = []
        real_gate = mod._has_reviewable_content

        def spy_gate(diff):
            result = real_gate(diff)
            seen.append(result)
            return result

        with (
            patch.object(mod, "_has_reviewable_content", side_effect=spy_gate),
            patch.object(mod, "_run_check", side_effect=spy),
        ):
            _run(_stop_event(), diff=_diff_for("hooks/foo.py"))
        # Gate was consulted and returned True; a check ran behind it.
        assert seen == [True]
        assert spy.calls != []

    def test_no_reviewable_content_short_circuits_before_any_check(self):
        """When the gate reports nothing reviewable, no check is ever invoked."""
        spy = _CheckSpy(results={SMOKE: _drift()})
        with (
            patch.object(mod, "_has_reviewable_content", return_value=False),
            patch.object(mod, "_run_check", side_effect=spy),
        ):
            code, out, _ = _run(_stop_event(), diff=_diff_for("hooks/foo.py"))
        assert spy.calls == []
        assert code == 0
        assert _rewake_summary(out) is None


# ---------------------------------------------------------------------------
# Toolkit-repo identity gate: the hook runs ONLY when the session cwd IS the
# toolkit repo (cwd/pyproject.toml declares [project] name == "vexjoy-agent").
# In any other repo it silently no-ops. Clone-portable intrinsic marker.
# ---------------------------------------------------------------------------


def _write_pyproject(dir_path: Path, name: str = "vexjoy-agent") -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n', encoding="utf-8")
    return dir_path


class TestIsToolkitRepo:
    def test_true_when_pyproject_names_vexjoy_agent(self, tmp_path):
        repo = _write_pyproject(tmp_path / "repo")
        assert mod._is_toolkit_repo(str(repo)) is True

    def test_false_when_pyproject_absent(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert mod._is_toolkit_repo(str(empty)) is False

    def test_false_when_pyproject_names_other_project(self, tmp_path):
        repo = _write_pyproject(tmp_path / "other", name="some-other-service")
        assert mod._is_toolkit_repo(str(repo)) is False

    def test_false_when_cwd_is_none(self):
        assert mod._is_toolkit_repo(None) is False

    def test_false_when_cwd_is_empty_string(self):
        assert mod._is_toolkit_repo("") is False

    def test_fail_open_on_unreadable_pyproject(self, tmp_path):
        """A pyproject.toml that can't be read -> False (fail-open, no-op)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        # pyproject.toml is a directory, so read_text raises OSError.
        (repo / "pyproject.toml").mkdir()
        assert mod._is_toolkit_repo(str(repo)) is False


class TestToolkitRepoGate:
    def test_non_toolkit_repo_no_ops_even_with_reviewable_drift(self):
        """Regression for the false positive in unrelated repos (e.g. Hermez):
        a reviewable diff in a NON-toolkit cwd exits 0 and never rewakes."""
        spy = _CheckSpy(results={SMOKE: _drift()})
        with patch.object(mod, "_run_check", side_effect=spy):
            code, out, _ = _run(
                _stop_event(),
                diff=_diff_for("hooks/foo.py"),
                toolkit_repo=False,
            )
        assert code == 0
        assert _rewake_summary(out) is None
        # Gated before any check ran.
        assert spy.calls == []

    def test_toolkit_repo_with_real_drift_still_rewakes(self):
        """In a toolkit cwd, real drift preserves the existing rewake behavior."""
        code, out, err = _run(
            _stop_event(),
            diff=_diff_for("hooks/foo.py"),
            check_results={SMOKE: _drift("hook crashed", "python3 scripts/smoke-test-hooks.py --ci")},
            toolkit_repo=True,
        )
        assert code == 2
        assert _rewake_summary(out) is not None

    def test_gate_consulted_with_real_pyproject_end_to_end(self, tmp_path):
        """Unpatched _is_toolkit_repo: a tmp toolkit repo (real pyproject) with
        drift rewakes; the same diff in a non-toolkit tmp dir stays silent."""
        toolkit = _write_pyproject(tmp_path / "toolkit")
        non_toolkit = tmp_path / "plain"
        non_toolkit.mkdir()
        results = {SMOKE: _drift()}

        def fake(name, cwd, _map=results):
            return _map.get(name, _clean())

        def drive(cwd: str) -> tuple[int, str]:
            out = io.StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ, _clean_env(None), clear=True))
                stack.enter_context(patch.object(mod, "read_stdin", return_value=_stop_event(cwd=cwd)))
                stack.enter_context(patch.object(mod, "_working_tree_diff", return_value=_diff_for("hooks/foo.py")))
                stack.enter_context(patch.object(mod, "_run_check", side_effect=fake))
                stack.enter_context(redirect_stdout(out))
                stack.enter_context(redirect_stderr(io.StringIO()))
                code = 0
                try:
                    mod.main()
                except SystemExit as e:
                    code = int(e.code) if e.code is not None else 0
            return code, out.getvalue()

        code_t, out_t = drive(str(toolkit))
        assert code_t == 2
        assert _rewake_summary(out_t) is not None

        code_n, out_n = drive(str(non_toolkit))
        assert code_n == 0
        assert _rewake_summary(out_n) is None
