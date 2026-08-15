# Test-Driven Development Examples

This file contains complete TDD examples for Go, Python, and JavaScript showing the full RED-GREEN-REFACTOR cycle.

## Go TDD Example: String Reversal Function

### Iteration 1: Basic Reversal

#### RED Phase - Write Failing Test

**File: `strings/reverse_test.go`**
```go
package strings

import "testing"

func TestReverse_SimpleString_ReturnsReversed(t *testing.T) {
    // Arrange
    input := "hello"
    expected := "olleh"

    // Act
    result := Reverse(input)

    // Assert
    if result != expected {
        t.Errorf("Reverse(%q) = %q; want %q", input, result, expected)
    }
}
```

**Run test (RED):**
```bash
$ go test ./strings -v -run TestReverse
# strings [strings.test]
./reverse_test.go:9:14: undefined: Reverse
FAIL    strings [build failed]
```

✅ **Test fails for RIGHT reason**: Function doesn't exist yet

#### GREEN Phase - Minimum Implementation

**File: `strings/reverse.go`**
```go
package strings

func Reverse(s string) string {
    runes := []rune(s)
    for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
        runes[i], runes[j] = runes[j], runes[i]
    }
    return string(runes)
}
```

**Run test (GREEN):**
```bash
$ go test ./strings -v -run TestReverse
=== RUN   TestReverse_SimpleString_ReturnsReversed
--- PASS: TestReverse_SimpleString_ReturnsReversed (0.00s)
PASS
ok      strings    0.002s
```

✅ **Test passes**: Minimum implementation successful

#### REFACTOR Phase - Improve Code

**No refactoring needed yet** - implementation is clean and simple

**Commit:**
```bash
$ git add strings/
$ git commit -m "Add Reverse function for simple strings

- Add test for basic string reversal
- Implement rune-based reversal for Unicode support
- Passes all tests"
```

### Iteration 2: Handle Empty Strings

#### RED Phase - Add Edge Case Test

**File: `strings/reverse_test.go`**
```go
func TestReverse_EmptyString_ReturnsEmpty(t *testing.T) {
    // Arrange
    input := ""
    expected := ""

    // Act
    result := Reverse(input)

    // Assert
    if result != expected {
        t.Errorf("Reverse(%q) = %q; want %q", input, result, expected)
    }
}
```

**Run test (GREEN - already passes):**
```bash
$ go test ./strings -v -run TestReverse_EmptyString
=== RUN   TestReverse_EmptyString_ReturnsEmpty
--- PASS: TestReverse_EmptyString_ReturnsEmpty (0.00s)
PASS
ok      strings    0.001s
```

✅ **Test already passes**: Implementation handles edge case correctly

### Iteration 3: Table-Driven Tests (Refactor)

#### REFACTOR Phase - Consolidate Tests

**File: `strings/reverse_test.go`**
```go
package strings

import "testing"

func TestReverse(t *testing.T) {
    tests := []struct {
        name     string
        input    string
        expected string
    }{
        {
            name:     "simple string",
            input:    "hello",
            expected: "olleh",
        },
        {
            name:     "empty string",
            input:    "",
            expected: "",
        },
        {
            name:     "single character",
            input:    "a",
            expected: "a",
        },
        {
            name:     "unicode characters",
            input:    "Hello, 世界",
            expected: "界世 ,olleH",
        },
        {
            name:     "palindrome",
            input:    "racecar",
            expected: "racecar",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Act
            result := Reverse(tt.input)

            // Assert
            if result != tt.expected {
                t.Errorf("Reverse(%q) = %q; want %q", tt.input, result, tt.expected)
            }
        })
    }
}
```

**Run refactored tests:**
```bash
$ go test ./strings -v
=== RUN   TestReverse
=== RUN   TestReverse/simple_string
=== RUN   TestReverse/empty_string
=== RUN   TestReverse/single_character
=== RUN   TestReverse/unicode_characters
=== RUN   TestReverse/palindrome
--- PASS: TestReverse (0.00s)
    --- PASS: TestReverse/simple_string (0.00s)
    --- PASS: TestReverse/empty_string (0.00s)
    --- PASS: TestReverse/single_character (0.00s)
    --- PASS: TestReverse/unicode_characters (0.00s)
    --- PASS: TestReverse/palindrome (0.00s)
PASS
ok      strings    0.002s
```

