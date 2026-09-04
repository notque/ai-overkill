#!/usr/bin/env python3
"""Isolated router-decision experiment; not an execution-quality evaluation."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import subprocess
import tempfile
import time
from pathlib import Path

from process_control import run_process


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def validate_usage(usage):
    keys = ("input_tokens", "cached_input_tokens", "output_tokens")
    if not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] < 0 for key in keys):
        raise ValueError("Usage requires nonnegative integer input/cache/output tokens")
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        raise ValueError("Cached input exceeds input tokens")
    return {key: usage[key] for key in keys}


def parse_events(text):
    events, errors, usage, messages, tool_events = [], [], [], [], []
    usage_valid = True
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append(line)
            continue
        if not isinstance(event, dict):
            errors.append(line)
            continue
        events.append(event)
        if event.get("type") == "turn.completed":
            usage.append(event.get("usage"))
            try:
                validate_usage(event.get("usage"))
            except ValueError:
                usage_valid = False
        item = event.get("item", {})
        if not isinstance(item, dict):
            errors.append(line)
            continue
        if item and item.get("type") not in {"agent_message", "reasoning", "todo_list"}:
            tool_events.append(item)
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            if isinstance(item.get("text"), str):
                messages.append(item["text"])
            else:
                errors.append(line)
    keys = ("input_tokens", "cached_input_tokens", "output_tokens")
    known = bool(usage) and usage_valid
    return {
        "usage_known": known,
        "usage": {key: sum(row[key] for row in usage) for key in keys} if known else None,
        "usage_records": usage,
        "parse_errors": errors,
        "last_message": messages[-1] if messages else "",
        "tool_events": tool_events,
        "runtime_errors": [e for e in events if e.get("type") in ("error", "turn.failed") or e.get("error")],
    }


def assignments(cases, repeats, seed):
    rng, result = random.Random(seed), []
    for case in sorted(cases, key=lambda c: c["id"]):
        for repeat in range(repeats):
            arms = ["baseline", "challenger"]
            rng.shuffle(arms)
            for position, arm in enumerate(arms):
                uid = digest(f"{seed}:{case['id']}:{repeat}:{arm}".encode())[:20]
                result.append(
                    {
                        "uid": uid,
                        "case_id": case["id"],
                        "suite": case["suite"],
                        "repeat": repeat,
                        "arm": arm,
                        "position": position,
                    }
                )
    rng.shuffle(result)
    return result


def load(protocol_path):
    protocol_path = Path(protocol_path).resolve()
    root, protocol = protocol_path.parent, read_json(protocol_path)
    cases_path = root / protocol.get("cases_file", "cases.json")
    cases = read_json(cases_path)
    if isinstance(cases, dict):
        cases = cases["cases"]
    if set(protocol["arms"]) != {"baseline", "challenger"}:
        raise ValueError("Expected baseline and challenger arms")
    if protocol.get("model", "gpt-6-astra") != "gpt-6-astra":
        raise ValueError("Model must be gpt-6-astra")
    if protocol.get("effort", "low") != "low":
        raise ValueError("Effort must be low")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate case IDs")
    paths = [
        protocol_path,
        cases_path,
        Path(__file__).resolve(),
        Path(__file__).with_name("process_control.py").resolve(),
    ]
    paths += [root / arm["instruction_file"] for arm in protocol["arms"].values()]
    paths += [root / name for name in protocol.get("common_context_files", [])]
    paths += [root / case["prompt_file"] for case in cases]
    hashes = {str(p.resolve()): digest(p.read_bytes()) for p in paths}
    return root, protocol, cases, hashes


def freeze(output, hashes, protocol, cases, snapshot=None):
    manifest = {
        "fixture_hashes": hashes,
        "runtime": runtime_metadata(protocol),
        "assignments": assignments(
            cases, protocol.get("repeats", protocol.get("runs_per_arm", 5)), protocol.get("seed", 20260904)
        ),
    }
    path = output / "manifest.json"
    if path.exists():
        if read_json(path) != manifest:
            raise ValueError("Frozen manifest changed; use a new output directory")
    else:
        write_json(path, manifest)
    if snapshot is not None:
        if set(snapshot) != set(hashes) or any(digest(data) != hashes[name] for name, data in snapshot.items()):
            raise ValueError("Snapshot does not match frozen input hashes")
        inputs = output / "inputs"
        inputs.mkdir(exist_ok=True)
        for name, data in snapshot.items():
            destination = inputs / hashes[name]
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError("Digest-keyed input store corrupted")
            if not destination.exists():
                destination.write_bytes(data)
    return manifest


def runtime_metadata(protocol):
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=10)
    if version.returncode:
        raise ValueError("Unable to record Codex CLI version")
    return {
        "cli_version": version.stdout.strip(),
        "model_alias": protocol.get("model", "gpt-6-astra"),
        "effort": protocol.get("effort", "low"),
        "sandbox": "read-only",
        "approval": "never",
        "ignore_user_config": True,
        "ignore_rules": True,
        "ephemeral": True,
        "disabled_features": ["hooks", "plugins"],
        "skills_include_instructions": False,
        "project_doc_max_bytes": 0,
        "tools": "native runtime tools; instructed not to use; observed events invalidate routing run",
    }


def snapshot_inputs(hashes):
    snapshot = {path: Path(path).read_bytes() for path in hashes}
    if any(digest(data) != hashes[path] for path, data in snapshot.items()):
        raise ValueError("Input changed while taking frozen snapshot")
    return snapshot


def prompt_for(root, protocol, case, arm, snapshot=None):
    def content(name):
        path = (root / name).resolve()
        return snapshot[str(path)].decode() if snapshot is not None else path.read_text()

    sections = [content(protocol["arms"][arm]["instruction_file"])]
    sections += [content(name) for name in protocol.get("common_context_files", [])]
    sections += ["User request:\n" + content(case["prompt_file"])]
    return "\n\n".join(sections)


def validate_cached(result, assignment, prompt, hashes, directory):
    if any(result.get(key) != value for key, value in assignment.items()):
        raise ValueError("Cached result assignment mismatch")
    if result.get("prompt_sha256") != digest(prompt.encode()) or result.get("fixture_hashes") != hashes:
        raise ValueError("Cached result provenance mismatch")
    parsed = parse_events((directory / "stdout.jsonl").read_text())
    for key in ("usage", "usage_known", "usage_records", "tool_events", "parse_errors", "runtime_errors"):
        if result.get(key) != parsed[key]:
            raise ValueError("Cached result telemetry mismatch: " + key)
    final = (directory / "final.txt").read_text()
    if result.get("last_message") != final:
        raise ValueError("Cached final message mismatch")
    try:
        answer = json.loads(final)
    except json.JSONDecodeError:
        answer = None
    success = (
        result.get("returncode") == 0
        and not result.get("timed_out")
        and parsed["usage_known"]
        and isinstance(answer, dict)
        and final == parsed["last_message"]
        and not parsed["tool_events"]
        and not parsed["runtime_errors"]
        and not parsed["parse_errors"]
    )
    if result.get("answer") != answer or result.get("success") is not success:
        raise ValueError("Cached result outcome mismatch")
    return result


def run_one(root, protocol, case, assignment, output, hashes, snapshot=None):
    directory = output / "raw" / assignment["arm"] / assignment["uid"]
    result_file = directory / "result.json"
    snapshot = snapshot if snapshot is not None else snapshot_inputs(hashes)
    prompt = prompt_for(root, protocol, case, assignment["arm"], snapshot)
    if result_file.exists():
        return validate_cached(read_json(result_file), assignment, prompt, hashes, directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(
            "Interrupted attempt has raw artifacts but no result; preserve it and use a fresh output directory"
        )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "prompt.txt").write_text(prompt)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="router-decision-") as workspace:
        final_path = Path(workspace) / "final.txt"
        command = [
            "codex",
            "-a",
            "never",
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "--disable",
            "hooks",
            "--disable",
            "plugins",
            "-c",
            "skills.include_instructions=false",
            "-c",
            "project_doc_max_bytes=0",
            "--json",
            "-m",
            protocol.get("model", "gpt-6-astra"),
            "-c",
            "model_reasoning_effort=" + protocol.get("effort", "low"),
            "-s",
            "read-only",
            "-C",
            workspace,
            "--skip-git-repo-check",
            "-o",
            str(final_path),
            "-",
        ]
        timed_out = False
        try:
            process = run_process(
                command,
                input=prompt,
                timeout=min(protocol.get("timeout_seconds", 180), 180),
            )
            stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
        except subprocess.TimeoutExpired as error:
            timed_out, returncode = True, 124
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
        except OSError as error:
            stdout, stderr, returncode = "", str(error), 127
        parsed = parse_events(stdout)
        final = final_path.read_text() if final_path.exists() else parsed["last_message"]
    try:
        answer = json.loads(final)
        valid_answer = isinstance(answer, dict)
    except json.JSONDecodeError:
        answer, valid_answer = None, False
    result = {
        **assignment,
        **parsed,
        "answer": answer,
        "last_message": final,
        "duration_seconds": time.monotonic() - started,
        "returncode": returncode,
        "timed_out": timed_out,
        "prompt_sha256": digest(prompt.encode()),
        "fixture_hashes": hashes,
        "executor_command": command,
        "success": returncode == 0
        and not timed_out
        and parsed["usage_known"]
        and valid_answer
        and final == parsed["last_message"]
        and not parsed["tool_events"]
        and not parsed["runtime_errors"]
        and not parsed["parse_errors"],
    }
    (directory / "stdout.jsonl").write_text(stdout)
    (directory / "stderr.txt").write_text(stderr)
    (directory / "final.txt").write_text(final)
    write_json(result_file, result)
    return result


def export_blind(root, protocol, cases, output, manifest, snapshot=None):
    packets, mapping, missing = [], {}, []
    snapshot = snapshot if snapshot is not None else snapshot_inputs(manifest["fixture_hashes"])
    lookup = {case["id"]: case for case in cases}
    for assignment in manifest["assignments"]:
        path = output / "raw" / assignment["arm"] / assignment["uid"] / "result.json"
        if not path.exists():
            missing.append(assignment)
            continue
        case = lookup[assignment["case_id"]]
        prompt = prompt_for(root, protocol, case, assignment["arm"], snapshot)
        result = validate_cached(read_json(path), assignment, prompt, manifest["fixture_hashes"], path.parent)
        opaque = digest(("judge:" + assignment["uid"]).encode())[:24]
        case = lookup[assignment["case_id"]]
        packets.append(
            {
                "id": opaque,
                "task": snapshot[str((root / case["prompt_file"]).resolve())].decode(),
                "answer": result["last_message"],
            }
        )
        mapping[opaque] = assignment
    random.Random(protocol.get("seed", 20260904) + 1).shuffle(packets)
    write_json(output / "blind" / "packets.json", packets)
    write_json(output / "private" / "judge-map.json", mapping)
    write_json(
        output / "private" / "export-status.json",
        {
            "complete": not missing,
            "missing_assignments": missing,
            "expected": len(manifest["assignments"]),
            "exported": len(packets),
        },
    )
    return len(packets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "export-blind", "validate"], nargs="?", default="run")
    parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("protocol.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--phase", choices=["baseline", "challenger", "both"], default="both")
    parser.add_argument("--cases", choices=["dev", "holdout", "all"], default="all")
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()
    root, protocol, cases, hashes = load(args.protocol)
    snapshot = snapshot_inputs(hashes)
    output = (args.output or root / "results").resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A directory lock prevents two runners from racing resume/output writes.
    import fcntl

    with (output / ".runner.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = freeze(output, hashes, protocol, cases, snapshot)
        if args.command == "validate":
            print(json.dumps({"valid": True, "runs": len(manifest["assignments"])}))
            return
        if args.command == "export-blind":
            count = export_blind(root, protocol, cases, output, manifest, snapshot)
            print(json.dumps({"packets": count, **read_json(output / "private" / "export-status.json")}))
            return
        selected = [
            a
            for a in manifest["assignments"]
            if (args.phase == "both" or a["arm"] == args.phase) and (args.cases == "all" or a["suite"] == args.cases)
        ]
        lookup = {case["id"]: case for case in cases}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.concurrency, 6))) as pool:
            futures = [
                pool.submit(run_one, root, protocol, lookup[a["case_id"]], a, output, hashes, snapshot)
                for a in selected
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                print(json.dumps({key: result[key] for key in ("uid", "arm", "case_id", "success")}), flush=True)


if __name__ == "__main__":
    main()
