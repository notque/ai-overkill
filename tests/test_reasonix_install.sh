#!/usr/bin/env bash
#
# E2E test for the Reasonix install/uninstall flow in install.sh.
#
# Strategy: stage a temp HOME, point HOME at it, and run a sequence of install/uninstall
# commands. After each step, assert the filesystem state matches expectations:
#   - skills entries are symlinks (--symlink mode) or real dirs (--copy mode)
#   - settings.json contains only the non-tool Reasonix events VexJoy wires directly
#   - all hook commands reference $HOME/.reasonix/ (or path) and never .claude
#   - scripts/ and hooks/ are mirrors of the repo
#   - uninstall archives settings.json and removes skills/hooks/scripts
#   - ~/.reasonix/config.json is NEVER touched (user-owned)
#
# Run:  bash tests/test_reasonix_install.sh
# Exit: 0 on success, 1 on any failure (with a clear failure message).

set -uo pipefail

# Resolve repo root from this test file's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Test scratch dir. Stays under /tmp so we don't pollute the dev home.
TEST_HOME="$(mktemp -d -t vexjoy-reasonix-e2e-XXXXXX)"
trap 'rm -rf "$TEST_HOME"' EXIT

# Override HOME for every subshell; export XDG too in case a tool consults it.
export HOME="$TEST_HOME"
export XDG_CONFIG_HOME="${TEST_HOME}/.config"
export XDG_DATA_HOME="${TEST_HOME}/.local/share"

# Build minimal Python site: install.sh runs `python3 -c '...'` inline.
# We trust the system python3 to exist (install.sh's check_python asserts this).

# Color-less, single-line output for clean diffs.
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
assert_eq() {
    local desc="$1" actual="$2" expected="$3"
    if [ "$actual" = "$expected" ]; then
        pass "$desc"
    else
        fail "$desc — expected '$expected', got '$actual'"
    fi
}
assert_contains() {
    local desc="$1" haystack="$2" needle="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        pass "$desc"
    else
        fail "$desc — '$needle' not in output"
        log "    first 300 chars: ${haystack:0:300}"
    fi
}
assert_not_contains() {
    local desc="$1" haystack="$2" needle="$3"
    if [[ "$haystack" != *"$needle"* ]]; then
        pass "$desc"
    else
        fail "$desc — '$needle' was present"
    fi
}

run_install() {
    local mode="$1"
    shift
    ( cd "$REPO_ROOT" && bash install.sh "$mode" 2>&1 )
}

echo "==================================================================="
echo "Reasonix install E2E (test_home=$TEST_HOME)"
echo "==================================================================="

# --- Pre-flight: scaffold a fake user config.json so install --copy doesn't
#     trip the "no config" path. This is a real user-owned file the toolkit
#     must never overwrite.
mkdir -p "$TEST_HOME/.reasonix"
cat > "$TEST_HOME/.reasonix/config.json" <<'EOF'
{
  "editMode": "yolo",
  "setupCompleted": true,
  "userMarker": "USER-OWNED-DO-NOT-OVERWRITE"
}
EOF
log "Seeded user-owned config.json with userMarker=USER-OWNED-DO-NOT-OVERWRITE"

# --- Step 1: --symlink install ---
echo ""
echo "[1] install --symlink"
output=$(run_install --symlink 2>&1)
if [ $? -ne 0 ]; then
    fail "install --symlink exited non-zero"
    log "$output"
    exit 1
fi
pass "install --symlink exited 0"

# Skill should be a symlink to the source dir, NOT a copy.
SAMPLE_SKILL="${TEST_HOME}/.reasonix/skills/do"
if [ -L "$SAMPLE_SKILL" ]; then
    pass "skills/do is a symlink"
else
    fail "skills/do should be a symlink in --symlink mode"
fi

# The symlink target should point into the repo's skills tree.
SKILL_TARGET=$(readlink "$SAMPLE_SKILL" 2>/dev/null || echo "")
assert_contains "skills/do symlink target lives in repo" "$SKILL_TARGET" "/skills/"

