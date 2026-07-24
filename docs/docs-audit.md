---
summary: "Work order with a keep/rewrite/merge/retire verdict per docs/ file."
read_when:
  - "planning docs/ cleanup PRs"
---

# Docs Audit

Work order for follow-up PRs. Covers every `docs/` file outside the value-clarity rewrite set (README.md, start-here.md, for-knowledge-workers.md, for-developers.md, for-ai-wizards.md, rewritten in the same PR that adds this file). One row per file. Actions: keep / rewrite / merge-into-X / retire.

`docs/images/` and `docs/repo-hero.png` are assets, not docs; excluded.

| File | Audience | What it claims | Clarity / value issue | Action |
|---|---|---|---|---|
| `PHILOSOPHY.md` | Developers, evaluators | Design principles backed by measured A/B evidence | None significant. Strongest doc in the set; every principle carries numbers or file pointers. | keep |
| `what-didnt-work.md` | Future sessions, maintainers | Negative-results registry: failed experiments with evidence and decisions | None. Load-bearing for evidence-gated evolution; format is enforced and queryable. | keep |
| `QUICKSTART.md` | New users | 30-second start: install, `/do`, mental model | Duplicates start-here.md (install, entry-point table, first commands, verify steps). No inbound links from README or any other doc; orphaned. Two starts confuse the funnel. | merge-into-start-here.md, then retire |
| `REFERENCE.md` | Users wanting the full command list | "Everything in one place. Scan in 2 minutes." | Hand-maintained catalog; drifts from `INDEX.json` truth as components land. Only inbound link is QUICKSTART.md (itself a retire candidate). | rewrite: generate from `scripts/routing-manifest.py`; absorb QUICKSTART's "want the full list" pointer |
| `skills.md` | Users browsing the skill catalog | Full catalog of 131 skills by category | Hand-maintained; same drift risk as REFERENCE.md. README links it, so it must stay accurate. | rewrite: generate via `scripts/generate-skill-index.py` output (script, not prose pass) |
| `for-claude-code.md` | LLMs operating in the repo | Machine-dense inventory: paths, schemas, conventions | Fit for purpose; value framing would be wasted on a machine audience. Minor: repo map lists `~/private-skills/` inside the repo tree, which misstates its location. | keep (fix the one map line in a follow-up) |
| `for-linkedin.md` | Humans who enjoy the joke | Parody of AI-influencer launch posts | The AI patterns are the content. De-AI editing or value rewriting would destroy the parody. Counts (44/124/83) currently match validator truth. | keep |
| `CITATIONS.md` | Maintainers | Provenance of patterns and prior art | None. Low traffic but cheap to keep and useful for "why is it built this way". | keep |
| `compaction-reference.md` | Agents (in-session) | What survives context compaction, when to compact | None. Agent-facing operational reference; paired with `suggest-compact.py`. | keep |
| `deprecation-template.md` | Maintainers | Record form for retiring a skill/agent | None. Linked from README Maintenance section; part of the pruning loop. | keep |
| `injected-context-contracts.md` | Agents, hook authors | Full spec for every injected context tag | None. Linked from CLAUDE.md as the tag catalog; behavioral contract, must stay. | keep |
| `workflow-terminology-migration.md` | Maintainers | Plan to canonicalize "workflow" over "pipeline" | Plan document, not reference. Once steps 1-2 are verified landed it is history, and its frozen-identifier list belongs near the code it protects. | retire to `docs/archive/` after confirming steps landed; move the frozen-identifier list into `skills/workflow/` docs first |
| `archive/positive-instruction-migration.md` | Maintainers | Completed migration loop for positive-instruction rewrites | Already archived; correct end state. | keep |

## Action counts

| Action | Count |
|---|---|
| keep | 9 |
| rewrite | 2 |
| merge-into-X | 1 |
| retire | 1 |

## Follow-up order

1. QUICKSTART merge + retire (removes the duplicate funnel; smallest diff).
2. skills.md generation script (README links it; drift risk is live).
3. REFERENCE.md regeneration (depends on the same manifest script).
4. workflow-terminology-migration retirement (verify steps landed first).
