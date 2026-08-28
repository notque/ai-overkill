# Verification Checklists

Comprehensive verification checklists for different domains and scenarios.

## Universal Verification Checklist

Use this checklist for ANY code change, regardless of language or domain:

### Core Checks (Required)
- [ ] **Tests executed**: Ran relevant test suite with verbose output
- [ ] **Tests passed**: All tests completed successfully (output shown)
- [ ] **Build succeeded**: Project builds without errors (output shown)
- [ ] **Files reviewed**: Used Read tool on all changed files
- [ ] **Syntax validated**: Code parses correctly (syntax checker run)
- [ ] **No debug code**: Removed console.log, print statements, debug flags
- [ ] **Diff checked**: Reviewed git diff for unintended changes
- [ ] **Dependencies resolved**: All imports/requires work correctly

### Extended Checks (Recommended)
- [ ] **Documentation updated**: README, docstrings, comments reflect changes
- [ ] **Error handling**: Edge cases and errors properly handled
- [ ] **Backwards compatibility**: Existing functionality not broken
- [ ] **Performance check**: No obvious performance regressions
- [ ] **Security review**: No credentials, secrets, or vulnerabilities introduced
- [ ] **Type safety**: Type annotations correct and checked (where applicable)
- [ ] **Resource cleanup**: Proper cleanup of files, connections, locks
- [ ] **Logging appropriate**: Important operations logged, no excessive logging

---

## Python Project Checklist

### Python-Specific Verification
- [ ] **pytest executed**: `pytest -v` run with full output shown
- [ ] **Test coverage**: Coverage report generated and reviewed (aim for >80%)
- [ ] **Syntax check**: `python -m py_compile` on all changed .py files
- [ ] **Import validation**: All imports resolve correctly
- [ ] **Type hints**: Type annotations correct (if using mypy/pyright)
- [ ] **Linting**: `ruff` or `flake8` passes without new warnings
- [ ] **Formatting**: `black` or `ruff format` applied consistently
- [ ] **Security scan**: `bandit` run for security issues (if using python-quality-gate)
- [ ] **Dependencies**: No new vulnerable dependencies added

### Flask Application Specific
- [ ] **App starts**: Flask app runs without errors
- [ ] **Routes accessible**: Test endpoints with curl/requests
- [ ] **Database migrations**: Migrations up-to-date (if using Flask-Migrate)
- [ ] **Templates render**: HTML templates don't have syntax errors
- [ ] **Static files**: JavaScript/CSS files load correctly

### Django Application Specific
- [ ] **Migrations created**: `python manage.py makemigrations --check` passes
- [ ] **Migrations applied**: `python manage.py migrate` succeeds
- [ ] **Admin registered**: Models show correctly in admin (if applicable)
- [ ] **URL patterns**: `python manage.py check --deploy` passes
- [ ] **Static collected**: `python manage.py collectstatic` works

### FastAPI Application Specific
- [ ] **OpenAPI docs**: `/docs` endpoint shows correct schema
- [ ] **Pydantic validation**: Request/response models validate correctly
- [ ] **Dependency injection**: Dependencies resolve properly
- [ ] **Async operations**: No blocking calls in async functions

---

## Go Project Checklist

### Go-Specific Verification
- [ ] **Tests executed**: `go test ./... -v` run with full output
- [ ] **Race detection**: `go test -race ./...` passes
- [ ] **Build succeeds**: `go build ./...` completes without errors
- [ ] **Linting**: `golangci-lint run ./...` passes
- [ ] **Go modules**: `go mod tidy` doesn't change go.mod/go.sum
- [ ] **Formatting**: `gofmt -l .` shows no unformatted files
- [ ] **Vet passed**: `go vet ./...` shows no issues

### Go Best Practices
- [ ] **Error wrapping**: Errors wrapped with context (fmt.Errorf with %w)
- [ ] **Resource cleanup**: defer statements for Close/Cancel operations
- [ ] **Thread safety**: Concurrent code uses proper synchronization
- [ ] **Context propagation**: Context passed through call chains
- [ ] **Structured logging**: Uses structured logging (not fmt.Println)

