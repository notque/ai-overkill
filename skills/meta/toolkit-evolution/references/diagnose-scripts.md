# DIAGNOSE Phase Scripts

> **Scope**: Concrete bash/Python commands for each step of Phase 1 DIAGNOSE and Phase 0 DISCOVER (frequency check, briefing data, PR-history mining). Load this reference before running those phases. The SKILL.md contains the prose instructions and decision logic; this file contains the exact commands to execute.

---

## Discovery Frequency Check

Check the last discovery run date before starting Phase 0:

```bash
# Find the most recent discovery report
latest=$(ls -t evolution-reports/discovery-*.md 2>/dev/null | head -1)
if [ -z "$latest" ]; then
  echo "NO_PREVIOUS_DISCOVERY"
else
  # Extract date from filename: discovery-YYYY-MM-DD.md
  report_date=$(basename "$latest" | sed 's/discovery-//;s/\.md//')
  days_ago=$(( ($(date +%s) - $(date -d "$report_date" +%s)) / 86400 ))
  echo "Last discovery: $report_date ($days_ago days ago)"
  [ "$days_ago" -ge 30 ] && echo "DISCOVER_DUE" || echo "DISCOVER_SKIPPED"
fi
```

## DISCOVER Step 1: Briefing Data

Collect current toolkit state to brief all perspective agents:

```bash
# Skill count and category distribution
python3 -c "
import json
with open('skills/INDEX.json') as f:
    idx = json.load(f)
skills = idx.get('skills', {})
print(f'Total skills: {len(skills)}')
categories = {}
for s, meta in skills.items():
    cat = meta.get('category', 'uncategorized')
    categories[cat] = categories.get(cat, 0) + 1
for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')
"

# Agent count
python3 -c "
import json
with open('agents/INDEX.json') as f:
    idx = json.load(f)
agents = idx.get('agents', {})
print(f'Total agents: {len(agents)}')
for a in sorted(agents):
    print(f'  {a}')
"
```

---

## DISCOVER Step 2b: PR-History Reflection

Read-only `gh` queries. No mutation of PRs, comments, or labels.

```bash
# Titles, bodies, and changed files for the last 30 merged PRs
gh pr list --state merged --limit 30 --json number,title,body,files \
  --jq '.[] | {number, title, files: [.files[].path]}'

# Review-comment threads for each of those PRs
for n in $(gh pr list --state merged --limit 30 --json number --jq '.[].number'); do
  echo "--- PR #$n ---"
  gh pr view "$n" --comments
done
```

Read the combined output for three signals:
- **Recurring friction**: the same file, directory, or component named as the diff target across 3+ PRs — a change that keeps needing a change is a design gap, not bad luck.
- **Repeated fix patterns**: review comments requesting the identical correction (a missing test, a missing frontmatter field, a missing validation call) on separate PRs — the fix belongs in a hook, script, or skill step, not in each reviewer's memory.
- **Skill/agent gaps**: a PR manually performs a step (e.g., hand-editing INDEX.json, manually chasing a routing entry) that an existing script or skill should have automated, or that no component covers.

Each signal needs 2+ distinct PRs as evidence (Triple-Validation recurrence check) before it becomes a proposal. Format proposals like other DISCOVER output: one-sentence description, evidence (PR numbers), estimated impact. Tag source `[PR-HISTORY]`.

## DIAGNOSE Step 1: Routing telemetry queries

Run these queries to surface weak routes, error-prone dispatches, and reviewer cost:

```bash
python3 ~/.claude/scripts/learning-db.py route-health
python3 ~/.claude/scripts/learning-db.py route-stats --by agent
python3 ~/.claude/scripts/learning-db.py route-stats --by skill
python3 ~/.claude/scripts/learning-db.py route-stats --by errors
python3 ~/.claude/scripts/learning-db.py review-roi
```

Read `route-health` first: it reports the outcome basis, and a per-route error rate computed mostly from neutral outcomes describes the scorer rather than the router. A route with many dispatches and a high error rate is a routing gap; a component with zero dispatches over a long window is shelf-ware. For prior cycle history and already-shelved proposals, read `docs/what-didnt-work.md` and `references/evolution-history.md` — re-proposing a rejected idea is the failure this step prevents.

## DIAGNOSE Step 2: Git History Scan

```bash
# Frequent fixes to same areas suggest chronic issues
git log --oneline --since="2 weeks ago" | head -40

# Files changed most frequently (churn = potential problems)
git log --since="2 weeks ago" --pretty=format: --name-only | sort | uniq -c | sort -rn | head -20
```

## DIAGNOSE Step 3: Dream Report Check

```bash
ls -t ~/.claude/state/dream-* 2>/dev/null | head -5
# Then read the most recent dream-analysis-*.md file
```

## DIAGNOSE Step 3b: Dream Insight Cross-Validation

For each insight from the dream report, verify it still matches current state before treating it as a proposal signal. A dream report can be days old; the repo moves fast.

