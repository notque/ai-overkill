# Feedback Loop Construction

Building a loop that reproduces the bug is the hardest and most important step in debugging. The loop IS the skill. Everything else -- hypothesizing, fixing, verifying -- depends on having a tight, fast, deterministic reproduction that you can run on demand.

A good feedback loop answers one question: "did the bug just happen?" If you can trigger that answer in under 5 seconds with no manual intervention, you have a loop worth building on. If reproducing requires manual clicks, waiting for external services, or squinting at logs, your loop is too slow and you will waste time on every subsequent hypothesis.

Invest heavily in this step. A 30-minute investment in a solid loop saves hours of "I think that fixed it" guessing.

---

## 10 Loop Construction Methods

Choose the method that matches your bug's environment and observability. Start with the simplest method that can reproduce the bug. Escalate only when the simple method cannot capture the failure.

### 1. Failing Test (Unit or Integration)

Write a test that encodes the exact failure. This is the gold standard when the bug lives in a function with clear inputs and outputs.

```python
def test_off_by_one_pagination():
    """Reproduces: page 2 returns duplicate of last item from page 1."""
    items = create_items(25)  # 25 items, 10 per page
    page1 = paginate(items, page=1, size=10)
    page2 = paginate(items, page=2, size=10)
    assert page1[-1] != page2[0], f"Duplicate item {page2[0].id} across page boundary"
```

**When to use**: Pure logic bugs, data transformation errors, boundary conditions, API contract violations.

**When this fails**: The bug requires infrastructure (database state, network, filesystem), the setup is too expensive for a unit test, or the bug is in the interaction between components.

### 2. curl/HTTP Script

A bash script that hits the endpoint and checks the response. Fastest path for API bugs.

```bash
#!/bin/bash
# reproduce-auth-bypass.sh
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8080/admin/users \
  -H "Authorization: Bearer ${EXPIRED_TOKEN}")

if [ "$RESPONSE" != "401" ]; then
  echo "FAIL: Expected 401, got $RESPONSE (expired token accepted)"
  exit 1
fi
echo "PASS: Expired token correctly rejected"
```

**When to use**: HTTP API bugs, auth issues, header handling, content-type problems, CORS.

**When this fails**: The bug requires browser state (cookies, JS execution), websocket connections, or multi-step session flows.

### 3. Headless Browser (Playwright/Puppeteer)

Automate the exact user interaction that triggers the bug. Use when the bug is in the browser, involves JS rendering, or requires multi-step UI flows.

```typescript
test('cart total updates after removing item', async ({ page }) => {
  await page.goto('/cart');
  await page.click('[data-testid="remove-item-3"]');
  // Bug: total still includes removed item until page refresh
  const total = await page.textContent('[data-testid="cart-total"]');
  expect(total).not.toContain('$45.00'); // price of removed item
});
```

**When to use**: UI rendering bugs, JS interaction issues, race conditions in frontend state, visual regressions.

**When this fails**: The bug is server-side only, or the headless environment does not match the real browser environment.

### 4. Replay Trace (Record/Replay)

Capture the exact sequence of inputs that caused the bug, then replay them. Use when the bug appeared in production and you need to reproduce the exact conditions.

```bash
# Record: capture HTTP traffic during the failing scenario
mitmdump -w failing-session.flow --set confdir=~/.mitmproxy

# Replay: feed the exact same requests to your local server
mitmdump -nC failing-session.flow --set server_replay_kill_extra=true \
  --set server_replay=failing-session.flow
```

**When to use**: Production bugs you cannot reproduce from scratch, complex multi-request sequences, bugs that depend on specific request ordering.

**When this fails**: The bug depends on server-side state that is not captured in the trace, or timing-sensitive interactions that replay cannot reproduce faithfully.

### 5. Throwaway Harness (Minimal Reproducer)

Strip everything down to the smallest possible program that exhibits the bug. This is the most powerful debugging technique when the codebase is large and the bug's location is unknown.

```python
# reproduce_memory_leak.py -- standalone, no project dependencies
import gc
import tracemalloc

tracemalloc.start()

for i in range(1000):
    # Isolated reproduction of the suspected leak
    obj = SuspectedLeakyClass()
    obj.process(sample_data)
    del obj
    gc.collect()

current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024:.1f} KB, Peak: {peak / 1024:.1f} KB")
assert current < 1024 * 100, f"Memory leak: {current / 1024:.1f} KB after cleanup"
```

**When to use**: Bugs you suspect but cannot isolate, memory leaks, import-time side effects, dependency conflicts, "works on my machine" problems.

