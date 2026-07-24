# Competitive Intelligence Reference

Competitive analysis framework, battlecard structure, positioning strategy, and landmine question design. The goal: help sellers win deals against specific competitors with evidence-based positioning.

---

## Competitive Research Protocol

### Research Checklist Per Competitor

Run these searches for each competitor. Mark each as completed or "not publicly available."

| Research Area | Search Queries | What to Extract |
|--------------|---------------|-----------------|
| Product | "[Competitor] product features" | Core capabilities, recent additions, gaps |
| Pricing | "[Competitor] pricing" | Model (per seat, usage, flat), tiers, enterprise pricing |
| Positioning | "[Competitor] about" site:competitor.com | How they describe themselves, target market, value props |
| Recent releases | "[Competitor] changelog OR product updates OR releases" (90 days) | What they shipped, direction signals |
| Reviews | "[Competitor] reviews G2 OR Capterra OR TrustRadius" | Customer sentiment, common complaints, praised features |
| Customers | "[Competitor] customers" OR "[Competitor] case study" | Logos, industries, use cases |
| Hiring | "[Competitor] careers" | Growth areas (hiring for X = investing in X) |
| Funding | "[Competitor] funding crunchbase" | Stage, amount, investors, runway signals |
| Comparisons | "[Competitor] vs" | Third-party comparisons, feature matrices |
| Weaknesses | "[Competitor] problems OR issues OR limitations" | Known issues, migration stories |

### Source Quality Hierarchy

| Source | Trust Level | Notes |
|--------|------------|-------|
| Competitor's own website/docs | High for features, low for weaknesses | They don't advertise limitations |
| G2/Capterra verified reviews | High | Real users, verified purchase |
| Independent analyst reports | High | Gartner, Forrester have methodology |
| Customer case studies | Medium | Self-selected success stories |
| Reddit/HN discussions | Medium | Authentic but anecdotal |
| Blog comparisons | Low-Medium | Often affiliate-driven or outdated |
| Your sales team's field intel | High for deal context | But may have confirmation bias |

**Never cite a source you did not find in search results.** If a claim cannot be sourced, mark it as "unverified field intel" or drop it.

---

## Battlecard Structure

One battlecard per competitor. Each battlecard follows this structure.

### 1. Competitor Profile

| Field | Content |
|-------|---------|
| Company | Name, website |
| Founded | Year |
| Funding | Stage + total raised |
| Employees | Count or range |
| Target Market | Who they sell to (size, industry, role) |
| Pricing Model | How they charge |
| Market Position | Leader / Challenger / Niche / Emerging |

### 2. What They Sell

2-3 sentences. What their product does, who it serves, how they position it. Use their own language (from their website) to show you understand their pitch.

### 3. Recent Releases (Last 90 Days)

| Date | Release | Strategic Signal |
|------|---------|-----------------|
| [Date] | [Feature/Product] | [What this tells you about their direction] |

Each release tells you where they're investing. Multiple releases in one area = strategic priority. No releases in an area = potential weakness or deprioritization.

### 4. Where They Win

Be honest. Credibility with prospects comes from acknowledging competitor strengths.

| Area | Their Advantage | Your Counter |
|------|----------------|-------------|
| [Area] | [Specific strength with evidence] | [How to handle when prospect raises it] |

**Counter strategies**:
- **Acknowledge and redirect**: "You're right, they're strong in X. The question is whether X is the critical factor for your use case."
- **Reframe the criteria**: "X matters, but [related capability] is where most teams spend their time."
- **Concede and differentiate**: "They do X well. Where we differ is Y, which [evidence] shows matters more for [their situation]."

### 5. Where You Win

| Area | Your Advantage | Proof Point |
|------|---------------|-------------|
| [Area] | [Specific strength] | [Customer quote, metric, case study] |

Proof points must be real. Verifiable customer results. Named companies (with permission). Specific metrics. If no proof point exists for a claimed advantage, mark it as "advantage without public proof point."

