#!/usr/bin/env python3
"""Tests for the ` pipeline=<name>` token on the [do-route] marker.

build-dispatch.py emits `pipeline={name}` whenever the router picks a workflow
pipeline. The recorder never parsed it, so every pipeline pick was invisible:
the `evidence_route_decisions.pipeline` column stayed NULL on every row.

Covers:
- A marker carrying `pipeline=X` writes X to the DECISION event and to the
  evidence_route_decisions.pipeline column.
- A marker without the token writes no event field and leaves the column NULL.
- Marker-line scoping: `pipeline=` in the task body is prose, never a token.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_routing_pipeline_token.py -v
"""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
A_PATH = HOOKS_DIR / "routing-decision-recorder.py"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB and the bridge state dir at a throwaway location."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    import routing_outcome_state as ros

    monkeypatch.setattr(ros, "_STATE_DIR", tmp_path / "state")
    yield {"db_dir": db_dir, "state": tmp_path / "state"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


def _event(marker_body, *, session, body="do the work"):
    """PostToolUse:Agent event whose prompt starts with the supplied marker line."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": session,
        "tool_input": {
            "subagent_type": "python-general-engineer",
            "description": "do work",
            "prompt": marker_body + "\n" + body,
        },
        "tool_result": {"output": "ok", "is_error": False},
    }


def _run(db_env, monkeypatch, marker_body, session, body="do the work"):
    """Run the recorder on one marker; return (decision event, evidence row)."""
    a = _load(A_PATH, f"rdr_pipe_{session}")
    monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
    monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
    event = _event(marker_body, session=session, body=body)
    with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
        a.main()
    return _decision_event(db_env), _evidence_row(db_env, session)


def _decision_event(db_env):
    path = db_env["db_dir"] / "route-events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return next(e for e in events if e["type"] == "decision")


def _evidence_row(db_env, session):
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    conn = sqlite3.connect(ldb.get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM evidence_route_decisions WHERE session_id = ?",
            (session,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


_MARKER = "[do-route] agent=python-general-engineer skill=pr-workflow complexity=medium"


class TestPipelineToken:
    def test_pipeline_token_recorded(self, db_env, monkeypatch):
        decision, row = _run(
            db_env,
            monkeypatch,
            f"{_MARKER} pipeline=doc-pipeline model=opus",
            "pipe-yes",
        )
        assert decision["pipeline"] == "doc-pipeline"
        assert row["pipeline"] == "doc-pipeline"
        assert decision["model"] == "opus"  # sibling tokens still parse

    def test_absent_pipeline_token_records_null(self, db_env, monkeypatch):
        decision, row = _run(db_env, monkeypatch, _MARKER, "pipe-no")
        assert "pipeline" not in decision
        assert row["pipeline"] is None

    def test_pipeline_in_body_ignored(self, db_env, monkeypatch):
        # Marker-line scoping: prose mentioning pipeline= is not a router token.
        decision, row = _run(
            db_env,
            monkeypatch,
            _MARKER,
            "pipe-body",
            body="Document the pipeline=doc-pipeline token syntax.",
        )
        assert "pipeline" not in decision
        assert row["pipeline"] is None

    def test_dash_pipeline_records_null(self, db_env, monkeypatch):
        decision, row = _run(db_env, monkeypatch, f"{_MARKER} pipeline=-", "pipe-dash")
        assert "pipeline" not in decision
        assert row["pipeline"] is None


class TestParsePipelineUnit:
    def test_parse_pipeline_reads_marker_line(self):
        a = _load(A_PATH, "rdr_pipe_unit")
        assert a.parse_pipeline(f"{_MARKER} pipeline=research-pipeline") == "research-pipeline"
        assert a.parse_pipeline(_MARKER) is None
        assert a.parse_pipeline("no marker here pipeline=doc-pipeline") is None
