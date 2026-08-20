#!/usr/bin/env python3
"""Validate that every hard CI gate has at least one test proving it can fail.

A "hard gate" is a `scripts/validate-*.py` or `scripts/check-*.py` invocation
in `.github/workflows/test.yml` whose step has no `continue-on-error: true`
and whose `run:` command has no trailing `|| true`.

A "negative test" is any test in `scripts/tests/test_<name>*.py` that asserts
a non-zero exit code or a SystemExit with a non-zero code.

Exit codes:
  0 — all hard gates have negative tests, no stale allowlist entries.
  1 — at least one hard gate lacks a negative test, or a stale allowlist entry exists.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Validator/check scripts plus generators used as strict ``--check`` gates.
_SCRIPT_RE = re.compile(r"\b((?:validate|check|generate)-[\w-]+\.py)\b")


# ---------------------------------------------------------------------------
# Workflow parsing
# ---------------------------------------------------------------------------


def _parse_workflow(workflow_path: Path) -> list[dict]:
    """Parse the GitHub Actions workflow and return gate metadata.

    Each item: {script, hard: bool, job_name, step_name}.
    """
    import yaml

    text = workflow_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return []

    gates: list[dict] = []
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        return []

    for job_name, job_def in jobs.items():
        if not isinstance(job_def, dict):
            continue
        job_coe = job_def.get("continue-on-error", False)

        steps = job_def.get("steps", [])
        if not isinstance(steps, list):
            continue

        for step in steps:
            if not isinstance(step, dict):
                continue
            run_cmd = step.get("run", "")
            if not isinstance(run_cmd, str):
                continue

            matches = _SCRIPT_RE.findall(run_cmd)
            matches = [m for m in matches if not m.startswith("generate-") or "--check" in run_cmd]
            if not matches:
                continue

            step_coe = step.get("continue-on-error", False)
            has_or_true = run_cmd.rstrip().endswith("|| true")

            is_advisory = bool(job_coe) or bool(step_coe) or has_or_true

            step_name = step.get("name", "")

            for script in matches:
                gates.append(
                    {
                        "script": script,
                        "hard": not is_advisory,
                        "job_name": job_name,
                        "step_name": step_name,
                    }
                )

    return gates


# ---------------------------------------------------------------------------
# Test file analysis (AST-based)
# ---------------------------------------------------------------------------


def _has_negative_test(test_path: Path, script_name: str) -> bool:
    """Return True if the test file contains at least one assertion of non-zero exit.

    Detected patterns (conservative — false negatives OK, false positives NOT):
      - `assert ... returncode == 1`
      - `assert ... returncode != 0`
      - `assert rc == 1` / `assert rc != 0`
      - `pytest.raises(SystemExit, match="<non-zero code>")`

    A comparison counts only when it is the condition of an ``assert``. Bare
    comparisons in helper logic do not prove anything, and an unconstrained
    ``pytest.raises(SystemExit)`` can accept ``SystemExit(0)``.
    """
    try:
        source = test_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(test_path))
    except (OSError, SyntaxError):
        return False

    target_tokens = {script_name, script_name.removesuffix(".py").replace("-", "_")}

    for test in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        if not test.name.startswith("test_") or _is_skipped_test(test):
            continue
        executed: set[str] = set()
        for node in ast.walk(test):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                target_call = value if isinstance(value, ast.Call) else None
                if (
                    isinstance(value, ast.Attribute)
                    and value.attr == "returncode"
                    and isinstance(value.value, ast.Call)
                ):
                    target_call = value.value
                if target_call is not None and _call_names_target(target_call, target_tokens):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    executed.update(t.id for t in targets if isinstance(t, ast.Name))

        for node in ast.walk(test):
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
                if _is_negative_returncode_compare(node.test, executed):
                    return True

            if isinstance(node, ast.With):
                for item in node.items:
                    if not isinstance(item.context_expr, ast.Call):
                        continue
                    if not _is_pytest_raises_nonzero_systemexit(item.context_expr):
                        continue
                    if any(
                        isinstance(child, ast.Call) and _call_names_target(child, target_tokens)
                        for stmt in node.body
                        for child in ast.walk(stmt)
                    ):
                        return True

    return False


def _is_skipped_test(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True for skip/xfail-decorated tests or tests calling pytest.skip."""
    decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
    if "skip" in decorators or "xfail" in decorators:
        return True
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id == "pytest"
        and child.func.attr == "skip"
        for child in ast.walk(node)
    )


