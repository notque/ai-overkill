# Retro and ADR Validation Phases

Full details for Phase 4c (RETRO) and Phase 4d (ADR VALIDATION) of the PR Pipeline.
Both phases apply to the vexjoy-agent repo only.

---

## Phase 4c: RETRO

**Detection**: Both `agents/` and `skills/` directories exist at project root.

```bash
# Detect toolkit repo
if [ -d "agents" ] && [ -d "skills" ]; then
    echo "Toolkit repo detected -- RETRO phase required"
else
    echo "Not toolkit repo -- skipping RETRO phase"
    # Skip to Phase 5
fi
```

### Step 1: Collect Review Findings

Gather all findings from Phase 2 (REVIEW) and Phase 4b (REVIEW-FIX LOOP) that were identified and fixed. Include:
- Security findings that were addressed
- Code quality issues that were corrected
- Business logic errors that were fixed
- Methodology gaps that were exposed

For each finding, identify the **responsible agent or skill** -- the component whose instructions should have prevented the issue.

### Step 2: Embed in the responsible agent or skill

Write the finding into the component that should have prevented it, in this PR, as a reviewed edit. A review finding in this repo is a structural fix, so it lands in the file directly — no staging store in between.

| Finding Target | Update Location | Section to Modify |
|---------------|----------------|-------------------|
| Agent produced incorrect code | `agents/{name}.md` | Problem signals or missing guidance |
| Skill methodology gap | `skills/{name}/SKILL.md` | Instructions or missing guidance |
| Router missed a pattern | `skills/meta/do/SKILL.md` | Routing tables or Force-Routes |
| Hook failed to catch | `hooks/{name}.py` | Detection logic |

Write the pattern at the right abstraction level -- generalize from the specific bug to the class of bug (e.g., "validate all CLI inputs" not "validate subreddit names in _cmd_classify").

### Step 3: Stage Retro Changes

```bash
# Stage updated agent/skill files alongside the code changes
git add agents/{updated-agent}.md
git add skills/{updated-skill}/SKILL.md
```

These changes will be included in the existing commit (amend in next push cycle) or in a new commit if Phase 4b already completed cleanly.

---

## Phase 4d: ADR VALIDATION

**Detection**: Same as Phase 4c -- only runs in the toolkit repo (both `agents/` and `skills/` directories exist at root).

### Step 1: Run ADR Format Check

```bash
python3 ~/.claude/scripts/adr-status.py check
```

If exit code 1 (warnings found):
- Review each warning (missing headings, empty status)
- Fix formatting issues in the ADR files
- Stage the fixes: `git add adr/`

### Step 2: Run ADR Status Report

```bash
python3 ~/.claude/scripts/adr-status.py status
```

Include the status summary in the PR body if the PR touches any `adr/*.md` files. This gives reviewers an at-a-glance view of ADR state.
