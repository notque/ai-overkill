"""Tests for audit-skill-content.py.

Covers happy path (clean skill -> 0 violations), per-category detection,
false-positive guards (References / Examples / Reference Loading Table),
severity assignment, and exit-code semantics.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load the hyphenated script as a module via importlib.
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "audit-skill-content.py"
_spec = importlib.util.spec_from_file_location("audit_skill_content", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_skill_content"] = audit
_spec.loader.exec_module(audit)


# ---- Helpers ----------------------------------------------------------------


def make_skill(root: Path, name: str, body: str) -> Path:
    """Create a skill directory with a SKILL.md containing `body`."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(body, encoding="utf-8")
    return skill_path


CLEAN_SKILL = """---
name: clean-skill
description: A skill with only runtime content.
---

# Clean Skill

One-paragraph overview the model reads at invocation.

## Instructions

### Step 1: Do the thing

Concrete steps here.

### Step 2: Verify

More concrete steps.

## Reference Loading Table

| Signal | Load |
|--------|------|
| foo    | references/foo.md |

## References

- `references/foo.md` -- domain depth.

## Examples

### Example 1: Simple case

A worked example.
"""


# ---- Happy path -------------------------------------------------------------


def test_clean_skill_produces_no_violations(tmp_path: Path) -> None:
    """A skill with only runtime content has no findings."""
    make_skill(tmp_path, "clean", CLEAN_SKILL)
    skill_paths = audit.discover_skills(tmp_path)
    assert len(skill_paths) == 1

    violations = audit.audit_skill_file(skill_paths[0], tmp_path)
    assert violations == [], f"unexpected violations: {violations}"


# ---- Detection cases --------------------------------------------------------


