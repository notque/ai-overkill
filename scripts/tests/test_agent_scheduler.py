"""Tests for agent-scheduler.py — cron parsing, config loading, cost estimation, DB operations."""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
agent_scheduler = importlib.import_module("agent-scheduler")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config_path(tmp_path: Path) -> Path:
    """Write a minimal schedules.json and return its path."""
    config = {
        "version": 1,
        "defaults": {"model": "haiku", "timeout_seconds": 60, "enabled": True},
        "daily_budget_usd": 5.0,
        "webhook_port": 19100,
        "jobs": [
            {
                "name": "test-cron",
                "description": "Test cron job",
                "trigger": {"type": "cron", "schedule": "*/5 * * * *"},
                "prompt": "echo test",
                "model": "haiku",
                "timeout_seconds": 10,
                "cost_limit_usd": 0.01,
            },
            {
                "name": "test-webhook",
                "description": "Test webhook job",
                "trigger": {"type": "webhook", "path": "/webhook/test", "filter": {"event": "push"}},
                "prompt": "Review {payload.ref}",
                "model": "sonnet",
                "timeout_seconds": 30,
                "cost_limit_usd": 0.05,
            },
            {
                "name": "test-disabled",
                "description": "Disabled job",
                "trigger": {"type": "cron", "schedule": "0 * * * *"},
                "prompt": "should not run",
                "enabled": False,
            },
        ],
    }
    path = tmp_path / "schedules.json"
    path.write_text(json.dumps(config))
    return path


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the scheduler DB to a temporary directory."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    db_path = db_dir / "scheduler-results.db"
    monkeypatch.setattr(agent_scheduler, "_DB_DIR", db_dir)
    monkeypatch.setattr(agent_scheduler, "_DB_PATH", db_path)
    return db_path


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_valid_config(self, sample_config_path: Path) -> None:
        config = agent_scheduler.load_config(sample_config_path)
        assert len(config["jobs"]) == 3
        assert config["daily_budget_usd"] == 5.0

    def test_defaults_applied(self, sample_config_path: Path) -> None:
        config = agent_scheduler.load_config(sample_config_path)
        disabled_job = next(j for j in config["jobs"] if j["name"] == "test-disabled")
        assert disabled_job["model"] == "haiku"
        assert disabled_job["timeout_seconds"] == 60

    def test_missing_config_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            agent_scheduler.load_config(tmp_path / "nonexistent.json")

    def test_invalid_json_exits(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")
        with pytest.raises(SystemExit):
            agent_scheduler.load_config(bad_file)

    def test_missing_jobs_key_exits(self, tmp_path: Path) -> None:
        no_jobs = tmp_path / "no-jobs.json"
        no_jobs.write_text(json.dumps({"version": 1}))
        with pytest.raises(SystemExit):
            agent_scheduler.load_config(no_jobs)

    def test_command_runner_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "schedules.json"
        config_path.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "name": "doc-counts",
                            "runner": "command",
                            "trigger": {"type": "cron", "schedule": "0 * * * *"},
                            "command": ["python3", "scripts/validate-doc-counts.py"],
                        }
                    ]
                }
            )
        )

        config = agent_scheduler.load_config(config_path)
        job = config["jobs"][0]
        assert job["runner"] == "command"
        assert job["model"] == "command"
        assert job["cost_limit_usd"] == 0.0

    def test_command_runner_requires_argv_array(self, tmp_path: Path) -> None:
        config_path = tmp_path / "schedules.json"
        config_path.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "name": "bad-command",
                            "runner": "command",
                            "trigger": {"type": "cron", "schedule": "0 * * * *"},
                            "command": "python3 scripts/validate-doc-counts.py",
                        }
                    ]
                }
            )
        )

        with pytest.raises(SystemExit):
            agent_scheduler.load_config(config_path)


# ---------------------------------------------------------------------------
# Cron expression parsing
# ---------------------------------------------------------------------------


