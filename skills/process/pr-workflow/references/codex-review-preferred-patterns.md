# Code Review Patterns for Verification
<!-- no-pair-required: document introduction, not an individual failure mode block -->

> **Scope**: Common code failure modes to detect during review, with grep commands for codebase verification.
> **Version range**: Language-specific version notes inline
> **Generated**: 2026-04-16

---

## Overview

Code review — whether by Codex, Claude, or a human — needs concrete patterns to look for.
This file catalogs high-signal failure modes across Go, TypeScript/JavaScript, and Python.
Detection commands let you verify findings in the actual codebase rather than relying on
model interpretation alone.

---

## Go Review Patterns
<!-- no-pair-required: section header with no content -->

### Swallowed errors (blank identifier on error return)

**Detection**:
```bash
rg ',\s*_\s*:?=' --type go -n | grep -v '_test\.go'
grep -rn ',\s*_\s*=' --include="*.go" | grep -v test
```

**What it looks like**:
```go
result, _ := db.Query("SELECT ...")  // error silently dropped
file.Close()                          // return value ignored
```

**Why wrong**: Silent failures compound — the next operation uses invalid state.
Debugging in production becomes impossible without error context.

**Do instead:** Capture every error return and either handle it, wrap it with context, or propagate it to the caller. Use `fmt.Errorf("operation: %w", err)` for wrapping. For cleanup calls like `file.Close()`, use a deferred closure that logs the error rather than discarding it.

**Fix**:
```go
result, err := db.Query("SELECT ...")
if err != nil {
    return fmt.Errorf("query users: %w", err)
}
defer func() {
    if err := file.Close(); err != nil {
        log.Printf("close file: %v", err)
    }
}()
```

**Version note**: `%w` for error wrapping requires Go 1.13+.

---

### Goroutine with no exit strategy

**Detection**:
```bash
rg 'go func\(\)' --type go -n
rg 'go\s+\w+\(' --type go -n | grep -v '_test'
```

**What it looks like**:
```go
func start() {
    go func() {
        for {
            process()  // no context.Done(), no stop channel
        }
    }()
}
```

**Why wrong**: Goroutines with no exit path leak on shutdown. Under load or repeated
invocations, this causes unbounded memory growth.

**Do instead:** Accept a `context.Context` parameter and select on `ctx.Done()` inside the loop. When reviewing, check whether the caller holds a context that gets canceled on shutdown — if yes, flag the missing `ctx` parameter as a goroutine leak risk.

**Fix**:
```go
func start(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            default:
                process()
            }
        }
    }()
}
```

---

### Mutex copied by value (sync.Mutex in struct passed by value)

**Detection**:
```bash
rg 'sync\.Mutex|sync\.RWMutex' --type go -n
# Then check for value receivers on structs containing mutex
grep -rn 'func\s*(\w\+\s\w\+)' --include="*.go" | grep -v '\*'
```

**What it looks like**:
```go
type Counter struct {
    mu  sync.Mutex
    val int
}
func process(c Counter) { ... }  // copies Counter — mutex state diverges
```

**Why wrong**: Copying `sync.Mutex` copies its internal state. The copy and original have
independent lock states — concurrent access is not protected.

**Do instead:** Always pass structs that embed a mutex by pointer, not by value. When reviewing, check every function signature and method receiver on structs containing `sync.Mutex` or `sync.RWMutex`. A value receiver or value parameter is a guaranteed data race.

**Fix**: Always pass structs containing mutexes by pointer:
```go
func process(c *Counter) { ... }
```

**Version note**: `go vet` detects this via the `copylocks` analyzer (all versions).

---

## TypeScript/JavaScript Review Patterns
<!-- no-pair-required: section header with no content -->

### Floating Promise (unhandled async)

**Detection**:
```bash
rg '^\s+[a-zA-Z]\w*\(.*\);$' --type ts -n | grep -v 'await\|return\|const\|let\|var\|//'
rg 'Promise\.' --type ts -n | grep -v '\.catch\|\.then\|await\|void'
```

**What it looks like**:
```typescript
async function handler() {
    sendNotification(userId);  // promise not awaited — errors swallowed
    return { ok: true };
}
```

**Why wrong**: Errors from `sendNotification` are silently dropped. The function returns
before the async work completes, making success/failure undetectable.

**Do instead:** Always `await` async calls whose errors matter, or explicitly mark fire-and-forget calls with `.catch()` so errors are logged. When reviewing, flag any async call that is neither awaited nor has a `.catch()` handler as a swallowed-error risk.

**Fix**:
```typescript
async function handler() {
    await sendNotification(userId);
    return { ok: true };
}
// Or if truly fire-and-forget, handle errors explicitly:
sendNotification(userId).catch(err => logger.error('notification failed', { err }));
```

---

### `as any` silencing TypeScript type checking

**Detection**:
```bash
rg 'as any' --type ts -n
rg ':\s*any\b' --type ts -n | grep -v '\.d\.ts\|// '
```

**What it looks like**:
```typescript
const user = response.data as any;
user.profile.name;  // no type safety — runtime error if profile is undefined
```

**Why wrong**: `as any` opts out of TypeScript's type system entirely. Downstream property
access has no compile-time protection — null reference errors appear at runtime.

