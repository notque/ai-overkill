"""Check blind judge calibration controls without changing frozen expectations."""

import argparse
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent
# Additional failures adjudicated from compound criteria, not treatment results.
ADJUDICATED = {"VRR-07": {"VRR-07-C1"}, "VRR-04": {"VRR-04-C2"}}


def compare(judgments, expected, passes=2):
    controls = expected["expectations"]
    errors = []
    seen = {}
    for row in judgments:
        key = (row.get("pass"), row.get("id"))
        if key in seen or key[0] not in range(1, passes + 1) or key[1] not in controls:
            errors.append(f"Unexpected or duplicate judgment: {key}")
            continue
        seen[key] = row
        oracle = controls[key[1]]
        checks = row.get("checks", [])
        scores = {c.get("id"): c.get("score") for c in checks}
        wanted = oracle["expected_criteria"]
        if len(checks) != len(wanted) or set(scores) != set(wanted):
            errors.append(f"Incomplete criteria: {key}")
            continue
        for criterion, score in scores.items():
            allowed_extra = oracle["control"] == "bad" and criterion in ADJUDICATED.get(oracle["source_case"], set())
            if type(score) is not int or score not in (0, 1):
                errors.append(f"Invalid score: {key} {criterion}")
            elif score != wanted[criterion] and not (allowed_extra and score == 0):
                errors.append(f"Unexpected score: {key} {criterion}")
        critical = row.get("critical_violations", [])
        if any(type(c.get("violated")) is not bool for c in critical):
            errors.append(f"Invalid critical flag: {key}")
        if any(c.get("violated") is True for c in critical) != oracle["expected_critical_failure"]:
            errors.append(f"Incorrect critical result: {key}")
    for pass_index in range(1, passes + 1):
        for packet, oracle in controls.items():
            key = (pass_index, packet)
            if key not in seen:
                errors.append(f"Missing judgment: {key}")
                continue
            duplicate = oracle.get("duplicate_of")
            if duplicate and (pass_index, duplicate) in seen:
                original = seen[(pass_index, duplicate)]
                row = seen[key]

                def scores(r):
                    return {c["id"]: c["score"] for c in r["checks"]}

                def flags(r):
                    return {c["criterion"]: c["violated"] for c in r["critical_violations"]}

                if scores(row) != scores(original) or flags(row) != flags(original):
                    errors.append(f"Duplicate control disagreement: {key}")
    return {"accepted": not errors, "judgments": len(judgments), "passes": passes, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judgments", required=True, type=Path)
    parser.add_argument("--expected", type=Path, default=CORPUS / "calibration-expected.json")
    parser.add_argument("--passes", type=int, default=2)
    args = parser.parse_args()
    if args.passes < 2:
        parser.error("Require at least two calibration passes")
    judgments = [json.loads(line) for line in args.judgments.read_text().splitlines() if line.strip()]
    report = compare(judgments, json.loads(args.expected.read_text()), args.passes)
    print(json.dumps(report))
    raise SystemExit(0 if report["accepted"] else 1)


if __name__ == "__main__":
    main()
