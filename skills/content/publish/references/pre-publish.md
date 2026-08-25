# Pre-Publish Checker Skill

## Overview

This skill performs rigorous pre-publication validation for Hugo blog posts using a **Sequential Validation** workflow: assess structure, validate fields, check assets, and report results. It embeds Hugo-specific rules and SEO best practices to catch publication blockers before they reach production.

The skill is **non-destructive** (modifies files only with explicit user request), **complete** (shows all validation results—always shows complete output), and **severity-aware** (distinguishes BLOCKER from SUGGESTION throughout the workflow).

---

## Instructions

### Usage

```
/pre-publish [path-to-post]
/pre-publish content/posts/2025-01-my-post.md
/pre-publish --check-external content/posts/2025-01-my-post.md
```

If no path provided, prompt user to specify the post file.

### Phase 1: ASSESS

**Goal**: Parse post structure and extract all validatable elements.

**Step 1: Read the target markdown file**

Verify the file exists. If not, list available posts and ask user to confirm.

**Step 2: Extract front matter**

Hugo supports both TOML and YAML front matter. Detect delimiter type:
- TOML: enclosed in `+++` delimiters
- YAML: enclosed in `---` delimiters

Parse all fields into structured data.

**Step 3: Extract body content**

Everything after front matter closing delimiter. Inventory:
- Word count (prose only, exclude code fences)
- Header hierarchy (H2, H3 levels)
- Internal links, external links, image references
- TODO/FIXME markers and placeholder patterns

**Gate**: File parsed successfully. Front matter extracted. Body content inventoried. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Run all validation checks with correct severity classification.

**Step 1: Front matter validation**

| Field | Requirement | Severity | Reasoning |
|-------|-------------|----------|-----------|
| title | Present, non-empty | BLOCKER | Hugo build fails without title |
| date | Present, valid format | BLOCKER | Publishing requires valid timestamp |
| draft | Must be `false` | BLOCKER | Hugo excludes draft posts; this is a non-negotiable check |
| description | Present, 150-160 chars | SUGGESTION | SEO optimization; user may omit intentionally |
| tags | Present, 3-5 items | SUGGESTION | Recommendation for taxonomy consistency; not required |
| categories | Present, 1-2 items | SUGGESTION | Recommendation for site organization; not required |

Always validate draft field first. Treat as highest-priority blocker—draft posts are excluded from production builds entirely.

**Step 2: SEO validation**

| Check | Optimal Range | Severity | Reasoning |
|-------|---------------|----------|-----------|
| Title length | 50-60 characters | SUGGESTION | Search engine display optimization |
| Description length | 150-160 characters | SUGGESTION | Meta description window sizing |
| Slug format | URL-friendly, no special chars | SUGGESTION | Internal naming convention |

Derive slug from filename: `2025-01-my-post.md` becomes `my-post`.

**Step 3: Content quality validation**

| Check | Requirement | Severity | Reasoning |
|-------|-------------|----------|-----------|
| Word count | Minimum 500 words | SUGGESTION | Depth indicator; user retains discretion |
| Reading time | Calculate at 200 WPM | INFO | Report only, not a blocker |
| Header structure | H2/H3 present, logical hierarchy | SUGGESTION | Readability and scannability |
| Opening paragraph | No preamble phrases | SUGGESTION | Content quality; user may override |

Preamble detection phrases: "In this post, I will...", "Today I'm going to...", "Let me explain...", "Welcome to...", "First of all...", "Before we begin..."

**Step 4: Link validation**

- **Internal links**: Pattern `](/posts/...)` or `](/images/...)`. Verify target exists. Severity: BLOCKER if missing (broken links prevent navigation).
- **External links**: Pattern `](https://...)`. Skip by default. Severity: WARNING if unreachable (when enabled). Rationale: External validation adds network latency and rate-limiting concerns; skip unless user opts in with `--check-external`.
- **Image links**: Pattern `![alt](path)` or Hugo shortcodes. Verify file exists in static/. Severity: BLOCKER if missing (reader sees broken image).

**Step 5: Image validation**

| Check | Requirement | Severity | Reasoning |
|-------|-------------|----------|-----------|
| Alt text | All images must have non-empty alt | SUGGESTION | Accessibility best practice |
| File existence | All referenced images exist in static/ | BLOCKER | Missing images break page rendering |
| Path format | Correct Hugo static path convention | SUGGESTION | Consistency with site standards |

Hugo image path patterns: `/images/filename.png` (absolute from static/), `images/filename.png` (relative), `{{< figure src="..." >}}` (shortcode).

**Step 6: Anti-AI pattern validation**

| Check | Requirement | Severity | Reasoning |
|-------|-------------|----------|-----------|
| AI pattern scan | Run anti-AI editor skill scan | BLOCKER | AI-sounding content damages voice authenticity and reader trust |

For the installed private de-AI editor, use the exact `Call the Skill tool with \`skill-name\`.` contract with its indexed name. It is not a script and is deployed to `~/.claude/skills/` from `~/private-skills` when installed. Apply its ASSESS phase. At minimum, load its detection-patterns reference and scan for all 14 detection categories. A severity score above 15 is a BLOCKER. Score 6-15 is a WARNING with specific line numbers and suggested fixes. Score 0-5 is a PASS.

