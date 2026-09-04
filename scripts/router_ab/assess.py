#!/usr/bin/env python3
"""Fail-closed blind packet preparation and frozen routing metrics; never authorizes production promotion."""

import argparse
import json
import random
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import mean, median

import judge
import runner


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def frozen(routing):
    manifest = read(routing / "manifest.json")
    snapshots = {}
    for name, sha in manifest["fixture_hashes"].items():
        data = (routing / "inputs" / sha).read_bytes()
        require(runner.digest(data) == sha, "Frozen input digest mismatch")
        snapshots[name] = data
    protocols = []
    for name, data in snapshots.items():
        if name.endswith(".json"):
            value = json.loads(data)
            if isinstance(value, dict) and {"arms", "cases_file"} <= value.keys():
                protocols.append((Path(name).parent, value))
    require(len(protocols) == 1, "Expected one frozen protocol")
    root, protocol = protocols[0]
    cases = json.loads(snapshots[str((root / protocol["cases_file"]).resolve())])
    cases = cases["cases"] if isinstance(cases, dict) else cases
    expected = runner.assignments(cases, protocol.get("repeats", 5), protocol.get("seed", 20260904))
    require(manifest["assignments"] == expected, "Frozen assignment denominator mismatch")
    require(len({a["uid"] for a in expected}) == len(expected), "Duplicate assignment")
    return manifest, snapshots, root, protocol, {c["id"]: c for c in cases}


def records(routing, suite):
    manifest, snapshots, root, protocol, cases = frozen(routing)
    selected = [a for a in manifest["assignments"] if suite == "all" or a["suite"] == suite]
    require(bool(selected), "Empty selected suite")
    result = []
    for assignment in selected:
        directory = routing / "raw" / assignment["arm"] / assignment["uid"]
        case = cases[assignment["case_id"]]
        prompt = runner.prompt_for(root, protocol, case, assignment["arm"], snapshots)
        record = runner.validate_cached(
            read(directory / "result.json"), assignment, prompt, manifest["fixture_hashes"], directory
        )
        task = snapshots[str((root / case["prompt_file"]).resolve())].decode()
        result.append((assignment, record, task))
    return manifest, protocol, cases, result


def prepare(routing, packets_path, map_path, suite, rubrics_dir):
    manifest, _, _, results = records(routing, suite)
    rubrics = {}
    for path in sorted(rubrics_dir.glob("*rubrics.jsonl")):
        for rubric in lines(path):
            require(rubric["id"] not in rubrics, "Duplicate rubric id")
            rubrics[rubric["id"]] = rubric
    packets, mapping = [], {}
    for assignment, record, task in results:
        identifier = runner.digest(("judge:" + assignment["uid"]).encode())[:24]
        rubric_id = assignment["case_id"]
        require(rubric_id in rubrics, "Missing independent rubric")
        rubric = rubrics[rubric_id]
        require(bool(rubric.get("checks")), "Empty rubric")
        require(all(c.get("points", 1) == 1 for c in rubric["checks"]), "Only unit-weight checks supported")
        rubric = {
            "checks": [{"id": c["id"], "criterion": c["criterion"]} for c in rubric["checks"]],
            "critical_failures": rubric.get("critical_failures", []),
        }
        packet = {
            "id": identifier,
            "request": task,
            "context": "",
            "response": record["last_message"],
            "rubric": rubric,
        }
        packets.append(packet)
        mapping[identifier] = {
            "assignment": assignment,
            "success": record["success"],
            "packet_sha256": judge.digest(packet),
            "rubric": rubric,
            "rubric_sha256": judge.digest(rubric),
            "packet": packet,
        }
    random.Random(4905).shuffle(packets)
    private = {
        "manifest_sha256": runner.digest((routing / "manifest.json").read_bytes()),
        "suite": suite,
        "expected": len(results),
        "packets": mapping,
        "packet_order": [p["id"] for p in packets],
        "judge_config": judge_config(),
    }
    require(not packets_path.exists() and not map_path.exists(), "Refusing to overwrite frozen packets/map")
    packets_path.parent.mkdir(parents=True, exist_ok=True)
    packets_path.write_text("".join(json.dumps(p) + "\n" for p in packets))
    runner.write_json(map_path, private)
    return {"packets": len(packets), "failures": sum(not r["success"] for _, r, _ in results)}


