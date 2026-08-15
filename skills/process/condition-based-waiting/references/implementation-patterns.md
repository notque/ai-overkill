# Wait and Retry Implementation Patterns

Complete implementations for condition-based waiting patterns. The main SKILL.md provides the methodology; this file provides copy-paste-ready code.

## Table of Contents
1. [Simple Polling](#simple-polling)
2. [Exponential Backoff](#exponential-backoff)
3. [Rate Limit Recovery](#rate-limit-recovery)
4. [Health Check Waiting](#health-check-waiting)
5. [Circuit Breaker](#circuit-breaker)

---

## Simple Polling

### Python

```python
import time
from typing import Callable, TypeVar

T = TypeVar('T')

def wait_for(
    condition: Callable[[], T],
    description: str,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.1,
) -> T:
    """
    Poll until condition returns truthy value.

    Args:
        condition: Callable that returns truthy value when ready
        description: Human-readable description for error messages
        timeout_seconds: Maximum time to wait
        poll_interval_seconds: Time between checks (min 0.01)

    Returns:
        The truthy value returned by condition

    Raises:
        TimeoutError: If condition not met within timeout
    """
    poll_interval_seconds = max(0.01, poll_interval_seconds)
    start = time.monotonic()
    deadline = start + timeout_seconds
    last_result = None

    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        last_result = result
        time.sleep(poll_interval_seconds)

    elapsed = time.monotonic() - start
    raise TimeoutError(
        f"Timeout waiting for: {description}. "
        f"Waited {elapsed:.1f}s, last result: {last_result}"
    )
```

### Python Usage

```python
# Wait for file to exist
wait_for(
    lambda: os.path.exists("/tmp/signal.txt"),
    "signal file to be created",
    timeout_seconds=10.0
)

# Wait for state machine
wait_for(
    lambda: machine.state == "ready",
    "state machine to reach 'ready' state",
    timeout_seconds=60.0
)

# Wait for complex condition
wait_for(
    lambda: obj.ready and obj.value > 10 and not obj.error,
    "object ready with value > 10 and no error",
    timeout_seconds=15.0
)
```

### Bash

```bash
wait_for() {
    local condition="$1"
    local description="$2"
    local timeout="${3:-30}"
    local interval="${4:-0.5}"

    local deadline=$(($(date +%s) + timeout))

    while [ $(date +%s) -lt $deadline ]; do
        if eval "$condition"; then
            return 0
        fi
        sleep "$interval"
    done

    echo "Timeout waiting for: $description (${timeout}s elapsed)" >&2
    return 1
}

# Usage:
wait_for "test -f /tmp/signal.txt" "signal file" 30 0.5
wait_for "! pgrep -f 'my_process'" "process to terminate" 60 1
wait_for "nc -z localhost 8080 2>/dev/null" "port 8080 to open" 30 0.5
wait_for "curl -sf http://localhost:8080/health" "health endpoint" 60 2
```

---

## Exponential Backoff

### Python

```python
import random
import time
from typing import Callable, TypeVar, Type, Tuple

T = TypeVar('T')

def retry_with_backoff(
    operation: Callable[[], T],
    description: str,
    max_retries: int = 5,
    initial_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    backoff_factor: float = 2.0,
    jitter_range: float = 0.5,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> T:
    """
    Retry operation with exponential backoff and jitter.

    Args:
        operation: Callable to retry
        description: Human-readable description for logging
        max_retries: Maximum number of retry attempts
        initial_delay_seconds: First delay between retries
        max_delay_seconds: Maximum delay cap
        backoff_factor: Multiplier for each subsequent delay
        jitter_range: Random factor (0.5 = +/- 50% of delay)
        retryable_exceptions: Exception types to retry on

    Returns:
        Result of successful operation

    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None
    delay = initial_delay_seconds

    for attempt in range(max_retries + 1):
        try:
            return operation()
        except retryable_exceptions as e:
            last_exception = e

            if attempt >= max_retries:
                break

            jitter = 1.0 + random.uniform(-jitter_range, jitter_range)
            actual_delay = min(delay * jitter, max_delay_seconds)

            print(f"[{description}] Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                  f"Retrying in {actual_delay:.1f}s...")

            time.sleep(actual_delay)
            delay = min(delay * backoff_factor, max_delay_seconds)

    raise last_exception
```

### Python Usage

```python
import requests

# Retry HTTP request
def fetch_data():
    response = requests.get("https://api.example.com/data", timeout=10)
    response.raise_for_status()
    return response.json()

data = retry_with_backoff(
    fetch_data,
    "fetch API data",
    max_retries=3,
    initial_delay_seconds=1.0,
    retryable_exceptions=(requests.RequestException,),
)
```

### Bash

```bash
retry_with_backoff() {
    local max_retries="$1"
    local initial_delay="$2"
    shift 2
    local command="$@"

    local attempt=0
    local delay="$initial_delay"

    while [ $attempt -lt $max_retries ]; do
        if eval "$command"; then
            return 0
        fi

        attempt=$((attempt + 1))

        if [ $attempt -lt $max_retries ]; then
            local jitter=$(awk "BEGIN {printf \"%.1f\", 0.5 + rand()}")
            local actual_delay=$(awk "BEGIN {printf \"%.1f\", $delay * $jitter}")

            echo "Attempt $attempt/$max_retries failed. Retrying in ${actual_delay}s..." >&2
            sleep "$actual_delay"

            delay=$(awk "BEGIN {d = $delay * 2; print (d > 60 ? 60 : d)}")
        fi
    done

    echo "All $max_retries attempts failed" >&2
    return 1
}

# Usage:
retry_with_backoff 5 1 curl -sf https://api.example.com/data
retry_with_backoff 3 2 docker-compose up -d
```

---

## Rate Limit Recovery

### Python

```python
import time
import requests

class RateLimitedClient:
    """HTTP client with automatic rate limit handling."""

    def __init__(
        self,
        base_url: str,
        max_retries: int = 3,
        default_retry_after: float = 60.0,
    ):
        self.base_url = base_url
        self.max_retries = max_retries
        self.default_retry_after = default_retry_after
        self.session = requests.Session()

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make request with automatic rate limit retry."""
        url = f"{self.base_url}{path}"

        for attempt in range(self.max_retries + 1):
            response = self.session.request(method, url, **kwargs)

            if response.status_code != 429:
                return response

            if attempt >= self.max_retries:
                response.raise_for_status()

            retry_after = self._parse_retry_after(response)
            print(f"Rate limited. Waiting {retry_after:.1f}s before retry...")
            time.sleep(retry_after)

        return response

    def _parse_retry_after(self, response: requests.Response) -> float:
        """Parse Retry-After header, return default if missing."""
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return self.default_retry_after
        try:
            return float(retry_after)
        except ValueError:
            return self.default_retry_after

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)
```

---

## Health Check Waiting

### Python

```python
import time
import socket
from typing import List
from dataclasses import dataclass

@dataclass
class HealthCheck:
    name: str
    check_type: str  # "tcp", "http", "command"
    target: str      # host:port, URL, or command
    timeout: float = 5.0

def check_tcp(host: str, port: int, timeout: float) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.error, socket.timeout):
        return False

def check_http(url: str, timeout: float) -> bool:
    import requests
    try:
        response = requests.get(url, timeout=timeout)
        return 200 <= response.status_code < 300
    except requests.RequestException:
        return False

def check_command(command: str, timeout: float) -> bool:
    import subprocess
    try:
        result = subprocess.run(command, shell=True, timeout=timeout, capture_output=True)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False

def wait_for_healthy(
    checks: List[HealthCheck],
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> bool:
    """Wait for all health checks to pass."""
    start = time.monotonic()
    deadline = start + timeout_seconds

    while time.monotonic() < deadline:
        all_healthy = True
        status_report = []

        for check in checks:
            if check.check_type == "tcp":
                host, port = check.target.split(":")
                healthy = check_tcp(host, int(port), check.timeout)
            elif check.check_type == "http":
                healthy = check_http(check.target, check.timeout)
            elif check.check_type == "command":
                healthy = check_command(check.target, check.timeout)
            else:
                raise ValueError(f"Unknown check type: {check.check_type}")

            status = "OK" if healthy else "FAIL"
            status_report.append(f"  {check.name}: {status}")
            if not healthy:
                all_healthy = False

        if all_healthy:
            return True

        time.sleep(poll_interval_seconds)

    raise TimeoutError(
        f"Health checks did not pass within {timeout_seconds}s. "
        f"Final status:\n" + "\n".join(status_report)
    )
```

### Python Usage

```python
checks = [
    HealthCheck("postgres", "tcp", "localhost:5432"),
    HealthCheck("redis", "tcp", "localhost:6379"),
    HealthCheck("api", "http", "http://localhost:8080/health"),
    HealthCheck("worker", "command", "pgrep -f 'celery worker'"),
]
wait_for_healthy(checks, timeout_seconds=120)
```

### Bash

```bash
wait_for_services() {
    local timeout="$1"
    shift
    local services=("$@")

    local deadline=$(($(date +%s) + timeout))

    while [ $(date +%s) -lt $deadline ]; do
        local all_healthy=true

        for service in "${services[@]}"; do
            local type="${service%%:*}"
            local target="${service#*:}"

            case "$type" in
                tcp)
                    local host="${target%%:*}"
                    local port="${target#*:}"
                    if ! nc -z "$host" "$port" 2>/dev/null; then
                        all_healthy=false
                    fi
                    ;;
                http)
                    if ! curl -sf "$target" >/dev/null 2>&1; then
                        all_healthy=false
                    fi
                    ;;
            esac
        done

        if $all_healthy; then
            return 0
        fi
        sleep 2
    done

    echo "Timeout waiting for services" >&2
    return 1
}

# Usage:
wait_for_services 60 \
    "tcp:localhost:5432" \
    "tcp:localhost:6379" \
    "http:http://localhost:8080/health"
```

---

## Circuit Breaker

### Python

```python
import time
import threading
from enum import Enum
from typing import Callable, TypeVar, Optional

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass

class CircuitBreaker:
    """
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def call(self, operation: Callable[[], T]) -> T:
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit '{self.name}' is OPEN. Retry after {self.recovery_timeout_seconds}s."
            )
        try:
            result = operation()
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
```

### Python Usage

```python
import requests

api_circuit = CircuitBreaker(
    name="payment-api",
    failure_threshold=5,
    recovery_timeout_seconds=30.0,
)

def make_payment(amount: float) -> dict:
    def _call():
        response = requests.post(
            "https://api.payments.com/charge",
            json={"amount": amount},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    try:
        return api_circuit.call(_call)
    except CircuitOpenError:
        return {"status": "queued", "message": "Payment queued for later"}
```
