# Testing Patterns to Detect and Fix Catalog

Detailed code examples for all 10 failure modes. Each section shows BAD (what to avoid) and GOOD (what to do instead) in Go, Python, and JavaScript where applicable.

---

## 1. Testing Implementation Details (Not Behavior)

Tests that assert on internal state, private methods, or implementation specifics break on any refactoring, even when behavior is unchanged.

**Detection heuristic:** If the test would break from a pure refactoring (no behavior change), it tests implementation.

### BAD

```go
// Testing internal state
func TestParser_InternalRegex(t *testing.T) {
    parser := NewParser()
    assert.Equal(t, `\d{3}-\d{3}-\d{4}`, parser.phoneRegex)
}
```

```javascript
// Testing that a specific method was called
test('validates user', () => {
  const spy = jest.spyOn(validator, '_checkEmailFormat');
  validateUser({ email: 'test@example.com' });
  expect(spy).toHaveBeenCalled();  // Tests HOW, not WHAT
});
```

```python
# Asserting on private attributes
def test_cache_internal_storage():
    cache = Cache()
    cache.set("key", "value")
    assert cache._storage["key"] == "value"
```

### GOOD

```go
// Test observable behavior
func TestParser_ValidPhoneNumber_Parses(t *testing.T) {
    parser := NewParser()
    result, err := parser.Parse("123-456-7890")
    assert.NoError(t, err)
    assert.Equal(t, "1234567890", result.Digits())
}
```

```javascript
// Test the outcome
test('validates user with valid email', () => {
  const result = validateUser({ email: 'test@example.com' });
  expect(result.isValid).toBe(true);
});
```

```python
# Test through public interface
def test_cache_stores_and_retrieves():
    cache = Cache()
    cache.set("key", "value")
    assert cache.get("key") == "value"
```

---

## 2. Fragile Tests (Over-Mocking, Brittle Selectors)

When mock setup is longer than test logic, you are testing that mocks work, not that code works.

**Rule of thumb:** If mock setup is >50% of test code, consider integration testing.

### BAD

```javascript
// Over-mocking destroys test value
test('user service creates user', async () => {
  const mockDb = { insert: jest.fn().mockResolvedValue({ id: 1 }) };
  const mockLogger = { info: jest.fn() };
  const mockValidator = { validate: jest.fn().mockReturnValue(true) };
  const mockNotifier = { send: jest.fn() };
  const mockCache = { set: jest.fn() };

  const service = new UserService(mockDb, mockLogger, mockValidator, mockNotifier, mockCache);
  const user = await service.create({ name: 'Alice' });
  expect(mockDb.insert).toHaveBeenCalled();  // Testing mock, not behavior
});

// Brittle CSS selectors
test('shows user name', () => {
  render(<UserProfile user={testUser} />);
  expect(document.querySelector('div.user-card > span.name-text:nth-child(2)')).toHaveTextContent('Alice');
});
```

### GOOD

```javascript
// Mock only external boundaries
test('user service creates user in database', async () => {
  const db = await createTestDatabase();
  const service = new UserService(db);
  const user = await service.create({ name: 'Alice' });

  expect(user.id).toBeDefined();
  expect(user.name).toBe('Alice');
  const retrieved = await db.findById(user.id);
  expect(retrieved.name).toBe('Alice');
});

// Use semantic selectors
test('shows user name', () => {
  render(<UserProfile user={testUser} />);
  expect(screen.getByRole('heading', { name: /Alice/ })).toBeInTheDocument();
});
```

---

## 3. Test Interdependence (Order-Dependent Tests)

Tests that share state and must run in a specific order. They fail when run in isolation or parallel.

**Verification:** Run tests in random order. If they fail, you have interdependence.

### BAD

```python
# Tests share state and must run in order
class TestUserWorkflow:
    user_id = None  # Shared state

    def test_1_create_user(self):
        response = client.post('/users', json={'name': 'Alice'})
        TestUserWorkflow.user_id = response.json()['id']
        assert response.status_code == 201

    def test_2_get_user(self):
        response = client.get(f'/users/{TestUserWorkflow.user_id}')  # Depends on test_1
        assert response.json()['name'] == 'Alice'
```

```go
// Global state mutated by tests
var globalDB *Database

func TestCreateUser(t *testing.T) {
    globalDB.Insert(User{Name: "Alice"})
}

func TestListUsers(t *testing.T) {
    users := globalDB.List()
    assert.Contains(t, users, User{Name: "Alice"})  // Depends on TestCreateUser
}
```

### GOOD

```python
# Each test is self-contained
class TestUserWorkflow:
    def test_create_user(self):
        response = client.post('/users', json={'name': 'Alice'})
        assert response.status_code == 201
        assert response.json()['name'] == 'Alice'

    def test_get_user(self):
        create_response = client.post('/users', json={'name': 'Bob'})
        user_id = create_response.json()['id']
        response = client.get(f'/users/{user_id}')
        assert response.json()['name'] == 'Bob'
```

