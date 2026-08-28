#!/usr/bin/env python3
"""Tests for scoping the instruction skip rate to the population that carried
the directive.

M04/M05/M06 measure whether a directive reached the dispatch prompt, but only
scripts/build-dispatch.py injects those directives, and only into /do-routed
prompts. Reviewer fan-out and nested subagent dispatches legitimately carry
none, so a skip rate computed over every Agent dispatch measures the wrong
population. Each observation now records whether the dispatch carried the
`[do-route]` marker, and the report scores only the expected population.

Covers:
- has_do_route_marker: True for a line-start marker, False otherwise.
- The hook records directive_expected True for a /do-routed prompt, False for a
  plain one.
- Skip rate excludes not-expected and unknown rows and states its denominator.
- CONVERT TO GATE is computed only over the expected population.
- The v8 -> v9 migration runs twice without error and leaves history unknown.
- The hook exits 0 on empty and malformed stdin.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_instruction_population.py -v
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "hooks" / "lib"
SCRIPTS_LIB_DIR = REPO_ROOT / "scripts" / "lib"
HOOK_PATH = REPO_ROOT / "hooks" / "instruction-compliance.py"
CLI_PATH = REPO_ROOT / "scripts" / "learning-db.py"

for _path in (LIB_DIR, SCRIPTS_LIB_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import learning_db_v2 as ldb
from route_types import has_do_route_marker

_spec = importlib.util.spec_from_file_location("instruction_compliance", HOOK_PATH)
assert _spec is not None and _spec.loader is not None
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

DO_ROUTE_PROMPT = (
    "[do-route] agent=hook-development-engineer skill=pr-workflow complexity=medium\n\n"
    "Consult the Reference Loading Table before starting work.\n"
    "Deliver the finished product. Ship the complete thing.\n"
    "Write dense. High fidelity, minimum words.\n"
)
PLAIN_PROMPT = (
    "Consult the Reference Loading Table before starting work.\n"
    "Deliver the finished product. Ship the complete thing.\n"
    "Write dense. High fidelity, minimum words.\n"
)


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    yield tmp_path
    monkeypatch.setattr(ldb, "_initialized", False, raising=False)


def _rows() -> list[dict]:
    with ldb.get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM instruction_compliance")]


def _run_hook(prompt: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    event = json.dumps(
        {
            "session_id": "pop-session",
            "tool_name": "Agent",
            "tool_input": {"prompt": prompt},
            "tool_response": {"output": "done"},
        }
    )
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_path)}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=event,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _run_skip_rate(tmp_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_path), "PYTHONPATH": str(LIB_DIR)}
    return subprocess.run(
        [sys.executable, str(CLI_PATH), "skip-rate", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _seed(instruction_id: str, compliant: int, non_compliant: int, expected: bool | None) -> None:
    ldb.record_instruction_compliance_batch(
        [(instruction_id, True, "seed", expected) for _ in range(compliant)]
        + [(instruction_id, False, "seed", expected) for _ in range(non_compliant)]
    )


# ── marker detection ──────────────────────────────────────────────


class TestMarkerDetection:
    def test_line_start_marker_is_detected(self):
        assert has_do_route_marker(DO_ROUTE_PROMPT) is True

    def test_plain_prompt_carries_no_marker(self):
        assert has_do_route_marker(PLAIN_PROMPT) is False

    def test_quoted_mid_prose_mention_is_not_a_marker(self):
        assert has_do_route_marker("I changed the [do-route] agent=x line in the docs.") is False

    @pytest.mark.parametrize("value", ["", None])
    def test_empty_input_carries_no_marker(self, value):
        assert has_do_route_marker(value) is False


# ── recording the population ──────────────────────────────────────


class TestPopulationRecording:
    def test_do_routed_dispatch_records_expected_true(self, db_env):
        assert _run_hook(DO_ROUTE_PROMPT, db_env).returncode == 0
        rows = _rows()
        assert {r["instruction_id"] for r in rows} == {"M04", "M05", "M06"}
        assert all(r["directive_expected"] == 1 for r in rows)

    def test_unrouted_dispatch_records_expected_false(self, db_env):
        assert _run_hook(PLAIN_PROMPT, db_env).returncode == 0
        rows = _rows()
        assert rows
        assert all(r["directive_expected"] == 0 for r in rows)

    def test_caller_that_states_no_population_records_unknown(self, db_env):
        hook.record_compliance_batch({"M04": True}, "no-population")
        assert [r["directive_expected"] for r in _rows()] == [None]

    def test_every_observable_instruction_declares_its_population(self):
        for instr_id, instr in hook.INSTRUCTIONS.items():
            assert isinstance(instr.get("injected_by_do_route"), bool), f"{instr_id} lacks a population declaration"


# ── skip-rate denominator ─────────────────────────────────────────


class TestSkipRateDenominator:
    def test_rate_ignores_not_expected_and_unknown_rows(self, db_env):
        _seed("M04", compliant=30, non_compliant=10, expected=True)  # 25% of 40
        _seed("M04", compliant=0, non_compliant=500, expected=False)
        _seed("M04", compliant=0, non_compliant=100, expected=None)

        result = _run_skip_rate(db_env, ["--json"])
        assert result.returncode == 0
        m04 = next(r for r in json.loads(result.stdout) if r["id"] == "M04")
        assert m04["scored_observations"] == 40
        assert m04["skip_rate"] == 25.0
        assert m04["not_expected"] == 500
        assert m04["unknown"] == 100
        assert m04["status"] == "CONVERT_TO_GATE"

    def test_gate_verdict_needs_an_expected_population(self, db_env):
        _seed("M05", compliant=0, non_compliant=600, expected=False)
        _seed("M05", compliant=0, non_compliant=400, expected=None)

        result = _run_skip_rate(db_env, ["--json"])
        m05 = next(r for r in json.loads(result.stdout) if r["id"] == "M05")
        assert m05["scored_observations"] == 0
        assert m05["skip_rate"] is None
        assert m05["status"] != "CONVERT_TO_GATE"

    def test_unobservable_instruction_stays_not_measurable(self, db_env):
        _seed("M01", compliant=5, non_compliant=35, expected=True)
        result = _run_skip_rate(db_env, ["--json"])
        m01 = next(r for r in json.loads(result.stdout) if r["id"] == "M01")
        assert m01["observations"] == 40
        assert m01["status"] == "NOT MEASURABLE"

    def test_report_states_its_denominator(self, db_env):
        _seed("M04", compliant=30, non_compliant=10, expected=True)
        _seed("M04", compliant=0, non_compliant=500, expected=False)
        result = _run_skip_rate(db_env, [])
        assert result.returncode == 0
        assert "[do-route]" in result.stdout
        assert "Not expected" in result.stdout
        assert "Unknown" in result.stdout

    def test_no_gate_recommendation_from_the_wrong_population(self, db_env):
        _seed("M06", compliant=10, non_compliant=990, expected=False)
        result = _run_skip_rate(db_env, [])
        assert "CONVERT TO GATE" not in result.stdout
        assert "No instructions flagged" in result.stdout


# ── migration ─────────────────────────────────────────────────────


class TestMigration:
    def test_column_exists_after_init(self, db_env):
        with ldb.get_connection() as conn:
            columns = {r[1] for r in conn.execute("PRAGMA table_info(instruction_compliance)")}
        assert "directive_expected" in columns

    def test_migration_runs_twice_without_error(self, db_env):
        with ldb.get_connection() as conn:
            ldb._run_migrations(conn)
            ldb._run_migrations(conn)
            columns = {r[1] for r in conn.execute("PRAGMA table_info(instruction_compliance)")}
        assert "directive_expected" in columns

    def test_pre_migration_rows_become_unknown(self, tmp_path, monkeypatch):
        """A v8 database keeps its history and reports it as an unknown population."""
        monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
        monkeypatch.setattr(ldb, "_initialized", False, raising=False)
        db_path = tmp_path / "learning.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE instruction_compliance ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, instruction_id TEXT NOT NULL, "
            "compliant BOOLEAN NOT NULL, session_id TEXT, "
            "timestamp TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO instruction_compliance (instruction_id, compliant) VALUES ('M04', 0)")
        conn.execute("PRAGMA user_version = 8")
        conn.commit()
        conn.close()

        ldb.init_db()
        with ldb.get_connection() as connection:
            rows = [dict(r) for r in connection.execute("SELECT * FROM instruction_compliance")]
        assert len(rows) == 1
        assert rows[0]["directive_expected"] is None
        monkeypatch.setattr(ldb, "_initialized", False, raising=False)


# ── non-blocking ──────────────────────────────────────────────────


class TestNonBlocking:
    @pytest.mark.parametrize("payload", ["", "{not json", "null"])
    def test_hook_exits_zero(self, payload, tmp_path):
        env = {**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert result.returncode == 0
