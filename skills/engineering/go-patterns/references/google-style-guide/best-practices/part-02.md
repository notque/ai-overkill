    if got, want := spyCC.Charges, charges; !cmp.Equal(got, want) {
        t.Errorf("spyCC.Charges = %v, want %v", got, want)
    }
}
```

This is clearer than when the name is not prefixed.

```go
// Bad:
package payment

import "path/to/creditcardtest"

func TestProcessor(t *testing.T) {
    var cc creditcardtest.Spy

    proc := &Processor{CC: cc}

    // declarations omitted: card and amount
    if err := proc.Process(card, amount); err != nil {
        t.Errorf("proc.Process(card, amount) = %v, want nil", err)
    }

    charges := []creditcardtest.Charge{
        {Card: card, Amount: amount},
    }

    if got, want := cc.Charges, charges; !cmp.Equal(got, want) {
        t.Errorf("cc.Charges = %v, want %v", got, want)
    }
}
```

<a id="shadowing"></a>

### Shadowing

**Note:** This explanation uses two informal terms, *stomping* and *shadowing*.
They are not official concepts in the Go language spec.

Like many programming languages, Go has mutable variables: assigning to a
variable changes its value.

```go
// Good:
func abs(i int) int {
    if i < 0 {
        i *= -1
    }
    return i
}
```

When using [short variable declarations] with the `:=` operator, in some cases a
new variable is not created. We can call this *stomping*. It's OK to do this
when the original value is no longer needed.

```go
// Good:
// innerHandler is a helper for some request handler, which itself issues
// requests to other backends.
func (s *Server) innerHandler(ctx context.Context, req *pb.MyRequest) *pb.MyResponse {
    // Unconditionally cap the deadline for this part of request handling.
    ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
    defer cancel()
    ctxlog.Info(ctx, "Capped deadline in inner request")

    // Code here no longer has access to the original context.
    // This is good style if when first writing this, you anticipate
    // that even as the code grows, no operation legitimately should
    // use the (possibly unbounded) original context that the caller provided.

    // ...
}
```

Be careful using short variable declarations in a new scope, though: that
introduces a new variable. We can call this *shadowing* the original variable.
Code after the end of the block refers to the original. Here is a buggy attempt
to shorten the deadline conditionally:

```go
// Bad:
func (s *Server) innerHandler(ctx context.Context, req *pb.MyRequest) *pb.MyResponse {
    // Attempt to conditionally cap the deadline.
    if *shortenDeadlines {
        ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
        defer cancel()
        ctxlog.Info(ctx, "Capped deadline in inner request")
    }

    // BUG: "ctx" here again means the context that the caller provided.
    // The above buggy code compiled because both ctx and cancel
    // were used inside the if statement.

    // ...
}
```

A correct version of the code might be:

```go
// Good:
func (s *Server) innerHandler(ctx context.Context, req *pb.MyRequest) *pb.MyResponse {
    if *shortenDeadlines {
        var cancel func()
        // Note the use of simple assignment, = and not :=.
        ctx, cancel = context.WithTimeout(ctx, 3*time.Second)
        defer cancel()
        ctxlog.Info(ctx, "Capped deadline in inner request")
    }
    // ...
}
```

In the case we called stomping, because there's no new variable, the type being
assigned must match that of the original variable. With shadowing, an entirely
new entity is introduced so it can have a different type. Intentional shadowing
can be a useful practice, but you can always use a new name if it improves
[clarity](guide#clarity).

It is not a good idea to use variables with the same name as standard packages
other than very small scopes, because that renders free functions and values
from that package inaccessible. Conversely, when picking a name for your
package, avoid names that are likely to require
[import renaming](decisions#import-renaming) or cause shadowing of otherwise
good variable names at the client side.

```go
// Bad:
func LongFunction() {
    url := "https://example.com/"
    // Oops, now we can't use net/url in code below.
}
```

[short variable declarations]: https://go.dev/ref/spec#Short_variable_declarations

<a id="util-packages"></a>

### Util packages

Go packages have a name specified on the `package` declaration, separate from
the import path. The package name matters more for readability than the path.

Go package names should be
[related to what the package provides](decisions#package-names). Naming a
package just `util`, `helper`, `common` or similar is usually a poor choice (it
can be used as *part* of the name though). Uninformative names make the code
harder to read, and if used too broadly they are liable to cause needless
[import conflicts](decisions#import-renaming).

Instead, consider what the callsite will look like.

```go
// Good:
db := spannertest.NewDatabaseFromFile(...)

_, err := f.Seek(0, io.SeekStart)

