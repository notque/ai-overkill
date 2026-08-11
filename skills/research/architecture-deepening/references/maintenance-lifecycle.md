# Architecture Maintenance Lifecycle

Load during Phase 1 before ranking candidates and Phase 3 before recording an outcome. This reference controls when a survey starts, how it stays bounded, what decisions persist, and which existing workflow receives the result.

## Safe Entry Moments

| Entry | Required evidence | Start scope |
|---|---|---|
| Explicit architecture improvement | Interface, caller knowledge, or multi-module coordination named by the user | Named module and its callers |
| After overview or review | User asks for improvement, or the artifact contains 3+ specific interface-leak or caller-coordination signals | Modules named by the artifact |
| Before feature approach selection | Planned change crosses 2+ module interfaces, changes a public interface, or makes callers coordinate 2+ components for one operation | Feature-touched modules and callers |
| After a bug fix | The fix is complete and diagnosis found no clean regression-test seam, duplicated caller recovery, hidden coupling, or order-dependent calls | Fixed path and related callers |
| Manual maintenance | User requests a survey with no narrower evidence artifact | Recent-change hot spots |

A single vague question, generic architecture label, mapping-only request, defect-only review, security/reliability concern, or one-file cleanup does not qualify. Keep its primary route.

## Scope and Recent-Change Bias

Apply this order:

1. Use a user-named module or directory.
2. Else use modules named by the triggering artifact.
3. Else rank paths changed in the last 50 commits:

```bash
git log -n 50 --name-only --format= -- . \
  | sed '/^$/d' \
  | sort \
  | uniq -c \
  | sort -nr \
  | head -30
```

4. Inspect at most 5 top module boundaries and their direct callers.
5. Widen once to adjacent modules only when the initial scope has no candidate meeting the evidence floor and the user requested repository-wide analysis.

Exclude generated files, vendored dependencies, fixtures, snapshots, lockfiles, and build output from change counts. Recent change is a priority signal. Shallowness still requires interface and caller evidence.

## Prior-Decision Read

Before ranking, search the repository's existing decision sources:

```bash
find adr docs -maxdepth 2 -type f -name '*.md' 2>/dev/null \
  | sort
rg -n -i 'rejected|deferred|no.change|interface|module boundary|caller coordination' adr docs 2>/dev/null
test ! -f .local/architecture-decisions.md || printf '%s\n' .local/architecture-decisions.md
```

Build a canonical fingerprint with the bundled helper:

```bash
python3 skills/research/architecture-deepening/scripts/decision_memory.py fingerprint \
  --module '<repo-relative-module>' \
  --symbol '<public-symbol-or-module>' \
  --burden-kind '<leaked-dependency|repeated-configuration|duplicated-coordination|source-knowledge|temporal-ordering|error-leak>'
```

The helper normalizes the module to a repository-relative POSIX path, preserves the exact public symbol, and restricts burden to a fixed enum. Query the store with:

```bash
python3 skills/research/architecture-deepening/scripts/decision_memory.py find \
  --repo-root . \
  --store '<decision-store>' \
  --fingerprint '<canonical-fingerprint>'
```

Before emitting a handoff, run the helper's `validate --fingerprint '<canonical-fingerprint>'` command. It rejects malformed escapes and identities that do not round-trip through the canonicalizer.

The latest matching entry is current. A later entry with `Supersedes` links to the prior entry without rewriting history. A prior decision suppresses a candidate only when the fingerprint and assumptions still match. Changed callers, dependencies, constraints, or feature direction reopen it; append a superseding entry and cite the changed assumption.

## Candidate Evidence Floor

A candidate must contain:

- one specific public interface or module boundary;
- one observed caller burden: leaked dependency, repeated configuration, duplicated coordination, required source reading, or temporal ordering;
- either 2+ affected callers or one high-impact caller with concrete risk;
- a plausible seam and caller deletion or simplification;
- no active matching rejection with unchanged assumptions.

Rank passing candidates by shallowness severity, caller leverage, change likelihood, and deletion-test value. Use HIGH/MEDIUM/LOW labels; the evidence matters more than false numeric precision. Cap the report at 5 candidates.

## Candidate Record

```markdown
### Candidate: <fingerprint>

- Rank: <1-5>
- Scope: <module and callers>
- Interface evidence: <symbols/types/errors callers use>
- Caller burden: <specific knowledge or coordination>
- Change evidence: <named work item or recent-change count>
- Seam: <data|protocol|temporal|error>
- Leverage: <callers and impact>
- Deletion test: <caller code/tests that could simplify>
- Prior decision: <none|path and status|reopened assumption>
- Score: <HIGH|MEDIUM|LOW>
```

This record is read-only analysis. It proposes no interface before the user selects the candidate.

## No-Findings Result

No findings is a complete result:

```markdown
## Architecture Survey: No Material Findings

- Scope inspected: <paths and callers>
- Evidence used: <named artifact or recent-change window>
- Prior decisions applied: <paths or none>
- Candidates considered: <count>
- Why none passed: <failed evidence-floor items>
- Revisit when: <specific feature, caller growth, or changed assumption>
- Next skill: null
- Next pipeline: null
```

Do not invent low-value candidates to reach a count.

## Durable Decision Memory

Record an outcome when all are true:

1. The user selected, rejected, deferred, or closed a real candidate as no-change.
2. At least two credible options existed.
3. The reason is stable and would surprise a future survey.
4. Reversal or repeated analysis has meaningful cost.

Use `docs/architecture-decisions.md` as the conventional shared store. Use the ignored, discoverable `.local/architecture-decisions.md` as the conventional private store. These are the only writable decision-memory paths. Create or update either store only with user approval. Every record carries `memory_scope: shared | local`; a path alone never implies visibility.

