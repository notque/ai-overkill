
### Don't panic

<a id="TOC-Don-t-Panic"></a>

Do not use `panic` for normal error handling. Instead, use `error` and multiple
return values. See the [Effective Go section on errors].

Within `package main` and initialization code, consider [`log.Exit`] for errors
that should terminate the program (e.g., invalid configuration), as in many of
these cases a stack trace will not help the reader. Please note that
[`log.Exit`] calls [`os.Exit`] and any deferred functions will not be run.

For errors that indicate "impossible" conditions, namely bugs that should always
be caught during code review and/or testing, a function may reasonably return an
error or call [`log.Fatal`].

Also see [when panic is acceptable](best-practices.md#when-to-panic).

**Note:** `log.Fatalf` is not the standard library log. See [#logging].

[Effective Go section on errors]: http://golang.org/doc/effective_go.html#errors
[`os.Exit`]: https://pkg.go.dev/os#Exit

<a id="must-functions"></a>

### Must functions

Setup helper functions that stop the program on failure follow the naming
convention `MustXYZ` (or `mustXYZ`). In general, they should only be called
early on program startup, not on things like user input where normal Go error
handling is preferred.

This often comes up for functions called to initialize package-level variables
exclusively at
[package initialization time](https://golang.org/ref/spec#Package_initialization)
(e.g. [template.Must](https://golang.org/pkg/text/template/#Must) and
[regexp.MustCompile](https://golang.org/pkg/regexp/#MustCompile)).

```go
// Good:
func MustParse(version string) *Version {
    v, err := Parse(version)
    if err != nil {
        panic(fmt.Sprintf("MustParse(%q) = _, %v", version, err))
    }
    return v
}

// Package level "constant". If we wanted to use `Parse`, we would have had to
// set the value in `init`.
var DefaultVersion = MustParse("1.2.3")
```

The same convention may be used in test helpers that only stop the current test
(using `t.Fatal`). Such helpers are often convenient in creating test values,
for example in struct fields of [table driven tests](#table-driven-tests), as
functions that return errors cannot be directly assigned to a struct field.

```go
// Good:
func mustMarshalAny(t *testing.T, m proto.Message) *anypb.Any {
  t.Helper()
  any, err := anypb.New(m)
  if err != nil {
    t.Fatalf("mustMarshalAny(t, m) = %v; want %v", err, nil)
  }
  return any
}

func TestCreateObject(t *testing.T) {
  tests := []struct{
    desc string
    data *anypb.Any
  }{
    {
      desc: "my test case",
      // Creating values directly within table driven test cases.
      data: mustMarshalAny(t, mypb.Object{}),
    },
    // ...
  }
  // ...
}
```

In both of these cases, the value of this pattern is that the helpers can be
called in a "value" context. These helpers should not be called in places where
it's difficult to ensure an error would be caught or in a context where an error
should be [checked](#handle-errors) (e.g., in many request handlers). For
constant inputs, this allows tests to easily ensure that the `Must` arguments
are well-formed, and for non-constant inputs it permits tests to validate that
errors are [properly handled or propagated](best-practices#error-handling).

Where `Must` functions are used in a test, they should generally be
[marked as a test helper](#mark-test-helpers) and call `t.Fatal` on error (see
[error handling in test helpers](best-practices#test-helper-error-handling) for
more considerations of using that).

They should not be used when
[ordinary error handling](best-practices#error-handling) is possible (including
with some refactoring):

```go
// Bad:
func Version(o *servicepb.Object) (*version.Version, error) {
    // Return error instead of using Must functions.
    v := version.MustParse(o.GetVersionString())
    return dealiasVersion(v)
}
```

<a id="goroutine-lifetimes"></a>

### Goroutine lifetimes

<a id="TOC-GoroutineLifetimes"></a>

When you spawn goroutines, make it clear when or whether they exit.

Goroutines can leak by blocking on channel sends or receives. The garbage
collector will not terminate a goroutine blocked on a channel even if no other
goroutine has a reference to the channel.

Even when goroutines do not leak, leaving them in-flight when they are no longer
needed can cause other subtle and hard-to-diagnose problems. Sending on a
channel that has been closed causes a panic.

```go
// Bad:
ch := make(chan int)
ch <- 42
close(ch)
ch <- 13 // panic
```

Modifying still-in-use inputs "after the result isn't needed" can lead to data
races. Leaving goroutines in-flight for arbitrarily long can lead to
unpredictable memory usage.

Concurrent code should be written such that the goroutine lifetimes are obvious.
Typically this will mean keeping synchronization-related code constrained within
the scope of a function and factoring out the logic into
[synchronous functions]. If the concurrency is still not obvious, it is
important to document when and why the goroutines exit.

Code that follows best practices around context usage often helps make this
clear. It is conventionally managed with a [`context.Context`]:

```go
// Good:
func (w *Worker) Run(ctx context.Context) error {
    var wg sync.WaitGroup
    // ...
    for item := range w.q {
        // process returns at latest when the context is cancelled.
        wg.Add(1)
        go func() {
            defer wg.Done()
            process(ctx, item)
        }()
    }
    // ...
    wg.Wait()  // Prevent spawned goroutines from outliving this function.
}
```

There are other variants of the above that use raw signal channels like `chan
struct{}`, synchronized variables, [condition variables][rethinking-slides], and
more. The important part is that the goroutine's end is evident for subsequent
maintainers.

In contrast, the following code is careless about when its spawned goroutines
finish:

```go
// Bad:
func (w *Worker) Run() {
    // ...
    for item := range w.q {
        // process returns when it finishes, if ever, possibly not cleanly
        // handling a state transition or termination of the Go program itself.
        go process(item)
    }
    // ...
}
```

This code may look OK, but there are several underlying problems:

*   The code probably has undefined behavior in production, and the program may
    not terminate cleanly, even if the operating system releases the resources.

*   The code is difficult to test meaningfully due to the code's indeterminate
    lifecycle.

*   The code may leak resources as described above.

See also:

*   [Never start a goroutine without knowing how it will stop][cheney-stop]
*   Rethinking Classical Concurrency Patterns: [slides][rethinking-slides],
    [video][rethinking-video]
*   [When Go programs end]
*   [Documentation Conventions: Contexts]

[synchronous functions]: #synchronous-functions
[cheney-stop]: https://dave.cheney.net/2016/12/22/never-start-a-goroutine-without-knowing-how-it-will-stop
[rethinking-slides]: https://drive.google.com/file/d/1nPdvhB0PutEJzdCq5ms6UI58dp50fcAN/view
[rethinking-video]: https://www.youtube.com/watch?v=5zXAHh5tJqQ
[When Go programs end]: https://changelog.com/gotime/165
[Documentation Conventions: Contexts]: best-practices.md#documentation-conventions-contexts

<a id="interfaces"></a>

### Interfaces

<a id="TOC-Interfaces"></a>

Avoid creating interfaces until a [real need](guide#simplicity) exists. Focus on
the required behavior rather than just abstract named patterns like "service" or
"repository" and the like.

*   Do not wrap RPC clients in new manual interfaces just for the sake of
    abstraction or testing.
    [Use real transports](best-practices#use-real-transports) instead
    ([testing RPC]).

*   Do not define back doors or export [test double] implementations of an
    interface solely for testing. Prefer testing via the [public API] of the
    real implementation instead.

Design interfaces to be small for easier implementation and composition
([GoTip #78: Minimal Viable Interfaces]). Document interfaces appropriately
including their contract, edge cases, and expected errors. Keep interface types
unexported if they are only used internally within a package.

The consumer of the interface should define it (not the package implementing the
interface), ensuring it includes only the methods they actually use. The
producer package may export the interface if the interface is the product (a
common protocol) to prevent interface redefinition bloat.

There is an adage: Functions should take interfaces as arguments but return
concrete types ([GoTip #49: Accept Interfaces, Return Concrete Types]).
Returning concrete types allows the caller to have access to every public method
and field of that specific implementation, not just the subset of methods
defined in a pre-chosen interface. The caller can still pass that concrete
result into any other function that expects an interface. Sometimes returning an
interface is acceptable for encapsulation (e.g., `error` interface), and certain
constructs like command, chaining, factory, and
[strategy](https://en.wikipedia.org/wiki/Strategy_pattern) patterns.

Deeper discussion on interfaces exists in the
[Best Practices' section on interfaces](best-practices#interfaces).

[GoTip #78: Minimal Viable Interfaces]: https://google.github.io/styleguide/go/index.html#gotip
[GoTip #49: Accept Interfaces, Return Concrete Types]: https://google.github.io/styleguide/go/index.html#gotip
[testing RPC]: https://codelabs.developers.google.com/grpc/getting-started-grpc-go#3
[test double]: https://abseil.io/resources/swe-book/html/ch13.html
[public API]: https://abseil.io/resources/swe-book/html/ch12.html#test_via_public_apis

<a id="generics"></a>

### Generics

Generics (formally called "[Type Parameters]") are allowed where they fulfill
your business requirements. In many applications, a conventional approach using
existing language features (slices, maps, interfaces, and so on) works just as
well without the added complexity, so be wary of premature use. See the
discussion on [least mechanism](guide#least-mechanism).

When introducing an exported API that uses generics, make sure it is suitably
documented. It's highly encouraged to include motivating runnable [examples].

Do not use generics just because you are implementing an algorithm or data
structure that does not care about the type of its member elements. If there is
only one type being instantiated in practice, start by making your code work on
that type without using generics at all. Adding polymorphism later will be
straightforward compared to removing abstraction that is found to be
unnecessary.

Do not use generics to invent domain-specific languages (DSLs). In particular,
refrain from introducing error-handling frameworks that might put a significant
burden on readers. Instead prefer established [error handling](#errors)
practices. For testing, be especially wary of introducing
[assertion libraries](#assert) or frameworks that result in less useful
[test failures](#useful-test-failures).

In general:

*   [Write code, don't design types]. From a GopherCon talk by Robert Griesemer
    and Ian Lance Taylor.
*   If you have several types that share a useful unifying interface, consider
    modeling the solution using that interface. Generics may not be needed.
*   Otherwise, instead of relying on the `any` type and excessive
    [type switching](https://tour.golang.org/methods/16), consider generics.

See also:

*   [Using Generics in Go], talk by Ian Lance Taylor

*   [Generics tutorial] on Go's webpage

[Generics tutorial]: https://go.dev/doc/tutorial/generics
[Type Parameters]: https://go.dev/design/43651-type-parameters
[Using Generics in Go]: https://www.youtube.com/watch?v=nr8EpUO9jhw
[Write code, don't design types]: https://www.youtube.com/watch?v=Pa_e9EeCdy8&t=1250s

<a id="pass-values"></a>

### Pass values

<a id="TOC-PassValues"></a>

Do not pass pointers as function arguments just to save a few bytes. If a
function reads its argument `x` only as `*x` throughout, then the argument
shouldn't be a pointer. Common instances of this include passing a pointer to a
string (`*string`) or a pointer to an interface value (`*io.Reader`). In both
cases, the value itself is a fixed size and can be passed directly.

This advice does not apply to large structs, or even small structs that may
increase in size. In particular, protocol buffer messages should generally be
handled by pointer rather than by value. The pointer type satisfies the
`proto.Message` interface (accepted by `proto.Marshal`, `protocmp.Transform`,
etc.), and protocol buffer messages can be quite large and often grow larger
over time.

<a id="receiver-type"></a>

### Receiver type

<a id="TOC-ReceiverType"></a>

A [method receiver] can be passed either as a value or a pointer, just as if it
were a regular function parameter. The choice between the two is based on which
[method set(s)] the method should be a part of.

[method receiver]: https://golang.org/ref/spec#Method_declarations
[method set(s)]: https://golang.org/ref/spec#Method_sets

**Correctness wins over speed or simplicity.** There are cases where you must
use a pointer value. In other cases, pick pointers for large types or as
future-proofing if you don't have a good sense of how the code will grow, and
use values for simple [plain old data].

The list below spells out each case in further detail:

*   If the receiver is a slice and the method doesn't reslice or reallocate the
    slice, use a value rather than a pointer.

    ```go
    // Good:
    type Buffer []byte

    func (b Buffer) Len() int { return len(b) }
    ```

*   If the method needs to mutate the receiver, the receiver must be a pointer.

    ```go
    // Good:
    type Counter int

    func (c *Counter) Inc() { *c++ }

    // See https://pkg.go.dev/container/heap.
    type Queue []Item

    func (q *Queue) Push(x Item) { *q = append([]Item{x}, *q...) }
    ```

*   If the receiver is a struct containing fields that
    [cannot safely be copied](#copying), use a pointer receiver. Common examples
    are [`sync.Mutex`] and other synchronization types.

    ```go
    // Good:
    type Counter struct {
        mu    sync.Mutex
        total int
    }

    func (c *Counter) Inc() {
        c.mu.Lock()
        defer c.mu.Unlock()
        c.total++
    }
    ```

    **Tip:** Check the type's [Godoc] for information about whether it is safe
    or unsafe to copy.

*   If the receiver is a "large" struct or array, a pointer receiver may be more
    efficient. Passing a struct is equivalent to passing all of its fields or
    elements as arguments to the method. If that seems too large to
    [pass by value](#pass-values), a pointer is a good choice.

*   For methods that will call or run concurrently with other functions that
    modify the receiver, use a value if those modifications should not be
    visible to your method; otherwise use a pointer.
