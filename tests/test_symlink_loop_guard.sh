#!/usr/bin/env bash
#
# Regression test for the self-referential symlink loop bug.
#
# Bug: when a runtime mirror dir (e.g. ~/.claude/hooks or ~/.reasonix/hooks) is
# a WHOLE-DIR symlink pointing back into the source repo's hooks/ dir, running
#   ./install.sh --symlink --per-item --force
# would create self-referential symlinks inside the source repo
# (e.g. hooks/foo.py -> hooks/foo.py) because mkdir -p was a no-op on the
# symlink and every per-item link then resolved back into the source itself.
#
# The fix adds:
#   1. _same_realpath() — compares canonical paths via os.path.realpath
#   2. Guard in install_component per-item branch — bails if target resolves to source
#   3. Guard in sync_mirror_entry per-item branch — returns early if target resolves to source
#   4. clean_codex_hooks_mirror_if_looped call in the Reasonix hooks section
#
# This test reproduces both looped starting states and asserts:
#   - install exits 0 (no set -e trip)
#   - NO self-referential symlinks are left in $REPO_ROOT/hooks/
#   - git status of $REPO_ROOT/hooks/ stays clean (no typechange, no deletion)
#   - the target dir is converted to a real dir containing per-item symlinks pointing INTO the repo
#
# Run:  bash tests/test_symlink_loop_guard.sh
# Exit: 0 on success, 1 on any failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TEST_HOME="$(mktemp -d -t vexjoy-loop-guard-e2e-XXXXXX)"
trap 'rm -rf "$TEST_HOME"' EXIT

export HOME="$TEST_HOME"
export XDG_CONFIG_HOME="${TEST_HOME}/.config"
export XDG_DATA_HOME="${TEST_HOME}/.local/share"

PASS=0
FAIL=0
log()  { echo "  $*"; }
pass() { PASS=$((PASS + 1)); echo "  PASS: $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $*"; }
assert() {
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then
        pass "$desc"
    else
        fail "$desc"
        log "    ran: $*"
    fi
}

# check_no_self_referential_symlinks DIR
# Returns 1 (and prints offenders) if any symlink in DIR points at itself.
check_no_self_referential_symlinks() {
    local dir="$1"
    local found
    found=$(find "$dir" -maxdepth 2 -type l 2>/dev/null | while read -r f; do
        t=$(readlink "$f")
        [ "$t" = "$f" ] && echo "$f"
    done)
    if [ -n "$found" ]; then
        echo "SELF-REFERENTIAL SYMLINKS FOUND: $found"
        return 1
    fi
    return 0
}

# check_source_hooks_clean
# Returns 1 if git sees any changes (typechange, deletion, modification) in hooks/.
check_source_hooks_clean() {
    local dirty
    dirty=$(git -C "$REPO_ROOT" status --porcelain hooks/ 2>/dev/null)
    if [ -n "$dirty" ]; then
        echo "SOURCE HOOKS DIRTY: $dirty"
        return 1
    fi
    return 0
}

echo "==================================================================="
echo "Symlink loop guard regression (test_home=$TEST_HOME)"
echo "==================================================================="

# -----------------------------------------------------------------------
# Scenario 1: ~/.claude/hooks is a whole-dir symlink into source repo
#             (exercises the install_component per-item guard)
# -----------------------------------------------------------------------
echo ""
echo "[1] Scenario 1: ~/.claude/hooks whole-dir symlink -> source repo"

mkdir -p "$TEST_HOME/.claude"
ln -s "$REPO_ROOT/hooks" "$TEST_HOME/.claude/hooks"
assert "precondition: ~/.claude/hooks is a whole-dir symlink" test -L "$TEST_HOME/.claude/hooks"

output1=$( cd "$REPO_ROOT" && \
    HOME="$TEST_HOME" \
    XDG_CONFIG_HOME="${TEST_HOME}/.config" \
    XDG_DATA_HOME="${TEST_HOME}/.local/share" \
    bash install.sh --symlink --per-item --force 2>&1 )
rc1=$?

if [ "$rc1" -eq 0 ]; then
    pass "Scenario 1: install --symlink --per-item --force exited 0"
else
    fail "Scenario 1: install exited $rc1 (set -e may have fired)"
    log "    output tail: ${output1: -400}"
fi

# Core regression assertion: source repo hooks/ must be untouched.
src_clean1=$(check_source_hooks_clean 2>&1)
if [ -z "$src_clean1" ]; then
    pass "Scenario 1: source hooks/ is clean (no typechange/deletion in git status)"
else
    fail "Scenario 1: source hooks/ is dirty — loop guard failed"
    log "    $src_clean1"
fi

self_ref1=$(check_no_self_referential_symlinks "$REPO_ROOT/hooks" 2>&1)
if [ -z "$self_ref1" ]; then
    pass "Scenario 1: no self-referential symlinks in source hooks/"
else
    fail "Scenario 1: self-referential symlinks found in source hooks/"
    log "    $self_ref1"
fi

# ~/.claude/hooks must now be a real dir (converted from whole-dir symlink).
if [ ! -L "$TEST_HOME/.claude/hooks" ] && [ -d "$TEST_HOME/.claude/hooks" ]; then
    pass "Scenario 1: ~/.claude/hooks is now a real dir (converted from whole-dir symlink)"
else
    fail "Scenario 1: ~/.claude/hooks should be a real dir after install"
    log "    state: $( [ -L "$TEST_HOME/.claude/hooks" ] \
        && echo "still a symlink -> $(readlink "$TEST_HOME/.claude/hooks")" \
        || echo "not a dir / does not exist" )"
