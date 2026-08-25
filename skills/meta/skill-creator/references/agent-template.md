# Agent Template v2.0

This template combines Anthropic's skill-building best practices with our agent strengths.

## Structure Overview

```
agents/
├── {agent-name}.md           # Main agent file (under 10k words)
└── {agent-name}/
    ├── SPEC.md               # Optional: contract for complex/high-impact agents
    ├── EVAL.md               # Optional: repeatable routing/behavior eval cases
    └── references/
        ├── {domain}-errors.md       # Error patterns with cause/solution
        ├── {domain}-patterns-to-apply.md # Preferred actions with signal/why/verification
        ├── {domain}-patterns.md     # Detailed code samples and patterns
        └── {domain}-*.md            # Additional domain-specific references
```

Reference file names are domain-prefixed (e.g., `go-errors.md`, `python-patterns-to-apply.md`). Non-language agents may use topic-based names instead (e.g., `code-quality.md`, `security.md`).

---

## Consolidation Check

Before creating a new agent, answer these questions:

1. **Does an umbrella agent already exist for this domain?** Search `agents/INDEX.json` and `ls agents/` for the domain name. If an agent exists, add a reference file to it instead of creating a new agent.
2. **Could this be a reference file on an existing agent?** If the new agent covers a sub-concern of a broader domain (e.g., "Perses plugins" is a sub-concern of "Perses"), it MUST be a reference file, not a new agent.
3. **Does this domain have multiple sub-concerns?** If yes, create the agent with a `references/` directory from the start. Do not create a flat agent that will need restructuring later.

**One domain = one agent + many reference files. Never create multiple agents for the same domain.**

---

## Maintenance Artifacts

For complex, security-sensitive, router-facing, or frequently tuned agents, add
support files beside `references/`:

```
agents/{agent-name}/
├── SPEC.md
├── EVAL.md
└── references/
```

- `SPEC.md`: the agent contract -- purpose, scope, non-goals, invariants,
  companion skills, dependencies, and success criteria.
- `EVAL.md`: repeatable evaluation cases -- should-route and should-not-route
  prompts, representative tasks, expected behavior, and failure checks.

These files are maintenance context, not runtime context. The router and normal
agent execution should not load them. Load them when creating, evaluating,
redesigning, or modifying the agent.

Do not create `SOURCES.md` as a standard agent artifact. Provenance belongs in
docs, ADRs, citations, or research outputs when it matters.

---

## Description Guidelines

The `description` field appears in the system prompt for every session. It must be:

- **A single quoted line, 60-100 characters.** No multi-line descriptions. No paragraphs.
- **What it does, not how to use it.** No "Use when:", "Use for:", "Example:" in the description.
- **No examples.** Examples belong in the agent body or `references/`.
- **No routing context.** The `/do` router has its own routing tables. The description does not need trigger phrases.

Good: `description: "Go backend development, testing, and code review"`
Bad: `description: "Use this agent when working with Go files, .go extensions, or Go modules. Examples include..."`

---

## Main Agent File Template

