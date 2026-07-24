# Go Version Idioms and Gates

Version-pinned idiom table, hard gates, and error-message-to-version map. Check `go.mod` before applying any row: writing a 1.24+ idiom on a project pinned to 1.21 breaks the build.

```bash
grep '^go ' go.mod   # "go 1.23" means 1.23 features, not 1.24+
```

## Idiom Replacement Table (Go 1.18–1.26)

The most common AI-generated Go failure mode is old idioms where modern ones exist:

| Outdated Pattern | Modern Replacement | Since |
|-----------------|-------------------|-------|
| `interface{}` | `any` | 1.18 |
| `if a > b { return a }; return b` | `max(a, b)` / `min(a, b)` | 1.21 |
| Manual loop for slice search | `slices.Contains(items, x)` | 1.21 |
| `sort.Slice(s, less)` | `slices.SortFunc(s, cmp)` | 1.21 |
| Manual map copy loop | `maps.Clone(m)` | 1.21 |
| `sync.Once` + wrapper func | `sync.OnceFunc(fn)` / `sync.OnceValue(fn)` | 1.21 |
| `log.Printf(...)` | `slog.Info(msg, key, val)` | 1.21 |
| `for i := 0; i < n; i++` | `for i := range n` | 1.22 |
| Chain of nil checks for defaults | `cmp.Or(a, b, c, "default")` | 1.22 |
| Third-party HTTP router | `mux.HandleFunc("GET /path/{id}", h)` + `r.PathValue("id")` | 1.22 |
| Custom iterator types | `iter.Seq[T]` / `iter.Seq2[K,V]` | 1.23 |
| String dedup caches | `unique.Make(s)` | 1.23 |
| `for _, p := range strings.Split(s, ",")` | `for p := range strings.SplitSeq(s, ",")` | 1.24 |
| `for i := 0; i < b.N; i++` in benchmarks | `for b.Loop()` | 1.24 |
| `ctx, cancel := context.WithCancel(...)` in tests | `ctx := t.Context()` | 1.24 |
| `json:"field,omitempty"` for structs/Duration | `json:"field,omitzero"` | 1.24 |
| Manual path sanitization | `os.OpenRoot(dir)` | 1.24 |
| `time.Sleep` in concurrency tests | `testing/synctest` | 1.24 |
| `wg.Add(1); go func() { defer wg.Done()... }()` | `wg.Go(func() { ... })` | 1.25 |
| `x := val; &x` for pointer | `new(val)` | 1.26 |
| `var t *T; errors.As(err, &t)` | `errors.AsType[*T](err)` | 1.26 |

Notes on the newest rows:
- `new(val)` infers the type: `new(0)` is `*int`, `new(T{})` is `*T`. Write `new(0)` directly; a cast like `new(int(0))` is redundant.
- Loop variables are per-iteration since 1.22; explicit capture (`go func(i Item) {...}(item)`) remains the portable pattern for older targets.
- `b.Loop()` also excludes setup iterations from timing.

## Hard Gates (STOP / REPORT / FIX)

Framework: `skills/shared-patterns/forbidden-patterns-template.md`.

| Pattern | Why blocked | Fix |
|---------|-------------|-----|
| `_ = err` (blank error) | Silent failures | `if err != nil { return fmt.Errorf("context: %w", err) }` |
| `panic()` in library code | Crashes caller with no recovery path | Return errors; panic stays in `main()`/`init()` for config failures |
| `go func()` without WaitGroup/context | Goroutine leak, no way to wait/cancel | WaitGroup or context for lifecycle |
| `json:",omitempty"` on structs/Duration | Zero-value structs and Durations still serialize | `json:",omitzero"` (1.24+); on older targets, pointer fields |

```bash
grep -rn "_ = .*err" --include="*.go"
grep -rn "interface{}" --include="*.go"
grep -rn "for.*b\.N" --include="*_test.go"
grep -rn 'omitempty.*Duration\|omitempty.*Time\|omitempty.*struct' --include="*.go"
```

Sanctioned exceptions: `panic()` in `main()`/`init()` for configuration errors; `interface{}` in generated code (protobuf); blank identifier for intentionally ignored non-error values; `omitempty` when targeting Go < 1.24.

## Error Message → Version Map

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `undefined: slices.Contains` | Go < 1.21 | Upgrade go.mod or implement manually |
| `cannot range over N (variable of type int)` | Go < 1.22 | `for i := 0; i < N; i++` |
| `t.Context undefined` | Go < 1.24 | `context.WithCancel(context.Background())` + `t.Cleanup(cancel)` |
| `undefined: (*sync.WaitGroup).Go` | Go < 1.25 | Add/Done pattern |
| `undefined: errors.AsType` | Go < 1.26 | `errors.As(err, &target)` |
