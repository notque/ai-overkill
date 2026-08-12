
# Go Testing Skill

Go testing follows a 4-phase workflow: understand what needs testing, write
idiomatic tests, run and verify, review quality. Use table-driven tests when
many cases share the same test logic. Every helper calls t.Helper(). Every
concurrent test runs with -race.

## Instructions

### Phase 1: UNDERSTAND Test Requirements

**Goal**: Determine what needs testing and the appropriate test strategy.

**Step 1: Identify test scope**
- What function/method/package is being tested?
- Is this a new test, modification, or coverage gap?
- Are there existing tests to follow as patterns?

Read and follow repository CLAUDE.md before writing tests — project conventions
override these defaults.

**Step 2: Choose test type**

| Need | Test Type | Pattern |
|------|-----------|---------|
| Many similar input/output cases | Table-driven unit test | `[]struct` + `t.Run` |
| Distinct scenarios with different logic | Focused unit tests | Separate `TestXxx` functions |
| Single specific behavior | Focused unit test | Standard `TestXxx` |
| Cross-component interaction | Integration test | Setup/teardown helpers |
| Performance measurement | Benchmark | `b.Loop()` with `b.ReportAllocs()` |
| API usage documentation | Example test | `ExampleXxx` functions |

**Step 3: Verify test file structure**

```go
package mypackage_test  // Black-box testing (preferred over internal)

import (
    "testing"
    "mymodule/mypackage"
)

// Order: Unit tests, Integration tests, Benchmarks, Examples
```

Black-box testing (`package_test`) is preferred because it tests the public API the
way consumers use it. Internal testing (`package`) is acceptable only when testing
unexported behavior that can't be reached through the public API.

**Gate**: Test scope, type, and file location identified. Proceed only when gate passes.

### Phase 2: WRITE Tests

**Goal**: Implement tests following Go idioms.

**Step 1: Choose table-driven or focused tests**

Use a table-driven pattern when many cases can be tested with similar logic and
the cases benefit from an explicit input/output table. Keep cases in separate
focused tests when they need different setup, assertions, or control flow. Do
not force unrelated scenarios into one table merely because there is more than
one case.

```go
func TestParseConfig(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    Config
        wantErr bool
    }{
        {
            name:  "valid YAML",
            input: `key: value`,
            want:  Config{Key: "value"},
        },
        {
            name:    "invalid syntax",
            input:   `{{{`,
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseConfig(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("ParseConfig() error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if !tt.wantErr && got != tt.want {
                t.Errorf("ParseConfig() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

Write only the tests needed — no speculative coverage, no "while I'm here"
additions. Each test should exercise a specific behavior, not pad a coverage number.

**Step 2: Test helpers with t.Helper()**

Every test helper MUST call `t.Helper()` as its first line — without it, test
failure messages point to the helper's line instead of the caller's, which makes
debugging failures slow and frustrating:

```go
func assertEqual[T comparable](t *testing.T, got, want T) {
    t.Helper()  // MUST be first line
    if got != want {
        t.Errorf("got %v, want %v", got, want)
    }
}
```

**Step 3: Mocking interfaces**

Use manual mocks with function fields for flexible per-test behavior:

```go
type MockStore struct {
    GetFunc func(key string) ([]byte, error)
}

func (m *MockStore) Get(key string) ([]byte, error) {
    if m.GetFunc != nil {
        return m.GetFunc(key)
    }
    return nil, nil
}
```

See `${CLAUDE_SKILL_DIR}/references/testing/go-test-patterns.md` for complete mock patterns with call tracking.

**Step 4: Parallel tests**

Use `t.Parallel()` for independent tests by default — it catches unintended
shared state and runs faster:

```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel()
        // test body (use tt directly in Go 1.22+)
    })
}
```

**Step 5: Test error paths too**

Test error conditions, not just happy paths. If a function can return an error,
write at least one test case that triggers that error and verifies the message.

**Gate**: Test structure matches the cases, helpers use `t.Helper()`, and test doubles are no more complex than needed. Proceed only when the gate passes.

### Phase 3: RUN and Verify

**Goal**: Execute tests and confirm correctness.

**Step 1: Run tests**

```bash
# Standard run with verbose output
go test -v ./path/to/package/...

# With race detector (REQUIRED for concurrent code — race conditions
# are silent until production; the -race flag catches them deterministically)
go test -race -v ./path/to/package/...