✅ **All tests pass after refactoring**

---

## Python TDD Example: Email Validator

### Iteration 1: Basic Email Validation

#### RED Phase - Write Failing Test

**File: `tests/test_validator.py`**
```python
import pytest
from validator import EmailValidator

def test_validate_email_valid_format_returns_true():
    # Arrange
    validator = EmailValidator()
    email = "user@example.com"

    # Act
    result = validator.validate(email)

    # Assert
    assert result is True
```

**Run test (RED):**
```bash
$ pytest tests/test_validator.py::test_validate_email_valid_format_returns_true -v
================================ test session starts =================================
collected 0 items / 1 error

======================================= ERRORS =======================================
________________ ERROR collecting tests/test_validator.py ___________________________
tests/test_validator.py:2: in <module>
    from validator import EmailValidator
E   ModuleNotFoundError: No module named 'validator'
```

✅ **Test fails for RIGHT reason**: Module doesn't exist yet

#### GREEN Phase - Minimum Implementation

**File: `validator.py`**
```python
import re

class EmailValidator:
    def __init__(self):
        self.pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    def validate(self, email: str) -> bool:
        return bool(re.match(self.pattern, email))
```

**Run test (GREEN):**
```bash
$ pytest tests/test_validator.py::test_validate_email_valid_format_returns_true -v
================================ test session starts =================================
collected 1 item

tests/test_validator.py::test_validate_email_valid_format_returns_true PASSED [100%]

================================= 1 passed in 0.01s ==================================
```

✅ **Test passes**: Minimum implementation successful

### Iteration 2: Invalid Email Format

#### RED Phase - Add Failure Case

**File: `tests/test_validator.py`**
```python
def test_validate_email_invalid_format_returns_false():
    # Arrange
    validator = EmailValidator()
    email = "invalid-email"

    # Act
    result = validator.validate(email)

    # Assert
    assert result is False
```

**Run test (GREEN - already passes):**
```bash
$ pytest tests/test_validator.py::test_validate_email_invalid_format_returns_false -v
================================ test session starts =================================
collected 1 item

tests/test_validator.py::test_validate_email_invalid_format_returns_false PASSED [100%]

================================= 1 passed in 0.01s ==================================
```

✅ **Test already passes**: Regex handles invalid format

### Iteration 3: Parametrized Tests (Refactor)

#### REFACTOR Phase - Use pytest.mark.parametrize

**File: `tests/test_validator.py`**
```python
import pytest
from validator import EmailValidator

@pytest.mark.parametrize("email,expected", [
    # Valid emails
    ("user@example.com", True),
    ("test.user@example.co.uk", True),
    ("user+tag@example.com", True),
    ("user_name@example-domain.com", True),

    # Invalid emails
    ("invalid-email", False),
    ("@example.com", False),
    ("user@", False),
    ("user@.com", False),
    ("user name@example.com", False),
    ("user@example", False),
])
def test_validate_email(email, expected):
    # Arrange
    validator = EmailValidator()

    # Act
    result = validator.validate(email)

    # Assert
    assert result is expected, f"validate({email!r}) should return {expected}"
```

**Run refactored tests:**
```bash
$ pytest tests/test_validator.py -v
================================ test session starts =================================
collected 10 items

tests/test_validator.py::test_validate_email[user@example.com-True] PASSED    [ 10%]
tests/test_validator.py::test_validate_email[test.user@example.co.uk-True] PASSED [ 20%]
tests/test_validator.py::test_validate_email[user+tag@example.com-True] PASSED [ 30%]
tests/test_validator.py::test_validate_email[user_name@example-domain.com-True] PASSED [ 40%]
tests/test_validator.py::test_validate_email[invalid-email-False] PASSED      [ 50%]
tests/test_validator.py::test_validate_email[@example.com-False] PASSED       [ 60%]
tests/test_validator.py::test_validate_email[user@-False] PASSED              [ 70%]
tests/test_validator.py::test_validate_email[user@.com-False] PASSED          [ 80%]
tests/test_validator.py::test_validate_email[user name@example.com-False] PASSED [ 90%]
tests/test_validator.py::test_validate_email[user@example-False] PASSED       [100%]

================================= 10 passed in 0.02s =================================
```

