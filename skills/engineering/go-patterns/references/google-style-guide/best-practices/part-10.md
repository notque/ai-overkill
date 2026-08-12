[`image.RegisterFormat`](https://pkg.go.dev/image#RegisterFormat) function.
Consider the litmus tests from above applied to a typical decoder, like the one
for handling the [PNG](https://pkg.go.dev/image/png) format:

*   Multiple calls to `package image`'s APIs that use the registered decoders
    (for example, `image.Decode`) cannot interfere with one another, similarly
    for tests. The only exception is `image.RegisterFormat`, but that is
    mitigated by the points below.
*   It is extremely unlikely that a user would want to replace a decoder with a
    [test double], as the PNG decoder exemplifies a case in which our codebase's
    preference for real objects applies. However, a user would be more likely to
    replace a decoder with a test double if the decoder statefully interacted
    with operating system resources (for example, the network).
*   Collisions in registration are conceivable, though they are probably rare in
    practice.
*   The decoders are stateless, idempotent, and pure.

<a id="globals-default-instance"></a>

### Providing a default instance

While not recommended, it is acceptable to provide a simplified API that uses
package level state if you need to maximize convenience for the user.

Follow the [litmus tests](#globals-litmus-tests) with these guidelines in such
cases:

1.  The package must offer clients the ability to create isolated instances of
    package types as [described above](#globals-forms).
2.  The public APIs that use global state must be a thin proxy to the previous
    API. A good example of this is
    [`http.Handle`](https://pkg.go.dev/net/http#Handle) internally calling
    [`(*http.ServeMux).Handle`](https://pkg.go.dev/net/http#ServeMux.Handle) on
    the package variable
    [`http.DefaultServeMux`](https://pkg.go.dev/net/http#DefaultServeMux).
3.  This package-level API must only be used by [binary build targets], not
    [libraries], unless the libraries are undertaking a refactoring to support
    dependency passing. Infrastructure libraries that can be imported by other
    packages must not rely on package-level state of the packages they import.

    For example, an infrastructure provider implementing a sidecar that is to be
    shared with other teams using the API from the top should offer an API to
    accommodate this:

    ```go
    // Good:
    package cloudlogger

    func New() *Logger { ... }

    func Register(r *sidecar.Registry, l *Logger) {
      r.Register("Cloud Logging", l)
    }
    ```

4.  This package-level API must [document](#documentation-conventions) and
    enforce its invariants (for example, at which stage in the program's life it
    can be called, whether it can be used concurrently). Further, it must
    provide an API to reset global state to a known-good default (for example,
    to facilitate testing).

[binary build targets]: https://github.com/bazelbuild/rules_go/blob/master/docs/go/core/rules.md#go_binary
[libraries]: https://github.com/bazelbuild/rules_go/blob/master/docs/go/core/rules.md#go_library

See also:

*   [Go Tip #36: Enclosing Package-Level State](https://google.github.io/styleguide/go/index.html#gotip)
*   [Go Tip #80: Dependency Injection Principles](https://google.github.io/styleguide/go/index.html#gotip)

<a id="interfaces"></a>

## Interfaces

Interfaces in Go are powerful but can be overused or misunderstood. Because Go
interfaces are satisfied implicitly, they are a structural tool rather than a
declarative one. The following guidance provides the best practices for how to
design and return interfaces in Go without over-engineering your codebase.

Refer to [Decisions' section on interfaces](decisions#interfaces) for a summary.

<a id="avoid-unnecessary-interfaces"></a>

### Avoid unnecessary interfaces

The most common mistake is creating an interface before a
[real need](guide#simplicity) exists.

1.  **Don’t confuse the concept with the keyword:** Just because you are
    designing a "service" or a "repository" or similar pattern doesn't mean you
    need a named interface type (e.g., `type Service interface`). Focus on the
    behavior and its concrete implementation first.

2.  **Reuse existing interfaces:** If an interface already exists, especially in
    generated code, like a RPC client or server, use it ([testing RPC]). Do not
    wrap a generated RPC code in a new, manual interface just for the sake of
    abstraction or testing. [Use real transports](#use-real-transports) instead.

3.  **Don't define back doors only for tests:** Do not export a [test double]
    implementation of an interface from an API that consumes it. Instead, prefer
    to design the API so that it can be tested using the [public API] of the
    real implementation.

    Every exported type increases the cognitive load for the reader. When you
    export a test double alongside the real implementation, you force the reader
    to understand three entities (the interface, the real implementation, and
    the test double) instead of one.

    Export an interface for a test double when you have a
    [material need](guide#least-mechanism) to support substitution.

When it does make sense to create an interface:

1.  **Multiple implementations:** When there are two or more concrete types that
    must be handled by the same logic (e.g., something that operates with both
    [json.Encoder](https://pkg.go.dev/encoding/json#Encoder) and
    [gob.GobEncoder](https://pkg.go.dev/encoding/gob#GobEncoder)), the API
    consumer could define an interface.

2.  **Decoupling packages:** To break circular dependencies between two packages
    (see an [example](#avoiding-circular-dependencies)), an API producer could
    define an interface.

    **Caution:** Carefully observe guidance on [Package Size](#package-size).
    Introducing interfaces to break dependency cycles is often a signal of
    improperly structured packages.

3.  **Hiding complexity:** When a concrete type has a massive API surface, but a
    specific function only needs one or two methods, an API consumer may define
    an interface.

<a id="interface-ownership-and-visibility"></a>

### Interface ownership and visibility

1.  **Do not export interface types unnecessarily:** If an interface is only
    used internally within a package to satisfy a specific logic flow, keep the
    interface unexported. Exporting an interface commits you to maintaining that
    API for external callers.

2.  **The consumer defines the interface:** In Go, interfaces generally belong
    in the package that uses them, not the package that implements them. The
    consumer should define only the methods they actually use
    [GoTip #78: Minimal Viable Interfaces], adhering to the idea that
    [the bigger the interface, the weaker the abstraction](https://go-proverbs.github.io/).

    There are common scenarios where it often makes sense for the producer (the
    package providing the logic) to export the interface:

    *   **The interface is the product:** When a package’s primary purpose is to
        provide a common protocol that many different implementations must
        follow, the producer defines the interface. For example,
        [io.Writer](https://pkg.go.dev/io#Writer),
        [hash.Hash](https://pkg.go.dev/hash#Hash). The concept of "protocol"
        includes aspects like [documentation](#documentation) about critical
        behaviors (e.g., expected use case, edge cases, concurrency) that need
        to be centrally and canonically explicated. Another prominent example of
        this is generated interfaces from protobuf. It doesn't abstract a
        specific behavior, it defines a boundary. Its purpose is to ensure that
        your server implementation exactly matches the schema defined in the
        `.proto` file. Here, the interface serves as a rigid legal contract
        between the service and its clients.

        For large systems, if the interface lives inside a huge implementation
        package, every client is forced to import the entire world just to
        reference the interface. You may define the interface in a standalone,
        implementation-free package, avoiding unnecessary symbols and potential
        circular dependencies. This is also the same philosophy used by
        generated code from protobuf.

    *   **Prevent interface bloat:** In large codebases, maintenance becomes
        difficult if numerous packages utilize the same `AuthService` while each
        defining an identical `type Authorizer interface`. While Go often favors
        [a little copying over a little dependency](https://go-proverbs.github.io/),
        keep in mind that maintaining perfectly mirrored interfaces (see point
        above) across many packages can create an unnecessary burden.

    *   **Resolve circular dependency:** see
        [an example](#avoiding-circular-dependencies) below.

<a id="designing-effective-interfaces"></a>

### Designing effective interfaces

1.  **Keep interfaces small:** The larger the interface,
    [the harder it is to implement and to write code that takes advantage of it](https://go-proverbs.github.io/).
    Small interfaces are easier to compose into larger ones if needed.

2.  **Documentation:** Treat every interface as the "user manual" for your
    abstraction. The depth of your documentation should be proportional to the
    interface's cognitive load, not just the count of its methods. Whether an
    interface has ten methods or a single `Write` of
    [io.Writer](https://pkg.go.dev/io#Writer), if a programmer is expected to
    interact with that type, the API must be documented thoroughly.

    *   **Single-method interfaces:** documentation on the type itself is
        usually sufficient (e.g., io.Writer). Explain its contract, edge cases,
        and expected errors.
    *   **Multi-method interfaces:** each individual method requires its own
        documentation.
    *   **Unexported interfaces:** consider documenting them anyway. They are
        often the glue that holds complex internal logic together, and because
        they are invisible to external users, they can easily become mystery
        code for future maintainers (including your future self).

3.  **Accept interfaces, return concrete types:** Returning a concrete type
    allows the caller to use the full functionality of the value without being
    locked into a specific interface abstraction
    [GoTip #49: Accept Interfaces, Return Concrete Types].

There are several common scenarios where returning an interface is the idiomatic
choice:

1.  **Encapsulation:** While interfaces cannot strictly hide exported methods
    (as they remain accessible via type assertions), returning an interface is a
    powerful tool for limiting the default API surface and guiding the caller's
    behavior.. The most common example is the `error` interface; you
    [almost never return a concrete error type](decisions#errors) like
    `*MyCustomError`.

    Consider a `ThrottledReader` that implements `io.Reader` but also has a
    `Refill` method for internal bucket management. Returning the concrete
    `*ThrottledReader` invites the caller to manage the bucket manually, which
    could lead to race conditions or broken rate-limiting logic. By returning an
    interface, you tell the caller that your only job is to consume this reader.
    If you try to cast this back to a `ThrottledReader` to `Refill` the internal
    bucket, you are breaking the contract.

    ```go
    // Good:
    type ThrottledReader struct {
        source     io.Reader
        limit      int  // bytes per second
        balance    int  // current allowance of bytes
        lastRefill time.Time
    }

    // Read implements the io.Reader interface with rate-limiting logic.
    func (t *ThrottledReader) Read(p []byte) (int, error) { ... }

    // Refill manually adds tokens to the bucket.
    // INTERNAL USE ONLY: Calling this from outside breaks the rate limit logic.
    func (t *ThrottledReader) Refill(amount int) {
        t.balance = min(t.balance + amount, t.limit)
    }

    // New returns the io.Reader with rate-limiting.
    func New(r io.Reader, bytesPerSec int) io.Reader {
        return &ThrottledReader{
            source:     r,
            limit:      bytesPerSec,
            balance:    bytesPerSec, // start with a full bucket
            lastRefill: time.Now(),
        }
    }
    ```

    This raises a natural question: if `Refill` is dangerous, why export it at
    all? In complex systems, you often need internal orchestration. For example,
    an `AggregateReader` manages multiple `ThrottledReader` values to ensure
    total bandwidth across all streams stays under a global limit. This
    coordinator needs to call Refill to distribute tokens, but the non-power
    user processing the data should never see that capability.

    **Caution:** Before returning an interface to hide implementation, ask:
    "Would a user calling these extra methods actually break the system's
    integrity or meaningfully limit maintainability?" If the extra details allow
    the user to bypass safety checks, or if exposing the concrete type makes it
    impossible to change the underlying provider later without a breaking
    change, you may return an interface. Do not rotely encapsulate without
    reason.

2.  **Certain patterns:** If a function is designed to return one of several
    different concrete types based on decisions made at runtime, it must return
    an interface. This is commonly true with command, chaining, factory, and
    [strategy](https://en.wikipedia.org/wiki/Strategy_pattern) patterns.
    Consider this code that selects which encoder to use based the requested
    format:

    ```go
    // Good:
    func NewWriter(format string) io.Writer {
        switch format {
        case "json":
            return &jsonWriter{}
        case "xml":
            return &xmlWriter{}
        default:
            return &textWriter{}
        }
    }
    ```

    The following example of a chaining API demonstrates how returning an
    interface enables polymorphic behavior. By allowing callers to use either
    `client.Do(req)` or `client.WithAuth("token").Do(req)`, you can swap
    implementations without breaking the calling code.

    ```go
    // Good:
    type Client interface {
        WithAuth(token string) Client
        Do(req *Request) error
    }
    ```

    These patterns are guidelines, not rules. Avoid forcing an interface if a
    single, robust concrete type can handle the abstraction internally. For
    example, the standard [database/sql](https://pkg.go.dev/database/sql#DB)
    library exports a single concrete `DB` type instead of forcing an interface
    to handle types like `MySQLDB` and `OracleDB`.

3.  <span id="avoiding-circular-dependencies">**Avoiding circular
    dependencies:**</span> If returning a concrete type would require importing
    a package that already imports your current package, you must return an
    interface to break the circular dependency.

    For example:

    ```go
    // Bad:
    package app

    import "myproject/plugin"

    type Config struct {
        APIKey string
    }

    func Start() {
        p := plugin.New()
    }
    ```

    ```go
    // Bad:
    package plugin

    import "myproject/app"  // ERROR: Import cycle!

    func New() *app.Config {
        return &app.Config{APIKey: "secret"}
    }
    ```

    In this case, `plugin`'s `New` cannot return `*app.Config` because it would
    create a circular import. To break this, we use the fact that interfaces are
    satisfied implicitly. We move the "contract" to a neutral place or have the
    producer return an interface that the consumer already understands.

    If `plugin`'s `New` returns an interface instead of the concrete
    `*app.Config` struct, it no longer needs to import package `app`.

    ```go
    package plugin

    type Configurer interface {
        APIKey() string
    }

    type localConfig struct {
        key string
    }

    func (c localConfig) APIKey() string { return c.key }

    // New returns the interface Configurer instead of the concrete app.Config
    func New() Configurer {
        return &localConfig{key: "secret"}
    }
    ```

    ```go
    package app

    import "myproject/plugin"

    func Start() {
        conf := plugin.New()  // 'conf' is now a Configurer interface
        fmt.Println(conf.APIKey())
    }
    ```

    **Caution:** Carefully observe guidance on [Package Size](#package-size).
    Introducing interfaces to break dependency cycles is often a signal of
    improperly structured packages. Consolidated packages are often preferred
    over too many too small packages that fail to stand on their own.

[GoTip #78: Minimal Viable Interfaces]: https://google.github.io/styleguide/go/index.html#gotip
[GoTip #49: Accept Interfaces, Return Concrete Types]: https://google.github.io/styleguide/go/index.html#gotip
[testing RPC]: https://codelabs.developers.google.com/grpc/getting-started-grpc-go#3
[test double]: https://abseil.io/resources/swe-book/html/ch13.html
[public API]: https://abseil.io/resources/swe-book/html/ch12.html#test_via_public_apis
