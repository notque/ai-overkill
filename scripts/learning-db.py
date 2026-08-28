#!/usr/bin/env python3
"""
Learning Database CLI — Deterministic operations on the unified knowledge store.

Usage:
    python3 scripts/learning-db.py learn --skill go-patterns "insight text"
    python3 scripts/learning-db.py learn --agent golang-general-engineer "insight text"
    python3 scripts/learning-db.py record TOPIC KEY VALUE --category error
    python3 scripts/learning-db.py query --topic debugging --min-confidence 0.6
    python3 scripts/learning-db.py stats
    python3 scripts/learning-db.py purge --topic worktree-branches
    python3 scripts/learning-db.py export --format l1
    python3 scripts/learning-db.py export --format l2 --output-dir /tmp/learnings
    python3 scripts/learning-db.py import --from-retro ~/.claude/retro
    python3 scripts/learning-db.py import --from-patterns ~/.claude/learning/patterns.db
    python3 scripts/learning-db.py graduate TOPIC KEY TARGET
    python3 scripts/learning-db.py boost TOPIC KEY [--delta 0.15]
    python3 scripts/learning-db.py prune --category error --dry-run
    python3 scripts/learning-db.py prune --topic unknown --max-confidence 0.5 --older-than 90 --apply
    python3 scripts/learning-db.py stale [--min-age-days 30] [--json]
    python3 scripts/learning-db.py stale-prune --dry-run [--min-age-days 30]
    python3 scripts/learning-db.py stale-prune --confirm [--min-age-days 30]
    python3 scripts/learning-db.py migrate
    python3 scripts/learning-db.py record-activation TOPIC KEY --session SESSION_ID --outcome success
    python3 scripts/learning-db.py record-waste --session SESSION_ID --tokens 1500
    python3 scripts/learning-db.py record-session --session SESSION_ID --had-retro --failures 2 --waste-tokens 3000
    python3 scripts/learning-db.py roi [--json]
    python3 scripts/learning-db.py route-stats --by agent|skill|force-route|errors|override|week|day [--json]
    python3 scripts/learning-db.py review-roi [--json]
    python3 scripts/learning-db.py route-delta --from REF --to REF [--key AGENT:SKILL] [--metric error|tokens] [--json]
    python3 scripts/learning-db.py telemetry-query --topic eval:evals/<dir> [--git-sha SHA] [--key KEY] [--format json]
    python3 scripts/learning-db.py record-routing-outcome AGENT_SKILL --success
    python3 scripts/learning-db.py record-routing-outcome AGENT_SKILL --failure --reason "user re-routed"
    python3 scripts/learning-db.py route-failure AGENT:SKILL --reason "re-route after unusable output" --routing-relevant yes [--session SID --marker MK]
    python3 scripts/learning-db.py backfill-routing-outcomes
    python3 scripts/learning-db.py route-health [--json]
    python3 scripts/learning-db.py route-weights --json
    python3 scripts/learning-db.py skip-rate [--json] [--include-test]
    python3 scripts/learning-db.py record-review-fp --reviewer reviewer-code --finding "unused import" --reason "import used in test"
    python3 scripts/learning-db.py review-fps [--json] [--min-confidence 0.5]
    python3 scripts/learning-db.py evidence-recent [--json]
    python3 scripts/learning-db.py evidence-route-context AGENT:SKILL [--json]
    python3 scripts/learning-db.py evidence-file-history PATH [--json]
    python3 scripts/learning-db.py evidence-failures [--json]
    python3 scripts/learning-db.py evidence-decide AGENT:SKILL [--json]
    python3 scripts/learning-db.py stack-usage [--json]
    python3 scripts/learning-db.py backfill-stack-usage [--force]
"""

import argparse
import inspect
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Also check ~/.claude/hooks/lib for cross-repo usage (lower priority)
_home_lib = Path.home() / ".claude" / "hooks" / "lib"
if _home_lib.is_dir():
    sys.path.insert(0, str(_home_lib))

# Add repo hooks/lib AFTER home lib so repo copy takes priority (inserted at pos 0)
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

from learning_db_v2 import (
    boost_confidence,
    decay_confidence,
    export_markdown,
    get_connection,
    get_db_path,
    get_evidence_decision,
    get_evidence_failures,
    get_evidence_file_history,
    get_evidence_route_context,
    get_stats,
    import_from_patterns_db,
    import_from_retro,
    init_db,
    list_evidence_events,
    mark_graduated,
    query_instruction_skip_rate,
    query_learnings,
    record_learning,
    search_learnings,
)


def cmd_record(args):
    result = record_learning(
        topic=args.topic,
        key=args.key,
        value=args.value,
        category=args.category,
        confidence=args.confidence,
        tags=args.tags.split(",") if args.tags else None,
        source=args.source or "manual:cli",
        source_detail=args.source_detail,
        project_path=args.project_path,
    )
    action = "Updated" if not result["is_new"] else "Recorded"
    print(
        f"{action}: [{result['category']}] {result['topic']}/{result['key']} "
        f"(confidence: {result['confidence']:.2f}, observations: {result['observation_count']})"
    )


def cmd_query(args):
    results = query_learnings(
        topic=args.topic,
        category=args.category,
        tags=args.tags.split(",") if args.tags else None,
        min_confidence=args.min_confidence,
        exclude_graduated=not args.include_graduated,
        order_by=args.order_by,
        limit=args.limit,
    )

    if args.format == "json":
        print(json.dumps(results, indent=2, default=str))
    else:
        if not results:
            print("No learnings found matching criteria.")
            return
        for r in results:
            grad = " [GRADUATED]" if r.get("graduated_to") else ""
            obs = f" [{r['observation_count']}x]" if r["observation_count"] > 1 else ""
            print(f"[{r['category']}] {r['topic']}/{r['key']}{obs}{grad}")
            print(f"  confidence: {r['confidence']:.2f} | source: {r['source']}")
            first_line = r["value"].split("\n")[0][:100]
            print(f"  {first_line}")
            print()


def cmd_search(args):
    results = search_learnings(
        args.query,
        min_confidence=args.min_confidence,
        exclude_graduated=not args.include_graduated,
        limit=args.limit,
    )

    if args.format == "json":
        print(json.dumps(results, indent=2, default=str))
    else:
        if not results:
            print("No learnings found matching query.")
            return
        for r in results:
            grad = " [GRADUATED]" if r.get("graduated_to") else ""
            obs = f" [{r['observation_count']}x]" if r["observation_count"] > 1 else ""
            rank = f" (rank: {r.get('rank', 0):.2f})" if r.get("rank") is not None else ""
            print(f"[{r['category']}] {r['topic']}/{r['key']}{obs}{grad}{rank}")
            print(f"  confidence: {r['confidence']:.2f} | source: {r['source']}")
            first_line = r["value"].split("\n")[0][:100]
            print(f"  {first_line}")
            print()


def cmd_stats(args):
    stats = get_stats()

    if args.format == "json":
        print(json.dumps(stats, indent=2))
        return

    print(f"Learning Database: {get_db_path()}")
    print(f"{'─' * 50}")
    print(f"Total learnings:      {stats['total_learnings']}")
    print(f"High confidence (≥0.7): {stats['high_confidence']}")
    print(f"Graduated:            {stats['graduated']}")
    print(f"Sessions tracked:     {stats['sessions_tracked']}")
    print(f"Learnings/session:    {stats['learnings_per_session']}")
    print()

    if stats["by_category"]:
        print("By Category:")
        for cat, cnt in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            print(f"  {cat:20s} {cnt}")
        print()

    if stats["by_topic"]:
        print("By Topic (top 20):")
        for topic, cnt in sorted(stats["by_topic"].items(), key=lambda x: -x[1]):
            print(f"  {topic:30s} {cnt}")


def cmd_export(args):
    output = export_markdown(fmt=args.format, output_dir=args.output_dir)
    print(output)


def cmd_import(args):
    if args.from_retro:
        result = import_from_retro(args.from_retro)
        print(f"Imported from retro: {result['imported']} entries, {result['skipped']} skipped")  # security-review: ignore (print, not SQL; pre-existing)  # fmt: skip
    elif args.from_patterns:
        result = import_from_patterns_db(args.from_patterns)
        print(f"Imported from patterns.db: {result['imported']} entries, {result['skipped']} skipped")  # security-review: ignore (print, not SQL; pre-existing)  # fmt: skip
    else:
        print("Specify --from-retro or --from-patterns")
        sys.exit(1)

    if result.get("errors"):
        print(f"Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  - {e}")


def cmd_graduate(args):
    mark_graduated(args.topic, args.key, args.target)
    print(f"Graduated: {args.topic}/{args.key} → {args.target}")


def cmd_boost(args):
    new_conf = boost_confidence(args.topic, args.key, args.delta)
    print(f"Boosted: {args.topic}/{args.key} → confidence {new_conf:.2f}")


def cmd_decay(args):
    new_conf = decay_confidence(args.topic, args.key, args.delta)
    print(f"Decayed: {args.topic}/{args.key} → confidence {new_conf:.2f}")


# Rows always protected from prune: graduated entries and the routing/effectiveness
# rows that route-weights and route-health read.
_PRUNE_PROTECT_SQL = "graduated_to IS NULL AND NOT (topic = 'routing' AND category = 'effectiveness')"


def build_prune_filter(
    category: str | None = None,
    topic: str | None = None,
    max_confidence: float | None = None,
    older_than: int | None = None,
) -> tuple[str, list]:
    """Build the WHERE clause and bound params for a prune run.

    Filters compose with AND. Protection clauses (graduated, routing weights)
    are always included. Raises ValueError when no filter is given — a
    filterless prune would match the whole table.
    """
    clauses = [_PRUNE_PROTECT_SQL]
    params: list = []
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if topic is not None:
        clauses.append("topic = ?")
        params.append(topic)
    if max_confidence is not None:
        clauses.append("confidence <= ?")
        params.append(max_confidence)
    if older_than is not None:
        cutoff = (datetime.now() - timedelta(days=older_than)).isoformat()
        clauses.append("last_seen < ?")
        params.append(cutoff)
    if not params:
        raise ValueError("prune requires at least one filter (--category/--topic/--max-confidence/--older-than)")
    return " AND ".join(clauses), params