### 6. Pricing Intelligence

| Dimension | Their Model | Your Model | Positioning |
|-----------|-----------|-----------|------------|
| Base pricing | [Their price point or model] | [Your price point] | [How to discuss] |
| Hidden costs | [Implementation, training, add-ons] | [Your all-in cost] | [Surface their hidden costs] |
| Contract terms | [Length, exit clauses] | [Your terms] | [Flexibility advantage if applicable] |
| Discounting | [Known discount patterns] | [Your approach] | [Don't race to bottom] |

If competitor pricing is not publicly available, state "not publicly listed" rather than guessing. Guessed pricing destroys credibility if the prospect knows the real number.

### 7. Talk Tracks

Scenario-based positioning for different deal situations.

**When they come up early in evaluation**:
```
Acknowledge them. Position the evaluation criteria. "Good company to evaluate.
Here's what I'd suggest looking at when you compare us: [your strong dimensions].
Most teams in your situation find [dimension] is what separates the options."
```

**When prospect currently uses them (displacement)**:
```
Don't badmouth. Ask about their experience. "What's working well? Where do you
wish it did more?" Let them articulate the gaps. Then connect those gaps to your
strengths. Never say "they can't do X" -- say "teams that need X usually find..."
```

**When added late to evaluation (you're the incumbent threat)**:
```
Emphasize switching cost, relationship depth, and roadmap alignment. "You've
invested in [your product]. Here's what we're building toward [roadmap]. The
question is whether the delta justifies the migration cost and timeline."
```

### 8. Objection Handling

| Objection | Response |
|-----------|---------|
| "Competitor is cheaper" | [Reframe to TCO: implementation, training, ongoing cost. Or: "What's included at that price?"] |
| "Competitor has [feature]" | [If true: acknowledge and redirect. If partial: clarify scope. If false: correct gently with source.] |
| "Competitor is bigger/more established" | [Reframe: size != fit. Your advantage in [responsiveness/focus/speed].] |
| "We already use Competitor" | [Ask about gaps. Quantify friction. Propose parallel evaluation or phased migration.] |

### 9. Landmine Questions

Questions that expose competitor weaknesses without badmouthing. Ask these during discovery or evaluation to set criteria in your favor.

**Design principle**: A landmine question asks the prospect to evaluate a dimension where you're strong and the competitor is weak. The prospect discovers the gap themselves.

| Your Strength | Their Weakness | Landmine Question |
|--------------|---------------|------------------|
| [Capability] | [Their gap] | "How important is [capability] to your evaluation?" |
| [Performance] | [Their limitation] | "What performance requirements do you have for [dimension]?" |
| [Integration] | [Their ecosystem gap] | "Which tools in your stack need to integrate with this?" |
| [Support] | [Their support model] | "What level of support does your team need during implementation?" |
| [Security] | [Their compliance gap] | "What compliance certifications are required for your organization?" |

**Rules for landmine questions**:
- Frame as discovery questions, not gotchas
- Never mention the competitor in the question
- Let the prospect connect the dots
- Have follow-up questions ready when they answer
- If they don't know, it's still useful: "Worth checking with [Competitor] how they handle this"

---

## Comparison Matrix Design

Build a feature-level comparison grid for the user's reference.

### Matrix Structure

| Category | Capability | You | Competitor A | Competitor B |
|----------|-----------|-----|-------------|-------------|
| [Core] | [Feature 1] | [Status] | [Status] | [Status] |
| [Core] | [Feature 2] | [Status] | [Status] | [Status] |
| [Advanced] | [Feature 3] | [Status] | [Status] | [Status] |
| [Integration] | [Feature 4] | [Status] | [Status] | [Status] |

### Status Values

| Status | Meaning | Display |
|--------|---------|---------|
| Full | Feature exists, mature, no caveats | Green check |
| Partial | Feature exists with limitations | Yellow circle |
| Beta | Feature exists but not production-ready | Orange dot |
| Roadmap | Planned but not shipped | Gray clock |
| None | Not available | Red X |
| Unknown | Cannot determine from public sources | Question mark |

**Honesty rules**:
- Mark your own features honestly (Partial is better than lying about Full)
- Mark competitor features at their strongest interpretation from public sources
- Mark "Unknown" rather than guessing "None"
- Include categories where competitors are stronger

---

## Win/Loss Analysis Framework

When the user has win/loss data (from CRM or experience), analyze for patterns.

### Win Pattern Analysis

| Dimension | What to Analyze |
|-----------|----------------|
| Deal size | Do you win more often in certain deal sizes? |
| Industry | Are certain verticals stronger for you? |
| Buyer persona | Which roles champion you? |
| Entry point | How did the deal start? (Inbound, outbound, referral) |
| Evaluation criteria | Which criteria predict your wins? |
| Competitor | Which competitors do you beat consistently? |

### Loss Pattern Analysis

| Dimension | What to Analyze |
|-----------|----------------|
| Loss reason | Price, features, relationship, timing, status quo? |
| Stage of loss | Early disqualification vs late-stage loss? |
| Competitor | Which competitor wins the deals you lose? |
| Missing capability | What feature/capability gap caused the loss? |
| Process | Did you have access to decision maker? |

### Pattern-to-Action Mapping

| Pattern | Action |
|---------|--------|
| Consistently lose on price to Competitor X | Reframe to TCO. Develop pricing counter-talk track. |
| Win when Champion is [Role] | Target that role in prospecting. |
| Lose when evaluation starts at [feature] | Set evaluation criteria early. Plant landmines before formal eval. |
| Win in [Industry], lose in [Industry] | Focus GTM on strong verticals. Develop weak-vertical playbook. |

---

## Competitive Monitoring Cadence

| Activity | Frequency | What to Check |
|----------|-----------|--------------|
| Product page scan | Monthly | New features, messaging changes |
| Pricing page check | Monthly | Pricing model changes, new tiers |
| G2/Capterra reviews | Monthly | New reviews, trend changes, competitor response |
| Job postings | Monthly | New roles signal investment areas |
| News/press | Weekly (automated) | Announcements, funding, partnerships |
| Changelog/blog | Bi-weekly | Product releases, strategic direction |
| Analyst reports | Quarterly | Market positioning shifts |
| Win/loss review | Quarterly | Pattern updates from recent deals |

---

## Positioning Strategy Frameworks

### Two-Dimensional Positioning Map

Pick two dimensions where you can differentiate. Plot yourself and competitors.

Common dimension pairs:
- Ease of use vs. Power/Depth
- Price vs. Feature completeness
- Speed to deploy vs. Customizability
- Point solution vs. Platform
- SMB-focused vs. Enterprise-focused

The goal: find dimensions where you occupy a unique position. If you're in the same quadrant as a competitor, you're competing on execution, not positioning.

### Category Creation

When you can't win in an existing category, define a new one.

| Existing Category | Category Creation | Positioning Advantage |
|------------------|-------------------|---------------------|
| "CRM" | "Revenue Intelligence Platform" | Shifts from feature comparison to vision |
| "Project Management" | "Work OS" | Broadens scope beyond direct competitors |
| "Monitoring" | "Observability Platform" | Reframes the problem |

Category creation works when: you have a genuine capability expansion, the prospect has needs beyond the existing category, the new category has enough market validation to not seem made up.

Category creation fails when: it's just relabeling the same product, the prospect thinks in the existing category, you can't deliver on the broader promise.

---

## Competitive Intelligence Ethics

| Do | Don't |
|----|-------|
| Use public information | Use stolen/leaked confidential data |
| Acknowledge competitor strengths | Fabricate competitor weaknesses |
| Ask prospects about their experience | Pressure prospects to share competitor pricing |
| Position on your merits | Badmouth competitors by name |
| Cite verified reviews | Cherry-pick unrepresentative reviews |
| Update battlecards with real field data | Invent customer quotes or results |
