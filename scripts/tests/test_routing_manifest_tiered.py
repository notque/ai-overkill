"""Tests for scripts/routing-manifest.py --tiered mode.

Covers the tiered-manifest contract:
- tiered output is smaller than full output
- stub entries still parse (name + em-dash + description)
- force-route entries always render FULL
- working set = weight rows (n >= 1) UNION recent route-events DECISIONs

All learning reads go through a temp CLAUDE_LEARNING_DIR — never the live one.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "routing-manifest.py"

_spec = importlib.util.spec_from_file_location("routing_manifest", SCRIPT)
assert _spec and _spec.loader
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _entry(
    name: str,
    entry_type: str = "skill",
    description: str = "A long description with many words to exercise stub truncation behavior",
    force_route: bool = False,
    **extra: object,
) -> dict:
    return {
        "name": name,
        "type": entry_type,
        "description": description,
        "triggers": [],
        "category": extra.get("category", ""),
        "agent": extra.get("agent"),
        "model": None,
        "pairs_with": extra.get("pairs_with", []),
        "force_route": force_route,
        **({"not_for": extra["not_for"]} if "not_for" in extra else {}),
    }


ENTRIES = [
    _entry("alpha-agent", "agent", "Agent for alpha domain tasks plus extra trailing words"),
    _entry("beta-agent", "agent", "Agent for beta domain tasks plus extra trailing words"),
    _entry("cold-skill", "skill", "Never routed skill with a very long description tail", category="misc"),
    _entry("hot-skill", "skill", "Recently routed skill with a very long description tail", category="misc"),
    _entry(
        "force-skill",
        "skill",
        "Force-routed skill with a very long description tail",
        force_route=True,
        category="git-workflow",
        not_for="metaphorical uses",
    ),
    _entry("a-pipeline", "pipeline", "Pipeline description stays full"),
    _entry(
        "paired-cold-skill",
        "skill",
        "Cold skill that declares an agent pairing here",
        agent="alpha-agent",
        category="misc",
    ),
    _entry(
        "guarded-cold-skill",
        "skill",
        "Cold skill carrying a not_for guard clause tail",
        not_for="metaphorical uses of guard",
        category="misc",
    ),
]


@pytest.fixture
def learning_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temp learning dir; CLAUDE_LEARNING_DIR points at it for module reads."""
    d = tmp_path / "learning"
    d.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(d))
    return d


