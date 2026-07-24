# LLM HR Failure Modes

Where LLMs fail in HR contexts. Every mode in the HR skill must account for these failure modes. This reference loads with every HR task.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers HR-specific failures only.

---

## Failure Mode Categories

| Category | Risk Level | Prevalence | Detection Difficulty |
|----------|-----------|------------|---------------------|
| **Bias in language** | High | Very common | Medium — requires pattern awareness |
| **Data fabrication** | Critical | Common | Low — easy to detect if you check |
| **Compliance gaps** | Critical | Common | High — requires jurisdictional knowledge |
| **Inappropriate phrasing** | High | Very common | Medium — context-dependent |
| **False confidence** | High | Universal | High — LLMs present uncertainty as certainty |
| **Template over-reliance** | Medium | Common | Low — output feels generic |

---

## 1. Bias in Language

### Gendered Language in Job Postings

LLMs default to language patterns that discourage diverse applicants.

| Biased Term | Problem | Neutral Alternative |
|-------------|---------|-------------------|
| "Rockstar" / "Ninja" / "Guru" | Masculine-coded. Discourages women and non-binary applicants from applying. | "Expert", "Specialist", "Experienced" |
| "Aggressive" / "Dominant" | Masculine-coded. Signals adversarial culture. | "Ambitious", "Results-oriented", "Driven" |
| "Nurturing" / "Supportive" | Feminine-coded. Limits role perception. | Describe the behavior: "Mentors junior engineers" |
| "Culture fit" | Undefined proxy for "like us." Enables homogeneity. | "Values alignment" with specific, defined values |
| "Young and dynamic team" | Age discrimination signal. Illegal in many jurisdictions. | "Collaborative team" — describe the work style, not demographics |
| "Native English speaker" | National origin discrimination. Illegal. | "Fluent English" or "Strong written and verbal English" |
| "Must be willing to work long hours" | Discriminates against caregivers, disabilities. | "Ability to meet project deadlines" — focus on outcome |
| "Digital native" | Age proxy. | "Proficient with [specific tools]" |

### Inflated Requirements

LLMs generate wish lists, not requirements.

| Pattern | Problem | Fix |
|---------|---------|-----|
| "10+ years experience" for mid-level roles | Excludes career changers, fast learners. Years ≠ skill. | State the actual skill needed: "Can design distributed systems independently" |
| "CS degree required" for skills-based roles | Excludes bootcamp grads, self-taught engineers. Degree ≠ competence. | "CS degree or equivalent practical experience" |
| "Expert in [8 technologies]" | No one is expert in 8 things. Discourages qualified candidates. | "Primary expertise in 1-2: [list]. Familiarity with others is a plus." |
| "Must have startup experience" | Excludes enterprise talent who may be excellent. | "Comfortable with ambiguity and changing priorities" |

### Performance Review Bias

LLMs replicate common performance review biases.

| Bias | How LLM Manifests It | Detection | Mitigation |
|------|----------------------|-----------|------------|
| **Halo effect** | One strong accomplishment colors entire review as "Exceeds" | Check: are all competency ratings high, or just one? | Score competencies independently |
| **Similarity bias** | More positive language for people "like" the reviewer | Check: compare adjective intensity across reviews | Use SBI framework, not adjectives |
| **Recency bias** | Review content clusters around recent events | Check: are examples spread across the full review period? | Require examples from each quarter |
| **Attribution bias** | Success attributed to individuals, failure to circumstances | Check: does the same review have "she achieved" and "the project failed"? | Consistent attribution framing |
| **Gender-coded feedback** | Women: "collaborative, helpful, supportive." Men: "technical, visionary, strategic." | Check: swap names and re-read. Does the feedback still fit? | Focus on behaviors and outcomes, not traits |

---

## 2. Data Fabrication

### Compensation Data

**This is the highest-risk failure mode.** LLMs will generate plausible-sounding salary numbers that are entirely invented.

