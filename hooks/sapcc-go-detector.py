#!/usr/bin/env python3
# hook-version: 1.0.1
"""
SessionStart Hook: SAP Converged Cloud Go Project Detection

Detects when the working directory is an sapcc Go project and injects
the go-patterns skill context. Runs once at session start.

Detection Logic:
- Check for go.mod in CWD (searches up to 3 parent directories)
- Check if module path starts with github.com/sapcc/ or github.com/sap-cloud-infrastructure/
- Check if dependencies include key sapcc libraries (go-bits, go-api-declarations)
- Check if go.mod contains any sapcc or sap-cloud-infrastructure imports

Output Format:
- [sapcc-go] Detected SAP CC Go project: {module}
- [auto-skill] go-patterns
- Call the Skill tool with `go-patterns`.

Design Principles:
- Lightweight detection (reads go.mod only, no subprocess)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
"""

import os
import re
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error

EVENT_NAME = "SessionStart"

# Patterns that indicate an sapcc Go project
SAPCC_MODULE_PREFIXES = [
    "github.com/sapcc/",
    "github.com/sap-cloud-infrastructure/",
]
SAPCC_IMPORT_PATTERN = re.compile(r"github\.com/(sapcc|sap-cloud-infrastructure)/")

# Key sapcc libraries that trigger the skill even in non-sapcc modules
SAPCC_LIBRARIES = {
    "github.com/sapcc/go-bits",
    "github.com/sapcc/go-api-declarations",
    "github.com/sapcc/gophercloud-sapcc",
    "github.com/sap-cloud-infrastructure/go-bits",
}


def find_go_mod() -> Path | None:
    """
    Find go.mod in CWD or parent directories (up to 3 levels).

    Returns:
        Path to go.mod or None if not found
    """
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents[:3]):
        go_mod = parent / "go.mod"
        if go_mod.is_file():
            return go_mod
    return None


def detect_sapcc_project(go_mod_path: Path) -> tuple[bool, str]:
    """
    Detect if a Go project is an SAP CC project.

    Checks (in order, returns on first match):
    1. Module path starts with github.com/sapcc/ or github.com/sap-cloud-infrastructure/
    2. Dependencies include key sapcc libraries (go-bits, go-api-declarations)
    3. Any sapcc or sap-cloud-infrastructure import found in go.mod

    Returns:
        Tuple of (is_sapcc, module_name)
    """
    try:
        content = go_mod_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[sapcc-go] Warning: go.mod exists but cannot be read: {e}", file=sys.stderr)
        return False, ""

    # Extract module name
    module_match = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
    module_name = module_match.group(1) if module_match else "unknown"

    # Check 1: Module itself is sapcc or sap-cloud-infrastructure
    if any(module_name.startswith(prefix) for prefix in SAPCC_MODULE_PREFIXES):
        return True, module_name

    # Check 2: Dependencies include sapcc libraries
    for lib in SAPCC_LIBRARIES:
        if lib in content:
            return True, module_name

    # Check 3: Any sapcc import at all
    if SAPCC_IMPORT_PATTERN.search(content):
        return True, module_name

    return False, module_name


def get_sapcc_injection(module_name: str) -> str:
    """Get the context injection for SAP CC Go projects.

    Emits only tags. The go-patterns skill carries its own conventions.
    ADR hook-injection-condensation: removed conventions summary.
    """
    return (
        f"[sapcc-go] Detected SAP CC Go project: {module_name}\n"
        "[auto-skill] go-patterns\n"
        "Call the Skill tool with `go-patterns`."
    )


def main():
    """Main entry point for the hook."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        # Find go.mod
        go_mod = find_go_mod()
        if not go_mod:
            empty_output(EVENT_NAME).print_and_exit()

        # Check if it's an sapcc project
        is_sapcc, module_name = detect_sapcc_project(go_mod)

        if not is_sapcc:
            if debug:
                print(f"[sapcc-go] Not an sapcc project: {module_name}", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Log detection
        if debug:
            print(f"[sapcc-go] Detected: {module_name} (go.mod: {go_mod})", file=sys.stderr)

        # Inject sapcc context
        injection = get_sapcc_injection(module_name)
        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        hook_error("sapcc-go-detector", e)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