def cmd_prune(args):
    """Filtered prune of learnings. Dry-run by default; --apply deletes + VACUUM.

    Never touches graduated rows or routing/effectiveness rows (read by
    route-weights and route-health). FTS stays consistent via the
    learnings_ad delete trigger; VACUUM reclaims space after --apply.
    """
    max_confidence = args.max_confidence if args.max_confidence is not None else args.below_confidence
    try:
        where, params = build_prune_filter(
            category=args.category,
            topic=args.topic,
            max_confidence=max_confidence,
            older_than=args.older_than,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    init_db()
    with get_connection() as conn:
        total_before = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        # `where` is built only from fixed clauses; all user values are bound as ? params.
        matched_sql = (
            f"SELECT COUNT(*) FROM learnings WHERE {where}"  # security-review: ignore (fixed clauses; bound ?)
        )
        matched = conn.execute(matched_sql, params).fetchone()[0]
        breakdown = conn.execute(
            f"SELECT category, topic, COUNT(*) AS n FROM learnings WHERE {where} "  # security-review: ignore (fixed clauses; user values bound as ?)
            "GROUP BY category, topic ORDER BY n DESC",
            params,
        ).fetchall()

        print(f"Total learnings before: {total_before}")
        print(f"Matched for prune: {matched} (graduated and routing/effectiveness rows always excluded)")
        if breakdown:
            print("By category/topic:")
            for row in breakdown:
                print(f"  [{row['category']}] {row['topic']:30s} {row['n']}")

        if not args.apply:
            print()
            print("DRY RUN — nothing deleted. Re-run with --apply to delete.")
            print("Back up the database first: cp <db> <db>.bak-$(date +%Y%m%d)")
            return

        delete_sql = f"DELETE FROM learnings WHERE {where}"  # security-review: ignore (fixed clauses; bound ? params)
        cursor = conn.execute(delete_sql, params)
        deleted = cursor.rowcount
        conn.commit()
        total_after = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        conn.execute("VACUUM")
    print(f"Deleted {deleted} entries. Total learnings: {total_before} -> {total_after}.")


def _query_stale_entries(conn: sqlite3.Connection, min_age_days: int) -> list[dict]:
    """Query entries matching staleness criteria.

    Staleness criteria:
    - Entry age > min_age_days (based on first_seen)
    - Confidence < 0.5
    - NOT graduated
    """
    cutoff = (datetime.now() - timedelta(days=min_age_days)).isoformat()
    rows = conn.execute(
        """
        SELECT id, topic, key, value, confidence, category,
               first_seen, last_seen, graduated_to
        FROM learnings
        WHERE first_seen < ?
          AND confidence < 0.5
          AND graduated_to IS NULL
        ORDER BY confidence ASC
        """,
        (cutoff,),
    ).fetchall()
    return [dict(row) for row in rows]


def _ensure_archive_table(conn: sqlite3.Connection) -> None:
    """Create the learning_archive table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_archive (
            id INTEGER PRIMARY KEY,
            topic TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            confidence REAL,
            category TEXT,
            created_at TEXT,
            updated_at TEXT,
            archived_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def cmd_stale(args):
    """Show entries that appear stale (old, low-confidence, not graduated)."""
    init_db()
    with get_connection() as conn:
        entries = _query_stale_entries(conn, args.min_age_days)

    if args.json:
        print(json.dumps(entries, indent=2, default=str))
        return

    if not entries:
        print(f"No stale entries found (age > {args.min_age_days} days, confidence < 0.5, not graduated).")
        return

    print(f"Stale entries ({len(entries)} found):")
    print(f"{'─' * 90}")
    print(f"{'Topic':<25} {'Key':<20} {'Conf':>6} {'Age':>6} {'Last Updated':<20}")
    print(f"{'─' * 90}")

    now = datetime.now()
    for entry in entries:
        first_seen = datetime.fromisoformat(entry["first_seen"]) if entry["first_seen"] else now
        age_days = (now - first_seen).days
        last_updated = entry["last_seen"] or entry["first_seen"] or "unknown"
        if last_updated != "unknown":
            last_updated = last_updated[:19]  # Trim to datetime precision

        topic_display = entry["topic"][:24]
        key_display = entry["key"][:19]
        print(f"{topic_display:<25} {key_display:<20} {entry['confidence']:>5.2f} {age_days:>5}d {last_updated:<20}")

    print(f"{'─' * 90}")
    print(f"Total: {len(entries)} stale entries")


def cmd_stale_prune(args):
    """Archive stale entries to learning_archive table."""
    init_db()
    with get_connection() as conn:
        entries = _query_stale_entries(conn, args.min_age_days)

        if not entries:
            print(f"No stale entries to archive (age > {args.min_age_days} days, confidence < 0.5, not graduated).")
            return

        if args.dry_run:
            print(f"DRY RUN: Would archive {len(entries)} stale entries:")
            print()
            now = datetime.now()
            for entry in entries:
                first_seen = datetime.fromisoformat(entry["first_seen"]) if entry["first_seen"] else now
                age_days = (now - first_seen).days
                print(f"  {entry['topic']}/{entry['key']} (confidence: {entry['confidence']:.2f}, age: {age_days}d)")
            print()
            print(f"Run with --confirm to archive these {len(entries)} entries.")
            return

        # --confirm: actually archive
        _ensure_archive_table(conn)
        archived_at = datetime.now().isoformat()
        archived_count = 0

        for entry in entries:
            conn.execute(
                """
                INSERT INTO learning_archive (id, topic, key, value, confidence, category, created_at, updated_at, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["id"],
                    entry["topic"],
                    entry["key"],
                    entry["value"],
                    entry["confidence"],
                    entry["category"],
                    entry["first_seen"],
                    entry["last_seen"],
                    archived_at,
                ),
            )
            conn.execute("DELETE FROM learnings WHERE id = ?", (entry["id"],))
            archived_count += 1

        conn.commit()
    print(f"Archived {archived_count} stale entries to learning_archive table.")


def cmd_record_activation(args: argparse.Namespace) -> None:
    """Record that a learning was activated during a session."""
    init_db()
    now = datetime.now().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO activations (topic, key, session_id, timestamp, outcome) VALUES (?, ?, ?, ?, ?)",
                (args.topic, args.key, args.session, now, args.outcome),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Recorded activation: {args.topic}/{args.key} (session: {args.session}, outcome: {args.outcome})")


def cmd_record_waste(args: argparse.Namespace) -> None:
    """Record wasted tokens from a failure in a session.

    Increments failure_count by 1 and adds tokens to waste_tokens.
    Creates the session_stats row if it doesn't exist.
    """
    init_db()
    now = datetime.now().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO session_stats (session_id, failure_count, waste_tokens, created_at, had_retro_knowledge)
                   VALUES (?, 1, ?, ?, 0)
                   ON CONFLICT(session_id) DO UPDATE SET
                       failure_count = failure_count + 1,
                       waste_tokens = waste_tokens + excluded.waste_tokens""",
                (args.session, args.tokens, now),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Recorded waste: session={args.session}, tokens={args.tokens}")


def cmd_record_session_stats(args: argparse.Namespace) -> None:
    """Create or update a session_stats entry.

    On conflict (existing session_id), overwrites had_retro_knowledge,
    failure_count, and waste_tokens with the provided values.
    """
    init_db()
    now = datetime.now().isoformat()
    had_retro = 1 if args.had_retro else 0

    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO session_stats (session_id, had_retro_knowledge, failure_count, waste_tokens, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                       had_retro_knowledge = excluded.had_retro_knowledge,
                       failure_count = excluded.failure_count,
                       waste_tokens = excluded.waste_tokens""",
                (args.session, had_retro, args.failures, args.waste_tokens, now),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Recorded session: {args.session} (retro={bool(had_retro)}, failures={args.failures}, waste={args.waste_tokens})"
    )


def _compute_roi_data(db_path: Path) -> dict:
    """Compute ROI metrics from the database.

    Returns a dict with all ROI data suitable for both human and JSON output.
    """
    with get_connection() as conn:
        # Session cohort stats
        total_sessions = conn.execute("SELECT COUNT(*) FROM session_stats").fetchone()[0]
        with_retro = conn.execute("SELECT COUNT(*) FROM session_stats WHERE had_retro_knowledge = 1").fetchone()[0]
        without_retro = conn.execute("SELECT COUNT(*) FROM session_stats WHERE had_retro_knowledge = 0").fetchone()[0]

        # Failure totals per cohort
        retro_failures_row = conn.execute(
            "SELECT COALESCE(SUM(failure_count), 0) FROM session_stats WHERE had_retro_knowledge = 1"
        ).fetchone()
        retro_failures = retro_failures_row[0]

        no_retro_failures_row = conn.execute(
            "SELECT COALESCE(SUM(failure_count), 0) FROM session_stats WHERE had_retro_knowledge = 0"
        ).fetchone()
        no_retro_failures = no_retro_failures_row[0]

        # Average waste tokens for non-retro cohort only (counterfactual baseline)
        avg_waste_row = conn.execute(
            "SELECT COALESCE(AVG(waste_tokens), 0) FROM session_stats WHERE had_retro_knowledge = 0"
        ).fetchone()
        avg_waste = avg_waste_row[0]

        # Top activated learnings
        top_activations = []
        for row in conn.execute(
            "SELECT topic, key, COUNT(*) as activation_count FROM activations GROUP BY topic, key ORDER BY activation_count DESC LIMIT 5"
        ).fetchall():
            top_activations.append({"topic": row["topic"], "key": row["key"], "count": row["activation_count"]})

        # Dead weight: learnings with 0 activations (ADR-032 requires 10+ total sessions)
        dead_weight: list[dict] = []
        if total_sessions >= 10:
            for row in conn.execute(
                """SELECT l.topic, l.key, l.first_seen
                   FROM learnings l
                   LEFT JOIN activations a ON l.topic = a.topic AND l.key = a.key
                   WHERE a.id IS NULL
                   ORDER BY l.first_seen ASC
                   LIMIT 10"""
            ).fetchall():
                age_days = -1
                if row["first_seen"]:
                    try:
                        first_seen_dt = datetime.fromisoformat(row["first_seen"])
                        age_days = (datetime.now() - first_seen_dt).days
                    except (ValueError, TypeError) as e:
                        print(f"Warning: cannot parse first_seen for {row['topic']}/{row['key']}: {e}", file=sys.stderr)
                        age_days = -1
                dead_weight.append({"topic": row["topic"], "key": row["key"], "age_days": age_days})

    # Compute rates and improvement
    sufficient_data = with_retro >= 3 and without_retro >= 3
    rate_with_retro = retro_failures / with_retro if with_retro > 0 else 0.0
    rate_without_retro = no_retro_failures / without_retro if without_retro > 0 else 0.0

    if sufficient_data and rate_without_retro > 0:
        improvement_pct = (rate_without_retro - rate_with_retro) / rate_without_retro * 100
        # estimated_savings = improvement_fraction * avg_waste_per_session * sessions_with_retro
        estimated_savings = round(improvement_pct / 100 * avg_waste * with_retro)
    else:
        improvement_pct = None
        estimated_savings = None

    return {
        "total_sessions": total_sessions,
        "with_retro": with_retro,
        "without_retro": without_retro,
        "rate_with_retro": round(rate_with_retro, 2),
        "rate_without_retro": round(rate_without_retro, 2),
        "improvement_pct": round(improvement_pct, 1) if improvement_pct is not None else None,
        "estimated_savings": estimated_savings,
        "sufficient_data": sufficient_data,
        "top_activations": top_activations,
        "dead_weight": dead_weight,
    }


def cmd_roi(args: argparse.Namespace) -> None:
    """Compute and display learning ROI report."""
    init_db()
    db_path = get_db_path()
    data = _compute_roi_data(db_path)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    print("=== Learning ROI Report ===")
    print()
    print(
        f"Sessions: {data['total_sessions']} total ({data['with_retro']} with retro, {data['without_retro']} without)"
    )
    print()

    if not data["sufficient_data"]:
        print("Failure Rates:")
        print("  Insufficient data (need >= 3 sessions per cohort)")
        print()
    else:
        print("Failure Rates:")
        print(f"  With retro knowledge:    {data['rate_with_retro']:.2f} failures/session")
        print(f"  Without retro knowledge: {data['rate_without_retro']:.2f} failures/session")
        if data["improvement_pct"] is not None:
            if data["improvement_pct"] < 0:
                print(f"  WARNING: Retro cohort shows REGRESSION: {data['improvement_pct']:.1f}%")
                print(f"  Estimated waste increase: ~{abs(data['estimated_savings']):,} tokens")
            else:
                print(f"  Improvement:             {data['improvement_pct']:.1f}%")
                print(f"  Estimated Savings:       ~{data['estimated_savings']:,} tokens saved")
        else:
            print("  Improvement:             N/A (no failures in baseline cohort)")
        print()

    if data["top_activations"]:
        print("Top Activated Learnings:")
        for i, act in enumerate(data["top_activations"], 1):
            print(f"  {i}. {act['topic']}/{act['key']}  ({act['count']} activations)")
        print()

    if data["dead_weight"]:
        print("Dead Weight (0 activations):")
        for dw in data["dead_weight"]:
            print(f"  - {dw['topic']}/{dw['key']} (age: {dw['age_days']} days)")
        print()


