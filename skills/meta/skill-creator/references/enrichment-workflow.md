# Enrichment Workflow

Deep reference for the enrichment loop described in SKILL.md → "Enriching existing skills".
Read this file when executing any phase of the loop.

---

## AUDIT phase

Goal: establish a factual baseline before touching anything.

**Depth inventory** — count what the skill currently has:

```
references/   count files (target: 3+)
scripts/      count files (target: 1+ deterministic tools)
agents/       count files (target: 0–2 bundled subagents)
```

Record counts in `enrichment-workspace/audit.json`:

```json
{
  "skill": "skill-name",
  "audit_date": "YYYY-MM-DD",
  "references_count": 0,
  "scripts_count": 0,
  "agents_count": 0,
  "depth_verdict": "thin | adequate | rich",
  "gaps": ["no pattern catalog", "no before/after examples", "no validation checklist"]
}
```

**Baseline runs** — run the skill against 2–3 prompts that exercise its core domain.
Use `scripts/run_eval.py` with `--skill-path` pointing at the skill directory.
Save each output to `enrichment-workspace/baseline/eval-N/output.md`.

Capture what is missing from baseline outputs: generic advice, no domain idioms,
no concrete examples, no checklists, no error scenarios — these become research targets.

**Depth verdict**:
- `thin`: references < 2 files AND no scripts → enrichment warranted
- `adequate`: 2–4 references OR 1+ scripts → enrichment may help, evaluate carefully
- `rich`: 4+ references AND scripts AND agents → enrichment unlikely to move needle;
  consider description optimization instead

---

## RESEARCH phase

Goal: find knowledge that will change the skill's output behavior — not summaries,
but patterns, checklists, before/after examples, and common mistakes.

**Step 1 — read for gaps**
Read the skill's SKILL.md and all files in its `references/` directory.
List what knowledge would change a model's output if it had it:
- Specific checklists the domain uses
- Before/after examples of correct vs incorrect patterns
- Common mistakes practitioners make
- Decision criteria for choosing between approaches
- Validation rules that are non-obvious

**Step 2 — consult domain-research-targets.md**
Look up the skill's domain in `references/domain-research-targets.md`.
It lists primary sources (highest authority), secondary sources (patterns and
examples), and what to extract from each.

**Step 3 — gather knowledge**
For each source in the domain table:

*Official docs*: Read methodology sections, not API reference. Extract:
- Named patterns with rationale
- Failure modes the docs explicitly warn against
- Decision trees or "when to use X vs Y" guidance

*Secondary sources* (blogs, talks, books): Extract:
- Before/after examples (these are gold — models respond to concrete diffs)
- Common mistake catalogs with explanation of why they are mistakes
- Checklists practitioners actually use

*The negative-results registry*: Run:
```bash
grep -n -i "skill-domain-keyword" docs/what-didnt-work.md
```
This surfaces approaches already tried and refuted in this domain, so the new skill does not prescribe one of them.

**What to capture** (format for reference files):

```markdown
## Pattern: Name

**When**: [situation where this applies]
**Do this**:
```code
good example
```
**Not this**:
```code
bad example
```
**Why**: [one-sentence rationale]
```

Aim to collect at minimum:
- 5–10 named patterns with before/after examples
- 1 checklist of 8–15 items practitioners use
- 5–10 common mistakes with explanations
- Any domain-specific validation criteria

---

## ENRICH phase

Goal: add research content to the skill in a form that changes behavior at execution time.

**Where content goes**:

| Content type | Target location |
|---|---|
| Pattern catalog with before/after | `references/patterns.md` (new) |
| Checklist practitioners use | `references/checklist.md` (new) |
| Common mistakes | `references/preferred-patterns.md` (new, or add to existing) |
| Validation criteria | `references/validation-criteria.md` (new) |
| Repeatable deterministic operation | `scripts/tool-name.py` (new) |

**Structuring reference files**:
- Lead with the most behaviorally impactful content (checklists, before/after examples)
- Group by use-case phase, not by alphabet
- Keep each file focused — one theme per file is easier for the skill to load selectively
- Include the "why" for each pattern; models generalize reasoning better than rules

**Updating SKILL.md**:
Add exactly one line per new reference file to the existing "## Reference files" section:
```
- `references/patterns.md` — [domain] pattern catalog: N named patterns with before/after examples
```
Do not expand SKILL.md prose. The orchestrator stays lean; depth lives in references.

