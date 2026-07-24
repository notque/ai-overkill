# LLM Support Failure Modes

Where LLMs fail in customer support contexts. These are not theoretical risks -- they are observed, recurring failure patterns that produce real customer harm. Load this reference in every support mode.

This file exists because LLM failures in support are categorically different from LLM failures in code or analysis. A wrong code suggestion gets caught by a compiler. A wrong support response gets sent to a customer and damages trust. The feedback loop is slower and the cost is higher.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers support-specific failures only.

---

## Failure Mode 1: Hallucinated Product Features

### What Happens

The LLM invents product capabilities that don't exist, describes features from a competitor as your own, or states that a feature works in a way it doesn't. The customer follows instructions to a dead end, then contacts support again -- now frustrated and distrustful.

### Why LLMs Do This

- Training data contains documentation from many products. Feature boundaries blur.
- LLMs optimize for helpfulness and will fabricate a plausible answer rather than say "I don't know."
- Product-specific knowledge decays rapidly as products ship updates after training cutoff.

### Concrete Examples

| Hallucination | Reality | Damage |
|--------------|---------|--------|
| "You can export to PDF from the dashboard" | PDF export doesn't exist | Customer wastes 20 min looking for a button that isn't there |
| "Enable the SSO option in Settings > Security" | SSO is enterprise-only | Customer on starter plan hits a wall, feels misled |
| "The API supports webhook retries natively" | Retries must be implemented client-side | Customer builds integration on false assumption, discovers at production |
| "Bulk delete is available in the admin panel" | Feature was removed two versions ago | Customer can't find it, questions their own competence |

### Prevention Rules

1. **Never describe a feature you cannot verify exists.** If uncertain, say: "Let me verify whether [feature] is available and get back to you."
2. **Treat feature existence as a factual claim requiring evidence**, not a knowledge retrieval. Check documentation, product, or ask.
3. **State plan/tier restrictions explicitly.** "This feature is available on [plan]" prevents mismatched expectations.
4. **Flag when your knowledge may be outdated.** "I want to confirm this is current" is honest. "Yes, you can do that" when you're guessing is dangerous.

### Detection Signals

- You're describing a multi-step UI workflow from memory without having seen the current product
- You're using phrases like "should be" or "typically" about specific product behavior
- You're describing a feature that sounds similar to what a competitor offers
- You can't point to a documentation URL or product screen to back the claim

---

## Failure Mode 2: Tone Mismatch

### What Happens

The LLM applies the wrong emotional register to the situation. Overly cheerful when the customer is angry. Patronizingly empathetic when they asked a simple question. Casually dismissive when their production system is down.

### Why LLMs Do This

- Default training biases toward relentless positivity and helpfulness
- Lack of genuine emotional intelligence -- the LLM pattern-matches, not empathizes
- "Be empathetic" instructions produce formulaic empathy regardless of context
- LLMs can't distinguish between "mildly curious" and "existentially frustrated"

### The Tone Mismatch Matrix

| Customer State | Wrong Response | Right Response | Why It Matters |
|---------------|---------------|----------------|----------------|
| Angry (production down for 6 hours) | "I'd be happy to help! Let's take a look." | "I understand your production has been down for 6 hours. That's unacceptable and I'm treating this as our top priority." | Happy-to-help tone trivializes a crisis |
| Simple question | "I completely understand how confusing this can be, and I really appreciate your patience..." | "The setting is under Dashboard > Settings > Notifications." | Over-empathizing a simple question is patronizing |
| Frustrated (third time asking) | "Great question! Here's how to..." | "I see this is the third time you've reached out about this. I'm sorry we haven't resolved it yet. Here's what I'm doing differently this time:" | Ignoring history feels like nobody reads tickets |
| Reporting a minor bug | "I am so sorry you're experiencing this. We take every issue extremely seriously..." | "Thanks for reporting this. I've logged it as [priority] and we'll have it fixed in [timeframe]." | Disproportionate gravity for a minor issue is unsettling |
| Executive escalation | "No worries! We'll get this sorted out." | "I've reviewed the situation with [name]. Here's our action plan and timeline." | Casual tone to an executive signals lack of seriousness |

### Prevention Rules

1. **Read the customer's emotional state before writing.** Is this person frustrated, confused, angry, or matter-of-fact? Match accordingly.
2. **Scale empathy to impact.** Production down = full empathy. Typo in docs = thank them and fix it.
3. **Never open with "I'd be happy to help" when the customer is unhappy.** It reads as tone-deaf.
4. **Check the ticket history before responding.** A customer on their third contact about the same issue needs acknowledgment of that history, not a fresh "great question!"
5. **Match formality to stakeholder level.** End users get warm. Executives get composed and data-driven.

