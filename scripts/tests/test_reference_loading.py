"""Pytest suite validating progressive disclosure reference loading for agents and skills.

Five agent test categories:
1. Reference Loading Table Completeness — every reference file has a table entry and vice-versa
2. Keyword-to-Reference Mapping Validation — query keywords resolve to correct reference files
3. Reference File Size Compliance — all reference files under 500 lines (warn at 400)
4. Joy-Check Spot Validation — flag negative framing in reference file headings
5. Cross-Agent Reference Isolation — no agent references files from another agent's directory

Two skill test categories (Categories 6-7):
6. Skill Reference File Size Compliance — all skills/*/references/**/*.md under 500 lines
7. Skill Reference File Existence — every skills/ directory can be discovered and scanned

Allowlist behavior (SKILL_REFS_STRICT env flag):
  Default (xfail mode): files in _KNOWN_OVERSIZED_SKILL_REFS xfail so CI stays green while
  the list serves as an authoritative TODO for gradual decomposition.
  Set SKILL_REFS_STRICT=1 to force all known violations to hard-fail — useful for audit runs.
  Any file NOT in the allowlist that exceeds 500 lines always hard-fails regardless of mode.

  _KNOWN_OVERSIZED_SKILL_REFS is the authoritative TODO list. Removing a file from the list
  without first decomposing it below 500 lines will cause that test to hard-fail.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import ClassVar

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"

# When SKILL_REFS_STRICT=1, pre-existing oversized skill files hard-fail instead of xfail.
# Default is xfail (warn mode) so CI stays green while the allowlist tracks decomposition work.
# Set SKILL_REFS_STRICT=1 for audit runs that should surface all violations as hard failures.
_SKILL_REFS_STRICT: bool = os.environ.get("SKILL_REFS_STRICT", "0") == "1"

REFERENCE_LINE_WARN = 400
REFERENCE_LINE_LIMIT = 500

NEGATIVE_FRAMING_WORDS = {"avoid", "don't", "never", "incorrect", "wrong", "bad", "anti-pattern"}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

REFERENCE_LOADING_TESTS: list[dict[str, object]] = [
    {
        "agent": "react-native-engineer",
        "query": "optimize FlashList scrolling performance",
        "expected_refs": ["list-performance.md"],
        "unexpected_refs": ["animation-patterns.md", "navigation-patterns.md"],
    },
    {
        "agent": "react-native-engineer",
        "query": "add smooth Reanimated gesture animations",
        "expected_refs": ["animation-patterns.md"],
        "unexpected_refs": ["list-performance.md"],
    },
    {
        "agent": "react-native-engineer",
        "query": "set up native stack navigation with deep links",
        "expected_refs": ["navigation-patterns.md"],
        "unexpected_refs": ["animation-patterns.md"],
    },
    {
        # "data fetching" also appears in the RSC row, so the query intentionally
        # avoids that phrase to test SWR→client-patterns specificity.
        "agent": "typescript-frontend-engineer",
        "query": "implement SWR client-side caching with request deduplication",
        "expected_refs": ["react-client-data-fetching.md"],
        "unexpected_refs": ["react-server-patterns.md", "react-composition-patterns.md"],
    },
    {
        "agent": "typescript-frontend-engineer",
        "query": "add ViewTransition animations between routes",
        "expected_refs": ["react-view-transitions.md"],
        "unexpected_refs": ["react-server-patterns.md"],
    },
    {
        "agent": "performance-optimization-engineer",
        "query": "eliminate async waterfall in API calls",
        "expected_refs": ["react-async-patterns.md"],
        "unexpected_refs": ["js-algorithm-optimizations.md"],
    },
    {
        "agent": "performance-optimization-engineer",
        "query": "optimize Set and Map lookups in hot loop",
        "expected_refs": ["js-algorithm-optimizations.md"],
        "unexpected_refs": ["react-async-patterns.md"],
    },
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReferenceTableEntry:
    """One row from an agent's reference loading table.

    Attributes:
        keywords: Trigger keywords from the first column (lowercased, comma-split).
        ref_file: Basename of the target reference file.
        raw_keywords: Raw first column text before splitting.
    """

    keywords: list[str]
    ref_file: str
    raw_keywords: str = field(repr=False)


@dataclass
class AgentReferenceInfo:
    """Parsed reference metadata for a single agent.

    Attributes:
        agent_name: Agent name (matches the .md filename stem).
        agent_file: Path to the agent .md file.
        refs_dir: Path to the agent's references/ directory (may not exist).
        table_entries: Rows parsed from the reference loading table.
        files_on_disk: Basenames of .md files found in refs_dir.
        has_table: Whether the agent has a keyword-based reference loading table.
    """

    agent_name: str
    agent_file: Path
    refs_dir: Path
    table_entries: list[ReferenceTableEntry]
    files_on_disk: list[str]
    has_table: bool


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_reference_loading_table(md_text: str) -> list[ReferenceTableEntry]:
    """Extract rows from an agent's reference loading table.

    Supports two header patterns:
    - ``| Task involves | Load reference |``
    - ``| Task Keywords | Reference File |`` (with optional extra columns)

    Args:
        md_text: Full markdown text of an agent file.

    Returns:
        List of ReferenceTableEntry. Empty list if no matching table found.
    """
    entries: list[ReferenceTableEntry] = []

    # Find table sections with headers matching known patterns.
    # Match a header row that contains both a keyword column and a file column.
    header_pattern = re.compile(
        r"^\|[^\n]*(?:task involves|task keywords)[^\n]*\|[^\n]*(?:load reference|reference file)[^\n]*\|",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in header_pattern.finditer(md_text):
        start = match.start()
        # Collect lines from this header forward until a blank line or non-table line
        block = md_text[start:]
        rows: list[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                rows.append(stripped)
            elif rows:
                # Stop at first non-table line after we've started collecting
                break

        # rows[0] = header, rows[1] = separator, rows[2:] = data rows
        if len(rows) < 3:
            continue

        for row in rows[2:]:
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if len(cells) < 2:
                continue
            keyword_col = cells[0]
            ref_col = cells[1]

            # Extract filename from markdown link or plain text
            link_match = re.search(r"\[([^\]]+\.md)\]", ref_col)
            if link_match:
                ref_filename = link_match.group(1)
            else:
                # Plain text — extract last path segment
                ref_filename = ref_col.strip().split("/")[-1].strip("`")

            if not ref_filename.endswith(".md"):
                continue

            # Split comma-separated keywords, strip whitespace, lowercase
            keywords = [kw.strip().lower() for kw in keyword_col.split(",") if kw.strip()]

            entries.append(
                ReferenceTableEntry(
                    keywords=keywords,
                    ref_file=ref_filename,
                    raw_keywords=keyword_col,
                )
            )

    return entries


def _load_agent_info(agent_name: str) -> AgentReferenceInfo:
    """Load reference metadata for a named agent.

    Args:
        agent_name: Agent stem name (e.g. ``react-native-engineer``).

    Returns:
        AgentReferenceInfo populated from the agent .md file and references/ directory.

    Raises:
        FileNotFoundError: If the agent .md file does not exist.
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file}")

    md_text = agent_file.read_text(encoding="utf-8")
    table_entries = _parse_reference_loading_table(md_text)

    refs_dir = AGENTS_DIR / agent_name / "references"
    files_on_disk: list[str] = []
    if refs_dir.exists():
        files_on_disk = [p.name for p in sorted(refs_dir.glob("*.md"))]

    return AgentReferenceInfo(
        agent_name=agent_name,
        agent_file=agent_file,
        refs_dir=refs_dir,
        table_entries=table_entries,
        files_on_disk=files_on_disk,
        has_table=len(table_entries) > 0,
    )