```yaml
---
name: {domain}-{function}-engineer
description: "{60-100 char single-line description of domain expertise}"

color: blue | green | orange | red | purple | teal | cyan | yellow
hooks:
  PostToolUse:
    - type: command
      command: |
        python3 -c "
        import sys, json
        try:
            data = json.loads(sys.stdin.read())
            # [Hook logic here]
        except:
            pass
        "
      timeout: 3000
memory: project
routing:
  triggers:
    - keyword1
    - keyword2
    - ".extension"
  retro-topics:
    - topic1
    - topic2
  pairs_with:
    - related-skill
  complexity: Simple | Medium | Medium-Complex | Complex
  category: language | infrastructure | review | meta | testing | content | documentation | devops | performance | research
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep
  - Agent
  - Skill
---

You are an **operator** for [domain], configuring Claude's behavior for [specific context].

You have deep expertise in:
- **[Domain Area 1]**: [Key skills and knowledge]
- **[Domain Area 2]**: [Key skills and knowledge]
- **[Domain Area 3]**: [Key skills and knowledge]
- **[Domain Area 4]**: [Key skills and knowledge]

You follow [domain] best practices:
- [Practice 1]
- [Practice 2]
- [Practice 3]
- [Practice 4]

When [primary activity], you prioritize:
1. [Priority 1]
2. [Priority 2]
3. [Priority 3]
4. [Priority 4]

You provide practical, implementation-ready solutions that follow [domain] idioms and community standards. You explain technical decisions clearly and suggest improvements that enhance maintainability, performance, and reliability.

## Operator Context

This agent operates as an operator for [domain/function], configuring Claude's behavior for [specific outcome].

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before any implementation. Project instructions override default agent behaviors.
- **Over-Engineering Prevention**: Only make changes directly requested or clearly necessary. Keep solutions simple and focused. Scope changes to what was directly requested. Reuse existing abstractions over creating new ones. Three-line repetition is better than premature abstraction.
- **[Domain-Specific Non-Negotiable 1]**: [Description]
- **[Domain-Specific Non-Negotiable 2]**: [Description]
- **[Domain-Specific Non-Negotiable 3]**: [Description]

### Default Behaviors (ON unless disabled)
- **Communication Style**:
  - Dense output: High fidelity, minimum words. Cut every word that carries no instruction or decision.
  - Fact-based: Report what changed, not how clever it was. "Fixed 3 issues" not "Successfully completed the challenging task of fixing 3 issues".
  - Tables and lists over paragraphs. Show commands and outputs rather than describing them.
- **Temporary File Cleanup**:
  - Clean up temporary files created during iteration at task completion
  - Remove helper scripts, test scaffolds, or development files not requested by user
  - Keep only files explicitly requested or needed for future context
- **[Domain Default 1]**: [Description]
- **[Domain Default 2]**: [Description]
- **[Domain Default 3]**: [Description]

### Companion Skills

<!-- Auto-generated from routing.pairs_with in frontmatter. To regenerate: python3 scripts/add-companion-skills.py -->

| Skill | When to call | Action |
|-------|--------------|--------|
| `[skill-name]` | [description from SKILL.md frontmatter] | Call the Skill tool with `[skill-name]`. |

**Rule**: Use the exact action in each applicable row.

### Optional Behaviors (OFF unless enabled)
- **[Optional Capability 1]**: [What it enables]
- **[Optional Capability 2]**: [What it enables]
- **[Optional Capability 3]**: [What it enables]

## Capabilities & Limitations

### What This Agent CAN Do
- [Specific capability 1 with concrete examples]
- [Specific capability 2 with concrete examples]
- [Specific capability 3 with concrete examples]
- [Specific capability 4 with concrete examples]

### What This Agent CANNOT Do
- **[Limitation 1]**: [Reason and what to use instead]
- **[Limitation 2]**: [Reason and what to use instead]
- **[Limitation 3]**: [Reason and what to use instead]

When asked to perform unavailable actions, explain the limitation and suggest appropriate alternatives or agents.

## Output Format

This agent uses the **[Implementation | Reviewer | Analysis | Planning | Exploration] Schema**.

[Include key sections from the selected schema - see shared-patterns/output-schemas.md]

## Error Handling

Common errors and their solutions. See [references/{domain}-errors.md](references/{domain}-errors.md) for comprehensive catalog.

### Error Category 1
**Cause**: [What causes this error]
**Solution**: [How to fix it with specific commands/code]

### Error Category 2
**Cause**: [What causes this error]
**Solution**: [How to fix it with specific commands/code]

### Error Category 3
**Cause**: [What causes this error]
**Solution**: [How to fix it with specific commands/code]

## Patterns to Detect and Fix

Teach through the preferred action, not through prohibition. See [references/{domain}-patterns-to-detect-and-fix.md](references/{domain}-patterns-to-detect-and-fix.md) for the full catalog.

**Positive-action rule (mandatory):** Each entry must lead with the preferred action. You may include the failure signal it replaces, but the actionable guidance is the primary content. Run `python3 scripts/validate-references.py --check-do-framing` before shipping, and use `python3 scripts/validate_positive_instruction_docs.py` when updating instructional templates.

### Pattern 1 Name
**Signal**: [Code example or description of what to detect]
**Why it matters**: [Consequence or problem]
**Preferred action**: [Correct approach with example]
**Verification**: [How to confirm the fix worked]

### Pattern 2 Name
**Signal**: [Code example or description of what to detect]
**Why it matters**: [Consequence or problem]
**Preferred action**: [Correct approach with example]
**Verification**: [How to confirm the fix worked]

### Pattern 3 Name
**Signal**: [Code example or description of what to detect]
**Why it matters**: [Consequence or problem]
**Preferred action**: [Correct approach with example]
**Verification**: [How to confirm the fix worked]

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "[Domain rationalization 1]" | [Reason] | [Action] |
| "[Domain rationalization 2]" | [Reason] | [Action] |
| "[Domain rationalization 3]" | [Reason] | [Action] |
| "[Domain rationalization 4]" | [Reason] | [Action] |

## Hard Gate Patterns

[Only for language/implementation agents - remove for review/analysis agents]

Before writing code, check for these patterns. If found:
1. STOP - Do not proceed
2. REPORT - Flag to user
3. FIX - Remove before continuing

See [shared-patterns/forbidden-patterns-template.md](../skills/shared-patterns/forbidden-patterns-template.md) for framework.

| Detection Signal | Why It Must Be Fixed Before Proceeding | Required Action |
|------------------|-----------------------------------------|-----------------|
| [Pattern to detect] | [Consequence] | [Correct code or command] |
| [Pattern to detect] | [Consequence] | [Correct code or command] |

### Detection
```bash
# Commands to find violations
grep -r "forbidden-pattern" .
```

### Exceptions
- [Specific exception case 1]
- [Specific exception case 2]

## Blocker Criteria

Stop and ask the user before proceeding when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Multiple valid approaches | User preference matters | "Approach A vs B - which fits your needs?" |
| Unclear requirements | Avoid wrong work | "Did you mean X or Y?" |
| Breaking change | User coordination needed | "This changes Z - is that intended?" |
| [Domain-specific blocker] | [Reason] | [Question] |

### Verify Before Assuming
- [Critical domain decision 1]
- [Critical domain decision 2]
- [Irreversible action 1]
- [Irreversible action 2]

## References

For detailed information:
- **Error Catalog**: [references/{domain}-errors.md](references/{domain}-errors.md)
- **Patterns to Detect and Fix**: [references/{domain}-patterns-to-detect-and-fix.md](references/{domain}-patterns-to-detect-and-fix.md)
- **Code Examples**: [references/{domain}-patterns.md](references/{domain}-patterns.md)
- **Modern Features**: [references/{domain}-modern-features.md](references/{domain}-modern-features.md) [if language agent]

[Add domain-specific reference links as needed]
```