def judge_config():
    return {
        "version": 2,
        "instruction": judge.INSTRUCTION,
        "schema": judge.SCHEMA,
        "model": "gpt-6-astra",
        "effort": "low",
        "passes": 2,
        "seed": 4904,
        "batch_size": 5,
        "timeout": 300,
        "calibration": False,
    }


def judge_batches(packets, config):
    assignments = []
    for number in range(1, config["passes"] + 1):
        order = list(packets)
        random.Random(config["seed"] + number).shuffle(order)
        while order:
            batch, remaining, seen = [], [], set()
            for packet in order:
                key = judge.digest(packet["request"])
                if len(batch) < config["batch_size"] and key not in seen:
                    batch.append(packet)
                    seen.add(key)
                else:
                    remaining.append(packet)
            assignments.append((number, batch))
            order = remaining
    return assignments


def verified_judgments(directory, packets, config):
    require(config == judge_config(), "Frozen judge configuration mismatch")
    batches = judge_batches(packets, config)
    expected = {
        **config,
        "packets": packets,
        "assignments": [{"pass": number, "packet_ids": [p["id"] for p in batch]} for number, batch in batches],
    }
    require(read(directory / "manifest.json") == expected, "Judge manifest packet/configuration mismatch")
    rows, directories = [], set()
    for number, batch in batches:
        fingerprint = judge.digest(
            {
                "packets": batch,
                "instruction": config["instruction"],
                "schema": config["schema"],
                "model": config["model"],
                "effort": config["effort"],
                "pass": number,
            }
        )
        target = directory / f"pass-{number}-{fingerprint[:16]}"
        directories.add(target.name)
        result = read(target / "result.json")
        require(
            result.get("valid") is True
            and type(result.get("returncode")) is int
            and result["returncode"] == 0
            and result.get("calibration") is False
            and not result.get("error"),
            "Invalid judge batch",
        )
        require(
            result.get("fingerprint") == fingerprint
            and result.get("pass") == number
            and result.get("packet_ids") == [p["id"] for p in batch],
            "Judge batch identity mismatch",
        )
        stdout = (target / "events.jsonl").read_text()
        require(judge.validate_usage(result["usage"]) == judge.parse_events(stdout), "Judge usage mismatch")
        final = read(target / "final.json")
        messages = [
            e["item"]["text"]
            for e in lines(target / "events.jsonl")
            if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"
        ]
        require(bool(messages) and json.loads(messages[-1]) == final, "Judge final differs from raw response")
        scores = judge.validate(final, batch)
        require(result["judgments"] == scores, "Judge scores differ from raw final")
        require(read(target / "schema.json") == config["schema"], "Judge schema mismatch")
        prefix = config["instruction"] + "\nPACKETS:\n"
        prompt = (target / "prompt.txt").read_text()
        require(prompt.startswith(prefix) and json.loads(prompt[len(prefix) :]) == batch, "Judge prompt mismatch")
        rows.extend({"pass": number, **row} for row in scores)
    require(
        {p.name for p in directory.glob("pass-*") if p.is_dir()} == directories,
        "Unexpected or missing judge batch directory",
    )
    require(lines(directory / "judgments.jsonl") == rows, "Exported judgments differ from validated batches")
    return rows


