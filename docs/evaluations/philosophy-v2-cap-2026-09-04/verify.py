#!/usr/bin/env python3
"""Reproduce V2's frozen contract failure from archived records, without model calls."""

import argparse
import hashlib
import importlib
import json
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def usage_events(path):
    events = lines(path)
    result = Counter()
    completions = 0
    for event in events:
        assert isinstance(event, dict)
        assert event.get("type") not in {"error", "turn.failed"} and not event.get("error")
        item = event.get("item", {})
        assert isinstance(item, dict)
        if item:
            assert item.get("type") in {"agent_message", "reasoning", "todo_list"}
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
            assert isinstance(usage, dict)
            for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                assert type(usage.get(key)) is int and usage[key] >= 0
                result[key] += usage[key]
            assert usage["cached_input_tokens"] <= usage["input_tokens"]
            completions += 1
    assert completions
    messages = [
        e["item"]["text"]
        for e in events
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"
    ]
    assert messages
    return result, messages[-1]


def verify(evidence):
    index = read(evidence / "archive-index.json")
    with tempfile.TemporaryDirectory(prefix="philosophy-v2-replay-") as temporary:
        root = Path(temporary)
        for name, archive in index["archives"].items():
            assert sha(evidence / name) == archive["sha256"]
            expected = {m["path"]: m for m in archive["members"]}
            with tarfile.open(evidence / name, "r:gz") as stream:
                members = stream.getmembers()
                assert len(members) == len(expected) and {m.name for m in members} == set(expected)
                for member in members:
                    assert member.isfile() and not Path(member.name).is_absolute()
                    target = root / member.name
                    assert target.resolve().is_relative_to(root)
                    data = stream.extractfile(member).read()
                    assert hashlib.sha256(data).hexdigest() == expected[member.name]["sha256"]
                    assert len(data) == expected[member.name]["bytes"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
        experiment, workers, calibration = root / "experiment", root / "workers", root / "calibration"
        prereg = read(experiment / "preregistration.json")
        for name, digest in prereg["input_hashes"].items():
            assert sha(experiment / name) == digest, name
        verdict = read(experiment / "VERDICT.json")
        for name, digest in verdict["evidence_hashes"].items():
            target = workers / name.removeprefix("results/") if name.startswith("results/") else experiment / name
            assert sha(target) == digest, name
        assert sha(experiment / "analyze.py") == read(experiment / "analysis-freeze.json")["analyze.py"]
        assert (
            sha(experiment / "inputs/challenger.md")
            == verdict["candidate_sha256"]
            == ("e8c33c22987ba0a3cbaa8cbe24314d3b5162a07c0bb2c7b8263b131868f671e3")
        )
        sys.path.insert(0, str(experiment / "harness"))
        assessor = importlib.import_module("assess")
        judge = importlib.import_module("judge")
        manifest, _, cases, records = assessor.records(workers, "all")
        assert len(records) == len(manifest["assignments"]) == 400 and len(cases) == 40
        assert len(list((workers / "raw").glob("*/*/result.json"))) == 400
        assert len(list((workers / "raw").glob("*/*/stdout.jsonl"))) == 400
        totals, counts, failures, samples = Counter(), Counter(), [], defaultdict(list)
        for assignment, record, _task in records:
            folder = workers / "raw" / assignment["arm"] / assignment["uid"]
            usage, final = usage_events(folder / "stdout.jsonl")
            assert record["success"] and record["usage_known"] and not record["timed_out"]
            assert usage == record["usage"] and final == record["last_message"] == (folder / "final.txt").read_text()
            answer = json.loads(final)
            assert isinstance(answer, dict) and set(answer) == {"answer"} and isinstance(answer["answer"], str)
            words = len(answer["answer"].split())
            counts[assignment["arm"]] += 1
            if words > 180:
                failures.append(
                    {
                        "id": assignment["uid"],
                        "case": assignment["case_id"],
                        "arm": assignment["arm"],
                        "keys": ["answer"],
                        "words": words,
                    }
                )
            totals.update(usage)
            samples[(assignment["arm"], assignment["repeat"])].append(usage["input_tokens"] + usage["output_tokens"])
        assert counts == {"baseline": 200, "challenger": 200}
        assert len(failures) == 25 and Counter(f["arm"] for f in failures) == {"baseline": 4, "challenger": 21}
        assert min(f["words"] for f in failures) == 181 and max(f["words"] for f in failures) == 189
        assert sorted(failures, key=lambda f: f["id"]) == sorted(
            read(experiment / "contract-audit.json"), key=lambda f: f["id"]
        )
        corpus_medians = {
            arm: [median(samples[(arm, repeat)]) for repeat in range(5)] for arm in ("baseline", "challenger")
        }
        assert all(len(v) == 40 for v in samples.values()) and len(samples) == 10
        report = read(experiment / "worker-report.json")
        assert report["corpus_medians"] == corpus_medians and not report["raw_and_contract_valid"]
        assert (
            report["usage"] == totals
            and report["total_tokens"] == totals["input_tokens"] + totals["output_tokens"] == 7236407
        )
        baseline, challenger = (median(corpus_medians[arm]) for arm in ("baseline", "challenger"))
        assert report["baseline_median"] == baseline and report["challenger_median"] == challenger
        assert report["saving"] == baseline - challenger and report["reduction"] == (baseline - challenger) / baseline
        expected = read(experiment / "private/calibration-map.json")
        packets = {p["id"]: p for p in lines(experiment / "calibration-packets.jsonl")}
        cal_totals, seen = Counter(), set()
        batches = list(calibration.glob("pass-*/result.json"))
        assert len(batches) == 4
        for path in batches:
            result, folder = read(path), path.parent
            usage, final = usage_events(folder / "events.jsonl")
            assert result["valid"] and result["returncode"] == 0 and usage == result["usage"]
            output = read(folder / "final.json")
            assert json.loads(final) == output
            batch = [packets[identifier] for identifier in result["packet_ids"]]
            assert judge.validate(output, batch) == result["judgments"]
            assert (folder / "prompt.txt").read_text() == judge.INSTRUCTION + "\nPACKETS:\n" + json.dumps(
                batch, ensure_ascii=False
            )
            for row in result["judgments"]:
                key = (row["id"], result["pass"])
                assert key not in seen
                seen.add(key)
                assert {c["id"]: c["score"] for c in row["checks"]} == expected[row["id"]]["expected_checks"]
                assert not any(c["violated"] for c in row["critical_violations"])
            cal_totals.update(usage)
        assert seen == {(identifier, number) for identifier in packets for number in (1, 2)} and len(seen) == 12
        assert cal_totals == read(experiment / "calibration-verdict.json")["usage"]
        assert cal_totals["input_tokens"] + cal_totals["output_tokens"] == 58137
        totals.update(cal_totals)
        assert totals == verdict["all_measured_usage"]
        assert totals["input_tokens"] + totals["output_tokens"] == verdict["all_measured_total_tokens"] == 7294544
        assert verdict["status"] == "REJECT" and not verdict["production_authorized"]
        assert verdict["semantic_judge_calls"] == verdict["unknown_usage_attempts"] == 0
        assert verdict["raw_valid_workers"] == 400 and verdict["response_contract_valid_workers"] == 375
        return {
            "verified": True,
            "raw_valid_workers": 400,
            "contract_valid_workers": 375,
            "violations": {"baseline": 4, "challenger": 21},
            "arm_denominators": 200,
            "measured_tokens": 7294544,
            "semantic_judge_calls": 0,
            "unknown_usage_attempts": 0,
            "status": "REJECT",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence), indent=2))


if __name__ == "__main__":
    main()
