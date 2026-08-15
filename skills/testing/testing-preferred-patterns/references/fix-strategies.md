# Fix Strategies by Language

Practical tooling and patterns for resolving testing failure modes in Go, Python, and JavaScript/TypeScript.

---

## Go

### Flaky Test Detection
```bash
# Run a test 100 times to detect flakiness
go test -count=100 -run TestSuspectTest ./...

# Run with race detector
go test -race ./...
```

### Parallelization
```go
// Add t.Parallel() to independent tests
func TestFeatureA(t *testing.T) {
    t.Parallel()
    // ...
}
```

### Fresh State per Test
```go
// Use t.Cleanup for deterministic teardown
func setupTestDB(t *testing.T) *Database {
    t.Helper()
    db := NewTestDatabase()
    t.Cleanup(func() { db.Close() })
    return db
}
```

### Error Checking
```go
// Use require for setup, assert for verification
func TestExample(t *testing.T) {
    result, err := SetupDependency()
    require.NoError(t, err, "setup must succeed")  // Fails test immediately

    output := result.Process()
    assert.Equal(t, expected, output)  // Reports but continues
}
```

### Table-Driven Tests for Edge Cases
```go
func TestParseNumber(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr bool
    }{
        {"positive", "42", 42, false},
        {"negative", "-1", -1, false},
        {"zero", "0", 0, false},
        {"empty", "", 0, true},
        {"letters", "abc", 0, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseNumber(tt.input)
            if tt.wantErr {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
                assert.Equal(t, tt.want, got)
            }
        })
    }
}
```

---

## Python

### Flaky Test Detection
```bash
# Install and run with pytest-repeat
pip install pytest-repeat
pytest --count=20 tests/test_suspect.py

# Run with random order
pip install pytest-randomly
pytest -p randomly
```

### Fixture Scoping for Speed
```python
import pytest

# Expensive setup shared across session
@pytest.fixture(scope="session")
def database():
    db = create_database()
    db.run_migrations()
    yield db
    db.cleanup()

# Per-test isolation via transaction rollback
@pytest.fixture
def db_session(database):
    database.begin_transaction()
    yield database
    database.rollback()
```

### Controlling Time
```python
from unittest.mock import patch
from freezegun import freeze_time

# Deterministic time in tests
@freeze_time("2024-01-15 10:30:00")
def test_expiration():
    token = create_token(expires_in=3600)
    assert token.expires_at == datetime(2024, 1, 15, 11, 30, 0)
```

### Skipped Test Audit
```bash
# Find all skipped tests
grep -rn "@pytest.mark.skip\|@unittest.skip\|pytest.skip" tests/

# Find tests with no assertions
grep -rn "def test_" tests/ | while read line; do
    file=$(echo "$line" | cut -d: -f1)
    func=$(echo "$line" | grep -oP 'def \K\w+')
    if ! grep -A 20 "def $func" "$file" | grep -q "assert\|raises\|pytest.raises"; then
        echo "NO ASSERTION: $line"
    fi
done
```

---

## JavaScript / TypeScript

### Flaky Test Detection
```bash
# Run with Jest repeat
npx jest --testPathPattern=suspect.test.ts --repeat=20

# Vitest retry to identify flaky tests
# vitest.config.ts: test.retry = 3
```

### Replacing sleep with waitFor
```javascript
// BAD
await sleep(500);
expect(element).toBeVisible();

// GOOD (React Testing Library)
await waitFor(() => {
  expect(screen.getByText('loaded')).toBeInTheDocument();
});

// GOOD (Playwright)
await expect(page.getByText('loaded')).toBeVisible();
```

### Semantic Selectors over CSS
```javascript
// BAD: Brittle CSS selector
document.querySelector('div.card > span:nth-child(2)');

// GOOD: Testing Library queries (priority order)
screen.getByRole('button', { name: /submit/i });    // 1. Role
screen.getByLabelText('Email');                       // 2. Label
screen.getByPlaceholderText('Enter email');            // 3. Placeholder
screen.getByText('Submit');                            // 4. Text
screen.getByTestId('submit-btn');                      // 5. Test ID (last resort)
```

### Mock Cleanup
```javascript
// Ensure mocks don't leak between tests
afterEach(() => {
  jest.restoreAllMocks();
});

// Or use Vitest's automatic cleanup
// vitest.config.ts: test.restoreMocks = true
```

---

## Cross-Language Patterns

### The Mock Boundary Rule
Mock at the **architectural boundary**, not at every dependency:
- Mock: HTTP clients, databases, file systems, external APIs
- Prefer real executions for pure functions, value objects, and internal collaborators; reserve mocks for external boundaries

### The Assertion Density Rule
Each test should have **1-3 focused assertions** on the behavior under test:
- 0 assertions = no test (just execution)
- 1-3 assertions = focused test
- 10+ assertions = probably over-specified, split into multiple tests

### The Naming Convention
Consistent naming across languages:
- Go: `TestComponent_Condition_ExpectedResult`
- Python: `test_component_condition_expected_result`
- JS: `describe('Component') > it('expected result when condition')`
