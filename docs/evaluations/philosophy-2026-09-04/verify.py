#!/usr/bin/env python3
"""Verify the rejected V1 result from preserved votes, adjudication and raw runs.

Extract the evidence archives together; then run:
python verify.py --experiment experiment --workers workers --judges judges --verifier verifier
No model calls. The verifier directory supplies the archived integrity assessor.
"""

import argparse
import hashlib
import importlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

p = argparse.ArgumentParser(description=__doc__)
for key in ("experiment", "workers", "judges", "verifier"):
    p.add_argument("--" + key, type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.verifier.resolve()))
assess = importlib.import_module("assess")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def equal(actual, expected):
    if isinstance(actual, float) or isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)
    elif isinstance(actual, dict):
        assert actual.keys() == expected.keys()
        for key in actual:
            equal(actual[key], expected[key])
    else:
        assert actual == expected, (actual, expected)


# Independent raw-integrity pass before examining post-adjudication arithmetic.
raw = assess.assess(a.workers, a.judges, a.experiment / "judge-map.json")
assert raw["runs"] == 300 and raw["failures"] == 0
mapping = read(a.experiment / "judge-map.json")["packets"]
verdict = read(a.experiment / "VERDICT.json")
adjpath = a.experiment / "adjudications.json"
assert sha(adjpath) == "37da040d59f803def3c2175d056a336744e357e2f00e3307c59a5baf1320d424"
assert verdict["adjudication_sha256"] == sha(adjpath)
adjudication = read(adjpath)
assert adjudication["unresolved_count"] == 0
assert adjudication["rule_sha256"] == sha(a.experiment / "adjudication-rule.md")
assert adjudication["input_sha256"] == sha(a.experiment / "disputed-blind.json")
votes = defaultdict(dict)
rows = [json.loads(line) for line in (a.judges / "judgments.jsonl").read_text().splitlines() if line.strip()]
assert len(rows) == 600
for row in rows:
    assert row["id"] in mapping and row["pass"] in (1, 2)
    assert row["pass"] not in votes[row["id"]]
    votes[row["id"]][row["pass"]] = row
assert set(votes) == set(mapping) and all(set(v) == {1, 2} for v in votes.values())
adj = {row["packetid"]: row for row in adjudication["adjudications"]}
assert len(adj) == len(adjudication["adjudications"]) == 9
saved_rows = read(a.experiment / "adjudicated-scores.json")
saved = {row["id"]: row for row in saved_rows}
assert len(saved_rows) == len(saved) == 300 and set(saved) == set(mapping)
bycase = defaultdict(list)
tokens = {}
disputes = set()
changed_checks = 0
for identifier, passes in votes.items():
    first, second = passes[1], passes[2]
    left = {c["id"]: c["score"] for c in first["checks"]}
    right = {c["id"]: c["score"] for c in second["checks"]}
    expected = {c["id"] for c in mapping[identifier]["rubric"]["checks"]}
    assert set(left) == set(right) == expected
    assert all(type(x) is int and x in (0, 1) for x in [*left.values(), *right.values()])
    # This experiment has no critical-violation criteria or votes.
    assert not first["critical_violations"] and not second["critical_violations"]
    differing = {key for key in left if left[key] != right[key]}
    resolved = dict(left)
    if differing:
        disputes.add(identifier)
        decisions = adj[identifier]
        equal(sorted(decisions["original_judgments"], key=lambda x: x["pass"]), [first, second])
        checks = {c["checkid"]: c for c in decisions["checks"]}
        assert len(checks) == len(decisions["checks"]) and set(checks) == expected
        for key, item in checks.items():
            assert item["disputed"] is (key in differing)
            assert type(item["score"]) is int and item["score"] in (0, 1)
            if key in differing:
                resolved[key] = item["score"]
                changed_checks += 1
            else:
                assert item["score"] == left[key] == right[key]
    else:
        assert identifier not in adj
    assignment = mapping[identifier]["assignment"]
    equal(saved[identifier]["assignment"], assignment)
    equal(saved[identifier]["scores"], resolved)
    utility = mean(resolved.values())
    equal(saved[identifier]["utility"], utility)
    bycase[(assignment["case_id"], assignment["arm"])].append(utility)
    record = read(a.workers / "raw" / assignment["arm"] / assignment["uid"] / "result.json")
    assert record["success"] and record["usage_known"]
    tokens[(assignment["case_id"], assignment["repeat"], assignment["arm"])] = record["usage"]
assert disputes == set(adj) == set(raw["disagreements"])
assert len(bycase) == 60 and all(len(values) == 5 for values in bycase.values())
case_means = {
    case: {arm: mean(bycase[(case, arm)]) for arm in ("baseline", "challenger")}
    for case in sorted({key[0] for key in bycase})
}
equal(case_means, verdict["case_utility"])
regressions = sorted(case for case, scores in case_means.items() if scores["challenger"] < scores["baseline"])
assert regressions == verdict["regressions"] and len(regressions) == 8
metrics = {}
for metric in ("total_tokens", "input_tokens", "cached_input_tokens", "output_tokens"):

    def value(usage, key=metric):
        return usage["input_tokens"] + usage["output_tokens"] if key == "total_tokens" else usage[key]

    baseline, challenger, paired = [], [], []
    for (case, repeat, arm), usage in tokens.items():
        if arm == "baseline":
            b, c = value(usage), value(tokens[(case, repeat, "challenger")])
            baseline.append(b)
            challenger.append(c)
            paired.append(b - c)
    assert len(baseline) == len(challenger) == 150
    b, c = median(baseline), median(challenger)
    metrics[metric] = {
        "baseline_median": b,
        "challenger_median": c,
        "paired_saving_median": median(paired),
        "reduction": (b - c) / b if b else 0,
    }
equal(metrics, verdict["metrics"])
equal(metrics, raw["metrics"])
assert verdict["runs"] == 300 and verdict["failures"] == 0
assert verdict["status"] == "REJECT" and verdict["production_authorized"] is False
assert verdict["original_disputed_packets"] == 9 and verdict["unresolved_disagreements"] == 0
print(
    json.dumps(
        {
            "verified": True,
            "runs": 300,
            "original_votes": 600,
            "disputed_packets": len(disputes),
            "disputed_checks_resolved": changed_checks,
            "undisputed_scores_preserved": True,
            "regressions": regressions,
            "total_token_metrics": metrics["total_tokens"],
            "status": "REJECT",
        },
        indent=2,
    )
)
