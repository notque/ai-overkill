# WordPress Uploader Skill

## Overview

This skill provides WordPress REST API integration for posts and media uploads using deterministic Python scripts. **LJMs orchestrate. Scripts execute.** All WordPress operations go through the three provided Python scripts (`wordpress-upload.py`, `wordpress-media-upload.py`, `wordpress-edit-post.py`), never via curl or raw API calls. This approach ensures credential security, deterministic behavior, and proper markdown-to-Gutenberg conversion.

**Scope**: Create new posts, upload media, edit existing posts, manage featured images, handle categories/tags. Does not write article prose (use voice-writer) or edit prose style (use the private de-AI editor skill). Requires HTTPS-only connections and Application Password authentication configured in `~/.env`.

---

## Instructions

### Phase 1: VALIDATE ENVIRONMENT

**Goal**: Confirm credentials and target file exist before any API call.

Before executing any script, always complete these validation steps.

**Step 1: Check credentials**

Verify `~/.env` contains all required WordPress variables:

```bash
python3 -c "
import os
from pathlib import Path
env = Path(os.path.expanduser('~/.env')).read_text()
required = ['WORDPRESS_SITE', 'WORDPRESS_USER', 'WORDPRESS_APP_PASSWORD']
missing = [v for v in required if v + '=' not in env]
print('OK' if not missing else f'MISSING: {missing}')
"
```

This check is mandatory — the most common upload failures stem from missing or misconfigured credentials. Never assume credentials are fine. Never log, display, or echo the Application Password value.

**Step 2: Verify source file**

If uploading content, confirm the markdown file exists and is non-empty using `ls -la <path>`. Check for typos in paths and verify file is not zero bytes.

**HTTPS Requirement**: Confirm `WORDPRESS_SITE` in `~/.env` uses HTTPS, not HTTP. The REST API will reject non-HTTPS connections.

**Gate**: All environment variables present AND non-empty, source file exists and has content, site URL is HTTPS. Proceed only when gate passes.

### Phase 2: UPLOAD / EXECUTE

**Goal**: Run the appropriate script for the requested operation.

Always use `--human` flag for all script invocations to get human-readable output. Always create posts as drafts unless explicitly told to publish. If publishing, ask for user confirmation before setting status to publish (confirm-before-publish default behavior).

**For new posts:**

```bash
python3 ~/.claude/skills/content/publish/scripts/wordpress-upload.py \
  --file <path-to-markdown> \
  --title "Post Title" \
  --human
```

The `--title` flag is optional. If omitted, the script extracts the title from markdown H1. If both `--title` AND H1 exist, this creates a duplicate title rendering in WordPress (failure mode). Use one or the other, not both.

**Auto-create missing categories (opt-in):**

By default, frontmatter or `--category` names that don't exist on the target site are skipped with a warning, and the post lands without them. Pass `--create-missing-categories` to create them on the fly via `POST /wp/v2/categories`:

```bash
python3 ~/.claude/skills/content/publish/scripts/wordpress-upload.py \
  --file <path-to-markdown> \
  --create-missing-categories \
  --human
```

When the flag is on, every missing category triggers `Created category '<name>' (id <new-id>)` in `--human` output, the new ID is cached for the rest of the run, and the new ID is attached to the post. On permission denied or any 4xx/5xx from the categories endpoint, the script logs a warning and falls back to the existing skip behavior — the upload never crashes.

Auto-create only applies at upload time. `wordpress-edit-post.py` accepts category IDs (not names) and does not perform name resolution or auto-create; create categories at upload time, or pre-create them via the REST API, before editing.

**For media uploads:**

```bash
python3 ~/.claude/skills/content/publish/scripts/wordpress-media-upload.py \
  --file <path-to-image> \
  --alt "Descriptive alt text" \
  --human
```

Always provide descriptive alt text for accessibility.

**For editing existing posts:**

```bash
python3 ~/.claude/skills/content/publish/scripts/wordpress-edit-post.py \
  --id <post-id> \
  --human \
  [--title "New Title"] \
  [--content-file updated.md] \
  [--featured-image <media-id>] \
  [--status draft|publish|pending|private]
```

**For inspecting a post before editing:**

```bash
python3 ~/.claude/skills/content/publish/scripts/wordpress-edit-post.py \
  --id <post-id> \
  --get \
  --human
```

Use `--get` to retrieve post details for review before making edits.

**Always execute scripts through these deterministic Python wrappers.** Never use curl or raw API calls. The scripts handle credential injection, error formatting, and markdown-to-Gutenberg conversion that manual requests would lose.

**Display complete script output**. Never summarize, truncate, or hide results. The full JSON response contains post IDs, URLs, and validation details the user needs.

**Gate**: Script returns `"status": "success"` with a valid post_id or media_id. Proceed only when gate passes.

### Phase 3: VERIFY

**Goal**: Confirm the operation succeeded and report results to the user.

**Step 1**: Parse script output for post_id, post_url, or media_id. Verify the returned ID is numeric and non-zero.