def cmd_route_stats(args: argparse.Namespace) -> None:
    """Display routing decision statistics."""
    init_db()

    # Time-series dimensions (ADR: learning-telemetry-envelope) read the
    # append-only telemetry_runs table, not the aggregated learnings value string.
    if args.by in ("week", "day"):
        _route_stats_time_series(args)
        return

    results = query_learnings(topic="routing", category="effectiveness", limit=10000, exclude_graduated=False)

    if not results:
        print("No routing data found. Run sessions with /do to capture routing decisions.")
        return

    # Parse pipe-delimited values into dicts
    records: list[dict[str, str | int]] = []
    for r in results:
        parsed: dict[str, str | int] = {"key": r["key"], "observation_count": r.get("observation_count", 1)}
        for pair in r["value"].split(" | "):
            if ": " in pair:
                k, v = pair.split(": ", 1)
                parsed[k.strip()] = v.strip()
        records.append(parsed)

    dimension = args.by

    if dimension == "agent":
        _print_freq_table(
            records, "Agent", lambda r: str(r["key"]).split(":")[0] if ":" in str(r["key"]) else str(r["key"])
        )
    elif dimension == "skill":
        _print_freq_table(
            records, "Skill", lambda r: str(r["key"]).split(":")[-1] if ":" in str(r["key"]) else str(r["key"])
        )
    elif dimension == "force-route":
        total = len(records)
        force = sum(1 for r in records if r.get("force_used") == "1" or "force-route" in str(r.get("key", "")))
        print(f"Force-Route Stats ({total} total routes)")
        print(f"{'─' * 40}")
        if total:
            print(f"  Force-routed:  {force:>4} ({force / total * 100:.0f}%)")
            print(f"  Scored:        {total - force:>4} ({(total - force) / total * 100:.0f}%)")
        else:
            print("  No data")
    elif dimension == "errors":
        errored = [r for r in records if r.get("tool_errors") == "1"]
        print(f"Routes with Tool Errors ({len(errored)} of {len(records)})")
        print(f"{'─' * 50}")
        for r in errored:
            req = str(r.get("request", ""))[:60]
            print(f"  {str(r['key']):40s} | {req}")
        if not errored:
            print("  No tool errors recorded.")
    elif dimension == "override":
        total = len(records)
        overrides = sum(1 for r in records if r.get("llm_override") == "1")
        print(f"LLM Override Stats ({total} total routes)")
        print(f"{'─' * 40}")
        if total:
            print(f"  LLM overrode Phase 0: {overrides:>4} ({overrides / total * 100:.0f}%)")
            print(f"  Used Phase 0 as-is:   {total - overrides:>4} ({(total - overrides) / total * 100:.0f}%)")
        else:
            print("  No data")

    if args.json:
        import json as json_mod

        print(json_mod.dumps(records, indent=2, default=str))


