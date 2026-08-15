# AT Protocol API Reference

> **Scope**: Bluesky/AT Protocol XRPC endpoint patterns, data shapes, pagination, and rate limits for public read-only access
> **Version range**: AT Protocol v1 (lexicon `app.bsky.*`, `com.atproto.*`)
> **Generated**: 2026-04-16 — verify endpoint behavior against current Bluesky API docs

---

## Overview

The AT Protocol exposes XRPC (cross-resolver procedure call) endpoints under two base URLs:
- **Public app view** (`public.api.bsky.app`): No auth, read-only, Bluesky-specific lexicons
- **Personal data server** (`bsky.social`): Auth required, full read/write access

For read-only content retrieval, prefer the public app view — it bypasses authentication and is
more permissive with rate limits for unauthenticated clients.

---

## Endpoint Table

| Endpoint | Auth | Limit param | Returns |
|----------|------|-------------|---------|
| `app.bsky.feed.getAuthorFeed` | No | `limit` (1-100) | Posts by a specific actor |
| `app.bsky.feed.searchPosts` | No | `limit` (1-100) | Global full-text search results |
| `app.bsky.actor.getProfile` | No | — | Profile metadata for one handle/DID |
| `app.bsky.actor.searchActors` | No | `limit` (1-100) | Actor search by keyword |
| `app.bsky.feed.getPostThread` | No | `depth` (0-1000) | Thread containing a post |
| `com.atproto.identity.resolveHandle` | No | — | Resolve handle to DID |
| `app.bsky.feed.getTimeline` | **Yes** | `limit` (1-100) | Authenticated user's home timeline |

---

## Correct Patterns

### Building XRPC URLs

XRPC endpoints map directly to URL paths. Always URL-encode the `actor` param — handles
containing dots and colons will be misrouted without encoding.

```python
import urllib.request

BASE = "https://public.api.bsky.app/xrpc"

def build_url(lexicon: str, **params: str | int) -> str:
    """Build a public XRPC request URL."""
    encoded = "&".join(
        f"{k}={urllib.request.quote(str(v))}" for k, v in params.items() if v
    )
    return f"{BASE}/{lexicon}?{encoded}" if encoded else f"{BASE}/{lexicon}"

# Correct
url = build_url("app.bsky.feed.getAuthorFeed", actor="user.bsky.social", limit=30)
# -> https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=user.bsky.social&limit=30
```

**Why**: Handles like `did:plc:abc123` contain colons — without quoting, some HTTP clients
split on the colon and corrupt the parameter.

---

### Cursor-Based Pagination

The API uses opaque cursor strings, not page numbers. Store the cursor from each response
and pass it in the next request.

```python
def fetch_all_posts(handle: str, max_posts: int = 500) -> list[dict]:
    """Fetch posts across multiple pages using cursor pagination."""
    posts: list[dict] = []
    cursor = ""

    while len(posts) < max_posts:
        url = build_url(
            "app.bsky.feed.getAuthorFeed",
            actor=handle,
            limit=100,
            cursor=cursor,
        )
        data = fetch_json(url)
        batch = data.get("feed", [])
        if not batch:
            break  # No more posts

        posts.extend(batch)
        cursor = data.get("cursor", "")
        if not cursor:
            break  # Last page

    return posts[:max_posts]
```

**Why**: The cursor encodes server state. Reconstructing it from local data or using offset
integers will return wrong results or raise `InvalidRequest`.

---

### Feed Filter for Posts-Only

`getAuthorFeed` returns posts, replies, AND reposts by default. Use `filter` to narrow:

```python
url = build_url(
    "app.bsky.feed.getAuthorFeed",
    actor=handle,
    limit=50,
    filter="posts_no_replies",  # Only original posts
)
```

| Filter value | Returns |
|---|---|
| `posts_with_replies` | Posts + replies (default) |
| `posts_no_replies` | Only top-level posts, no replies |
| `posts_with_media` | Posts containing images/video |
| `posts_and_author_threads` | Posts + self-reply threads |

