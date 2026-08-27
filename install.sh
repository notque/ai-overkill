#!/bin/bash
#
# VexJoy Agent - Installation Script
#
# This script sets up the VexJoy Agent ecosystem in your Claude Code environment.
#
# Usage:
#   ./install.sh              # Interactive install
#   ./install.sh --symlink    # Use symlinks (recommended for development)
#   ./install.sh --copy       # Copy files (recommended for stability)
#   ./install.sh --uninstall  # Remove installation
#   ./install.sh --dry-run    # Show what would happen without making changes
#
# What this script does:
#   1. Verifies Python 3.10+ is available
#   2. Creates ~/.claude directory if needed
#   3. Links/copies agents, skills, hooks, commands, scripts to ~/.claude
#   4. Mirrors skills, agents, hooks, and scripts to ~/.codex, ~/.factory,
#      ~/.hermes, and ~/.reasonix (no agent surface for ~/.reasonix)
#   5. Sets up local overlay directory
#   6. Configures hooks in settings.json
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
CODEX_DIR="${HOME}/.codex"
CODEX_SKILLS_DIR="${CODEX_DIR}/skills"
CODEX_AGENTS_DIR="${CODEX_DIR}/agents"
CODEX_HOOKS_DIR="${CODEX_DIR}/hooks"
CODEX_SCRIPTS_DIR="${CODEX_DIR}/scripts"
FACTORY_DIR="${HOME}/.factory"
FACTORY_SKILLS_DIR="${FACTORY_DIR}/skills"
FACTORY_DROIDS_DIR="${FACTORY_DIR}/droids"
FACTORY_HOOKS_DIR="${FACTORY_DIR}/hooks"
FACTORY_COMMANDS_DIR="${FACTORY_DIR}/commands"
FACTORY_SCRIPTS_DIR="${FACTORY_DIR}/scripts"
HERMES_DIR="${HOME}/.hermes"
HERMES_SKILLS_DIR="${HERMES_DIR}/skills"
HERMES_SCRIPTS_DIR="${HERMES_DIR}/scripts"
REASONIX_DIR="${HOME}/.reasonix"
REASONIX_SKILLS_DIR="${REASONIX_DIR}/skills"
REASONIX_SCRIPTS_DIR="${REASONIX_DIR}/scripts"
REASONIX_HOOKS_DIR="${REASONIX_DIR}/hooks"
REASONIX_INDEX_OWNER_MARKER="${REASONIX_SKILLS_DIR}/.vexjoy-managed-index"
REASONIX_INDEX_BACKUP="${REASONIX_SKILLS_DIR}/.vexjoy-index-backup"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                VexJoy Agent - Installation Script               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Parse arguments
MODE=""
DRY_RUN=false
FORCE=true  # Default to force — never prompt about existing directories
CONFLICT_MODE=""  # per-item | replace | skip; set by --per-item/--sync or conflict prompt
SYNC_REFRESH=false  # true only for explicit --sync; --per-item preserves existing children
CONFIGURE=false
CONFIGURE_ONLY=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --symlink)
            MODE="symlink"
            shift
            ;;
        --copy)
            MODE="copy"
            shift
            ;;
        --uninstall)
            MODE="uninstall"
            shift
            ;;
        --rollback)
            MODE="rollback"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force|-f)
            FORCE=true  # Already default, accepted for backward compat
            shift
            ;;
        --no-force)
            FORCE=false  # Opt in to interactive prompts
            shift
            ;;
        --per-item)
            CONFLICT_MODE="per-item"
            shift
            ;;
        --sync)
            CONFLICT_MODE="per-item"
            SYNC_REFRESH=true
            # --sync implies symlink mode when MODE is not yet set
            [ -z "$MODE" ] && MODE="symlink"
            shift
            ;;
        --configure)
            CONFIGURE=true
            shift
            ;;
        --configure-only)
            CONFIGURE_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--symlink|--copy|--uninstall|--rollback|--dry-run|--force|--per-item|--sync]"
            echo ""
            echo "Options:"
            echo "  --symlink    Create symlinks to this repo (recommended for development)"
            echo "  --copy       Copy files to ~/.claude (recommended for stability)"
            echo "  --uninstall  Remove the installation"
            echo "  --rollback   Restore settings.json from the most recent backup"
            echo "  --dry-run    Show what would happen without making changes"
            echo "  --force      Replace existing directories without prompting (default)"
            echo "  --no-force   Prompt before replacing existing directories"
            echo "  --per-item   Symlink each item individually; preserve external content"
            echo "  --sync       Refresh toolkit-owned Codex entries; preserve runtime-only entries"
            echo "  --configure       Run the interactive profile picker, then install"
            echo "  --configure-only  Run the picker, write .local/profile.yaml, then exit"
            echo ""
            echo "If no option provided, will prompt interactively."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Dry run banner
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                          DRY RUN MODE                          ║${NC}"
    echo -e "${YELLOW}║             No changes will be made to your system             ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
fi

# Function to check Python version
check_python() {
    echo -e "${YELLOW}Checking Python version...${NC}"

    # Try python3 first, then python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}Error: Python not found. Please install Python 3.10+${NC}"
        exit 1
    fi

    # Check version
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
        echo -e "${RED}Error: Python 3.10+ required, found $PYTHON_VERSION${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
}

# Prefer pip from the validated Python interpreter so dependency installs land
# in the same environment used by the rest of the installer. Fall back to
# platform-native pip commands only if that interpreter does not have pip.
detect_pip_command() {
    if "$PYTHON_CMD" -m pip --version &> /dev/null; then
        PIP_CMD=("$PYTHON_CMD" -m pip)
    elif command -v pip3 &> /dev/null; then
        PIP_CMD=(pip3)
    elif command -v pip &> /dev/null; then
        PIP_CMD=(pip)
    else
        echo -e "${RED}Error: pip not found. Please install pip for ${PYTHON_CMD}.${NC}"
        exit 1
    fi

    if ! "${PIP_CMD[@]}" --version &> /dev/null; then
        echo -e "${RED}Error: ${PIP_CMD[*]} found but appears broken.${NC}"
        exit 1
    fi
}

pip_supports_break_system_packages() {
    "${PIP_CMD[@]}" install --help 2>/dev/null | grep -q -- "--break-system-packages"
}

print_manual_pip_command() {
    local use_break_system_packages=${1:-false}
    local -a manual_cmd=("${PIP_CMD[@]}" install -r "${SCRIPT_DIR}/requirements.txt")
    local manual_cmd_str

    if [ "$use_break_system_packages" = true ]; then
        manual_cmd+=(--break-system-packages)
    fi

    printf -v manual_cmd_str '%q ' "${manual_cmd[@]}"
    echo "  Run manually: ${manual_cmd_str% }"
}