def collect_route_weights() -> dict[str, dict[str, object]]:
    """Read routing/effectiveness rows into a weight map.

    Returns a dict keyed `<agent>:<skill>` with the fields confidence, n
    (observation_count), success, failure, last_seen. Read-only; excludes
    obvious test rows (source LIKE 'test%'); deterministic key ordering.
    On any sqlite3 error, returns {} (no evidence = keep behavior).
    """
    try:
        init_db()
        # Read only the columns we emit, ordered by key, for speed and determinism.
        # Excludes obvious test rows (source LIKE 'test%'); read-only.
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT key, confidence, observation_count, success_count, failure_count, last_seen
                FROM learnings
                WHERE topic = 'routing' AND category = 'effectiveness'
                  AND source NOT LIKE 'test%'
                ORDER BY key ASC
                """
            ).fetchall()
        return {
            row["key"]: {
                "confidence": round(float(row["confidence"]), 4),
                "n": int(row["observation_count"] or 0),
                "success": int(row["success_count"] or 0),
                "failure": int(row["failure_count"] or 0),
                "last_seen": row["last_seen"],
            }
            for row in rows
        }
    except sqlite3.Error:
        return {}


def cmd_route_weights(args: argparse.Namespace) -> None:
    """Emit routing weights as JSON for health-aware re-ranking."""
    try:
        print(json.dumps(collect_route_weights(), indent=2, default=str))
    except sqlite3.Error:
        print("{}")


# Default minimum cohort size below which route-delta prints a low-sample WARNING.
# Report-only — it never blocks; the numbers still print (ADR: learning-telemetry-envelope).
MIN_N = 5


def _route_stats_time_series(args: argparse.Namespace) -> None:
    """route-stats --by week|day: per-period run/error counts from telemetry_runs."""
    # strftime period format: ISO-ish week ('%Y-W%W') or calendar day ('%Y-%m-%d').
    period_fmt = "%Y-W%W" if args.by == "week" else "%Y-%m-%d"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT strftime(?, recorded_at) AS period, "
            "COUNT(*) AS runs, "
            "COALESCE(SUM(tool_errors), 0) AS errors, "
            "ROUND(100.0 * SUM(tool_errors) / COUNT(*), 1) AS error_pct "
            "FROM telemetry_runs WHERE topic = 'routing' "
            "GROUP BY period ORDER BY period",
            (period_fmt,),
        ).fetchall()

    data = [
        {"period": r["period"], "runs": r["runs"], "errors": r["errors"], "error_pct": r["error_pct"]} for r in rows
    ]

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return

    if not data:
        print("No telemetry runs yet. Telemetry captures from the next /do dispatch after merge+sync.")
        return

    label = "Week" if args.by == "week" else "Day"
    max_runs = max(row["runs"] for row in data) or 1
    print(f"Routing telemetry by {label.lower()} ({sum(row['runs'] for row in data)} runs)")
    print("-" * 56)
    print(f"{label:<11} {'runs':>5} {'errors':>7} {'err%':>6}  bar")
    for row in data:
        bar = "#" * max(1, round(20 * row["runs"] / max_runs))
        pct = row["error_pct"] if row["error_pct"] is not None else 0.0
        print(f"{row['period']:<11} {row['runs']:>5} {row['errors']:>7} {pct:>5.1f}%  {bar}")


def _resolve_cohort(conn, ref: str, key: str | None) -> str:
    """Build the WHERE clause for one cohort ref (git-SHA prefix or date), with params.

    A `ref` that is all hex and >=4 chars is treated as a git-SHA prefix matched
    against telemetry_runs.git_sha; otherwise it is matched as a date prefix on
    recorded_at. --key further scopes to one route. Returns (where_sql, params).
    """
    clauses = ["topic = 'routing'"]
    params: list[str] = []
    is_sha = len(ref) >= 4 and all(c in "0123456789abcdefABCDEF" for c in ref)
    if is_sha:
        clauses.append("git_sha LIKE ?")
        params.append(ref + "%")
    else:
        clauses.append("recorded_at LIKE ?")
        params.append(ref + "%")
    if key:
        clauses.append("key = ?")
        params.append(key)
    return " AND ".join(clauses), params


def _cohort_error(conn, where: str, params: list[str]) -> dict:
    """Error-rate stats for one cohort."""
    # `where` is built only from fixed clauses; all user values are bound as ? params.
    row = conn.execute(
        f"SELECT COUNT(*) AS runs, COALESCE(SUM(tool_errors), 0) AS errors FROM telemetry_runs WHERE {where}",  # security-review: ignore (fixed clauses; user values bound as ?)
        params,
    ).fetchone()
    runs = row["runs"]
    errors = row["errors"]
    pct = round(100.0 * errors / runs, 1) if runs else None
    return {"runs": runs, "errors": errors, "error_pct": pct}


def _cohort_tokens(conn, where: str, params: list[str]) -> dict:
    """Token stats for one cohort. n counts NON-NULL token rows only; NULL never
    counts as 0 (ADR NULL-tolerance)."""
    # `where` is built only from fixed clauses; all user values are bound as ? params.
    row = conn.execute(
        f"SELECT COUNT(token_count) AS n, AVG(token_count) AS avg_tokens, COUNT(*) AS runs FROM telemetry_runs WHERE {where}",  # security-review: ignore (fixed clauses; user values bound as ?)
        params,
    ).fetchone()
    n = row["n"]
    avg = round(row["avg_tokens"], 1) if row["avg_tokens"] is not None else None
    return {"runs": row["runs"], "n": n, "avg_tokens": avg}


# Below this many findings-bearing reviews the ROI table refuses to assert a
# "best" tier — a humility gate, not a merge gate (ADR: review-tier-roi).
ROI_MIN_REVIEWS = 20

_RIGHTSIZING_KEY_RE = re.compile(r"^rightsizing:tier(\d+)$")
# Running-sum fields stored by accumulate_rightsizing (learning_db_v2). review-roi
# divides these true sums by their true counts — no per-review sample survives.
_RIGHTSIZING_SUM_KEYS = (
    "reviews",
    "sum_critical",
    "sum_high",
    "sum_medium",
    "n_findings",
    "sum_tokens",
    "n_tokens",
    "sum_wall_clock_s",
    "n_wall",
)


def _parse_pipe_value(value: str) -> dict[str, str]:
    """Parse a pipe-delimited `k: v | k: v` value into a dict (route-stats format)."""
    parsed: dict[str, str] = {}
    for pair in value.split(" | "):
        if ": " in pair:
            k, v = pair.split(": ", 1)
            parsed[k.strip()] = v.strip()
    return parsed


def _to_int(s: str | None) -> int:
    """Read a stored sum/count field to int; non-numeric or missing => 0."""
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _avg(total: float, count: int) -> float | None:
    """Average, or None when there is no contributing row (n/a, not 0)."""
    return round(total / count, 2) if count else None


def _compute_review_roi() -> list[dict]:
    """Aggregate rightsizing:tier{N} rows into per-tier ROI dicts, tier ascending.

    Each row stores RUNNING SUMS, not one sample, so averages are true means
    (ADR: review-tier-roi). Findings averages divide sum_critical/high/medium by
    n_findings (findings-bearing reviews only) — legacy no-findings reviews are
    counted in `reviews` but never inflate the findings denominator. Cost
    averages divide sum_tokens by n_tokens (and wall by n_wall); an all-"-" tier
    has n_tokens 0 and reports null (n/a, not 0). A tier with zero
    findings-bearing reviews (n_findings 0) is excluded from the table.

    `reviews` displayed = n_findings (the reviews the findings averages rest on),
    so the count and the averages describe the same sample."""
    rows = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )
    # One row per tier carries the running sums; merge defensively if duplicated.
    agg: dict[int, dict[str, int]] = {}
    for r in rows:
        m = _RIGHTSIZING_KEY_RE.match(r["key"])
        if not m:
            continue
        f = _parse_pipe_value(r["value"])
        tier = int(m.group(1))
        a = agg.setdefault(tier, dict.fromkeys(_RIGHTSIZING_SUM_KEYS, 0))
        for k in _RIGHTSIZING_SUM_KEYS:
            a[k] += _to_int(f.get(k))

    # Reviews underpinning the findings averages, summed across findings-bearing tiers.
    total_reviews = sum(a["n_findings"] for a in agg.values() if a["n_findings"])
    insufficient = total_reviews < ROI_MIN_REVIEWS
    out = []
    for tier in sorted(agg):
        a = agg[tier]
        nf = a["n_findings"]
        if nf <= 0:
            continue  # composition-only tier: no findings to average
        out.append(
            {
                "tier": tier,
                "reviews": nf,
                "avg_critical": _avg(a["sum_critical"], nf),
                "avg_high": _avg(a["sum_high"], nf),
                "avg_medium": _avg(a["sum_medium"], nf),
                "avg_tokens": _avg(a["sum_tokens"], a["n_tokens"]),
                "avg_wall_clock_s": _avg(a["sum_wall_clock_s"], a["n_wall"]),
                "insufficient_data": insufficient,
            }
        )
    return out


def cmd_review_roi(args: argparse.Namespace) -> None:
    """review-roi: per-tier review cost/findings ROI (report-only, never blocks)."""
    init_db()
    data = _compute_review_roi()
    total_reviews = sum(r["reviews"] for r in data)

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return

    if not data:
        print("No review-ROI data. Run reviews that emit findings= in the rightsizing banner.")
        return

    def _cell(v: float | None) -> str:
        return "n/a" if v is None else f"{v:g}"

    print(f"Review-Tier ROI  ({total_reviews} reviews)")
    print(
        f"{'Tier':<5} {'Reviews':>8} {'Avg Crit':>9} {'Avg High':>9} {'Avg Med':>8} {'Avg Tokens':>11} {'Avg Wall(s)':>12}"
    )
    for r in data:
        print(
            f"{r['tier']:<5} {r['reviews']:>8} {_cell(r['avg_critical']):>9} {_cell(r['avg_high']):>9} "
            f"{_cell(r['avg_medium']):>8} {_cell(r['avg_tokens']):>11} {_cell(r['avg_wall_clock_s']):>12}"
        )
    if data and data[0]["insufficient_data"]:
        print(
            f"INSUFFICIENT DATA: {total_reviews} reviews (<{ROI_MIN_REVIEWS}). "
            "Numbers shown for inspection; do not act on them."
        )


def cmd_route_delta(args: argparse.Namespace) -> None:
    """route-delta --from REF --to REF: 'did that change help?' cohort comparison.

    Report-only — a low sample prints a WARNING but never blocks (exit 0).
    """
    init_db()
    metric = args.metric
    with get_connection() as conn:
        where_a, params_a = _resolve_cohort(conn, args.from_ref, args.key)
        where_b, params_b = _resolve_cohort(conn, args.to_ref, args.key)
        if metric == "tokens":
            cohort_a = _cohort_tokens(conn, where_a, params_a)
            cohort_b = _cohort_tokens(conn, where_b, params_b)
        else:
            cohort_a = _cohort_error(conn, where_a, params_a)
            cohort_b = _cohort_error(conn, where_b, params_b)

    if metric == "tokens":
        a_val = cohort_a["avg_tokens"]
        b_val = cohort_b["avg_tokens"]
        delta = round(b_val - a_val, 1) if (a_val is not None and b_val is not None) else None
        result = {"metric": "tokens", "from": cohort_a, "to": cohort_b, "delta_tokens": delta}
    else:
        a_pct = cohort_a["error_pct"]
        b_pct = cohort_b["error_pct"]
        delta = round(b_pct - a_pct, 1) if (a_pct is not None and b_pct is not None) else None
        result = {"metric": "error", "from": cohort_a, "to": cohort_b, "delta_pts": delta}

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    scope = f"  key={args.key}" if args.key else ""
    print(f"route-delta  metric={metric}  from={args.from_ref}  to={args.to_ref}{scope}")  # security-review: ignore (print, not SQL)  # fmt: skip
    print("-" * 56)
    if metric == "tokens":
        a_disp = f"{cohort_a['avg_tokens']}" if cohort_a["avg_tokens"] is not None else "n/a"
        b_disp = f"{cohort_b['avg_tokens']}" if cohort_b["avg_tokens"] is not None else "n/a"
        print(f"Cohort A ({args.from_ref}): {cohort_a['runs']:>4} runs, avg tokens {a_disp} (n={cohort_a['n']})")
        print(f"Cohort B ({args.to_ref}): {cohort_b['runs']:>4} runs, avg tokens {b_disp} (n={cohort_b['n']})")
        if delta is not None:
            direction = "fewer" if delta < 0 else "more"
            print(f"Delta: {delta:+} tokens ({direction})   n_A={cohort_a['n']} n_B={cohort_b['n']}")
        else:
            print("Delta: n/a (a cohort has no non-NULL token_count)")
    else:
        a_pct = f"{cohort_a['error_pct']:.1f}%" if cohort_a["error_pct"] is not None else "n/a"
        b_pct = f"{cohort_b['error_pct']:.1f}%" if cohort_b["error_pct"] is not None else "n/a"
        print(f"Cohort A ({args.from_ref}): {cohort_a['runs']:>4} runs, {cohort_a['errors']:>3} errors ({a_pct})")
        print(f"Cohort B ({args.to_ref}): {cohort_b['runs']:>4} runs, {cohort_b['errors']:>3} errors ({b_pct})")
        if delta is not None:
            direction = "improved" if delta < 0 else ("worse" if delta > 0 else "flat")
            print(f"Delta: {delta:+} pts error rate  ({direction})   n_A={cohort_a['runs']} n_B={cohort_b['runs']}")
        else:
            print("Delta: n/a (a cohort has no runs)")

    # Low-sample advisory — report-only, never blocks.
    for label, n in (("A", cohort_a["runs"]), ("B", cohort_b["runs"])):
        if n < MIN_N:
            print(f"WARNING: cohort {label} has only {n} run(s) (< MIN_N={MIN_N}); treat the delta as low-confidence.")


def _parse_ablation_value(value: str) -> dict[str, object]:
    """Parse the key=value envelope used by pre-telemetry ablation records."""
    fields: dict[str, object] = {}
    for part in (value or "").split():
        name, separator, raw = part.partition("=")
        if not separator:
            continue
        fields[name] = raw

    for name in ("pass_rate",):
        try:
            fields[name] = float(fields[name])
        except (KeyError, TypeError, ValueError):
            fields[name] = None
    try:
        fields["runs"] = int(fields["runs"])
    except (KeyError, TypeError, ValueError):
        fields["runs"] = None
    return fields


def cmd_telemetry_query(args: argparse.Namespace) -> None:
    """Read telemetry_runs rows and compatible ablation fallback records.

    Current ablation runs store their per-run envelope in telemetry_runs. Older
    or degraded runs store one packed summary in learnings; those rows are
    returned only when a matching telemetry row is not present. JSON fallback
    rows include ``storage=learnings`` plus the parsed pass rate and run count.
    Report-only; exit 0.
    """
    init_db()
    # Fixed clauses only; all user values are bound as ? params.
    clauses = ["topic = ?"]
    params: list = [args.topic]
    if args.git_sha:
        clauses.append("git_sha LIKE ?")
        params.append(args.git_sha + "%")
    if args.key:
        clauses.append("key = ?")
        params.append(args.key)
    where = " AND ".join(clauses)
    params.append(args.limit)
    with get_connection() as conn:
        telemetry_rows = [
            dict(r)
            for r in conn.execute(
                f"SELECT * FROM telemetry_runs WHERE {where} ORDER BY recorded_at DESC LIMIT ?",  # security-review: ignore (fixed clauses; user values bound as ?)
                params,
            ).fetchall()
        ]

        for row in telemetry_rows:
            row["storage"] = "telemetry_runs"

        fallback_params = [args.topic, "effectiveness", "manual:skill-eval-ablation"]
        fallback_sql = (
            "SELECT rowid AS learning_id, topic, key, value, source, category, "
            "first_seen, last_seen, observation_count "
            "FROM learnings WHERE topic = ? AND category = ? AND source = ?"
        )
        if args.key:
            fallback_sql += " AND key = ?"
            fallback_params.append(args.key)
        fallback_sql += " ORDER BY last_seen DESC LIMIT ?"
        fallback_params.append(args.limit)
        fallback_rows = [dict(r) for r in conn.execute(fallback_sql, fallback_params).fetchall()]

    rows = list(telemetry_rows)
    telemetry_identity = {(r["topic"], r["key"], r.get("git_sha")) for r in telemetry_rows}
    telemetry_keys = {(r["topic"], r["key"]) for r in telemetry_rows}
    for learning in fallback_rows:
        parsed = _parse_ablation_value(learning["value"])
        git_sha = parsed.get("git_commit_sha") or parsed.get("head")
        if args.git_sha and (not isinstance(git_sha, str) or not git_sha.startswith(args.git_sha)):
            continue
        if not args.git_sha and (learning["topic"], learning["key"]) in telemetry_keys:
            continue
        if args.git_sha and (learning["topic"], learning["key"], git_sha) in telemetry_identity:
            continue
        rows.append(
            {
                "id": None,
                "run_id": None,
                "batch_id": None,
                "topic": learning["topic"],
                "key": learning["key"],
                "session_id": None,
                "git_sha": git_sha,
                "model_id": parsed.get("model_id"),
                "skill_version": parsed.get("skill_version"),
                "token_count": None,
                "wall_clock_ms": None,
                "tool_errors": 0,
                "recorded_at": learning["last_seen"],
                "source": learning["source"],
                "storage": "learnings",
                "learning_id": learning["learning_id"],
                "pass_rate": parsed.get("pass_rate"),
                "runs": parsed.get("runs"),
                "base_sha": parsed.get("base"),
                "head_sha": parsed.get("head"),
                "observation_count": learning["observation_count"],
                "value": learning["value"],
            }
        )

    rows.sort(key=lambda row: row.get("recorded_at") or "", reverse=True)
    rows = rows[: args.limit]

    if args.format == "json":
        print(json.dumps(rows, indent=2, default=str))
        return
    if not rows:
        print(f"No telemetry or ablation fallback runs for topic={args.topic}.")
        return
    for r in rows:
        line = f"{r['recorded_at']}  {r['topic']}/{r['key']}  git_sha={r['git_sha']}  source={r['source']}"
        if r["storage"] == "learnings":
            line += f"  pass_rate={r['pass_rate']}  runs={r['runs']}  storage=learnings"
        print(line)


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _print_evidence_rows(rows: list[dict]) -> None:
    if not rows:
        print("No evidence rows found.")
        return
    for row in rows:
        status = ""
        if row.get("success") is True:
            status = " ok"
        elif row.get("success") is False:
            status = " failed"
        target = f" target={row['target']}" if row.get("target") else ""
        route = f" route={row['route_key']}" if row.get("route_key") else ""
        print(f"{row['ts']}  {row['event_type']}{status} source={row['source']}{route}{target}")


def cmd_evidence_recent(args: argparse.Namespace) -> None:
    rows = list_evidence_events(
        limit=args.limit,
        session_id=args.session,
        event_type=args.type,
        route_key=args.route_key,
        agent=args.agent,
        skill=args.skill,
        failures_only=args.failures,
    )
    if args.json:
        _print_json(rows)
    else:
        _print_evidence_rows(rows)


def cmd_evidence_route_context(args: argparse.Namespace) -> None:
    context = get_evidence_route_context(args.route_key, limit=args.limit)
    if args.json:
        _print_json(context)
        return
    totals = context["totals"]
    print(
        f"{args.route_key}: {totals['decisions']} decision(s), "
        f"{totals['successes']} success(es), {totals['failures']} failure(s)"
    )
    _print_evidence_rows(context["failures"])


def cmd_evidence_file_history(args: argparse.Namespace) -> None:
    rows = get_evidence_file_history(args.target, limit=args.limit)
    if args.json:
        _print_json(rows)
    else:
        _print_evidence_rows(rows)


def cmd_evidence_failures(args: argparse.Namespace) -> None:
    rows = get_evidence_failures(
        limit=args.limit,
        route_key=args.route_key,
        agent=args.agent,
        skill=args.skill,
    )
    if args.json:
        _print_json(rows)
    else:
        _print_evidence_rows(rows)


def cmd_evidence_decide(args: argparse.Namespace) -> None:
    decision = get_evidence_decision(args.route_key)
    if args.json:
        _print_json(decision)
        return
    print(f"{decision['route_key']}: {decision['recommendation']} ({decision['confidence']})")
    for reason in decision["reasons"]:
        print(f"- {reason}")


def cmd_record_routing_outcome(args: argparse.Namespace) -> None:
    """Record whether a routing decision succeeded or failed."""
    init_db()
    key = args.agent_skill

    # Verify the routing entry exists
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )
    entry = next((r for r in results if r["key"] == key), None)
    if entry is None:
        print(f"WARNING: No routing entry found for key '{key}' — route was never recorded.", file=sys.stderr)
        sys.exit(1)

    if args.success:
        new_conf = boost_confidence("routing", key, delta=0.05)
    else:
        new_conf = decay_confidence("routing", key, delta=0.08)

    # Append reason to value if provided
    if args.reason:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM learnings WHERE topic = ? AND key = ?",
                ("routing", key),
            ).fetchone()
            if row:
                new_value = f"{row['value']} | outcome_reason: {args.reason}"
                conn.execute(
                    "UPDATE learnings SET value = ? WHERE topic = ? AND key = ?",
                    (new_value, "routing", key),
                )
                conn.commit()

    outcome = "success" if args.success else "failure"
    print(f"Recorded {outcome} for routing/{key} — confidence: {new_conf:.4f}")


def _ensure_route_failure_dedup_table(conn: sqlite3.Connection) -> None:
    """Create the route_failure_dedup table if absent (idempotence ledger).

    learning_db_v2.py is never edited (a pre-existing SQLi false-positive there
    trips the commit security gate), so the table is created here, like
    _ensure_archive_table. One row per (session, marker) dispatch key records a
    failure already counted, so a retry loop cannot decay a pair repeatedly.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS route_failure_dedup (
            session TEXT NOT NULL,
            marker TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (session, marker)
        )
        """
    )
    conn.commit()


def cmd_route_failure(args: argparse.Namespace) -> None:
    """Record an orchestrator-reported routing failure (ADR: orchestrator-reported-route-failures).

    Routing-relevant => decay the pair's weight row via the finalizer's decay
    path (apply_outcome failure) AND append a reasoned failure event. Not-relevant
    => event only, zero decay (a task failure by the right route must not poison
    route health). Idempotent per dispatch key (session, marker): a duplicate is a
    no-op, exit 0. Malformed pair (no ':') exits non-zero.
    """
    key = args.agent_skill
    if ":" not in key:
        print(f"Error: pair must be 'agent:skill', got {key!r}", file=sys.stderr)
        sys.exit(2)

    # Resolve reason from --reason or --reason-file.
    if getattr(args, "reason_file", None):
        args.reason = Path(args.reason_file).read_text(encoding="utf-8")

    init_db()
    routing_relevant = args.routing_relevant == "yes"
    session = args.session or ""
    marker = args.marker or ""

    # Idempotence ordering — at-least-once, NOT at-most-once. The failure signal
    # is the scarcest resource in this loop, so a dropped signal is worse than a
    # re-applied one. Ordering:
    #   (a) fast dup exit: if the dedup row already exists, no-op (exit 0);
    #   (b) do the decay + outcome-event work;
    #   (c) THEN insert + commit the dedup row.
    # A crash between (b) and (c) leaves no dedup row, so a retry re-applies ONE
    # decay — bounded and acceptable on a single-user toolkit. The old order
    # (commit dedup first) silently DROPPED the signal on a crash between commit
    # and decay: a retry hit IntegrityError and no-op'd, exit 0, no error.
    # Two identical concurrent invocations can both pass (a) and both apply once;
    # accepted (single-user, no concurrent route-failure calls).
    dedup_active = bool(session and marker)
    if dedup_active:
        with get_connection() as conn:
            _ensure_route_failure_dedup_table(conn)
            row = conn.execute(
                "SELECT 1 FROM route_failure_dedup WHERE session = ? AND marker = ?",
                (session, marker),
            ).fetchone()
        if row is not None:
            print(f"Duplicate dispatch key (session={session}, marker={marker}); no-op.")
            return

    # route_events lives in hooks/lib (already on sys.path via the header).
    from route_events import record_outcome_event

    decayed_note = "no decay (not routing-relevant)"
    if routing_relevant:
        # Reuse the finalizer's decay path — do NOT invent a second formula.
        from routing_outcome_score import apply_outcome, decision_row_exists

        if decision_row_exists(key):
            new_conf = apply_outcome(key, "failure")
            decayed_note = f"decayed routing/{key} -> confidence {new_conf:.4f}"
        else:
            decayed_note = f"no weight row for {key}; event logged, nothing to decay"

    # Pass routing_relevant only if record_outcome_event accepts it. A sibling
    # change adds the optional param; guard via signature so neither agent breaks
    # the other while both land.
    event_kwargs: dict[str, object] = {
        "session": session,
        "key": key,
        "outcome": "failure",
        "reason": args.reason,
    }
    if "routing_relevant" in inspect.signature(record_outcome_event).parameters:
        event_kwargs["routing_relevant"] = routing_relevant
    record_outcome_event(**event_kwargs)

    # (c) Mark the dispatch key done only AFTER the work succeeded.
    if dedup_active:
        with get_connection() as conn:
            _ensure_route_failure_dedup_table(conn)
            try:
                conn.execute(
                    "INSERT INTO route_failure_dedup (session, marker, recorded_at) VALUES (?, ?, ?)",
                    (session, marker, datetime.now().isoformat()),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # A concurrent invocation won the insert race; the work is done.
                pass

    print(f"Recorded route failure: {key} (routing-relevant={args.routing_relevant}) — {decayed_note}")


def cmd_backfill_routing_outcomes(args: argparse.Namespace) -> None:
    """Backfill routing outcomes from existing entry data."""
    init_db()
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )

    boosted = 0
    decayed_count = 0
    skipped = 0
    unchanged = 0

    for r in results:
        # Idempotency: skip entries already scored
        if (r["success_count"] or 0) + (r["failure_count"] or 0) > 0:
            skipped += 1
            continue

        value = r["value"]
        if "tool_errors=1" in value or "user_rerouted=1" in value:
            decay_confidence("routing", r["key"], delta=0.08)
            decayed_count += 1
        elif "outcome=committed_and_pushed" in value or "outcome=success" in value:
            boost_confidence("routing", r["key"], delta=0.05)
            boosted += 1
        else:
            unchanged += 1

    total = boosted + decayed_count + unchanged + skipped
    print(f"Backfill complete: {total} entries processed")
    print(f"  Boosted:   {boosted}")
    print(f"  Decayed:   {decayed_count}")
    print(f"  Skipped:   {skipped}")
    print(f"  Unchanged: {unchanged}")


# The recording hook owns the observability declaration; this mirror is used
# only when it cannot be imported (cross-repo copy, missing file).
_OBSERVABLE_FALLBACK = frozenset({"M04", "M05", "M06"})


def _observable_instructions() -> frozenset[str]:
    """Instruction IDs the recording hook declares it CAN observe.

    Source of truth: hooks/instruction-compliance.py INSTRUCTIONS. Anything not
    in this set is unobservable, including an ID the hook no longer declares.
    Unobservable rows stay in the table — they are history — but a skip rate
    measured on a surface that cannot show compliance must never recommend a
    blocking gate.
    """
    try:
        import importlib.util

        hook = _repo_root / "hooks" / "instruction-compliance.py"
        spec = importlib.util.spec_from_file_location("instruction_compliance", hook)
        if spec is None or spec.loader is None:
            return _OBSERVABLE_FALLBACK
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return frozenset(i for i, d in mod.INSTRUCTIONS.items() if d.get("observable", False))
    except Exception:
        return _OBSERVABLE_FALLBACK


def cmd_skip_rate(args: argparse.Namespace) -> None:
    """Display instruction skip-rate report from the instruction_compliance table.

    Queries the dedicated instruction_compliance table for per-observation
    data and computes skip rate per instruction. Flags instructions with
    >20% skip rate over 30+ observations for conversion to programmatic gates —
    but only instructions the recording hook can actually observe. Unobservable
    ones keep their historical rows and are reported as NOT MEASURABLE.
    """
    init_db()

    # Instruction ID -> human-readable name mapping. M05/M06 measure whether the
    # directive reached the prompt, not whether the output followed it.
    instr_names: dict[str, str] = {
        "M01": "Phase Banners",
        "M03": "Routing Decision",
        "M04": "Reference Loading",
        "M05": "Completeness Injected",
        "M06": "Density Injected",
    }
    observable = _observable_instructions()

    def _status(instr_id: str, skip_rate: float, observations: int, gate_label: str) -> str:
        if instr_id not in observable:
            return "NOT MEASURABLE"
        return gate_label if skip_rate > 20 and observations >= 30 else "OK"

    results = query_instruction_skip_rate(days=30)

    if not results:
        print("No instruction compliance data found. Run sessions to collect data.")
        return

    if args.json:
        report = []
        for r in results:
            instr_id = r["instruction_id"]
            report.append(
                {
                    "id": instr_id,
                    "name": instr_names.get(instr_id, instr_id),
                    "observations": r["observations"],
                    "non_compliant": r["non_compliant"],
                    "skip_rate": r["skip_rate"],
                    "status": _status(instr_id, r["skip_rate"], r["observations"], "CONVERT_TO_GATE"),
                }
            )
        print(json.dumps(report, indent=2))
        return

    # Human-readable output
    print("Instruction Skip Rate Report")
    print("=" * 72)
    print(f"{'ID':<6}{'Instruction':<22}{'Observations':>14}{'Skip Rate':>12}{'Status':>18}")
    print("-" * 72)

    for r in results:
        instr_id = r["instruction_id"]
        name = instr_names.get(instr_id, instr_id)
        skip_rate = r["skip_rate"]
        status = _status(instr_id, skip_rate, r["observations"], "CONVERT TO GATE")

        print(f"{instr_id:<6}{name:<22}{r['observations']:>14}{skip_rate:>11.1f}%{status:>17}")

    print("-" * 72)
    flagged = sum(
        1 for r in results if r["instruction_id"] in observable and r["skip_rate"] > 20 and r["observations"] >= 30
    )
    if flagged:
        print(f"{flagged} instruction(s) flagged for conversion to programmatic gates (>20% skip, 30+ obs)")
    else:
        print("No instructions flagged. Threshold: >20% skip rate over 30+ observations.")
    unmeasurable = sorted(r["instruction_id"] for r in results if r["instruction_id"] not in observable)
    if unmeasurable:
        print(
            f"NOT MEASURABLE, so not scored: {', '.join(unmeasurable)} — "
            "the recording hook cannot observe these; see hooks/instruction-compliance.py"
        )


_BASIS_LABELS = (
    "rejection_detected",
    "tool_errors_only",
    "acceptance_detected",
    "default_no_complaint",
    # C6 weak-positive: repeat dispatch, no intervening failure. Neither strong
    # feedback nor silent default-success — reported on its own line and kept
    # OUT of the silent-success share (strong + default formula unchanged).
    "repeat_dispatch_weak",
)


def _read_basis_counts() -> dict[str, int]:
    """Sum routing_outcome_basis counts per label. Best-effort: {} on any error.

    All three labels are always present (0 when unseen) so callers never
    KeyError. Table absent / unreadable (pre-v6 DB) => all zeros.
    """
    counts = {label: 0 for label in _BASIS_LABELS}
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT basis, SUM(count) AS n FROM routing_outcome_basis GROUP BY basis").fetchall()
        for row in rows:
            if row["basis"] in counts:
                counts[row["basis"]] = int(row["n"] or 0)
    except Exception:
        pass
    return counts


# ─── Counter-metrics to the fallback rate ────────────────────────────────────
#
# Fallback rate ALONE is gameable. A router told to minimize it can route
# everything to one specialist (python-general-engineer is already 27.9% of
# traffic) and score a perfect 0% with zero accuracy gain. So the fallback rate
# is only ever printed alongside three counters that such a move would blow up:
# top-2 concentration, distribution entropy, and the observed misroute /
# route-fit negative rates. Read from evidence_route_decisions (one row per
# dispatch), NOT from the aggregated learnings rows — those are one row per
# route KEY, so they cannot measure traffic share.
_FALLBACK_AGENT = "general-purpose"
# Target band. Below ~8% the router is forcing specialists it has no evidence
# for (or gaming the number); above 20% it is not routing at all. Both are
# alarms — a fallback rate can be too LOW.
_FALLBACK_BAND_LOW, _FALLBACK_BAND_HIGH = 10.0, 15.0
_FALLBACK_ALARM_LOW, _FALLBACK_ALARM_HIGH = 8.0, 20.0
_TOP2_TARGET = 50.0  # top-2 agent share; above this the "distribution" is two agents
_ROUTE_FIT_BASIS_PREFIX = "route_fit:"


def _read_agent_distribution() -> dict[str, int]:
    """Dispatches per agent from evidence_route_decisions. {} on any error."""
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT agent, COUNT(*) AS n FROM evidence_route_decisions GROUP BY agent").fetchall()
        return {row["agent"]: int(row["n"] or 0) for row in rows if row["agent"]}
    except Exception:
        return {}


def _read_route_fit_counts() -> dict[str, int]:
    """route-fit verdict counts, keyed by verdict. {} on any error/no data."""
    counts: dict[str, int] = {}
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT basis, SUM(count) AS n FROM routing_outcome_basis WHERE basis LIKE ? GROUP BY basis",
                (f"{_ROUTE_FIT_BASIS_PREFIX}%",),
            ).fetchall()
        for row in rows:
            verdict = str(row["basis"])[len(_ROUTE_FIT_BASIS_PREFIX) :]
            if verdict:
                counts[verdict] = int(row["n"] or 0)
    except Exception:
        pass
    return counts


def _read_misroute_count() -> int:
    """Total recorded misroutes (scripts/record-misroute.py rows). 0 on error."""
    try:
        rows = query_learnings(
            topic="routing",
            category="misroute",
            min_confidence=0.0,
            limit=10000,
            exclude_graduated=False,
            exclude_test_sources=True,
        )
        return sum(int(r.get("observation_count") or 1) for r in rows)
    except Exception:
        return 0


def _fallback_band(pct: float) -> str:
    """Label one fallback rate against the target band."""
    if pct > _FALLBACK_ALARM_HIGH:
        return "ALARM-HIGH"
    if pct < _FALLBACK_ALARM_LOW:
        return "ALARM-LOW"
    if _FALLBACK_BAND_LOW <= pct <= _FALLBACK_BAND_HIGH:
        return "IN BAND"
    return "WATCH"


def _routing_shape(dist: dict[str, int]) -> dict:
    """Fallback rate + concentration + entropy for one agent distribution.

    Entropy is Shannon over the agent traffic shares, in bits. It is the
    counter-metric that cannot be gamed by shifting traffic: moving every
    fallback onto ONE specialist lowers the fallback rate and lowers entropy at
    the same time, so the trade shows up instead of reading as a win.
    `effective_agents` (2**H) restates it as "this traffic behaves like N evenly
    used agents" — comparable across different agent-roster sizes.
    """
    total = sum(dist.values())
    if not total:
        return {"dispatch_total": 0}
    import math

    ordered = sorted(dist.items(), key=lambda kv: (-kv[1], kv[0]))
    top2 = ordered[:2]
    entropy = -sum((n / total) * math.log2(n / total) for n in dist.values() if n > 0)
    max_entropy = math.log2(len(dist)) if len(dist) > 1 else 0.0
    fallback_n = dist.get(_FALLBACK_AGENT, 0)
    fallback_pct = fallback_n / total * 100
    return {
        "dispatch_total": total,
        "distinct_agents": len(dist),
        "fallback_count": fallback_n,
        "fallback_rate_pct": round(fallback_pct, 1),
        "fallback_band": _fallback_band(fallback_pct),
        "top2_agents": [name for name, _ in top2],
        "top2_concentration_pct": round(sum(n for _, n in top2) / total * 100, 1),
        "top2_target_pct": _TOP2_TARGET,
        "agent_entropy_bits": round(entropy, 2),
        "agent_entropy_max_bits": round(max_entropy, 2),
        "agent_entropy_normalized": round(entropy / max_entropy, 2) if max_entropy else None,
        "effective_agents": round(2**entropy, 1),
    }


def _route_fit_summary(counts: dict[str, int]) -> dict:
    """Totals and the negative rate for the route-fit verdicts."""
    total = sum(counts.values())
    negatives = total - counts.get("ok", 0)
    return {
        "route_fit_counts": counts,
        "route_fit_total": total,
        "route_fit_negative": negatives,
        "route_fit_negative_rate_pct": round(negatives / total * 100, 1) if total else None,
    }


def _print_routing_shape(shape: dict, fit: dict, misroutes: int) -> None:
    """Print the fallback rate together with every counter-metric."""
    total = shape.get("dispatch_total", 0)
    if not total:
        print("Fallback rate: no dispatch rows yet (evidence_route_decisions is empty)")
        return
    print(
        f"Fallback rate: {shape['fallback_count']}/{total} dispatches went to "
        f"{_FALLBACK_AGENT} ({shape['fallback_rate_pct']:.1f}%) — {shape['fallback_band']}"
    )
    print(
        f"  target band {_FALLBACK_BAND_LOW:.0f}-{_FALLBACK_BAND_HIGH:.0f}%; "
        f"alarm above {_FALLBACK_ALARM_HIGH:.0f}%; alarm below {_FALLBACK_ALARM_LOW:.0f}%"
    )
    print(
        f"Top-2 agent concentration: {shape['top2_concentration_pct']:.1f}% "
        f"({', '.join(shape['top2_agents'])}) — target below {_TOP2_TARGET:.0f}%"
    )
    norm = shape["agent_entropy_normalized"]
    norm_text = f", normalized {norm:.2f}" if norm is not None else ""
    print(
        f"Agent distribution entropy: {shape['agent_entropy_bits']:.2f} bits of "
        f"{shape['agent_entropy_max_bits']:.2f} max{norm_text} across "
        f"{shape['distinct_agents']} agents (effective agents {shape['effective_agents']:.1f})"
    )
    print(f"Misroute rate: {misroutes}/{total} dispatches reported a misroute ({misroutes / total * 100:.1f}%)")
    fit_total = fit["route_fit_total"]
    if fit_total:
        print(
            f"Route-fit negatives: {fit['route_fit_negative']}/{fit_total} verdicts "
            f"({fit['route_fit_negative_rate_pct']:.1f}%) — "
            f"{', '.join(f'{v} {n}' for v, n in sorted(fit['route_fit_counts'].items()))}"
        )
    else:
        print("Route-fit negatives: no route-fit verdicts yet (banner lands with the next dispatches)")


def cmd_route_health(args: argparse.Namespace) -> None:
    """Display a quick health summary of routing entries."""
    init_db()
    as_json = getattr(args, "json", False)
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        min_confidence=0.0,
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )

    total = len(results)
    if total == 0:
        if as_json:
            print(json.dumps({"total": 0, "entries_with_outcomes": 0}, indent=2))
        else:
            print("No routing entries found.")
        return

    baseline = sum(1 for r in results if r["success_count"] == 0 and r["failure_count"] == 0)
    boosted = sum(1 for r in results if r["success_count"] > 0)
    decayed_count = sum(1 for r in results if r["failure_count"] > 0)
    has_outcome = total - baseline
    pct = has_outcome / total * 100
    status = "CLOSED" if pct >= 50 else "OPEN"
    no_outcome_pct = baseline / total * 100

    # Outcome-basis split (ADR: silent-failure-outcome-quality). strong-feedback
    # = an observed signal scored the outcome; default-success = success on
    # silence (upper bound on silent success, NOT confirmed silent failures).
    basis = _read_basis_counts()
    strong = basis["rejection_detected"] + basis["tool_errors_only"] + basis["acceptance_detected"]
    default_success = basis["default_no_complaint"]
    # repeat_dispatch_weak (C6) is reported but stays OUT of strong/default and
    # the silent-success share: it is an inferred signal, not user feedback and
    # not silence-scored success. Formula unchanged from pre-C6.
    basis_total = strong + default_success
    silent_share = (default_success / basis_total) if basis_total else None

    # Correction rate (ADR: correction-harvesting). Share of routed sessions that
    # drew correction language, plus corrections with no concurrent /do route.
    # Read-only: adds informational lines, changes no boost/decay, no schema.
    corrections = query_learnings(
        topic="user-correction",
        category="correction",
        min_confidence=0.65,
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=True,
    )
    corr_sessions = {c["session_id"] for c in corrections if c.get("session_id")}
    routed_sessions = {r["session_id"] for r in results if r.get("session_id")}
    routed_with_corr = len(corr_sessions & routed_sessions)
    pct_corr = (routed_with_corr / len(routed_sessions) * 100) if routed_sessions else 0.0
    unattributed_corr = len(corr_sessions - routed_sessions)

    # Fallback rate + its counter-metrics. Never report one without the others:
    # the fallback rate on its own is minimized by routing everything to a
    # single agent, which these three make visible.
    shape = _routing_shape(_read_agent_distribution())
    fit = _route_fit_summary(_read_route_fit_counts())
    misroutes = _read_misroute_count()
    dispatch_total = shape.get("dispatch_total", 0)
    misroute_rate = round(misroutes / dispatch_total * 100, 1) if dispatch_total else None

    if as_json:
        print(
            json.dumps(
                {
                    "total": total,
                    "entries_with_outcomes": has_outcome,
                    "outcome_pct": round(pct, 1),
                    "baseline": baseline,
                    "boosted": boosted,
                    "decayed": decayed_count,
                    "feedback_loop": status,
                    "basis": basis,
                    "strong_feedback": strong,
                    "default_success": default_success,
                    "silent_success_share": silent_share,
                    "governed_path_coverage": round(pct, 1),
                    "correction_rate_pct": round(pct_corr, 1),
                    "routed_sessions_with_correction": routed_with_corr,
                    "routed_sessions": len(routed_sessions),
                    "unattributed_corrections": unattributed_corr,
                    **shape,
                    **fit,
                    "misroute_count": misroutes,
                    "misroute_rate_pct": misroute_rate,
                },
                indent=2,
            )
        )
        return

    print(f"Route Health: {has_outcome}/{total} entries have outcomes ({pct:.0f}%)")
    print(f"Confidence: {baseline} at baseline | {boosted} boosted | {decayed_count} decayed")
    print(f"Feedback loop: {status} ({no_outcome_pct:.0f}% entries have no outcome data)")

    if basis_total == 0:
        print("Outcome basis: no basis data yet")
    else:
        print(f"Outcome basis: {strong} strong-feedback vs {default_success} default-success")
        print(f"  rejection_detected   {basis['rejection_detected']}")
        print(f"  tool_errors_only     {basis['tool_errors_only']}")
        print(f"  acceptance_detected  {basis['acceptance_detected']}")
        print(f"  default_no_complaint {basis['default_no_complaint']}")
        print(f"  repeat_dispatch_weak {basis['repeat_dispatch_weak']} (weak-positive; outside the share below)")
        print(f"Silent-success share: {silent_share * 100:.0f}% of scored outcomes ({default_success}/{basis_total})")
    print(f"Governed-path coverage: {has_outcome}/{total} routing rows carry a finalized outcome ({pct:.0f}%)")
    print(
        f"Correction rate: {routed_with_corr}/{len(routed_sessions)} "
        f"routed sessions drew correction language ({pct_corr:.0f}%)"
    )
    print(f"Unattributed corrections: {unattributed_corr} (correction with no concurrent /do route)")
    _print_routing_shape(shape, fit, misroutes)


def _print_freq_table(records: list[dict[str, str | int]], label: str, key_fn: object) -> None:
    """Print a frequency table sorted by count descending."""
    from collections import Counter

    counts = Counter(key_fn(r) for r in records)  # type: ignore[operator]
    total = sum(counts.values())
    print(f"{label} Frequency ({total} total routes)")
    print(f"{'─' * 50}")
    for name, count in counts.most_common(20):
        bar = "█" * min(count, 30)
        print(f"  {name:35s} {count:>4} {bar}")


def cmd_learn(args):
    """Record a skill- or agent-scoped learning with minimal friction."""
    import hashlib

    # Resolve value from positional arg or --value-file.
    if getattr(args, "value_file", None):
        value = Path(args.value_file).read_text(encoding="utf-8")
    else:
        value = args.value
    # Auto-generate key from value hash
    key = hashlib.sha256(value.encode()).hexdigest()[:12]

    # Determine topic from --skill or --agent
    if args.skill:
        topic = f"skill:{args.skill}"
    elif args.agent:
        topic = f"agent:{args.agent}"
    else:
        topic = args.topic or "general"

    result = record_learning(
        topic=topic,
        key=key,
        value=value,
        category="gotcha",
        confidence=0.7,
        tags=[args.skill or args.agent or "general"],
        source="manual:learn",
        source_detail=None,
        project_path=args.project_path,
    )
    action = "Updated" if not result["is_new"] else "Recorded"
    print(f"{action}: [{topic}] {value[:80]}... (confidence: {result['confidence']:.2f})")


def cmd_purge(args):
    """Delete all entries matching a topic."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM learnings WHERE topic = ?", (args.topic,))
        count = cursor.rowcount
        conn.commit()
    print(f"Purged {count} entries with topic '{args.topic}'")