b := elliptic.Marshal(curve, x, y)
```

You can tell roughly what each of these do even without knowing the imports list
(`cloud.google.com/go/spanner/spannertest`, `io`, and `crypto/elliptic`). With
less focused names, these might read:

```go
// Bad:
db := test.NewDatabaseFromFile(...)

_, err := f.Seek(0, common.SeekStart)

b := helper.Marshal(curve, x, y)
```

<a id="package-size"></a>

## Package size

If you're asking yourself how big your Go packages should be and whether to
place related types in the same package or split them into different ones, a
good place to start is the [Go blog post about package names][blog-pkg-names].
Despite the post title, it's not solely about naming. It contains some helpful
hints and cites several useful articles and talks.

Here are some other considerations and notes.

Users see [godoc] for the package in one page, and any methods exported by types
supplied by the package are grouped by their type. Godoc also group constructors
along with the types they return. If *client code* is likely to need two values
of different type to interact with each other, it may be convenient for the user
to have them in the same package.

Code within a package can access unexported identifiers in the package. If you
have a few related types whose *implementation* is tightly coupled, placing them
in the same package lets you achieve this coupling without polluting the public
API with these details. A good test for this coupling is to imagine a
hypothetical user of two packages, where the packages cover closely related
topics: if the user must import both packages in order to use either in any
meaningful way, combining them together is usually the right thing to do. The
standard library generally demonstrates this kind of scoping and layering well.

All of that being said, putting your entire project in a single package would
likely make that package too large. When something is conceptually distinct,
giving it its own small package can make it easier to use. The short name of the
package as known to clients together with the exported type name work together
to make a meaningful identifier: e.g. `bytes.Buffer`, `ring.New`. The
[Package Names blog post][blog-pkg-names] has more examples.

Go style is flexible about file size, because maintainers can move code within a
package from one file to another without affecting callers. But as a general
guideline: it is usually not a good idea to have a single file with many
thousands of lines in it, or having many tiny files. There is no "one type, one
file" convention as in some other languages. As a rule of thumb, files should be
focused enough that a maintainer can tell which file contains something, and the
files should be small enough that it will be easy to find once there. The
standard library often splits large packages to several source files, grouping
related code by file. The source for [package `bytes`] is a good example.
Packages with long package documentation may choose to dedicate one file called
`doc.go` that has the [package documentation](decisions#package-comments), a
package declaration, and nothing else, but this is not required.

Within the Google codebase and in projects using Bazel, directory layout for Go
code is different than it is in open source Go projects: you can have multiple
`go_library` targets in a single directory. A good reason to give each package
its own directory is if you expect to open source your project in the future.

A few non-canonical reference examples to help demonstrate these ideas in
action:

*   small packages that contain one cohesive idea that warrant nothing more
    being added nor nothing being removed:

    *   [package `csv`][package `csv`]: CSV data encoding and decoding with
        responsibility split respectively between [reader.go] and [writer.go].
    *   [package `expvar`][package `expvar`]: whitebox program telemetry all
        contained in [expvar.go].

*   moderately sized packages that contain one large domain and its multiple
    responsibilities together:

    *   [package `flag`][package `flag`]: command line flag management all
        contained in [flag.go].

*   large packages that divide several closely related domains across several
    files:

    *   [package `http`][package `http`]: the core of HTTP:
        [client.go][http-client], support for HTTP clients;
        [server.go][http-client], support for HTTP servers; [cookie.go], cookie
        management.
    *   [package `os`][package `os`]: cross-platform operating system
        abstractions: [exec.go], subprocess management; [file.go], file
        management; [tempfile.go], temporary files.

See also:

*   [Test double packages](#naming-doubles)
*   [Organizing Go Code (Blog Post)]
*   [Organizing Go Code (Presentation)]

[blog-pkg-names]: https://go.dev/blog/package-names
[package `bytes`]: https://go.dev/src/bytes/
[Organizing Go Code (Blog Post)]: https://go.dev/blog/organizing-go-code
[Organizing Go Code (Presentation)]: https://go.dev/talks/2014/organizeio.slide
[package `csv`]: https://pkg.go.dev/encoding/csv
[reader.go]: https://go.googlesource.com/go/+/refs/heads/master/src/encoding/csv/reader.go
[writer.go]: https://go.googlesource.com/go/+/refs/heads/master/src/encoding/csv/writer.go
[package `expvar`]: https://pkg.go.dev/expvar
[expvar.go]: https://go.googlesource.com/go/+/refs/heads/master/src/expvar/expvar.go
[package `flag`]: https://pkg.go.dev/flag
[flag.go]: https://go.googlesource.com/go/+/refs/heads/master/src/flag/flag.go
[godoc]: https://pkg.go.dev/
[package `http`]: https://pkg.go.dev/net/http
[http-client]: https://go.googlesource.com/go/+/refs/heads/master/src/net/http/client.go
[http-server]: https://go.googlesource.com/go/+/refs/heads/master/src/net/http/server.go
[cookie.go]: https://go.googlesource.com/go/+/refs/heads/master/src/net/http/cookie.go
[package `os`]: https://pkg.go.dev/os
[exec.go]: https://go.googlesource.com/go/+/refs/heads/master/src/os/exec.go
[file.go]: https://go.googlesource.com/go/+/refs/heads/master/src/os/file.go
[tempfile.go]: https://go.googlesource.com/go/+/refs/heads/master/src/os/tempfile.go

<a id="imports"></a>

## Imports

<a id="import-protos"></a>

### Protocol Buffer Messages and Stubs

Proto library imports are treated differently than standard Go imports due to
their cross-language nature. The convention for renamed proto imports are based
on the rule that generated the package:

*   The `pb` suffix is generally used for `go_proto_library` rules.
*   The `grpc` suffix is generally used for `go_grpc_library` rules.

Often a single word describing the package is used:

```go
// Good:
import (
    foopb "path/to/package/foo_service_go_proto"
    foogrpc "path/to/package/foo_service_go_grpc"
)
```

Follow the style guidance for
[package names](https://google.github.io/styleguide/go/decisions#package-names).
Prefer whole words. Short names are good, but avoid ambiguity. When in doubt,
use the proto package name up to _go with a pb suffix:

```go
// Good:
import (
    pushqueueservicepb "path/to/package/push_queue_service_go_proto"
)
```

**Note:** Previous guidance encouraged very short names such as "xpb" or even
just "pb". New code should prefer more descriptive names. Existing code which
uses short names should not be used as an example, but does not need to be
changed.

<a id="import-order"></a>

### Import ordering

See the [Go Style Decisions: Import grouping](decisions.md#import-grouping).

<a id="error-handling"></a>

## Error handling

In Go, [errors are values]; they are created by code and consumed by code.
Errors can be:

*   Converted into diagnostic information for display to humans
*   Used by the maintainer
*   Interpreted by an end user

Error messages also show up across a variety of different surfaces including log
messages, error dumps, and rendered UIs.

Code that processes (produces or consumes) errors should do so deliberately. It
can be tempting to ignore or blindly propagate an error return value. However,
it is always worth considering whether the current function in the call frame is
positioned to handle the error most effectively. This is a large topic and it is
hard to give categorical advice. Use your judgment, but keep the following
considerations in mind:

*   When creating an error value, decide whether to give it any
    [structure](#error-structure).
*   When handling an error, consider [adding information](#error-extra-info)
    that you have but that the caller and/or callee might not.
*   See also guidance on [error logging](#error-logging).

While it is usually not appropriate to ignore an error, a reasonable exception
to this is when orchestrating related operations, where often only the first
error is useful. Package [`errgroup`] provides a convenient abstraction for a
group of operations that can all fail or be canceled as a group.

[errors are values]: https://go.dev/blog/errors-are-values
[`errgroup`]: https://pkg.go.dev/golang.org/x/sync/errgroup

See also:

*   [Effective Go on errors](https://go.dev/doc/effective_go#errors)
*   [A post by the Go Blog on errors](https://go.dev/blog/go1.13-errors)
*   [Package `errors`](https://pkg.go.dev/errors)
*   [Package `upspin.io/errors`](https://commandcenter.blogspot.com/2017/12/error-handling-in-upspin.html)
*   [GoTip #89: When to Use Canonical Status Codes as Errors](https://google.github.io/styleguide/go/index.html#gotip)
*   [GoTip #48: Error Sentinel Values](https://google.github.io/styleguide/go/index.html#gotip)
*   [GoTip #13: Designing Errors for Checking](https://google.github.io/styleguide/go/index.html#gotip)

<a id="error-structure"></a>

### Error structure

If callers need to interrogate the error (e.g., distinguish different error
conditions), give the error value structure so that this can be done
programmatically rather than having the caller perform string matching. This
advice applies to production code as well as to tests that care about different
error conditions.

The simplest structured errors are unparameterized global values.

```go
type Animal string

var (
    // ErrDuplicate occurs if this animal has already been seen.
    ErrDuplicate = errors.New("duplicate")

    // ErrMarsupial occurs because we're allergic to marsupials outside Australia.
    // Sorry.
    ErrMarsupial = errors.New("marsupials are not supported")
)
