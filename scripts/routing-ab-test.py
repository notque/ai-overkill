#!/usr/bin/env python3
"""Blind A/B harness for routing experiments.

Originally built for the semantic-first experiment; extended (feat/route-ab-harness)
with manifest-variant arms, pre-registered gates, and a fast-path bucket assertion.
One harness judges ANY router change — never build a parallel one.

LEGACY MODE (no --manifest-arm): compares two routing arms over a labeled corpus,
using ONE Haiku semantic decision per query (reused across both arms):

  Arm A (control, deterministic-first):
      A_route = pre_route  IF pre_route.matched AND confidence == "high"
                else haiku
      This is the CURRENT /do behaviour: a high-confidence keyword match
      short-circuits and skips the semantic router.

  Arm B (treatment, semantic-first + safety net = "Option B"):
      B_route = haiku
      THEN if pre_route is a high-confidence force_route for a SAFETY-critical
      skill (pr-workflow or security-review) and haiku disagrees, override
      B_route to the pre_route target. Semantic decides the long tail;
      deterministic guarantees the safety routes.

Cost model (Haiku calls):
  Arm A makes a Haiku call ONLY when pre_route is not high-confidence
  (i.e. it fell through). Arm B always makes a Haiku call.

MANIFEST-ARM MODE (--manifest-arm name=command, repeatable, --emit-prompts only):
arms differ by manifest, so each arm gets its OWN prompt set and its own Haiku
answer per query. Every arm is scored as production routes today (semantic pick
+ deterministic safety net). The blind judge flow is IDENTICAL; the private uid
map carries (case, arm). Example:

  --manifest-arm full="python3 scripts/routing-manifest.py --compact" \\
  --manifest-arm tiered="python3 scripts/routing-manifest.py --tiered"

Arms may also differ by MODEL instead of (or as well as) manifest: --model-arm
name=model (one per manifest arm) records the per-arm routing model in
arms.json `models` for the bridge ("default" = omit --model, the session
model). The harness still never calls models itself.

This script can NOT call Haiku itself (no API key, by design). It runs in
stages and a human/agent runner bridges them:

  --emit-prompts : writes <out>/prompts/<id>.txt (legacy) or
                   <out>/prompts/<arm>/<id>.txt (manifest arms) plus
                   <out>/queries.json (the ordered query list).
  --score        : reads collected Haiku answers from <out>/answers/<id>.json
                   (legacy) or <out>/answers/<arm>/<id>.json, computes routes +
                   per-query records + cost, and writes raw.json.
  --build-judge  : after --score, builds an arm-stripped, shuffled judge input
                   (judge-input.json) plus a private uid->arm map (uid-map.json
                   the judge never sees).
  --rejoin       : after the judge runs, reads judge-output.json + uid-map.json,
                   rejoins by uid, and writes the scoreboard (scoreboard.json)
                   with per-arm and per-bucket accuracy.
  --gate         : after --score (and normally --rejoin), applies the
                   PRE-REGISTERED promote/reject gates to raw.json using
                   deterministic expected-pair matching. Prints the gates BEFORE
                   the results. Exit 0 PROMOTE, 1 REJECT, 2 UNDERPOWERED.
  --pre-route-map: runs the deterministic pre-router across the whole corpus and
                   writes pre-route-map.json — a fully reproducible (no model)
                   record of which queries Arm A short-circuits (high-confidence
                   keyword match, skips Haiku) vs. defers to the semantic router.
                   With --assert-buckets it becomes the fast-path equivalence
                   check: safety buckets must be fast-path eligible, guard
                   bucket must not. Exit 0/1.

--out-dir (default scripts/routing-ab-results) redirects ALL artifacts; prior
completed runs in the default directory must never be overwritten — give every
new run its own subdirectory.

Corpus schema: {request, expected_agent, expected_skill, category, bucket,
notes} plus OPTIONAL expected_pipeline (default null), acceptable (list of
{agent, skill} alternate pairs), uncertain (best-effort gold label), provenance
({source, workload, sample}: where the case came from — local-telemetry names
the single machine's workload it was sampled from, catalog-derived means it was
written from INDEX semantics, absent resolves to unknown-legacy). Carried into
queries.json/raw.json so a run can be sliced by workload: a delta driven by one
workload's cases is not evidence about the other machines. Absent optional
fields mean legacy behavior; the 49 legacy cases are untouched.

Stdlib only. Deterministic given fixed inputs (shuffle uses a fixed seed).

Usage:
    python3 scripts/routing-ab-test.py --emit-prompts
    python3 scripts/routing-ab-test.py --score
    python3 scripts/routing-ab-test.py --build-judge
    python3 scripts/routing-ab-test.py --rejoin
    python3 scripts/routing-ab-test.py --gate
    python3 scripts/routing-ab-test.py --pre-route-map [--assert-buckets]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
CORPUS = SCRIPTS / "routing-ab-corpus.json"
RESULTS = SCRIPTS / "routing-ab-results"
PROMPTS_DIR = RESULTS / "prompts"
ANSWERS_DIR = RESULTS / "answers"

# Safety-critical force-route skills. Arm B's deterministic safety net only
# fires for these: a high-confidence force_route here overrides a disagreeing
# semantic decision so the commit->quality-gate and security guarantees hold.
SAFETY_SKILLS = {"pr-workflow", "security-review"}

# Gate (c): buckets where a challenger may introduce ZERO new misses.
SAFETY_BUCKETS = {"benchmark-force_route", "false-positive-guard", "paraphrase-git", "paraphrase-security"}

# --assert-buckets: buckets that must / must not be fast-path eligible
# (eligible = pre-route confidence "high" AND match_type "force_route").
FAST_PATH_REQUIRED_BUCKETS = {"benchmark-force_route", "paraphrase-git", "paraphrase-security"}
FAST_PATH_FORBIDDEN_BUCKETS = {"false-positive-guard"}

# Gate UNDERPOWERED threshold: McNemar needs at least this many discordant pairs.
MIN_DISCORDANT_PAIRS = 6

# Pre-registered gates. Printed verbatim BEFORE results by --gate and quoted in
# docs/router-ab-runbook.md. Rule: gates change only BEFORE a run; changing them
# after seeing results invalidates the run.
GATES_TEXT = """\
PRE-REGISTERED GATES (fixed in code before any run; change only BEFORE a run):
  (a) accuracy : challenger accuracy not worse than baseline by more than 3.0 points.
                 correct = exact expected agent+skill pair; where `acceptable` is
                 present, any listed {agent, skill} alternate also counts.
  (b) harm     : McNemar exact p for harm > 0.05. Fails only when challenger-harm
                 pairs exceed challenger-help pairs AND p <= 0.05.
  (c) safety   : ZERO new misses (baseline correct -> challenger wrong) in buckets
                 benchmark-force_route, false-positive-guard, paraphrase-git,
                 paraphrase-security.
  (d) stub-tier: challenger correct count in the stub-tier bucket within 1 case
                 of baseline.