def _call_names_target(node: ast.Call, target_tokens: set[str]) -> bool:
    """Return True when a call expression names the gate under audit."""
    rendered = ast.unparse(node)
    return "SCRIPT" in rendered or any(token in rendered for token in target_tokens)


def _is_pytest_raises_nonzero_systemexit(node: ast.Call) -> bool:
    """Check for ``pytest.raises(SystemExit, match=...)`` with a non-zero code."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "raises":
        if isinstance(func.value, ast.Name) and func.value.id == "pytest":
            if not any(isinstance(arg, ast.Name) and arg.id == "SystemExit" for arg in node.args):
                return False
            for keyword in node.keywords:
                if keyword.arg != "match":
                    continue
                if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
                    return False
                return bool(re.search(r"[1-9]", keyword.value.value))
    return False


def _is_negative_returncode_compare(node: ast.Compare, executed: set[str]) -> bool:
    """Check if a Compare node asserts a non-zero exit code.

    Matches:
      - <expr>.returncode == 1  (or any non-zero int)
      - <expr>.returncode != 0
      - rc == 1 / rc != 0 (where rc is a simple name)
      - result.returncode == 1
    """
    # We check left and comparators for returncode-shaped expressions.
    left = node.left
    for op, comparator in zip(node.ops, node.comparators):
        if _is_returncode_nonzero(left, op, comparator, executed):
            return True
        # Reversed comparison: `1 == result.returncode`
        if _is_returncode_nonzero(comparator, _flip_op(op), left, executed):
            return True
    return False


def _is_returncode_attr_or_rc_name(node: ast.AST, executed: set[str]) -> bool:
    """True if node is `<something>.returncode` or a Name like `rc`."""
    if isinstance(node, ast.Attribute) and node.attr == "returncode":
        return isinstance(node.value, ast.Name) and node.value.id in executed
    if isinstance(node, ast.Name) and node.id in executed:
        return True
    return False


def _is_returncode_nonzero(left: ast.AST, op: ast.cmpop, right: ast.AST, executed: set[str]) -> bool:
    """True if `left <op> right` asserts a non-zero exit code."""
    if not _is_returncode_attr_or_rc_name(left, executed):
        return False

    if not isinstance(right, ast.Constant) or not isinstance(right.value, int):
        return False

    value = right.value

    # returncode == <non-zero> or returncode >= 1
    if isinstance(op, ast.Eq) and value != 0:
        return True
    # returncode != 0
    if isinstance(op, ast.NotEq) and value == 0:
        return True
    # returncode > 0
    if isinstance(op, (ast.Gt, ast.GtE)) and value >= 1:
        return True

    return False


def _flip_op(op: ast.cmpop) -> ast.cmpop:
    """Flip a comparison operator for reversed comparisons."""
    flips: dict[type, type] = {
        ast.Eq: ast.Eq,
        ast.NotEq: ast.NotEq,
        ast.Lt: ast.Gt,
        ast.Gt: ast.Lt,
        ast.LtE: ast.GtE,
        ast.GtE: ast.LtE,
    }
    return flips.get(type(op), type(op))()


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------


def _parse_allowlist(path: Path) -> dict[str, str]:
    """Parse `script-name.py: reason` lines. Returns {script: reason}."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            name, reason = line.split(":", 1)
            name, reason = name.strip(), reason.strip()
            if name:
                out[name] = reason
    return out


# ---------------------------------------------------------------------------
# Locate test files
# ---------------------------------------------------------------------------