**Do instead:** Define an interface for the expected shape and cast to it, then narrow with a type guard or optional chaining before accessing nested properties. When reviewing, flag `as any` on API response shapes as high priority because those surfaces change silently.

**Fix**: Use proper typing or a type guard:
```typescript
interface UserResponse { profile: { name: string } | null }
const user = response.data as UserResponse;
if (user.profile) {
    user.profile.name;  // safe
}
```

---

### `console.log` left in production code

**Detection**:
```bash
rg 'console\.(log|error|warn|debug)\(' --type ts -n | grep -v '\.test\.\|\.spec\.\|__test'
grep -rn 'console\.log' --include="*.ts" --include="*.js" | grep -v test
```

**What it looks like**:
```typescript
async function processOrder(id: string) {
    console.log('processing order', id);  // leaks order IDs to stdout
}
```

**Why wrong**: Console output bypasses structured logging, loses correlation IDs, and may
leak PII to log aggregators that lack access controls.

**Do instead:** Use the project's structured logger (e.g., `pino`, `winston`, `zap`) with a named field for each value. When reviewing, flag any `console.log` that includes an ID, email, order number, or other identifier as a PII-leak risk regardless of whether it looks sensitive in isolation.

**Fix**: Use the project's structured logger:
```typescript
logger.info({ orderId: id }, 'processing order');
```

---

## Python Review Patterns
<!-- no-pair-required: section header with no content -->

### Bare `except` clause

**Detection**:
```bash
rg '^\s+except\s*:' --type py -n
grep -rn 'except:$' --include="*.py"
```

**What it looks like**:
```python
try:
    result = fetch_data()
except:          # catches KeyboardInterrupt, SystemExit, everything
    pass         # silently continues
```

**Why wrong**: Catches `KeyboardInterrupt` and `SystemExit` — Ctrl-C won't stop the process.
Also swallows errors that should surface for debugging.

**Do instead:** Catch only the specific exception types the code can actually recover from, bind them to `e`, log the error, and re-raise or return a meaningful error value. When reviewing, a bare `except:` or `except Exception:` with a `pass` body is always a Critical finding.

**Fix**:
```python
try:
    result = fetch_data()
except (ValueError, ConnectionError) as e:
    logger.error("fetch failed: %s", e)
    raise
```

---

### Mutable default argument

**Detection**:
```bash
rg 'def \w+\(.*=\[\]|def \w+\(.*=\{\}' --type py -n
grep -rn 'def .*=\[\]\|def .*={}' --include="*.py"
```

**What it looks like**:
```python
def add_item(item, items=[]):  # shared across ALL calls
    items.append(item)
    return items
```

**Why wrong**: The default list is created once at function definition, not per call. All
invocations without an explicit `items` argument share the same list — state leaks.

**Do instead:** Use `None` as the default and initialize the mutable object inside the function body on first call. When reviewing, flag any function signature where a default argument is a list literal `[]`, dict literal `{}`, or any other mutable object.

**Fix**:
```python
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

**Version note**: Applies to all Python versions. `pylint W0102` and `mypy` detect this.

---

### `os.system()` or `shell=True` with dynamic input

**Detection**:
```bash
rg 'os\.system\(' --type py -n
rg 'subprocess\.call\(.*shell=True|subprocess\.run\(.*shell=True' --type py -n
```

**What it looks like**:
```python
os.system(f"process {user_input}")  # injection if user_input contains ; or |
subprocess.run(f"grep {pattern} log.txt", shell=True)
```

**Why wrong**: Shell metacharacters in dynamic input execute arbitrary commands. Classic
injection vulnerability — always flag as Critical when input is from user or external source.

**Do instead:** Pass commands as a list of strings with `shell=False` (the default). When reviewing, trace where each dynamic value in an `os.system()` or `shell=True` call originates — if it can reach user-controlled input at any point in the call chain, classify as Critical injection risk.

**Fix**:
```python
subprocess.run(["process", user_input], check=True)  # shell=False (default)
subprocess.run(["grep", pattern, "log.txt"], check=True)
```

---

## Error-Fix Mappings

| Code Pattern Found | Likely Root Cause | Review Severity |
|-------------------|-------------------|-----------------|
| `_, _ = fn()` in Go | Both return values discarded | Critical if fn returns error |
| `as any` in hot path TypeScript | Type mismatch the author couldn't resolve | Improvements — suggest proper interface |
| `shell=True` with f-string | Developer convenience over safety | Critical — injection risk |
| `except: pass` | Debugging residue never removed | Critical — silences all exceptions |
| `go func()` without `ctx` parameter | Pattern copied from simpler code | Improvements — check if caller has context |
| `console.log` with user identifiers | Debug logging committed accidentally | Improvements — PII leak risk |

---

## Detection Commands Reference

```bash
# Go: swallowed errors
rg ',\s*_\s*:?=' --type go -n | grep -v '_test'

# Go: goroutine leaks
rg 'go func\(\)' --type go -n

# TypeScript: floating promises
rg '^\s+[a-zA-Z]\w*\(' --type ts -n | grep -v 'await\|return\|const\|let\|var\|//'

# TypeScript: any casts
rg 'as any' --type ts -n

# Python: bare except
rg '^\s+except\s*:' --type py -n

# Python: mutable defaults
rg 'def \w+\(.*=\[\]' --type py -n

# Python: shell injection risk
rg 'os\.system\(|shell=True' --type py -n
```
