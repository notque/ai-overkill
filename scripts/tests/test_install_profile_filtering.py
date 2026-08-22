"""Integration tests for opt-in install profile filtering.

Runs install.sh against a temporary HOME. VEXJOY_INSTALL_PROFILE points
install.sh at a test profile so the repo's real .local/profile.yaml is
never touched. No profile file = behavior identical to today (opt-in pin).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
CONFIGURE = REPO_ROOT / "scripts" / "configure-profile.py"
ALLOWLIST = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"

if shutil.which("bash") is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)


def _run_install(fake_home: Path, args: list[str], profile: Path | None = None) -> subprocess.CompletedProcess:
    # The installer may attempt an advisory dependency install. Keep these
    # integration tests offline so they exercise installation behavior only.
    env = {
        **os.environ,
        "HOME": str(fake_home),
        "TERM": "dumb",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    if profile is not None:
        env["VEXJOY_INSTALL_PROFILE"] = str(profile)
    else:
        env["VEXJOY_INSTALL_PROFILE"] = str(fake_home / "no-such-profile.yaml")
    return subprocess.run(
        ["bash", str(INSTALL_SH)] + args,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _first_agent() -> str:
    return sorted(p.stem for p in (REPO_ROOT / "agents").glob("*.md") if not p.stem.upper().startswith("README"))[0]


def _first_allowlisted_hook() -> str:
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        return line.split(":", 1)[1].split()[0]
    raise AssertionError("no allowlisted hooks found")


def _first_top_level_skill() -> str:
    for entry in sorted((REPO_ROOT / "skills").iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            return entry.name
    raise AssertionError("no top-level skill found")


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    # install.sh syncs a runtime mirror only when the runtime's command is on
    # PATH or its home dir exists. CI runners lack the codex CLI, so pre-create
    # ~/.codex to simulate a machine with the Codex runtime installed.
    (home / ".codex").mkdir()
    return home


def _write_profile(path: Path, skills: list[str], agents: list[str], hooks: list[str]) -> None:
    lines = ["disabled:"]
    for cat, items in (("skills", skills), ("agents", agents), ("hooks", hooks)):
        if items:
            lines.append(f"  {cat}:")
            lines.extend(f"    - {i}" for i in items)
        else:
            lines.append(f"  {cat}: []")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_no_profile_dry_run_mentions_no_filtering(fake_home: Path) -> None:
    """Opt-in pin: without profile.yaml, install plans nothing profile-related."""
    result = _run_install(fake_home, ["--dry-run", "--sync"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert "Install profile:" not in result.stdout
    assert "disabled by profile" not in result.stdout.lower()


def test_no_profile_installs_everything(fake_home: Path) -> None:
    """Opt-in pin: without profile.yaml the candidate items all install."""
    agent, hook, skill = _first_agent(), _first_allowlisted_hook(), _first_top_level_skill()
    result = _run_install(fake_home, ["--sync"])
    assert result.returncode == 0, result.stderr[-2000:]
    assert (fake_home / ".claude" / "agents" / f"{agent}.md").exists()
    assert (fake_home / ".claude" / "hooks" / hook).exists()
    assert (fake_home / ".claude" / "skills" / skill).exists()
    assert (fake_home / ".claude" / "skills" / "game-design" / "SKILL.md").exists()
    assert (fake_home / ".codex" / "hooks" / hook).exists()
    assert (fake_home / ".codex" / "skills" / "game-design" / "SKILL.md").exists()


def test_profile_filters_per_item_install(fake_home: Path, tmp_path: Path) -> None:
    """--sync (per-item) skips disabled agent/hook/skill in Claude + Codex + settings.json."""
    agent, hook, skill = _first_agent(), _first_allowlisted_hook(), _first_top_level_skill()
    profile = tmp_path / "profile.yaml"
    _write_profile(profile, skills=[skill], agents=[agent], hooks=[hook])

    result = _run_install(fake_home, ["--sync"], profile=profile)
    assert result.returncode == 0, result.stderr[-2000:]

    assert not (fake_home / ".claude" / "agents" / f"{agent}.md").exists()
    assert not (fake_home / ".claude" / "hooks" / hook).exists()
    assert not (fake_home / ".claude" / "skills" / skill).exists()
    assert not (fake_home / ".codex" / "hooks" / hook).exists()
    assert not (fake_home / ".codex" / "skills" / skill).exists()

    settings = (fake_home / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert hook not in settings

    # Sibling items still install.
    other_agents = [p.stem for p in (REPO_ROOT / "agents").glob("*.md") if p.stem != agent]
    if other_agents:
        assert (fake_home / ".claude" / "agents" / f"{other_agents[0]}.md").exists()


def test_configure_plain_fallback_writes_profile(tmp_path: Path) -> None:
    """Picker works without questionary: --plain reads names from stdin."""
    agent = _first_agent()
    out = tmp_path / "profile.yaml"
    result = subprocess.run(
        [sys.executable, str(CONFIGURE), "--plain", "--output", str(out)],
        input=f"\n{agent}\n\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert agent in text
    assert "disabled:" in text
