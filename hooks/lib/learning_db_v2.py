#!/usr/bin/env python3
"""
Learning Database v2 — Unified cross-session knowledge store.

Replaces both patterns.db (error-learner) and retro L2 markdown files
with a single SQLite database at ~/.claude/learning/learning.db.

All hooks and scripts use this interface to record and query learnings.
Designed for <50ms query performance with indexed columns.

Design Principles:
- Single source of truth for all learned knowledge
- Record liberally, inject conservatively (confidence thresholds)
- Automatic table creation and migration
- WAL mode for concurrent session reads
- Graceful degradation on errors
"""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── Configuration ─────────────────────────────────────────────

_DEFAULT_DB_DIR = Path.home() / ".claude" / "learning"

_CURRENT_SCHEMA_VERSION = 7

CATEGORY_DEFAULTS = {
    "error": 0.55,
    "pivot": 0.60,
    "review": 0.70,
    "design": 0.65,
    "debug": 0.60,
    "gotcha": 0.70,
    "effectiveness": 0.50,
    "misroute": 0.80,
}

VALID_CATEGORIES = set(CATEGORY_DEFAULTS.keys())

# Carried over from learning_db.py for backward compatibility
ERROR_TYPES = {
    "missing_file": [
        r"no such file",
        r"file not found",
        r"cannot find",
        r"does not exist",
    ],
    "permissions": [r"permission denied", r"access denied", r"not permitted"],
    "syntax_error": [r"syntax ?error", r"unexpected token", r"parse error"],
    "type_error": [r"type error", r"cannot convert", r"incompatible type"],
    "import_error": [r"import error", r"module not found", r"no module named"],
    "timeout": [r"timeout", r"timed out", r"deadline exceeded"],
    "connection": [r"connection refused", r"network error", r"unreachable"],
    "memory": [r"out of memory", r"memory error", r"heap"],
    "multiple_matches": [r"multiple matches", r"found \d+ matches", r"replace_all"],
}

DEFAULT_FIX_ACTIONS = {
    "missing_file": {"fix_type": "auto", "fix_action": "create_file"},
    "permissions": {"fix_type": "manual", "fix_action": "check_permissions"},
    # systematic-debugging is a workflow pipeline, not an invocable skill.
    "syntax_error": {"fix_type": "skill", "fix_action": "workflow"},
    "type_error": {"fix_type": "skill", "fix_action": "workflow"},
    "import_error": {"fix_type": "auto", "fix_action": "install_module"},
    "timeout": {"fix_type": "auto", "fix_action": "retry_with_timeout"},
    "connection": {"fix_type": "auto", "fix_action": "retry"},
    "memory": {"fix_type": "manual", "fix_action": "reduce_memory"},
    "multiple_matches": {"fix_type": "auto", "fix_action": "use_replace_all"},
}


# ─── Database Connection ───────────────────────────────────────


def get_db_dir() -> Path:
    """Return the learning database directory, honoring CLAUDE_LEARNING_DIR.

    Public API for callers that need the directory path (e.g. to locate
    sibling files like route-events.jsonl). Keeps ADR-122 chmod hardening
    in get_db_path() which calls this.
    """
    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_DB_DIR


def get_db_path() -> Path:
    db_dir = get_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    # Harden directory permissions (ADR-122)
    try:
        os.chmod(db_dir, 0o700)
    except OSError:
        pass
    return db_dir / "learning.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path(), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


_initialized = False


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run pending schema migrations based on PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]

    if current < 1:
        # v0 -> v1: Initial version tracking
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (1, 'initial version tracking')"
        )

    if current < 2:
        # v1 -> v2: Add graduation_proposed_at column (moved from knowledge-graduation-proposer.py)
        try:
            conn.execute("ALTER TABLE learnings ADD COLUMN graduation_proposed_at TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists from old ad-hoc migration
        conn.execute("PRAGMA user_version = 2")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (2, 'add graduation_proposed_at column to learnings')"
        )

    if current < 3:
        # v2 -> v3: Add performance indexes for timestamp range queries and ROI cohort scans
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_learnings_last_seen ON learnings(last_seen)",
            "CREATE INDEX IF NOT EXISTS idx_learnings_first_seen ON learnings(first_seen)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time)",
            "CREATE INDEX IF NOT EXISTS idx_activations_timestamp ON activations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_session_stats_had_retro ON session_stats(had_retro_knowledge)",
            "CREATE INDEX IF NOT EXISTS idx_session_stats_created_at ON session_stats(created_at)",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # Index already exists
        conn.execute("PRAGMA user_version = 3")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (3, 'add timestamp and cohort indexes for query performance')"
        )

    if current < 4:
        # v3 -> v4: Add instruction_compliance table for per-observation tracking
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS instruction_compliance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instruction_id TEXT NOT NULL,
                compliant BOOLEAN NOT NULL,
                session_id TEXT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ic_instruction_id ON instruction_compliance(instruction_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ic_timestamp ON instruction_compliance(timestamp)")
        conn.execute("PRAGMA user_version = 4")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (4, 'add instruction_compliance table for per-observation tracking')"
        )

    if current < 5:
        # v4 -> v5: append-only per-run telemetry envelope (ADR: learning-telemetry-envelope).
        # Same DDL a fresh DB gets from _SCHEMA; idempotent IF NOT EXISTS. Old rows untouched.
        conn.executescript(_TELEMETRY_DDL)
        conn.execute("PRAGMA user_version = 5")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (5, 'add telemetry_runs table for per-run envelope')"
        )

    if current < 6:
        # v5 -> v6: per-route outcome-basis counters (ADR: silent-failure-outcome-quality).
        # Same DDL a fresh DB gets from _SCHEMA; idempotent IF NOT EXISTS. Old rows untouched.
        conn.executescript(_BASIS_DDL)
        conn.execute("PRAGMA user_version = 6")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (6, 'add routing_outcome_basis table for outcome-basis counters')"
        )

    if current < 7:
        # v6 -> v7: local agent evidence read model for queryable sessions,
        # hook events, and route decisions. Additive and idempotent.
        conn.executescript(_EVIDENCE_DDL)
        conn.execute("PRAGMA user_version = 7")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (7, 'add agent evidence event and route decision tables')"
        )

    if current < 8:
        # v7 -> v8: carry the router's ` pipeline=<name>` marker token. The
        # column may already exist from an ad-hoc ALTER on a live DB; the
        # duplicate-column error is the expected no-op there.
        try:
            conn.execute("ALTER TABLE evidence_route_decisions ADD COLUMN pipeline TEXT")
        except sqlite3.OperationalError:
            pass  # column already present
        conn.execute("PRAGMA user_version = 8")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (8, 'add pipeline column to evidence_route_decisions')"
        )

    conn.commit()


def init_db():
    global _initialized
    if _initialized:
        return
    with get_connection() as conn:
        # Read version before migrations so _migrate_fts knows if triggers were active
        pre_migration_version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.executescript(_SCHEMA)
        _run_migrations(conn)
    _migrate_fts(pre_migration_version)
    # Harden DB file permissions after creation (ADR-122)
    try:
        os.chmod(get_db_path(), 0o600)
    except OSError:
        pass
    _initialized = True


def _migrate_fts(pre_migration_version: int = 0) -> None:
    """Rebuild the FTS5 inverted index from the learnings table.

    Called once from init_db() on each process start. The 'rebuild'
    command re-reads all content from the learnings table and
    reconstructs the inverted index. This is necessary for databases
    that predate the FTS5 schema -- the content-sync FTS5 table
    reports COUNT(*) from the content table even when the inverted
    index is empty, so we always rebuild on first init.

    Rebuild is idempotent and fast (<100ms for hundreds of rows).

    Args:
        pre_migration_version: The user_version before migrations ran. If >= 1,
            FTS triggers were active from table creation so the inverted index
            is already current and the expensive rebuild can be skipped.
    """
    if pre_migration_version >= 1:
        # Triggers have maintained the FTS index since the DB was first created
        return

    with get_connection() as conn:
        try:
            main_count = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        except sqlite3.OperationalError:
            return  # Table doesn't exist yet

        if main_count > 0:
            try:
                conn.execute("INSERT INTO learnings_fts(learnings_fts) VALUES('rebuild')")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # FTS table doesn't exist yet


