#!/usr/bin/env python3
"""Automated Rules Distillation — ADR-114.

Scans all skill and pipeline SKILL.md files for cross-cutting principles,
applies a four-layer filter, and writes candidate proposals to
~/.claude/learning/rules-distill-pending.json for in-session user approval.

Four-layer filter (from ADR-114):
  1. Principle appears in 2+ skills
  2. Principle is actionable ("do X" / "don't do Y")
  3. Clear violation risk exists (what breaks if ignored)
  4. Not already covered in existing shared patterns (including diff wording)

NEVER auto-applies. All writes require explicit in-session user approval.

Usage:
    python3 scripts/rules-distill.py             # Full run, writes pending.json
    python3 scripts/rules-distill.py --dry-run   # Preview only, no file writes
    python3 scripts/rules-distill.py --auto      # Cron mode (same as full run)
    python3 scripts/rules-distill.py --status    # Show current pending candidates
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
PIPELINES_DIR = REPO_ROOT / "pipelines"
SHARED_PATTERNS_DIR = SKILLS_DIR / "shared-patterns"
CLAUDE_DIR = Path.home() / ".claude"
LEARNING_DIR = CLAUDE_DIR / "learning"
PENDING_JSON = LEARNING_DIR / "rules-distill-pending.json"
LAST_RUN_FILE = LEARNING_DIR / "rules-distill-last-run"

# How many days before a pending candidate is auto-promoted to "deferred"
STALENESS_DAYS = 30

# ---------------------------------------------------------------------------
# Pattern extraction helpers
# ---------------------------------------------------------------------------

# Sentences or bullet items that look like behavioral rules
_RULE_RE = re.compile(
    r"""
    (?:
        # Imperative bullet: "- Always X", "- Never Y", "* ALWAYS X"
        ^[ \t]*[-*]\s+
        (?:
            \*{0,2}(?:always|never|must|do not|don't|avoid|require|ensure|verify|
                      check|run|use|prefer|return|exit|write|read|follow|enforce|
                      block|reject|emit|log|skip)\b
        )
        .{10,200}
        |
        # Bold inline rule: "**ALWAYS** do X"
        ^[ \t]*\*{2}(?:ALWAYS|NEVER|MUST|DO NOT|AVOID|REQUIRE|ENSURE)\*{2}.{5,200}
        |
        # Numbered list rule: "1. Always X" / "2. Never Y"
        ^[ \t]*\d+[.)]\s+
        (?:
            (?:always|never|must|do not|don't|avoid|require|ensure|verify|
               check|run|use|prefer|return|exit|write|read|follow|enforce|
               block|reject|emit|log|skip)\b
        )
        .{10,200}
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Strip markdown emphasis and clean up a candidate sentence
_STRIP_MD = re.compile(r"\*{1,3}|`")
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = _STRIP_MD.sub("", text).strip()
    text = _WS.sub(" ", text)
    # Truncate very long principles
    if len(text) > 200:
        text = text[:197] + "..."
    return text


def extract_principles_from_text(text: str, source_label: str) -> list[dict]:
    """Extract rule-like sentences from markdown text.

    Returns a list of dicts:
        {"principle": str, "raw": str, "source": str}
    """
    results = []
    for m in _RULE_RE.finditer(text):
        raw = m.group(0).strip()
        principle = _clean(raw)
        if len(principle) < 15:
            continue
        results.append({"principle": principle, "raw": raw, "source": source_label})
    return results


# ---------------------------------------------------------------------------
# Skill scanning
# ---------------------------------------------------------------------------


def collect_skill_files() -> list[Path]:
    """Return all SKILL.md files under skills/ (not shared-patterns/)."""
    paths: list[Path] = []
    for root in (SKILLS_DIR, PIPELINES_DIR):
        if not root.exists():
            continue
        for p in sorted(root.rglob("SKILL.md")):
            # Skip shared-patterns — those ARE the baseline
            if "shared-patterns" in p.parts:
                continue
            paths.append(p)
    return paths


def collect_shared_pattern_files() -> list[Path]:
    """Return all markdown files in skills/shared-patterns/."""
    if not SHARED_PATTERNS_DIR.exists():
        return []
    return sorted(SHARED_PATTERNS_DIR.glob("*.md"))


