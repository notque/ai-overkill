"""Regression tests for hook-mirror symlink safety in install.sh."""

import os
import shlex
import shutil
import subprocess  # nosec B404 - fixed installer argv; no shell execution
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_NAME = "user-correction-capture.py"
BASH: str = shutil.which("bash") or ""

if BASH is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)

MODES = [
    pytest.param(["--copy", "--force"], None, False, id="copy"),
    pytest.param(["--symlink", "--force"], "2\n", True, id="symlink"),
    pytest.param(["--symlink", "--per-item", "--force"], None, True, id="symlink-per-item"),
]


@pytest.fixture
def installer_tree(tmp_path: Path) -> Path:
    """Build the smallest isolated source tree that exercises Reasonix hooks."""
    root = tmp_path / "repo"
    for directory in ("hooks", "scripts", "skills"):
        (root / directory).mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "install.sh", root / "install.sh")
    shutil.copy2(REPO_ROOT / "hooks" / HOOK_NAME, root / "hooks" / HOOK_NAME)
    shutil.copy2(
        REPO_ROOT / "scripts" / "generate-reasonix-settings-hooks.py",
        root / "scripts" / "generate-reasonix-settings-hooks.py",
    )
    (root / "scripts" / "reasonix-hooks-allowlist.txt").write_text(f"UserPromptSubmit:{HOOK_NAME}\n", encoding="utf-8")
    (root / "requirements.txt").write_text("", encoding="utf-8")
    return root


@pytest.fixture
def fake_python_bin(tmp_path: Path) -> Path:
    """Stub pip calls while delegating installer Python work to pytest's interpreter."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "python3"
    wrapper.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
        '  [ "$3" = "--version" ] && echo "pip test-stub"\n'
        "  exit 0\n"
        "fi\n"
        f'exec {shlex.quote(sys.executable)} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return bin_dir


def _run_install(
    root: Path,
    home: Path,
    python_bin: Path,
    args: list[str],
    stdin: str | None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{python_bin}:/usr/bin:/bin",
        "TERM": "dumb",
    }
    return subprocess.run(  # nosec B603 - fixed executable and argument list
        [BASH, str(root / "install.sh"), *args],
        cwd=root,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(("args", "stdin", "expect_link"), MODES)
def test_source_hook_link_is_replaced_without_source_damage(
    installer_tree: Path,
    fake_python_bin: Path,
    tmp_path: Path,
    args: list[str],
    stdin: str | None,
    expect_link: bool,
) -> None:
    home = tmp_path / "home"
    reasonix = home / ".reasonix"
    reasonix.mkdir(parents=True)
    hooks_dir = reasonix / "hooks"
    hooks_dir.symlink_to(installer_tree / "hooks", target_is_directory=True)
    source_hook = installer_tree / "hooks" / HOOK_NAME
    original = source_hook.read_bytes()

    for _ in range(2):
        result = _run_install(installer_tree, home, fake_python_bin, args, stdin)
        assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    installed_hook = hooks_dir / HOOK_NAME
    assert hooks_dir.is_dir() and not hooks_dir.is_symlink()
    assert source_hook.is_file() and not source_hook.is_symlink()
    assert source_hook.read_bytes() == original
    assert installed_hook.read_bytes() == original
    assert installed_hook.is_symlink() is expect_link


@pytest.mark.parametrize(("args", "stdin", "expect_link"), MODES)
def test_distinct_hook_link_and_user_files_are_preserved(
    installer_tree: Path,
    fake_python_bin: Path,
    tmp_path: Path,
    args: list[str],
    stdin: str | None,
    expect_link: bool,
) -> None:
    home = tmp_path / "home"
    reasonix = home / ".reasonix"
    external_hooks = tmp_path / "external-hooks"
    reasonix.mkdir(parents=True)
    external_hooks.mkdir()
    hooks_dir = reasonix / "hooks"
    hooks_dir.symlink_to(external_hooks, target_is_directory=True)
    sentinel = external_hooks / "user-note.txt"
    sentinel.write_text("keep me\n", encoding="utf-8")
    user_hook_source = tmp_path / "user-hook.py"
    user_hook_source.write_text("# user hook\n", encoding="utf-8")
    user_hook = external_hooks / "user-hook.py"
    user_hook.symlink_to(user_hook_source)

    result = _run_install(installer_tree, home, fake_python_bin, args, stdin)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert hooks_dir.is_symlink() and hooks_dir.resolve() == external_hooks.resolve()
    assert sentinel.read_text(encoding="utf-8") == "keep me\n"
    assert user_hook.is_symlink() and user_hook.resolve() == user_hook_source.resolve()
    installed_hook = external_hooks / HOOK_NAME
    assert installed_hook.read_bytes() == (installer_tree / "hooks" / HOOK_NAME).read_bytes()
    assert installed_hook.is_symlink() is expect_link
