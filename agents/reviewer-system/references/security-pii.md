# PII Exposure Patterns

Load when reviewing code that handles personal data in logs, test fixtures, error responses, serialized output, URLs, telemetry, or git history.

PII exposure: personally identifiable information appears in a context with broader visibility, longer retention, or lower trust than intended. Use synthetic data in tests, structured identifiers in logs, explicit field selection in API responses.

---

## Use Synthetic Data in Test Fixtures

Tests, fixtures, snapshots, cassettes, and seed files must use obviously synthetic identifiers.

### Correct Pattern

**Python:**
```python
fixture = {
    "email": "user@example.com",
    "org_slug": "org-slug",
    "name": "Jane Doe",
    "ip": "198.51.100.23",       # RFC 5737
    "arr_usd": 120000,
    "renewal_date": "2026-01-01",
}
```

**TypeScript:**
```ts
const fixture = {
  email: 'user@example.com',
  orgSlug: 'org-slug',
  name: 'John Doe',
  ip: '203.0.113.42',  // RFC 5737 TEST-NET-3
  monthlySpend: 1000,
  seatCount: 25,
};
```

### Safe Domains and IP Ranges

| Type | Safe Values | Standard |
|------|-------------|----------|
| Email domains | `example.com`, `example.org`, `example.net`, `.invalid` | RFC 2606 |
| IPv4 | `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` | RFC 5737 |
| IPv6 | `2001:db8::/32` | RFC 3849 |
| Names | `Jane Doe`, `John Doe`, `Alice`, `Bob`, `Acme Corp` | Convention |

### Why This Matters

Real data in git history cannot be fully purged. A single real email is a GDPR data subject access request waiting to happen.

### Detection

```bash
rg -n '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' tests/ fixtures/ --type py --type ts | \
  rg -v 'example\.(com|org|net)|noreply|test@|foo@|user@'

rg -n '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b' tests/ fixtures/ | \
  rg -v '192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|127\.0\.0\.|0\.0\.0\.0|10\.\|172\.(1[6-9]|2|3[01])\.|192\.168\.'

rg -n 'customer|account.*slug|org.*slug|tenant' tests/ fixtures/ --type py --type ts
```

---

## Log Structured Identifiers Instead of Raw PII

Log internal ID, salted hash, or correlation ID — never raw email, IP, phone, or request body.

### Correct Pattern

**Python:**
```python
import hashlib

def hash_email(email: str) -> str:
    return hashlib.sha256(f"salt:{email}".encode()).hexdigest()[:12]

logger.warning(
    "identity lookup failed",
    extra={"user_id": user.id, "email_hash": hash_email(user.email)},
)
```

**TypeScript:**
```ts
logger.warn('signup failed', {
  userId: user.id,
  reason: 'validation_failed',
});
```

**Go:**
```go
slog.Warn("identity lookup failed",
    "user_id", user.ID,
    "error", err,
)
```

### Why This Matters

PII in logs creates a secondary data store bypassing access controls. Log aggregators retain data for months, index for full-text search, and expose to broad teams.

### Detection

```bash
rg -n 'logger\.\w+\(.*email|logger\.\w+\(.*REMOTE_ADDR|logger\.\w+\(.*request\.(body|data|META)' --type py
rg -n 'logger\.\w+\(.*email|logger\.\w+\(.*req\.(body|ip)|console\.\w+\(.*email' --type ts
rg -n 'set_user\(|set_tag\(.*email|set_extra\(.*email' --type py
rg -n 'slog\.\w+\(.*email|log\.\w+\(.*email|zap\.\w+\(.*email' --type go
```

---

## Keep PII Out of URL Query Strings and Path Segments

Emails, phone numbers, names in URLs appear in browser history, server logs, CDN logs, referrer headers, analytics.

### Correct Pattern

**Python:**
```python
request.session["login_error"] = "invalid_magic_code"
return redirect("/login/error")
```

