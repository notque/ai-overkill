#!/usr/bin/env python3
"""Validate learning database effectiveness with concrete health metrics.

Measures feedback loop closure, confidence distribution, activation coverage,
staleness, category health, and produces a composite effectiveness score (0-100).

Usage:
    python3 scripts/validate-learning-effectiveness.py
    python3 scripts/validate-learning-effectiveness.py --json
    python3 scripts/validate-learning-effectiveness.py --verbose
    python3 scripts/validate-learning-effectiveness.py --section routing
    python3 scripts/validate-learning-effectiveness.py --section confidence --json

Exit codes:
    0 - Effectiveness score >= 50
    1 - Effectiveness score < 50
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add repo hooks/lib for learning_db_v2 import
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

from learning_db_v2 import get_connection, init_db

# ---------------------------------------------------------------------------
# Section: Routing Feedback Loop Health
# ---------------------------------------------------------------------------

DEAD_WEIGHT_AGE_DAYS = 7

VALID_SECTIONS = {"routing", "confidence", "utilization", "staleness", "category", "score"}


def measure_routing_health() -> dict:
    """Measure routing feedback loop health.

    Returns:
        Dict with total_routing, pct_with_outcomes, pct_confidence_moved,
        diversity_ratio, unique_combos, and detail lists.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT key, confidence, success_count, failure_count FROM learnings WHERE topic = 'routing'"
        ).fetchall()

    total = len(rows)
    if total == 0:
        return {
            "total_routing": 0,
            "pct_with_outcomes": 0.0,
            "pct_confidence_moved": 0.0,
            "unique_combos": 0,
            "diversity_ratio": 0.0,
        }

    with_outcomes = sum(1 for r in rows if (r["success_count"] or 0) + (r["failure_count"] or 0) > 0)
    confidence_moved = sum(1 for r in rows if abs(r["confidence"] - 0.5) > 1e-9)
    unique_keys = {r["key"] for r in rows}

    return {
        "total_routing": total,
        "pct_with_outcomes": round(with_outcomes / total * 100, 1),
        "pct_confidence_moved": round(confidence_moved / total * 100, 1),
        "unique_combos": len(unique_keys),
        "diversity_ratio": round(len(unique_keys) / total, 3),
    }


# ---------------------------------------------------------------------------
# Section: Confidence Distribution
# ---------------------------------------------------------------------------

CONFIDENCE_BUCKETS = [
    ("0.0-0.3", 0.0, 0.3),
    ("0.3-0.5", 0.3, 0.5),
    ("0.5-0.7", 0.5, 0.7),
    ("0.7-0.9", 0.7, 0.9),
    ("0.9-1.0", 0.9, 1.01),  # inclusive upper bound for 1.0
]


