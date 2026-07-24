---
title: LLM Operations Failure Modes — Where LLMs Fail in Operations Work
domain: operations
level: 3
skill: operations
---

# LLM Operations Failure Modes

> **Scope**: Catalog of predictable LLM failure modes when generating operational content — runbooks, risk assessments, process documentation, change requests, vendor evaluations, and capacity plans. Each failure mode includes detection criteria and countermeasures. Load this reference for ALL operations modes. It is the quality guard for everything this skill produces.
> **Generated**: 2026-05-05 — LLM capabilities evolve. Re-validate failure modes when underlying models change.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers operations-specific failures only.

---

## Overview

LLMs produce plausible-looking operational content that fails in production. The failure is insidious because the output reads well — proper formatting, complete sections, professional tone — while containing gaps that only become visible when someone tries to follow the runbook at 3am, assess actual risk under pressure, or execute the change plan.

This reference catalogs where LLMs predictably fail in operations work, how to detect each failure, and what to do about it. Every operations mode should be checked against this list before delivery.

---

## Failure Mode 1: Vague Procedures

### The Problem

LLMs default to abstract language. "Deploy the changes" instead of the exact command. "Verify the system" instead of the specific check. "Update the configuration" instead of which file, which key, which value.

This is the #1 failure in runbook generation. The LLM produces a document that looks complete but cannot be followed by someone who does not already know the procedure.

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| Missing paths | "Edit the config file" | Does the step specify which file? Full path? |
| Missing commands | "Run the migration" | Is the exact command present with all flags? |
| Missing users | "SSH to the server" | Which server? As which user? With which key? |
| Missing output | "Check the logs" | Which log? What to grep for? What does success look like? |
| Weasel verbs | "Ensure", "Verify", "Confirm" without specifying HOW | Is there a concrete action after every verification verb? |
| Implicit knowledge | "The usual process" | Would a new hire understand this without asking someone? |
| Assumed context | "As before" / "Same as above" | Is each step self-contained? |

### Countermeasures

1. **Five-component enforcement**: Every step must have Action, Expected Result, Failure Handling, Verification, and Rollback. Reject steps missing any component.
2. **New-hire test**: Read each step as if you have never seen the system. If any step requires knowledge not present in the document, it fails.
3. **Command audit**: Every step that involves running a command must include the full command with path, flags, user context, and expected output.
4. **Verb specificity check**: Flag "ensure", "verify", "confirm", "check", "validate" that are not followed by a concrete how-to within the same sentence.

---

## Failure Mode 2: Underestimated Risk Ratings

### The Problem

LLMs have a systematic bias toward rating risks as "Low" or "Medium" when evidence is ambiguous. This manifests as:
- "Low probability" without evidence (absence of incidents ≠ low probability)
- Downplaying impact by using qualitative descriptions instead of quantifiable measures
- Rating everything "Medium" to avoid seeming alarmist (the "everything is Medium" trap)
- Conflating "unlikely" with "impossible"

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| Unsupported "Low" | "Probability: Low" with no rationale | Is there evidence justifying Low, or is it default? |
| Unquantified impact | "Impact: High" | Is impact expressed in dollars, hours, users, or SLA? |
| Everything Medium | 5+ risks all rated Medium | Is there genuine differentiation, or is Medium the default? |
| Missing worst case | Risk only describes likely outcome | What happens in the worst realistic case? |
| Optimism framing | "Should not happen" / "Unlikely scenario" | "Should not" is not "cannot." What conditions would cause it? |
| No evidence for probability | "Has not happened before" | "Has not happened" requires "and here is why it cannot" to justify Low |

### Countermeasures

1. **Evidence requirement**: Every probability rating must include supporting evidence. No evidence = cannot rate Low.
2. **Quantification mandate**: At least one impact dimension must be quantified (dollars, hours, affected users, SLA percentage).
3. **Distribution check**: If >60% of risks are rated the same level, force re-assessment. Real risk profiles are not uniform.
4. **Challenge-down test**: For every "Low" rating, ask: "What would need to be true for this to be Medium?" If the answer describes current conditions, it is Medium.
5. **Pre-mortem frame**: Instead of "What is the risk?", ask "Assume this failed. What went wrong?" Different framing produces different (often higher) severity ratings.

---

## Failure Mode 3: Generic Templates Without Context

### The Problem

LLMs fill templates with plausible-sounding but generic content. The process documentation, change request, or vendor evaluation looks complete but contains no information specific to the actual organization, system, or situation.

