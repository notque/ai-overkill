# GitHub REST API Patterns Reference

> **Scope**: Efficient API usage for code analysis — repos, trees, content, PR reviews, rate limiting. Not Actions/webhooks.
> **Version range**: GitHub REST API v3; GraphQL not covered

Rate limits: 60 req/hr unauth, 5000 req/hr auth. Patterns below minimize request count.

## Efficient Analysis Sequence

```
1. GET /users/{username}                    → 1 req — public_repos count
2. GET /users/{username}/repos?sort=stars   → 1-2 req — top repos by activity
3. GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1  → 1 req per repo — full file tree
4. GET /repos/{owner}/{repo}/contents/{path}  → 1 req per file — file content (base64)
5. GET /repos/{owner}/{repo}/pulls?state=all  → 1-2 req per repo — PR list
6. GET /repos/{owner}/{repo}/pulls/{pr}/reviews  → 1 req per PR — review comments
```

Total for 5 repos × 10 files × 3 PRs each: ~5 + 5 + 50 + 15 = **75 requests**. Well within authenticated limits.

---

## Pattern Table

| Endpoint | Optimal Use | Request Count | Notes |
|----------|-------------|---------------|-------|
| `/users/{username}/repos?sort=stars&per_page=5` | Get top 5 repos by stars | 1 | Add `&type=owner` to exclude forked repos |
| `/repos/{o}/{r}/git/trees/{sha}?recursive=1` | Full file tree in one call | 1 per repo | Truncated above ~100k files — check `truncated` field |
| `/repos/{o}/{r}/contents/{path}` | Single file content (base64) | 1 per file | `content` field is base64 — decode before parsing |
| `/repos/{o}/{r}/pulls?state=closed&per_page=10` | Most recent merged PRs | 1-2 per repo | Use `closed` for historical preference signals |
| `/repos/{o}/{r}/pulls/{n}/reviews` | Review comments per PR | 1 per PR | `body` field has the comment text |
| `/rate_limit` | Check remaining before large batches | 1 | Check before each analysis phase |

---

## Correct Patterns

### Rate Limit Check Before Batch Operations

Always check rate limits before starting a new analysis phase:

```python
def check_rate_limit(headers: dict) -> None:
    """Raise if fewer than 10 requests remaining."""
    remaining = int(headers.get("X-RateLimit-Remaining", 0))
    reset_time = int(headers.get("X-RateLimit-Reset", 0))

    if remaining < 10:
        wait_seconds = reset_time - time.time()
        raise RateLimitError(
            f"Rate limit nearly exhausted ({remaining} remaining). "
            f"Resets in {wait_seconds:.0f}s. "
            "Provide a GitHub token for 5000 req/hr: --token <your_token>"
        )
```

---

### Fetch File Tree (Recursive, One Request)

```python
def get_file_tree(owner: str, repo: str, branch: str = "HEAD") -> list[str]:
    """Return all file paths in a repo using one API call."""
    # First get the commit SHA for branch
    resp = github_get(f"/repos/{owner}/{repo}/commits/{branch}")
    tree_sha = resp["commit"]["tree"]["sha"]

    # Fetch entire tree recursively
    resp = github_get(f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1")

    if resp.get("truncated"):
        # Repo has >100k files — fall back to directory-by-directory
        return get_file_tree_paged(owner, repo, tree_sha)

    return [item["path"] for item in resp["tree"] if item["type"] == "blob"]
```

One request vs N+1 recursive directory calls. 500-file repo saves 30+ requests.

---

### Decode File Content

```python
import base64

def get_file_content(owner: str, repo: str, path: str) -> str:
    """Fetch and decode file content from GitHub API."""
    resp = github_get(f"/repos/{owner}/{repo}/contents/{path}")

    if resp.get("encoding") != "base64":
        raise ValueError(f"Unexpected encoding: {resp.get('encoding')}")

    # Content has newlines inserted by GitHub — strip before decoding
    return base64.b64decode(resp["content"].replace("\n", "")).decode("utf-8", errors="replace")
```

GitHub `content` includes `\n` that must be stripped before base64 decode.

---

### Prioritize Top Repos

