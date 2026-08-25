#!/usr/bin/env python3
"""Tests for scripts/validate-workflow-conformance.py — the conformance gate.

A native .js workflow declares a pure-literal ``meta.contract`` (phases, the
static Wave-1 roster of ``{agentType, skill}``, ``agents:{static,dynamic}``, and a
top-level ``dynamic`` flag for data-driven passes). The validator asserts the
actual script against that contract:

- STATIC: ``meta.phases`` titles == ``contract.phases``; the static roster's
  agentType+skill pairs are present in source ``agentType:``/exact Skill-tool calls
  tokens; the declared static agent count matches the roster.
- DYNAMIC (only when node is available): shells to conformance-harness.mjs and
  asserts the recorded trace (phases entered subset of contract.phases; static
  Wave-1 roster agentType+skills) against the contract. For ``dynamic:true``
  rosters it asserts SHAPE + SKILLS, not COUNT (honest limits).

Files WITHOUT a ``meta.contract`` are EXEMPT (skipped), not failed.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "validate-workflow-conformance.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "conformance"
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_WORKFLOW_DIR = REPO_ROOT / "skills" / "workflow" / "references"
CONTRACTED_WORKFLOWS = tuple(
    REAL_WORKFLOW_DIR / name
    for name in (
        "comprehensive-review-workflow.js",
        "de-ai-pipeline.js",
        "explore-pipeline.js",
        "fan-out-workflow.js",
        "research-pipeline.js",
        "toolkit-improvement.js",
    )
)

# Import the module for unit-level tests of the static checker.
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("validate_workflow_conformance", SCRIPT)
vwc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vwc)

NODE = shutil.which("node")


def _run_json(*paths_or_flags):
    """Run the validator CLI with --json over given dir/flags; return (rc, data)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", *paths_or_flags],
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, data


def _result_for(data, name_substr):
    """Find the per-file result whose path contains name_substr."""
    for r in data["files"]:
        if name_substr in r["file"]:
            return r
    raise AssertionError(f"no result for {name_substr} in {[r['file'] for r in data['files']]}")


def _run_helper(skills):
    """Call skillDirectives() in a fresh Node process."""
    helper = REAL_WORKFLOW_DIR / "workflow-helpers.js"
    script = (
        "import { skillDirectives } from "
        + json.dumps(helper.as_uri())
        + "; process.stdout.write(skillDirectives(JSON.parse(process.argv[1])));"
    )
    return subprocess.run(
        [NODE, "--input-type=module", "-e", script, json.dumps(skills)],
        capture_output=True,
        text=True,
    )


def _run_fan_out(roster, synth_agent="research-coordinator-engineer"):
    """Execute fan-out with recording mocks and return its fail-closed trace."""
    workflow = REAL_WORKFLOW_DIR / "fan-out-workflow.js"
    script = """
      const calls = [];
      globalThis.phase = () => {};
      globalThis.budget = { remaining: () => 100000 };
      globalThis.agent = async ({ agentType }) => {
        calls.push(agentType);
        return { verdict: "PASS", summary: "ok" };
      };
      globalThis.parallel = (thunks) => Promise.all(thunks.map((thunk) => thunk()));
      const mod = await import(WORKFLOW_URL);
      try {
        await mod.default({ scope: {}, roster: ROSTER, synthAgentType: SYNTH_AGENT });
        process.stdout.write(JSON.stringify({ threw: false, calls }));
      } catch (error) {
        process.stdout.write(JSON.stringify({ threw: true, calls, error: String(error.message) }));
      }
    """
    script = script.replace("WORKFLOW_URL", json.dumps(workflow.as_uri()))
    script = script.replace("ROSTER", json.dumps(roster))
    script = script.replace("SYNTH_AGENT", json.dumps(synth_agent))
    proc = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# --- STATIC: pure parser unit tests ------------------------------------------