Create one JSON record valid against `decision-memory-record.schema.json`, then use the only supported write path:

```bash
python3 skills/research/architecture-deepening/scripts/decision_memory.py append \
  --repo-root . \
  --store 'docs/architecture-decisions.md' \
  --record 'adr/handoffs/<safe-record-name>.json'
```

The command validates the record and canonical fingerprint, refuses symbolic links in the canonical store and lock paths, locks a stable sidecar, re-reads under lock, writes the appended state to a same-directory temporary file, flushes and fsyncs it, atomically replaces the store, then fsyncs the directory. It rejects unsafe record/store/evidence paths and lost-update races. Do not append with Write/Edit, shell redirection, or a second helper. Read this state before each future survey. Preserve earlier entries as decision history. Rejection or deferral still closes when the durability test fails or the user declines the write.

## Terminal States

| Result | Required design/artifact state | Successor |
|---|---|---|
| `selected` | Canonical candidate; non-empty module and caller paths; current/proposed interface; migration; 2+ measurable criteria (3+ for feature work). Decision memory remains consent-gated. | Typed skill/pipeline from change class. |
| `rejected` | Canonical candidate and non-empty inspected scope. Interface, migration, criteria, consultation ADR, skill, and pipeline are null/empty. Decision memory is optional. | Close. |
| `deferred` | Same null action fields as rejected. Decision memory is optional. | Close. |
| `no-change` | Canonical candidate, non-empty scope, and non-empty current-interface rationale. Proposed interface, migration, criteria, skill, and pipeline are null/empty. HIGH risk requires a registered ADR path/hash. | Close. |
| `no-findings` | Candidate, decision artifact/scope, ADR path/hash, interfaces, migration, skill, and pipeline are null; criteria is empty; risk is LOW; inspected modules are non-empty. | Close. |

## Architecture Change Handoff

Emit exactly one handoff per valid terminal result. Emission means the complete JSON is part of the result even in a read-only execution; writing it is a separate authorized persistence step. A fingerprint contradiction, unsafe/symlinked path, containment failure, or stale provenance is invalid input rather than a terminal result: emit no handoff, authorize no requested path, and dispatch no successor. Human approval is required for selected, rejected, deferred, and no-change outcomes; Phase 1 evidence is enough for no-findings. Add the exact `"origin": "architecture-deepening"` field. For action-bearing results when writes are authorized, validate the JSON from standard input and write it through the neutral boundary; validation, containment, and ADR provenance all pass before the repository-anchored atomic writer performs the first write:

```bash
python3 scripts/handoff.py write --stdin \
  --repo-root . \
  --handoff 'adr/handoffs/<safe-name>.json'
```

For no-findings, validate the inline JSON and retain it only in the response. This performs no disk write and creates no transient handoff artifact:

```bash
python3 scripts/handoff.py validate --stdin --repo-root .
```

```json
{
  "origin": "architecture-deepening",
  "result": "selected | rejected | deferred | no-change | no-findings",
  "candidate": "<fingerprint or null>",
  "change_class": "close | behavior-preserving-refactor | interface-migration | new-behavior",
  "scope": {"modules": ["<path>"], "callers": ["<caller source path>"]},
  "risk": "low | medium | high",
  "decision_artifact": "<path or null>",
  "decision_scope": "shared | local | null",
  "consultation_adr": "<registered ADR path or null>",
  "consultation_adr_hash": "<sha256 digest or null>",
  "current_interface": "<summary or null>",
  "proposed_interface": "<summary or null>",
  "migration": "<incremental path or null>",
  "success_criteria": ["<measurable conditions>"],
  "next_skill": "workflow | feature-lifecycle | null",
  "next_pipeline": "systematic-refactoring | null"
}
```

The shared schema encodes each result's nullability, persistence, ADR, successor, scope, interface, migration, and criteria invariants, including the exact decision-store/scope pairing. Action-bearing paths (`scope.modules`, `scope.callers`, `decision_artifact`, `consultation_adr`, plus the handoff/store/record CLI paths) must be repository-relative and may not contain absolute roots, `.`/`..` segments, controls, backslashes, empty segments, leading option segments, or shell metacharacters. Schema checks lexical form; `scripts/handoff.py` decodes the fingerprint, requires its module identity in `scope.modules`, resolves every path, and proves containment after symlink resolution. `scripts/adr-query.py validate-registration` owns generic ADR containment, non-symlink session registration, and content-hash provenance. Every consumer reruns neutral handoff validation with its expected skill/pipeline before acting.

## Successor Rules

| Change class | Typed successor | ADR/consultation rule |
|---|---|---|
| `close` | `next_skill: null`, `next_pipeline: null` | HIGH-risk no-change requires a canonical registered ADR path/hash; other close results carry no consultation ADR. |
| `behavior-preserving-refactor` | `next_skill: workflow`, `next_pipeline: systematic-refactoring` | LOW risk needs no ADR. MEDIUM/HIGH creates, registers, validates, and consults one ADR before workflow intake. |
| `interface-migration` | `next_skill: feature-lifecycle`, `next_pipeline: null` | Incoming handoff has null ADR fields. Feature DESIGN adopts the handoff and creates/registers its canonical feature ADR. The existing pre-IMPLEMENT gate runs consultation once. |
| `new-behavior` | `next_skill: feature-lifecycle`, `next_pipeline: null` | Same feature DESIGN and pre-IMPLEMENT consultation ownership as interface migration. |

Never encode a skill and pipeline as one slash-delimited identifier. Both names must exist in the generated skill/pipeline registries. For any non-null consultation ADR, first run `adr-query.py register`, capture its `sha256:` hash, and run `adr-query.py validate-registration`; consumers repeat that validation. Durable decision memory remains separate from the consultation ADR. The human approves the successor before dispatch.