# With coverage
go test -coverprofile=coverage.out ./path/to/package/...
go tool cover -func=coverage.out
```

Always show actual `go test` output. Never summarize as "tests pass" — the user
needs to see what ran, what passed, and what the output looks like.

**Step 2: Verify results**
- All tests pass (show actual output)
- No race conditions detected
- Critical paths have >80% coverage
- Error paths are exercised

After editing test files, use `go_diagnostics` (gopls MCP) to catch errors
before running tests — faster feedback than a full `go test` cycle.

**Step 3: Run full suite**

```bash
go test ./...
```

Verify no regressions in other packages.

**Gate**: All tests pass, race detector clean, coverage adequate. Proceed only when gate passes.

### Phase 4: REVIEW Test Quality

**Goal**: Ensure tests are maintainable and complete.

**Checklist**:
- [ ] Table-driven tests used only where many cases share similar logic?
- [ ] Test helpers marked with `t.Helper()`?
- [ ] Parallel execution where safe?
- [ ] Error conditions tested?
- [ ] Edge cases covered (empty, nil, boundary)?
- [ ] Cleanup performed (`t.Cleanup` or `defer`)?
- [ ] No test interdependencies?
- [ ] Race detector passes?

Test names must accurately describe the code path exercised. If a test simulates
behavior rather than exercising the production code path, the name must reflect
this — "pragmatic approximation" is not a valid reason for a misleading test name.

**Gate**: All checklist items satisfied. Tests are complete.

---

## Benchmark Guide

Use `b.Loop()` (Go 1.24+) for all new benchmarks — it prevents dead code
elimination, manages timers automatically, and produces more accurate results
than the manual `for i := 0; i < b.N; i++` loop:

```go
func BenchmarkProcess(b *testing.B) {
    b.ReportAllocs()
    for b.Loop() {
        _ = Process(input)
    }
}
```

Sub-benchmarks for comparison:

```go
func BenchmarkBuilder(b *testing.B) {
    b.Run("strings.Builder", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() { /* ... */ }
    })
    b.Run("bytes.Buffer", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() { /* ... */ }
    })
}
```

Run: `go test -bench=. -benchmem ./...`

See `${CLAUDE_SKILL_DIR}/references/testing/go-benchmark-and-concurrency.md` for benchstat comparison workflow and synctest patterns.

---

## Commands Reference

```bash
go test ./...                              # Run all tests
go test -v ./...                           # Verbose output
go test -race ./...                        # Race detector
go test -run TestMyFunc ./...              # Specific test
go test -run TestMyFunc/subtest ./...      # Specific subtest
go test -coverprofile=coverage.out ./...   # Coverage profile
go tool cover -func=coverage.out           # Coverage summary
go tool cover -html=coverage.out           # Coverage HTML
go test -bench=. -benchmem ./...           # Benchmarks
go test -short ./...                       # Skip long tests
go test -timeout 30s ./...                 # With timeout
go test -count=10 ./...                    # Detect flaky tests
```

---

## Error Handling

### Error: "test passes but shouldn't"
Cause: Test assertion is wrong or testing the wrong thing (tautological test)
Solution:
1. Verify test actually exercises the code under test
2. Temporarily break the implementation and confirm test fails
3. Check assertion compares meaningful values, not self-referential ones

### Error: "race detected during test"
Cause: Shared mutable state accessed from goroutines without synchronization
Solution:
1. Use `sync.Mutex` or `atomic` operations for shared state
2. Use channels for goroutine communication
3. Ensure mock call tracking uses mutex protection
4. See `${CLAUDE_SKILL_DIR}/references/testing/go-benchmark-and-concurrency.md` for patterns

### Error: "test passes locally but fails in CI"
Cause: Environment dependency, timing assumption, or file path difference
Solution:
1. Use `t.TempDir()` instead of hardcoded paths
2. Use `t.Setenv()` for environment variables (auto-restored)
3. Replace `time.Sleep` with `synctest.Test` for timing-dependent tests
4. Check for platform-specific assumptions

---

## Available Scripts

- **`scripts/gen-table-test.sh`** — Scaffold a table-driven test file for a Go function
- **`scripts/bench-compare.sh`** — Run Go benchmarks with optional benchstat comparison

---

## References

- `${CLAUDE_SKILL_DIR}/references/testing/go-test-patterns.md`: Full examples for table-driven tests, helpers, mocking, interface deduplication
- `${CLAUDE_SKILL_DIR}/references/testing/go-benchmark-and-concurrency.md`: b.Loop() benchmarks, benchstat, synctest, race detection patterns
