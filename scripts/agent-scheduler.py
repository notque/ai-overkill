#!/usr/bin/env python3
"""
Agent Scheduler Daemon — autonomous execution of Claude agent jobs.

Reads job definitions from schedules.json, executes deterministic commands or
Claude prompts, and persists results in SQLite. Supports cron schedules, HTTP
webhooks, and filesystem watchers.

Usage:
    python3 scripts/agent-scheduler.py                     # Run with default config
    python3 scripts/agent-scheduler.py --config alt.json   # Custom config file
    python3 scripts/agent-scheduler.py --dry-run            # Validate config only

Signals:
    SIGHUP  — Reload schedules.json without restart
    SIGTERM — Graceful shutdown

Exit codes:
    0 = clean shutdown
    1 = startup error (config, permissions, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "schedules.json"
_DB_DIR = Path.home() / ".claude" / "learning"
_DB_PATH = _DB_DIR / "scheduler-results.db"
_PID_FILE = Path("/tmp/agent-scheduler.pid")

_COST_PER_MILLION: dict[str, dict[str, float]] = {
    # Claude API list price per 1M tokens for the model each alias resolves to
    # today (haiku -> Haiku 4.5, sonnet -> Sonnet 5, opus -> Opus 5). Re-check
    # whenever the alias targets change.
    "haiku": {"input": 1.00, "output": 5.00},
    "sonnet": {"input": 2.00, "output": 10.00},
    "opus": {"input": 5.00, "output": 25.00},
}

log = logging.getLogger("agent-scheduler")

# ---------------------------------------------------------------------------
# SQLite helpers (follows hooks/lib/usage_db.py patterns)
# ---------------------------------------------------------------------------


@contextmanager
def get_connection():
    """Get a database connection with Row factory and automatic cleanup."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize scheduler database schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS job_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                stdout TEXT,
                stderr TEXT,
                model TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                cost_estimate_usd REAL,
                trigger_detail TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_costs (
                date TEXT PRIMARY KEY,
                total_cost_usd REAL NOT NULL DEFAULT 0.0,
                job_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_job_name ON job_results(job_name);
            CREATE INDEX IF NOT EXISTS idx_started_at ON job_results(started_at);
        """)
        conn.commit()


def record_result(
    job_name: str,
    trigger_type: str,
    started_at: str,
    finished_at: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    model: str,
    duration_seconds: float,
    cost_estimate_usd: float,
    trigger_detail: str,
) -> None:
    """Persist a job execution result and update daily cost tracking."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO job_results
            (job_name, trigger_type, started_at, finished_at, exit_code,
             stdout, stderr, model, duration_seconds, cost_estimate_usd, trigger_detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                trigger_type,
                started_at,
                finished_at,
                exit_code,
                stdout,
                stderr,
                model,
                duration_seconds,
                cost_estimate_usd,
                trigger_detail,
            ),
        )
        conn.execute(
            """
            INSERT INTO daily_costs (date, total_cost_usd, job_count)
            VALUES (?, ?, 1)
            ON CONFLICT(date) DO UPDATE SET
                total_cost_usd = total_cost_usd + excluded.total_cost_usd,
                job_count = job_count + 1
            """,
            (today, cost_estimate_usd),
        )
        conn.commit()


