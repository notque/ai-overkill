#!/usr/bin/env python3
"""Generate a compact routing manifest for the /do router (orchestrator self-route).

Reads skills/INDEX.json, agents/INDEX.json, and pipeline-index.json,
then outputs a compact text manifest that an LLM can parse efficiently.

Usage:
    python3 scripts/routing-manifest.py
    python3 scripts/routing-manifest.py --json
    python3 scripts/routing-manifest.py --tiered

--tiered is REJECTED for production routing: two blind A/B runs failed
gates (c) safety misses and (d) stub-tier (verdicts in
scripts/routing-ab-results/tiered-v1|v2/VERDICT.md on PR #771's branch).
The flag stays for experimentation only; the /do router uses the full
manifest (no flag).

Line format (default/full manifest):

    AGENTS:
      name [pairs_with] — description NOT: excluded t:phrase|phrase
    SKILLS:
      name FORCE agent=x (category) — description NOT: excluded t:phrase|phrase

The trailing ``t:`` field carries up to TRIGGER_CAP hand-curated trigger
phrases from INDEX.json — the discriminating signal the router needs to
tell two same-domain skills apart. Every FULL line carries it, in the
default manifest and on --tiered's FULL lines alike. --tiered stubs and
--compact skip it: both exist to shrink the manifest, so neither pays for
the field.

Exit codes:
    0 — Always (advisory)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Shared tracked+local INDEX merge — single source in routing_index_merge.py.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from routing_index_merge import load_index_items as _load_index_items

# Canonical DB-dir resolver (ADR-122 hardening lives there)
_HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))
from learning_db_v2 import get_db_dir

# Tiered mode: how far back a route-events DECISION keeps a name in the
# working set, and how many description words a stub line keeps.
WORKING_SET_WINDOW_SECONDS = 30 * 86400
STUB_DESC_WORDS = 6

# Trigger phrases rendered per AGENTS/SKILLS line. The manifest is injected on
# every routing decision, so this is a byte budget, not a preference: measured
# against the 37,367-byte no-trigger manifest, top-3 costs +19%, top-5 +29%,
# and all 1,791 curated phrases +80%. Top-5 is the chosen trade. Tune here.
TRIGGER_CAP = 5
TRIGGER_PREFIX = " t:"
TRIGGER_SEP = "|"


INDEX_PATHS = {
    "skills": (REPO_ROOT / "skills" / "INDEX.json", "INDEX.local.json"),
    "agents": (REPO_ROOT / "agents" / "INDEX.json", "INDEX.local.json"),
    "pipelines": (REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json", None),
}


def load_entries() -> list[dict]:
    """Load all INDEX entries into a flat list."""
    entries = []

    for index_type, (tracked, local_name) in INDEX_PATHS.items():
        items = _load_index_items(tracked, local_name, index_type)

        for name, data in items.items():
            if not isinstance(data, dict):
                continue
            entry: dict = {
                "name": name,
                "type": "skill" if index_type == "skills" else index_type.rstrip("s"),
                "description": data.get("description") or data.get("short_description", ""),
                "triggers": data.get("triggers", []),
                "category": data.get("category", ""),
                "agent": data.get("agent"),
                "model": data.get("model"),
                "pairs_with": data.get("pairs_with", []),
                "force_route": bool(data.get("force_route", False)),
            }
            not_for = data.get("not_for")
            if isinstance(not_for, str):
                # Formatters below prepend "NOT: "; strip a source-side
                # prefix so a prefixed frontmatter value cannot render as
                # "NOT: NOT:".
                stripped = not_for.strip()
                if stripped.upper().startswith("NOT:"):
                    not_for = stripped[4:].lstrip()
            if not_for:
                entry["not_for"] = not_for
            entries.append(entry)

    return entries


def _learning_dir() -> Path:
    """Resolve the learning dir from CLAUDE_LEARNING_DIR (tests redirect it)."""
    return get_db_dir()


def _names_from_key(key: str, names: set[str]) -> None:
    """Add the agent and skill names from an `agent:skill` route key."""
    for part in key.split(":", 1):
        part = part.strip()
        if part and part != "-":
            names.add(part)


def load_working_set(now: float | None = None) -> set[str]:
    """Names (agents and skills) with recorded routes.

    Union of: route-weight rows (n >= 1, test rows excluded) from learning.db,
    and DECISION events from route-events.jsonl in the last 30 days.
    Read-only. Any read failure yields a smaller set, never an error —
    a smaller working set only means more stub lines.
    """
    names: set[str] = set()
    base = _learning_dir()

    db_path = base / "learning.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT key FROM learnings"
                    " WHERE topic = 'routing' AND category = 'effectiveness'"
                    " AND observation_count >= 1 AND source NOT LIKE 'test%'"
                ).fetchall()
            finally:
                conn.close()
            for (key,) in rows:
                _names_from_key(str(key), names)
        except sqlite3.Error:
            pass

    events_path = base / "route-events.jsonl"
    cutoff = (now if now is not None else time.time()) - WORKING_SET_WINDOW_SECONDS
    try:
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("type") != "decision":
                    continue
                ts = event.get("ts")
                if not isinstance(ts, (int, float)) or ts < cutoff:
                    continue
                for field in ("agent", "skill"):
                    value = event.get(field)
                    if isinstance(value, str) and value and value != "-":
                        names.add(value)
    except OSError:
        pass

    return names


def section_names(entries: list[dict]) -> dict[str, set[str]]:
    """Names owned by each section, keyed by entry type."""
    names: dict[str, set[str]] = {"agent": set(), "skill": set(), "pipeline": set()}
    for e in entries:
        names.setdefault(e["type"], set()).add(e["name"])
    return names


def select_triggers(entry: dict, reserved: set[str], cap: int | None = None) -> list[str]:
    """Pick up to `cap` trigger phrases that add routing signal to this line.

    Two classes of phrase are dropped before the cap applies:

    - A phrase equal to a component name in the OTHER section. The /do section
      validator decides `route.agent in agents` by tokenizing the text between
      the AGENTS: and SKILLS: headers, so a skill name printed inside an agent
      line would validate that skill as an agent. Five real cases exist today
      (agent kotlin-general-engineer carries trigger "kotlin", which is also a
      skill). Dropping them keeps SECTION-INTEGRITY true by construction.
    - A phrase already present verbatim in the description, which spends bytes
      to repeat a token the router can already read on the same line.
    """
    cap = TRIGGER_CAP if cap is None else cap
    desc = str(entry.get("description") or "").lower()
    picked: list[str] = []
    for raw in entry.get("triggers") or []:
        if len(picked) >= cap:
            break
        phrase = str(raw).strip()
        if not phrase or phrase in reserved or phrase.lower() in desc:
            continue
        picked.append(phrase)
    return picked


def format_triggers(entry: dict, reserved: set[str]) -> str:
    """Render the trailing ` t:a|b|c` field, or "" when nothing survives selection."""
    picked = select_triggers(entry, reserved)
    return TRIGGER_PREFIX + TRIGGER_SEP.join(picked) if picked else ""


def _stub_line(entry: dict) -> str:
    """One-line stub: name + router-critical metadata + first STUB_DESC_WORDS description words.

    Skill stubs keep the agent= pairing and not_for — dropping them made the
    router return the right skill with agent: null (tiered-v1 REJECT).
    Agent stubs stay name + truncated description.
    """
    desc = " ".join(str(entry["description"]).split()[:STUB_DESC_WORDS])
    if entry["type"] != "skill":
        return f"  {entry['name']} — {desc}"
    agent_str = f" agent={entry['agent']}" if entry.get("agent") else ""
    not_for = entry.get("not_for", "")
    not_for_str = f" NOT: {not_for}" if not_for else ""
    return f"  {entry['name']}{agent_str} — {desc}{not_for_str}"


def format_tiered(entries: list[dict], working_set: set[str]) -> str:
    """Format entries with FULL lines for the working set, stubs for the rest.

    FULL: working-set names (recorded routes) and every force-route entry —
    force-route entries are never stubbed, and a FULL line here is the same
    line format_compact renders, triggers included. Stub: name + 6-word
    description, no triggers. Pipelines are few; they always render FULL.
    """
    agents = []
    skills = []
    pipelines = []
    names = section_names(entries)

    for e in entries:
        name = e["name"]
        full = name in working_set or e.get("force_route", False)

        if e["type"] == "pipeline":
            pipelines.append(f"  {name} — {e['description']}")
            continue
        if not full:
            (agents if e["type"] == "agent" else skills).append(_stub_line(e))
            continue

        desc = e["description"]
        pairs = ", ".join(e["pairs_with"][:3]) if e["pairs_with"] else ""
        not_for = e.get("not_for", "")
        not_for_str = f" NOT: {not_for}" if not_for else ""

        if e["type"] == "agent":
            pairs_str = f" [{pairs}]" if pairs else ""
            trig_str = format_triggers(e, names["skill"])
            agents.append(f"  {name}{pairs_str} — {desc}{not_for_str}{trig_str}")
        else:
            force_str = " FORCE" if e.get("force_route") else ""
            agent_str = f" agent={e['agent']}" if e.get("agent") else ""
            cat_str = f" ({e['category']})" if e.get("category") else ""
            trig_str = format_triggers(e, names["agent"])
            skills.append(f"  {name}{force_str}{agent_str}{cat_str} — {desc}{not_for_str}{trig_str}")

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def format_compact(entries: list[dict]) -> str:
    """Format entries as a compact text manifest for LLM consumption.

    Two sections: agents (with paired skills) and skills. Both carry a trailing
    ``t:`` trigger field — the curated phrases are what let the router tell two
    same-domain entries apart, so they render here even though they cost bytes.
    One line per entry.
    """
    agents = []
    skills = []
    pipelines = []
    names = section_names(entries)

    for e in entries:
        name = e["name"]
        desc = e["description"]
        pairs = ", ".join(e["pairs_with"][:3]) if e["pairs_with"] else ""

        not_for = e.get("not_for", "")
        not_for_str = f" NOT: {not_for}" if not_for else ""

        if e["type"] == "agent":
            pairs_str = f" [{pairs}]" if pairs else ""
            trig_str = format_triggers(e, names["skill"])
            agents.append(f"  {name}{pairs_str} — {desc}{not_for_str}{trig_str}")
        elif e["type"] == "pipeline":
            pipelines.append(f"  {name} — {desc}")
        else:
            force_str = " FORCE" if e.get("force_route") else ""
            agent_str = f" agent={e['agent']}" if e.get("agent") else ""
            cat_str = f" ({e['category']})" if e.get("category") else ""
            trig_str = format_triggers(e, names["agent"])
            skills.append(f"  {name}{force_str}{agent_str}{cat_str} — {desc}{not_for_str}{trig_str}")

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def truncate_desc(desc: str, max_len: int = 60) -> str:
    """Truncate description to max_len chars, adding '...' if truncated."""
    if len(desc) <= max_len:
        return desc
    return desc[: max_len - 3] + "..."


def format_compact_mode(entries: list[dict], request_text: str = "") -> str:
    """Format entries in compact mode: truncated descriptions, conditional PIPELINES.

    PIPELINES section is omitted unless request_text contains 'pipeline'.
    """
    show_pipelines = "pipeline" in request_text.lower()

    agents = []
    skills = []
    pipelines = []

    for e in entries:
        name = e["name"]
        desc = truncate_desc(e["description"])
        pairs = ", ".join(e["pairs_with"][:3]) if e["pairs_with"] else ""

        not_for = e.get("not_for", "")
        not_for_str = f" NOT: {truncate_desc(not_for, 40)}" if not_for else ""

        if e["type"] == "agent":
            pairs_str = f" [{pairs}]" if pairs else ""
            agents.append(f"  {name}{pairs_str} — {desc}{not_for_str}")
        elif e["type"] == "pipeline":
            if show_pipelines:
                pipelines.append(f"  {name} — {desc}")
        else:
            force_str = " FORCE" if e.get("force_route") else ""
            agent_str = f" agent={e['agent']}" if e.get("agent") else ""
            cat_str = f" ({e['category']})" if e.get("category") else ""
            skills.append(f"  {name}{force_str}{agent_str}{cat_str} — {desc}{not_for_str}")

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate routing manifest for the /do router.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact mode: truncated descriptions, omit PIPELINES unless --request mentions pipeline",
    )
    parser.add_argument(
        "--request",
        type=str,
        default="",
        help="Request text (used with --compact to decide whether to include PIPELINES)",
    )
    parser.add_argument(
        "--tiered",
        action="store_true",
        help="Tiered mode (EXPERIMENT ONLY — rejected for production by two A/B runs, see module docstring): FULL lines for the live working set and force-route entries, one-line stubs otherwise",
    )
    args = parser.parse_args()

    try:
        entries = load_entries()

        if args.json:
            print(json.dumps(entries, indent=2))
        elif args.compact:
            print(format_compact_mode(entries, request_text=args.request))
        elif args.tiered:
            print(format_tiered(entries, load_working_set()))
        else:
            print(format_compact(entries))
    except Exception as exc:
        # Safe fallback: empty manifest so the router falls through gracefully.
        # Always print the cause so the failure is visible without debug flags.
        print(
            f"[routing-manifest] FALLBACK: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print("AGENTS:\n\nSKILLS:\n\nPIPELINES:")

    return 0


if __name__ == "__main__":
    sys.exit(main())