✅ **All tests pass after refactoring**

#### REFACTOR Phase - Extract Pattern to Constant

**File: `validator.py`**
```python
import re
from typing import ClassVar

class EmailValidator:
    EMAIL_PATTERN: ClassVar[str] = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    def __init__(self):
        self._compiled_pattern = re.compile(self.EMAIL_PATTERN)

    def validate(self, email: str) -> bool:
        """Validate email format using RFC-compliant regex pattern."""
        if not email:
            return False
        return bool(self._compiled_pattern.match(email))
```

**Run tests after refactoring:**
```bash
$ pytest tests/test_validator.py -v
================================= 10 passed in 0.02s =================================
```

✅ **Tests still pass after refactoring**

**Commit:**
```bash
$ git add validator.py tests/
$ git commit -m "Add email validator with comprehensive tests

- Add EmailValidator class with regex pattern
- Parametrized tests for valid/invalid emails
- Extract pattern to class constant
- All 10 test cases passing"
```

---

## JavaScript TDD Example: Shopping Cart

### Iteration 1: Add Items to Cart

#### RED Phase - Write Failing Test

**File: `tests/cart.test.js`**
```javascript
import { describe, it, expect } from 'vitest'
import { ShoppingCart } from '../src/cart'

describe('ShoppingCart', () => {
  it('should add item to cart', () => {
    // Arrange
    const cart = new ShoppingCart()
    const item = { id: 1, name: 'Widget', price: 9.99 }

    // Act
    cart.addItem(item)

    // Assert
    expect(cart.getItems()).toHaveLength(1)
    expect(cart.getItems()[0]).toEqual(item)
  })
})
```

**Run test (RED):**
```bash
$ npm test -- cart.test.js

 FAIL  tests/cart.test.js
  ShoppingCart
    ✕ should add item to cart (2 ms)

  ● ShoppingCart › should add item to cart

    Cannot find module '../src/cart' from 'tests/cart.test.js'
```

✅ **Test fails for RIGHT reason**: Module doesn't exist yet

#### GREEN Phase - Minimum Implementation

**File: `src/cart.js`**
```javascript
export class ShoppingCart {
  constructor() {
    this.items = []
  }

  addItem(item) {
    this.items.push(item)
  }

  getItems() {
    return this.items
  }
}
```

**Run test (GREEN):**
```bash
$ npm test -- cart.test.js

 PASS  tests/cart.test.js
  ShoppingCart
    ✓ should add item to cart (2 ms)

Test Files  1 passed (1)
     Tests  1 passed (1)
```

✅ **Test passes**: Minimum implementation successful

### Iteration 2: Calculate Total

#### RED Phase - Add Total Calculation Test

**File: `tests/cart.test.js`**
```javascript
it('should calculate total price', () => {
  // Arrange
  const cart = new ShoppingCart()
  cart.addItem({ id: 1, name: 'Widget', price: 9.99 })
  cart.addItem({ id: 2, name: 'Gadget', price: 14.99 })

  // Act
  const total = cart.getTotal()

  // Assert
  expect(total).toBe(24.98)
})
```

**Run test (RED):**
```bash
$ npm test -- cart.test.js

 FAIL  tests/cart.test.js
  ShoppingCart
    ✓ should add item to cart (1 ms)
    ✕ should calculate total price (3 ms)

  ● ShoppingCart › should calculate total price

    TypeError: cart.getTotal is not a function
```

✅ **Test fails for RIGHT reason**: Method doesn't exist