def test_extract_contract_present():
    src = (FIXTURES / "matching.js").read_text()
    contract = vwc.extract_contract(src)
    assert contract is not None
    assert contract["phases"] == ["wave-1", "verify"]
    assert contract["agents"]["static"] == 2


def test_extract_contract_absent_is_none():
    src = (FIXTURES / "no-contract.js").read_text()
    assert vwc.extract_contract(src) is None


def test_extract_phase_titles_from_source():
    src = (FIXTURES / "matching.js").read_text()
    assert vwc.extract_phase_titles(src) == {"wave-1", "verify"}


def test_extract_skill_tokens_from_source():
    src = (FIXTURES / "matching.js").read_text()
    skills = vwc.extract_skill_tokens(src)
    assert "systematic-code-review" in skills
    assert "multi-persona-critique" in skills


def test_extract_skill_tokens_picks_up_skills_array():
    """Skill names declared inside a `skills: ["a", "b"]` array are resolvable.

    The roster entry now carries a skills LIST; every element must be collected
    as a resolvable skill token (so the per-skill check can verify each one).
    """
    src = (FIXTURES / "matching.js").read_text()
    skills = vwc.extract_skill_tokens(src)
    # verification-before-completion is declared only inside skills:[...] arrays.
    assert "verification-before-completion" in skills


def test_extract_skills_list_from_roster_entry():
    """Each static roster entry exposes its full skills LIST (not a single skill)."""
    matching = vwc.extract_contract((FIXTURES / "matching.js").read_text())
    entry = matching["roster"][0]
    assert vwc.entry_skills(entry) == ["systematic-code-review", "verification-before-completion"]


@pytest.mark.parametrize(
    ("skills", "message"),
    (
        ([], "at least one skill"),
        (["not-an-indexed-skill"], "unknown skill"),
        (["reviewer-system"], "agent, not a skill"),
        ([42], "skill name must be a string"),
    ),
)
@pytest.mark.skipif(NODE is None, reason="node not available; helper runtime tests require node")
def test_skill_directives_rejects_untrusted_or_empty_names(skills, message):
    """Directive rendering fails closed before untrusted names enter a prompt."""
    proc = _run_helper(skills)
    assert proc.returncode != 0, proc.stdout
    assert message in proc.stderr.lower(), proc.stderr


@pytest.mark.parametrize(
    ("roster", "synth_agent", "message"),
    (
        (
            [
                {"agentType": "reviewer-system", "skills": ["systematic-code-review"]},
                {"agentType": "not-an-indexed-agent", "skills": ["systematic-code-review"]},
            ],
            "research-coordinator-engineer",
            "unknown agent",
        ),
        (
            [
                {"agentType": "reviewer-system", "skills": ["systematic-code-review"]},
                {"agentType": "reviewer-code", "skills": ["not-an-indexed-skill"]},
            ],
            "research-coordinator-engineer",
            "unknown skill",
        ),
        (
            [{"agentType": "reviewer-system", "skills": ["systematic-code-review"]}],
            "not-an-indexed-agent",
            "unknown agent",
        ),
        (
            [{"agentType": "systematic-code-review", "skills": ["verification-before-completion"]}],
            "research-coordinator-engineer",
            "skill, not an agent",
        ),
        (
            [
                {"agentType": "reviewer-system", "skills": ["systematic-code-review"]},
                {"agentType": "reviewer-code", "skills": []},
            ],
            "research-coordinator-engineer",
            "at least one skill",
        ),
    ),
)
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_fan_out_rejects_entire_untrusted_dispatch_before_agent_calls(roster, synth_agent, message):
    """One invalid dynamic name rejects the whole fan-out before any dispatch."""
    trace = _run_fan_out(roster, synth_agent)
    assert trace["threw"] is True, trace
    assert trace["calls"] == [], trace
    assert message in trace["error"].lower(), trace


