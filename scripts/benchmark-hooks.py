#!/usr/bin/env python3
"""
Hook benchmark script for CI performance enforcement.

Times all registered hooks with representative inputs and reports
pass/fail against configurable thresholds.

Usage:
    python scripts/benchmark-hooks.py                    # Run with defaults
    python scripts/benchmark-hooks.py --ci --threshold 200  # CI mode, 200ms limit
    python scripts/benchmark-hooks.py --verbose          # Show detailed timing
    python scripts/benchmark-hooks.py --json             # JSON output for tracking
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"

# Default threshold in milliseconds
DEFAULT_THRESHOLD_MS = 200
ITERATIONS = 5

# Synthetic inputs for different hook event types
INPUTS: dict[str, str] = {
    "UserPromptSubmit": json.dumps(
        {
            "type": "UserPromptSubmit",
            "prompt": "implement a feature with testing and documentation",
        }
    ),
    "PostToolUse": json.dumps(
        {
            "type": "PostToolUse",
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.py"},
            "tool_result": "File written successfully",
        }
    ),
    "SessionStart": json.dumps(
        {
            "type": "SessionStart",
        }
    ),
    "PreCompact": json.dumps(
        {
            "type": "PreCompact",
            "summary": "Working on feature implementation",
        }
    ),
    "Stop": json.dumps(
        {
            "type": "Stop",
        }
    ),
}

# Map hooks to their expected event types based on common patterns
HOOK_EVENT_MAP: dict[str, str] = {
    "skill-evaluator": "UserPromptSubmit",
    "retro-knowledge-injector": "UserPromptSubmit",
    "instruction-reminder": "UserPromptSubmit",
    "operator-context-detector": "UserPromptSubmit",
    "fish-shell-detector": "UserPromptSubmit",
    "adr-context-injector": "UserPromptSubmit",
    "adr-enforcement": "UserPromptSubmit",
    "pipeline-context-detector": "UserPromptSubmit",
    "confidence-decay": "UserPromptSubmit",
    "post-tool-lint-hint": "PostToolUse",
    "error-learner": "PostToolUse",
    "pretool-learning-injector": "PostToolUse",
    "task-completed-learner": "PostToolUse",
    "usage-tracker": "PostToolUse",
    "session-context": "SessionStart",
    "session-summary": "Stop",
    "precompact-archive": "PreCompact",
    "sync-to-user-claude": "PreCompact",
    "cross-repo-agents": "SessionStart",
    "subagent-completion-guard": "PostToolUse",
}


def discover_hooks() -> list[Path]:
    """Find all Python hook files in hooks/ directory."""
    hooks = []
    for f in sorted(HOOKS_DIR.glob("*.py")):
        if f.name.startswith("__"):
            continue
        hooks.append(f)
    return hooks


def get_input_for_hook(hook_name: str) -> str:
    """Get appropriate synthetic input for a hook."""
    event_type = HOOK_EVENT_MAP.get(hook_name, "UserPromptSubmit")
    return INPUTS.get(event_type, INPUTS["UserPromptSubmit"])


def benchmark_hook(hook_path: Path, iterations: int = ITERATIONS) -> dict:
    """Benchmark a single hook, return timing results."""
    hook_name = hook_path.stem
    input_data = get_input_for_hook(hook_name)
    times_ms: list[float] = []

    for _ in range(iterations):
        start = time.perf_counter()
        try:
            subprocess.run(
                [sys.executable, str(hook_path)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(REPO_ROOT),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)
        except subprocess.TimeoutExpired:
            times_ms.append(5000.0)  # 5s timeout = failure
        except Exception:
            times_ms.append(-1.0)  # Error

    valid_times = [t for t in times_ms if t >= 0]
    if not valid_times:
        return {
            "name": hook_name,
            "avg_ms": -1,
            "median_ms": -1,
            "max_ms": -1,
            "min_ms": -1,
            "error": True,
        }

    return {
        "name": hook_name,
        "avg_ms": round(statistics.mean(valid_times), 1),
        "median_ms": round(statistics.median(valid_times), 1),
        "max_ms": round(max(valid_times), 1),
        "min_ms": round(min(valid_times), 1),
        "error": False,
    }


def main() -> int:
    """Run hook benchmarks."""
    parser = argparse.ArgumentParser(description="Benchmark Claude Code hooks")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on threshold violations")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_MS, help="Max allowed time in ms")
    parser.add_argument("--verbose", action="store_true", help="Show detailed timing table")
    parser.add_argument("--json", action="store_true", help="JSON output for trend tracking")
    parser.add_argument("--iterations", type=int, default=ITERATIONS, help="Number of iterations per hook")
    args = parser.parse_args()

    hooks = discover_hooks()
    if not hooks:
        print("No hooks found in hooks/ directory")
        return 1

    results = []
    for hook in hooks:
        result = benchmark_hook(hook, iterations=args.iterations)
        result["pass"] = result["median_ms"] <= args.threshold and not result["error"]
        results.append(result)

    # JSON output
    if args.json:
        print(json.dumps({"threshold_ms": args.threshold, "hooks": results}, indent=2))
        return 0

    # Table output
    violations = 0
    name_width = max(len(r["name"]) for r in results)

    header = f"{'Hook':<{name_width}}  {'Median':>8}  {'Avg':>8}  {'Max':>8}  {'Status':>6}"
    print(header)
    print("-" * len(header))

    for r in sorted(results, key=lambda x: x["median_ms"], reverse=True):
        if r["error"]:
            status = "ERROR"
            violations += 1
        elif r["pass"]:
            status = "PASS"
        else:
            status = "FAIL"
            violations += 1

        print(
            f"{r['name']:<{name_width}}  {r['median_ms']:>7.1f}ms  {r['avg_ms']:>7.1f}ms  "
            f"{r['max_ms']:>7.1f}ms  {status:>6}"
        )

    print()
    print(
        f"Threshold: {args.threshold}ms | Hooks: {len(results)} | "
        f"Pass: {len(results) - violations} | Fail: {violations}"
    )

    if args.ci and violations > 0:
        print(f"\nCI FAILURE: {violations} hook(s) exceeded {args.threshold}ms threshold")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