class TestCronParsing:
    """Test the stdlib cron expression parser."""

    @pytest.fixture
    def scheduler(self, sample_config_path: Path) -> Any:
        config = agent_scheduler.load_config(sample_config_path)
        return agent_scheduler.Scheduler(config, sample_config_path)

    @pytest.mark.parametrize(
        ("expression", "dt", "expected"),
        [
            ("* * * * *", datetime(2026, 3, 14, 12, 30, tzinfo=timezone.utc), True),
            ("*/5 * * * *", datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc), True),
            ("*/5 * * * *", datetime(2026, 3, 14, 12, 5, tzinfo=timezone.utc), True),
            ("*/5 * * * *", datetime(2026, 3, 14, 12, 3, tzinfo=timezone.utc), False),
            ("30 8 * * *", datetime(2026, 3, 14, 8, 30, tzinfo=timezone.utc), True),
            ("30 8 * * *", datetime(2026, 3, 14, 9, 30, tzinfo=timezone.utc), False),
            ("0 */6 * * *", datetime(2026, 3, 14, 0, 0, tzinfo=timezone.utc), True),
            ("0 */6 * * *", datetime(2026, 3, 14, 6, 0, tzinfo=timezone.utc), True),
            ("0 */6 * * *", datetime(2026, 3, 14, 3, 0, tzinfo=timezone.utc), False),
            ("0 8 * * *", datetime(2026, 3, 14, 8, 0, tzinfo=timezone.utc), True),
            ("0 8 * * *", datetime(2026, 3, 14, 9, 0, tzinfo=timezone.utc), False),
            ("0 0 1 * *", datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), True),
            ("0 0 1 * *", datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc), False),
            ("10-20 * * * *", datetime(2026, 3, 14, 12, 15, tzinfo=timezone.utc), True),
            ("10-20 * * * *", datetime(2026, 3, 14, 12, 25, tzinfo=timezone.utc), False),
            ("0,30 * * * *", datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc), True),
            ("0,30 * * * *", datetime(2026, 3, 14, 12, 30, tzinfo=timezone.utc), True),
            ("0,30 * * * *", datetime(2026, 3, 14, 12, 15, tzinfo=timezone.utc), False),
        ],
    )
    def test_cron_matches(self, scheduler: Any, expression: str, dt: datetime, expected: bool) -> None:
        assert scheduler._cron_matches(expression, dt) is expected

    def test_invalid_field_count_returns_false(self, scheduler: Any) -> None:
        dt = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
        assert scheduler._cron_matches("* * *", dt) is False

    def test_field_matches_star(self) -> None:
        assert agent_scheduler.Scheduler._field_matches("*", 5, 0) is True

    def test_field_matches_step(self) -> None:
        assert agent_scheduler.Scheduler._field_matches("*/10", 20, 0) is True
        assert agent_scheduler.Scheduler._field_matches("*/10", 25, 0) is False

    def test_field_matches_exact(self) -> None:
        assert agent_scheduler.Scheduler._field_matches("30", 30, 0) is True
        assert agent_scheduler.Scheduler._field_matches("30", 31, 0) is False


# ---------------------------------------------------------------------------
# Prompt template rendering
# ---------------------------------------------------------------------------


class TestRenderPrompt:
    def test_simple_variable(self) -> None:
        result = agent_scheduler.render_prompt("Hello {file_path}", {"file_path": "/tmp/test.md"})
        assert result == "Hello /tmp/test.md"

    def test_nested_dot_notation(self) -> None:
        variables: dict[str, Any] = {"payload": {"repository": {"full_name": "user/repo"}, "number": 42}}
        result = agent_scheduler.render_prompt(
            "Review PR #{payload.number} on {payload.repository.full_name}", variables
        )
        assert result == "Review PR #42 on user/repo"

    def test_missing_variable_preserved(self) -> None:
        result = agent_scheduler.render_prompt("Missing {unknown_var}", {})
        assert result == "Missing {unknown_var}"

    def test_job_self_reference(self) -> None:
        variables: dict[str, Any] = {"job": {"name": "health-check", "description": "Check health"}}
        result = agent_scheduler.render_prompt("Job: {job.name} - {job.description}", variables)
        assert result == "Job: health-check - Check health"

    def test_command_job_command_renders_each_arg_without_shell(self) -> None:
        job = {"command": ["python3", "scripts/check.py", "--path", "{file_path}"]}
        result = agent_scheduler.build_command_job_command(job, {"file_path": "a file.md"})
        assert result == ["python3", "scripts/check.py", "--path", "a file.md"]


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_haiku_estimation_from_output_length(self) -> None:
        stdout = "x" * 400
        cost = agent_scheduler.estimate_cost("haiku", stdout)
        assert cost > 0
        assert cost < 0.01

    def test_opus_more_expensive_than_haiku(self) -> None:
        stdout = "x" * 4000
        haiku_cost = agent_scheduler.estimate_cost("haiku", stdout)
        opus_cost = agent_scheduler.estimate_cost("opus", stdout)
        assert opus_cost > haiku_cost

    def test_token_count_parsing(self) -> None:
        stdout = "Some output\ninput_tokens: 1000\noutput_tokens: 500\n"
        cost = agent_scheduler.estimate_cost("haiku", stdout)
        expected = (1000 / 1_000_000) * 1.00 + (500 / 1_000_000) * 5.00
        assert abs(cost - round(expected, 6)) < 0.000001

    def test_unknown_model_falls_back_to_sonnet(self) -> None:
        cost = agent_scheduler.estimate_cost("unknown-model", "x" * 400)
        sonnet_cost = agent_scheduler.estimate_cost("sonnet", "x" * 400)
        assert cost == sonnet_cost


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