_canonical_path() {
    local python_cmd=${PYTHON_CMD:-}

    if [ -z "$python_cmd" ]; then
        if command -v python3 > /dev/null 2>&1; then
            python_cmd="python3"
        elif command -v python > /dev/null 2>&1; then
            python_cmd="python"
        else
            return 1
        fi
    fi

    "$python_cmd" -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

is_command_available() {
    command -V -- "$1" >/dev/null 2>&1
}

_symlink_target_state() {
    local link=$1
    local expected=$2
    local actual actual_canonical expected_canonical

    [ -L "$link" ] || return 1
    actual=$(readlink "$link") || return 2
    case "$actual" in
        /*) ;;
        *) actual="$(dirname "$link")/$actual" ;;
    esac
    actual_canonical=$(_canonical_path "$actual") || return 2
    expected_canonical=$(_canonical_path "$expected") || return 2
    [ -n "$actual_canonical" ] || return 2
    [ -n "$expected_canonical" ] || return 2
    [ "$actual_canonical" = "$expected_canonical" ] && return 0
    return 1
}

_symlink_points_to() {
    _symlink_target_state "$1" "$2" && return 0
    return 1
}

clean_hooks_mirror_if_source_link() {
    local hook_dir="$1"
    local hook_source_dir="$2"
    local link_state

    if [ -z "$hook_dir" ] || [ -z "$hook_source_dir" ]; then
        return 2
    fi

    if _symlink_target_state "$hook_dir" "$hook_source_dir"; then
        link_state=0
    else
        link_state=$?
    fi

    if [ "$link_state" -eq 2 ]; then
        echo -e "${YELLOW}  Skipping hooks mirror: could not verify symlink target: ${hook_dir}${NC}"
        return 2
    fi

    if [ "$link_state" -eq 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}  Would remove stale hooks mirror symlink: ${hook_dir}${NC}"
            echo -e "${YELLOW}  (points back into source hooks: ${hook_source_dir})${NC}"
            return
        fi
        echo -e "${YELLOW}  Removing stale hooks mirror symlink: ${hook_dir}${NC}"
        echo -e "${YELLOW}  (points back into source hooks: ${hook_source_dir})${NC}"
        unlink "$hook_dir"
    fi
    return 0
}

# unlink_skills_nested TARGET — tear down a nested skills tree built by
# link_skills_nested, preserving any external (non-toolkit) entries.
# Removes only symlinks; for category dirs, removes the per-skill symlinks we
# created and drops the category dir if it ends up empty. Real files/dirs the
# user added are left untouched.
unlink_skills_nested() {
    local target=$1
    local source=${2:-${SCRIPT_DIR}/skills}
    local entry entry_name child child_name

    [ -d "$target" ] || return 0

    for entry in "$target"/*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        entry_name=$(basename "$entry")
        if [ -L "$entry" ]; then
            # Top-level skill or file symlink (or a whole-category symlink from
            # an older install): remove it only when it points at this toolkit.
            if _symlink_points_to "$entry" "$source/$entry_name"; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove skills entry: ${entry}${NC}"
                else
                    rm "$entry"
                fi
            fi
        elif [ -d "$entry" ]; then
            # Category / support dir: remove per-skill symlinks, keep real entries.
            for child in "$entry"/*; do
                [ -L "$child" ] || continue
                child_name=$(basename "$child")
                if _symlink_points_to "$child" "$source/$entry_name/$child_name"; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove skill symlink: ${child}${NC}"
                    else
                        rm "$child"
                    fi
                fi
            done
            # Drop the category dir if nothing external remains.
            if [ "$DRY_RUN" != true ]; then
                rmdir "$entry" 2>/dev/null || true
            fi
        fi
    done
    # Drop the skills dir itself if now empty (no external content remained).
    if [ "$DRY_RUN" != true ]; then
        rmdir "$target" 2>/dev/null || true
        echo -e "${GREEN}  ✓ Removed toolkit skills (preserved any external skills)${NC}"
    fi
}

# Function to uninstall
uninstall() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║               VexJoy Agent - Uninstaller               ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    MANIFEST_FILE="${CLAUDE_DIR}/.install-manifest.json"
    SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
    COMPONENTS=(agents skills hooks commands scripts)
    REMOVED=()
    PRESERVED=()

    # Phase 1: Determine install mode from manifest or fall back to detection
    echo -e "${YELLOW}Reading install manifest...${NC}"
    INSTALL_MODE=""
    if [ -f "$MANIFEST_FILE" ]; then
        INSTALL_MODE=$(python3 -c "import json; print(json.load(open('${MANIFEST_FILE}')).get('mode', ''))" 2>/dev/null || echo "")
        if [ -n "$INSTALL_MODE" ]; then
            echo -e "${GREEN}  ✓ Manifest found (mode: ${INSTALL_MODE})${NC}"
        else
            echo -e "${YELLOW}  Manifest found but mode unreadable. Falling back to detection.${NC}"
        fi
    else
        echo -e "${YELLOW}  No manifest found. Falling back to symlink detection.${NC}"
    fi

    # Phase 2: Remove component directories and symlinks
    echo ""
    echo -e "${YELLOW}Removing installed components...${NC}"
    for item in "${COMPONENTS[@]}"; do
        target="${CLAUDE_DIR}/${item}"
        if [ "$item" = "skills" ] && [ "$INSTALL_MODE" != "copy" ] && { [ -L "$target" ] || [ -d "$target" ]; }; then
            if [ -L "$target" ] && _symlink_points_to "$target" "${SCRIPT_DIR}/skills"; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove symlink: ${target}${NC}"
                else
                    rm "$target"
                    echo -e "${GREEN}  ✓ Removed symlink: ${target}${NC}"
                fi
                REMOVED+=("$item (symlink)")
            else
                # The skills dir may be a nested tree of toolkit-owned symlinks
                # (real category dirs + per-skill links). Remove only what the
                # toolkit created and preserve any external skills the user added.
                unlink_skills_nested "$target" "${SCRIPT_DIR}/skills"
                REMOVED+=("$item (nested symlinks)")
            fi
        elif [ -L "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove symlink: ${target}${NC}"
            else
                rm "$target"
                echo -e "${GREEN}  ✓ Removed symlink: ${target}${NC}"
            fi
            REMOVED+=("$item (symlink)")
        elif [ -d "$target" ]; then
            # Only remove directories if the manifest says we copied them,
            # or if no manifest exists (best-effort cleanup)
            if [ "$INSTALL_MODE" = "copy" ] || [ -z "$INSTALL_MODE" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove directory: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed directory: ${target}${NC}"
                fi
                REMOVED+=("$item (directory)")
            else
                echo -e "${YELLOW}  Skipping ${target}: manifest says symlink but found directory${NC}"
                PRESERVED+=("$item (unexpected directory, not removed)")
            fi
        else
            echo "  Not found: ${target} (already removed or never installed)"
        fi
    done

    # Phase 2.5: Clean private-voice entries from repo skills directory
    if [ -d "${SCRIPT_DIR}/private-voices" ]; then
        echo ""
        echo -e "${YELLOW}Cleaning private voice entries from skills/...${NC}"
        for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
            [ -d "$voice_dir" ] || continue
            voice_name=$(basename "$voice_dir")
            target="${SCRIPT_DIR}/skills/voice-${voice_name}"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed voice-${voice_name} from skills/${NC}"
                fi
                REMOVED+=("voice-${voice_name} from skills/")
            fi
        done

        # Clean voice shared references from skills/shared-patterns/
        if [ -d "${SCRIPT_DIR}/private-voices/shared-references" ]; then
            echo ""
            echo -e "${YELLOW}Cleaning voice shared references from skills/shared-patterns/...${NC}"
            for ref_file in "${SCRIPT_DIR}/private-voices/shared-references/"*.md; do
                [ -f "$ref_file" ] || continue
                ref_name=$(basename "$ref_file")
                target="${SCRIPT_DIR}/skills/shared-patterns/${ref_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove: ${target}${NC}"
                    else
                        rm -f "$target"
                        echo -e "${GREEN}  ✓ Removed ${ref_name} from skills/shared-patterns/${NC}"
                    fi
                    REMOVED+=("${ref_name} from skills/shared-patterns/")
                fi
            done
        fi
    fi

    # Phase 3: Clean hooks from settings.json
    echo ""
    echo -e "${YELLOW}Cleaning hooks from settings.json...${NC}"
    if [ -f "$SETTINGS_FILE" ]; then
        # Check if hooks key exists
        HAS_HOOKS=$(python3 -c "import json; d=json.load(open('${SETTINGS_FILE}')); print('yes' if 'hooks' in d else 'no')" 2>/dev/null || echo "no")
        if [ "$HAS_HOOKS" = "yes" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would back up: ${SETTINGS_FILE}${NC}"
                echo -e "${BLUE}  Would remove 'hooks' key from settings.json${NC}"
            else
                # Create timestamped backup (same pattern as installer)
                BACKUP_TS=$(date +%Y%m%d-%H%M%S)
                cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup.${BACKUP_TS}"
                echo -e "${GREEN}  ✓ Backed up settings.json to settings.json.backup.${BACKUP_TS}${NC}"

                # Remove the hooks key, preserve everything else
                python3 -c "
import json, os
dst = '${SETTINGS_FILE}'
with open(dst, encoding='utf-8') as f:
    data = json.load(f)
data.pop('hooks', None)
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
"
                echo -e "${GREEN}  ✓ Removed hooks from settings.json${NC}"
            fi
            REMOVED+=("hooks config from settings.json")
        else
            echo "  No hooks key found in settings.json. Nothing to clean."
        fi
    else
        echo "  No settings.json found. Nothing to clean."
    fi

    # Phase 3.5: Clean toolkit-owned Codex mirror entries
    echo ""
    echo -e "${YELLOW}Cleaning Codex skills mirror...${NC}"
    if [ -d "$CODEX_SKILLS_DIR" ]; then
        for item in "${SCRIPT_DIR}/skills/"*; do
            [ -e "$item" ] || continue
            target="${CODEX_SKILLS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                fi
                REMOVED+=("Codex skill $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -d "$voice_dir" ] || continue
                skill_src="${voice_dir}/skill"
                [ -d "$skill_src" ] || continue
                voice_name=$(basename "$voice_dir")
                target="${CODEX_SKILLS_DIR}/voice-${voice_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                    fi
                    REMOVED+=("Codex skill voice-${voice_name}")
                fi
            done
        fi

        if [ -d "${SCRIPT_DIR}/private-skills" ]; then
            for item in "${SCRIPT_DIR}/private-skills/"*; do
                [ -e "$item" ] || continue
                target="${CODEX_SKILLS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                    fi
                    REMOVED+=("Codex skill $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.codex/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Codex agents mirror...${NC}"
    if [ -d "$CODEX_AGENTS_DIR" ]; then
        for item in "${SCRIPT_DIR}/agents/"*; do
            [ -e "$item" ] || continue
            target="${CODEX_AGENTS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                fi
                REMOVED+=("Codex agent $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-agents" ]; then
            for item in "${SCRIPT_DIR}/private-agents/"*; do
                [ -e "$item" ] || continue
                target="${CODEX_AGENTS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                    fi
                    REMOVED+=("Codex agent $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.codex/agents mirror found. Nothing to clean."
    fi

    # Phase 3.6: Clean toolkit-owned Codex hooks mirror (ADR-182)
    echo ""
    echo -e "${YELLOW}Cleaning Codex hooks mirror...${NC}"
    if [ -d "$CODEX_HOOKS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${CODEX_HOOKS_DIR}${NC}"
        else
            rm -rf "$CODEX_HOOKS_DIR"
            echo -e "${GREEN}  ✓ Removed ${CODEX_HOOKS_DIR}${NC}"
        fi
        REMOVED+=("Codex hooks mirror directory")
    else
        echo "  No ~/.codex/hooks mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Codex scripts mirror...${NC}"
    if [ -d "$CODEX_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${CODEX_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$CODEX_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${CODEX_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Codex scripts mirror directory")
    else
        echo "  No ~/.codex/scripts mirror found. Nothing to clean."
    fi

    if [ -f "${CODEX_DIR}/hooks.json" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would archive: ${CODEX_DIR}/hooks.json${NC}"
        else
            # Archive rather than delete so users who edited the file manually
            # can recover any custom entries we did not write.
            ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
            mv "${CODEX_DIR}/hooks.json" "${CODEX_DIR}/hooks.json.uninstalled.${ARCHIVE_TS}"
            echo -e "${GREEN}  ✓ Archived ${CODEX_DIR}/hooks.json${NC}"
        fi
        REMOVED+=("Codex hooks.json (archived)")
    else
        echo "  No ~/.codex/hooks.json found. Nothing to archive."
    fi

    # Note: [features] hooks = true is intentionally left in config.toml.
    # Users may have other Codex hook configurations we did not write.

    # Phase 3.9: Clean toolkit-owned Factory mirror
    echo ""
    echo -e "${YELLOW}Cleaning Factory mirror...${NC}"
    for dir_var in FACTORY_SKILLS_DIR FACTORY_DROIDS_DIR FACTORY_HOOKS_DIR FACTORY_COMMANDS_DIR FACTORY_SCRIPTS_DIR; do
        target="${!dir_var}"
        if [ "$dir_var" = "FACTORY_SKILLS_DIR" ] && { [ -L "$target" ] || [ -d "$target" ]; }; then
            if [ -L "$target" ] && _symlink_points_to "$target" "${SCRIPT_DIR}/skills"; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove: ${target}${NC}"
                else
                    rm "$target"
                    echo -e "${GREEN}  ✓ Removed: ${target}${NC}"
                fi
            else
                unlink_skills_nested "$target" "${SCRIPT_DIR}/skills"
            fi
            REMOVED+=("Factory $(basename "$target")")
        elif [ -L "$target" ] || [ -d "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove: ${target}${NC}"
            else
                rm -rf "$target"
                echo -e "${GREEN}  ✓ Removed: ${target}${NC}"
            fi
            REMOVED+=("Factory $(basename "$target")")
        fi
    done

    if [ -f "${FACTORY_DIR}/settings.json" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would archive: ${FACTORY_DIR}/settings.json${NC}"
        else
            ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
            mv "${FACTORY_DIR}/settings.json" "${FACTORY_DIR}/settings.json.uninstalled.${ARCHIVE_TS}"
            echo -e "${GREEN}  ✓ Archived ${FACTORY_DIR}/settings.json${NC}"
        fi
        REMOVED+=("Factory settings.json (archived)")
    else
        echo "  No ~/.factory/settings.json found. Nothing to archive."
    fi

    # Note: ~/.factory/config.toml is intentionally left untouched.
    # Users may have other Factory configurations we did not write.

    # Phase 3.10: Clean toolkit-owned Hermes skills mirror
    echo ""
    echo -e "${YELLOW}Cleaning Hermes skills mirror...${NC}"
    if [ -d "$HERMES_SKILLS_DIR" ]; then
        for item in "${SCRIPT_DIR}/skills/"*; do
            [ -e "$item" ] || continue
            target="${HERMES_SKILLS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Hermes entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Hermes entry: ${target}${NC}"
                fi
                REMOVED+=("Hermes skill $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -d "$voice_dir" ] || continue
                skill_src="${voice_dir}/skill"
                [ -d "$skill_src" ] || continue
                voice_name=$(basename "$voice_dir")
                target="${HERMES_SKILLS_DIR}/voice-${voice_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Hermes entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Hermes entry: ${target}${NC}"
                    fi
                    REMOVED+=("Hermes skill voice-${voice_name}")
                fi
            done
        fi

        if [ -d "${SCRIPT_DIR}/private-skills" ]; then
            for item in "${SCRIPT_DIR}/private-skills/"*; do
                [ -e "$item" ] || continue
                target="${HERMES_SKILLS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Hermes entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Hermes entry: ${target}${NC}"
                    fi
                    REMOVED+=("Hermes skill $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.hermes/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Hermes scripts mirror...${NC}"
    if [ -d "$HERMES_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${HERMES_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$HERMES_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${HERMES_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Hermes scripts mirror directory")
    else
        echo "  No ~/.hermes/scripts mirror found. Nothing to clean."
    fi

    # Note: ~/.hermes/config.yaml is intentionally left untouched.
    # Users may have other Hermes configurations we did not write.

    # Phase 3.11: Clean toolkit-owned Reasonix mirror (legacy skills + scripts + hooks + settings.json)
    echo ""
    echo -e "${YELLOW}Cleaning Reasonix skills mirror...${NC}"
    # Remove ONLY the toolkit-owned flatten-copy output, recomputed from the repo so it
    # matches what the install wrote (skills/<cat>/<name> + top-level skills + private-skills
    # flattened to <name>, voice skills as voice-<name>, support dirs copied by name). Skills
    # a USER added by hand (real dirs we never wrote) are left intact. Also sweep stale
    # toolkit symlinks left by the pre-flatten installer. Finally drop the dir if now empty.
    if [ -d "$REASONIX_SKILLS_DIR" ]; then
        reasonix_uninstall_entry() {
            [ -n "$1" ] || return 0
            local target="${REASONIX_SKILLS_DIR}/$1"
            [ -e "$target" ] || [ -L "$target" ] || return 0
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove Reasonix entry: ${target}${NC}"
            else
                rm -rf "$target"
                echo -e "${GREEN}  ✓ Removed Reasonix entry: ${target}${NC}"
            fi
            REMOVED+=("Reasonix skill $1")
        }

        # Flattened skills + private skills (basename of each dir holding a SKILL.md).
        while IFS= read -r skill_md; do
            [ -n "$skill_md" ] || continue
            reasonix_uninstall_entry "$(basename "$(dirname "$skill_md")")"
        done < <(find "${SCRIPT_DIR}/skills" "${SCRIPT_DIR}/private-skills" -name SKILL.md 2>/dev/null)

        # Voice skills (voice-<name>).
        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -f "${voice_dir}/skill/SKILL.md" ] || continue
                reasonix_uninstall_entry "voice-$(basename "$voice_dir")"
            done
        fi

        # Support dirs (no SKILL.md anywhere — shared-patterns, kb, voice-shared*).
        for support_dir in "${SCRIPT_DIR}/skills/"*/; do
            [ -d "$support_dir" ] || continue
            [ -z "$(find "$support_dir" -name SKILL.md -print -quit)" ] || continue
            reasonix_uninstall_entry "$(basename "$support_dir")"
        done

        # Restore a user-owned registry only when install recorded that it
        # replaced one. Without the marker, INDEX.json is outside our ownership.
        if [ -f "$REASONIX_INDEX_OWNER_MARKER" ]; then
            reasonix_index_ownership=$(head -1 "$REASONIX_INDEX_OWNER_MARKER" 2>/dev/null || true)
            if [ "$DRY_RUN" = true ]; then
                if [ "$reasonix_index_ownership" = "restore" ] && \
                   { [ -e "$REASONIX_INDEX_BACKUP" ] || [ -L "$REASONIX_INDEX_BACKUP" ]; }; then
                    echo -e "${BLUE}  Would restore pre-existing Reasonix INDEX.json${NC}"
                else
                    echo -e "${BLUE}  Would remove VexJoy-managed Reasonix INDEX.json${NC}"
                fi
            else
                rm -f "${REASONIX_SKILLS_DIR}/INDEX.json"
                if [ "$reasonix_index_ownership" = "restore" ] && \
                   { [ -e "$REASONIX_INDEX_BACKUP" ] || [ -L "$REASONIX_INDEX_BACKUP" ]; }; then
                    mv "$REASONIX_INDEX_BACKUP" "${REASONIX_SKILLS_DIR}/INDEX.json"
                    echo -e "${GREEN}  ✓ Restored pre-existing Reasonix INDEX.json${NC}"
                else
                    rm -f "$REASONIX_INDEX_BACKUP"
                    echo -e "${GREEN}  ✓ Removed VexJoy-managed Reasonix INDEX.json${NC}"
                fi
                rm -f "$REASONIX_INDEX_OWNER_MARKER"
            fi
            REMOVED+=("Reasonix managed skill index")
        elif [ -e "${REASONIX_SKILLS_DIR}/INDEX.json" ] || [ -L "${REASONIX_SKILLS_DIR}/INDEX.json" ]; then
            echo -e "${YELLOW}  Preserving unmanaged Reasonix INDEX.json${NC}"
        fi

        # Stale toolkit symlinks — only entries whose target no longer exists
        # (broken symlinks). Healthy toolkit symlinks in --symlink mode were
        # already removed by the per-name loop above.
        if [ "$DRY_RUN" != true ]; then
            find "$REASONIX_SKILLS_DIR" -maxdepth 1 -mindepth 1 -type l ! -exec test -e {} \; -delete 2>/dev/null || true
            rmdir "$REASONIX_SKILLS_DIR" 2>/dev/null && \
                echo -e "${GREEN}  ✓ Removed empty ${REASONIX_SKILLS_DIR}${NC}" || true
        fi
    else
        echo "  No ~/.reasonix/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Reasonix scripts mirror...${NC}"
    if [ -d "$REASONIX_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${REASONIX_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$REASONIX_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${REASONIX_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Reasonix scripts mirror directory")
    else
        echo "  No ~/.reasonix/scripts mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Reasonix hooks mirror...${NC}"
    if [ -d "$REASONIX_HOOKS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${REASONIX_HOOKS_DIR}${NC}"
        else
            rm -rf "$REASONIX_HOOKS_DIR"
            echo -e "${GREEN}  ✓ Removed ${REASONIX_HOOKS_DIR}${NC}"
        fi
        REMOVED+=("Reasonix hooks mirror directory")
    else
        echo "  No ~/.reasonix/hooks mirror found. Nothing to clean."
    fi

    # Archive the generated Reasonix settings.json (hooks key). config.json is
    # user-owned and never touched.
    if [ -f "${REASONIX_DIR}/settings.json" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would archive: ${REASONIX_DIR}/settings.json${NC}"
        else
            ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
            mv "${REASONIX_DIR}/settings.json" "${REASONIX_DIR}/settings.json.uninstalled.${ARCHIVE_TS}"
            echo -e "${GREEN}  ✓ Archived ${REASONIX_DIR}/settings.json${NC}"
        fi
        REMOVED+=("Reasonix settings.json (archived)")
    fi

    # Note: ~/.reasonix/config.json is intentionally left untouched.
    # Users own MCP/model/permissions config we did not write.

    # Phase 4: Remove install manifest
    echo ""
    echo -e "${YELLOW}Cleaning up manifest...${NC}"
    if [ -f "$MANIFEST_FILE" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${MANIFEST_FILE}${NC}"
        else
            rm "$MANIFEST_FILE"
            echo -e "${GREEN}  ✓ Removed install manifest${NC}"
        fi
        REMOVED+=("install manifest")
    else
        echo "  No manifest to remove."
    fi

    # Summary
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${GREEN}║                    Dry Run Uninstall Summary                   ║${NC}"
    else
        echo -e "${GREEN}║                      Uninstall Complete                        ║${NC}"
    fi
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ ${#REMOVED[@]} -gt 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "Would remove:"
        else
            echo "Removed:"
        fi
        for r in "${REMOVED[@]}"; do
            echo -e "  ${GREEN}✓${NC} ${r}"
        done
    else
        echo "  Nothing to remove."
    fi

    echo ""
    echo "Preserved (not touched):"
    echo "  • ~/.claude/settings.json (all keys except hooks)"
    echo "  • ~/.claude/projects/"
    echo "  • ~/.claude/memory/"
    echo "  • ~/.codex/config.toml (including [features] hooks flag)"
    echo "  • ~/.factory/config.toml (if present, like Codex)"
    echo "  • ~/.hermes/config.yaml (Hermes Agent configuration)"
    echo "  • ~/.reasonix/config.json (Reasonix MCP/model/permissions, user-owned)"
    echo "  • .local/ customizations in the toolkit repo"
    echo "  • Python packages (remove manually if needed)"
    if [ ${#PRESERVED[@]} -gt 0 ]; then
        for p in "${PRESERVED[@]}"; do
            echo "  • ${p}"
        done
    fi

    echo ""
    echo -e "${YELLOW}Tip:${NC} You can also run ${BLUE}./install.sh --rollback${NC} to restore"
    echo "your previous settings.json from the most recent backup."
    echo ""
    exit 0
}

# Handle uninstall
if [ "$MODE" = "uninstall" ]; then
    uninstall
fi

# Handle rollback
if [ "$MODE" = "rollback" ]; then
    echo -e "${YELLOW}Rolling back settings.json...${NC}"
    SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
    # Find the most recent backup
    LATEST_BACKUP=$(ls -1t "${SETTINGS_FILE}.backup."* 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo -e "${RED}Error: No settings.json backup found in ${CLAUDE_DIR}${NC}"
        exit 1
    fi
    echo "  Restoring from: $(basename "$LATEST_BACKUP")"
    cp "$LATEST_BACKUP" "$SETTINGS_FILE"
    echo -e "${GREEN}✓ settings.json restored from $(basename "$LATEST_BACKUP")${NC}"
    exit 0
fi

# Interactive mode selection
if [ -z "$MODE" ]; then
    echo "How would you like to install?"
    echo ""
    echo "  1) Symlink (recommended for development)"
    echo "     - Changes to this repo appear immediately in Claude Code"
    echo "     - Easy to update with git pull"
    echo ""
    echo "  2) Copy (recommended for stability)"
    echo "     - Independent copy in ~/.claude"
    echo "     - Re-run install.sh to update"
    echo ""
    read -p "Choose [1/2]: " choice

    case $choice in
        1) MODE="symlink" ;;
        2) MODE="copy" ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
fi

# Verify requirements
check_python
detect_pip_command

# Optional runtime mirrors sync when the runtime's command is on PATH OR its
# home dir already exists. The dir check keeps existing installs syncing when
# the runtime has no CLI on PATH (e.g. ~/.factory without a `factory` binary);
# clean environments get no new runtime dirs.
MIRROR_CODEX=false
MIRROR_FACTORY=false
MIRROR_HERMES=false
MIRROR_REASONIX=false
if is_command_available codex || [ -d "$CODEX_DIR" ]; then
    MIRROR_CODEX=true
fi
if is_command_available factory || [ -d "$FACTORY_DIR" ]; then
    MIRROR_FACTORY=true
fi
if is_command_available hermes || [ -d "$HERMES_DIR" ]; then
    MIRROR_HERMES=true
fi
if is_command_available reasonix || [ -d "$REASONIX_DIR" ]; then
    MIRROR_REASONIX=true
fi

# Create ~/.claude if needed
echo ""
echo -e "${YELLOW}Setting up ~/.claude directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${CLAUDE_DIR}${NC}"
else
    mkdir -p "${CLAUDE_DIR}"
fi
echo -e "${GREEN}✓ ${CLAUDE_DIR} ready${NC}"

echo ""
if [ "$MIRROR_CODEX" = true ]; then
    echo ""
    echo -e "${YELLOW}Setting up ~/.codex skills directory...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${CODEX_SKILLS_DIR}${NC}"
    else
        mkdir -p "${CODEX_SKILLS_DIR}"
    fi
    echo -e "${GREEN}✓ ${CODEX_SKILLS_DIR} ready${NC}"

    echo ""
    echo -e "${YELLOW}Setting up ~/.codex agents directory...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${CODEX_AGENTS_DIR}${NC}"
    else
        mkdir -p "${CODEX_AGENTS_DIR}"
    fi
    echo -e "${GREEN}✓ ${CODEX_AGENTS_DIR} ready${NC}"
else
    echo ""
    echo -e "${BLUE}Skipping ~/.codex setup (codex not detected: no command, no ~/.codex).${NC}"
fi


if [ "$MIRROR_FACTORY" = true ]; then
    echo ""
    echo -e "${YELLOW}Setting up ~/.factory directory...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${FACTORY_DIR}${NC}"
    else
        mkdir -p "${FACTORY_DIR}"
    fi
    echo -e "${GREEN}✓ ${FACTORY_DIR} ready${NC}"
else
    echo ""
    echo -e "${BLUE}Skipping ~/.factory setup (factory not detected: no command, no ~/.factory).${NC}"
fi

if [ "$MIRROR_HERMES" = true ]; then
    echo ""
    echo -e "${YELLOW}Setting up ~/.hermes/skills directory...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${HERMES_SKILLS_DIR}${NC}"
    else
        mkdir -p "${HERMES_SKILLS_DIR}"
    fi
    echo -e "${GREEN}✓ ${HERMES_SKILLS_DIR} ready${NC}"
else
    echo ""
    echo -e "${BLUE}Skipping ~/.hermes setup (hermes not detected: no command, no ~/.hermes).${NC}"
fi

if [ "$MIRROR_REASONIX" = true ]; then
    echo ""
    echo -e "${YELLOW}Setting up ~/.reasonix/skills directory...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${REASONIX_SKILLS_DIR}${NC}"
    else
        mkdir -p "${REASONIX_SKILLS_DIR}"
    fi
    echo -e "${GREEN}✓ ${REASONIX_SKILLS_DIR} ready${NC}"
else
    echo ""
    echo -e "${BLUE}Skipping ~/.reasonix setup (reasonix not detected: no command, no ~/.reasonix).${NC}"
fi

# detect_conflicts — scans all runtime dirs × all component types.
# Populates parallel arrays conflict_keys[] and conflict_vals[] (bash 3.2 compatible).
conflict_keys=()
conflict_vals=()

_conflict_set() {
    conflict_keys+=("$1")
    conflict_vals+=("$2")
}

_conflict_get() {
    local _k _i
    _k="$1"
    for _i in "${!conflict_keys[@]}"; do
        [ "${conflict_keys[$_i]}" = "$_k" ] && { printf '%s' "${conflict_vals[$_i]}"; return 0; }
    done
    return 1
}

_conflict_has() {
    _conflict_get "$1" > /dev/null 2>&1
}

detect_conflicts() {
    local runtime_dir component target src count items item name
    local -a runtime_dirs=("$CLAUDE_DIR")
    [ "$MIRROR_CODEX" = true ] && runtime_dirs+=("$CODEX_DIR")
    [ "$MIRROR_FACTORY" = true ] && runtime_dirs+=("$FACTORY_DIR")
    [ "$MIRROR_HERMES" = true ] && runtime_dirs+=("$HERMES_DIR")
    [ "$MIRROR_REASONIX" = true ] && runtime_dirs+=("$REASONIX_DIR")

    for runtime_dir in "${runtime_dirs[@]}"; do
        [ -d "$runtime_dir" ] || continue
        for component in agents skills hooks commands scripts; do
            if [ "$runtime_dir" = "$REASONIX_DIR" ]; then
                case "$component" in
                    agents|commands) continue ;;
                esac
            fi
            target="$runtime_dir/$component"
            src="$SCRIPT_DIR/$component"
            [ -d "$src" ] || continue
            [ -d "$target" ] || [ -L "$target" ] || continue
            if [ -L "$target" ]; then
                if _symlink_points_to "$target" "$src"; then
                    # Whole-dir symlink pointing at our source (e.g. a prior
                    # --force install). Per-item mode will convert it to a real
                    # dir so external siblings can coexist; surface it here so
                    # the conversion is not silent.
                    _conflict_set "$runtime_dir/$component" "whole-dir symlink (will convert to per-item)"
                else
                    # Whole-dir symlink pointing elsewhere (external content lives there).
                    _conflict_set "$runtime_dir/$component" "symlink→$(readlink "$target")"
                fi
                continue
            fi
            # Count items (files and dirs) in target not present in src
            count=0; items=""
            for item in "$target"/*; do
                [ -e "$item" ] || [ -L "$item" ] || continue
                name=$(basename "$item")
                [ -e "$src/$name" ] || { count=$((count+1)); items="$items $name"; }
            done
            if [ "$count" -gt 0 ]; then
                _conflict_set "$runtime_dir/$component" "$count external:$items"
            fi
        done
    done
    return 0
}

print_conflict_table() {
    local _i
    echo ""
    echo "Found existing content in the following locations:"
    for _i in "${!conflict_keys[@]}"; do
        echo "  ${conflict_keys[$_i]}  (${conflict_vals[$_i]})"
    done
    echo ""
    echo "Choose install mode for all conflicting locations:"
    echo "  [1] per-item  — symlink each vexjoy item individually; preserve external content (recommended)"
    echo "  [2] replace   — rm -rf and replace with whole-dir symlink (destroys external content)"
    echo "  [3] skip      — leave conflicting locations unchanged; install only conflict-free locations"
    echo ""
}

# Install components
echo ""
echo -e "${YELLOW}Installing components (mode: ${MODE})...${NC}"

install_component() {
    local name=$1
    local base_dir=${2:-$CLAUDE_DIR}
    local target_name=${3:-$name}
    local source="${SCRIPT_DIR}/${name}"
    local target="${base_dir}/${target_name}"

    local component_key="$base_dir/$target_name"

    # Profile filtering active for this component? Whole-dir symlinks cannot
    # exclude items, so a filtered component is always installed per-item.
    local filtered=false
    case $name in
        skills|agents|hooks) _category_filtered "$name" && filtered=true ;;
    esac

    # Skip mode: leave conflicting locations untouched; install conflict-free ones normally.
    if [ "$CONFLICT_MODE" = "skip" ] && [ "$MODE" = "symlink" ] && _conflict_has "$component_key"; then
        echo -e "${YELLOW}  Skipping ${target} (kept existing — skip mode)${NC}"
        return
    fi

    # Per-item mode: symlink each item (file or dir) individually; preserve external content.
    if [ "$MODE" = "symlink" ] && \
       { [ "$filtered" = true ] || { [ "$CONFLICT_MODE" = "per-item" ] && \
       { _conflict_has "$component_key" || [ -d "$target" ] || [ -L "$target" ]; }; }; }; then
        if [ "$DRY_RUN" = true ]; then
            if [ -L "$target" ] && _symlink_points_to "$target" "$source"; then
                echo -e "${BLUE}  Would convert whole-dir symlink to per-item dir: ${target}${NC}"
            else
                echo -e "${BLUE}  Would per-item symlink into: ${target}${NC}"
            fi
        else
            # A prior --force install may have left a whole-dir symlink into the
            # repo. Convert only toolkit-owned symlinks; external symlinks are
            # preserved and receive add-only per-item links through the symlink.
            if [ -L "$target" ] && _symlink_points_to "$target" "$source"; then
                echo "  Converting whole-dir symlink to per-item dir: $target"
                rm "$target"
            fi
            mkdir -p "$target"
            local item item_name
            for item in "$source"/*; do
                [ -e "$item" ] || [ -L "$item" ] || continue
                item_name=$(basename "$item")
                if [ "$filtered" = true ] && _profile_disabled "$name" "$item_name"; then
                    echo -e "${YELLOW}  Skipping ${item_name} (not selected)${NC}"
                    continue
                fi
                if [ "$name" = "hooks" ] && [ "$item_name" = "lib" ]; then
                    if [ -L "$target/$item_name" ] || [ -f "$target/$item_name" ]; then
                        rm -rf "$target/$item_name"
                    fi
                    mkdir -p "$target/$item_name"
                    local lib_item lib_name
                    for lib_item in "$item"/*; do
                        [ -e "$lib_item" ] || [ -L "$lib_item" ] || continue
                        lib_name=$(basename "$lib_item")
                        if [ -e "$target/$item_name/$lib_name" ] || [ -L "$target/$item_name/$lib_name" ]; then
                            rm -rf "$target/$item_name/$lib_name"
                        fi
                        ln -s "$lib_item" "$target/$item_name/$lib_name"
                    done
                    echo -e "${GREEN}  ✓ Per-item refreshed ${item_name}${NC}"
                    continue
                fi
                if [ -e "$target/$item_name" ]; then
                    echo -e "${YELLOW}  WARNING: $target/$item_name already exists — skipping (kept existing)${NC}"
                    continue
                fi
                ln -s "$item" "$target/$item_name"
                echo -e "${GREEN}  ✓ Per-item linked ${item_name}${NC}"
            done
        fi
        return
    fi

    # Check if target exists
    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ -L "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove existing symlink: $target${NC}"
            else
                echo "  Removing existing symlink: $target"
                rm "$target"
            fi
        else
            echo -e "${YELLOW}  Warning: $target exists and is not a symlink${NC}"
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would replace existing directory${NC}"
            elif [ "$FORCE" = true ]; then
                echo "  Replacing existing directory (--force): $target"
                rm -rf "$target"
            else
                read -p "  Overwrite? [y/N]: " confirm
                if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
                    echo "  Skipping $name"
                    return
                fi
                rm -rf "$target"
            fi
        fi
    fi

    if [ "$MODE" = "symlink" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would symlink: ${source} -> ${target}${NC}"
        else
            ln -s "$source" "$target"
            echo -e "${GREEN}  ✓ Symlinked ${name}${NC}"
        fi
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy: ${source} -> ${target}${NC}"
        else
            cp -r "$source" "$target"
            echo -e "${GREEN}  ✓ Copied ${name}${NC}"
            # Copy mode: prune profile-disabled items from the fresh copy.
            if [ "$filtered" = true ]; then
                local copied copied_name
                for copied in "$target"/*; do
                    [ -e "$copied" ] || continue
                    copied_name=$(basename "$copied")
                    if _profile_disabled "$name" "$copied_name"; then
                        rm -rf "$copied"
                        echo -e "${YELLOW}  Removed ${copied_name} (disabled by profile)${NC}"
                    fi
                done
            fi
        fi
    fi
}

# link_skills_nested SOURCE TARGET — build a nested skills tree (symlink mode).
#
# The repo skills/ tree is category/skill (e.g. skills/business/csuite), plus a
# few top-level entries that are skills themselves (a dir holding SKILL.md) or
# loose files (INDEX.json). To let users drop their own skills alongside ours at
# any level, we retain category links and add a root alias for every nested
# skill. Runtimes that scan one level deep can therefore discover every skill.
# This is add-only — existing external entries are preserved, never overwritten.
link_skills_nested() {
    local source=$1
    local target=$2
    local entry entry_name child child_name

    if [ "$DRY_RUN" = true ]; then
        if [ -L "$target" ]; then
            echo -e "${BLUE}  Would convert whole-dir symlink to nested skills dir: ${target}${NC}"
        else
            echo -e "${BLUE}  Would nest per-skill symlinks into: ${target}${NC}"
        fi
        return
    fi

    # A prior install may have left ~/.../skills as a whole-dir symlink into the
    # repo; replace only that toolkit-owned symlink with a real dir so per-skill
    # links can live inside. External symlinks are preserved and populated add-only.
    if [ -L "$target" ] && _symlink_points_to "$target" "$source"; then
        echo "  Converting whole-dir symlink to nested skills dir: $target"
        rm "$target"
    fi
    mkdir -p "$target"

    for entry in "$source"/*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        entry_name=$(basename "$entry")

        # Top-level file (e.g. INDEX.json) or a top-level skill dir (has SKILL.md):
        # link the whole thing at the top level.
        if [ ! -d "$entry" ] || [ -f "$entry/SKILL.md" ]; then
            if [ -d "$entry" ] && _profile_disabled skills "$entry_name"; then
                echo -e "${YELLOW}  Skipping ${entry_name} (not selected)${NC}"
                continue
            fi
            if [ -e "$target/$entry_name" ] || [ -L "$target/$entry_name" ]; then
                continue  # external/existing entry; keep it
            fi
            ln -s "$entry" "$target/$entry_name"
            echo -e "${GREEN}  ✓ Linked ${entry_name}${NC}"
            continue
        fi

        # Category / support dir (no SKILL.md at this level): make a real dir and
        # link each child individually so external skills can coexist.
        # If a prior install left this category as a whole-dir symlink into the
        # repo, convert it. Preserve category symlinks pointing elsewhere.
        if [ -L "$target/$entry_name" ] && _symlink_points_to "$target/$entry_name" "$entry"; then
            rm "$target/$entry_name"
        fi
        mkdir -p "$target/$entry_name"
        for child in "$entry"/*; do
            [ -e "$child" ] || [ -L "$child" ] || continue
            child_name=$(basename "$child")
            if [ -d "$child" ] && _profile_disabled skills "$child_name"; then
                echo -e "${YELLOW}  Skipping ${entry_name}/${child_name} (not selected)${NC}"
                continue
            fi
            # Skip skills folded into a parent via promoted_to: frontmatter,
            # but only when the target skill exists (forward-looking tags stay deployed).
            if [ -f "$child/SKILL.md" ]; then
                _promoted_target=$(head -20 "$child/SKILL.md" | grep '^promoted_to:' | sed 's/^promoted_to:\s*//' | tr -d ' ')
                if [ -n "$_promoted_target" ]; then
                    # Check if target skill dir exists anywhere under source
                    _target_found=false
                    for _cat in "$source"/*/; do
                        if [ -f "${_cat}${_promoted_target}/SKILL.md" ]; then
                            _target_found=true
                            break
                        fi
                    done
                    if [ "$_target_found" = true ]; then
                        continue
                    fi
                fi
            fi
            if [ -e "$target/$entry_name/$child_name" ] || [ -L "$target/$entry_name/$child_name" ]; then
                continue  # external/existing entry; keep it
            fi
            ln -s "$child" "$target/$entry_name/$child_name"
            # Expose nested skills to one-level runtime scanners as well. Keep
            # an external root skill when a name collision exists.
            if [ -f "$child/SKILL.md" ] && [ ! -e "$target/$child_name" ] && [ ! -L "$target/$child_name" ]; then
                ln -s "$child" "$target/$child_name"
            fi
        done
        echo -e "${GREEN}  ✓ Nested ${entry_name}/${NC}"
    done
}

sync_mirror_entry() {
    local source=$1
    local target=$2
    local label=${3:-Mirror}
    local refresh_existing=${4:-false}
    local name
    name=$(basename "$source")

    # Per-item mode: add-only symlink for each item (file or dir); skip existing entries
    if [ "$CONFLICT_MODE" = "per-item" ] && [ "$MODE" = "symlink" ] && [ -d "$source" ]; then
        if [ "$DRY_RUN" = true ]; then
            if [ -L "$target" ] && _symlink_points_to "$target" "$source"; then
                echo -e "${BLUE}  Would convert whole-dir symlink to per-item ${label} dir: ${target}${NC}"
            else
                echo -e "${BLUE}  Would per-item sync ${label} entry: ${source} -> ${target}/${NC}"
            fi
        else
            # Convert only toolkit-owned whole-dir symlinks. External symlinks
            # remain the user's chosen active path. Never traverse them: a
            # refresh inside that directory would mutate external content.
            if [ -L "$target" ] && _symlink_points_to "$target" "$source"; then
                echo -e "${GREEN}  ✓ ${label} converting whole-dir symlink to per-item dir${NC}"
                rm "$target"
            elif [ -L "$target" ]; then
                echo -e "${YELLOW}  Skipping external ${label} symlink: ${target}${NC}"
                return
            fi
            mkdir -p "$target"
            local item item_name
            for item in "$source"/*; do
                [ -e "$item" ] || [ -L "$item" ] || continue
                item_name=$(basename "$item")
                if [ "$name" = "lib" ] && [ "$(basename "$(dirname "$source")")" = "hooks" ]; then
                    if [ -e "$target/$item_name" ] || [ -L "$target/$item_name" ]; then
                        rm -rf "$target/$item_name"
                    fi
                    ln -s "$item" "$target/$item_name"
                    echo -e "${GREEN}  ✓ ${label} per-item refreshed ${item_name}${NC}"
                    continue
                fi
                if [ -e "$target/$item_name" ] || [ -L "$target/$item_name" ]; then
                    if [ "$refresh_existing" != true ]; then
                        continue  # external/existing entry; keep it
                    fi
                    if [ -d "$item" ] && [ -d "$target/$item_name" ] && [ ! -L "$target/$item_name" ]; then
                        sync_mirror_entry "$item" "$target/$item_name" "$label" true
                        continue
                    fi
                    rm -rf "$target/$item_name"
                    ln -s "$item" "$target/$item_name"
                    echo -e "${GREEN}  ✓ ${label} per-item refreshed ${item_name}${NC}"
                    continue
                fi
                ln -s "$item" "$target/$item_name"
                echo -e "${GREEN}  ✓ ${label} per-item linked ${item_name}${NC}"
            done
        fi
        return
    fi

    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would replace ${label} entry: ${target}${NC}"
        else
            rm -rf "$target"
        fi
    fi

    if [ "$MODE" = "symlink" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would symlink ${label} entry: ${source} -> ${target}${NC}"
        else
            ln -s "$source" "$target"
            echo -e "${GREEN}  ✓ ${label} symlinked ${name}${NC}"
        fi
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy ${label} entry: ${source} -> ${target}${NC}"
        else
            if [ -d "$source" ]; then
                cp -r "$source" "$target"
            else
                cp "$source" "$target"
            fi
            echo -e "${GREEN}  ✓ ${label} copied ${name}${NC}"
        fi
    fi
}

# Backward-compatible wrapper for existing call sites
sync_codex_entry() {
    # Codex is a generated toolkit mirror. Refresh canonical children during
    # --sync so an earlier copy or stale link cannot shadow changed source.
    # Entries not present in the source remain untouched.
    sync_mirror_entry "$1" "$2" "Codex" "$SYNC_REFRESH"
}

# install_git_hook — writes .git/hooks/post-merge to auto-sync new items after git pull.
# Add-only, never removes, never overwrites existing entries.
install_git_hook() {
    local hook=".git/hooks/post-merge"
    [ -d ".git" ] || return 0  # no-op outside a git repo clone
    # Never clobber a pre-existing hook we did not write.
    if [ -e "$hook" ] && ! grep -q "Written by vexjoy-agent" "$hook" 2>/dev/null; then
        echo -e "${YELLOW}  Existing post-merge hook found — not overwriting: ${hook}${NC}"
        return 0
    fi
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would install post-merge hook: ${hook}${NC}"
        return 0
    fi
    mkdir -p ".git/hooks"
    cat > "$hook" << 'HOOK'
#!/usr/bin/env bash
# Written by vexjoy-agent install.sh — auto-syncs new items after git pull.
# Add-only: skips items already present; never removes or overwrites.
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
for runtime_dir in     "$HOME/.claude" "$HOME/.codex"     "$HOME/.factory" "$HOME/.hermes" "$HOME/.reasonix"; do
  [ -d "$runtime_dir" ] || continue
  for component in agents skills hooks commands scripts; do
    if [ "$runtime_dir" = "$HOME/.reasonix" ]; then
      case "$component" in
        agents|commands) continue ;;
      esac
    fi
    src="$REPO_DIR/$component"
    dst="$runtime_dir/$component"
    [ -d "$src" ] || continue
    [ -d "$dst" ] || continue  # only sync if component dir already installed
    for item in "$src"/*; do
      [ -e "$item" ] || [ -L "$item" ] || continue
      name=$(basename "$item")
      [ -e "$dst/$name" ] && continue  # already present; skip
      ln -s "$item" "$dst/$name"
      echo "[vexjoy-agent] auto-synced: $dst/$name"
    done
  done
done

# Deploy-staleness notice (warn-only): the sync above is add-only, so an EDITED
# hook/script stays stale in ~/.claude until sync-to-user-claude.py runs. If this
# merge touched hooks/ or scripts/, tell the user to redeploy. Guarded so it can
# never fail the merge; the hook always exits 0.
if git rev-parse --verify -q ORIG_HEAD >/dev/null 2>&1 && git rev-parse --verify -q HEAD >/dev/null 2>&1; then
  changed="$(git diff-tree -r --name-only --no-commit-id ORIG_HEAD HEAD 2>/dev/null | grep -E '^(hooks|scripts)/' || true)"
  if [ -n "$changed" ]; then
    echo "[vexjoy-agent] hook/script changes merged — run:"
    echo "  python3 ~/.claude/hooks/sync-to-user-claude.py"
    echo "to deploy live (or restart the session)."
  fi
fi
exit 0
HOOK
    chmod +x "$hook"
    echo -e "${GREEN}  ✓ Installed post-merge hook: ${hook}${NC}"
}

# ---------------------------------------------------------------------------
# Opt-in install profile (.local/profile.yaml) — credit: @thomasvan.
# Absent profile = no filtering; install behaves exactly as without this block.
# VEXJOY_INSTALL_PROFILE overrides the path (used by tests).
# ---------------------------------------------------------------------------
PROFILE_FILE="${VEXJOY_INSTALL_PROFILE:-${SCRIPT_DIR}/.local/profile.yaml}"
DISABLED_SKILLS=""
DISABLED_AGENTS=""
DISABLED_HOOKS=""

if [ "$CONFIGURE" = true ] || [ "$CONFIGURE_ONLY" = true ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would run interactive profile picker (scripts/configure-profile.py)${NC}"
    else
        $PYTHON_CMD "${SCRIPT_DIR}/scripts/configure-profile.py" --output "$PROFILE_FILE"
    fi
    if [ "$CONFIGURE_ONLY" = true ]; then
        echo "Profile written. Run ./install.sh to apply it."
        exit 0
    fi
fi

if [ -f "$PROFILE_FILE" ]; then
    DISABLED_SKILLS=$($PYTHON_CMD "${SCRIPT_DIR}/scripts/load-profile.py" --list skills --profile "$PROFILE_FILE") || DISABLED_SKILLS=""
    DISABLED_AGENTS=$($PYTHON_CMD "${SCRIPT_DIR}/scripts/load-profile.py" --list agents --profile "$PROFILE_FILE") || DISABLED_AGENTS=""
    DISABLED_HOOKS=$($PYTHON_CMD "${SCRIPT_DIR}/scripts/load-profile.py" --list hooks --profile "$PROFILE_FILE") || DISABLED_HOOKS=""
    _ns=$(printf '%s' "$DISABLED_SKILLS" | grep -c . || true)
    _na=$(printf '%s' "$DISABLED_AGENTS" | grep -c . || true)
    _nh=$(printf '%s' "$DISABLED_HOOKS" | grep -c . || true)
    echo -e "${YELLOW}Install profile: ${PROFILE_FILE} (disabled: ${_ns} skills, ${_na} agents, ${_nh} hooks)${NC}"
fi

# _profile_disabled CATEGORY NAME — 0 when NAME is disabled by the profile.
# Agents match by stem (foo.md and foo/ both match "foo"); skills and hooks
# match the basename as-is (skill dir name, hook filename like foo.py).
_profile_disabled() {
    local list name=$2
    case $1 in
        skills) list="$DISABLED_SKILLS" ;;
        agents) list="$DISABLED_AGENTS"; name="${name%.md}" ;;
        hooks)  list="$DISABLED_HOOKS" ;;
        *) return 1 ;;
    esac
    [ -n "$list" ] || return 1
    printf '%s\n' "$list" | grep -Fxq -- "$name"
}

# _category_filtered CATEGORY — 0 when the profile disables anything in CATEGORY.
_category_filtered() {
    case $1 in
        skills) [ -n "$DISABLED_SKILLS" ] ;;
        agents) [ -n "$DISABLED_AGENTS" ] ;;
        hooks)  [ -n "$DISABLED_HOOKS" ] ;;
        *) return 1 ;;
    esac
}

# Generate a runtime-local skill registry from the mirror that was actually
# deployed. The temporary output is atomically moved over a source INDEX.json
# symlink, so both copy and symlink installs validate profile exclusions against
# the installed tree rather than the repository inventory.
generate_installed_skill_index() {
    local runtime_dir=$1
    local label=$2
    local preserve_existing=${3:-false}
    local skills_dir="${runtime_dir}/skills"
    local index_path="${skills_dir}/INDEX.json"
    local output_tmp local_output_tmp index_output prepared=false ownership=""
    local deployed_skill_link deployed_skill_target deployed_skill_md deployed_skill_dir deployed_skill_name
    local source_skills_canonical
    local -a index_layout_args=()

    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would generate ${label} installed skill index: ${index_path}${NC}"
        return 0
    fi

    mkdir -p "$skills_dir"
    # A prior symlink install may have deployed a skill that the current
    # profile disables. Install loops skip disabled skills but must also remove
    # their old root aliases and nested category links before inventory scans.
    # Preserve user links by removing only symlinks that resolve inside this
    # toolkit's public skills tree.
    if [ -n "$DISABLED_SKILLS" ]; then
        source_skills_canonical=$(_canonical_path "${SCRIPT_DIR}/skills") || source_skills_canonical=""
        if [ -n "$source_skills_canonical" ]; then
            while IFS= read -r deployed_skill_link; do
                [ -n "$deployed_skill_link" ] || continue
                deployed_skill_name=$(basename "$deployed_skill_link")
                _profile_disabled skills "$deployed_skill_name" || continue
                deployed_skill_target=$(_canonical_path "$deployed_skill_link") || continue
                case "$deployed_skill_target" in
                    "$source_skills_canonical"/*)
                        rm "$deployed_skill_link"
                        echo -e "${YELLOW}  Removed ${label} ${deployed_skill_name} symlink (disabled by profile)${NC}"
                        ;;
                esac
            done < <(find -P "$skills_dir" -mindepth 1 -maxdepth 2 -type l -print 2>/dev/null)
        fi
    fi

    # Copy-mode category mirrors contain nested skills as well as flat aliases.
    # Remove disabled nested copies before indexing so deployment and inventory
    # agree. This scan does not follow the external symlinks preserved above.
    if [ -n "$DISABLED_SKILLS" ]; then
        while IFS= read -r deployed_skill_md; do
            [ -n "$deployed_skill_md" ] || continue
            deployed_skill_dir=$(dirname "$deployed_skill_md")
            deployed_skill_name=$(basename "$deployed_skill_dir")
            if _profile_disabled skills "$deployed_skill_name"; then
                rm -rf "$deployed_skill_dir"
                echo -e "${YELLOW}  Removed ${label} ${deployed_skill_name} (disabled by profile)${NC}"
            fi
        done < <(find "$skills_dir" -mindepth 2 -name SKILL.md -print 2>/dev/null)
    fi

    if [ "$preserve_existing" = true ] && [ ! -f "$REASONIX_INDEX_OWNER_MARKER" ]; then
        if [ -e "$index_path" ] || [ -L "$index_path" ]; then
            rm -f "$REASONIX_INDEX_BACKUP"
            mv "$index_path" "$REASONIX_INDEX_BACKUP"
            ownership="restore"
        else
            ownership="remove"
        fi
        printf '%s\n' "$ownership" > "$REASONIX_INDEX_OWNER_MARKER"
        prepared=true
    fi

    output_tmp=$(mktemp "${skills_dir}/.INDEX.json.vexjoy.XXXXXX")
    local_output_tmp=$(mktemp "${skills_dir}/.INDEX.local.json.vexjoy.XXXXXX")
    # Whole-directory symlinks retain the repository's nested category layout.
    # In that layout --include-private would request flattened file paths, then
    # prune every nested-only entry as a phantom. Real runtime skill dirs use
    # either copied nested paths, nested aliases, or flat mirrors; their paths
    # are discoverable in-place and private-inclusive scanning remains correct.
    if [ ! -L "$skills_dir" ]; then
        index_layout_args+=(--include-private)
    fi
    if index_output=$(HOME="$runtime_dir" "$PYTHON_CMD" "${SCRIPT_DIR}/scripts/generate-skill-index.py" \
        "${index_layout_args[@]}" \
        --repo-root "$runtime_dir" \
        --output "$output_tmp" 2>&1); then
        cp "$output_tmp" "$local_output_tmp"
        mv -f "$local_output_tmp" "${skills_dir}/INDEX.local.json"
        mv -f "$output_tmp" "$index_path"
        echo -e "${GREEN}  ✓ Generated ${label} installed skill inventories${NC}"
        return 0
    fi

    rm -f "$output_tmp" "$local_output_tmp"
    if [ "$prepared" = true ]; then
        rm -f "$REASONIX_INDEX_OWNER_MARKER"
        if [ "$ownership" = "restore" ] && \
           { [ -e "$REASONIX_INDEX_BACKUP" ] || [ -L "$REASONIX_INDEX_BACKUP" ]; }; then
            mv "$REASONIX_INDEX_BACKUP" "$index_path"
        else
            rm -f "$REASONIX_INDEX_BACKUP"
        fi
    fi
    echo -e "${RED}  ✗ Failed to generate ${label} installed skill index${NC}"
    echo -e "${RED}${index_output}${NC}"
    return 1
}

# Generate the agent registry from the files actually deployed to a runtime.
# This cannot depend on the source agents/INDEX.json: a clean checkout may not
# have generated it yet, and copy mode installs agents before the source index
# refresh near the end of this script. Native workflow helpers import the
# installed registry at module load, so absence is fatal rather than advisory.
generate_installed_agent_index() {
    local runtime_dir=$1
    local label=$2
    local agents_dir="${runtime_dir}/agents"
    local index_path="${agents_dir}/INDEX.json"
    local output_tmp local_output_tmp index_output

    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would generate ${label} installed agent inventories: ${index_path}${NC}"
        return 0
    fi

    mkdir -p "$agents_dir"
    output_tmp=$(mktemp "${agents_dir}/.INDEX.json.vexjoy.XXXXXX")
    local_output_tmp=$(mktemp "${agents_dir}/.INDEX.local.json.vexjoy.XXXXXX")
    if index_output=$(HOME="$runtime_dir" "$PYTHON_CMD" "${SCRIPT_DIR}/scripts/generate-agent-index.py" \
        --include-private \
        --repo-root "$runtime_dir" \
        --output "$output_tmp" 2>&1); then
        cp "$output_tmp" "$local_output_tmp"
        mv -f "$local_output_tmp" "${agents_dir}/INDEX.local.json"
        mv -f "$output_tmp" "$index_path"
        echo -e "${GREEN}  ✓ Generated ${label} installed agent inventories${NC}"
        return 0
    fi

    rm -f "$output_tmp" "$local_output_tmp"
    echo -e "${RED}  ✗ Failed to generate ${label} installed agent inventories${NC}"
    echo -e "${RED}${index_output}${NC}"
    return 1
}

# Scan for conflicts before first install_component call
if [ "$MODE" = "symlink" ]; then
    detect_conflicts
    if [ ${#conflict_keys[@]} -gt 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            print_conflict_table
            _default_mode="${CONFLICT_MODE:-per-item}"
            echo -e "${BLUE}  DRY RUN: Would prompt for conflict mode. Default would be: ${_default_mode}${NC}"
            echo -e "${BLUE}  Would use mode: ${_default_mode}${NC}"
            [ -z "$CONFLICT_MODE" ] && CONFLICT_MODE="per-item"
        elif [ -z "$CONFLICT_MODE" ]; then
            print_conflict_table
            # `read` returns non-zero on EOF (e.g. stdin from /dev/null in CI or
            # any non-interactive run). Guard it so that does not trip `set -e`;
            # an empty answer falls through to the documented default below.
            if ! read -r -p "Choice [1/2/3, default=1]: " _ans; then
                _ans=""
            fi
            case "${_ans:-1}" in
                1) CONFLICT_MODE="per-item" ;;
                2) CONFLICT_MODE="replace"  ;;
                3) CONFLICT_MODE="skip"     ;;
                *) CONFLICT_MODE="per-item" ;;
            esac
            echo ""
        fi
    fi
fi

# Install main components
for component in agents skills hooks commands scripts; do
    if [ -d "${SCRIPT_DIR}/${component}" ]; then
        # Skills get a nested layout (real category dirs + per-skill symlinks),
        # matching ~/.codex, so users can drop their own skills
        # into any category. Only in symlink mode, and not when explicitly
        # replacing or skipping conflicting locations.
        if [ "$component" = "skills" ] && [ "$MODE" = "symlink" ] && \
           [ "$CONFLICT_MODE" != "replace" ] && [ "$CONFLICT_MODE" != "skip" ]; then
            link_skills_nested "${SCRIPT_DIR}/skills" "${CLAUDE_DIR}/skills"
        else
            install_component "$component"
        fi
    fi
done

# Install private components (if they exist, gitignored)
for private_dir in private-agents private-skills private-hooks; do
    public_name="${private_dir#private-}"  # strips "private-" prefix
    if [ -d "${SCRIPT_DIR}/${private_dir}" ]; then
        echo ""
        echo -e "${YELLOW}Installing private ${public_name}...${NC}"
        # Copy/link private components into the same ~/.claude target
        # Private overrides public when same name exists
        if [ "$MODE" = "symlink" ]; then
            for item in "${SCRIPT_DIR}/${private_dir}/"*; do
                [ -e "$item" ] || continue
                item_name=$(basename "$item")
                target="${CLAUDE_DIR}/${public_name}/${item_name}"
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would link private: ${item_name}${NC}"
                else
                    rm -rf "$target" 2>/dev/null
                    ln -sf "$item" "$target"
                    echo -e "${GREEN}  ✓ Linked private ${item_name}${NC}"
                fi
            done
        else
            for item in "${SCRIPT_DIR}/${private_dir}/"*; do
                [ -e "$item" ] || continue
                item_name=$(basename "$item")
                target="${CLAUDE_DIR}/${public_name}/${item_name}"
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would copy private: ${item_name}${NC}"
                else
                    rm -rf "$target" 2>/dev/null
                    cp -r "$item" "$target"
                    echo -e "${GREEN}  ✓ Copied private ${item_name}${NC}"
                fi
            done
        fi
    fi
done

generate_installed_agent_index "$CLAUDE_DIR" "Claude"

# Install private-voices into Claude skills (goes through symlink into repo/skills/)
if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    echo ""
    echo -e "${YELLOW}Installing private voices (Claude)...${NC}"
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        if _profile_disabled skills "voice-${voice_name}"; then
            echo -e "${YELLOW}  Skipping voice-${voice_name} (not selected)${NC}"
            target="${CLAUDE_DIR}/skills/voice-${voice_name}"
            if [ -L "$target" ] && _symlink_points_to "$target" "$skill_src"; then
                rm "$target"
                echo -e "${YELLOW}  Removed Claude voice-${voice_name} symlink (disabled by profile)${NC}"
            fi
            continue
        fi
        target="${CLAUDE_DIR}/skills/voice-${voice_name}"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would link voice: voice-${voice_name}${NC}"
        else
            rm -rf "$target" 2>/dev/null
            if [ "$MODE" = "symlink" ]; then
                ln -sf "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Linked voice-${voice_name}${NC}"
            else
                cp -r "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Copied voice-${voice_name}${NC}"
            fi
        fi
    done
fi

generate_installed_skill_index "$CLAUDE_DIR" "Claude"

# Install git post-merge hook for automatic sync on git pull
echo ""
echo -e "${YELLOW}Installing post-merge git hook...${NC}"
install_git_hook

echo ""
if [ "$MIRROR_CODEX" = true ]; then
    echo -e "${YELLOW}Syncing Codex skills mirror...${NC}"
    CODEX_ENTRY_COUNT=0
    for item in "${SCRIPT_DIR}/skills/"*; do
        [ -e "$item" ] || continue
        if [ -d "$item" ] && [ -f "$item/SKILL.md" ] && _profile_disabled skills "$(basename "$item")"; then
            echo -e "${YELLOW}  Skipping $(basename "$item") (not selected)${NC}"
            continue
        fi
        target="${CODEX_SKILLS_DIR}/$(basename "$item")"
        sync_codex_entry "$item" "$target"
        CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
    done

    # Public skills live under category directories in the repository. Codex
    # scans its skills root, so mirror each nested skill by its stable name.
    while IFS= read -r skill_file; do
        skill_src=$(dirname "$skill_file")
        skill_name=$(basename "$skill_src")
        if _profile_disabled skills "$skill_name"; then
            continue
        fi
        sync_codex_entry "$skill_src" "${CODEX_SKILLS_DIR}/${skill_name}"
        CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
    done < <(find "${SCRIPT_DIR}/skills" -mindepth 3 -maxdepth 3 -name SKILL.md | sort)

    if [ -d "${SCRIPT_DIR}/private-voices" ]; then
        for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
            [ -d "$voice_dir" ] || continue
            skill_src="${voice_dir}/skill"
            [ -d "$skill_src" ] || continue
            voice_name=$(basename "$voice_dir")
            if _profile_disabled skills "voice-${voice_name}"; then
                echo -e "${YELLOW}  Skipping voice-${voice_name} (not selected)${NC}"
                target="${CODEX_SKILLS_DIR}/voice-${voice_name}"
                if { [ -L "$target" ] && _symlink_points_to "$target" "$skill_src"; } || \
                   { [ -d "$target" ] && [ -L "$target/SKILL.md" ] && \
                     _symlink_points_to "$target/SKILL.md" "$skill_src/SKILL.md"; }; then
                    rm -rf "$target"
                    echo -e "${YELLOW}  Removed Codex voice-${voice_name} mirror (disabled by profile)${NC}"
                fi
                continue
            fi
            target="${CODEX_SKILLS_DIR}/voice-${voice_name}"
            sync_codex_entry "$skill_src" "$target"
            CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
        done
    fi

    if [ -d "${SCRIPT_DIR}/private-skills" ]; then
        for item in "${SCRIPT_DIR}/private-skills/"*; do
            [ -e "$item" ] || continue
            target="${CODEX_SKILLS_DIR}/$(basename "$item")"
            sync_codex_entry "$item" "$target"
            CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
        done
    fi

    generate_installed_skill_index "$CODEX_DIR" "Codex"

    echo ""
    echo -e "${YELLOW}Syncing Codex agents mirror...${NC}"
    CODEX_AGENT_COUNT=0
    for item in "${SCRIPT_DIR}/agents/"*; do
        [ -e "$item" ] || continue
        if _profile_disabled agents "$(basename "$item")"; then
            echo -e "${YELLOW}  Skipping $(basename "$item") (not selected)${NC}"
            continue
        fi
        target="${CODEX_AGENTS_DIR}/$(basename "$item")"
        sync_codex_entry "$item" "$target"
        CODEX_AGENT_COUNT=$((CODEX_AGENT_COUNT + 1))
    done

    if [ -d "${SCRIPT_DIR}/private-agents" ]; then
        for item in "${SCRIPT_DIR}/private-agents/"*; do
            [ -e "$item" ] || continue
            target="${CODEX_AGENTS_DIR}/$(basename "$item")"
            sync_codex_entry "$item" "$target"
            CODEX_AGENT_COUNT=$((CODEX_AGENT_COUNT + 1))
        done
    fi

    generate_installed_agent_index "$CODEX_DIR" "Codex"

    # Sync Codex hooks mirror (ADR-182)
    echo ""
    echo -e "${YELLOW}Syncing Codex hooks mirror...${NC}"
    CODEX_HOOK_COUNT=0
    CODEX_HOOKS_ALLOWLIST="${SCRIPT_DIR}/scripts/codex-hooks-allowlist.txt"
    CODEX_MANAGED_HOOKS_MANIFEST="${CODEX_HOOKS_DIR}/.vexjoy-managed-hooks"

    if [ -f "$CODEX_HOOKS_ALLOWLIST" ]; then
        if clean_hooks_mirror_if_source_link "$CODEX_HOOKS_DIR" "${SCRIPT_DIR}/hooks"; then

        # Remove only files recorded by the previous VexJoy install. This
        # refreshes hooks removed from the current compatibility inventory
        # without touching user-owned files in ~/.codex/hooks.
        if [ -f "$CODEX_MANAGED_HOOKS_MANIFEST" ]; then
            while IFS= read -r managed_name || [ -n "$managed_name" ]; do
                case "$managed_name" in
                    ""|.*|*/*|*\\*) continue ;;
                esac
                managed_path="${CODEX_HOOKS_DIR}/${managed_name}"
                if [ -e "$managed_path" ] || [ -L "$managed_path" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove previously managed Codex hook: ${managed_path}${NC}"
                    else
                        rm -f "$managed_path"
                    fi
                fi
            done < "$CODEX_MANAGED_HOOKS_MANIFEST"
        fi

        # Ensure hooks directory exists
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would create: ${CODEX_HOOKS_DIR}${NC}"
        else
            mkdir -p "$CODEX_HOOKS_DIR"
        fi

        CODEX_MANAGED_NAMES="codex-hook-adapter.py"

        # Deploy the adapter before hooks.json can reference it. Codex runs all
        # mirrored hooks through this compatibility boundary.
        CODEX_ADAPTER_SOURCE="${SCRIPT_DIR}/hooks/codex-hook-adapter.py"
        if [ -f "$CODEX_ADAPTER_SOURCE" ]; then
            sync_codex_entry "$CODEX_ADAPTER_SOURCE" "${CODEX_HOOKS_DIR}/codex-hook-adapter.py"
        else
            echo -e "${RED}  ✗ Codex hook adapter missing: ${CODEX_ADAPTER_SOURCE}${NC}"
        fi

        # Parse allowlist and mirror each allowlisted hook file.
        # Format per line: EVENT:filename [key=value compatibility metadata]
        # Comments (#) and blank lines are ignored.
        while IFS= read -r line || [ -n "$line" ]; do
            # Strip leading/trailing whitespace for the blank check.
            trimmed="${line#"${line%%[![:space:]]*}"}"
            trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
            [ -z "$trimmed" ] && continue
            [ "${trimmed#\#}" != "$trimmed" ] && continue

            # Extract filename: everything between the first colon and the first space (or EOL)
            rest="${trimmed#*:}"
            filename="${rest%% *}"

            if _profile_disabled hooks "$filename"; then
                echo -e "${YELLOW}  Skipping ${filename} (not selected)${NC}"
                continue
            fi

            source_file="${SCRIPT_DIR}/hooks/${filename}"
            if [ ! -f "$source_file" ]; then
                echo -e "${RED}  ✗ Allowlisted hook missing: ${filename}${NC}"
                continue
            fi

            target_file="${CODEX_HOOKS_DIR}/${filename}"
            sync_codex_entry "$source_file" "$target_file"
            CODEX_HOOK_COUNT=$((CODEX_HOOK_COUNT + 1))
            CODEX_MANAGED_NAMES="${CODEX_MANAGED_NAMES}
${filename}"
        done < "$CODEX_HOOKS_ALLOWLIST"

        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would write managed-hook manifest: ${CODEX_MANAGED_HOOKS_MANIFEST}${NC}"
        else
            printf '%s\n' "$CODEX_MANAGED_NAMES" | sed '/^$/d' | sort -u > "$CODEX_MANAGED_HOOKS_MANIFEST"
        fi

        # Also mirror the hooks/lib directory so intra-hook imports resolve
        # (hook_utils, injection_patterns, stdin_timeout, usage_db, etc.).
        if [ -d "${SCRIPT_DIR}/hooks/lib" ]; then
            lib_target="${CODEX_HOOKS_DIR}/lib"
            sync_codex_entry "${SCRIPT_DIR}/hooks/lib" "$lib_target"
        fi

        # Generate hooks.json via the dedicated script.
        CODEX_HOOKS_JSON="${CODEX_DIR}/hooks.json"
        if [ -f "$CODEX_HOOKS_JSON" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would back up existing ${CODEX_HOOKS_JSON} before replacement${NC}"
            else
                echo -e "${BLUE}  Will back up existing ${CODEX_HOOKS_JSON} before replacement${NC}"
            fi
        fi
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would generate: ${CODEX_HOOKS_JSON}${NC}"
            echo -e "${BLUE}  Changed Codex hook definitions are skipped until they are reviewed and trusted with /hooks${NC}"
        else
            # Profile filtering: generate from a filtered allowlist copy so
            # hooks.json never references hooks we did not mirror.
            EFFECTIVE_ALLOWLIST="$CODEX_HOOKS_ALLOWLIST"
            if [ -n "$DISABLED_HOOKS" ]; then
                EFFECTIVE_ALLOWLIST=$(mktemp)
                printf '%s\n' "$DISABLED_HOOKS" | $PYTHON_CMD "${SCRIPT_DIR}/scripts/filter-codex-allowlist.py" \
                    --input "$CODEX_HOOKS_ALLOWLIST" --disabled /dev/stdin --output "$EFFECTIVE_ALLOWLIST"
            fi
            if $PYTHON_CMD "${SCRIPT_DIR}/scripts/generate-codex-hooks-json.py" \
                --allowlist "$EFFECTIVE_ALLOWLIST" \
                --output "$CODEX_HOOKS_JSON" \
                --codex-hooks-dir "$CODEX_HOOKS_DIR" 2>&1; then
                echo -e "${GREEN}  ✓ Generated ${CODEX_HOOKS_JSON}${NC}"
                echo -e "${YELLOW}  ⚠ New or changed Codex hook definitions are skipped until you review and trust them with /hooks.${NC}"
            else
                echo -e "${RED}  ✗ Failed to generate hooks.json${NC}"
            fi
            if [ "$EFFECTIVE_ALLOWLIST" != "$CODEX_HOOKS_ALLOWLIST" ]; then
                rm -f "$EFFECTIVE_ALLOWLIST"
            fi
        fi

        # Ensure hooks and explicit MultiAgent V2 routing are enabled in Codex.
        CODEX_CONFIG="${CODEX_DIR}/config.toml"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would ensure ${CODEX_CONFIG} has hooks and explicit subagent routing${NC}"
        else
            codex_flag_action=$($PYTHON_CMD "${SCRIPT_DIR}/scripts/ensure-codex-feature-flag.py" \
                --config "$CODEX_CONFIG" 2>&1)
            codex_flag_status=$?
            if [ "$codex_flag_status" -eq 0 ]; then
                echo -e "${GREEN}  ✓ Codex config features: ${codex_flag_action}${NC}"
            else
                echo "$codex_flag_action"
                echo -e "${YELLOW}  ⚠ Could not update ${CODEX_CONFIG} (see error above). Codex hooks may not activate.${NC}"
            fi
        fi

        # Current parity was verified on Codex CLI v0.144.1. The old v0.114
        # floor supported ADR-182's six-hook subset, not apply_patch parity.
        if command -v codex >/dev/null 2>&1; then
            cx_ver=$(codex --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            if [ -n "$cx_ver" ]; then
                min_major=0; min_minor=144; min_patch=1
                IFS='.' read -r cx_maj cx_min cx_pat <<< "$cx_ver"
                if [ "$cx_maj" -lt "$min_major" ] || \
                   { [ "$cx_maj" -eq "$min_major" ] && [ "$cx_min" -lt "$min_minor" ]; } || \
                   { [ "$cx_maj" -eq "$min_major" ] && [ "$cx_min" -eq "$min_minor" ] && [ "$cx_pat" -lt "$min_patch" ]; }; then
                    echo -e "${YELLOW}  ⚠ Codex CLI version ${cx_ver} is below 0.144.1. Current hook parity may not work.${NC}"
                fi
            fi
        else
            echo -e "${BLUE}  (codex CLI not installed; hooks will activate when Codex is installed)${NC}"
        fi
        else
            echo -e "${YELLOW}  ⚠ Codex hooks mirror left unchanged because its target could not be verified.${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠ Codex hooks allowlist not found at ${CODEX_HOOKS_ALLOWLIST}; skipping hooks mirror${NC}"
    fi

    echo ""
    echo -e "${YELLOW}Syncing Codex scripts mirror...${NC}"
    if [ -d "${SCRIPT_DIR}/scripts" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would mirror scripts to: ${CODEX_SCRIPTS_DIR}${NC}"
        else
            mkdir -p "$CODEX_SCRIPTS_DIR"
        fi
        sync_codex_entry "${SCRIPT_DIR}/scripts" "$CODEX_SCRIPTS_DIR"
        CODEX_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | wc -l)
        echo -e "${GREEN}  ✓ Scripts mirrored to ${CODEX_SCRIPTS_DIR}${NC}"
    else
        CODEX_SCRIPT_COUNT=0
    fi
else
    echo ""
    echo -e "${BLUE}Skipping Codex mirror sync (codex not detected: no command, no ~/.codex).${NC}"
    CODEX_ENTRY_COUNT=0
    CODEX_AGENT_COUNT=0
    CODEX_HOOK_COUNT=0
    CODEX_SCRIPT_COUNT=0
fi

echo ""
if [ "$MIRROR_FACTORY" = true ]; then
    echo -e "${YELLOW}Installing Factory components (mode: ${MODE})...${NC}"
# Factory uses the same top-level symlink/copy pattern as Claude.
# Only difference: 'agents' is named 'droids' under ~/.factory.
for component in agents skills hooks commands scripts; do
    if [ -d "${SCRIPT_DIR}/${component}" ]; then
        target_name="$component"
        [ "$component" = "agents" ] && target_name="droids"
        # Skills get the same nested layout as Claude/Codex.
        if [ "$component" = "skills" ] && [ "$MODE" = "symlink" ] && \
           [ "$CONFLICT_MODE" != "replace" ] && [ "$CONFLICT_MODE" != "skip" ]; then
            link_skills_nested "${SCRIPT_DIR}/skills" "${FACTORY_SKILLS_DIR}"
        else
            install_component "$component" "$FACTORY_DIR" "$target_name"
        fi
    fi
done

# Install private Factory components (mirrors Claude private overlay logic)
for private_dir in private-agents private-skills private-hooks; do
    public_name="${private_dir#private-}"
    [ "$public_name" = "agents" ] && public_name="droids"
    if [ -d "${SCRIPT_DIR}/${private_dir}" ]; then
        echo ""
        echo -e "${YELLOW}Installing Factory private ${public_name}...${NC}"
        for item in "${SCRIPT_DIR}/${private_dir}/"*; do
            [ -e "$item" ] || continue
            item_name=$(basename "$item")
            target="${FACTORY_DIR}/${public_name}/${item_name}"
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would install Factory private: ${item_name}${NC}"
            else
                rm -rf "$target" 2>/dev/null
                if [ "$MODE" = "symlink" ]; then
                    ln -sf "$item" "$target"
                    echo -e "${GREEN}  ✓ Linked Factory private ${item_name}${NC}"
                else
                    cp -r "$item" "$target"
                    echo -e "${GREEN}  ✓ Copied Factory private ${item_name}${NC}"
                fi
            fi
        done
    fi
done

# Install private-voices into Factory skills (goes through symlink into repo/skills/)
if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    echo ""
    echo -e "${YELLOW}Installing Factory private voices...${NC}"
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${FACTORY_DIR}/skills/voice-${voice_name}"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would install Factory voice: voice-${voice_name}${NC}"
        else
            rm -rf "$target" 2>/dev/null
            if [ "$MODE" = "symlink" ]; then
                ln -sf "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Linked Factory voice-${voice_name}${NC}"
            else
                cp -r "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Copied Factory voice-${voice_name}${NC}"
            fi
        fi
    done
fi

generate_installed_skill_index "$FACTORY_DIR" "Factory"

# Component counts for the install summary (count source dirs, not per-entry)
FACTORY_SKILL_COUNT=$(ls -1 "${SCRIPT_DIR}/skills/"*/SKILL.md 2>/dev/null | wc -l)
FACTORY_DROID_COUNT=$(ls -1 "${SCRIPT_DIR}/agents/"*.md 2>/dev/null | grep -v README | wc -l)
FACTORY_HOOK_COUNT=$(ls -1 "${SCRIPT_DIR}/hooks/"*.py 2>/dev/null | grep -cv '__init__')

# Generate ~/.factory/settings.json
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would sync hooks from ${SCRIPT_DIR}/.claude/settings.json to ${FACTORY_DIR}/settings.json (with path rewrite)${NC}"
elif [ -f "${SCRIPT_DIR}/.claude/settings.json" ]; then
    FACTORY_SETTINGS="${FACTORY_DIR}/settings.json"
    if [ ! -f "$FACTORY_SETTINGS" ]; then
        echo '{}' > "$FACTORY_SETTINGS"
    fi
    BACKUP_TS=$(date +%Y%m%d-%H%M%S)
    cp "$FACTORY_SETTINGS" "${FACTORY_SETTINGS}.backup.${BACKUP_TS}"
    $PYTHON_CMD -c "
import json, os
repo = json.load(open('${SCRIPT_DIR}/.claude/settings.json'))
dst = '${FACTORY_SETTINGS}'
try:
    merged = json.load(open(dst, encoding='utf-8'))
except (FileNotFoundError, json.JSONDecodeError):
    merged = {}
hooks_json = json.dumps(repo.get('hooks', {}))
hooks_json = hooks_json.replace('\$HOME/.claude/', '\$HOME/.factory/')
hooks_json = hooks_json.replace('\${HOME}/.claude/', '\${HOME}/.factory/')
merged['hooks'] = json.loads(hooks_json)
merged.setdefault('attribution', repo.get('attribution', {'commit': '', 'pr': ''}))
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(merged, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
print('  Factory hooks configured from .claude/settings.json')
"
else
    echo -e "${YELLOW}  Warning: ${SCRIPT_DIR}/.claude/settings.json not found, skipping Factory hook sync${NC}"
fi


else
    echo ""
    echo -e "${BLUE}Skipping Factory mirror sync (factory not detected: no command, no ~/.factory).${NC}"
    FACTORY_SKILL_COUNT=0
    FACTORY_DROID_COUNT=0
    FACTORY_HOOK_COUNT=0
fi

if [ "$MIRROR_HERMES" = true ]; then
echo ""
echo -e "${YELLOW}Syncing Hermes skills mirror...${NC}"
HERMES_ENTRY_COUNT=0
for item in "${SCRIPT_DIR}/skills/"*; do
    [ -e "$item" ] || continue
    if [ -d "$item" ] && [ -f "$item/SKILL.md" ] && _profile_disabled skills "$(basename "$item")"; then
        echo -e "${YELLOW}  Skipping $(basename "$item") (not selected)${NC}"
        continue
    fi
    target="${HERMES_SKILLS_DIR}/$(basename "$item")"
    sync_mirror_entry "$item" "$target" "Hermes"
    HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
done

# Hermes also scans one level deep, so mirror category skills by stable name.
while IFS= read -r skill_file; do
    skill_src=$(dirname "$skill_file")
    skill_name=$(basename "$skill_src")
    if _profile_disabled skills "$skill_name"; then
        continue
    fi
    sync_mirror_entry "$skill_src" "${HERMES_SKILLS_DIR}/${skill_name}" "Hermes"
    HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
done < <(find "${SCRIPT_DIR}/skills" -mindepth 3 -maxdepth 3 -name SKILL.md | sort)

if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${HERMES_SKILLS_DIR}/voice-${voice_name}"
        sync_mirror_entry "$skill_src" "$target" "Hermes"
        HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
    done
fi

if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    for item in "${SCRIPT_DIR}/private-skills/"*; do
        [ -e "$item" ] || continue
        target="${HERMES_SKILLS_DIR}/$(basename "$item")"
        sync_mirror_entry "$item" "$target" "Hermes"
        HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
    done
fi

generate_installed_skill_index "$HERMES_DIR" "Hermes"

echo ""
echo -e "${YELLOW}Syncing Hermes scripts mirror...${NC}"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror scripts to: ${HERMES_SCRIPTS_DIR}${NC}"
    else
        mkdir -p "$HERMES_SCRIPTS_DIR"
    fi
    sync_mirror_entry "${SCRIPT_DIR}/scripts" "$HERMES_SCRIPTS_DIR" "Hermes"
    HERMES_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Scripts mirrored to ${HERMES_SCRIPTS_DIR}${NC}"
else
    HERMES_SCRIPT_COUNT=0
fi
else
    echo ""
    echo -e "${BLUE}Skipping Hermes mirror sync (hermes not detected: no command, no ~/.hermes).${NC}"
    HERMES_ENTRY_COUNT=0
    HERMES_SCRIPT_COUNT=0
fi

if [ "$MIRROR_REASONIX" = true ]; then
# ── Reasonix mirror (skills + scripts + hooks; Claude-Code-compatible extension layer) ──
# Reasonix natively reads ~/.reasonix/skills, shells out to scripts via the SDIR chain,
# and runs hooks declared in ~/.reasonix/settings.json (hooks key only; MCP/model/permissions
# live in user-owned ~/.reasonix/config.json, which we never touch).
#
# Reasonix scans skill roots EXACTLY ONE LEVEL DEEP (src/skills.ts): a dir entry <X> is a
# skill only when <X>/SKILL.md exists, and it never recurses. vexjoy skills live at
# skills/<category>/<name>/SKILL.md (two levels), so we FLATTEN every skill to
# ~/.reasonix/skills/<name>/SKILL.md (one level deep). Each entry is a per-entry symlink
# in --symlink mode (Reasonix v0.52+ follows symlinked skill dirs) and a real-dir copy in
# --copy mode.
echo ""
echo -e "${YELLOW}Syncing Reasonix skills mirror (flatten + per-entry symlink/copy)...${NC}"
REASONIX_ENTRY_COUNT=0
REASONIX_SEEN_NAMES=" "  # space-delimited set of flat names claimed this run (collision guard)
if [ "$DRY_RUN" != true ]; then
    mkdir -p "$REASONIX_SKILLS_DIR"
    # Sweep broken symlinks before installing. A symlink whose target vanished is stale
    # toolkit output: a skill removed/renamed in the repo, or mode-switch residue (a prior
    # --symlink install whose source moved, now re-running --copy). reasonix_install_skill
    # only refreshes entries for skills that STILL exist, so dead links would otherwise
    # linger until uninstall. Healthy symlinks (valid --symlink install) and user-added
    # real dirs are left untouched. Matches the uninstall sweep below.
    find "$REASONIX_SKILLS_DIR" -maxdepth 1 -mindepth 1 -type l ! -exec test -e {} \; -delete 2>/dev/null || true
fi

reasonix_install_skill() {
    # $1 = skill source dir (the dir containing SKILL.md); $2 = flat skill name
    local skill_dir=$1
    local name=$2
    local target="${REASONIX_SKILLS_DIR}/${name}"

    # Within-run collision guard: basenames are verified unique, but never clobber a name
    # already claimed by this run. (A target left from a PRIOR run is refreshed below.)
    case "$REASONIX_SEEN_NAMES" in
        *" ${name} "*)
            echo -e "${YELLOW}  Warning: duplicate Reasonix skill name '${name}', skipping ${skill_dir}${NC}"
            return 0
            ;;
    esac
    REASONIX_SEEN_NAMES="${REASONIX_SEEN_NAMES}${name} "

    if [ "$DRY_RUN" = true ]; then
        if [ "$MODE" = "symlink" ]; then
            echo -e "${BLUE}  Would symlink Reasonix skill: ${skill_dir} -> ${target}/${NC}"
        else
            echo -e "${BLUE}  Would copy Reasonix skill: ${skill_dir} -> ${target}/${NC}"
        fi
    else
        rm -rf "$target"            # idempotent re-run: refresh content like the other mirrors
        if [ "$MODE" = "symlink" ]; then
            ln -s "$skill_dir" "$target"
            echo -e "${GREEN}  ✓ Reasonix symlinked ${name}${NC}"
        else
            mkdir -p "$target"
            cp -r "${skill_dir}/." "$target/"
            echo -e "${GREEN}  ✓ Reasonix copied ${name}${NC}"
        fi
    fi
    REASONIX_ENTRY_COUNT=$((REASONIX_ENTRY_COUNT + 1))
}

# Private skills FIRST so they claim canonical names; matching public-skill names then
# trip the within-run collision guard and yield to the private override (parity with the
# Claude install: private overrides public).
if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    while IFS= read -r skill_md; do
        [ -n "$skill_md" ] || continue
        skill_dir=$(dirname "$skill_md")
        reasonix_install_skill "$skill_dir" "$(basename "$skill_dir")"
    done < <(find "${SCRIPT_DIR}/private-skills" -name SKILL.md | sort)
fi

# Voice skills: private-voices/<name>/skill/SKILL.md -> ~/.reasonix/skills/voice-<name>/
if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -f "${skill_src}/SKILL.md" ] || continue
        voice_name=$(basename "$voice_dir")
        reasonix_install_skill "$skill_src" "voice-${voice_name}"
    done
fi

# Public skills last: same-name entries are skipped by the collision guard (private wins).
while IFS= read -r skill_md; do
    [ -n "$skill_md" ] || continue
    skill_dir=$(dirname "$skill_md")
    if _profile_disabled skills "$(basename "$skill_dir")"; then
        echo -e "${YELLOW}  Skipping $(basename "$skill_dir") (not selected)${NC}"
        continue
    fi
    reasonix_install_skill "$skill_dir" "$(basename "$skill_dir")"
done < <(find "${SCRIPT_DIR}/skills" -name SKILL.md | sort)

# Support dirs (no SKILL.md anywhere — e.g. shared-patterns, kb): copy as real top-level
# dirs so flattened skills' sibling references like ../shared-patterns/*.md resolve, and so
# the downstream voice shared-references deploy (which targets ${REASONIX_SKILLS_DIR}/shared-patterns)
# keeps working. These are not skills (reasonix ignores them: no SKILL.md) so they are not counted.
for support_dir in "${SCRIPT_DIR}/skills/"*/; do
    [ -d "$support_dir" ] || continue
    [ -z "$(find "$support_dir" -name SKILL.md -print -quit)" ] || continue  # skip dirs that hold skills
    support_name=$(basename "$support_dir")
    support_target="${REASONIX_SKILLS_DIR}/${support_name}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would copy Reasonix support dir: ${support_dir} -> ${support_target}/${NC}"
    else
        rm -rf "$support_target"
        cp -r "$support_dir" "$support_target"
        echo -e "${GREEN}  ✓ Reasonix copied support dir ${support_name}${NC}"
    fi
done

generate_installed_skill_index "$REASONIX_DIR" "Reasonix" true

echo ""
echo -e "${YELLOW}Syncing Reasonix scripts mirror...${NC}"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror scripts to: ${REASONIX_SCRIPTS_DIR}${NC}"
    else
        mkdir -p "$REASONIX_SCRIPTS_DIR"
    fi
    sync_mirror_entry "${SCRIPT_DIR}/scripts" "$REASONIX_SCRIPTS_DIR" "Reasonix"
    REASONIX_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Scripts mirrored to ${REASONIX_SCRIPTS_DIR}${NC}"
else
    REASONIX_SCRIPT_COUNT=0
fi

# Reasonix hooks mirror — allowlist-driven, like Codex.
# Mirrors only the hook files listed in the allowlist and uses an allowlist-aware generator
# to produce ~/.reasonix/settings.json in Reasonix's native flat shape.
echo ""
echo -e "${YELLOW}Syncing Reasonix hooks mirror (allowlist-driven)...${NC}"
REASONIX_HOOK_COUNT=0
REASONIX_HOOK_MISSING=0          # allowlisted hooks whose source file is absent
REASONIX_HOOK_MISSING_LIST=""    # space-delimited names, for the summary
REASONIX_HOOK_FAILED=false       # settings.json generator failed → hooks never wire in
REASONIX_HOOKS_ALLOWLIST="${SCRIPT_DIR}/scripts/reasonix-hooks-allowlist.txt"

if [ -f "$REASONIX_HOOKS_ALLOWLIST" ]; then
    if clean_hooks_mirror_if_source_link "$REASONIX_HOOKS_DIR" "${SCRIPT_DIR}/hooks"; then

    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${REASONIX_HOOKS_DIR}${NC}"
    else
        mkdir -p "$REASONIX_HOOKS_DIR"
    fi

    # Parse allowlist and mirror each allowlisted hook file.
    while IFS= read -r line || [ -n "$line" ]; do
        trimmed="${line#"${line%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue
        [ "${trimmed#\#}" != "$trimmed" ] && continue

        rest="${trimmed#*:}"
        filename="${rest%% *}"

        source_file="${SCRIPT_DIR}/hooks/${filename}"
        if [ ! -f "$source_file" ]; then
            echo -e "${RED}  ✗ Allowlisted hook missing: ${filename}${NC}"
            REASONIX_HOOK_MISSING=$((REASONIX_HOOK_MISSING + 1))
            REASONIX_HOOK_MISSING_LIST="${REASONIX_HOOK_MISSING_LIST}${filename} "
            continue
        fi

        target_file="${REASONIX_HOOKS_DIR}/${filename}"
        sync_mirror_entry "$source_file" "$target_file" "Reasonix"
        REASONIX_HOOK_COUNT=$((REASONIX_HOOK_COUNT + 1))
    done < "$REASONIX_HOOKS_ALLOWLIST"

    # Surface an incomplete mirror loudly. The generator below reads the same allowlist,
    # so it would otherwise emit settings.json entries pointing at files we did not mirror.
    if [ "$REASONIX_HOOK_MISSING" -gt 0 ]; then
        echo -e "${RED}  ⚠ ${REASONIX_HOOK_MISSING} allowlisted Reasonix hook(s) missing from hooks/: ${REASONIX_HOOK_MISSING_LIST}${NC}"
        echo -e "${RED}    Their settings.json entries will reference absent files. Fix scripts/reasonix-hooks-allowlist.txt or restore the hook.${NC}"
    fi

    # Mirror hooks/lib so intra-hook imports resolve.
    if [ -d "${SCRIPT_DIR}/hooks/lib" ]; then
        lib_target="${REASONIX_HOOKS_DIR}/lib"
        sync_mirror_entry "${SCRIPT_DIR}/hooks/lib" "$lib_target" "Reasonix"
    fi

    # Generate ~/.reasonix/settings.json from the allowlist (Reasonix-native flat shape).
    # On failure the OLD settings.json is left untouched (or none exists on a fresh install),
    # so hooks are mirrored but NEVER wired into Reasonix. Fail loud — do not let the final
    # summary report a hookless install as success.
    REASONIX_SETTINGS="${REASONIX_DIR}/settings.json"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would generate: ${REASONIX_SETTINGS}${NC}"
    else
        gen_err=$($PYTHON_CMD "${SCRIPT_DIR}/scripts/generate-reasonix-settings-hooks.py" \
            --allowlist "$REASONIX_HOOKS_ALLOWLIST" \
            --output "$REASONIX_SETTINGS" \
            --reasonix-hooks-dir "$REASONIX_HOOKS_DIR" 2>&1)
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ Generated ${REASONIX_SETTINGS}${NC}"
        else
            REASONIX_HOOK_FAILED=true
            echo -e "${RED}  ✗ Failed to generate ${REASONIX_SETTINGS} — Reasonix hooks are NOT wired in.${NC}"
            echo -e "${RED}${gen_err}${NC}"
        fi
    fi
    else
        echo -e "${YELLOW}  ⚠ Reasonix hooks mirror left unchanged because its target could not be verified.${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ Reasonix hooks allowlist not found at ${REASONIX_HOOKS_ALLOWLIST}; skipping hooks mirror${NC}"
fi

else
    echo ""
    echo -e "${BLUE}Skipping Reasonix mirror sync (reasonix not detected: no command, no ~/.reasonix).${NC}"
    REASONIX_ENTRY_COUNT=0
    REASONIX_SCRIPT_COUNT=0
    REASONIX_HOOK_COUNT=0
    REASONIX_HOOK_MISSING=0
    REASONIX_HOOK_MISSING_LIST=""
    REASONIX_HOOK_FAILED=false
fi

# Deploy private-voices shared references into skills/shared-patterns/
# These files were removed from the public repo and live in private-voices/shared-references/
# (gitignored). They must be deployed at install time into every runtime's shared-patterns dir.
if [ -d "${SCRIPT_DIR}/private-voices/shared-references" ]; then
    echo ""
    echo -e "${YELLOW}Installing voice shared references...${NC}"
    SHARED_REF_COUNT=0
    for ref_file in "${SCRIPT_DIR}/private-voices/shared-references/"*.md; do
        [ -f "$ref_file" ] || continue
        ref_name=$(basename "$ref_file")
        for target_dir in "${CLAUDE_DIR}/skills/shared-patterns" "${CODEX_SKILLS_DIR}/shared-patterns" "${FACTORY_SKILLS_DIR}/shared-patterns" "${HERMES_SKILLS_DIR}/shared-patterns" "${REASONIX_SKILLS_DIR}/shared-patterns"; do
            # Resolve symlinks so we write into the actual directory
            resolved_dir="$target_dir"
            [ -L "$target_dir" ] && resolved_dir="$(readlink -f "$target_dir")"
            if [ -d "$resolved_dir" ]; then
                target="${resolved_dir}/${ref_name}"
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would install: ${ref_name} -> ${target_dir}${NC}"
                else
                    if [ "$MODE" = "symlink" ]; then
                        ln -sf "$ref_file" "$target"
                    elif [ -e "$target" ] && [ "$ref_file" -ef "$target" ]; then
                        # A prior symlink install may already expose this exact
                        # private reference through the deployed tree. Treat it
                        # as current instead of asking cp to copy a file onto
                        # itself, which aborts a later copy-mode reinstall.
                        :
                    else
                        cp -f "$ref_file" "$target"
                    fi
                fi
            fi
        done
        SHARED_REF_COUNT=$((SHARED_REF_COUNT + 1))
    done
    if [ "$SHARED_REF_COUNT" -gt 0 ]; then
        echo -e "${GREEN}  ✓ ${SHARED_REF_COUNT} voice shared references installed${NC}"
    fi
fi

# Set up local overlay
echo ""
echo -e "${YELLOW}Setting up local overlay...${NC}"
if [ ! -d "${SCRIPT_DIR}/.local" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${SCRIPT_DIR}/.local/agents${NC}"
        echo -e "${BLUE}  Would create: ${SCRIPT_DIR}/.local/skills${NC}"
    else
        mkdir -p "${SCRIPT_DIR}/.local/agents"
        mkdir -p "${SCRIPT_DIR}/.local/skills"
    fi
fi

# Copy example overlay if .local is empty (only has .gitkeep)
if [ -d "${SCRIPT_DIR}/.local.example" ]; then
    LOCAL_FILES=$(find "${SCRIPT_DIR}/.local" -type f ! -name '.gitkeep' 2>/dev/null | wc -l)
    if [ "$LOCAL_FILES" -eq 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy overlay templates from .local.example/ to .local/${NC}"
        else
            echo "  Copying overlay templates to .local/"
            cp -r "${SCRIPT_DIR}/.local.example/"* "${SCRIPT_DIR}/.local/" 2>/dev/null || true
            echo -e "${GREEN}  ✓ Local overlay templates installed${NC}"
            echo -e "${YELLOW}  Edit files in .local/ with your personal configurations${NC}"
        fi
    else
        echo -e "${GREEN}  ✓ Local overlay already configured${NC}"
    fi
fi

# Configure hooks in settings.json
echo ""
echo -e "${YELLOW}Configuring hooks...${NC}"

SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
HOOKS_DIR="${CLAUDE_DIR}/hooks"

# Create settings.json if it doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${SETTINGS_FILE}${NC}"
    else
        echo '{}' > "$SETTINGS_FILE"
    fi
fi

# Sync hooks from repo's .claude/settings.json (authoritative source)
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would sync hooks from ${SCRIPT_DIR}/.claude/settings.json${NC}"
elif [ -f "${SCRIPT_DIR}/.claude/settings.json" ]; then
    # Create a timestamped backup before modifying
    BACKUP_TS=$(date +%Y%m%d-%H%M%S)
    cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup.${BACKUP_TS}"

    # Sync hooks and attribution from repo settings — repo is authoritative
    $PYTHON_CMD -c "
import json, os
repo = json.load(open('${SCRIPT_DIR}/.claude/settings.json'))
dst = '${SETTINGS_FILE}'
try:
    glob = json.load(open(dst, encoding='utf-8'))
except (FileNotFoundError, json.JSONDecodeError):
    glob = {}
glob['hooks'] = repo.get('hooks', {})
glob.setdefault('attribution', repo.get('attribution', {'commit': '', 'pr': ''}))
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(glob, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
print('  Hooks configured from .claude/settings.json')
"
    # Profile filtering: drop disabled hooks from the freshly synced block.
    if [ -n "$DISABLED_HOOKS" ]; then
        printf '%s\n' "$DISABLED_HOOKS" | $PYTHON_CMD "${SCRIPT_DIR}/scripts/filter-settings-hooks.py" \
            --input "$SETTINGS_FILE" --disabled /dev/stdin --output "$SETTINGS_FILE"
        echo -e "${YELLOW}  Filtered profile-disabled hooks from settings.json${NC}"
    fi
else
    echo -e "${YELLOW}  Warning: ${SCRIPT_DIR}/.claude/settings.json not found, skipping hook sync${NC}"
fi

# Install Python dependencies
echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would install: dependencies from requirements.txt${NC}"
else
    USE_BREAK_SYSTEM_PACKAGES=false
    PIP_INSTALL_ARGS=(-r "${SCRIPT_DIR}/requirements.txt" --quiet)
    if pip_supports_break_system_packages; then
        PIP_INSTALL_ARGS+=(--break-system-packages)
        USE_BREAK_SYSTEM_PACKAGES=true
        echo -e "${YELLOW}  Note: Enabling --break-system-packages because the selected pip supports it${NC}"
    fi

    # Try pip install with --user fallback
    if "${PIP_CMD[@]}" install "${PIP_INSTALL_ARGS[@]}" 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    elif "${PIP_CMD[@]}" install "${PIP_INSTALL_ARGS[@]}" --user 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed (user mode)${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not auto-install Python dependencies${NC}"
        print_manual_pip_command "$USE_BREAK_SYSTEM_PACKAGES"
    fi
fi

# Set permissions
echo ""
echo -e "${YELLOW}Setting permissions...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would set 644 on docs/*.md${NC}"
    echo -e "${BLUE}  Would set 755 on mirrored hooks/scripts *.py under runtime directories${NC}"
    echo -e "${BLUE}    - ~/.claude/hooks, ~/.claude/scripts${NC}"
    if [ "$MIRROR_CODEX" = true ]; then
        echo -e "${BLUE}    - ~/.codex/hooks, ~/.codex/scripts${NC}"
    else
        echo -e "${BLUE}    - ~/.codex skipped (codex not detected: no command, no ~/.codex)${NC}"
    fi
    if [ "$MIRROR_FACTORY" = true ]; then
        echo -e "${BLUE}    - ~/.factory/hooks, ~/.factory/scripts${NC}"
    else
        echo -e "${BLUE}    - ~/.factory skipped (factory not detected: no command, no ~/.factory)${NC}"
    fi
    if [ "$MIRROR_HERMES" = true ]; then
        echo -e "${BLUE}    - ~/.hermes/scripts${NC}"
    else
        echo -e "${BLUE}    - ~/.hermes skipped (hermes not detected: no command, no ~/.hermes)${NC}"
    fi
    if [ "$MIRROR_REASONIX" = true ]; then
        echo -e "${BLUE}    - ~/.reasonix/hooks, ~/.reasonix/scripts${NC}"
    else
        echo -e "${BLUE}    - ~/.reasonix skipped (reasonix not detected: no command, no ~/.reasonix)${NC}"
    fi
    echo -e "${BLUE}  Would set 600 on ~/.claude/settings.json${NC}"
    echo -e "${BLUE}  Would set 700 on ~/.claude/ and ~/.claude/learning/${NC}"
    echo -e "${BLUE}  Would set 600 on ~/.claude/history.jsonl (if it exists)${NC}"
    if [ "$MIRROR_FACTORY" = true ]; then
        echo -e "${BLUE}  Would set 600 on ~/.factory/settings.json${NC}"
    fi
    if [ "$MIRROR_REASONIX" = true ]; then
        echo -e "${BLUE}  Would set 600 on ~/.reasonix/settings.json${NC}"
    fi
else
    set_mirror_python_permissions() {
        local target_dir="$1"
        local path
        [ -d "$target_dir" ] || return 0
        while IFS= read -r -d '' path; do
            chmod 755 "$path" 2>/dev/null || true
        done < <(find "$target_dir" -type f -name "*.py" -print0 2>/dev/null)
    }

    # NOTE: Mirror-runtime paths only to avoid mutating checked-out sources.
    set_mirror_python_permissions "$CLAUDE_DIR/hooks"
    set_mirror_python_permissions "$CLAUDE_DIR/scripts"
    [ "$MIRROR_CODEX" = true ] && set_mirror_python_permissions "$CODEX_HOOKS_DIR"
    [ "$MIRROR_CODEX" = true ] && set_mirror_python_permissions "$CODEX_SCRIPTS_DIR"
    [ "$MIRROR_FACTORY" = true ] && set_mirror_python_permissions "$FACTORY_HOOKS_DIR"
    [ "$MIRROR_FACTORY" = true ] && set_mirror_python_permissions "$FACTORY_SCRIPTS_DIR"
    [ "$MIRROR_HERMES" = true ] && set_mirror_python_permissions "$HERMES_SCRIPTS_DIR"
    [ "$MIRROR_REASONIX" = true ] && set_mirror_python_permissions "$REASONIX_HOOKS_DIR"
    [ "$MIRROR_REASONIX" = true ] && set_mirror_python_permissions "$REASONIX_SCRIPTS_DIR"

    chmod 644 "${SCRIPT_DIR}/docs/"*.md 2>/dev/null || true
    # Harden ~/.claude/ sensitive files (ADR-122)
    chmod 700 "${CLAUDE_DIR}" 2>/dev/null || true
    chmod 600 "${SETTINGS_FILE}" 2>/dev/null || true
    chmod 600 "$(ls -1t "${SETTINGS_FILE}.backup."* 2>/dev/null | head -1)" 2>/dev/null || true
    chmod 700 "${CLAUDE_DIR}/learning" 2>/dev/null || true
    chmod 600 "${CLAUDE_DIR}/history.jsonl" 2>/dev/null || true
    if [ "$MIRROR_FACTORY" = true ]; then
        chmod 600 "${FACTORY_DIR}/settings.json" 2>/dev/null || true
        chmod 600 "$(ls -1t "${FACTORY_DIR}/settings.json.backup."* 2>/dev/null | head -1)" 2>/dev/null || true
    fi
    if [ "$MIRROR_REASONIX" = true ]; then
        chmod 600 "${REASONIX_DIR}/settings.json" 2>/dev/null || true
        chmod 600 "$(ls -1t "${REASONIX_DIR}/settings.json.backup."* 2>/dev/null | head -1)" 2>/dev/null || true
    fi
fi
echo -e "${GREEN}✓ Permissions set${NC}"

# Summary
echo ""
# Regenerate INDEX.json files with private components included
echo ""
echo -e "${YELLOW}Regenerating indexes (including private components)...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would regenerate skills/INDEX.json with ${NC}"
    echo -e "${BLUE}  Would regenerate agents/INDEX.json with ${NC}"
else
    python3 "${SCRIPT_DIR}/scripts/generate-skill-index.py"  >/dev/null 2>&1 && \
        echo -e "${GREEN}  ✓ Skills index regenerated${NC}" || \
        echo -e "${YELLOW}  ⚠ Skills index generation failed (non-critical)${NC}"
    python3 "${SCRIPT_DIR}/scripts/generate-agent-index.py"  >/dev/null 2>&1 && \
        echo -e "${GREEN}  ✓ Agents index regenerated${NC}" || \
        echo -e "${YELLOW}  ⚠ Agents index generation failed (non-critical)${NC}"
fi

# Write install manifest
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would write: ${CLAUDE_DIR}/.install-manifest.json${NC}"
else
    VEXJOY_MANIFEST_DISABLED_SKILLS="$DISABLED_SKILLS" $PYTHON_CMD -c "
import json, datetime, os, subprocess, sys
try:
    commit = subprocess.check_output(['git', '-C', '${SCRIPT_DIR}', 'rev-parse', '--short', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
except Exception:
    commit = 'unknown'
manifest = {
    'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'toolkit_commit': commit,
    'toolkit_path': '${SCRIPT_DIR}',
    'mode': '${MODE}',
    'components': ['agents', 'skills', 'hooks', 'commands', 'scripts'],
    'codex_components': ['skills', 'agents', 'hooks', 'scripts'],
    'factory_components': ['skills', 'droids', 'hooks'],
    'hermes_components': ['skills', 'scripts'],
    'reasonix_components': ['skills', 'scripts', 'hooks'],
    'reasonix_hooks_allowlist': 'scripts/reasonix-hooks-allowlist.txt',
    'disabled_skills': [name for name in os.environ.get('VEXJOY_MANIFEST_DISABLED_SKILLS', '').splitlines() if name],
}
json.dump(manifest, open('${CLAUDE_DIR}/.install-manifest.json', 'w'), indent=2)
print('  Install manifest written to ~/.claude/.install-manifest.json')
" && echo -e "${GREEN}  ✓ Install manifest written${NC}" || echo -e "${YELLOW}  ⚠ Install manifest write failed (non-critical)${NC}"
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                       Dry Run Complete!                        ║${NC}"
    echo -e "${YELLOW}║           Re-run without --dry-run to apply changes            ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                     Installation Complete!                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
fi
# Count components dynamically (excluding README files)
AGENT_COUNT=$(ls -1 "${SCRIPT_DIR}/agents/"*.md 2>/dev/null | grep -v README | wc -l)
SKILL_COUNT=$(ls -1 "${CLAUDE_DIR}/skills/"*/SKILL.md 2>/dev/null | wc -l)
HOOK_COUNT=$(ls -1 "${SCRIPT_DIR}/hooks/"*.py 2>/dev/null | wc -l)
COMMAND_COUNT=$(ls -1 "${SCRIPT_DIR}/commands/"*.md 2>/dev/null | grep -v README | wc -l)
SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | wc -l)
INVOCABLE_COUNT=$(grep -l 'user-invocable: true' "${CLAUDE_DIR}/skills/"*/SKILL.md 2>/dev/null | wc -l)

echo ""
echo "Installed components:"
echo "  • Agents: ${AGENT_COUNT} specialized domain experts"
echo "  • Skills: ${SKILL_COUNT} workflow methodologies (${INVOCABLE_COUNT} user-invocable)"
if [ "$MIRROR_CODEX" = true ]; then
    echo "  • Codex skills: ${CODEX_ENTRY_COUNT} mirrored entries in ~/.codex/skills"
    echo "  • Codex agents: ${CODEX_AGENT_COUNT} mirrored entries in ~/.codex/agents"
    echo "  • Codex hooks: ${CODEX_HOOK_COUNT} mirrored entries in ~/.codex/hooks"
    echo "  • Codex scripts: ${CODEX_SCRIPT_COUNT} mirrored scripts in ~/.codex/scripts"
else
    echo "  • Codex: skipped (codex not detected: no command, no ~/.codex)"
fi
if [ "$MIRROR_FACTORY" = true ]; then
    echo "  • Factory skills: ${FACTORY_SKILL_COUNT} mirrored entries in ~/.factory/skills"
    echo "  • Factory droids: ${FACTORY_DROID_COUNT} mirrored entries in ~/.factory/droids"
    echo "  • Factory hooks: ${FACTORY_HOOK_COUNT} mirrored entries in ~/.factory/hooks"
else
    echo "  • Factory: skipped (factory not detected: no command, no ~/.factory)"
fi
if [ "$MIRROR_HERMES" = true ]; then
    echo "  • Hermes skills: ${HERMES_ENTRY_COUNT} mirrored entries in ~/.hermes/skills"
    echo "  • Hermes scripts: ${HERMES_SCRIPT_COUNT} mirrored scripts in ~/.hermes/scripts"
else
    echo "  • Hermes: skipped (hermes not detected: no command, no ~/.hermes)"
fi
if [ "$MIRROR_REASONIX" = true ]; then
    echo "  • Reasonix skills: ${REASONIX_ENTRY_COUNT} flattened skills (per-entry symlink in --symlink mode, copy in --copy mode) in ~/.reasonix/skills"
    echo "  • Reasonix scripts: ${REASONIX_SCRIPT_COUNT} mirrored scripts in ~/.reasonix/scripts"
    echo "  • Reasonix hooks: ${REASONIX_HOOK_COUNT} mirrored entries in ~/.reasonix/hooks"
else
    echo "  • Reasonix: skipped (reasonix not detected: no command, no ~/.reasonix)"
fi
if [ "$REASONIX_HOOK_FAILED" = true ]; then
    echo -e "${RED}  • FAILED: ~/.reasonix/settings.json was not generated — Reasonix hooks (gates + observers) will NOT fire. See the error above.${NC}"
fi
if [ "${REASONIX_HOOK_MISSING:-0}" -gt 0 ]; then
    echo -e "${RED}  • WARNING: ${REASONIX_HOOK_MISSING} allowlisted Reasonix hook(s) were missing and not mirrored: ${REASONIX_HOOK_MISSING_LIST}${NC}"
fi
echo "  • Hooks: ${HOOK_COUNT} automation hooks"
echo "  • Commands: ${COMMAND_COUNT} slash commands"
echo "  • Scripts: ${SCRIPT_COUNT} utility scripts"
echo ""
echo "Next steps:"
echo "  1. Customize .local/ with your personal configurations"
echo "  2. Run 'claude' in any project directory"
echo "  3. Open any project and run: claude"
echo "  4. Try: /do what can you do?"
echo ""
echo "Documentation:"
echo "  • Quick start: docs/QUICKSTART.md"
echo "  • Full reference: docs/REFERENCE.md"
echo "  • Voice system: docs/VOICE-SYSTEM.md"
echo ""
if [ "$MODE" = "symlink" ]; then
    echo -e "${YELLOW}Note: Using symlink mode. Run 'git pull' in this repo to update.${NC}"
else
    echo -e "${YELLOW}Note: Using copy mode. Re-run install.sh to update.${NC}"
fi
echo ""
