import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("runner", Path(__file__).with_name("runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_cached_answer_must_match_recorded_model_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stdout = "\n".join(
                map(
                    json.dumps,
                    [
                        {"type": "item.completed", "item": {"type": "agent_message", "text": '{"route":"original"}'}},
                        {
                            "type": "turn.completed",
                            "usage": {"input_tokens": 5, "cached_input_tokens": 0, "output_tokens": 3},
                        },
                    ],
                )
            )
            (directory / "stdout.jsonl").write_text(stdout)
            parsed = runner.parse_events(stdout)
            result = {
                **parsed,
                "uid": "one",
                "prompt_sha256": runner.digest(b"prompt"),
                "fixture_hashes": {},
                "answer": {"route": "original"},
                "returncode": 0,
                "timed_out": False,
                "success": True,
            }
            (directory / "final.txt").write_text(result["last_message"])
            runner.validate_cached(result, {"uid": "one"}, "prompt", {}, directory)
            result.update(answer={"route": "substituted"}, last_message='{"route":"substituted"}')
            (directory / "final.txt").write_text(result["last_message"])
            with self.assertRaisesRegex(ValueError, "outcome mismatch"):
                runner.validate_cached(result, {"uid": "one"}, "prompt", {}, directory)

    def test_partial_attempt_is_preserved_without_resampling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results"
            directory = output / "raw" / "baseline" / "one"
            directory.mkdir(parents=True)
            artifact = directory / "prompt.txt"
            artifact.write_text("interrupted prompt")
            snapshot = {str(root / "arm.txt"): b"policy", str(root / "task.txt"): b"task"}
            protocol = {"arms": {"baseline": {"instruction_file": "arm.txt"}}}
            with self.assertRaisesRegex(ValueError, "Interrupted attempt"):
                runner.run_one(
                    root, protocol, {"prompt_file": "task.txt"}, {"arm": "baseline", "uid": "one"}, output, {}, snapshot
                )
            self.assertEqual(artifact.read_text(), "interrupted prompt")
            self.assertFalse((directory / "result.json").exists())

    def test_any_malformed_completion_invalidates_all_usage(self):
        good = {"type": "turn.completed", "usage": {"input_tokens": 7, "cached_input_tokens": 3, "output_tokens": 2}}
        for bad_usage in [
            None,
            {},
            [],
            {"input_tokens": 1, "cached_input_tokens": 2, "output_tokens": 0},
            {"input_tokens": True, "cached_input_tokens": 0, "output_tokens": 0},
            {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": -1},
        ]:
            for events in [
                [good, {"type": "turn.completed", "usage": bad_usage}],
                [{"type": "turn.completed", "usage": bad_usage}, good],
            ]:
                with self.subTest(usage=bad_usage, first=events[0]):
                    parsed = runner.parse_events("\n".join(map(json.dumps, events)))
                    self.assertFalse(parsed["usage_known"])
                    self.assertIsNone(parsed["usage"])

    def test_all_tool_and_unknown_items_fail_closed(self):
        for event_type in ["item.started", "item.updated", "item.completed"]:
            for item_type in ["command_execution", "future_remote_tool", "image_generation", "file_read"]:
                with self.subTest(event=event_type, item=item_type):
                    parsed = runner.parse_events(json.dumps({"type": event_type, "item": {"type": item_type}}))
                    self.assertEqual(len(parsed["tool_events"]), 1)
        for bad_item in [None, [], "tool"]:
            parsed = runner.parse_events(json.dumps({"type": "item.started", "item": bad_item}))
            self.assertTrue(parsed["parse_errors"])

    def test_runtime_error_and_non_tool_items(self):
        parsed = runner.parse_events(json.dumps({"type": "notice", "error": {"message": "failed"}}))
        self.assertTrue(parsed["runtime_errors"])
        for item in ["agent_message", "reasoning", "todo_list"]:
            self.assertFalse(
                runner.parse_events(json.dumps({"type": "item.started", "item": {"type": item}}))["tool_events"]
            )

    def test_freeze_persists_digest_keyed_input_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            data = b"policy contents"
            hashes = {"policy.txt": runner.digest(data)}
            runner.freeze(output, hashes, {"seed": 1}, [{"id": "one", "suite": "dev"}], {"policy.txt": data})
            stored = output / "inputs" / hashes["policy.txt"]
            self.assertEqual(stored.read_bytes(), data)
            stored.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                runner.freeze(output, hashes, {"seed": 1}, [{"id": "one", "suite": "dev"}], {"policy.txt": data})

    def test_started_tool_is_violation(self):
        parsed = runner.parse_events(
            json.dumps({"type": "item.started", "item": {"type": "command_execution", "command": "pwd"}})
        )
        self.assertEqual(len(parsed["tool_events"]), 1)

    def test_snapshot_survives_live_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            arm, task = root / "arm.txt", root / "task.txt"
            arm.write_text("original policy")
            task.write_text("original task")
            hashes = {str(p): runner.digest(p.read_bytes()) for p in [arm, task]}
            snapshot = runner.snapshot_inputs(hashes)
            arm.write_text("changed policy")
            protocol = {"arms": {"baseline": {"instruction_file": "arm.txt"}}}
            prompt = runner.prompt_for(root, protocol, {"prompt_file": "task.txt"}, "baseline", snapshot)
            self.assertIn("original policy", prompt)
            self.assertNotIn("changed policy", prompt)
            with self.assertRaises(ValueError):
                runner.snapshot_inputs(hashes)

    def test_cached_assignment_and_false_success_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "stdout.jsonl").write_text("")
            (root / "final.txt").write_text("{}")
            result = {
                **runner.parse_events(""),
                "uid": "a",
                "prompt_sha256": runner.digest(b"prompt"),
                "fixture_hashes": {},
                "answer": {},
                "last_message": "{}",
                "returncode": 0,
                "timed_out": False,
                "success": False,
            }
            self.assertIs(runner.validate_cached(result, {"uid": "a"}, "prompt", {}, root), result)
            with self.assertRaises(ValueError):
                runner.validate_cached(result, {"uid": "b"}, "prompt", {}, root)
            result["success"] = True
            with self.assertRaises(ValueError):
                runner.validate_cached(result, {"uid": "a"}, "prompt", {}, root)

    def test_parser(self):
        events = [
            {"type": "turn.completed", "usage": {"input_tokens": 12, "cached_input_tokens": 5, "output_tokens": 3}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": '{"route":"x"}'}},
        ]
        parsed = runner.parse_events("\n".join(map(json.dumps, events)))
        self.assertTrue(parsed["usage_known"])
        self.assertEqual(parsed["usage"]["cached_input_tokens"], 5)
        self.assertEqual(parsed["last_message"], '{"route":"x"}')

    def test_missing_usage(self):
        for payload in ["", "{}", '{"type":"turn.completed","usage":{"input_tokens":1}}']:
            self.assertFalse(runner.parse_events(payload)["usage_known"])
            self.assertIsNone(runner.parse_events(payload)["usage"])

    def test_assignments(self):
        cases = [{"id": "one", "suite": "dev"}, {"id": "two", "suite": "holdout"}]
        rows = runner.assignments(cases, 5, 77)
        self.assertEqual(rows, runner.assignments(cases, 5, 77))
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({r["uid"] for r in rows}), 20)
        self.assertEqual(sum(r["arm"] == "baseline" for r in rows), 10)

    def test_arm_hash_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            protocol = {"seed": 1, "repeats": 5}
            cases = [{"id": "one", "suite": "dev"}]
            runner.freeze(output, {"arm.txt": "old"}, protocol, cases)
            runner.freeze(output, {"arm.txt": "old"}, protocol, cases)
            with self.assertRaisesRegex(ValueError, "Frozen manifest changed"):
                runner.freeze(output, {"arm.txt": "new"}, protocol, cases)


if __name__ == "__main__":
    unittest.main()