def test_fully_dynamic_roster_requires_registry_validation_call():
    """Shape-only conformance cannot pass without fail-closed name validation."""
    source = (FIXTURES / "dynamic-roster.js").read_text()
    contract = vwc.extract_contract(source)
    stripped = source.replace("validateRoster(roster)", "roster")
    errors, _ = vwc._static_checks(stripped, contract)
    assert any("validate" in error.lower() and "roster" in error.lower() for error in errors), errors


@pytest.mark.parametrize(
    ("agent_type", "skills", "message"),
    (
        ("not-an-indexed-agent", ["systematic-code-review"], "unknown agent"),
        ("reviewer-system", ["reviewer-code"], "agent, not a skill"),
        ("reviewer-system", [], "at least one skill"),
    ),
)
def test_static_contract_rejects_untrusted_wrong_type_or_empty_roster_entries(agent_type, skills, message):
    """Conformance validates roster names against the trusted component indexes."""
    contract = {
        "phases": ["fan-out"],
        "roster": [{"agentType": agent_type, "skills": skills}],
        "agents": {"static": 1, "dynamic": False},
        "dynamic": False,
    }
    source = f'''
      enterPhase("fan-out");
      const roster = [{{agentType: "{agent_type}", skills: {json.dumps(skills)}}}];
      skillDirectives(roster[0].skills);
      agent({{agentType: "{agent_type}"}});
    '''
    errors, _ = vwc._static_checks(source, contract)
    assert any(message in error.lower() for error in errors), errors


def test_count_agent_callsites():
    src = (FIXTURES / "matching.js").read_text()
    # matching.js dispatches agent() twice (wave-1 map + verify).
    assert vwc.count_agent_callsites(src) == 2


# --- STATIC: pass / fail matrix via the CLI ----------------------------------


def test_matching_fixture_passes():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res
    # matching.js itself passes; rc reflects whole-dir (which includes mismatches).


def test_mismatch_phase_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-phase.js")
    assert res["status"] == "fail"
    assert any("phase" in e.lower() for e in res["static_errors"]), res["static_errors"]
    assert rc != 0


def test_mismatch_skill_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-skill.js")
    assert res["status"] == "fail"
    assert any("skill" in e.lower() for e in res["static_errors"]), res["static_errors"]


def test_mismatch_agentcount_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-agentcount.js")
    assert res["status"] == "fail"
    assert any("count" in e.lower() or "roster" in e.lower() or "static" in e.lower() for e in res["static_errors"]), (
        res["static_errors"]
    )


def test_no_contract_is_exempt():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "no-contract.js")
    assert res["status"] == "exempt"


def test_dir_with_any_failure_exits_nonzero():
    rc, _ = _run_json("--dir", str(FIXTURES), "--static-only")
    assert rc != 0  # fixtures dir contains deliberate mismatches


# --- The real hardened workflow MUST conform (static) ------------------------


def test_real_comprehensive_review_workflow_passes_static():
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR), "--static-only")
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res
    assert rc == 0, data


@pytest.mark.parametrize("path", (*CONTRACTED_WORKFLOWS, SCRIPT), ids=lambda path: path.name)
def test_active_workflow_contract_surfaces_drop_legacy_skill_syntax(path: Path):
    """Active workflow guidance must not compete with the exact call contract."""
    source = path.read_text(encoding="utf-8")
    assert "Skill(" not in source, f"legacy Skill() contract remains in {path}"


def test_contracted_workflows_use_only_active_skill_names():
    """Retired aliases stay out of executable native workflow surfaces."""
    source = "\n".join(path.read_text(encoding="utf-8") for path in CONTRACTED_WORKFLOWS)
    assert '"roast"' not in source
    assert '"codebase-analyzer"' not in source
    assert '"multi-persona-critique"' in source
    assert '"codebase-overview"' in source


# --- DYNAMIC: only when node is available ------------------------------------


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_matching_fixture_passes_dynamic():
    rc, data = _run_json("--dir", str(FIXTURES))
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_real_workflow_dynamic_trace_matches_contract():
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR))
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True
    assert not res["dynamic_errors"], res["dynamic_errors"]