def assess(routing, judge_dir, map_path):
    private = read(map_path)
    manifest, protocol, cases, results = records(routing, private["suite"])
    require(
        private["manifest_sha256"] == runner.digest((routing / "manifest.json").read_bytes()),
        "Mapping provenance mismatch",
    )
    mapping = private["packets"]
    require(private["expected"] == len(results) == len(mapping), "Mapping denominator mismatch")
    indexed = {}
    for assignment, result, task in results:
        identifier = runner.digest(("judge:" + assignment["uid"]).encode())[:24]
        require(identifier in mapping, "Missing packet mapping")
        entry = mapping[identifier]
        require(
            entry["assignment"] == assignment and entry["success"] is result["success"], "Mapping identity mismatch"
        )
        packet = {
            "id": identifier,
            "request": task,
            "context": "",
            "response": result["last_message"],
            "rubric": entry["rubric"],
        }
        require(
            entry["packet_sha256"] == judge.digest(packet) and entry["packet"] == packet,
            "Mapped response or rubric changed",
        )
        require(entry["rubric_sha256"] == judge.digest(entry["rubric"]), "Mapped rubric changed")
        indexed[identifier] = (assignment, result)
    judgments = defaultdict(list)
    order = private["packet_order"]
    require(len(order) == len(mapping) and set(order) == set(mapping), "Packet order coverage mismatch")
    packets = [mapping[key]["packet"] for key in order]
    for row in verified_judgments(judge_dir, packets, private["judge_config"]):
        require(row["id"] in mapping, "Unknown judgment packet")
        judgments[row["id"]].append(row)
    utility, critical, tokens = defaultdict(list), defaultdict(int), {}
    disagreement = []
    failures = 0
    for identifier, (assignment, result) in indexed.items():
        rows = judgments[identifier]
        require(len(rows) == 2 and {r.get("pass") for r in rows} == {1, 2}, "Missing or duplicate judgment pass")
        rubric = mapping[identifier]["rubric"]
        rubric = {"checks": rubric["checks"], "critical_failures": rubric.get("critical_failures", [])}
        for row in rows:
            judge.validate({"judgments": [row]}, [{"id": identifier, "rubric": rubric}])
        signatures = [
            (
                sorted((c["id"], c["score"]) for c in r["checks"]),
                sorted((c["criterion"], c["violated"]) for c in r["critical_violations"]),
            )
            for r in rows
        ]
        if signatures[0] != signatures[1]:
            disagreement.append(identifier)
        key = (assignment["case_id"], assignment["arm"])
        checks = rows[0]["checks"]
        utility[key].append(Fraction(sum(c["score"] for c in checks), len(checks)))
        critical[key] += sum(c["violated"] for c in rows[0]["critical_violations"])
        failures += not result["success"]
        require(result["usage_known"], "Unknown usage invalidates measured denominator")
        tokens[(assignment["case_id"], assignment["repeat"], assignment["arm"])] = result["usage"]
    regressions = [
        case
        for case in {a["case_id"] for a, _, _ in results}
        if mean(utility[(case, "challenger")]) < mean(utility[(case, "baseline")])
        or critical[(case, "challenger")] > critical[(case, "baseline")]
    ]
    metrics = {}
    for metric in ("total_tokens", "input_tokens", "cached_input_tokens", "output_tokens"):

        def value(usage, key=metric):
            return usage["input_tokens"] + usage["output_tokens"] if key == "total_tokens" else usage[key]

        baseline, challenger, delta = [], [], []
        for case, repeat, arm in tokens:
            if arm == "baseline":
                b, c = value(tokens[(case, repeat, arm)]), value(tokens[(case, repeat, "challenger")])
                baseline.append(b)
                challenger.append(c)
                delta.append(b - c)
        bmed, cmed = median(baseline), median(challenger)
        metrics[metric] = {
            "baseline_median": bmed,
            "challenger_median": cmed,
            "paired_saving_median": median(delta),
            "reduction": (bmed - cmed) / bmed if bmed else 0,
        }
    total = metrics["total_tokens"]
    efficient = (
        total["reduction"] >= max(0.05, protocol.get("target_reduction", 0.05)) and total["paired_saving_median"] > 23
    )
    status = (
        "INCONCLUSIVE" if disagreement else "REJECT" if failures or regressions or not efficient else "REVIEW_READY"
    )
    prerequisites = [
        "Independent calibration certification",
        "Execution-backed verification with isolated evaluator authority",
        "Project-required CI and authorized review/release",
    ]
    if private["suite"] != "all" or len(results) != 300:
        prerequisites.append("Full 300-assignment routing comparison")
    return {
        "status": status,
        "runs": len(results),
        "failures": failures,
        "disagreements": disagreement,
        "regressions": regressions,
        "metrics": metrics,
        "production_authorized": False,
        "unresolved_prerequisites": prerequisites,
        "critical_violations": {
            case: {arm: critical[(case, arm)] for arm in ("baseline", "challenger")}
            for case in sorted({a["case_id"] for a, _, _ in results})
        },
        "case_utility": {
            case: {arm: float(mean(utility[(case, arm)])) for arm in ("baseline", "challenger")}
            for case in sorted({a["case_id"] for a, _, _ in results})
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "assess"):
        command = sub.add_parser(name)
        command.add_argument("--routing-results", type=Path, required=True)
        command.add_argument("--map", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--packets", type=Path, required=True)
            command.add_argument("--suite", choices=("dev", "holdout", "all"), default="all")
            command.add_argument(
                "--rubrics", type=Path, default=Path(__file__).resolve().parents[2] / "evals" / "router-value"
            )
        else:
            command.add_argument("--judge-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (
            prepare(args.routing_results, args.packets, args.map, args.suite, args.rubrics)
            if args.command == "prepare"
            else assess(args.routing_results, args.judge_dir, args.map)
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"status": "INVALID", "error": str(error)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
