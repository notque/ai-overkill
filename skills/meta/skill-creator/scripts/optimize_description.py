#!/usr/bin/env python3
"""
optimize_description.py — Train/test description optimization for skill triggering accuracy.

Splits eval queries 60/40 train/test. Evaluates the current description (3 runs per query
for variance reduction). Proposes improvements based on train set failures. Re-evaluates
on both sets. Selects best description by test score to prevent overfitting.

Eval set format (trigger-eval.json):
  [
    {"query": "user prompt text", "should_trigger": true},
    {"query": "adjacent domain prompt", "should_trigger": false}
  ]
"""

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RUNS_PER_QUERY = 3  # Runs per query for variance reduction


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Optimize skill description for triggering accuracy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--skill-path", required=True, help="Path to the skill directory (contains SKILL.md)")
    p.add_argument("--eval-set", required=True, help="Path to trigger-eval.json")
    p.add_argument("--model", default=None, help="Claude model for claude -p (default: your configured model)")
    p.add_argument("--max-iterations", type=int, default=5, help="Maximum optimization iterations (default: 5)")
    p.add_argument("--seed", type=int, default=42, help="Random seed for train/test split (default: 42)")
    p.add_argument("--dry-run", action="store_true", help="Show split and current accuracy without optimizing")
    return p


def check_claude_available() -> None:
    if shutil.which("claude") is None:
        print(
            "ERROR: 'claude' CLI not found in PATH.\nInstall with: npm install -g @anthropic-ai/claude-code",
            file=sys.stderr,
        )
        sys.exit(1)


