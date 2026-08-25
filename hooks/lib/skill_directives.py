"""Render Skill-tool calls only for installed, indexed skills."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _default_index_paths() -> tuple[Path, ...]:
    """Return the active runtime's authoritative skill index."""
    runtime_root = Path(__file__).absolute().parents[2]
    return (runtime_root / "skills" / "INDEX.json",)


@lru_cache(maxsize=8)
def _indexed_skill_names(index_paths: tuple[Path, ...]) -> frozenset[str]:
    names: set[str] = set()
    for path in index_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        entries = data.get("skills", data) if isinstance(data, dict) else data
        if isinstance(entries, dict):
            names.update(name for name in entries if isinstance(name, str))
        elif isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, str):
                    names.add(entry)
                elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    names.add(entry["name"])
    return frozenset(names)


def skill_call_directive(name: object, *, index_paths: tuple[Path, ...] | None = None) -> str | None:
    """Return the canonical call sentence for an indexed skill; fail closed."""
    if not isinstance(name, str) or not _SKILL_NAME.fullmatch(name):
        return None
    paths = index_paths if index_paths is not None else _default_index_paths()
    if name not in _indexed_skill_names(tuple(paths)):
        return None
    return f"Call the Skill tool with `{name}`."
