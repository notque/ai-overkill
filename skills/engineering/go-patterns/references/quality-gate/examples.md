# Go PR Quality Gate - Usage Examples

**Note**: Examples using `fish -c` assume Fish shell is installed. You can substitute with your shell of choice (e.g., `bash -c`).

## Example 1: Successful Quality Check

### Scenario
All quality checks pass with good coverage.

### Command
```bash
cd /path/to/go-project
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --verbose
```

### Expected Output (JSON)
```json
{
  "status": "success",
  "coverage": "87.3%",
  "checks_passed": ["static-check", "test", "coverage"],
  "summary": "All quality checks passed"
}
```

### Expected Output (stderr with --verbose)
```
🔍 Running quality checks...
  ├─ Static analysis... ⏳
  ├─ Unit tests... ⏳
  └─ Coverage report... ⏳

✅ All quality checks passed
📊 Coverage: 87.3%
```

### Next Steps
1. View detailed coverage report: `fish -c 'open build/cover.html'`
2. Create commit if ready
3. Push changes for PR review

---

## Example 2: Linting Errors (errcheck)

### Scenario
Code has unchecked error returns.

### Command
```bash
cd /path/to/go-project
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py
```

### Expected Output (JSON)
```json
{
  "status": "failed",
  "exit_code": 2,
  "errors": {
    "linting": [
      {
        "linter": "errcheck",
        "file": "pkg/api/handler.go",
        "line": 45,
        "column": 2,
        "message": "Error return value of `resp.Body.Close` is not checked",
        "description": "Unchecked error returns - detects when error values are not checked",
        "fix_suggestion": "Check error return values or explicitly ignore with _ = err. Common pattern: if err != nil { return err }",
        "severity": "high"
      },
      {
        "linter": "errcheck",
        "file": "pkg/service/processor.go",
        "line": 123,
        "column": 5,
        "message": "Error return value of `file.Close` is not checked",
        "description": "Unchecked error returns - detects when error values are not checked",
        "fix_suggestion": "Check error return values or explicitly ignore with _ = err. Common pattern: if err != nil { return err }",
        "severity": "high"
      }
    ]
  },
  "fix_commands": [],
  "error_count": 2,
  "summary": "Quality checks failed with 2 errors"
}
```

### Fix
```go
// Before (error)
defer resp.Body.Close()

// After (fixed)
defer func() {
    if err := resp.Body.Close(); err != nil {
        log.Printf("failed to close response body: %v", err)
    }
}()
```

---

## Example 3: Import Formatting Issues

### Scenario
Imports are not properly formatted.

### Command
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py
```

### Expected Output (JSON)
```json
{
  "status": "failed",
  "exit_code": 2,
  "errors": {
    "linting": [
      {
        "linter": "goimports",
        "file": "pkg/api/routes.go",
        "line": 5,
        "column": 1,
        "message": "File is not `goimports`-ed",
        "description": "Import formatting issues - detects improperly formatted or missing imports",
        "fix_suggestion": "Run: make goimports (or goimports -w .)",
        "severity": "low"
      }
    ]
  },
  "fix_commands": ["make goimports"],
  "error_count": 1,
  "summary": "Quality checks failed with 1 errors"
}
```

### Fix
```bash
fish -c "make goimports"
# Re-run checks
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py
```

---

## Example 4: Test Failures

### Scenario
Unit tests are failing.

### Command
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --verbose
```

### Expected Output (JSON)
```json
{
  "status": "failed",
  "exit_code": 2,
  "errors": {
    "tests": [
      {
        "package": "github.com/your-org/project/pkg/service",
        "test": "TestProcessRequest",
        "error": "Test failed - check output for details",
        "type": "test_failure"
      }
    ]
  },
  "fix_commands": [],
  "error_count": 1,
  "summary": "Quality checks failed with 1 errors"
}
```

### Expected Output (stderr with --verbose)
```
❌ Quality checks failed (exit code: 2)
📊 Total errors: 1

🧪 Test failures: 1
  • TestProcessRequest in github.com/your-org/project/pkg/service
```

### Debug
```bash
# Run specific test with verbose output
fish -c "go test -v -run TestProcessRequest ./pkg/service"
```

---

## Example 5: Multiple Error Types

### Scenario
Mix of linting errors, test failures, and license issues.

### Command
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --verbose
```

### Expected Output (JSON)
```json
{
  "status": "failed",
  "exit_code": 2,
  "errors": {
    "linting": [
      {
        "linter": "errcheck",
        "file": "pkg/api/handler.go",
        "line": 45,
        "column": 2,
        "message": "Error return value not checked",
        "description": "Unchecked error returns",
        "fix_suggestion": "Check error return values or explicitly ignore with _ = err",
        "severity": "high"
      },
      {
        "linter": "gosec",
        "file": "pkg/crypto/hash.go",
        "line": 23,
        "column": 10,
        "message": "Use of weak cryptographic primitive (G401)",
        "description": "Security vulnerabilities",
        "fix_suggestion": "Review security issue and apply recommended fix. Common issues: weak crypto, command injection, SQL injection",
        "severity": "critical"
      }
    ],
    "tests": [
      {
        "package": "github.com/your-org/project/pkg/service",
        "test": "TestProcessRequest",
        "error": "Test failed - check output for details",
        "type": "test_failure"
      }
    ]
  },
  "fix_commands": [],
  "error_count": 3,
  "summary": "Quality checks failed with 3 errors"
}
```

### Expected Output (stderr with --verbose)
```
❌ Quality checks failed (exit code: 2)
📊 Total errors: 3

