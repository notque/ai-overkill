# AT Protocol Patterns to Detect and Fix

> **Scope**: Common mistakes when reading Bluesky/AT Protocol data with Python and the public XRPC API
> **Version range**: AT Protocol v1, all versions
> **Generated**: 2026-04-16

---

## Overview

The AT Protocol has several non-obvious gotchas: opaque cursor pagination (not offset-based),
a `feed` key in author feeds vs `posts` in search results, DID vs handle disambiguation, and
feed items that wrap posts inside `post` and `reason` sub-keys. Missing any of these silently
returns incomplete or wrong data.

---

## Pattern Catalog

### Using bsky.social for Public Reads

**Detection**:
```bash
rg 'bsky\.social/xrpc' --type py
grep -rn 'https://bsky.social/xrpc' --include="*.py"
```

**What it looks like**:
```python
# Wrong — bsky.social requires auth for most endpoints
url = f"https://bsky.social/xrpc/app.bsky.feed.getAuthorFeed?actor={handle}"
```

**Why wrong**: `bsky.social` is a PDS (Personal Data Server) that requires JWT authentication
for most endpoints. Unauthenticated requests return `HTTP 401: AuthRequired`. The public app
view (`public.api.bsky.app`) is purpose-built for unauthenticated reads.

**Fix**:
```python
# Correct — public app view, no auth needed
url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={handle}"
```

---

### Offset-Based Pagination Instead of Cursor

**Detection**:
```bash
grep -rn '\boffset\b' --include="*.py" | grep -i 'bsky\|atproto\|feed'
grep -rn 'page\s*\*\s*limit\|skip=' --include="*.py"
```

**What it looks like**:
```python
# Wrong — AT Protocol has no offset parameter
for page in range(10):
    url = f"{BASE}/app.bsky.feed.getAuthorFeed?actor={handle}&limit=100&offset={page * 100}"
    data = fetch_json(url)
```

**Why wrong**: The AT Protocol lexicon has no `offset` parameter — the API ignores it silently.
All pagination is cursor-based. Passing `offset` fetches the same first page on every iteration.

**Fix**:
```python
# Correct — use cursor from each response
cursor = ""
while True:
    params = {"actor": handle, "limit": 100}
    if cursor:
        params["cursor"] = cursor
    data = fetch_json(build_url("app.bsky.feed.getAuthorFeed", **params))
    posts = data.get("feed", [])
    if not posts:
        break
    cursor = data.get("cursor", "")
    if not cursor:
        break  # Final page
```

---

### Using "posts" Key on Author Feed Response

**Detection**:
```bash
grep -rn '\.get("posts"' --include="*.py" | grep -i 'author\|feed'
grep -rn '\["posts"\]' --include="*.py"
```

**What it looks like**:
```python
# Wrong — getAuthorFeed uses "feed" key, not "posts"
data = fetch_json(url)
posts = data["posts"]  # KeyError or empty list
```

**Why wrong**: `getAuthorFeed` returns `{"feed": [...], "cursor": "..."}`. The `posts` key
is only used by `searchPosts`. Confusing the two silently returns nothing.

**Fix**:
```python
# getAuthorFeed
data = fetch_json(url)
items = data.get("feed", [])   # Each item is a FeedViewPost wrapper

# searchPosts
data = fetch_json(search_url)
items = data.get("posts", [])  # Each item is a PostView directly
```

---

### Accessing post.text Directly on a Feed Item

**Detection**:
```bash
grep -rn 'item\["text"\]\|item\.get("text"' --include="*.py"
grep -rn 'feed_item\["text"\]' --include="*.py"
```

**What it looks like**:
```python
# Wrong — feed items wrap the post data, text is nested
for item in data["feed"]:
    text = item["text"]  # KeyError — text lives at item["post"]["record"]["text"]
```

**Why wrong**: `getAuthorFeed` returns `FeedViewPost` objects, not raw posts. The actual post
record is nested at `item["post"]["record"]`. The outer `item` holds `post`, `reason`, and
`reply` sub-keys.

**Fix**:
```python
for item in data.get("feed", []):
    post_data = item.get("post", {})
    record = post_data.get("record", {})
    text = record.get("text", "")
    author = post_data.get("author", {}).get("handle", "")
    like_count = post_data.get("likeCount", 0)
```

---

### Missing Repost Detection

**Detection**:
```bash
grep -rn '"reason"' --include="*.py" | grep -v '#\|reason='
# Should find code handling the reason key; absence means reposts are silently misattributed
```

**What it looks like**:
```python
# Wrong — treats reposts as original posts by the feed owner
for item in data["feed"]:
    handle = item["post"]["author"]["handle"]  # This is the ORIGINAL author, not reposter
    print(f"@{handle}: {item['post']['record']['text']}")
```

