# Conventional Commits Reference

Complete guide to conventional commit format with real examples from this repository.

## Format Specification

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Valid Types

| Type | Description | Example Use Case |
|------|-------------|------------------|
| `feat` | New feature | Adding a new agent, skill, or command |
| `fix` | Bug fix | Fixing broken functionality |
| `docs` | Documentation only | README updates, adding guides |
| `style` | Code style (formatting, no logic change) | Running formatter, fixing whitespace |
| `refactor` | Code restructuring (no behavior change) | Renaming variables, extracting functions |
| `perf` | Performance improvement | Optimizing algorithm, reducing memory usage |
| `test` | Adding or updating tests | New test cases, fixing test failures |
| `build` | Build system or dependencies | Updating package.json, Makefile |
| `ci` | CI/CD configuration | GitHub Actions, workflow updates |
| `chore` | Maintenance tasks | .gitignore updates, config changes |
| `revert` | Reverting previous commit | Rolling back broken change |

## Type Selection Guide

**Use `feat` when:**
- Adding completely new functionality
- Creating new files that provide new capabilities
- Examples:
  - `feat: add golang-general-engineer agent`
  - `feat: implement git-commit-flow skill`
  - `feat: add /do smart routing command`

**Use `fix` when:**
- Correcting broken behavior
- Resolving bugs reported by users
- Examples:
  - `fix: resolve race condition in cache invalidation`
  - `fix: correct error handling in validation script`
  - `fix: prevent sensitive file false positives`

**Use `docs` when:**
- ONLY documentation changes (no code)
- README, guides, API documentation
- Examples:
  - `docs: add installation instructions to README`
  - `docs: update agent creation guide`
  - `docs: add examples to git-commit-flow skill`

**Use `refactor` when:**
- Improving code structure without changing behavior
- Renaming for clarity
- Extracting reusable functions
- Examples:
  - `refactor: extract validation logic to separate function`
  - `refactor: simplify error handling in validate_state.py`
  - `refactor: rename ambiguous variable names`

**Use `test` when:**
- Adding new tests
- Fixing existing tests
- Updating test data
- Examples:
  - `test: add unit tests for sensitive file detection`
  - `test: update validation script test cases`
  - `test: add integration tests for commit workflow`

**Use `chore` when:**
- Maintenance tasks that don't fit other categories
- Configuration updates
- .gitignore changes
- Examples:
  - `chore: add .env to .gitignore`
  - `chore: update .editorconfig settings`
  - `chore: remove deprecated files`

## Scope (Optional)

Scope provides additional context about what part of the codebase is affected.

**Format**: `type(scope): description`

**Common scopes in this repository:**
- `agents` - Changes to agent files
- `skills` - Changes to skill files
- `commands` - Changes to command files
- `hooks` - Changes to hook system
- `docs` - Documentation (when combined with other types)

**Examples with scope:**
```
feat(agents): add systematic-debugging agent
fix(skills): resolve validation error in git-commit-flow
docs(commands): add usage examples for /do command
refactor(hooks): simplify routing-outcome scoring logic
```

**When to omit scope:**
- Changes affect multiple areas (cross-cutting)
- Scope is obvious from description
- Repository-wide changes (e.g., formatting all files)

## Subject Line Rules

**DO:**
- Start with lowercase (after `type:`)
- Use imperative mood ("add" not "added", "fix" not "fixes")
- Keep under 72 characters (50 preferred)
- Be specific and descriptive
- Omit period at end

**DON'T:**
- Start with uppercase (after `type:`)
- Use past tense
- End with period
- Be vague ("update stuff", "fix bug")
- Include issue numbers in subject (put in footer instead)

**Good Examples:**
```
feat: add user authentication flow
fix: resolve login timeout issue
docs: update API authentication guide
refactor: simplify validation logic
test: add authentication flow tests
```

**Bad Examples:**
```
feat: Added User Authentication.  ❌ (uppercase, past tense, period)
fix: fixes bug  ❌ (wrong tense, vague)
Update files  ❌ (no type, vague)
FEATURE: NEW STUFF  ❌ (uppercase, vague)
```

## Body (Optional but Recommended)

The body provides additional context about WHAT changed and WHY.

**Format:**
- Separated from subject by blank line
- Wrapped at 72 characters per line
- Use bullet points for multiple items
- Explain motivation and context
- Describe implementation approach (if complex)

**Example with body:**
```
feat: add git commit flow skill

Implements phase-gated commit workflow with:
- Sensitive file detection using regex patterns
- CLAUDE.md compliance enforcement
- Conventional commit message validation
- Smart file staging with grouping

This addresses inconsistent git operations scattered across
8 PR-related commands by providing a standardized, reusable
workflow.
```

**When to include body:**
- Change is non-trivial
- Context or motivation isn't obvious
- Implementation involves multiple steps
- Breaking changes or deprecations
- Security fixes

**When body can be omitted:**
- Change is obvious from subject
- Trivial fixes (typos, formatting)
- Simple refactoring

## Footer (Optional)

Footers provide metadata about the commit.

**Common footer types:**
- **Breaking changes**: `BREAKING CHANGE: description`
- **Issue references**: `Fixes #123`, `Closes #456`, `Refs #789`
- **Co-authors**: `Co-authored-by: Name <email@example.com>`
- **Signed-off**: `Signed-off-by: Name <email@example.com>`

**IMPORTANT: Repository CLAUDE.md Restrictions**

