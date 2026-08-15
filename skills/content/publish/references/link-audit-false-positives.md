# Known False Positives

Sites that block automated link validation but work fine in browsers.

---

## Why This Happens

Many sites actively block or rate-limit automated requests to:
- Prevent scraping
- Reduce server load
- Block spam bots
- Protect user data

This means link validation tools often report "broken" links that actually work.

---

## Known Blocking Sites

### Social Media Platforms

| Domain | Response | Notes |
|--------|----------|-------|
| `linkedin.com` | 403, 999 | Aggressive bot blocking |
| `twitter.com` | 400, 403 | Rate limiting + bot detection |
| `x.com` | 400, 403 | Same as twitter.com |
| `facebook.com` | 403 | Requires authentication |
| `instagram.com` | 403 | Requires authentication |
| `tiktok.com` | 403 | Bot protection |
| `threads.net` | 403 | Bot protection |

### Content Platforms

| Domain | Response | Notes |
|--------|----------|-------|
| `medium.com` | 403, 429 | Intermittent blocking |
| `substack.com` | Sometimes blocks | Varies by newsletter |
| `dev.to` | Usually works | Occasional rate limiting |
| `hashnode.com` | Usually works | Occasional rate limiting |

### Code Hosting

| Domain | Response | Notes |
|--------|----------|-------|
| `github.com` | Usually works | Rate limited, may 429 |
| `gitlab.com` | Usually works | Rate limited |
| `bitbucket.org` | Usually works | Rate limited |
| `gist.github.com` | Usually works | Same as github.com |

### Documentation Sites

| Domain | Response | Notes |
|--------|----------|-------|
| `docs.google.com` | 403 | Requires authentication |
| `notion.so` | 403 | Requires authentication |
| `confluence.atlassian.com` | 403 | Requires authentication |

### News Sites

| Domain | Response | Notes |
|--------|----------|-------|
| `wsj.com` | Paywall redirect | Not technically broken |
| `nytimes.com` | Paywall redirect | Not technically broken |
| `ft.com` | Paywall redirect | Not technically broken |

---

## How the Scanner Handles These

The link scanner maintains an internal list of known false-positive domains. When encountering these domains:

1. **Skips HTTP validation** for known blockers
2. **Reports as "blocked (expected)"** not broken
3. **Does not count against broken link total**

---

## Updating the False Positive List

To add a new domain to the scanner's false positive list, edit:

```python
# In scripts/link_scanner.py (not yet implemented)
# When implemented, false positives would be configured as:

FALSE_POSITIVE_DOMAINS = {
    'linkedin.com': 'Returns 403/999 for bots',
    'twitter.com': 'Returns 400 for bots',
    # Add new entries here:
    'example.com': 'Blocks automated requests',
}
```

---

## Manual Verification

For sites that report as blocked, manually verify in browser:

1. **Copy the URL** from the audit report
2. **Open in incognito/private window** (tests without login)
3. **Check if page loads** with actual content
4. If loads: Confirmed false positive, ignore
5. If 404/error: Actually broken, needs fix

---

## Common False Positive Patterns

### Pattern 1: Cloudflare Protection

Sites using Cloudflare bot protection often return:
- 403 Forbidden
- Challenge page (captcha)
- JavaScript-required page

**Indicator**: Response includes "cf-" headers

### Pattern 2: Rate Limiting

Multiple requests to same domain trigger:
- 429 Too Many Requests
- Temporary blocks

**Solution**: Scanner caches results to avoid duplicate requests

### Pattern 3: User-Agent Blocking

Sites block requests with:
- Generic User-Agents
- Known crawler User-Agents
- Empty User-Agents

**Solution**: Scanner uses browser-like User-Agent

### Pattern 4: Referrer Requirements

Some sites require:
- Specific referrer header
- Same-origin referrer
- No referrer at all

---

## When to Investigate

Consider manual investigation when:

1. **Many links to same domain fail** - May need to add to false positives
2. **New domain blocks requests** - Verify and add to list
3. **Previously working site now fails** - May have changed protection
4. **Important external resource** - Worth verifying manually

---

## Related

- `link-graph-metrics.md` - Understanding link graph analysis
- `fix-strategies.md` - How to address link issues