def get_daily_cost() -> float:
    """Get total cost for the current UTC day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute("SELECT total_cost_usd FROM daily_costs WHERE date = ?", (today,)).fetchone()
        return float(row["total_cost_usd"]) if row else 0.0


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(config_path: Path) -> dict[str, Any]:
    """Load and validate schedules.json configuration.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        SystemExit: If config is missing or invalid.
    """
    if not config_path.exists():
        log.error("Config not found: %s", config_path)
        sys.exit(1)

    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        log.error("Invalid JSON in %s: %s", config_path, exc)
        sys.exit(1)

    if "jobs" not in data or not isinstance(data["jobs"], list):
        log.error("Config missing 'jobs' array")
        sys.exit(1)

    defaults = data.get("defaults", {})
    for job in data["jobs"]:
        runner = job.setdefault("runner", defaults.get("runner", "claude"))
        if runner not in {"claude", "command"}:
            log.error("Job %s has invalid runner: %s", job.get("name", "<unnamed>"), runner)
            sys.exit(1)

        if runner == "command":
            command = job.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
                log.error(
                    "Command job %s must define command as a non-empty string array", job.get("name", "<unnamed>")
                )
                sys.exit(1)
            job["model"] = "command"
            job.setdefault("cost_limit_usd", 0.0)
        else:
            if not isinstance(job.get("prompt"), str) or not job["prompt"]:
                log.error("Claude job %s must define a non-empty prompt", job.get("name", "<unnamed>"))
                sys.exit(1)
            job.setdefault("model", defaults.get("model", "sonnet"))
            job.setdefault("cost_limit_usd", 1.0)

        job.setdefault("timeout_seconds", defaults.get("timeout_seconds", 120))
        job.setdefault("max_retries", defaults.get("max_retries", 0))
        job.setdefault("enabled", defaults.get("enabled", True))

    log.info("Loaded %d jobs from %s", len(data["jobs"]), config_path)
    return data


# ---------------------------------------------------------------------------
# Prompt template rendering
# ---------------------------------------------------------------------------


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    """Render a prompt template with dot-notation variable substitution.

    Supports {payload.repository.full_name} style nested access,
    {file_path}, and {job.name} / {job.description}.
    """
    import re

    def _resolve(match: re.Match[str]) -> str:
        key = match.group(1)
        parts = key.split(".")
        value: Any = variables
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, match.group(0))
            else:
                return match.group(0)
        return str(value)

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}", _resolve, template)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def estimate_cost(model: str, stdout: str) -> float:
    """Estimate USD cost from Claude CLI output.

    Looks for token count lines in stdout. Falls back to a rough estimate
    based on output length when token counts are unavailable.
    """
    import re

    rates = _COST_PER_MILLION.get(model, _COST_PER_MILLION["sonnet"])

    # Try to parse token counts from Claude CLI output
    input_match = re.search(r"input[_ ]tokens?[:\s]+(\d+)", stdout, re.IGNORECASE)
    output_match = re.search(r"output[_ ]tokens?[:\s]+(\d+)", stdout, re.IGNORECASE)

    if input_match and output_match:
        input_tokens = int(input_match.group(1))
        output_tokens = int(output_match.group(1))
    else:
        # Rough estimate: ~4 chars per token
        output_tokens = max(len(stdout) // 4, 100)
        input_tokens = output_tokens // 2

    cost = (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]
    return round(cost, 6)


def build_command_job_command(job: dict[str, Any], variables: dict[str, Any]) -> list[str]:
    """Render a deterministic command job as argv without shell parsing."""
    return [render_prompt(arg, variables) for arg in job["command"]]


def build_claude_job_command(job: dict[str, Any], prompt: str, model: str) -> list[str]:
    """Build the Claude CLI command for a judgment-requiring job."""
    allowed_tools: list[str] = job.get("allowed_tools", [])
    if allowed_tools:
        return [
            "claude",
            "-p",
            prompt,
            "--model",
            model,
            "--allowedTools",
            ",".join(allowed_tools),
            "--print",
        ]

    log.debug("Job %s has no allowed_tools — running with --dangerously-skip-permissions", job["name"])
    return [
        "claude",
        "-p",
        prompt,
        "--model",
        model,
        "--dangerously-skip-permissions",
        "--print",
    ]


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------


class Scheduler:
    """Core scheduler managing job execution, overlap prevention, and budget enforcement."""

    def __init__(self, config: dict[str, Any], config_path: Path) -> None:
        self.config = config
        self.config_path = config_path
        self._running_jobs: set[str] = set()
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._cron_thread: threading.Thread | None = None
        self._webhook_server: HTTPServer | None = None
        self._webhook_thread: threading.Thread | None = None
        self._file_watchers: list[Any] = []

    @property
    def daily_budget(self) -> float:
        return float(self.config.get("daily_budget_usd", 10.0))

    def _get_jobs_by_trigger(self, trigger_type: str) -> list[dict[str, Any]]:
        """Return enabled jobs matching the given trigger type."""
        return [j for j in self.config["jobs"] if j.get("enabled", True) and j["trigger"]["type"] == trigger_type]

    def execute_job(
        self,
        job: dict[str, Any],
        trigger_type: str,
        trigger_detail: str,
        extra_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute a single scheduled job.

        Returns the result dict, or None if the job was skipped.
        """
        name = job["name"]
        runner = job.get("runner", "claude")

        # Overlap prevention
        with self._lock:
            if name in self._running_jobs:
                log.warning("Skipping %s — previous run still active", name)
                return None
            self._running_jobs.add(name)

        try:
            # Daily model budget applies only to Claude jobs. Command jobs have
            # no token cost and should keep routine maintenance running.
            current_cost = get_daily_cost()
            if runner == "claude" and current_cost >= self.daily_budget:
                log.warning(
                    "Daily budget $%.2f reached (spent $%.2f). Skipping %s", self.daily_budget, current_cost, name
                )
                return None

            variables: dict[str, Any] = {"job": {"name": name, "description": job.get("description", "")}}
            if extra_vars:
                variables.update(extra_vars)

            model = job.get("model", "sonnet")
            timeout = job.get("timeout_seconds", 120)

            if runner == "command":
                cmd = build_command_job_command(job, variables)
                model = "command"
            else:
                prompt = render_prompt(job["prompt"], variables)
                cmd = build_claude_job_command(job, prompt, model)

            log.info("Executing job=%s runner=%s model=%s trigger=%s", name, runner, model, trigger_type)
            started_at = datetime.now(timezone.utc).isoformat()
            start_time = time.monotonic()

            workdir = Path(job.get("workdir", str(_REPO_ROOT))).expanduser()
            if not workdir.is_absolute():
                workdir = _REPO_ROOT / workdir

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(workdir))
                exit_code = result.returncode
                stdout = result.stdout
                stderr = result.stderr
            except subprocess.TimeoutExpired:
                exit_code = 124
                stdout = ""
                stderr = f"Job timed out after {timeout}s"
                log.error("Job %s timed out after %ds", name, timeout)
            except FileNotFoundError:
                exit_code = 127
                stdout = ""
                stderr = f"{cmd[0]} not found in PATH"
                log.error("%s not found — cannot execute job %s", cmd[0], name)
            except Exception as exc:
                exit_code = 1
                stdout = ""
                stderr = str(exc)
                log.error("Job %s failed: %s", name, exc)

            duration = time.monotonic() - start_time
            finished_at = datetime.now(timezone.utc).isoformat()
            cost = 0.0 if runner == "command" else estimate_cost(model, stdout)

            # Per-job cost limit check (flag, not prevent — run already completed)
            cost_limit = job.get("cost_limit_usd", 1.0)
            if cost > cost_limit:
                log.warning("Job %s cost $%.4f exceeds limit $%.2f", name, cost, cost_limit)

            record_result(
                job_name=name,
                trigger_type=trigger_type,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                stdout=stdout[:50000],  # Cap stored output at 50KB
                stderr=stderr[:10000],
                model=model,
                duration_seconds=round(duration, 2),
                cost_estimate_usd=cost,
                trigger_detail=trigger_detail,
            )

            status = "OK" if exit_code == 0 else "FAIL"
            log.info("Job %s finished: %s exit=%d duration=%.1fs cost=$%.4f", name, status, exit_code, duration, cost)

            return {
                "job_name": name,
                "exit_code": exit_code,
                "duration_seconds": round(duration, 2),
                "cost_estimate_usd": cost,
            }
        finally:
            with self._lock:
                self._running_jobs.discard(name)

    # --- Cron scheduling ---

    def _cron_matches(self, expression: str, now: datetime) -> bool:
        """Check if a cron expression matches the given datetime.

        Supports standard 5-field cron: minute hour day_of_month month day_of_week.
        Supports: *, */N, N, N-M, and comma-separated values.
        """
        fields = expression.strip().split()
        if len(fields) != 5:
            return False

        checks = [
            (fields[0], now.minute, 0),
            (fields[1], now.hour, 0),
            (fields[2], now.day, 1),
            (fields[3], now.month, 1),
            (fields[4], now.isoweekday() % 7, 0),  # Sunday = 0
        ]

        return all(self._field_matches(field, current, low) for field, current, low in checks)

    @staticmethod
    def _field_matches(field: str, value: int, low: int) -> bool:
        """Check if a single cron field matches the given value."""
        for part in field.split(","):
            if part == "*":
                return True
            if "/" in part:
                base, step_str = part.split("/", 1)
                step = int(step_str)
                start = low if base == "*" else int(base)
                if value >= start and (value - start) % step == 0:
                    return True
            elif "-" in part:
                range_start, range_end = part.split("-", 1)
                if int(range_start) <= value <= int(range_end):
                    return True
            else:
                if value == int(part):
                    return True
        return False

    def _cron_loop(self) -> None:
        """Main cron loop — checks every 30 seconds, fires on minute boundaries."""
        last_fire_minute: str = ""
        while not self._shutdown.is_set():
            now = datetime.now(timezone.utc)
            minute_key = now.strftime("%Y-%m-%d %H:%M")

            if minute_key != last_fire_minute:
                last_fire_minute = minute_key
                for job in self._get_jobs_by_trigger("cron"):
                    schedule = job["trigger"].get("schedule", "")
                    if self._cron_matches(schedule, now):
                        threading.Thread(
                            target=self.execute_job,
                            args=(job, "cron", schedule),
                            daemon=True,
                            name=f"job-{job['name']}",
                        ).start()

            self._shutdown.wait(timeout=30)

    def start_cron(self) -> None:
        """Start the cron scheduler thread."""
        cron_jobs = self._get_jobs_by_trigger("cron")
        if not cron_jobs:
            log.info("No cron jobs configured")
            return
        log.info("Starting cron scheduler with %d jobs", len(cron_jobs))
        self._cron_thread = threading.Thread(target=self._cron_loop, daemon=True, name="cron-scheduler")
        self._cron_thread.start()

    # --- Webhook server ---

    def _create_webhook_handler(self) -> type[BaseHTTPRequestHandler]:
        """Create an HTTP request handler class with access to the scheduler."""
        scheduler = self

        class WebhookHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                log.debug("HTTP %s", format % args)

            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length > 0 else b""

                # Find matching webhook jobs
                matched_jobs = [
                    j for j in scheduler._get_jobs_by_trigger("webhook") if j["trigger"].get("path") == self.path
                ]

                if not matched_jobs:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'{"error": "no matching webhook job"}')
                    return

                # Require webhook authentication. When GITHUB_WEBHOOK_SECRET is not
                # set, all POST requests are rejected with 403. To enable webhook
                # processing, set the GITHUB_WEBHOOK_SECRET environment variable.
                webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
                if not webhook_secret:
                    log.warning(
                        "Rejected unauthenticated webhook POST to %s (GITHUB_WEBHOOK_SECRET not set)", self.path
                    )
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        b'{"error": "webhook authentication required", '
                        b'"fix": "set GITHUB_WEBHOOK_SECRET environment variable"}'
                    )
                    return

                signature = self.headers.get("X-Hub-Signature-256", "")
                expected = "sha256=" + hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, expected):
                    log.warning("Webhook signature mismatch on %s", self.path)
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b'{"error": "invalid signature"}')
                    return

                # Parse payload
                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    payload = {}

                # Filter by event type
                event = self.headers.get("X-GitHub-Event", "")

                triggered = 0
                for job in matched_jobs:
                    job_filter = job["trigger"].get("filter", {})
                    if job_filter:
                        if job_filter.get("event") and event != job_filter["event"]:
                            continue
                        allowed_actions = job_filter.get("action", [])
                        if allowed_actions and payload.get("action") not in allowed_actions:
                            continue

                    threading.Thread(
                        target=scheduler.execute_job,
                        args=(job, "webhook", self.path, {"payload": payload}),
                        daemon=True,
                        name=f"job-{job['name']}",
                    ).start()
                    triggered += 1

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"triggered": triggered}).encode())

            def do_GET(self) -> None:
                """Health check endpoint."""
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    status = {
                        "status": "running",
                        "jobs": len(scheduler.config.get("jobs", [])),
                        "daily_cost": get_daily_cost(),
                        "daily_budget": scheduler.daily_budget,
                    }
                    self.wfile.write(json.dumps(status).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

        return WebhookHandler

    def start_webhook_server(self) -> None:
        """Start the webhook HTTP server in a background thread."""
        webhook_jobs = self._get_jobs_by_trigger("webhook")
        if not webhook_jobs:
            log.info("No webhook jobs configured — skipping HTTP server")
            return

        port = int(self.config.get("webhook_port", 9100))
        handler_cls = self._create_webhook_handler()

        # webhook_bind defaults to 127.0.0.1 (localhost-only). Set to "0.0.0.0"
        # in schedules.json if you need external access (e.g. behind a reverse proxy).
        bind_address = self.config.get("webhook_bind", "127.0.0.1")

        webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        if not webhook_secret:
            log.warning(
                "GITHUB_WEBHOOK_SECRET not set — all webhook POST requests will be rejected (403). "
                "Set the env var to enable webhook processing."
            )

        try:
            self._webhook_server = HTTPServer((bind_address, port), handler_cls)
        except OSError as exc:
            log.error("Cannot bind webhook port %d: %s", port, exc)
            return

        log.info("Webhook server listening on %s:%d (%d jobs)", bind_address, port, len(webhook_jobs))
        self._webhook_thread = threading.Thread(
            target=self._webhook_server.serve_forever, daemon=True, name="webhook-server"
        )
        self._webhook_thread.start()

    # --- File watcher ---

    def start_file_watchers(self) -> None:
        """Start filesystem watchers for file_watch trigger jobs.

        Uses polling-based file watching (stdlib only, no watchdog dependency).
        Checks every 5 seconds for new/modified files matching the configured pattern.
        """
        file_jobs = self._get_jobs_by_trigger("file_watch")
        if not file_jobs:
            log.info("No file_watch jobs configured")
            return

        for job in file_jobs:
            trigger = job["trigger"]
            directory = Path(trigger["directory"])
            pattern = trigger.get("pattern", "*")
            event_type = trigger.get("event", "created")

            if not directory.exists():
                log.warning("Watch directory does not exist: %s (job=%s)", directory, job["name"])
                continue

            thread = threading.Thread(
                target=self._file_watch_loop,
                args=(job, directory, pattern, event_type),
                daemon=True,
                name=f"file-watch-{job['name']}",
            )
            thread.start()
            self._file_watchers.append(thread)
            log.info("Watching %s/%s for '%s' events (job=%s)", directory, pattern, event_type, job["name"])

    def _file_watch_loop(self, job: dict[str, Any], directory: Path, pattern: str, event_type: str) -> None:
        """Poll a directory for file changes. 5-second debounce."""
        import fnmatch

        known_files: dict[str, float] = {}
        # Snapshot existing files on startup
        for f in directory.iterdir():
            if f.is_file() and fnmatch.fnmatch(f.name, pattern):
                known_files[str(f)] = f.stat().st_mtime

        debounce: dict[str, float] = {}

        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=5)
            if self._shutdown.is_set():
                break

            current_files: dict[str, float] = {}
            try:
                for f in directory.iterdir():
                    if f.is_file() and fnmatch.fnmatch(f.name, pattern):
                        current_files[str(f)] = f.stat().st_mtime
            except OSError:
                continue

            triggered_paths: list[str] = []

            if event_type == "created":
                for fpath in current_files:
                    if fpath not in known_files:
                        triggered_paths.append(fpath)
            elif event_type == "modified":
                for fpath, mtime in current_files.items():
                    if fpath in known_files and mtime > known_files[fpath]:
                        triggered_paths.append(fpath)

            for fpath in triggered_paths:
                now = time.monotonic()
                if fpath in debounce and (now - debounce[fpath]) < 5.0:
                    continue  # Within debounce window
                debounce[fpath] = now
                threading.Thread(
                    target=self.execute_job,
                    args=(job, "file_watch", fpath, {"file_path": fpath}),
                    daemon=True,
                    name=f"job-{job['name']}",
                ).start()

            known_files = current_files

    # --- Lifecycle ---

    def reload_config(self) -> None:
        """Reload configuration from disk (triggered by SIGHUP)."""
        log.info("Reloading configuration from %s", self.config_path)
        try:
            new_config = load_config(self.config_path)
            self.config = new_config
            log.info("Configuration reloaded: %d jobs", len(new_config["jobs"]))
        except SystemExit:
            log.error("Config reload failed — keeping previous configuration")

    def shutdown(self) -> None:
        """Graceful shutdown."""
        log.info("Shutting down scheduler")
        self._shutdown.set()
        if self._webhook_server:
            self._webhook_server.shutdown()
        _PID_FILE.unlink(missing_ok=True)

    def run(self) -> None:
        """Start all components and block until shutdown signal."""
        # Write PID file
        _PID_FILE.write_text(str(os.getpid()))

        init_db()
        self.start_cron()
        self.start_webhook_server()
        self.start_file_watchers()

        log.info("Scheduler running (pid=%d). Waiting for signals...", os.getpid())

        # Block until shutdown
        try:
            while not self._shutdown.is_set():
                self._shutdown.wait(timeout=60)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