**TypeScript:**
```ts
return redirect('/oauth/error?reason=invalid_code');
```

### Detection

```bash
rg -n 'redirect.*email=|redirect.*user=|redirect.*phone=' --type py --type ts
rg -n 'f".*\?.*email|`.*\?.*email|\?.*email=' --type py --type ts
```

---

## Exclude PII Fields from Serialized API Responses

Declare explicit field lists excluding PII not required by the caller.

### Correct Pattern

**Python (DRF):**
```python
class UserPublicSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'display_name', 'avatar_url']
```

**TypeScript (Prisma):**
```ts
const user = await prisma.user.findUnique({
  where: { id },
  select: { id: true, displayName: true, avatarUrl: true },
});
return res.json(user);
```

**GraphQL:**
```graphql
type UserPublic {
  id: ID!
  displayName: String!
  avatarUrl: String
}
```

### Why This Matters

`fields = '__all__'` exposes every column including fields added by future migrations. Full-row Prisma queries return password hashes, 2FA secrets.

### Detection

```bash
rg -n "fields = '__all__'" --type py
rg -n 'email|phone|ipAddress|password' --type graphql --type ts | rg 'type |interface '
rg -n 'findUnique\(|findFirst\(' --type ts | rg -v 'select:'
```

---

## Scrub PII from Error Responses and Exception Handlers

Error responses: generic message + correlation ID. Stack traces, SQL, request bodies stay server-side.

### Correct Pattern

**Python:**
```python
import uuid

@app.errorhandler(Exception)
def handle_error(error):
    correlation_id = str(uuid.uuid4())
    app.logger.error("unhandled exception",
        extra={"correlation_id": correlation_id, "error": str(error)}, exc_info=True)
    return {"error": "internal server error", "reference": correlation_id}, 500
```

**TypeScript:**
```ts
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  const correlationId = crypto.randomUUID();
  console.error({ correlationId, error: err.stack });
  res.status(500).json({ error: 'internal server error', reference: correlationId });
});
```

### Detection

```bash
rg -n 'err\.stack|error\.stack|traceback|exc_info' --type py --type ts | rg -v 'logger\.|console\.'
rg -n 'request\.(body|data|form)|req\.body' --type py --type ts | rg 'return |res\.(json|send)'
rg -n 'set_user\(|set_context\(|set_extra\(' --type py | rg 'email|phone|ip|address'
```

---

## Detect Common PII Patterns in Code

```bash
# Email addresses (excluding safe domains)
rg -n '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' --type py --type ts --type js \
  --glob '!node_modules/*' --glob '!vendor/*' | \
  rg -v 'example\.(com|org|net)|noreply|test@|foo@|bar@|user@|\.invalid'

# US phone numbers
rg -n '\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b' --type py --type ts --type js --glob '!node_modules/*'

# US Social Security Numbers
rg -n '\b\d{3}-\d{2}-\d{4}\b' --type py --type ts --type js --glob '!node_modules/*'

# Credit card patterns
rg -n '\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,7}\b' --type py --type ts --type js --glob '!node_modules/*'

# IP addresses in non-test code
rg -n '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b' --type py --type ts \
  --glob '!tests/*' --glob '!*test*' --glob '!node_modules/*' | \
  rg -v '0\.0\.0\.0|127\.0\.0\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.'

# AWS access keys
rg -n 'AKIA[0-9A-Z]{16}' --type py --type ts --type js
```

### Distinguishing Real PII from Safe Placeholders

Before reporting, verify:
1. **Domain.** RFC 2606 domains (`example.com`, `.invalid`) are safe.
2. **Context.** Git author metadata, translator credits are public by choice.
3. **IP range.** RFC 5737 (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and RFC 3849 (`2001:db8::/32`) are reserved.
4. **File role.** `tests/` with synthetic names and round numbers is fixture data.
5. **Sink.** Email in memory is normal. Same email in a log statement, URL, metric tag, or error response is a finding.
