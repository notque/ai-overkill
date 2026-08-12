#!/usr/bin/env python3
"""Deterministic force-route guard for /do routing.

Matches user requests against the triggers of force_route entries ONLY
(skills/INDEX.json `force_route: true`, plus SUPPLEMENTAL_TRIGGERS). A match
that survives the semantic guards reports `match_type: force_route`,
`confidence: high`; everything else falls through — semantic intent routing
(the orchestrator's in-session self-route) decides the long tail. The guard
exists so genuine git/security/codex requests always hit their quality gates:
a high-confidence force match for pr-workflow or a security skill enables the
/do fast path and overrides a disagreeing semantic pick.

Non-force keyword routing was retired 2026-07: replaying 49 real /do requests
it fell through 43/49, and both non-force keyword matches it did produce were
wrong. The guard/companion tables stay — they are the precision layer of the
force-route guarantee, pinned by the ADR corpus tests
(test_pre_route_pr_workflow/planning/public_web_deploy).

Output contract (stable): matched, agent, skill, confidence, match_type,
reasoning. Consumers: skills/meta/do/SKILL.md Phase 2, routing-ab-test.py,
router-self-audit.py (load_entries).

Usage:
    python3 scripts/pre-route.py --request "create a PR" --json-compact
    python3 scripts/pre-route.py --request-file /tmp/req.txt --json-compact

Exit codes:
    0 -- always (output is JSON to stdout)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GO_SOURCE_OPERAND_RE = re.compile(r"\.go(?=(?::\d+|#L\d+)?(?:$|[\s`'\",;!?()\[\]{}]|\.(?=$|\s)))")
PROTECTED_GO_COMPOSITE_SKILLS = {"pr-workflow", "pr-pipeline", "security-review"}
PR_CREATE_INTENT_RE = re.compile(
    r"\b(?:create|open|make|draft|submit|raise|file)\b"
    r"(?:\s+\S+){0,5}?\s+(?:a\s+)?(?:pr|pull\s+request)\b",
    re.IGNORECASE,
)

# Shared tracked+local INDEX merge — single source in routing_index_merge.py.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from routing_index_merge import load_index_items as _load_index_items

# INDEX.json is a generated artifact (untracked). When the tracked path is
# missing — fresh checkout, no install.sh run — regenerate it on the fly from
# SKILL.md/agent frontmatter via these generators.
_INDEX_GENERATORS = {
    "skills": REPO_ROOT / "scripts" / "generate-skill-index.py",
    "agents": REPO_ROOT / "scripts" / "generate-agent-index.py",
}


def _ensure_index(index_type: str, path: Path) -> None:
    """Regenerate a missing index by invoking its generator.

    Fail-safe: any failure (generator missing, non-zero exit, timeout) is
    swallowed so routing never crashes. A missing index simply means
    load_entries() reads nothing for that type and the request falls through.
    """
    if path.exists():
        return
    generator = _INDEX_GENERATORS.get(index_type)
    if generator is None or not generator.exists():
        return
    try:
        subprocess.run(
            [sys.executable, str(generator)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=20,
        )
    except (subprocess.SubprocessError, OSError):
        pass


INDEX_PATHS = {
    "skills": (REPO_ROOT / "skills" / "INDEX.json", "INDEX.local.json"),
    "agents": (REPO_ROOT / "agents" / "INDEX.json", "INDEX.local.json"),
}

# Verbs/nouns that signal working ON a site (build, edit, debug, discuss) rather
# than PUBLISHING one. Shared blocklist for public-web-deploy idiom triggers so
# overloaded deploy companions ("public", "domain") cannot wave through ordinary
# dev/content/architecture requests.
# Only ACTION verbs and unambiguous non-deploy modifiers belong here. Site-TYPE
# nouns (blog, docs, app, content, image, form, font) are deliberately excluded:
# "deploy my blog website to my domain" is a genuine deploy, and the
# accompanying work-verb (translate/optimize/fix/...) is what marks a non-deploy
# request, not the noun. Keep this a verb/intent blocklist, not a noun list.
_SITE_WORK_GUARD: set[str] = {
    # build / generate
    "build",
    "generator",
    "generators",
    "generation",
    "ssg",
    "convert",
    "migrate",
    "scaffold",
    # edit / content actions
    "edit",
    "write",
    "rewrite",
    "wording",
    "css",
    "style",
    "restyle",
    "design",
    "redesign",
    "translate",
    "translation",
    "localize",
    "localise",
    "localization",
    "rebrand",
    "branding",
    "retheme",
    "theme",
    "search",
    "seo",
    "newsletter",
    "navigation",
    "accessibility",
    "audit",
    # debug / maintenance actions
    "fix",
    "bug",
    "error",
    "debug",
    "caching",
    "cache",
    "optimize",
    "optimization",
    "performance",
    "tuning",
    "analytics",
    "tracking",
    "redirect",
    "redirects",
    "lighthouse",
    "vitals",
    # discuss / compare
    "compare",
    "comparison",
    "review",
    "architecture",
    "dynamic",
    "versus",
    "vs",
    "difference",
    "terminology",
    "examples",
    "example",
    # test
    "test",
    "tests",
    "unit",
    "qa",
    # "site"-prefix overmatch (the matcher treats the last trigger word as a
    # prefix, so "deploy site" matches "deploy sitemap"/"sitecore"). Block the
    # non-deploy site* words explicitly.
    "sitemap",
    "sitemaps",
    "sitecore",
}

# Repo/code/package visibility vocabulary. "make (it) public" most often means
# flipping a GitHub repo / npm package / code symbol to public, not deploying a
# web page. These words near the trigger discard the public-web-deploy match.
# Note: "github"/"gitlab" are intentionally absent — "make my website public on
# github pages" is a genuine managed-static deploy. The repo-visibility signal
# is carried by repo/repository/gist/code/source/package, not the host name.
_VISIBILITY_OP_GUARD: set[str] = {
    "repo",
    "repository",
    "gist",
    "code",
    "source",
    "package",
    "npm",
    "pypi",
    "crate",
    "gem",
    "method",
    "field",
    "function",
    "class",
    "variable",
    "module",
}

# Safety-net triggers the INDEX files lack. The routing A/B corpus
# (scripts/routing-ab-corpus.json, buckets paraphrase-git and
# paraphrase-security) holds genuine git/security requests phrased without any
# INDEX keyword; these force-route skills MUST catch them so quality gates
# always run. Merged into the skill's INDEX triggers at load time, so each
# match keeps the entry's force_route flag and passes the same guard checks.
# Keep every pattern narrow: multi-word, intent-specific, and guarded below
# when it could collide with ordinary English.
SUPPLEMENTAL_TRIGGERS: dict[str, tuple[str, ...]] = {
    "pr-workflow": (
        "send commits",  # "send my commits to the server"
        "shared repository",  # "save my work to the shared repository"
        "submit changes",  # "I'd like to submit my changes for review"
        "into version control",  # "record what I changed into version control"
        "to version control",
        "under version control",
        "upload my work",  # "upload my finished work so the team can see it"
        "went green",  # "check if the tests on my submitted change went green"
    ),
    "security-review": (
        "code safe",  # "look over my code for safety problems" (safe* covers safety)
        "is unsafe",  # "check whether anything here is unsafe"
        "break into",  # "someone could break into this" — companion-gated below
        "passwords keys",  # "did I leave any passwords or keys in the code"
    ),
}

# Phrases that look like trigger matches but are common English idioms
# unrelated to the skill. Keyed by skill name -> disqualifying context words.
#
# The value is either:
#   - set[str]            : guards applied to EVERY trigger of the skill (legacy)
#   - dict[str, set[str]] : per-trigger guards, keyed by the lowercased trigger
#                           phrase, so a disqualifier scoped to one idiom does
#                           not over-suppress an unrelated trigger of the same
#                           skill (e.g. "repo" disambiguates "make it public"
#                           but must not suppress "deploy website").
SEMANTIC_GUARDS: dict[str, set[str] | dict[str, set[str]]] = {
    "pr-workflow": {
        "back",
        "against",
        "pressure",
        "pushback",
        "pushed",
        "pushing",
        # Idiom guards for ship/merge/publish/review triggers (ADR pr-create-skill-guard).
        # These suppress matches when context indicates non-git intent.
        "theseus",
        "manuscript",
        "captain",
        "ideas",
        "personalities",
        "merger",
        "head",
        "paper",
        "arxiv",
        "menu",
        "essay",
        "offsite",
    },
    "shell-config": {"for", "bugs", "compliments", "information", "ideas", "answers"},
    "voice-writer": {"remove", "strip", "clean", "detect", "identify", "fix", "scan", "audit"},
    # ADR public-web-deploy. Low-specificity idiom triggers ("go live",
    # "make it public", "static site", "use my domain", "set up https",
    # "public website") are handled by the POSITIVE companion-word requirement
    # below (SEMANTIC_REQUIRE_COMPANION), not by enumerating disqualifiers — a
    # blocklist loses the arms race against ordinary phrasing. Only the
    # near-specific "deploy website" keeps a negative guard for its one idiom.
    # Defense-in-depth for public-web-deploy: a match routes only when it
    # survives BOTH this per-trigger blocklist AND (for idiom triggers) the
    # companion-word requirement below. The blocklist catches build/edit/
    # discuss verbs that overloaded companions ("public", "domain") would
    # otherwise wave through ("compare static site generators for public docs").
    "public-web-deploy": {
        # build / edit / discuss verbs that mean "work ON a site", not "publish one"
        "static site": _SITE_WORK_GUARD,
        "landing page": _SITE_WORK_GUARD,
        "public website": _SITE_WORK_GUARD,
        "public site": _SITE_WORK_GUARD,
        "nginx public site": _SITE_WORK_GUARD,
        "deploy site": _SITE_WORK_GUARD,
        "deploy website": _SITE_WORK_GUARD | {"unit"},  # + "deploy website unit tests"
        "set up https": _SITE_WORK_GUARD | {"client", "pinning", "validation", "certificate"},
        # "host a website locally for testing" -> local/QA, not a public deploy
        # (aligns with the skill's not_for: local-only preview needs no deploy)
        "host a website": {"local", "locally", "localhost", "testing", "qa", "dev"},
        # "website online store checkout bug" -> e-commerce/app bug, not deploy
        "website online": {"store", "shop", "checkout", "cart"},
        # "make (it) public" -> repo/code/package visibility ops, not a web deploy.
        # Runs before the companion gate, so a nearby "website"/"site" can't
        # rescue "make website repo public on github".
        "make public": _VISIBILITY_OP_GUARD,
        "make it public": _VISIBILITY_OP_GUARD,
    },
    # Guards for the SUPPLEMENTAL_TRIGGERS above. Per-trigger dict: these
    # apply only to the listed idiom-prone triggers, never to the skill's
    # INDEX triggers.
    "security-review": {
        # "make the code thread-safe" / "type safety" = language mechanics,
        # not a security review.
        "code safe": {
            "thread",
            "threads",
            "threadsafe",
            "type",
            "types",
            "typesafe",
            "null",
            "race",
            "concurrency",
            "exception",
            "exceptions",
        },
        # Rust's `unsafe` keyword and pointer talk, not a vulnerability check.
        "is unsafe": {
            "rust",
            "keyword",
            "block",
            "blocks",
            "pointer",
            "pointers",
            "transmute",
            "deref",
        },
    },
}

# Positive companion-word requirement: keyed by skill -> trigger -> set of
# words that MUST appear in the 60-char window around the matched trigger,
# otherwise the match is discarded. Use this for low-specificity idiom
# triggers where "deploy intent" is only confirmed by a nearby deploy/host
# term — the inverse of SEMANTIC_GUARDS (allowlist instead of blocklist).
# This kills the false-positive arms race: ordinary requests that merely
# mention "static site" or "go live" fall through unless a deploy companion
# is present. High-specificity triggers ("public site", "website online",
# "nginx public site", "deploy site", "put X online", "host a website",
# "point my domain") are NOT listed here and route on their own.
# Public-web-SPECIFIC companions only. Generic terms (server, production, prod,
# publish, serve) are deliberately excluded — they appear in ordinary non-deploy
# requests ("on production", "publish the report") and would re-open the false
# positives. Every word here names public web hosting / DNS / TLS concretely.
_DEPLOY_COMPANIONS: set[str] = {
    # "site"/"website" confirm deploy intent for verb-only idiom triggers
    # ("set up https for my website", "go live with my website"). They are
    # excluded when they are the matched trigger's own words, so triggers like
    # "static site"/"public website" cannot self-satisfy on them.
    "site",
    "website",
    "webpage",
    "webserver",
    # common deploy-target nouns ("set up https for my portfolio",
    # "make my homepage public", "deploy my landing page"). "docs"/"blog"/"app"
    # are intentionally absent — they are ambiguous ("https docs for the team"
    # is documentation, not a deploy); those deploy when paired with
    # "site"/"website" ("deploy my docs website"), which are companions.
    "portfolio",
    "homepage",
    "landing",
    "online",
    "public",
    "publicly",
    "host",
    "hosted",
    "hosting",
    "domain",
    "subdomain",
    "dns",
    "nginx",
    "caddy",
    "apache",
    "cloudflare",
    "pages",
    "vercel",
    "netlify",
    "heroku",
    "render",
    "surge",
    "fly",  # fly.io — tokenizer splits on ".", so match the "fly" token
    "https",
    "tls",
    "ssl",
    "certbot",
    "letsencrypt",
    "deploy",
    "deployed",
    "deploying",
    "internet",
    "internet-facing",
    "vps",
    "droplet",
}
SEMANTIC_REQUIRE_COMPANION: dict[str, dict[str, set[str]]] = {
    "public-web-deploy": {
        "go live": _DEPLOY_COMPANIONS,
        "make it public": _DEPLOY_COMPANIONS,
        "make public": _DEPLOY_COMPANIONS,
        "static site": _DEPLOY_COMPANIONS,
        "landing page": _DEPLOY_COMPANIONS,
        "use my domain": _DEPLOY_COMPANIONS,
        "set up https": _DEPLOY_COMPANIONS,
        "public website": _DEPLOY_COMPANIONS,
        # "public site" force-routes only with a deploy companion nearby, so
        # "translate my public site", "rebrand my public site", etc. (work ON an
        # already-public site) fall through. The trigger's own words
        # ("public"/"site") are excluded from satisfying this.
        # NOTE: "deploy site"/"deploy website" are NOT companion-gated — "deploy"
        # itself is unambiguous deploy intent, so "deploy my site to vercel"
        # must route. Their _SITE_WORK_GUARD blocklist still catches
        # "retheme the deploy site" / "deploy website unit tests".
        "public site": _DEPLOY_COMPANIONS,
        "nginx public site": _DEPLOY_COMPANIONS,
    },
    # "break into" routes only with an intrusion word nearby ("someone could
    # break into this"). Refactor phrasing ("break this into smaller
    # functions") has no such companion and falls through.
    "security-review": {
        "break into": {
            "someone",
            "somebody",
            "anyone",
            "anybody",
            "hacker",
            "hackers",
            "attacker",
            "attackers",
            "intruder",
            "intruders",
            "hack",
            "hacked",
            "hacking",
            "malicious",
            "breach",
            "steal",
            "stolen",
            "burglar",
            "criminals",
        },
    },
}

# Multi-word disqualifying phrases (substring match in lowered request).
# Use this when a unigram guard would over-suppress legitimate requests
# (e.g. 'out' alone collides with "log out", "check out"; but "fish out"
# reliably means search/extract, not the Fish shell).
SEMANTIC_GUARD_PHRASES: dict[str, set[str]] = {
    "shell-config": {"fish out", "fish for", "zsh out", "zsh for"},
    # ADR pr-create-skill-guard: phrase guards for newly-added pr-workflow triggers.
    # The unigram guards above catch most idioms; these phrase guards suppress
    # multi-word collisions that span the trigger window (e.g. 'ship of theseus'
    # has 'ship' adjacent to 'theseus' as a phrase, not just a word in context).
    "pr-workflow": {
        "ship of theseus",
        "merge ideas",
        "merge personalities",
        "publish a paper",
        "publish a book",
        "review the menu",
        "review my essay",
        # Supplemental-trigger idioms: "upload my work to google drive" is a
        # file sync, "shared repository of knowledge" is a metaphor.
        "google drive",
        "to dropbox",
        "repository of knowledge",
    },
}


@dataclass
class MatchEntry:
    """A single trigger-to-target mapping."""

    name: str
    entry_type: str  # "skill" or "agent"
    agent: str | None
    force_route: bool
    trigger: str
    pattern: re.Pattern[str]


@dataclass
class ScoredMatch:
    """A candidate match with computed score."""

    name: str
    entry_type: str
    agent: str | None
    force_route: bool
    matched_triggers: list[str] = field(default_factory=list)
    total_chars: int = 0
    score: float = 0.0


def load_entries() -> list[dict]:
    """Load all INDEX entries into a flat list."""
    entries: list[dict] = []

    for index_type, (tracked, local_name) in INDEX_PATHS.items():
        # Auto-regenerate a missing (untracked) tracked index before reading.
        # Fail-safe.
        _ensure_index(index_type, tracked)
        items = _load_index_items(tracked, local_name, index_type)

        for name, data in items.items():
            if not isinstance(data, dict):
                continue
            triggers = list(data.get("triggers", []))
            # Safety-net paraphrase triggers the INDEX lacks (see
            # SUPPLEMENTAL_TRIGGERS). The entry keeps its force_route flag.
            triggers.extend(t for t in SUPPLEMENTAL_TRIGGERS.get(name, ()) if t not in triggers)
            entries.append(
                {
                    "name": name,
                    "type": "skill" if index_type == "skills" else "agent",
                    "triggers": triggers,
                    "agent": data.get("agent"),
                    "force_route": bool(data.get("force_route", False)),
                }
            )

    return entries


def _build_pattern(trigger_lower: str) -> re.Pattern[str]:
    """Build a regex pattern for a trigger phrase.

    Single-word triggers: exact word-boundary match.
    Multi-word triggers: each word must appear in order with up to 2
    intervening words allowed (handles "create a PR" matching trigger
    "create PR", or "run the go tests" matching "go test").
    """
    words = trigger_lower.split()
    if len(words) == 1:
        escaped = re.escape(words[0])
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)

    # Multi-word: allow up to 2 words between each trigger word.
    # Also allow the last trigger word to be a prefix (e.g. "test" matches "tests").
    parts = []
    for i, word in enumerate(words):
        escaped = re.escape(word)
        if i == len(words) - 1:
            # Last word: allow plural/suffix (word boundary after stem)
            parts.append(rf"\b{escaped}\w*\b")
        else:
            parts.append(rf"\b{escaped}\b")

    # Join with "up to 2 intervening words" gap
    gap = r"(?:\s+\S+){0,2}\s+"
    full_pattern = gap.join(parts)
    return re.compile(full_pattern, re.IGNORECASE)


def build_match_table(entries: list[dict]) -> list[MatchEntry]:
    """Compile force_route entries' trigger keywords into regex patterns.

    Non-force entries are skipped: pre-route matches only force-routes; the
    semantic router owns the long tail. Single-word triggers use exact
    word-boundary match. Multi-word triggers allow up to 2 intervening words
    between trigger words (e.g. "create PR" matches "create a PR").
    """
    table: list[MatchEntry] = []

    for entry in entries:
        name = entry["name"]
        entry_type = entry["type"]
        agent = entry.get("agent")
        force_route = entry.get("force_route", False)
        if not force_route:
            continue

        for trigger in entry.get("triggers", []):
            if not isinstance(trigger, str):
                continue
            trigger_lower = trigger.lower()
            pattern = _build_pattern(trigger_lower)

            table.append(
                MatchEntry(
                    name=name,
                    entry_type=entry_type,
                    agent=agent,
                    force_route=force_route,
                    trigger=trigger_lower,
                    pattern=pattern,
                )
            )

    return table


def _is_semantically_guarded(
    skill_name: str, request_lower: str, matched_trigger: str, trigger_pattern: re.Pattern[str]
) -> bool:
    """Check if the match is a false positive due to common English idioms.

    Three layers of suppression:
    1. SEMANTIC_GUARD_PHRASES (multi-word substring match anywhere in request) —
       used when a single guard word would over-suppress (e.g. "fish out").
    2. SEMANTIC_GUARDS (unigram blocklist in 60-char context window around the
       trigger) — discard when a disqualifying word is near the trigger.
    3. SEMANTIC_REQUIRE_COMPANION (unigram allowlist in the same window) —
       discard UNLESS a required companion word is near the trigger. Used for
       low-specificity idiom triggers where deploy intent is only confirmed by
       a nearby deploy/host term; avoids the blocklist arms race.

    Uses the trigger's compiled regex pattern to locate the match position,
    which correctly handles multi-word triggers with intervening words
    (e.g. "create a PR" matching trigger "create pr").

    Returns True if the match should be discarded.
    """
    # Phrase-level guard: if any disqualifying phrase appears as a whole-word
    # match anywhere in the request, this is not a domain match. Word-boundary
    # match prevents "fish for" suppressing "selfish forum" etc.
    phrase_guards = SEMANTIC_GUARD_PHRASES.get(skill_name)
    if phrase_guards:
        for phrase in phrase_guards:
            if re.search(rf"\b{re.escape(phrase)}\b", request_lower):
                return True

    # Resolve the active blocklist word-set. Two shapes are supported:
    #   - set[str]            : applies to every trigger of the skill (legacy)
    #   - dict[str, set[str]] : per-trigger; pick the set for the matched idiom
    #                           so a guard scoped to one trigger does not
    #                           over-suppress an unrelated trigger.
    guard_spec = SEMANTIC_GUARDS.get(skill_name)
    guards: set[str] | None = None
    if isinstance(guard_spec, dict):
        guards = guard_spec.get(matched_trigger)
    elif guard_spec:
        guards = guard_spec

    companion_spec = SEMANTIC_REQUIRE_COMPANION.get(skill_name, {})
    required_companions = companion_spec.get(matched_trigger)

    if not guards and not required_companions:
        return False

    # Use the regex pattern to find the trigger match position, not str.find().
    # str.find() fails for multi-word triggers with intervening words.
    m = trigger_pattern.search(request_lower)
    if m is None:
        return False

    trigger_pos = m.start()
    match_len = m.end() - m.start()

    # Extract context window: 60 chars before and after the trigger match.
    ctx_start = max(0, trigger_pos - 60)
    ctx_end = min(len(request_lower), trigger_pos + match_len + 60)
    context = request_lower[ctx_start:ctx_end]
    words_in_context = set(re.findall(r"\b\w+\b", context))

    # Blocklist: a disqualifying word near the trigger discards the match.
    if guards and (words_in_context & guards):
        return True

    # Allowlist: exclude the trigger's own words so the trigger cannot satisfy
    # its own companion requirement (e.g. "live" in "go live"). Discard the
    # match when no required companion word is present in the window.
    if required_companions:
        trigger_words = set(matched_trigger.split())
        companion_words = words_in_context - trigger_words
        if not (companion_words & required_companions):
            return True

    return False


def score_matches(table: list[MatchEntry], request: str) -> dict[str, ScoredMatch]:
    """Collect force_route entries whose triggers match, ranked for tie-breaks.

    Ranking (only used when multiple force entries match):
    - Each matched trigger adds 1.0 to score
    - Longer triggers get a specificity bonus (len/100)
    """
    request_lower = request.lower()
    candidates: dict[str, ScoredMatch] = {}

    for entry in table:
        if not entry.pattern.search(request_lower):
            continue

        # Semantic guard check
        if _is_semantically_guarded(entry.name, request_lower, entry.trigger, entry.pattern):
            continue

        key = f"{entry.entry_type}:{entry.name}"
        if key not in candidates:
            candidates[key] = ScoredMatch(
                name=entry.name,
                entry_type=entry.entry_type,
                agent=entry.agent,
                force_route=entry.force_route,
            )

        match = candidates[key]
        match.matched_triggers.append(entry.trigger)
        match.total_chars += len(entry.trigger)

    # Compute final scores
    for match in candidates.values():
        trigger_count = len(match.matched_triggers)
        specificity_bonus = match.total_chars / 100.0
        match.score = trigger_count + specificity_bonus

    return candidates


def determine_confidence(match: ScoredMatch) -> str:
    """Force match with 1+ surviving trigger -> "high"; anything else -> "low".

    A force_route match that reaches scoring already passed every semantic
    guard (score_matches discards guarded matches), so one surviving trigger
    is a deterministic signal. The /do fast path and Step 1(a) safety
    override act only on "high".
    """
    if match.force_route and len(match.matched_triggers) >= 1:
        return "high"
    return "low"


def route(request: str, entries: list[dict] | None = None) -> dict:
    """Run the pre-router on a request string.

    Args:
        request: The user's request text.
        entries: Optional pre-loaded INDEX entries. Loaded from disk if None.

    Returns:
        Routing decision dict with matched, agent, skill, confidence,
        match_type, and reasoning fields.
    """
    if entries is None:
        entries = load_entries()

    table = build_match_table(entries)
    candidates = score_matches(table, request)

    go_operand = GO_SOURCE_OPERAND_RE.search(request) is not None

    # A bare "push <file.go>" is still a git/PR operation even though the
    # pr-workflow trigger list intentionally avoids the overloaded bare verb.
    request_words = set(re.findall(r"\b\w+\b", request.lower()))
    pr_guards = SEMANTIC_GUARDS["pr-workflow"]
    assert isinstance(pr_guards, set)
    genuine_push = bool(re.search(r"\bpush\b", request, re.IGNORECASE)) and not (request_words & pr_guards)
    protected_pr_intent = PR_CREATE_INTENT_RE.search(request) is not None or genuine_push
    if go_operand and protected_pr_intent and "skill:pr-workflow" not in candidates:
        pr_entry = next((entry for entry in table if entry.name == "pr-workflow"), None)
        if pr_entry is not None:
            candidates["skill:pr-workflow"] = ScoredMatch(
                name="pr-workflow",
                entry_type="skill",
                agent=pr_entry.agent,
                force_route=True,
                matched_triggers=["protected PR intent with <go-source>"],
                total_chars=len("protected PR intent with <go-source>"),
                score=100,
            )

    if go_operand and re.search(r"\bsecurity\s+audit\b", request, re.IGNORECASE):
        security_entry = next((entry for entry in table if entry.name == "security-review"), None)
        if security_entry is not None:
            candidates["skill:security-review"] = ScoredMatch(
                name="security-review",
                entry_type="skill",
                agent=security_entry.agent,
                force_route=True,
                matched_triggers=["security audit"],
                total_chars=len("security audit"),
                score=100,
            )

    if not candidates:
        return {
            "matched": False,
            "agent": None,
            "skill": None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": "no trigger keywords matched",
            "stack": [],
        }

    # Sort by score descending, then by name ascending for deterministic tie-breaking
    # A Go source-file extension is stronger domain evidence than a generic
    # process phrase such as "fix typo". Ensure every .go edit loads the Go
    # skill's mandatory style baseline while leaving non-Go typo work on quick.
    protected = [candidate for candidate in candidates.values() if candidate.name in PROTECTED_GO_COMPOSITE_SKILLS]
    if go_operand and not protected and "skill:go-patterns" in candidates:
        candidates["skill:go-patterns"].score += 100

    ranked = sorted(candidates.values(), key=lambda m: (-m.score, m.name))
    top = ranked[0]
    confidence = determine_confidence(top)

    if confidence == "low":
        return {
            "matched": False,
            "agent": top.agent,
            "skill": top.name if top.entry_type == "skill" else None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": f"weak match on {top.matched_triggers!r} for {top.name} (score={top.score:.2f})",
            "stack": [],
        }

    # Determine agent and skill from the match
    agent = top.agent
    skill = top.name if top.entry_type == "skill" else None

    # If matched entry is an agent (not skill), set agent from name
    if top.entry_type == "agent":
        agent = top.name
        skill = None

    match_type = "force_route"  # only force entries reach the match table
    triggers_str = ", ".join(f"'{t}'" for t in top.matched_triggers)

    return {
        "matched": True,
        "agent": agent,
        "skill": skill,
        "confidence": confidence,
        "match_type": match_type,
        "reasoning": f"matched triggers [{triggers_str}] for {top.name}",
        "stack": ["go-patterns"] if go_operand and top.name in PROTECTED_GO_COMPOSITE_SKILLS else [],
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Deterministic pre-router for /do dispatch.",
    )
    req_group = parser.add_mutually_exclusive_group(required=True)
    req_group.add_argument(
        "--request",
        help="The user request string to route.",
    )
    req_group.add_argument(
        "--request-file",
        help="Path to a file containing the request string (avoids shell-splicing).",
    )
    parser.add_argument(
        "--json-compact",
        action="store_true",
        help="Output compact JSON (no indentation).",
    )
    args = parser.parse_args()

    try:
        if args.request_file:
            request_text = Path(args.request_file).read_text(encoding="utf-8")
        else:
            request_text = args.request

        result = route(request_text)
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        result = {
            "matched": False,
            "agent": None,
            "skill": None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": f"pre-route error: {type(exc).__name__}: {exc}",
        }

    indent = None if args.json_compact else 2
    print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