**When this fails**: The bug requires the full application context and cannot be isolated.

### 6. Property/Fuzz Testing Loop

Generate random inputs and check invariants. Use when you know what properties should hold but not which specific input breaks them.

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers(), min_size=1))
def test_sort_preserves_length(xs):
    result = custom_sort(xs)
    assert len(result) == len(xs), f"Sort dropped elements: {len(xs)} -> {len(result)}"

@given(st.lists(st.integers(), min_size=2))
def test_sort_is_ordered(xs):
    result = custom_sort(xs)
    for i in range(len(result) - 1):
        assert result[i] <= result[i+1], f"Out of order at index {i}: {result[i]} > {result[i+1]}"
```

**When to use**: Data processing bugs, serialization round-trip failures, parser edge cases, any function where you can state an invariant but cannot guess the failing input.

**When this fails**: The invariant is hard to express, or the state space is so large that random exploration is unlikely to hit the failing case.

### 7. Bisection Harness (git bisect + test)

Find the exact commit that introduced the bug by binary searching git history. Combine with any of the above loop methods as the test oracle.

```bash
# Write the test script first (must exit 0 for good, 1 for bad)
cat > /tmp/bisect-test.sh << 'SCRIPT'
#!/bin/bash
go build ./... 2>/dev/null || exit 125  # skip uncompilable commits
go test ./pkg/auth/ -run TestExpiredTokenRejected -count=1 -timeout 30s
SCRIPT
chmod +x /tmp/bisect-test.sh

# Run bisection
git bisect start
git bisect bad HEAD
git bisect good v1.2.0  # last known good version
git bisect run /tmp/bisect-test.sh
```

**When to use**: The bug exists now but did not exist before, and you have a test that detects it. Especially valuable in large codebases where reading every commit is impractical.

**Exit code convention**: 0 = good (bug absent), 1 = bad (bug present), 125 = skip (commit cannot be tested).

### 8. Differential Loop (Compare Good vs Bad)

Run the same input through two versions and compare outputs. Use when you have a known-good version (previous release, reference implementation, or different configuration).

```bash
#!/bin/bash
# differential-test.sh
INPUT='{"user_id": 42, "action": "transfer", "amount": 100.50}'

OLD=$(echo "$INPUT" | docker run --rm -i myapp:v1.2.0 process)
NEW=$(echo "$INPUT" | docker run --rm -i myapp:latest process)

if [ "$OLD" != "$NEW" ]; then
  echo "DIFF DETECTED:"
  diff <(echo "$OLD") <(echo "$NEW")
  exit 1
fi
echo "PASS: Outputs match"
```

**When to use**: Regression bugs, migration verification, "it used to work" situations, comparing behavior across configurations or environments.

**When this fails**: No known-good version exists, or the output is intentionally different (new features).

### 9. Human-in-the-Loop Bash Script

A script that sets up the reproduction environment, triggers the bug, and asks the human to observe the result. Use when the failure is visual, subjective, or requires human judgment to confirm.

```bash
#!/bin/bash
# hitl-reproduce.sh
echo "=== Setting up reproduction environment ==="
docker compose up -d
sleep 3

echo "=== Triggering the bug ==="
curl -s http://localhost:8080/api/dashboard/render > /tmp/dashboard.html
open /tmp/dashboard.html  # or xdg-open on Linux

echo ""
echo "=== HUMAN CHECK ==="
echo "Look at the dashboard. Is the chart legend overlapping the data?"
echo "Press 'y' if bug is visible, 'n' if not:"
read -r ANSWER

if [ "$ANSWER" = "y" ]; then
  echo "Bug reproduced. Saving screenshot for evidence."
  exit 1
fi
echo "Bug not visible in this run."
exit 0
```

**When to use**: Visual/rendering bugs, UX issues, problems that require human judgment, bugs that automated assertions cannot detect.

**When this fails**: The observation is too subtle for reliable human detection, or you need CI-compatible automation.

### 10. Log Correlation Loop (Tail + Grep + Trigger)

Watch logs in real-time while triggering the bug. Use when you know the bug happens but cannot see it in tests -- the evidence is in the runtime output.

```bash
#!/bin/bash
# log-correlation.sh
LOG_FILE="/var/log/myapp/app.log"

# Start watching for the error signature in background
tail -f "$LOG_FILE" | grep --line-buffered "DEADLOCK\|timeout exceeded\|connection reset" &
WATCH_PID=$!

# Trigger the scenario that causes the bug
curl -s http://localhost:8080/api/heavy-query &
curl -s http://localhost:8080/api/heavy-query &
curl -s http://localhost:8080/api/heavy-query &
wait

