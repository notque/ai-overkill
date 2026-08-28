"""Tests for instruction compliance hook and skip-rate dashboard command.

Covers:
- M01 phase banner detection (compliant and non-compliant)
- M03 routing decision detection
- M04 reference loading detection
- M05 completeness standard detection
- M06 density standard detection
- Multiple instructions in single output
- Empty/malformed input graceful handling
- skip-rate command formatted output
- Accurate skip-rate calculation across multiple observations
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

# Add hooks/lib to path for learning_db_v2 imports
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

# Import hook module with hyphenated filename via importlib
_hook_path = _repo_root / "hooks" / "instruction-compliance.py"
_spec = importlib.util.spec_from_file_location("instruction_compliance", _hook_path)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

check_compliance = _module.check_compliance
record_compliance_batch = _module.record_compliance_batch
INSTRUCTIONS = _module.INSTRUCTIONS


def record_compliance(
    instr_id: str,
    instr_name: str,
    compliant: bool,
    session_id: str,
    directive_expected: bool | None = True,
) -> None:
    """Thin wrapper for tests: single-observation convenience using batch API.

    Defaults to the /do-routed population — the one the skip rate is scored over.
    """
    from learning_db_v2 import record_instruction_compliance

    record_instruction_compliance(
        instruction_id=instr_id,
        compliant=compliant,
        session_id=session_id,
        directive_expected=directive_expected,
    )


# ─── check_compliance unit tests ──────────────────────────────────


class TestCheckCompliance:
    """Test compliance detection for each instruction."""

    def test_m01_phase_banner_compliant(self) -> None:
        """Agent output with phase banners -> M01 compliant."""
        text = "## Phase 1: Understanding\nSome content\n## Phase 2: Implementation"
        results = check_compliance(text)
        assert results["M01"] is True

    def test_m01_phase_banner_variant(self) -> None:
        """Phase N: variant also detected."""
        text = "Phase 1: Analysis\nPhase 2: Build"
        results = check_compliance(text)
        assert results["M01"] is True

    def test_m01_phase_banner_non_compliant(self) -> None:
        """Agent output WITHOUT phase banners -> M01 non-compliant."""
        text = "I analyzed the code and made changes. The tests pass now."
        results = check_compliance(text)
        assert results["M01"] is False

    def test_m03_routing_decision_compliant_equals(self) -> None:
        """Triple equals on standalone line signals routing table."""
        text = "===\nAgent: golang-general-engineer\nSkill: go-patterns\n==="
        results = check_compliance(text)
        assert results["M03"] is True

    def test_m03_no_false_positive_js_strict_equals(self) -> None:
        """JS === operator must NOT trigger M03 (false positive guard)."""
        text = "if (value === 'test') { return true; }"
        results = check_compliance(text)
        assert results["M03"] is False

    def test_m03_no_false_positive_markdown_separator(self) -> None:
        """Inline markdown === must NOT trigger M03 when not standalone."""
        text = "Some heading\n===continued text"
        results = check_compliance(text)
        assert results["M03"] is False

    def test_m03_routing_decision_compliant_keyword(self) -> None:
        """ROUTING: keyword signals routing decision."""
        text = "ROUTING: golang-general-engineer -> go-patterns"
        results = check_compliance(text)
        assert results["M03"] is True

    def test_m03_routing_decision_compliant_selected(self) -> None:
        """Selected: keyword signals routing decision."""
        text = "Selected: python-general-engineer with quick skill"
        results = check_compliance(text)
        assert results["M03"] is True

    def test_m03_routing_decision_non_compliant(self) -> None:
        """No routing markers -> M03 non-compliant."""
        text = "I'll help you with that Go code refactoring."
        results = check_compliance(text)
        assert results["M03"] is False

    def test_m04_reference_loading_compliant(self) -> None:
        """Reference Loading mention -> M04 compliant."""
        text = "Check the Reference Loading Table for signals matching this task."
        results = check_compliance(text)
        assert results["M04"] is True

    def test_m04_reference_loading_table_variant(self) -> None:
        """Reference table variant also detected."""
        text = "Loaded reference table entries for error patterns."
        results = check_compliance(text)
        assert results["M04"] is True

    def test_m04_before_starting_work_variant(self) -> None:
        """'Before starting work' prompt injection marker -> M04 compliant."""
        text = "Before starting work, read your agent .md file to find the Reference Loading Table."
        results = check_compliance(text)
        assert results["M04"] is True

    def test_m04_load_every_reference_variant(self) -> None:
        """'Load EVERY reference file' prompt marker -> M04 compliant."""
        text = "Load EVERY reference file whose signal matches this task."
        results = check_compliance(text)
        assert results["M04"] is True

    def test_m04_reference_loading_non_compliant(self) -> None:
        """No reference loading mention -> M04 non-compliant."""
        text = "I read the file and fixed the bug."
        results = check_compliance(text)
        assert results["M04"] is False

    def test_m05_completeness_compliant(self) -> None:
        """'deliver the finished product' -> M05 compliant."""
        text = "Your task: deliver the finished product. No partial work."
        results = check_compliance(text)
        assert results["M05"] is True

    def test_m05_completeness_ship_variant(self) -> None:
        """'ship the complete thing' variant also detected."""
        text = "Ship the complete thing before reporting done."
        results = check_compliance(text)
        assert results["M05"] is True

    def test_m05_completeness_non_compliant(self) -> None:
        """No completeness signal -> M05 non-compliant."""
        text = "Here's the implementation you requested."
        results = check_compliance(text)
        assert results["M05"] is False

    def test_m06_density_compliant(self) -> None:
        """'write dense' -> M06 compliant."""
        text = "Write dense. Cut filler. Prefer tables over paragraphs."
        results = check_compliance(text)
        assert results["M06"] is True

    def test_m06_density_variant(self) -> None:
        """'high fidelity, minimum words' variant also detected."""
        text = "High fidelity, minimum words. Report what changed."
        results = check_compliance(text)
        assert results["M06"] is True

    def test_m06_density_non_compliant(self) -> None:
        """No density signal -> M06 non-compliant."""
        text = "Let me provide a detailed explanation of every change."
        results = check_compliance(text)
        assert results["M06"] is False

    def test_multiple_instructions_single_output(self) -> None:
        """Multiple instructions detected in single output."""
        text = (
            "## Phase 1: Analysis\n"
            "===\n"
            "ROUTING: python-general-engineer\n"
            "===\n"
            "Reference Loading Table checked.\n"
            "Deliver the finished product.\n"
            "Write dense.\n"
        )
        results = check_compliance(text)
        assert results["M01"] is True
        assert results["M03"] is True
        assert results["M04"] is True
        assert results["M05"] is True
        assert results["M06"] is True

    def test_empty_text(self) -> None:
        """Empty text -> all non-compliant."""
        results = check_compliance("")
        assert all(v is False for v in results.values())

    def test_all_instruction_ids_present(self) -> None:
        """All 5 instrumented instructions are checked."""
        results = check_compliance("anything")
        expected_ids = {"M01", "M03", "M04", "M05", "M06"}
        assert set(results.keys()) == expected_ids


# ─── record_compliance unit tests ────────────────────────────────


class TestRecordCompliance:
    """Test compliance recording to instruction_compliance table."""

    def test_record_compliant(self, tmp_path: Path) -> None:
        """Recording a compliant observation inserts into instruction_compliance."""
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(tmp_path)}):
            import learning_db_v2

            learning_db_v2._initialized = False

            record_compliance("M01", "Phase Banners", True, "test-session-123")

            from learning_db_v2 import get_connection

            with get_connection() as conn:
                rows = conn.execute("SELECT * FROM instruction_compliance WHERE instruction_id = 'M01'").fetchall()
                assert len(rows) == 1
                assert rows[0]["compliant"] == 1  # SQLite stores True as 1
                assert rows[0]["session_id"] == "test-session-123"

    def test_record_non_compliant(self, tmp_path: Path) -> None:
        """Recording a non-compliant observation."""
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(tmp_path)}):
            import learning_db_v2

            learning_db_v2._initialized = False

            record_compliance("M01", "Phase Banners", False, "test-session-456")

            from learning_db_v2 import get_connection

            with get_connection() as conn:
                rows = conn.execute("SELECT * FROM instruction_compliance WHERE instruction_id = 'M01'").fetchall()
                assert len(rows) == 1
                assert rows[0]["compliant"] == 0  # SQLite stores False as 0

    def test_observations_accumulate(self, tmp_path: Path) -> None:
        """Multiple calls INSERT separate rows — never overwrite."""
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(tmp_path)}):
            import learning_db_v2

            learning_db_v2._initialized = False

            record_compliance("M01", "Phase Banners", True, "s1")
            record_compliance("M01", "Phase Banners", False, "s2")
            record_compliance("M01", "Phase Banners", True, "s3")

            from learning_db_v2 import get_connection

            with get_connection() as conn:
                rows = conn.execute("SELECT * FROM instruction_compliance WHERE instruction_id = 'M01'").fetchall()
                assert len(rows) == 3

    def test_batch_recording(self, tmp_path: Path) -> None:
        """Batch recording inserts the observable results in one transaction.

        M01/M03 are declared unobservable from this hook's surface and are
        dropped. Full contract: hooks/tests/test_instruction_observability.py.
        """
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(tmp_path)}):
            import learning_db_v2

            # Force full re-initialization in the temp directory
            learning_db_v2._initialized = False
            learning_db_v2.init_db()

            results = {"M01": True, "M03": False, "M04": True, "M05": False, "M06": True}
            record_compliance_batch(results, "batch-session")

            with learning_db_v2.get_connection() as conn:
                rows = conn.execute("SELECT * FROM instruction_compliance").fetchall()
                assert len(rows) == 3
                ids = {r["instruction_id"] for r in rows}
                assert ids == {"M04", "M05", "M06"}


# ─── Hook stdin integration tests ────────────────────────────────


class TestHookIntegration:
    """Test the hook script end-to-end via subprocess."""

    def _run_hook(self, stdin_data: str, tmp_dir: str) -> subprocess.CompletedProcess[str]:
        """Run the hook script with given stdin."""
        hook_path = _repo_root / "hooks" / "instruction-compliance.py"
        env = {
            **os.environ,
            "CLAUDE_LEARNING_DIR": tmp_dir,
            "PYTHONPATH": str(_repo_root / "hooks" / "lib"),
        }
        return subprocess.run(
            [sys.executable, str(hook_path)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def test_empty_stdin_exits_zero(self, tmp_path: Path) -> None:
        """Empty stdin -> graceful exit 0."""
        result = self._run_hook("", str(tmp_path))
        assert result.returncode == 0

    def test_malformed_json_exits_zero(self, tmp_path: Path) -> None:
        """Malformed JSON -> graceful exit 0, no crash."""
        result = self._run_hook("not json at all", str(tmp_path))
        assert result.returncode == 0

    def test_valid_agent_output_records(self, tmp_path: Path) -> None:
        """Valid agent output with phase banners records compliance."""
        event = {
            "tool_name": "Agent",
            "tool_result": {"output": "## Phase 1: Analysis\nRouting: selected agent\n"},
            "tool_input": "Write dense. Deliver the finished product.",
        }
        result = self._run_hook(json.dumps(event), str(tmp_path))
        assert result.returncode == 0

    def test_empty_tool_result_exits_zero(self, tmp_path: Path) -> None:
        """Event with empty tool result -> graceful exit 0."""
        event = {"tool_name": "Agent", "tool_result": {}}
        result = self._run_hook(json.dumps(event), str(tmp_path))
        assert result.returncode == 0


# ─── skip-rate command tests ─────────────────────────────────────


class TestSkipRateCommand:
    """Test the skip-rate dashboard command."""

    def _run_skip_rate(self, tmp_dir: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run the skip-rate command."""
        script_path = _repo_root / "scripts" / "learning-db.py"
        cmd = [sys.executable, str(script_path), "skip-rate"]
        if extra_args:
            cmd.extend(extra_args)
        env = {
            **os.environ,
            "CLAUDE_LEARNING_DIR": tmp_dir,
            "PYTHONPATH": str(_repo_root / "hooks" / "lib"),
        }
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)

    def _seed_compliance_data(self, tmp_dir: str) -> None:
        """Seed instruction_compliance table with test observations."""
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": tmp_dir}):
            import learning_db_v2

            learning_db_v2._initialized = False

            # Record some compliant and non-compliant observations
            record_compliance("M01", "Phase Banners", True, "seed-session")
            record_compliance("M03", "Routing Decision", True, "seed-session")
            record_compliance("M04", "Reference Loading", False, "seed-session")
            record_compliance("M05", "Completeness", False, "seed-session")
            record_compliance("M06", "Density Standard", True, "seed-session")

    def test_no_data_message(self, tmp_path: Path) -> None:
        """No compliance data -> informative message."""
        result = self._run_skip_rate(str(tmp_path))
        assert result.returncode == 0
        assert "No instruction compliance data found" in result.stdout

    def test_formatted_output(self, tmp_path: Path) -> None:
        """With data, produces formatted table."""
        self._seed_compliance_data(str(tmp_path))
        result = self._run_skip_rate(str(tmp_path))
        assert result.returncode == 0
        assert "Instruction Skip Rate Report" in result.stdout
        assert "M01" in result.stdout

    def test_json_output(self, tmp_path: Path) -> None:
        """--json flag produces valid JSON."""
        self._seed_compliance_data(str(tmp_path))
        result = self._run_skip_rate(str(tmp_path), ["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "skip_rate" in data[0]

    def test_skip_rate_40_percent(self, tmp_path: Path) -> None:
        """3 compliant + 2 non-compliant for M01 -> 40% skip rate."""
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(tmp_path)}):
            import learning_db_v2

            learning_db_v2._initialized = False

            # 3 compliant
            record_compliance("M01", "Phase Banners", True, "s1")
            record_compliance("M01", "Phase Banners", True, "s2")
            record_compliance("M01", "Phase Banners", True, "s3")
            # 2 non-compliant
            record_compliance("M01", "Phase Banners", False, "s4")
            record_compliance("M01", "Phase Banners", False, "s5")

        result = self._run_skip_rate(str(tmp_path), ["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        m01 = next(r for r in data if r["id"] == "M01")
        assert m01["observations"] == 5
        assert m01["non_compliant"] == 2
        assert m01["scored_observations"] == 5
        assert m01["skip_rate"] == 40.0
        assert "[do-route]" in m01["denominator"]
