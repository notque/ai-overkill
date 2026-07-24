# Legal Writing

Formats, templates, and methodology for legal documents: memos, briefs, responses, meeting briefings, incident briefs. Includes escalation triggers for templated responses and template creation guide.

---

## Document Types

| Type | Purpose | Audience | Formality |
|------|---------|----------|-----------|
| Legal memo | Internal analysis of a legal question | Legal team, stakeholders | High |
| Legal brief | Summary of issue, law, and recommendation | Legal team, executives | High |
| Legal response | Templated response to common inquiry | External parties, regulators, internal teams | Medium-High |
| Meeting brief | Pre-meeting context and talking points | Meeting attendees | Medium |
| Incident brief | Rapid situation assessment | Response team, leadership | Medium-High |

---

## Legal Memo Format

```
## Legal Memorandum

**To**: [recipient]
**From**: [author]
**Date**: [date]
**Re**: [subject]
**Privileged**: [Yes/No -- mark "ATTORNEY-CLIENT PRIVILEGED / WORK PRODUCT" if applicable]

### Question Presented
[Specific legal question in one sentence. Frame precisely.]

### Short Answer
[Direct answer in 2-3 sentences. State the conclusion first.]

### Facts
[Relevant facts only. Chronological or topical organization. Distinguish established facts from assumptions.]

### Analysis
[Apply law to facts. Address counterarguments. Identify ambiguities.]

#### [Sub-issue 1]
[Analysis with supporting reasoning]

#### [Sub-issue 2]
[Analysis with supporting reasoning]

### Conclusion
[Restate answer with key reasoning. Note confidence level.]

### Recommended Action
1. [Specific action with owner and timeline]
2. [Specific action with owner and timeline]

### Open Questions
[What remains unknown. What additional information would change the analysis.]
```

**Writing standards:**
- State the conclusion first, then support it
- Distinguish "the law requires X" from "the law likely requires X" from "this is unsettled"
- Flag jurisdiction-specific variations explicitly
- Note training data limitations for recent legal developments
- Never present LLM analysis as authoritative legal opinion

---

## Legal Brief Format

```
## Legal Brief: [Topic]

**Date**: [date]
**Prepared for**: [recipient/audience]
**Privileged**: [Yes/No]

### Executive Summary
[2-3 sentence summary. Conclusion first.]

### Background
[Context and history. What led to this issue.]

### Issue
[Precise statement of the legal question or situation]

### Analysis
[Structured analysis. Use headings for sub-issues.]

### Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| [Risk] | [H/M/L] | [H/M/L] | [How to address] |

### Recommendation
[Clear recommendation with rationale and confidence level]

### Next Steps
1. [Action -- Owner -- Deadline]
```

---

## Legal Response Templates

### Response Categories

| Category | Sub-types | Key Elements |
|----------|-----------|-------------|
| Data Subject Request (DSR) | Acknowledgment, verification, fulfillment, partial denial, full denial, extension | Applicable regulation, timeline, verification requirements, rights information |
| Litigation Hold | Initial notice, reminder, modification, release | Matter reference, preservation obligations, scope, prohibition on spoliation |
| Vendor Question | Contract status, amendment request, compliance certification, audit response | Agreement reference, specific response, caveats, next steps |
| NDA Request | Send standard form, accept with markup, decline, renew | Purpose, standard terms, execution instructions, timeline |
| Privacy Inquiry | Cookie/tracking, policy questions, data sharing, cross-border | Privacy notice reference, specific answers, privacy team contact |
| Subpoena Response | Acknowledgment, objection, extension request, compliance cover | Case reference, objections, preservation confirmation, privilege log |
| Insurance Notification | Initial claim, supplemental info, reservation of rights response | Policy number, matter description, timeline, coverage request |

### DSR Response Templates

**Acknowledgment:**
```
Subject: Your Data [Access/Deletion/Correction] Request -- Reference [ID]

Dear [Name],

We received your request dated [date] to [access/delete/correct] your personal
data under [applicable regulation].

We will respond substantively by [deadline: 30 days GDPR / 45 days CCPA].

To verify your identity, please provide: [verification requirements].

If you have questions, contact [privacy team contact].

[Rights information: right to lodge complaint with supervisory authority]
```

**Extension notification:**
```
Subject: Update on Your Data Request -- Reference [ID]

Dear [Name],

We are writing regarding your [request type] request dated [date].

Due to [complexity of request / number of requests], we require additional time
to respond. Under [regulation], we are extending our response period by
[60 days GDPR / 45 days CCPA].

We will provide our substantive response by [new deadline].

[Contact information]
```

