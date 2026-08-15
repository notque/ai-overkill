#!/usr/bin/env python3
"""Routing regression benchmark for the /do router.

Validates that all expected routing targets (agents, skills, pipelines) referenced
in the benchmark test fixture actually exist in the INDEX.json files. This is a
STRUCTURAL benchmark — it checks that routing targets are valid, not that the LLM
routes correctly.

Also verifies coverage accounting: every indexed skill must have a benchmark case
or an explicit, machine-readable exclusion explaining why no deterministic case
belongs in this corpus.

Usage:
    python3 scripts/routing-benchmark.py
    python3 scripts/routing-benchmark.py --verbose
    python3 scripts/routing-benchmark.py --coverage
    python3 scripts/routing-benchmark.py --category go-development
    python3 scripts/routing-benchmark.py --fixture path/to/custom.json

Exit codes:
    0 - All test cases have valid targets (or all expected targets are null)
    1 - Invalid targets or invalid coverage accounting
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = REPO_ROOT / "scripts" / "routing-benchmark.json"
AGENTS_INDEX = REPO_ROOT / "agents" / "INDEX.json"
SKILLS_INDEX = REPO_ROOT / "skills" / "INDEX.json"
PIPELINES_INDEX = REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json"
COVERAGE_EXCLUSIONS = REPO_ROOT / "scripts" / "routing-benchmark-exclusions.json"

# Harness-provided agents that are routable but carry no agents/*.md file, so
# they never appear in agents/INDEX.json (same set as validate-do-references.py
# and validate-merged-index.py). A fixture may name them as an expected agent —
# "general-purpose is correct here" is a real assertion, distinct from null.
BUILTIN_AGENTS = frozenset({"general-purpose"})


def load_json(path: Path) -> dict:
    """Load and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        SystemExit: If the file is missing or contains invalid JSON.
    """
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _public_skill_names(index: dict, repo_root: Path = REPO_ROOT) -> set[str]:
    """Return indexed skills whose declared files exist in this public checkout.

    The generated index may include local overlay skills when explicitly built
    with ``--include-private``. Their flat deployment paths are intentionally
    absent from this repository, so they do not belong in a public benchmark
    or its committed coverage accounting.
    """
    skills: set[str] = set()
    for name, entry in index.get("skills", {}).items():
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file")
        if isinstance(file_path, str) and (repo_root / file_path).is_file():
            skills.add(name)
    return skills


def load_component_names() -> tuple[set[str], set[str], set[str]]:
    """Load all known agent, skill, and pipeline names from INDEX files.

    Returns:
        Tuple of (agent_names, skill_names, pipeline_names).
    """
    agents: set[str] = set()
    skills: set[str] = set()
    pipelines: set[str] = set()

    if AGENTS_INDEX.exists():
        data = load_json(AGENTS_INDEX)
        agents = set(data.get("agents", {}).keys())

    if SKILLS_INDEX.exists():
        data = load_json(SKILLS_INDEX)
        skills = _public_skill_names(data)

    if PIPELINES_INDEX.exists():
        data = load_json(PIPELINES_INDEX)
        # Pipelines INDEX may use "pipelines" or "skills" as the key
        pipelines = set(data.get("pipelines", data.get("skills", {})).keys())

    return agents, skills, pipelines


def validate_test_case(
    case: dict,
    agents: set[str],
    skills: set[str],
    pipelines: set[str],
) -> list[str]:
    """Validate a single test case against known components.

    Args:
        case: Test case dictionary with expected_agent and expected_skill.
        agents: Set of known agent names.
        skills: Set of known skill names.
        pipelines: Set of known pipeline names.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    expected_agent = case.get("expected_agent")
    if expected_agent and expected_agent not in agents and expected_agent not in BUILTIN_AGENTS:
        errors.append(f"agent '{expected_agent}' not found in agents/INDEX.json")

    expected_skill = case.get("expected_skill")
    if expected_skill and expected_skill not in skills and expected_skill not in pipelines:
        errors.append(f"skill '{expected_skill}' not found in skills/INDEX.json")

    return errors


