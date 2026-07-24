# Go Compact Reference — Versions, Detection, Error Map

> **Scope**: Version-pinned idiom upgrades, detection commands, error-to-version lookup. Go 1.18–1.26.

Targets Go 1.26+; check go.mod before using version-specific features.

```bash
grep '^go ' go.mod   # "go 1.23" means 1.23 features, not 1.24+
```

## Version Upgrade Table

| Old Idiom | Modern Idiom | Since | Detection |
|-----------|-------------|-------|-----------|
| `interface{}` | `any` | 1.18 | `rg 'interface\{\}' --type go` |
| `sort.Slice(s, func(i,j int) bool{...})` | `slices.SortFunc(s, cmp.Compare)` | 1.21 | `rg 'sort\.Slice\(' --type go` |
| Hand-rolled min/max | `min(a, b)` / `max(a, b)` | 1.21 | manual review |
| `for i := 0; i < n; i++` | `for i := range n` | 1.22 | `rg 'for i := 0; i < ' --type go` |
| `item := item` loop-var capture | Per-iteration variables, capture unneeded | 1.22 | `rg 'item := item' --type go` |
| `strings.Split` in `range` | `strings.SplitSeq` | 1.24 | `rg 'strings\.Split\(' --type go` |
| `context.WithCancel` in tests | `t.Context()` | 1.24 | `rg 'context\.Background' --type go --glob '*_test.go'` |
| `for i := 0; i < b.N; i++` | `for b.Loop()` | 1.24 | `rg 'i < b\.N' --type go` |
| `omitempty` on structs/Duration | `omitzero` | 1.24 | check JSON tags |
| `wg.Add(1); go func(){defer wg.Done()...}` | `wg.Go(fn)` | 1.25 | `rg 'wg\.Add\(1\)' --type go` |
| `x := val; &x` | `new(val)` | 1.26 | `rg 'x := .*; &x' --type go` |
| `errors.As(err, &t)` | `errors.AsType[T](err)` | 1.26 | `rg 'errors\.As\(' --type go` |

Version notes: `t.TempDir()` since 1.15, `t.Setenv` since 1.17, fuzzing since 1.18, `t.Cleanup` since 1.14. On Go < 1.25 keep `wg.Add(1)` before the `go` statement (Add inside the goroutine races `Wait()`). On Go < 1.24 pair `context.WithCancel` with `t.Cleanup(cancel)`.

## Error Message → Fix Map

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `undefined: slices.Contains` | Go < 1.21 | Upgrade go.mod or implement manually |
| `cannot range over N (variable of type int)` | Go < 1.22 | `for i := 0; i < N; i++` |
| `t.Context undefined` | Go < 1.24 | `context.WithCancel(context.Background())` + `t.Cleanup(cancel)` |
| `undefined: (*sync.WaitGroup).Go` | Go < 1.25 | Add/Done pattern |
| `undefined: errors.AsType` | Go < 1.26 | `errors.As(err, &target)` |
| `flag provided but not defined: -test.fuzz` | Go < 1.18 | Upgrade; fuzz requires 1.18+ |
| `panic: t.Parallel called after t.Cleanup` | Ordering: `t.Parallel()` must be the subtest's first line | Move `t.Parallel()` to line 1 of the `t.Run` func |
| `goleak: found unexpected goroutines` / `test ended with leaked goroutines` | Goroutines outlive the test | Pass `t.Context()` (1.24+) or `t.Cleanup(cancel)` to every goroutine |
| `DATA RACE` on WaitGroup from `-race` | `wg.Add()` inside goroutine | Move `wg.Add()` before `go`, or `wg.Go()` (1.25+) |

## Detection Commands

```bash
rg 'interface\{\}' --type go                       # upgrade to any
rg 'for i := 0; i < ' --type go                    # upgrade to for range n
rg 'wg\.Add\(1\)' --type go                        # upgrade to wg.Go (1.25+)
rg 'return nil, err$' --type go -g '!*_test.go'    # add fmt.Errorf("...: %w", err) context
grep -rn 'os.TempDir()' --include="*_test.go"      # upgrade to t.TempDir()
go test -race ./...                                # always in CI
```