def measure_confidence_distribution() -> dict:
    """Measure confidence distribution across all learnings.

    Returns:
        Dict with histogram (bucket counts), pct_at_baseline,
        and category_movement breakdown.
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT confidence, category FROM learnings").fetchall()

    total = len(rows)
    if total == 0:
        return {
            "histogram": {label: 0 for label, _, _ in CONFIDENCE_BUCKETS},
            "pct_at_baseline": 0.0,
            "category_movement": {},
        }

    histogram: dict[str, int] = {label: 0 for label, _, _ in CONFIDENCE_BUCKETS}
    at_baseline = 0
    category_moved: dict[str, int] = {}
    category_total: dict[str, int] = {}

    for row in rows:
        conf = row["confidence"]
        cat = row["category"]

        for label, low, high in CONFIDENCE_BUCKETS:
            if low <= conf < high:
                histogram[label] += 1
                break

        if abs(conf - 0.5) <= 1e-9:
            at_baseline += 1

        category_total[cat] = category_total.get(cat, 0) + 1
        if abs(conf - 0.5) > 1e-9:
            category_moved[cat] = category_moved.get(cat, 0) + 1

    # Build category movement as pct
    cat_movement = {}
    for cat, tot in sorted(category_total.items()):
        moved = category_moved.get(cat, 0)
        cat_movement[cat] = {"total": tot, "moved": moved, "pct_moved": round(moved / tot * 100, 1) if tot else 0.0}

    return {
        "histogram": histogram,
        "pct_at_baseline": round(at_baseline / total * 100, 1),
        "category_movement": cat_movement,
    }


# ---------------------------------------------------------------------------
# Section: Learning Utilization
# ---------------------------------------------------------------------------


def measure_utilization() -> dict:
    """Measure how well learnings are being utilized via activations.

    Returns:
        Dict with total_learnings, total_with_activations, coverage_rate,
        top_10_activated, and dead_weight_count.
    """
    with get_connection() as conn:
        total_learnings = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]

        # Learnings that have at least one activation (join on topic+key)
        activated = conn.execute(
            """
            SELECT COUNT(DISTINCT l.id) FROM learnings l
            INNER JOIN activations a ON l.topic = a.topic AND l.key = a.key
            """
        ).fetchone()[0]

        # Top 10 most activated
        top_10 = conn.execute(
            """
            SELECT a.topic, a.key, COUNT(*) as activation_count
            FROM activations a
            GROUP BY a.topic, a.key
            ORDER BY activation_count DESC
            LIMIT 10
            """
        ).fetchall()

        # Dead weight: learnings with 0 activations and age > DEAD_WEIGHT_AGE_DAYS
        cutoff_7d = (datetime.now() - timedelta(days=DEAD_WEIGHT_AGE_DAYS)).isoformat()
        dead_weight = conn.execute(
            """
            SELECT COUNT(*) FROM learnings l
            LEFT JOIN activations a ON l.topic = a.topic AND l.key = a.key
            WHERE a.id IS NULL AND l.first_seen < ?
            """,
            (cutoff_7d,),
        ).fetchone()[0]

    coverage = round(activated / total_learnings * 100, 1) if total_learnings else 0.0

    return {
        "total_learnings": total_learnings,
        "total_with_activations": activated,
        "coverage_rate": coverage,
        "top_10_activated": [{"topic": r["topic"], "key": r["key"], "count": r["activation_count"]} for r in top_10],
        "dead_weight_count": dead_weight,
    }


# ---------------------------------------------------------------------------
# Section: Staleness
# ---------------------------------------------------------------------------


def measure_staleness() -> dict:
    """Measure staleness of learning entries.

    Returns:
        Dict with stale_30d, stale_90d, and category breakdown.
    """
    now = datetime.now()
    cutoff_30 = (now - timedelta(days=30)).isoformat()
    cutoff_90 = (now - timedelta(days=90)).isoformat()

    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]

        stale_30 = conn.execute("SELECT COUNT(*) FROM learnings WHERE last_seen < ?", (cutoff_30,)).fetchone()[0]
        stale_90 = conn.execute("SELECT COUNT(*) FROM learnings WHERE last_seen < ?", (cutoff_90,)).fetchone()[0]

        # Category breakdown of 30d stale
        cat_rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM learnings WHERE last_seen < ? GROUP BY category ORDER BY cnt DESC",
            (cutoff_30,),
        ).fetchall()

    return {
        "total": total,
        "stale_30d": stale_30,
        "stale_90d": stale_90,
        "pct_stale_30d": round(stale_30 / total * 100, 1) if total else 0.0,
        "pct_stale_90d": round(stale_90 / total * 100, 1) if total else 0.0,
        "stale_by_category": {r["category"]: r["cnt"] for r in cat_rows},
    }


# ---------------------------------------------------------------------------
# Section: Category Health
# ---------------------------------------------------------------------------


def measure_category_health() -> dict:
    """Measure per-category health metrics.

    Returns:
        Dict with per-category stats and list of categories with zero graduations.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT category,
                   COUNT(*) as count,
                   AVG(confidence) as avg_confidence,
                   AVG(observation_count) as avg_observations,
                   SUM(CASE WHEN graduated_to IS NOT NULL THEN 1 ELSE 0 END) as graduated_count
            FROM learnings
            GROUP BY category
            ORDER BY count DESC
            """
        ).fetchall()

    categories = {}
    zero_graduated = []

    for r in rows:
        cat = r["category"]
        categories[cat] = {
            "count": r["count"],
            "avg_confidence": round(r["avg_confidence"], 3),
            "avg_observations": round(r["avg_observations"], 1),
            "graduated_count": r["graduated_count"],
        }
        if r["graduated_count"] == 0:
            zero_graduated.append(cat)

    return {
        "categories": categories,
        "zero_graduated": zero_graduated,
    }


# ---------------------------------------------------------------------------
# Section: Effectiveness Score
# ---------------------------------------------------------------------------


def compute_effectiveness_score(
    routing: dict,
    confidence: dict,
    utilization: dict,
    staleness: dict,
    category: dict,
) -> dict:
    """Compute composite effectiveness score (0-100).

    Weights:
        - Feedback loop closure: 30 (% routing entries with outcomes)
        - Confidence movement: 20 (% entries that moved from baseline)
        - Activation coverage: 20 (% learnings activated)
        - Freshness: 15 (% entries seen in last 30 days)
        - Graduation rate: 15 (% high-confidence entries that graduated)

    Args:
        routing: Output from measure_routing_health().
        confidence: Output from measure_confidence_distribution().
        utilization: Output from measure_utilization().
        staleness: Output from measure_staleness().
        category: Output from measure_category_health().

    Returns:
        Dict with total score, component scores, and weights.
    """
    # Component 1: Feedback loop closure (0-100)
    feedback_score = min(routing["pct_with_outcomes"], 100.0)

    # Component 2: Confidence movement (0-100) — 0 if no learnings exist
    has_learnings = utilization["total_learnings"] > 0
    confidence_score = min(100.0 - confidence["pct_at_baseline"], 100.0) if has_learnings else 0.0

    # Component 3: Activation coverage (0-100)
    activation_score = min(utilization["coverage_rate"], 100.0)

    # Component 4: Freshness (0-100) — % NOT stale in 30d; 0 if no learnings
    freshness_score = max(100.0 - staleness["pct_stale_30d"], 0.0) if has_learnings else 0.0

    # Component 5: Graduation rate — % of categories with at least one graduation
    total_cats = len(category["categories"])
    cats_with_grad = total_cats - len(category["zero_graduated"])
    graduation_score = round(cats_with_grad / total_cats * 100, 1) if total_cats else 0.0

    weights = {
        "feedback_loop": 30,
        "confidence_movement": 20,
        "activation_coverage": 20,
        "freshness": 15,
        "graduation_rate": 15,
    }

    components = {
        "feedback_loop": round(feedback_score, 1),
        "confidence_movement": round(confidence_score, 1),
        "activation_coverage": round(activation_score, 1),
        "freshness": round(freshness_score, 1),
        "graduation_rate": round(graduation_score, 1),
    }

    total = sum(components[k] * weights[k] / 100 for k in weights)

    return {
        "total": round(total, 1),
        "components": components,
        "weights": weights,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_routing(data: dict, verbose: bool = False) -> None:
    """Print routing feedback loop health."""
    print("=== Routing Feedback Loop Health ===")
    print(f"  Total routing entries:       {data['total_routing']}")
    print(f"  With outcomes (s+f > 0):     {data['pct_with_outcomes']}%")
    print(f"  Confidence moved from 0.5:   {data['pct_confidence_moved']}%")  # security-review: ignore (print, not SQL; pre-existing)  # fmt: skip
    print(f"  Unique agent:skill combos:   {data['unique_combos']}")
    if verbose:
        print(f"  Diversity ratio:             {data['diversity_ratio']}")
    print()


def print_confidence(data: dict, verbose: bool = False) -> None:
    """Print confidence distribution."""
    print("=== Confidence Distribution ===")
    for bucket, count in data["histogram"].items():
        bar = "#" * min(count // 5, 40) if count else ""
        print(f"  {bucket:8s}: {count:>5} {bar}")
    print(f"  At baseline (0.5):           {data['pct_at_baseline']}%")
    if verbose and data["category_movement"]:
        print("  Category movement:")
        for cat, info in sorted(data["category_movement"].items()):
            print(f"    {cat:20s}: {info['moved']}/{info['total']} ({info['pct_moved']}%)")
    print()


def print_utilization(data: dict, verbose: bool = False) -> None:
    """Print learning utilization."""
    print("=== Learning Utilization ===")
    print(f"  Total learnings:             {data['total_learnings']}")
    print(f"  With activations:            {data['total_with_activations']}")
    print(f"  Coverage rate:               {data['coverage_rate']}%")
    print(f"  Dead weight (0 act, >7d):    {data['dead_weight_count']}")
    if verbose and data["top_10_activated"]:
        print("  Top 10 activated:")
        for item in data["top_10_activated"]:
            print(f"    {item['topic']}/{item['key']}: {item['count']} activations")
    print()


def print_staleness(data: dict, verbose: bool = False) -> None:
    """Print staleness metrics."""
    print("=== Staleness ===")
    print(f"  Not seen in 30+ days:        {data['stale_30d']} ({data['pct_stale_30d']}%)")
    print(f"  Not seen in 90+ days:        {data['stale_90d']} ({data['pct_stale_90d']}%)")
    if verbose and data["stale_by_category"]:
        print("  Stale (30d) by category:")
        for cat, cnt in data["stale_by_category"].items():
            print(f"    {cat:20s}: {cnt}")
    print()


def print_category(data: dict, verbose: bool = False) -> None:
    """Print category health."""
    print("=== Category Health ===")
    for cat, info in data["categories"].items():
        grad_marker = " *" if info["graduated_count"] == 0 else ""
        print(
            f"  {cat:20s}: n={info['count']:>4}, "
            f"avg_conf={info['avg_confidence']:.2f}, "
            f"avg_obs={info['avg_observations']:.1f}, "
            f"grad={info['graduated_count']}{grad_marker}"
        )
    if data["zero_graduated"]:
        print(f"  (* = zero graduations: {', '.join(data['zero_graduated'])})")
    print()


def print_score(data: dict, verbose: bool = False) -> None:
    """Print effectiveness score."""
    print("=== Effectiveness Score ===")
    for component, score in data["components"].items():
        weight = data["weights"][component]
        weighted = round(score * weight / 100, 1)
        label = component.replace("_", " ").title()
        if verbose:
            print(f"  {label:25s}: {score:>5.1f}/100 (weight {weight:>2}, contributes {weighted:.1f})")
        else:
            print(f"  {label:25s}: {score:>5.1f}/100 (weight {weight:>2})")
    print(f"  {'':25s}  {'─' * 20}")
    print(f"  {'TOTAL':25s}: {data['total']:>5.1f}/100")
    status = "PASS" if data["total"] >= 50 else "FAIL"
    print(f"  Status: {status}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_all_sections(*, section_filter: str | None = None) -> dict:
    """Run all measurement sections and return collected data.

    When section_filter is set to a non-score section, the score is still
    computed (for exit-code purposes) but stored under the "_score" key so
    callers can access it without it appearing in printed output.

    Args:
        section_filter: If set, only run/display this specific section.

    Returns:
        Dict with section results and the composite score.
    """
    init_db()

    results: dict = {}

    run_all = section_filter is None

    if run_all or section_filter == "routing":
        results["routing"] = measure_routing_health()
    if run_all or section_filter == "confidence":
        results["confidence"] = measure_confidence_distribution()
    if run_all or section_filter == "utilization":
        results["utilization"] = measure_utilization()
    if run_all or section_filter == "staleness":
        results["staleness"] = measure_staleness()
    if run_all or section_filter == "category":
        results["category"] = measure_category_health()

    # Always compute score for exit code purposes
    if run_all or section_filter == "score":
        # Need all section data for score
        routing = results.get("routing") or measure_routing_health()
        confidence = results.get("confidence") or measure_confidence_distribution()
        utilization = results.get("utilization") or measure_utilization()
        staleness = results.get("staleness") or measure_staleness()
        category = results.get("category") or measure_category_health()
        results["score"] = compute_effectiveness_score(routing, confidence, utilization, staleness, category)
    elif section_filter is not None:
        # Non-score section filter: compute score for exit code but don't display
        routing = results.get("routing") or measure_routing_health()
        confidence = results.get("confidence") or measure_confidence_distribution()
        utilization = results.get("utilization") or measure_utilization()
        staleness = results.get("staleness") or measure_staleness()
        category = results.get("category") or measure_category_health()
        results["_score"] = compute_effectiveness_score(routing, confidence, utilization, staleness, category)

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate learning database effectiveness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--verbose", action="store_true", help="Detailed breakdown")
    parser.add_argument(
        "--section",
        choices=sorted(VALID_SECTIONS),
        default=None,
        help="Run a single section only",
    )

    args = parser.parse_args()
    results = run_all_sections(section_filter=args.section)

    if args.json:
        # "_score" is the internal carrier for the exit code when a section
        # filter suppresses the score display. It is not part of the --json
        # contract, so strip it rather than shipping a private key to callers.
        print(json.dumps({k: v for k, v in results.items() if not k.startswith("_")}, indent=2))
    else:
        printers = {
            "routing": print_routing,
            "confidence": print_confidence,
            "utilization": print_utilization,
            "staleness": print_staleness,
            "category": print_category,
            "score": print_score,
        }
        for section, data in results.items():
            if section in printers:
                printers[section](data, verbose=args.verbose)

    # Exit code based on score (use _score if score wasn't displayed)
    score_data = results.get("score") or results.get("_score", {})
    score = score_data.get("total")
    if score is not None and score < 50:
        sys.exit(1)


if __name__ == "__main__":
    main()