def compute_coverage(test_cases: list[dict], skills: set[str]) -> tuple[set[str], set[str]]:
    """Split known skills into benchmark-covered and uncovered sets.

    A skill counts as covered when any test case names it in expected_skill
    or expected_stacked. References to unknown skills are ignored — validity
    is the benchmark's job, not coverage's.

    Args:
        test_cases: Benchmark test case dicts.
        skills: Skill names from skills/INDEX.json.

    Returns:
        Tuple of (covered, uncovered) skill name sets.
    """
    referenced: set[str] = set()
    for case in test_cases:
        skill = case.get("expected_skill")
        if skill:
            referenced.add(skill)
        referenced.update(case.get("expected_stacked") or [])
    return skills & referenced, skills - referenced


def load_coverage_exclusions(path: Path = COVERAGE_EXCLUSIONS) -> dict[str, str]:
    """Load per-skill reasons for deliberate benchmark exclusions.

    An exclusion is documentation of a known evaluation boundary, not a passing
    benchmark. Keeping it separate from the corpus makes uncovered skills visible
    while preventing silent coverage regressions as the index changes.
    """
    data = load_json(path)
    exclusions = data.get("exclusions")
    if not isinstance(exclusions, dict):
        print(f"ERROR: {path} must contain an object named 'exclusions'", file=sys.stderr)
        sys.exit(1)

    invalid = [
        name
        for name, reason in exclusions.items()
        if not isinstance(name, str) or not isinstance(reason, str) or not reason.strip()
    ]
    if invalid:
        print(f"ERROR: {path} contains exclusions without a non-empty reason: {invalid}", file=sys.stderr)
        sys.exit(1)
    return exclusions


def compute_coverage_accounting(
    test_cases: list[dict], skills: set[str], exclusions: dict[str, str]
) -> tuple[set[str], set[str], set[str], list[str]]:
    """Return benchmarked, excluded, unaccounted skills and configuration errors."""
    covered, _ = compute_coverage(test_cases, skills)
    excluded = skills & set(exclusions)
    unaccounted = skills - covered - excluded
    errors: list[str] = []

    unknown_exclusions = sorted(set(exclusions) - skills)
    if unknown_exclusions:
        errors.append(f"Exclusions name skills absent from skills/INDEX.json: {unknown_exclusions}")  # security-review: ignore (error message, not SQL)  # fmt: skip

    overlapping = sorted(covered & excluded)
    if overlapping:
        errors.append(f"Skills are both benchmarked and excluded: {overlapping}")

    if unaccounted:
        errors.append(f"Indexed skills lack a benchmark case or exclusion: {sorted(unaccounted)}")

    return covered, excluded, unaccounted, errors


def print_coverage_report(test_cases: list[dict], skills: set[str], exclusions: dict[str, str]) -> list[str]:
    """Print coverage accounting and return configuration errors.

    Args:
        test_cases: Benchmark test case dicts (unfiltered).
        skills: Skill names from skills/INDEX.json.
    """
    covered, excluded, unaccounted, errors = compute_coverage_accounting(test_cases, skills, exclusions)
    print()
    print(
        f"Coverage: {len(covered)} benchmarked, {len(excluded)} excluded, {len(unaccounted)} unaccounted / {len(skills)} indexed skills"
    )
    if excluded:
        print(f"Excluded skills ({len(excluded)}):")
        for name in sorted(excluded):
            print(f"  - {name}: {exclusions[name]}")
    if errors:
        print("Coverage accounting errors:")
        for error in errors:
            print(f"  - {error}")
    return errors


