"""Repository-wide invariants for Skill-tool call instructions."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

from scripts.lib.frontmatter import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOTS = ("agents", "commands", "docs", "hooks", "skills")
RUNTIME_SUFFIXES = {".js", ".md", ".mjs", ".py"}
CONCRETE_CALL = re.compile(r"(?i)call the Skill tool with `([a-z0-9][a-z0-9-]*)`")
LEGACY_ACTION = re.compile(
    r"(?i)\b(?:"
    r"(?:invoke|run|follow)\s+(?:the\s+)?"
    r"`(?P<direct_name>[a-z0-9][a-z0-9-]*)(?:\s+--[^`]*)?`(?:\s+skill(?:'s)?)?"
    r"|(?:use|load)\s+(?:the\s+)?"
    r"`(?P<labelled_name>[a-z0-9][a-z0-9-]*)(?:\s+--[^`]*)?`\s+skill(?:'s)?"
    r")(?=\s|[.,:;—)\]]|$)"
)

# These are evidence or routing-scope descriptions, not runtime instructions.
# Keep this allowlist narrow and content-addressed by path + component name so a
# new handoff cannot inherit an exemption through nearby wording.
LEGACY_NON_ACTION_ALLOWLIST = {
    (
        "skills/infrastructure/shell-process-patterns/references/preferred-patterns.md",
        "public-web-deploy",
    ): "dated incident evidence; changing it would rewrite the recorded failure",
    (
        "skills/meta/html-artifact/SPEC.md",
        "distinctive-frontend-design",
    ): "scope exclusion, not an execution step",
    (
        "skills/research/markdown-converter/SKILL.md",
        "video-transcript",
    ): "descriptive format-routing exclusion; the optional skill is not in this repository index",
}


def _runtime_files() -> list[Path]:
    files: list[Path] = []
    for root_name in RUNTIME_ROOTS:
        root = REPO_ROOT / root_name
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in RUNTIME_SUFFIXES and "tests" not in path.parts
        )
    return sorted(files)


def _actionable_legacy_handoffs(source: str) -> list[re.Match[str]]:
    """Find imperative skill handoffs outside frontmatter and fenced examples."""
    matches: list[re.Match[str]] = []
    in_frontmatter = source.startswith("---\n")
    in_fence = False
    offset = 0
    for line in source.splitlines(keepends=True):
        stripped = line.lstrip()
        if in_frontmatter:
            if offset and stripped.startswith("---"):
                in_frontmatter = False
            offset += len(line)
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            offset += len(line)
            continue
        if not in_fence:
            matches.extend(LEGACY_ACTION.finditer(source, offset, offset + len(line)))
        offset += len(line)
    return matches


def _legacy_name(match: re.Match[str]) -> str:
    """Return the component captured by either legacy-action branch."""
    return match.group("direct_name") or match.group("labelled_name")


def test_concrete_skill_calls_are_canonical_and_indexed() -> None:
    indexed = set(json.loads((REPO_ROOT / "skills/INDEX.json").read_text(encoding="utf-8"))["skills"])
    failures: list[str] = []

    for path in _runtime_files():
        source = path.read_text(encoding="utf-8")
        for match in CONCRETE_CALL.finditer(source):
            name = match.group(1)
            rendered = source[match.start() : match.end() + 1]
            expected = f"Call the Skill tool with `{name}`."
            if rendered != expected:
                failures.append(f"{path.relative_to(REPO_ROOT)}: non-canonical call {rendered!r}")
            if name not in indexed:
                failures.append(f"{path.relative_to(REPO_ROOT)}: {name!r} is not an indexed skill")

    assert failures == []


def test_commands_with_skill_calls_grant_skill_tool() -> None:
    failures: list[str] = []
    for path in sorted((REPO_ROOT / "commands").glob("*.md")):
        source = path.read_text(encoding="utf-8")
        if not CONCRETE_CALL.search(source):
            continue
        frontmatter, _ = parse_frontmatter(source)
        tools = frontmatter.get("allowed-tools", []) if frontmatter else []
        if "Skill" not in tools:
            failures.append(str(path.relative_to(REPO_ROOT)))
    assert failures == []


def test_command_skill_handoffs_use_exact_calls() -> None:
    legacy = re.compile(
        r"(?i)(?:read|load) and follow (?:the )?(?:full )?skill(?: file)? at|invoke the [a-z0-9-]+ skill"
    )
    failures: list[str] = []
    for path in sorted((REPO_ROOT / "commands").glob("*.md")):
        if legacy.search(path.read_text(encoding="utf-8")):
            failures.append(str(path.relative_to(REPO_ROOT)))
    assert failures == []


def test_actionable_named_skill_handoffs_do_not_use_legacy_wording() -> None:
    indexed = set(json.loads((REPO_ROOT / "skills/INDEX.json").read_text(encoding="utf-8"))["skills"])
    failures: list[str] = []
    for path in _runtime_files():
        source = path.read_text(encoding="utf-8")
        for match in _actionable_legacy_handoffs(source):
            # A backticked active skill is actionable even when prose omits the
            # word "skill". Retired/unindexed names remain actionable when the
            # prose explicitly labels them as skills, so stale handoffs cannot
            # evade the guard merely by disappearing from INDEX.json.
            name = _legacy_name(match)
            explicitly_skill = re.search(r"\bskill(?:'s)?$", match.group(0), re.IGNORECASE)
            if name not in indexed and explicitly_skill is None:
                continue
            relative = str(path.relative_to(REPO_ROOT))
            if (relative, name) in LEGACY_NON_ACTION_ALLOWLIST:
                continue
            failures.append(f"{relative}: {match.group(0).strip()}")
    assert failures == []


def test_legacy_handoff_detector_handles_markdown_action_contexts() -> None:
    source = """\
