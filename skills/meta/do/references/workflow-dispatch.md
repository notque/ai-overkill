# Workflow Dispatch (Phase 4 Steps 1b/1c)

Native-Workflow executor selection and roster rules, moved verbatim from `SKILL.md` Phase 4. Load on: a pipeline `pick`, Complex/tier-4 with no pick, or an explicit "run through a workflow" request.

**Step 1b (native Workflow dispatch): run the deterministic variant when the harness supports it, else the prose pipeline.** When the Phase 2 Step 0 self-route emitted a pipeline `pick` (#686), select the executor with this ADR decision table (`harness-conditional-workflow-dispatch`):

```
pick = route.pipeline                               # #686, may be null
cap  = scripts/detect-workflow-capability.py        # env proxy: {harness, workflow_capable}
reg  = scripts/workflow-registry.py                 # auto-derived {meta.name: path}
{scope, tier} = scripts/right-size-review.py        # #688 right-sizing (review picks)
complex4 = (complexity == Complex) or (tier == 4)   # ADR native-fast-path Stage 2

if pick is not None and reg.get(pick) and cap.workflow_capable and (Workflow tool in MY tool list):
        # NAMED pipeline: env proxy AND LLM tool-list self-check (authoritative gate)
                                                            -> Workflow.run(reg[pick], {scope, tier})
elif pick is not None and reg.get(pick):                    -> run the prose pipeline markdown (unchanged)
elif pick is None and complex4 and cap.workflow_capable and (Workflow tool in MY tool list):
        # NO named pipeline + Complex/tier-4: generic native fan-out (Stage 2)
                                                            -> Workflow.run("fan-out-workflow", {scope, tier, roster})
elif pick is None and complex4:                             # Workflow tool absent -> floor
                                                            -> dispatch multiple Agent tools in one message (prose fan-out, unchanged)
else:                                                       -> agent + skill direct (simpler; unchanged)
```

Build `roster` from the Phase-3 enhancement signals, scaled by `tier`. **Each entry is `{agentType, skills: [...], lens}` — `skills` is a LIST carrying the FULL Phase-3 stack a direct dispatch would build.** Per agent, emit `Call the Skill tool with \`skill-name\`.` once per callable `skills` element and the four /do mandatory injections. Native forms: `comprehensive-review-workflow.js` (named pipeline), `fan-out-workflow.js` (generic Complex/tier-4). Both pseudocode gates (env proxy AND the orchestrator's own tool-list self-check) must hold; a `pick` with no registry entry is prose-only.

**File ownership batching:** batch fan-out items by file ownership before opening PRs — branches touching the same file merge serially and each later one goes CONFLICTING (evidence: PRs #789/#791/#793 each added rows to pr-workflow SKILL.md, costing a remediation wave). Put shared-file items on one branch or declare a merge order.

**Banner parity (R4):** expand the pipeline name → phase list for the routing banner on BOTH paths, so it reads identically regardless of executor (e.g. complexity-trigger fan-out shows `fan-out → synthesize`).

**Step 1c (inline-authored Workflow scripts): when the user explicitly asks to "run through a workflow" with no named pipeline `pick`, the orchestrator MUST dictate roster size and skill stacks — never delegate those to the Workflow tool** (whose defaults skew toward many-skeptic adversarial fan-outs and rarely emit the exact Skill-tool call). Before any inline `script:`, build the same `roster` Step 1b uses and pin:

| Constraint | Rule |
|------------|------|
| **Agent count** | Dictate explicit roster length per task class (table below), not the Workflow tool's "comprehensiveness" heuristics. |
| **Skill stacks** | EVERY `agent()` prompt MUST contain `Call the Skill tool with \`skill-name\`.` once per callable element of its roster entry's `skills` list. Empty `skills` is a routing bug — fail closed and re-route. |
| **Adversarial passes** | Default to **single skeptic per finding**, not 3–5. Escalate to 3 only on a request for "adversarial," "heavy refute," or "high-stakes review," and only on findings surviving the first pass. |
| **Phase count** | Reuse a registry pipeline's phase shape (`comprehensive-review-workflow`, `fan-out-workflow`, `research-pipeline`) over inventing novel phase names. |

Roster-size table (counts dictated, NOT advisory):

| Request class | Roster size | Skeptic pass |
|---------------|-------------|--------------|
| PR review (Tier 1, ≤6 files) | 3 reviewers | none default; 1 skeptic on user request |
| PR review (Tier 2–3) | 12 / 17 reviewers per `right-size-review.py` | 1 skeptic on "Critical" findings only |
| PR review (Tier 4) | 27 reviewers | 1 skeptic on Critical+High findings |
| Adversarial validation of N findings | 1 skeptic × N (not 3 × N) | escalate to 3 only on user-flagged "heavy pushback" |
| Research fan-out | 3–5 researchers per `research-pipeline` Wave 1 | n/a |
| Generic complexity-trigger fan-out | use `fan-out-workflow` registered roster | n/a |

Inline `script:` shape (exact Skill-tool calls in EVERY worker, count from the roster):

```js
const ROSTER = [/* dictated count, NOT model-chosen */
  {agentType: "reviewer-system",       skills: ["systematic-code-review", "anti-rationalization-review"], lens: "security"},
  {agentType: "reviewer-domain",       skills: ["systematic-code-review", "anti-rationalization-review"], lens: "domain"},
  {agentType: "reviewer-perspectives", skills: ["systematic-code-review", "anti-rationalization-review"], lens: "newcomer"},
];
const findings = await parallel(ROSTER.map(r => async () => {
  const prompt = `${skillDirectives(r.skills)}\n${buildPrompt(r)}`;
  return agent(prompt, {agentType: r.agentType, schema: FINDINGS_SCHEMA});
}));
```

Catching a model-chosen N (`parallel(Array.from({length: N}, ...))`) or a missing exact Skill-tool call means **stop and rebuild the script from the roster table above**.
