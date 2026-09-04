#!/usr/bin/env python3
"""Replay frozen philosophy comparisons without network or model calls."""

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replay(root, arguments, reports):
    before = {name: read(root / name) for name in reports}
    result = subprocess.run(
        [sys.executable, "-B", str(root / "analyze.py"), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    assert not result.stderr.strip(), result.stderr
    output = json.loads(result.stdout)
    assert isinstance(output, dict) and output
    expected_code = 1 if arguments == ["score", "dev"] else 0
    assert result.returncode == expected_code, (arguments, result.returncode, output)
    if arguments == ["score", "dev"]:
        assert output["status"] == "REJECT" and output["regressions"] == ["v3dev009"]
    elif arguments == ["score"]:
        assert output["status"] == "ELIGIBLE_ON_OUTPUT_CONSTRAINTS_ONLY"
    for name, expected in before.items():
        assert read(root / name) == expected, (arguments, name)


def verify(evidence):
    index = read(evidence / "archive-index.json")
    with tempfile.TemporaryDirectory(prefix="philosophy-v3-replay-") as temporary:
        workspace = Path(temporary)
        extracted = set()
        for name, archive in index["archives"].items():
            assert sha((evidence / name).read_bytes()) == archive["sha256"]
            expected = {member["path"]: member for member in archive["members"]}
            with tarfile.open(evidence / name, "r:gz") as stream:
                members = stream.getmembers()
                assert len(members) == len(expected)
                assert {member.name for member in members} == set(expected)
                for member in members:
                    assert member.isfile() and not Path(member.name).is_absolute()
                    assert member.name not in extracted
                    extracted.add(member.name)
                    target = workspace / member.name
                    assert target.resolve().is_relative_to(workspace)
                    data = stream.extractfile(member).read()
                    assert sha(data) == expected[member.name]["sha256"]
                    assert len(data) == expected[member.name]["bytes"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
        results = {}
        for label in ("meaning", "constraints"):
            root = workspace / label
            for manifest in ("FINAL-FREEZE.json", "preregistration.json"):
                for name, digest in read(root / manifest)["files"].items():
                    assert sha((root / name).read_bytes()) == digest, name
            final = read(root / "FINAL-REPORT.json")
            assert sha((root / "preregistration.json").read_bytes()) == final["preregistration_sha256"]
            assert sha((root / "inputs/challenger.md").read_bytes()) == index["candidate_sha256"]
            totals, calls, unknown = Counter(), 0, []
            for path in root.rglob("result.json"):
                record = read(path)
                if "usage" not in record:
                    continue
                calls += 1
                usage = record["usage"]
                if record.get("usage_known") is False or usage is None:
                    unknown.append(str(path.relative_to(root)))
                    continue
                for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                    assert type(usage[key]) is int and usage[key] >= 0
                assert usage["cached_input_tokens"] <= usage["input_tokens"]
                totals.update(usage)
            assert not unknown and not final["unknown_cli_attempts"]
            assert totals == final["known_cli_usage"]
            assert totals["input_tokens"] + totals["output_tokens"] == final["known_cli_total_tokens"]
            assert final["recovery_calls"] == 0
            replay(root, ["calibration"], ["calibration-verdict.json"])
            if label == "meaning":
                assert calls == 424
                assert final["fresh_workers_started"] == 0 and not final["fresh_holdout_evaluated"]
                replay(root, ["workers", "dev"], ["dev/worker-report.json", "dev/output-compliance.json"])
                replay(root, ["disputes", "dev"], ["dev/disputed-blind.json"])
                replay(root, ["score", "dev"], ["dev/VERDICT.json"])
                verdict = read(root / "dev/VERDICT.json")
                assert verdict["status"] == final["status"] == "REJECT"
                assert verdict["regressions"] == ["v3dev009"]
                failure = next(row for row in verdict["case_utility"] if row["id"] == "v3dev009")
                assert failure["exact_means"] == {"baseline": "1", "challenger": "2/3"}
                receipt = read(root / "dev/adjudicator-resume-review.json")
                assert sha((root / "dev/adjudications.json").read_bytes()) == receipt["resolution_sha256"]
            else:
                assert calls == 92
                replay(root, ["workers"], ["worker-report.json"])
                replay(root, ["disputes"], ["disputed-blind.json"])
                replay(root, ["score"], ["VERDICT.json"])
                verdict = read(root / "VERDICT.json")
                assert verdict["status"] == "ELIGIBLE_ON_OUTPUT_CONSTRAINTS_ONLY"
                assert not verdict["regressions"] and not verdict["unresolved"]
                assert read(root / "worker-report.json")["format_passes"] == 60
            results[label] = {
                "status": verdict["status"],
                "recorded_cli_calls": calls,
                "known_cli_tokens": final["known_cli_total_tokens"],
            }
        return {"verified": True, "comparisons": results, "promotion_authorized": False}


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).resolve().parent), indent=2))