#### GREEN Phase - Implement Total Calculation

**File: `src/cart.js`**
```javascript
export class ShoppingCart {
  constructor() {
    this.items = []
  }

  addItem(item) {
    this.items.push(item)
  }

  getItems() {
    return this.items
  }

  getTotal() {
    return this.items.reduce((sum, item) => sum + item.price, 0)
  }
}
```

**Run test (GREEN):**
```bash
$ npm test -- cart.test.js

 PASS  tests/cart.test.js
  ShoppingCart
    ✓ should add item to cart (1 ms)
    ✓ should calculate total price (1 ms)

Test Files  1 passed (1)
     Tests  2 passed (2)
```

✅ **Test passes**: Total calculation working

### Iteration 3: Handle Quantities

#### RED Phase - Add Quantity Test

**File: `tests/cart.test.js`**
```javascript
it('should handle item quantities', () => {
  // Arrange
  const cart = new ShoppingCart()
  const item = { id: 1, name: 'Widget', price: 9.99 }

  // Act
  cart.addItem(item, 3)

  // Assert
  expect(cart.getItems()).toHaveLength(1)
  expect(cart.getItems()[0].quantity).toBe(3)
  expect(cart.getTotal()).toBe(29.97)
})
```

**Run test (RED):**
```bash
$ npm test -- cart.test.js

 FAIL  tests/cart.test.js
  ● ShoppingCart › should handle item quantities

    expect(received).toBe(expected) // Object.is equality

    Expected: 3
    Received: undefined
```

✅ **Test fails for RIGHT reason**: Quantity not tracked

#### GREEN Phase - Add Quantity Support

**File: `src/cart.js`**
```javascript
export class ShoppingCart {
  constructor() {
    this.items = []
  }

  addItem(item, quantity = 1) {
    this.items.push({ ...item, quantity })
  }

  getItems() {
    return this.items
  }

  getTotal() {
    return this.items.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    )
  }
}
```

**Run test (GREEN):**
```bash
$ npm test -- cart.test.js

 PASS  tests/cart.test.js
  ShoppingCart
    ✓ should add item to cart (1 ms)
    ✓ should calculate total price (1 ms)
    ✓ should handle item quantities (1 ms)

Test Files  1 passed (1)
     Tests  3 passed (3)
```

✅ **All tests pass**: Quantity support working

#### REFACTOR Phase - Round Total to 2 Decimals

**File: `src/cart.js`**
```javascript
export class ShoppingCart {
  constructor() {
    this.items = []
  }

  addItem(item, quantity = 1) {
    this.items.push({ ...item, quantity })
  }

  getItems() {
    return this.items
  }

  getTotal() {
    const total = this.items.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    )
    // Round to 2 decimal places to avoid floating point errors
    return Math.round(total * 100) / 100
  }
}
```

**Run tests after refactoring:**
```bash
$ npm test -- cart.test.js

 PASS  tests/cart.test.js
  ShoppingCart
    ✓ should add item to cart (1 ms)
    ✓ should calculate total price (1 ms)
    ✓ should handle item quantities (1 ms)

Test Files  1 passed (1)
     Tests  3 passed (3)
```

✅ **Tests still pass after refactoring**

**Commit:**
```bash
$ git add src/cart.js tests/cart.test.js
$ git commit -m "Add shopping cart with item management

- Add ShoppingCart class with addItem and getTotal
- Support item quantities with default of 1
- Round totals to 2 decimal places
- All tests passing (3/3)"
```

---

## Advanced TDD Patterns

### Pattern 1: Property-Based Testing (Go)

**Test random inputs to find edge cases:**

```go
package strings

import (
    "testing"
    "testing/quick"
)

func TestReverse_PropertyBased_DoublReverse(t *testing.T) {
    // Property: Reverse(Reverse(s)) == s
    f := func(s string) bool {
        return Reverse(Reverse(s)) == s
    }

    if err := quick.Check(f, nil); err != nil {
        t.Error(err)
    }
}
```

### Pattern 2: Test Fixtures with Cleanup (Python)

