---
description: "Comprehensive PR review using specialized agents, with automatic retro knowledge capture"
argument-hint: "[review-aspects]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Agent"]
---

# Comprehensive PR Review (with Retro Learning)

Comprehensive PR review using specialized agents, with automatic knowledge capture.

This is a local fork of `pr-review-toolkit:review-pr` with a retro learning phase that
records review patterns to the knowledge store.

## Scope

This command accepts either a PR reference or a local branch diff. You do not need an open PR to use it.

| Invocation form | What it reviews |
|----------------|-----------------|
| `/pr-review` (no argument) | Uncommitted and committed local changes against the base branch (`HEAD` vs base) |
| `/pr-review 123` or `/pr-review https://github.com/org/repo/pull/123` | The diff of the specified open PR |

When no argument is provided, the command reads `git diff` to determine changed files. When a PR number or URL is provided, it fetches the PR diff via `gh pr view`. All review phases and retro learning apply in both cases.

## Usage

```
/pr-review              # Full review (all aspects)
/pr-review tests errors # Specific aspects only
/pr-review all parallel # All agents in parallel
```

**Related**: `/pr-review-address-feedback` — Process existing GitHub reviewer comments (validate-then-fix workflow)

## Review Aspects

- **comments** - Analyze code comment accuracy and maintainability
- **tests** - Review test coverage quality and completeness
- **errors** - Check error handling for silent failures
- **types** - Analyze type design and invariants (if new types added)
- **code** - General code review for project guidelines
- **simplify** - Simplify code for clarity and maintainability
- **all** - Run all applicable reviews (default)

## Instructions for Claude

**Review Aspects (optional):** "$ARGUMENTS"

### Phase 1: Determine Review Scope

1. Check git status to identify changed files: `git diff --name-only`
2. Parse arguments to see if user requested specific review aspects
3. Default: Run all applicable reviews
4. Check if PR already exists: `gh pr view 2>/dev/null`

### Phase 2: Identify Applicable Reviews

Based on changes:
- **Always applicable**: code-reviewer (general quality)
- **If test files changed**: pr-test-analyzer
- **If comments/docs added**: comment-analyzer
- **If error handling changed**: silent-failure-hunter
- **If types added/modified**: type-design-analyzer
- **If organization Go project** (see Phase 3 detection): organization-specific reviewer for convention compliance
- **After passing review**: code-simplifier (polish and refine)

### Phase 3: Detect Languages and Domain

Before launching agents, detect the primary language(s) of changed files:
- `.go` files → Go domain
- `.py` files → Python domain
- `.ts`/`.tsx` files → TypeScript domain
- `.md` files → Documentation domain

**Organization detection** (run this when Go files are present):
Check if this is an organization-specific Go project using ANY of:
1. Session context contains an org marker (injected by operator-context-detector hook at session start)
2. `go.mod` contains organization-specific imports
3. Module path matches organization patterns

If any check passes → **org domain**: add organization-specific reviewer to the agent list for Phase 4.

**gopls MCP Integration** (when `.go` files are in the diff):

When Go files are detected in the changed files, use gopls MCP tools to give every downstream review agent type-aware context:

1. Run `ToolSearch("gopls")` to fetch gopls tool schemas
2. Call `go_workspace` to understand module structure, build configuration, and workspace layout
3. Call `go_file_context` on EACH changed `.go` file to get intra-package dependency context (what other files in the same package this file depends on)
4. Collect all type-aware context (module structure, package dependencies, symbol relationships) and pass it as structured input to every review agent dispatched in Phase 4

This replaces text-only grep analysis with type-aware understanding — catching interface implementations, cross-package symbol usage, and dependency relationships that text search misses.

If gopls MCP is unavailable (ToolSearch returns no results), fall back to Grep-based analysis but note the limitation in the review output.

This determines which retro topics are relevant in Phase 8.

### Phase 3.5: Caller Tracing (Go signature/semantic changes)

**Trigger**: Run this phase for Go projects when the diff modifies any of:
- Function or method signatures (parameters added/removed/retyped)
- Parameter semantics (e.g., a parameter now accepts sentinel values like `"*"`)
- Exported symbols (new exports, changed interfaces)
- Sentinel or special values introduced (constants, magic strings, wildcard patterns)

**Skip condition**: If the diff only modifies function bodies without changing signatures, parameter semantics, or exported symbols, skip to Phase 4.

**Steps**:

1. **Identify changed symbols**: Scan the diff for all functions/methods whose signatures or parameter semantics changed. List each with its file, old signature, and new signature.

2. **Find ALL callers**: For each changed symbol:
   - **Preferred**: Use gopls `go_symbol_references` (type-aware, catches interface implementations)
   - **Fallback**: Grep with receiver syntax (e.g., `.GetEvents(` not just `GetEvents`) across the entire repo, excluding vendor/
   - Document the total caller count per symbol

3. **Verify each call site**: Read each caller and verify it has been updated for the new signature/semantics:
   - Does it pass the correct number/type of arguments?
   - Does it handle new return values or error conditions?
   - For interface methods: do ALL implementations honor the new contract?