def _match_refs_for_query(query: str, entries: list[ReferenceTableEntry]) -> list[str]:
    """Return reference filenames whose keywords appear in the query.

    Each table entry is checked: if ANY of its keywords match the query as a
    whole word or phrase (using word boundaries), the entry's reference file
    is included. Word-boundary matching prevents short keywords like "min" or
    "map" from matching inside longer words like "eliminate" or "bitmap".

    Args:
        query: Free-text task description.
        entries: Reference loading table rows to match against.

    Returns:
        Deduplicated list of matched reference file basenames.
    """
    query_lower = query.lower()
    matched: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        for keyword in entry.keywords:
            if not keyword:
                continue
            # Use word-boundary anchors so "min" does not match "eliminate"
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, query_lower):
                if entry.ref_file not in seen:
                    matched.append(entry.ref_file)
                    seen.add(entry.ref_file)
                break

    return matched


def _collect_all_agents_with_refs() -> list[str]:
    """Return agent names that have a references/ subdirectory.

    Returns:
        Sorted list of agent name strings.
    """
    agents = []
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if agent_dir.is_dir() and (agent_dir / "references").exists():
            agents.append(agent_dir.name)
    return agents


# ---------------------------------------------------------------------------
# Category 1: Reference Loading Table Completeness
# ---------------------------------------------------------------------------


