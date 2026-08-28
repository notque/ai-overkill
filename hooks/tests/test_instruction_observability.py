#!/usr/bin/env python3
"""Tests for instruction observability declarations in instruction-compliance.

The hook runs on PostToolUse:Agent and scans only the dispatch prompt plus the
subagent report. Phase banners (M01) and the routing banner (M03) are
main-thread orchestrator output, present in neither string — their recorded
skip rates were an artifact of the measuring surface, not of behavior. Each
instruction now declares whether this hook can observe it; unobservable ones
are not recorded, and the skip-rate report never proposes a gate for them.

Covers:
- Every instruction declares `observable`; M01/M03 are False, M04-M06 True.
- record_compliance_batch writes rows only for observable instructions.
- Two-sample proof per recorded instruction: one text that matches, one that
  does not.
- skip-rate never flags an unobservable instruction for gate conversion, and
  still flags an observable one.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_instruction_observability.py -v
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "hooks" / "lib"
HOOK_PATH = REPO_ROOT / "hooks" / "instruction-compliance.py"
CLI_PATH = REPO_ROOT / "scripts" / "learning-db.py"

sys.path.insert(0, str(LIB_DIR))

_spec = importlib.util.spec_from_file_location("instruction_compliance", HOOK_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

INSTRUCTIONS = mod.INSTRUCTIONS
check_compliance = mod.check_compliance
record_compliance_batch = mod.record_compliance_batch


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB at a throwaway location."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    yield db_dir


def _rows(instruction_id: str | None = None) -> list[dict]:
    import learning_db_v2 as ldb

    with ldb.get_connection() as conn:
        if instruction_id:
            cur = conn.execute(
                "SELECT * FROM instruction_compliance WHERE instruction_id = ?",
                (instruction_id,),
            )
        else:
            cur = conn.execute("SELECT * FROM instruction_compliance")
        return [dict(r) for r in cur.fetchall()]


class TestObservabilityDeclarations:
    """Every instruction states whether this hook's surface can see it."""

    def test_every_instruction_declares_observable(self):
        for instr_id, instr in INSTRUCTIONS.items():
            assert isinstance(instr.get("observable"), bool), f"{instr_id} lacks an observable declaration"

    def test_main_thread_instructions_are_unobservable(self):
        assert INSTRUCTIONS["M01"]["observable"] is False
        assert INSTRUCTIONS["M03"]["observable"] is False

    def test_prompt_surface_instructions_stay_observable(self):
        assert INSTRUCTIONS["M04"]["observable"] is True
        assert INSTRUCTIONS["M05"]["observable"] is True
        assert INSTRUCTIONS["M06"]["observable"] is True


class TestUnobservableNotRecorded:
    """Unobservable instructions produce no compliance rows."""

    def test_batch_skips_unobservable_instructions(self, db_env):
        record_compliance_batch(
            {"M01": False, "M03": False, "M04": True, "M05": False, "M06": True},
            "obs-session",
        )
        recorded = {r["instruction_id"] for r in _rows()}
        assert recorded == {"M04", "M05", "M06"}

    def test_batch_of_only_unobservable_writes_nothing(self, db_env):
        record_compliance_batch({"M01": True, "M03": True}, "obs-none")
        assert _rows() == []


class TestRecordedInstructionTwoSampleProof:
    """One text that must match, one that must not, per recorded instruction."""

    @pytest.mark.parametrize(
        ("instr_id", "hit", "miss"),
        [
            (
                "M04",
                "Consult the Reference Loading Table before starting work.",
                "I read the file and fixed the bug.",
            ),
            (
                "M05",
                "Deliver the finished product. Ship the complete thing.",
                "Here is the implementation you requested.",
            ),
            (
                "M06",
                "Write dense. High fidelity, minimum words.",
                "Let me explain every change in detail.",
            ),
        ],
    )
    def test_two_sample_proof(self, instr_id, hit, miss):
        assert check_compliance(hit)[instr_id] is True
        assert check_compliance(miss)[instr_id] is False


class TestSkipRateGateVerdict:
    """The gate recommendation reads only instructions this hook can observe."""

    def _seed(self, instruction_id: str, compliant: int, non_compliant: int) -> None:
        """Seed /do-routed observations — the population the rate is scored over."""
        from learning_db_v2 import record_instruction_compliance_batch

        record_instruction_compliance_batch(
            [(instruction_id, True, "seed", True) for _ in range(compliant)]
            + [(instruction_id, False, "seed", True) for _ in range(non_compliant)]
        )

    def _run(self, db_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "CLAUDE_LEARNING_DIR": str(db_dir), "PYTHONPATH": str(LIB_DIR)}
        return subprocess.run(
            [sys.executable, str(CLI_PATH), "skip-rate", *args],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

    def test_unobservable_instruction_never_flagged(self, db_env):
        self._seed("M01", compliant=5, non_compliant=35)  # 87.5% skip, 40 obs
        result = self._run(db_env, ["--json"])
        assert result.returncode == 0
        m01 = next(r for r in json.loads(result.stdout) if r["id"] == "M01")
        assert m01["observations"] == 40  # historical rows stay visible
        assert m01["status"] != "CONVERT_TO_GATE"

    def test_observable_instruction_still_flagged(self, db_env):
        self._seed("M04", compliant=5, non_compliant=35)
        result = self._run(db_env, ["--json"])
        m04 = next(r for r in json.loads(result.stdout) if r["id"] == "M04")
        assert m04["status"] == "CONVERT_TO_GATE"

    def test_flagged_count_excludes_unobservable(self, db_env):
        self._seed("M01", compliant=5, non_compliant=35)
        result = self._run(db_env, [])
        assert result.returncode == 0
        assert "M01" in result.stdout  # row stays in the table
        assert "No instructions flagged" in result.stdout
