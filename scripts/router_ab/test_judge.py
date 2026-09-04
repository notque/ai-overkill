import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("blind_judge", Path(__file__).with_name("judge.py"))
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def stream(*events):
    return "\n".join(json.dumps(e) for e in events)


def complete(input_tokens=10, cached_input_tokens=3, output_tokens=2):
    return {
        "type": "turn.completed",
        "usage": {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
        },
    }


def test_sum_all_completed_turns():
    assert judge.parse_events(stream(complete(), complete(20, 5, 4))) == {
        "input_tokens": 30,
        "cached_input_tokens": 8,
        "output_tokens": 6,
    }


@pytest.mark.parametrize(
    "event",
    [
        {"type": "error", "message": "retrying"},
        {"type": "turn.failed"},
        {"type": "item.started", "item": {"type": "command_execution"}},
        {"type": "item.started", "item": {"type": "function_call"}},
        {"type": "turn.completed", "usage": {}},
        complete(-1, 0),
        complete(True, 0),
        complete(2, 3),
        complete(output_tokens="2"),
    ],
)
def test_invalid_stream(event):
    with pytest.raises(ValueError):
        judge.parse_events(stream(complete(), event))


def test_malformed_and_absent_stream():
    for raw in ["", "broken json", "[]"]:
        with pytest.raises(ValueError):
            judge.parse_events(raw)


def test_packet_metadata_whitening(tmp_path):
    path = tmp_path / "packets.jsonl"
    raw = {
        "id": "opaque",
        "request": "Fix it",
        "response": {"answer": "done"},
        "arm": "secret",
        "policy": "secret",
        "tokens": 100,
        "timing": 5,
        "mapping": {"opaque": "secret"},
        "rubric": {
            "checks": [{"id": "c1", "criterion": "Works", "points": 1}],
            "critical_failures": [],
            "author": "secret",
        },
    }
    path.write_text(json.dumps(raw))
    packets = judge.prepare_packets(path, tmp_path)
    assert "secret" not in json.dumps(packets)
    assert set(packets[0]) == {"id", "request", "context", "response", "rubric"}


def test_manifest_freezes_inputs_and_coverage(tmp_path):
    tmp_path = tmp_path / "isolated"
    tmp_path.mkdir()
    manifest = {
        "packets": [{"id": "a"}],
        "instruction": "fixed",
        "schema": {},
        "model": "gpt-6-astra",
        "effort": "low",
        "assignments": [1, 2],
    }
    judge.freeze_manifest(tmp_path, manifest)
    judge.freeze_manifest(tmp_path, manifest)
    for change in [{"packets": []}, {"instruction": "changed"}, {"assignments": [1]}]:
        with pytest.raises(ValueError):
            judge.freeze_manifest(tmp_path, {**manifest, **change})


def test_invalid_resume_preserved_without_cli(tmp_path, monkeypatch):
    batch = [{"id": "opaque", "request": "task", "response": "response", "rubric": {}}]
    fingerprint = judge.digest(
        {
            "packets": batch,
            "instruction": judge.INSTRUCTION,
            "schema": judge.SCHEMA,
            "model": "gpt-6-astra",
            "effort": "low",
            "pass": 1,
        }
    )
    target = tmp_path / f"pass-1-{fingerprint[:16]}"
    target.mkdir()
    original = {"fingerprint": fingerprint, "pass": 1, "packet_ids": ["opaque"], "valid": False, "error": "turn.failed"}
    judge.write_json(target / "result.json", original)
    monkeypatch.setattr(judge.subprocess, "run", lambda *_a, **_k: pytest.fail("retried invalid run"))
    assert judge.run_batch(1, batch, SimpleNamespace(out=tmp_path)) == original
    original["packet_ids"] = []
    judge.write_json(target / "result.json", original)
    with pytest.raises(ValueError, match="coverage"):
        judge.run_batch(1, batch, SimpleNamespace(out=tmp_path))


def test_missing_check_invalid():
    packet = {"id": "opaque", "rubric": {"checks": [{"id": "c1"}], "critical_failures": []}}
    with pytest.raises(ValueError, match="criterion"):
        judge.validate({"judgments": [{"id": "opaque", "checks": [], "critical_violations": []}]}, [packet])