def cmd_migrate(args):
    """Run all migrations: import from patterns.db and retro markdown."""
    init_db()
    print(f"Database initialized at: {get_db_path()}")

    # Import from patterns.db if it exists
    patterns_path = Path.home() / ".claude" / "learning" / "patterns.db"
    if patterns_path.exists():
        result = import_from_patterns_db(str(patterns_path))
        print(f"patterns.db: {result['imported']} imported, {result['skipped']} skipped")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  error: {e}")
    else:
        print("patterns.db: not found, skipping")

    # Import from retro L2 if it exists
    retro_dir = Path.home() / ".claude" / "retro"
    if (retro_dir / "L2").is_dir():
        result = import_from_retro(str(retro_dir))
        print(f"retro L2: {result['imported']} imported, {result['skipped']} skipped")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  error: {e}")
    else:
        print("retro L2: not found, skipping")

    # Also check repo retro
    repo_retro = _repo_root / "retro"
    if (repo_retro / "L2").is_dir() and repo_retro != retro_dir:
        result = import_from_retro(str(repo_retro))
        print(f"repo retro L2: {result['imported']} imported, {result['skipped']} skipped")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  error: {e}")

    stats = get_stats()
    print(
        f"\nPost-migration: {stats['total_learnings']} total learnings, "
        f"{stats['high_confidence']} high confidence, "
        f"{stats['sessions_tracked']} sessions"
    )