---

### AT URI to Web URL Conversion

AT URIs (`at://did:plc:xxx/app.bsky.feed.post/rkey`) must be rewritten to `bsky.app` URLs
for human-readable links. The rkey (record key) is the final path segment.

```python
def at_uri_to_url(uri: str, handle: str) -> str:
    """Convert AT URI to bsky.app web URL.

    at://did:plc:abc/app.bsky.feed.post/3kg7abc -> https://bsky.app/profile/handle/post/3kg7abc
    """
    parts = uri.split("/")
    if len(parts) < 5:
        return uri  # Malformed URI, return as-is
    rkey = parts[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"
```

**Why**: AT URIs use DIDs, not handles. Using the DID directly in the URL works but produces
opaque links — handle-based URLs are stable and human-readable.

---

### Global Full-Text Search vs Local Filter

The basic `search` command fetches all posts then filters locally. For keyword search
across a profile's full history or across all of Bluesky, use `app.bsky.feed.searchPosts`:

```python
url = build_url(
    "app.bsky.feed.searchPosts",
    q="search terms here",
    author="user.bsky.social",  # Scope to one author
    limit=25,
)
data = fetch_json(url)
posts = data.get("posts", [])  # Note: "posts" key, not "feed"
```

**Why**: Local filtering caps at the fetch limit (100 posts). `searchPosts` indexes the full
post history and returns ranked results. Use it when you need historical coverage beyond 100 posts.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---|---|---|
| `HTTP 400: InvalidRequest` | Bad param value or missing required param | Check `actor` is URL-encoded; verify param names match lexicon |
| `HTTP 400: UnknownActor` | Handle does not resolve or account is deleted | Verify handle spelling; try resolving with `resolveHandle` first |
| `HTTP 429: RateLimitExceeded` | Too many requests from this IP | Add `time.sleep(1)` between pages; stay under ~100 req/min |
| `HTTP 500: InternalServerError` | Transient server error | Retry after 5-15 seconds with exponential backoff |
| `JSONDecodeError` on response | Server returned HTML error page instead of JSON | Check `Content-Type` header before parsing |

---

## Data Shape: FeedViewPost

Each item in the `feed` array is a `FeedViewPost`. Key fields:

```python
# feed item structure (simplified)
{
    "post": {
        "uri": "at://did:plc:xxx/app.bsky.feed.post/rkey",
        "cid": "bafy...",
        "author": {
            "did": "did:plc:xxx",
            "handle": "user.bsky.social",
            "displayName": "User Name",
        },
        "record": {
            "$type": "app.bsky.feed.post",
            "text": "post content",
            "createdAt": "2024-01-15T12:00:00.000Z",
            "reply": {},   # Present if this is a reply
            "embed": {},   # Present if post has images/links/quotes
        },
        "likeCount": 42,
        "repostCount": 7,
        "replyCount": 3,
    },
    "reason": {  # Only present for reposts
        "$type": "app.bsky.feed.defs#reasonRepost",
        "by": {"handle": "reposter.bsky.social"},
    },
    "reply": {  # Only present for replies
        "root": {},
        "parent": {},
    }
}
```

---

## Detection Commands Reference

```bash
# Find calls that use numeric offset instead of cursor (wrong pagination)
grep -rn 'offset=' --include="*.py" | grep -i 'bsky\|bluesky\|atproto'

# Find hardcoded bsky.social base URL (should use public.api.bsky.app for public reads)
rg 'bsky\.social/xrpc' --type py

# Find feed parsing that skips the 'reason' key (misses repost detection)
grep -n 'feed_item\[.post.\]' --include="*.py" -r

# Find missing cursor handling in fetch loops
grep -B2 -A10 'getAuthorFeed' --include="*.py" -r | grep -c 'cursor'
```

---

## See Also

- `at-protocol-preferred-patterns.md` — Common mistakes using the AT Protocol API
- AT Protocol Lexicon browser: https://atproto.com/lexicons/app-bsky-feed