VERDICT: PROMOTE (exit 0) = all gates pass AND discordant pairs >= 6.
         UNDERPOWERED (exit 2) = all gates pass but discordant pairs < 6.
         REJECT (exit 1) = any gate fails."""

# Haiku routing prompt template (REQUEST + MANIFEST filled in).
# Git rule back-ported 2026-07-01 from production skills/meta/do/SKILL.md
# (genuine-git-only). Runs before this date used the blunt "For git operations
# (push, commit, PR, merge), ALWAYS select pr-workflow." rule and are NOT
# template-comparable with later runs.
PROMPT_TEMPLATE = """You are a routing agent. Given a user request and a manifest of available agents, skills, and pipelines, select the BEST agent+skill combination.
USER REQUEST: {request}
ROUTING MANIFEST:
{manifest}
Return your answer as JSON: {{"agent": "...|null","skill":"...|null","pipeline":"...|null","reasoning":"one sentence","confidence":"high/medium/low"}}
FORCE-ROUTE RULE: Entries marked "FORCE" MUST be selected when their domain clearly matches the user's intent. FORCE matching is SEMANTIC, not keyword-based — match what the user MEANS. For GENUINE git / version-control operations — actually pushing code, committing files to a repository, or opening/merging a pull request — ALWAYS select pr-workflow. Do NOT route metaphorical or non-version-control uses of these words (e.g. 'commit to a decision/plan', 'merge ideas in your head', 'push back on a proposal') to pr-workflow. Pick the most specific match. Return a single skill name as a string."""

# Optional corpus fields carried into queries.json/raw.json ONLY when present,
# so legacy artifacts stay byte-identical.
OPTIONAL_CASE_FIELDS = ("expected_pipeline", "acceptable", "uncertain", "provenance")


def _norm(value: object) -> str | None:
    """Normalize a route field: treat null-likes as None, else stripped str."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"null", "none", "n/a", "na"}:
        return None
    return text


def load_corpus(corpus_path: Path | None = None) -> list[dict]:
    path = corpus_path if corpus_path is not None else CORPUS
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["test_cases"]


def query_id(index: int) -> str:
    """Stable per-query id: q00, q01, ... (zero-padded, corpus order)."""
    return f"q{index:02d}"


def run_pre_route(request: str) -> dict:
    """Invoke pre-route.py for one request and parse its JSON output."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "pre-route.py"), "--request", request, "--json-compact"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
        check=False,
    )
    return json.loads(proc.stdout)


def build_manifest() -> str:
    """Generate the compact routing manifest the semantic router consumes."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "routing-manifest.py"), "--compact"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
        check=False,
    )
    return proc.stdout.strip()


def build_manifest_cmd(command: str) -> str:
    """Generate a manifest by running an arm's command string (shlex-split)."""
    proc = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
        check=False,
    )
    return proc.stdout.strip()


def parse_manifest_arms(values: list[str]) -> dict[str, str]:
    """Parse repeated --manifest-arm name=command flags into an ordered map."""
    arms: dict[str, str] = {}
    for value in values:
        name, sep, command = value.partition("=")
        name = name.strip()
        command = command.strip()
        if not sep or not name or not command:
            raise SystemExit(f"ERROR: --manifest-arm must be name=command, got: {value!r}")
        if name in arms:
            raise SystemExit(f"ERROR: duplicate --manifest-arm name: {name!r}")
        arms[name] = command
    if len(arms) < 2:
        raise SystemExit("ERROR: need at least two --manifest-arm flags (baseline + challenger)")
    return arms


def parse_model_arms(values: list[str], arm_names: list[str]) -> dict[str, str]:
    """Parse repeated --model-arm name=model flags; names must match --manifest-arm names.

    The harness never calls models; the bridge reads arms.json `models` to pick
    the `claude -p --model` value per arm (`default` = omit --model, session model).
    """
    models: dict[str, str] = {}
    for value in values:
        name, sep, model = value.partition("=")
        name = name.strip()
        model = model.strip()
        if not sep or not name or not model:
            raise SystemExit(f"ERROR: --model-arm must be name=model, got: {value!r}")
        if name in models:
            raise SystemExit(f"ERROR: duplicate --model-arm name: {name!r}")
        if name not in arm_names:
            raise SystemExit(f"ERROR: --model-arm name {name!r} has no matching --manifest-arm (arms: {arm_names})")
        models[name] = model
    missing = [a for a in arm_names if a not in models]
    if missing:
        raise SystemExit(f"ERROR: --model-arm missing for arms: {missing} (give one per arm)")
    return models


