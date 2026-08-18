"""Tests for fill-template.py — deterministic saved-template clone-and-fill."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from importlib import import_module
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "fill-template.py")
SAVED_DIR = Path(__file__).parent.parent.parent / "templates" / "saved"

sys.path.insert(0, str(Path(__file__).parent.parent))
fill_mod = import_module("fill-template")


def _run(*args: str, slots: dict | None = None) -> subprocess.CompletedProcess:
    """Run the CLI, optionally writing slots to a temp JSON file first."""
    argv = [sys.executable, SCRIPT, *args]
    if slots is not None:
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(slots, f)
        f.close()
        argv += ["--slots", f.name]
    return subprocess.run(argv, capture_output=True, text=True)


# --- gallery integrity: every shipped template is valid ---


def test_all_shipped_templates_listed() -> None:
    """Every .html with a manifest appears in --list; the three we ship are present."""
    names = fill_mod.list_templates()
    for expected in ("business-review", "project-kickoff", "system-design"):
        assert expected in names


def test_shipped_manifests_are_valid_json() -> None:
    for manifest in SAVED_DIR.glob("*.slots.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "slots" in data and isinstance(data["slots"], list)
        for slot in data["slots"]:
            assert "name" in slot


def test_every_manifest_slot_marker_exists_in_html() -> None:
    """A declared slot must have a matching {{MARKER}} in the template body."""
    for manifest in SAVED_DIR.glob("*.slots.json"):
        name = manifest.stem.replace(".slots", "")
        html = (SAVED_DIR / f"{name}.html").read_text(encoding="utf-8")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for slot in data["slots"]:
            assert f"{{{{{slot['name']}}}}}" in html, f"{name}: declared slot {slot['name']} has no marker in HTML"


def test_every_html_marker_is_declared() -> None:
    """Every {{MARKER}} in a template must be declared in its manifest — no orphan markers."""
    for html_path in SAVED_DIR.glob("*.html"):
        manifest_path = SAVED_DIR / f"{html_path.stem}.slots.json"
        if not manifest_path.exists():
            continue  # e.g. github-issues.html is a static artifact, not a slot template
        html = html_path.read_text(encoding="utf-8")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = {s["name"] for s in data["slots"]}
        markers = set(fill_mod.MARKER_RE.findall(html))
        orphan = markers - declared
        assert not orphan, f"{html_path.stem}: undeclared markers {orphan}"


# --- fill_template() behaviour ---


def _required(name: str) -> dict[str, str]:
    data = fill_mod.load_manifest(name)
    return {s["name"]: f"<p>{s['name']}</p>" for s in data["slots"] if s.get("required", True)}


def test_fill_leaves_no_markers() -> None:
    for name in fill_mod.list_templates():
        html = fill_mod.fill_template(name, _required(name))
        assert not fill_mod.MARKER_RE.findall(html)


def test_fill_substitutes_content() -> None:
    values = _required("business-review")
    values["TITLE"] = "Q3 Review UNIQUEMARKER"
    html = fill_mod.fill_template("business-review", values)
    assert "Q3 Review UNIQUEMARKER" in html


def test_layout_is_preserved() -> None:
    """Clone mode must not alter chrome: the CSS stamp and structure survive verbatim."""
    html = fill_mod.fill_template("business-review", _required("business-review"))
    assert "vexjoy-artifact: shape=report theme=birchline" in html
    assert '<body data-shape="report">' in html


def test_missing_required_slot_exits_1() -> None:
    r = _run("--template", "business-review", slots={"TITLE": "x"})
    assert r.returncode == 1
    assert "missing required slot" in r.stderr


def test_unknown_slot_exits_1() -> None:
    values = _required("business-review")
    values["NOT_A_SLOT"] = "x"
    r = _run("--template", "business-review", slots=values)
    assert r.returncode == 1
    assert "not declared" in r.stderr


def test_optional_slot_omitted_is_blank() -> None:
    """An omitted optional slot resolves to empty string, never a leftover marker."""
    values = _required("business-review")  # KICKER/META/FOOTER are optional, omitted
    html = fill_mod.fill_template("business-review", values)
    assert not fill_mod.MARKER_RE.findall(html)


def test_unknown_template_exits_2() -> None:
    r = _run("--template", "does-not-exist", slots={"TITLE": "x"})
    assert r.returncode == 2


def test_list_flag() -> None:
    r = _run("--list")
    assert r.returncode == 0
    assert "business-review" in r.stdout


def test_bad_slots_json_exits_2() -> None:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    f.write("{not valid json")
    f.close()
    r = subprocess.run(
        [sys.executable, SCRIPT, "--template", "business-review", "--slots", f.name],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