```go
// Fresh state per test
func TestCreateUser(t *testing.T) {
    db := setupTestDB(t)
    defer db.Cleanup()
    db.Insert(User{Name: "Alice"})
    // ...
}

func TestListUsers(t *testing.T) {
    db := setupTestDB(t)
    defer db.Cleanup()
    db.Insert(User{Name: "Test User"})
    users := db.List()
    assert.Len(t, users, 1)
}
```

---

## 4. Incomplete Assertions (Testing Too Little)

Tests that check existence but not correctness. They pass with completely wrong output.

**Heuristic:** After writing assertions, ask "Could this test pass with obviously wrong output?"

### BAD

```python
def test_fetch_user():
    result = fetch_user(user_id=123)
    assert result is not None  # What if it's an error object?
```

```go
func TestCalculate(t *testing.T) {
    result, err := Calculate(10, 20)
    assert.NoError(t, err)
    // Never checks what result actually is!
}
```

### GOOD

```python
def test_fetch_user():
    result = fetch_user(user_id=123)
    assert result['id'] == 123
    assert result['name'] == 'Alice'
    assert result['email'] == 'alice@example.com'
```

```go
func TestCalculate(t *testing.T) {
    result, err := Calculate(10, 20)
    assert.NoError(t, err)
    assert.Equal(t, 30, result.Value)
    assert.Equal(t, "addition", result.Operation)
}
```

---

## 5. Over-Specification (Testing Too Much)

Asserting on every field including defaults, exact timestamps, and implementation artifacts. Obscures what behavior actually matters.

**Rule:** Each test should have a clear purpose. If you cannot name what behavior it tests, it is over-specified.

### BAD

```javascript
test('creates user', async () => {
  const user = await createUser({ name: 'Alice', email: 'alice@test.com' });
  expect(user.id).toBe(1);  // Why must it be exactly 1?
  expect(user.name).toBe('Alice');
  expect(user.email).toBe('alice@test.com');
  expect(user.createdAt).toBe('2024-01-15T10:30:00Z');  // Exact timestamp
  expect(user.updatedAt).toBe('2024-01-15T10:30:00Z');
  expect(user.version).toBe(1);
  expect(user.isActive).toBe(true);
  expect(user.loginCount).toBe(0);
  expect(user.lastLoginAt).toBeNull();
  expect(user.preferences).toEqual({});
  expect(user.roles).toEqual(['user']);
});
```

### GOOD

```javascript
test('creates user with provided name and email', async () => {
  const user = await createUser({ name: 'Alice', email: 'alice@test.com' });
  expect(user.id).toBeDefined();
  expect(user.name).toBe('Alice');
  expect(user.email).toBe('alice@test.com');
  expect(user.createdAt).toBeInstanceOf(Date);
});

// Separate test for defaults if that behavior matters
test('new user has correct defaults', async () => {
  const user = await createUser({ name: 'Bob', email: 'bob@test.com' });
  expect(user.isActive).toBe(true);
  expect(user.roles).toContain('user');
});
```

---

## 6. Ignored Failures (Skipped Tests, Swallowed Errors)

Skipped tests are broken tests waiting to cause production issues. Swallowed errors hide real failures.

**Action:** Audit skipped tests quarterly. Delete or fix them.

### BAD

```python
@pytest.mark.skip("TODO: fix later")  # Been here 2 years
def test_payment_processing():
    ...

@pytest.mark.skip("Flaky on CI")  # Hiding a real problem
def test_concurrent_updates():
    ...
```

```javascript
test('processes data', async () => {
  try {
    await processData(invalidInput);
    expect(true).toBe(true);  // Always passes
  } catch (e) {
    // Swallowed -- test "passes" even when it fails
  }
});
```

```go
func TestSaveUser(t *testing.T) {
    user := User{Name: "Alice"}
    _ = db.Save(user)  // Error ignored
    retrieved, _ := db.Find(user.ID)  // Another ignored error
    assert.Equal(t, "Alice", retrieved.Name)
}
```

### GOOD

```javascript
test('rejects invalid input', async () => {
  await expect(processData(invalidInput)).rejects.toThrow('Invalid format');
});
```

```go
func TestSaveUser(t *testing.T) {
    user := User{Name: "Alice"}
    err := db.Save(user)
    require.NoError(t, err, "save should succeed")
    retrieved, err := db.Find(user.ID)
    require.NoError(t, err, "find should succeed")
    assert.Equal(t, "Alice", retrieved.Name)
}
```

---

## 7. Poor Test Naming (Unclear What Is Tested)

When test names do not explain behavior, failures do not explain what broke.

**Template:** `Test{Component}_{Condition}_{ExpectedResult}` or `{component} {does what} when {condition}`

### BAD

