# Worktree Agent Rules

> From the demoted `worktree-agent` skill. Canonical worktree isolation rules for agents dispatched with `isolation: "worktree"`.

Mandatory rules for any agent dispatched with `isolation: "worktree"`.

## Rule 1: Verify Your Working Directory

On start, run `pwd`. Your path MUST contain `.claude/worktrees/`.
If your CWD is the main repo path, **STOP** and report the error.

## Rule 2: Create Feature Branch First

```bash
git checkout -b <branch-name>
```

Never commit on the default `worktree-agent-*` branch. Create your feature branch FIRST.

If `git checkout -b <branch-name>` fails with "a branch named X already exists":

```bash
# Option A: the branch has no commits beyond main — safe to reset and reuse
git branch -D <branch-name>
git checkout -b <branch-name>

# Option B: the branch is checked out in another active worktree — use a unique name
git checkout -b <branch-name>-2   # or append timestamp: $(date +%s)
```

If `git checkout -b <branch-name>` fails with "X is already used by worktree at Y":

```bash
# Branch is live in another worktree — use a unique suffix
git checkout -b <branch-name>-$(date +%s)
```

To update a branch held by another worktree (e.g. an existing PR branch): work detached from `origin/<branch>` and push with `git push origin HEAD:<branch>`. `gh pr merge`'s post-merge local-checkout errors are harmless.

## Rule 3: Use Worktree-Relative Paths

Never hardcode absolute paths from the main repo. Use `$(git rev-parse --show-toplevel)/path`.
**Exception**: Reading gitignored ADR files requires the main repo absolute path.

## Rule 4: Ignore Auto-Plan Hooks

Keep planning inline instead of creating `task_plan.md`. If the auto-plan hook fires, continue with the current task and keep your attention on implementation.

## Rule 5: Stage Specific Files Only

```bash
git add path/to/specific/file.py
```

Never `git add .`, `git add -A`, or `git add --all`. Verify with `git diff --cached --stat`.

## Rule 6: Do Not Touch the Main Worktree

Never write to paths outside your worktree directory. Never run `git checkout` in the main repo.

## Rule 7: Commit with Conventional Format

Use the commit message specified in your prompt. No attribution lines.

## Rule 8: Run Both ruff Checks Before Declaring CI-Ready

For any Python code changes, run both checks before pushing or creating a PR:

```bash
ruff check . --config pyproject.toml
ruff format --check . --config pyproject.toml
```

Running only `ruff check` misses formatting violations. The `Tests / lint` CI job runs both — if you skip `ruff format --check`, the PR will fail CI and cannot merge due to branch protection.

## Rule 9: Run Preflight Check on Start

Run the preflight script at the start of any worktree task to confirm clean state:

```bash
bash scripts/worktree-preflight.sh <intended-branch-name>
```

If it exits 1, fix the reported issue before proceeding.

## Rule 10: Reserve disk capacity before creating a checkout

The dispatcher runs this before each implementation worktree:

```bash
python3 ~/.claude/skills/process/worktree-agent/scripts/worktree_capacity.py \
  --repo "$(git rev-parse --show-toplevel)" --strict
```

| State | Dispatcher action |
|---|---|
| `ready` (<80% used) | Create the one implementation checkout for the candidate. |
| `cleanup-soon` (80–<85%) | Reclaim accepted clean checkouts before adding another. Use root read-only review work where possible. |
| `blocked` (≥85%) | Integrate, deploy, verify, or reclaim; create no new checkout. |

The report lists clean candidates only. The dispatcher confirms their task is inactive before removal.

## Rule 11: Assign checkout roles deliberately

| Task | Checkout policy |
|---|---|
| Source implementation or repair | One writable task worktree, reused through review corrections. |
| Code review, test-plan review, or read-only investigation | Read the candidate through `git diff` or `git show` from the repository root; allocate no checkout. |
| Large repository implementation | Create a sparse worktree containing declared source/test/config scopes; include whole-repository content only when the task requires it. |

```bash
git worktree add --no-checkout <worktree-path> -b <branch> <base-sha>
git -C <worktree-path> sparse-checkout init --no-cone
git -C <worktree-path> sparse-checkout set --no-cone <declared-path>...
git -C <worktree-path> checkout
```

Record any full-checkout reason in the dispatch handoff.

## Post-Merge Cleanup

After integration or a PR merge, the dispatcher confirms the task is inactive and the checkout is clean, then runs:

```bash
git worktree remove -- <accepted-worktree-path>
bash scripts/worktree-cleanup.sh --force
```

`git worktree remove` frees the materialized checkout while preserving its branch for recovery. The cleanup script then prunes stale records and removes merged harness branches.

## Dispatcher Rules

These two rules bind the orchestrator that dispatches agents, not the worktree agent itself. `hooks/pretool-worktree-edit-guard.py` blocks a worktree agent from writing into the shared main tree. Nothing stops an orchestrator from putting two writers in that tree to begin with.

### Rule D1: Give Every File-Writing Agent Its Own Worktree

Dispatch any agent that writes files with `isolation: "worktree"` when you also run git commands in the main tree, or when another writing agent is already running there. Agents that only read are safe to run concurrently in the main tree.

Two writers in one tree contend for `HEAD` and the index. Observed damage: a `git reset --hard` during one agent's rebase dropped a sibling agent's committed branch, recoverable only through the reflog.

When agents must share a tree, sequence their git index operations and record a recovery ref before any rebase:

```bash
git branch backup/$(git branch --show-current)-$(date +%s)
```

### Rule D2: Validate an Agent's PR Against origin, Not Your Working Tree

Reset the branch to its pushed state before you grep or test a background agent's work locally:

```bash
git fetch origin
git reset --hard origin/<branch>
```

The main tree can carry staged files left over from earlier worktree juggling. Those files silently revert the agent's commit, so local greps and test runs read code the agent never wrote — and a correct agent looks broken. The committed blob is the authority. Read it directly when you need one file:

```bash
git show <sha>:<path>
```

## Failure Modes This Prevents

| Failure | Rule | Without It |
|---------|------|-----------|
| Agent edits main repo files | 1, 6 | Changes leak to main, get stashed/lost |
| Two agents corrupt each other's branches | D1 | A rebase drops a sibling's commits; reflog is the only recovery |
| Local validation reads stale staged files | D2 | The agent's correct work is reported as broken |
| Context wasted on task_plan.md | 4 | Implementation budget consumed by planning |
| Commit on wrong branch | 2 | Orchestrator merges wrong content |
| PR has changes from 2 ADRs | 5, 6 | Cross-contamination between agents |
| Branch locked by worktree | 2 | Fatal error on checkout |
| PR fails CI on format | 8 | Merge blocked; `ruff format --check` was skipped |
| New task fails to create worktree | 9 | Branch name collision from prior stale run |
