# Knowledge Base

Deep reference for converting resolved support tickets into publish-ready KB articles: article type selection, structure templates, search optimization, formatting standards, maintenance cadence, and categorization taxonomy.

---

## When to Create a KB Article

Not every resolved ticket deserves an article. Create one when:

| Signal | Article Type |
|--------|-------------|
| Same question asked 3+ times | FAQ or How-to |
| Ticket resolution required non-obvious steps | Troubleshooting |
| Product behavior surprises customers | Known Issue or FAQ |
| New feature launched without adequate docs | How-to |
| Workaround exists for a known bug | Known Issue |
| Complex setup customers struggle with | How-to |
| Common error message with non-obvious fix | Troubleshooting |

Skip when:
- One-off account-specific issue
- Issue already covered by existing article (update instead)
- Bug will be fixed within days and workaround is simple
- Issue requires internal-only context to understand

---

## Article Type Selection

| Type | Purpose | Best For | Structure |
|------|---------|----------|-----------|
| **How-to** | Step-by-step task completion | Setup, configuration, workflow guidance | Prerequisites -> Steps -> Verify -> Common Issues |
| **Troubleshooting** | Diagnose and fix a problem | Error resolution, unexpected behavior | Symptoms -> Cause -> Solution(s) -> Prevention |
| **FAQ** | Quick answer to common question | Policy, capability, pricing, simple factual | Direct Answer -> Details -> Related Questions |
| **Known Issue** | Document a bug with workaround | Active bugs, limitations, regressions | Status -> Symptoms -> Workaround -> Fix Timeline |
| **Reference** | Technical specification or comparison | API docs, plan comparisons, config options | Overview -> Details (tables) -> Examples |

### Type Disambiguation

| Customer says | Type | Reasoning |
|--------------|------|-----------|
| "How do I...?" | How-to | Task-oriented, needs steps |
| "It's not working" | Troubleshooting | Problem-oriented, needs diagnosis |
| "Can I...?" or "Does it...?" | FAQ | Yes/no answer with context |
| "I'm seeing an error that I heard is a known bug" | Known Issue | Active defect, needs status/workaround |
| "What are the limits?" | Reference | Factual, tabular |

---

## Article Structure Templates

### How-to Article

```markdown
# How to [accomplish task]

[1-2 sentence overview: what this guide covers and when you'd use it]

## Prerequisites
- [What's needed before starting]
- [Required permissions, plan level, etc.]

## Steps

### 1. [Action verb phrase]
[Instruction with specific UI paths: "Go to Settings > Integrations > API Keys"]
[What you should see after completing: "A green confirmation banner appears"]

### 2. [Action verb phrase]
[Instruction]

### 3. [Action verb phrase]
[Instruction]

## Verify It Worked
[How to confirm the task succeeded -- specific observable outcome]

## Common Issues
| Issue | Fix |
|-------|-----|
| [Problem that might occur] | [Resolution] |
| [Another common snag] | [Resolution] |

## Related Articles
- [Link to related how-to or troubleshooting]
```

**Writing rules for how-tos:**
- Start each step with a verb
- Include the full navigation path ("Settings > Integrations > API Keys")
- State what the user should see after each step
- Test steps against the actual product before publishing
- One task per article -- split multi-task guides

### Troubleshooting Article

```markdown
# [Problem description -- what the user sees]

If you're seeing [symptom in customer language], this article
explains how to fix it.

## Symptoms
- [Observable behavior 1]
- [Observable behavior 2]
- [Exact error message if applicable, in code block]

## Cause
[Why this happens -- brief, non-jargon explanation.
Keep it simple even if the root cause is complex.]

## Solution

### Option 1: [Primary fix -- most likely to work]
1. [Step]
2. [Step]
3. [Step]

### Option 2: [Alternative if Option 1 doesn't work]
1. [Step]
2. [Step]

## Prevention
[How to avoid this in the future, if applicable]

## Still Having Issues?
If these steps didn't resolve the problem, contact support
with the following information:
- [What to include in their ticket]
```

