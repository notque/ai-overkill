---
summary: "Non-developer intro: describe work in plain English, the router does the rest."
read_when:
  - "introducing the toolkit to a non-developer"
---

# For Knowledge Workers

## What This Gives You

Describe your work in plain English. One command routes to 122 skills and their quality checks.

## Interface

```
/do write a blog post about remote work burnout
```

Write your task after `/do`. The router selects an agent and skill, then runs the work.

```
/do research the current state of supply chain AI
/do analyze this CSV and tell me what's driving churn
/do turn this research into an HTML report
/do moderate my subreddit
/do brainstorm blog post ideas for next month
```

## HTML Artifacts

```
/html report on Q3 churn findings
/html pitch deck for the new onboarding flow
/do turn this doc into an interactive prototype
```

One self-contained `.html` file: report, slide deck, prototype, data viz, diagram. Opens in any browser, shares as a single attachment, needs no hosting and no tooling. Auto-detects which shape you need and styles it with a built-in design system. Decks can export to PowerPoint.

Use `/do` for research or analysis and `/html` to present the results.

## Writing & Content

### Blog Posts

```
/do write a blog post about debugging production incidents
```

8-phase pipeline: Load, Ground, Generate, Validate, Refine, Joy-check, Output, Cleanup. Enforces banned-word lists. Writes Hugo-compatible format.

Research-informed variant:

```
/do research then write an article about Kubernetes cost optimization
```

Defines 6 research dimensions, launches 5 parallel agents, compiles findings, writes the article. Research informs narrative without dominating it.

### Voice System

```
/do write a blog post about [topic] in the [voice-name] voice
```

Voice profiles ship as private `voice-*` skills, installed automatically from `~/private-skills` when present. The `voice-writer` pipeline drafts in the calibrated voice and validates deterministically against the profile's metrics: sentence length distribution, contraction rate, punctuation density. It allows up to 3 revision iterations.

### Anti-AI Editing

```
/do make this article sound more human
```

Scans for 397 AI patterns across 33 categories. Makes minimal targeted fixes. Shows every edit with reasoning.

### Repurposing

```
/do turn this article into posts for each platform
```

The content engine adapts a finished piece to each social platform.

### Content Planning

```
/do show my content calendar
/do add an idea about serverless cold starts
/do move the Kubernetes post to editing
```

6 stages: Ideas, Outlined, Drafted, Editing, Ready, Published. Timestamps, 14-day lookahead, stale content flags, duplicate warnings.

```
/do brainstorm blog post ideas
```

Topic brainstormer generates ideas through problem mining, gap analysis, technology expansion. Not random suggestions.

```
/do plan a 5-part series on observability
```

Series planner structures cross-linking, publishing cadence, navigation between parts.

## Research

```
/do research the impact of LLMs on software development productivity
```

5-phase pipeline: **Scope** (primary question + sub-questions), **Gather** (3+ parallel agents, distinct angles), **Synthesize** (evidence quality ratings), **Validate** (gap/bias check), **Deliver** (saves to `research/{topic}/report.md`).

Two modes. Quick runs fewer tool calls per agent. Deep doubles the work per agent.

```
/do quick research on WebAssembly adoption trends
/do deep research on CQRS adoption patterns in fintech
```

## Community Moderation

```
/reddit-moderate
```

Connects to Reddit via PRAW. Fetches modqueue. Classifies items against your subreddit's rules.

Three modes:
- **Interactive**: confirm each action
- **Dry-run**: recommendations only
- **Auto**: high-confidence automated, ambiguous flagged

Setup bootstraps subreddit data: rules files, mod log summaries, repeat offender list.

```bash
python3 skills/content/reddit-moderate/scripts/reddit-mod.py setup
```

Proactive scanning checks posts beyond what's reported:

```
/do scan my subreddit for rule violations in the last 24 hours
```

Pairs with `/loop 10m /reddit-moderate --auto` for hands-off monitoring. First pass for obvious stuff. Not a replacement for human judgment.

## Data Analysis

```
/do analyze sales_data.csv -- what's driving the Q3 revenue drop?
```

Decision-first. Works backward from your question: determines the decision, identifies needed evidence, then touches data. Handles trend analysis, cohort comparison, A/B tests, distribution profiling, anomaly detection.

Statistical rigor built in. Won't claim significance without running the test. Output: structured report tied to your original question.

## Content Publishing

### Pre-Publish Checks

```
/do check this post before publishing
```

Validates frontmatter, SEO fields, internal links, image paths, draft status, taxonomy. Classifies findings as blockers or suggestions. Won't modify files without asking.

### SEO

```
/do optimize this post for search
```

Keyword placement, density analysis, alternative titles, internal linking opportunities, meta descriptions (150-160 chars). Voice preservation is a hard constraint. No keyword-stuffing. No clickbait.

### Link Auditing

```
/do audit links across my site
```

Builds internal link graph. Finds orphan pages, broken links, under-linked content.

## Automation

### Recurring Tasks

```
/loop 10m /reddit-moderate --auto
```

Runs any task on a schedule. Works with any command.

### Condition-Based Waiting

Exponential backoff, timeouts, error handling. Describe what you're waiting for.

## Entry Point

Describe the work after `/do`; the router selects the workflow.