# settings.json exists and parses as JSON with the right shape.
SETTINGS="${TEST_HOME}/.reasonix/settings.json"
assert "settings.json exists" test -f "$SETTINGS"
SETTINGS_JSON=$(cat "$SETTINGS")
assert_contains "settings.json has hooks key" "$SETTINGS_JSON" '"hooks"'
assert_not_contains "settings.json does NOT contain PreToolUse" "$SETTINGS_JSON" '"PreToolUse"'
assert_not_contains "settings.json does NOT contain PostToolUse" "$SETTINGS_JSON" '"PostToolUse"'
assert_contains "settings.json has UserPromptSubmit" "$SETTINGS_JSON" '"UserPromptSubmit"'
assert_contains "settings.json has Stop" "$SETTINGS_JSON" '"Stop"'

# No Claude-Code-only events should be in the Reasonix settings.
for forbidden in SessionStart PreCompact PostCompact SubagentStop StopFailure TaskCompleted; do
    assert_not_contains "settings.json does NOT contain $forbidden" "$SETTINGS_JSON" "\"$forbidden\""
done

# All hook commands must reference ~/.reasonix/ (or the test path), never ~/.claude/.
assert_not_contains "no hook references .claude/" "$SETTINGS_JSON" '.claude'
assert_contains "hooks reference .reasonix/" "$SETTINGS_JSON" '.reasonix'

# settings.json must be Reasonix-native flat shape (no nested "hooks" arrays with "type").
assert_not_contains "no nested {hooks:[{type:command,...}]} structure" "$SETTINGS_JSON" '"type": "command"'
assert_not_contains "no tool match fields without tool hooks" "$SETTINGS_JSON" '"match"'
assert_not_contains "does not use 'matcher' (Claude naming)" "$SETTINGS_JSON" '"matcher"'

# The prompt/session event set is the entire direct Reasonix hook surface.
EVENT_COUNT=$(python3 -c "import json; d=json.load(open('${SETTINGS}')); print(len(d.get('hooks', {})))")
assert_eq "settings.json has exactly 2 hook events" "$EVENT_COUNT" "2"

# All allowlisted hook files are mirrored.
SAMPLE_HOOK="${TEST_HOME}/.reasonix/hooks/user-correction-capture.py"
assert "allowlisted hook mirrored" test -f "$SAMPLE_HOOK"
REMOVED_TOOL_HOOK="${TEST_HOME}/.reasonix/hooks/pretool-branch-safety.py"
assert "removed tool hook NOT mirrored" test ! -f "$REMOVED_TOOL_HOOK"
# Non-allowlisted hooks (e.g. pretool-ruff-format-gate IS allowlisted; pick one NOT in
# the allowlist — we excluded SessionStart-style ones, but check for a disabled stub).
NOT_ALLOWLISTED="${TEST_HOME}/.reasonix/hooks/creation-request-enforcer-userprompt.py"
assert "non-allowlisted disabled stub NOT mirrored" test ! -f "$NOT_ALLOWLISTED"

# hooks/lib is mirrored (intra-hook imports).
assert "hooks/lib mirrored" test -d "${TEST_HOME}/.reasonix/hooks/lib"

# scripts/ is a symlink to the repo scripts dir.
SCRIPTS_DIR="${TEST_HOME}/.reasonix/scripts"
if [ -L "$SCRIPTS_DIR" ]; then
    pass "scripts/ is a symlink"
else
    fail "scripts/ should be a symlink in --symlink mode"
fi

# Support dirs (no SKILL.md) like shared-patterns are still copied (not symlinked) so
# sibling-ref resolution inside skills works.
assert "shared-patterns support dir exists" test -d "${TEST_HOME}/.reasonix/skills/shared-patterns"

# User-owned config.json is untouched.
USER_MARKER=$(python3 -c "import json; print(json.load(open('${TEST_HOME}/.reasonix/config.json')).get('userMarker',''))")
assert_eq "user-owned config.json untouched" "$USER_MARKER" "USER-OWNED-DO-NOT-OVERWRITE"

# --- Step 2: re-run --symlink (idempotent) ---
echo ""
echo "[2] install --symlink (re-run, idempotent)"
output=$(run_install --symlink 2>&1)
if [ $? -ne 0 ]; then
    fail "second install --symlink exited non-zero"
    log "$output"
    exit 1
fi
pass "second install --symlink exited 0"
# Re-confirm a key fact: skills/do is still a symlink (not promoted to a copy).
if [ -L "${TEST_HOME}/.reasonix/skills/do" ]; then
    pass "skills/do remains a symlink after re-run"
else
    fail "skills/do should still be a symlink after re-run"