**Scripts**:
When research reveals a repeatable mechanical operation (e.g., "run these 4 checks
in sequence"), extract it to `scripts/`. Scripts save tokens on every invocation
and ensure consistency. Use argparse, write to stdout, exit non-zero on error.

**The focus test**: before adding any content, ask — would this change what a model
outputs when executing the skill? If yes, add it. If it is background context the
model already has from training, skip it.

---

## TEST phase

Goal: measure whether the enrichment changed output quality.

**Write test prompts** — 2–3 prompts that specifically exercise the domain knowledge
you just added. If you added a pattern catalog for Go error handling, write prompts
that require correct error wrapping. Prompts must be realistic and specific.

**Run A/B eval**:
```bash
# Run enriched skill
python3 skills/meta/skill-creator/scripts/run_eval.py \
  --skill-path skills/target-skill \
  --prompt "realistic test prompt" \
  --output enrichment-workspace/iteration-1/with-enrichment/eval-1/

# Run baseline (no skill)
python3 skills/meta/skill-creator/scripts/run_eval.py \
  --prompt "realistic test prompt" \
  --output enrichment-workspace/iteration-1/baseline/eval-1/
```

Run both with identical prompts. Save all outputs under `enrichment-workspace/iteration-N/`.

**Workspace structure**:
```
enrichment-workspace/
├── audit.json
├── baseline/
│   ├── eval-1/output.md
│   └── eval-2/output.md
├── iteration-1/
│   ├── with-enrichment/
│   │   ├── eval-1/output.md
│   │   └── eval-2/output.md
│   ├── baseline/
│   │   ├── eval-1/output.md
│   │   └── eval-2/output.md
│   └── comparisons/
│       ├── eval-1-comparison.json
│       └── eval-2-comparison.json
└── iteration-2/
    └── ...
```

---

## EVALUATE phase

Goal: determine objectively whether the enriched version is better.

**Dispatch comparator** for each test prompt pair.
Load `agents/comparator.md` (bundled with skill-creator). Feed it both outputs
labeled "Output A" and "Output B" — do not reveal which is enriched. The comparator:
- Scores both on depth, accuracy, actionability, domain idioms (0–10 each)
- Picks a winner with cited evidence
- Saves to `enrichment-workspace/iteration-N/comparisons/eval-N-comparison.json`

**Decision rule**:
- Enriched wins 2/3 prompts or better → **PUBLISH**
- Tie (1–1 with 2 prompts, or 1–1–1 with 3) → run analyzer, then **RETRY**
- Baseline wins majority → run analyzer, then **RETRY**

**Run analyzer on loss/tie**:
Load `agents/analyzer.md`. Feed it: the comparison results, the enrichment content
added, and the baseline outputs. Ask it to identify specifically what the enriched
version lacked. Common findings:
- Content was added but never referenced in SKILL.md phases (the skill doesn't know to load it)
- Examples were too abstract — model didn't recognize them as patterns to apply
- Research angle was wrong for the prompt type being tested

Record the analyzer's findings in `enrichment-workspace/iteration-N/analysis.md`.
These drive the next research angle.

---

## PUBLISH phase

Goal: commit validated improvements cleanly so they can be reviewed and merged.

**Branch**:
```bash
git checkout -b feat/enrich-{skill-name}
```

**Stage only enrichment artifacts**:
```bash
git add skills/target-skill/references/
git add skills/target-skill/scripts/      # if scripts were added
git add skills/skill-name/SKILL.md        # pointer lines only
```

Do not commit `enrichment-workspace/` — it is ephemeral eval data.

**Commit message**:
```
feat(target-skill): enrich with {domain} patterns and checklist

Added {N} reference files covering {what}: pattern catalog with before/after
examples, practitioner checklist, and common mistake catalog. Enriched version
wins {2 or 3}/3 blind A/B evals against baseline on {domain} prompts.
```

**Push and create PR**:
```bash
git push -u origin feat/enrich-{skill-name}
gh pr create \
  --title "feat(target-skill): enrich with domain knowledge" \
  --body "Enrichment loop result: N reference files added, wins X/3 blind evals."
```

---

## Retry logic in detail

After a failed evaluation, pick the next research angle based on what the analyzer found:

**Iteration 1 — official docs + canonical best practices**
Focus: what the domain's authoritative sources say to do. Patterns and guidelines
from official documentation, language specs, or framework guides. This catches the
most common gap: missing canonical patterns.

**Iteration 2 — common mistakes + failure modes**
Focus: what practitioners actually get wrong. PR review comments, SO questions,
post-mortems, "gotchas" sections in docs. This adds the flip side: what NOT to do
and why. Models often produce safer output when they know the failure modes.

**Iteration 3 — advanced patterns + edge cases**
Focus: what experts know that beginners don't. Performance trade-offs, non-obvious
interactions, when the "standard" pattern breaks down. Only worth pursuing if
iterations 1 and 2 produced improvement but not enough.

**If iteration 3 still fails**:
Do not silently degrade. Report to the user:
- What enrichment was tried (3 research angles)
- What the comparator found lacking in each iteration
- Hypothesis for why the skill is hard to enrich (domain may require runtime context,
  not static reference content)
- Recommendation: accept current state, redesign the eval prompts, or try a
  fundamentally different enrichment approach (e.g., bundled agent instead of reference file)