🔍 Linting errors: 2
  • errcheck: 1 issues
    • pkg/api/handler.go:45: Error return value not checked
  • gosec: 1 issues
    • pkg/crypto/hash.go:23: Use of weak cryptographic primitive (G401)

🧪 Test failures: 1
  • TestProcessRequest in github.com/your-org/project/pkg/service
```

### Fix Process
1. **Fix critical security issue first** (gosec - weak crypto)
2. **Fix errcheck issues**
3. **Fix failing tests**
4. **Re-run checks**

---

## Example 6: Coverage Threshold Check

### Scenario
Check if coverage meets minimum threshold.

### Command
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --min-coverage 80.0
```

### Expected Output (coverage below threshold)
```json
{
  "status": "failed",
  "coverage": "75.3%",
  "checks_passed": ["static-check", "test", "coverage"],
  "coverage_check": {
    "required": 80.0,
    "actual": 75.3,
    "passed": false
  },
  "summary": "All quality checks passed"
}
```

### Expected Output (coverage meets threshold)
```json
{
  "status": "success",
  "coverage": "87.3%",
  "checks_passed": ["static-check", "test", "coverage"],
  "summary": "All quality checks passed"
}
```

---

## Example 7: Text Format Output

### Scenario
Human-readable text output instead of JSON.

### Command
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --format text
```

### Expected Output (success)
```
✅ All quality checks passed
📊 Coverage: 87.3%

Next steps:
  • View detailed coverage: fish -c 'open build/cover.html'
  • Create commit if ready
```

### Expected Output (failure)
```
❌ Quality checks failed (3 errors)

🔍 Linting Errors (2):

  [errcheck] - 1 issues
    • pkg/api/handler.go:45: Error return value not checked

  [gosec] - 1 issues
    • pkg/crypto/hash.go:23: Use of weak cryptographic primitive (G401)

🧪 Test Failures (1):
  • TestProcessRequest in github.com/your-org/project/pkg/service
    Test failed - check output for details

💡 Suggested fixes:
  • fish -c "make goimports"
```

---

## Example 8: Repository Not Valid

### Scenario
Running in non-Go directory.

### Command
```bash
cd /tmp
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py
```

### Expected Output (JSON to stderr)
```json
{
  "status": "error",
  "error_type": "QualityCheckError",
  "message": "Not a Go repository: go.mod not found in /tmp\nNavigate to a Go repository root directory."
}
```

### Exit Code
2 (validation error)

---

## Example 9: Integration with Claude Code PR Review

### Typical Conversation Flow

**User**: "Review this PR and check quality"

**Claude**: "I'll run the Go PR quality gate to check your code."

```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --verbose
```

**Output** (failure scenario):
```
❌ Quality checks failed (exit code: 2)
📊 Total errors: 2

🔍 Linting errors: 2
  • errcheck: 2 issues

💡 Suggested fixes:
  • fish -c "make goimports"
```

**Claude**: "The quality checks found 2 linting errors:

1. **pkg/api/handler.go:45** - Unchecked error return from `resp.Body.Close()`
   - Fix: Add error checking: `if err := resp.Body.Close(); err != nil { ... }`

2. **pkg/service/processor.go:123** - Unchecked error return from `file.Close()`
   - Fix: Add defer with error handling

Would you like me to show you how to fix these issues?"

---

## Common Error Patterns and Fixes

### Pattern 1: Import Issues
**Error**: `File is not 'goimports'-ed`
**Fix**: `fish -c "make goimports"`

### Pattern 2: Dependency Issues
**Error**: `go.mod is out of sync with go.sum`
**Fix**: `fish -c "make tidy-deps"`

### Pattern 3: License Headers
**Error**: `Missing SPDX license header`
**Fix**: `fish -c "make license-headers"`

### Pattern 4: Unchecked Errors
**Error**: `Error return value not checked (errcheck)`
**Fix**: Add error handling:
```go
if err := someFunc(); err != nil {
    // The called function already provides clear context, so preserve it.
    return err
}
```

### Pattern 5: Security Issues
**Error**: `Use of weak cryptographic primitive (gosec)`
**Fix**: Use strong crypto:
```go
// Before
h := md5.New()

// After
h := sha256.New()
```

---

## Advanced Usage

### Check Specific Repository
```bash
cd /path/to/go-project
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py
```

### Verbose Mode for Debugging
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --verbose
```

### Validate Only (No Checks)
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --validate-only
```

### Enforce Coverage Threshold
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py --min-coverage 85.0
```

### Combine Options
```bash
python3 ~/.claude/skills/engineering/go-patterns/scripts/quality_checker.py \
  --min-coverage 80.0 \
  --format text \
  --verbose
```

---

## Troubleshooting

### Issue: Script hangs during make check
**Solution**: Check for infinite loops in tests, increase timeout, or run tests individually

### Issue: golangci-lint not found
**Solution**: Install via Homebrew: `fish -c "brew install golangci-lint"`

### Issue: Permission denied
**Solution**: Ensure scripts are executable: `fish -c "chmod +x ~/.claude/skills/engineering/go-patterns/scripts/*.py"`

### Issue: Coverage not detected
**Solution**: Verify `make check` includes test coverage, check for `build/cover.out` file
