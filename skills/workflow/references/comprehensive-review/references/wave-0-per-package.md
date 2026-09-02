# Wave 0: Per-Package Deep Review

## Package Discovery Commands

| Language | Discovery Command | Agent Type | Min Package Size |
|----------|-------------------|------------|-----------------|
| Go | `find . -name "*.go" -path "*/internal/*" \| xargs dirname \| sort -u` | `golang-general-engineer` | 1 file |
| Go (also) | `find . -name "*.go" -not -path "*/internal/*" -not -path "*/vendor/*" \| xargs dirname \| sort -u` | `golang-general-engineer` | 1 file |
| Python | `find . -name "__init__.py" \| xargs dirname \| sort -u` | `python-general-engineer` | 1 file |
| TypeScript | `find . -name "index.ts" -o -name "index.tsx" \| xargs dirname \| sort -u` | `typescript-frontend-engineer` | 1 file |

Full discovery commands (excluding vendor/venv/git):

```bash
# Go packages (internal/ and top-level)
find . -name "*.go" -not -path "*/vendor/*" -not -path "*/.git/*" | xargs dirname | sort -u

# Python packages
find . -name "__init__.py" -not -path "*/venv/*" -not -path "*/.git/*" | xargs dirname | sort -u

# TypeScript modules (directories with index.ts/tsx)
find . -name "index.ts" -o -name "index.tsx" | grep -v node_modules | xargs dirname | sort -u
```

## Agent Selection by Language

| Language | Agent |
|----------|-------|
| Go | `golang-general-engineer` |
| Python | `python-general-engineer` |
| TypeScript | `typescript-frontend-engineer` |
| Mixed | Use language of majority files in that package |

Use `model: sonnet` for ALL per-package agents. Never use haiku for code review. The orchestrator runs on Opus; dispatched agents run on Sonnet for cost efficiency (40% savings, minimal quality tradeoff).

## Per-Package Agent Dispatch Prompt

Dispatch up to 10 agents per message. If more than 10 packages are discovered, use multiple batches:
- Batch 1: packages 1-10 (dispatch in ONE message)
- Batch 2: packages 11-20 (dispatch in ONE message after batch 1 completes)
- Continue until all packages are covered

Each per-package agent gets this prompt:

```
PER-PACKAGE DEEP REVIEW — Wave 0

PACKAGE: [package path]
LANGUAGE: [Go/Python/TypeScript]

MCP TOOL DISCOVERY (do this FIRST, before reading package files):
- Use ToolSearch to check for available MCP tools that can enhance your analysis:
  a. Run ToolSearch("gopls") — if this is a Go package, loads type-aware analysis
     tools (go_file_context, go_diagnostics, go_symbol_references, etc.)
  b. Run ToolSearch("context7") — loads library documentation lookup tools
- If gopls tools are available AND LANGUAGE is Go:
  * Use go_file_context after reading each .go file for intra-package dependency context
  * Use go_diagnostics on the package to detect build/analysis errors
  * Use go_symbol_references to check for unused or misused exported symbols
- If Context7 tools are available:
  * Use resolve-library-id + query-docs for unfamiliar library APIs in this package

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Run MCP TOOL DISCOVERY steps above
3. Read EVERY file in this package directory: [package path]/
4. Understand the package's purpose, internal APIs, and relationships
5. Review ALL code for issues — you have full package context
6. Use MCP tools (gopls, Context7) as you review for type-aware precision
7. Focus on issues that require understanding the WHOLE package:
   - Internal API misuse between files in this package
   - Inconsistent error handling patterns within the package
   - Missing or redundant functionality
   - Package-level design issues (cohesion, coupling)
   - Test coverage relative to package complexity
8. Use structured output format with severity classification
9. Include file:line references for every finding

CONTEXT: This is Wave 0 of a comprehensive review. Your per-package findings
will be passed to 20 cross-cutting review agents in Waves 1 and 2. Focus on
issues that require full package context to detect — cross-cutting agents will
handle file-level and project-level concerns.

OUTPUT FORMAT:
### PACKAGE: [package path]
**Files reviewed**: [list all files read]
**Package purpose**: [1-sentence summary]
**Package health**: [HEALTHY | MINOR_ISSUES | NEEDS_ATTENTION | CRITICAL]

Findings:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file:LINE`
**Issue**: [Description]
**Impact**: [Why this matters]
**Fix**: [Concrete code fix]
**Requires package context**: [Why a single-file reviewer would miss this]
---
```

## Wave 0 Aggregate Output Format

After all per-package agents complete, build this summary for Wave 1+2 context injection:

```markdown
## Wave 0 Per-Package Findings Summary (for Wave 1+2 context)

### Packages Reviewed: [N]
### Packages Healthy: [N] | Minor Issues: [N] | Needs Attention: [N] | Critical: [N]

### Per-Package Results

#### [package/path1] — [HEALTHY|MINOR_ISSUES|NEEDS_ATTENTION|CRITICAL]
- Purpose: [1-sentence]
- Files: [N]
- Findings: [N] (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)
- Key issues:
  - [SEVERITY]: [summary] at [file:line]
  - ...

#### [package/path2] — [STATUS]
- ...

### Cross-Package Patterns Detected
- [Pattern 1]: Seen in packages [list] — suggests systemic issue
- [Pattern 2]: ...

### Wave 0 Hotspots (packages with most findings)
1. [package] — [N findings, N critical]
2. [package] — [N findings, N high]
3. ...
```
