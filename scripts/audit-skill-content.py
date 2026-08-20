#!/usr/bin/env python3
"""Audit SKILL.md files for non-runtime content.

Enforces docs/PHILOSOPHY.md "Skills Contain Execution Context Only".

A skill's body is what the LLM consumes at runtime. Install instructions,
license blocks, contributor lists, ethical-boundary declarations, and
"About" sections do not change what the model does next; they pollute the
runtime context. They belong in README.md, docs/, or CITATIONS.md.

Detection strategy:
  - Primary signal: H1/H2/H3 section headings whose text matches the
    suspect-heading regex. The section is the violation; we capture its
    line range so the maintainer can strip it cleanly.
  - Secondary signal: standalone content blocks (license headers, copyright
    lines) that are not embedded inside legitimate execution-context prose.
  - False-positive guards: a whitelist of legitimate heading words
    ("References", "Reference Loading Table", "Examples", "Calibration
    Examples") suppresses headings that look suspect but are part of the
    skill's runtime contract.

Severity:
  - HIGH:   ethical-boundaries / ethical-considerations / honest-limits /
            install-instructions (as dedicated section) / source-discipline
            (as dedicated section).
  - MEDIUM: license / credits / attribution / citation / provenance.
  - LOW:   "About" / "Author" sections, tangential philosophy framing.

Exit codes:
  0 = no high-severity violations
  1 = at least one high-severity violation
  2 = script error (bad path, IO failure, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------

# Heading-text patterns and their severity. Each entry is (regex, severity,
# match_reason). The regex is matched against the heading text only (after
# stripping the leading `#`s and surrounding whitespace), case-insensitive.
HEADING_RULES: list[tuple[re.Pattern[str], str, str]] = [
    # HIGH: ethical / honest-limits / install / source-discipline as sections.
    (
        re.compile(r"^\s*ethical\s+(boundaries|considerations|limits)\b", re.I),
        "high",
        "ethical-boundaries section",
    ),
    (
        re.compile(r"^\s*honest\s+limits?\b", re.I),
        "high",
        "honest-limits section",
    ),
    (
        re.compile(r"^\s*(installation|install\s+instructions)\b", re.I),
        "high",
        "installation section",
    ),
    (
        re.compile(r"^\s*source\s+discipline\b", re.I),
        "high",
        "source-discipline section",
    ),
    (
        re.compile(r"^\s*(what\s+this\s+(voice|skill)\s+cannot\s+claim|cannot\s+honestly\s+claim)", re.I),
        "high",
        "honest-limits framing",
    ),
    # MEDIUM: license / credits / attribution / citation / provenance.
    (
        re.compile(r"^\s*licen[cs]e\b", re.I),
        "medium",
        "license section",
    ),
    (
        re.compile(r"^\s*credits?\b", re.I),
        "medium",
        "credits section",
    ),
    (
        re.compile(r"^\s*attributions?\b", re.I),
        "medium",
        "attribution section",
    ),
    (
        re.compile(r"^\s*citations?\b", re.I),
        "medium",
        "citation section",
    ),
    (
        re.compile(r"^\s*provenance\b", re.I),
        "medium",
        "provenance section",
    ),
    (
        re.compile(r"^\s*contributing\b", re.I),
        "medium",
        "contributing section",
    ),
    # LOW: tangential framing.
    (
        re.compile(r"^\s*about(\s+(the\s+)?(author|skill|this))?\s*$", re.I),
        "low",
        "about section",
    ),
    (
        re.compile(r"^\s*authors?\b", re.I),
        "low",
        "author section",
    ),
    (
        re.compile(r"^\s*why\s+this\s+(skill\s+)?matters\b", re.I),
        "low",
        "why-this-matters framing",
    ),
    (
        re.compile(r"^\s*philosophy\b", re.I),
        "low",
        "philosophy section",
    ),
]

# Whitelist patterns: if the heading text matches one of these, it is NEVER
# a violation, even if a HEADING_RULES regex above also matches. The
# whitelist is checked first.
HEADING_WHITELIST: list[re.Pattern[str]] = [
    re.compile(r"^\s*references?\s*$", re.I),
    re.compile(r"^\s*reference\s+loading\s+table\b", re.I),
    re.compile(r"^\s*reference\s+material\b", re.I),
    re.compile(r"^\s*examples?\s*$", re.I),
    re.compile(r"^\s*(calibration|worked)\s+examples?\b", re.I),
    re.compile(r"^\s*example\s+\d", re.I),
    re.compile(r"^\s*phrase\s+fingerprints\b", re.I),
    # "Citation" inside a code-comment example or table cell is handled at
    # the line level; here we whitelist headings that contain "citations" as
    # part of a larger workflow phrase (e.g., "Citations / Sources Phase").
    re.compile(r"^\s*citations?\s*/\s*sources\b", re.I),
]

# Standalone content patterns: these match a single line that, by itself,
# strongly indicates non-runtime content. They are surfaced as MEDIUM-severity
# violations only when the surrounding section heading is NOT already flagged
# (to avoid duplicate reporting).
CONTENT_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"^\s*Copyright\s+\d{4}", re.I),
        "medium",
        "copyright line",
    ),
    (
        re.compile(r"^\s*MIT\s+License\b", re.I),
        "medium",
        "license header",
    ),
    (
        re.compile(r"^\s*Apache\s+License\b", re.I),
        "medium",
        "license header",
    ),
    (
        re.compile(r"^\s*BSD\s+(2|3)-Clause\b", re.I),
        "medium",
        "license header",
    ),
    (
        re.compile(r"^\s*Permission\s+is\s+hereby\s+granted", re.I),
        "high",
        "license boilerplate",
    ),
    (
        re.compile(r"^\s*npx\s+skills\s+add\b", re.I),
        "high",
        "skill-install command",
    ),
]

# A standalone install-command line (not in error handling). We require that
# the line is BARE (no surrounding prose) AND lives under a heading that
# names "Installation" (handled by HEADING_RULES) OR appears in a numbered
# list item that is the first thing under such a heading. We do NOT match
# `npm install` in arbitrary contextual prose because that is legitimate
# runtime guidance ("if not installed, advise user to run npm install").

SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """A single audit finding within a SKILL.md file."""

    skill_name: str
    skill_path: str
    line_range: tuple[int, int]  # 1-indexed, inclusive
    heading: str
    match_reason: str
    severity: str  # "high" | "medium" | "low"


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------


HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$")


@dataclass(frozen=True)
class Section:
    """One heading and the line range it owns."""

    level: int  # 1..6
    heading_text: str
    start_line: int  # 1-indexed line of the heading itself
    end_line: int  # 1-indexed; last line of the section (inclusive)


def parse_sections(lines: list[str]) -> list[Section]:
    """Walk the file and return every heading with its inclusive line range.

    A section ends at the next heading whose level is <= its own. Code
    fences (``` ... ```) are skipped so headings inside fenced blocks are
    not treated as real headings.
    """
    headings: list[tuple[int, str, int]] = []  # (level, text, line_index_0)
    in_fence = False
    for idx, raw in enumerate(lines):
        stripped = raw.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(raw)
        if not m:
            continue
        level = len(m.group("hashes"))
        text = m.group("text").strip()
        headings.append((level, text, idx))

    sections: list[Section] = []
    for i, (level, text, line0) in enumerate(headings):
        # Find next heading with level <= this one.
        end0 = len(lines) - 1
        for j in range(i + 1, len(headings)):
            other_level, _, other_line0 = headings[j]
            if other_level <= level:
                end0 = other_line0 - 1
                break
        sections.append(
            Section(
                level=level,
                heading_text=text,
                start_line=line0 + 1,
                end_line=end0 + 1,
            )
        )
    return sections


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def heading_is_whitelisted(text: str) -> bool:
    """Return True if the heading text matches any whitelist pattern."""
    return any(p.search(text) for p in HEADING_WHITELIST)


def classify_heading(text: str) -> tuple[str, str] | None:
    """Return (severity, match_reason) if heading is suspect, else None."""
    if heading_is_whitelisted(text):
        return None
    for pattern, severity, reason in HEADING_RULES:
        if pattern.search(text):
            return severity, reason
    return None


def audit_skill_file(path: Path, root: Path) -> list[Violation]:
    """Return every violation found inside one SKILL.md file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read {path}: {exc}") from exc

    lines = text.splitlines()
    sections = parse_sections(lines)
    skill_name = path.parent.name
    rel_path = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)

    violations: list[Violation] = []
    flagged_ranges: list[tuple[int, int]] = []

    # 1) Heading-based detection.
    for section in sections:
        verdict = classify_heading(section.heading_text)
        if verdict is None:
            continue
        severity, reason = verdict
        violations.append(
            Violation(
                skill_name=skill_name,
                skill_path=rel_path,
                line_range=(section.start_line, section.end_line),
                heading=section.heading_text,
                match_reason=reason,
                severity=severity,
            )
        )
        flagged_ranges.append((section.start_line, section.end_line))

    # 2) Content-pattern detection (skip lines already inside flagged sections).
    in_fence = False
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        # Don't double-flag inside fenced blocks (license-text-like prose
        # quoted as an illustration would otherwise fire).
        if in_fence:
            continue
        if any(start <= idx <= end for start, end in flagged_ranges):
            continue
        for pattern, severity, reason in CONTENT_RULES:
            if pattern.search(raw):
                # Find the nearest enclosing heading for context.
                heading = "(top of file)"
                for section in sections:
                    if section.start_line <= idx <= section.end_line:
                        heading = section.heading_text
                violations.append(
                    Violation(
                        skill_name=skill_name,
                        skill_path=rel_path,
                        line_range=(idx, idx),
                        heading=heading,
                        match_reason=reason,
                        severity=severity,
                    )
                )
                break  # one violation per line is enough

    return violations