def cmd_record_review_fp(args):
    """Record a structured review false positive with full metadata."""
    value = (
        f"finding: {args.finding} "
        f"| reviewer: {args.reviewer} "
        f"| reason: {args.reason} "
        f"| source: {args.source_file or 'unknown'}"
    )
    tags = ["false-positive"]
    if args.reviewer:
        tags.append(args.reviewer)

    result = record_learning(
        topic="review-false-positive",
        key=args.finding[:50].lower().strip().replace(" ", "-"),
        value=value,
        category="review",
        confidence=0.70,
        tags=tags,
        source=args.source or "cli:record-review-fp",
        source_detail=args.source_detail,
        project_path=args.project_path,
    )
    action = "Updated" if not result["is_new"] else "Recorded"
    print(
        f"{action}: review-false-positive/{result['key']} "
        f"(reviewer: {args.reviewer}, confidence: {result['confidence']:.2f}, "
        f"observations: {result['observation_count']})"
    )


def cmd_review_fps(args):
    """List accumulated review false positives, grouped by reviewer agent."""
    init_db()
    results = query_learnings(
        topic="review-false-positive",
        category="review",
        min_confidence=args.min_confidence,
        exclude_graduated=not args.include_graduated,
        order_by="last_seen DESC",
        limit=args.limit,
    )

    if args.json:
        # Group by reviewer for JSON output
        grouped = {}
        for r in results:
            reviewer = _extract_reviewer_from_value(r.get("value", ""))
            grouped.setdefault(reviewer, []).append(r)
        print(json.dumps(grouped, indent=2, default=str))
        return

    if not results:
        print("No review false positives recorded.")
        return

    # Group by reviewer
    grouped = {}
    for r in results:
        reviewer = _extract_reviewer_from_value(r.get("value", ""))
        grouped.setdefault(reviewer, []).append(r)

    for reviewer, entries in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        print(f"\n=== {reviewer} ({len(entries)} false positive(s)) ===")
        for r in entries:
            obs = f" [{r['observation_count']}x]" if r["observation_count"] > 1 else ""
            print(f"  [{r['confidence']:.2f}]{obs} {r['key']}")
            # Extract finding and reason from pipe-delimited value
            parts = _parse_pipe_value(r.get("value", ""))
            if parts.get("finding"):
                print(f"    finding: {parts['finding'][:100]}")
            if parts.get("reason"):
                print(f"    reason:  {parts['reason']}")
            if parts.get("source") and parts["source"] != "unknown":
                print(f"    source:  {parts['source']}")
            print(f"    last seen: {r.get('last_seen', 'unknown')}")


