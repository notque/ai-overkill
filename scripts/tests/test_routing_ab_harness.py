"""Tests for the extended routing A/B harness (scripts/routing-ab-test.py).

Covers:
- Corpus schema (incl. optional expected_pipeline / acceptable / uncertain) and
  legacy-case immutability (the 49 v1.0 cases are pinned by SHA-256).
- Back-compat regression: with no --manifest-arm, every legacy mode produces
  byte-identical artifacts (golden files generated from the pre-extension
  script; regen instructions in fixtures/routing_ab/golden/README.md).
- Manifest-arm plumbing end-to-end with two trivially-different commands.
- Gate logic on synthetic raw.json inputs, McNemar on known 2x2 tables.
- --assert-buckets on the fixture corpus and on synthetic rows.
- No writes outside the chosen --out-dir.

Never invokes claude/Haiku: pre-route and manifests are stubbed; the only
subprocesses are tiny `python -c "print(...)"` manifest commands.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "scripts" / "routing-ab-test.py"
REAL_CORPUS = REPO_ROOT / "scripts" / "routing-ab-corpus.json"
REAL_RESULTS = REPO_ROOT / "scripts" / "routing-ab-results"
FIX = Path(__file__).parent / "fixtures" / "routing_ab"
GOLDEN = FIX / "golden"

# SHA-256 of json.dumps(test_cases[:49], sort_keys=True, ensure_ascii=False)
# at corpus v1.0. The legacy cases are immutable; extending the corpus means
# APPENDING cases, never editing these.
#
# Exception (2026-07-04, post-merge fixup I3): commit 87977cdb (codebase-analyzer
# demoted to codebase-overview) edited the `notes` field of legacy entries 18-20
# to rename the skill reference — an owner-approved content correction, not a
# scope change to the pinned cases. The pin is updated to the new digest rather
# than reverted, because the old digest now describes stale prose (a skill name
# that no longer exists), which is a worse invariant to protect than "notes
# mention the current skill name." Future edits to cases[:49] still require the
# same scrutiny this pin exists to enforce.
# Exception (2026-07-05, skill consolidation): 35 skills folded into 13 parents
# via promoted_to. Legacy edits, all rename-class: notes in cases 18-20 and 31
# (codebase-analyzer -> codebase-overview, fish-shell-config -> shell-config)
# and case 42 gold label (roast -> multi-persona-critique, its parent). Same
# rationale as the 87977cdb exception above: the old digest pins gold labels
# for skills that no longer exist.
LEGACY_CASES_SHA = "f7b95f03ecd51857dd85adde93304caff5c9b29224afb082bf4298ce75738fd9"
NEW_BUCKETS = {
    "stub-tier",
    "sibling-disambiguation",
    "pipeline-pick",
    "vague-interview",
    "plain-english",
    "reachability",
    # v1.3: cases drawn from recorded production general-purpose fallbacks.
    "prod-fallback-specialist",
    "prod-fallback-general",
    "prod-fallback-coordinator",
    "prod-fallback-ambiguous",
}

# v1.4 provenance. Absence resolves to unknown-legacy: the 49 pinned v1.0 cases
# cannot carry the field, and their provenance was never recorded.
PROVENANCE_SOURCES = frozenset({"local-telemetry", "catalog-derived", "unknown-legacy"})
UNKNOWN_PROVENANCE = {"source": "unknown-legacy", "workload": None, "sample": None}


def resolve_provenance(case: dict) -> dict:
    """Provenance of one case; absent means unknown-legacy, never guessed."""
    return case.get("provenance", UNKNOWN_PROVENANCE)


def load_harness(workdir: Path):
    """Import routing-ab-test.py with paths redirected and pre-route/manifest stubbed."""
    spec = importlib.util.spec_from_file_location("routing_ab_test", HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = workdir / "routing-ab-results"
    mod.CORPUS = FIX / "corpus.json"
    mod.RESULTS = results
    mod.PROMPTS_DIR = results / "prompts"
    mod.ANSWERS_DIR = results / "answers"
    stub = json.loads((FIX / "pre_route_stub.json").read_text(encoding="utf-8"))
    mod.run_pre_route = lambda request: stub[request]
    mod.build_manifest = lambda: "STUB MANIFEST v1"
    return mod


def run_legacy_pipeline(mod) -> Path:
    """Run all five legacy modes over the fixture corpus; return the results dir."""
    assert mod.emit_prompts() == 0
    for ans in sorted((FIX / "answers").glob("*.json")):
        shutil.copy(ans, mod.ANSWERS_DIR / ans.name)
    assert mod.score() == 0
    assert mod.build_judge() == 0
    shutil.copy(FIX / "judge-output.json", mod.RESULTS / "judge-output.json")
    assert mod.rejoin() == 0
    assert mod.pre_route_map() == 0
    return mod.RESULTS


# --------------------------------------------------------------------------- #
# Corpus schema + legacy immutability
# --------------------------------------------------------------------------- #
class TestCorpus:
    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return json.loads(REAL_CORPUS.read_text(encoding="utf-8"))["test_cases"]

    def test_legacy_cases_unchanged(self, cases):
        digest = hashlib.sha256(json.dumps(cases[:49], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert digest == LEGACY_CASES_SHA, "the 49 legacy corpus cases must never change — append only"

    def test_legacy_cases_have_no_new_fields(self, cases):
        for case in cases[:49]:
            for field in ("expected_pipeline", "acceptable", "uncertain"):
                assert field not in case, f"legacy case gained new field {field}: {case['request']!r}"

    def test_required_schema_all_cases(self, cases):
        for case in cases:
            for field in ("request", "expected_agent", "expected_skill", "category", "bucket", "notes"):
                assert field in case, f"missing {field}: {case.get('request')!r}"
            assert isinstance(case["request"], str) and case["request"]
            assert case["expected_agent"] is None or isinstance(case["expected_agent"], str)
            assert case["expected_skill"] is None or isinstance(case["expected_skill"], str)

    def test_optional_field_types(self, cases):
        for case in cases:
            if "expected_pipeline" in case:
                assert case["expected_pipeline"] is None or isinstance(case["expected_pipeline"], str)
            if "acceptable" in case:
                assert isinstance(case["acceptable"], list) and case["acceptable"]
                for alt in case["acceptable"]:
                    assert set(alt) == {"agent", "skill"}, f"acceptable entries are {{agent, skill}}: {alt}"
            if "uncertain" in case:
                assert case["uncertain"] is True

    def test_new_cases_only_in_new_buckets(self, cases):
        for case in cases[49:]:
            assert case["bucket"] in NEW_BUCKETS, f"new case in legacy bucket: {case['request']!r}"

    def test_new_bucket_minimum_counts(self, cases):
        counts: dict[str, int] = {}
        for case in cases[49:]:
            counts[case["bucket"]] = counts.get(case["bucket"], 0) + 1
        minimums = {
            "stub-tier": 10,
            "sibling-disambiguation": 10,
            "pipeline-pick": 8,
            "vague-interview": 6,
            "plain-english": 8,
            "prod-fallback-specialist": 40,
            "prod-fallback-general": 20,
            "prod-fallback-coordinator": 12,
        }
        for bucket, minimum in minimums.items():
            assert counts.get(bucket, 0) >= minimum, f"{bucket}: {counts.get(bucket, 0)} < {minimum}"

    def test_null_agent_rate_stays_bounded(self, cases):
        """A corpus that mostly expects no agent cannot detect under-routing.

        At v1.2 the corpus asserted expected_agent null on 142/178 cases (79.8%),
        so a router that grew more timid scored BETTER on it. Keep the rate low
        enough that the agent slot carries real signal.
        """
        nulls = sum(1 for case in cases if case["expected_agent"] is None)
        rate = 100.0 * nulls / len(cases)
        assert rate <= 60.0, f"expected_agent null rate {rate:.1f}% — corpus is blind to under-routing"

    def test_general_purpose_is_labelled_explicitly(self, cases):
        """`general-purpose` must be an asserted label, not the meaning of null.

        Explicit labels are what makes an over-aggressive router fail too.
        """
        explicit = [c for c in cases if c["expected_agent"] == "general-purpose"]
        assert len(explicit) >= 20, f"only {len(explicit)} cases assert general-purpose explicitly"

    def test_provenance_is_declared_and_well_formed(self, cases):
        """Every case says where it came from, so telemetry is separable from catalog work.

        The 49 pinned v1.0 cases cannot carry the field (SHA-256 pin plus
        test_legacy_cases_have_no_new_fields), so absence resolves to
        unknown-legacy rather than being guessed at.
        """
        for i, case in enumerate(cases):
            prov = resolve_provenance(case)
            assert set(prov) == {"source", "workload", "sample"}, f"case {i}: bad provenance keys {sorted(prov)}"
            assert prov["source"] in PROVENANCE_SOURCES, f"case {i}: unknown source {prov['source']!r}"
            if prov["source"] == "local-telemetry":
                assert prov["workload"], f"case {i}: local-telemetry must name the workload it was sampled from"
            else:
                assert prov["workload"] is None, f"case {i}: only local-telemetry carries a workload"
            if i >= 49:
                assert "provenance" in case, f"case {i} is taggable and must declare provenance"

    def test_no_single_workload_dominates_agent_labels(self, cases):
        """One machine's telemetry must not decide what "correct routing" means.

        This toolkit runs on several machines with different workloads. learning.db
        is per-box — no host or project column, no cross-box aggregation — so a
        local sample describes ONE box, and local absence of an agent is not
        evidence that the agent is unused elsewhere. The v1.3 cases came from a
        single Flask/Peewee/SQLite workload; left uncapped, a routing change that
        suits that one box scores as a win and can regress every other box. That is
        the #860 failure mode (a corpus that could not see under-routing certifying
        a regression as a 7-point gain) pointed the other way.

        The cap is a ratchet, not a target. At v1.4 the top workload holds 70.0% of
        the agent-asserting cases; the cap sits just above that so the share cannot
        grow, and it should be lowered as maintainers on other machines contribute
        cases from their own workloads. Balance comes from real cases other boxes
        record — never from inventing cases for workloads nobody has observed.
        """
        asserting = [c for c in cases if c["expected_agent"]]
        counts: dict[str, int] = {}
        for case in asserting:
            workload = resolve_provenance(case)["workload"]
            if workload:
                counts[workload] = counts.get(workload, 0) + 1
        if not counts:
            return
        workload, top = max(counts.items(), key=lambda kv: kv[1])
        share = 100.0 * top / len(asserting)
        assert share <= 75.0, (
            f"workload {workload!r} holds {share:.1f}% of the {len(asserting)} agent-asserting cases "
            "— the corpus now measures one machine. Add cases from other workloads; do not invent them."
        )

    def test_pipeline_pick_cases_carry_expected_pipeline(self, cases):
        for case in cases:
            if case["bucket"] == "pipeline-pick":
                assert "expected_pipeline" in case, f"pipeline-pick case missing expected_pipeline: {case['request']!r}"


# --------------------------------------------------------------------------- #
# Back-compat regression: legacy modes byte-identical to pre-extension goldens
# --------------------------------------------------------------------------- #
class TestLegacyByteIdentical:
    @pytest.fixture(scope="class")
    def results(self, tmp_path_factory) -> Path:
        mod = load_harness(tmp_path_factory.mktemp("legacy"))
        return run_legacy_pipeline(mod)

    @pytest.mark.parametrize(
        "name",
        [
            "queries.json",
            "manifest-used.txt",
            "raw.json",
            "judge-input.json",
            "uid-map.json",
            "scoreboard.json",
            "pre-route-map.json",
        ],
    )
    def test_artifact_bytes(self, results: Path, name: str):
        assert (results / name).read_bytes() == (GOLDEN / name).read_bytes(), f"{name} diverged from golden"

    def test_prompt_bytes(self, results: Path):
        golden_prompts = sorted((GOLDEN / "prompts").glob("*.txt"))
        produced = sorted((results / "prompts").glob("*.txt"))
        assert [p.name for p in produced] == [p.name for p in golden_prompts]
        for got, want in zip(produced, golden_prompts):
            assert got.read_bytes() == want.read_bytes(), f"prompt {got.name} diverged"


# --------------------------------------------------------------------------- #
# Manifest-arm plumbing (no model: manifests come from tiny python -c commands)
# --------------------------------------------------------------------------- #
def _arm_answers(qids: list[str], answers: dict[str, dict], out: Path, arm: str) -> None:
    for qid in qids:
        (out / "answers" / arm / f"{qid}.json").write_text(json.dumps(answers[qid]), encoding="utf-8")


class TestManifestArms:
    @pytest.fixture()
    def mod(self, tmp_path):
        return load_harness(tmp_path)

    @pytest.fixture()
    def arms(self) -> dict[str, str]:
        py = sys.executable
        return {
            "full": f"{py} -c \"print('MANIFEST FULL')\"",
            "tiered": f"{py} -c \"print('MANIFEST TIERED')\"",
        }

    def test_parse_manifest_arms(self, mod):
        parsed = mod.parse_manifest_arms(["full=cmd one", "tiered=cmd two"])
        assert parsed == {"full": "cmd one", "tiered": "cmd two"}
        with pytest.raises(SystemExit):
            mod.parse_manifest_arms(["only=one"])
        with pytest.raises(SystemExit):
            mod.parse_manifest_arms(["bad-no-equals", "x=y"])
        with pytest.raises(SystemExit):
            mod.parse_manifest_arms(["dup=a", "dup=b"])

    def test_parse_model_arms(self, mod):
        names = ["haiku", "self-route"]
        parsed = mod.parse_model_arms(["haiku=haiku", "self-route=default"], names)
        assert parsed == {"haiku": "haiku", "self-route": "default"}
        with pytest.raises(SystemExit):  # name without a manifest arm
            mod.parse_model_arms(["haiku=haiku", "bogus=opus"], names)
        with pytest.raises(SystemExit):  # missing an arm
            mod.parse_model_arms(["haiku=haiku"], names)
        with pytest.raises(SystemExit):  # duplicate
            mod.parse_model_arms(["haiku=a", "haiku=b", "self-route=c"], names)
        with pytest.raises(SystemExit):  # malformed
            mod.parse_model_arms(["no-equals", "self-route=x"], names)

    def test_emit_prompts_records_model_arms(self, mod, arms):
        models = {"full": "haiku", "tiered": "default"}
        assert mod.emit_prompts(manifest_arms=arms, model_arms=models) == 0
        record = json.loads((mod.RESULTS / "arms.json").read_text(encoding="utf-8"))
        assert record["models"] == models
        assert record["arms"] == ["full", "tiered"]

    def test_emit_prompts_omits_models_key_when_unset(self, mod, arms):
        assert mod.emit_prompts(manifest_arms=arms) == 0
        record = json.loads((mod.RESULTS / "arms.json").read_text(encoding="utf-8"))
        assert "models" not in record

    def test_emit_prompts_per_arm(self, mod, arms):
        assert mod.emit_prompts(manifest_arms=arms) == 0
        out = mod.RESULTS
        for arm, manifest in [("full", "MANIFEST FULL"), ("tiered", "MANIFEST TIERED")]:
            prompts = sorted((out / "prompts" / arm).glob("*.txt"))
            assert [p.name for p in prompts] == ["q00.txt", "q01.txt", "q02.txt", "q03.txt"]
            assert manifest in prompts[0].read_text(encoding="utf-8")
            assert (out / f"manifest-used-{arm}.txt").read_text(encoding="utf-8") == manifest
        assert json.loads((out / "arms.json").read_text(encoding="utf-8"))["arms"] == ["full", "tiered"]

    def test_score_judge_rejoin_per_arm(self, mod, arms):
        assert mod.emit_prompts(manifest_arms=arms) == 0
        out = mod.RESULTS
        qids = ["q00", "q01", "q02", "q03"]
        # full: routes q00 correctly via safety net, misses q02.
        full = {
            "q00": {"agent": None, "skill": "publish", "pipeline": None, "confidence": "medium"},
            "q01": {"agent": None, "skill": None, "pipeline": None, "confidence": "low"},
            "q02": {"agent": None, "skill": "quick", "pipeline": None, "confidence": "low"},
            "q03": {
                "agent": "python-general-engineer",
                "skill": "python-quality-gate",
                "pipeline": None,
                "confidence": "high",
            },
        }
        # tiered: matches full except it recovers q02.
        tiered = dict(full)
        tiered["q02"] = {"agent": None, "skill": "pr-workflow", "pipeline": None, "confidence": "high"}
        _arm_answers(qids, full, out, "full")
        _arm_answers(qids, tiered, out, "tiered")

        assert mod.score() == 0
        raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
        assert raw["arms"] == ["full", "tiered"]
        assert raw["cost"]["haiku_calls_total"] == {"full": 4, "tiered": 4}
        q00 = raw["records"][0]
        # Safety net: pre-route high force pr-workflow overrides the 'publish' pick.
        assert q00["arms"]["full"]["route"] == {
            "agent": None,
            "skill": "pr-workflow",
            "pipeline": None,
            "source": "safety_net",
            "safety_override": True,
        }
        assert raw["records"][2]["arms"]["tiered"]["route"]["skill"] == "pr-workflow"

        assert mod.build_judge() == 0
        uid_map = json.loads((out / "uid-map.json").read_text(encoding="utf-8"))
        assert len(uid_map) == 8
        assert {m["arm"] for m in uid_map.values()} == {"full", "tiered"}
        rows = json.loads((out / "judge-input.json").read_text(encoding="utf-8"))
        for row in rows:  # blind: no arm leakage to the judge
            assert "arm" not in row and "source" not in row

        judge_out = {uid: "correct" for uid in uid_map}
        (out / "judge-output.json").write_text(json.dumps(judge_out), encoding="utf-8")
        assert mod.rejoin() == 0
        scoreboard = json.loads((out / "scoreboard.json").read_text(encoding="utf-8"))
        assert set(scoreboard["overall"]) == {"full", "tiered"}
        assert scoreboard["overall"]["full"]["n"] == 4

    def test_gate_runs_on_manifest_raw(self, mod, arms, capsys):
        self.test_score_judge_rejoin_per_arm(mod, arms)
        rc = mod.gate()
        out_text = capsys.readouterr().out
        # Gates print BEFORE results.
        assert out_text.index("PRE-REGISTERED GATES") < out_text.index("=== RESULTS")
        # tiered recovers q02, no harm; only 1 discordant pair -> UNDERPOWERED.
        assert "UNDERPOWERED" in out_text
        assert rc == 2


# --------------------------------------------------------------------------- #
# Gate logic + McNemar on synthetic inputs
# --------------------------------------------------------------------------- #
def _make_raw(rows: list[dict]) -> dict:
    """Synthetic manifest-arm raw.json. rows: {bucket, expected, base, chal, acceptable?}."""
    records = []
    for i, row in enumerate(rows):
        exp_agent, exp_skill = row["expected"]
        rec = {
            "id": f"q{i:02d}",
            "query": f"synthetic {i}",
            "bucket": row["bucket"],
            "expected_agent": exp_agent,
            "expected_skill": exp_skill,
            "arms": {
                "base": {"route": {"agent": row["base"][0], "skill": row["base"][1]}},
                "chal": {"route": {"agent": row["chal"][0], "skill": row["chal"][1]}},
            },
        }
        if "acceptable" in row:
            rec["acceptable"] = row["acceptable"]
        records.append(rec)
    return {"arms": ["base", "chal"], "records": records}


def _row(bucket: str, expected, base, chal, **extra) -> dict:
    return {"bucket": bucket, "expected": expected, "base": base, "chal": chal, **extra}


HIT = (None, "right")
MISS = (None, "wrong")
EXP = (None, "right")


class TestMcNemar:
    @pytest.fixture(scope="class")
    def mod(self, tmp_path_factory):
        return load_harness(tmp_path_factory.mktemp("mcnemar"))

    def test_known_tables(self, mod):
        p = mod._mcnemar_exact_p
        assert p(0, 0) == 1.0
        # n=6, k=1: 2 * (C(6,0)+C(6,1)) / 2^6 = 14/64
        assert p(5, 1) == pytest.approx(14 / 64)
        # n=8, k=0: 2 * 1/256
        assert p(8, 0) == pytest.approx(2 / 256)
        # n=10, k=5 (balanced): clamps to 1.0
        assert p(5, 5) == 1.0

    def test_symmetry(self, mod):
        assert mod._mcnemar_exact_p(2, 7) == mod._mcnemar_exact_p(7, 2)

    def test_paired_stats_shape(self, mod):
        per_case = [{"baseline_correct": b, "challenger_correct": c} for b, c in [(1, 1), (0, 1), (0, 1), (1, 0)]]
        stats = mod.compute_paired_stats(per_case, bootstrap_iters=200)
        assert stats["help"] == 2 and stats["harm"] == 1 and stats["discordant"] == 3
        assert stats["D"] == pytest.approx(0.25)
        assert stats["D_ci_low"] <= stats["D"] <= stats["D_ci_high"]
        assert 0.0 < stats["mcnemar_p"] <= 1.0


class TestGateLogic:
    @pytest.fixture(scope="class")
    def mod(self, tmp_path_factory):
        return load_harness(tmp_path_factory.mktemp("gate"))

    def _verdict(self, mod, rows):
        return mod.gate_verdict(_make_raw(rows), "base", "chal")

    def test_promote(self, mod):
        # 20 concordant hits + 7 challenger-only recoveries: powered, no harm.
        rows = [_row("plain-english", EXP, HIT, HIT) for _ in range(20)]
        rows += [_row("plain-english", EXP, MISS, HIT) for _ in range(7)]
        v = self._verdict(mod, rows)
        assert v["gates"] == {"a_accuracy": True, "b_harm": True, "c_safety_buckets": True, "d_stub_tier": True}
        assert v["verdict"] == "PROMOTE" and v["exit_code"] == 0

    def test_underpowered(self, mod):
        rows = [_row("plain-english", EXP, HIT, HIT) for _ in range(20)]
        rows += [_row("plain-english", EXP, MISS, HIT) for _ in range(3)]
        v = self._verdict(mod, rows)
        assert v["failing_gates"] == []
        assert v["discordant_pairs"] == 3
        assert v["verdict"] == "UNDERPOWERED" and v["exit_code"] == 2

    def test_reject_accuracy_drop(self, mod):
        # Challenger loses 4/20 = 20 points: gate (a) fails.
        rows = [_row("plain-english", EXP, HIT, HIT) for _ in range(16)]
        rows += [_row("plain-english", EXP, HIT, MISS) for _ in range(4)]
        v = self._verdict(mod, rows)
        assert "a_accuracy" in v["failing_gates"]
        assert v["verdict"] == "REJECT" and v["exit_code"] == 1

    def test_reject_significant_harm(self, mod):
        # 8 harm vs 0 help: p = 2/256 <= 0.05 -> gate (b) fails (and (a) too).
        rows = [_row("plain-english", EXP, HIT, HIT) for _ in range(100)]
        rows += [_row("plain-english", EXP, HIT, MISS) for _ in range(8)]
        v = self._verdict(mod, rows)
        assert "b_harm" in v["failing_gates"]
        assert v["verdict"] == "REJECT"

    def test_reject_single_safety_miss(self, mod):
        # One new miss in a safety bucket rejects, even with big overall gains.
        rows = [_row("plain-english", EXP, MISS, HIT) for _ in range(10)]
        rows += [_row("paraphrase-git", EXP, HIT, MISS)]
        v = self._verdict(mod, rows)
        assert v["new_safety_misses"] == ["q10"]
        assert "c_safety_buckets" in v["failing_gates"]
        assert v["verdict"] == "REJECT"

    def test_reject_stub_tier_drop(self, mod):
        # Stub-tier drops by 2 (> 1 allowed): gate (d) fails.
        rows = [_row("plain-english", EXP, MISS, HIT) for _ in range(10)]
        rows += [_row("stub-tier", EXP, HIT, MISS) for _ in range(2)]
        rows += [_row("stub-tier", EXP, HIT, HIT) for _ in range(3)]
        v = self._verdict(mod, rows)
        assert v["stub_tier"] == {"n": 5, "baseline_correct": 5, "challenger_correct": 3}
        assert "d_stub_tier" in v["failing_gates"]
        assert v["verdict"] == "REJECT"

    def test_stub_tier_within_one_passes(self, mod):
        rows = [_row("plain-english", EXP, MISS, HIT) for _ in range(10)]
        rows += [_row("stub-tier", EXP, HIT, MISS)]
        rows += [_row("stub-tier", EXP, HIT, HIT) for _ in range(4)]
        v = self._verdict(mod, rows)
        assert v["gates"]["d_stub_tier"] is True

    def test_acceptable_alternates_count_as_correct(self, mod):
        rows = [
            _row(
                "sibling-disambiguation",
                (None, "systematic-code-review"),
                (None, "systematic-code-review"),
                (None, "quick"),
                acceptable=[{"agent": None, "skill": "quick"}],
            )
        ]
        v = self._verdict(mod, rows)
        assert v["stats"]["harm"] == 0  # alternate accepted, not a new miss

    def test_route_correct_exact_and_null(self, mod):
        rec = {"expected_agent": None, "expected_skill": None}
        assert mod.route_correct(rec, {"agent": None, "skill": None})
        assert not mod.route_correct(rec, {"agent": None, "skill": "pr-workflow"})
        rec2 = {"expected_agent": "golang-general-engineer", "expected_skill": "go-patterns"}
        assert mod.route_correct(rec2, {"agent": "golang-general-engineer", "skill": "go-patterns"})
        assert not mod.route_correct(rec2, {"agent": None, "skill": "go-patterns"})


# --------------------------------------------------------------------------- #
# --assert-buckets (fast-path equivalence, deterministic)
# --------------------------------------------------------------------------- #
class TestAssertBuckets:
    def test_fixture_corpus_reports_paraphrase_violation(self, tmp_path, capsys):
        # Fixture: q00 force_route high (ok), q01 guard fallthrough (ok),
        # q02 paraphrase-git fallthrough -> REQUIRED bucket not eligible -> fail.
        mod = load_harness(tmp_path)
        rc = mod.pre_route_map(assert_buckets=True)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL: 1 violations" in out
        assert "q02" in out and "paraphrase-git" in out

    def test_synthetic_pass(self, tmp_path, capsys):
        mod = load_harness(tmp_path)
        rows = [
            {
                "id": "q00",
                "bucket": "benchmark-force_route",
                "pre_route_confidence": "high",
                "pre_route_match_type": "force_route",
                "pre_route_skill": "pr-workflow",
                "query": "a",
            },
            {
                "id": "q01",
                "bucket": "false-positive-guard",
                "pre_route_confidence": "low",
                "pre_route_match_type": "fallthrough",
                "pre_route_skill": None,
                "query": "b",
            },
            {
                "id": "q02",
                "bucket": "benchmark-candidate",
                "pre_route_confidence": "medium",
                "pre_route_match_type": "candidate",
                "pre_route_skill": "x",
                "query": "c",
            },
        ]
        assert mod._assert_buckets(rows) == 0
        assert "PASS" in capsys.readouterr().out

    def test_synthetic_guard_violation(self, tmp_path, capsys):
        mod = load_harness(tmp_path)
        rows = [
            {
                "id": "q00",
                "bucket": "false-positive-guard",
                "pre_route_confidence": "high",
                "pre_route_match_type": "force_route",
                "pre_route_skill": "pr-workflow",
                "query": "push back",
            },
        ]
        assert mod._assert_buckets(rows) == 1
        assert "MUST NOT be fast-path eligible" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Write containment: nothing outside the chosen out-dir
# --------------------------------------------------------------------------- #
class TestWriteContainment:
    def test_all_modes_write_only_under_out_dir(self, tmp_path):
        before = {p: p.stat().st_mtime_ns for p in REAL_RESULTS.rglob("*") if p.is_file()}
        mod = load_harness(tmp_path)
        run_legacy_pipeline(mod)
        out = tmp_path / "elsewhere"
        assert mod.pre_route_map(out_dir=out) == 0
        assert (out / "pre-route-map.json").exists()
        after = {p: p.stat().st_mtime_ns for p in REAL_RESULTS.rglob("*") if p.is_file()}
        assert before == after, "a mode wrote into the default results dir of the repo"
        written = {p for p in tmp_path.rglob("*") if p.is_file()}
        assert written, "sanity: artifacts were produced under tmp"
