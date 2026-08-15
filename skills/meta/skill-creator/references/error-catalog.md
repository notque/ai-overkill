# Skill Creator Error Catalog

Comprehensive error patterns and solutions for skill creation.

## Category: Description Errors

### Error: Vague Description

**Symptoms**:
- Skill doesn't trigger when it should
- Users can't find the skill
- /do router doesn't select skill for relevant requests

**Cause**:
Description doesn't clearly state the What+When formula or the trigger phrases users would actually say.

**Solution**:
Apply formula: "Do [specific action] when [trigger condition]. Use for [use cases]. Route adjacent work to the dedicated skill."

**Example Fix**:
```yaml
# Before (vague)
description: Helps with testing workflows

# After (specific)
description: |
  Run Vitest tests and parse results into actionable output. Use when user
  says "run tests", "vitest", "check if tests pass", or "test results".
  Best for Vitest-driven workflows; route Jest, Mocha, and manual testing to their dedicated paths.
```

**Prevention**:
- Always include trigger phrases users would actually say
- Test: Ask Claude "When would you use the [skill-name] skill?"
- If Claude can't explain clearly, revise description

---

### Error: Description Over 1024 Characters

**Symptoms**:
- Skill fails to load
- Error during Claude Code startup
- YAML parsing errors

**Cause**:
Anthropic enforces a 1024 character maximum for skill descriptions.

**Solution**:
Condense description to essential What+When, move details to SKILL.md body:

```yaml
# Before (too long - 1200 chars)
description: |
  This skill performs comprehensive data analysis on CSV files including
  statistical modeling, regression analysis, clustering algorithms, time
  series forecasting, anomaly detection, and visualization generation.
  It can handle missing data imputation, outlier detection, feature
  engineering, dimensionality reduction, and much more... [continues]

# After (concise - 350 chars)
description: |
  Advanced data analysis for CSV files: statistical modeling, regression,
  clustering, time series, anomaly detection. Use for "analyze data",
  "csv statistics", and "data modeling". Best for deeper analysis; use data-viz
  for simple exploration.
```

**Prevention**:
- Aim for 500-700 characters
- Move methodology details to SKILL.md body
- Keep only What+When+Triggers in description

---

### Error: Missing Negative Triggers

**Symptoms**:
- Skill triggers on irrelevant queries
- Users disable the skill
- Overtriggering on generic requests

**Cause**:
Description doesn't state the intended scope or handoff points.

**Solution**:
Add a scope note that names related work routed elsewhere:

```yaml
# Before (overtriggers)
description: |
  Analyzes code quality and provides recommendations.

# After (scoped)
description: |
  Deep security-focused code review with OWASP checks. Use for "security
  review", "vulnerability scan", and "security audit". Best for security
  concerns; route general code review, performance analysis, and style checks
  to their dedicated workflows.
```

**Prevention**:
- List 2-3 related but excluded use cases
- Test with queries that SHOULD NOT trigger the skill

---

## Category: Structure Errors

### Error: SKILL.md Case Mismatch

**Symptoms**:
- Skill not found
- Claude Code doesn't load the skill
- Silent failure during skill discovery

**Cause**:
SKILL.md must be exact case. `skill.md`, `Skill.md`, or `SKILL.MD` will not work.

**Solution**:
```bash
# Fix the filename
cd .claude/skills/my-skill/
mv skill.md SKILL.md  # or whatever the incorrect case is
```

**Prevention**:
- Always use `SKILL.md` (all caps, .md lowercase)
- Use templates or scripts to create skills
- Validate after creation: `ls .claude/skills/*/SKILL.md`

---

### Error: Name/Folder Mismatch

**Symptoms**:
- Skill loads but behaves unexpectedly
- Routing fails
- Duplicate skill errors

**Cause**:
Skill folder name doesn't match `name:` field in YAML frontmatter.

**Solution**:
```yaml
# Folder: .claude/skills/deploy-pipeline/
# SKILL.md frontmatter:
---
name: deploy-pipeline  # MUST match folder name exactly
---
```

**Prevention**:
- Create folder first, then copy folder name into YAML
- Validate: `basename $(dirname $(find .claude/skills -name SKILL.md))` should match `name:` field

---

### Error: README.md Inside Skill Folder

**Symptoms**:
- Confusion about which file is authoritative
- Documentation drift
- Context bloat

**Cause**:
Creating README.md inside `.claude/skills/my-skill/` when all docs should be in SKILL.md or references/

**Solution**:
```bash
# Remove README.md
rm .claude/skills/my-skill/README.md

# Move content to SKILL.md or references/
```

**Prevention**:
- All skill documentation goes in SKILL.md
- Extended docs go in references/ directory
- README.md only at repo root, never inside skill folders

---

## Category: Routing Errors

### Error: Missing Complexity Tier

**Symptoms**:
- Skill doesn't appear in routing tables
- /do doesn't know how to prioritize skill
- Skill evaluation fails

**Cause**:
`routing.complexity` not specified in YAML frontmatter.

**Solution**:
```yaml
routing:
  triggers:
    - keyword1
  pairs_with: []
  complexity: Simple | Medium | Medium-Complex | Complex  # Add this
  category: meta
```