def _extract_reviewer_from_value(value: str) -> str:
    """Extract reviewer name from pipe-delimited value string."""
    parts = _parse_pipe_value(value)
    return parts.get("reviewer", "unknown")


# Key prefix routing-decision-recorder.py uses for stack-usage rows (must
# match hooks/routing-decision-recorder.py's _STACK_USAGE_KEY_PREFIX).
STACK_USAGE_KEY_PREFIX = "stack-usage:"
_STACK_USAGE_BACKFILL_MARKER = f"{STACK_USAGE_KEY_PREFIX}_backfilled"


def _collect_stack_usage() -> list[dict[str, object]]:
    """Read every stack-usage row into {skill, times_stacked, last_seen}, most-frequent first."""
    init_db()
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )
    rows = []
    for r in results:
        key = str(r["key"])
        if not key.startswith(STACK_USAGE_KEY_PREFIX) or key == _STACK_USAGE_BACKFILL_MARKER:
            continue
        rows.append(
            {
                "skill": key[len(STACK_USAGE_KEY_PREFIX) :],
                "times_stacked": r.get("observation_count", 1),
                "last_seen": r.get("last_seen"),
            }
        )
    rows.sort(key=lambda r: -int(r["times_stacked"]))
    return rows


def cmd_stack_usage(args: argparse.Namespace) -> None:
    """List enhancement skills seen in `[do-route]` `stack={...}` tokens.

    One row per enhancement skill: times stacked (observation_count) and last
    seen, most-frequent first — the routing-table utilization audit's view
    onto stacked skills (voice-validator, joy-check, etc.) that the primary
    per-dispatch `route-stats`/`route-weights` rows never surface.
    """
    rows = _collect_stack_usage()

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        print(
            "No stack usage recorded yet. Data accumulates once a [do-route] "
            "marker carries a stack={...} token; run backfill-stack-usage to "
            "import any stack data already in route-events.jsonl."
        )
        return

    print(f"Stack Usage ({len(rows)} enhancement skill(s) seen)")
    print(f"{'Skill':<40} {'Times Stacked':>14}  Last Seen")
    print(f"{'─' * 40} {'─' * 14}  {'─' * 19}")
    for r in rows:
        print(f"{r['skill']:<40} {r['times_stacked']:>14}  {r['last_seen']}")


def cmd_backfill_stack_usage(args: argparse.Namespace) -> None:
    """One-shot: aggregate historical stack={...} data from route-events.jsonl.

    routing-decision-recorder.py only started writing stack-usage rows once
    this feature shipped; route-events.jsonl may already carry older DECISION
    events with a `stack` field from before that. This replays those events
    through the same per-skill counting the live hook uses, so historical
    stacking isn't invisible to the query surface.

    Idempotent via a marker row: re-running without --force is a no-op (a
    second pass would double-count the same historical events, since each
    event bump is indistinguishable from a fresh live dispatch).
    """
    init_db()
    with get_connection() as conn:
        already = conn.execute(
            "SELECT value FROM learnings WHERE topic = 'routing' AND key = ?",
            (_STACK_USAGE_BACKFILL_MARKER,),
        ).fetchone()
    if already and not args.force:
        print(f"Already backfilled ({already['value']}). Pass --force to re-run (will double-count).")
        return

    try:
        from route_events import events_path
    except ImportError:
        print(
            "route_events not found; run from repo root or ensure hooks/lib is on PYTHONPATH.",
            file=sys.stderr,
        )
        return

    path = events_path()
    if not path.exists():
        print(f"No route-events.jsonl found at {path}; nothing to backfill.")
        record_learning(
            topic="routing",
            key=_STACK_USAGE_BACKFILL_MARKER,
            value="backfilled: 0 events (route-events.jsonl absent)",
            category="effectiveness",
            source="cli:backfill-stack-usage",
        )
        return

    events_with_stack = 0
    skill_increments = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "decision":
                continue
            stack = event.get("stack")
            if not stack:
                continue
            events_with_stack += 1
            for skill in dict.fromkeys(stack):
                if not skill:
                    continue
                record_learning(
                    topic="routing",
                    key=f"{STACK_USAGE_KEY_PREFIX}{skill}",
                    value=f"stack-usage: skill={skill}",
                    category="effectiveness",
                    tags=["stack-usage", skill],
                    source="cli:backfill-stack-usage",
                )
                skill_increments += 1

    record_learning(
        topic="routing",
        key=_STACK_USAGE_BACKFILL_MARKER,
        value=f"backfilled: {events_with_stack} historical decision events, {skill_increments} skill increments",
        category="effectiveness",
        source="cli:backfill-stack-usage",
    )
    print(
        f"Backfill complete: {events_with_stack} historical decision event(s) with stack data, "
        f"{skill_increments} skill-usage increment(s) recorded."
    )


def _non_negative_int(value: str) -> int:
    """Validate that an argparse integer value is non-negative.

    Args:
        value: String value from argparse to convert and validate.

    Returns:
        The parsed non-negative integer.

    Raises:
        argparse.ArgumentTypeError: If the value is negative.
    """
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError(f"Value must be >= 0, got {n}")
    return n