def discover_skills(root: Path) -> list[Path]:
    """Return every `SKILL.md` at depth 1 or 2 under *root*."""
    if not root.exists():
        raise RuntimeError(f"skills root does not exist: {root}")
    if not root.is_dir():
        raise RuntimeError(f"skills root is not a directory: {root}")
    hits: set[Path] = set()
    for pattern in ("*/SKILL.md", "*/*/SKILL.md"):
        hits.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(hits)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def filter_by_severity(violations: list[Violation], minimum: str) -> list[Violation]:
    """Drop violations below the given severity floor."""
    threshold = SEVERITY_ORDER[minimum]
    return [v for v in violations if SEVERITY_ORDER[v.severity] >= threshold]


def render_markdown(
    violations: list[Violation],
    skills_scanned: int,
    severity_floor: str,
) -> str:
    """Render the aggregate report as Markdown."""
    out: list[str] = []
    out.append("# Skill Content Cleanliness Audit")
    out.append("")
    out.append(f"- Skills scanned: **{skills_scanned}**")
    out.append(f"- Violations found: **{len(violations)}** (severity >= {severity_floor})")

    by_sev: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for v in violations:
        by_sev[v.severity] = by_sev.get(v.severity, 0) + 1
    out.append(f"- Severity breakdown: high={by_sev['high']}, medium={by_sev['medium']}, low={by_sev['low']}")
    out.append("")

    if not violations:
        out.append("No violations. Skills are clean.")
        out.append("")
        return "\n".join(out)

    # Top violators.
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.skill_name] = counts.get(v.skill_name, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    out.append("## Top violators")
    out.append("")
    for skill, n in top:
        out.append(f"- `{skill}`: {n}")
    out.append("")

    # Group by skill and print full details.
    out.append("## Violations by skill")
    out.append("")
    by_skill: dict[str, list[Violation]] = {}
    for v in violations:
        by_skill.setdefault(v.skill_name, []).append(v)
    for skill in sorted(by_skill):
        out.append(f"### `{skill}`")
        out.append("")
        out.append("| Lines | Severity | Reason | Heading |")
        out.append("|-------|----------|--------|---------|")
        for v in sorted(by_skill[skill], key=lambda v: v.line_range[0]):
            lo, hi = v.line_range
            line_str = f"{lo}" if lo == hi else f"{lo}-{hi}"
            out.append(f"| {line_str} | {v.severity} | {v.match_reason} | `{v.heading}` |")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Audit SKILL.md files for non-runtime content.",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path("skills"),
        help="Skills directory root (default: ./skills)",
    )
    p.add_argument(
        "--severity",
        choices=("high", "medium", "low"),
        default="low",
        help="Minimum severity to report (default: low)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON instead of Markdown",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root.resolve()

    try:
        skill_paths = discover_skills(root)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    all_violations: list[Violation] = []
    for path in skill_paths:
        try:
            all_violations.extend(audit_skill_file(path, root))
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    filtered = filter_by_severity(all_violations, args.severity)

    if args.json:
        payload = {
            "skills_scanned": len(skill_paths),
            "severity_floor": args.severity,
            "violations": [asdict(v) for v in filtered],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_markdown(filtered, len(skill_paths), args.severity))

    has_high = any(v.severity == "high" for v in all_violations)
    return 1 if has_high else 0


if __name__ == "__main__":
    raise SystemExit(main())