For each insight that names a specific file path:

```bash
# Verify the file exists
ls -la {path-mentioned-in-dream} 2>/dev/null || echo "STALE: path does not exist -- exclude this insight"
```

For each insight that claims recent activity on a file or area:

```bash
# Verify recent git activity matches the insight
git log --oneline --since="7 days ago" -- {path} 2>/dev/null | head -5
# If empty: the "recent activity" the dream described may be older than 7 days
```

**Staleness rules:**
- Name a file that no longer exists → mark STALE, exclude from opportunity list
- Claims "recent activity" but git log shows nothing in 7 days → mark STALE
- References a pattern already captured in a merged PR → check git log to confirm, then exclude (it is done)

Only forward dream insights where at least one current-state check passes.

## DIAGNOSE Step 4: Routing-Table Drift Check

```bash
python3 scripts/check-routing-drift.py --verbose
```

The `--verbose` flag prints each skill checked plus the final PASS/FAIL. Exit code 1 means skills are missing from the routing manifest.

## DIAGNOSE Step 4b: Orphaned ADR Session Check

```bash
if [ -f ".adr-session.json" ]; then
  adr_info=$(python3 -c "
import json, sys
try:
    d = json.load(open('.adr-session.json'))
    adr_path = d.get('adr_path', '')
    domain = d.get('domain', adr_path)
    print(f'{adr_path}|{domain}')
except Exception as e:
    print('PARSE_ERROR|PARSE_ERROR')
")
  adr_path="${adr_info%|*}"
  domain="${adr_info#*|}"
  if [ "$domain" = "PARSE_ERROR" ]; then
    echo "WARNING: .adr-session.json exists but is unparseable -- flag as cleanup opportunity"
  elif [ -z "$adr_path" ] || [ ! -f "$adr_path" ]; then
    echo "WARNING: .adr-session.json references '$domain' but '$adr_path' does not exist"
    echo "  Orphaned session file. Add 'Remove orphaned .adr-session.json' to the opportunity list."
  else
    echo "ADR session OK: $domain exists at $adr_path"
  fi
else
  echo "No active ADR session file (OK)"
fi
if [ -f ".adr-session.json.stale" ]; then
  echo "STALE: .adr-session.json.stale exists -- flag as cleanup opportunity"
fi
```

## DIAGNOSE Step 4c: Stub Hook Audit

```bash
python3 -c "
import json, os, re
from pathlib import Path

settings_path = Path('.claude/settings.json')
if not settings_path.exists():
    print('No .claude/settings.json found -- skip hook stub audit')
else:
    with open(settings_path) as f:
        settings = json.load(f)
    hooks = settings.get('hooks', {})
    stubs = []
    for event, groups in hooks.items():
        for group in (groups if isinstance(groups, list) else [groups]):
            entries = group.get('hooks', [group]) if isinstance(group, dict) else [group]
            for entry in entries:
                cmd = entry.get('command', '') if isinstance(entry, dict) else str(entry)
                m = re.search(r'python3 [\"\x27]?([\w/.\$~-]+\.py)[\"\x27]?', cmd)
                if not m:
                    continue
                script = m.group(1).replace('\$HOME', str(Path.home()))
                script = os.path.expandvars(script)
                if not os.path.exists(script):
                    continue
                with open(script) as sf:
                    body = sf.read()
                if 'DISABLED' in body or 'empty_output()' in body:
                    desc = entry.get('description', '(no description)') if isinstance(entry, dict) else ''
                    stubs.append((event, os.path.basename(script), desc))
    if stubs:
        print(f'{len(stubs)} stub hook(s) registered in settings.json:')
        for ev, name, desc in stubs:
            print(f'  [{ev}] {name} -- {desc}')
        print('  Add stub deregistration to the opportunity list.')
    else:
        print('No stub hooks found (OK)')
"
```

## DIAGNOSE Step 4d: Usage and Governance Signals

Two activity feeds turn runtime telemetry into opportunities. Both exit 0 on success.

```bash
# Dormant skills/agents (unused in the window) — feed into gap discovery.
# A long-dormant component is either a discoverability gap or a retirement candidate.
python3 scripts/usage-report.py --dormant --json

# Unresolved governance events (last 30 days) — feed into the "what's failing" diagnosis.
# Repeated hook_blocked / policy_violation events surface enforcement friction worth fixing.
python3 scripts/governance-report.py --days 30 --unresolved
```

**How to use the output:**
- **usage-report `--dormant`**: Each dormant skill/agent is a candidate for the opportunity list — tag the source `[USAGE]`. Cross-check before proposing retirement: dormant may mean low discoverability (routing/trigger gap) rather than low value.
- **governance-report `--unresolved`**: Cluster unresolved events by `TYPE` and `TOOL`. A recurring `policy_violation` or `hook_blocked` cluster is an enforcement-friction signal — tag it `[GOVERNANCE]` on the opportunity list with the event count as evidence.
