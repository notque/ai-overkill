# Authorization Security Patterns

Load when reviewing code that handles permissions, access control, RBAC, IDOR, JWT validation, session management, or protected resources.

Authorization answers: is this principal permitted to perform this action on this resource?

---

## Scope Querysets to the Authenticated User

Every database query for a user-owned resource must filter by the authenticated principal. The query is the authorization boundary.

### Correct Pattern

**Django/DRF:**
```python
class OrderViewSet(ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(organization=self.request.user.organization)
```

**Express/Prisma:**
```ts
router.get('/orders/:id', requireAuth, async (req, res) => {
  const order = await db.order.findFirst({
    where: { id: req.params.id, userId: req.user.id },
  });
  if (!order) return res.sendStatus(404);
  res.json(order);
});
```

**FastAPI:**
```python
@router.get("/orders/{order_id}")
async def get_order(order_id: int, user: User = Depends(get_current_user)):
    order = await Order.filter(id=order_id, owner=user).first()
    if not order:
        raise HTTPException(status_code=404)
    return order
```

**Go:**
```go
func (h *Handler) GetOrder(w http.ResponseWriter, r *http.Request) {
    userID := auth.UserIDFromContext(r.Context())
    orderID := chi.URLParam(r, "orderID")
    order, err := h.store.GetOrderForUser(r.Context(), orderID, userID)
    if err != nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    json.NewEncoder(w).Encode(order)
}
```

### Why This Matters

Unscoped queries are the most common authorization vulnerability. `Order.objects.get(id=order_id)` without a user filter lets any authenticated user read any order by enumerating IDs (IDOR).

Real incidents: Shopify HackerOne #2207248, SingleStore HackerOne #3219944.

**CVEs:** OWASP A01:2021 Broken Access Control — #1 web vulnerability category.

### Detection

```bash
rg -n 'class \w+ViewSet.*ModelViewSet' --type py -l | xargs rg -L 'def get_queryset'
rg -n 'objects\.(get|filter)\(id=.*kwargs\[|id=.*request\.(GET|POST|data)' --type py
rg -n 'findUnique\(\{.*where:.*req\.params' --type ts
rg -n 'GetOrder|FindOrder|FetchOrder' --type go -l | xargs rg -n 'func.*http\.Request'
```

---

## Close Permission Functions with Explicit Default Deny

Every permission function must end with `return False` (or equivalent). Unrecognized roles must deny access.

### Correct Pattern

**Python:**
```python
def can_edit(user, resource):
    if user.role == "admin":
        return True
    if user.role == "editor" and resource.owner_id == user.id:
        return True
    return False
```

**TypeScript:**
```ts
function canEdit(user: User, resource: Resource): boolean {
  if (user.role === 'admin') return true;
  if (user.role === 'editor' && resource.ownerId === user.id) return true;
  return false;
}
```

**Go:**
```go
func canEdit(user *User, resource *Resource) bool {
    switch user.Role {
    case "admin":
        return true
    case "editor":
        return resource.OwnerID == user.ID
    default:
        return false
    }
}
```

### Why This Matters

Missing `return False` causes `None`/`undefined` returns, which are falsy but leak through callers checking truthiness differently. Apollo Router CVE-2025-64347: a renamed directive bypassed authorization because the default path allowed the request.

### Detection

```bash
rg -n 'def (can_|has_|check_|is_allowed|is_authorized)' --type py
rg -n 'function (can|has|check|isAllowed|isAuthorized)' --type ts
```

---

## Restrict Writable Fields with Explicit Allowlist

Serializers and update handlers must declare exactly which fields a client can write. Spreading request body into DB operations allows mass assignment.

### Correct Pattern

**Django/DRF:**
```python
class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['display_name', 'avatar_url', 'timezone']
```

**Express/Zod:**
```ts
const ProfileUpdate = z.object({
  displayName: z.string().max(80).optional(),
  avatarUrl: z.string().url().optional(),
  timezone: z.string().optional(),
});

router.patch('/me', requireAuth, async (req, res) => {
  const data = ProfileUpdate.parse(req.body);
  const user = await db.user.update({ where: { id: req.user.id }, data });
  res.json(user);
});
```

**FastAPI/Pydantic:**
```python
class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: HttpUrl | None = None
    timezone: str | None = None

    class Config:
        extra = "forbid"
```

### Why This Matters

DRF's `fields = '__all__'` on a write endpoint exposes every model field including `is_staff`, `is_superuser`. Spreading `req.body` into Prisma's `data` does the same.

