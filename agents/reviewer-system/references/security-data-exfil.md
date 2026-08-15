# Data Exfiltration Patterns

Load when reviewing code that handles URL fetching, file paths, raw SQL, XML parsing, response serialization, debug modes, or error handling that may expose internal data.

Data exfiltration: data crosses a trust boundary it should not. Validate inputs at the boundary, expose only fields the caller needs.

---

## Validate URLs at the IP Layer Before Fetching

When fetching user-provided URLs (webhooks, image proxies, import-from-URL), validate the resolved IP against a blocklist of internal ranges. String-based URL checks fail because DNS rebinding, IP encoding, and redirects bypass hostname validation.

### Correct Pattern

**Python:**
```python
import ipaddress, socket
from urllib.parse import urlparse

BLOCKED_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
]

def safe_fetch(user_url: str) -> bytes:
    parsed = urlparse(user_url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('scheme not allowed')
    addr = socket.getaddrinfo(parsed.hostname, parsed.port or 443)[0][4][0]
    ip = ipaddress.ip_address(addr)
    if any(ip in net for net in BLOCKED_RANGES):
        raise ValueError('internal IP not allowed')
    resp = requests.get(user_url, allow_redirects=False, timeout=10)
    return resp.content
```

**TypeScript:**
```ts
import { lookup } from 'dns/promises';
import ipaddr from 'ipaddr.js';

const BLOCKED_RANGES = ['private', 'linkLocal', 'loopback', 'uniqueLocal', 'unspecified'];

async function safeFetch(userUrl: string): Promise<Response> {
  const parsed = new URL(userUrl);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('scheme not allowed');
  const { address } = await lookup(parsed.hostname);
  const ip = ipaddr.parse(address);
  if (BLOCKED_RANGES.includes(ip.range())) throw new Error('internal IP not allowed');
  return fetch(parsed.href, { redirect: 'manual' });
}
```

### Why This Matters

SSRF reaches internal services, cloud metadata (169.254.169.254 returns IAM credentials).

**CVEs:** Capital One 2019, CVE-2021-26855 (Exchange ProxyLogon), CVE-2024-34351 (Next.js Server Actions SSRF), CVE-2020-28168 (axios redirect bypass), CVE-2024-21893 (Ivanti SAML SSRF).

### Detection

```bash
rg -n 'requests\.(get|post|put)\(|urlopen\(|urllib\.request' --type py
rg -n 'fetch\(|axios\.(get|post)\(|got\(' --type ts --type js
rg -n 'callback_url|webhook_url|target_url|redirect_url' --type py --type ts
rg -n 'allow_redirects=True' --type py
```

---

## Contain File Paths with Realpath Validation

Resolve the full path and verify it stays within the intended base directory.

### Correct Pattern

**Python:**
```python
from pathlib import Path
from flask import abort, send_file

def serve_export(name: str):
    base = Path("/var/app/exports").resolve()
    target = (base / name).resolve()
    if not target.is_relative_to(base):
        abort(403)
    return send_file(target)
```

**TypeScript:**
```ts
import path from 'path';

function serveFile(name: string, res: Response) {
  const base = path.resolve('/var/app/exports');
  const target = path.resolve(base, name);
  if (!target.startsWith(base + path.sep)) return res.sendStatus(403);
  res.sendFile(target);
}
```

**Go:**
```go
func serveExport(w http.ResponseWriter, r *http.Request) {
    base := "/var/app/exports"
    name := filepath.Base(r.URL.Query().Get("name"))
    target := filepath.Join(base, name)
    clean, err := filepath.EvalSymlinks(target)
    if err != nil || !strings.HasPrefix(clean, base) {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    http.ServeFile(w, r, clean)
}
```

**Archive extraction (Python):**
```python
import tarfile

def safe_extract(archive_path: str, dest: str):
    with tarfile.open(archive_path) as tar:
        tar.extractall(path=dest, filter="data")  # Python 3.12+
```

### Why This Matters

Path traversal reads arbitrary files. Archive extraction compounds risk (zip-slip).

**CVEs:** CVE-2007-4559 (Python tarfile), CVE-2022-48285 (jszip), CVE-2023-26111 (node-static).

### Detection

```bash
rg -n 'os\.path\.join\(|Path\(' --type py | rg -v 'resolve\(\)|realpath'
rg -n 'extractall\(' --type py | rg -v 'filter='
rg -n 'sendFile\(|readFile\(|readFileSync\(' --type ts
rg -n 'open\(.*request\.|open\(.*user_' --type py
```

---

## Use Parameterized Queries for All Database Access

Pass user values as parameters, never interpolated strings.

### Correct Pattern

**Python (Django):**
```python
invoices = Invoice.objects.filter(customer_id=request.GET["cid"])

# When raw SQL unavoidable:
Invoice.objects.extra(where=["customer_id = %s"], params=[request.GET["cid"]])
```

