# Domain Research Targets

Lookup table for the enrichment loop RESEARCH phase. Given a skill's domain, this
file tells you where to look for knowledge, what authority each source carries, and
what to extract from it.

Format per entry:
- **Primary sources** — official docs, specs, canonical reference material (highest authority)
- **Secondary sources** — blogs, talks, books, community guides (patterns and examples)
- **Extract** — what form of knowledge to pull out (checklists, before/after, decision trees)

---

## Go general (go-patterns, go-patterns, go-patterns, go-patterns, go-patterns)

**Primary sources**
- [Effective Go](https://go.dev/doc/effective_go) — canonical idioms; extract named
  patterns with rationale
- [Go specification](https://go.dev/ref/spec) — authoritative on language semantics;
  useful for edge cases and subtle behavior
- [Go standard library source](https://cs.opensource.google/go/go) — how the stdlib
  itself applies patterns; extract struct design, error handling, and interface choices
- [Go Blog](https://go.dev/blog) — official in-depth articles; especially errors,
  modules, generics, and concurrency posts
- [Go wiki: CodeReviewComments](https://github.com/golang/go/wiki/CodeReviewComments) —
  community-maintained list of Go code review feedback; extract as checklist
- [Go wiki: CommonMistakes](https://github.com/golang/go/wiki/CommonMistakes) —
  extract directly as failure mode catalog

**Secondary sources**
- [Go Proverbs](https://go-proverbs.github.io) (Rob Pike) — memorable heuristics;
  useful for decision criteria
- Dave Cheney's blog (dave.cheney.net) and talks — especially error handling, interfaces,
  and performance; extract before/after examples
- [100 Go Mistakes](https://100go.co) (Teiva Harsanyi) — structured mistake catalog;
  extract mistake + root cause + fix format
- Go 1.22+ release notes — new patterns and deprecations worth knowing

**Extract**
- Checklist: idiomatic Go review (interface size, error wrapping, goroutine hygiene)
- Before/after: common rewrites (bare error returns → wrapped; goroutine leak → context cancel)
- Decision tree: when to use channels vs mutexes, when to define an interface vs use concrete type
- Failure mode catalog: goroutine leaks, error shadowing, interface pollution, unnecessary abstractions

---

## Go SAPCC (go-patterns)

This skill is already rich — it was built from extracted PR review comments from
sapcc/keppel and sapcc/go-bits. Enrichment is low-value unless new PR review
patterns have accumulated.

**When to enrich**: mine new merged PRs from sapcc/keppel and sapcc/go-bits since
the skill's last update date. Look for reviewer comments that establish new patterns
not yet in the skill's references.

**Primary source**: sapcc/keppel PR review history (via `skills/meta/skill-creator/scripts/` pr-workflow (miner))

**Extract**: reviewer comment → pattern name → before/after example, same format as
existing sapcc references

---

## Python (python-quality-gate)

**Primary sources**
- [PEP 8](https://peps.python.org/pep-0008/) — style; extract checklist of the
  non-obvious rules (the obvious ones are already in every model's training)
- [PEP 484](https://peps.python.org/pep-0484/) — type hints; extract annotation patterns
- [PEP 526](https://peps.python.org/pep-0526/) — variable annotations
- [PEP 3107](https://peps.python.org/pep-3107/) — function annotations
- [Python docs: typing module](https://docs.python.org/3/library/typing.html) —
  extract: when to use Protocol vs ABC, TypeVar constraints, overload patterns
- [mypy docs](https://mypy.readthedocs.io) — extract: common type errors and their
  fixes, strict mode implications

**Secondary sources**
- [ruff rules reference](https://docs.astral.sh/ruff/rules/) — every rule has a
  rationale; extract the non-obvious ones as checklist
- Real Python tutorials — extract before/after examples from "Pythonic" articles
- Hynek Schlawack's blog — especially async and attrs patterns

**Extract**
- Checklist: pre-commit quality gate (ruff, mypy, bandit checks that matter most)
- Before/after: common Python failure modes with idiomatic rewrites
- Decision tree: when to use dataclass vs TypedDict vs NamedTuple vs attrs
- Failure mode catalog: mutable default arguments, broad except, type: ignore abuse

---

## Kubernetes (kubernetes umbrella: debugging + security references)

**Primary sources**
- [Kubernetes official docs](https://kubernetes.io/docs/) — especially Concepts and
  Tasks sections; extract patterns, not API reference
- [RBAC best practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/)
- [Network Policy docs](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes) —
  extract as security checklist with severity levels
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

**Secondary sources**
- *Kubernetes Patterns* (Ibryam & Huss) — extract named patterns with use-case criteria
- Learnk8s blog — extract debugging decision trees and before/after manifests
- [kubectl cheat sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/) —
  extract as debugging command reference

**Extract**
- Checklist: security hardening (RBAC, network policies, pod security, secret management)
- Decision tree: debugging pod failures (CrashLoopBackOff → ImagePullBackOff → OOMKilled flow)
- Before/after: insecure manifest → hardened manifest examples
- Failure mode catalog: over-privileged service accounts, missing resource limits, secret in env vars

---

## TypeScript (typescript-check)

**Primary sources**
- [TypeScript handbook](https://www.typescriptlang.org/docs/handbook/) — extract
  non-obvious type patterns: conditional types, mapped types, template literals
- [TypeScript release notes](https://www.typescriptlang.org/docs/handbook/release-notes/overview.html)
  — new features per version; extract patterns introduced in 5.x
- [@types conventions](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/README.md)

**Secondary sources**
- Matt Pocock (total-typescript.com) — extract: advanced type patterns with before/after,
  common TS mistakes with fixes
- [TypeScript Deep Dive](https://basarat.gitbook.io/typescript/) — extract failure modes section

**Extract**
- Checklist: strict mode implications and what each flag catches
- Before/after: `any` abuse → proper generics, type assertion abuse → type guards
- Decision tree: when to use `interface` vs `type`, `unknown` vs `any`, generics vs overloads
- Failure mode catalog: type assertions without guards, overly broad union types, enum misuse

---

## React / Next.js (distinctive-frontend-design, threejs-builder)

**Primary sources**
- [React docs](https://react.dev) — especially the "Thinking in React" and hooks
  reference sections; extract composability patterns
- [Next.js docs](https://nextjs.org/docs) — extract: App Router patterns, server
  component vs client component decision criteria, data fetching patterns

**Secondary sources**
- Vercel blog — extract: App Router migration patterns, performance optimization cases
- Kent C. Dodds (kentcdodds.com) — extract: compound component pattern, custom hooks
  patterns, testing philosophy
- Josh Comeau (joshwcomeau.com) — extract: CSS-in-JS patterns, animation approaches

**Extract**
- Decision tree: server component vs client component selection criteria
- Before/after: common React failure modes (prop drilling → context, useEffect abuse → derived state)
- Checklist: performance review (unnecessary re-renders, missing keys, large bundle items)
- Pattern catalog: compound components, render props, custom hooks with clear interfaces

---

## Testing (test-driven-development, testing-patterns, e2e-testing)

**Primary sources**
- [Playwright docs](https://playwright.dev/docs/intro) — extract: Page Object Model
  structure, locator best practices, network interception patterns
- [pytest docs](https://docs.pytest.org) — extract: fixture patterns, parametrize,
  conftest scope decisions

**Secondary sources**
- Kent C. Dodds — Testing Trophy and [testing-library principles](https://testing-library.com/docs/guiding-principles)
  — extract: what to test at each level
- *Growing Object-Oriented Software, Guided by Tests* (Freeman & Pryce) — extract:
  outside-in TDD pattern, listening to tests as design signal
- *xUnit Test Patterns* (Meszaros) — extract: test smell catalog with names and fixes
- Martin Fowler's [bliki on test doubles](https://martinfowler.com/bliki/TestDouble.html)

**Extract**
- Checklist: test quality review (one assertion focus, arrange-act-assert, test isolation)
- Failure mode catalog with names: Mystery Guest, Eager Test, Fragile Test, Slow Test
- Decision tree: unit vs integration vs E2E for a given scenario
- Before/after: brittle selector → resilient locator, over-mocked test → integrated test

---

## Security (security-threat-model)

**Primary sources**
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) — extract each category as
  a named vulnerability with detection criteria and mitigation checklist
- [OWASP Cheat Sheets](https://cheatsheetseries.owasp.org) — extract checklists per
  topic (SQL injection, XSS, CSRF, auth, etc.)
- [CWE Top 25](https://cwe.mitre.org/top25/) — extract as severity-ranked catalog
- [NIST guidelines](https://csrc.nist.gov/publications) — especially SP 800-53 controls

**Secondary sources**
- PortSwigger Web Security Academy — extract: attack pattern → detection → fix format
- Troy Hunt's blog — extract: real-world mistake catalog

**Extract**
- Checklist: threat modeling prompts (per STRIDE category)
- Before/after: vulnerable code → remediated code for each OWASP Top 10 item
- Decision tree: severity classification (Critical/High/Medium/Low with criteria)
- Failure mode catalog: hard-coded secrets, overly permissive CORS, missing auth checks

---

## Perses (perses-*)

**Primary sources**
- [Perses docs](https://perses.dev/docs/) — extract: dashboard definition spec,
  plugin architecture, variable interpolation formats
- [Perses GitHub wiki](https://github.com/perses/perses/wiki) — supplementary patterns
- [PromQL docs](https://prometheus.io/docs/prometheus/latest/querying/basics/) —
  extract: query optimization patterns, recording rules, alerting rule structure

**Secondary sources**
- Perses GitHub issues and PR discussions — extract: community-documented gotchas
  and workarounds

**Extract**
- Checklist: dashboard quality (variable usage, panel alignment, datasource scoping)
- Before/after: raw PromQL → optimized PromQL with recording rules
- Decision tree: when to use global vs project vs dashboard scope for variables
- Failure mode catalog: hardcoded datasource names, missing variable fallbacks, over-complex queries

---

## Voice skills (create-voice, voice-writer, voice-validator)

These skills are already rich — they have deterministic Python validators and
wabi-sabi calibration built in. Enrichment is rarely warranted.

**When to enrich**: if the banned-pattern list in `voice-validator.py` needs
expansion, or a new voice profile introduces patterns the existing rules don't cover.
Mine the validator's false-positive/false-negative log if one exists.

---

## Code review (systematic-code-review, parallel-code-review)

**Primary sources**
- [Google Engineering Practices: Code Review](https://google.github.io/eng-practices/review/)
  — extract: reviewer standards, author responsibilities, speed guidelines
- [Conventional Comments](https://conventionalcomments.org) — label taxonomy for
  review comments (nitpick, suggestion, issue, question, etc.)

**Secondary sources**
- Michaela Greiler (michaelagreiler.com) — extract: research-backed review effectiveness
  checklist, failure modes in reviewer behavior
- SmartBear Code Review research papers — extract: optimal review size, defect density
  findings as concrete thresholds

**Extract**
- Checklist: what to check at each review tier (security, logic, style, naming)
- Before/after: vague review comment → actionable comment with label
- Decision tree: block vs request-changes vs comment vs approve criteria
- Failure mode catalog: rubber-stamping, nitpick overload, missing context in comments

---

## Git / PR workflows (pr-workflow (pipeline), pr-workflow (sync), git-commit-flow)

**Primary sources**
- [Conventional Commits spec](https://www.conventionalcommits.org) — extract:
  type taxonomy, breaking change notation, footer format
- [GitHub API docs](https://docs.github.com/en/rest) — extract: PR creation fields,
  check run status, review request patterns
- [gh CLI reference](https://cli.github.com/manual/) — extract: useful command
  combinations for PR workflows

**Secondary sources**
- [Git best practices](https://sethrobertson.github.io/GitBestPractices/) — extract:
  commit hygiene rules
- [Chris Beams: How to Write a Git Commit Message](https://cbea.ms/git-commit/) —
  extract: 7 rules as checklist

**Extract**
- Checklist: pre-PR commit hygiene (message format, squash policy, branch naming)
- Before/after: bad commit message → conventional commit message
- Decision tree: squash vs merge vs rebase for different PR types
- Failure mode catalog: fixup commits left in history, force-push to shared branch,
  PR too large to review
