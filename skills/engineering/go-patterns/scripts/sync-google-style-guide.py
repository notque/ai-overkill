#!/usr/bin/env python3
"""Refresh the pinned, complete Google Go style guide snapshot."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib.request import urlopen

REVISION = "1809c769de31ba388c755ad15dd057a9ba8531fd"
DOCUMENTS = ("index.md", "guide.md", "decisions.md", "best-practices.md")
CHUNK_LINES = 400
BASE_URL = f"https://raw.githubusercontent.com/google/styleguide/{REVISION}/go"
DESTINATION = Path(__file__).resolve().parents[1] / "references" / "google-style-guide"


def write_document(destination: Path, name: str, content: bytes) -> list[Path]:
    """Write one source document directly or as ordered chunks."""
    lines = content.splitlines(keepends=True)
    direct = destination / name
    part_dir = destination / name.removesuffix(".md")
    if len(lines) <= CHUNK_LINES:
        if part_dir.exists():
            for stale in part_dir.glob("part-*.md"):
                stale.unlink()
            part_dir.rmdir()
        temporary = direct.with_suffix(".md.tmp")
        temporary.write_bytes(content)
        temporary.replace(direct)
        return [direct]

    direct.unlink(missing_ok=True)
    part_dir.mkdir(exist_ok=True)
    for stale in part_dir.glob("part-*.md"):
        stale.unlink()
    parts = []
    for number, offset in enumerate(range(0, len(lines), CHUNK_LINES), start=1):
        part = part_dir / f"part-{number:02d}.md"
        part.write_bytes(b"".join(lines[offset : offset + CHUNK_LINES]))
        parts.append(part)
    return parts


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    checksums = []
    load_order = ["# Google Go Style Guide load order", ""]
    for name in DOCUMENTS:
        for attempt in range(3):
            try:
                with urlopen(f"{BASE_URL}/{name}", timeout=60) as response:
                    content = response.read()
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        for part in write_document(DESTINATION, name, content):
            relative = part.relative_to(DESTINATION)
            load_order.append(f"- [{relative}]({relative})")
        checksums.append(f"{hashlib.sha256(content).hexdigest()}  {name}")

    (DESTINATION / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    (DESTINATION / "UPSTREAM_REVISION").write_text(REVISION + "\n", encoding="utf-8")
    (DESTINATION / "LOAD_ORDER.md").write_text("\n".join(load_order) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