### Go Service/API Specific
- [ ] **Service builds**: Binary builds without errors
- [ ] **Service starts**: Can start and handle graceful shutdown
- [ ] **Health endpoint**: `/healthz` or equivalent responds correctly
- [ ] **Metrics exposed**: Prometheus metrics endpoint accessible
- [ ] **API contract**: OpenAPI/Swagger spec matches implementation

---

## JavaScript/TypeScript Project Checklist

### JavaScript-Specific Verification
- [ ] **Tests executed**: `npm test` run with full output shown
- [ ] **Build succeeds**: `npm run build` completes without errors
- [ ] **Syntax check**: `node -c` on all changed .js files
- [ ] **Linting**: `npm run lint` passes without new warnings
- [ ] **Type checking**: `npx tsc --noEmit` passes (if TypeScript)
- [ ] **Dependencies installed**: `npm install` completes successfully

### React Application Specific
- [ ] **Development server**: `npm start` runs without errors
- [ ] **Production build**: `npm run build` creates optimized bundle
- [ ] **Bundle size**: Build output shows reasonable file sizes
- [ ] **Components render**: No React errors in console
- [ ] **Tests pass**: Jest/React Testing Library tests pass

### Node.js Backend Specific
- [ ] **Server starts**: Application starts and listens on port
- [ ] **API endpoints**: Routes respond with expected status codes
- [ ] **Database connection**: Database connects successfully
- [ ] **Environment variables**: All required env vars documented
- [ ] **Error handling**: Unhandled promise rejections caught

---

## Database Change Checklist

### Schema Changes
- [ ] **Migration created**: Database migration file generated
- [ ] **Migration tested**: Migration runs successfully on test database
- [ ] **Rollback tested**: Down migration works correctly
- [ ] **Data preserved**: Existing data not lost during migration
- [ ] **Indexes created**: Appropriate indexes added for new columns
- [ ] **Constraints valid**: Foreign keys, unique constraints work correctly

### Query Changes
- [ ] **Queries tested**: New/modified queries execute successfully
- [ ] **Performance checked**: EXPLAIN ANALYZE shows reasonable plan
- [ ] **Indexes used**: Queries use appropriate indexes
- [ ] **N+1 prevented**: No new N+1 query patterns introduced
- [ ] **Transactions proper**: Transaction boundaries correct

### Schema Verification Gate

Run when a diff touches migration files or schema definitions. Verify schema state before and after the change, not just that the migration command exited 0.

**Before the change** — capture the baseline schema:
- [ ] **SQLite**: `sqlite3 <db> "SELECT sql FROM sqlite_master WHERE type IN ('table','index')"` -- save output
- [ ] **Django**: `python manage.py showmigrations` -- confirm current applied state
- [ ] **Rails**: `rails db:migrate:status` -- confirm current applied state
- [ ] **Raw SQL migrations**: dump schema (`pg_dump --schema-only`, `mysqldump --no-data`, or equivalent) -- save output

**After the change** — diff against the baseline:
- [ ] **SQLite**: re-run `SELECT sql FROM sqlite_master ...`, diff against before-output
- [ ] **Django**: `showmigrations` shows the new migration applied; `makemigrations --check` reports no pending changes
- [ ] **Rails**: `db:migrate:status` shows the new migration `up`
- [ ] **Raw SQL migrations**: re-dump schema, diff against before-output -- confirm only the intended tables/columns changed

**Duplicate/collision check**:
- [ ] **No existing equivalent**: grep the schema dump / model definitions for a table or column that already covers this data under another name (renamed field, near-duplicate table) before adding a new one
- [ ] **Existing queries compatible**: grep the codebase for references to the changed table/column (raw SQL strings, ORM model fields, serializers) -- confirm none break against the new schema

---

## Infrastructure/DevOps Checklist

### Configuration Changes
- [ ] **Config validated**: Configuration files parse correctly
- [ ] **Secrets secured**: No credentials in version control
- [ ] **Environment tested**: Changes work in target environment
- [ ] **Backwards compatible**: Old deployments still function
- [ ] **Documentation updated**: Deployment docs reflect changes