**CVEs:** OWASP A01:2021, Rails CVE-2012-2661, GitHub 2012 mass-assignment incident.

### Detection

```bash
rg -n "fields = '__all__'" --type py
rg -n 'data: req\.body|\.create\(req\.body\)|\.update\(.*req\.body' --type ts
rg -n "extra = .allow." --type py
```

---

## Apply Authorization Guards at the Router Level

Mount permission middleware on the router or controller, not per-handler. A new endpoint without the decorator is silently unprotected.

### Correct Pattern

**FastAPI:**
```python
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)]
)
```

**Express:**
```ts
app.use('/admin', requireAuth, requireAdmin, adminRouter);
```

**NestJS:**
```ts
@UseGuards(AuthGuard, AdminGuard)
@Controller('admin')
export class AdminController {
  @Get('users')
  findAll() { return this.userService.findAll(); }
}
```

**Django:**
```python
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.LoginRequiredMiddleware',
]
```

### Why This Matters

MLflow ajax-api endpoints shipped without `Depends()` — the guard existed but was never attached. Every unguarded route is a potential privilege escalation.

### Detection

```bash
rg -n 'APIRouter\(' --type py | rg -v 'dependencies='
rg -n "app\.use\('/(admin|api|internal)" --type ts
rg -n '@Controller' --type ts -l | xargs rg -L '@UseGuards'
```

---

## Validate JWT Claims with Algorithm Pinning and Scope Verification

Decode JWTs with signature verification enabled, algorithm pinned. After verification, confirm token claims (org, tenant, scope) match the resource.

### Correct Pattern

**Python (PyJWT):**
```python
payload = jwt.decode(token, public_key, algorithms=["RS256"])
if payload["org_id"] != request.org.id:
    raise PermissionDenied("token org mismatch")
if "org:admin" not in payload.get("scope", []):
    raise PermissionDenied("insufficient scope")
```

**TypeScript (jsonwebtoken):**
```ts
const claims = jwt.verify(token, publicKey, { algorithms: ['RS256'] });
if (claims.orgId !== req.org.id) {
  throw new ForbiddenError('token org mismatch');
}
```

### Why This Matters

`jwt.decode()` without verification returns attacker-controlled strings. Algorithm confusion attacks (RS256 key as HS256 secret) let attackers forge tokens.

**CVEs:** jsonwebtoken CVE-2022-23540, CVE-2022-23541, PyJWT CVE-2022-29217, Java ECDSA CVE-2022-21449.

### Detection

```bash
rg -n 'jwt\.decode.*verify_signature.*False|jwt\.decode\(.*options=' --type py
rg -n 'jwt\.decode' --type py | rg -v 'algorithms='
rg -n 'jwt\.decode\(' --type ts
rg -n 'jwt\.verify' --type ts | rg -v 'algorithms'
```

---

## Enforce Authorization Inside Server Actions

Next.js Server Actions are directly invokable HTTP endpoints. Page-level auth does not protect the action — every Server Action must verify identity independently.

### Correct Pattern

```ts
'use server';

export async function deleteUser(userId: string) {
  const session = await auth();
  if (!session?.user?.isAdmin) {
    throw new Error('unauthorized');
  }
  await db.user.delete({ where: { id: userId } });
}
```

### Why This Matters

Server Actions are HTTP POST endpoints invokable by anyone who constructs the request, bypassing page-level guards entirely.

**CVEs:** CVE-2025-55182 (React2Shell).

### Detection

```bash
rg -rn "'use server'" --type ts -l | xargs rg -L 'auth\(\)|getSession\(\)|getServerSession'
rg -A5 "'use server'" --type ts | rg 'delete|update|create|insert'
```

---

## Verify Session Integrity Before Trusting Identity

Session-derived claims must come from a verified server-side store, not client-modifiable cookies or unsigned tokens.

### Correct Pattern

**Django:**
```python
user = request.user  # Resolved from session middleware
if not user.is_authenticated:
    return HttpResponseForbidden()
```

**Express:**
```ts
app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { secure: true, httpOnly: true, sameSite: 'strict' },
}));
```

### Why This Matters

Impersonation endpoints without staff-role gates, session binding, or audit logging allow privilege escalation.

**CVEs:** ruby-saml CVE-2024-45409.

### Detection

```bash
rg -n 'login.as|impersonate|switch.user|view.as|act.as' --type py --type ts -i
rg -n 'cookie:.*secure.*false|httpOnly.*false|sameSite.*none' --type ts
```