4. **Trace security-sensitive parameters**: For parameters that control authorization, filtering, data access, or resource scoping:
   - Classify each value source: **user-controlled** (query params, form values, request body, headers) vs **server-controlled** (auth tokens, UUIDs, constants, config)
   - For user-controlled sources: verify validation exists BEFORE the value reaches the changed function
   - Verify sentinel value reachability by checking all input sources, including user input — a value like `"*"` meaning "unfiltered" may be constructed by users even if no Go code constructs it

5. **Document results** in structured format:
   ```
   CALLER TRACING RESULTS:

   Symbol: [package.Function/Method]
   Signature change: [old] → [new]
   Total callers: [N]

   Verified callers:
     - [file:line] — updated: YES | parameter source: [server-controlled]
     - [file:line] — updated: YES | parameter source: [user-controlled, validated at line N]

   Unverified/problematic callers:
     - [file:line] — ISSUE: [description]

   Security-sensitive parameters:
     - [param name]: [N] user-controlled sources, [M] validated, [K] UNVALIDATED
   ```

6. **Critical finding rule**: Any unvalidated caller passing user-controlled input to a security-sensitive parameter is a **Critical** finding. Feed all caller tracing results to review agents in Phase 4 as mandatory input context.

### Phase 4: Launch Review Agents

Use the pr-review-toolkit plugin agents (they're already available):

**Sequential approach** (default):
- Easier to understand and act on
- Each report is complete before next

**Parallel approach** (when user passes "parallel"):
- Launch all agents simultaneously via Agent tool
- Faster for comprehensive review

Each review agent writes its findings to a file (e.g., `pr-review-findings.md`) before returning, so context compaction cannot lose review output.

### Phase 5: Aggregate Results

After agents complete, summarize:
- **Critical Issues** (must fix before merge)
- **Important Issues** (should fix)
- **Suggestions** (nice to have)
- **Positive Observations** (what's good)

### Phase 6: Provide Action Plan

```markdown
# PR Review Summary

## Critical Issues (X found)
- [agent-name]: Issue description [file:line]

## Important Issues (X found)
- [agent-name]: Issue description [file:line]

## Suggestions (X found)
- [agent-name]: Suggestion [file:line]

## Strengths
- What's well-done in this PR

## Recommended Action
1. Fix critical issues first
2. Address important issues
3. Consider suggestions
4. Re-run review after fixes
```

### Phase 7: Apply Fixes (if requested)

If the user asks to fix issues, apply the fixes using the code-simplifier agent or direct edits.

### Phase 8: Retro Learning (run after every review)

After the review is complete and results are presented, extract reusable patterns.

**Step 1: Identify what was learned**

Review the findings from all agents and ask:
- Did we discover a recurring code pattern (good or bad) worth remembering?
- Did a specific review agent find something that applies broadly to this language/domain?
- Did we find a project-specific convention violation that should be documented?
- Did we discover a testing gap pattern that recurs across PRs?

If nothing reusable was learned, skip recording. Generic findings like "add more tests" are NOT worth recording.

**Step 2: Record via retro-record-adhoc**

For each reusable finding, call:

```bash
python3 ~/.claude/scripts/feature-state.py retro-record-adhoc TOPIC KEY "VALUE"
```

Where:
- **TOPIC**: Match the domain detected in Phase 3:
  - Go code → `go-patterns`
  - Python code → `python-patterns`
  - TypeScript code → `typescript-patterns`
  - Testing patterns → `testing`
  - Error handling patterns → `debugging`
  - General review patterns → `code-review-patterns`
- **KEY**: Short kebab-case identifier (e.g., `missing-context-cancel-check`, `n-plus-one-in-handler`)
- **VALUE**: 1-2 sentence specific, actionable finding. Not generic advice.

**Step 3: Report what was learned**

After the review summary, add a brief learning section:

```
LEARNED: [key] → [topic]
  [one-line value]
```

**Quality gate for recordings**:

| Record this | Don't record this |
|-------------|-------------------|
| "Missing defer rows.Close() in 3 of 5 SQL handlers" | "Close database resources" |
| "Test assertions check status code but never response body" | "Add more assertions" |
| "Error wrapping loses original context in middleware chain" | "Improve error handling" |
| "Unused exported types in api/ package suggest dead code" | "Remove unused code" |

Only record findings that are specific enough to be actionable guidance for future reviews.

## Agent Descriptions

**comment-analyzer**: Verifies comment accuracy vs code, identifies comment rot, checks documentation completeness.

**pr-test-analyzer**: Reviews behavioral test coverage, identifies critical gaps, evaluates test quality.

**silent-failure-hunter**: Finds silent failures, reviews catch blocks, checks error logging.

**type-design-analyzer**: Analyzes type encapsulation, reviews invariant expression, rates type design quality (4 dimensions, 1-10 each).

**code-reviewer**: Checks CLAUDE.md compliance, detects bugs and issues, reviews general code quality.

**code-simplifier**: Simplifies complex code, improves clarity and readability, applies project standards, preserves functionality.

## Tips

- **Run early**: Before creating PR, not after
- **Focus on changes**: Agents analyze git diff by default
- **Address critical first**: Fix high-priority issues before lower priority
- **Re-run after fixes**: Verify issues are resolved
- **Use specific reviews**: Target specific aspects when you know the concern
- **Learning accumulates**: Each review adds to the retro knowledge store, making future reviews smarter
