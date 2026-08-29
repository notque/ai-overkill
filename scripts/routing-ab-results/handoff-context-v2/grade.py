#!/usr/bin/env python3
"""Requirement coverage of the dispatched prompt(s) for the long request."""

import json
import re
import subprocess
import sys
from pathlib import Path

ARM = sys.argv[1]
PFX = sys.argv[2] if len(sys.argv) > 2 else "long"
OUT = Path("/tmp/ab-handoff") / f"{PFX}-{ARM}"
WT = f"/tmp/ab-handoff/wt/{PFX}-{ARM}"
PROJ = Path.home() / ".claude" / "projects"
REQ = Path("/tmp/ab-handoff/T8.txt" if PFX == "long" else "/tmp/ab-handoff/T9-turn1.txt").read_text()

# One regex per requirement; matched case-insensitively against a prompt.
REQS = {
    "R1 recorder file": r"routing-decision-recorder\.py",
    "R2 seven labels": r"Prior results",
    "R2b repo-state header": r"Repo state",
    "R3 spec_score 0-7": r"spec_score",
    "R4 spec_missing list": r"spec_missing",
    "R5 prompt_chars": r"prompt_chars",
    "R6 NULL without marker": r"(NULL|None|null).{0,80}(marker|do-route)|(marker|do-route).{0,80}(NULL|None|null)",
    "R7 learning_db_v2 ALTER": r"learning_db_v2",
    "R7b pipeline-column pattern": r"pipeline column|line 337|:337",
    "R7c idempotent": r"idempotent|twice",
    "R8 hot path <50ms": r"50 ?ms",
    "R8b module-level compile": r"module level|module-level",
    "R9 env var": r"VEXJOY_SPEC_SCORE_DISABLE",
    "R10 five tests a-e": r"pre-migration|migration test",
    "R10b build_preamble in test": r"build_preamble",
    "R11 ruff both": r"ruff format --check",
    "R11b validate-hook-health": r"validate-hook-health",
    "R12 do not touch build-dispatch/skills": r"(not|never|do not).{0,40}build-dispatch|build-dispatch.{0,60}(not|never)",
    "R13 do not commit": r"(do not|don't|never) commit|not commit",
    "R14 report diff-stat + timing": r"diff --stat",
    "R15 why (A/B 3/3)": r"3/3|A/B",
    "R16 record_route_fit pattern": r"record_route_fit",
}
if PFX == "long2":
    REQS.update(
        {
            "D8 handoff-report subcommand": r"handoff-report",
            "D8b histogram 0-7": r"histogram",
            "D8c underspecified by score": r"underspecified",
            "D8d empty-table message": r"no scored dispatches yet",
            "D10 test_learning_db_cli": r"test_learning_db_cli",
            "F4 next migration number checked": r"next free|not assumed|schema_migrations",
            "O1 Gaps excluded": r"Gaps",
        }
    )


def prompts_for(sid):
    for f in PROJ.glob(f"*/{sid}.jsonl"):
        out = []
        for line in f.read_text().splitlines():
            try:
                ev = json.loads(line)
            except Exception:
                continue
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Agent":
                    out.append((b["input"].get("subagent_type"), b["input"].get("prompt", "")))
        return out
    return []


j = json.loads((OUT / "T8.json").read_text())
ps = prompts_for(j["session_id"])
union = "\n".join(p for _, p in ps)
cov = {k: bool(re.search(rx, union, re.I | re.S)) for k, rx in REQS.items()}
largest = max((p for _, p in ps), key=len, default="")
cov_largest = sum(bool(re.search(rx, largest, re.I | re.S)) for rx in REQS.values())

rc, diffstat = subprocess.run(["git", "diff", "--stat"], cwd=WT, capture_output=True, text=True).returncode, ""
diffstat = (
    subprocess.run(["git", "diff", "--stat"], cwd=WT, capture_output=True, text=True).stdout.strip().splitlines()[-1:]
)
tests = (
    subprocess.run(
        ["python3", "-m", "pytest", "hooks/tests/test_routing_decision_recorder.py", "-q"],
        cwd=WT,
        capture_output=True,
        text=True,
    )
    .stdout.strip()
    .splitlines()[-1:]
)
grep = (
    subprocess.run(
        "grep -c 'spec_score' hooks/routing-decision-recorder.py hooks/lib/learning_db_v2.py hooks/tests/test_routing_decision_recorder.py",
        shell=True,
        cwd=WT,
        capture_output=True,
        text=True,
    )
    .stdout.strip()
    .replace("\n", " ")
)
touched = subprocess.run(["git", "diff", "--name-only"], cwd=WT, capture_output=True, text=True).stdout.split()
forbidden = [f for f in touched if f.startswith("skills/") or f == "scripts/build-dispatch.py"]

print(
    json.dumps(
        {
            "arm": (OUT / "ARM").read_text().strip(),
            "request_chars": len(REQ),
            "dispatches": [(t, len(p)) for t, p in ps],
            "largest_prompt_chars": len(largest),
            "union_chars": len(union),
            "coverage_union": f"{sum(cov.values())}/{len(REQS)}",
            "coverage_largest_single": f"{cov_largest}/{len(REQS)}",
            "missing_in_union": [k for k, v in cov.items() if not v],
            "outcome": {
                "diffstat": diffstat,
                "tests": tests,
                "spec_score_mentions": grep,
                "forbidden_files": forbidden,
            },
            "cost_usd": round(j.get("total_cost_usd", 0), 2),
            "turns": j.get("num_turns"),
        },
        indent=1,
    )
)