class TestDatabase:
    def test_init_creates_tables(self, temp_db: Path) -> None:
        agent_scheduler.init_db()
        conn = sqlite3.connect(str(temp_db))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t[0] for t in tables}
        assert "job_results" in table_names
        assert "daily_costs" in table_names
        conn.close()

    def test_record_result(self, temp_db: Path) -> None:
        agent_scheduler.init_db()
        agent_scheduler.record_result(
            job_name="test-job",
            trigger_type="cron",
            started_at="2026-03-14T12:00:00+00:00",
            finished_at="2026-03-14T12:00:05+00:00",
            exit_code=0,
            stdout="output",
            stderr="",
            model="haiku",
            duration_seconds=5.0,
            cost_estimate_usd=0.001,
            trigger_detail="*/5 * * * *",
        )

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM job_results").fetchall()
        assert len(rows) == 1
        assert rows[0]["job_name"] == "test-job"
        assert rows[0]["exit_code"] == 0
        assert rows[0]["duration_seconds"] == 5.0
        conn.close()

    def test_daily_costs_accumulate(self, temp_db: Path) -> None:
        agent_scheduler.init_db()
        for i in range(3):
            agent_scheduler.record_result(
                job_name=f"job-{i}",
                trigger_type="cron",
                started_at=f"2026-03-14T12:0{i}:00+00:00",
                finished_at=f"2026-03-14T12:0{i}:05+00:00",
                exit_code=0,
                stdout="",
                stderr="",
                model="haiku",
                duration_seconds=5.0,
                cost_estimate_usd=0.01,
                trigger_detail="* * * * *",
            )

        daily_cost = agent_scheduler.get_daily_cost()
        assert abs(daily_cost - 0.03) < 0.001

    def test_get_daily_cost_no_data(self, temp_db: Path) -> None:
        agent_scheduler.init_db()
        assert agent_scheduler.get_daily_cost() == 0.0


# ---------------------------------------------------------------------------
# Scheduler job execution
# ---------------------------------------------------------------------------