# Give logs a moment to flush
sleep 2
kill $WATCH_PID 2>/dev/null

# Check if error appeared
if grep -q "DEADLOCK\|timeout exceeded" "$LOG_FILE"; then
  echo "FAIL: Error signature found in logs"
  tail -20 "$LOG_FILE"
  exit 1
fi
echo "PASS: No error signatures detected"
```

**When to use**: Concurrency bugs, connection pool exhaustion, deadlocks, bugs that only manifest under load, problems where the symptom is a log entry rather than a wrong return value.

**When this fails**: The bug does not leave a log trace, or the log output is too noisy to isolate the signal.

---

## Loop Quality Iteration

A working loop is not necessarily a good loop. After initial reproduction, improve the loop across three dimensions.

### Speed

The loop should complete in under 5 seconds. Every second you add to the loop adds minutes to the debugging session, because you run the loop dozens of times while testing hypotheses.

| Loop time | Impact |
|-----------|--------|
| < 1 second | Ideal. Hypothesis testing feels interactive. |
| 1-5 seconds | Acceptable. Slight delay but maintains flow. |
| 5-30 seconds | Slow. You will start multitasking and lose context. |
| > 30 seconds | Too slow. Invest time in making the loop faster before continuing. |

Speed improvements: mock external services, use in-memory databases, reduce dataset size, skip irrelevant setup, use test-specific configuration that disables caching warm-up.

### Signal Sharpness

The loop output should make the bug's presence or absence obvious. A sharp signal is a single line: `PASS` or `FAIL: expected X, got Y`. A blurry signal is 500 lines of log output that you have to scan manually.

Sharpen signals by:
- Asserting on the exact failure condition, not on side effects
- Reducing output to pass/fail with the failing values on the FAIL line
- Using exit codes (0 = pass, non-zero = fail) so the loop can be composed with other tools (`git bisect run`, CI, watch loops)

### Determinism

The loop must produce the same result on every run. If it passes sometimes and fails sometimes, you have two bugs: the original one and a non-deterministic test.

Make loops deterministic by:
- Fixing random seeds
- Mocking time-dependent functions
- Using fixed ports and avoiding port conflicts
- Serializing concurrent operations during reproduction
- Controlling filesystem state (clean temp dirs before each run)

---

## Non-Deterministic Bugs

Some bugs resist deterministic reproduction: race conditions, timing-dependent failures, bugs that depend on external service state. These require specialized loop techniques.

### Race Conditions

The bug depends on the relative timing of two or more operations. The loop must increase the probability of hitting the race window.

**Amplification technique**: Insert artificial delays at the suspected race point to widen the window, then run the loop in a tight count-loop.

```bash
# Run 100 iterations to catch intermittent race
FAILURES=0
for i in $(seq 1 100); do
  if ! ./reproduce-race.sh 2>/dev/null; then
    FAILURES=$((FAILURES + 1))
  fi
done
echo "Failed $FAILURES/100 runs"
if [ "$FAILURES" -gt 0 ]; then
  echo "Race condition confirmed: $FAILURES% failure rate"
fi
```

For Go: use `-race` flag. For general concurrency: use thread sanitizers (TSan). These tools instrument the runtime to detect races even when timing does not trigger a visible failure.

### Timing-Dependent Failures

The bug depends on absolute timing (timeouts, TTLs, cache expiry). The loop must control time.

**Approach**: Mock the clock. Most languages have time-mocking libraries. If the clock cannot be mocked, reduce timeouts in test configuration to make the timing window easier to hit.

### External Service Dependencies

The bug depends on a specific response from an external service (database state, third-party API, network conditions). The loop must stub or simulate the external behavior.

**Approach priority**:
1. Record the external response and replay it (method 4: replay trace)
2. Stub the external call with a fixed response that triggers the bug
3. Use a local mock service (WireMock, localstack, test containers)
4. If none work: document the exact external conditions required and build a HITL script (method 9)

### When Reproduction Seems Impossible

If you have spent 30 minutes and cannot reproduce the bug, stop and assess:

1. **Add instrumentation**: Add logging at the suspected failure point and deploy to the environment where the bug occurs. Wait for it to happen again with better observability.
2. **Narrow the conditions**: Identify what is different about the environment where it fails vs where it passes. The difference is a clue.
3. **Accept probabilistic reproduction**: For some bugs, a loop that fails 1 in 50 runs is good enough. Run it 200 times and you will have statistical evidence.
4. **Record and replay in production**: If the bug only happens in production, use traffic recording to capture the exact sequence, then replay locally (method 4).