Generic tells:
- Risk mitigations that apply to any organization ("implement monitoring")
- Process steps that describe any process ("review and approve")
- Vendor evaluations that could describe any vendor ("strong market position")
- Change requests with no system-specific impact analysis

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| Substitutable content | "Implement appropriate monitoring" | Would this sentence change if the system/vendor/process were different? |
| No proper nouns | Risk register with no system names | Does the document reference specific systems, teams, people? |
| Template language | "As appropriate" / "as needed" / "relevant stakeholders" | These are placeholders, not content. |
| Missing metrics | "Measure performance" | Which metric? What target? How to collect? |
| Universal truths | "Ensure high availability" | Would any organization disagree? If nobody would disagree, it carries no information. |
| No exceptions | Process with zero edge cases | Every real process has exceptions. Zero exceptions = template, not documentation. |

### Countermeasures

1. **Proper noun density**: Every operations document should reference specific systems, teams, tools, and people by name. If it could describe any organization, it does not describe yours.
2. **Substitution test**: Replace the subject (vendor name, system name, process name) with a different one. If the document still reads correctly, it is generic.
3. **Exception requirement**: Every process document must include at least 3 exceptions/edge cases. If the LLM produces zero, push back: "What goes wrong? What is the unusual case?"
4. **Metrics specificity**: Every metric must have a named KPI, a numeric target, and a collection method. "Track performance" is not a metric.

---

## Failure Mode 4: Missing Rollback and Recovery

### The Problem

LLMs consistently produce success-path-only content. Runbooks describe what happens when everything works. Change requests describe the implementation but not the undo. Risk assessments describe mitigations but not what to do when mitigations fail.

This is optimism bias in document form. The document assumes the happy path because describing failure modes is harder and the LLM has no operational experience to draw from.

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| No rollback section | Change request with implementation plan but no undo | Is there a tested procedure to reverse this change? |
| Success-only steps | Runbook steps without failure handling | What happens when step 3 fails? Is that documented? |
| No escalation paths | Procedure with no "if this does not work" guidance | When should the operator stop and call someone? |
| Rollback as afterthought | "If something goes wrong, undo the changes" | Are rollback steps as specific as implementation steps? |
| Untested rollback | "Rollback: revert to previous version" | Has this rollback been tested? How long does it take? |
| Missing non-reversible markers | Steps that cannot be undone are not called out | Which steps are irreversible? What compensating actions exist? |

### Countermeasures

1. **Symmetry requirement**: For every implementation step, require a corresponding rollback step. If rollback is not possible, require explicit documentation of why and what compensating action exists.
2. **Rollback specificity parity**: Rollback steps must be as specific as implementation steps. "Undo the migration" fails the same vagueness test as "Run the migration."
3. **Non-reversible marking**: Any step that cannot be undone must be flagged prominently with compensating actions documented.
4. **Escalation completeness**: Every procedure must define when to stop trying and escalate, with contact information and message template.
5. **Rollback time estimation**: Every rollback plan must include estimated duration. "Roll back" without timing is not planning.

---

## Failure Mode 5: Artificial Completeness

### The Problem

LLMs produce documents that look complete — all sections filled, all tables populated, all checkboxes checked — without having the information to fill them. This is more dangerous than obvious incompleteness because it passes casual review.

The LLM invents plausible-sounding data to fill templates: made-up SLA numbers, invented vendor capabilities, fabricated process metrics, placeholder people in RACI matrices.

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| Suspiciously complete | All fields filled on first draft without user input | Were all these values provided, or were some generated? |
| Round numbers | "99.9% uptime" / "$100,000 impact" / "50 users affected" | Are these measured values or estimates? |
| Named people without verification | "Owner: John Smith" | Was this person confirmed as owner, or was the name generated? |
| Metrics without sources | "Error rate: 2.3%" | Where does this number come from? Can you verify it? |
| Consistent formatting | Every risk scored, every field filled, no gaps | Gaps in real assessments are normal. Perfect completeness is suspicious. |

### Countermeasures

1. **Mark unknowns explicitly**: It is better to write "[UNKNOWN — verify with ops team]" than to fabricate a value. Require LLM to mark any value not directly provided by the user.
2. **Source attribution**: Every metric, number, or factual claim must cite its source. No source = flagged for verification.
3. **Confidence tagging**: Tag each section as "verified" (user provided data), "estimated" (LLM inferred from context), or "placeholder" (needs verification). Never tag fabricated data as verified.
4. **Gap tolerance**: Incomplete documents with honest gaps are better than complete documents with hidden fabrications. Enforce a culture where "[TODO]" is professional and fabrication is failure.