def load_eval_set(eval_path: Path) -> list[dict]:
    try:
        data = json.loads(eval_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Could not load eval set {eval_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list) or not data:
        print("ERROR: eval set must be a non-empty JSON array", file=sys.stderr)
        sys.exit(1)

    for entry in data:
        if "query" not in entry or "should_trigger" not in entry:
            print(
                f"ERROR: each eval entry must have 'query' and 'should_trigger' fields. Got: {entry}",
                file=sys.stderr,
            )
            sys.exit(1)

    return data


def split_eval_set(eval_set: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    """60/40 train/test split, stratified by should_trigger."""
    rng = random.Random(seed)
    should_trigger = [e for e in eval_set if e["should_trigger"]]
    should_not = [e for e in eval_set if not e["should_trigger"]]

    def split(items: list) -> tuple[list, list]:
        shuffled = items[:]
        rng.shuffle(shuffled)
        split_point = math.ceil(len(shuffled) * 0.6)
        return shuffled[:split_point], shuffled[split_point:]

    train_trigger, test_trigger = split(should_trigger)
    train_no, test_no = split(should_not)
    return train_trigger + train_no, test_trigger + test_no


def test_trigger(query: str, description: str, model: str) -> bool:
    """
    Ask claude whether it would use the skill given this description and query.
    Returns True if the skill should trigger, False otherwise.
    """
    prompt = (
        f"You are a routing system. A skill has this description:\n\n"
        f"---\n{description}\n---\n\n"
        f'A user says: "{query}"\n\n'
        f"Answer with exactly one word: YES if you would use this skill for this request, "
        f"NO if you would not. Do not explain."
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, *(["--model", model] if model else [])],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"WARNING: claude exited {result.returncode}: {result.stderr[:200]}",
                file=sys.stderr,
            )
            return False
        answer = result.stdout.strip().upper()
        return answer.startswith("YES")
    except subprocess.TimeoutExpired:
        return False


def evaluate_description(description: str, eval_queries: list[dict], model: str, runs: int = RUNS_PER_QUERY) -> float:
    """Evaluate a description against a set of queries. Returns accuracy (0.0-1.0)."""
    if not eval_queries:
        return 0.0

    correct = 0
    total = 0

    for entry in eval_queries:
        query = entry["query"]
        should_trigger = entry["should_trigger"]

        # Run multiple times for variance reduction; take majority vote
        votes = [test_trigger(query, description, model) for _ in range(runs)]
        majority_triggered = votes.count(True) > runs / 2

        if majority_triggered == should_trigger:
            correct += 1
        total += 1

    return correct / total if total > 0 else 0.0


def propose_improvement(
    description: str,
    train_queries: list[dict],
    failures: list[dict],
    model: str,
) -> str:
    """
    Ask claude to propose a better description based on train set failures.
    Returns the proposed description text.
    """
    failure_examples = "\n".join(
        f'- Query: "{f["query"]}" | Expected: {"TRIGGER" if f["should_trigger"] else "NO TRIGGER"} | Got: {"TRIGGER" if f["triggered"] else "NO TRIGGER"}'
        for f in failures[:10]  # Cap at 10 examples to avoid prompt bloat
    )

    prompt = (
        f"You are improving a Claude skill's description to optimize triggering accuracy.\n\n"
        f"Current description:\n---\n{description}\n---\n\n"
        f"Failures on training set:\n{failure_examples}\n\n"
        f"Requirements:\n"
        f"1. Keep the description under 1024 characters\n"
        f"2. No XML angle brackets (< or >)\n"
        f"3. Maintain the What+When formula: 'Do X when Y. Use for [triggers]. Do NOT use for [anti-triggers].'\n"
        f"4. Do not overfit to the failure examples — improve the description generally\n"
        f"5. Return ONLY the new description text, no explanation\n\n"
        f"New description:"
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, *(["--model", model] if model else [])],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(
                f"WARNING: claude exited {result.returncode} proposing improvement: {result.stderr[:200]}",
                file=sys.stderr,
            )
            return description
        proposed = result.stdout.strip()
        if not proposed:
            print("WARNING: claude returned empty improvement. Keeping current.", file=sys.stderr)
            return description
        if len(proposed) > 1024:
            print(f"WARNING: Proposed description exceeds 1024 chars ({len(proposed)}). Truncating.", file=sys.stderr)
            proposed = proposed[:1020] + "..."
        return proposed
    except subprocess.TimeoutExpired:
        print("WARNING: Timeout proposing description improvement. Keeping current.", file=sys.stderr)
        return description


def identify_failures(description: str, queries: list[dict], model: str) -> list[dict]:
    """Return list of queries where the description produced incorrect routing."""
    failures = []
    for entry in queries:
        query = entry["query"]
        should_trigger = entry["should_trigger"]
        votes = [test_trigger(query, description, model) for _ in range(RUNS_PER_QUERY)]
        triggered = votes.count(True) > RUNS_PER_QUERY / 2
        if triggered != should_trigger:
            failures.append({**entry, "triggered": triggered})
    return failures


def optimize(args: argparse.Namespace) -> int:
    check_claude_available()

    skill_path = Path(args.skill_path).resolve()
    skill_md = skill_path / "SKILL.md"
    eval_path = Path(args.eval_set).resolve()

    if not skill_md.exists():
        print(f"ERROR: SKILL.md not found at {skill_md}", file=sys.stderr)
        return 1

    eval_set = load_eval_set(eval_path)
    train_set, test_set = split_eval_set(eval_set, seed=args.seed)

    print(f"Eval set: {len(eval_set)} queries ({len(train_set)} train, {len(test_set)} test)", file=sys.stderr)

    # Extract current description from SKILL.md frontmatter
    skill_text = skill_md.read_text()
    description_start = skill_text.find("description: |")
    if description_start == -1:
        print("ERROR: Could not find 'description: |' in SKILL.md frontmatter", file=sys.stderr)
        return 1

    # Extract description block (lines until next YAML key)
    lines = skill_text.split("\n")
    desc_lines = []
    in_desc = False
    for line in lines:
        if line.strip().startswith("description: |"):
            in_desc = True
            continue
        if in_desc:
            if line and not line[0].isspace() and ":" in line:
                break
            desc_lines.append(line.lstrip())

    current_description = "\n".join(desc_lines).strip()
    print(f"Current description ({len(current_description)} chars)", file=sys.stderr)

    if args.dry_run:
        train_acc = evaluate_description(current_description, train_set, args.model)
        test_acc = evaluate_description(current_description, test_set, args.model)
        print(f"Train accuracy: {train_acc:.1%}")
        print(f"Test accuracy:  {test_acc:.1%}")
        return 0

    # Evaluate initial accuracy
    print("Evaluating initial description...", file=sys.stderr)
    best_description = current_description
    best_test_acc = evaluate_description(current_description, test_set, args.model)
    print(f"Initial test accuracy: {best_test_acc:.1%}", file=sys.stderr)

    history = [{"iteration": 0, "description": current_description, "test_accuracy": best_test_acc}]

    for iteration in range(1, args.max_iterations + 1):
        print(f"\nIteration {iteration}/{args.max_iterations}", file=sys.stderr)

        failures = identify_failures(best_description, train_set, args.model)
        train_acc = 1.0 - (len(failures) / len(train_set)) if train_set else 0.0
        print(f"Train accuracy: {train_acc:.1%} ({len(failures)} failures)", file=sys.stderr)

        if not failures:
            print("No failures on train set. Optimization complete.", file=sys.stderr)
            break

        proposed = propose_improvement(best_description, train_set, failures, args.model)
        proposed_test_acc = evaluate_description(proposed, test_set, args.model)
        print(f"Proposed test accuracy: {proposed_test_acc:.1%}", file=sys.stderr)

        history.append(
            {
                "iteration": iteration,
                "description": proposed,
                "train_accuracy": train_acc,
                "test_accuracy": proposed_test_acc,
            }
        )

        if proposed_test_acc >= best_test_acc:
            best_description = proposed
            best_test_acc = proposed_test_acc
            print(f"Accepted (test accuracy improved or held: {best_test_acc:.1%})", file=sys.stderr)
        else:
            print(f"Rejected (test accuracy decreased: {proposed_test_acc:.1%} < {best_test_acc:.1%})", file=sys.stderr)

    # Report results
    print(f"\n=== Optimization Complete ===")
    print(f"Best test accuracy: {best_test_acc:.1%}")
    print(f"Iterations run: {len(history) - 1}")

    if best_description != current_description:
        print(f"\nBest description ({len(best_description)} chars):\n")
        print(best_description)
    else:
        print("\nNo improvement found. Current description is already optimal.")

    # Write history to optimization_history.json alongside the eval set
    history_path = eval_path.parent / "optimization_history.json"
    history_path.write_text(
        json.dumps(
            {
                "skill_path": str(skill_path),
                "eval_set": str(eval_path),
                "model": args.model,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "best_test_accuracy": best_test_acc,
                "best_description": best_description,
                "history": history,
            },
            indent=2,
        )
    )
    print(f"\nHistory written: {history_path}", file=sys.stderr)

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return optimize(args)


if __name__ == "__main__":
    sys.exit(main())