**Why wrong**: When a user reposts, `item["reason"]["$type"]` is
`"app.bsky.feed.defs#reasonRepost"` and `item["reason"]["by"]` holds the reposter's info.
The `item["post"]["author"]` is always the original author. Without checking `reason`, every
repost is presented as if the profile owner wrote it.

**Fix**:
```python
for item in data.get("feed", []):
    reason = item.get("reason", {})
    is_repost = reason.get("$type", "") == "app.bsky.feed.defs#reasonRepost"
    reposted_by = reason.get("by", {}).get("handle", "") if is_repost else ""

    post = item.get("post", {})
    author = post.get("author", {}).get("handle", "")
    text = post.get("record", {}).get("text", "")

    if is_repost:
        print(f"[repost by @{reposted_by}] @{author}: {text}")
    else:
        print(f"@{author}: {text}")
```

---

### Not URL-Encoding Handle Parameter

**Detection**:
```bash
grep -rn 'actor={handle}\|actor={actor}\|f".*actor=' --include="*.py"
# Check if urllib.parse.quote or urllib.request.quote is missing around the handle
rg 'actor=\{' --type py
```

**What it looks like**:
```python
# Wrong — handle not encoded, will break for DID-based actors
handle = "did:plc:abc123def456"
url = f"{BASE}/app.bsky.feed.getAuthorFeed?actor={handle}&limit=30"
# -> ...?actor=did:plc:abc123def456&limit=30
# Colon in DID may be misinterpreted by proxies/CDNs
```

**Why wrong**: While most handles (`user.bsky.social`) survive unencoded, DID identifiers
(`did:plc:...`, `did:web:...`) contain colons that some HTTP proxies interpret as port
separators, producing corrupted requests. Always encode `actor` consistently.

**Fix**:
```python
import urllib.request

handle = "did:plc:abc123def456"
encoded = urllib.request.quote(handle, safe="")
url = f"{BASE}/app.bsky.feed.getAuthorFeed?actor={encoded}&limit=30"
```

---

### Ignoring Timeout on urllib.request.urlopen

**Detection**:
```bash
grep -rn 'urlopen(' --include="*.py" | grep -v 'timeout'
```

**What it looks like**:
```python
# Wrong — no timeout, hangs indefinitely on network stall
with urllib.request.urlopen(req) as resp:
    return json.loads(resp.read())
```

**Why wrong**: The Bluesky public API can stall under load. Without a timeout, the script
hangs until the OS TCP timeout (often 2+ minutes), making the tool appear frozen.

**Fix**:
```python
# Correct — 15 second timeout matches expected API response time
with urllib.request.urlopen(req, timeout=15) as resp:
    return json.loads(resp.read())
```

**Version note**: `timeout` parameter available in `urllib.request.urlopen` since Python 2.6.
No version concern for Python 3.x.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|---|---|---|
| `KeyError: 'feed'` | Using `data["feed"]` without `.get()`, or response is an error dict | Use `data.get("feed", [])` and check for `data.get("error")` first |
| `KeyError: 'text'` | Accessing text at wrong nesting level | Navigate `item["post"]["record"]["text"]` not `item["text"]` |
| `HTTP 401: AuthRequired` | Using `bsky.social` base URL without auth | Switch to `public.api.bsky.app` |
| `TimeoutError` | No timeout on `urlopen` | Add `timeout=15` to `urlopen` call |
| `UnicodeDecodeError` | Emoji/non-ASCII in post text decoded with wrong charset | Use `resp.read().decode("utf-8")`, not `"ascii"` |
| Infinite loop on pagination | Cursor not advancing (always passing empty cursor) | Ensure cursor is extracted from `data.get("cursor", "")` and passed to next request |

---

## Detection Commands Reference

```bash
# Wrong base URL
rg 'bsky\.social/xrpc' --type py

# Offset-based pagination
grep -rn '\boffset\b' --include="*.py" | grep -i 'bsky\|atproto'

# Wrong response key for author feed
grep -rn '\.get("posts"' --include="*.py" | grep -i 'author\|feed'

# Direct text access on feed item (wrong nesting)
grep -rn 'item\["text"\]\|item\.get("text"' --include="*.py"

# Missing repost detection
grep -rn 'reason' --include="*.py"  # Expect at least one hit per fetch function

# Unencoded actor parameter
rg 'actor=\{(?!.*quote)' --type py

# urlopen without timeout
grep -rn 'urlopen(' --include="*.py" | grep -v 'timeout'
```

---

## See Also

- `at-protocol-api.md` — Endpoint reference, pagination patterns, data shapes