def _find_test_files(script_name: str, tests_dir: Path) -> list[Path]:
    """Find test files matching a script name.

    validate-foo.py -> test_validate_foo*.py
    check-bar.py    -> test_check_bar*.py
    """
    stem = script_name.removesuffix(".py")
    test_prefix = "test_" + stem.replace("-", "_")
    results: list[Path] = []
    if tests_dir.is_dir():
        for p in tests_dir.iterdir():
            if p.name.startswith(test_prefix) and p.suffix == ".py":
                results.append(p)
    return results


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def validate(
    workflow_path: Path,
    tests_dir: Path,
    allowlist_path: Path,
) -> tuple[list[dict], list[dict]]:
    """Run the validation. Returns (gates, findings).

    Each gate: {script, hard, job_name, step_name, has_test_file, has_negative_test}.
    Each finding: {script, kind, message}.
    """
    gates = _parse_workflow(workflow_path)
    allowlist = _parse_allowlist(allowlist_path)
    findings: list[dict] = []

    # Deduplicate gates by script name (same script may appear in multiple steps).
    seen: set[str] = set()
    deduped: list[dict] = []
    for g in gates:
        if g["script"] not in seen:
            seen.add(g["script"])
            deduped.append(g)
        else:
            # If any invocation is hard, the gate is hard.
            for d in deduped:
                if d["script"] == g["script"] and g["hard"]:
                    d["hard"] = True

    for g in deduped:
        test_files = _find_test_files(g["script"], tests_dir)
        g["has_test_file"] = len(test_files) > 0
        g["has_negative_test"] = any(_has_negative_test(tf, g["script"]) for tf in test_files)
        g["allowlisted"] = g["script"] in allowlist

    # Check hard gates without negative tests.
    for g in deduped:
        if not g["hard"]:
            continue
        if g["has_negative_test"]:
            continue
        if g["script"] in allowlist:
            continue
        kind = "missing-test-file" if not g["has_test_file"] else "no-negative-test"
        findings.append(
            {
                "script": g["script"],
                "kind": kind,
                "message": (
                    f"{g['script']}: hard gate has no test proving it can fail"
                    if kind == "no-negative-test"
                    else f"{g['script']}: hard gate has no test file"
                ),
            }
        )

    # Check stale allowlist entries.
    gate_scripts = {g["script"] for g in deduped}
    for script, reason in allowlist.items():
        # Stale if: script is no longer in CI.
        if script not in gate_scripts:
            findings.append(
                {
                    "script": script,
                    "kind": "stale-allowlist-not-in-ci",
                    "message": f"{script}: allowlisted but no longer in CI — remove from allowlist",
                }
            )
            continue
        # Stale if: script now has a negative test.
        for g in deduped:
            if g["script"] == script and g["has_negative_test"]:
                findings.append(
                    {
                        "script": script,
                        "kind": "stale-allowlist-has-test",
                        "message": f"{script}: allowlisted but now has a negative test — remove from allowlist",
                    }
                )
                break

    return deduped, findings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_table(gates: list[dict], findings: list[dict]) -> None:
    """Print a human-readable results table."""
    print(f"{'Script':<45} {'Type':<10} {'Test File':<10} {'Neg Test':<10} {'Status'}")
    print("-" * 95)

    for g in sorted(gates, key=lambda x: x["script"]):
        gate_type = "hard" if g["hard"] else "advisory"
        has_file = "yes" if g.get("has_test_file") else "no"
        has_neg = "yes" if g.get("has_negative_test") else "no"

        if not g["hard"]:
            status = "skip (advisory)"
        elif g.get("has_negative_test"):
            status = "OK"
        elif g.get("allowlisted"):
            status = "allowlisted"
        else:
            status = "FAIL"

        print(f"{g['script']:<45} {gate_type:<10} {has_file:<10} {has_neg:<10} {status}")

    print()
    if findings:
        print(f"{len(findings)} finding(s):")
        for f in findings:
            print(f"  {f['kind']}: {f['message']}")
    else:
        print("0 finding(s): every hard gate has a negative test or an explicit allowlist entry.")


def _print_json(gates: list[dict], findings: list[dict]) -> None:
    """Print JSON output."""
    output = {
        "gates": gates,
        "findings": findings,
        "pass": len(findings) == 0,
    }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Validate that every hard CI gate has a negative test.

    Returns:
        0 if all hard gates pass, 1 if any finding exists.
    """
    parser = argparse.ArgumentParser(
        description="Validate that every hard CI gate has at least one test proving it can fail."
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=None,
        help="Path to GitHub Actions workflow (default: .github/workflows/test.yml)",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=None,
        help="Path to tests directory (default: scripts/tests)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Path to allowlist file (default: scripts/negative-control-allowlist.txt)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON instead of human-readable table",
    )
    args = parser.parse_args()

    repo_root = args.repo_root or REPO_ROOT
    workflow = args.workflow or (repo_root / ".github" / "workflows" / "test.yml")
    tests_dir = args.tests_dir or (repo_root / "scripts" / "tests")
    allowlist = args.allowlist or (repo_root / "scripts" / "negative-control-allowlist.txt")

    if not workflow.exists():
        print(f"ERROR: workflow not found: {workflow}", file=sys.stderr)
        return 1

    gates, findings = validate(workflow, tests_dir, allowlist)

    if args.json_output:
        _print_json(gates, findings)
    else:
        _print_table(gates, findings)

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