This check exists because voice validation and joy-check do not catch AI writing patterns. Content can pass both gates while containing emotional flatlines ("This is the part I find most interesting"), false concessions, synonym cycling, and other patterns that signal AI-generated text. The anti-AI editor catches these through regex patterns and contextual analysis.

**Step 7: Draft status validation**

| Check | Requirement | Severity | Reasoning |
|-------|-------------|----------|-----------|
| draft field | Must be `false` | BLOCKER | Hugo build filter; non-negotiable |
| TODO comments | None present | WARNING | Development artifact—likely unintentional in published post |
| FIXME comments | None present | WARNING | Development artifact—likely unintentional in published post |
| Placeholder text | None present | BLOCKER | Content is incomplete if placeholders remain |

Placeholder patterns: `[insert X here]`, `[TBD]`, `[TODO]`, `XXX`, `PLACEHOLDER`, `Lorem ipsum`.

**Gate**: All validation checks executed. Each check produced a status (PASS, FAIL, WARN, SKIP, INFO). Proceed only when gate passes.

### Phase 3: SUGGEST TAXONOMY

**Goal**: Provide actionable taxonomy suggestions when tags or categories are missing.

**Step 1: Build taxonomy index**

Read existing posts to collect all tags and categories currently in use. Rationale: Always read existing posts before suggesting. Inventing generic tags like "programming" or "tech" without checking the site creates inconsistent taxonomy and fragments content organization.

**Step 2: Analyze content**

Match current post content against existing taxonomy terms. Prefer established terms over inventing new ones.

**Step 3: Generate suggestions**

Suggest 3-5 tags and 1-2 categories. Distribute suggestions evenly across the taxonomy rather than over-suggesting popular tags; distribute evenly across the taxonomy. Report suggestions even if tags/categories are already present—they validate against site conventions.

**Gate**: Taxonomy suggestions generated from existing site data (not invented). Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Generate structured validation report with clear outcome.

Format the report as:

```
===============================================================
 PRE-PUBLISH CHECK: [file path]
===============================================================

 FRONT MATTER:
   [status] field: "value" (details)

 SEO:
   [status] check: result (optimal range)

 CONTENT:
   [status] metric: value

 LINKS:
   [status] type: count valid/invalid

 IMAGES:
   [status] check: result

 AI PATTERNS:
   [status] de-AI editor score: N (threshold: 15)

 DRAFT STATUS:
   [status] check: result

===============================================================
 RESULT: [READY FOR PUBLISH | NOT READY - N blockers]
===============================================================
```

**Status icons**: `[PASS]`, `[WARN]`, `[FAIL]`, `[SKIP]`, `[INFO]`

**Result classification**:
- READY FOR PUBLISH: Zero blockers (suggestions and warnings are acceptable)
- NOT READY: One or more blockers present; list all blockers after result

Ensure accurate blocker count. Count blockers and suggestions independently in the final result—count them independently.

**Gate**: Report generated with accurate blocker count. Result matches blocker tally.

---

## Examples

### Example 1: Clean Post
User says: "Check my kubernetes post before I publish"
Actions:
1. Parse front matter and body content (ASSESS)
2. Validate all fields, links, images, draft status (VALIDATE)
3. All tags present, skip taxonomy (SUGGEST)
4. Report: READY FOR PUBLISH with all PASS (REPORT)
Result: Structured report, zero blockers, post cleared for publication

### Example 2: Post With Blockers
User says: "Is my draft ready?"
Actions:
1. Parse front matter — draft: true detected (ASSESS)
2. Validate — draft blocker, missing image, TODO found (VALIDATE)
3. Tags missing — suggest from existing taxonomy (SUGGEST)
4. Report: NOT READY - 3 blockers listed (REPORT)
Result: Structured report with blocker list and suggestions

---

## Error Handling

### Error: "File Not Found"
Cause: Wrong path, running from wrong directory, or file moved
Solution:
1. Verify the path is correct and absolute
2. List available posts with `ls content/posts/`
3. Check if running from repository root
4. Ask user to confirm the correct file path

### Error: "Cannot Parse Front Matter"
Cause: Syntax errors in TOML/YAML, mismatched delimiters, invalid date
Solution:
1. Check for matching delimiters (`+++` or `---`)
2. Validate TOML/YAML syntax (unclosed quotes, bad indentation)
3. Verify date format matches Hugo expectations
4. Report the parse error location and suggest correction

### Error: "Image Path Cannot Be Verified"
Cause: Non-standard path format, Hugo shortcode variant, or missing static/ directory
Solution:
1. Normalize path (strip leading `/`, resolve relative paths)
2. Check both `static/` and `assets/` directories
3. Handle Hugo shortcode `figure` and `img` variants
4. Report as SKIP with explanation if path format is unrecognizable

---

## References

- `${CLAUDE_SKILL_DIR}/references/pre-publish-seo-guidelines.md`: SEO length requirements and best practices
- `${CLAUDE_SKILL_DIR}/references/pre-publish-hugo-frontmatter.md`: Hugo front matter fields and formats
- `${CLAUDE_SKILL_DIR}/references/pre-publish-checklist.md`: Complete validation checklist reference