```go
func TestUser(t *testing.T) { ... }
func TestUserFunc(t *testing.T) { ... }
func TestUserFunc2(t *testing.T) { ... }
```

```python
def test_call_validate_then_save(): ...
def test_with_mock(): ...
def test_new(): ...
```

### GOOD

```go
func TestUser_EmptyName_ReturnsValidationError(t *testing.T) { ... }
func TestUser_DuplicateEmail_ReturnsConflictError(t *testing.T) { ... }
func TestUser_ValidInput_CreatesAndReturnsUser(t *testing.T) { ... }
```

```python
def test_user_with_empty_name_raises_validation_error(): ...
def test_user_with_duplicate_email_raises_conflict_error(): ...
def test_creating_user_with_valid_data_returns_user(): ...
```

---

## 8. Missing Edge Cases

Only testing the happy path gives false confidence. Real users hit edge cases.

**Edge case checklist:**
- Empty input (null, empty string, empty array)
- Boundary values (0, 1, -1, max, min)
- Invalid types
- Unicode / special characters
- Very large / small values
- Concurrent access
- Error conditions

### BAD

```python
def test_parse_number():
    assert parse_number("42") == 42
    assert parse_number("100") == 100
    # What about: "", "abc", None, "-1", "1.5", "999999999999999"?
```

### GOOD

```python
class TestParseNumber:
    def test_positive_integer(self):
        assert parse_number("42") == 42

    def test_negative_integer(self):
        assert parse_number("-42") == -42

    def test_zero(self):
        assert parse_number("0") == 0

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_number("")

    def test_none_raises(self):
        with pytest.raises(TypeError):
            parse_number(None)

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            parse_number("abc")

    def test_whitespace_is_trimmed(self):
        assert parse_number("  42  ") == 42

    def test_very_large_number(self):
        assert parse_number("999999999999") == 999999999999
```

---

## 9. Slow Test Suites (Heavy Setup, No Parallelization)

When setup time dominates test time, developers stop running tests.

**Optimization strategies:**
- Use `t.Parallel()` (Go), `pytest-xdist` (Python), concurrent runners (JS)
- Share expensive fixtures at session/module scope
- Use transactions with rollback instead of database recreation
- Mock external services (network calls are slow)

### BAD

```python
class TestUserAPI:
    def setup_method(self):
        self.db = create_database()       # 2 seconds
        self.db.run_migrations()
        self.db.seed_all_fixtures()
        self.app = create_app(self.db)
        self.client = TestClient(self.app)

    def test_get_user(self):
        # 50ms test, 2000ms setup
        response = self.client.get('/users/1')
        assert response.status_code == 200
```

### GOOD

```python
@pytest.fixture(scope="session")
def db():
    """Database connection shared across all tests."""
    database = create_database()
    database.run_migrations()
    yield database
    database.cleanup()

@pytest.fixture
def client(db):
    """Fresh test client with transaction rollback."""
    db.begin_transaction()
    yield TestClient(create_app(db))
    db.rollback()  # Instant cleanup

def test_get_user(client):
    response = client.get('/users/1')
    assert response.status_code == 200
```

```go
func TestGetUser(t *testing.T) {
    t.Parallel()
    db := setupTestDB(t)
    client := newTestClient(db)
    resp := client.Get("/users/1")
    assert.Equal(t, 200, resp.StatusCode)
}
```

---

## 10. Flaky Tests (Race Conditions, Timing Issues)

Tests that fail randomly erode trust. Developers start ignoring failures.

**Flaky test fixes:**
- Replace `sleep()` with explicit waits/conditions
- Inject clocks for time-dependent logic
- Use synchronization primitives (WaitGroups, channels)
- Run in loop to reproduce: `go test -count=100`

### BAD

```javascript
test('shows loading then content', async () => {
  render(<DataLoader />);
  expect(screen.getByText('Loading...')).toBeInTheDocument();
  await sleep(500);  // Might not be enough
  expect(screen.getByText('Data loaded')).toBeInTheDocument();
});
```

```go
func TestCounter(t *testing.T) {
    counter := NewCounter()
    for i := 0; i < 100; i++ {
        go counter.Increment()
    }
    // Race! Goroutines might not be done
    assert.Equal(t, 100, counter.Value())
}
```

### GOOD

```javascript
test('shows loading then content', async () => {
  render(<DataLoader />);
  expect(screen.getByText('Loading...')).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByText('Data loaded')).toBeInTheDocument();
  });
});
```

```python
def test_rate_limiter():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=5, window_seconds=1, clock=clock)
    for i in range(5):
        assert limiter.allow() == True
    assert limiter.allow() == False
    clock.advance(1.0)  # Deterministic
    assert limiter.allow() == True
```

```go
func TestCounter(t *testing.T) {
    counter := NewCounter()
    var wg sync.WaitGroup
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            counter.Increment()
        }()
    }
    wg.Wait()
    assert.Equal(t, 100, counter.Value())
}
```
