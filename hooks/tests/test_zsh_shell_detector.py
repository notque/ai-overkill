"""Tests for zsh-shell-detector.py."""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the modules under test
# ---------------------------------------------------------------------------

HOOKS_DIR = Path(__file__).resolve().parent.parent

_zsh_spec = importlib.util.spec_from_file_location(
    "zsh_shell_detector",
    HOOKS_DIR / "zsh-shell-detector.py",
)
zsh_mod = importlib.util.module_from_spec(_zsh_spec)
_zsh_spec.loader.exec_module(zsh_mod)

_fish_spec = importlib.util.spec_from_file_location(
    "fish_shell_detector",
    HOOKS_DIR / "fish-shell-detector.py",
)
fish_mod = importlib.util.module_from_spec(_fish_spec)
_fish_spec.loader.exec_module(fish_mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_zsh_main(shell: str = "", debug: str = "") -> tuple[int, dict | None]:
    """Invoke zsh_mod.main() with $SHELL set to the given value.

    Returns (exit_code, parsed_stdout_json).
    """
    env = {k: v for k, v in os.environ.items()}
    env["SHELL"] = shell
    if debug:
        env["CLAUDE_HOOKS_DEBUG"] = debug
    else:
        env.pop("CLAUDE_HOOKS_DEBUG", None)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, env, clear=True),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            zsh_mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    parsed = None
    if output:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            pass
    return 0, parsed


# ---------------------------------------------------------------------------
# is_zsh_shell unit tests
# ---------------------------------------------------------------------------


class TestIsZshShell:
    def test_zsh_in_shell_returns_true(self):
        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}, clear=False):
            assert zsh_mod.is_zsh_shell() is True

    def test_zsh_usr_bin_returns_true(self):
        with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}, clear=False):
            assert zsh_mod.is_zsh_shell() is True

    def test_fish_shell_returns_false(self):
        with patch.dict(os.environ, {"SHELL": "/usr/bin/fish"}, clear=False):
            assert zsh_mod.is_zsh_shell() is False

    def test_bash_shell_returns_false(self):
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}, clear=False):
            assert zsh_mod.is_zsh_shell() is False

    def test_empty_shell_returns_false(self):
        env = {k: v for k, v in os.environ.items()}
        env.pop("SHELL", None)
        with patch.dict(os.environ, env, clear=True):
            assert zsh_mod.is_zsh_shell() is False

    def test_shell_unset_returns_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert zsh_mod.is_zsh_shell() is False


# ---------------------------------------------------------------------------
# Fish false-positive regression tests
# ---------------------------------------------------------------------------


class TestFishFalsePositiveRegression:
    """Regression: fish config dir present but $SHELL=/bin/zsh must not trigger fish detection."""

    def test_zsh_shell_with_fish_config_dir_is_not_fish(self, tmp_path: Path):
        """Core regression: SHELL=zsh + ~/.config/fish/ present → fish detector returns False."""
        fish_config = tmp_path / ".config" / "fish"
        fish_config.mkdir(parents=True)

        with (
            patch.dict(os.environ, {"SHELL": "/bin/zsh"}, clear=False),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            assert fish_mod.is_fish_shell() is False

    def test_zsh_shell_with_fish_config_dir_is_zsh(self, tmp_path: Path):
        """Core regression: SHELL=zsh + ~/.config/fish/ present → zsh detector returns True."""
        fish_config = tmp_path / ".config" / "fish"
        fish_config.mkdir(parents=True)

        with (
            patch.dict(os.environ, {"SHELL": "/bin/zsh"}, clear=False),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            assert zsh_mod.is_zsh_shell() is True

    def test_bash_shell_with_fish_config_dir_is_not_fish(self, tmp_path: Path):
        """SHELL=bash + ~/.config/fish/ → fish detector returns False."""
        fish_config = tmp_path / ".config" / "fish"
        fish_config.mkdir(parents=True)

        with (
            patch.dict(os.environ, {"SHELL": "/bin/bash"}, clear=False),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            assert fish_mod.is_fish_shell() is False

    def test_no_shell_with_fish_config_dir_is_fish(self, tmp_path: Path):
        """SHELL unset + ~/.config/fish/ exists → fish fallback fires (no known non-fish shell)."""
        fish_config = tmp_path / ".config" / "fish"
        fish_config.mkdir(parents=True)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            assert fish_mod.is_fish_shell() is True

    def test_fish_shell_explicit_returns_true(self):
        """SHELL=/usr/bin/fish → fish detector still returns True."""
        with patch.dict(os.environ, {"SHELL": "/usr/bin/fish"}, clear=False):
            assert fish_mod.is_fish_shell() is True


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestZshMain:
    def test_zsh_detected_emits_context(self):
        """SHELL=/bin/zsh → main() emits additionalContext with zsh tags."""
        _, parsed = _run_zsh_main(shell="/bin/zsh")
        assert parsed is not None
        inner = parsed.get("hookSpecificOutput", {})
        ctx = inner.get("additionalContext", "")
        assert "[zsh-shell] Detected Zsh shell user" in ctx
        assert "[auto-skill] shell-config" in ctx
        assert "Call the Skill tool with `shell-config`." in ctx

    def test_non_zsh_emits_empty(self):
        """SHELL=/bin/bash → main() emits empty output (no additionalContext)."""
        _, parsed = _run_zsh_main(shell="/bin/bash")
        assert parsed is not None
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" not in inner

    def test_fish_shell_emits_empty(self):
        """SHELL=/usr/bin/fish → main() emits empty output (no additionalContext)."""
        _, parsed = _run_zsh_main(shell="/usr/bin/fish")
        assert parsed is not None
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" not in inner

    def test_empty_shell_emits_empty(self):
        """SHELL='' → main() emits empty output."""
        _, parsed = _run_zsh_main(shell="")
        assert parsed is not None
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" not in inner

    def test_exit_code_always_0(self):
        """main() always exits 0 regardless of detection result."""
        code, _ = _run_zsh_main(shell="/bin/zsh")
        assert code == 0

        code, _ = _run_zsh_main(shell="/bin/bash")
        assert code == 0

    def test_injection_format_correct(self):
        """Injected context matches exact expected format."""
        # zsh-shell-config folded into shell-config (skill consolidation).
        assert zsh_mod.get_zsh_injection() == (
            "[zsh-shell] Detected Zsh shell user\n[auto-skill] shell-config\nCall the Skill tool with `shell-config`."
        )
