"""Offline checks for the frozen router-value evaluation corpus and hidden oracles."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[2] / "evals" / "router-value"


def jsonl(name):
    return [json.loads(line) for line in (CORPUS / name).read_text().splitlines()]


def test_prompt_hashes_preserve_frozen_experiment():
    frozen = json.loads((CORPUS / "PROMPT_FREEZE.json").read_text())
    assert set(frozen) == {"development_prompts.jsonl", "holdout_prompts.jsonl", "executor_contract.json"}
    for name, digest in frozen.items():
        assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(("split", "count"), [("development", 20), ("holdout", 10)])
def test_executor_prompts_exclude_oracle_and_treatment_labels(split, count):
    prompts = jsonl(f"{split}_prompts.jsonl")
    rubrics = jsonl(f"{split}_rubrics.jsonl")
    assert len(prompts) == len(rubrics) == count
    assert len({case["id"] for case in prompts}) == count
    assert [case["id"] for case in prompts] == [rubric["id"] for rubric in rubrics]
    for case in prompts:
        assert set(case) == {"id", "split", "request", "context", "execution_fixture"}
        assert case["split"] == split
        for rubric in rubrics:
            for criterion in rubric["checks"]:
                assert criterion["id"] not in json.dumps(case)
        fixture = case["execution_fixture"]
        if fixture:
            assert (CORPUS / "fixtures" / fixture).is_dir()
            assert (CORPUS / "evaluators" / fixture / "check.py").is_file()


def test_blind_judge_packets_hide_control_labels_and_include_exact_duplicates():
    packets = jsonl("judge-calibration.jsonl")
    expected = json.loads((CORPUS / "calibration-expected.json").read_text())["expectations"]
    by_id = {packet["packet_id"]: packet for packet in packets}
    assert len(by_id) == len(packets) == 14
    assert set(by_id) == set(expected)
    duplicates = 0
    for packet in packets:
        assert set(packet) == {"packet_id", "task", "response", "rubric_id"}
        assert set(packet["task"]) == {"id", "request", "context"}
        assert packet["rubric_id"] == packet["task"]["id"]
        assert "control" not in packet["response"]
        original_id = expected[packet["packet_id"]].get("duplicate_of")
        if original_id:
            original = by_id[original_id]
            assert packet["response"] == original["response"]
            assert packet["task"] == original["task"]
            duplicates += 1
    assert duplicates == 2


def test_hidden_execution_checkers_reject_bugs_and_accept_references():
    result = subprocess.run(
        [sys.executable, "-B", str(CORPUS / "calibrate.py")],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    calibration = json.loads(result.stdout)
    assert calibration["calibrated"] == 6
    for row in calibration["results"]:
        assert row["fixtures"]["exit"] != 0
        assert row["reference_solutions"]["exit"] == 0
        assert row["fixtures"]["result"]["passed"] < row["fixtures"]["result"]["total"]
        assert row["reference_solutions"]["result"]["passed"] == row["reference_solutions"]["result"]["total"]


@pytest.mark.parametrize("fixture", ["label_only", "sample_timeout", "duplicate_email"])
def test_execution_oracles_reject_protected_effects(tmp_path, fixture):
    workspace = tmp_path / fixture
    shutil.copytree(CORPUS / "reference_solutions" / fixture, workspace)
    if fixture == "label_only":
        config = json.loads((workspace / "ui.json").read_text())
        config["telemetry_key"] = "Submit"
        (workspace / "ui.json").write_text(json.dumps(config))
    elif fixture == "sample_timeout":
        (workspace / "production.json").write_text('{"timeout_seconds":10}\n')
    else:
        app = workspace / "app.py"
        app.write_text(app.read_text().replace("return list(users)", "return users"))
    result = subprocess.run(
        [sys.executable, "-B", str(CORPUS / "evaluators" / fixture / "check.py"), str(workspace)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["passed"] < report["total"]


def test_calibration_comparison_rejects_bad_controls_scored_as_good():
    import importlib.util

    spec = importlib.util.spec_from_file_location("judge_calibration_check", CORPUS / "check_judge_calibration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = {
        "expectations": {
            "opaque-control": {
                "control": "bad",
                "source_case": "case",
                "expected_criteria": {"criterion": 0},
                "expected_critical_failure": True,
            }
        }
    }
    judgments = [
        {
            "pass": pass_index,
            "id": "opaque-control",
            "checks": [{"id": "criterion", "score": 0}],
            "critical_violations": [{"criterion": "forbidden effect", "violated": True}],
        }
        for pass_index in (1, 2)
    ]
    assert module.compare(judgments, expected)["accepted"]
    judgments[0]["checks"][0]["score"] = 1
    assert not module.compare(judgments, expected)["accepted"]
    judgments[0]["checks"][0]["score"] = 0
    judgments[1]["critical_violations"][0]["violated"] = False
    assert not module.compare(judgments, expected)["accepted"]
    assert not module.compare(judgments[:1], expected)["accepted"]