class TestReferenceLoadingTableCompleteness:
    """Every reference file on disk must have a table entry, and vice versa."""

    AGENTS_WITH_TABLES: ClassVar[list[str]] = [
        "react-native-engineer",
        "typescript-frontend-engineer",
        "performance-optimization-engineer",
    ]

    @pytest.mark.parametrize("agent_name", AGENTS_WITH_TABLES)
    def test_table_entries_point_to_existing_files(self, agent_name: str) -> None:
        """Each row in the reference loading table must point to a file that exists on disk.

        Args:
            agent_name: Agent under test.
        """
        info = _load_agent_info(agent_name)
        assert info.has_table, f"{agent_name}: no reference loading table found in agent markdown"

        missing: list[str] = []
        for entry in info.table_entries:
            ref_path = info.refs_dir / entry.ref_file
            if not ref_path.exists():
                missing.append(entry.ref_file)

        assert not missing, f"{agent_name}: table entries point to files that do not exist on disk:\n" + "\n".join(
            f"  - {f}" for f in missing
        )

    @pytest.mark.parametrize("agent_name", AGENTS_WITH_TABLES)
    def test_all_disk_files_have_table_entries(self, agent_name: str) -> None:
        """Every .md file in the references/ directory must appear in the loading table.

        Agents are expected to maintain complete tables. A file on disk with no
        table entry is dead — the agent will never load it.

        Args:
            agent_name: Agent under test.
        """
        info = _load_agent_info(agent_name)
        assert info.has_table, f"{agent_name}: no reference loading table found in agent markdown"

        table_files = {entry.ref_file for entry in info.table_entries}
        orphaned = [f for f in info.files_on_disk if f not in table_files]

        assert not orphaned, (
            f"{agent_name}: reference files on disk have no corresponding table entry "
            f"(agent will never load them):\n" + "\n".join(f"  - {f}" for f in orphaned)
        )

    @pytest.mark.parametrize("agent_name", AGENTS_WITH_TABLES)
    def test_table_has_at_least_one_entry(self, agent_name: str) -> None:
        """The reference loading table must contain at least one parseable row.

        Args:
            agent_name: Agent under test.
        """
        info = _load_agent_info(agent_name)
        assert len(info.table_entries) > 0, f"{agent_name}: reference loading table is empty"


# ---------------------------------------------------------------------------
# Category 2: Keyword-to-Reference Mapping Validation
# ---------------------------------------------------------------------------


def _build_test_id(case: dict[str, object]) -> str:
    """Build a readable pytest ID from a test case dict.

    Args:
        case: A dict from REFERENCE_LOADING_TESTS.

    Returns:
        String in the form ``agent-name::first 30 chars of query``.
    """
    agent = str(case["agent"])
    query = str(case["query"])[:30]
    return f"{agent}::{query}"