def _query_record(case: dict, qid: str) -> dict:
    """Build one queries.json row. Optional fields appear ONLY when present."""
    row = {
        "id": qid,
        "request": case["request"],
        "expected_agent": case.get("expected_agent"),
        "expected_skill": case.get("expected_skill"),
        "category": case.get("category"),
        "bucket": case.get("bucket"),
        "notes": case.get("notes"),
    }
    for field in OPTIONAL_CASE_FIELDS:
        if field in case:
            row[field] = case[field]
    return row


# --------------------------------------------------------------------------- #
# Mode: emit-prompts
# --------------------------------------------------------------------------- #
def emit_prompts(
    out_dir: Path | None = None,
    manifest_arms: dict[str, str] | None = None,
    corpus_path: Path | None = None,
    model_arms: dict[str, str] | None = None,
) -> int:
    """Write Haiku routing prompts plus the ordered query list.

    Legacy (no manifest_arms): one shared prompt per query under prompts/.
    Manifest arms: one prompt set per arm under prompts/<arm>/, one manifest
    snapshot per arm, answer dirs answers/<arm>/, and arms.json (the arm order
    --score joins on).
    """
    out = out_dir if out_dir is not None else RESULTS
    corpus = load_corpus(corpus_path)

    if manifest_arms:
        manifests: dict[str, str] = {}
        for arm, command in manifest_arms.items():
            manifest = build_manifest_cmd(command)
            if not manifest:
                print(f"ERROR: arm {arm!r} produced an empty manifest; check its entry in arms.json", file=sys.stderr)
                return 1
            manifests[arm] = manifest

        queries = []
        for i, case in enumerate(corpus):
            qid = query_id(i)
            queries.append(_query_record(case, qid))
            for arm, manifest in manifests.items():
                prompt = PROMPT_TEMPLATE.format(request=case["request"], manifest=manifest)
                arm_prompts = out / "prompts" / arm
                arm_prompts.mkdir(parents=True, exist_ok=True)
                (arm_prompts / f"{qid}.txt").write_text(prompt, encoding="utf-8")
        for arm in manifests:
            (out / "answers" / arm).mkdir(parents=True, exist_ok=True)
            (out / f"manifest-used-{arm}.txt").write_text(manifests[arm], encoding="utf-8")

        (out / "queries.json").write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
        arms_record: dict = {"arms": list(manifest_arms), "commands": manifest_arms}
        if model_arms:
            arms_record["models"] = model_arms
        (out / "arms.json").write_text(
            json.dumps(arms_record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {len(queries)} prompts per arm ({', '.join(manifest_arms)}) under {out / 'prompts'}")
        print(f"Query list: {out / 'queries.json'}")
        print(f"Arm map: {out / 'arms.json'}")
        print(f"Drop Haiku JSON answers into {out / 'answers'}/<arm>/<id>.json, then run --score")
        return 0

    manifest = build_manifest()
    if not manifest:
        print("ERROR: empty manifest from routing-manifest.py", file=sys.stderr)
        return 1

    prompts_dir = out / "prompts"
    answers_dir = out / "answers"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    queries = []
    for i, case in enumerate(corpus):
        qid = query_id(i)
        request = case["request"]
        prompt = PROMPT_TEMPLATE.format(request=request, manifest=manifest)
        (prompts_dir / f"{qid}.txt").write_text(prompt, encoding="utf-8")
        queries.append(_query_record(case, qid))

    (out / "queries.json").write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
    # Persist the manifest used, so the experiment is reproducible.
    (out / "manifest-used.txt").write_text(manifest, encoding="utf-8")
    print(f"Wrote {len(queries)} prompts to {prompts_dir}")
    print(f"Query list: {out / 'queries.json'}")
    print(f"Manifest snapshot: {out / 'manifest-used.txt'}")
    print(f"Drop Haiku JSON answers into {answers_dir}/<id>.json, then run --score")
    return 0


# --------------------------------------------------------------------------- #
# Mode: score
# --------------------------------------------------------------------------- #
def _haiku_skill(haiku: dict) -> str | None:
    return _norm(haiku.get("skill"))


def _haiku_agent(haiku: dict) -> str | None:
    return _norm(haiku.get("agent"))


def compute_arms(pre_route: dict, haiku: dict) -> dict:
    """Compute Arm A and Arm B routes + cost flags from one Haiku decision."""
    pr_high = bool(pre_route.get("matched")) and pre_route.get("confidence") == "high"
    pr_skill = _norm(pre_route.get("skill"))
    pr_agent = _norm(pre_route.get("agent"))
    pr_force = pre_route.get("match_type") == "force_route"

    h_skill = _haiku_skill(haiku)
    h_agent = _haiku_agent(haiku)

    # Arm A: deterministic-first short-circuit.
    if pr_high:
        a_skill, a_agent, a_source = pr_skill, pr_agent, "pre_route"
        a_haiku_calls = 0
    else:
        a_skill, a_agent, a_source = h_skill, h_agent, "haiku"
        a_haiku_calls = 1

    # Arm B: semantic-first, then safety net.
    b_skill, b_agent, b_source = h_skill, h_agent, "haiku"
    safety_override = False
    if pr_high and pr_force and pr_skill in SAFETY_SKILLS and h_skill != pr_skill:
        b_skill, b_agent, b_source = pr_skill, pr_agent, "safety_net"
        safety_override = True
    b_haiku_calls = 1  # Arm B always asks the model.

    return {
        "pre_route_high": pr_high,
        "pre_route_force": pr_force,
        "A_skill": a_skill,
        "A_agent": a_agent,
        "A_source": a_source,
        "A_haiku_calls": a_haiku_calls,
        "B_skill": b_skill,
        "B_agent": b_agent,
        "B_source": b_source,
        "B_haiku_calls": b_haiku_calls,
        "B_safety_override": safety_override,
    }


def compute_manifest_route(pre_route: dict, haiku: dict) -> dict:
    """Route one manifest arm exactly as production routes today.

    Semantic pick first, then the deterministic safety net (same rule as legacy
    Arm B): a high-confidence force_route for a safety-critical skill overrides
    a disagreeing semantic decision.
    """
    pr_high = bool(pre_route.get("matched")) and pre_route.get("confidence") == "high"
    pr_force = pre_route.get("match_type") == "force_route"
    pr_skill = _norm(pre_route.get("skill"))
    pr_agent = _norm(pre_route.get("agent"))

    skill, agent, source = _haiku_skill(haiku), _haiku_agent(haiku), "haiku"
    safety_override = False
    if pr_high and pr_force and pr_skill in SAFETY_SKILLS and skill != pr_skill:
        skill, agent, source = pr_skill, pr_agent, "safety_net"
        safety_override = True
    return {
        "agent": agent,
        "skill": skill,
        "pipeline": _norm(haiku.get("pipeline")),
        "source": source,
        "safety_override": safety_override,
    }


def _score_manifest_arms(out: Path, arms: list[str]) -> int:
    """Join per-arm Haiku answers into raw.json (manifest-arm mode)."""
    queries = json.loads((out / "queries.json").read_text(encoding="utf-8"))

    records = []
    missing = []
    cost = dict.fromkeys(arms, 0)
    for q in queries:
        qid = q["id"]
        answers = {}
        for arm in arms:
            ans_path = out / "answers" / arm / f"{qid}.json"
            if not ans_path.exists():
                missing.append(f"{arm}/{qid}")
                continue
            answers[arm] = json.loads(ans_path.read_text(encoding="utf-8"))
        if len(answers) != len(arms):
            continue
        pre_route = run_pre_route(q["request"])
        rec = {
            "id": qid,
            "query": q["request"],
            "bucket": q["bucket"],
            "category": q["category"],
            "expected_agent": q["expected_agent"],
            "expected_skill": q["expected_skill"],
            "notes": q["notes"],
        }
        for field in OPTIONAL_CASE_FIELDS:
            if field in q:
                rec[field] = q[field]
        rec["pre_route"] = pre_route
        rec["arms"] = {}
        for arm in arms:
            route = compute_manifest_route(pre_route, answers[arm])
            cost[arm] += 1  # every manifest arm asks the model once per query
            rec["arms"][arm] = {"haiku_raw": answers[arm], "route": route}
        records.append(rec)

    if missing:
        print(f"ERROR: missing Haiku answers for {len(missing)} (arm/query) pairs: {missing}", file=sys.stderr)
        print(f"Drop each as {out / 'answers'}/<arm>/<id>.json then re-run --score", file=sys.stderr)
        return 1

    n = len(records)
    out_data = {
        "n_queries": n,
        "arms": arms,
        "cost": {
            "haiku_calls_total": {arm: cost[arm] for arm in arms},
            "calls_per_request": {arm: round(cost[arm] / n, 3) if n else 0 for arm in arms},
        },
        "records": records,
    }
    (out / "raw.json").write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Scored {n} queries x {len(arms)} arms -> {out / 'raw.json'}")
    print(f"Cost: " + ", ".join(f"{arm}={cost[arm]} Haiku calls" for arm in arms))
    return 0


def score(out_dir: Path | None = None) -> int:
    """Read collected Haiku answers, compute routes per arm, write raw.json."""
    out = out_dir if out_dir is not None else RESULTS
    queries_path = out / "queries.json"
    if not queries_path.exists():
        print("ERROR: run --emit-prompts first (queries.json missing)", file=sys.stderr)
        return 1

    arms_path = out / "arms.json"
    if arms_path.exists():
        arms = json.loads(arms_path.read_text(encoding="utf-8"))["arms"]
        return _score_manifest_arms(out, arms)

    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    answers_dir = out / "answers"

    records = []
    missing = []
    cost_a = cost_b = 0
    for q in queries:
        qid = q["id"]
        ans_path = answers_dir / f"{qid}.json"
        if not ans_path.exists():
            missing.append(qid)
            continue
        haiku = json.loads(ans_path.read_text(encoding="utf-8"))
        pre_route = run_pre_route(q["request"])
        arms = compute_arms(pre_route, haiku)
        cost_a += arms["A_haiku_calls"]
        cost_b += arms["B_haiku_calls"]
        records.append(
            {
                "id": qid,
                "query": q["request"],
                "bucket": q["bucket"],
                "category": q["category"],
                "expected_agent": q["expected_agent"],
                "expected_skill": q["expected_skill"],
                "notes": q["notes"],
                "pre_route": pre_route,
                "haiku_raw": haiku,
                "A_route": {"agent": arms["A_agent"], "skill": arms["A_skill"], "source": arms["A_source"]},
                "B_route": {"agent": arms["B_agent"], "skill": arms["B_skill"], "source": arms["B_source"]},
                "A_haiku_calls": arms["A_haiku_calls"],
                "B_haiku_calls": arms["B_haiku_calls"],
                "B_safety_override": arms["B_safety_override"],
            }
        )

    if missing:
        print(f"ERROR: missing Haiku answers for {len(missing)} queries: {missing}", file=sys.stderr)
        print(f"Drop each as {answers_dir}/<id>.json then re-run --score", file=sys.stderr)
        return 1

    out_data = {
        "n_queries": len(records),
        "cost": {
            "A_haiku_calls_total": cost_a,
            "B_haiku_calls_total": cost_b,
            "A_calls_per_request": round(cost_a / len(records), 3) if records else 0,
            "B_calls_per_request": round(cost_b / len(records), 3) if records else 0,
            "delta_calls_per_request": round((cost_b - cost_a) / len(records), 3) if records else 0,
        },
        "records": records,
    }
    (out / "raw.json").write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Scored {len(records)} queries -> {out / 'raw.json'}")
    print(
        f"Cost: A={cost_a} Haiku calls, B={cost_b} Haiku calls (delta {out_data['cost']['delta_calls_per_request']}/request)"
    )
    return 0


# --------------------------------------------------------------------------- #
# Mode: build-judge
# --------------------------------------------------------------------------- #
def build_judge(out_dir: Path | None = None) -> int:
    """Build a shuffled, arm-stripped judge input + private uid->arm map.

    Each arm's prediction becomes its own row with a fresh uid. Rows carry NO
    arm field and NO method hint. Rows are interleaved by a seeded shuffle so
    the judge cannot infer arm from position. Works for legacy A/B raw.json and
    for manifest-arm raw.json (uid map carries the arm name).
    """
    out = out_dir if out_dir is not None else RESULTS
    raw_path = out / "raw.json"
    if not raw_path.exists():
        print("ERROR: run --score first (raw.json missing)", file=sys.stderr)
        return 1
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    rows = []
    uid_map = {}
    uid = 0
    for rec in raw["records"]:
        if "arms" in raw:
            arm_routes = [(arm, rec["arms"][arm]["route"]) for arm in raw["arms"]]
        else:
            arm_routes = [(arm_key[0], rec[arm_key]) for arm_key in ("A_route", "B_route")]
        for arm, route in arm_routes:
            uid_str = f"u{uid:03d}"
            uid += 1
            rows.append(
                {
                    "uid": uid_str,
                    "query": rec["query"],
                    "expected_agent": rec["expected_agent"],
                    "expected_skill": rec["expected_skill"],
                    "notes": rec["notes"],
                    "predicted_agent": route["agent"],
                    "predicted_skill": route["skill"],
                }
            )
            uid_map[uid_str] = {"query_id": rec["id"], "arm": arm, "bucket": rec["bucket"]}

    rng = random.Random(20260527)  # fixed seed: reproducible interleave
    rng.shuffle(rows)

    (out / "judge-input.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "uid-map.json").write_text(json.dumps(uid_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(rows)} arm-stripped rows -> {out / 'judge-input.json'}")
    print(f"Private map (judge never sees) -> {out / 'uid-map.json'}")
    print("Dispatch ONE judge agent over judge-input.json; save its JSON to judge-output.json; then --rejoin")
    return 0


# --------------------------------------------------------------------------- #
# Mode: rejoin
# --------------------------------------------------------------------------- #
def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def rejoin(out_dir: Path | None = None) -> int:
    """Rejoin judge output by uid -> per-arm and per-bucket accuracy."""
    out = out_dir if out_dir is not None else RESULTS
    jo_path = out / "judge-output.json"
    map_path = out / "uid-map.json"
    if not jo_path.exists() or not map_path.exists():
        print("ERROR: need judge-output.json and uid-map.json (run --build-judge + judge)", file=sys.stderr)
        return 1
    judged = json.loads(jo_path.read_text(encoding="utf-8"))
    uid_map = json.loads(map_path.read_text(encoding="utf-8"))

    # Accept either {uid: verdict} or {uid: {"verdict": ...}} shapes.
    def verdict_of(value: object) -> str:
        if isinstance(value, dict):
            return str(value.get("verdict", "")).strip().lower()
        return str(value).strip().lower()

    # Arm names come from the uid map: legacy runs yield A/B, manifest-arm runs
    # yield the --manifest-arm names. Legacy output is unchanged (sorted = A, B).
    arms = sorted({meta["arm"] for meta in uid_map.values()})

    # arm -> verdict -> count ; arm -> bucket -> verdict -> count
    arm_tally: dict[str, dict[str, int]] = {arm: {} for arm in arms}
    bucket_tally: dict[str, dict[str, dict[str, int]]] = {arm: {} for arm in arms}
    per_uid = {}
    missing = []
    for uid, meta in uid_map.items():
        if uid not in judged:
            missing.append(uid)
            continue
        v = verdict_of(judged[uid])
        if v not in {"correct", "partial", "incorrect"}:
            v = "incorrect"
        arm = meta["arm"]
        bucket = meta["bucket"]
        arm_tally[arm][v] = arm_tally[arm].get(v, 0) + 1
        bucket_tally[arm].setdefault(bucket, {})
        bucket_tally[arm][bucket][v] = bucket_tally[arm][bucket].get(v, 0) + 1
        per_uid[uid] = {"arm": arm, "bucket": bucket, "query_id": meta["query_id"], "verdict": v}

    if missing:
        print(f"ERROR: judge output missing {len(missing)} uids: {missing}", file=sys.stderr)
        return 1

    def summarize(tally: dict[str, int]) -> dict:
        c = tally.get("correct", 0)
        p = tally.get("partial", 0)
        i = tally.get("incorrect", 0)
        n = c + p + i
        return {
            "n": n,
            "correct": c,
            "partial": p,
            "incorrect": i,
            "correct_pct": _pct(c, n),
            "partial_pct": _pct(p, n),
            "incorrect_pct": _pct(i, n),
            # accuracy = correct + half credit for partial (reported separately too)
            "accuracy_strict_pct": _pct(c, n),
            "accuracy_lenient_pct": round(_pct(c, n) + 0.5 * _pct(p, n), 1),
        }

    buckets = sorted({m["bucket"] for m in uid_map.values()})
    scoreboard = {
        "overall": {arm: summarize(arm_tally[arm]) for arm in arms},
        "per_bucket": {
            bucket: {arm: summarize(bucket_tally[arm].get(bucket, {})) for arm in arms} for bucket in buckets
        },
        "per_uid": per_uid,
    }
    (out / "scoreboard.json").write_text(json.dumps(scoreboard, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable summary to stdout.
    print("=== OVERALL (strict = correct only) ===")
    for arm in arms:
        s = scoreboard["overall"][arm]
        print(
            f"  Arm {arm}: {s['correct']}/{s['n']} correct ({s['correct_pct']}%), "
            f"{s['partial']} partial, {s['incorrect']} incorrect"
        )
    print(f"=== PER BUCKET (correct% {' -> '.join(arms)}) ===")
    for bucket in buckets:
        parts = []
        for arm in arms:
            s = scoreboard["per_bucket"][bucket][arm]
            parts.append(f"{arm}={s['correct']}/{s['n']} ({s['correct_pct']}%)")
        print(f"  {bucket:24s} " + "  ".join(parts))
    print(f"Scoreboard -> {out / 'scoreboard.json'}")
    return 0


# --------------------------------------------------------------------------- #
# Mode: gate (pre-registered promote/reject verdict)
# --------------------------------------------------------------------------- #
def _mcnemar_exact_p(b01: int, b10: int) -> float:
    """Two-sided exact McNemar p over the n=b01+b10 discordant pairs (binomial,
    p=0.5). Returns 1.0 when there are no discordant pairs.

    Ported verbatim from feat/outcome-routing-loop:scripts/route-value-eval.py.
    """
    n = b01 + b10
    if n == 0:
        return 1.0
    k = min(b01, b10)
    # Two-sided: 2 * sum_{i=0..k} C(n,i) (0.5)^n, clamped to 1.
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    return min(1.0, 2.0 * tail)


def compute_paired_stats(
    per_case: list[dict],
    seed: int = 20260527,
    bootstrap_iters: int = 5000,
) -> dict:
    """Paired baseline/challenger stats: D, 95% bootstrap CI, help/harm, McNemar p.

    per_case: list of {"baseline_correct": bool, "challenger_correct": bool}.
    Shape ported from compute_value_stats in
    feat/outcome-routing-loop:scripts/route-value-eval.py (paired bootstrap on D,
    discordant-pair McNemar), renamed to baseline/challenger.
    """
    k = len(per_case)
    base = [bool(c["baseline_correct"]) for c in per_case]
    chal = [bool(c["challenger_correct"]) for c in per_case]
    d = (sum(chal) - sum(base)) / k if k else 0.0

    harm = sum(1 for b, c in zip(base, chal) if b and not c)  # baseline right, challenger wrong
    help_ = sum(1 for b, c in zip(base, chal) if (not b) and c)  # baseline wrong, challenger right

    ci_low = ci_high = 0.0
    if k:
        rng = random.Random(seed)
        diffs = [int(c) - int(b) for b, c in zip(base, chal)]
        deltas = []
        for _ in range(bootstrap_iters):
            sample = [diffs[rng.randrange(k)] for _ in range(k)]
            deltas.append(sum(sample) / k)
        deltas.sort()
        ci_low = deltas[int(0.025 * bootstrap_iters)]
        ci_high = deltas[min(int(0.975 * bootstrap_iters), bootstrap_iters - 1)]

    return {
        "n": k,
        "baseline_correct": sum(base),
        "challenger_correct": sum(chal),
        "D": d,
        "D_ci_low": ci_low,
        "D_ci_high": ci_high,
        "help": help_,
        "harm": harm,
        "discordant": help_ + harm,
        "mcnemar_p": _mcnemar_exact_p(help_, harm),
    }


def route_correct(rec: dict, route: dict) -> bool:
    """Deterministic correctness: exact expected pair, or any `acceptable` alternate."""
    agent = _norm(route.get("agent"))
    skill = _norm(route.get("skill"))
    if agent == _norm(rec.get("expected_agent")) and skill == _norm(rec.get("expected_skill")):
        return True
    for alt in rec.get("acceptable", []) or []:
        if agent == _norm(alt.get("agent")) and skill == _norm(alt.get("skill")):
            return True
    return False


def _arm_route(raw: dict, rec: dict, arm: str) -> dict:
    """Fetch one arm's route from a legacy or manifest-arm raw.json record."""
    if "arms" in raw:
        return rec["arms"][arm]["route"]
    return rec[f"{arm}_route"]


def gate_verdict(raw: dict, baseline: str, challenger: str) -> dict:
    """Apply the pre-registered gates to raw.json. Pure; no I/O."""
    records = raw["records"]
    n = len(records)
    per_case = []
    new_safety_misses = []
    stub_base = stub_chal = stub_n = 0
    for rec in records:
        b_ok = route_correct(rec, _arm_route(raw, rec, baseline))
        c_ok = route_correct(rec, _arm_route(raw, rec, challenger))
        per_case.append({"baseline_correct": b_ok, "challenger_correct": c_ok})
        if rec["bucket"] in SAFETY_BUCKETS and b_ok and not c_ok:
            new_safety_misses.append(rec["id"])
        if rec["bucket"] == "stub-tier":
            stub_n += 1
            stub_base += b_ok
            stub_chal += c_ok

    stats = compute_paired_stats(per_case)
    base_acc = _pct(stats["baseline_correct"], n)
    chal_acc = _pct(stats["challenger_correct"], n)

    gate_a = chal_acc >= base_acc - 3.0
    harm_significant = stats["harm"] > stats["help"] and stats["mcnemar_p"] <= 0.05
    gate_b = not harm_significant
    gate_c = len(new_safety_misses) == 0
    gate_d = stub_chal >= stub_base - 1  # vacuously true when stub_n == 0

    gates = {"a_accuracy": gate_a, "b_harm": gate_b, "c_safety_buckets": gate_c, "d_stub_tier": gate_d}
    all_pass = all(gates.values())
    underpowered = stats["discordant"] < MIN_DISCORDANT_PAIRS
    if not all_pass:
        verdict, exit_code = "REJECT", 1
    elif underpowered:
        verdict, exit_code = "UNDERPOWERED", 2
    else:
        verdict, exit_code = "PROMOTE", 0

    return {
        "baseline": baseline,
        "challenger": challenger,
        "n": n,
        "baseline_accuracy_pct": base_acc,
        "challenger_accuracy_pct": chal_acc,
        "stats": stats,
        "new_safety_misses": new_safety_misses,
        "stub_tier": {"n": stub_n, "baseline_correct": stub_base, "challenger_correct": stub_chal},
        "gates": gates,
        "failing_gates": [k for k, v in gates.items() if not v],
        "discordant_pairs": stats["discordant"],
        "min_discordant_pairs": MIN_DISCORDANT_PAIRS,
        "verdict": verdict,
        "exit_code": exit_code,
    }


def gate(out_dir: Path | None = None, baseline: str | None = None, challenger: str | None = None) -> int:
    """Print the pre-registered gates, then the verdict. Exit 0/1/2."""
    out = out_dir if out_dir is not None else RESULTS
    raw_path = out / "raw.json"
    if not raw_path.exists():
        print("ERROR: run --score first (raw.json missing)", file=sys.stderr)
        return 1
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    arms = raw.get("arms", ["A", "B"])
    baseline = baseline if baseline is not None else arms[0]
    challenger = challenger if challenger is not None else arms[1]
    for arm in (baseline, challenger):
        if arm not in arms:
            print(f"ERROR: arm {arm!r} not in raw.json arms {arms}", file=sys.stderr)
            return 1
    if baseline == challenger:
        print("ERROR: baseline and challenger must differ", file=sys.stderr)
        return 1

    # Gates print BEFORE any result, by design.
    print(GATES_TEXT)
    print()

    result = gate_verdict(raw, baseline, challenger)
    (out / "gate-verdict.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    s = result["stats"]
    print(f"=== RESULTS (baseline={baseline}, challenger={challenger}, n={result['n']}) ===")
    print(f"  accuracy: baseline={result['baseline_accuracy_pct']}% challenger={result['challenger_accuracy_pct']}%")
    print(
        f"  paired: D={round(s['D'], 4)} 95% CI [{round(s['D_ci_low'], 4)}, {round(s['D_ci_high'], 4)}] "
        f"help={s['help']} harm={s['harm']} discordant={s['discordant']} mcnemar_p={round(s['mcnemar_p'], 4)}"
    )
    print(f"  new safety-bucket misses: {result['new_safety_misses'] or 'none'}")
    st = result["stub_tier"]
    print(f"  stub-tier: n={st['n']} baseline={st['baseline_correct']} challenger={st['challenger_correct']}")
    print(f"  gates: {json.dumps(result['gates'])}")
    print(f"VERDICT: {result['verdict']} (exit {result['exit_code']})")
    print(f"Gate verdict -> {out / 'gate-verdict.json'}")
    return result["exit_code"]


# --------------------------------------------------------------------------- #
# Mode: pre-route-map (deterministic, no model required)
# --------------------------------------------------------------------------- #
def pre_route_map(
    out_dir: Path | None = None,
    assert_buckets: bool = False,
    corpus_path: Path | None = None,
) -> int:
    """Record, per corpus query, what the deterministic pre-router decides.

    Fully reproducible: depends only on pre-route.py + the INDEX files. This is
    the Arm A short-circuit map — queries with confidence == high skip Haiku;
    everything else defers to the semantic router. Quantifies the keyword-first
    coverage gap on paraphrased intents.

    With assert_buckets (the fast-path equivalence check, zero model calls):
    every benchmark-force_route, paraphrase-git, and paraphrase-security case
    must be fast-path eligible (confidence "high" AND match_type "force_route");
    every false-positive-guard case must NOT be. Returns 1 on any violation.
    """
    out = out_dir if out_dir is not None else RESULTS
    corpus = load_corpus(corpus_path)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    bucket_stats: dict[str, dict[str, int]] = {}
    for i, case in enumerate(corpus):
        pr = run_pre_route(case["request"])
        high = bool(pr.get("matched")) and pr.get("confidence") == "high"
        bucket = case["bucket"]
        bucket_stats.setdefault(bucket, {"total": 0, "short_circuit": 0, "deferred": 0})
        bucket_stats[bucket]["total"] += 1
        bucket_stats[bucket]["short_circuit" if high else "deferred"] += 1
        rows.append(
            {
                "id": query_id(i),
                "query": case["request"],
                "bucket": bucket,
                "expected_skill": case.get("expected_skill"),
                "expected_agent": case.get("expected_agent"),
                "pre_route_matched": bool(pr.get("matched")),
                "pre_route_confidence": pr.get("confidence"),
                "pre_route_skill": _norm(pr.get("skill")),
                "pre_route_agent": _norm(pr.get("agent")),
                "pre_route_match_type": pr.get("match_type"),
                "arm_A_short_circuits": high,
                "arm_A_skips_haiku": high,
            }
        )

    short = sum(1 for r in rows if r["arm_A_short_circuits"])
    out_data = {
        "n_queries": len(rows),
        "short_circuit_count": short,
        "deferred_to_semantic_count": len(rows) - short,
        "per_bucket": bucket_stats,
        "rows": rows,
    }
    (out / "pre-route-map.json").write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Pre-route map -> {out / 'pre-route-map.json'}")
    print(
        f"{short}/{len(rows)} queries short-circuit (Arm A skips Haiku); "
        f"{len(rows) - short} defer to the semantic router"
    )
    print("Per bucket (short_circuit/total):")
    for b in sorted(bucket_stats):
        s = bucket_stats[b]
        print(f"  {b:24s} {s['short_circuit']}/{s['total']}")

    if assert_buckets:
        return _assert_buckets(rows)
    return 0


def _assert_buckets(rows: list[dict]) -> int:
    """Fast-path equivalence assertion over pre-route-map rows. Exit 0/1."""
    violations = []
    for r in rows:
        eligible = r["pre_route_confidence"] == "high" and r["pre_route_match_type"] == "force_route"
        if r["bucket"] in FAST_PATH_REQUIRED_BUCKETS and not eligible:
            violations.append(
                f"{r['id']} [{r['bucket']}] NOT fast-path eligible "
                f"(confidence={r['pre_route_confidence']}, match_type={r['pre_route_match_type']}): {r['query']!r}"
            )
        elif r["bucket"] in FAST_PATH_FORBIDDEN_BUCKETS and eligible:
            violations.append(
                f"{r['id']} [{r['bucket']}] MUST NOT be fast-path eligible but is "
                f"(skill={r['pre_route_skill']}): {r['query']!r}"
            )

    checked = sum(1 for r in rows if r["bucket"] in (FAST_PATH_REQUIRED_BUCKETS | FAST_PATH_FORBIDDEN_BUCKETS))
    print(f"=== ASSERT BUCKETS (fast-path equivalence, {checked} cases checked) ===")
    print(f"  required eligible : {sorted(FAST_PATH_REQUIRED_BUCKETS)}")
    print(f"  forbidden eligible: {sorted(FAST_PATH_FORBIDDEN_BUCKETS)}")
    if violations:
        print(f"FAIL: {len(violations)} violations")
        for v in violations:
            print(f"  {v}")
        return 1
    print("PASS: all asserted buckets conform")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Blind A/B routing experiment harness.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit-prompts", action="store_true", help="Write per-query Haiku prompts.")
    group.add_argument("--score", action="store_true", help="Score collected answers into raw.json.")
    group.add_argument("--build-judge", action="store_true", help="Build arm-stripped judge input.")
    group.add_argument("--rejoin", action="store_true", help="Rejoin judge output into scoreboard.")
    group.add_argument("--gate", action="store_true", help="Apply pre-registered gates to raw.json (exit 0/1/2).")
    group.add_argument(
        "--pre-route-map",
        action="store_true",
        help="Deterministic pre-router map across the corpus (no model needed).",
    )
    parser.add_argument(
        "--manifest-arm",
        action="append",
        default=None,
        metavar="NAME=COMMAND",
        help="Repeatable, --emit-prompts only: per-arm manifest command, e.g. "
        'tiered="python3 scripts/routing-manifest.py --tiered". Omit for legacy single-prompt mode.',
    )
    parser.add_argument(
        "--model-arm",
        action="append",
        default=None,
        metavar="NAME=MODEL",
        help="Repeatable, with --emit-prompts --manifest-arm only: per-arm routing model, recorded in "
        'arms.json for the bridge, e.g. haiku=haiku self-route=default ("default" = omit --model). '
        "One per manifest arm.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Artifact directory (default scripts/routing-ab-results). Use a fresh subdirectory per run; "
        "never overwrite a completed run.",
    )
    parser.add_argument(
        "--corpus", type=Path, default=None, help="Corpus path (default scripts/routing-ab-corpus.json)."
    )
    parser.add_argument("--baseline-arm", default=None, help="--gate: baseline arm name (default: first arm).")
    parser.add_argument("--challenger-arm", default=None, help="--gate: challenger arm name (default: second arm).")
    parser.add_argument(
        "--assert-buckets",
        action="store_true",
        help="--pre-route-map only: assert fast-path bucket eligibility (exit 1 on violation).",
    )
    args = parser.parse_args()

    if args.manifest_arm and not args.emit_prompts:
        parser.error("--manifest-arm is only valid with --emit-prompts (later modes read arms.json)")
    if args.model_arm and not args.manifest_arm:
        parser.error("--model-arm is only valid with --emit-prompts --manifest-arm")
    if args.assert_buckets and not args.pre_route_map:
        parser.error("--assert-buckets is only valid with --pre-route-map")
    if (args.baseline_arm or args.challenger_arm) and not args.gate:
        parser.error("--baseline-arm/--challenger-arm are only valid with --gate")

    if args.emit_prompts:
        manifest_arms = parse_manifest_arms(args.manifest_arm) if args.manifest_arm else None
        model_arms = parse_model_arms(args.model_arm, list(manifest_arms)) if args.model_arm else None
        return emit_prompts(
            out_dir=args.out_dir, manifest_arms=manifest_arms, corpus_path=args.corpus, model_arms=model_arms
        )
    if args.score:
        return score(out_dir=args.out_dir)
    if args.build_judge:
        return build_judge(out_dir=args.out_dir)
    if args.rejoin:
        return rejoin(out_dir=args.out_dir)
    if args.gate:
        return gate(out_dir=args.out_dir, baseline=args.baseline_arm, challenger=args.challenger_arm)
    if args.pre_route_map:
        return pre_route_map(out_dir=args.out_dir, assert_buckets=args.assert_buckets, corpus_path=args.corpus)
    return 1


if __name__ == "__main__":
    sys.exit(main())