```python
def get_analysis_repos(username: str, max_repos: int = 5) -> list[dict]:
    """Return repos sorted by relevance: stars + recent activity, excluding forks."""
    repos = github_get(f"/users/{username}/repos?sort=pushed&per_page=20&type=owner")

    # Sort by stars (strongest signal), filter forks (project-specific style)
    owned = [r for r in repos if not r["fork"]]
    owned.sort(key=lambda r: r["stargazers_count"], reverse=True)

    return owned[:max_repos]
```

Forks contain upstream style, not user's. Star-sorted owned repos = most polished work.

---

## Pattern Catalog

### Use Recursive Tree Endpoint for File Listing
**Detection** (in your own code pattern):
```bash
grep -rn 'GET /repos.*contents' scripts/ | grep -v 'tree'
```

**Signal**:
```python
# Expensive: 1 request per directory level, recursive
def list_files(owner, repo, path=""):
    items = github_get(f"/repos/{owner}/{repo}/contents/{path}")
    for item in items:
        if item["type"] == "dir":
            yield from list_files(owner, repo, item["path"])  # N+1 requests!
        else:
            yield item["path"]
```

**Why**: 200-file repo = 21 requests. Recursive tree = 1.

**Fix**: `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`

---

### Handle Pagination for All List Endpoints
**Detection**:
```bash
grep -rn 'per_page' scripts/ | grep -v 'pagination\|next\|link'
```

**Signal**:
```python
repos = github_get(f"/users/{username}/repos?per_page=100")
# Assumes all repos fit in one page — fails for users with 100+ repos
```

**Why**: Max 100 items/page. 100+ repos = silently incomplete.

**Fix**:
```python
def paginate(url: str) -> list:
    results = []
    while url:
        resp = requests.get(url, headers=auth_headers)
        results.extend(resp.json())
        # GitHub uses Link header for pagination
        url = resp.links.get("next", {}).get("url")
    return results
```

---

### Authenticate All API Requests
**Detection**:
```bash
grep -rn 'github_get\|requests.get' scripts/ | grep -v 'Authorization\|token'
```

**Signal**:
```python
headers = {"Accept": "application/vnd.github.v3+json"}
# Missing: Authorization header — capped at 60 req/hr
```

**Why**: 60 req/hr exhausted by 2-3 repos. Analysis needs 50-200 minimum.

**Fix**: Accept `--token` flag; check `GITHUB_TOKEN` env var:
```python
import os
token = args.token or os.environ.get("GITHUB_TOKEN")
headers = {
    "Accept": "application/vnd.github.v3+json",
    **({"Authorization": f"token {token}"} if token else {})
}
```

---

## Error-Fix Mappings

| Error Message / HTTP Status | Root Cause | Fix |
|----------------------------|------------|-----|
| `403 API rate limit exceeded` | Rate limit hit (60/hr unauth, 5000/hr auth) | Provide `--token` or wait for reset (`X-RateLimit-Reset` header) |
| `404 Not Found` on `/users/{u}` | Invalid username | Verify spelling; user may have changed username |
| `404 Not Found` on `/repos/{o}/{r}/contents/{p}` | File doesn't exist on default branch | Check branch name; file may have been deleted |
| `422 Repository is empty` | New repo with no commits | Skip repo; no content to analyze |
| `binascii.Error: Invalid base64` | Not stripping `\n` from content field before decode | `base64.b64decode(content.replace("\n", ""))` |
| `403 Resource not accessible by integration` | Requesting private data without correct token scope | Only request public endpoints; verify token scopes |
| `451 Repository access blocked` | DMCA or legal takedown | Skip repo; log and continue |

---

## Detection Commands Reference

```bash
# Check current rate limit status
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit | jq '.rate'

# Verify a username exists
curl -s "https://api.github.com/users/{username}" | jq '.login,.public_repos'

# Get top 5 repos by stars
curl -s "https://api.github.com/users/{username}/repos?sort=stars&per_page=5&type=owner" \
  | jq '.[].name'

# Get file tree for a repo (requires auth for large repos)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1" \
  | jq '.tree[].path' | grep -E '\.(go|py|ts|js)$' | head -20
```

---

## See Also

- `rule-categories.md` — taxonomy of extractable rule types with confidence scoring
- `confidence-scoring.md` — detailed scoring algorithm and edge cases
