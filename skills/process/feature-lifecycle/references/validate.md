# Feature Validate Phase

Run comprehensive quality gates on the implemented feature. Phase 4 of the feature lifecycle (design > plan > implement > **validate** > release).

## Instructions

### Phase 0: PRIME

1. Read and follow the repository CLAUDE.md before any other action -- it may override defaults for linting, test commands, or gate criteria.
2. Verify feature state is `validate` and `implement` is completed. All state operations go through `python3 ~/.claude/scripts/feature-state.py` -- never modify state files directly.
3. Load implementation artifact from `.feature/state/implement/`. Validation cannot proceed without implementation artifacts; if missing, stop and report.
4. Load L0, L1, and implementation context so quality gates run against the correct scope.

**Gate**: Implementation artifact loaded. Feature state confirms `implement` completed. Proceed.

### Phase 1: EXECUTE (Quality Gates)

**Verification means execution, not reasoning.** Run the command. Do not reason about whether the command would pass. Do not summarize the expected output. Execute the check, paste the exit code, paste the relevant output. A verification phase that produces a verdict without an observed tool result is not a verification — it is a guess with a rigor aesthetic.

**Step 1: Language Detection**

Auto-detect project language(s) from file extensions, build files, and the implementation artifact. This detection drives which quality gate skill runs next.

**Step 2: Run Quality Gates**

Use the repository's existing quality gate skills -- do not re-implement linting or test runners inline. Route to the appropriate skill per language:

| Language | Quality Gate | Command |
|----------|-------------|---------|
| Go | go-patterns | `make check` or `go test ./... && go vet ./...` |
| Python | python-quality-gate | `ruff check && pytest && mypy` |
| TypeScript | universal-quality-gate | `npm run typecheck && npm run lint && npm test` |
| Other | universal-quality-gate | Detect and run project-specific checks |

Show the full, unedited command output for every gate -- never summarize or truncate test results, because summaries hide the exact failure details needed for diagnosis.

**Step 3: Regression Check**

Run the full test suite and compare against pre-implementation baseline:
- New test failures = regression
- Missing tests for new code = coverage gap

Existing tests must still pass; new failures here block advancement regardless of new-feature test results.

**Step 4: Custom Gates**

If the design document specified custom validation criteria, check those too.

**Step 5 (optional): Security and Performance**

If explicitly enabled by the user:
- **Security scan**: Run security-focused review agent
- **Performance check**: Run benchmarks against baseline

These are off by default -- do not run them unless the user requests it.

**Gate**: Every gate must pass. No gate may be skipped and no failure may be approved -- a single failing gate blocks advancement to release. Proceed only when all results are green.

### Phase 2: VALIDATE (Report)

Produce the validation report:

```markdown
# Validation Report: [Feature Name]

## Quality Gates
- [ ] Tests: PASS/FAIL (X/Y passed)
- [ ] Lint: PASS/FAIL (N issues)
- [ ] Type Check: PASS/FAIL
- [ ] Regression: PASS/FAIL

## Coverage
- New files: X
- Modified files: Y
- Test coverage: Z%

## Issues Found
- [Issue 1]: [severity]
- [Issue 2]: [severity]

## Verdict: PASS / NEEDS_FIXES / BLOCK
```

The verdict must reflect actual gate results -- never mark PASS if any gate failed.

If `NEEDS_FIXES`: suggest routing back to the implement phase with specific fix tasks. This phase does not fix failing tests; it reports them and routes back.
If `BLOCK`: explain blocking issues.

**Gate**: Report produced. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

1. Save validation artifact (all state operations through the feature-state script):
   ```bash
   echo "VALIDATION_REPORT" | python3 ~/.claude/scripts/feature-state.py checkpoint FEATURE validate
   ```

2. If validation passed, advance:
   ```bash
   python3 ~/.claude/scripts/feature-state.py advance FEATURE
   ```

3. Suggest next step:
   ```
   Validation passed. Run /feature-lifecycle to continue to the release phase.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Tests fail | Implementation bugs | Route back to implement phase with failure details |
| No test framework detected | Project setup incomplete | Report gap, suggest setup |
| Lint failures | Style issues | Auto-fix if trivial, otherwise route back |