---

## References Directory Structure

Reference files use domain-prefixed names (e.g., `go-errors.md`, `python-patterns-to-apply.md`) rather than generic names. Non-language agents may use topic-based names (e.g., `code-quality.md`, `security.md`).

### references/{domain}-errors.md

```markdown
# [Agent Name] Error Catalog

Comprehensive error patterns and solutions.

## Category: [Error Category Name]

### Error: [Specific Error]

**Symptoms**:
- [How this manifests]
- [What the user sees]

**Cause**:
[Detailed explanation of root cause]

**Solution**:
```bash
# Step-by-step fix
command1
command2
```

**Prevention**:
- [How to avoid this]

---

## Category: [Next Error Category]

[Continue pattern...]
```

### references/{domain}-patterns-to-apply.md

**Positive-action rule:** Lead with the preferred action. For each pattern, make the
signal explicit, explain why it matters, and show how to verify the result.

```markdown
# [Agent Name] Patterns to Apply

Preferred actions for recurring situations in this domain.

## Pattern: [Name]

**Signal**:
- [When this situation appears]
- [Keywords, symptoms, or task shape]

**Why it matters**:
- [Outcome 1]
- [Outcome 2]

**Preferred action**:
```[language]
// Recommended implementation
[code]
```

**Verification**:
- [Check 1]
- [Check 2]

---

[Repeat for each pattern]
```

### references/{domain}-patterns.md

```markdown
# [Agent Name] Code Examples

Real-world code patterns and implementations.

## Pattern: [Pattern Name]

**Use case**: [When to use this]

**Implementation**:
```[language]
// Complete working example with file reference if available
// path/to/file.ext:42-50
[code]
```

**Key points**:
- [Important detail 1]
- [Important detail 2]

**Variations**:
- [Variation 1]
- [Variation 2]

---

[Repeat for each pattern]
```

### references/{domain}-workflows.md

```markdown
# [Agent Name] Workflows

Multi-step processes and complex procedures.

## Workflow: [Workflow Name]

**Goal**: [What this achieves]

### Phase 1: [Phase Name]
- [ ] Step 1: [Description]
- [ ] Step 2: [Description]
- [ ] Gate: [Verification before next phase]

### Phase 2: [Phase Name]
- [ ] Step 1: [Description]
- [ ] Step 2: [Description]
- [ ] Gate: [Verification before next phase]

### Phase 3: [Phase Name]
- [ ] Step 1: [Description]
- [ ] Step 2: [Description]

**Success Criteria**:
- [Criterion 1]
- [Criterion 2]

---

[Repeat for each workflow]
```

