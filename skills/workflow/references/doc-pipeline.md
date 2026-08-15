---
description: "Structured 5-phase documentation pipeline with research."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
context: fork
command: /doc
routing:
  triggers:
    - document this
    - create readme
    - write documentation
    - document codebase
    - generate docs
    - technical documentation
    - "create documentation"
    - "write docs"
    - "generate README"
    - "document the API"
  pairs_with:
    - codebase-overview
    - technical-documentation-engineer
  complexity: medium
  category: documentation
---

# Documentation Pipeline Skill

## Instructions

This skill implements a **5-phase pipeline** for structured documentation creation with artifact persistence at each phase. Every phase produces a saved file to prevent work loss to context decay. Follow CLAUDE.md before starting: read and follow repository CLAUDE.md before any documentation work.

### Phase 1: RESEARCH

**Goal**: Gather comprehensive understanding of the subject before writing a single line of documentation.

**Why research first**: Jumping straight to generating prose based on a quick glance at the code produces shallow documentation that misses edge cases, prerequisites, and actual usage patterns. Users will not trust docs that omit critical details. Aspirational docs rot faster than any other kind of documentation.

**Step 1: Launch parallel subagents**

Three subagents run simultaneously with a 5-minute timeout:

| Subagent | Focus | Output |
|----------|-------|--------|
| Code Analysis | Components, public APIs, dependencies, configuration | Structured findings |
| Usage Patterns | Test examples, common patterns, edge cases, error scenarios | Examples with context |
| Context Gathering | Problem solved, audience, prerequisites, related docs | Context summary |

If a subagent times out (subject is too broad or codebase is very large):
1. Narrow the research scope to a specific module or component
2. Re-launch only the timed-out subagent with a more focused prompt
3. If still timing out, run research sequentially instead of in parallel

**Step 2: Compile research**

Merge subagent findings into a single research document. Resolve any contradictions between subagents by re-reading the actual source code.

**Step 3: Save artifact**

Write compiled research to `doc-research.md` in the working directory.

**Gate**: Research artifact exists with findings from all three subagents. Subject is understood well enough to outline. Proceed only when gate passes.

### Phase 2: OUTLINE

**Goal**: Structure documentation based on research findings before generating prose.

**Why outline first**: Outlining forces you to identify gaps where research is insufficient before you invest time in prose. It also prevents over-documentation where every private method and implementation detail makes readers unable to find what they actually need.

**Step 1: Identify sections**

Standard documentation structure (adapt based on subject):

```markdown
# [Subject]
## Overview        - What it is, what problem it solves
## Setup           - Installation, configuration, prerequisites
## Quick Start     - Minimal working example
## Usage           - Detailed usage with examples
## API Reference   - Function/method signatures (if applicable)
## Troubleshooting - Common issues and solutions
## See Also        - Related documentation
```

**Step 2: Assign research to sections**

Map each research finding to the section where it belongs. Identify gaps where research is insufficient and gather additional information. Document only public APIs, common tasks, and what users actually need to accomplish — not internal constants or every private method.

**Step 3: Save artifact**

Write outline to `doc-outline.md` in the working directory.

**Gate**: Outline covers all necessary sections. Every section has assigned content from research. No gaps remain. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Write documentation that is clear, accurate, and useful to the target audience.

**Why verify before publishing**: Documentation that sounds like a press release ("The system leverages enterprise-grade functionality...") drives readers away. Write like you're explaining to a colleague. Be direct. Be specific. Cut filler.

**Step 1: Load context**

Read `doc-research.md` and `doc-outline.md` to ground generation in verified facts.

**Step 2: Write each section**

For each outlined section:
- Write in clear, direct prose. Use concrete language instead of filler phrases and hedging.
- Include working code examples drawn from research findings
- Assume the reader's knowledge level matches the identified audience
- Start with what the user needs to know most urgently

**Step 3: Save artifact**

Write complete draft to `doc-draft.md` in the working directory.

**Gate**: Draft covers every section from the outline. All code examples are included. No placeholder text remains. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Prove every claim and example in the documentation is accurate.

**Why verification is mandatory**: Unverified docs erode trust over time. Broken examples destroy documentation credibility — one bad example makes users distrust all examples. If examples were derived from outdated patterns, test mocks, or incomplete context, execution will reveal the problem. Never document code that does not yet exist or features that are aspirational.

**Step 1: Execute code examples**

Run every code snippet in the documentation. Capture output. Compare against documented expectations.

If an example fails:
1. Re-read the actual source code for the function being demonstrated
2. Check if the function requires specific setup or environment
3. Rewrite the example based on working test cases in the codebase
4. If the function itself is broken, document the limitation rather than a broken example

**Step 2: Validate API signatures**

Cross-reference every function name, parameter, and return type against actual source code.

**Step 3: Check installation steps**

If the documentation includes setup instructions, execute them in order and confirm they work.

**Step 4: Fix issues**

For each verification failure:
1. Determine whether the documentation or the example is wrong
2. Fix the documentation to match reality (not the other way around)
3. Re-verify the fixed section

Maximum 3 fix-and-verify iterations. If still failing after 3 attempts, flag the section with a `<!-- NEEDS REVIEW -->` comment and proceed.

**Special case — No Usage Patterns**: If research finds no usage patterns (code is new, untested, or internal-only with no existing consumers):
1. Check git history for how the author used the code in commits
2. Look for related test files that exercise the code paths
3. Read the code directly and construct examples from the API surface
4. Flag the documentation as "based on API analysis, not observed usage"

**Gate**: All code examples execute. API signatures match source. Installation steps work. Proceed only when gate passes.

### Phase 5: OUTPUT

**Goal**: Deliver final documentation to its target location.

**Step 1: Write to target**

Copy verified documentation to the requested output location. If no location specified, write to the most logical path in the repository.

**Step 2: Produce verification report**

Append a brief summary of what was verified:

```markdown
<!-- Verification Report
- Code examples: X/Y passed
- API signatures: verified against source
- Installation steps: executed successfully
- Generated: [date]
-->
```

**Step 3: Clean up artifacts**

Remove `doc-research.md`, `doc-outline.md`, and `doc-draft.md` unless the user requests they be kept.

**Gate**: Final documentation exists at target location. Verification report attached. Artifacts cleaned up.

---

## Error Handling

### Error: "Subagent Timeout During Research"
Cause: Subject is too broad or codebase is very large, causing subagents to exceed 5-minute timeout
Solution:
1. Narrow the research scope to a specific module or component
2. Re-launch only the timed-out subagent with a more focused prompt
3. If still timing out, run research sequentially instead of in parallel

### Error: "Code Examples Fail Verification"
Cause: Examples were derived from outdated patterns, test mocks, or incomplete context
Solution:
1. Re-read the actual source code for the function being demonstrated
2. Check if the function requires specific setup or environment
3. Rewrite the example based on working test cases in the codebase
4. If the function itself is broken, document the limitation rather than a broken example

### Error: "Research Finds No Usage Patterns"
Cause: Code is new, untested, or internal-only with no existing consumers
Solution:
1. Check git history for how the author used the code in commits
2. Look for related test files that exercise the code paths
3. Read the code directly and construct examples from the API surface
4. Flag the documentation as "based on API analysis, not observed usage"

---

## References

This skill follows CLAUDE.md requirements for artifact persistence, verification gates, and scope discipline. Every claim must be verified against source code before publication. Code examples must be executed. Installation steps must be tested end-to-end. Documentation must represent what exists today, not aspirational features.