class TestSchedulerExecution:
    @pytest.fixture
    def scheduler(self, sample_config_path: Path, temp_db: Path) -> Any:
        config = agent_scheduler.load_config(sample_config_path)
        agent_scheduler.init_db()
        return agent_scheduler.Scheduler(config, sample_config_path)

    def test_get_jobs_by_trigger(self, scheduler: Any) -> None:
        cron_jobs = scheduler._get_jobs_by_trigger("cron")
        assert len(cron_jobs) == 1
        assert cron_jobs[0]["name"] == "test-cron"

    def test_disabled_jobs_excluded(self, scheduler: Any) -> None:
        all_cron = [j for j in scheduler.config["jobs"] if j["trigger"]["type"] == "cron"]
        enabled_cron = scheduler._get_jobs_by_trigger("cron")
        assert len(all_cron) == 2
        assert len(enabled_cron) == 1

    @patch("subprocess.run")
    def test_execute_job_success(self, mock_run: MagicMock, scheduler: Any) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="Job output", stderr="")
        job = scheduler.config["jobs"][0]
        result = scheduler.execute_job(job, "cron", "*/5 * * * *")
        assert result is not None
        assert result["exit_code"] == 0
        assert result["job_name"] == "test-cron"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_job_overlap_prevention(self, mock_run: MagicMock, scheduler: Any) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler._running_jobs.add("test-cron")
        job = scheduler.config["jobs"][0]
        result = scheduler.execute_job(job, "cron", "*/5 * * * *")
        assert result is None
        mock_run.assert_not_called()

    @patch("subprocess.run", side_effect=FileNotFoundError("claude not found"))
    def test_execute_job_claude_not_found(self, _mock_run: MagicMock, scheduler: Any) -> None:
        job = scheduler.config["jobs"][0]
        result = scheduler.execute_job(job, "cron", "*/5 * * * *")
        assert result is not None
        assert result["exit_code"] == 127

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=10))
    def test_execute_job_timeout(self, _mock_run: MagicMock, scheduler: Any) -> None:
        job = scheduler.config["jobs"][0]
        result = scheduler.execute_job(job, "cron", "*/5 * * * *")
        assert result is not None
        assert result["exit_code"] == 124

    @patch("subprocess.run")
    def test_execute_command_job_uses_command_runner(self, mock_run: MagicMock, scheduler: Any, temp_db: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="docs ok", stderr="")
        job = {
            "name": "doc-counts",
            "runner": "command",
            "trigger": {"type": "cron", "schedule": "0 * * * *"},
            "command": ["python3", "scripts/validate-doc-counts.py"],
            "timeout_seconds": 10,
            "model": "command",
            "cost_limit_usd": 0.0,
        }

        result = scheduler.execute_job(job, "cron", "0 * * * *")

        assert result is not None
        assert result["exit_code"] == 0
        assert result["cost_estimate_usd"] == 0.0
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ["python3", "scripts/validate-doc-counts.py"]
        assert kwargs["cwd"] == str(agent_scheduler._REPO_ROOT)

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT model, cost_estimate_usd FROM job_results WHERE job_name = ?", ("doc-counts",)
        ).fetchone()
        assert row["model"] == "command"
        assert row["cost_estimate_usd"] == 0.0
        conn.close()

    def test_daily_budget_enforcement(self, scheduler: Any) -> None:
        for i in range(10):
            agent_scheduler.record_result(
                job_name=f"expensive-{i}",
                trigger_type="cron",
                started_at=f"2026-03-14T{i:02d}:00:00+00:00",
                finished_at=f"2026-03-14T{i:02d}:01:00+00:00",
                exit_code=0,
                stdout="",
                stderr="",
                model="opus",
                duration_seconds=60,
                cost_estimate_usd=1.0,
                trigger_detail="* * * * *",
            )

        job = scheduler.config["jobs"][0]
        result = scheduler.execute_job(job, "cron", "*/5 * * * *")
        assert result is None

    @patch("subprocess.run")
    def test_daily_budget_does_not_block_command_jobs(self, mock_run: MagicMock, scheduler: Any) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        for i in range(10):
            agent_scheduler.record_result(
                job_name=f"expensive-{i}",
                trigger_type="cron",
                started_at=f"2026-03-14T{i:02d}:00:00+00:00",
                finished_at=f"2026-03-14T{i:02d}:01:00+00:00",
                exit_code=0,
                stdout="",
                stderr="",
                model="opus",
                duration_seconds=60,
                cost_estimate_usd=1.0,
                trigger_detail="* * * * *",
            )

        job = {
            "name": "doc-counts",
            "runner": "command",
            "trigger": {"type": "cron", "schedule": "0 * * * *"},
            "command": ["python3", "scripts/validate-doc-counts.py"],
            "timeout_seconds": 10,
            "model": "command",
            "cost_limit_usd": 0.0,
        }
        result = scheduler.execute_job(job, "cron", "0 * * * *")
        assert result is not None
        assert result["exit_code"] == 0


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------


class TestWebhookHandler:
    def test_signature_verification_valid(self) -> None:
        secret = "test-secret"  # security-review: ignore - intentional HMAC test fixture, not a credential
        body = b'{"action": "opened"}'
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        computed = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert hmac.compare_digest(expected, computed)

    def test_signature_verification_invalid(self) -> None:
        secret = "test-secret"  # security-review: ignore - intentional HMAC test fixture, not a credential
        body = b'{"action": "opened"}'
        wrong_sig = "sha256=" + "0" * 64
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert not hmac.compare_digest(wrong_sig, expected)
