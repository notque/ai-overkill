# Response Drafting

Deep reference for customer-facing response drafting: tone calibration by situation, relationship-stage adjustments, de-escalation patterns, channel-appropriate formatting, follow-up templates, and quality verification.

---

## Tone Spectrum

Select tone based on the situation type. Every response sits somewhere on this spectrum.

| Situation | Tone | Characteristics | Risk if Wrong |
|-----------|------|----------------|---------------|
| Good news / wins | Celebratory | Enthusiastic, warm, congratulatory, forward-looking | Flat delivery kills the moment |
| Routine update | Professional | Clear, concise, informative, friendly | Too formal reads cold; too casual reads unserious |
| Technical response | Precise | Accurate, detailed, structured, patient | Condescension if you over-explain; confusion if you under-explain |
| Delayed delivery | Accountable | Honest, apologetic, action-oriented, specific | Defensiveness or vagueness destroys trust |
| Bad news | Candid | Direct, empathetic, solution-oriented, respectful | Burying the news in jargon feels dishonest |
| Issue / outage | Urgent | Immediate, transparent, actionable, reassuring | Downplaying severity insults intelligence |
| Escalation | Executive | Composed, ownership-taking, plan-presenting, confident | Panic signals incompetence |
| Billing / account | Precise | Clear, factual, empathetic, resolution-focused | Vagueness about money creates anxiety |

---

## Relationship Stage Calibration

### New Customer (0-3 months)