**Step 1**: Invoke the `workflow` skill.
After validation passes, run the `condense` skill.
- Recovery: follow `planning` skill.
For this task, use the `joy-check` skill.
1. Load `read-only-ops` skill first.
**Step 2**: Run `routing-table-updater` after generation.
"""
    assert [_legacy_name(match) for match in _actionable_legacy_handoffs(source)] == [
        "workflow",
        "condense",
        "planning",
        "joy-check",
        "read-only-ops",
        "routing-table-updater",
    ]


def test_legacy_handoff_detector_ignores_frontmatter_and_fenced_history() -> None:
    source = """\
---
not_for: use the `workflow` skill instead
---
```text
Historical bad example: Invoke the `planning` skill.
```
"""
    assert _actionable_legacy_handoffs(source) == []


def test_legacy_non_action_allowlist_is_narrow_and_current() -> None:
    observed: set[tuple[str, str]] = set()
    for relative, name in LEGACY_NON_ACTION_ALLOWLIST:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        observed.update(
            (relative, _legacy_name(match))
            for match in _actionable_legacy_handoffs(source)
            if _legacy_name(match) == name
        )
    assert observed == set(LEGACY_NON_ACTION_ALLOWLIST)


def test_actionable_pipeline_handoffs_route_through_workflow() -> None:
    skill_index = set(json.loads((REPO_ROOT / "skills/INDEX.json").read_text(encoding="utf-8"))["skills"])
    pipeline_index = set(
        json.loads((REPO_ROOT / "skills/workflow/references/pipeline-index.json").read_text(encoding="utf-8"))[
            "pipelines"
        ]
    )
    pipeline_only = pipeline_index - skill_index
    failures: list[str] = []

    for path in _runtime_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name in pipeline_only:
                handoff = re.compile(
                    rf"(?i)\b(?:hand off to|invoke(?::| the)?|route to|follow(?: the)?)\s+"
                    rf"(?:/)?`?{re.escape(name)}`?(?![a-z0-9-])"
                )
                if handoff.search(line):
                    failures.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {name}")
    assert failures == []


def test_companion_generator_freshness_is_ci_gated() -> None:
    workflow = (REPO_ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    assert "python scripts/add-companion-skills.py --check" in workflow


def test_debug_error_remediation_uses_indexed_workflow_skill(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "hooks/lib"))
    default_fix_actions = importlib.import_module("learning_db_v2").DEFAULT_FIX_ACTIONS

    for error_type in ("syntax_error", "type_error"):
        assert default_fix_actions[error_type] == {"fix_type": "skill", "fix_action": "workflow"}