**Prevention**:
- Always specify complexity tier during design phase
- Use checklist: Simple (1 phase), Medium (2-3 phases), Complex (multi-agent)

---

### Error: Missing Category

**Symptoms**:
- Skill not categorized in routing tables
- Discovery issues
- Hard to find related skills

**Cause**:
`routing.category` not specified.

**Solution**:
```yaml
routing:
  category: language | infrastructure | review | meta | content
```

**Categories**:
- `language`: Go, Python, TypeScript, etc.
- `infrastructure`: K8s, Docker, Ansible, etc.
- `review`: Code review, security audit, etc.
- `meta`: Skill/agent creation, system workflows
- `content`: Blog writing, documentation, etc.

**Prevention**:
- Select category during design phase
- One category per skill (don't multi-categorize)

---

## Category: Progressive Disclosure Errors

### Error: Everything in Main File

**Symptoms**:
- SKILL.md over 5000 words
- Slow skill loading
- Context bloat

**Cause**:
Not applying progressive disclosure - all content inline in SKILL.md.

**Solution**:
Move verbose content to references/:
```
Before:
.claude/skills/my-skill/
└── SKILL.md (5000 lines)

After:
.claude/skills/my-skill/
├── SKILL.md (1200 lines)
└── references/
    ├── error-catalog.md
    ├── code-examples.md
    └── workflows.md
```

**Prevention**:
- Complexity tier targets: Simple (300-600), Medium (800-1500), Complex (1500-2500)
- Move to references/ if content is:
  - Comprehensive error listings (keep top 3-5 in main)
  - Extended code examples (keep 1-2 in main)
  - Detailed procedures (keep summaries in main)

---

### Error: Verbose Frontmatter

**Symptoms**:
- Token usage increases on every request
- Slower Claude Code startup
- Description truncated

**Cause**:
Putting detailed instructions in frontmatter description instead of SKILL.md body.

**Solution**:
```yaml
# Before (verbose frontmatter)
description: |
  This skill helps you deploy applications. First, it validates your
  environment by checking Docker, Kubernetes, and Helm installations.
  Then it builds the Docker image, pushes to registry, updates Helm
  values, and deploys... [2000 characters]

# After (concise frontmatter)
description: |
  Deploy applications to Kubernetes via Helm with validation gates.
  Use for "deploy", "release", "push to prod". See SKILL.md for
  detailed workflow.
```

**Prevention**:
- Keep frontmatter under 700 characters
- Only What+When+Triggers in description
- Move all How to SKILL.md body

---

## Category: Workflow Errors

### Error: Phases Without Gates

**Symptoms**:
- Phase 2 executes even when Phase 1 failed
- Cascading failures
- Unclear failure points

**Cause**:
Sequential steps without verification between phases.

**Solution**:
```markdown
# Before (no gates)
### Phase 1: Analyze
- Step 1
- Step 2

### Phase 2: Execute
- Step 3

# After (with gates)
### Phase 1: Analyze
- Step 1
- Step 2
- **GATE**: Validation passes before Phase 2

### Phase 2: Execute
- Step 3
```

**Prevention**:
- Add GATE after every phase for Medium+ skills
- Define what "pass" means for each gate
- Include failure handling for each gate

---

### Error: Infinite Retry Loops

**Symptoms**:
- Skill runs indefinitely
- High token usage
- Session hangs

**Cause**:
No retry limits on iterative phases.

**Solution**:
```markdown
# Before (infinite)
### Phase 2: Refine
- Check quality
- If fails: Go back to Phase 2

# After (limited)
### Phase 2: Refine (max 3 iterations)
- Check quality
- If fails AND iterations < 3: Retry
- If fails AND iterations = 3: STOP and report
```

**Prevention**:
- Always specify max iterations (typically 3)
- Include escape condition
- Report after max attempts

---

## Category: Security Errors

### Error: XML Injection in Frontmatter

**Symptoms**:
- Skill fails security validation
- Claude Code refuses to load skill
- System prompt contamination

**Cause**:
Using `<` or `>` in frontmatter description (can inject instructions into Claude's system prompt).

**Solution**:
```yaml
# Before (dangerous)
description: |
  Use for <critical tasks> and <important operations>

# After (safe)
description: |
  Use for critical tasks and important operations
```

**Prevention**:
- Never use `<` or `>` in YAML frontmatter
- Use plain text only
- Markdown formatting goes in SKILL.md body, not frontmatter

---

### Error: Hardcoded Secrets

**Symptoms**:
- API keys visible in skill files
- Security audit failures
- Credential leaks

**Cause**:
Embedding secrets directly in SKILL.md or scripts.

**Solution**:
```python
# Before (hardcoded)
api_key = "sk-1234567890abcdef"

# After (environment variable)
import os
api_key = os.environ.get("API_KEY")
if not api_key:
    raise ValueError("API_KEY environment variable required")
```

**Prevention**:
- All secrets in environment variables
- Document required env vars in SKILL.md
- Use `.env.example` for templates (never `.env` in repo)