### Litigation Hold Template

```
Subject: LEGAL HOLD NOTICE -- [Matter Name] -- Action Required

PRIVILEGED AND CONFIDENTIAL
ATTORNEY-CLIENT COMMUNICATION

Dear [Custodian Name],

You are receiving this notice because you may possess documents, communications,
or data relevant to the matter referenced above.

PRESERVATION OBLIGATION:
Effective immediately, you must preserve all documents and electronically stored
information (ESI) related to:

- Subject matter: [scope]
- Date range: [start date] to present
- Document types: [email, chat, files, voicemail, text messages, etc.]
- Systems: [list specific systems]

DO NOT delete, destroy, modify, or discard any potentially relevant materials.
This includes suspending any automatic deletion or archival processes.

WHAT TO PRESERVE:
- All emails, attachments, and calendar entries related to the subject matter
- All chat messages (Slack, Teams, etc.) related to the subject matter
- All documents, spreadsheets, presentations, and notes
- All drafts, even if a final version exists
- All voicemails and recorded calls
- All text messages and instant messages

WHAT TO DO:
1. Read this notice carefully
2. Identify all locations where relevant materials may exist
3. Take steps to preserve those materials
4. Acknowledge receipt by [deadline]
5. Contact [legal contact] with any questions

IMPORTANT: Do not discuss the substance of this hold or the related matter
with anyone outside the legal team.

Please acknowledge receipt by responding to this email by [date].

[Legal contact information]
```

### Hold Release Template

```
Subject: RELEASE OF LEGAL HOLD -- [Matter Name]

PRIVILEGED AND CONFIDENTIAL

Dear [Custodian Name],

The legal hold issued on [original date] regarding [Matter Name] is hereby released.

You may resume normal document retention and deletion practices for materials
that were subject to this hold.

Note: This release applies only to the hold identified above. If you are subject
to any other legal holds, those obligations remain in effect.

[Legal contact information]
```

---

## Escalation Triggers

Before generating ANY templated legal response, check these triggers. If any fire, recommend escalation to qualified counsel instead of generating a template.

### Universal Triggers (All Categories)

| Trigger | Why It Matters |
|---------|---------------|
| Potential litigation or regulatory investigation | Templated response could create admissions or waive rights |
| From regulator, government agency, or law enforcement | Requires individualized, counsel-reviewed response |
| Could create binding legal commitment or waiver | Template may not account for specific implications |
| Potential criminal liability | Requires specialized counsel |
| Media attention involved or likely | Response becomes public statement |
| Unprecedented situation | No template can account for novel facts |
| Multiple jurisdictions with conflicting requirements | Template designed for single jurisdiction |
| Involves executive leadership or board members | Heightened sensitivity and scrutiny |

### Category-Specific Triggers

**DSR:**
- Minor's data or request from/on behalf of a minor
- From regulatory authority (not individual)
- Data subject to litigation hold
- Current/former employee with active dispute or HR matter
- Unusually broad scope (possible fishing expedition)
- Special category data (health, biometric, genetic)

**Litigation Hold:**
- Potential criminal liability
- Unclear, disputed, or overbroad preservation scope
- Prior holds for same/related matter exist
- Conflicts with regulatory deletion requirements (GDPR right to erasure vs. hold)
- Custodian objects to hold scope

**Vendor:**
- Dispute or potential breach
- Vendor threatening litigation or termination
- Involves regulatory compliance (not just contract terms)
- Could create binding commitment or waiver
- Could affect ongoing negotiation

**NDA Request:**
- Counterparty is a competitor
- Government classified information
- Potential M&A transaction
- Unusual subject matter (AI training data, biometric data)

**Subpoena:**
- ALWAYS requires counsel review (templates are starting points only)
- Privilege issues identified
- Third-party data involved
- Cross-border production
- Unreasonable timeline

### When Trigger Fires

1. **Stop** -- Do not generate templated response
2. **Alert** -- Inform user which trigger was detected
3. **Explain** -- Why this matters and what could go wrong with a template
4. **Recommend** -- Appropriate escalation path (senior counsel, outside counsel, specific team)
5. **Offer** -- Draft marked "DRAFT -- FOR COUNSEL REVIEW ONLY" rather than final response

---

## Meeting Brief Format