# Append-only per-run telemetry envelope (schema v5). Defined standalone so the
# v4->v5 migration block can run the identical DDL an existing DB never got from
# _SCHEMA. A fresh DB gets the same table from _SCHEMA below; both are idempotent
# (IF NOT EXISTS). See ADR: learning-telemetry-envelope.
_TELEMETRY_DDL = """
CREATE TABLE IF NOT EXISTS telemetry_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    batch_id      TEXT,
    topic         TEXT NOT NULL,
    key           TEXT NOT NULL,
    session_id    TEXT,
    git_sha       TEXT,
    model_id      TEXT,
    skill_version TEXT,
    token_count   INTEGER,
    wall_clock_ms INTEGER,
    tool_errors   INTEGER DEFAULT 0,
    recorded_at   TEXT NOT NULL DEFAULT (datetime('now')),
    source        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_recorded_at ON telemetry_runs(recorded_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_git_sha ON telemetry_runs(git_sha);
CREATE INDEX IF NOT EXISTS idx_telemetry_topic_key ON telemetry_runs(topic, key);
CREATE INDEX IF NOT EXISTS idx_telemetry_batch ON telemetry_runs(batch_id);
"""


# Per-route outcome-basis counters (schema v6). Labels each finalized routing
# outcome by its evidence basis so route-health can report the silent-success
# share. Additive and idempotent; same DDL a fresh DB gets from _SCHEMA and the
# v5->v6 migration runs on an existing DB. See ADR: silent-failure-outcome-quality.
_BASIS_DDL = """
CREATE TABLE IF NOT EXISTS routing_outcome_basis (
    key   TEXT NOT NULL,
    basis TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, basis)
);
"""


_EVIDENCE_DDL = """
CREATE TABLE IF NOT EXISTS evidence_sessions (
    session_id    TEXT PRIMARY KEY,
    project_path  TEXT,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
    summary       TEXT
);

CREATE TABLE IF NOT EXISTS evidence_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      TEXT NOT NULL UNIQUE,
    session_id    TEXT,
    ts            TEXT NOT NULL DEFAULT (datetime('now')),
    event_type    TEXT NOT NULL,
    source        TEXT NOT NULL,
    agent         TEXT,
    skill         TEXT,
    tool_name     TEXT,
    route_key     TEXT,
    action        TEXT,
    target        TEXT,
    target_hash   TEXT,
    success       INTEGER,
    error         TEXT,
    model         TEXT,
    tokens        INTEGER,
    metadata      TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_events_ts ON evidence_events(ts);
CREATE INDEX IF NOT EXISTS idx_evidence_events_session ON evidence_events(session_id);
CREATE INDEX IF NOT EXISTS idx_evidence_events_type ON evidence_events(event_type);
CREATE INDEX IF NOT EXISTS idx_evidence_events_route ON evidence_events(route_key);
CREATE INDEX IF NOT EXISTS idx_evidence_events_agent_skill ON evidence_events(agent, skill);
CREATE INDEX IF NOT EXISTS idx_evidence_events_target_hash ON evidence_events(target_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_events_success ON evidence_events(success);

CREATE VIRTUAL TABLE IF NOT EXISTS evidence_events_fts USING fts5(
    event_type,
    source,
    agent,
    skill,
    tool_name,
    route_key,
    action,
    target,
    error,
    metadata,
    content='evidence_events',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS evidence_events_ai AFTER INSERT ON evidence_events BEGIN
    INSERT INTO evidence_events_fts(
        rowid, event_type, source, agent, skill, tool_name, route_key, action, target, error, metadata
    )
    VALUES (
        new.id, new.event_type, new.source, new.agent, new.skill, new.tool_name, new.route_key,
        new.action, new.target, new.error, new.metadata
    );
END;

CREATE TRIGGER IF NOT EXISTS evidence_events_ad AFTER DELETE ON evidence_events BEGIN
    INSERT INTO evidence_events_fts(
        evidence_events_fts, rowid, event_type, source, agent, skill, tool_name, route_key,
        action, target, error, metadata
    )
    VALUES (
        'delete', old.id, old.event_type, old.source, old.agent, old.skill, old.tool_name, old.route_key,
        old.action, old.target, old.error, old.metadata
    );
END;

CREATE TRIGGER IF NOT EXISTS evidence_events_au AFTER UPDATE ON evidence_events BEGIN
    INSERT INTO evidence_events_fts(
        evidence_events_fts, rowid, event_type, source, agent, skill, tool_name, route_key,
        action, target, error, metadata
    )
    VALUES (
        'delete', old.id, old.event_type, old.source, old.agent, old.skill, old.tool_name, old.route_key,
        old.action, old.target, old.error, old.metadata
    );
    INSERT INTO evidence_events_fts(
        rowid, event_type, source, agent, skill, tool_name, route_key, action, target, error, metadata
    )
    VALUES (
        new.id, new.event_type, new.source, new.agent, new.skill, new.tool_name, new.route_key,
        new.action, new.target, new.error, new.metadata
    );
END;

CREATE TABLE IF NOT EXISTS evidence_route_decisions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id          TEXT NOT NULL UNIQUE,
    session_id           TEXT,
    route_key            TEXT NOT NULL,
    agent                TEXT NOT NULL,
    skill                TEXT,
    complexity           TEXT,
    model                TEXT,
    action               TEXT,
    health               REAL,
    n                    INTEGER,
    failure              INTEGER DEFAULT 0,
    gate_inputs_present  INTEGER DEFAULT 0,
    outcome              TEXT,
    outcome_basis        TEXT,
    request_snippet      TEXT,
    stack                TEXT,
    pipeline             TEXT,
    alternates           TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_evidence_route_key ON evidence_route_decisions(route_key);
CREATE INDEX IF NOT EXISTS idx_evidence_route_session ON evidence_route_decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_evidence_route_created ON evidence_route_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_route_outcome ON evidence_route_decisions(outcome);
"""


_SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    tags TEXT,
    source TEXT NOT NULL,
    source_detail TEXT,
    project_path TEXT,
    session_id TEXT,
    observation_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    graduated_to TEXT,
    error_signature TEXT,
    error_type TEXT,
    fix_type TEXT,
    fix_action TEXT,
    UNIQUE(topic, key)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    start_time TEXT,
    end_time TEXT,
    project_path TEXT,
    files_modified INTEGER DEFAULT 0,
    tools_used INTEGER DEFAULT 0,
    errors_encountered INTEGER DEFAULT 0,
    errors_resolved INTEGER DEFAULT 0,
    learnings_captured INTEGER DEFAULT 0,
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_learnings_topic ON learnings(topic);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);
CREATE INDEX IF NOT EXISTS idx_learnings_confidence ON learnings(confidence);
CREATE INDEX IF NOT EXISTS idx_learnings_tags ON learnings(tags);
CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(project_path);
CREATE INDEX IF NOT EXISTS idx_learnings_graduated ON learnings(graduated_to);
CREATE INDEX IF NOT EXISTS idx_learnings_error_sig ON learnings(error_signature);
CREATE INDEX IF NOT EXISTS idx_learnings_last_seen ON learnings(last_seen);
CREATE INDEX IF NOT EXISTS idx_learnings_first_seen ON learnings(first_seen);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);

CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts USING fts5(
    topic,
    key,
    value,
    tags,
    content='learnings',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    session_id TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    outcome TEXT DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS session_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    had_retro_knowledge INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    waste_tokens INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_activations_topic_key ON activations(topic, key);
CREATE INDEX IF NOT EXISTS idx_activations_session ON activations(session_id);
CREATE INDEX IF NOT EXISTS idx_activations_timestamp ON activations(timestamp);
CREATE INDEX IF NOT EXISTS idx_session_stats_session ON session_stats(session_id);
CREATE INDEX IF NOT EXISTS idx_session_stats_had_retro ON session_stats(had_retro_knowledge);
CREATE INDEX IF NOT EXISTS idx_session_stats_created_at ON session_stats(created_at);

CREATE TRIGGER IF NOT EXISTS learnings_ai AFTER INSERT ON learnings BEGIN
    INSERT INTO learnings_fts(rowid, topic, key, value, tags)
    VALUES (new.id, new.topic, new.key, new.value, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS learnings_ad AFTER DELETE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, topic, key, value, tags)
    VALUES ('delete', old.id, old.topic, old.key, old.value, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS learnings_au AFTER UPDATE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, topic, key, value, tags)
    VALUES ('delete', old.id, old.topic, old.key, old.value, old.tags);
    INSERT INTO learnings_fts(rowid, topic, key, value, tags)
    VALUES (new.id, new.topic, new.key, new.value, new.tags);
END;

CREATE TABLE IF NOT EXISTS governance_events (
    id          TEXT PRIMARY KEY,
    session_id  TEXT,
    event_type  TEXT NOT NULL,
    tool_name   TEXT,
    hook_phase  TEXT,
    severity    TEXT,
    payload     TEXT,
    blocked     INTEGER DEFAULT 0,
    resolved_at TEXT,
    resolution  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gov_session   ON governance_events(session_id);
CREATE INDEX IF NOT EXISTS idx_gov_type      ON governance_events(event_type);
CREATE INDEX IF NOT EXISTS idx_gov_severity  ON governance_events(severity);
CREATE INDEX IF NOT EXISTS idx_gov_created   ON governance_events(created_at);

CREATE TABLE IF NOT EXISTS instruction_compliance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instruction_id TEXT NOT NULL,
    compliant BOOLEAN NOT NULL,
    session_id TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ic_instruction_id ON instruction_compliance(instruction_id);
CREATE INDEX IF NOT EXISTS idx_ic_timestamp ON instruction_compliance(timestamp);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);
"""
    + _TELEMETRY_DDL
    + _BASIS_DDL
    + _EVIDENCE_DDL
)


# ─── Injection Defense ────────────────────────────────────────


def sanitize_for_context(text: str) -> str:
    """Neutralize known injection patterns in text before agent context injection.

    Replaces role boundary tags and strips zero-width Unicode characters to prevent
    second-order prompt injection via stored learning database values.
    """
    if not text:
        return text
    # Neutralize role boundary tags (case-insensitive)
    for tag in ("system", "user", "assistant", "human"):
        text = re.sub(rf"<{tag}>", f"[{tag}]", text, flags=re.IGNORECASE)
        text = re.sub(rf"</{tag}>", f"[/{tag}]", text, flags=re.IGNORECASE)
    # Strip zero-width Unicode characters
    zero_width = "\u200b\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff"
    for ch in zero_width:
        text = text.replace(ch, "")
    return text


def sanitize_fts_query(term: str) -> str:
    """Strip FTS5 operators from a search term to prevent query injection.

    FTS5 operators (NOT, NEAR, AND, OR, *, quotes, parens, minus, colon) are removed
    to ensure terms are treated as plain text matches.
    """
    import re as _re

    # Remove FTS5 keyword operators FIRST (before special-char removal strips
    # adjacent parens and breaks word boundaries, e.g. "NEAR(a b)" -> "NEARa b").
    term = _re.sub(r"\b(NOT|NEAR|AND|OR)\b", "", term, flags=_re.IGNORECASE)
    # Remove FTS5 special characters
    term = _re.sub(r'["\(\)\*:\-\^\+]', "", term)
    return term.strip()


# ─── Error Classification (from learning_db.py) ───────────────


def classify_error(message: str) -> str:
    message_lower = message.lower()
    for error_type, patterns in ERROR_TYPES.items():
        if any(re.search(p, message_lower) for p in patterns):
            return error_type
    return "unknown"


def normalize_error(message: str) -> str:
    normalized = message.lower().strip()
    normalized = re.sub(r"[/\\][\w./\\-]+[/\\]", "", normalized)
    normalized = re.sub(r"line \d+", "line N", normalized)
    normalized = re.sub(r"0x[0-9a-f]+", "0xADDR", normalized)
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}", "TIMESTAMP", normalized)
    return normalized


def generate_signature(error_message: str, error_type: str) -> str:
    normalized = normalize_error(error_message)
    content = f"{error_type}:{normalized}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


# ─── Core API ──────────────────────────────────────────────────


def record_learning(
    topic: str,
    key: str,
    value: str,
    category: str,
    *,
    confidence: float | None = None,
    tags: list[str] | None = None,
    source: str = "manual",
    source_detail: str | None = None,
    project_path: str | None = None,
    session_id: str | None = None,
    error_signature: str | None = None,
    error_type: str | None = None,
    fix_type: str | None = None,
    fix_action: str | None = None,
) -> dict:
    """Record or update a learning entry.

    If topic+key exists: increment observation_count, update last_seen,
    keep higher confidence, update value only if new is longer.
    """
    init_db()
    now = datetime.now().isoformat()

    if confidence is None:
        confidence = CATEGORY_DEFAULTS.get(category, 0.5)

    tags_str = ",".join(tags) if tags else None

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO learnings
                (topic, key, value, category, confidence, tags,
                 source, source_detail, project_path, session_id,
                 first_seen, last_seen,
                 error_signature, error_type, fix_type, fix_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic, key) DO UPDATE SET
                value = CASE WHEN length(excluded.value) > length(value) THEN excluded.value ELSE value END,
                confidence = max(confidence, excluded.confidence),
                observation_count = observation_count + 1,
                last_seen = excluded.last_seen,
                source = excluded.source,
                source_detail = excluded.source_detail,
                tags = COALESCE(excluded.tags, tags),
                error_signature = COALESCE(excluded.error_signature, error_signature),
                error_type = COALESCE(excluded.error_type, error_type),
                fix_type = COALESCE(excluded.fix_type, fix_type),
                fix_action = COALESCE(excluded.fix_action, fix_action)
            """,
            (
                topic,
                key,
                value,
                category,
                confidence,
                tags_str,
                source,
                source_detail,
                project_path,
                session_id,
                now,
                now,
                error_signature,
                error_type,
                fix_type,
                fix_action,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT value, confidence, observation_count FROM learnings WHERE topic = ? AND key = ?",
            (topic, key),
        ).fetchone()
        is_new = row["observation_count"] == 1
        return {
            "topic": topic,
            "key": key,
            "value": row["value"],
            "category": category,
            "confidence": row["confidence"],
            "observation_count": row["observation_count"],
            "is_new": is_new,
        }


# ─── Rightsizing ROI accumulation (ADR: review-tier-roi) ──────
#
# The rightsizing:tier{N} row must yield a TRUE per-tier mean, not the last
# review's sample. record_learning's upsert keeps only the longest `value` and
# discards per-review numbers, so it cannot store a running mean. This function
# read-modify-writes running sums in the value envelope under one connection, so
# review-roi divides true sums by true counts. Findings-bearing and cost counts
# are tracked separately: a legacy (no-findings) review bumps `reviews` only,
# never the findings sums or denominator; a review with tokens "-" never enters
# the token sum. Atomic: SELECT + UPSERT share one connection and commit.

# Order is the stored value's field order; review-roi parses by name, not order.
_RIGHTSIZING_SUM_FIELDS = (
    "reviews",  # all banners at this tier (= observation_count)
    "sum_critical",
    "sum_high",
    "sum_medium",
    "n_findings",  # banners that carried findings= (findings denominator)
    "sum_tokens",
    "n_tokens",  # banners with a numeric tokens= (token denominator)
    "sum_wall_clock_s",
    "n_wall",  # banners with a numeric wall_clock_s=
)


def _parse_rightsizing_sums(value: str) -> dict[str, int]:
    """Read the running-sum envelope into ints; missing/non-numeric fields = 0."""
    sums = dict.fromkeys(_RIGHTSIZING_SUM_FIELDS, 0)
    for pair in (value or "").split(" | "):
        if ": " not in pair:
            continue
        k, v = pair.split(": ", 1)
        k = k.strip()
        if k in sums:
            try:
                sums[k] = int(float(v.strip()))
            except (ValueError, TypeError):
                pass
    return sums


def accumulate_rightsizing(
    tier: int,
    *,
    critical: int | None = None,
    high: int | None = None,
    medium: int | None = None,
    tokens: int | None = None,
    wall_clock_s: int | None = None,
    source: str = "hook:routing-decision-recorder",
    session_id: str | None = None,
    confidence: float | None = None,
) -> dict:
    """Add one rightsizing review to the tier's running sums. Atomic upsert.

    Pass None for an absent banner field. `critical/high/medium` are all-or-none:
    when all three are given it counts as a findings-bearing review (bumps
    n_findings and the severity sums); when all three are None it is a legacy
    composition-only review (bumps `reviews` alone). `tokens` / `wall_clock_s`
    each enter their own sum and denominator only when numeric.

    The stored `value` always reflects the new sums (written directly, not via
    record_learning's longest-value merge). observation_count = reviews at tier.
    """
    init_db()
    now = datetime.now().isoformat()
    if confidence is None:
        confidence = CATEGORY_DEFAULTS.get("effectiveness", 0.5)

    key = f"rightsizing:tier{int(tier)}"
    has_findings = critical is not None and high is not None and medium is not None
    has_tokens = tokens is not None
    has_wall = wall_clock_s is not None

    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM learnings WHERE topic = 'routing' AND key = ?",
            (key,),
        ).fetchone()
        sums = _parse_rightsizing_sums(row["value"]) if row else dict.fromkeys(_RIGHTSIZING_SUM_FIELDS, 0)

        sums["reviews"] += 1
        if has_findings:
            sums["sum_critical"] += int(critical)
            sums["sum_high"] += int(high)
            sums["sum_medium"] += int(medium)
            sums["n_findings"] += 1
        if has_tokens:
            sums["sum_tokens"] += int(tokens)
            sums["n_tokens"] += 1
        if has_wall:
            sums["sum_wall_clock_s"] += int(wall_clock_s)
            sums["n_wall"] += 1

        value = f"tier: {int(tier)} | " + " | ".join(f"{f}: {sums[f]}" for f in _RIGHTSIZING_SUM_FIELDS)
        tags_str = ",".join(["routing", "rightsizing", f"tier{int(tier)}"])

        conn.execute(
            """
            INSERT INTO learnings
                (topic, key, value, category, confidence, tags,
                 source, session_id, first_seen, last_seen)
            VALUES ('routing', ?, ?, 'effectiveness', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic, key) DO UPDATE SET
                value = excluded.value,
                confidence = max(confidence, excluded.confidence),
                observation_count = observation_count + 1,
                last_seen = excluded.last_seen,
                source = excluded.source,
                tags = COALESCE(excluded.tags, tags)
            """,
            (key, value, confidence, tags_str, source, session_id, now, now),
        )
        conn.commit()

        out = conn.execute(
            "SELECT value, observation_count FROM learnings WHERE topic = 'routing' AND key = ?",
            (key,),
        ).fetchone()
        return {"key": key, "value": out["value"], "observation_count": out["observation_count"]}


