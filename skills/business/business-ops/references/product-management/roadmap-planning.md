# Roadmap Planning Reference

Deep reference for roadmap creation, updates, and prioritization. Loaded by ROADMAP mode.

---

## Roadmap Frameworks

### Now / Next / Later

The simplest and most effective format for most teams.

| Horizon | Timeframe | Confidence | Content |
|---------|-----------|-----------|---------|
| **Now** | Current sprint/month | High — committed | Active work. Scoped. Owners assigned. |
| **Next** | 1-3 months | Medium — planned | Prioritized, not started. Good confidence in what, less in when. |
| **Later** | 3-6+ months | Low — directional | Strategic bets and opportunities. Scope and timing flexible. |

**When to use**: Most teams, most of the time. Avoids false precision on dates. Good for leadership and external communication.

**Failure modes**: Treating "Later" as a dumping ground. Items in Later should still tie to strategy — they are directional bets, not a wish list.

### Quarterly Themes

2-3 themes per quarter representing strategic investment areas.

```
Q3 2026 Themes:
├── Enterprise Readiness
│   ├── SSO / SAML support
│   ├── Audit logging
│   └── Role-based access control
├── Activation Improvements
│   ├── Guided onboarding v2
│   ├── Template gallery
│   └── First-run experience redesign
└── Platform Extensibility
    ├── Public API v2
    └── Webhook improvements
```

**When to use**: When you need strategic alignment visibility. Good for planning meetings and executive communication.

**Failure modes**: Themes that are too broad ("Make product better") or too narrow (a single feature disguised as a theme).

### OKR-Aligned Roadmap

Map items directly to Objectives and Key Results.

| Objective | Key Result | Initiatives | Expected Impact |
|-----------|-----------|------------|----------------|
| Make product indispensable for daily workflows | Increase DAU/MAU from 0.35 to 0.50 | Notification improvements, mobile app, quick actions | +0.08 DAU/MAU |
| | Increase D30 retention from 40% to 55% | Onboarding v2, activation flow, email re-engagement | +10pp retention |

**When to use**: Organizations that run on OKRs. Creates clear accountability between what you build and what you measure.

**Failure modes**: Initiatives without expected impact estimates. If you cannot estimate impact, the link to the KR is speculative.

### Timeline / Gantt

Calendar-based view showing start dates, end dates, durations, parallelism, and dependencies.

**When to use**: Execution planning with engineering. Identifying scheduling conflicts.

**When NOT to use**: External communication. Creates false precision expectations. "Shipping SSO on March 15" becomes a promise.

---

## Prioritization Frameworks

### RICE Score

**Formula**: (Reach x Impact x Confidence) / Effort

| Dimension | Definition | Scale |
|-----------|-----------|-------|
| **Reach** | Users/customers affected in a time period | Concrete numbers (e.g., 500/quarter) |
| **Impact** | Needle movement per person reached | 3=massive, 2=high, 1=medium, 0.5=low, 0.25=minimal |
| **Confidence** | How confident in reach + impact estimates | 100%=data-backed, 80%=some evidence, 50%=gut feel |
| **Effort** | Person-months (eng + design + all functions) | Concrete estimate |

**When to use**: Large backlog, need quantitative defensibility.

**Failure modes**: Gaming confidence scores to make preferred initiatives win. If RICE does not match intuition, investigate why — do not adjust inputs until it does.

### ICE Score

**Formula**: Impact x Confidence x Ease (each 1-10)

Simpler than RICE. Ease is inverse of effort (higher = easier to build).

**When to use**: Quick prioritization. Early-stage products. Insufficient data for RICE.

### MoSCoW

| Category | Definition | Decision Test |
|----------|-----------|---------------|
| **Must** | Roadmap fails without these. Non-negotiable. | "Would the quarter be a failure without this?" |
| **Should** | Important and expected. Delivery viable without. | High-priority fast follows. |
| **Could** | Desirable. Lower priority. | Include only if capacity allows. |
| **Won't** | Explicitly out of scope this period. | List for clarity. |

**When to use**: Scoping a release or quarter. Forcing prioritization conversations with stakeholders.

### Value vs Effort Matrix

| | Low Effort | High Effort |
|---|---|---|
| **High Value** | Quick Wins — do first | Big Bets — plan carefully |
| **Low Value** | Fill-ins — spare capacity | Money Pits — do not do |

**When to use**: Visual prioritization in team sessions. Building shared understanding of tradeoffs.

---

## OKR Alignment

### Writing Product OKRs

**Objectives**: Qualitative, aspirational, time-bound (quarterly/annually), directional.

**Key Results**: Quantitative, specific, time-bound, outcome-based (not output-based), 2-4 per Objective.

| Weak KR | Problem | Strong KR |
|---------|---------|-----------|
| "Launch onboarding v2" | Output, not outcome | "Increase activation rate from 30% to 50%" |
| "Ship 10 features" | Activity, not impact | "3 core workflows achieve >80% task completion" |
| "Improve NPS" | No target, no timeline | "Increase NPS from 32 to 45 by end of Q3" |

**Scoring**: 0.0-0.3 = missed, 0.4-0.6 = progress, 0.7-1.0 = achieved. 70% completion is the target for stretch OKRs.

**Failure modes**:
- Too many OKRs (2-3 objectives max)
- KRs that are sandbagged (100% confidence = not ambitious enough)
- KRs that measure effort instead of results
- Not reviewing at mid-period
- Not grading honestly at end of period

### Roadmap-to-OKR Mapping

Every roadmap item should answer: "Which Key Result does this move?"

Items that cannot answer this question are one of:
1. **Strategically orphaned** — cut them or justify with a separate rationale
2. **Infrastructure/tech debt** — legitimate but frame as enabling future KRs
3. **Reactive work** — customer escalations, compliance requirements (acceptable, but track the ratio)