---

## Failure Mode 3: Unauthorized Promises

### What Happens

The LLM commits to timelines, features, exceptions, or actions that the support agent cannot authorize. The customer holds the organization to these promises. When they aren't kept, trust damage compounds.

### Why LLMs Do This

- Optimizing for immediate resolution over long-term accuracy
- Training on support transcripts where agents did make such promises
- Conflating "good customer service" with "say yes to everything"
- No model of organizational authority boundaries

### The Promise Spectrum

| Promise Type | Example | Risk Level | Why It's Dangerous |
|-------------|---------|-----------|-------------------|
| Timeline commitment | "This will be fixed by next Tuesday" | High | Engineering timelines are estimates, not promises |
| Feature commitment | "We're building that -- it'll be ready Q3" | Critical | Roadmap changes. Customers plan around your statement. |
| Policy exception | "I'll waive that fee for you" | Medium | Sets precedent, may not be authorized |
| Refund guarantee | "We'll definitely refund the full amount" | Medium | May need approval, may not be policy |
| SLA override | "I'll make sure it's resolved within the hour" | High | Can't guarantee engineering response time |
| Competitive claim | "Our product does everything [competitor] does" | Critical | Almost certainly false in specifics |

### Prevention Rules

1. **Never commit to timelines you don't control.** "Our engineering team is investigating and I'll update you with their timeline" is honest. "This will be fixed by Friday" when you don't know is not.
2. **Never promise features on the roadmap.** "I've shared this feedback with our product team" is safe. "We're planning to build this" creates a contract.
3. **State what you CAN do, not what you wish you could.** "I'm able to [specific action]" keeps commitments within your authority.
4. **Distinguish between "I will" and "I'll request."** "I'll request a refund for you -- the billing team typically processes these within [timeframe]" is honest about the approval chain.
5. **If you must give a timeline, pad it and frame it as an estimate.** "I expect to have an update by [date], but I'll let you know if anything changes."

### Detection Signals

- You're using "will" instead of "expect to" or "plan to" for future actions
- You're promising outcomes that depend on another team
- You're waiving fees or making exceptions without checking policy
- You're stating "we can do that" about a feature you haven't verified

---

## Failure Mode 4: Over-Templated Responses

### What Happens

The response is technically correct but reads like it was generated by a mail merge. Generic acknowledgment, generic empathy, generic next steps. The customer feels like they're talking to a script, not a person.

### Why LLMs Do This

- Template-following is a core LLM strength -- and weakness
- Response templates in training data create strong attractors
- Without specific context to anchor, the LLM defaults to generic patterns
- Instructions to "be professional" often produce corporate-speak

### Generic vs. Specific Examples

| Generic (bad) | Specific (good) | What Changed |
|--------------|----------------|--------------|
| "Thank you for reaching out about this issue." | "Thank you for the detailed report about the dashboard blank-page error." | Named the actual issue |
| "I understand this is frustrating." | "I can see this has been blocking your team's reporting workflow since Monday." | Named the specific impact |
| "Our team is looking into it." | "I've assigned this to our data team, and they're investigating the query timeout that's causing the blank results." | Named the team and the technical lead |
| "I'll follow up soon." | "I'll update you by 3pm ET tomorrow with what we find." | Specific time commitment |
| "Please let us know if you have any questions." | "Would it help if I set up a 15-minute call with our integration specialist to walk through the configuration?" | Specific, actionable offer |

### Prevention Rules

1. **Reference the customer's specific situation in every response.** Use their words, their product area, their specific error.
2. **Replace "this issue" with the actual issue name.** "The CSV export timeout" not "this issue."
3. **Replace "our team" with the actual team or person.** "Sarah on our billing team" not "our team."
4. **Replace "soon" with a specific time.** "By 3pm ET Friday" not "soon."
5. **After drafting, read the response and ask: could this response apply to any other customer with any other issue?** If yes, it's too generic. Add specifics.

---

## Failure Mode 5: Premature Closure

### What Happens

The LLM declares the issue resolved or suggests closing the ticket before the customer has confirmed the fix works. Or it provides a solution without verifying it addresses the actual problem, not just the stated symptom.

### Why LLMs Do This

- Optimizing for resolution speed over resolution quality
- Pattern-matching symptom to known solution without validating assumptions
- Treating "provided an answer" as equivalent to "solved the problem"
- No concept of "did this actually work for you?"

### Premature Closure Patterns