def read_skill(path: Path) -> dict:
    """Read a skill file and return metadata + content."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {"path": str(path), "name": path.parent.name, "content": ""}
    return {
        "path": str(path),
        "name": path.parent.name,
        "content": content,
    }


# ---------------------------------------------------------------------------
# Four-layer filter
# ---------------------------------------------------------------------------


def filter_layer1_multi_skill(
    candidates: list[dict],
    min_skills: int = 2,
) -> list[dict]:
    """Layer 1: principle must appear in 2+ skills.

    Groups extracted principles by normalized text. Principles seen only in
    one skill are discarded.

    Returns candidates enriched with "skills" (list of source labels) and
    "occurrence_count".
    """
    from collections import defaultdict

    # Normalize: lowercase + collapse whitespace for grouping
    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().strip())

    groups: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        key = normalize(c["principle"])
        groups[key].append(c)

    result = []
    for key, items in groups.items():
        # Deduplicate sources (a skill file may repeat a principle)
        seen_sources: set[str] = set()
        unique_sources = []
        for item in items:
            if item["source"] not in seen_sources:
                seen_sources.add(item["source"])
                unique_sources.append(item["source"])

        if len(seen_sources) < min_skills:
            continue

        # Use the first occurrence as the canonical form
        canonical = items[0]
        result.append(
            {
                **canonical,
                "skills": unique_sources,
                "occurrence_count": len(seen_sources),
            }
        )
    return result


# Actionability keywords: start of trimmed principle (after removing bullet/number)
_ACTIONABLE_RE = re.compile(
    r"\b(?:always|never|must|do not|don't|avoid|require|ensure|verify|"
    r"check|run|use|prefer|return|exit|write|read|follow|enforce|"
    r"block|reject|emit|log|skip|call|parse|store|assert|confirm|validate)\b",
    re.IGNORECASE,
)


def filter_layer2_actionable(candidates: list[dict]) -> list[dict]:
    """Layer 2: principle must be actionable ('do X' or 'don't do Y').

    Checks for imperative/prohibitive language in the principle text.
    """
    result = []
    for c in candidates:
        if _ACTIONABLE_RE.search(c["principle"]):
            result.append(c)
    return result


# Violation risk: phrases that suggest consequences
_VIOLATION_RE = re.compile(
    r"\b(?:otherwise|fail|break|error|corrupt|lose|miss|skip|block|reject|"
    r"prevent|deadlock|hang|crash|inconsistent|stale|invalid|unsafe|"
    r"non-blocking|exit 0|exits 0|always exit|never block)\b",
    re.IGNORECASE,
)


def filter_layer3_violation_risk(
    candidates: list[dict],
    skill_contents: dict[str, str],
) -> list[dict]:
    """Layer 3: clear violation risk must exist (what breaks if ignored).

    For each candidate, checks the surrounding context (the source skill body)
    for consequence language near the principle. Falls back to checking the
    principle text itself.
    """
    result = []
    for c in candidates:
        principle = c["principle"]
        # First check the principle itself
        if _VIOLATION_RE.search(principle):
            result.append(c)
            continue
        # Check surrounding context in each source skill
        has_risk = False
        for source in c.get("skills", [c.get("source", "")]):
            body = skill_contents.get(source, "")
            if not body:
                continue
            # Find the principle vicinity (±500 chars)
            idx = body.lower().find(principle.lower()[:40])
            if idx == -1:
                continue
            window = body[max(0, idx - 200) : idx + 500]
            if _VIOLATION_RE.search(window):
                has_risk = True
                break
        if has_risk:
            result.append(c)
    return result


def _normalize_for_dedup(text: str) -> str:
    """Aggressive normalization for semantic deduplication."""
    text = _STRIP_MD.sub("", text.lower())
    # Remove common filler words
    for word in ("always", "never", "must", "ensure", "verify", "that", "the", "a", "an"):
        text = re.sub(rf"\b{word}\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def filter_layer4_not_covered(
    candidates: list[dict],
    shared_pattern_texts: list[str],
) -> list[dict]:
    """Layer 4: not already covered in shared-patterns (including diff wording).

    Normalizes both candidate and shared pattern text and checks for
    substantial overlap (≥40% of candidate words appear in any shared pattern).
    """
    # Pre-compute normalized shared pattern corpus
    shared_corpus = " ".join(_normalize_for_dedup(t) for t in shared_pattern_texts)
    shared_words = set(shared_corpus.split())

    result = []
    for c in candidates:
        norm = _normalize_for_dedup(c["principle"])
        candidate_words = set(norm.split())
        if not candidate_words:
            continue
        overlap = candidate_words & shared_words
        overlap_ratio = len(overlap) / len(candidate_words)
        if overlap_ratio < 0.4:
            result.append({**c, "overlap_ratio": round(overlap_ratio, 2)})
        # else: already covered — discard
    return result


# ---------------------------------------------------------------------------
# LLM extraction (optional, falls back to keyword matching)
# ---------------------------------------------------------------------------


def _run_claude_code(prompt: str, model: str | None = None) -> tuple[str, str]:
    """Run Claude Code and return (assistant_text, raw_result_text).

    Soft-fail contract: returns ('', '') on any failure (non-zero exit, invalid
    JSON, timeout). Callers must treat empty strings as a no-op and fall back
    to keyword-based extraction.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--print"]
    if model:
        cmd.extend(["--model", model])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"claude -p failed (exit {result.returncode}): {result.stderr}", file=sys.stderr)
        return "", ""

    try:
        events = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"claude -p returned invalid JSON: {result.stdout[:200]}", file=sys.stderr)
        return "", ""

    assistant_text = ""
    raw_result_text = ""
    for event in events:
        if event.get("type") == "assistant":
            message = event.get("message", {})
            for content in message.get("content", []):
                if content.get("type") == "text":
                    assistant_text += content.get("text", "")
        elif event.get("type") == "result":
            raw_result_text = event.get("result", "")

    return assistant_text or raw_result_text, raw_result_text


