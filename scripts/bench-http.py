#!/usr/bin/env python3
"""Measure HTTP latency for a local API, and print one number.

WHAT IT MEASURES
    Per-request wall-clock latency in milliseconds, timed around each request
    from connect through the last byte of the response body. Requests come from
    a pinned fixture file, replayed in order and looped as needed, so every run
    sends the same work in the same sequence.

THE ONE NUMBER
    By default stdout carries a single value: the median across runs of p99
    latency in milliseconds. Lower is better. Choose another with --metric
    (p50, p95, p99, mean, or rps; for rps, higher is better).

    Use this as the MEASURE command of a hill-climb SPEC:
        METRIC   p99 latency, ms (lower is better)
        MEASURE  python3 scripts/bench-http.py --url http://127.0.0.1:8000 \
                     --fixture fixtures/api.jsonl --requests 500
        TARGET   e.g. <= 200

HOW TO PIN THE FIXTURE
    --fixture takes a JSONL file: one JSON object per line, one request each.

        {"method": "GET",  "path": "/health"}
        {"method": "POST", "path": "/search", "body": {"q": "hello"},
         "headers": {"content-type": "application/json"}}

    Fields: path (required); method (default GET); headers (object); body
    (object, list, or string; an object or list is sent as JSON); expect_status
    (int or list of ints, default: any 2xx or 3xx).

    --json reports the fixture's SHA-256. Record it in the hill-climb ledger:
    it proves the dataset did not change between iterations. Never edit,
    reorder, or re-sample the fixture mid-loop. Pin these too: --requests or
    --duration, --concurrency, --warmup, --runs, the server build, and its
    data. A warm cache and a cold cache are different workloads.

SAFETY
    The target must be a loopback host. This machine is a public web server;
    benchmarking hammers whatever it points at. --allow-remote is required to
    aim anywhere else, and remains the caller's decision to justify.

KNOWN NOISE SOURCES
    Thermal throttling after minutes of load; other load on the machine, this
    script's own CPU cost included, which is why --concurrency above a few
    threads measures the harness as much as the server; garbage collection in
    the server, which lands in the high percentiles p99 reads; JIT or cache
    warm-up, which --warmup discards; connection setup, which is included by
    design and is real cost for the first request in a run.

EXIT CODES
    0 ok. 1 bad usage, unreadable fixture, or a non-loopback target without
    --allow-remote. 2 the run failed: no successful request, or an unexpected
    response status. 3 run-to-run spread exceeded --max-spread.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HIGHER_IS_BETTER = {"rps"}


def die(message: str, code: int = 1) -> None:
    """Print a diagnostic to stderr and exit."""
    print(f"bench-http: {message}", file=sys.stderr)
    sys.exit(code)


@dataclass
class Request:
    """One fixture line, already normalized into what the sender needs."""

    method: str
    path: str
    headers: dict[str, str]
    body: bytes | None
    expect_status: list[int] | None


@dataclass
class RunResult:
    """Latency samples and error counts from a single run."""

    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    wall_s: float = 0.0


def is_loopback(host: str) -> bool:
    """Report whether the host resolves only to loopback addresses."""
    if host in {"localhost", ""}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_loopback for info in infos)


def load_fixture(path: Path) -> tuple[list[Request], str]:
    """Parse the JSONL fixture and return its requests with the file checksum."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        die(f"cannot read fixture {path}: {exc}")
    checksum = hashlib.sha256(raw).hexdigest()
    requests: list[Request] = []
    for lineno, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"{path}:{lineno}: not valid JSON: {exc}")
        if not isinstance(entry, dict) or "path" not in entry:
            die(f'{path}:{lineno}: each line needs an object with a "path" field')
        headers = {str(k): str(v) for k, v in (entry.get("headers") or {}).items()}
        body = entry.get("body")
        if isinstance(body, (dict, list)):
            body_bytes = json.dumps(body).encode("utf-8")
            headers.setdefault("content-type", "application/json")
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        elif body is None:
            body_bytes = None
        else:
            die(f"{path}:{lineno}: body must be an object, list, or string")
        expect = entry.get("expect_status")
        if isinstance(expect, int):
            expect = [expect]
        requests.append(
            Request(
                method=str(entry.get("method", "GET")).upper(),
                path=str(entry["path"]),
                headers=headers,
                body=body_bytes,
                expect_status=expect,
            )
        )
    if not requests:
        die(f"fixture {path} has no requests")
    return requests, checksum


