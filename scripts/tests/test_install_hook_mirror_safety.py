"""Regression tests for hook-mirror symlink safety in install.sh."""

import os
import shlex
import shutil
import subprocess  # nosec B404 - fixed installer argv; no shell execution
import sys
from pathlib import Path
from typing import cast

import pytest

# Shells out to the full install.sh. Deselected from the default local run
# by the marker filter in pyproject.toml; CI still runs it via `-m ""`.
pytestmark = [pytest.mark.slow, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_NAME = "user-correction-capture.py"
BASH_PATH = shutil.which("bash")

if BASH_PATH is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)
BASH = cast(str, BASH_PATH)

MODES = [
    pytest.param(["--copy", "--force"], None, False, id="copy"),
    pytest.param(["--symlink", "--force"], "2\n", True, id="symlink"),
    pytest.param(["--symlink", "--per-item", "--force"], None, True, id="symlink-per-item"),
]


@pytest.fixture
def installer_tree(tmp_path: Path) -> Path:
    """Build the smallest isolated source tree that exercises Reasonix hooks."""
    root = tmp_path / "repo with spaces"
    for directory in ("hooks", "scripts/lib", "skills/process/quick"):
        (root / directory).mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "install.sh", root / "install.sh")
    shutil.copy2(REPO_ROOT / "hooks" / HOOK_NAME, root / "hooks" / HOOK_NAME)
    shutil.copy2(
        REPO_ROOT / "scripts" / "generate-reasonix-settings-hooks.py",
        root / "scripts" / "generate-reasonix-settings-hooks.py",
    )
    shutil.copy2(REPO_ROOT / "scripts" / "generate-agent-index.py", root / "scripts" / "generate-agent-index.py")
    shutil.copy2(REPO_ROOT / "scripts" / "generate-skill-index.py", root / "scripts" / "generate-skill-index.py")
    shutil.copy2(REPO_ROOT / "scripts" / "lib" / "frontmatter.py", root / "scripts" / "lib" / "frontmatter.py")
    shutil.copy2(REPO_ROOT / "skills" / "process" / "quick" / "SKILL.md", root / "skills/process/quick/SKILL.md")
    (root / "scripts" / "reasonix-hooks-allowlist.txt").write_text(f"UserPromptSubmit:{HOOK_NAME}\n", encoding="utf-8")
    (root / "requirements.txt").write_text("", encoding="utf-8")
    return root


def _write_python_wrapper(bin_dir: Path, name: str, canonicalization: str = "ok") -> None:
    canonicalization_case = {
        "ok": "",
        "fail": 'case "$2" in *"os.path.realpath"*) exit 9 ;; esac\n',
        "empty": 'case "$2" in *"os.path.realpath"*) exit 0 ;; esac\n',
    }[canonicalization]
    wrapper = bin_dir / name
    wrapper.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
        '  [ "$3" = "--version" ] && echo "pip test-stub"\n'
        "  exit 0\n"
        "fi\n"
        f"{canonicalization_case}"
        f'exec {shlex.quote(sys.executable)} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)


def _isolated_python_bin(tmp_path: Path, canonicalization: str = "ok") -> Path:
    """Provide installer tools with `python`, but no `python3`, on PATH."""
    bin_dir = tmp_path / f"python-only-{canonicalization}"
    bin_dir.mkdir(parents=True)
    for name in (
        "basename",
        "chmod",
        "cp",
        "cut",
        "date",
        "dirname",
        "find",
        "grep",
        "head",
        "ln",
        "ls",
        "mkdir",
        "mktemp",
        "mv",
        "readlink",
        "rm",
        "sed",
        "sort",
        "tr",
        "unlink",
        "wc",
    ):
        executable = shutil.which(name)
        assert executable is not None
        (bin_dir / name).symlink_to(executable)
    _write_python_wrapper(bin_dir, "python", canonicalization)
    return bin_dir


