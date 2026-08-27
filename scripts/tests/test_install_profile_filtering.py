"""Integration tests for opt-in install profile filtering.

Runs install.sh against a temporary HOME. VEXJOY_INSTALL_PROFILE points
install.sh at a test profile so the repo's real .local/profile.yaml is
never touched. No profile file = behavior identical to today (opt-in pin).
"""

import json
import os
import shutil
import subprocess
import sys
import uuid
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


def _run_doctor_codex_check(fake_home: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/install-doctor.py"), "check", "--json"],
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = json.loads(result.stdout)
    return next(check for check in payload["checks"] if check["name"] == "codex_skills")


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


@pytest.fixture
def private_voice_fixture() -> str:
    """Create an ignored private voice so clean-checkout tests exercise its install path."""
    voice_name = f"ci-profile-{uuid.uuid4().hex}"
    voice_root = REPO_ROOT / "private-voices" / voice_name
    skill_dir = voice_root / "skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: voice-{voice_name}\ndescription: CI private voice fixture.\n---\n\n# Fixture\n",
        encoding="utf-8",
    )
    try:
        yield f"voice-{voice_name}"
    finally:
        shutil.rmtree(voice_root)


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
    installed_skills = len(list((fake_home / ".claude" / "skills").glob("*/SKILL.md")))
    installed_invocable = sum(
        "user-invocable: true" in path.read_text(encoding="utf-8")
        for path in (fake_home / ".claude" / "skills").glob("*/SKILL.md")
    )
    assert f"Skills: {installed_skills} workflow methodologies ({installed_invocable} user-invocable)" in result.stdout


def test_sync_refreshes_existing_codex_skill_files_and_keeps_extras(fake_home: Path) -> None:
    """A repeated --sync refreshes canonical Codex files without pruning local skills."""
    initial = _run_install(fake_home, ["--sync"])
    assert initial.returncode == 0, initial.stderr[-2000:]

    installed_do = fake_home / ".codex" / "skills" / "do" / "SKILL.md"
    if installed_do.is_symlink():
        installed_do.unlink()
    installed_do.write_text("# stale do\n", encoding="utf-8")
    references = fake_home / ".codex" / "skills" / "do" / "references"
    if references.is_symlink():
        references.unlink()
        references.mkdir()
    local_reference = references / "local.md"
    local_reference.write_text("runtime-only\n", encoding="utf-8")
    canonical_reference = next((REPO_ROOT / "skills/meta/do/references").glob("*.md"))
    stale_reference = references / canonical_reference.name
    if stale_reference.is_symlink():
        stale_reference.unlink()
    stale_reference.write_text("stale canonical reference\n", encoding="utf-8")
    extra = fake_home / ".codex" / "skills" / "codex-only"
    extra.mkdir()
    (extra / "SKILL.md").write_text("# Codex-only\n", encoding="utf-8")

    preserved = _run_install(fake_home, ["--symlink", "--per-item"])
    assert preserved.returncode == 0, preserved.stderr[-2000:]
    assert installed_do.read_text(encoding="utf-8") == "# stale do\n"

    refreshed = _run_install(fake_home, ["--sync"])
    assert refreshed.returncode == 0, refreshed.stderr[-2000:]

    assert installed_do.read_bytes() == (REPO_ROOT / "skills/meta/do/SKILL.md").read_bytes()
    assert stale_reference.read_bytes() == canonical_reference.read_bytes()
    assert local_reference.read_text(encoding="utf-8") == "runtime-only\n"
    assert (extra / "SKILL.md").read_text(encoding="utf-8") == "# Codex-only\n"


def test_sync_never_traverses_external_codex_skill_symlink(fake_home: Path, tmp_path: Path) -> None:
    external = tmp_path / "external-do"
    external.mkdir()
    external_skill = external / "SKILL.md"
    external_skill.write_text("# external do\n", encoding="utf-8")
    codex_skills = fake_home / ".codex" / "skills"
    codex_skills.mkdir()
    (codex_skills / "do").symlink_to(external, target_is_directory=True)

    result = _run_install(fake_home, ["--sync"])
    assert result.returncode == 0, result.stderr[-2000:]

    installed = codex_skills / "do"
    assert installed.is_symlink()
    assert installed.resolve() == external
    assert external_skill.read_text(encoding="utf-8") == "# external do\n"


def test_profile_filters_private_voices_from_claude_and_codex(
    fake_home: Path, tmp_path: Path, private_voice_fixture: str
) -> None:
    voice = private_voice_fixture
    profile = tmp_path / "profile.yaml"
    _write_profile(profile, skills=[voice], agents=[], hooks=[])

    result = _run_install(fake_home, ["--sync"], profile=profile)
    assert result.returncode == 0, result.stderr[-2000:]

    assert not (fake_home / ".claude" / "skills" / voice).exists()
    assert not (fake_home / ".codex" / "skills" / voice).exists()


def test_profile_transition_removes_only_installer_owned_private_voice(
    fake_home: Path, tmp_path: Path, private_voice_fixture: str
) -> None:
    voice = private_voice_fixture
    enabled = _run_install(fake_home, ["--sync"])
    assert enabled.returncode == 0, enabled.stderr[-2000:]
    claude_voice = fake_home / ".claude" / "skills" / voice
    codex_voice = fake_home / ".codex" / "skills" / voice
    assert claude_voice.exists()
    assert codex_voice.exists()

    profile = tmp_path / "profile.yaml"
    _write_profile(profile, skills=[voice], agents=[], hooks=[])
    disabled = _run_install(fake_home, ["--sync"], profile=profile)
    assert disabled.returncode == 0, disabled.stderr[-2000:]

    assert not claude_voice.exists() and not claude_voice.is_symlink()
    assert not codex_voice.exists() and not codex_voice.is_symlink()


def test_doctor_honors_profile_omissions_and_still_detects_enabled_drift(fake_home: Path, tmp_path: Path) -> None:
    disabled = "quick"
    profile = tmp_path / "profile.yaml"
    _write_profile(profile, skills=[disabled], agents=[], hooks=[])

    installed = _run_install(fake_home, ["--sync"], profile=profile)
    assert installed.returncode == 0, installed.stderr[-2000:]
    assert _run_doctor_codex_check(fake_home)["passed"] is True

    enabled_skill = fake_home / ".codex" / "skills" / "do" / "SKILL.md"
    enabled_skill.unlink()
    enabled_skill.write_text("# stale enabled skill\n", encoding="utf-8")

    drift = _run_doctor_codex_check(fake_home)
    assert drift["passed"] is False
    assert "do/SKILL.md" in drift["detail"]


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
