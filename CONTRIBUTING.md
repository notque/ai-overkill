# Contributing

The system has four component types, a quality bar, and a PR workflow. Everything else is implementation detail you discover by building things.

## Standards

Every contribution passes through this filter. Not aspirational. Enforced.

| Criterion | Pass | Fail |
|-----------|------|------|
| **Specific** | Actionable steps, exit criteria | Vague advice ("be careful") |
| **Verifiable** | Evidence requirements | Trusts LLM confidence |
| **Battle-tested** | Real workflows, A/B tested | Hypothetical "should work" |
| **Minimal** | What guides the agent, nothing else | Verbose human explanations |
| **Dense** | Every word carries instruction | Prose where a table works |

## Component Types

| Component | Location | Format | Purpose |
|-----------|----------|--------|---------|
| Agent | `agents/{name}.md` | YAML frontmatter + markdown | Domain expertise |
| Skill | `skills/{name}/SKILL.md` | YAML frontmatter + phased instructions | Workflow methodology |
| Hook | `hooks/{name}.py` | Python, JSON in/out | Event-driven automation |
| Script | `scripts/{name}.py` | Python CLI | Deterministic operations |

The constraint that separates them: agents know *what*, skills know *how*, hooks react to *events*, scripts do *mechanical work*. If it requires judgment, it belongs in an agent or skill. If it requires speed and determinism, it belongs in a script or hook.

## Adding Components

The toolkit has creator agents. Tell `/do` what you want.

**Agent:**
```
/do create an agent for [domain]
```

**Skill:**
```
/do create a skill for [workflow]
```

**Hook:**
```
/do create a hook for [purpose]
```

The creator handles file structure, frontmatter, index registration, and routing integration. Test routing after creation:

```
/do [request that should trigger your new component]
```

## PR Workflow

The full cycle, in order:

1. **Branch** from main (`feature/`, `fix/`, `refactor/`)
2. **Implement** changes
3. **Wave review** via `/pr-review` (parallel reviewer agents)
4. **Fix** findings (up to 3 iterations)
5. **Record** any dead end in `docs/what-didnt-work.md` with its evidence location
6. **Edit** the agent or skill file yourself when a finding should change behavior
7. **Commit** (conventional format, no AI attribution)
8. **Push** to remote
9. **PR** via `gh pr create`
10. **CI** passes
11. **Merge**

The `pr-workflow` skill automates steps 3 through 10.

## Quality Gates

Before submitting:

- `ruff check . --config pyproject.toml` passes
- `ruff format --check . --config pyproject.toml` passes
- `python3 scripts/validate-references.py` passes (if adding references)
- New components appear in INDEX after running generators
- No secrets in committed files

## Testing

pytest. Two directories: `hooks/tests/`, `scripts/tests/`.

```bash
pytest -v                          # everything
pytest hooks/tests/ -v             # hooks only
pytest scripts/tests/ -v           # scripts only
```

Hooks: feed JSON, assert JSON output. Scripts: deterministic input/output verification. Agents and skills use the eval harness in `skills/meta/skill-eval/`.

## Conventions

**Conventional commits.** `type(scope): description`. Types: feat, fix, refactor, docs, test, chore.

**No AI attribution.** No "Generated with Claude Code" or co-author lines. Ever.

**Branch safety.** Create feature branches for all work. The pretool hook enforces this.

**INDEX.json is generated.** Run `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`. Do not hand-edit.

**Scripts are deterministic.** LLM judgment goes in agents and skills, not scripts.

**50ms hook budget.** Hooks fire on every tool call. Keep them fast. `scripts/benchmark-hooks.py` validates this.

**Wabi-sabi in docs.** Write like a human. Contractions fine. Fragments fine. Banned words: "delve", "leverage", "comprehensive", "robust", "streamline", "empower". `scripts/scan-ai-patterns.py` catches violations.

### Negative results

Tried something that lost? Record it in `docs/what-didnt-work.md` before you forget. One dated section, four fields (Expectation, What happened, Evidence, Decision), newest on top. Evidence must be a location, not a claim. Check the file before re-running an experiment, so you don't re-litigate a decision already made.