def test_node_absent_skips_dynamic_gracefully(monkeypatch):
    """When node is unavailable the dynamic pass is skipped, not failed."""
    # Force the 'node missing' path regardless of host.
    monkeypatch.setattr(vwc, "node_available", lambda: False)
    results = vwc.validate_dir(FIXTURES / "matching.js", static_only=False)
    res = results[0]
    assert res["status"] == "pass"
    assert res["dynamic_ran"] is False
    assert any("node" in n.lower() for n in res["notes"]), res["notes"]


# --- Honest-limits surface ---------------------------------------------------


def test_output_labels_count_vs_shape_checks():
    """The validator must say which checks are COUNT vs SHAPE+SKILLS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    blob = json.dumps(res).lower()
    assert "count" in blob and ("shape" in blob or "skills" in blob), res


# --- FULLY-DYNAMIC ROSTER: the fan-out contract shape ------------------------
# A fully-dynamic-roster workflow has no static agentType/exact-call literals
# (the roster is caller-supplied). The contract declares roster:{dynamic:true}.
# The validator must assert the STRUCTURAL invariant — source emits a Skill(
# directive derived from a roster variable AND dispatches agentType from a roster
# variable — NOT specific names, and LABEL the check as structural.


def test_roster_is_fully_dynamic_helper():
    """roster_is_fully_dynamic() is True for {dynamic:true}, False for a list."""
    assert vwc.roster_is_fully_dynamic({"roster": {"dynamic": True}}) is True
    assert vwc.roster_is_fully_dynamic({"roster": [{"agentType": "x", "skill": "y"}]}) is False
    assert vwc.roster_is_fully_dynamic({"roster": []}) is False


def test_has_dynamic_skill_directive_detects_interpolated_skill():
    """A template-derived exact sentence counts as a per-roster Skill call."""
    yes = r"agent({ prompt: `Call the Skill tool with \`${r.skill}\`.`, agentType: r.agentType })"
    no = "agent({ prompt: `review the diff`, agentType: r.agentType })"
    assert vwc.has_dynamic_skill_directive(yes) is True
    assert vwc.has_dynamic_skill_directive(no) is False


def test_has_dynamic_agent_dispatch_detects_variable_agenttype():
    """agentType: <variable> (not a string literal) counts as dynamic dispatch."""
    yes = "agent({ agentType: r.agentType })"
    literal_only = 'agent({ agentType: "reviewer-system" })'
    assert vwc.has_dynamic_agent_dispatch(yes) is True
    assert vwc.has_dynamic_agent_dispatch(literal_only) is False


def test_dynamic_roster_fixture_passes_static():
    """Fully-dynamic roster WITH the structural invariant present PASSES."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "dynamic-roster.js")
    assert res["status"] == "pass", res


def test_dynamic_roster_missing_skill_fails_static():
    """Fully-dynamic roster MISSING the Skill(-from-roster invariant FAILS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "dynamic-roster-missing-skill.js")
    assert res["status"] == "fail", res
    assert any("skill" in e.lower() for e in res["static_errors"]), res["static_errors"]


def test_dynamic_roster_labels_structural():
    """The validator must LABEL the dynamic-roster check as STRUCTURAL (honest limits)."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "dynamic-roster.js")
    blob = json.dumps(res["checks"]).lower()
    assert "structural" in blob, res["checks"]


