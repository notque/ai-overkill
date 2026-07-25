# PHP Conventions, Gates, and Testing

Repo conventions with detection commands and fixes. Generic PHP security tutorials stay out; the base model covers them.

## Hard Gates

Blocked unconditionally; replace with the fix in any code you edit.

| Pattern | Reason | Fix |
|---------|--------|-----|
| `$$variable` (variable variables) in business logic | Arbitrary indirection; unanalyzable by static analysis; unauditable attack surface | Explicit variables or a typed map |
| Dynamic code execution via string-eval functions | Executes arbitrary strings as PHP code, in all contexts | Match expressions, callables, allowlisted dispatch |
| `mysql_*` functions | Removed in PHP 7; occurrence signals legacy migration debt needing immediate remediation | PDO prepared statements |
| `preg_replace` with `/e` modifier | Executes replacement string as PHP code; removed in PHP 7 | `preg_replace_callback` |
| Disabling CSRF protection without documented reason | State-changing endpoints become forgeable cross-site | Keep tokens; any `VerifyCsrfToken` exclusion carries a documented, reviewed reason |
| `md5()` / `sha1()` for passwords | Cryptographically broken for password storage | `password_hash()` / `password_verify()` |
| `$guarded = []` (Eloquent) | Mass-assignment: attacker POSTs `{"is_admin": true}` | `$fillable` allowlist; `->update($request->validate([...]))` |
| Secrets hardcoded in config/code | Committed secrets are an immediate incident | `env('PAYMENT_API_KEY')` or a secrets manager |

## Pattern Detection Commands

| Pattern to Replace | Risk | Detection | Fix |
|-------------|------|-----------|-----|
| Fat controller (Eloquent/DB in controllers) | Couples transport to domain, kills testability | `grep -rn --include="*.php" -E 'Eloquent\\Model\|DB::' app/Http/Controllers/` | Thin controller: validate (form request) → delegate to service → return response; business logic, queries, and API calls live in services |
| Associative arrays where DTOs fit | Untyped arrays skip static analysis, risky refactors | `grep -rn --include="*.php" -E '\$data\s*=\s*\[' app/Services/` | `final readonly` DTO classes for commands/payloads; value objects validate in the constructor |
| Raw SQL string interpolation | SQL injection | `grep -rn --include="*.php" -E '(query\|exec)\s*\(\s*["\x27].*\$' src/` | Prepared statements (below) |
| `extract()` on user input | User-controlled variable names injected into scope | `grep -rn --include="*.php" 'extract(\$_' src/` | Explicit assignment from validated input |
| Debug output left in code | `var_dump`/`dd`/`dump`/`die` leak state, break responses | `grep -rn --include="*.php" -E 'var_dump\s*\(\|dd\s*\(\|dump\s*\(\|die\s*\(' src/` | Remove before commit (PostToolUse hook also flags) |
| Service-locator in business services | Hidden dependencies, untestable | `grep -rn --include="*.php" -E 'app\(\)->make\(\|Container::getInstance' app/Services/` | Constructor injection |
| Missing `declare(strict_types=1)` | Implicit coercion hides type bugs | `grep -rLz 'declare(strict_types=1)' $(find src/ app/ -name "*.php" -not -path "*/vendor/*")` | Add to every application file |
| `$guarded = []` | Mass assignment | `grep -rn --include="*.php" 'guarded\s*=\s*\[\s*\]' app/` | `$fillable` allowlist |
| CSRF exclusions | Forgeable endpoints | `grep -rn --include="*.php" -E 'VerifyCsrfToken\|withoutMiddleware.*csrf\|except.*csrf' app/Http/` | Documented reason or removal |

## SQL: Prepared Statements

```php
// PDO
$stmt = $pdo->prepare('SELECT * FROM users WHERE email = :email');
$stmt->execute(['email' => $email]);

// Eloquent query builder
$user = User::where('email', $email)->first();

// Doctrine QueryBuilder
$user = $em->createQueryBuilder()
    ->select('u')->from(User::class, 'u')
    ->where('u.email = :email')->setParameter('email', $email)
    ->getQuery()->getOneOrNullResult();
```

Prepared statements separate SQL structure from data at the driver level. `DB::raw(...$var...)` and `unserialize()` on external input get the same scrutiny as string-built SQL; use `json_decode(..., flags: JSON_THROW_ON_ERROR)` for untrusted payloads, and `unserialize($v, ['allowed_classes' => [...]])` for internal cache/session data only.

## Sessions and Dependency Hygiene

- Regenerate the session ID after authentication and after any privilege change: `$request->session()->regenerate();` (Laravel) or `session_regenerate_id(true);`.
- Run `composer audit` after every `composer update` and before deploying.

## Testing Conventions

### PHPUnit vs. Pest Decision Rule

| Condition | Choice |
|-----------|--------|
| New project, greenfield | PHPUnit (default) |
| Existing project already uses Pest | Pest (stay consistent) |
| Laravel project with team preference for expressive syntax | Pest acceptable |
| CI pipeline expects PHPUnit XML output | PHPUnit |

One test framework per test class — PHPUnit or Pest, exclusively.

### Factory Fixtures (Mandatory)

Generate fixture data through Laravel factories or custom builders; hand-written large arrays are brittle.

```php
$user = User::factory()->verified()->withSubscription('pro')->create();

$order = OrderBuilder::new()
    ->withItems([ProductBuilder::create()->atPrice(1000)])
    ->forCustomer($user)
    ->build();
```

### Unit vs. Integration Separation

| Test Type | What It Tests | Speed | Database |
|-----------|-------------|-------|---------|
| Unit | Single class, dependencies mocked | Fast (<1ms) | No |
| Integration | Service + real DB, or controller + real HTTP stack | Slower (>10ms) | Yes |
| Feature/E2E | Full request lifecycle | Slowest | Yes |

Run unit tests in tight loops; run integration tests in CI. Database usage stays in integration test classes.

### Coverage Commands

```bash
./vendor/bin/phpunit --coverage-text --coverage-html=coverage/
./vendor/bin/pest --coverage --coverage-html=coverage/
```
