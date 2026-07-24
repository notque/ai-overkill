# LLM Failure Modes in Product Management

Where LLMs systematically fail at PM tasks. Loaded across all modes as a guardrail reference.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers product management-specific failures only.

---

## Why This File Exists

LLMs are fluent generators. Fluency is dangerous in PM work because PM artifacts look correct when they are not. A spec with vague acceptance criteria passes a casual read. Fabricated user quotes sound plausible. A roadmap that is a feature list with dates looks like strategic planning.

This reference catalogs the specific failure modes, their signatures, and the defenses against each.

---

## Failure Mode 1: Vague Specifications

### What Happens

The LLM produces a spec that reads well but contains requirements no engineer can implement against. Requirements use subjective language ("intuitive", "fast", "user-friendly") without measurable definitions. Acceptance criteria are either missing or restate the requirement in different words.

### Signatures

| Signal | Example |
|--------|---------|
| Subjective adjectives | "The interface should be intuitive and responsive" |
| Restated requirements as AC | Requirement: "Support file upload." AC: "Users can upload files." |
| Missing edge cases | Happy path only. No error states, empty states, or boundary conditions. |
| Implementation-free | No consideration of what happens at scale, under load, or with bad input |
| Ambiguous scope | "Support major file formats" — which ones? |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Ban ambiguous words | Maintain a banned-word list: intuitive, fast, user-friendly, responsive, scalable, secure — require concrete definitions for each |
| Given/When/Then enforcement | Every requirement gets at least one Given/When/Then acceptance criterion |
| Edge case prompting | Explicitly prompt for: error states, empty states, boundary conditions, concurrent access, permission failures, offline/degraded |
| Quantity check | Each P0 requirement should have 3-5 acceptance criteria covering happy path + edge cases |
| Engineer review test | "Could an engineer implement this without asking any clarifying questions?" If no, the spec is incomplete. |

---

## Failure Mode 2: Fabricated Research Data

### What Happens

The LLM generates plausible-sounding user quotes, statistics, persona details, or research findings that are not grounded in any data the user provided. Because the LLM is trained on real research examples, fabricated data looks authentic.

### Signatures

| Signal | Example |
|--------|---------|
| Unsourced quotes | "As one user put it, 'I just wish the export worked better'" — when no user said this |
| Precise statistics from nowhere | "67% of users reported frustration with the onboarding flow" — when no survey was conducted |
| Rich persona details without data | "Sarah, 34, marketing manager at a 200-person SaaS company, uses the product 3x daily" — entirely invented |
| Consistent findings | All findings align perfectly with a clean narrative. Real data is messy. |
| Missing uncertainty | No confidence levels, no "we don't know", no contradictions |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Source citation requirement | Every finding must cite a specific source the user provided. No exceptions. |
| Quote verification | Every verbatim quote must trace to user-provided data. If the user did not provide interview transcripts, there are no quotes. |
| Confidence level mandate | Every finding gets High/Medium/Low confidence. If data is thin, say so. |
| Contradiction check | If all findings align too neatly, flag it. Real research has contradictions. |
| Explicit unknowns | Require an "Open Questions" section listing what the data does NOT answer. |
| Never generate synthetic data | The LLM never invents statistics, quotes, or persona attributes. If the data is not there, the finding is not there. |

### The Core Rule

**Every claim in a research synthesis must trace to something the user provided.** If the user gave 5 interview notes, findings come from those 5 interviews. If the user gave survey results, statistics come from that survey. The LLM synthesizes, interprets, and structures — it does not invent.

---

## Failure Mode 3: Generic Competitive Analysis

### What Happens

The LLM produces a competitive brief that reads like a marketing brochure mashup. Feature comparisons are based on publicly available feature lists rather than real product experience. Strengths and weaknesses are generic ("strong brand", "large customer base"). Strategic implications are obvious ("we should differentiate").

### Signatures