def _llm_extract_principles(skill_content: str, skill_name: str) -> list[dict] | None:
    """Try to extract principles via Claude Code.

    Returns list of dicts with "principle" key, or None if unavailable.
    """
    try:
        prompt = f"""You are analyzing a Claude Code skill file to extract cross-cutting behavioral principles.

Skill: {skill_name}

<skill_content>
{skill_content[:4000]}
</skill_content>

Extract up to 10 behavioral principles from this skill that:
1. Are actionable commands ("always do X", "never do Y", "must verify Z")
2. Would be useful as shared rules for ALL Claude Code agents
3. Have a clear violation risk (what breaks if ignored)

Return the principles as a JSON array of strings, one principle per string (1-2 sentences each).
Example: ["Always exit 0 from hooks regardless of errors", "Never auto-apply changes without explicit user approval"]

Return [] if no universal principles are found."""

        raw, _ = _run_claude_code(prompt, model="sonnet")
        raw = raw.strip()
        # Parse the first JSON array in the reply; tolerate surrounding prose or fences.
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        principles = json.loads(match.group(0) if match else raw)
        if not isinstance(principles, list):
            return None
        return [
            {"principle": str(p), "raw": str(p), "source": skill_name}
            for p in principles
            if isinstance(p, str) and len(p) >= 15
        ]
    except Exception as exc:
        print(f"LLM extraction failed: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Staleness policy
# ---------------------------------------------------------------------------


def apply_staleness_policy(candidates: list[dict]) -> list[dict]:
    """Promote pending candidates older than STALENESS_DAYS to 'deferred'."""
    now = datetime.now(timezone.utc)
    updated = []
    for c in candidates:
        if c.get("status") != "pending":
            updated.append(c)
            continue
        created_str = c.get("created_at", "")
        if not created_str:
            updated.append(c)
            continue
        try:
            created = datetime.fromisoformat(created_str)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = (now - created).days
            if age_days > STALENESS_DAYS:
                updated.append({**c, "status": "deferred", "deferred_reason": "staleness"})
                continue
        except ValueError:
            pass
        updated.append(c)
    return updated


# ---------------------------------------------------------------------------
# Pending JSON management
# ---------------------------------------------------------------------------


def load_pending() -> dict:
    """Load existing pending proposals, or return empty structure."""
    if not PENDING_JSON.exists():
        return {"distilled_at": "", "skills_scanned": [], "candidates": []}
    try:
        return json.loads(PENDING_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"distilled_at": "", "skills_scanned": [], "candidates": []}


def merge_candidates(existing: list[dict], new_candidates: list[dict]) -> list[dict]:
    """Merge new candidates into existing list, skipping already-seen principles.

    Already-approved or already-skipped candidates are never re-surfaced.
    """
    # Build set of normalized principles already in the list
    existing_norms: set[str] = set()
    for c in existing:
        if c.get("status") in ("approved", "skipped"):
            existing_norms.add(_normalize_for_dedup(c.get("principle", "")))

    merged = list(existing)
    now_str = datetime.now(timezone.utc).isoformat()

    for nc in new_candidates:
        norm = _normalize_for_dedup(nc["principle"])
        if norm in existing_norms:
            continue
        # Check if this principle is already pending (avoid duplicates)
        already_pending = any(
            _normalize_for_dedup(c.get("principle", "")) == norm for c in merged if c.get("status") == "pending"
        )
        if already_pending:
            continue
        merged.append(
            {
                "id": _make_id(nc["principle"]),
                "principle": nc["principle"],
                "skills": nc.get("skills", [nc.get("source", "")]),
                "occurrence_count": nc.get("occurrence_count", 1),
                "overlap_ratio": nc.get("overlap_ratio", 0.0),
                "confidence": _compute_confidence(nc),
                "verdict": _assign_verdict(nc),
                "target": "skills/shared-patterns/",
                "draft": nc["principle"],
                "status": "pending",
                "created_at": now_str,
            }
        )
    return merged


def _make_id(principle: str) -> str:
    """Generate a short stable ID for a principle."""
    import hashlib

    return hashlib.md5(principle.encode()).hexdigest()[:8]


def _compute_confidence(candidate: dict) -> float:
    """Heuristic confidence score 0.0-1.0."""
    score = 0.5
    count = candidate.get("occurrence_count", 1)
    if count >= 5:
        score += 0.3
    elif count >= 3:
        score += 0.2
    elif count >= 2:
        score += 0.1
    # Reward low overlap with existing patterns (more novel = more useful)
    overlap = candidate.get("overlap_ratio", 0.5)
    score += (1.0 - overlap) * 0.2
    return round(min(score, 1.0), 2)


def _assign_verdict(candidate: dict) -> str:
    """Assign a suggested action verdict."""
    overlap = candidate.get("overlap_ratio", 0.5)
    if overlap > 0.2:
        return "Revise"  # Partial overlap — refine existing pattern
    count = candidate.get("occurrence_count", 1)
    if count >= 4:
        return "New Section"
    return "Append"


# ---------------------------------------------------------------------------
# Main distillation logic
# ---------------------------------------------------------------------------


def run_distillation(dry_run: bool = False, verbose: bool = False) -> dict:
    """Full distillation pipeline. Returns result dict."""
    skill_files = collect_skill_files()
    shared_files = collect_shared_pattern_files()

    if verbose:
        print(f"[rules-distill] Scanning {len(skill_files)} skill/pipeline files", file=sys.stderr)
        print(f"[rules-distill] Baseline: {len(shared_files)} shared-pattern files", file=sys.stderr)

    # Read all skills
    skills = [read_skill(p) for p in skill_files]
    skill_contents: dict[str, str] = {s["name"]: s["content"] for s in skills}

    # Read shared patterns for layer-4 dedup
    shared_texts = []
    for sp in shared_files:
        try:
            shared_texts.append(sp.read_text(encoding="utf-8"))
        except OSError:
            pass

    # Extract principles from each skill
    all_raw: list[dict] = []
    for skill in skills:
        if not skill["content"]:
            continue
        # Try LLM extraction first
        llm_results = _llm_extract_principles(skill["content"], skill["name"])
        if llm_results is not None:
            all_raw.extend(llm_results)
        else:
            # Keyword-based fallback
            all_raw.extend(extract_principles_from_text(skill["content"], skill["name"]))

    if verbose:
        print(f"[rules-distill] Extracted {len(all_raw)} raw principles", file=sys.stderr)

    # Apply four-layer filter
    after_l1 = filter_layer1_multi_skill(all_raw)
    if verbose:
        print(f"[rules-distill] After layer 1 (multi-skill): {len(after_l1)}", file=sys.stderr)

    after_l2 = filter_layer2_actionable(after_l1)
    if verbose:
        print(f"[rules-distill] After layer 2 (actionable): {len(after_l2)}", file=sys.stderr)

    after_l3 = filter_layer3_violation_risk(after_l2, skill_contents)
    if verbose:
        print(f"[rules-distill] After layer 3 (violation risk): {len(after_l3)}", file=sys.stderr)

    after_l4 = filter_layer4_not_covered(after_l3, shared_texts)
    if verbose:
        print(f"[rules-distill] After layer 4 (not covered): {len(after_l4)}", file=sys.stderr)

    new_candidates = after_l4

    # Load existing pending, apply staleness, merge
    now_str = datetime.now(timezone.utc).isoformat()
    existing = load_pending()
    old_candidates = apply_staleness_policy(existing.get("candidates", []))
    merged = merge_candidates(old_candidates, new_candidates)

    result = {
        "distilled_at": now_str,
        "skills_scanned": [s["name"] for s in skills],
        "candidates": merged,
    }

    if not dry_run:
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)
        PENDING_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
        LAST_RUN_FILE.write_text(now_str, encoding="utf-8")
        if verbose:
            print(f"[rules-distill] Wrote {PENDING_JSON}", file=sys.stderr)
    else:
        if verbose:
            print("[rules-distill] Dry-run: no files written", file=sys.stderr)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_status() -> None:
    """Print current pending candidates."""
    data = load_pending()
    candidates = data.get("candidates", [])
    pending = [c for c in candidates if c.get("status") == "pending"]
    deferred = [c for c in candidates if c.get("status") == "deferred"]
    approved = [c for c in candidates if c.get("status") == "approved"]
    skipped = [c for c in candidates if c.get("status") == "skipped"]

    print(f"Rules Distill Status — last run: {data.get('distilled_at', 'never')}")
    print(f"  Pending:  {len(pending)}")
    print(f"  Deferred: {len(deferred)}")
    print(f"  Approved: {len(approved)}")
    print(f"  Skipped:  {len(skipped)}")

    if pending:
        print("\nPending candidates:")
        for i, c in enumerate(pending, 1):
            conf = c.get("confidence", "?")
            verdict = c.get("verdict", "?")
            skills_str = ", ".join(c.get("skills", []))
            print(f"  [{i}] ({conf}) [{verdict}] {c['principle'][:80]}")
            print(f"       Sources: {skills_str}")