### Kubernetes/Helm Changes
- [ ] **YAML valid**: `kubectl apply --dry-run` succeeds
- [ ] **Helm lint**: `helm lint` passes without errors
- [ ] **Helm template**: `helm template` generates correct manifests
- [ ] **Resources defined**: CPU/memory limits set appropriately
- [ ] **Probes configured**: Liveness/readiness probes working

### Docker Changes
- [ ] **Image builds**: `docker build` completes successfully
- [ ] **Image size**: Image size reasonable (not bloated)
- [ ] **Container starts**: `docker run` starts container without errors
- [ ] **Layers optimized**: Dockerfile uses layer caching effectively
- [ ] **Security scanned**: Image scanned for vulnerabilities

---

## Quality Gate Checklist

Use this when running language-specific quality gates:

### Go Quality Gate (go-patterns)
- [ ] **golangci-lint**: All linters pass without violations
- [ ] **go test**: All tests pass with `-v` flag
- [ ] **Race detector**: `go test -race` passes without issues
- [ ] **go build**: Project builds successfully
- [ ] **go vet**: Static analysis passes
- [ ] **gofmt**: All files properly formatted
- [ ] **Coverage**: Test coverage meets project standards (typically >70%)

### Python Quality Gate (python-quality-gate)
- [ ] **ruff**: Linting passes without violations
- [ ] **pytest**: All tests pass with coverage report
- [ ] **mypy**: Type checking passes (if configured)
- [ ] **bandit**: Security scan passes without HIGH severity issues
- [ ] **Coverage**: Test coverage meets standards (typically >80%)

### Universal Quality Gate (universal-quality-gate)
- [ ] **Language detection**: All project languages detected correctly
- [ ] **Per-language linting**: Each language's linter passes
- [ ] **Per-language tests**: Each language's tests pass
- [ ] **Build verification**: All languages build successfully
- [ ] **Summary report**: Overall quality report shows all green

---

## Documentation Change Checklist

### Documentation Verification
- [ ] **Markdown valid**: Markdown syntax correct (no broken formatting)
- [ ] **Links work**: All links point to valid URLs/files
- [ ] **Code examples**: Code snippets are syntactically correct
- [ ] **Examples tested**: Code examples actually run successfully
- [ ] **Spelling checked**: No obvious typos or misspellings
- [ ] **Formatting consistent**: Consistent style throughout

### API Documentation Specific
- [ ] **Examples accurate**: API examples match actual API behavior
- [ ] **Parameters documented**: All parameters listed with types
- [ ] **Responses documented**: Response formats and status codes listed
- [ ] **Errors documented**: Error conditions and codes documented
- [ ] **Authentication described**: Auth requirements clearly stated

---

## CI/CD Pipeline Checklist

### Pipeline Changes
- [ ] **Syntax valid**: CI config file parses correctly
- [ ] **Pipeline runs**: Pipeline executes without errors
- [ ] **Tests execute**: Test jobs run successfully
- [ ] **Build succeeds**: Build jobs complete without errors
- [ ] **Deploy tested**: Deployment steps work in staging
- [ ] **Rollback possible**: Rollback mechanism still functional

---

## Security Change Checklist

### Security Verification
- [ ] **Secrets excluded**: No credentials in code or logs
- [ ] **Input validated**: User input properly sanitized
- [ ] **Authentication checked**: Auth mechanisms still work
- [ ] **Authorization verified**: Permission checks correct
- [ ] **Dependencies scanned**: No new vulnerable dependencies
- [ ] **Security tests**: Security-related tests pass

---

## Performance Change Checklist

### Performance Verification
- [ ] **Benchmarks run**: Performance benchmarks executed
- [ ] **No regression**: Performance not significantly worse
- [ ] **Memory usage**: Memory consumption reasonable
- [ ] **Load tested**: Handles expected load (if applicable)
- [ ] **Profiling done**: CPU/memory profiling shows no issues

---

## Tuned-Threshold Feature Checklist

Use this when a feature is correct only if a user actually reaches something during normal use: a progress meter, an unlock, a rate limit, a difficulty curve, an onboarding funnel.