**Healthy ratio**: 70%+ of roadmap items directly tied to OKRs. 20% tech health. 10% unplanned buffer.

---

## Dependency Mapping

### Dependency Types

| Type | Description | Example | Risk Level |
|------|------------|---------|-----------|
| Technical | Feature B requires infra from Feature A | "API v2 needs auth service refactor" | Medium |
| Team | Requires work from another team | "Need design review from Design team" | High |
| External | Waiting on vendor, partner, third party | "Stripe Connect certification" | Very High |
| Knowledge | Need research/investigation results first | "User testing results before building flow" | Medium |
| Sequential | Must ship A before starting B | "Billing integration before usage-based pricing" | Medium |

### Managing Dependencies

| Rule | Implementation |
|------|---------------|
| List explicitly | Every dependency visible in roadmap |
| Assign owner | Someone responsible for resolving each dependency |
| Set "need by" date | When does the dependent item need this resolved? |
| Build buffer | Dependencies are highest-risk items. Pad them. |
| Flag cross-team early | Cross-team coordination requires lead time |
| Contingency plan | What if the dependency slips? |

### Reducing Dependencies

Before accepting a dependency, ask:
- Can we build a simpler version that avoids it?
- Can we parallelize with an interface contract or mock?
- Can we sequence differently to move the dependency earlier?
- Can we absorb the work into our team?

---

## Capacity Planning

### Estimating Capacity

```
Raw capacity = engineers x days in sprint
Overhead = meetings + on-call + interviews + holidays + PTO
Available capacity = Raw capacity - Overhead
Planned capacity = Available capacity x 0.65 (60-70% rule)
```

### Allocation Model

| Category | % | Purpose |
|----------|---|---------|
| Planned features | 70% | Roadmap items advancing strategic goals |
| Technical health | 20% | Tech debt, reliability, performance, DX |
| Unplanned | 10% | Buffer for urgent issues, quick wins, requests |

**Adjustments by context**:

| Situation | Shift |
|-----------|-------|
| New product | More features, less tech debt |
| Mature product | More tech debt and reliability |
| Post-incident | More reliability, fewer features |
| Rapid growth | More scalability and performance |

### Capacity vs Ambition

- If commitments exceed capacity, something must give
- Do not solve capacity problems by pretending people can do more — cut scope
- When adding to roadmap, always ask "What comes off?"
- Commit to fewer things and deliver reliably > overcommit and disappoint

---

## Communicating Roadmap Changes

### Change Triggers

- New strategic priority from leadership
- Customer feedback / research that changes priorities
- Technical discovery that changes estimates
- Dependency slip from another team
- Resource change (team grows, shrinks, key person leaves)
- Competitive move requiring response

### Communication Framework

| Step | Action |
|------|--------|
| 1. Acknowledge | Be direct about what is changing and why |
| 2. Explain | What new information drove this decision? |
| 3. Show tradeoff | What was deprioritized? What slips? |
| 4. Present new plan | Updated roadmap with changes reflected |
| 5. Acknowledge impact | Who is affected? Stakeholders expecting deprioritized items hear it directly. |

### Avoiding Roadmap Whiplash

- Do not change for every piece of new information. Have a threshold.
- Batch updates at natural cadences (monthly, quarterly) unless truly urgent.
- Distinguish "roadmap change" (strategic reprioritization) from "scope adjustment" (normal execution refinement).
- Track change frequency. Frequent changes may signal unclear strategy, not responsiveness.

---

## Theme-Based Planning

### Building Themes

Themes represent strategic investment areas, not individual features.

**Good theme characteristics**:
- Tied to a business outcome or user need cluster
- Broad enough to contain multiple initiatives
- Narrow enough to be a coherent narrative
- Communicates WHY you are investing, not just WHAT you are building

| Bad Theme | Why | Good Theme |
|-----------|-----|-----------|
| "Build stuff" | No strategic signal | "Enterprise readiness" |
| "SSO" | Too narrow (single feature) | "Security and compliance foundations" |
| "Make users happy" | Too vague, no direction | "Reduce time-to-first-value for new users" |

### Theme-to-Initiative Mapping

```
Theme: Reduce time-to-first-value for new users
├── Guided onboarding flow (Now)
├── Template gallery (Now)
├── Sample data environment (Next)
├── Onboarding email sequence (Next)
└── AI-assisted setup (Later)
```

Each initiative under a theme inherits the strategic rationale. When stakeholders ask "why are we building X?" the answer is the theme.

### Balancing Themes

- 2-3 themes per quarter (max)
- Themes should be roughly balanced in investment unless explicitly stated otherwise
- At least one theme should address existing user retention/satisfaction (not all new growth)
- Review theme balance against business priorities each quarter

---

## Roadmap Review Cadences

| Cadence | Purpose | Depth | Attendees |
|---------|---------|-------|-----------|
| Weekly | Execution check, surface blockers | Status updates on Now items | PM + eng lead |
| Monthly | Trend review, priority adjustments | Now/Next reprioritization | Product team + stakeholders |
| Quarterly | Strategic review, OKR scoring, next-quarter planning | Full roadmap reassessment | Product + eng + design + leadership |

### Quarterly Planning Process

1. **Score** — Grade previous quarter OKRs honestly
2. **Review** — What worked, what did not, what changed
3. **Input** — Gather strategic context: company priorities, customer feedback, competitive intel, tech debt backlog
4. **Draft** — Propose themes, initiatives, and OKRs for next quarter
5. **Negotiate** — Stakeholder review, capacity check, priority tradeoffs
6. **Commit** — Finalize roadmap and OKRs, communicate broadly