| What LLM Does | Why It's Dangerous | Prevention |
|---------------|-------------------|-----------|
| Generates specific percentile values ($185K base, $50K equity) | These numbers inform real pay decisions. Wrong numbers cause underpayment or overpayment. | Always state: "These are estimates based on training data, not current market data." |
| Cites "Glassdoor" or "Levels.fyi" with specific numbers | Numbers may be fabricated. Citation adds false credibility. | Never cite a specific number from a source without actually querying that source. |
| Presents ranges without stating data vintage | 2022 data applied to 2025 decisions. Market moves 5-15% annually. | Always state data vintage: "Based on training data through [date]. Verify with current sources." |
| Provides location-adjusted figures | Adjustment percentages may be invented or outdated | State the adjustment methodology explicitly. Better: let the user provide local data. |

**Rule: If you don't have real data, say so. Never present generated numbers as market data.**

### People Analytics

| Fabrication Risk | Example | Prevention |
|-----------------|---------|-----------|
| Generating benchmark rates | "Industry average attrition is 13.2%" | State source explicitly. If no source, say "typical ranges are X-Y% based on general HR knowledge." |
| Inventing correlation | "Our data shows a strong correlation between..." | Only state correlations present in user-provided data. Never infer from training data. |
| Hallucinating survey results | "Based on your engagement survey..." | Only reference data the user actually provided. |

---

## 3. Compliance Gaps

### Jurisdiction Sensitivity

Employment law varies by country, state, and city. LLMs default to US norms or generate jurisdiction-agnostic advice that may be illegal in the user's location.

| Topic | Jurisdiction Risk | LLM Failure Mode |
|-------|------------------|-------------------|
| **At-will employment** | US concept. Most of the world has termination protections. | Generates "at-will" language for international offers |
| **Non-compete clauses** | Unenforceable in CA. Varying enforceability elsewhere. FTC rule pending. | Includes non-competes without jurisdiction check |
| **Notice periods** | US: often none. Europe: 1-3 months. Some countries: 6 months. | Generates US-style immediate termination language |
| **Salary transparency** | Required in NYC, CO, CA, WA, and growing list. | Omits salary range from job posting |
| **Leave policies** | Parental leave: US (none federal), Europe (extensive), varies globally | Generates US-centric leave language |
| **Discrimination protections** | Protected classes vary by jurisdiction | Generates advice legal in one jurisdiction, illegal in another |
| **Data privacy** | GDPR (EU), CCPA (CA), varying global privacy laws | Suggests collecting or storing PII without privacy consideration |

**Rule: Always ask for jurisdiction before providing employment law guidance. Never default to US law.**

### Offer Letter Compliance

| Issue | LLM Failure | Correct Approach |
|-------|-------------|-----------------|
| Missing required language | Omits at-will disclaimer, arbitration clause, EEOC statement | Use company's legal-approved template as the base |
| Implied contract | "We expect you to be here for at least 2 years" creates implied contract | Avoid duration implications unless it's a fixed-term contract |
| Benefit promises | "You will receive full benefits" when there's a waiting period | Specify enrollment dates, waiting periods, plan options |
| Equity promises | "Your options will be worth $X" | "Subject to board approval. Value is not guaranteed." |

### PIP and Termination

| Risk | LLM Failure | Correct Approach |
|------|-------------|-----------------|
| Discriminatory timing | PIP issued right after employee announces pregnancy/disability | Establish documented performance concerns well before protected event |
| Vague success criteria | "Improve your work quality" — unmeasurable, undefendable | Specific, measurable, time-bound criteria |
| Retaliation appearance | PIP after employee filed HR complaint | Ensure HR/legal review for any performance action near protected activity |
| Inconsistent application | PIP for one employee but not another with same performance | Document policy: same standards applied to all employees |

---

## 4. Inappropriate Phrasing

### Performance Review Language

| Inappropriate | Why | Better |
|-------------|-----|--------|
| "She is very emotional" | Gendered, personality-based, not behavioral | "Expressed frustration during the sprint review, which disrupted the discussion" |
| "He's not a culture fit" | Vague, potentially discriminatory | "Did not follow the team's code review process in 4 of 6 sprints" |
| "Natural leader" | Implies some people aren't natural leaders (coded) | "Organized the incident response, assigned roles, and led the post-mortem" |
| "Aggressive" (about a woman) | Disproportionately applied to women. Same behavior in men = "assertive." | "Advocated strongly for the architectural change in the design review" |
| "Surprisingly technical" | Implies expectation of low competence (often gendered/racial) | "Demonstrated strong technical depth in the system design review" |
| "Doesn't speak up enough" | Penalizes introverts. Communication ≠ volume. | "When [person] shares input, it's high quality. Finding more venues for contribution would increase impact." |
| "Works too hard" | Not a development area. Masks burnout concern. | "I've noticed 60+ hour weeks. Let's discuss workload sustainability." |