| Signal | Example |
|--------|---------|
| Feature list comparison | Checking boxes for "has feature X" without assessing quality or depth |
| Marketing language | Using competitors' own positioning language uncritically |
| No evidence sources | Claims without citations (customer reviews, analyst reports, real usage) |
| Balanced to the point of useless | Every competitor has "strengths and weaknesses" but nothing actionable |
| Missing "so what" | Analysis without strategic implications |
| Competitor dismissal | Downplaying competitor strengths to make our position look better |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Evidence requirement | Every claim about a competitor cites a source: customer review, analyst report, pricing page, job posting |
| Quality rating | Rate capabilities as Strong/Adequate/Weak/Absent, not just present/absent |
| Honest assessment | Rate based on real product experience and customer feedback, not marketing claims. Be honest about where competitors lead. |
| Strategic implications mandate | The brief must end with specific recommendations: build/accelerate/deprioritize, differentiate vs parity |
| Customer perspective | Frame comparison through what buyers evaluate, not internal categories |
| Shelf-life awareness | Note the date. Flag areas that change fast. Competitive analysis gets stale quickly. |

---

## Failure Mode 4: Metrics Without Context

### What Happens

The LLM presents numbers without comparison baselines, statistical awareness, or acknowledgment of uncertainty. A metric is reported as "good" or "bad" without reference to industry benchmarks, previous periods, or targets. Small fluctuations are treated as meaningful trends. Correlation is implied to be causation.

### Signatures

| Signal | Example |
|--------|---------|
| Naked numbers | "DAU is 15,000" — is that good? Bad? Up? Down? |
| False precision | "Retention improved by 0.3%" on a sample of 200 users |
| Missing sample sizes | Percentages without denominators |
| Causation claims | "We shipped feature X and retention improved" without experimental evidence |
| Cherry-picked timeframes | Choosing the period that tells the best story |
| Vanity framing | "We have 100,000 total signups!" — cumulative metric that only goes up |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Comparison mandate | Every metric shows: current value, previous period, target, benchmark |
| Sample size reporting | Always report the n. Flag small samples explicitly. |
| Statistical significance | For A/B tests: require p < 0.05. For metric movements: distinguish signal from noise. |
| Causation guard | Never claim causation from observational data. Use language like "correlated with", "coincided with", "may be related to" |
| Consistent timeframes | Same comparison period across all metrics. No mixing. |
| Rate over cumulative | Use rate metrics (DAU, weekly conversion) over cumulative (total signups ever) |
| Segment check | Always ask: does the aggregate mask segment-specific trends? |

---

## Failure Mode 5: Roadmaps Disconnected from Strategy

### What Happens

The LLM produces a feature list with dates and calls it a roadmap. Items lack strategic rationale. No connection to company goals, OKRs, or user research. The "roadmap" answers "what are we building?" but not "why are we building it?" or "what are we choosing NOT to build?"

### Signatures

| Signal | Example |
|--------|---------|
| Feature list format | Items described as features, not outcomes or opportunities |
| No "why" | Items have descriptions but no strategic justification |
| Missing non-goals | No mention of what was explicitly excluded |
| No capacity awareness | More items than the team can build, with no acknowledgment |
| No prioritization rationale | Items are listed but not ranked with defensible logic |
| No dependency mapping | Cross-team dependencies unmentioned |

### Defenses

| Defense | Implementation |
|---------|---------------|
| OKR linkage | Every item answers: "Which Key Result does this move?" |
| Theme organization | Group items under strategic themes, not just timeframes |
| Non-goals section | Explicitly list what is NOT on the roadmap and why |
| Capacity check | Compare total estimated effort against available capacity. Flag overcommitment. |
| Prioritization framework | Apply RICE, ICE, or MoSCoW with visible scores/rationale |
| Dependency mapping | List all cross-team, external, and sequential dependencies |
| "What comes off?" rule | Adding an item requires naming what is deprioritized or delayed |

---

## Failure Mode 6: Happy-Path-Only Specifications

### What Happens

The LLM describes only the successful path through a feature. Error handling, edge cases, failure modes, empty states, permission boundaries, and concurrent access scenarios are omitted. The spec looks complete because the happy path is well-described, but engineers discover gaps during implementation.

### Signatures

| Signal | Example |
|--------|---------|
| No error states | What happens when the API fails? Network timeout? Invalid input? |
| No empty states | What does the user see before any data exists? |
| No permission model | What can viewers see vs editors vs admins? |
| No concurrent access | What if two users edit the same thing simultaneously? |
| No offline/degraded behavior | What happens with poor connectivity? |
| No limits | What happens at maximum items? Maximum characters? Zero items? |

