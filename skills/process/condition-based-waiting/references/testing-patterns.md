# Testing Wait and Retry Code

> **Scope**: pytest patterns for testing condition-based polling, exponential backoff, and circuit breakers.
> **Version range**: Python 3.8+, pytest 7+
> **Generated**: 2026-04-16

---

## Overview

Wait/retry code is notoriously hard to test correctly. The two failure modes: tests that pass because the real sleep ran (slow, flaky in CI), and tests that mock away the sleep but don't verify the retry logic actually ran. The patterns below separate timing from logic so tests are fast and deterministic.

---

## Pattern Table

| Need | Tool | Notes |
|------|------|-------|
| Mock `time.sleep` | `unittest.mock.patch` | Verify call count and delay values |
| Control `time.monotonic` | `freezegun` or `time_machine` | Advance clock without real sleep |
| Force N failures then success | `side_effect` list | Returns exception N times, then returns value |
| Verify retry count | `mock.call_count` | Assert exactly N+1 attempts |
| Test timeout fires | `pytest.raises(TimeoutError)` | Never satisfy the condition |

---

## Correct Patterns

### Testing Simple Polling with Mocked Sleep

Verify the poll loop calls `time.sleep` with the right interval and raises `TimeoutError` when the condition never becomes true.

```python
from unittest.mock import patch, MagicMock
import pytest
from mymodule import wait_for

def test_wait_for_success(mocker):
    condition = mocker.MagicMock(side_effect=[False, False, True])
    mocker.patch("time.sleep")

    result = wait_for(condition, "test condition", timeout_seconds=10, poll_interval_seconds=0.1)

    assert result is True
    assert condition.call_count == 3

def test_wait_for_timeout(mocker):
    condition = mocker.MagicMock(return_value=False)
    mocker.patch("time.monotonic", side_effect=[0, 1, 2, 31])  # Exceeds 30s timeout
    mocker.patch("time.sleep")

    with pytest.raises(TimeoutError, match="test condition"):
        wait_for(condition, "test condition", timeout_seconds=30)
```

**Why**: Mocking `time.sleep` prevents actual delays. Controlling `time.monotonic` makes the timeout deterministic without requiring real time to pass.

---

### Testing Exponential Backoff — Delay Progression

Verify delays grow exponentially and are capped at `max_delay`.

```python
from unittest.mock import patch, call
import pytest
from mymodule import retry_with_backoff

def test_backoff_delay_progression(mocker):
    operation = mocker.MagicMock(side_effect=[ValueError("fail")] * 3 + [42])
    sleep_mock = mocker.patch("time.sleep")
    # Patch random.uniform to return 0 so jitter is predictable
    mocker.patch("random.uniform", return_value=0.0)

    result = retry_with_backoff(
        operation,
        "test op",
        max_retries=3,
        initial_delay_seconds=1.0,
        backoff_factor=2.0,
        max_delay_seconds=10.0,
        retryable_exceptions=(ValueError,),
    )

    assert result == 42
    assert operation.call_count == 4
    delays = [c.args[0] for c in sleep_mock.call_args_list]
    assert delays == [1.0, 2.0, 4.0]  # 1 → 2 → 4, capped before 10

def test_backoff_raises_after_max_retries(mocker):
    operation = mocker.MagicMock(side_effect=ValueError("always fails"))
    mocker.patch("time.sleep")
    mocker.patch("random.uniform", return_value=0.0)

    with pytest.raises(ValueError, match="always fails"):
        retry_with_backoff(operation, "test", max_retries=3, retryable_exceptions=(ValueError,))

    assert operation.call_count == 4  # Initial attempt + 3 retries
```

---

### Testing Non-Retryable Errors Pass Through Immediately

```python
def test_non_retryable_error_not_retried(mocker):
    operation = mocker.MagicMock(side_effect=PermissionError("not retryable"))
    sleep_mock = mocker.patch("time.sleep")

    with pytest.raises(PermissionError):
        retry_with_backoff(
            operation,
            "test",
            max_retries=5,
            retryable_exceptions=(TimeoutError,),  # PermissionError is not in this list
        )

    assert operation.call_count == 1  # No retries
    assert sleep_mock.call_count == 0
```

---

### Testing Rate Limit Recovery (429 Handling)