**Writing rules for troubleshooting:**
- Lead with symptoms, not causes -- customers search for what they see
- Include exact error messages in code blocks (customers copy-paste into search)
- Provide multiple solutions ordered by likelihood
- Always include "Still having issues?" pointing to support
- Keep customer-facing explanation simple even if root cause is complex

### FAQ Article

```markdown
# [Question in the customer's words]

[Direct answer -- 1-3 sentences. Answer in the first sentence.]

## Details
[Additional context, nuance, or edge cases if needed.
Keep brief -- if this needs a walkthrough, it's a how-to.]

## Related Questions
- [Link to related FAQ]
- [Link to related FAQ]
```

**Writing rules for FAQs:**
- Answer the question in the first sentence
- Keep it concise -- if the answer needs steps, it's a how-to
- Use the customer's language in the title, not internal terminology
- Group related FAQs and cross-link

### Known Issue Article

```markdown
# Known Issue: [Brief description]

**Status:** [Investigating | Workaround Available | Fix In Progress | Resolved]
**Affected:** [Who/what is affected -- plan, feature, browser, etc.]
**Last updated:** [Date]

## Symptoms
[What users experience]

## Workaround
[Steps to work around the issue]
[Or: "No workaround currently available."]

## Fix Timeline
[Expected fix date, or current investigation status]

## Updates
- [Date]: [Update -- most recent first]
- [Date]: [Update]
```

**Writing rules for known issues:**
- Keep status current -- stale known-issue articles erode trust fast
- Update when fix ships, mark as Resolved
- Keep resolved articles live for 30 days (customers still searching old symptoms)
- If no workaround, say so honestly -- don't fabricate one

### Reference Article

```markdown
# [Topic]: [Specific scope]

[1-2 sentence overview of what this reference covers]

## [Section]

| [Column 1] | [Column 2] | [Column 3] |
|------------|------------|------------|
| [Data] | [Data] | [Data] |

## Examples
[Concrete examples showing usage or application]

## Related
- [Links to related reference or how-to articles]
```

---

## Search Optimization

Articles are useless if customers can't find them. Every article must be findable through search using the words a customer would type.

### Title Rules

| Good Title | Bad Title | Why |
|------------|-----------|-----|
| "How to configure SSO with Okta" | "SSO Setup" | Specific, includes the tool name |
| "Fix: Dashboard shows blank page" | "Dashboard Issue" | Includes the symptom |
| "API rate limits and quotas" | "API Information" | Includes specific terms |
| "Error: 'Connection refused' when importing data" | "Import Problems" | Includes exact error message |
| "Why is my export missing rows?" | "Export FAQ" | Matches customer's question |

### Keyword Strategies

- **Exact error messages**: customers copy-paste error text into search
- **Customer language**: "can't log in" not "authentication failure"
- **Common synonyms**: delete/remove, dashboard/home page, export/download
- **Alternate phrasings**: address the issue from different angles in the overview
- **Product area tags**: match how customers think about the product

### Opening Sentence Formulas

| Article Type | Formula |
|-------------|---------|
| How-to | "This guide shows you how to [accomplish X]." |
| Troubleshooting | "If you're seeing [symptom], this article explains how to fix it." |
| FAQ | "[Question in customer's words]? Here's the answer." |
| Known issue | "Some users are experiencing [symptom]. Here's what we know and how to work around it." |
| Reference | "This page documents [topic scope] for [audience]." |

---

## Formatting Standards

### Universal Rules

