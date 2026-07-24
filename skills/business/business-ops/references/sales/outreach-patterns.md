# Outreach Patterns Reference

Personalized outreach frameworks, anti-template patterns, channel selection, and follow-up sequences. The core principle: research first, draft second. Generic outreach is noise.

---

## The Anti-Template Principle

Templates are the enemy of effective outreach. A template-shaped email triggers the prospect's spam filter (mental and literal) because it reads like every other sales email.

**The test**: Could this email opening apply to any prospect at any company? If yes, it is a template. Rewrite it.

| Template-Shaped (Bad) | Research-Driven (Good) |
|----------------------|----------------------|
| "I hope this email finds you well" | [Delete this line entirely] |
| "I noticed you work at Company" | "Saw Company's Series B announcement last week" |
| "Congrats on your new role" | "Congrats on the VP Eng role -- saw you came from Stripe's platform team" |
| "I'm reaching out because we help companies like yours" | "Your CTO mentioned scaling challenges in that Podcast X interview" |
| "We're an AI-powered platform that helps..." | [Lead with their problem, not your product] |
| "I wanted to introduce myself" | [Nobody cares who you are yet. Lead with value.] |

---

## Personalization Hierarchy

Hooks ranked by effectiveness. Use the highest-tier hook available.

### Tier 1: Trigger Events (Most Effective)

A trigger event is a change that creates urgency or relevance.

| Trigger | Why It Works | Example Opening |
|---------|-------------|----------------|
| Funding round | New capital = new priorities, new hires, new projects | "With the Series C closing last month, curious how you're thinking about [topic]" |
| Leadership hire | New leader = new direction, eager to make impact | "Saw you joined as VP Engineering -- teams I work with in their first 90 days often..." |
| Product launch | Signals priorities and investment areas | "Noticed the launch of [Product Feature]. Teams scaling [related capability] often..." |
| Acquisition | Integration creates new problems | "With the [Company] acquisition closing, integration planning usually surfaces..." |
| Earnings mention | Public signal of strategic priorities | "In last quarter's earnings, [CEO] mentioned [priority]. That's where..." |
| Job posting | Hiring for X = investing in X | "Saw you're hiring [X]. Teams building that capability often need..." |

### Tier 2: Mutual Connections

| Connection Type | Opening Pattern |
|----------------|----------------|
| Shared contact | "[Name] mentioned you'd be a good person to talk to about [topic]" |
| Shared company | "We overlapped at [Company] -- I was in [department] from [years]" |
| Shared school | Brief mention only if natural. Don't force it. |
| Shared community | "Enjoyed your post in [community/forum] about [topic]" |

### Tier 3: Their Content

| Content Type | Opening Pattern |
|-------------|----------------|
| Blog post | "Your piece on [topic] resonated -- especially [specific point]" |
| Podcast appearance | "Caught your episode on [podcast]. Your point about [X] stuck with me" |
| Conference talk | "Saw your talk at [event] on [topic]. The point about [X] was spot on" |
| LinkedIn post | "Your post about [topic] sparked a thought about [related angle]" |

### Tier 4: Company Initiative

| Signal | Opening Pattern |
|--------|----------------|
| Strategic initiative | "Noticed [Company] is investing in [initiative]" |
| Industry trend | "Teams in [industry] are dealing with [trend]. Curious how it's affecting [Company]" |
| Regulatory change | "[Regulation] is changing the game for [industry]. Wondering how you're approaching..." |

### Tier 5: Role-Based Pain (Last Resort)

Use only if Tiers 1-4 yield nothing. Least personal but still better than no personalization.

| Role | Common Pain | Opening Pattern |
|------|-------------|----------------|
| VP Engineering | Team productivity, technical debt, hiring | "Engineering leaders I talk to are spending [X%] of time on [pain]" |
| CTO | Architecture decisions, scaling, security | "CTOs scaling from [stage] to [stage] often hit [specific challenge]" |
| VP Sales | Pipeline quality, forecast accuracy, rep productivity | "Sales leaders in [industry] are seeing [specific trend]" |
| CFO | Spend visibility, vendor consolidation, ROI justification | "Finance teams consolidating vendors often discover [insight]" |