```
## Meeting Brief

### Meeting Details
**Meeting**: [title] | **Date**: [date/time/timezone] | **Duration**: [duration]
**Location**: [physical/video] | **Your Role**: [advisor/presenter/negotiator/observer]

### Participants
| Name | Organization | Role | Key Interests | Notes |
|------|-------------|------|---------------|-------|
| [name] | [org] | [role] | [what they care about] | [context] |

### Agenda / Expected Topics
1. [Topic] -- [brief context]

### Background and Context
[2-3 paragraphs: relevant history, current state, why this meeting is happening]

### Open Issues
| Issue | Status | Owner | Priority |
|-------|--------|-------|----------|
| [issue] | [status] | [who] | [H/M/L] |

### Legal Considerations
[Risks, compliance issues, privilege concerns relevant to meeting topics]

### Talking Points
1. [Point with supporting context]

### Questions to Raise
- [Question] -- [why it matters]

### Decisions Needed
- [Decision] -- [options and recommendation]

### Red Lines / Non-Negotiables
[Positions that cannot be conceded, if negotiation meeting]

### Preparation Gaps
[Information not found, questions for user]
```

### Meeting-Type Preparation Guide

| Meeting Type | Additional Sections |
|-------------|-------------------|
| Deal review | Deal summary, contract status, approval requirements, counterparty dynamics |
| Board/Committee | Legal department update, risk highlights, regulatory update, pending approvals, litigation summary |
| Vendor call | Agreement status, open issues, performance metrics, negotiation objectives |
| Regulatory | Regulatory body context, matter history, compliance posture, privilege considerations |
| Litigation/Dispute | Case status, recent developments, strategy, settlement parameters |

---

## Incident Brief Format

```
## Incident Brief: [Topic]
**Prepared**: [timestamp]
**Classification**: [severity if determinable]

### Situation Summary
[What is known]

### Timeline
[Chronological events]

### Immediate Legal Considerations
- Regulatory notification deadlines (e.g., 72 hours GDPR)
- Preservation obligations
- Privilege concerns

### Relevant Agreements
[Contracts, insurance, indemnification provisions implicated]

### Recommended Immediate Actions
1. [Most urgent]
2. [Second priority]

### Information Gaps
[What is not yet known]
```

**Incident brief rules:**
- Speed over completeness. Produce quickly with available information.
- Flag litigation hold obligations immediately
- Mark as privileged if appropriate
- If data breach: flag applicable notification deadlines
- Recommend outside counsel if matter is significant

---

## Template Creation Guide

When no template exists for an inquiry type:

### 1. Define Use Case
- Inquiry type and frequency
- Typical audience and urgency

### 2. Identify Required Elements
- Legal requirements for this response type
- Organizational policies that govern it

### 3. Define Variables
- Use clear names: `{{requester_name}}`, `{{response_deadline}}`, `{{matter_reference}}`
- Distinguish what changes per use from what stays constant

### 4. Draft Template
- Clear, professional language
- All legally required elements
- Subject line template for email use

### 5. Define Escalation Triggers
- Specific situations where this template should NOT be used

### 6. Add Metadata
- Version, last reviewed date, author, approver
- Follow-up actions checklist

### Template Metadata Format

```
## Template: [Name]
**Category**: [type] | **Version**: [n] | **Last Reviewed**: [date]
**Approved By**: [name]

### Use When
- [Condition]

### Do NOT Use When (Escalation Triggers)
- [Trigger]

### Variables
| Variable | Description | Example |
|----------|-------------|---------|
| {{var}} | [what it is] | [example] |

### Body
[Template text with {{variables}}]

### Follow-Up Actions
1. [Post-send action]
```

---

## Action Item Tracking

After meetings or incident responses, capture action items:

```
## Action Items -- [Context] -- [Date]

| # | Action | Owner | Deadline | Priority | Type | Status |
|---|--------|-------|----------|----------|------|--------|
| 1 | [specific task] | [name] | [date] | [H/M/L] | [Legal/Business/External] | Open |
```

**Rules:**
- Be specific ("Send redline of Section 4.2" not "Follow up on contract")
- One owner per item (not a team)
- Specific date, not "soon" or "ASAP"
- Note dependencies on other actions or external input
- Distinguish: legal team actions, business team actions, external actions, follow-up meetings

**Review cadence:**
- High priority: daily until completed
- Medium priority: weekly
- Low priority: monthly
- Overdue: escalate to owner and manager
