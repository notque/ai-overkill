#!/usr/bin/env python3
"""Regression tests for the lint gate that catches undefined names (F821).

WHY THIS EXISTS

hooks/tests/test_adr_enforcement.py pins ONE undefined-name bug: the
``__EVENT_NAME`` / ``_EVENT_NAME`` typo that made adr-enforcement.py raise
NameError on every invocation and logged 1,795 crashes. That test pins the
specific typo and bans one specific shape (module-level ``__`` constants).

It does not pin the reason the typo survived. ``F821`` (undefined-name) — the
pyflakes rule that flags exactly this bug on sight — was listed in
pyproject.toml's global ``ignore`` as "false positives in conditional imports
and dynamic code". With the rule off, the repo's own lint gate reported "All
checks passed!" on the crashing file; with it on, that same file produces 8
F821 errors. The typo therefore shipped in the initial release and survived
until an unrelated refactor renamed the constant by accident.

The "false positives" claim was tested rather than assumed. Turning F821 on
across the whole repo produced TWO findings, and both were real latent
NameErrors, not false positives:

  * skills/meta/routing-table-updater/scripts/update_routing.py used
    ``re.match`` with no ``import re`` — NameError on every markdown table
    validated.
  * hooks/tests/test_do_routing.py registered
    ``test_routes_go_test_to_go_testing_skill``; the function is actually named
    ``..._to_go_patterns_skill`` — NameError that took the suite down.

Both are fixed. These tests keep the gate on and the repo clean, so the next
undefined name is caught by lint instead of by a hook crashing silently in its
own fail-open path.

Run with: python3 -m pytest hooks/tests/test_undefined_name_gate.py -v
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _lint_ignore_list() -> list[str]:
    with open(PYPROJECT, "rb") as f:
        config = tomllib.load(f)
    return config["tool"]["ruff"]["lint"].get("ignore", [])


def test_f821_is_not_globally_ignored() -> None:
    """F821 must stay enabled — it is the only automatic guard for this bug class.

    Fails if someone re-adds "F821" to the global ignore list. Needs no ruff
    binary, so this guard cannot be skipped away in a stripped test environment.
    """
    ignored = _lint_ignore_list()
    assert "F821" not in ignored, (
        "F821 (undefined-name) is globally ignored again. It is the rule that "
        "catches the adr-enforcement NameError class — a hook that crashes in "
        "its skip path enforces nothing, silently. Re-enable it and fix the "
        "findings instead; when this was last measured, every F821 finding in "
        "the repo was a real bug."
    )


def test_f821_is_enabled_in_the_selected_rule_set() -> None:
    """Enabling is not just absence from `ignore` — `select` must still cover F.

    Guards the other way the rule could be lost: narrowing `select` so the
    pyflakes "F" family no longer applies.
    """
    with open(PYPROJECT, "rb") as f:
        config = tomllib.load(f)
    selected = config["tool"]["ruff"]["lint"].get("select", [])
    assert any(rule == "F" or rule.startswith("F8") for rule in selected), (
        f"ruff lint.select={selected!r} no longer covers the pyflakes F family, "
        "so F821 (undefined-name) is not enforced."
    )


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_repo_has_no_undefined_names() -> None:
    """The repo must be free of undefined names under the project's own config.

    This is the test that actually failed before the fix: two real NameErrors
    were live in tracked source while the lint gate reported success.
    """
    result = subprocess.run(
        [
            "ruff",
            "check",
            ".",
            "--config",
            str(PYPROJECT),
            "--select",
            "F821",
            "--output-format",
            "concise",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    findings = [line for line in result.stdout.splitlines() if "F821" in line]
    assert not findings, "undefined names found (each is a latent NameError):\n" + "\n".join(findings)


def test_the_original_crash_would_now_be_caught(tmp_path: Path) -> None:
    """Reconstruct the adr-enforcement bug and prove the gate rejects it.

    The historical file defined ``__EVENT_NAME`` and referenced ``_EVENT_NAME``.
    Under the old config ruff passed this file; it must not pass now.
    """
    if shutil.which("ruff") is None:
        pytest.skip("ruff not installed")

    crashing = tmp_path / "hook_with_typo.py"
    crashing.write_text(
        "__EVENT_NAME = 'PostToolUse'\n\n\ndef main() -> None:\n    print(_EVENT_NAME)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["ruff", "check", str(crashing), "--config", str(PYPROJECT), "--output-format", "concise"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "F821" in result.stdout, (
        "the project lint config no longer flags the exact typo that caused "
        f"1,795 adr-enforcement crashes. ruff said:\n{result.stdout or result.stderr}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