**TypeScript (Prisma):**
```ts
const users = await prisma.$queryRaw`SELECT * FROM users WHERE name = ${name}`;
// NEVER use $queryRawUnsafe with user input
```

**Go:**
```go
row := db.QueryRowContext(ctx,
    "SELECT * FROM orders WHERE id = $1 AND user_id = $2",
    orderID, userID,
)
```

### Why This Matters

SQL injection via string interpolation remains one of the most exploited vulnerability classes. ORM escape hatches (`.raw()`, `.extra()`, `$queryRawUnsafe`) bypass parameterization.

**CVEs:** CVE-2023-25813 (Sequelize `literal()`), CVE-2025-23061 (Mongoose `populate({match: userObj})`).

### Detection

```bash
rg -n '\.raw\(f"|\.extra\(where=\[f"|cursor\.execute\(f"|RawSQL\(f"' --type py
rg -n 'text\(f"|session\.execute\(f"' --type py
rg -n '\$queryRawUnsafe|\$executeRawUnsafe' --type ts
rg -n 'literal\(|sequelize\.query\(' --type ts --type js
rg -n 'fmt\.Sprintf.*SELECT|fmt\.Sprintf.*INSERT|fmt\.Sprintf.*UPDATE' --type go
```

---

## Disable External Entity Resolution in XML Parsers

Configure XML parsers to reject DTDs and external entity references before parsing untrusted XML.

### Correct Pattern

**Python:**
```python
from defusedxml import ElementTree as ET
tree = ET.fromstring(request.data)

# Or configure lxml explicitly
from lxml import etree
parser = etree.XMLParser(resolve_entities=False, no_network=True)
tree = etree.fromstring(request.data, parser=parser)
```

**Java:**
```java
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
```

**TypeScript/Node:**
```ts
const doc = libxmljs.parseXml(xmlString, { noent: false, nonet: true });
```

### Why This Matters

XXE reads files (`file:///etc/passwd`), makes SSRF requests, or reaches deserialization gadgets.

**CVEs:** CVE-2024-6508 (lxml entity resolution bypass).

### Detection

```bash
rg -n 'xml\.etree|xml\.sax|xml\.dom\.minidom|xml\.parsers\.expat' --type py
rg -n 'etree\.fromstring\(|etree\.parse\(' --type py | rg -v 'resolve_entities=False'
rg -n 'DocumentBuilderFactory|SAXParserFactory' --type java
rg -n 'defusedxml' --type py
```

---

## Expose Only Required Fields in API Responses

Define explicit field lists or DTOs. The database row is never the API response.

### Correct Pattern

**Python (DRF):**
```python
class UserPublicSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'display_name', 'avatar_url']
```

**Python (FastAPI/Pydantic):**
```python
class UserResponse(BaseModel):
    id: int
    display_name: str
    avatar_url: str | None

    class Config:
        extra = "ignore"

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    user = await User.get(id=user_id)
    return user
```

**TypeScript (Prisma):**
```ts
const user = await prisma.user.findUnique({
  where: { id },
  select: { id: true, displayName: true, avatarUrl: true },
});
return res.json(user);
```

**Go:**
```go
type UserResponse struct {
    ID          string `json:"id"`
    DisplayName string `json:"display_name"`
    AvatarURL   string `json:"avatar_url,omitempty"`
}
```

### Why This Matters

Raw rows leak password hashes, API tokens, internal flags. Pydantic `extra = "allow"` passes through unexpected fields.

Real incident: Sentry `0c0aae90ac1` — Pydantic model leaked internal `SeerRunState`.

### Detection

```bash
rg -n "fields = '__all__'" --type py
rg -n '@app\.(get|post|put|patch)' --type py | rg -v 'response_model='
rg -n 'extra = .allow.' --type py
rg -n 'findUnique\(|findFirst\(|findMany\(' --type ts | rg -v 'select:'
rg -n 'DEBUG = True|debug: true|stackTrace.*true' --type py --type ts --type js
```

---

## Disable Debug Modes and Verbose Error Responses in Production

Production errors: generic message to client, full stack trace server-side only.

### Correct Pattern

**Python (Flask):**
```python
@app.errorhandler(500)
def internal_error(error):
    app.logger.error("Internal error", exc_info=error)
    return {"error": "internal server error"}, 500
```

**TypeScript (Express):**
```ts
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  console.error(err.stack);
  res.status(500).json({ error: 'internal server error' });
});
```

### Why This Matters

Debug pages reveal file paths, DB queries, config values, environment variables.

### Detection

```bash
rg -n 'DEBUG = True|debug=True|app\.debug' --type py
rg -n 'err\.stack|error\.stack|traceback' --type ts --type js
rg -n 'traceback\.format_exc\(\)|traceback\.print_exc\(\)' --type py
```