def send(base_url: str, req: Request, timeout: float) -> tuple[float, str | None]:
    """Send one request. Return its latency in ms and an error string, if any."""
    url = urllib.parse.urljoin(base_url, req.path)
    request = urllib.request.Request(url, data=req.body, method=req.method)
    for key, value in req.headers.items():
        request.add_header(key, value)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
    except Exception as exc:  # any transport failure is one error sample
        return (time.perf_counter() - start) * 1000.0, f"{req.method} {req.path}: {exc}"
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    expected = req.expect_status
    ok = status in expected if expected else 200 <= status < 400
    if not ok:
        want = expected if expected else "2xx/3xx"
        return elapsed_ms, f"{req.method} {req.path}: status {status}, expected {want}"
    return elapsed_ms, None


def run_once(args: argparse.Namespace, requests: list[Request]) -> RunResult:
    """Run warmup then the measured load, and collect the samples."""
    result = RunResult()
    counter = threading.Lock()
    index = [0]
    stop_at = time.perf_counter() + args.duration if args.duration else None
    budget = [args.requests if args.requests else None]

    def next_request() -> Request | None:
        with counter:
            if budget[0] is not None:
                if budget[0] <= 0:
                    return None
                budget[0] -= 1
            if stop_at is not None and time.perf_counter() >= stop_at:
                return None
            req = requests[index[0] % len(requests)]
            index[0] += 1
            return req

    def warm() -> None:
        for i in range(args.warmup):
            send(args.url, requests[i % len(requests)], args.timeout)

    warm()

    lock = threading.Lock()

    def worker() -> None:
        while True:
            req = next_request()
            if req is None:
                return
            latency, error = send(args.url, req, args.timeout)
            with lock:
                if error:
                    result.errors.append(error)
                else:
                    result.latencies_ms.append(latency)

    started = time.perf_counter()
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    result.wall_s = time.perf_counter() - started
    return result


def quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated quantile of an already sorted list."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    low, high = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def summarize(run: RunResult) -> dict[str, float | int]:
    """Turn one run's samples into the reported distribution."""
    values = sorted(run.latencies_ms)
    return {
        "requests": len(values),
        "errors": len(run.errors),
        "mean": round(statistics.fmean(values), 3),
        "p50": round(quantile(values, 0.50), 3),
        "p95": round(quantile(values, 0.95), 3),
        "p99": round(quantile(values, 0.99), 3),
        "max": round(values[-1], 3),
        "rps": round(len(values) / run.wall_s, 2) if run.wall_s > 0 else 0.0,
        "wall_s": round(run.wall_s, 3),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI. Help text is written for someone who has not read the source."""
    parser = argparse.ArgumentParser(
        prog="bench-http.py",
        description="Measure HTTP latency for a local API and print one number.",
        epilog=(
            "Fixture format: one JSON object per line, for example\n"
            '  {"method": "GET", "path": "/health"}\n'
            '  {"method": "POST", "path": "/search", "body": {"q": "hi"}}\n\n'
            "The default output is a single number, so it can be the MEASURE command of a\n"
            "hill-climb loop. Use --json for the full distribution, the run-to-run spread,\n"
            "and the fixture checksum to record in the ledger.\n\n"
            "Examples:\n"
            "  python3 scripts/bench-http.py --url http://127.0.0.1:8000 \\\n"
            "      --fixture fixtures/api.jsonl --requests 500\n"
            "  python3 scripts/bench-http.py --url http://127.0.0.1:8000 \\\n"
            "      --fixture fixtures/api.jsonl --duration 5 --runs 10 --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="Base URL of the API, for example http://127.0.0.1:8000")
    parser.add_argument(
        "--fixture", required=True, type=Path, help="JSONL file of requests. This is the pinned dataset."
    )
    parser.add_argument("--concurrency", type=int, default=1, help="Requests in flight at once (default 1)")
    parser.add_argument(
        "--requests", type=int, default=None, help="Requests per run. Mutually exclusive with --duration."
    )
    parser.add_argument(
        "--duration", type=float, default=None, help="Seconds of load per run. Mutually exclusive with --requests."
    )
    parser.add_argument(
        "--warmup", type=int, default=20, help="Requests sent and discarded before each run (default 20)"
    )
    parser.add_argument("--runs", type=int, default=5, help="Runs; the printed number is their median (default 5)")
    parser.add_argument(
        "--metric",
        choices=["p50", "p95", "p99", "mean", "rps"],
        default="p99",
        help="Which number to print (default p99). Latencies are ms, lower is better; rps is higher is better.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full distribution and per-run spread as JSON")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds (default 10)")
    parser.add_argument(
        "--max-spread",
        type=float,
        default=None,
        help="Exit 3 if max-min of the chosen metric across runs exceeds this. Default: warn only.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit a non-loopback target. Off by default: a benchmark against a public host is an attack.",
    )
    return parser


def validate(args: argparse.Namespace) -> None:
    """Check the arguments that argparse cannot express."""
    if args.requests and args.duration:
        die("pass --requests or --duration, not both")
    if not args.requests and not args.duration:
        args.requests = 200
    if args.concurrency < 1:
        die("--concurrency must be at least 1")
    if args.runs < 1:
        die("--runs must be at least 1")
    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme not in {"http", "https"}:
        die(f"--url must be http or https, got {args.url!r}")
    if not args.allow_remote and not is_loopback(parsed.hostname or ""):
        die(
            f"refusing to bench non-loopback host {parsed.hostname!r}. "
            "Benchmarks generate sustained load; aiming one at a shared or public host can "
            "take it down. Bench a local instance, or pass --allow-remote if you own the "
            "target and have permission to load it."
        )


def main() -> None:
    """Parse arguments, run the benchmark, print one number or the JSON report."""
    args = build_parser().parse_args()
    validate(args)
    requests, checksum = load_fixture(args.fixture)

    runs = []
    for _ in range(args.runs):
        run = run_once(args, requests)
        if not run.latencies_ms:
            first = run.errors[0] if run.errors else "no requests were sent"
            die(f"no successful request. First failure: {first}", 2)
        if run.errors:
            die(f"{len(run.errors)} request(s) failed; the run is not comparable. First: {run.errors[0]}", 2)
        runs.append(summarize(run))

    values = [float(run[args.metric]) for run in runs]
    spread = round(max(values) - min(values), 3)
    value = round(statistics.median(values), 3)
    report = {
        "metric": args.metric,
        "unit": "rps" if args.metric == "rps" else "ms",
        "value": value,
        "higher_is_better": args.metric in HIGHER_IS_BETTER,
        "url": args.url,
        "fixture": str(args.fixture),
        "fixture_sha256": checksum,
        "fixture_requests": len(requests),
        "concurrency": args.concurrency,
        "warmup": args.warmup,
        "runs": args.runs,
        "across": {
            key: round(statistics.median([float(run[key]) for run in runs]), 3)
            for key in ("mean", "p50", "p95", "p99", "rps")
        },
        "spread": spread,
        "spread_pct": round(spread / value * 100, 2) if value else 0.0,
        "per_run": runs,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(value)

    if args.max_spread is not None and spread > args.max_spread:
        die(
            f"run-to-run spread of {args.metric} is {spread}, above --max-spread {args.max_spread}. "
            "Any hill-climb delta smaller than that is noise. Close background load, "
            "let the machine cool, or raise --runs.",
            3,
        )
    if args.max_spread is None and report["spread_pct"] > 10:
        print(
            f"bench-http: warning: spread {spread} {report['unit']} "
            f"({report['spread_pct']}% of the median) across runs. Treat smaller deltas as noise.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