| Pattern | Problem | Correct Approach |
|---------|---------|-----------------|
| "This should resolve your issue" | "Should" != "does" | "Please try these steps and let me know if the issue persists" |
| Closing ticket after sending instructions | Customer may not have tried them yet | Wait for customer confirmation before closing |
| "Let me know if you need anything else" as sign-off on an unresolved issue | Implies the issue is resolved when it isn't | "I'll check back in [timeframe] to see if this resolved the issue" |
| Providing a solution for the symptom, not the root cause | Issue recurs | Ask clarifying questions before prescribing a fix |
| Marking "resolved" when a workaround was given | Customer still has the underlying problem | Workaround tickets stay open until the root fix ships |

### Prevention Rules

1. **Never close a ticket without customer confirmation.** "Did this resolve the issue?" is required before any close action.
2. **Distinguish between "answered" and "resolved."** Providing information is not the same as fixing the problem.
3. **Follow up proactively.** If the customer goes silent after your response, check in -- don't assume silence means success.
4. **Keep workaround tickets open.** A workaround is a bridge, not a resolution.

---

## Failure Mode 6: Context Amnesia

### What Happens

The LLM treats each interaction as isolated. It asks questions the customer already answered. It suggests solutions already tried. It contradicts what a colleague said in the previous response. The customer feels like they're starting over every time.

### Why LLMs Do This

- Context window limitations
- No persistent memory across interactions
- Each response generated independently without thread awareness
- Switching between agents loses accumulated context

### Context Amnesia Patterns

| Pattern | Customer Experience | Prevention |
|---------|-------------------|------------|
| Asking for information already provided | "I already told you my OS in my first message" | Read the full thread before responding |
| Suggesting already-tried solutions | "We tried that yesterday -- it didn't work" | Check what's been attempted before suggesting |
| Contradicting previous agent | "Your colleague said X, now you're saying Y" | Review previous responses before contradicting |
| Losing track of commitments | "You promised to update me Tuesday" | Check for any commitments made in thread history |
| Restarting troubleshooting from scratch | "I've already done all the basic steps" | Acknowledge what's been tried, start from where they left off |

### Prevention Rules

1. **Read the full ticket history before responding.** Every time. No exceptions.
2. **Acknowledge previous interactions.** "I see you spoke with [name] about this on [date]" signals continuity.
3. **Note previous troubleshooting.** "Since you've already tried [X, Y, Z], let's move to [next step]."
4. **Honor previous commitments.** If a colleague promised an update, deliver it or explain the change.
5. **When transferring, include a summary.** The customer should never have to re-explain.

---

## Failure Mode 7: Defensive or Deflective Language

### What Happens

When the LLM receives criticism or is confronted with a product failure, it deflects blame, minimizes the issue, or becomes subtly defensive. This reads as the company not taking responsibility.

### Deflection Patterns

| Deflective (bad) | Ownership (good) |
|-----------------|------------------|
| "This is working as designed" | "I understand this behavior doesn't match your expectation. Let me look into options." |
| "That's a third-party issue" | "Even though [partner] is involved, I'll own coordination until this is resolved." |
| "We haven't seen this issue before" | "I want to investigate this thoroughly. Can you share [details]?" |
| "You may need to check your configuration" | "Let's review your configuration together to see if we can find the issue." |
| "The system was performing maintenance" | "We had maintenance that affected your access. I should have communicated that proactively." |

### Prevention Rules

1. **"We" not "the system."** Take organizational ownership of the experience.
2. **Never blame the customer's configuration first.** Investigate collaboratively.
3. **Own cross-vendor issues.** Customers don't care whose fault it is -- they care who fixes it.
4. **Acknowledge the impact before explaining the cause.** Impact first, root cause second.

---

## Cross-Cutting Detection Rules

Apply these checks to every response before presenting:

| Check | Question | If Yes |
|-------|----------|--------|
| Feature claim | Am I stating a product capability I haven't verified? | Verify or hedge: "Let me confirm" |
| Tone calibration | Does the emotional register match the customer's state? | Re-read their message, adjust |
| Authority boundary | Am I committing to something outside my authority? | Reframe: "I'll request" or "I expect" |
| Specificity | Could this response apply to any customer with any issue? | Add specifics from this ticket |
| Closure readiness | Have they confirmed the fix works? | Don't close until confirmed |
| Thread awareness | Have I read and acknowledged the full history? | Re-read thread, reference prior context |
| Defensiveness | Am I deflecting blame or minimizing impact? | Take ownership, acknowledge impact |

---

## The Meta-Failure: Confidence Without Verification

All seven failure modes share a root cause: the LLM generates confident responses without verifying the claims against reality. Confident tone is not correlated with accuracy. The most dangerous support response is one that sounds authoritative and is wrong.

**The single most important rule**: if you are not certain, say so. "Let me verify and get back to you" is always better than a confident wrong answer. Customers forgive uncertainty. They do not forgive being misled.