def main():
    parser = argparse.ArgumentParser(description="Learning Database CLI — manage the unified knowledge store")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # record
    p_record = subparsers.add_parser("record", help="Record a learning")
    p_record.add_argument("topic", help="Domain category (e.g., go-patterns, debugging)")
    p_record.add_argument("key", help="Short identifier (e.g., mutex-over-atomics)")
    p_record.add_argument("value", help="Learning content")
    p_record.add_argument(
        "--category",
        default="design",
        choices=["error", "pivot", "review", "design", "debug", "gotcha", "effectiveness", "misroute"],
        help="Learning category",
    )
    p_record.add_argument("--confidence", type=float, default=None)
    p_record.add_argument("--tags", help="Comma-separated tags")
    p_record.add_argument("--source", help="Source identifier")
    p_record.add_argument("--source-detail", help="Additional source context")
    p_record.add_argument("--project-path", help="Project path")
    p_record.set_defaults(func=cmd_record)

    # query
    p_query = subparsers.add_parser("query", help="Query learnings")
    p_query.add_argument("--topic", help="Filter by topic")
    p_query.add_argument("--category", help="Filter by category")
    p_query.add_argument("--tags", help="Filter by tags (comma-separated, matches ANY)")
    p_query.add_argument("--min-confidence", type=float, default=0.0)
    p_query.add_argument("--include-graduated", action="store_true")
    p_query.add_argument("--order-by", default="confidence DESC")
    p_query.add_argument("--limit", type=int, default=20)
    p_query.add_argument("--format", choices=["human", "json"], default="human")
    p_query.set_defaults(func=cmd_query)

    # search
    p_search = subparsers.add_parser("search", help="Full-text search with BM25 ranking")
    p_search.add_argument("query", help="FTS5 query (e.g. 'circuit breaker retry', 'goroutine OR channel')")
    p_search.add_argument("--min-confidence", type=float, default=0.0)
    p_search.add_argument("--include-graduated", action="store_true")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--format", choices=["human", "json"], default="human")
    p_search.set_defaults(func=cmd_search)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show learning statistics")
    p_stats.add_argument("--format", choices=["human", "json"], default="human")
    p_stats.set_defaults(func=cmd_stats)

    # export
    p_export = subparsers.add_parser("export", help="Export learnings as markdown")
    p_export.add_argument("--format", choices=["l1", "l2", "full"], default="l2")
    p_export.add_argument("--output-dir", help="Directory for L2 files")
    p_export.set_defaults(func=cmd_export)

    # import
    p_import = subparsers.add_parser("import", help="Import from legacy stores")
    p_import.add_argument("--from-retro", help="Path to retro/ directory")
    p_import.add_argument("--from-patterns", help="Path to patterns.db")
    p_import.set_defaults(func=cmd_import)

    # graduate
    p_grad = subparsers.add_parser("graduate", help="Mark entry as graduated")
    p_grad.add_argument("topic")
    p_grad.add_argument("key")
    p_grad.add_argument("target", help="Target (e.g., agent:golang-general-engineer)")
    p_grad.set_defaults(func=cmd_graduate)

    # boost
    p_boost = subparsers.add_parser("boost", help="Boost confidence")
    p_boost.add_argument("topic")
    p_boost.add_argument("key")
    p_boost.add_argument("--delta", type=float, default=0.10)
    p_boost.set_defaults(func=cmd_boost)

    # decay
    p_decay = subparsers.add_parser("decay", help="Decay confidence")
    p_decay.add_argument("topic")
    p_decay.add_argument("key")
    p_decay.add_argument("--delta", type=float, default=0.10)
    p_decay.set_defaults(func=cmd_decay)

    # prune — filtered delete, dry-run by default
    p_prune = subparsers.add_parser("prune", help="Filtered prune of learnings (dry-run default; --apply deletes)")
    p_prune.add_argument("--category", help="Filter by category (e.g., error)")
    p_prune.add_argument("--topic", help="Filter by topic (e.g., unknown)")
    p_prune.add_argument("--max-confidence", type=float, default=None, help="Match rows with confidence <= N")
    p_prune.add_argument("--below-confidence", type=float, default=None, help="Deprecated alias for --max-confidence")
    p_prune.add_argument("--older-than", type=int, default=None, help="Match rows with last_seen older than N days")
    p_prune_mode = p_prune.add_mutually_exclusive_group()
    p_prune_mode.add_argument("--dry-run", action="store_true", help="Preview counts (default)")
    p_prune_mode.add_argument("--apply", action="store_true", help="Delete matched rows, then VACUUM")
    p_prune.set_defaults(func=cmd_prune)

    # stale (show stale entries)
    p_stale = subparsers.add_parser("stale", help="Show entries that appear stale")
    p_stale.add_argument("--min-age-days", type=int, default=30, help="Minimum age in days (default: 30)")
    p_stale.add_argument("--json", action="store_true", help="Output as JSON")
    p_stale.set_defaults(func=cmd_stale)

    # stale-prune (archive stale entries)
    p_stale_prune = subparsers.add_parser("stale-prune", help="Archive stale entries to learning_archive table")
    p_stale_prune.add_argument("--min-age-days", type=int, default=30, help="Minimum age in days (default: 30)")
    p_stale_prune_group = p_stale_prune.add_mutually_exclusive_group(required=True)
    p_stale_prune_group.add_argument("--dry-run", action="store_true", help="Preview what would be archived")
    p_stale_prune_group.add_argument("--confirm", action="store_true", help="Actually archive stale entries")
    p_stale_prune.set_defaults(func=cmd_stale_prune)

    # learn (low-friction skill-scoped recording)
    p_learn = subparsers.add_parser("learn", help="Record a skill/agent-scoped learning (one-liner)")
    p_learn_value = p_learn.add_mutually_exclusive_group(required=True)
    p_learn_value.add_argument("value", nargs="?", default=None, help="The learning content (one sentence)")
    p_learn_value.add_argument(
        "--value-file", help="Path to a file containing the learning content (avoids shell-splicing)"
    )
    p_learn.add_argument("--skill", help="Skill name (sets topic to skill:{name})")
    p_learn.add_argument("--agent", help="Agent name (sets topic to agent:{name})")
    p_learn.add_argument("--topic", help="Custom topic (fallback if no --skill/--agent)")
    p_learn.add_argument("--project-path", help="Project path")
    p_learn.set_defaults(func=cmd_learn)

    # purge (delete by topic)
    p_purge = subparsers.add_parser("purge", help="Delete all entries matching a topic")
    p_purge.add_argument("--topic", required=True, help="Topic to purge (e.g., worktree-branches)")
    p_purge.set_defaults(func=cmd_purge)

    # migrate
    p_migrate = subparsers.add_parser("migrate", help="Import from all legacy stores")
    p_migrate.set_defaults(func=cmd_migrate)

    # record-activation
    p_rec_act = subparsers.add_parser("record-activation", help="Record a learning activation")
    p_rec_act.add_argument("topic", help="Learning topic")
    p_rec_act.add_argument("key", help="Learning key")
    p_rec_act.add_argument("--session", required=True, help="Session ID")
    p_rec_act.add_argument("--outcome", default="success", help="Outcome (success/failure)")
    p_rec_act.set_defaults(func=cmd_record_activation)

    # record-waste
    p_rec_waste = subparsers.add_parser("record-waste", help="Record wasted tokens from a failure")
    p_rec_waste.add_argument("--session", required=True, help="Session ID")
    p_rec_waste.add_argument("--tokens", type=_non_negative_int, required=True, help="Number of wasted tokens")
    p_rec_waste.set_defaults(func=cmd_record_waste)

    # record-session
    p_rec_sess = subparsers.add_parser("record-session", help="Create or update a session_stats entry")
    p_rec_sess.add_argument("--session", required=True, help="Session ID")
    p_rec_sess.add_argument("--had-retro", action="store_true", help="Session had retro knowledge injected")
    p_rec_sess.add_argument("--failures", type=_non_negative_int, default=0, help="Number of failures")
    p_rec_sess.add_argument("--waste-tokens", type=_non_negative_int, default=0, help="Wasted tokens")
    p_rec_sess.set_defaults(func=cmd_record_session_stats)

    # roi
    p_roi = subparsers.add_parser("roi", help="Compute and display learning ROI report")
    p_roi.add_argument("--json", action="store_true", help="Output as JSON")
    p_roi.set_defaults(func=cmd_roi)

    # route-stats
    p_route_stats = subparsers.add_parser("route-stats", help="Show routing decision statistics")
    p_route_stats.add_argument(
        "--by",
        required=True,
        choices=["agent", "skill", "force-route", "errors", "override", "week", "day"],
        help="Dimension to aggregate by (week|day read telemetry_runs time-series)",
    )
    p_route_stats.add_argument("--json", action="store_true", help="Also output raw JSON")
    p_route_stats.set_defaults(func=cmd_route_stats)

    # route-weights
    p_route_weights = subparsers.add_parser(
        "route-weights", help="Emit routing weights as JSON (read-only) for health-aware re-rank"
    )
    p_route_weights.add_argument("--json", action="store_true", help="Output as JSON (only supported format)")
    p_route_weights.set_defaults(func=cmd_route_weights)

    # review-roi — per-tier review cost/findings ROI (report-only).
    p_review_roi = subparsers.add_parser("review-roi", help="Per-tier review cost/findings ROI")
    p_review_roi.add_argument("--json", action="store_true", help="Output as JSON")
    p_review_roi.set_defaults(func=cmd_review_roi)

    # route-delta — "did that change help?" cohort comparison over telemetry_runs.
    p_route_delta = subparsers.add_parser("route-delta", help="Compare two cohorts (git-SHA or date) of telemetry runs")
    p_route_delta.add_argument("--from", dest="from_ref", required=True, help="Cohort A: git-SHA prefix or date prefix")
    p_route_delta.add_argument("--to", dest="to_ref", required=True, help="Cohort B: git-SHA prefix or date prefix")
    p_route_delta.add_argument("--key", help="Scope to one route key (agent:skill)")
    p_route_delta.add_argument(
        "--metric", choices=["error", "tokens"], default="error", help="error rate (default) or avg tokens"
    )
    p_route_delta.add_argument("--json", action="store_true", help="Output as JSON")
    p_route_delta.set_defaults(func=cmd_route_delta)

    # telemetry-query — read telemetry_runs rows and ablation compatibility fallbacks.
    p_tquery = subparsers.add_parser(
        "telemetry-query", help="Query telemetry_runs and saved ablation fallback rows by topic"
    )
    p_tquery.add_argument("--topic", required=True, help="Filter by topic (e.g., eval:evals/<dir>)")
    p_tquery.add_argument("--git-sha", dest="git_sha", help="Filter to a git-SHA prefix")
    p_tquery.add_argument("--key", help="Filter to one key (e.g., <skill>@<head>:<arm>)")
    p_tquery.add_argument("--limit", type=int, default=50)
    p_tquery.add_argument("--format", choices=["human", "json"], default="human")
    p_tquery.set_defaults(func=cmd_telemetry_query)

    # evidence-recent — recent queryable agent evidence rows.
    p_e_recent = subparsers.add_parser("evidence-recent", help="List recent agent evidence events")
    p_e_recent.add_argument("--limit", type=int, default=50)
    p_e_recent.add_argument("--session", help="Filter by session id")
    p_e_recent.add_argument("--type", help="Filter by event type")
    p_e_recent.add_argument("--route-key", help="Filter by route key (agent:skill)")
    p_e_recent.add_argument("--agent", help="Filter by agent")
    p_e_recent.add_argument("--skill", help="Filter by skill")
    p_e_recent.add_argument("--failures", action="store_true", help="Only failed events")
    p_e_recent.add_argument("--json", action="store_true", help="Output as JSON")
    p_e_recent.set_defaults(func=cmd_evidence_recent)

    # evidence-route-context — route-specific decision history and failures.
    p_e_route = subparsers.add_parser("evidence-route-context", help="Show local evidence for one route")
    p_e_route.add_argument("route_key", help="Route key (agent:skill)")
    p_e_route.add_argument("--limit", type=int, default=20)
    p_e_route.add_argument("--json", action="store_true", help="Output as JSON")
    p_e_route.set_defaults(func=cmd_evidence_route_context)

    # evidence-file-history — events touching a file/path target.
    p_e_file = subparsers.add_parser("evidence-file-history", help="Show evidence events for a target path")
    p_e_file.add_argument("target", help="File path or target text")
    p_e_file.add_argument("--limit", type=int, default=50)
    p_e_file.add_argument("--json", action="store_true", help="Output as JSON")
    p_e_file.set_defaults(func=cmd_evidence_file_history)

    # evidence-failures — recent failed evidence rows.
    p_e_failures = subparsers.add_parser("evidence-failures", help="List recent failed evidence events")
    p_e_failures.add_argument("--limit", type=int, default=50)
    p_e_failures.add_argument("--route-key", help="Filter by route key")
    p_e_failures.add_argument("--agent", help="Filter by agent")
    p_e_failures.add_argument("--skill", help="Filter by skill")
    p_e_failures.add_argument("--json", action="store_true", help="Output as JSON")
    p_e_failures.set_defaults(func=cmd_evidence_failures)

    # evidence-decide — compact advisory derived from route evidence.
    p_e_decide = subparsers.add_parser("evidence-decide", help="Summarize the advisory state for one route")
    p_e_decide.add_argument("route_key", help="Route key (agent:skill)")
    p_e_decide.add_argument("--json", action="store_true", help="Output as JSON")
    p_e_decide.set_defaults(func=cmd_evidence_decide)

    # record-routing-outcome
    p_rro = subparsers.add_parser("record-routing-outcome", help="Record routing decision outcome")
    p_rro.add_argument("agent_skill", help="Routing key (e.g., golang-general-engineer:go-patterns)")
    p_rro_group = p_rro.add_mutually_exclusive_group(required=True)
    p_rro_group.add_argument("--success", action="store_true", help="Route succeeded")
    p_rro_group.add_argument("--failure", action="store_true", help="Route failed")
    p_rro.add_argument("--reason", help="Reason for outcome (appended to value)")
    p_rro.set_defaults(func=cmd_record_routing_outcome)

    # route-failure — orchestrator-reported routing failure (ADR: orchestrator-reported-route-failures)
    p_rf = subparsers.add_parser("route-failure", help="Record an orchestrator-reported routing failure")
    p_rf.add_argument("agent_skill", help="Routing key (e.g., golang-general-engineer:go-patterns)")
    p_rf_reason = p_rf.add_mutually_exclusive_group(required=True)
    p_rf_reason.add_argument("--reason", help="Why the route failed (recorded with the event)")
    p_rf_reason.add_argument(
        "--reason-file", help="Path to a file containing the failure reason (avoids shell-splicing)"
    )
    p_rf.add_argument(
        "--routing-relevant",
        dest="routing_relevant",
        required=True,
        choices=["yes", "no"],
        help="yes => decay the pair + log event; no => log event only, no decay",
    )
    p_rf.add_argument("--session", help="Session ID (with --marker, the idempotence dispatch key)")
    p_rf.add_argument("--marker", help="Dispatch marker (with --session, the idempotence dispatch key)")
    p_rf.set_defaults(func=cmd_route_failure)

    # backfill-routing-outcomes
    p_backfill = subparsers.add_parser(
        "backfill-routing-outcomes", help="Retroactively score routing entries from existing data"
    )
    p_backfill.set_defaults(func=cmd_backfill_routing_outcomes)

    # skip-rate
    p_skip_rate = subparsers.add_parser("skip-rate", help="Show instruction skip-rate report")
    p_skip_rate.add_argument("--json", action="store_true", help="Output as JSON")
    p_skip_rate.add_argument("--include-test", action="store_true", help="Ignored (kept for backward compat)")
    p_skip_rate.set_defaults(func=cmd_skip_rate)

    # route-health
    p_route_health = subparsers.add_parser("route-health", help="Quick routing feedback loop health check")
    p_route_health.add_argument("--json", action="store_true", help="Output as JSON")
    p_route_health.set_defaults(func=cmd_route_health)

    # record-review-fp (structured review false-positive recording)
    p_rrfp = subparsers.add_parser("record-review-fp", help="Record a review false positive with full metadata")
    p_rrfp.add_argument("--reviewer", required=True, help="Reviewer agent name (e.g., reviewer-code)")
    p_rrfp.add_argument("--finding", required=True, help="The review finding text that was wrong")
    p_rrfp.add_argument("--reason", required=True, help="Why the finding was judged wrong")
    p_rrfp.add_argument("--source-file", help="Source file or skill the finding was about")
    p_rrfp.add_argument("--source", help="Source identifier (default: cli:record-review-fp)")
    p_rrfp.add_argument("--source-detail", help="Additional source context")
    p_rrfp.add_argument("--project-path", help="Project path")
    p_rrfp.set_defaults(func=cmd_record_review_fp)

    # review-fps (list false positives per reviewer)
    p_rfps = subparsers.add_parser("review-fps", help="List review false positives grouped by reviewer agent")
    p_rfps.add_argument("--min-confidence", type=float, default=0.0, help="Minimum confidence threshold")
    p_rfps.add_argument("--include-graduated", action="store_true", help="Include graduated entries")
    p_rfps.add_argument("--limit", type=int, default=100, help="Maximum entries to return")
    p_rfps.add_argument("--json", action="store_true", help="Output as JSON")
    p_rfps.set_defaults(func=cmd_review_fps)

    # stack-usage (per-enhancement-skill utilization from [do-route] stack={...})
    p_stack_usage = subparsers.add_parser(
        "stack-usage", help="List enhancement skills seen stacked, with times stacked + last seen"
    )
    p_stack_usage.add_argument("--json", action="store_true", help="Output as JSON")
    p_stack_usage.set_defaults(func=cmd_stack_usage)

    # backfill-stack-usage (one-shot import from route-events.jsonl)
    p_backfill_stack = subparsers.add_parser(
        "backfill-stack-usage", help="One-shot: import historical stack={...} data from route-events.jsonl"
    )
    p_backfill_stack.add_argument("--force", action="store_true", help="Re-run even if already backfilled")
    p_backfill_stack.set_defaults(func=cmd_backfill_stack_usage)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
