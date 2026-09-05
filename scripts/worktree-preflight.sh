#!/usr/bin/env bash
# worktree-preflight.sh — validate worktree state before an agent starts work.
#
# Exits 0 if the environment is clean, 1 if stale state that could cause
# failures is detected. Run this at the start of a worktree agent task.
#
# Checks:
#   1. Current checkout is a Git linked worktree (Rule 1 validation)
#   2. No stale .git/worktrees entries for directories that no longer exist
#   3. Target branch (if provided) is not already checked out in another worktree
#
# Usage:
#   bash scripts/worktree-preflight.sh                    # CWD check only
#   bash scripts/worktree-preflight.sh feat/my-branch     # also check branch availability

set -euo pipefail

TARGET_BRANCH="${1:-}"
ISSUES=0

echo "[worktree-preflight] checking environment..."

# Check 1: Git, rather than a directory name, establishes isolation.
CWD="$(pwd -P)"
GIT_DIR="$(git rev-parse --absolute-git-dir 2>/dev/null || true)"
COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [[ -z "$GIT_DIR" || "$GIT_DIR" == "$COMMON_DIR" ]]; then
    echo "ERROR: CWD is not a linked worktree: $CWD"
    ISSUES=$((ISSUES + 1))
else
    echo "OK: Linked worktree: $CWD"
fi

# Check 2: Prune and report stale worktree admin entries.
STALE="$(git worktree prune --dry-run 2>&1)" || true
if [[ -n "$STALE" ]]; then
    echo "WARN: Stale worktree entries detected (will be pruned by cleanup):"
    echo "$STALE" | sed 's/^/  /'
    git worktree prune 2>&1 || true
    echo "  Auto-pruned."
fi

# Check 3: Target branch availability.
if [[ -n "$TARGET_BRANCH" ]]; then
    CURRENT_BRANCH="$(git branch --show-current)"
    if [[ "$CURRENT_BRANCH" == "$TARGET_BRANCH" ]]; then
        echo "OK: Assigned branch is checked out here: $TARGET_BRANCH"
    elif [[ -n "$(git for-each-ref --format='%(worktreepath)' "refs/heads/$TARGET_BRANCH")" ]]; then
        echo "ERROR: Branch '$TARGET_BRANCH' is checked out in another worktree."
        ISSUES=$((ISSUES + 1))
    elif git show-ref --verify --quiet "refs/heads/$TARGET_BRANCH"; then
        echo "WARN: Branch '$TARGET_BRANCH' exists. Confirm ownership before using it, or choose a fresh name."
    else
        echo "OK: Branch '$TARGET_BRANCH' is available for checkout."
    fi
fi

if [[ $ISSUES -gt 0 ]]; then
    echo ""
    echo "[worktree-preflight] FAILED: $ISSUES issue(s) require attention before proceeding."
    exit 1
fi

echo "[worktree-preflight] PASSED: environment is clean."
exit 0