def test_dynamic_roster_not_vacuous_pass():
    """A fully-dynamic contract must NOT pass merely because there are no names to
    check. Stripping the structural invariant from a {dynamic:true} contract source
    must produce a failure (proves the check is doing real work)."""
    src = (FIXTURES / "dynamic-roster.js").read_text()
    contract = vwc.extract_contract(src)
    assert vwc.roster_is_fully_dynamic(contract) is True
    errors, _ = vwc._static_checks(src, contract)
    assert errors == [], errors  # the real fixture passes
    # Remove the inline exact call literal AND the per-roster
    # skillDirectives(r.skills) CALL -> the structural invariant is violated ->
    # must error. The helper DEFINITION (function skillDirectives(...)) is excluded
    # from evidence by the gate's lookbehind, so it does not mask the removal.
    stripped = src.replace("Call the Skill tool with \\`${s}\\`.", "your usual methodology").replace(
        "skillDirectives(r.skills)", "your usual methodology"
    )
    errs2, _ = vwc._static_checks(stripped, contract)
    assert any("skill" in e.lower() for e in errs2), errs2


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_dynamic_roster_fixture_passes_dynamic():
    """With node, the fully-dynamic fixture records a real trace and PASSES."""
    rc, data = _run_json("--dir", str(FIXTURES))
    res = _result_for(data, "dynamic-roster.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True
    assert not res["dynamic_errors"], res["dynamic_errors"]


# --- The real fan-out workflow MUST conform (static) -------------------------


def test_real_fan_out_workflow_passes_static():
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR), "--static-only")
    res = _result_for(data, "fan-out-workflow.js")
    assert res["status"] == "pass", res


# --- skills[] CONTRACT: full stack per agent (Stage 2.5) ---------------------
# Each roster entry now declares a skills LIST and the body must emit one
# exact Skill-tool call per element. The gate verifies EACH declared skill has a
# corresponding call (static for literal rosters; structural for
# fully-dynamic rosters where emission is delegated to skillDirectives(<var>)).


def test_matching_multi_skill_fixture_passes_static():
    """A static roster with a multi-skill list, all skills emitted, PASSES."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res


def test_missing_one_of_several_skills_fails_static():
    """A static roster entry declaring 2 skills but emitting only 1 FAILS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-skill.js")
    assert res["status"] == "fail", res
    assert any("verification-before-completion" in e for e in res["static_errors"]), res["static_errors"]


def test_each_declared_skill_checked_independently():
    """The gate asserts EACH skill in the list, not just the first one."""
    src = (FIXTURES / "mismatch-skill.js").read_text()
    contract = vwc.extract_contract(src)
    errors, _ = vwc._static_checks(src, contract)
    # systematic-code-review is emitted (ok); verification-before-completion is not.
    assert any("verification-before-completion" in e for e in errors), errors
    assert not any("'systematic-code-review'" in e and "not resolvable" in e for e in errors), errors


def test_delegated_skill_directives_call_satisfies_invariant():
    """has_dynamic_skill_directive() also recognizes a skillDirectives(<var>) call.

    The real workflows delegate per-roster Skill-tool call emission to an imported helper
    skillDirectives(r.skills); the inline exact sentence lives in the
    helper module, not the workflow body. The structural invariant must accept the
    delegated call as evidence the per-roster methodology attach is emitted.
    """
    delegated = "agent({ prompt: `You are ${r.agentType}.` + skillDirectives(r.skills), agentType: r.agentType })"
    inline = r"agent({ prompt: `Call the Skill tool with \`${r.skill}\`.`, agentType: r.agentType })"
    none = "agent({ prompt: `review the diff`, agentType: r.agentType })"
    assert vwc.has_dynamic_skill_directive(delegated) is True
    assert vwc.has_dynamic_skill_directive(inline) is True
    assert vwc.has_dynamic_skill_directive(none) is False


def test_real_comprehensive_review_passes_static_with_skills_list():
    """The hardened comprehensive-review workflow (skills[] per entry) PASSES."""
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR), "--static-only")
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_real_comprehensive_review_dynamic_records_every_skill():
    """The recorded trace shows EVERY declared skill per agent."""
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR))
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res
    assert not res["dynamic_errors"], res["dynamic_errors"]


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_real_fan_out_dynamic_records_every_skill():
    """The fan-out recorded trace shows every skill in each worker's list."""
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR))
    res = _result_for(data, "fan-out-workflow.js")
    assert res["status"] == "pass", res
    assert not res["dynamic_errors"], res["dynamic_errors"]