class TestKeywordToReferenceMappingValidation:
    """Keyword matching resolves to correct reference files for known queries."""

    @pytest.mark.parametrize("case", REFERENCE_LOADING_TESTS, ids=[_build_test_id(c) for c in REFERENCE_LOADING_TESTS])
    def test_expected_refs_are_matched(self, case: dict[str, object]) -> None:
        """The expected reference file(s) must be selected for the given query.

        Args:
            case: A test case dict with agent, query, expected_refs, unexpected_refs.
        """
        agent_name = str(case["agent"])
        query = str(case["query"])
        expected_refs: list[str] = list(case["expected_refs"])  # type: ignore[arg-type]

        info = _load_agent_info(agent_name)
        if not info.has_table:
            pytest.skip(f"{agent_name} has no reference loading table")

        matched = _match_refs_for_query(query, info.table_entries)

        missing_from_match = [r for r in expected_refs if r not in matched]
        assert not missing_from_match, (
            f"{agent_name}: query '{query}' did not match expected refs:\n"
            + "\n".join(f"  - {r}" for r in missing_from_match)
            + f"\n  Matched: {matched}"
        )

    @pytest.mark.parametrize("case", REFERENCE_LOADING_TESTS, ids=[_build_test_id(c) for c in REFERENCE_LOADING_TESTS])
    def test_unexpected_refs_are_not_matched(self, case: dict[str, object]) -> None:
        """Reference files listed as unexpected must not be selected for the query.

        Args:
            case: A test case dict with agent, query, expected_refs, unexpected_refs.
        """
        agent_name = str(case["agent"])
        query = str(case["query"])
        unexpected_refs: list[str] = list(case["unexpected_refs"])  # type: ignore[arg-type]

        info = _load_agent_info(agent_name)
        if not info.has_table:
            pytest.skip(f"{agent_name} has no reference loading table")

        matched = _match_refs_for_query(query, info.table_entries)

        false_positives = [r for r in unexpected_refs if r in matched]
        assert not false_positives, (
            f"{agent_name}: query '{query}' incorrectly matched refs that should NOT be selected:\n"
            + "\n".join(f"  - {r}" for r in false_positives)
            + f"\n  All matched: {matched}"
        )


# ---------------------------------------------------------------------------
# Category 3: Reference File Size Compliance
# ---------------------------------------------------------------------------


def _all_reference_files() -> list[Path]:
    """Collect every .md file under any agent's references/ directory.

    Returns:
        Sorted list of Path objects.
    """
    files: list[Path] = []
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        refs_dir = agent_dir / "references"
        if refs_dir.exists():
            files.extend(sorted(refs_dir.glob("*.md")))
    return files


def _ref_file_id(p: Path) -> str:
    """Return a short test ID for a reference file path.

    Args:
        p: Path to the reference file.

    Returns:
        String in the form ``agent-name/references/file.md``.
    """
    parts = p.parts
    # Find agents/ in the path and return the two-level suffix
    try:
        agents_idx = list(parts).index("agents")
        return "/".join(parts[agents_idx + 1 :])
    except ValueError:
        return p.name


ALL_REFERENCE_FILES = _all_reference_files()


_KNOWN_OVERSIZED: set[str] = {
    "hook-development-engineer/references/code-examples.md",
    "reviewer-domain/references/operational-preferred-patterns.md",
    "typescript-debugging-engineer/references/debugging-workflows.md",
    "typescript-frontend-engineer/references/react19-typescript-patterns.md",
    "typescript-frontend-engineer/references/typescript-preferred-patterns.md",
    "typescript-frontend-engineer/references/typescript-errors.md",
}


class TestReferenceFileSizeCompliance:
    """Reference files must be under 500 lines; warn at 400."""

    @pytest.mark.parametrize("ref_path", ALL_REFERENCE_FILES, ids=[_ref_file_id(p) for p in ALL_REFERENCE_FILES])
    def test_file_under_hard_limit(self, ref_path: Path) -> None:
        """Reference file must be under 500 lines.

        Pre-existing oversized files are tracked in _KNOWN_OVERSIZED and marked
        as xfail. New files that exceed the limit will hard-fail.

        Args:
            ref_path: Path to the reference .md file.
        """
        ref_id = _ref_file_id(ref_path)
        line_count = len(ref_path.read_text(encoding="utf-8").splitlines())
        if ref_id in _KNOWN_OVERSIZED:
            pytest.xfail(f"{ref_id}: {line_count} lines (known oversized, tracked as tech debt)")
        assert line_count <= REFERENCE_LINE_LIMIT, (
            f"{ref_id}: {line_count} lines exceeds limit of {REFERENCE_LINE_LIMIT}. "
            f"Split the file or remove stale content."
        )

    @pytest.mark.parametrize("ref_path", ALL_REFERENCE_FILES, ids=[_ref_file_id(p) for p in ALL_REFERENCE_FILES])
    def test_file_approaching_limit_warning(self, ref_path: Path) -> None:
        """Warn when a reference file is between 400 and 499 lines.

        Args:
            ref_path: Path to the reference .md file.
        """
        line_count = len(ref_path.read_text(encoding="utf-8").splitlines())
        if line_count >= REFERENCE_LINE_WARN:
            pytest.warns(
                UserWarning,
                match="approaching",
            ) if False else None  # soft warning — emit via xfail marker
            pytest.xfail(
                f"{_ref_file_id(ref_path)}: {line_count} lines is approaching the {REFERENCE_LINE_LIMIT}-line limit "
                f"(threshold: {REFERENCE_LINE_WARN}). Consider trimming."
            )