- **Headers (H2, H3)** for scannable sections
- **Numbered lists** for sequential steps (order matters)
- **Bullet lists** for non-sequential items (order doesn't matter)
- **Bold** for UI element names, key terms, emphasis
- **Code blocks** for commands, API calls, error messages, config values
- **Tables** for comparisons, options, reference data
- **Callouts** for warnings, tips, important caveats
- **Short paragraphs**: 2-4 sentences max
- **One idea per section**: if covering two topics, split

### Metadata Block

Every article includes:

```yaml
Title: [searchable, specific]
Type: [How-to | Troubleshooting | FAQ | Known Issue | Reference]
Category: [Product area]
Tags: [comma-separated searchable terms]
Audience: [All users | Admins | Developers | Specific plan]
Last updated: [Date]
```

---

## Categorization Taxonomy

Organize articles into a hierarchy matching customer mental models:

```
Getting Started
├── Account setup
├── First-time configuration
└── Quick start guides

Features & How-tos
├── [Feature area 1]
├── [Feature area 2]
└── [Feature area 3]

Integrations
├── [Per-integration guides]
└── API reference

Troubleshooting
├── Common errors
├── Performance issues
└── Known issues

Billing & Account
├── Plans and pricing
├── Billing questions
└── Account management
```

### Linking Rules

| From | To | Purpose |
|------|----|---------|
| Troubleshooting | How-to | "For setup instructions, see [Guide]" |
| How-to | Troubleshooting | "If you encounter errors, see [Troubleshooting]" |
| FAQ | Detailed article | "For a full walkthrough, see [Guide]" |
| Known issue | Workaround | Keep problem-to-solution chain short |

Link articles in one direction unless both are genuinely useful entry points. Use relative links within the KB — they survive restructuring.

---

## Maintenance Cadence

Knowledge bases decay without maintenance. Stale or wrong articles are worse than no articles.

| Activity | Frequency | Owner |
|----------|-----------|-------|
| New article review | Before publishing | Peer + SME for technical content |
| Accuracy audit | Quarterly | Support reviews top-traffic articles |
| Stale content check | Monthly | Flag articles not updated in 6+ months |
| Known issue updates | Weekly | Update status on all open known issues |
| Analytics review | Monthly | Low helpfulness ratings, high bounce rates |
| Gap analysis | Quarterly | Top ticket topics without KB articles |

### Article Lifecycle

| State | Meaning | Trigger |
|-------|---------|---------|
| Draft | Written, needs review | New article created |
| Published | Live, available to customers | Review passed |
| Needs Update | Flagged for revision | Product change, feedback, or age |
| Archived | Not live but preserved | No longer relevant |
| Retired | Removed from KB | Content permanently obsolete |

### Update vs. Create New

**Update existing when:**
- Product changed and steps need refreshing
- Article is mostly right but missing a detail
- Customer feedback says a section is confusing
- Better workaround or solution found

**Create new when:**
- New feature or product area needs docs
- Resolved ticket reveals a gap (no article exists)
- Existing article covers too many topics (split it)
- Different audience needs different explanation

---

## Ticket-to-Article Conversion Process

### Step 1: Identify the Candidate

After resolving a ticket, ask:
- Would this resolution help future customers self-serve?
- Has this question come up before (or will it again)?
- Is the workaround non-obvious?

### Step 2: Extract the Essentials

From the ticket thread, extract:
- The original problem in customer language
- The resolution steps (in order, with specifics)
- Edge cases or caveats discovered during resolution
- Environment or configuration details that matter

### Step 3: Generalize

Transform the ticket-specific resolution into a general guide:
- Remove customer-specific account details
- Replace specific values with representative examples
- Add prerequisites that were implicit in the ticket context
- Cover alternate scenarios the ticket didn't encounter

### Step 4: Validate

- Follow the steps yourself (or have someone unfamiliar follow them)
- Verify against the current product version
- Get SME review for technical accuracy
- Check that search terms match customer language

### Step 5: Publish and Link

- Add to the appropriate category
- Link from related articles
- Tag for searchability
- Set a review date (30-90 days depending on product change velocity)

---

## KB Quality Failure Modes

| Failure Mode | Problem | Fix |
|-------------|---------|-----|
| Internal jargon in title | Customers can't find it via search | Rewrite in customer language |
| Steps that skip prerequisites | Customer gets stuck at step 1 | Add explicit prerequisites section |
| No "Still Having Issues?" section | Dead end when article doesn't help | Always include support escalation path |
| Screenshots without text descriptions | Breaks when UI changes, not accessible | Describe UI elements in text, use screenshots as supplement |
| Monster article covering 5 topics | Hard to find, hard to maintain | Split into focused single-topic articles |
| Outdated known issue without status update | Erodes trust in entire KB | Weekly status sweeps on all known issues |
| Written for internal audience | Customer can't follow | Rewrite with zero assumed internal knowledge |