fi

# At least one hook file inside the converted dir must be a symlink pointing INTO the repo.
sample_hook=$(find "$TEST_HOME/.claude/hooks" -maxdepth 1 -type l 2>/dev/null | \
    grep -v '/lib$' | head -1)
if [ -n "$sample_hook" ]; then
    hook_target=$(readlink "$sample_hook" 2>/dev/null || echo "")
    if [[ "$hook_target" == "$REPO_ROOT/hooks/"* ]]; then
        pass "Scenario 1: hook symlinks point INTO repo hooks/ (correct direction)"
    else
        fail "Scenario 1: hook symlink points to unexpected location: $hook_target"
    fi
else
    fail "Scenario 1: no per-item hook symlinks found in ~/.claude/hooks after install"
fi

# -----------------------------------------------------------------------
# Scenario 2: ~/.reasonix/hooks is a whole-dir symlink into source repo
#             (exercises the sync_mirror_entry per-item guard and
#              clean_codex_hooks_mirror_if_looped in the Reasonix section)
# -----------------------------------------------------------------------
echo ""
echo "[2] Scenario 2: ~/.reasonix/hooks whole-dir symlink -> source repo"

# Fresh TEST_HOME for this scenario so state does not bleed across.
TEST_HOME2="$(mktemp -d -t vexjoy-loop-guard-reasonix-XXXXXX)"
trap 'rm -rf "$TEST_HOME2"' EXIT

mkdir -p "$TEST_HOME2/.reasonix"
ln -s "$REPO_ROOT/hooks" "$TEST_HOME2/.reasonix/hooks"
assert "precondition: ~/.reasonix/hooks is a whole-dir symlink" \
    test -L "$TEST_HOME2/.reasonix/hooks"

output2=$( cd "$REPO_ROOT" && \
    HOME="$TEST_HOME2" \
    XDG_CONFIG_HOME="${TEST_HOME2}/.config" \
    XDG_DATA_HOME="${TEST_HOME2}/.local/share" \
    bash install.sh --symlink --per-item --force 2>&1 )
rc2=$?

if [ "$rc2" -eq 0 ]; then
    pass "Scenario 2: install --symlink --per-item --force exited 0"
else
    fail "Scenario 2: install exited $rc2 (set -e may have fired)"
    log "    output tail: ${output2: -400}"
fi

src_clean2=$(check_source_hooks_clean 2>&1)
if [ -z "$src_clean2" ]; then
    pass "Scenario 2: source hooks/ is clean after Reasonix loop seed"
else
    fail "Scenario 2: source hooks/ is dirty — Reasonix loop guard failed"
    log "    $src_clean2"
fi

self_ref2=$(check_no_self_referential_symlinks "$REPO_ROOT/hooks" 2>&1)
if [ -z "$self_ref2" ]; then
    pass "Scenario 2: no self-referential symlinks in source hooks/"
else
    fail "Scenario 2: self-referential symlinks found in source hooks/"
    log "    $self_ref2"
fi

# ~/.reasonix/hooks must now be a real dir (the whole-dir symlink was removed).
if [ ! -L "$TEST_HOME2/.reasonix/hooks" ] && [ -d "$TEST_HOME2/.reasonix/hooks" ]; then
    pass "Scenario 2: ~/.reasonix/hooks is now a real dir (converted from whole-dir symlink)"
else
    fail "Scenario 2: ~/.reasonix/hooks should be a real dir after install"
    log "    state: $( [ -L "$TEST_HOME2/.reasonix/hooks" ] \
        && echo "still a symlink -> $(readlink "$TEST_HOME2/.reasonix/hooks")" \
        || echo "not a dir / does not exist" )"
fi

# -----------------------------------------------------------------------
# Scenario 3: idempotent — re-running after Scenario 2 state is clean
# -----------------------------------------------------------------------
echo ""
echo "[3] Scenario 3: idempotent re-run after Scenario 2 (no corruption)"

output3=$( cd "$REPO_ROOT" && \
    HOME="$TEST_HOME2" \
    XDG_CONFIG_HOME="${TEST_HOME2}/.config" \
    XDG_DATA_HOME="${TEST_HOME2}/.local/share" \
    bash install.sh --symlink --per-item --force 2>&1 )
rc3=$?

if [ "$rc3" -eq 0 ]; then
    pass "Scenario 3: second install --symlink --per-item --force exited 0"
else
    fail "Scenario 3: second install exited $rc3"
    log "    output tail: ${output3: -400}"
fi

src_clean3=$(check_source_hooks_clean 2>&1)
if [ -z "$src_clean3" ]; then
    pass "Scenario 3: source hooks/ still clean after idempotent re-run"
else
    fail "Scenario 3: source hooks/ became dirty on re-run"
    log "    $src_clean3"
fi

self_ref3=$(check_no_self_referential_symlinks "$REPO_ROOT/hooks" 2>&1)
if [ -z "$self_ref3" ]; then
    pass "Scenario 3: still no self-referential symlinks in source hooks/"
else
    fail "Scenario 3: self-referential symlinks appeared after re-run"
    log "    $self_ref3"
fi

if [ ! -L "$TEST_HOME2/.reasonix/hooks" ] && [ -d "$TEST_HOME2/.reasonix/hooks" ]; then
    pass "Scenario 3: ~/.reasonix/hooks remains a real dir after re-run"
else
    fail "Scenario 3: ~/.reasonix/hooks should remain a real dir after re-run"
fi

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
echo ""
echo "==================================================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================================================="
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