# ---------------------------------------------------------------------------
# Category 4: Joy-Check Spot Validation
# ---------------------------------------------------------------------------


def _heading_lines(md_text: str) -> list[str]:
    """Extract all ## heading lines from markdown text.

    Args:
        md_text: Raw markdown string.

    Returns:
        List of heading line strings (including the ## prefix).
    """
    return [line for line in md_text.splitlines() if re.match(r"^#{1,6}\s", line)]


class TestJoyCheckSpotValidation:
    """Reference file headings must not contain negative framing signals."""

    @pytest.mark.parametrize("ref_path", ALL_REFERENCE_FILES, ids=[_ref_file_id(p) for p in ALL_REFERENCE_FILES])
    def test_no_negative_framing_in_headings(self, ref_path: Path) -> None:
        """Flag headings containing negative framing words as warnings (not hard failures).

        Negative words: avoid, don't, never, incorrect, wrong, bad, anti-pattern.
        These signal problem-oriented rather than solution-oriented framing.

        Args:
            ref_path: Path to the reference .md file.
        """
        md_text = ref_path.read_text(encoding="utf-8")
        headings = _heading_lines(md_text)

        flagged: list[str] = []
        for heading in headings:
            heading_lower = heading.lower()
            for word in NEGATIVE_FRAMING_WORDS:
                if word in heading_lower:
                    flagged.append(heading.strip())
                    break

        if flagged:
            pytest.xfail(
                f"{_ref_file_id(ref_path)}: {len(flagged)} heading(s) contain negative framing signals "
                f"(warning, not hard failure):\n" + "\n".join(f"  - {h}" for h in flagged)
            )


# ---------------------------------------------------------------------------
# Category 5: Cross-Agent Reference Isolation
# ---------------------------------------------------------------------------


def _extract_reference_links(md_text: str) -> list[str]:
    """Extract all relative markdown link targets from an agent file.

    Args:
        md_text: Raw markdown text of an agent file.

    Returns:
        List of link target strings (the href portion of ``[text](href)``).
    """
    return re.findall(r"\]\(([^)]+\.md)\)", md_text)


class TestCrossAgentReferenceIsolation:
    """Each agent must only reference files within its own directory."""

    AGENTS_WITH_TABLES: ClassVar[list[str]] = [
        "react-native-engineer",
        "typescript-frontend-engineer",
        "performance-optimization-engineer",
        "ui-design-engineer",
    ]

    @pytest.mark.parametrize("agent_name", AGENTS_WITH_TABLES)
    def test_agent_references_are_self_contained(self, agent_name: str) -> None:
        """An agent's reference loading table must not link into another agent's directory.

        Shared patterns (e.g. ``skills/shared-patterns/``) are excluded from this check
        as they are intentionally cross-cutting.

        Args:
            agent_name: Agent under test.
        """
        info = _load_agent_info(agent_name)
        agent_prefix = f"{agent_name}/references/"

        cross_agent_refs: list[str] = []
        for entry in info.table_entries:
            # Reconstruct the full link target the table entry came from by checking
            # the raw agent markdown for this filename
            md_text = info.agent_file.read_text(encoding="utf-8")
            all_links = _extract_reference_links(md_text)

            for link in all_links:
                if entry.ref_file in link:
                    # Shared skills/ paths are allowed
                    if link.startswith("../skills/") or link.startswith("skills/"):
                        continue
                    # Links must point into this agent's own directory
                    if agent_prefix not in link and entry.ref_file in link:
                        # Check it doesn't belong to another known agent
                        for other_agent_dir in AGENTS_DIR.iterdir():
                            if other_agent_dir.is_dir() and other_agent_dir.name != agent_name:
                                if other_agent_dir.name in link:
                                    cross_agent_refs.append(f"{link!r} (in {agent_name})")

        assert not cross_agent_refs, f"{agent_name}: reference loading table contains cross-agent links:\n" + "\n".join(
            f"  - {r}" for r in cross_agent_refs
        )

    def test_all_agent_dirs_are_isolated_from_each_other(self) -> None:
        """No .md file in one agent's references/ directory should be symlinked
        or physically co-located in another agent's references/ directory.

        Args: none
        """
        agent_dirs = [d for d in AGENTS_DIR.iterdir() if d.is_dir()]
        violations: list[str] = []

        for agent_dir in sorted(agent_dirs):
            refs_dir = agent_dir / "references"
            if not refs_dir.exists():
                continue
            for ref_file in refs_dir.glob("*.md"):
                # Check that this file's resolved path is actually inside this agent's dir
                try:
                    resolved = ref_file.resolve()
                    if not str(resolved).startswith(str(agent_dir.resolve())):
                        violations.append(f"{ref_file} resolves outside its agent dir to {resolved}")
                except OSError:
                    pass

        assert not violations, "Cross-agent reference isolation violated:\n" + "\n".join(f"  - {v}" for v in violations)