def record_telemetry_run(
    *,
    topic: str,
    key: str,
    run_id: str,
    source: str,
    batch_id: str | None = None,
    session_id: str | None = None,
    git_sha: str | None = None,
    model_id: str | None = None,
    skill_version: str | None = None,
    token_count: int | None = None,
    wall_clock_ms: int | None = None,
    tool_errors: bool = False,
) -> None:
    """Append one per-run telemetry envelope row. Pure INSERT, never upsert.

    Best-effort fields stay NULL when the caller has no value (ADR:
    learning-telemetry-envelope). NULL is the honest value — it is never
    coerced to 0, so a query that averages tokens can report its true n.
    """
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO telemetry_runs (run_id, batch_id, topic, key, session_id, "
            "git_sha, model_id, skill_version, token_count, wall_clock_ms, tool_errors, source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                batch_id,
                topic,
                key,
                session_id,
                git_sha,
                model_id,
                skill_version,
                token_count,
                wall_clock_ms,
                1 if tool_errors else 0,
                source,
            ),
        )
        conn.commit()


def _bounded_text(value: object, limit: int = 2000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _json_text(value: object) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        return json.dumps(str(value))


def _parse_json_text(value: str | None) -> object:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _target_hash(target: str | None) -> str | None:
    if not target:
        return None
    return hashlib.sha256(target.encode("utf-8", errors="replace")).hexdigest()[:24]


def _route_key(agent: str, skill: str | None = None) -> str:
    clean_agent = (agent or "").strip()
    clean_skill = (skill or "").strip()
    return f"{clean_agent}:{clean_skill}" if clean_skill else f"{clean_agent}:"


def _event_id(*parts: object) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _event_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["success"] = _bool_or_none(data.get("success"))
    data["metadata"] = _parse_json_text(data.get("metadata")) or {}
    return data


def _record_evidence_session(conn: sqlite3.Connection, session_id: str | None, project_path: str | None = None) -> None:
    if not session_id:
        return
    conn.execute(
        """
        INSERT INTO evidence_sessions (session_id, project_path, started_at, last_seen_at)
        VALUES (?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(session_id) DO UPDATE SET
            project_path = COALESCE(excluded.project_path, evidence_sessions.project_path),
            last_seen_at = datetime('now')
        """,
        (session_id, project_path),
    )


def record_evidence_event(
    *,
    event_type: str,
    source: str,
    session_id: str | None = None,
    project_path: str | None = None,
    agent: str | None = None,
    skill: str | None = None,
    tool_name: str | None = None,
    route_key: str | None = None,
    action: str | None = None,
    target: str | None = None,
    success: bool | None = None,
    error: str | None = None,
    model: str | None = None,
    tokens: int | None = None,
    metadata: dict | list | str | None = None,
    event_id: str | None = None,
    ts: str | None = None,
) -> dict:
    """Record a queryable agent evidence event and return the inserted row."""
    init_db()
    event_type = _bounded_text(event_type, 120) or "event"
    source = _bounded_text(source, 160) or "unknown"
    session_id = _bounded_text(session_id, 160)
    project_path = _bounded_text(project_path, 1000)
    agent = _bounded_text(agent, 160)
    skill = _bounded_text(skill, 160)
    tool_name = _bounded_text(tool_name, 160)
    route_key = _bounded_text(route_key, 320)
    action = _bounded_text(action, 160)
    target = _bounded_text(target, 1000)
    error = _bounded_text(error, 2000)
    model = _bounded_text(model, 160)
    metadata_text = _bounded_text(_json_text(metadata), 4000)
    target_hash = _target_hash(target)
    ts = _bounded_text(ts, 80)
    event_id = _bounded_text(
        event_id
        or _event_id(
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            event_type,
            source,
            session_id,
            agent,
            skill,
            tool_name,
            route_key,
            action,
            target_hash,
        ),
        160,
    )

    with get_connection() as conn:
        _record_evidence_session(conn, session_id, project_path)
        conn.execute(
            """
            INSERT INTO evidence_events (
                event_id, session_id, ts, event_type, source, agent, skill, tool_name,
                route_key, action, target, target_hash, success, error, model, tokens, metadata
            )
            VALUES (?, ?, COALESCE(?, datetime('now')), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                session_id = excluded.session_id,
                ts = excluded.ts,
                event_type = excluded.event_type,
                source = excluded.source,
                agent = excluded.agent,
                skill = excluded.skill,
                tool_name = excluded.tool_name,
                route_key = excluded.route_key,
                action = excluded.action,
                target = excluded.target,
                target_hash = excluded.target_hash,
                success = excluded.success,
                error = excluded.error,
                model = excluded.model,
                tokens = excluded.tokens,
                metadata = excluded.metadata
            """,
            (
                event_id,
                session_id,
                ts,
                event_type,
                source,
                agent,
                skill,
                tool_name,
                route_key,
                action,
                target,
                target_hash,
                None if success is None else int(bool(success)),
                error,
                model,
                tokens,
                metadata_text,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM evidence_events WHERE event_id = ?", (event_id,)).fetchone()
        return _event_row(row)


def record_evidence_route_decision(
    *,
    session_id: str | None,
    agent: str,
    skill: str | None = None,
    complexity: str | None = None,
    model: str | None = None,
    request_snippet: str | None = None,
    stack: list[str] | tuple[str, ...] | str | None = None,
    pipeline: str | None = None,
    health: float | None = None,
    n: int | None = None,
    failure: bool | None = None,
    action: str | None = None,
    alternates: list[str] | tuple[str, ...] | str | None = None,
    gate_inputs_present: bool = False,
    decision_id: str | None = None,
    outcome: str | None = None,
    outcome_basis: str | None = None,
) -> dict:
    """Record a route decision plus a companion evidence event."""
    init_db()
    agent = _bounded_text(agent, 160) or "unknown"
    skill = _bounded_text(skill, 160)
    route_key = _route_key(agent, skill)
    session_id = _bounded_text(session_id, 160)
    decision_id = _bounded_text(
        decision_id
        or _event_id(
            datetime.now(timezone.utc).isoformat(timespec="microseconds"), session_id, route_key, request_snippet
        ),
        160,
    )
    stack_text = _bounded_text(_json_text(stack), 2000)
    alternates_text = _bounded_text(_json_text(alternates), 2000)

    with get_connection() as conn:
        _record_evidence_session(conn, session_id)
        conn.execute(
            """
            INSERT INTO evidence_route_decisions (
                decision_id, session_id, route_key, agent, skill, complexity, model, action,
                health, n, failure, gate_inputs_present, outcome, outcome_basis,
                request_snippet, stack, pipeline, alternates, created_at, updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now')
            )
            ON CONFLICT(decision_id) DO UPDATE SET
                session_id = excluded.session_id,
                route_key = excluded.route_key,
                agent = excluded.agent,
                skill = excluded.skill,
                complexity = excluded.complexity,
                model = excluded.model,
                action = excluded.action,
                health = excluded.health,
                n = excluded.n,
                failure = excluded.failure,
                gate_inputs_present = excluded.gate_inputs_present,
                outcome = excluded.outcome,
                outcome_basis = excluded.outcome_basis,
                request_snippet = excluded.request_snippet,
                stack = excluded.stack,
                pipeline = excluded.pipeline,
                alternates = excluded.alternates,
                updated_at = datetime('now')
            """,
            (
                decision_id,
                session_id,
                route_key,
                agent,
                skill,
                _bounded_text(complexity, 80),
                _bounded_text(model, 160),
                _bounded_text(action, 80),
                health,
                n,
                None if failure is None else int(bool(failure)),
                int(bool(gate_inputs_present)),
                _bounded_text(outcome, 80),
                _bounded_text(outcome_basis, 120),
                _bounded_text(request_snippet, 1000),
                stack_text,
                _bounded_text(pipeline, 160),
                alternates_text,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM evidence_route_decisions WHERE decision_id = ?", (decision_id,)).fetchone()

    record_evidence_event(
        event_type="route_decision",
        source="hook:routing",
        session_id=session_id,
        agent=agent,
        skill=skill,
        route_key=route_key,
        action=action,
        success=None if failure is None else not bool(failure),
        model=model,
        metadata={
            "complexity": complexity,
            "health": health,
            "n": n,
            "gate_inputs_present": gate_inputs_present,
            "stack": stack,
            "outcome": outcome,
            "outcome_basis": outcome_basis,
        },
        event_id=f"route:{decision_id}",
    )
    data = dict(row)
    data["failure"] = _bool_or_none(data.get("failure"))
    data["gate_inputs_present"] = bool(data.get("gate_inputs_present"))
    data["stack"] = _parse_json_text(data.get("stack")) or []
    data["alternates"] = _parse_json_text(data.get("alternates")) or []
    return data


def update_evidence_route_outcome(
    *,
    route_key: str,
    session_id: str | None = None,
    outcome: str,
    outcome_basis: str | None = None,
) -> None:
    """Attach the latest outcome to the newest matching route decision."""
    init_db()
    clauses = ["route_key = ?"]
    params: list = [route_key]
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    where = " AND ".join(clauses)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT decision_id FROM evidence_route_decisions WHERE {where} ORDER BY id DESC LIMIT 1",  # security-review: ignore (fixed clauses; user values bound as ?)
            params,
        ).fetchone()
        if not row:
            return
        conn.execute(
            """
            UPDATE evidence_route_decisions
            SET outcome = ?, outcome_basis = ?, updated_at = datetime('now')
            WHERE decision_id = ?
            """,
            (_bounded_text(outcome, 80), _bounded_text(outcome_basis, 120), row["decision_id"]),
        )
        conn.commit()


def list_evidence_events(
    *,
    limit: int = 50,
    session_id: str | None = None,
    event_type: str | None = None,
    route_key: str | None = None,
    agent: str | None = None,
    skill: str | None = None,
    target: str | None = None,
    failures_only: bool = False,
) -> list[dict]:
    init_db()
    clauses: list[str] = []
    params: list = []
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if route_key:
        clauses.append("route_key = ?")
        params.append(route_key)
    if agent:
        clauses.append("agent = ?")
        params.append(agent)
    if skill:
        clauses.append("skill = ?")
        params.append(skill)
    if target:
        clauses.append("(target_hash = ? OR target LIKE ?)")
        params.extend([_target_hash(target), f"%{target}%"])
    if failures_only:
        clauses.append("success = 0")
    joined_clauses = " AND ".join(clauses)
    where = ("WHERE " + joined_clauses) if clauses else ""  # security-review: ignore (fixed clauses; pre-existing)
    params.append(max(1, min(int(limit), 500)))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM evidence_events {where} ORDER BY id DESC LIMIT ?",  # security-review: ignore (fixed clauses; user values bound as ?)
            params,
        ).fetchall()
    return [_event_row(row) for row in rows]


def get_evidence_failures(
    *,
    limit: int = 50,
    route_key: str | None = None,
    agent: str | None = None,
    skill: str | None = None,
) -> list[dict]:
    return list_evidence_events(
        limit=limit,
        route_key=route_key,
        agent=agent,
        skill=skill,
        failures_only=True,
    )


def get_evidence_file_history(target: str, *, limit: int = 50) -> list[dict]:
    return list_evidence_events(limit=limit, target=target)


def _decision_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["failure"] = _bool_or_none(data.get("failure"))
    data["gate_inputs_present"] = bool(data.get("gate_inputs_present"))
    data["stack"] = _parse_json_text(data.get("stack")) or []
    data["alternates"] = _parse_json_text(data.get("alternates")) or []
    return data


def get_evidence_route_context(route_key: str, *, limit: int = 20) -> dict:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM evidence_route_decisions
            WHERE route_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (route_key, max(1, min(int(limit), 200))),
        ).fetchall()
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS decisions,
                COALESCE(SUM(CASE WHEN failure = 1 OR outcome = 'failure' THEN 1 ELSE 0 END), 0) AS failures,
                COALESCE(SUM(CASE WHEN outcome IN ('success', 'weak_success') THEN 1 ELSE 0 END), 0) AS successes,
                MAX(updated_at) AS last_seen
            FROM evidence_route_decisions
            WHERE route_key = ?
            """,
            (route_key,),
        ).fetchone()
    total_data = dict(totals)
    return {
        "route_key": route_key,
        "totals": total_data,
        "recent": [_decision_row(row) for row in rows],
        "failures": get_evidence_failures(route_key=route_key, limit=limit),
    }


def get_evidence_decision(route_key: str) -> dict:
    context = get_evidence_route_context(route_key, limit=10)
    totals = context["totals"]
    decisions = int(totals.get("decisions") or 0)
    failures = int(totals.get("failures") or 0)
    successes = int(totals.get("successes") or 0)
    if decisions == 0:
        return {
            "route_key": route_key,
            "recommendation": "no_data",
            "confidence": "none",
            "reasons": ["No local evidence has been recorded for this route."],
            "context": context,
        }

    failure_rate = failures / decisions
    reasons = [
        f"{decisions} recorded decision(s)",
        f"{failure_rate:.0%} failure rate",
    ]
    if successes:
        reasons.append(f"{successes} successful outcome(s)")

    if failure_rate > 0.65:
        recommendation = "investigate"
        confidence = "medium" if decisions >= 3 else "low"
    elif failure_rate >= 0.25:
        recommendation = "watch"
        confidence = "medium" if decisions >= 4 else "low"
    else:
        recommendation = "keep"
        confidence = "medium" if decisions >= 3 else "low"

    return {
        "route_key": route_key,
        "recommendation": recommendation,
        "confidence": confidence,
        "reasons": reasons,
        "context": context,
    }


def query_learnings(
    *,
    topic: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    min_confidence: float = 0.0,
    project_path: str | None = None,
    session_id: str | None = None,
    exclude_graduated: bool = True,
    exclude_test_sources: bool = True,
    order_by: str = "confidence DESC",
    limit: int = 50,
) -> list[dict]:
    """Query learnings with filtering and ordering.

    Args:
        topic: Filter by topic prefix.
        category: Filter by category.
        tags: Filter by tags (matches ANY).
        min_confidence: Minimum confidence threshold.
        project_path: Filter by project path (NULL or exact match).
        session_id: Filter by session id.
        exclude_graduated: If True, omit entries with a graduation target.
        exclude_test_sources: If True (default), omit entries where source
            starts with 'test'. This prevents test fixtures from leaking
            into production session-context injection. Pass False to include
            test-source rows (e.g. for auditing or purge scripts).
        order_by: SQL ORDER BY clause (whitelisted).
        limit: Maximum rows to return.
    """
    init_db()

    conditions = ["confidence >= ?"]
    params: list = [min_confidence]

    if topic:
        conditions.append("topic = ?")
        params.append(topic)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if project_path:
        conditions.append("(project_path IS NULL OR project_path = ?)")
        params.append(project_path)
    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)
    if exclude_graduated:
        conditions.append("graduated_to IS NULL")
    if exclude_test_sources:
        conditions.append("source NOT LIKE 'test%'")

    if tags:
        tag_clauses = []
        for tag in tags:
            tag_clauses.append("tags LIKE ?")
            params.append(f"%{tag}%")
        conditions.append(f"({' OR '.join(tag_clauses)})")

    # Whitelist valid ORDER BY to prevent injection
    valid_orders = {
        "confidence DESC",
        "confidence ASC",
        "last_seen DESC",
        "last_seen ASC",
        "observation_count DESC",
        "observation_count ASC",
        "first_seen DESC",
        "first_seen ASC",
    }
    if order_by not in valid_orders:
        order_by = "confidence DESC"

    where = " AND ".join(conditions)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM learnings WHERE {where} ORDER BY {order_by} LIMIT ?",  # security-review: ignore (internal clauses; user values bound as ?; pre-existing)
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def search_learnings(
    query: str,
    *,
    min_confidence: float = 0.0,
    exclude_graduated: bool = True,
    categories: list[str] | None = None,
    project_path: str | None = None,
    exclude_test_sources: bool = True,
    limit: int = 50,
) -> list[dict]:
    """Full-text search across learnings with BM25 ranking.

    Unlike query_learnings() which matches exact tag substrings,
    this uses FTS5 with porter stemming for fuzzy, ranked retrieval.

    Args:
        query: FTS5 query string. Supports OR/AND operators and prefix
            matching (e.g. "goroutine OR channel", "circuit*").
        min_confidence: Minimum confidence threshold for results.
        exclude_graduated: If True, omit entries that have graduated.
        categories: If given, restrict results to rows whose category is in
            this list (matches ANY, same semantics as query_learnings()'s
            `tags` filter). Use this to keep cross-domain categories (e.g.
            "voice", "review", "design") out of results meant for a
            different domain (e.g. tool-error hints).
        project_path: If given, restrict results to rows with a NULL
            project_path (global knowledge) or an exact match — same
            semantics as query_learnings()'s `project_path` filter.
        exclude_test_sources: If True (default), omit entries where source
            starts with 'test' — same default and rationale as
            query_learnings() (ADR-191): keeps test fixtures out of
            production injection. Pass False to include them (e.g. auditing).
        limit: Maximum number of results to return.

    Returns:
        List of learning dicts ordered by BM25 relevance (best first),
        each with an additional 'rank' key containing the BM25 score.
    """
    init_db()

    if not query or not query.strip():
        return []

    # Sanitize FTS query terms before matching
    query_str = query
    if query_str:
        terms = query_str.split(" OR ")
        terms = [sanitize_fts_query(t.strip()) for t in terms if t.strip()]
        terms = [t for t in terms if t]  # Remove empty after sanitization
        if terms:
            query_str = " OR ".join(terms)
        else:
            return []  # All terms were FTS operators — no valid query

    conditions = ["l.confidence >= ?"]
    params: list = [min_confidence]

    if exclude_graduated:
        conditions.append("l.graduated_to IS NULL")

    if exclude_test_sources:
        conditions.append("l.source NOT LIKE 'test%'")

    if categories:
        category_clauses = []
        for category in categories:
            category_clauses.append("l.category = ?")
            params.append(category)
        conditions.append(f"({' OR '.join(category_clauses)})")

    if project_path:
        conditions.append("(l.project_path IS NULL OR l.project_path = ?)")
        params.append(project_path)

    where = " AND ".join(conditions)

    with get_connection() as conn:
        try:
            rows = conn.execute(
                f"""
                SELECT l.*, bm25(learnings_fts) AS rank
                FROM learnings_fts fts
                JOIN learnings l ON l.id = fts.rowid
                WHERE learnings_fts MATCH ?
                  AND {where}
                ORDER BY rank
                LIMIT ?
                """,
                (query_str, *params, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            # Invalid FTS5 query syntax — fall back to empty results
            return []


def query_graduation_candidates(
    *,
    min_confidence: float = 0.9,
    min_observations: int = 3,
    limit: int = 10,
) -> list[dict]:
    """Return learning entries that are candidates for graduation into agent/skill files.

    Graduation criteria (all must be met):
    - confidence >= min_confidence
    - observation_count >= min_observations
    - graduated_to IS NULL (not already graduated)
    - topic is scoped (starts with 'skill:' or 'agent:')

    Args:
        min_confidence: Minimum confidence threshold (default 0.9).
        min_observations: Minimum observation count (default 3).
        limit: Maximum number of results to return (default 10).

    Returns:
        List of learning dicts sorted by confidence DESC, then observation_count DESC.
        Each dict contains: id, topic, key, value, category, confidence,
        observation_count, first_seen, last_seen, tags.
    """
    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, topic, key, value, category, confidence,
                   observation_count, first_seen, last_seen, tags
            FROM learnings
            WHERE confidence >= ?
              AND observation_count >= ?
              AND graduated_to IS NULL
              AND (topic LIKE 'skill:%' OR topic LIKE 'agent:%')
            ORDER BY confidence DESC, observation_count DESC
            LIMIT ?
            """,
            (min_confidence, min_observations, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def lookup_error_solution(
    error_message: str,
    min_confidence: float = 0.7,
) -> dict | None:
    """Look up a solution for an error pattern. Backward-compatible with error-learner."""
    init_db()

    error_type = classify_error(error_message)
    signature = generate_signature(error_message, error_type)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT topic, key, value, confidence, fix_type, fix_action, error_signature
            FROM learnings
            WHERE error_signature = ? AND confidence >= ? AND category = 'error'
            """,
            (signature, min_confidence),
        ).fetchone()

        if row:
            return dict(row)
        return None


def record_activations(
    entries: list[tuple[str, str]],
    session_id: str | None = None,
    outcome: str = "success",
) -> None:
    """Record that multiple learnings were surfaced during a session.

    Uses a single connection + executemany for efficiency.
    Called from injection hooks to track which learnings are actually used.

    Args:
        entries: List of (topic, key) pairs to record.
        session_id: Session identifier.
        outcome: Outcome string (default "success").
    """
    if not entries:
        return
    init_db()
    now = datetime.now().isoformat()
    rows = [(topic, key, session_id, now, outcome) for topic, key in entries]
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO activations (topic, key, session_id, timestamp, outcome) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def record_activation(
    topic: str,
    key: str,
    session_id: str | None = None,
    outcome: str = "success",
) -> None:
    """Record that a learning was surfaced during a session.

    Thin wrapper around record_activations() for single-entry convenience.
    """
    record_activations([(topic, key)], session_id, outcome)


def record_instruction_compliance(
    instruction_id: str,
    compliant: bool,
    session_id: str | None = None,
) -> None:
    """Record a single instruction compliance observation.

    Each call INSERTs a new row — observations accumulate, never overwrite.
    For multiple observations, prefer record_instruction_compliance_batch().

    Args:
        instruction_id: Instruction identifier (e.g. "M01").
        compliant: Whether the instruction was followed.
        session_id: Current session identifier.
    """
    record_instruction_compliance_batch([(instruction_id, compliant, session_id)])


def record_instruction_compliance_batch(
    records: list[tuple[str, bool, str | None]],
) -> None:
    """Record multiple instruction compliance observations in one transaction.

    Args:
        records: List of (instruction_id, compliant, session_id) tuples.
    """
    if not records:
        return
    init_db()
    now = datetime.now().isoformat()
    rows = [(instr_id, compliant, sid, now) for instr_id, compliant, sid in records]
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO instruction_compliance (instruction_id, compliant, session_id, timestamp) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def query_instruction_skip_rate(days: int = 30) -> list[dict]:
    """Query instruction compliance skip rates from the dedicated table.

    Args:
        days: Look back window in days (default 30).

    Returns:
        List of dicts with instruction_id, observations, non_compliant, skip_rate.
    """
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT instruction_id,
                   COUNT(*) as observations,
                   SUM(CASE WHEN NOT compliant THEN 1 ELSE 0 END) as non_compliant
            FROM instruction_compliance
            WHERE timestamp > datetime('now', ?)
            GROUP BY instruction_id
            ORDER BY instruction_id
            """,
            (f"-{days} days",),
        ).fetchall()
        results = []
        for row in rows:
            obs = row["observations"]
            nc = row["non_compliant"]
            skip_rate = (nc / obs * 100) if obs > 0 else 0.0
            results.append(
                {
                    "instruction_id": row["instruction_id"],
                    "observations": obs,
                    "non_compliant": nc,
                    "skip_rate": round(skip_rate, 1),
                }
            )
        return results


def boost_confidence(topic: str, key: str, delta: float = 0.10) -> float:
    """Boost confidence for an entry. Returns new confidence."""
    init_db()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence, success_count FROM learnings WHERE topic = ? AND key = ?",
            (topic, key),
        ).fetchone()
        if not row:
            return 0.0
        new_conf = min(1.0, row["confidence"] + delta)
        conn.execute(
            "UPDATE learnings SET confidence = ?, success_count = success_count + 1, last_seen = ? WHERE topic = ? AND key = ?",
            (new_conf, now, topic, key),
        )
        conn.commit()
        return new_conf


def decay_confidence(topic: str, key: str, delta: float = 0.10) -> float:
    """Decay confidence for an entry. Returns new confidence."""
    init_db()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence, failure_count FROM learnings WHERE topic = ? AND key = ?",
            (topic, key),
        ).fetchone()
        if not row:
            return 0.0
        new_conf = max(0.0, row["confidence"] - delta)
        conn.execute(
            "UPDATE learnings SET confidence = ?, failure_count = failure_count + 1, last_seen = ? WHERE topic = ? AND key = ?",
            (new_conf, now, topic, key),
        )
        conn.commit()
        return new_conf


