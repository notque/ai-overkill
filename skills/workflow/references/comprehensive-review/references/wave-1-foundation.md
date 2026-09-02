# Wave 1: Foundation Agents (12 agents)

These agents run in parallel with Wave 0 per-package findings as context. They perform cross-cutting analysis that spans packages and establish the foundation for Wave 2.

**ALL 12 agents MUST be dispatched in ONE message for true parallel execution.**

Use `model: sonnet` for all Wave 1 agents. The orchestrator runs on Opus; dispatched agents run on Sonnet.

## Agent Roster

| # | Agent | Focus Area | Key Catches |
|---|-------|------------|-------------|
| 1 | `reviewer-system` (security lens) | Security | OWASP Top 10, auth, injection, secrets |
| 2 | `reviewer-domain` (business-logic lens) | Domain | Edge cases, state transitions, requirement gaps |
| 3 | Architecture reviewer* | Architecture | Patterns, naming, structure, idioms |
| 4 | `reviewer-system` (silent-failures lens) | Error Handling | Swallowed errors, empty catches, bad fallbacks |
| 5 | `reviewer-code` (test-analyzer lens) | Test Coverage | Coverage gaps, fragile tests, missing negative cases |
| 6 | `reviewer-code` (type-design lens) | Type Design | Weak invariants, leaky encapsulation |
| 7 | `reviewer-code` (quality lens) | Quality/Style | CLAUDE.md violations, convention drift |
| 8 | `reviewer-code` (comment-analyzer lens) | Documentation | Comment rot, misleading docs, stale TODOs |
| 9 | `reviewer-code` (language-specialist lens) | Language Idioms | Modern stdlib, concurrency, LLM tells, org-specific rules |
| 10 | `reviewer-code` (docs-validator lens) | Project Health | README, CLAUDE.md, deps, CI, build system |
| 11 | `reviewer-domain` (adr-compliance lens) | ADR Compliance | Implementation matches ADR decisions, no scope creep |
| 12 | `reviewer-perspectives` (newcomer lens) | Newcomer Perspective | Documentation gaps, confusing code, implicit assumptions, onboarding friction |

*Architecture reviewer selection by language:

| File Types | Agent |
|-----------|-------|
| `.go` files | `golang-general-engineer` |
| `.py` files | `python-general-engineer` |
| `.ts`/`.tsx` files | `typescript-frontend-engineer` |
| Mixed or other | `Explore` |

## Standard Agent Prompt Template

Each agent prompt includes:

