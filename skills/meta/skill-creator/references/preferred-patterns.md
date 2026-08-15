# Skill Creator Patterns Guide

Common skill design issues, the signals that reveal them, and the preferred correction.

## Write Trigger-Rich Descriptions

Every skill description must state what the skill does, when to invoke it, and what to exclude. Include literal trigger phrases so the /do router can match user intent.

```yaml
description: |
  Deploy applications to Kubernetes via Helm with validation gates. Use when
  user says "deploy", "release", "push to prod", or "helm upgrade". Do NOT
  use for Docker-only deploys (use docker-deploy skill).
```

**Why this matters**: The /do router selects skills by matching user intent against descriptions. A description without trigger phrases undertriggers on relevant requests, making the skill invisible to users who need it.

**Detection**: Check for descriptions that lack trigger phrases or exclusion clauses:
```bash
grep -A5 'description:' skills/*/SKILL.md | grep -vE 'Use (when|for)|Do NOT'
```

---

## Gate Every Phase Transition

Define an explicit GATE condition at the end of each phase, with failure behavior. Phase 2 should never execute if Phase 1 validation failed.

```markdown
### Phase 1: Analyze
- Read configuration
- Validate inputs
- **GATE**: Configuration valid and all inputs verified

If gate fails:
- STOP execution
- Report validation errors
- Provide remediation steps

### Phase 2: Execute
- Run deployment
- Update status
- **GATE**: Deployment succeeded
```

**Why this matters**: Without gates, phase failures cascade silently. A bad configuration flows into execution, producing errors that are hard to trace back to the real cause. Gates isolate failures to the phase that caused them.

**Detection**: Look for multi-phase skills missing GATE markers:
```bash
grep -c 'GATE' skills/*/SKILL.md | awk -F: '$2 == 0 {print $1": no gates"}'
```

---

## Keep the Main File Under 500 Lines

Structure complex skills with SKILL.md as a thin orchestrator (~500 lines) and deep content in `references/`. The orchestrator tells the model what to do and when to load references. Heavy catalogs, examples, and failure modes live in reference files.

```
.claude/skills/my-complex-skill/
├── SKILL.md (1200 lines)
│   - Frontmatter (50 lines)
│   - Instructions (400 lines)
│   - Top 5 errors (200 lines)
│   - Top 5 anti-patterns (200 lines)
│   - Workflow summaries (200 lines)
│   - References section (150 lines)
└── references/
    ├── error-catalog.md (1200 lines)
    ├── code-examples.md (800 lines)
    ├── preferred-patterns.md (600 lines)
    └── workflows.md (400 lines)
```

**Why this matters**: A 4500-line SKILL.md bloats context with detail irrelevant to most invocations. Progressive disclosure means the content still exists, but only the relevant slice enters context at any given phase.

**Detection**: Find oversized skill files:
```bash
wc -l skills/*/SKILL.md | awk '$1 > 2000 {print}'
```

---

## State What, When, and Why in the Name and Description

Name skills with `{action}-{domain}` and write descriptions that answer three questions: what does it do, when should it fire, and what should it exclude.

```yaml
name: csv-statistical-analyzer
description: |
  Advanced statistical analysis for CSV files: regression, clustering,
  time series forecasting. Use for "analyze data", "csv statistics",
  "regression analysis", "clustering". Do NOT use for simple data
  exploration (use data-viz skill instead).
```

**Why this matters**: A skill named `data-processor` with a vague description will undertrigger because the router cannot determine when it applies. Specificity in naming and description drives correct routing.

**Detection**: Find generic descriptions missing trigger phrases:
```bash
grep -A3 'description:' skills/*/SKILL.md | grep -v 'Use for\|Use when\|Do NOT'
```

---

## Match Workflow Depth to Task Complexity

Size the skill's structure to its actual complexity. A simple cleanup workflow needs 4 phases and 300-600 lines, not 6 phases with complex gates and 2500 lines.

Simple skill (pr-workflow cleanup) should have:
- 4 phases with basic gates
- 3-5 common errors inline
- 2-3 failure modes inline
- No references/ directory
- 300-600 lines total

**Why this matters**: Over-engineering creates maintenance burden and confuses users. The framework's value is proportional to the workflow's complexity — a simple task with a complex skill wastes tokens loading unused structure.

**Detection**: Compare line count to complexity tier:
```bash
wc -l skills/*/SKILL.md | awk '$1 > 1500 {print $1, $2}'
```

---

## Add a Complexity Tier

Every skill must include a `complexity` field in its routing metadata. This lets /do prioritize skills appropriately and enables evaluation to assess whether the skill's size matches its tier.

```yaml
routing:
  triggers:
    - deploy
  pairs_with:
    - verification-before-completion
  complexity: Medium
  category: infrastructure
```

**Why this matters**: Without a complexity tier, the router cannot prioritize and evaluation tools cannot assess whether the skill is over- or under-engineered for its purpose.

**Detection**: Find skills missing the complexity field:
```bash
grep -L 'complexity:' skills/*/SKILL.md
```

---

## Bound Retries With Escalation

Every iterative loop must have a maximum iteration count and an escalation path when retries are exhausted. Open-ended retry loops cause session hangs and unbounded token usage.

```markdown
### Phase 2: Refine (max 3 iterations)
- Run quality check
- If fails AND iterations < 3: Retry Phase 2
- If fails AND iterations = 3:
  - STOP execution
  - Report all failures
  - Suggest manual intervention
```

**Why this matters**: An unbounded "if fails, go back to Phase 2" loop can consume the entire session budget without producing useful output. Bounded retries with escalation give users actionable information when automatic fixing fails.