@pytest.fixture
def fake_python_bin(tmp_path: Path) -> Path:
    """Stub pip calls while delegating installer Python work to pytest's interpreter."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_python_wrapper(bin_dir, "python3")
    return bin_dir


def _run_install(
    root: Path,
    home: Path,
    python_bin: Path,
    args: list[str],
    stdin: str | None,
    *,
    isolated_path: bool = False,
) -> subprocess.CompletedProcess[str]:
    path = str(python_bin) if isolated_path else f"{python_bin}:/usr/bin:/bin"
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": path,
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
    home = tmp_path / "home with spaces"
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
    home = tmp_path / "home with spaces"
    reasonix = home / ".reasonix"
    external_hooks = tmp_path / "external hooks"
    reasonix.mkdir(parents=True)
    external_hooks.mkdir()
    hooks_dir = reasonix / "hooks"
    hooks_dir.symlink_to(external_hooks, target_is_directory=True)
    sentinel = external_hooks / "user-note.txt"
    sentinel.write_text("keep me\n", encoding="utf-8")
    user_hook_source = tmp_path / "user hook.py"
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


@pytest.mark.parametrize(("args", "stdin", "expect_link"), MODES)
def test_python_only_source_link_is_replaced(
    installer_tree: Path,
    tmp_path: Path,
    args: list[str],
    stdin: str | None,
    expect_link: bool,
) -> None:
    home = tmp_path / "python only home"
    reasonix = home / ".reasonix"
    reasonix.mkdir(parents=True)
    hooks_dir = reasonix / "hooks"
    hooks_dir.symlink_to(installer_tree / "hooks", target_is_directory=True)
    source_hook = installer_tree / "hooks" / HOOK_NAME
    original = source_hook.read_bytes()
    python_bin = _isolated_python_bin(tmp_path)

    result = _run_install(installer_tree, home, python_bin, args, stdin, isolated_path=True)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert hooks_dir.is_dir() and not hooks_dir.is_symlink()
    assert source_hook.read_bytes() == original
    installed_hook = hooks_dir / HOOK_NAME
    assert installed_hook.read_bytes() == original
    assert installed_hook.is_symlink() is expect_link


@pytest.mark.parametrize(("args", "stdin", "expect_link"), MODES)
@pytest.mark.parametrize("canonicalization", ["fail", "empty"])
def test_source_link_is_preserved_when_resolution_is_unknown(
    installer_tree: Path,
    tmp_path: Path,
    args: list[str],
    stdin: str | None,
    expect_link: bool,
    canonicalization: str,
) -> None:
    del expect_link
    home = tmp_path / f"{canonicalization} source home"
    reasonix = home / ".reasonix"
    reasonix.mkdir(parents=True)
    hooks_dir = reasonix / "hooks"
    hooks_dir.symlink_to(installer_tree / "hooks", target_is_directory=True)
    source_hook = installer_tree / "hooks" / HOOK_NAME
    original = source_hook.read_bytes()
    python_bin = _isolated_python_bin(tmp_path / canonicalization, canonicalization)

    result = _run_install(installer_tree, home, python_bin, args, stdin, isolated_path=True)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert hooks_dir.is_symlink() and hooks_dir.resolve() == (installer_tree / "hooks").resolve()
    assert source_hook.is_file() and not source_hook.is_symlink()
    assert source_hook.read_bytes() == original


@pytest.mark.parametrize(("args", "stdin", "expect_link"), MODES)
@pytest.mark.parametrize("canonicalization", ["ok", "fail", "empty"])
def test_python_only_external_link_is_preserved_when_resolution_is_not_proven(
    installer_tree: Path,
    tmp_path: Path,
    args: list[str],
    stdin: str | None,
    expect_link: bool,
    canonicalization: str,
) -> None:
    home = tmp_path / f"{canonicalization} home"
    reasonix = home / ".reasonix"
    external_hooks = tmp_path / f"{canonicalization} external hooks"
    reasonix.mkdir(parents=True)
    external_hooks.mkdir()
    hooks_dir = reasonix / "hooks"
    hooks_dir.symlink_to(external_hooks, target_is_directory=True)
    sentinel = external_hooks / "user note.txt"
    sentinel.write_text("keep me\n", encoding="utf-8")
    python_bin = _isolated_python_bin(tmp_path / canonicalization, canonicalization)

    result = _run_install(installer_tree, home, python_bin, args, stdin, isolated_path=True)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert hooks_dir.is_symlink() and hooks_dir.resolve() == external_hooks.resolve()
    assert sentinel.read_text(encoding="utf-8") == "keep me\n"
    installed_hook = external_hooks / HOOK_NAME
    if canonicalization == "ok":
        assert installed_hook.read_bytes() == (installer_tree / "hooks" / HOOK_NAME).read_bytes()
        assert installed_hook.is_symlink() is expect_link
    else:
        assert not installed_hook.exists()
        assert not installed_hook.is_symlink()


@pytest.mark.parametrize(("args", "stdin", "expect_link"), MODES)
@pytest.mark.parametrize("link_kind", ["dangling", "loop"])
def test_unresolvable_hook_link_is_preserved(
    installer_tree: Path,
    fake_python_bin: Path,
    tmp_path: Path,
    args: list[str],
    stdin: str | None,
    expect_link: bool,
    link_kind: str,
) -> None:
    del expect_link
    home = tmp_path / f"{link_kind} home"
    reasonix = home / ".reasonix"
    reasonix.mkdir(parents=True)
    hooks_dir = reasonix / "hooks"
    target = tmp_path / "missing external hooks" if link_kind == "dangling" else hooks_dir
    hooks_dir.symlink_to(target, target_is_directory=True)
    original_target = os.readlink(hooks_dir)
    source_hook = installer_tree / "hooks" / HOOK_NAME
    original_source = source_hook.read_bytes()

    result = _run_install(installer_tree, home, fake_python_bin, args, stdin)

    assert result.returncode != 0
    assert hooks_dir.is_symlink()
    assert os.readlink(hooks_dir) == original_target
    assert source_hook.read_bytes() == original_source


def test_module_skips_collection_without_bash(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    probe = tmp_path / "test_no_bash_probe.py"
    probe.write_text(
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('hook_mirror_safety', {str(Path(__file__))!r})\n"
        "assert spec is not None and spec.loader is not None\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PATH": str(empty_path)}

    result = subprocess.run(  # nosec B603 - fixed interpreter and pytest argv
        [sys.executable, "-m", "pytest", str(probe), "-q"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode in {0, 5}, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "1 skipped" in result.stdout