```
REVIEW SCOPE:
- Files to review: [list of changed files]
- Change context: [what was changed and why, if known]
- Repository: [current directory]

WAVE 0 PER-PACKAGE CONTEXT (deep per-package review results):
[Insert $WAVE0_CONTEXT — loaded from $REVIEW_DIR/wave0-findings.md]

MCP TOOL DISCOVERY (do this FIRST, before any file reads):
- Use ToolSearch to check for available MCP tools that can enhance your analysis:
  a. Run ToolSearch("gopls") — if Go files are in scope, this loads type-aware
     analysis tools (go_file_context, go_diagnostics, go_symbol_references, etc.)
  b. Run ToolSearch("context7") — loads library documentation lookup tools for
     verifying dependency usage and API correctness
- If gopls tools are available AND this is a Go repository:
  * Use go_file_context after reading any .go file to understand intra-package dependencies
  * Use go_symbol_references before flagging unused or misused symbols
  * Use go_diagnostics on files you flag to confirm real vs false-positive issues
- If Context7 tools are available:
  * Use resolve-library-id + query-docs to verify library API usage in flagged code

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Run MCP TOOL DISCOVERY steps above
3. Review the Wave 0 per-package context to understand package-level findings
4. Review the specified files for issues in your domain
5. Use Wave 0 findings to AVOID duplicating per-package issues already found
6. Focus on CROSS-CUTTING concerns that span multiple packages
7. Use MCP tools (gopls, Context7) during analysis where they add precision
8. Use structured output format with severity classification
9. Include file:line references for every finding
10. For each finding, provide a concrete fix recommendation

OUTPUT FORMAT:
Return findings as:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file:LINE`
**Issue**: [Description]
**Impact**: [Why this matters]
**Fix**: [Concrete code fix]
**Wave 0 Cross-Ref**: [Which Wave 0 package finding this relates to, if any]
---
```

## Agent-Specific Prompt Additions

| Agent | Extra Instructions |
|-------|-------------------|
| `reviewer-system` (security) | Focus on OWASP Top 10, auth, input validation, and secrets. **MCP**: For Go, use gopls `go_symbol_references` to trace tainted input flows. **CALLER TRACING (mandatory)**: When the diff modifies functions with security-sensitive parameters (auth tokens, filter flags, sentinel values like `"*"`), grep for all callers across the repo and verify that each one validates the parameter. Verify independently rather than relying on PR descriptions. |
| `reviewer-domain` (business-logic) | Focus on requirements coverage, edge cases, and state transitions. **CALLER TRACING (mandatory)**: When the diff changes interface semantics or introduces sentinel values, grep for all callers (`.MethodName(`) across the repo and verify that each honors the contract. Search before concluding that no caller passes X. |
| Architecture reviewer | Focus on patterns, naming, structure, maintainability. **MCP**: For Go, use gopls `go_file_context` to understand cross-file dependencies |
| `reviewer-system` (silent-failures) | Focus on catch blocks, error swallowing, fallback behavior. **MCP**: For Go, use gopls `go_diagnostics` to verify error handling correctness |
| `reviewer-code` (test-analyzer) | Focus on coverage gaps, missing edge case tests, test quality. **ASSERTION DEPTH CHECK (mandatory)**: For security-sensitive code, flag presence-only assertions (NotEmpty, NotNil, hasKey). Tests MUST verify actual values, not just existence. |
| `reviewer-code` (type-design) | Focus on invariants, encapsulation, type safety. **MCP**: For Go, use gopls `go_package_api` to understand type surface area |
| `reviewer-code` (quality) | Focus on CLAUDE.md compliance, conventions, style |
| `reviewer-code` (comment-analyzer) | Focus on comment accuracy, rot, misleading docs |
| `reviewer-code` (language-specialist) | Detect language from files, check modern stdlib, idioms, concurrency, LLM tells. **MCP**: For Go files, use gopls `go_file_context` and `go_diagnostics` to detect non-idiomatic patterns with type awareness. If org conventions detected, append org-specific flags to prompt. |
| `reviewer-code` (docs-validator) | Check README.md, CLAUDE.md, deps, CI config, build system, LICENSE. Review the project, not the code. **MCP**: Use Context7 to verify documented library versions/APIs match actual usage |
| `reviewer-domain` (adr-compliance) | Auto-discover ADRs from `adr/` and `.adr-session.json`. Check every decision point has implementation, no contradictions, no scope creep. Output ADR COMPLIANT or NOT ADR COMPLIANT. |
| `reviewer-perspectives` (newcomer) | Review from a newcomer/fresh-eyes perspective. Focus on: documentation gaps that would confuse a new developer, implicit assumptions not explained in code or comments, confusing variable/function names, unclear control flow, missing "why" explanations. Flag anything where a developer unfamiliar with this codebase would be lost. |

## Wave 0+1 Aggregate Output Format

After Wave 1 completes, build this combined summary for Wave 2 context:

```markdown
## Wave 0+1 Findings Summary (for Wave 2 context)

### Wave 0 Per-Package Summary: [N packages reviewed]
- Packages with issues: [list with health status]
- Cross-package patterns: [list]
- Hotspot packages: [top 3 by finding count]
- Key per-package findings:
  - [package]: [SEVERITY] [summary]
  - ...

### Security — reviewer-system (Agent 1): [N findings]
- CRITICAL: [list if any]
- HIGH: [list]
- Files with security issues: [list]

### Business Logic — reviewer-domain (Agent 2): [N findings]
- State transitions identified: [list]
- Edge cases flagged: [list]
- Files with domain issues: [list]

### Architecture (Agent 3): [N findings]
- Architectural patterns noted: [list]
- Hot paths identified: [list]
- Files with structural issues: [list]

### Silent Failures — reviewer-system (Agent 4): [N findings]
- Swallowed errors at: [file:line list]
- Error paths without handling: [list]
- Files with error handling gaps: [list]

### Test Coverage — reviewer-code (Agent 5): [N findings]
- Coverage gaps: [list]
- Untested paths: [list]

### Type Design — reviewer-code (Agent 6): [N findings]
- Weak types identified: [list]
- Type safety issues at: [file:line list]

### Code Quality — reviewer-code (Agent 7): [N findings]
- Convention baseline established: [patterns]
- Convention violations: [list]
- CLAUDE.md compliance issues: [list]

### Comments — reviewer-code (Agent 8): [N findings]
- Comment rot at: [file:line list]
- Stale TODOs: [list]

### Language Specialist — reviewer-code (Agent 9): [N findings]
- Language-specific issues: [list]
- Modern stdlib opportunities: [list]
- LLM code tells: [list]

### Docs & Config — reviewer-code (Agent 10): [N findings]
- Documentation gaps: [list]
- Dependency issues: [list]
- CI/build issues: [list]

### ADR Compliance — reviewer-domain (Agent 11): [N findings]
- ADR decisions not implemented: [list]
- ADR contradictions: [list]
- Scope creep: [list]

### Newcomer Perspective — reviewer-perspectives (Agent 12): [N findings]
- Documentation gaps: [list]
- Confusing code: [list]
- Implicit assumptions: [list]
- Onboarding friction: [list]
```