```python
import requests
from unittest.mock import MagicMock, patch

def test_rate_limit_uses_retry_after_header(mocker):
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "3"}

    success = MagicMock()
    success.status_code = 200

    session_mock = mocker.patch("requests.Session")
    session_mock.return_value.request.side_effect = [rate_limited, success]
    sleep_mock = mocker.patch("time.sleep")

    from mymodule import RateLimitedClient
    client = RateLimitedClient("https://api.example.com")
    client.get("/data")

    sleep_mock.assert_called_once_with(3.0)

def test_rate_limit_uses_default_when_header_missing(mocker):
    rate_limited = MagicMock(status_code=429, headers={})
    success = MagicMock(status_code=200)

    mocker.patch("requests.Session").return_value.request.side_effect = [rate_limited, success]
    sleep_mock = mocker.patch("time.sleep")

    from mymodule import RateLimitedClient
    client = RateLimitedClient("https://api.example.com", default_retry_after=60.0)
    client.get("/data")

    sleep_mock.assert_called_once_with(60.0)
```

---

### Testing Health Check Waiting

```python
def test_health_check_passes_when_all_ready(mocker):
    mocker.patch("mymodule.check_tcp", return_value=True)
    mocker.patch("mymodule.check_http", return_value=True)
    mocker.patch("time.sleep")

    from mymodule import wait_for_healthy, HealthCheck
    result = wait_for_healthy(
        [HealthCheck("db", "tcp", "localhost:5432"),
         HealthCheck("api", "http", "http://localhost:8080/health")],
        timeout_seconds=10,
    )
    assert result is True

def test_health_check_times_out_when_service_down(mocker):
    mocker.patch("mymodule.check_tcp", return_value=False)
    mocker.patch("time.monotonic", side_effect=[0, 1, 2, 121])  # Exceeds 120s
    mocker.patch("time.sleep")

    with pytest.raises(TimeoutError, match="Health checks did not pass"):
        wait_for_healthy([HealthCheck("db", "tcp", "localhost:5432")], timeout_seconds=120)
```

---

### Testing Circuit Breaker State Transitions

```python
import time
from mymodule import CircuitBreaker, CircuitOpenError

def test_circuit_opens_after_failure_threshold():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout_seconds=30)
    failing_op = lambda: (_ for _ in ()).throw(RuntimeError("fail"))

    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(failing_op)

    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "should not run")

def test_circuit_recovers_after_timeout(mocker):
    cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout_seconds=30, half_open_max_calls=2)
    failing_op = lambda: (_ for _ in ()).throw(RuntimeError("fail"))

    with pytest.raises(RuntimeError):
        cb.call(failing_op)

    # Simulate recovery timeout elapsed
    mocker.patch("time.monotonic", return_value=time.monotonic() + 31)

    # Circuit should be HALF_OPEN now — calls pass through
    cb.call(lambda: "ok")
    cb.call(lambda: "ok")  # Second success closes the circuit

    from mymodule import CircuitState
    assert cb.state == CircuitState.CLOSED
```

---

## Pattern: Use `waitFor` or mocked clocks instead of direct `time.sleep`

**Detection**:
```bash
grep -rn 'time\.sleep' --include="test_*.py"
rg 'time\.sleep\(\d' --type py -g 'test_*'
```

**What it looks like**:
```python
def test_retry_waits():
    # Slow test — waits real time
    start = time.time()
    retry_with_backoff(flaky_op, "test", initial_delay_seconds=1.0)
    assert time.time() - start >= 1.0
```

**Why wrong**: This makes the test suite slow. A 3-retry test with 1s initial delay takes 7+ real seconds. In CI with many such tests, suite time becomes a blocker. You also can't test timing precisely without mocking.

**Fix**: Mock `time.sleep` and assert on the mock's call args instead of measuring wall time.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| Test passes locally but flakes in CI | Real `time.sleep` + slow CI runner | Mock `time.sleep`; use `mocker.patch("time.monotonic")` to control timeout |
| `assert mock.call_count == 4` fails, got 1 | Non-retryable exception type used | Check `retryable_exceptions` tuple includes the exception being raised |
| `TimeoutError` fires immediately in test | `time.monotonic` mock sequence exhausted | Add more return values to the `side_effect` list |
| Circuit stays CLOSED after failure threshold | `failure_threshold` not reached | Verify loop calls `cb.call()` exactly `failure_threshold` times with failures |

---

## See Also

- `implementation-patterns.md` — complete implementations for all patterns
- `preferred-patterns.md` — detection commands for common wait/retry mistakes