---

## Failure Mode 6: Shallow Compliance Artifacts

### The Problem

LLMs produce compliance documentation that satisfies the structure of a framework without satisfying the intent. Controls are documented as existing without evidence. Policies reference procedures that do not exist. Risk assessments list mitigations that have never been implemented.

This is checkbox theater: the document exists, the controls are listed, the boxes are checked — and none of it reflects reality.

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| Controls without evidence | "RBAC is implemented" | Where is the evidence? Access review logs? Configuration screenshots? |
| Policies without procedures | "Data retention policy exists" | Where is the procedure that enacts the policy? Who executes it? |
| Mitigations without implementation | "Automated scanning is in place" | When was the last scan? What were the results? Who reviews them? |
| Status "Complete" without date | "Control implemented" | When? By whom? Last verified when? |
| Generic control descriptions | "Appropriate security controls are in place" | Which controls? Configured how? Verified how? |

### Countermeasures

1. **Evidence chain**: Every control must link to evidence. Evidence must be dated and attributed. "Control exists" without evidence = control does not exist for audit purposes.
2. **Procedure validation**: For every documented policy, verify the implementing procedure exists, is current, and has been executed within its review cycle.
3. **Last-verified dates**: Every control must have a last-verified date and a next-review date. Undated controls are unverified controls.
4. **Reality sampling**: Pick 3 controls at random and verify they work as documented. If any fail, the entire compliance artifact is suspect.

---

## Failure Mode 7: Copy-Paste Mitigations

### The Problem

LLMs reuse the same mitigation language across different risks. "Implement monitoring and alerting" appears as the mitigation for network outage, data loss, security breach, and performance degradation. These are not mitigations — they are noise masquerading as action.

### Detection Criteria

| Indicator | Example | Test |
|-----------|---------|------|
| Repeated mitigations | Same "monitoring and alerting" for 3+ risks | Is the monitoring different for each risk, or is it the same phrase? |
| Non-specific monitoring | "Monitor the situation" | Monitor what? What threshold triggers action? Who acts? |
| Unbounded "improve" | "Improve documentation" | Which documentation? What improvement? By when? |
| Activity without outcome | "Conduct regular reviews" | How often? Who reviews? What happens with findings? |
| Mitigation = control | "Implement access controls" | This is a control, not a mitigation plan. What specific access control? For what? By when? |

### Countermeasures

1. **Uniqueness check**: Compare mitigations across the risk register. If >2 risks share identical mitigation language, each must be differentiated for its specific risk.
2. **SMART test**: Every mitigation must be Specific, Measurable, Assignable, Relevant, and Time-bound. "Monitor the situation" fails all five.
3. **Action-outcome pairing**: Every mitigation must state both the action AND the expected outcome. "Implement monitoring" -> "Configure PagerDuty alert for error rate >5%, reviewed by on-call engineer within 15 minutes, expected to reduce MTTR from 2 hours to 30 minutes."
4. **Owner and date**: No mitigation without a named owner and a completion date. Unowned mitigations are aspirations, not plans.

---

## Cross-Mode Quality Checklist

Run this checklist against every operations output before delivery.

```
## Operations Output Quality Gate

### Specificity
- [ ] No steps use "ensure", "verify", "check" without specifying HOW
- [ ] All commands include full paths, flags, and user context
- [ ] All references to systems/people/tools use proper nouns
- [ ] Could someone unfamiliar with the context follow this document?

### Risk Honesty
- [ ] No "Low" probability rating without supporting evidence
- [ ] All impact ratings include at least one quantified dimension
- [ ] Risk distribution is not artificially uniform
- [ ] "Has not happened" is not used as sole justification for "Low"

### Completeness Integrity
- [ ] Unknown values marked as [UNKNOWN] or [TODO], not fabricated
- [ ] All metrics cite their source
- [ ] Named people/roles are verified, not generated
- [ ] Gaps are honest, not filled with generic content

### Recovery Planning
- [ ] Rollback procedure exists for every changeable state
- [ ] Rollback steps are as specific as implementation steps
- [ ] Non-reversible steps are flagged with compensating actions
- [ ] Escalation paths include contact info and trigger criteria

### Context Specificity
- [ ] Substitution test passed (change the subject — does the doc still work? If yes, too generic)
- [ ] At least 3 exceptions/edge cases documented per process
- [ ] Mitigations are unique per risk, not copy-pasted
- [ ] Templates are filled with real data, not placeholder patterns
```