### Defenses

**Mandatory edge case checklist for every user story**:

- [ ] **Error state**: What happens when the primary action fails?
- [ ] **Empty state**: What appears before any data exists?
- [ ] **Boundary conditions**: Behavior at max/min/zero values
- [ ] **Permission variations**: Different views per role
- [ ] **Concurrent access**: Multiple users acting simultaneously
- [ ] **Undo/recovery**: Can the action be reversed?
- [ ] **Offline/degraded**: Behavior under poor connectivity
- [ ] **Loading state**: What appears during async operations?
- [ ] **Partial failure**: What if part of the operation succeeds and part fails?

---

## Failure Mode 7: Framework Regurgitation

### What Happens

The LLM dumps framework definitions (RICE, MoSCoW, JTBD, HMW, OST) as if listing them is the same as applying them. The PM gets a textbook explanation of RICE scoring instead of actual RICE scores for their specific initiatives. Frameworks are presented as templates to fill in rather than thinking tools to apply.

### Signatures

| Signal | Example |
|--------|---------|
| Framework definition instead of application | "RICE stands for Reach, Impact, Confidence, Effort..." without scoring anything |
| Multiple frameworks without selection | Listing 5 frameworks without recommending which fits this situation |
| Generic examples | "For example, a collaboration tool might..." instead of using the actual product |
| Framework as deliverable | The output IS the framework template, not a populated artifact |
| Framework shopping | Trying each framework until one gives the desired answer |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Apply, do not explain | If using RICE, produce actual scores for actual initiatives. Not a tutorial on RICE. |
| Select one framework | Choose the framework that fits the situation. Justify the choice. Do not list all options. |
| Use specific data | Populate with the user's actual numbers, products, and context. |
| Framework = means, not end | The deliverable is the prioritized list, not the framework. |
| Anti-gaming | If RICE scores do not match intuition, investigate the mismatch. Do not adjust inputs to force the desired ranking. |

---

## Failure Mode 8: Scope Creep Enablement

### What Happens

The LLM accepts every feature request and expands scope without surfacing tradeoffs. When a user says "could we also add X?" the LLM integrates X into the spec without noting the capacity impact, timeline extension, or what would need to be cut. The spec grows in every iteration.

### Signatures

| Signal | Example |
|--------|---------|
| Additive-only iteration | Every revision adds scope, nothing is ever removed |
| No tradeoff surfacing | New features accepted without capacity or timeline impact |
| Missing non-goals | The spec has no "won't do" section |
| v1 = everything | No phasing, no MVP definition, everything is "must have" |
| Stakeholder pleasing | Different stakeholders' wishes all accommodated without prioritization |

### Defenses

| Defense | Implementation |
|---------|---------------|
| "What comes off?" rule | Every scope addition requires naming what is deprioritized |
| Non-goals section | Mandatory in every spec. Reviewed after each scope change. |
| Capacity check | Total effort vs available capacity. Flag overcommitment immediately. |
| P0 challenge | "If everything is P0, nothing is P0." Challenge every must-have. |
| Phase separation | Clear v1 / v2 boundary. v2 is not "later" — it is "explicitly not now." |
| Investigation time-box | "If we cannot resolve X in 2 days, we cut it." |

---

## Cross-Cutting Defense: The Verification Habit

Across all failure modes, the root cause is the same: **the LLM generates plausible output that passes a casual read.** The defense is systematic verification at the point of generation, not after.

**Before delivering any PM artifact, verify**:

1. **Specificity test**: Could someone act on this without asking clarifying questions?
2. **Source test**: Does every factual claim trace to something the user provided?
3. **Completeness test**: Are edge cases, error states, and failure modes addressed?
4. **Tradeoff test**: Are tradeoffs made explicit, not hidden?
5. **Context test**: Are numbers presented with comparison, baseline, and uncertainty?
6. **Strategic test**: Does this connect to a goal, OKR, or strategic theme?
7. **Honesty test**: Does this acknowledge what we do not know?

If any test fails, fix it before delivering. Do not rationalize past it.