This repository PROHIBITS attribution footers:
- ❌ `Generated with Claude Code`
- ❌ `Co-Authored-By: Claude <noreply@anthropic.com>`
- ❌ `🤖 Generated`

**Breaking change example:**
```
feat!: change agent interface to async

BREAKING CHANGE: All agent implementations must now return
promises. Update existing agents by adding async/await.

Migration guide:
- Replace `def process()` with `async def process()`
- Add await when calling agents
```

**Issue reference example:**
```
fix: resolve authentication timeout

Fixes #123
Closes #124
Refs #125
```

## Real Examples from This Repository

### Example 1: Simple Feature
```
feat: add distinctive-frontend-design skill

Creates unique, context-driven frontend aesthetics that avoid
generic AI design patterns.
```

### Example 2: Bug Fix with Context
```
fix: resolve race condition in cache invalidation

The cache was not properly invalidating when multiple requests
arrived simultaneously. Added mutex lock to ensure atomic
invalidation operations.

Fixes #42
```

### Example 3: Documentation Update
```
docs: add agent creation guide to README

Adds comprehensive guide for creating new agents including:
- Agent structure requirements
- YAML frontmatter format
- Operator context definition
- Validation checklist
```

### Example 4: Refactoring
```
refactor: extract validation logic to separate module

Moves validation functions from main script to dedicated
validation.py module to improve code organization and
enable reuse across multiple scripts.
```

### Example 5: Multiple Related Changes
```
feat: implement routing-outcome hook system

Adds automatic routing outcome scoring with:
- Dispatch capture at PostToolUse:Agent
- Three-way outcome scoring on the next user turn
- Automatic feedback loop (success/failure tracking)
- Stop-time fallback for sessions with no following turn

This enables route-health reporting over time.
```

### Example 6: Breaking Change
```
feat!: migrate to Python 3.10+ type hints

BREAKING CHANGE: Python 3.9 and below are no longer supported.
All scripts now use PEP 604 union type syntax (X | Y instead
of Union[X, Y]).

Migration: Update Python to 3.10 or higher.
```

## Type Selection Flowchart

```
Does this add NEW functionality?
├─ YES → feat
└─ NO → Does this fix BROKEN functionality?
    ├─ YES → fix
    └─ NO → Is this ONLY documentation?
        ├─ YES → docs
        └─ NO → Does behavior stay the SAME?
            ├─ YES → Is structure improving?
            │   ├─ YES → refactor
            │   └─ NO → Is performance improving?
            │       ├─ YES → perf
            │       └─ NO → Is it code style?
            │           ├─ YES → style
            │           └─ NO → chore
            └─ NO → Are you adding/fixing tests?
                ├─ YES → test
                └─ NO → Is it build/CI related?
                    ├─ YES → build or ci
                    └─ NO → chore
```

## Common Mistakes and Fixes

### Mistake 1: Vague Subject
```
❌ fix: update stuff
✅ fix: resolve authentication timeout in login flow
```

### Mistake 2: Wrong Tense
```
❌ feat: added user authentication
✅ feat: add user authentication
```

### Mistake 3: Missing Type
```
❌ Update README installation section
✅ docs: update README installation section
```

### Mistake 4: Period at End
```
❌ feat: add new feature.
✅ feat: add new feature
```

### Mistake 5: Uppercase After Type
```
❌ feat: Add user authentication
✅ feat: add user authentication
```

### Mistake 6: Subject Too Long
```
❌ feat: add comprehensive user authentication flow with OAuth2 support and role-based access control
✅ feat: add user authentication with OAuth2 and RBAC

Implements comprehensive authentication flow with:
- OAuth2 login for external providers
- Role-based access control (RBAC)
- Token refresh mechanism
```

### Mistake 7: Including Banned Patterns
```
❌ feat: add new feature

Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>

✅ feat: add new feature

Implements XYZ functionality with ABC approach.
```

## Validation Checklist

Before committing, verify:

- [ ] Type is valid (feat, fix, docs, etc.)
- [ ] Subject starts with lowercase (after `type:`)
- [ ] Subject uses imperative mood
- [ ] Subject is under 72 characters
- [ ] Subject does NOT end with period
- [ ] Body is separated from subject by blank line
- [ ] Body lines are wrapped at 72 characters
- [ ] NO banned patterns (check CLAUDE.md)
- [ ] Describes WHAT changed and WHY

## Advanced: Conventional Commits with Semver

Conventional commits enable automatic semantic versioning:

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `fix:` | PATCH (1.0.0 → 1.0.1) | Bug fixes |
| `feat:` | MINOR (1.0.0 → 1.1.0) | New features (backward compatible) |
| `BREAKING CHANGE:` | MAJOR (1.0.0 → 2.0.0) | Breaking changes |
| Other types | No version bump | Documentation, tests, etc. |

**Example versioning workflow:**
```
1.0.0 (initial release)
  ↓ fix: resolve bug
1.0.1
  ↓ feat: add feature
1.1.0
  ↓ feat!: breaking change
2.0.0
```

## Tools and Automation

**Commitizen** - Interactive commit message helper
```bash
npm install -g commitizen
commitizen init cz-conventional-changelog --save-dev --save-exact

# Then use:
git cz
```

**Commitlint** - Validate commit messages in CI
```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional

# .commitlintrc.json
{
  "extends": ["@commitlint/config-conventional"]
}
```

**pr-workflow skill (commit intent)** - This skill provides validation
```bash
skill: pr-workflow commit
```

## References

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit)
- [Semantic Versioning](https://semver.org/)
- Repository CLAUDE.md (for project-specific rules)