**Step 2**: Report the complete result with all relevant URLs. Include:
  - Post URL (for posts)
  - WordPress edit URL (`https://<site>/wp-admin/post.php?post=<id>&action=edit`)
  - Media URL (for media uploads)

**Step 3**: Post-upload verification. Confirm success by checking the returned URL and post ID — these prove the script succeeded. If this was a publish operation (not draft), verify the post is accessible at its public URL.

**Step 4**: Multi-step workflow confirmation. If part of a workflow (e.g., image upload + post creation + featured image attachment), confirm ALL steps completed. If any step failed, the workflow is incomplete.

**No partial success**. If a multi-step operation fails at step N, report which steps succeeded and which failed. Do not claim completion.

**Gate**: User has received confirmation with URLs and IDs, all steps in workflow completed (or explicit failure report). Operation is complete.

### Phase 3.5: SEARCH MEDIA LIBRARY BEFORE UPLOADING (Optional)

**Goal**: Reuse imagery the site already hosts before uploading new media.

Before calling `wordpress-media-upload.py` for a new image, search the existing library by keyword. If a match exists, embed its URL inline in the markdown body or pass its ID to `wordpress-edit-post.py --featured-image <id>`. This saves CDN bytes, keeps the library tidy, and reuses already-licensed/already-cleared imagery.

**Workflow:**

1. Query `GET /wp/v2/media?search=<KEYWORD>&per_page=N&_fields=id,source_url,title,alt_text,date` with Application-Password basic auth.
2. Pick existing media items (by `id` or `source_url`) that match the article subject. Prefer recent results when ranking ties.
3. Embed the chosen `source_url` inline in the markdown body, or pass the `id` to `wordpress-edit-post.py --featured-image <id>` for the hero image.
4. Skip the new upload entirely when the library already covers the topic.

**Stdlib search snippet** (no third-party deps; uses the same `~/.env` credentials as the upload scripts):

```python
import base64
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


def load_env(path: Path = Path.home() / ".env") -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def search_media(keyword: str, per_page: int = 10) -> list[dict]:
    env = load_env()
    site = os.environ.get("WORDPRESS_SITE", env.get("WORDPRESS_SITE", "")).rstrip("/")
    user = os.environ.get("WORDPRESS_USER", env.get("WORDPRESS_USER", ""))
    pwd = os.environ.get("WORDPRESS_APP_PASSWORD", env.get("WORDPRESS_APP_PASSWORD", ""))
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()

    qs = urllib.parse.urlencode(
        {
            "search": keyword,
            "per_page": per_page,
            "_fields": "id,source_url,title,alt_text,date",
        }
    )
    req = urllib.request.Request(
        f"{site}/wp-json/wp/v2/media?{qs}",
        headers={"Authorization": f"Basic {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


if __name__ == "__main__":
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else "<KEYWORD>"
    for item in search_media(keyword):
        title = item.get("title", {}).get("rendered", "") if isinstance(item.get("title"), dict) else item.get("title", "")
        print(f"{item['id']}\t{title}\t{item['source_url']}")
```

Save as `wp_media_search.py` and run `python3 wp_media_search.py "<KEYWORD>"` to print `id<TAB>title<TAB>source_url` for the top matches. Pipe through `head` or `grep` to narrow further.

**When to skip the search**: brand-new subjects with zero prior coverage, or imagery that must be unique to this post (custom hero art, screenshots of a specific UI state). Otherwise, search first.

### Phase 4: POST-UPLOAD WORKFLOWS (Optional)

**Goal**: Handle multi-step workflows that combine operations (featured image, batch upload, draft cleanup). See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-workflows.md` for full command blocks.

**Always delete old drafts after uploading a replacement.** Multiple drafts of the same article accumulate in WordPress and cause confusion. This is mandatory cleanup, not optional.

---

## Script Reference

See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-script-reference.md` for full flag tables for `wordpress-upload.py`, `wordpress-media-upload.py`, and `wordpress-edit-post.py`, including category/tag resolution and YAML frontmatter behavior.

---

## Content Formatting

**Keep title and author out of the article body.** WordPress manages these as metadata, and duplicating them in content creates inconsistency when editing in wp-admin.

See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-content-formatting.md` for the full Gutenberg block type table, code block syntax, button links, and `--validate` output format.

---

## Error Handling

See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-error-handling.md` for common errors: missing credentials, 401 Unauthorized, 403 Forbidden, file not found.

## References

**Script Files**:
- `~/.claude/skills/content/publish/scripts/wordpress-upload.py`: Create new posts from markdown
- `~/.claude/skills/content/publish/scripts/wordpress-media-upload.py`: Upload images/media to library
- `~/.claude/skills/content/publish/scripts/wordpress-edit-post.py`: Edit existing posts (title, content, status, featured image)

**Environment Configuration**:
- File: `~/.env`
- Required variables: `WORDPRESS_SITE`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD`
- Must use HTTPS for the site URL

**Related Skills**:
- `voice-writer`: Use for writing articles (not uploading them)
- private de-AI editor skill: use for editing prose style (not publishing to WordPress)
- `wordpress-live-validation`: Post-upload browser-based live validation