**Detection**: Find retry patterns without bounds:
```bash
grep -n 'Go back to\|Retry Phase\|retry' skills/*/SKILL.md | grep -vi 'max\|iteration\|limit'
```

---

## Load Secrets From the Environment

Never hardcode credentials in skill scripts. Read secrets from environment variables and fail with a clear error message naming the missing variable.

```python
# scripts/deploy.py
import os

def deploy():
    api_key = os.environ.get("API_KEY")
    db_password = os.environ.get("DB_PASSWORD")

    if not api_key or not db_password:
        raise ValueError(
            "Required environment variables: API_KEY, DB_PASSWORD\n"
            "See references/setup.md for configuration"
        )

    connect(api_key=api_key, password=db_password)
```

**Why this matters**: Hardcoded secrets leak into git history, prevent sharing the skill, and fail audit. Environment variables keep secrets out of version control and allow per-environment configuration.

**Detection**: Find hardcoded credential patterns in skill scripts:
```bash
grep -rn 'API_KEY\|PASSWORD\|TOKEN\|SECRET' --include="*.py" skills/*/scripts/ | grep -v 'environ\|os.getenv'
```

---

## Add Explicit Error Handling

Every skill must document at least 3-5 common error scenarios with cause and solution. Place the error handling section after the workflow instructions.

```markdown
## Error Handling

### Error: "FileNotFoundError: file.csv"
**Cause**: Input file not found
**Solution**: Verify file path and run from correct directory

### Error: "ValueError: Invalid CSV format"
**Cause**: CSV file has formatting issues
**Solution**: Check for:
- Consistent column count
- Proper quoting
- Valid encoding (UTF-8)

### Error: "PermissionError: results.json"
**Cause**: Cannot write to output directory
**Solution**: `chmod +w $(dirname results.json)`
```

**Why this matters**: Without error handling guidance, users hit a wall when commands fail. Documented error-fix mappings turn a blocked user into a self-sufficient one.

**Detection**: Find skills without error handling sections:
```bash
grep -L 'Error Handling\|Error-Fix\|error.*cause.*solution' skills/*/SKILL.md
```

---

## Keep Frontmatter Under 700 Characters

Frontmatter is loaded on every request. Keep descriptions concise — state what the skill does, its trigger phrases, and exclusions. Move detailed workflow descriptions to the SKILL.md body.

```yaml
description: |
  Deploy applications to Kubernetes via Helm with validation gates.
  Use for "deploy", "release", "helm upgrade", "push to prod". Do NOT
  use for Docker-only deploys. See SKILL.md for detailed workflow.
```

**Why this matters**: Frontmatter is part of every session's token budget. A 2000-character description wastes tokens on content that belongs in the skill body, and violates progressive disclosure.

**Detection**: Check frontmatter description length:
```bash
python3 -c "
import yaml, glob
for f in glob.glob('skills/*/SKILL.md'):
    with open(f) as fh:
        content = fh.read().split('---')
        if len(content) >= 3:
            meta = yaml.safe_load(content[1])
            desc = meta.get('description', '')
            if len(desc) > 700:
                print(f'{f}: {len(desc)} chars')
"
```

---

## Use Valid Skill Names

Name skills using `{action}-{domain}` in kebab-case. The file must be named `SKILL.md` (exact case). Avoid decorative terms (wizard, guru, ninja, master, oracle).

- Folder: `.claude/skills/deployment-automation/`
- Name: `deployment-automation`
- File: `SKILL.md`

**Why this matters**: Consistent naming enables tooling, routing, and human navigation. Case mismatches between folder and name cause lookup failures. Decorative terms obscure function.

**Detection**: Find naming violations:
```bash
find skills/ -name 'SKILL.md' -exec dirname {} \; | xargs -I{} basename {} | grep -E '_|[A-Z]'
```

---

## Pair Mandates With Rationale

Attach a "because X" reason to every instruction. Bare imperatives without reasoning cannot generalize to edge cases the author did not anticipate. Reasoned constraints let the model make the right call in ambiguous situations.

```markdown
## Instructions
- Use structured logging (fmt.Println output isn't captured by the log aggregator
  and can't be filtered by severity in production)
- Validate all inputs at service boundaries (malformed data here propagates
  silently through downstream services and surfaces as confusing errors later)
- Check return values — Go's error model depends on callers inspecting errors;
  ignored errors cause silent failures that are hard to debug in production
```

**Why this matters**: LLMs follow instructions better when they understand the reasoning. Motivation makes the model follow willingly; gates catch failures regardless. When the model encounters an ambiguous case, understanding intent helps it make the right call.

**Detection**: Find bare imperatives without reasoning:
```bash
grep -n 'ALWAYS\|NEVER\|MUST' skills/*/SKILL.md | grep -v 'because\|since\|so that'
```

---

## Add Negative Triggers for Exclusions

When a skill has a broad domain that overlaps with specialized skills, add explicit exclusion clauses (e.g. "Use X skill instead for Y"). This prevents overtriggering on requests that belong to a more specialized skill.

```yaml
description: |
  General code quality analysis: style, complexity, maintainability. Use for
  "code review", "check quality", "analyze code". Do NOT use for security
  audits (use reviewer-security), performance analysis (use performance-
  optimization-engineer), or language-specific reviews (use go-patterns,
  python-code-review).
```

**Why this matters**: Without negative triggers, a broad skill overtriggers on requests meant for specialists. Users disable overtriggering skills, which means legitimate requests also stop routing correctly.

**Detection**: Find broad descriptions without exclusion clauses:
```bash
grep -A5 'description:' skills/*/SKILL.md | grep -v 'Do NOT\|do not use'
```
