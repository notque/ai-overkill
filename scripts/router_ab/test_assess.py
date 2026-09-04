"""Synthetic acceptance tests; never loads experiment answers or treatments."""

import json
import tempfile
import unittest
from pathlib import Path

import assess
import judge
import runner


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.routing = self.root / "routing"
        self.packets = self.root / "packets.jsonl"
        self.mapping = self.root / "map.json"
        self.judge_dir = self.root / "judge"
        self.judge_dir.mkdir()
        self.rubrics = self.root / "rubrics"
        self.rubrics.mkdir()
        self.protocol = {
            "arms": {"baseline": {"instruction_file": "base.txt"}, "challenger": {"instruction_file": "candidate.txt"}},
            "cases_file": "cases.json",
            "repeats": 5,
            "seed": 42,
        }
        cases = [
            {"id": f"case-{i}", "suite": "dev" if i < 20 else "holdout", "prompt_file": f"task-{i}.txt"}
            for i in range(30)
        ]
        data = {
            "protocol.json": json.dumps(self.protocol),
            "cases.json": json.dumps(cases),
            "base.txt": "Synthetic policy",
            "candidate.txt": "Synthetic policy shortened",
        }
        data.update({c["prompt_file"]: "Synthetic request " + c["id"] for c in cases})
        snapshots = {str(self.root / k): v.encode() for k, v in data.items()}
        hashes = {k: runner.digest(v) for k, v in snapshots.items()}
        self.assignments = runner.assignments(cases, 5, 42)
        manifest = {"fixture_hashes": hashes, "assignments": self.assignments}
        runner.write_json(self.routing / "manifest.json", manifest)
        (self.routing / "inputs").mkdir()
        for name, sha in hashes.items():
            (self.routing / "inputs" / sha).write_bytes(snapshots[name])
        lookup = {c["id"]: c for c in cases}
        for a in self.assignments:
            directory = self.directory(a)
            directory.mkdir(parents=True)
            usage = {
                "input_tokens": 1000 if a["arm"] == "baseline" else 900,
                "output_tokens": 100,
                "cached_input_tokens": 0,
            }
            stdout = "\n".join(
                json.dumps(event)
                for event in [
                    {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
                    {"type": "turn.completed", "usage": usage},
                ]
            )
            parsed = runner.parse_events(stdout)
            prompt = runner.prompt_for(self.root, self.protocol, lookup[a["case_id"]], a["arm"], snapshots)
            result = {
                **a,
                **parsed,
                "answer": {},
                "last_message": "{}",
                "returncode": 0,
                "timed_out": False,
                "success": True,
                "prompt_sha256": runner.digest(prompt.encode()),
                "fixture_hashes": hashes,
            }
            runner.write_json(directory / "result.json", result)
            (directory / "stdout.jsonl").write_text(stdout)
            (directory / "final.txt").write_text("{}")
        (self.rubrics / "synthetic-rubrics.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "id": c["id"],
                        "checks": [{"id": "correct", "criterion": "Meets synthetic request"}],
                        "critical_failures": ["Unsafe action"],
                    }
                )
                + "\n"
                for c in cases
            )
        )

    def directory(self, assignment):
        return self.routing / "raw" / assignment["arm"] / assignment["uid"]

    def prepare(self, suite="all"):
        return assess.prepare(self.routing, self.packets, self.mapping, suite, self.rubrics)

    def scores(self):
        rows = []
        for p in assess.lines(self.packets):
            for number in (1, 2):
                rows.append(
                    {
                        "id": p["id"],
                        "pass": number,
                        "checks": [{"id": "correct", "score": 1, "evidence": "synthetic evidence"}],
                        "critical_violations": [
                            {"criterion": "Unsafe action", "violated": False, "evidence": "No unsafe action proposed"}
                        ],
                    }
                )
        self.write_scores(rows)
        return rows

    def write_scores(self, rows):
        packets = assess.lines(self.packets)
        config = assess.judge_config()
        batches = assess.judge_batches(packets, config)
        manifest = {
            **config,
            "packets": packets,
            "assignments": [{"pass": number, "packet_ids": [p["id"] for p in batch]} for number, batch in batches],
        }
        runner.write_json(self.judge_dir / "manifest.json", manifest)
        exported = []
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
            target = self.judge_dir / f"pass-{number}-{fingerprint[:16]}"
            target.mkdir(exist_ok=True)
            ids = {p["id"] for p in batch}
            selected = [r for r in rows if r["pass"] == number and r["id"] in ids]
            scores = [{k: v for k, v in r.items() if k != "pass"} for r in selected]
            final = {"judgments": scores}
            usage = {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 20}
            result = {
                "valid": True,
                "returncode": 0,
                "calibration": False,
                "fingerprint": fingerprint,
                "pass": number,
                "packet_ids": [p["id"] for p in batch],
                "judgments": scores,
                "usage": usage,
            }
            runner.write_json(target / "result.json", result)
            runner.write_json(target / "final.json", final)
            runner.write_json(target / "schema.json", judge.SCHEMA)
            (target / "prompt.txt").write_text(
                judge.INSTRUCTION + "\nPACKETS:\n" + json.dumps(batch, ensure_ascii=False)
            )
            events = [
                {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(final)}},
                {"type": "turn.completed", "usage": usage},
            ]
            (target / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
            exported.extend(selected)
        (self.judge_dir / "judgments.jsonl").write_text("".join(json.dumps(r) + "\n" for r in exported))

    def result(self):
        return assess.assess(self.routing, self.judge_dir, self.mapping)

    def test_full_denominator_and_pending_execution(self):
        self.assertEqual(self.prepare()["packets"], 300)
        self.scores()
        result = self.result()
        self.assertEqual(result["status"], "REVIEW_READY")
        self.assertEqual(result["runs"], 300)
        self.assertEqual(result["metrics"]["total_tokens"]["paired_saving_median"], 100)
        packet = assess.lines(self.packets)[0]
        self.assertEqual(set(packet), {"id", "request", "context", "response", "rubric"})

    def test_dev_denominator(self):
        self.assertEqual(self.prepare("dev")["packets"], 200)
        self.scores()
        self.assertEqual(self.result()["runs"], 200)

    def test_missing_result_is_not_omitted(self):
        (self.directory(self.assignments[0]) / "result.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.packets.exists())

    def test_duplicate_pass_is_invalid(self):
        self.prepare()
        rows = self.scores()
        rows[1]["pass"] = 1
        self.write_scores(rows)
        with self.assertRaises(ValueError):
            self.result()

    def test_missing_judgment_is_invalid(self):
        self.prepare()
        rows = self.scores()
        self.write_scores(rows[:-1])
        with self.assertRaises(ValueError):
            self.result()

    def test_mapping_tampering_invalid(self):
        self.prepare()
        self.scores()
        mapping = assess.read(self.mapping)
        next(iter(mapping["packets"].values()))["assignment"]["arm"] = "unknown"
        runner.write_json(self.mapping, mapping)
        with self.assertRaisesRegex(ValueError, "Mapping identity"):
            self.result()

    def test_disagreement_inconclusive(self):
        self.prepare()
        rows = self.scores()
        rows[0]["checks"][0]["score"] = 0
        self.write_scores(rows)
        self.assertEqual(self.result()["status"], "INCONCLUSIVE")

    def test_failure_remains_in_denominator(self):
        directory = self.directory(self.assignments[0])
        result = assess.read(directory / "result.json")
        result.update(returncode=1, success=False)
        runner.write_json(directory / "result.json", result)
        self.assertEqual(self.prepare(), {"packets": 300, "failures": 1})
        self.scores()
        self.assertEqual(self.result()["status"], "REJECT")
        self.assertEqual(self.result()["runs"], 300)

    def test_case_regression_rejects_even_with_token_savings(self):
        self.prepare()
        rows = self.scores()
        mapping = assess.read(self.mapping)["packets"]
        target = next(key for key, value in mapping.items() if value["assignment"]["arm"] == "challenger")
        for row in rows:
            if row["id"] == target:
                row["checks"][0]["score"] = 0
        self.write_scores(rows)
        self.assertEqual(self.result()["status"], "REJECT")
        self.assertEqual(len(self.result()["regressions"]), 1)

    def assess_three_check_distributions(self, baseline, challenger):
        rubrics = assess.lines(self.rubrics / "synthetic-rubrics.jsonl")
        for rubric in rubrics:
            rubric["checks"] = [{"id": f"check-{i}", "criterion": f"Synthetic requirement {i}"} for i in range(3)]
        (self.rubrics / "synthetic-rubrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rubrics))
        self.prepare()
        mapping = assess.read(self.mapping)["packets"]
        rows = []
        for packet in assess.lines(self.packets):
            assignment = mapping[packet["id"]]["assignment"]
            counts = baseline if assignment["arm"] == "baseline" else challenger
            earned = counts[assignment["repeat"]] if assignment["case_id"] == "case-0" else 3
            for number in (1, 2):
                rows.append(
                    {
                        "id": packet["id"],
                        "pass": number,
                        "checks": [
                            {"id": f"check-{i}", "score": int(i < earned), "evidence": "synthetic evidence"}
                            for i in range(3)
                        ],
                        "critical_violations": [
                            {"criterion": "Unsafe action", "violated": False, "evidence": "No unsafe action proposed"}
                        ],
                    }
                )
        self.write_scores(rows)
        return self.result()

    def test_equal_totals_across_different_trial_distributions_do_not_regress(self):
        result = self.assess_three_check_distributions((0, 0, 0, 0, 3), (0, 0, 0, 1, 2))
        self.assertEqual(result["regressions"], [])
        self.assertEqual(result["status"], "REVIEW_READY")
        self.assertEqual(result["case_utility"]["case-0"], {"baseline": 0.2, "challenger": 0.2})
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_one_point_loss_still_regresses_with_fractional_trial_scores(self):
        result = self.assess_three_check_distributions((0, 0, 0, 0, 3), (0, 0, 0, 0, 2))
        self.assertEqual(result["regressions"], ["case-0"])
        self.assertEqual(result["status"], "REJECT")
        self.assertEqual(result["case_utility"]["case-0"], {"baseline": 0.2, "challenger": 2 / 15})

    def test_additional_critical_failure_rejects(self):
        self.prepare()
        rows = self.scores()
        mapping = assess.read(self.mapping)["packets"]
        target = next(key for key, value in mapping.items() if value["assignment"]["arm"] == "challenger")
        for row in rows:
            if row["id"] == target:
                row["critical_violations"][0]["violated"] = True
        self.write_scores(rows)
        self.assertEqual(self.result()["status"], "REJECT")

    def test_embedded_rubric_survives_external_rubric_drift(self):
        self.prepare()
        before = judge.prepare_packets(self.packets, self.rubrics)
        (self.rubrics / "synthetic-rubrics.jsonl").write_text("")
        self.assertEqual(judge.prepare_packets(self.packets, self.rubrics), before)
        self.assertEqual(before, assess.lines(self.packets))

    def test_missing_judge_batch_is_invalid(self):
        self.prepare()
        self.scores()
        next(self.judge_dir.glob("pass-*/result.json")).unlink()
        with self.assertRaises(FileNotFoundError):
            self.result()

    def test_judge_response_drift_rejected(self):
        self.prepare()
        self.scores()
        manifest = assess.read(self.judge_dir / "manifest.json")
        manifest["packets"][0]["response"] = "changed same ID"
        runner.write_json(self.judge_dir / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "manifest packet"):
            self.result()

    def test_judge_rubric_drift_rejected(self):
        self.prepare()
        self.scores()
        manifest = assess.read(self.judge_dir / "manifest.json")
        manifest["packets"][0]["rubric"]["checks"][0]["criterion"] = "Different criterion, same ID"
        runner.write_json(self.judge_dir / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "manifest packet"):
            self.result()

    def test_invalid_batch_cannot_be_hidden_by_export(self):
        self.prepare()
        self.scores()
        path = next(self.judge_dir.glob("pass-*/result.json"))
        result = assess.read(path)
        result["valid"] = False
        runner.write_json(path, result)
        with self.assertRaisesRegex(ValueError, "Invalid judge batch"):
            self.result()

    def test_missing_usage_column_rejected(self):
        self.prepare()
        self.scores()
        path = next(self.judge_dir.glob("pass-*/events.jsonl"))
        events = assess.lines(path)
        del events[-1]["usage"]["output_tokens"]
        path.write_text("".join(json.dumps(e) + "\n" for e in events))
        with self.assertRaisesRegex(ValueError, "Usage requires"):
            self.result()

    def test_final_score_tampering_rejected(self):
        self.prepare()
        self.scores()
        path = next(self.judge_dir.glob("pass-*/result.json"))
        result = assess.read(path)
        result["judgments"][0]["checks"][0]["score"] = 0
        runner.write_json(path, result)
        with self.assertRaisesRegex(ValueError, "scores differ"):
            self.result()

    def test_review_ready_never_authorizes_production(self):
        self.prepare()
        self.scores()
        result = self.result()
        self.assertEqual(result["status"], "REVIEW_READY")
        self.assertFalse(result["production_authorized"])
        self.assertGreaterEqual(len(result["unresolved_prerequisites"]), 3)

    def test_frozen_bytes_required(self):
        next((self.routing / "inputs").iterdir()).write_text("changed")
        with self.assertRaisesRegex(ValueError, "Frozen input digest"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
