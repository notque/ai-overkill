# Implementer Subagent Prompt Template

Use this template when dispatching the implementer subagent via the Task tool.

## Template

```
You are implementing a specific task from an implementation plan.

## Scene-Setting Context

{PROJECT_CONTEXT}

This is a {LANGUAGE} project. Key conventions:
{CONVENTIONS}

Current branch: {BRANCH}
Tests command: {TEST_COMMAND}
**Base SHA (before this task):** {BASE_SHA}

## Your Task

**Task {TASK_NUMBER}: {TASK_TITLE}**

{FULL_TASK_TEXT}

**Files to modify/create:**
{FILE_LIST}

**Verification:**
{VERIFICATION_STEPS}

## Instructions

1. **Understand First** - Read the task completely. Resolve routine choices from the request and repository. Ask before implementing when a missing decision materially affects the task. Executor-ready STOP conditions still apply.

2. **Verify behavior** - Use TDD where appropriate. Run relevant and project-required checks using `verification-before-completion`; preserve explicit per-step verification contracts.

3. **Stay Focused** - Only implement what the task specifies. No "while I'm here" improvements.

4. **Test Your Work** - Run tests before committing. All tests should pass.

5. **Self-Review** - Before committing, review your own code for obvious issues.

6. **Commit** - Commit your changes with a clear message.

## Questions?

If you have questions about:
- The requirements
- How to approach something
- What conventions to follow
- Anything else

Use the supplied context first. Ask for missing decisions that affect correctness or scope; continue independent work while waiting.

## Output

When done, report:
- What you implemented
- Tests status (all pass?)
- Self-review findings (if any issues you fixed)
- Commit message used

Begin the task when its requirements are clear; ask only for a needed decision.
```

## Placeholder Definitions

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{PROJECT_CONTEXT}` | Brief project description | "This is the user-preferences service that handles storing and retrieving user settings." |
| `{LANGUAGE}` | Primary language | "Go", "Python", "TypeScript" |
| `{CONVENTIONS}` | Key conventions from CLAUDE.md | "- Use snake_case for functions\n- Tests go in _test.go files" |
| `{BRANCH}` | Current git branch | "feature/add-user-preferences" |
| `{TEST_COMMAND}` | How to run tests | "go test ./...", "pytest", "npm test" |
| `{BASE_SHA}` | Git SHA before implementation starts | Run `git rev-parse HEAD` before dispatching |
| `{TASK_NUMBER}` | Task number from plan | "1", "2", etc. |
| `{TASK_TITLE}` | Task title from plan | "Create database migration" |
| `{FULL_TASK_TEXT}` | Complete task description | The full text from the plan, NOT "see plan" |
| `{FILE_LIST}` | Files to modify/create | "- Create: /path/to/new_file.py\n- Modify: /path/to/existing.py" |
| `{VERIFICATION_STEPS}` | How to verify success | "Run `python manage.py check` - should exit 0" |

## Example Filled Template

```
You are implementing a specific task from an implementation plan.

## Scene-Setting Context

This is the user-preferences service that handles storing and retrieving user settings for the main application.

This is a Python project. Key conventions:
- Use snake_case for functions and variables
- Tests go in tests/ directory
- Use pytest for testing
- Type hints required for public functions

Current branch: feature/add-user-preferences
Tests command: pytest tests/
**Base SHA (before this task):** a1b2c3d4

## Your Task

**Task 1: Create database migration**

Create a database migration to add the user_preferences table with the following columns:
- id (primary key, auto-increment)
- user_id (foreign key to users.id, unique)
- theme (string, default 'light')
- notifications_enabled (boolean, default true)
- created_at (timestamp)
- updated_at (timestamp)

The migration should be reversible.

**Files to modify/create:**
- Create: /home/user/project/migrations/0045_add_user_preferences.py

**Verification:**
- Run `python manage.py check` - should exit 0
- Run `python manage.py migrate --dry-run` - should show this migration

Follow the template instructions above. Report the implementation, checks, self-review findings, and commit.

```

## Executor-Ready Plans

When the plan follows `skills/process/planning/references/executor-ready-plan-template.md`, append this block to the dispatch prompt (fill `{PLAN_BASE_SHA}` from the plan's Metadata — this is the plan-creation SHA, not `{BASE_SHA}` above):

```
## Executor Contract (executor-ready plan)

Before touching any file, run the drift check:
- `git merge-base --is-ancestor {PLAN_BASE_SHA} HEAD` must succeed. Commits from this plan's earlier tasks are not drift.
- Before editing a file, confirm the step's inlined Context excerpt still matches the file.

Execute steps in order. Run each step's Verify command and match its Expected output before proceeding.

STOP and escalate — report what you completed, what triggered the stop, and what decision you need — when any of these fire:
1. Drift: ancestry check fails or a Context excerpt no longer matches.
2. A step's Verify command fails twice (one retry allowed).
3. Completing a step requires touching a file in the plan's Out-of-scope list, or any file absent from the In-scope list.
4. A step's Do section is ambiguous, or a (required) plan section is missing.
5. A previously passing test fails after a step.

Do not improvise past a STOP.
```

## Handling Questions

When implementer asks questions:

1. **Answer completely** - Don't be vague
2. **Provide context** - Why is this the answer?
3. **Re-dispatch if needed** - With answers included in prompt

Example Q&A flow:
```
Implementer: "Should the theme column allow NULL values?"

Answer: "No, theme should not be NULL. Use 'light' as default. This ensures
every user has a valid theme setting."

[Re-dispatch implementer with answer appended to context]
```