---

## Email Construction Rules

### Structure: AIDA (Attention, Interest, Desire, Action)

| Section | Purpose | Max Length | Rule |
|---------|---------|-----------|------|
| Subject line | Get the email opened | Under 50 chars | No spam words (free, guaranteed, act now). Personalized. |
| Opening | Prove you researched them | 1-2 sentences | Must reference specific research finding |
| Interest | Connect to their problem | 1-2 sentences | Their challenge, not your product |
| Desire | Brief proof point | 1 sentence | Similar company, specific result |
| CTA | One clear ask | 1 sentence | Low-friction. Question format. |

Total email: under 150 words. 5 sentences is ideal. 7 sentences is the hard max.

### Subject Line Patterns

| Pattern | Example | When to Use |
|---------|---------|-------------|
| [Their initiative] + [angle] | "Notion's AI scaling + a thought" | Trigger event available |
| Question format | "How [Company] handles [X]?" | Research reveals gap |
| Mutual connection | "[Name] suggested I reach out" | Warm intro available |
| Specific + short | "Re: your [conference] talk" | Content-based hook |

**Subject line failure modes** (cause low open rates):

| Bad Subject | Why It Fails |
|------------|-------------|
| "Quick question" | Overused. Feels manipulative. |
| "Touching base" | No value signal. Screams sales. |
| "Partnership opportunity" | Vague. Every spam email says this. |
| "I'd love to connect" | Nobody opens this. |
| "[Company] + [Your Company]" | Only works if your brand is known to them |
| ALL CAPS or excessive punctuation | Spam filter trigger |

### Formatting Rules

| Rule | Reason |
|------|--------|
| No markdown (no **bold**, no *italic*) | Renders as literal asterisks in many email clients |
| No HTML headers or bullet formatting | Plain text looks natural, formatted text looks templated |
| Short paragraphs (2-3 sentences) | Mobile readability. Most email is read on phones. |
| Plain dashes for lists | Renders correctly everywhere |
| No images or logos in cold outreach | Triggers spam filters. Adds load time. |
| No tracking pixels in first touch | Builds trust. Some prospects notice tracking. |

---

## Channel Selection Logic

```
1. Verified email available?
   YES -> Email preferred (higher response rate for cold outreach)
         Also prepare LinkedIn backup for follow-up
   NO  -> Go to step 2

2. LinkedIn profile found?
   YES -> LinkedIn connection request (no pitch)
         Follow-up message template for after connection
   NO  -> Go to step 3

3. Warm intro possible?
   YES -> Suggest mutual connection outreach first
         Draft message for the connector
   NO  -> Company website contact form (lowest priority)
```

### Channel-Specific Rules

| Channel | Length Limit | Tone | Structure |
|---------|-------------|------|-----------|
| Cold email | 150 words | Professional, direct | AIDA |
| LinkedIn connection request | 300 chars | Casual, no pitch | Personal hook + "would love to connect" |
| LinkedIn follow-up message | 200 words | Conversational | Value-first, then soft transition to why |
| Warm intro request | 100 words | Brief for the connector | Context for connector + what you'd like to discuss |

---

## Follow-Up Sequence Design

### Timing

| Touch | Timing | Purpose |
|-------|--------|---------|
| Initial email | Day 0 | Full AIDA outreach |
| Follow-up 1 | Day 3 | New angle. Not "just checking in." |
| Follow-up 2 | Day 7 | Different value prop or proof point |
| Follow-up 3 | Day 14 | Break-up email (creates urgency through scarcity) |
| LinkedIn touch | Day 5-10 | Parallel channel. Connection request or engage with their content. |

### Follow-Up Failure Modes