def _print_dry_run_report(result: dict) -> None:
    """Print dry-run report to stdout."""
    candidates = result.get("candidates", [])
    new_pending = [c for c in candidates if c.get("status") == "pending"]
    print(f"Rules Distill — dry-run report")
    print(f"  Skills scanned: {len(result.get('skills_scanned', []))}")
    print(f"  New candidates: {len(new_pending)}")
    if new_pending:
        print("\nProposed candidates:")
        for i, c in enumerate(new_pending, 1):
            conf = c.get("confidence", "?")
            verdict = c.get("verdict", "?")
            skills_str = ", ".join(c.get("skills", []))
            print(f"\n  [{i}] Confidence: {conf} | Verdict: {verdict}")
            print(f"       Principle: {c['principle']}")
            print(f"       Sources:   {skills_str}")
            print(f"       Target:    {c.get('target', 'skills/shared-patterns/')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Automated rules distillation — scans skills for cross-cutting principles."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview candidates without writing to pending.json",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Cron mode: same as default full run (exits 0 silently on success)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current pending candidates and exit",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print progress to stderr",
    )
    args = parser.parse_args(argv)

    if args.status:
        _print_status()
        return 0

    verbose = args.verbose or not args.auto
    result = run_distillation(dry_run=args.dry_run, verbose=verbose)

    if args.dry_run:
        _print_dry_run_report(result)
    elif not args.auto:
        pending_count = sum(1 for c in result["candidates"] if c.get("status") == "pending")
        print(f"[rules-distill] Done. {pending_count} pending candidate(s) in {PENDING_JSON}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
