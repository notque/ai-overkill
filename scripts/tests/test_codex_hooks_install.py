"""Integration tests for the Codex hooks mirror installed by install.sh.

Runs install.sh against a temporary HOME directory and verifies that
~/.codex/hooks/, ~/.codex/hooks.json, and ~/.codex/config.toml are set
up correctly. Each test gets a fresh fake_home fixture so tests are
fully independent.
"""

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# Shells out to the full install.sh. Deselected from the default local run
# by the marker filter in pyproject.toml; CI still runs it via `-m ""`.
pytestmark = [pytest.mark.slow, pytest.mark.integration]

# tomllib is stdlib on Python 3.11+. On 3.10, skip the subset of tests that
# use it to parse the post-install config.toml. Other tests still run.
try:
    import tomllib  # type: ignore[import-not-found,unused-ignore]

    _HAS_TOMLLIB = True
except ImportError:
    tomllib = None  # type: ignore[assignment]
    _HAS_TOMLLIB = False

requires_tomllib = pytest.mark.skipif(not _HAS_TOMLLIB, reason="tomllib requires Python 3.11+")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
ALLOWLIST = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"

# Module-level guard: bash must be available.
if shutil.which("bash") is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)


def _run_install(
    fake_home: Path, extra_args: list[str] | None = None, timeout: int = 180
) -> subprocess.CompletedProcess:
    """Run install.sh with the given fake HOME and extra args.

    Args:
        fake_home: Directory to use as $HOME.
        extra_args: Additional flags to pass to install.sh.
        timeout: Maximum seconds to wait before failing.

    Returns:
        CompletedProcess with stdout and stderr captured.
    """
    args = extra_args or []
    env = {**os.environ, "HOME": str(fake_home), "TERM": "dumb"}
    return subprocess.run(
        ["bash", str(INSTALL_SH)] + args,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_allowlist_filenames() -> set[str]:
    """Return the set of hook filenames from the allowlist.

    Returns:
        Set of bare filenames (e.g. 'session-github-briefing.py').
    """
    filenames: set[str] = set()
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rest = stripped.split(":", 1)[1]
        filename = rest.strip().split()[0]
        filenames.add(filename)
    return filenames


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Provide a clean temporary HOME directory for each test.

    Args:
        tmp_path: pytest-provided temporary directory.
        monkeypatch: pytest fixture for environment patching.

    Returns:
        Path to the fresh fake HOME.
    """
    home = tmp_path / "home"
    home.mkdir()
    # install.sh syncs a runtime mirror only when the runtime's command is on
    # PATH or its home dir exists. CI runners lack the codex CLI, so pre-create
    # ~/.codex to simulate a machine with the Codex runtime installed.
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    try:
        yield home
    finally:
        # Copy-mode installs mirror a large script corpus. Reclaim each fake
        # HOME immediately so the full installer suite cannot exhaust /tmp.
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_install_sh_creates_codex_hooks_dir(fake_home: Path) -> None:
    """install.sh --copy creates ~/.codex/hooks/ with the primary hook file."""
    result = _run_install(fake_home, ["--copy", "--force"])
    hooks_dir = fake_home / ".codex" / "hooks"

    assert hooks_dir.exists(), f"~/.codex/hooks/ not created.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert hooks_dir.is_dir(), "~/.codex/hooks is not a directory"

    target_hook = hooks_dir / "session-github-briefing.py"
    assert target_hook.exists(), "session-github-briefing.py missing from hooks dir"


def test_install_sh_mirrors_all_allowlisted_hooks(fake_home: Path) -> None:
    """Every filename in codex-hooks-allowlist.txt appears in ~/.codex/hooks/."""
    result = _run_install(fake_home, ["--copy", "--force"])
    hooks_dir = fake_home / ".codex" / "hooks"

    expected = _parse_allowlist_filenames()
    assert expected, "Allowlist is empty; nothing to verify"

    missing = []
    for filename in sorted(expected):
        if not (hooks_dir / filename).exists():
            missing.append(filename)

    assert not missing, (
        f"Missing hooks in ~/.codex/hooks/: {missing}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_install_sh_generates_valid_hooks_json(fake_home: Path) -> None:
    """install.sh produces a syntactically valid ~/.codex/hooks.json with correct schema."""
    result = _run_install(fake_home, ["--copy", "--force"])
    hooks_json_path = fake_home / ".codex" / "hooks.json"

    assert hooks_json_path.exists(), f"hooks.json not created.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    try:
        data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"hooks.json is not valid JSON: {exc}\nContent:\n{hooks_json_path.read_text()}")

    assert "hooks" in data, f"Top-level 'hooks' key missing from hooks.json: {data}"
    assert isinstance(data["hooks"], dict), "'hooks' value must be a dict"

    has_session_start = False
    has_bash_post_tool_use = False

    for event_key, matcher_groups in data["hooks"].items():
        assert isinstance(matcher_groups, list), f"Event '{event_key}' value must be a list, got {type(matcher_groups)}"
        for group in matcher_groups:
            assert isinstance(group, dict), f"Matcher group must be a dict, got {type(group)}"
            assert "hooks" in group, f"Matcher group missing 'hooks' key: {group}"
            assert isinstance(group["hooks"], list), "'hooks' within group must be a list"

            for entry in group["hooks"]:
                assert entry.get("type") == "command", f"Hook entry must have type='command': {entry}"
                assert "command" in entry, f"Hook entry missing 'command': {entry}"
                assert "timeout" in entry, f"Hook entry missing 'timeout': {entry}"

            if event_key == "SessionStart":
                has_session_start = True

            if event_key == "PostToolUse":
                matcher = group.get("matcher", "")
                if matcher == "Bash":
                    has_bash_post_tool_use = True

    assert has_session_start, "hooks.json has no SessionStart entries"
    assert has_bash_post_tool_use, "hooks.json has no PostToolUse entry with matcher='Bash'"

    commands = [entry["command"] for groups in data["hooks"].values() for group in groups for entry in group["hooks"]]
    assert len(commands) == 61
    assert all("codex-hook-adapter.py" in command for command in commands)
    script_count = len(list((REPO_ROOT / "scripts").glob("*.py")))
    assert f"Codex scripts: {script_count} mirrored scripts" in result.stdout
    assert "Hooks: 86 automation hooks" in result.stdout
    assert f"Scripts: {script_count} utility scripts" in result.stdout

    tool_matchers = {
        group.get("matcher")
        for event_key in ("PreToolUse", "PostToolUse")
        for group in data["hooks"].get(event_key, [])
    }
    assert tool_matchers == {"Bash", "Edit|Write"}


@requires_tomllib
def test_install_sh_sets_feature_flag(fake_home: Path) -> None:
    """install.sh sets hooks = true in ~/.codex/config.toml."""
    result = _run_install(fake_home, ["--copy", "--force"])
    config_path = fake_home / ".codex" / "config.toml"

    assert config_path.exists(), f"config.toml not created.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    with open(config_path, "rb") as fh:
        config = tomllib.load(fh)

    assert "features" in config, "[features] section missing from config.toml"
    assert config["features"].get("hooks") is True, f"hooks != true in [features]. Got: {config['features']}"
    assert config["features"].get("multi_agent_v2") == {
        "hide_spawn_agent_metadata": False,
        "tool_namespace": "agents",
    }, f"MultiAgent V2 routing compatibility missing. Got: {config['features']}"
    assert "codex_hooks" not in config["features"], (
        f"deprecated codex_hooks should not be written. Got: {config['features']}"
    )


@requires_tomllib
def test_install_sh_preserves_existing_config_toml_sections(fake_home: Path) -> None:
    """install.sh does not clobber pre-existing config.toml sections."""
    codex_dir = fake_home / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)

    existing_toml = (
        '[projects."/home/user/repo"]\ntrust_level = "trusted"\n\n[notice]\nhide_rate_limit_model_nudge = true\n'
    )
    config_path = codex_dir / "config.toml"
    config_path.write_text(existing_toml, encoding="utf-8")

    result = _run_install(fake_home, ["--copy", "--force"])

    assert config_path.exists(), f"config.toml disappeared.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    with open(config_path, "rb") as fh:
        config = tomllib.load(fh)

    assert "projects" in config or any(k.startswith("projects") for k in config), (
        f"[projects] section lost after install. Full config: {config}"
    )
    assert "notice" in config, f"[notice] section lost after install. Full config: {config}"
    assert config["notice"].get("hide_rate_limit_model_nudge") is True

    assert "features" in config, f"[features] section not added. Full config: {config}"
    assert config["features"].get("hooks") is True


@requires_tomllib
def test_install_sh_migrates_deprecated_codex_hooks_flag(fake_home: Path) -> None:
    """install.sh removes deprecated codex_hooks and reports the migration action."""
    codex_dir = fake_home / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)

    config_path = codex_dir / "config.toml"
    config_path.write_text("[features]\ncodex_hooks = true\ngoals = true\n", encoding="utf-8")

    result = _run_install(fake_home, ["--copy", "--force"])

    assert result.returncode == 0, f"install.sh failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    text = config_path.read_text(encoding="utf-8")
    assert "codex_hooks" not in text
    assert "Codex config features: migrated" in result.stdout

    with open(config_path, "rb") as fh:
        config = tomllib.load(fh)

    assert config["features"]["hooks"] is True
    assert config["features"]["goals"] is True
    assert "codex_hooks" not in config["features"]


def test_install_sh_dry_run_does_not_touch_filesystem(fake_home: Path) -> None:
    """install.sh --dry-run leaves ~/.codex untouched."""
    result = _run_install(fake_home, ["--dry-run", "--symlink"])

    hooks_dir = fake_home / ".codex" / "hooks"
    hooks_json = fake_home / ".codex" / "hooks.json"
    config_toml = fake_home / ".codex" / "config.toml"

    assert not hooks_dir.exists(), f"~/.codex/hooks/ was created during dry-run.\nSTDOUT:\n{result.stdout}"
    assert not hooks_json.exists(), f"hooks.json was created during dry-run.\nSTDOUT:\n{result.stdout}"
    assert not config_toml.exists(), f"config.toml was created during dry-run.\nSTDOUT:\n{result.stdout}"

    # Dry-run output should describe the Codex hooks block action.
    combined = result.stdout + result.stderr
    assert "Would create" in combined or "Would generate" in combined or "Would ensure" in combined, (
        f"Dry-run output contains no 'Would ...' lines for Codex hooks.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "/hooks" in combined
    assert "trust" in combined.lower()
    assert "skipped until" in combined.lower()


@requires_tomllib
def test_install_sh_uninstall_removes_hooks(fake_home: Path) -> None:
    """--uninstall removes ~/.codex/hooks/ and archives hooks.json; config.toml survives."""
    # Install first.
    install_result = _run_install(fake_home, ["--copy", "--force"])
    hooks_dir = fake_home / ".codex" / "hooks"
    assert hooks_dir.exists(), (
        f"Pre-condition failed: hooks dir not created by install.\nSTDOUT:\n{install_result.stdout}"
    )

    # Now uninstall.
    uninstall_result = _run_install(fake_home, ["--uninstall"])

    assert not hooks_dir.exists(), (
        f"~/.codex/hooks/ still present after --uninstall.\nSTDOUT:\n{uninstall_result.stdout}\nSTDERR:\n{uninstall_result.stderr}"
    )

    # hooks.json should have been archived, not deleted in place.
    codex_dir = fake_home / ".codex"
    hooks_json = codex_dir / "hooks.json"
    assert not hooks_json.exists(), (
        f"hooks.json still present as hooks.json (should be archived).\nSTDOUT:\n{uninstall_result.stdout}"
    )

    archived = list(codex_dir.glob("hooks.json.uninstalled.*"))
    assert archived, (
        f"No hooks.json.uninstalled.* archive found in {codex_dir}.\n"
        f"Files in codex_dir: {[f.name for f in codex_dir.iterdir()]}\n"
        f"STDOUT:\n{uninstall_result.stdout}"
    )

    # config.toml feature flag is intentionally NOT removed by uninstall.
    config_path = codex_dir / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as fh:
            config = tomllib.load(fh)
        assert config.get("features", {}).get("hooks") is True, (
            "Uninstall incorrectly removed hooks = true from config.toml"
        )


def test_per_item_install_refreshes_hooks_lib(fake_home: Path, tmp_path: Path) -> None:
    """Per-item hook installs must refresh hooks/lib, not preserve stale helpers."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    try:
        dst.symlink_to(src)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable for this user/platform: {exc}")
    dst.unlink()

    stale_lib = fake_home / ".claude" / "hooks" / "lib"
    stale_lib.mkdir(parents=True)
    (stale_lib / "hook_utils.py").write_text("def log_error(message): pass\n", encoding="utf-8")
    (stale_lib / "external_helper.py").write_text("# user-owned helper\n", encoding="utf-8")

    stale_codex_lib = fake_home / ".codex" / "hooks" / "lib"
    stale_codex_lib.mkdir(parents=True)
    (stale_codex_lib / "hook_utils.py").write_text("def log_error(message): pass\n", encoding="utf-8")
    (stale_codex_lib / "external_helper.py").write_text("# user-owned helper\n", encoding="utf-8")

    reasonix_dir = fake_home / ".reasonix"
    reasonix_dir.mkdir()
    stale_reasonix_lib = reasonix_dir / "hooks" / "lib"
    stale_reasonix_lib.mkdir(parents=True)
    (stale_reasonix_lib / "hook_utils.py").write_text("def log_error(message): pass\n", encoding="utf-8")
    (stale_reasonix_lib / "external_helper.py").write_text("# user-owned helper\n", encoding="utf-8")

    result = _run_install(fake_home, ["--symlink", "--per-item", "--force"])

    assert result.returncode == 0, f"install.sh failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    hook_utils = fake_home / ".claude" / "hooks" / "lib" / "hook_utils.py"
    assert "def hook_error(" in hook_utils.read_text(encoding="utf-8")
    assert (stale_lib / "external_helper.py").read_text(encoding="utf-8") == "# user-owned helper\n"

    codex_hook_utils = fake_home / ".codex" / "hooks" / "lib" / "hook_utils.py"
    assert "def hook_error(" in codex_hook_utils.read_text(encoding="utf-8")
    assert (stale_codex_lib / "external_helper.py").read_text(encoding="utf-8") == "# user-owned helper\n"

    reasonix_hook_utils = fake_home / ".reasonix" / "hooks" / "lib" / "hook_utils.py"
    assert "def hook_error(" in reasonix_hook_utils.read_text(encoding="utf-8")
    assert (stale_reasonix_lib / "external_helper.py").read_text(encoding="utf-8") == "# user-owned helper\n"


def test_install_mirrors_adapter_and_writes_managed_manifest(fake_home: Path) -> None:
    """The generated adapter command always points to an installed file."""
    result = _run_install(fake_home, ["--copy", "--force"])
    assert result.returncode == 0, result.stderr[-2000:]
    hooks_dir = fake_home / ".codex" / "hooks"
    assert (hooks_dir / "codex-hook-adapter.py").is_file()
    manifest = hooks_dir / ".vexjoy-managed-hooks"
    assert manifest.is_file()
    managed = set(manifest.read_text(encoding="utf-8").splitlines())
    assert "codex-hook-adapter.py" in managed
    assert _parse_allowlist_filenames() <= managed


def test_reinstall_removes_only_previously_managed_stale_hooks(fake_home: Path) -> None:
    """Stale toolkit files are removed while unlisted user files survive."""
    hooks_dir = fake_home / ".codex" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "stale-toolkit.py").write_text("# old toolkit file\n", encoding="utf-8")
    (hooks_dir / "user-hook.py").write_text("# user owned\n", encoding="utf-8")
    (hooks_dir / ".vexjoy-managed-hooks").write_text("stale-toolkit.py\n", encoding="utf-8")

    result = _run_install(fake_home, ["--copy", "--force"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert not (hooks_dir / "stale-toolkit.py").exists()
    assert (hooks_dir / "user-hook.py").read_text(encoding="utf-8") == "# user owned\n"


def test_install_reports_codex_hook_trust_review(fake_home: Path) -> None:
    """Changed definitions are not active until Codex hash trust is reviewed."""
    result = _run_install(fake_home, ["--copy", "--force"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert "/hooks" in result.stdout
    assert "review" in result.stdout.lower()
    assert "trust" in result.stdout.lower()
    assert "skipped until" in result.stdout.lower()


def test_dry_run_reports_existing_hooks_json_backup_plan(fake_home: Path) -> None:
    """Dry-run names the backup action without modifying hooks.json."""
    hooks_json = fake_home / ".codex" / "hooks.json"
    hooks_json.write_text('{"user": "content"}\n', encoding="utf-8")
    result = _run_install(fake_home, ["--dry-run", "--copy"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert "would back up" in result.stdout.lower()
    assert str(hooks_json) in result.stdout
    assert hooks_json.read_text(encoding="utf-8") == '{"user": "content"}\n'


def test_install_reports_and_creates_existing_hooks_json_backup(fake_home: Path) -> None:
    """Replacement announces and creates the generator's timestamped backup."""
    hooks_json = fake_home / ".codex" / "hooks.json"
    hooks_json.write_text('{"user": "content"}\n', encoding="utf-8")
    result = _run_install(fake_home, ["--copy", "--force"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert "will back up" in result.stdout.lower()
    assert str(hooks_json) in result.stdout
    backups = list((fake_home / ".codex").glob("hooks.bak.*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == '{"user": "content"}\n'


def test_install_warns_below_current_hook_floor(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old v0.114 floor no longer claims current apply_patch parity."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    codex = bin_dir / "codex"
    codex.write_text("#!/bin/sh\necho 'codex-cli 0.143.0'\n", encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    result = _run_install(fake_home, ["--copy", "--force"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert "below 0.144.1" in result.stdout