| Bad Follow-Up | Why It Fails | Instead |
|--------------|-------------|---------|
| "Just following up" | No new value. Feels like nagging. | Add new information, angle, or resource. |
| "Bumping this to the top of your inbox" | Patronizing. They saw it. | Offer a different reason to engage. |
| "Did you get my last email?" | Passive-aggressive. | New angle, acknowledge they're busy. |
| Same message resent | Lazy. Obviously automated. | Each follow-up must add new value. |
| "I know you're busy but..." | Undermines your importance. | Lead with value, not apology. |

### Follow-Up Templates by Touch

**Day 3 -- New Angle**:
```
Hi [Name],

[New piece of information: recent article, case study, data point].

Thought this might be relevant given [their situation].

[Same CTA from original email, rephrased].

[Signature]
```

**Day 7 -- Different Proof**:
```
Hi [Name],

[Different customer story or result]. They were dealing with
[similar challenge to prospect].

Happy to share how they approached it if useful.

[Signature]
```

**Day 14 -- Break-Up**:
```
Hi [Name],

Haven't heard back, so I'll assume the timing isn't right.

If [topic] becomes a priority, happy to reconnect.

[Signature]
```

The break-up email consistently has the highest response rate in the sequence because it removes pressure.

---

## Scenario-Specific Templates

### Cold Outreach (No Prior Relationship)

```
Subject: [Their initiative] + [your angle]

Hi [Name],

[Personal hook from Tier 1-3 research].

[1 sentence on their likely challenge based on role/company].

[Brief proof: "We helped [Similar Company] achieve [Result]".]

Worth a 15-min call to see if relevant?

[Signature]
```

### Warm Outreach (Mutual Connection / Prior Meeting)

```
Subject: Following up from [context]

Hi [Name],

[Reference how you know them or who connected you].

[Why reaching out now -- their trigger event].

[Specific value you can offer].

[Low-friction CTA]

[Signature]
```

### Re-Engagement (Went Dark)

```
Subject: [Short, curiosity-driven]

Hi [Name],

[Acknowledge time passed. No guilt.]

[New reason to reconnect -- their news or your news].

[Simple question to reopen dialogue]

[Signature]
```

### Post-Event Follow-Up

```
Subject: Great meeting you at [Event]

Hi [Name],

[Specific detail from your conversation -- proves it's not mass-sent].

[Value-add: article, intro, or resource related to what you discussed].

[Soft CTA for next conversation]

[Signature]
```

### Referral Request

```
Subject: Quick ask

Hi [Name],

[Mention shared success or positive experience].

Working with a few other [industry] companies on [topic].
Anyone in your network dealing with [specific challenge]?

Happy to return the favor.

[Signature]
```

---

## Outreach Quality Checklist

Run this checklist on every drafted email before presenting to the user.

| Check | Pass Criteria |
|-------|-------------|
| Opening is specific | References a fact only true of this prospect |
| Under word limit | Cold: under 150. Follow-up: under 100. |
| One CTA | Exactly one ask. Not two. Not zero. |
| No markdown | No asterisks, no headers, no bullet formatting |
| No spam words | No "free," "guaranteed," "limited time," "act now" |
| No feature dump | Product mentioned in one sentence max |
| Subject under 50 chars | Short, specific, no spam triggers |
| Plain text formatting | Would look natural pasted into Gmail |
| No fake personalization | Nothing that could apply to any prospect |
| Proof point is real | Customer story or result is verifiable |

---

## Response Rate Benchmarks

For calibrating expectations with the user.

| Metric | Cold Email | LinkedIn | Warm Intro |
|--------|-----------|----------|-----------|
| Open rate (email) | 30-50% | N/A | 60-80% |
| Reply rate | 5-15% | 10-25% | 30-50% |
| Meeting booked rate | 2-5% | 5-10% | 15-25% |
| Positive reply rate | 1-3% | 3-8% | 10-20% |

These are baselines for well-researched, personalized outreach. Mass-blast templated email performs 3-5x worse.
