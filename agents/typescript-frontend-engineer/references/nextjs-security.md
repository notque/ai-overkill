# Next.js / React Secure Implementation Patterns

Version-pinned Next.js security failures and the detection commands for each. Load when the task involves auth, XSS, CSRF, SSRF, Server Actions, middleware, or the image optimizer.

Generic advice (escape output, validate input, use HTTPS) is assumed known. What follows is the framework-specific part that gets missed.

---

## Server Actions Are Public RPC Endpoints

Every Server Action must verify the session independently. Page-level auth does not extend to Server Actions defined within that page.

An attacker who knows the action's exported name can invoke it with any arguments without ever visiting the page. Page-level `redirect('/login')` does nothing for the action. Inline actions that capture page `params` in their closure look scoped, but the captured values are serialized into action metadata and are attacker-controllable — **re-verify ownership inside the action**. CVE-2025-55182 documents this class.

Order: validate input, then authenticate, then authorize, then mutate.

```bash
# Server Actions with no session check
rg -A5 "'use server'" . | rg -v 'auth\(\)|getSession\(\)|getServerSession'
```

## Middleware Is Not a Security Boundary

CVE-2025-29927 allowed bypassing Next.js middleware entirely by sending the `x-middleware-subrequest` header. Fixed in Next.js 15.2.3, but the lesson stands: middleware is a single enforcement surface. Route handlers and Server Actions are independent surfaces that need their own checks.

Middleware matcher patterns also silently miss paths: `/admin` vs `/admin/`, and `/api/admin/*` is not covered by `/admin/:path*`.

```bash
# Route handlers with no auth
find . -path '*/app/api/*/route.ts' -o -path '*/app/api/*/route.tsx' | xargs rg -L 'auth\(\)|getSession'
jq '.dependencies.next' package.json   # confirm >= 15.2.3
```

## The Image Optimizer Is an Open Proxy by Default

`remotePatterns: [{ hostname: '**' }]` turns `/_next/image` into an SSRF primitive. `/_next/image?url=http://169.254.169.254/latest/meta-data/` exfiltrates cloud instance metadata through the image endpoint (GHSA-rvpw-p7vw-wj3m). Enumerate allowed hostnames explicitly.

```bash
rg -n "hostname.*\*\*" next.config.*
```

## RSC Props Are Wire Format

React Server Components serialize *all* props into the HTML response. Passing a full database row ships password hashes, API tokens, internal flags, and every column added by future migrations — visible in page source and the network response even when the UI never renders them. Select explicit fields into a DTO at the query.

```bash
# Queries returning whole rows
rg -n 'findUnique\(|findFirst\(|findMany\(' . --type ts --type tsx | rg -v 'select'
```