### Reachability Verification
- [ ] **Threshold reached live**: Drive the real app and hit the threshold through normal use
- [ ] **Turn or step count recorded**: Note how long it took, not just that it happened
- [ ] **Opposing forces modeled**: Decay, cooldowns, costs, and timeouts included in the check
- [ ] **Representative input used**: An average case, not a best-case deck, dataset, or profile
- [ ] **Regression test locks the result**: Encode the reached threshold as a test

**Why**: unit and integration gates assert that the mechanics compute correctly. They say nothing about whether the value ever climbs high enough. A meter mechanic once passed every unit and integration gate and three review workflows; driving the real app showed the charge thresholds were unreachable in normal play, because flat decay outran the gains. Simulation modeled the mechanic and under-modeled the economy around it.

**Measure before you tune**: check reachability first. If the threshold is already reached, the fix is a regression test that locks the behavior, not an economy change.

---

## Hotfix/Emergency Change Checklist

### Minimal Viable Verification (Emergency Only)
- [ ] **Core tests pass**: Critical path tests executed and passed
- [ ] **Build succeeds**: Application builds without errors
- [ ] **Smoke test**: Basic functionality verified
- [ ] **Rollback ready**: Can rollback quickly if needed
- [ ] **Monitoring active**: Can detect issues in production

**Note**: Document any skipped verification steps and plan comprehensive testing post-deployment.

---

## Verification Report Template

After completing verification, provide a report in this format:

```
✅ Verification Complete

**Domain**: [Python Flask / Go Service / React App / etc.]

**Tests Executed**:
```
[paste complete test output]
```

**Build Status**:
```
[paste complete build output]
```

**Files Verified**:
- `path/to/file1.py`: ✅ Reviewed, syntax valid, logic correct
- `path/to/file2.go`: ✅ Reviewed, syntax valid, logic correct
- `path/to/file3.js`: ✅ Reviewed, syntax valid, logic correct

**Checklist Status**:
- Core checks: 8/8 passed ✅
- Extended checks: 5/5 passed ✅
- Domain-specific checks: 7/7 passed ✅

**Total**: 20/20 verification checks passed

**Verification Evidence**:
- Tests: [link to test output or paste above]
- Build: [link to build output or paste above]
- Changed files reviewed with Read tool: [Yes/No]

**Next Steps**:
Test if this addresses the issue. Please verify the changes work for your specific use case.
```

---

## Completion Checks

### Patterns That Fail Verification
- Say "tests pass" without showing output
- Skip verification because "it's a small change"
- Assume tests exist without checking
- Mark complete based on code review alone
- Say "should work" or "should be fixed"
- Summarize test results instead of showing them

### ✅ ALWAYS Do This
- Show complete, unabbreviated test output
- Run verification even for one-line changes
- Check if tests exist, acknowledge if they don't
- Run actual tests, not just read code
- Say "test if this addresses the issue"
- Display full verification evidence

---

## Verification Levels

### Level 1: Quick Verification (< 2 minutes)
- Syntax check
- Build check
- Quick smoke test
- Changed files reviewed

**Use when**: Documentation changes, config tweaks, very small code changes

### Level 2: Standard Verification (2-5 minutes)
- Full test suite for affected modules
- Build verification
- Changed files reviewed
- Diff checked for unintended changes
- Basic integration check

**Use when**: Feature changes, bug fixes, refactoring

### Level 3: Comprehensive Verification (5-15 minutes)
- Full test suite (all tests)
- Integration tests
- Performance benchmarks
- Security scan
- Cross-platform testing
- Load testing (if applicable)

**Use when**: Major changes, API changes, security-sensitive code, pre-release

### Level 4: Production Verification (15+ minutes)
- All of Level 3
- Staging deployment
- Production smoke test
- Monitoring validation
- Rollback drill

**Use when**: Production deployments, critical hotfixes, infrastructure changes

---

## Success Criteria

Verification is complete when:
1. **All applicable checklists** are satisfied (boxes checked)
2. **Full test output** is shown (not summarized)
3. **Build output** is shown (not summarized)
4. **Changed files** are reviewed with Read tool
5. **Verification report** is provided using template above
6. **User is asked to test** with phrase "Test if this addresses the issue"

**Remember**: The goal is not to check boxes, but to have **confidence** that the changes work correctly and don't break anything.