_scheduler_instance: Scheduler | None = None


def _handle_sighup(_signum: int, _frame: Any) -> None:
    if _scheduler_instance:
        _scheduler_instance.reload_config()


def _handle_sigterm(_signum: int, _frame: Any) -> None:
    if _scheduler_instance:
        _scheduler_instance.shutdown()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the agent scheduler daemon."""
    global _scheduler_instance

    parser = argparse.ArgumentParser(description="Agent Scheduler Daemon")
    parser.add_argument("--config", "-c", type=Path, default=_DEFAULT_CONFIG, help="Path to schedules.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and exit")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )

    config = load_config(args.config)

    if args.dry_run:
        log.info("Config OK: %d jobs defined", len(config["jobs"]))
        for job in config["jobs"]:
            status = "enabled" if job.get("enabled", True) else "disabled"
            log.info(
                "  %-25s %-10s trigger=%s runner=%s model=%s",
                job["name"],
                status,
                job["trigger"]["type"],
                job["runner"],
                job["model"],
            )
        return 0

    # Check for existing instance
    if _PID_FILE.exists():
        old_pid = _PID_FILE.read_text().strip()
        try:
            os.kill(int(old_pid), 0)
            log.error("Scheduler already running (pid=%s). Use scheduler-ctl.py reload.", old_pid)
            return 1
        except (ProcessLookupError, ValueError):
            _PID_FILE.unlink(missing_ok=True)

    _scheduler_instance = Scheduler(config, args.config)

    signal.signal(signal.SIGHUP, _handle_sighup)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    _scheduler_instance.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