# ---------------------------------------------------------------------------
# Skill reference helpers
# ---------------------------------------------------------------------------


def _collect_all_skill_reference_files(skills_dir: Path = SKILLS_DIR) -> list[Path]:
    """Collect every .md file under any skill's references/ directory, recursively.

    Skills may have nested sub-directories inside references/ (e.g.
    go-patterns/references/sapcc-conventions/). All .md files at any depth
    are included so that deeply nested oversized files are caught.

    Returns:
        Sorted list of Path objects for every .md file under skills/*/references/.
    """
    files: list[Path] = []
    if not skills_dir.exists():
        return files
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        refs_dir = skill_file.parent / "references"
        if refs_dir.exists():
            files.extend(sorted(refs_dir.rglob("*.md")))
    return files


def _skill_ref_file_id(p: Path) -> str:
    """Return a short test ID for a skill reference file path.

    Args:
        p: Path to the skill reference file.

    Returns:
        String relative to the skills/ directory, e.g.
        ``docs-sync-checker/references/examples.md`` or
        ``go-patterns/references/sapcc-conventions/sapcc-code-patterns.md``.
    """
    try:
        return str(p.relative_to(SKILLS_DIR))
    except ValueError:
        return p.name


def _collect_skills_with_references(skills_dir: Path = SKILLS_DIR) -> list[Path]:
    """Return skill directories that have a references/ subdirectory.

    Returns:
        Sorted list of skill directories.
    """
    if not skills_dir.exists():
        return []
    return sorted(
        skill_file.parent for skill_file in skills_dir.rglob("SKILL.md") if (skill_file.parent / "references").exists()
    )


ALL_SKILL_REFERENCE_FILES: list[Path] = _collect_all_skill_reference_files()