def _write_db(learning_dir: Path, rows: list[tuple[str, int, str]]) -> None:
    """Write a minimal learning.db with (key, observation_count, source) rows."""
    conn = sqlite3.connect(learning_dir / "learning.db")
    conn.execute("CREATE TABLE learnings (key TEXT, topic TEXT, category TEXT, observation_count INTEGER, source TEXT)")
    conn.executemany(
        "INSERT INTO learnings VALUES (?, 'routing', 'effectiveness', ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _write_events(learning_dir: Path, events: list[dict]) -> None:
    lines = "".join(json.dumps(e) + "\n" for e in events)
    (learning_dir / "route-events.jsonl").write_text(lines, encoding="utf-8")


# ---------------------------------------------------------------------------
# load_working_set
# ---------------------------------------------------------------------------


def test_working_set_empty_when_no_data(learning_dir: Path) -> None:
    assert rm.load_working_set() == set()


def test_working_set_from_weight_rows(learning_dir: Path) -> None:
    _write_db(
        learning_dir,
        [
            ("alpha-agent:hot-skill", 3, "hook"),
            ("beta-agent:other", 0, "hook"),  # n=0 excluded
            ("x-agent:y-skill", 5, "test-fixture"),  # test source excluded
        ],
    )
    assert rm.load_working_set() == {"alpha-agent", "hot-skill"}


def test_working_set_from_recent_events_only(learning_dir: Path) -> None:
    now = time.time()
    _write_events(
        learning_dir,
        [
            {"type": "decision", "ts": now - 86400, "agent": "beta-agent", "skill": "hot-skill"},
            {"type": "decision", "ts": now - 40 * 86400, "agent": "stale-agent", "skill": "stale-skill"},
            {"type": "outcome", "ts": now, "key": "o-agent:o-skill"},  # not a decision
            {"type": "decision", "ts": now, "agent": "solo-agent", "skill": "-"},  # skill=- dropped
        ],
    )
    assert rm.load_working_set(now=now) == {"beta-agent", "hot-skill", "solo-agent"}


def test_working_set_unions_db_and_events(learning_dir: Path) -> None:
    _write_db(learning_dir, [("alpha-agent:cold-skill", 1, "hook")])
    _write_events(learning_dir, [{"type": "decision", "ts": time.time(), "agent": "beta-agent", "skill": "hot-skill"}])
    assert rm.load_working_set() == {"alpha-agent", "cold-skill", "beta-agent", "hot-skill"}


def test_working_set_survives_garbage_inputs(learning_dir: Path) -> None:
    (learning_dir / "learning.db").write_bytes(b"not a sqlite file")
    (learning_dir / "route-events.jsonl").write_text("not json\n{\n", encoding="utf-8")
    assert rm.load_working_set() == set()


# ---------------------------------------------------------------------------
# format_tiered
# ---------------------------------------------------------------------------


def test_tiered_smaller_than_full() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    full = rm.format_compact(ENTRIES)
    assert len(tiered) < len(full)


def test_stub_entries_parse() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    stub = next(line for line in tiered.splitlines() if line.startswith("  cold-skill"))
    name, _, desc = stub.strip().partition(" — ")
    assert name == "cold-skill"
    assert desc == "Never routed skill with a very"  # first 6 words
    # Section structure intact: every entry name still present.
    for e in ENTRIES:
        assert e["name"] in tiered
    assert tiered.index("AGENTS:") < tiered.index("SKILLS:") < tiered.index("PIPELINES:")


def test_force_route_always_full() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    line = next(line for line in tiered.splitlines() if line.startswith("  force-skill"))
    assert "FORCE" in line
    assert "Force-routed skill with a very long description tail" in line
    assert "NOT: metaphorical uses" in line


def test_working_set_entries_full() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set={"hot-skill", "alpha-agent"})
    lines = tiered.splitlines()
    hot = next(line for line in lines if line.startswith("  hot-skill"))
    assert "Recently routed skill with a very long description tail" in hot
    assert "(misc)" in hot
    alpha = next(line for line in lines if line.startswith("  alpha-agent"))
    assert "Agent for alpha domain tasks plus extra trailing words" in alpha
    cold = next(line for line in lines if line.startswith("  cold-skill"))
    assert cold.strip() == "cold-skill — Never routed skill with a very"


def test_stub_skill_keeps_agent_pairing() -> None:
    """Stub skill lines carry agent= — dropping it made the router return agent: null."""
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    line = next(ln for ln in tiered.splitlines() if ln.startswith("  paired-cold-skill"))
    assert "agent=alpha-agent" in line
    assert "Cold skill that declares an agent" in line  # first 6 words kept
    assert "pairing here" not in line  # description still truncated


def test_stub_skill_keeps_not_for() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    line = next(ln for ln in tiered.splitlines() if ln.startswith("  guarded-cold-skill"))
    assert "NOT: metaphorical uses of guard" in line
    assert "clause tail" not in line  # description still truncated


def test_agent_stub_stays_name_and_description() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    line = next(ln for ln in tiered.splitlines() if ln.startswith("  beta-agent"))
    assert line.strip() == "beta-agent — Agent for beta domain tasks plus"


def test_pipelines_always_full() -> None:
    tiered = rm.format_tiered(ENTRIES, working_set=set())
    assert "  a-pipeline — Pipeline description stays full" in tiered


# ---------------------------------------------------------------------------
# CLI integration (real INDEX files; temp learning dir)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (REPO_ROOT / "skills" / "INDEX.json").exists(), reason="INDEX.json not generated")
def test_cli_tiered_smaller_than_full(learning_dir: Path) -> None:
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(learning_dir)}

    def run(*args: str) -> str:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            check=True,
        ).stdout

    tiered = run("--tiered")
    full = run()
    assert len(tiered) < len(full)
    # force-route entries (e.g. pr-workflow) keep their full line in both modes
    if "pr-workflow FORCE" in full:
        full_line = next(line for line in full.splitlines() if line.startswith("  pr-workflow"))
        assert full_line in tiered
    # --json and --compact behavior unchanged by the new flag
    json.loads(run("--json"))


# Local index merge semantics live in test_routing_index_merge.py: all three
# scripts import the same routing_index_merge.load_index_items, and that file
# asserts the identity plus the merge rules once.