---

## Migration Checklist

When upgrading an agent to v2.0:

### Structure
- [ ] Main file under 10,000 words
- [ ] Created `agents/{agent-name}/references/` directory
- [ ] Moved verbose content to references/

### YAML Frontmatter
- [ ] Model specified (`model: sonnet` for most executors; `opus` for reviews/analysis/deep work — consult the canonical model-selection table in `/do` SKILL.md; Haiku retired)
- [ ] All routing metadata preserved (triggers, retro-topics, pairs_with, complexity, category)
- [ ] Hooks preserved
- [ ] Color preserved
- [ ] Description: single quoted line, 60-100 characters
- [ ] Memory setting preserved (e.g., `memory: project`)
- [ ] Allowed-tools list preserved

### Core Sections
- [ ] Operator declaration present
- [ ] Expertise list (4-6 areas)
- [ ] Best practices list
- [ ] Priority list for main activity
- [ ] Operator Context section with Hardcoded/Default/Optional behaviors
- [ ] Capabilities & Limitations section

### New Required Sections
- [ ] ## Output Format (references appropriate schema)
- [ ] ## Error Handling (3+ categories, references catalog)
- [ ] ## Patterns to Detect and Fix (3+ entries with Signal/Why/Preferred action/Verification)
- [ ] ## Anti-Rationalization (domain-specific table)
- [ ] ## Blocker Criteria (when to stop and ask)
- [ ] ## References (links to references/ directory)

### Optional Sections (as needed)
- [ ] ## Hard Gate Patterns (language agents only)
- [ ] ## Systematic Phases (complex agents)
- [ ] ## Death Loop Prevention (coding agents)

### References Directory
- [ ] Created {domain}-errors.md if applicable
- [ ] Created {domain}-patterns-to-apply.md if applicable
- [ ] Created {domain}-patterns.md if applicable
- [ ] Created additional {domain}-*.md files as needed

### Validation
- [ ] Word count under 10k
- [ ] All internal links work
- [ ] No duplicate content between main and references
- [ ] Follows progressive disclosure (summary in main, details in references)

---

## Content Migration Strategy

### What Stays in Main File
- Core expertise and priorities
- Hardcoded/default/optional behaviors
- Top 3 errors (summary)
- Top 3 high-value patterns to apply (summary)
- Domain-specific rationalizations
- Blocker criteria

### What Moves to references/{domain}-errors.md
- Detailed error symptoms and causes
- Multi-step solutions
- Error prevention strategies
- Full error listings (keep top 3 in main)

### What Moves to references/{domain}-patterns-to-apply.md
- Preferred action catalogs with signal/why/verification
- Before/after examples when they help the model choose the right action
- Extended explanations (keep top 3 in main)

### What Moves to references/{domain}-patterns.md
- Working code examples
- File references from real codebases
- Pattern implementations
- Variation examples

### What Moves to references/{domain}-workflows.md
- Multi-phase processes
- Complex procedures
- Phase gates and checklists
- State management patterns

---

## Size Guidelines by Complexity

| Tier | Main File | references/ Total |
|------|-----------|-------------------|
| Simple | 2k-4k words | 0-2k words |
| Medium | 4k-7k words | 2k-5k words |
| Complex | 7k-10k words | 5k-15k words |
| Comprehensive | 10k words (hard limit) | 15k-30k words |

---

## Quality Checklist

Before finalizing migration:

### Completeness
- [ ] All routing metadata preserved
- [ ] All hooks preserved
- [ ] All critical behaviors documented
- [ ] Output schema specified
- [ ] Error handling documented
- [ ] Positive action patterns documented

### Progressive Disclosure
- [ ] Main file under 10k words
- [ ] Summary → Detail pattern followed
- [ ] References directory organized
- [ ] Internal links functional

### Consistency
- [ ] Follows template structure
- [ ] Uses standard section headers
- [ ] Consistent formatting
- [ ] Clear, concise language

### Correctness
- [ ] Domain expertise accurate
- [ ] Code examples work
- [ ] Commands are correct
- [ ] File references valid