def test_detects_installation_section_as_high(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Installation\n\nRun `npm install`.\n"
    make_skill(tmp_path, "with-install", body)
    violations = audit.audit_skill_file(tmp_path / "with-install" / "SKILL.md", tmp_path)
    severities = {v.severity for v in violations}
    reasons = {v.match_reason for v in violations}
    assert "high" in severities
    assert any("installation" in r for r in reasons)


def test_detects_license_section_as_medium(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## License\n\nMIT License -- see LICENSE.\n"
    make_skill(tmp_path, "with-license", body)
    violations = audit.audit_skill_file(tmp_path / "with-license" / "SKILL.md", tmp_path)
    assert any(v.severity == "medium" and "license" in v.match_reason for v in violations)


def test_detects_credits_section_as_medium(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Credits\n\nThanks to Alice and Bob.\n"
    make_skill(tmp_path, "with-credits", body)
    violations = audit.audit_skill_file(tmp_path / "with-credits" / "SKILL.md", tmp_path)
    assert any(v.severity == "medium" and "credits" in v.match_reason for v in violations)


def test_detects_attribution_section_as_medium(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Attribution\n\nBased on prior art by X.\n"
    make_skill(tmp_path, "with-attribution", body)
    violations = audit.audit_skill_file(tmp_path / "with-attribution" / "SKILL.md", tmp_path)
    assert any(v.severity == "medium" and "attribution" in v.match_reason for v in violations)


def test_detects_ethical_boundaries_section_as_high(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Ethical Boundaries\n\nDo not use this for X.\n"
    make_skill(tmp_path, "with-ethics", body)
    violations = audit.audit_skill_file(tmp_path / "with-ethics" / "SKILL.md", tmp_path)
    assert any(v.severity == "high" and "ethical" in v.match_reason for v in violations)


def test_detects_honest_limits_section_as_high(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Honest Limits\n\nThis voice cannot honestly claim X.\n"
    make_skill(tmp_path, "with-honest", body)
    violations = audit.audit_skill_file(tmp_path / "with-honest" / "SKILL.md", tmp_path)
    assert any(v.severity == "high" and "honest" in v.match_reason for v in violations)


def test_detects_source_discipline_section_as_high(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Source Discipline\n\nOnly cite primary sources.\n"
    make_skill(tmp_path, "with-discipline", body)
    violations = audit.audit_skill_file(tmp_path / "with-discipline" / "SKILL.md", tmp_path)
    assert any(v.severity == "high" and "source-discipline" in v.match_reason for v in violations)


def test_detects_about_section_as_low(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## About\n\nThis skill was authored in 2024.\n"
    make_skill(tmp_path, "with-about", body)
    violations = audit.audit_skill_file(tmp_path / "with-about" / "SKILL.md", tmp_path)
    assert any(v.severity == "low" and "about" in v.match_reason for v in violations)


def test_detects_philosophy_section_as_low(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n## Philosophy\n\nWhy this matters in the broader sense.\n"
    make_skill(tmp_path, "with-philosophy", body)
    violations = audit.audit_skill_file(tmp_path / "with-philosophy" / "SKILL.md", tmp_path)
    assert any(v.severity == "low" and "philosophy" in v.match_reason for v in violations)


def test_detects_copyright_line_as_medium(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n\nCopyright 2024 ACME Corp.\n"
    make_skill(tmp_path, "with-copyright", body)
    violations = audit.audit_skill_file(tmp_path / "with-copyright" / "SKILL.md", tmp_path)
    assert any(v.severity == "medium" and "copyright" in v.match_reason for v in violations)


def test_detects_license_boilerplate_as_high(tmp_path: Path) -> None:
    body = CLEAN_SKILL + "\n\nPermission is hereby granted, free of charge, ...\n"
    make_skill(tmp_path, "with-boilerplate", body)
    violations = audit.audit_skill_file(tmp_path / "with-boilerplate" / "SKILL.md", tmp_path)
    assert any(v.severity == "high" and "license" in v.match_reason for v in violations)


# ---- False-positive guards --------------------------------------------------


def test_references_section_is_not_flagged(tmp_path: Path) -> None:
    """`## References` listing reference files is execution-context."""
    body = """---
name: ok
description: ok
---

# Ok Skill

## Instructions
Do stuff.

## References
- `references/foo.md`
- `references/bar.md`
"""
    make_skill(tmp_path, "ok", body)
    v = audit.audit_skill_file(tmp_path / "ok" / "SKILL.md", tmp_path)
    assert v == [], v


def test_reference_loading_table_is_not_flagged(tmp_path: Path) -> None:
    body = """---
name: ok
description: ok
---

# Ok

## Reference Loading Table
| Signal | Load |
|--------|------|
| x      | y    |
"""
    make_skill(tmp_path, "ok", body)
    v = audit.audit_skill_file(tmp_path / "ok" / "SKILL.md", tmp_path)
    assert v == [], v


def test_examples_and_calibration_examples_are_not_flagged(tmp_path: Path) -> None:
    body = """---
name: ok
description: ok
---

# Ok

## Examples

### Example 1: Foo

text

## Calibration Examples

### Example 2: Bar

text
"""
    make_skill(tmp_path, "ok", body)
    v = audit.audit_skill_file(tmp_path / "ok" / "SKILL.md", tmp_path)
    assert v == [], v


def test_contextual_npm_install_in_prose_is_not_flagged(tmp_path: Path) -> None:
    """`npm install` mentioned inside error-handling prose is legitimate."""
    body = """---
name: ok
description: ok
---

# Ok

## Error Handling

If vitest is missing, advise the user to run `npm install -D vitest` and re-run.
"""
    make_skill(tmp_path, "ok", body)
    v = audit.audit_skill_file(tmp_path / "ok" / "SKILL.md", tmp_path)
    assert v == [], v


def test_copyright_inside_code_fence_is_not_flagged(tmp_path: Path) -> None:
    """Code-fenced examples (e.g., showing what to skip) are legitimate."""
    body = """---
name: ok
description: ok
---

# Ok

## Instructions

Skip lines like:

```
Copyright 2024 ACME
```

That's an example of what to ignore.
"""
    make_skill(tmp_path, "ok", body)
    v = audit.audit_skill_file(tmp_path / "ok" / "SKILL.md", tmp_path)
    assert v == [], v


# ---- Section line-range capture --------------------------------------------


def test_violation_captures_section_line_range(tmp_path: Path) -> None:
    """The violation's line_range covers heading through end of section."""
    body = """---
name: x
description: x
---

# X

## Instructions
Do stuff.

## License

MIT License -- see LICENSE.

Copyright 2024 X.

## Other

Tail content.
"""
    make_skill(tmp_path, "x", body)
    violations = audit.audit_skill_file(tmp_path / "x" / "SKILL.md", tmp_path)
    license_v = next(v for v in violations if v.match_reason == "license section")
    lo, hi = license_v.line_range
    assert lo < hi
    # The range must start at the License heading and stop before the next H2.
    lines = (tmp_path / "x" / "SKILL.md").read_text().splitlines()
    assert lines[lo - 1].startswith("## License")
    # Next H2 sits at line hi+1.
    assert lines[hi].startswith("## Other"), f"expected '## Other' at line {hi + 1}, got {lines[hi]!r}"
    # The license body content (MIT License line, Copyright line) must be inside the range.
    body_text = "\n".join(lines[lo - 1 : hi])
    assert "MIT License" in body_text
    assert "Copyright 2024" in body_text


# ---- CLI / main() -----------------------------------------------------------


def test_main_returns_zero_when_no_high_violations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    make_skill(tmp_path, "clean", CLEAN_SKILL)
    rc = audit.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "Skills scanned" in out
    assert "No violations" in out


def test_main_returns_one_on_high_violation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    make_skill(tmp_path, "bad", CLEAN_SKILL + "\n## Installation\nRun stuff.\n")
    rc = audit.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "installation" in out.lower()


def test_main_returns_zero_when_only_medium_violations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit 0 unless a HIGH violation is present (regardless of severity floor reported)."""
    make_skill(tmp_path, "med", CLEAN_SKILL + "\n## License\nMIT.\n")
    rc = audit.main(["--root", str(tmp_path)])
    _ = capsys.readouterr()
    assert rc == 0


def test_main_returns_two_on_missing_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "does-not-exist"
    rc = audit.main(["--root", str(missing)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "does not exist" in err


def test_main_emits_json_when_requested(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    make_skill(tmp_path, "bad", CLEAN_SKILL + "\n## License\nMIT.\n")
    rc = audit.main(["--root", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    assert rc == 0  # only a medium-severity finding
    payload = json.loads(out)
    assert payload["skills_scanned"] == 1
    assert payload["severity_floor"] == "low"
    assert any(v["match_reason"] == "license section" for v in payload["violations"])


def test_main_severity_floor_filters_low(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--severity high` should suppress medium/low findings from the report."""
    body = CLEAN_SKILL + "\n## About\nLow.\n## License\nMedium.\n## Installation\nHigh.\n"
    make_skill(tmp_path, "bad", body)
    rc = audit.main(["--root", str(tmp_path), "--severity", "high", "--json"])
    out = capsys.readouterr().out
    assert rc == 1
    payload = json.loads(out)
    severities = {v["severity"] for v in payload["violations"]}
    assert severities == {"high"}, severities


# ---- discover_skills --------------------------------------------------------


def test_discover_skills_orders_results(tmp_path: Path) -> None:
    make_skill(tmp_path, "z-skill", CLEAN_SKILL)
    make_skill(tmp_path, "a-skill", CLEAN_SKILL)
    make_skill(tmp_path, "m-skill", CLEAN_SKILL)
    results = audit.discover_skills(tmp_path)
    names = [p.parent.name for p in results]
    assert names == ["a-skill", "m-skill", "z-skill"]


def test_discover_skills_finds_nested_depth_two(tmp_path: Path) -> None:
    """SKILL.md at depth 2 (e.g., skills/meta/do/SKILL.md) must be discovered."""
    # Create depth-1 skill
    make_skill(tmp_path, "top-level", CLEAN_SKILL)
    # Create depth-2 skill (the real repo structure)
    nested = tmp_path / "meta" / "do"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(CLEAN_SKILL, encoding="utf-8")

    results = audit.discover_skills(tmp_path)
    names = sorted(p.parent.name for p in results)
    assert "do" in names, f"depth-2 SKILL.md not found; got {names}"
    assert len(results) == 2, f"expected 2 skills, got {len(results)}: {names}"


def test_discover_skills_ignores_depth_three_and_deeper(tmp_path: Path) -> None:
    """Depth-1 and depth-2 SKILL.md are found; depth-3+ are ignored."""
    make_skill(tmp_path, "top", CLEAN_SKILL)
    # Depth-2 skill -- should be found
    depth2 = tmp_path / "meta" / "do"
    depth2.mkdir(parents=True)
    (depth2 / "SKILL.md").write_text(CLEAN_SKILL, encoding="utf-8")
    # Depth-3 skill inside references -- should be ignored
    nested = tmp_path / "top" / "references" / "nested-skill"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(CLEAN_SKILL, encoding="utf-8")
    results = audit.discover_skills(tmp_path)
    names = sorted(p.parent.name for p in results)
    assert len(results) == 2, f"expected 2 skills, got {len(results)}: {names}"
    assert "top" in names
    assert "do" in names
    assert "nested-skill" not in names