- More formal and professional tone
- Extra context and explanation (don't assume product knowledge)
- Proactively offer help and resources
- Build trust through reliability and responsiveness
- Include links to relevant documentation

### Established Customer (3+ months)

- Warm and collaborative tone
- Reference shared history and previous conversations
- More direct and efficient -- skip the preamble
- Show awareness of their goals and priorities
- "As you know" or "building on our previous conversation" signals continuity

### Frustrated or Escalated Customer

- Lead with empathy -- acknowledge before solving
- Urgency in response time and language
- Concrete action plan with specific commitments
- Shorter feedback loops ("I'll update you every 2 hours")
- Name the person accountable for resolution
- Offer a call or meeting for severity-appropriate situations

---

## De-escalation Patterns

When a customer is angry, frustrated, or escalating. The goal is not to win an argument. The goal is to move from emotion to resolution.

### The De-escalation Sequence

1. **Acknowledge** -- Name what they're feeling without being patronizing
2. **Validate** -- Confirm their concern is reasonable (even if the specific complaint isn't)
3. **Own** -- Take responsibility where appropriate, never deflect
4. **Plan** -- Present concrete next steps with timeline
5. **Commit** -- State exactly what you will do and by when

### De-escalation Language

| Instead of | Write | Why |
|-----------|-------|-----|
| "I understand your frustration" (generic) | "I can see how [specific impact] would be frustrating for your team" | Specificity proves you actually read their message |
| "Unfortunately, we can't..." | "Here's what we can do: [alternative]" | Lead with the solution, not the limitation |
| "This is working as designed" | "The current behavior is [X]. I can see why you'd expect [Y]. Let me explore options." | Validate their expectation before explaining the gap |
| "Per our policy..." | "Here's what I'm able to do in this situation: [action]" | Policy citations feel bureaucratic |
| "As I mentioned previously..." | [Just restate the information] | Implies they should have read your earlier message |
| "That's not really a bug" | "I see what you're experiencing. Let me dig into why it behaves that way." | Classification debate alienates; investigation helps |
| "You need to..." | "Here's how to resolve this: [steps]" | Directive language feels adversarial under stress |

<!-- no-pair-required: failure modes are self-explanatory failure modes; positive approach is in surrounding context -->
### De-escalation Failure Modes

| Failure Mode | Why It Fails |
|-------------|-------------|
| Matching their energy/anger | Escalates, never de-escalates |
| Excessive apologizing without action | Apology fatigue -- they want fixes, not sorry |
| Explaining the technical root cause first | They don't care about your architecture; they care about their workflow |
| Citing policy to justify the experience | Policy is your constraint, not their problem |
| Dismissing with "works for me" | Invalidates their experience entirely |
| Over-promising to end the conversation | Creates a bigger problem when you can't deliver |

---

## Response Structure

### Standard Structure (all situations)

```
1. Acknowledgment (1-2 sentences)
   - Acknowledge what they said, asked, or are experiencing
   - Show you understand their specific situation

2. Core Message (1-3 paragraphs)
   - Deliver the main information, answer, or update
   - Be specific and concrete
   - Include relevant details they need

3. Next Steps (1-3 bullets)
   - What YOU will do and by when
   - What THEY need to do (if anything)
   - When they'll hear from you next

4. Closing (1 sentence)
   - Warm but professional sign-off
   - Reinforce availability
```

### Length by Channel

| Channel | Target Length | Structure Notes |
|---------|-------------|-----------------|
| Chat/IM | 1-4 sentences | Get to the point immediately. Skip formal structure. |
| Support ticket | 1-3 short paragraphs | Structured and scannable. Use bullets freely. |
| Email | 3-5 paragraphs max | Respect their inbox. Headers for long responses. |
| Escalation response | As needed | Well-structured with headers. Thoroughness > brevity. |
| Executive communication | 2-3 paragraphs max | Shorter is better. Lead with the decision or ask. Data-driven. |

---

## Situation-Specific Approaches

### Answering a Product Question

- Lead with the direct answer, then context
- Link to documentation if relevant
- If you don't know: say so, commit to finding out, give a timeline
- Never guess or speculate about product capabilities

### Responding to a Bug Report

- Acknowledge the impact on their work specifically
- State what you know about the issue and its status
- Provide workaround if available
- Set expectations for resolution timeline
- Commit to regular updates

### Handling an Escalation

- Acknowledge severity and their frustration
- Take ownership (no deflecting, no "the engineering team...")
- Present a clear action plan with timeline
- Name the person accountable
- Offer a call if severity warrants it

### Delivering Bad News

- Be direct -- don't bury it in paragraph three
- Explain the reasoning honestly
- Acknowledge their specific impact
- Offer alternatives or mitigation
- Provide a clear path forward

### Declining a Request

- Acknowledge the request and its reasoning
- Be honest about the decision
- Explain why without being dismissive
- Offer alternatives when possible
- Leave the door open for future conversation

### Outage Communication

- Lead with status: what's affected, current state, ETA
- Be transparent about what you know and don't know
- Provide workaround if one exists
- Commit to update cadence
- Address prevention after resolution

---

## Writing Style Rules

### Do

- Active voice: "We'll investigate" not "This will be investigated"
- "I" for personal commitments, "we" for team commitments
- Name people when assigning actions: "Sarah from our engineering team will..."
- Use their terminology, not your internal jargon
- Specific dates and times: "by Friday January 24" not "in a few days"
- Break up long responses with headers or bullets

### Don't

- Corporate jargon: "synergy", "leverage", "paradigm shift", "circle back"
- Deflect blame to other teams, systems, or processes
- Passive voice to avoid ownership: "Mistakes were made"
- Excessive hedging that undermines confidence
- Exclamation marks beyond one per message (if any)
- "Please be advised" or "Kindly note" (bureaucratic distancing)
- "As per my last email" (passive-aggressive)

---

## Follow-up Templates

### Post-Resolution Check-in

```
Hi [Name],

I wanted to follow up on the [issue] we resolved on [date].
Is everything working as expected on your end?

If anything comes up, don't hesitate to reach out.

Best,
[Your name]
```

### After Silence (No Response)

```
Hi [Name],

I sent over [what you sent] on [date] and wanted to make
sure it didn't get lost.

[Brief reminder of what you need or what you offered]

If now isn't a good time, no worries -- let me know when
would work and I'm happy to reconnect then.

Best,
[Your name]
```

### Outage Resolution Notification

```
Hi [Name],

Good news -- the [issue] affecting [service/feature] has
been resolved as of [time].

**What happened:** [Clear, non-technical explanation]
**Root cause:** [Brief explanation]
**What we've done to prevent recurrence:** [Steps taken]

Your team should be able to [resume normal activity] now.
If you notice anything unusual, please let us know immediately.

I'm sorry for the disruption. We take reliability seriously
and have [specific preventive action] in place.

[Your name]
```

### Status Update (No New Information)

```
Hi [Name],

I wanted to give you an update on [issue]. Our team is
still actively investigating and I don't have new information
to share yet.

Here's where things stand:
- [What we've checked so far]
- [What we're looking at next]
- [Expected next milestone]

I'll update you again by [specific time]. If anything changes
before then, I'll let you know immediately.

[Your name]
```

---

## Follow-up Cadence

| Situation | Follow-up Timing |
|-----------|-----------------|
| Unanswered question | 2-3 business days |
| Open critical issue | Every 2-4 hours until resolved |
| Open standard issue | Daily until resolved |
| Post-resolution | 3-5 days to confirm |
| After delivering bad news | 1 week to check sentiment |
| Post-meeting action items | Within 24 hours (notes), then at deadline |

---

## Quality Verification Checklist

Run before presenting any draft:

### Content Checks
- [ ] Directly addresses the customer's actual question or concern
- [ ] Accurate -- no claims about features, timelines, or policies you can't verify
- [ ] No roadmap details that shouldn't be shared externally
- [ ] No internal jargon or team names the customer wouldn't know

### Commitment Checks
- [ ] No unauthorized timeline commitments
- [ ] No policy exceptions you can't approve
- [ ] No promises about features or fixes being built
- [ ] All next steps are achievable and within your authority

### Tone Checks
- [ ] Matches the situation (empathetic for frustration, direct for questions)
- [ ] Matches the relationship stage (formal for new, warm for established)
- [ ] No corporate jargon or bureaucratic distancing
- [ ] Active voice -- clear ownership of actions
- [ ] Appropriate length for the channel

### Structural Checks
- [ ] Clear acknowledgment of their situation
- [ ] Core message is specific and concrete
- [ ] Next steps include who does what by when
- [ ] Professional close with availability signal

---

## Internal Notes Format

Every drafted response includes internal notes (not sent to customer):

```
### Notes (internal -- do not send)
- **Tone rationale:** [Why this tone was chosen]
- **Verify before sending:** [Facts or commitments to confirm]
- **Risk factors:** [Anything sensitive about this response]
- **Follow-up needed:** [Actions after sending]
- **Escalation note:** [If someone else should review first]
```