fi

# --- Step 3: --copy install (separate temp home so we don't trample --symlink state) ---
echo ""
echo "[3] install --copy (fresh test_home)"
TEST_HOME2="$(mktemp -d -t vexjoy-reasonix-e2e-XXXXXX)"
trap 'rm -rf "$TEST_HOME" "$TEST_HOME2"' EXIT
export HOME="$TEST_HOME2"
mkdir -p "$TEST_HOME2/.reasonix"
cat > "$TEST_HOME2/.reasonix/config.json" <<'EOF'
{"editMode": "yolo", "userMarker": "COPY-USER-OWNED"}
EOF
output=$(HOME="$TEST_HOME2" bash install.sh --copy 2>&1)
if [ $? -ne 0 ]; then
    fail "install --copy exited non-zero"
    log "$output"
    exit 1
fi
pass "install --copy exited 0"

# In --copy mode, skills should be real dirs, not symlinks.
if [ ! -L "${TEST_HOME2}/.reasonix/skills/do" ] && [ -d "${TEST_HOME2}/.reasonix/skills/do" ]; then
    pass "skills/do is a real dir in --copy mode"
else
    fail "skills/do should be a real dir in --copy mode"
fi
# scripts/ should also be a real dir in --copy mode.
if [ ! -L "${TEST_HOME2}/.reasonix/scripts" ] && [ -d "${TEST_HOME2}/.reasonix/scripts" ]; then
    pass "scripts/ is a real dir in --copy mode"
else
    fail "scripts/ should be a real dir in --copy mode"
fi
# settings.json should still be prompt/session-only and not reference .claude/.
COPY_SETTINGS="${TEST_HOME2}/.reasonix/settings.json"
COPY_JSON=$(cat "$COPY_SETTINGS")
COPY_EVENT_COUNT=$(python3 -c "import json; d=json.load(open('${COPY_SETTINGS}')); print(len(d.get('hooks', {})))")
assert_eq "--copy settings.json has 2 events" "$COPY_EVENT_COUNT" "2"
assert_not_contains "--copy settings.json has no .claude" "$COPY_JSON" '.claude'

# User-owned config.json preserved.
COPY_USER=$(python3 -c "import json; print(json.load(open('${TEST_HOME2}/.reasonix/config.json')).get('userMarker',''))")
assert_eq "user config preserved in --copy mode" "$COPY_USER" "COPY-USER-OWNED"

# --- Step 4: --uninstall (back to the --symlink home) ---
echo ""
echo "[4] install --uninstall"
export HOME="$TEST_HOME"
output=$(HOME="$TEST_HOME" bash install.sh --uninstall 2>&1)
UNINSTALL_RC=$?
if [ $UNINSTALL_RC -ne 0 ]; then
    fail "install --uninstall exited non-zero (rc=$UNINSTALL_RC)"
    log "$output"
    exit 1
fi
pass "install --uninstall exited 0"

# settings.json was archived, not deleted in place.
ARCHIVED=$(ls "$TEST_HOME/.reasonix"/settings.json.uninstalled.* 2>/dev/null | head -1)
if [ -n "$ARCHIVED" ]; then
    pass "settings.json archived to $(basename "$ARCHIVED")"
else
    fail "settings.json was not archived"
fi
assert "settings.json in-place removed" test ! -f "${TEST_HOME}/.reasonix/settings.json"

# scripts/ dir removed.
assert "scripts/ removed" test ! -e "${TEST_HOME}/.reasonix/scripts"

# hooks/ dir removed.
assert "hooks/ removed" test ! -e "${TEST_HOME}/.reasonix/hooks"

# skills/ removed (or empty) — toolkit-owned entries gone.
SKILLS_LEFT=$(ls -1 "$TEST_HOME/.reasonix/skills/" 2>/dev/null | wc -l)
assert_eq "skills/ contents cleared by uninstall" "$SKILLS_LEFT" "0"

# config.json (user-owned) NEVER touched.
USER_MARKER_AFTER=$(python3 -c "import json; print(json.load(open('${TEST_HOME}/.reasonix/config.json')).get('userMarker',''))")
assert_eq "user config.json preserved through uninstall" "$USER_MARKER_AFTER" "USER-OWNED-DO-NOT-OVERWRITE"

# --- Summary ---
echo ""
echo "==================================================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================================================="
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
