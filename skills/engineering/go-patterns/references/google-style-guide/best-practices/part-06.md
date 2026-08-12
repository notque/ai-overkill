elements or members.

In contrast, using composite literals to declare empty or memberless values can
be visually noisy compared to [zero-value initialization](#vardeclzero).

When you need a pointer to a zero value, you have two options: empty composite
literals and `new`. Both are fine, but the `new` keyword can serve to remind the
reader that if a non-zero value were needed, a composite literal wouldn't work:

```go
// Good:
var (
  buf = new(bytes.Buffer) // non-empty Buffers are initialized with constructors.
  msg = new(pb.Message) // non-empty proto messages are initialized with builders or by setting fields one by one.
)
```

[composite literal]: https://golang.org/ref/spec#Composite_literals

<a id="vardeclsize"></a>

### Size hints

The following are declarations that take advantage of size hints in order to
preallocate capacity:

```go
// Good:
var (
    // Preferred buffer size for target filesystem: st_blksize.
    buf = make([]byte, 131072)
    // Typically process up to 8-10 elements per run (16 is a safe assumption).
    q = make([]Node, 0, 16)
    // Each shard processes shardSize (typically 32000+) elements.
    seen = make(map[string]bool, shardSize)
)
```

Size hints and preallocation are important steps **when combined with empirical
analysis of the code and its integrations**, to create performance-sensitive and
resource-efficient code.

Most code does not need a size hint or preallocation, and can allow the runtime
to grow the slice or map as necessary. It is acceptable to preallocate when the
final size is known (e.g. when converting between a map and a slice) but this is
not a readability requirement, and may not be worth the clutter in small cases.

**Warning:** Preallocating more memory than you need can waste memory in the
fleet or even harm performance. When in doubt, see
[GoTip #3: Benchmarking Go Code] and default to a
[zero initialization](#vardeclzero) or a
[composite literal declaration](#vardeclcomposite).

[GoTip #3: Benchmarking Go Code]: https://google.github.io/styleguide/go/index.html#gotip

<a id="decl-chan"></a>

### Channel direction

Specify [channel direction] where possible.

```go
// Good:
// sum computes the sum of all of the values. It reads from the channel until
// the channel is closed.
func sum(values <-chan int) int {
    // ...
}
```

This prevents casual programming errors that are possible without specification:

```go
// Bad:
func sum(values chan int) (out int) {
    for v := range values {
        out += v
    }
    // values must already be closed for this code to be reachable, which means
    // a second close triggers a panic.
    close(values)
}
```

When the direction is specified, the compiler catches simple errors like this.
It also helps to convey a measure of ownership to the type.

See also Bryan Mills' talk "Rethinking Classical Concurrency Patterns":
[slides][rethinking-concurrency-slides] [video][rethinking-concurrency-video].

[rethinking-concurrency-slides]: https://drive.google.com/file/d/1nPdvhB0PutEJzdCq5ms6UI58dp50fcAN/view?usp=sharing
[rethinking-concurrency-video]: https://www.youtube.com/watch?v=5zXAHh5tJqQ
[channel direction]: https://go.dev/ref/spec#Channel_types

<a id="funcargs"></a>

## Function argument lists

Don't let the signature of a function get too long. As more parameters are added
to a function, the role of individual parameters becomes less clear, and
adjacent parameters of the same type become easier to confuse. Functions with
large numbers of arguments are less memorable and more difficult to read at the
call-site.

When designing an API, consider splitting a highly configurable function whose
signature is growing complex into several simpler ones. These can share an
(unexported) implementation if necessary.

Where a function requires many inputs, consider introducing an [option struct]
for some of the arguments or employing the more advanced [variadic options]
technique. The primary consideration for which strategy to choose should be how
the function call looks across all expected use cases.

The recommendations below primarily apply to exported APIs, which are held to a
higher standard than unexported ones. These techniques may be unnecessary for
your use case. Use your judgment, and balance the principles of [clarity] and
[least mechanism].

See also:
[Go Tip #24: Use Case-Specific Constructions](https://google.github.io/styleguide/go/index.html#gotip)

[option struct]: #option-structure
[variadic options]: #variadic-options
[clarity]: guide#clarity
[least mechanism]: guide#least-mechanism

<a id="option-structure"></a>

### Option structure

An option structure is a struct type that collects some or all of the arguments
of a function or method, that is then passed as the last argument to the
function or method. (The struct should be exported only if it is used in an
exported function.)

Using an option structure has a number of benefits:

*   The struct literal includes both fields and values for each argument, which
    makes them self-documenting and harder to swap.
*   Irrelevant or "default" fields can be omitted.
*   Callers can share the option struct and write helpers to operate on it.
*   Structs provide cleaner per-field documentation than function arguments.
*   Option structs can grow over time without impacting call-sites.

Here is an example of a function that could be improved:

```go
// Bad:
func EnableReplication(ctx context.Context, config *replicator.Config, primaryRegions, readonlyRegions []string, replicateExisting, overwritePolicies bool, replicationInterval time.Duration, copyWorkers int, healthWatcher health.Watcher) {
    // ...
}
```

The function above could be rewritten with an option structure as follows:

```go
// Good:
type ReplicationOptions struct {
    Config              *replicator.Config
    PrimaryRegions      []string
    ReadonlyRegions     []string
    ReplicateExisting   bool
    OverwritePolicies   bool
    ReplicationInterval time.Duration
    CopyWorkers         int
    HealthWatcher       health.Watcher
}

func EnableReplication(ctx context.Context, opts ReplicationOptions) {
    // ...
}
```

The function can then be called in a different package:

```go
// Good:
func foo(ctx context.Context) {
    // Complex call:
    storage.EnableReplication(ctx, storage.ReplicationOptions{
        Config:              config,
        PrimaryRegions:      []string{"us-east1", "us-central2", "us-west3"},
        ReadonlyRegions:     []string{"us-east5", "us-central6"},
        OverwritePolicies:   true,
        ReplicationInterval: 1 * time.Hour,
        CopyWorkers:         100,
        HealthWatcher:       watcher,
    })

    // Simple call:
    storage.EnableReplication(ctx, storage.ReplicationOptions{
        Config:         config,
        PrimaryRegions: []string{"us-east1", "us-central2", "us-west3"},
    })
}
```

**Note:** [Contexts are never included in option structs](decisions#contexts).

This option is often preferred when some of the following apply:

*   All callers need to specify one or more of the options.
*   A large number of callers need to provide many options.
*   The options are shared between multiple functions that the user will call.

<a id="variadic-options"></a>

### Variadic options

Using variadic options, exported functions are created which return closures
that can be passed to the [variadic (`...`) parameter] of a function. The
function takes as its parameters the values of the option (if any), and the
returned closure accepts a mutable reference (usually a pointer to a struct
type) that will be updated based on the inputs.

[variadic (`...`) parameter]: https://golang.org/ref/spec#Passing_arguments_to_..._parameters

Using variadic options can provide a number of benefits:

*   Options take no space at a call-site when no configuration is needed.
*   Options are still values, so callers can share them, write helpers, and
    accumulate them.
*   Options can accept multiple parameters (e.g. `cartesian.Translate(dx, dy
    int) TransformOption`).
*   The option functions can return a named type to group options together in
    godoc.
*   Packages can allow (or prevent) third-party packages to define (or from
    defining) their own options.

**Note:** Using variadic options requires a substantial amount of additional
code (see the following example), so it should only be used when the advantages
outweigh the overhead.

Here is an example of a function that could be improved:

```go
// Bad:
func EnableReplication(ctx context.Context, config *placer.Config, primaryCells, readonlyCells []string, replicateExisting, overwritePolicies bool, replicationInterval time.Duration, copyWorkers int, healthWatcher health.Watcher) {
  ...
}
```

The example above could be rewritten with variadic options as follows:

```go
// Good:
type replicationOptions struct {
    readonlyCells       []string
    replicateExisting   bool
    overwritePolicies   bool
    replicationInterval time.Duration
    copyWorkers         int
    healthWatcher       health.Watcher
}

// A ReplicationOption configures EnableReplication.
type ReplicationOption func(*replicationOptions)

// ReadonlyCells adds additional cells that should additionally
// contain read-only replicas of the data.
//
// Passing this option multiple times will add additional
// read-only cells.
//
// Default: none
func ReadonlyCells(cells ...string) ReplicationOption {
    return func(opts *replicationOptions) {
        opts.readonlyCells = append(opts.readonlyCells, cells...)
    }
}

// ReplicateExisting controls whether files that already exist in the
// primary cells will be replicated.  Otherwise, only newly-added
// files will be candidates for replication.
//
// Passing this option again will overwrite earlier values.
//
// Default: false
func ReplicateExisting(enabled bool) ReplicationOption {
    return func(opts *replicationOptions) {
        opts.replicateExisting = enabled
    }
}

// ... other options ...

// DefaultReplicationOptions control the default values before
// applying options passed to EnableReplication.
var DefaultReplicationOptions = []ReplicationOption{
    OverwritePolicies(true),
    ReplicationInterval(12 * time.Hour),
    CopyWorkers(10),
}

func EnableReplication(ctx context.Context, config *placer.Config, primaryCells []string, opts ...ReplicationOption) {
    var options replicationOptions
    for _, opt := range DefaultReplicationOptions {
        opt(&options)
    }
    for _, opt := range opts {
        opt(&options)
    }
}
```

The function can then be called in a different package:

```go
// Good:
func foo(ctx context.Context) {
    // Complex call:
    storage.EnableReplication(ctx, config, []string{"po", "is", "ea"},
        storage.ReadonlyCells("ix", "gg"),
        storage.OverwritePolicies(true),
        storage.ReplicationInterval(1*time.Hour),
        storage.CopyWorkers(100),
        storage.HealthWatcher(watcher),
    )

    // Simple call:
    storage.EnableReplication(ctx, config, []string{"po", "is", "ea"})
}
```

Prefer this option when many of the following apply:

*   Most callers will not need to specify any options.
*   Most options are used infrequently.
*   There are a large number of options.
*   Options require arguments.
*   Options could fail or be set incorrectly (in which case the option function
    returns an `error`).
*   Options require a lot of documentation that can be hard to fit in a struct.
*   Users or other packages can provide custom options.

Options in this style should accept parameters rather than using presence to
signal their value; the latter can make dynamic composition of arguments much
more difficult. For example, binary settings should accept a boolean (e.g.
`rpc.FailFast(enable bool)` is preferable to `rpc.EnableFailFast()`). An
enumerated option should accept an enumerated constant (e.g.
`log.Format(log.Capacitor)` is preferable to `log.CapacitorFormat()`). The
alternative makes it much more difficult for users who must programmatically
choose which options to pass; such users are forced to change the actual
composition of the parameters rather than simply changing the arguments to the
options. Don't assume that all users will know the full set of options
statically.

In general, options should be processed in order. If there is a conflict or if a
non-cumulative option is passed multiple times, the last argument should win.

The parameter to the option function is generally unexported in this pattern, to
restrict the options to being defined only within the package itself. This is a
good default, though there may be times when it is appropriate to allow other
packages to define options.

See [Rob Pike's original blog post] and [Dave Cheney's talk] for a more in-depth
look at how these options can be used.

[Rob Pike's original blog post]: http://commandcenter.blogspot.com/2014/01/self-referential-functions-and-design.html
[Dave Cheney's talk]: https://dave.cheney.net/2014/10/17/functional-options-for-friendly-apis

<a id="complex-clis"></a>

## Complex command-line interfaces

Some programs wish to present users with a rich command-line interface that
includes sub-commands. For example, `kubectl create`, `kubectl run`, and many
other sub-commands are all provided by the program `kubectl`. There are at least
the following libraries in common use for achieving this.

If you don't have a preference or other considerations are equal, [subcommands]
is recommended, since it is the simplest and is easy to use correctly. However,
if you need different features that it doesn't provide, pick one of the other
options.

*   **[cobra]**

    *   Flag convention: getopt
    *   Common outside the Google codebase.
    *   Many extra features.
    *   Pitfalls in usage (see below).

*   **[subcommands]**

    *   Flag convention: Go
    *   Simple and easy to use correctly.
    *   Recommended if you don't need extra features.

**Warning**: cobra command functions should use `cmd.Context()` to obtain a
context rather than creating their own root context with `context.Background`.
Code that uses the subcommands package already receives the correct context as a
function parameter.

You are not required to place each subcommand in a separate package, and it is
often not necessary to do so. Apply the same considerations about package
boundaries as in any Go codebase. If your code can be used both as a library and
as a binary, it is usually beneficial to separate the CLI code and the library,
making the CLI just one more of its clients. (This is not specific to CLIs that
have subcommands, but is mentioned here because it is a common place where it
comes up.)