# Pre-existing oversized skill reference files, baselined on 2026-07-09.
#
# This is the authoritative dated debt register for gradual decomposition. Each entry xfails by
# default so CI stays green while decomposition work proceeds. The invariant below rejects both
# unregistered oversized files and stale exemptions, so a new violation cannot be hidden here.
#
# Set SKILL_REFS_STRICT=1 to force all entries to hard-fail for a decomposition audit.
_KNOWN_OVERSIZED_SKILL_REFS: dict[str, str] = {
    "engineering/go-patterns/references/sapcc-conventions.md": "2026-07-09",
    "engineering/go-patterns/references/sapcc-conventions/api-design-detailed.md": "2026-07-09",
    "engineering/go-patterns/references/sapcc-conventions/architecture-patterns.md": "2026-07-09",
    "engineering/go-patterns/references/sapcc-conventions/build-ci-detailed.md": "2026-07-09",
    "engineering/go-patterns/references/sapcc-conventions/error-handling-detailed.md": "2026-07-09",
    "engineering/go-patterns/references/sapcc-conventions/sapcc-code-patterns.md": "2026-07-09",
    "frontend/distinctive-frontend-design/references/animation-patterns.md": "2026-07-09",
    "frontend/distinctive-frontend-design/references/shader-integration-react.md": "2026-07-09",
    "frontend/threejs-builder/references/react-three-fiber.md": "2026-07-09",
    "frontend/threejs-builder/references/visual-polish.md": "2026-07-09",
    "frontend/threejs-builder/references/webgpu.md": "2026-07-09",
    "frontend/webgl-card-effects/references/shader-integration-react.md": "2026-07-09",
    "meta/skill-composer/references/examples.md": "2026-07-09",
    "meta/skill-creator/references/agent-template.md": "2026-07-09",
    "process/condition-based-waiting/references/implementation-patterns.md": "2026-07-09",
    "process/pr-workflow/references/commit-staging-rules.md": "2026-07-09",
    "process/pr-workflow/references/miner.md": "2026-07-09",
    "process/pr-workflow/references/pipeline.md": "2026-07-09",
    "process/verification-before-completion/references/verification-examples.md": "2026-07-09",
    "testing/test-driven-development/references/examples.md": "2026-07-09",
    "testing/testing-preferred-patterns/references/preferred-pattern-catalog.md": "2026-07-09",
    "workflow/references/comprehensive-review.md": "2026-07-09",
    "workflow/references/domain-research.md": "2026-07-09",
    "workflow/references/pipeline-scaffolder/references/pipeline-spec-format.md": "2026-07-09",
    "workflow/references/toolkit-improvement.md": "2026-07-09",
    "workflow/references/workflow-orchestrator/references/task-patterns.md": "2026-07-09",
}

_SKILLS_WITH_REFERENCES: list[str] = _collect_skills_with_references()

# ---------------------------------------------------------------------------
# Category 6: Skill Reference File Size Compliance
# ---------------------------------------------------------------------------


class TestSkillReferenceFileSizeCompliance:
    """Skill reference files must be under 500 lines; warn at 400.

    This is the same standard applied to agent reference files (Category 3).
    Skills were previously unguarded — ADR-190 extends coverage to close that gap.

    By default (xfail mode) files in _KNOWN_OVERSIZED_SKILL_REFS xfail so CI stays green
    while the allowlist tracks gradual decomposition. Any file NOT in the allowlist that
    exceeds 500 lines hard-fails immediately. Set SKILL_REFS_STRICT=1 to force all known
    violations to hard-fail for audit runs.
    """

    @pytest.mark.parametrize(
        "ref_path",
        ALL_SKILL_REFERENCE_FILES,
        ids=[_skill_ref_file_id(p) for p in ALL_SKILL_REFERENCE_FILES],
    )
    def test_skill_file_under_hard_limit(self, ref_path: Path) -> None:
        """Skill reference file must be under 500 lines.

        Pre-existing violations are tracked in _KNOWN_OVERSIZED_SKILL_REFS.
        By default they xfail so CI stays green during gradual decomposition.
        Set SKILL_REFS_STRICT=1 to force all known violations to hard-fail.
        New files not in the allowlist that exceed the limit always hard-fail.

        Args:
            ref_path: Path to the skill reference .md file.
        """
        ref_id = _skill_ref_file_id(ref_path)
        line_count = len(ref_path.read_text(encoding="utf-8").splitlines())

        if ref_id in _KNOWN_OVERSIZED_SKILL_REFS:
            if not _SKILL_REFS_STRICT:
                pytest.xfail(
                    f"skills/{ref_id}: {line_count} lines (known oversized, tracked as tech debt — "
                    f"set SKILL_REFS_STRICT=1 or remove from _KNOWN_OVERSIZED_SKILL_REFS after decomposing)"
                )
            # Strict mode: fall through to the assertion so CI sees a hard failure.
            assert line_count <= REFERENCE_LINE_LIMIT, (
                f"skills/{ref_id}: {line_count} lines exceeds limit of {REFERENCE_LINE_LIMIT}. "
                f"This is a pre-existing violation (ADR-190 Finding 4). "
                f"Decompose the file into sub-references under 500 lines, then remove it from "
                f"_KNOWN_OVERSIZED_SKILL_REFS in this test file."
            )
        else:
            assert line_count <= REFERENCE_LINE_LIMIT, (
                f"skills/{ref_id}: {line_count} lines exceeds limit of {REFERENCE_LINE_LIMIT}. "
                f"Split the file or remove stale content. "
                f"Do not add this file to _KNOWN_OVERSIZED_SKILL_REFS — fix it instead."
            )

    def test_legacy_size_debt_matches_current_violations(self) -> None:
        """Every exception is dated, still oversized, and no new violation is hidden."""
        actual_violations = {
            _skill_ref_file_id(path)
            for path in ALL_SKILL_REFERENCE_FILES
            if len(path.read_text(encoding="utf-8").splitlines()) > REFERENCE_LINE_LIMIT
        }
        registered = set(_KNOWN_OVERSIZED_SKILL_REFS)

        invalid_dates = [
            f"{ref_id} ({baseline_date})"
            for ref_id, baseline_date in _KNOWN_OVERSIZED_SKILL_REFS.items()
            if _parse_baseline_date(baseline_date) is None
        ]
        assert not invalid_dates, "Invalid legacy-debt dates:\n" + "\n".join(invalid_dates)
        assert actual_violations == registered, (
            "Reference-size debt register drifted. New violations must be decomposed; resolved "
            "violations must be removed from the register.\n"
            f"Unregistered: {sorted(actual_violations - registered)}\n"
            f"Stale: {sorted(registered - actual_violations)}"
        )

    @pytest.mark.parametrize(
        "ref_path",
        ALL_SKILL_REFERENCE_FILES,
        ids=[_skill_ref_file_id(p) for p in ALL_SKILL_REFERENCE_FILES],
    )
    def test_skill_file_approaching_limit_warning(self, ref_path: Path) -> None:
        """Warn when a skill reference file is between 400 and 499 lines.

        Args:
            ref_path: Path to the skill reference .md file.
        """
        line_count = len(ref_path.read_text(encoding="utf-8").splitlines())
        if line_count >= REFERENCE_LINE_WARN:
            pytest.xfail(
                f"skills/{_skill_ref_file_id(ref_path)}: {line_count} lines is approaching the "
                f"{REFERENCE_LINE_LIMIT}-line limit (threshold: {REFERENCE_LINE_WARN}). "
                f"Consider trimming or splitting before it exceeds the hard limit."
            )


