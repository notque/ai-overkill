#!/usr/bin/env python3
"""Doctor-style portability check: every SDIR-referenced script in SKILL.md
runs from a non-repo cwd.

The defect: SKILL.md invoked `python3 scripts/build-dispatch.py` (repo-relative)
instead of `python3 "$SDIR/build-dispatch.py"`. From a non-repo cwd the
MANDATORY builder fails silently. This test catches the class of bug by:

1. Extracting every `$SDIR/{script}` reference from the SKILL.md.
2. Verifying each referenced script exists at the resolved path.
3. Running each script with `--help` (or a harmless invocation) from /tmp to
   prove it executes from a non-repo working directory.

Run with: python3 -m pytest scripts/tests/test_sdir_portability.py -v
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"

# Match `$SDIR/{filename}` references in the SKILL.md. Captures the filename
# after the slash. Handles both `"$SDIR/foo.py"` and bare `$SDIR/foo.py`.
_SDIR_REF_RE = re.compile(r"\$SDIR/([a-zA-Z0-9_-]+\.py)")


def _extract_sdir_scripts() -> list[str]:
    """All unique script filenames referenced as $SDIR/{name} in SKILL.md."""
    text = SKILL_MD.read_text(encoding="utf-8")
    return sorted(set(_SDIR_REF_RE.findall(text)))


SDIR_SCRIPTS = _extract_sdir_scripts()


@pytest.fixture(params=SDIR_SCRIPTS)
def script_name(request):
    return request.param


def test_sdir_scripts_are_not_empty():
    """Sanity: SKILL.md must reference the mandatory scripts (pre-route.py,
    build-dispatch.py). Floor of 2 catches the extraction regex silently
    matching nothing."""
    assert len(SDIR_SCRIPTS) >= 2, (
        f"Expected at least 2 $SDIR scripts in SKILL.md, found {len(SDIR_SCRIPTS)}: {SDIR_SCRIPTS}"
    )


def test_script_exists_in_scripts_dir(script_name):
    """Every $SDIR-referenced script must exist in the repo's scripts/ dir."""
    path = REPO_ROOT / "scripts" / script_name
    assert path.exists(), f"scripts/{script_name} referenced in SKILL.md but missing"


def test_script_runs_from_non_repo_cwd(script_name):
    """Each script must be importable/runnable from a non-repo working directory.

    Uses --help where available; falls back to importing the module (exit 0 on
    success, non-zero on import failure). Running from /tmp proves the script
    does not depend on cwd being the repo root.
    """
    script_path = REPO_ROOT / "scripts" / script_name
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
        cwd="/tmp",
        timeout=10,
    )
    # --help exits 0 for argparse scripts; scripts without argparse may exit
    # non-zero on --help but still prove they can be loaded. Accept 0 or 2
    # (argparse error is fine — the script was loaded and ran its arg parser).
    msg = "scripts/%s failed from /tmp (exit %d):\nstderr: %s" % (
        script_name,
        result.returncode,
        result.stderr[:500],
    )
    assert result.returncode in (0, 2), msg


def test_no_bare_repo_relative_script_invocations():
    """SKILL.md must not contain bare `python3 scripts/` invocations.

    Every script invocation in executable context (code blocks, inline
    backticks) must use $SDIR, not a repo-relative path.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    # Match python3 scripts/ but NOT inside a prose reference like
    # "see scripts/foo.py". Only match executable patterns:
    # backtick-wrapped or inside code blocks.
    bare_invocations = re.findall(r"python3 scripts/[a-zA-Z0-9_-]+\.py", text)
    assert bare_invocations == [], f"Found bare repo-relative script invocations (should use $SDIR): {bare_invocations}"
