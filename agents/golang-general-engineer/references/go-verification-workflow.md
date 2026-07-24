# Go Verification Workflow

Toolkit-specific verification: gopls MCP ordering, library-source checks, rebuilt-binary and render-time verification, dead-code analysis. Loaded for any Go edit, review, or cleanup task.

## gopls MCP Tool Order

Available when `.mcp.json` has a gopls entry and the project has `go.mod`.

| Tool | When (mandatory ordering) |
|------|---------------------------|
| `go_workspace` | First call of every Go session |
| `go_vulncheck` | After `go_workspace` confirms a Go workspace; again after dependency changes |
| `go_file_context` | After reading any Go file for the first time |
| `go_symbol_references` | Before modifying any symbol definition |
| `go_diagnostics` | After every code edit; re-run after applying fixes |
| `go_search` / `go_package_api` | Fuzzy symbol search / third-party package API inspection, as needed |

```
go_symbol_references({"file": "/path/to/server.go", "symbol": "Server.Run"})
go_diagnostics({"files": ["/path/to/server.go"]})
```

Fallback without gopls: `LSP` tool (goToDefinition, findReferences), `Grep` for symbols, `go build` / `go vet` / `go test` for diagnostics. gopls understands types and references where grep sees text — use `go_symbol_references` before renaming.

## Verify the Library, Not the Protocol

**What it looks like**: "Kafka consumer groups will rebalance after a member leaves, so this is safe."
**Why wrong**: Protocol-level behavior and library-level behavior are not the same. LLMs reason from training data about protocols, not from reading the specific library version in go.mod.
**Do instead**: Read the library source in GOMODCACHE. The question is not "how does the protocol work?" but "how does THIS library version implement THIS method?"

```bash
cat $(go env GOMODCACHE)/path/to/lib@version/file.go
```

## Rebuilt Binary Check

When testing a fix to a CLI binary, confirm the binary you're running matches the fix. Check `stat -f %m ./bin/foo` (BSD stat; `stat -c %Y` on Linux) vs the fix commit time, or compare the embedded version SHA against `git rev-parse HEAD`. A stale binary silently passes tests against the old (broken) code path.

## Render-Time Fixes Need Render-Time Verification

Bugs that manifest at output-render time (table layout, template output, log formatting) slip past compile + `go test`. Build a small standalone reproducer under `/tmp` with realistic fake data, run it, and compare before/after output byte-for-byte. Use the module cache rather than vendoring; backend creds stay unneeded.

## Dead Code Analysis with deadcode

`golang.org/x/tools/cmd/deadcode` (SSA whole-program analysis) resolves interface dispatch, method values, and reflection — edges syntax tools miss. Run it during VERIFY for cleanup, review, or refactoring-prep tasks; skip it when the question is only "does this build and pass tests?"

```bash
go install golang.org/x/tools/cmd/deadcode@latest
deadcode ./...            # one line per unreachable function
deadcode -json ./...      # machine-parseable
deadcode -test ./...      # include test binary entry points

# VERIFY sequence for cleanup tasks
go vet ./... && deadcode ./... && go test ./...
```

Known false positives, with fixes:

| Finding | Cause | Fix |
|---------|-------|-----|
| Test helpers flagged (`setupTestDB`, `assertResponse`) | Reachability is computed from `main` entry points; test binaries are excluded by default | `grep -rn "<name>" --include="*_test.go"` to confirm usage, or run `deadcode -test ./...` |
| Exported library API flagged | deadcode cannot see callers outside the module | For library code, act only on unexported findings |

**Tooling decision (measured)**: A/B tested across 5 tests on 2 repos (hermes, log-router): tree-sitter call graph added no measurable value over grep + file reading for dead code detection, code audits, PR reviews, or impact analysis. `deadcode` + `gopls` + grep cover all Go use cases with equal or better results. For impact analysis ("what calls this function?"), use `go_symbol_references` or grep — both outperformed tree-sitter call graphs in blind testing.