# ---------------------------------------------------------------------------
# Category 7: Skill Reference Directory Discoverability
# ---------------------------------------------------------------------------


class TestSkillReferenceDirectoryDiscoverability:
    """Every skill with a references/ directory must be discoverable and non-empty.

    This is a structural sanity check — it catches skills whose references/
    directory exists but contains no .md files (empty directory, only non-md
    files, or broken symlinks). An empty references/ dir provides no value
    and may indicate an incomplete scaffold.
    """

    @pytest.mark.parametrize(
        "skill_dir",
        _SKILLS_WITH_REFERENCES,
        ids=[str(path.relative_to(SKILLS_DIR)) for path in _SKILLS_WITH_REFERENCES],
    )
    def test_skill_references_dir_contains_md_files(self, skill_dir: Path) -> None:
        """A skill's references/ directory must contain at least one .md file.

        An empty references/ directory is dead weight — either populate it or
        remove it so the skill body does not declare references that cannot load.

        Args:
            skill_dir: Skill directory under skills/.
        """
        refs_dir = skill_dir / "references"
        md_files = list(refs_dir.rglob("*.md"))
        assert md_files, (
            f"{skill_dir.relative_to(REPO_ROOT)}/references/ exists but contains no .md files. "
            f"Either add reference content or remove the empty directory."
        )


def _parse_baseline_date(value: str) -> date | None:
    """Return a valid ISO-8601 baseline date, or None for malformed entries."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def test_skill_reference_discovery_includes_nested_skill_directories(tmp_path: Path) -> None:
    """A category-nested skill and its nested references are both discoverable."""
    skills_dir = tmp_path / "skills"
    nested_reference = skills_dir / "testing" / "demo" / "references" / "examples" / "case.md"
    nested_reference.parent.mkdir(parents=True)
    nested_reference.write_text("# Case\n", encoding="utf-8")
    (nested_reference.parents[2] / "SKILL.md").write_text("# Demo\n", encoding="utf-8")

    assert _collect_all_skill_reference_files(skills_dir) == [nested_reference]
    assert _collect_skills_with_references(skills_dir) == [nested_reference.parents[2]]