def mark_graduated(topic: str, key: str, target: str) -> bool:
    """Mark entry as graduated to a permanent location.

    Returns:
        True if an entry was updated, False if no matching entry was found.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE learnings SET graduated_to = ? WHERE topic = ? AND key = ?",
            (target, topic, key),
        )
        conn.commit()
        if cursor.rowcount == 0:
            import sys

            print(f"WARNING: mark_graduated found no entry for topic={topic!r} key={key!r}", file=sys.stderr)
            return False
        return True


VALID_EVENT_TYPES = {
    "secret_detected",
    "approval_requested",
    "policy_violation",
    "security_finding",
    "hook_blocked",
}

VALID_SEVERITIES = {"critical", "high", "medium", "warning"}

VALID_RESOLUTIONS = {"dismissed", "false_positive", "remediated"}


def record_governance_event(
    event_type: str,
    *,
    session_id: str | None = None,
    tool_name: str | None = None,
    hook_phase: str | None = None,
    severity: str | None = None,
    payload: dict | None = None,
    blocked: bool = False,
    event_id: str | None = None,
) -> str | None:
    """Record a governance event to the governance_events table.

    Recording failures are always silent — this function never raises and
    never causes a hook to block. Returns the event id on success, None on failure.

    Args:
        event_type: One of secret_detected | approval_requested |
                    policy_violation | security_finding | hook_blocked.
        session_id: Claude Code session identifier.
        tool_name: Tool that triggered the event (Bash, Write, Edit, ...).
        hook_phase: 'pre' or 'post'.
        severity: One of critical | high | medium | warning.
        payload: Arbitrary dict serialised as JSON (command fingerprint,
                 matched pattern, secret types, etc.).
        blocked: True if the hook returned exit 2 to block the action.
        event_id: Override auto-generated id (for testing / idempotency).
    """
    import json as _json
    import time as _time

    try:
        init_db()

        ts_ns = _time.time_ns()
        ts_ms = ts_ns // 1_000_000
        suffix = hashlib.md5(f"{event_type}{session_id}{ts_ns}".encode()).hexdigest()[:6]
        eid = event_id or f"gov-{ts_ms}-{suffix}"

        payload_str = _json.dumps(payload) if payload else None
        created_at = datetime.now().isoformat()

        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO governance_events
                (id, session_id, event_type, tool_name, hook_phase,
                 severity, payload, blocked, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    session_id,
                    event_type,
                    tool_name,
                    hook_phase,
                    severity,
                    payload_str,
                    1 if blocked else 0,
                    created_at,
                ),
            )
            conn.commit()
        return eid
    except Exception:
        return None


def resolve_governance_event(
    event_id: str,
    resolution: str,
) -> bool:
    """Mark a governance event as resolved.

    Args:
        event_id: The event id to resolve.
        resolution: One of dismissed | false_positive | remediated.

    Returns:
        True if the event was found and updated, False otherwise.
    """
    if resolution not in VALID_RESOLUTIONS:
        return False

    try:
        init_db()
        resolved_at = datetime.now().isoformat()
        with get_connection() as conn:
            result = conn.execute(
                "UPDATE governance_events SET resolved_at = ?, resolution = ? WHERE id = ?",
                (resolved_at, resolution, event_id),
            )
            conn.commit()
            return result.rowcount > 0
    except Exception:
        return False


def query_governance_events(
    *,
    days: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    unresolved_only: bool = False,
    session_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Query governance events with optional filters.

    Args:
        days: Restrict to events created within the last N days.
        event_type: Filter by event type.
        severity: Filter by severity level.
        unresolved_only: If True, return only events with no resolution.
        session_id: Filter by session.
        limit: Maximum rows to return.

    Returns:
        List of event dicts ordered by created_at descending.
    """
    try:
        init_db()

        conditions: list[str] = []
        params: list = []

        if days is not None:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            conditions.append("created_at >= ?")
            params.append(cutoff)

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        if severity:
            conditions.append("severity = ?")
            params.append(severity)

        if unresolved_only:
            conditions.append("resolved_at IS NULL")

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""  # security-review: ignore (fixed condition strings; pre-existing)  # fmt: skip
        params.append(limit)

        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM governance_events {where} ORDER BY created_at DESC LIMIT ?",  # security-review: ignore (fixed clauses; user values bound as ?; pre-existing)
                params,
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def record_session(
    session_id: str,
    *,
    files_modified: int = 0,
    tools_used: int = 0,
    errors_encountered: int = 0,
    errors_resolved: int = 0,
    learnings_captured: int = 0,
    project_path: str | None = None,
    end_session: bool = False,
    summary: str | None = None,
) -> None:
    """Record or update session metrics."""
    init_db()
    now = datetime.now().isoformat()

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()

        if row:
            conn.execute(
                """
                UPDATE sessions SET
                    files_modified = files_modified + ?,
                    tools_used = tools_used + ?,
                    errors_encountered = errors_encountered + ?,
                    errors_resolved = errors_resolved + ?,
                    learnings_captured = learnings_captured + ?,
                    end_time = CASE WHEN ? THEN ? ELSE end_time END,
                    summary = COALESCE(?, summary)
                WHERE session_id = ?
                """,
                (
                    files_modified,
                    tools_used,
                    errors_encountered,
                    errors_resolved,
                    learnings_captured,
                    end_session,
                    now if end_session else None,
                    summary,
                    session_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO sessions
                (session_id, start_time, project_path,
                 files_modified, tools_used,
                 errors_encountered, errors_resolved,
                 learnings_captured, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    now,
                    project_path,
                    files_modified,
                    tools_used,
                    errors_encountered,
                    errors_resolved,
                    learnings_captured,
                    summary,
                ),
            )
        conn.commit()


def get_stats() -> dict:
    """Get learning statistics for dashboards."""
    init_db()

    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        high_conf = conn.execute("SELECT COUNT(*) FROM learnings WHERE confidence >= 0.7").fetchone()[0]
        graduated = conn.execute("SELECT COUNT(*) FROM learnings WHERE graduated_to IS NOT NULL").fetchone()[0]

        by_category = {}
        for row in conn.execute("SELECT category, COUNT(*) as cnt FROM learnings GROUP BY category").fetchall():
            by_category[row["category"]] = row["cnt"]

        by_topic = {}
        for row in conn.execute(
            "SELECT topic, COUNT(*) as cnt FROM learnings GROUP BY topic ORDER BY cnt DESC LIMIT 20"
        ).fetchall():
            by_topic[row["topic"]] = row["cnt"]

        sessions_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        learnings_per_session = total / max(sessions_count, 1)

        return {
            "total_learnings": total,
            "by_category": by_category,
            "by_topic": by_topic,
            "high_confidence": high_conf,
            "graduated": graduated,
            "sessions_tracked": sessions_count,
            "learnings_per_session": round(learnings_per_session, 2),
        }


def prune_ancillary(
    governance_days: int = 180,
    sessions_days: int = 365,
    activations_days: int = 90,
) -> dict[str, int]:
    """Prune old rows from ancillary tables. Returns per-table deletion counts.

    Args:
        governance_days: Delete governance_events older than this many days.
        sessions_days: Delete sessions and session_stats older than this many days.
        activations_days: Delete activations older than this many days.

    Returns:
        Dict mapping table name to number of rows deleted.
    """
    init_db()
    counts: dict[str, int] = {}

    # Table name → (timestamp column, cutoff days)
    table_specs = [
        ("governance_events", "created_at", governance_days),
        ("sessions", "start_time", sessions_days),
        ("session_stats", "created_at", sessions_days),
        ("activations", "timestamp", activations_days),
    ]

    with get_connection() as conn:
        for table, ts_col, days in table_specs:
            try:
                cursor = conn.execute(
                    f"DELETE FROM {table} WHERE {ts_col} < datetime('now', ?)",  # security-review: ignore (table/ts_col from hardcoded table_specs; days bound as ?; pre-existing)
                    (f"-{days} days",),
                )
                counts[table] = cursor.rowcount
            except sqlite3.OperationalError:
                counts[table] = 0  # Table may not exist yet
        conn.commit()

    return counts


def prune(min_confidence: float = 0.3, older_than_days: int = 90) -> int:
    """Remove low-confidence entries older than threshold."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM learnings WHERE confidence < ? AND last_seen < ? AND graduated_to IS NULL",
            (min_confidence, cutoff),
        )
        conn.commit()
        return result.rowcount


# ─── Import / Export ───────────────────────────────────────────


def import_from_retro(retro_dir: str) -> dict:
    """Import existing retro L2 markdown files into learning.db."""
    retro_path = Path(retro_dir)
    l2_dir = retro_path / "L2"
    if not l2_dir.is_dir():
        return {"imported": 0, "skipped": 0, "errors": ["L2 directory not found"]}

    imported = 0
    skipped = 0
    errors = []

    for md_file in sorted(l2_dir.glob("*.md")):
        try:
            content = md_file.read_text()
            topic = md_file.stem

            # Extract metadata from header
            conf_match = re.search(r"\*\*Confidence\*\*:\s*(\w+)", content)
            confidence_str = conf_match.group(1) if conf_match else "MEDIUM"
            conf_map = {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.45}
            base_confidence = conf_map.get(confidence_str.upper(), 0.65)

            tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
            tags = [t.strip() for t in tags_match.group(1).split(",")] if tags_match else []

            source_match = re.search(r"\*\*Source\*\*:\s*(.+)", content)
            source_str = f"migrated:{source_match.group(1).strip()}" if source_match else "migrated:retro"

            # Parse entries by ### heading
            parts = re.split(r"(?=^### )", content, flags=re.MULTILINE)
            for part in parts[1:] if len(parts) > 1 else []:
                heading_match = re.match(r"### (.+?)(?:\n|$)", part)
                if not heading_match:
                    continue

                raw_key = heading_match.group(1).strip()

                # Check for graduation marker
                graduated_to = None
                grad_match = re.search(r"\[GRADUATED\s*→\s*(.+?)\]", raw_key)
                if grad_match:
                    graduated_to = grad_match.group(1).strip()
                    raw_key = re.sub(r"\s*\[GRADUATED\s*→\s*.+?\]", "", raw_key).strip()

                # Check for observation count
                obs_match = re.search(r"\[(\d+)x\]", raw_key)
                obs_count = int(obs_match.group(1)) if obs_match else 1
                raw_key = re.sub(r"\s*\[\d+x\]", "", raw_key).strip()

                key = raw_key.lower().replace(" ", "-")
                value = part[len(heading_match.group(0)) :].strip()

                if not value:
                    skipped += 1
                    continue

                result = record_learning(
                    topic=topic,
                    key=key,
                    value=value,
                    category="design",  # Best guess for retro entries
                    confidence=base_confidence,
                    tags=tags if tags else None,
                    source=source_str,
                )

                # Apply graduated_to if present
                if graduated_to:
                    mark_graduated(topic, key, graduated_to)

                # Set observation count directly if > 1
                if obs_count > 1:
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE learnings SET observation_count = ? WHERE topic = ? AND key = ?",
                            (obs_count, topic, key),
                        )
                        conn.commit()

                imported += 1

        except Exception as e:
            errors.append(f"{md_file.name}: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


def import_from_patterns_db(db_path: str) -> dict:
    """Import existing patterns.db into learning.db."""
    patterns_path = Path(db_path)
    if not patterns_path.exists():
        return {"imported": 0, "skipped": 0, "errors": ["patterns.db not found"]}

    imported = 0
    skipped = 0
    errors = []

    try:
        with sqlite3.connect(patterns_path) as conn_old:
            conn_old.row_factory = sqlite3.Row

            rows = conn_old.execute("SELECT * FROM patterns").fetchall()
            for row in rows:
                try:
                    error_type = row["error_type"]
                    signature = row["signature"]
                    message = row["error_message"]
                    solution = row["solution"] or ""
                    value = f"{message[:200]}"
                    if solution:
                        value += f" → {solution}"

                    record_learning(
                        topic=error_type,
                        key=signature,
                        value=value,
                        category="error",
                        confidence=row["confidence"],
                        source="migrated:patterns-db",
                        project_path=row["project_path"],
                        error_signature=signature,
                        error_type=error_type,
                        fix_type=row["fix_type"],
                        fix_action=row["fix_action"],
                    )

                    # Set counts directly
                    with get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE learnings SET
                                success_count = ?, failure_count = ?,
                                observation_count = ?
                            WHERE topic = ? AND key = ?
                            """,
                            (
                                row["success_count"],
                                row["failure_count"],
                                row["success_count"] + row["failure_count"],
                                error_type,
                                signature,
                            ),
                        )
                        conn.commit()

                    imported += 1
                except Exception as e:
                    errors.append(f"pattern {row['signature']}: {e}")
                    skipped += 1

            # Import sessions too
            try:
                session_rows = conn_old.execute("SELECT * FROM sessions").fetchall()
                for srow in session_rows:
                    record_session(
                        srow["session_id"],
                        files_modified=srow["files_modified"] or 0,
                        tools_used=srow["tools_used"] or 0,
                        errors_encountered=srow["errors_encountered"] or 0,
                        errors_resolved=srow["errors_resolved"] or 0,
                        project_path=srow["project_path"],
                    )
            except Exception:
                pass  # Sessions are nice-to-have

    except Exception as e:
        errors.append(f"database: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


def export_markdown(fmt: str = "l2", output_dir: str | None = None) -> str:
    """Export learnings as markdown for human reading."""
    init_db()

    if fmt == "l1":
        return _export_l1()
    elif fmt == "l2":
        return _export_l2(output_dir)
    elif fmt == "full":
        return _export_full()
    else:
        return f"Unknown format: {fmt}"


def _export_l1() -> str:
    """Generate L1-style summary from learnings."""
    entries = query_learnings(
        min_confidence=0.5,
        exclude_graduated=True,
        order_by="confidence DESC",
        limit=30,
    )

    lines = ["# Accumulated Knowledge (L1 Summary)", ""]

    # Group by topic
    by_topic: dict[str, list[dict]] = {}
    for e in entries:
        t = e["topic"]
        if t not in by_topic:
            by_topic[t] = []
        by_topic[t].append(e)

    line_budget = 30
    lines_used = 2
    for topic, topic_entries in by_topic.items():
        if lines_used >= line_budget:
            break
        heading = topic.replace("-", " ").title() + " Patterns"
        lines.append(f"## {heading}")
        lines_used += 1
        for e in topic_entries:
            if lines_used >= line_budget:
                break
            first_line = e["value"].split("\n")[0][:120]
            lines.append(f"- {e['key']}: {first_line}")
            lines_used += 1
        lines.append("")
        lines_used += 1

    return "\n".join(lines) + "\n"


def _export_l2(output_dir: str | None) -> str:
    """Generate L2-style topic files from learnings."""
    entries = query_learnings(
        exclude_graduated=False,
        order_by="confidence DESC",
        limit=500,
    )

    by_topic: dict[str, list[dict]] = {}
    for e in entries:
        t = e["topic"]
        if t not in by_topic:
            by_topic[t] = []
        by_topic[t].append(e)

    files_written = []
    for topic, topic_entries in by_topic.items():
        all_tags = set()
        for e in topic_entries:
            if e["tags"]:
                all_tags.update(e["tags"].split(","))

        lines = [
            f"# Retro: {topic.replace('-', ' ').title()}",
            "**Source**: learning.db",
            f"**Tags**: {', '.join(sorted(all_tags)) if all_tags else topic}",
            "",
        ]

        for e in topic_entries:
            key_display = e["key"].replace("-", " ").title()
            suffix = ""
            if e["observation_count"] > 1:
                suffix += f" [{e['observation_count']}x]"
            if e["graduated_to"]:
                suffix += f" [GRADUATED → {e['graduated_to']}]"
            lines.append(f"### {key_display}{suffix}")
            lines.append(e["value"])
            lines.append("")

        content = "\n".join(lines)

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / f"{topic}.md").write_text(content)
            files_written.append(f"{topic}.md")
        else:
            files_written.append(content)

    if output_dir:
        return f"Wrote {len(files_written)} files: {', '.join(files_written)}"
    return "\n---\n".join(files_written)


def _export_full() -> str:
    """Full dump with metadata."""
    entries = query_learnings(
        min_confidence=0.0,
        exclude_graduated=False,
        limit=1000,
    )

    lines = ["# Full Learning Database Export", ""]
    for e in entries:
        lines.append(f"## [{e['category']}] {e['topic']}/{e['key']}")
        lines.append(f"- Confidence: {e['confidence']:.2f}")
        lines.append(f"- Observations: {e['observation_count']}")
        lines.append(f"- Source: {e['source']}")
        if e["graduated_to"]:
            lines.append(f"- Graduated to: {e['graduated_to']}")
        lines.append(f"- First seen: {e['first_seen']}")
        lines.append(f"- Last seen: {e['last_seen']}")
        lines.append("")
        lines.append(e["value"])
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    print(f"Database: {get_db_path()}")
    stats = get_stats()
    print(f"Stats: {stats}")