def run_benchmark(
    fixture_path: Path,
    *,
    verbose: bool = False,
    category_filter: str | None = None,
    show_coverage: bool = False,
) -> bool:
    """Run the routing benchmark and report results.

    Args:
        fixture_path: Path to the benchmark JSON fixture.
        verbose: Show per-test-case results.
        category_filter: Only run test cases in this category.
        show_coverage: Print the advisory coverage report after the summary.

    Returns:
        True if all test cases pass, False otherwise.
    """
    fixture = load_json(fixture_path)
    test_cases: list[dict] = fixture.get("test_cases", [])
    all_cases = test_cases  # coverage is fixture-wide, immune to --category

    if not test_cases:
        print("ERROR: No test cases found in fixture", file=sys.stderr)
        return False

    agents, skills, pipelines = load_component_names()

    if verbose:
        print(f"Loaded components: {len(agents)} agents, {len(skills)} skills, {len(pipelines)} pipelines")
        print()

    # Filter by category if requested
    if category_filter:
        test_cases = [tc for tc in test_cases if tc.get("category") == category_filter]
        if not test_cases:
            print(f"ERROR: No test cases found for category '{category_filter}'", file=sys.stderr)
            return False

    pass_count = 0
    fail_count = 0
    null_count = 0
    category_counts: Counter[str] = Counter()
    failures: list[tuple[dict, list[str]]] = []

    for case in test_cases:
        category = case.get("category", "uncategorized")
        category_counts[category] += 1

        expected_agent = case.get("expected_agent")
        expected_skill = case.get("expected_skill")

        # Null targets are valid — they represent requests that should NOT route
        if expected_agent is None and expected_skill is None:
            null_count += 1
            pass_count += 1
            if verbose:
                print(f"  PASS (null target) : {case['request']}")
            continue

        errors = validate_test_case(case, agents, skills, pipelines)
        if errors:
            fail_count += 1
            failures.append((case, errors))
            if verbose:
                print(f"  FAIL : {case['request']}")
                for err in errors:
                    print(f"         -> {err}")
        else:
            pass_count += 1
            if verbose:
                targets = []
                if expected_agent:
                    targets.append(f"agent={expected_agent}")
                if expected_skill:
                    targets.append(f"skill={expected_skill}")
                print(f"  PASS : {case['request']}  [{', '.join(targets)}]")

    total = pass_count + fail_count

    if verbose:
        print()

    # Summary
    print(f"Routing Benchmark: {pass_count}/{total} test cases have valid targets", end="")
    if null_count:
        print(f" ({null_count} null-target guards)")
    else:
        print()

    # Category breakdown
    cat_parts = [f"{cat}({count})" for cat, count in sorted(category_counts.items())]
    print(f"Categories: {', '.join(cat_parts)}")

    # Report failures
    if failures:
        print()
        print("FAILURES:")
        for case, errors in failures:
            print(f'  [{case.get("category", "?")}] "{case["request"]}"')
            for err in errors:
                print(f"    -> {err}")

    coverage_errors: list[str] = []
    if show_coverage:
        coverage_errors = print_coverage_report(all_cases, skills, load_coverage_exclusions())

    # Coverage errors are advisory per PHILOSOPHY.md Warn-Only Gates — they
    # print but do not fail the run. Only invalid routing targets block.
    return fail_count == 0


def main() -> None:
    """CLI entry point for the routing benchmark."""
    parser = argparse.ArgumentParser(
        description="Routing regression benchmark for the /do router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/routing-benchmark.py                     # Run all tests
  python3 scripts/routing-benchmark.py --verbose            # Show per-test results
  python3 scripts/routing-benchmark.py --category go-development  # Filter by category
        """,
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"Path to benchmark fixture JSON (default: {DEFAULT_FIXTURE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-test-case pass/fail results",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Only run test cases in this category",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Print skill coverage accounting (also shown with --verbose)",
    )

    args = parser.parse_args()
    success = run_benchmark(
        args.fixture,
        verbose=args.verbose,
        category_filter=args.category,
        show_coverage=args.coverage or args.verbose,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