**Use pytest fixtures for setup/teardown:**

```python
import pytest
import tempfile
import os

@pytest.fixture
def temp_database():
    """Create temporary database for testing."""
    # Setup
    db_fd, db_path = tempfile.mkstemp()
    db = Database(db_path)

    yield db  # Provide to test

    # Teardown
    db.close()
    os.close(db_fd)
    os.unlink(db_path)

def test_database_insert(temp_database):
    temp_database.insert({'id': 1, 'name': 'test'})
    assert temp_database.count() == 1
```

### Pattern 3: Mocking External Dependencies (JavaScript)

**Use vitest mocks to isolate code under test:**

```javascript
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { UserService } from '../src/userService'
import { ApiClient } from '../src/apiClient'

// Mock the API client
vi.mock('../src/apiClient')

describe('UserService', () => {
  let mockApiClient
  let userService

  beforeEach(() => {
    mockApiClient = {
      get: vi.fn()
    }
    userService = new UserService(mockApiClient)
  })

  it('should fetch user by id', async () => {
    // Arrange
    const mockUser = { id: 1, name: 'John' }
    mockApiClient.get.mockResolvedValue(mockUser)

    // Act
    const result = await userService.getUserById(1)

    // Assert
    expect(mockApiClient.get).toHaveBeenCalledWith('/users/1')
    expect(result).toEqual(mockUser)
  })
})
```

---

## TDD Patterns to Detect and Fix

### Signal 1: Writing Tests After Implementation

**Wrong:**
```javascript
// 1. Write implementation first
function calculateDiscount(price, percent) {
  return price * (percent / 100)
}

// 2. Then write test
it('should calculate discount', () => {
  expect(calculateDiscount(100, 10)).toBe(10)
})
```

**Right:**
```javascript
// 1. Write test first (RED)
it('should calculate discount', () => {
  expect(calculateDiscount(100, 10)).toBe(10)
})

// 2. Then implement (GREEN)
function calculateDiscount(price, percent) {
  return price * (percent / 100)
}
```

### Signal 2: Testing Implementation Details

**Wrong:**
```python
def test_user_service_uses_cache():
    service = UserService()
    service.get_user(1)
    # Testing HOW it works (implementation detail)
    assert service._cache_hits == 1
```

**Right:**
```python
def test_user_service_returns_user():
    service = UserService()
    user = service.get_user(1)
    # Testing WHAT it does (behavior)
    assert user.id == 1
    assert user.name is not None
```

### Signal 3: Overly Broad Tests

**Wrong:**
```go
func TestEverything(t *testing.T) {
    // Tests too many things at once
    user := CreateUser("john", "john@example.com")
    if user.Name != "john" {
        t.Error("name wrong")
    }
    if user.Email != "john@example.com" {
        t.Error("email wrong")
    }
    user.UpdateEmail("new@example.com")
    if user.Email != "new@example.com" {
        t.Error("email update wrong")
    }
}
```

**Right:**
```go
func TestCreateUser_ValidData_ReturnsUser(t *testing.T) {
    user := CreateUser("john", "john@example.com")

    if user.Name != "john" {
        t.Errorf("expected name %q, got %q", "john", user.Name)
    }
}

func TestUpdateEmail_ValidEmail_UpdatesSuccessfully(t *testing.T) {
    user := CreateUser("john", "john@example.com")

    user.UpdateEmail("new@example.com")

    if user.Email != "new@example.com" {
        t.Errorf("expected email %q, got %q", "new@example.com", user.Email)
    }
}
```

---

## TDD Workflow Summary

**The cycle for EVERY feature:**

1. **RED**: Write failing test → Run test → Verify failure reason
2. **GREEN**: Write minimum code → Run test → Verify pass
3. **REFACTOR**: Improve code → Run tests → Verify still pass
4. **COMMIT**: Save working test + implementation

**Key principles:**
- Test first, always
- Verify test fails for the RIGHT reason
- Implement minimum code to pass
- Refactor incrementally with green tests
- Commit atomic units of working code
