<!--* toc_depth: 3 *-->

# Go Style Decisions

https://google.github.io/styleguide/go/decisions

[Overview](index) | [Guide](guide) | [Decisions](decisions) |
[Best practices](best-practices)

<!--

-->

{% raw %}

**Note:** This is part of a series of documents that outline [Go Style](index)
at Google. This document is **[normative](index#normative) but not
[canonical](index#canonical)**, and is subordinate to the
[core style guide](guide). See [the overview](index#about) for more information.

<a id="about"></a>

## About

This document contains style decisions intended to unify and provide standard
guidance, explanations, and examples for the advice given by the Go readability
mentors.

This document is **not exhaustive** and will grow over time. In cases where
[the core style guide](guide) contradicts the advice given here, **the style
guide takes precedence**, and this document should be updated accordingly.

See [the Overview](https://google.github.io/styleguide/go#about) for the full
set of Go Style documents.

The following sections have moved from style decisions to another part of the
guide:

*   **MixedCaps**: see [guide#mixed-caps](guide#mixed-caps)
    <a id="mixed-caps"></a>

*   **Formatting**: see [guide#formatting](guide#formatting)
    <a id="formatting"></a>

*   **Line Length**: see [guide#line-length](guide#line-length)
    <a id="line-length"></a>

<a id="naming"></a>

## Naming

See the naming section within [the core style guide](guide#naming) for
overarching guidance on naming. The following sections provide further
clarification on specific areas within naming.

<a id="underscores"></a>

### Underscores

Names in Go should in general not contain underscores. There are three
exceptions to this principle:

1.  Package names that are only imported by generated code may contain
    underscores. See [package names](#package-names) for more detail around how
    to choose multi-word package names.
1.  Test, Benchmark and Example function names within `*_test.go` files may
    include underscores.
1.  Low-level libraries that interoperate with the operating system or cgo may
    reuse identifiers, as is done in [`syscall`]. This is expected to be very
    rare in most codebases.

**Note:** Filenames of source code are not Go identifiers and do not have to
follow these conventions. They may contain underscores.

[`syscall`]: https://pkg.go.dev/syscall#pkg-constants

<a id="package-names"></a>

### Package names

<a id="TOC-PackageNames"></a>

In Go, package names must be concise and use only lowercase letters and numbers
(e.g., [`k8s`], [`oauth2`]). Multi-word package names should remain unbroken and
in all lowercase (e.g., [`tabwriter`] instead of `tabWriter`, `TabWriter`, or
`tab_writer`).

Avoid selecting package names that are likely to be [shadowed] by commonly used
local variable names. For example, `usercount` is a better package name than
`count`, since `count` is a commonly used variable name.

Go package names should not have underscores. If you need to import a package
that does have one in its name (usually from generated or third party code), it
must be renamed at import time to a name that is suitable for use in Go code.

An exception to this is that package names that are only imported by generated
code may contain underscores. Specific examples include:

*   Using the `_test` suffix for unit tests that only exercise the exported API
    of a package (package `testing` calls these
    ["black box tests"](https://pkg.go.dev/testing)). For example, a package
    `linkedlist` must define its black box unit tests in a package named
    `linkedlist_test` (not `linked_list_test`)

*   Using underscores and the `_test` suffix for packages that specify
    functional or integration tests. For example, a linked list service
    integration test could be named `linked_list_service_test`

*   Using the `_test` suffix for
    [package-level documentation examples](https://go.dev/blog/examples)

[`tabwriter`]: https://pkg.go.dev/text/tabwriter
[`k8s`]: https://pkg.go.dev/k8s.io/client-go/kubernetes
[`oauth2`]: https://pkg.go.dev/golang.org/x/oauth2
[shadowed]: best-practices#shadowing

Avoid uninformative package names like `util`, `utility`, `common`, `helper`,
`model`, `testhelper`, and so on that would tempt users of the package to
[rename it when importing](#import-renaming). See:

*   [Guidance on so-called "utility packages"](best-practices#util-packages)
*   [Go Tip #97: What's in a Name](https://google.github.io/styleguide/go/index.html#gotip)
*   [Go Tip #108: The Power of a Good Package Name](https://google.github.io/styleguide/go/index.html#gotip)

When an imported package is renamed (e.g. `import foopb
"path/to/foo_go_proto"`), the local name for the package must comply with the
rules above, as the local name dictates how the symbols in the package are
referenced in the file. If a given import is renamed in multiple files,
particularly in the same or nearby packages, the same local name should be used
wherever possible for consistency.

<!--#include file="/go/g3doc/style/includes/special-name-exception.md"-->

See also: [Go blog post about package names](https://go.dev/blog/package-names).

<a id="receiver-names"></a>

### Receiver names

<a id="TOC-ReceiverNames"></a>

[Receiver] variable names must be:

*   Short (usually one or two letters in length)
*   Abbreviations for the type itself
*   Applied consistently to every receiver for that type
*   Not an underscore; omit the name if it is unused

Long Name                   | Better Name
--------------------------- | -------------------------
`func (tray Tray)`          | `func (t Tray)`
`func (info *ResearchInfo)` | `func (ri *ResearchInfo)`
`func (this *ReportWriter)` | `func (w *ReportWriter)`
`func (self *Scanner)`      | `func (s *Scanner)`

[Receiver]: https://golang.org/ref/spec#Method_declarations

<a id="constant-names"></a>

### Constant names

Constant names must use [MixedCaps] like all other names in Go. ([Exported]
constants start with uppercase, while unexported constants start with
lowercase.) This applies even when it breaks conventions in other languages.
Constant names should not be a derivative of their values and should instead
explain what the value denotes.

```go
// Good:
const MaxPacketSize = 512

const (
    ExecuteBit = 1 << iota
    WriteBit
    ReadBit
)
```

[MixedCaps]: guide#mixed-caps
[Exported]: https://tour.golang.org/basics/3

Do not use non-MixedCaps constant names or constants with a `K` prefix.

```go
// Bad:
const MAX_PACKET_SIZE = 512
const kMaxBufferSize = 1024
const KMaxUsersPergroup = 500
```

Name constants based on their role, not their values. If a constant does not
have a role apart from its value, then it is unnecessary to define it as a
constant.

```go
// Bad:
const Twelve = 12

const (
    UserNameColumn = "username"
    GroupColumn    = "group"
)
```

<!--#include file="/go/g3doc/style/includes/special-name-exception.md"-->

<a id="initialisms"></a>

### Initialisms

<a id="TOC-Initialisms"></a>

Words in names that are initialisms or acronyms (e.g., `URL` and `NATO`) should
have the same case. `URL` should appear as `URL` or `url` (as in `urlPony`, or
`URLPony`), never as `Url`. As a general rule, identifiers (e.g., `ID` and `DB`)
should also be capitalized similar to their usage in English prose.

*   In names with multiple initialisms (e.g. `XMLAPI` because it contains `XML`
    and `API`), each letter within a given initialism should have the same case,
    but each initialism in the name does not need to have the same case.
*   In names with an initialism containing a lowercase letter (e.g. `DDoS`,
    `iOS`, `gRPC`), the initialism should appear as it would in standard prose,
    unless you need to change the first letter for the sake of [exportedness].
    In these cases, the entire initialism should be the same case (e.g. `ddos`,
    `IOS`, `GRPC`).

[exportedness]: https://golang.org/ref/spec#Exported_identifiers

<!-- Keep this table narrow. If it must grow wider, replace with a list. -->

English Usage | Scope      | Correct  | Incorrect
------------- | ---------- | -------- | --------------------------------------
XML API       | Exported   | `XMLAPI` | `XmlApi`, `XMLApi`, `XmlAPI`, `XMLapi`
XML API       | Unexported | `xmlAPI` | `xmlapi`, `xmlApi`
iOS           | Exported   | `IOS`    | `Ios`, `IoS`
iOS           | Unexported | `iOS`    | `ios`
gRPC          | Exported   | `GRPC`   | `Grpc`
gRPC          | Unexported | `gRPC`   | `grpc`
DDoS          | Exported   | `DDoS`   | `DDOS`, `Ddos`
DDoS          | Unexported | `ddos`   | `dDoS`, `dDOS`
ID            | Exported   | `ID`     | `Id`
ID            | Unexported | `id`     | `iD`
DB            | Exported   | `DB`     | `Db`
DB            | Unexported | `db`     | `dB`
Txn           | Exported   | `Txn`    | `TXN`

<!--#include file="/go/g3doc/style/includes/special-name-exception.md"-->

<a id="getters"></a>

### Getters

<a id="TOC-Getters"></a>

Function and method names should not use a `Get` or `get` prefix, unless the
underlying concept uses the word "get" (e.g. an HTTP GET). Prefer starting the
name with the noun directly, for example use `Counts` over `GetCounts`.

If the function involves performing a complex computation or executing a remote
call, a different word like `Compute` or `Fetch` can be used in place of `Get`,
to make it clear to a reader that the function call may take time and could
block or fail.

<!--#include file="/go/g3doc/style/includes/special-name-exception.md"-->

<a id="variable-names"></a>

### Variable names

<a id="TOC-VariableNames"></a>

The general rule of thumb is that the length of a name should be proportional to
the size of its scope and inversely proportional to the number of times that it
is used within that scope. A variable created at file scope may require multiple
words, whereas a variable scoped to a single inner block may be a single word or
even just a character or two, to keep the code clear and avoid extraneous
information.

Here is a rough baseline. These numeric guidelines are not strict rules. Apply
judgement based on context, [clarity], and [concision].

*   A small scope is one in which one or two small operations are performed, say
    1-7 lines.
*   A medium scope is a few small or one large operation, say 8-15 lines.
*   A large scope is one or a few large operations, say 15-25 lines.
*   A very large scope is anything that spans more than a page (say, more than
    25 lines).

[clarity]: guide#clarity
[concision]: guide#concision

A name that might be perfectly clear (e.g., `c` for a counter) within a small
scope could be insufficient in a larger scope and would require clarification to
remind the reader of its purpose further along in the code. A scope in which
there are many variables, or variables that represent similar values or
concepts, may necessitate longer variable names than the scope suggests.

The specificity of the concept can also help to keep a variable's name concise.
For example, assuming there is only a single database in use, a short variable
name like `db` that might normally be reserved for very small scopes may remain
perfectly clear even if the scope is very large. In this case, a single word
`database` is likely acceptable based on the size of the scope, but is not
required as `db` is a very common shortening for the word with few alternate
interpretations.

The name of a local variable should reflect what it contains and how it is being
used in the current context, rather than where the value originated. For
example, it is often the case that the best local variable name is not the same
as the struct or protocol buffer field name.

In general:

*   Single-word names like `count` or `options` are a good starting point.
*   Additional words can be added to disambiguate similar names, for example
    `userCount` and `projectCount`.
*   Do not simply drop letters to save typing. For example `Sandbox` is
    preferred over `Sbx`, particularly for exported names.
*   Omit [types and type-like words] from most variable names.
    *   For a number, `userCount` is a better name than `numUsers` or
        `usersInt`.
    *   For a slice, `users` is a better name than `userSlice`.
    *   It is acceptable to include a type-like qualifier if there are two
        versions of a value in scope, for example you might have an input stored
        in `ageString` and use `age` for the parsed value.
*   Omit words that are clear from the [surrounding context]. For example, in
    the implementation of a `UserCount` method, a local variable called
    `userCount` is probably redundant; `count`, `users`, or even `c` are just as
    readable.

[types and type-like words]: #repetitive-with-type
[surrounding context]: #repetitive-in-context

<a id="v"></a>

#### Single-letter variable names

Single-letter variable names can be a useful tool to minimize
[repetition](#repetition), but can also make code needlessly opaque. Limit their
use to instances where the full word is obvious and where it would be repetitive
for it to appear in place of the single-letter variable.

In general:

*   For a [method receiver variable], a one-letter or two-letter name is
    preferred.
*   Using familiar variable names for common types is often helpful:
    *   `r` for an `io.Reader` or `*http.Request`
    *   `w` for an `io.Writer` or `http.ResponseWriter`
*   Single-letter identifiers are acceptable as integer loop variables,
    particularly for indices (e.g., `i`) and coordinates (e.g., `x` and `y`).
*   Abbreviations can be acceptable loop identifiers when the scope is short,
    for example `for _, n := range nodes { ... }`.

[method receiver variable]: #receiver-names

<a id="repetition"></a>

### Repetition

<!--
Note to future editors:

Do not use the term "stutter" to refer to cases when a name is repetitive.
-->

A piece of Go source code should avoid unnecessary repetition. One common source
of this is repetitive names, which often include unnecessary words or repeat
their context or type. Code itself can also be unnecessarily repetitive if the
same or a similar code segment appears multiple times in close proximity.

Repetitive naming can come in many forms, including:

<a id="repetitive-with-package"></a>

#### Package vs. exported symbol name

When naming exported symbols, the name of the package is always visible outside
your package, so redundant information between the two should be reduced or
eliminated. If a package exports only one type and it is named after the package
itself, the canonical name for the constructor is `New` if one is required.

> **Examples:** Repetitive Name -> Better Name
>
> *   `widget.NewWidget` -> `widget.New`
> *   `widget.NewWidgetWithName` -> `widget.NewWithName`
> *   `db.LoadFromDatabase` -> `db.Load`
> *   `goatteleportutil.CountGoatsTeleported` -> `gtutil.CountGoatsTeleported`
>     or `goatteleport.Count`
> *   `myteampb.MyTeamMethodRequest` -> `mtpb.MyTeamMethodRequest` or
>     `myteampb.MethodRequest`

<a id="repetitive-with-type"></a>

#### Variable name vs. type

The compiler always knows the type of a variable, and in most cases it is also
clear to the reader what type a variable is by how it is used. It is only
necessary to clarify the type of a variable if its value appears twice in the
same scope.