### Offer Letter Language

| Inappropriate | Why | Better |
|-------------|-----|--------|
| "We're like a family" | Creates implied obligation, blurs professional boundaries | "We're a collaborative team that supports each other" |
| "Fast-paced, high-intensity" | Signals unsustainable work expectations | "We ship frequently and iterate quickly" |
| "Unlimited PTO" without guidance | In practice people take less PTO. Companies save on accrual liability. | State minimum expected PTO usage: "We expect you to take at least X days" |

### Org Planning Language

| Inappropriate | Why | Better |
|-------------|-----|--------|
| "Move Alice because she's difficult" | Person-based org design, masks management failure | "Restructure the team around the authentication domain, not current reporting lines" |
| "Low performers in this team" | Labels people without evidence | "Three employees have been below target on sprint delivery for 2+ quarters" |
| "Right-sizing" | Euphemism for layoffs. Everyone sees through it. | "Headcount reduction of X positions due to [specific business reason]" |
| "Redundant roles" (without evidence) | Assumes without analysis | "These two roles have 80% task overlap based on job analysis" |

---

## 5. False Confidence

### Patterns

| Pattern | Example | Harm | Fix |
|---------|---------|------|-----|
| Stating opinions as facts | "The market rate for this role is $X" | User takes fabricated data as truth | "Based on general industry knowledge, ranges typically fall between $X-$Y. Verify with current market data." |
| Omitting uncertainty | "This org structure will improve velocity by 20%" | User expects guaranteed outcome | "Based on industry benchmarks, teams with 5-8 direct reports tend to have higher velocity. Measure after 90 days." |
| Overconfident legal advice | "Non-competes are unenforceable" | Varies by jurisdiction. Bad advice. | "Non-compete enforceability varies significantly by jurisdiction. Consult legal counsel for your specific location." |
| Definitive policy interpretation | "Your PTO policy means you can take 3 weeks" | Policy language may be ambiguous | "Based on the policy text you shared, it appears to allow X. Confirm with your HR team." |

---

## 6. Template Over-Reliance

### Problem

LLMs generate templates that look professional but carry no domain insight. A performance review template with "[insert specific example]" placeholders is not a performance review — it's a word processor.

### Detection

| Signal | What It Means |
|--------|-------------|
| Output is >80% boilerplate | Template, not analysis. No domain knowledge applied. |
| All examples are generic | "Improved team productivity" — which team, what productivity, by how much? |
| Structure is perfect, content is empty | The skeleton is the easy part. Filling it with insight is the job. |
| Same template regardless of role/level/context | Junior IC review looks identical to VP review |

### Mitigation

- Always ask clarifying questions before generating HR content
- Incorporate user-provided context into every section (not just the placeholders)
- Flag sections where the user needs to supply specific data
- Prefer fewer sections with real content over many sections with boilerplate

---

## Pre-Output Checklist

Run every HR output through these checks before delivering.

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Bias scan | No gendered, ageist, or exclusionary language |
| 2 | Data sourcing | All numbers sourced or flagged as estimates |
| 3 | Jurisdiction | Location-dependent advice identifies jurisdiction or asks |
| 4 | Legal disclaimer | Documents requiring legal review are flagged |
| 5 | PII minimization | Names/salaries used only when necessary, not casual |
| 6 | Behavioral language | All feedback describes behavior, not personality |
| 7 | Template quality | Content is specific to the user's context, not generic |
| 8 | Confidence calibration | Uncertainty stated explicitly, not hidden |
| 9 | Compliance flags | Offer letters, PIPs, termination language flagged for legal review |
| 10 | Source vintage | Data freshness stated where applicable |
