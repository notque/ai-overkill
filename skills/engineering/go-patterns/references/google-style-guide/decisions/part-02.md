Repetitive Name               | Better Name
----------------------------- | ----------------------
`var numUsers int`            | `var users int`
`var nameString string`       | `var name string`
`var primaryProject *Project` | `var primary *Project`

If the value appears in multiple forms, this can be clarified either with an
extra word like `raw` and `parsed` or with the underlying representation:

```go
// Good:
limitRaw := r.FormValue("limit")
limit, err := strconv.Atoi(limitRaw)
```

```go
// Good:
limitStr := r.FormValue("limit")
limit, err := strconv.Atoi(limitStr)
```

<a id="repetitive-in-context"></a>

#### External context vs. local names

Names that include information from their surrounding context often create extra
noise without benefit. The package name, method name, type name, function name,
import path, and even filename can all provide context that automatically
qualifies all names within.

```go
// Bad:
// In package "ads/targeting/revenue/reporting"
type AdsTargetingRevenueReport struct{}

func (p *Project) ProjectName() string
```

```go
// Good:
// In package "ads/targeting/revenue/reporting"
type Report struct{}

func (p *Project) Name() string
```

```go
// Bad:
// In package "sqldb"
type DBConnection struct{}
```

```go
// Good:
// In package "sqldb"
type Connection struct{}
```

```go
// Bad:
// In package "ads/targeting"
func Process(in *pb.FooProto) *Report {
    adsTargetingID := in.GetAdsTargetingID()
}
```

```go
// Good:
// In package "ads/targeting"
func Process(in *pb.FooProto) *Report {
    id := in.GetAdsTargetingID()
}
```

Repetition should generally be evaluated in the context of the user of the
symbol, rather than in isolation. For example, the following code has lots of
names that may be fine in some circumstances, but redundant in context:

```go
// Bad:
func (db *DB) UserCount() (userCount int, err error) {
    var userCountInt64 int64
    if dbLoadError := db.LoadFromDatabase("count(distinct users)", &userCountInt64); dbLoadError != nil {
        return 0, fmt.Errorf("failed to load user count: %s", dbLoadError)
    }
    userCount = int(userCountInt64)
    return userCount, nil
}
```

Instead, information about names that are clear from context or usage can often
be omitted:

```go
// Good:
func (db *DB) UserCount() (int, error) {
    var count int64
    if err := db.Load("count(distinct users)", &count); err != nil {
        return 0, fmt.Errorf("failed to load user count: %s", err)
    }
    return int(count), nil
}
```

<a id="commentary"></a>

## Commentary

The conventions around commentary (which include what to comment, what style to
use, how to provide runnable examples, etc.) are intended to support the
experience of reading the documentation of a public API. See
[Effective Go](http://golang.org/doc/effective_go.html#commentary) for more
information.

The best practices document's section on [documentation conventions] discusses
this further.

**Best Practice:** Use [doc preview] during development and code review to see
whether the documentation and runnable examples are useful and are presented the
way you expect them to be.

**Tip:** Godoc uses very little special formatting; lists and code snippets
should usually be indented to avoid linewrapping. Apart from indentation,
decoration should generally be avoided.

[doc preview]: best-practices#documentation-preview
[documentation conventions]:  best-practices#documentation-conventions

<a id="comment-line-length"></a>

### Comment line length

There is no fixed [line length] for comments in Go.

[line length]: guide#line-length

Long comment lines should be wrapped to ensure that source is readable in tools
which do not perform automatic wrapping of comment lines. If you are uncertain
where to wrap, 80 or 100 columns are common choices. However, this is not a hard
cut-off; there are situations where breaking a long literal text is harmful.
There is no requirement for the specific column width at which wrapping occurs.
Aim to be [consistent](guide#consistency) within a file.

See this [post from The Go Blog on documentation] for more on commentary.

[post from The Go Blog on documentation]: https://blog.golang.org/godoc-documenting-go-code

```text
# Good:
// This is a comment paragraph.
// The length of individual lines doesn't matter in Godoc;
// but the choice of wrapping makes it easy to read on narrow screens.
//
// Don't worry too much about the long URL:
// https://supercalifragilisticexpialidocious.example.com:8080/Animalia/Chordata/Mammalia/Rodentia/Geomyoidea/Geomyidae/
//
// Similarly, if you have other information that is made awkward
// by too many line breaks, use your judgment and include a long line
// if it helps rather than hinders.
```

Avoid comments that fit large amounts of text onto a single line, which is a
poor reader experience.

```text
# Bad:
// This is a comment paragraph. While some code editors and viewers will wrap the paragraph for the reader, others will display a very long line that will overflow most windows and require users to scroll horizontally. In addition, even on a screen capable of displaying the entire line, it is easier to read a narrower paragraph than very wide one.
//
// Don't worry too much about the long URL:
// https://supercalifragilisticexpialidocious.example.com:8080/Animalia/Chordata/Mammalia/Rodentia/Geomyoidea/Geomyidae/
```

<a id="doc-comments"></a>

### Doc comments

<a id="TOC-DocComments"></a>

All top-level exported names must have doc comments, as should unexported type
or function declarations with unobvious behavior or meaning. These comments
should be [full sentences] that begin with the name of the object being
described. An article ("a", "an", "the") can precede the name to make it read
more naturally.

```go
// Good:
// A Request represents a request to run a command.
type Request struct { ...

// Encode writes the JSON encoding of req to w.
func Encode(w io.Writer, req *Request) { ...
```

Doc comments appear in [Godoc](https://pkg.go.dev/) and are surfaced by IDEs,
and therefore should be written for anyone using the package.

[full sentences]: #comment-sentences

A documentation comment applies to the following symbol, or the group of fields
if it appears in a struct.

```go
// Good:
// Options configure the group management service.
type Options struct {
    // General setup:
    Name  string
    Group *FooGroup

    // Dependencies:
    DB *sql.DB

    // Customization:
    LargeGroupThreshold int // optional; default: 10
    MinimumMembers      int // optional; default: 2
}
```

**Best Practice:** If you have doc comments for unexported code, follow the same
custom as if it were exported (namely, starting the comment with the unexported
name). This makes it easy to export it later by simply replacing the unexported
name with the newly-exported one across both comments and code.

<a id="comment-sentences"></a>

### Comment sentences

<a id="TOC-CommentSentences"></a>

Comments that are complete sentences should be capitalized and punctuated like
standard English sentences. (As an exception, it is okay to begin a sentence
with an uncapitalized identifier name if it is otherwise clear. Such cases are
probably best done only at the beginning of a paragraph.)

Comments that are sentence fragments have no such requirements for punctuation
or capitalization.

[Documentation comments] should always be complete sentences, and as such should
always be capitalized and punctuated. Simple end-of-line comments (especially
for struct fields) can be simple phrases that assume the field name is the
subject.

```go
// Good:
// A Server handles serving quotes from the collected works of Shakespeare.
type Server struct {
    // BaseDir points to the base directory under which Shakespeare's works are stored.
    //
    // The directory structure is expected to be the following:
    //   {BaseDir}/manifest.json
    //   {BaseDir}/{name}/{name}-part{number}.txt
    BaseDir string

    WelcomeMessage  string // displayed when user logs in
    ProtocolVersion string // checked against incoming requests
    PageLength      int    // lines per page when printing (optional; default: 20)
}
```

[Documentation comments]: #doc-comments

<a id="examples"></a>

### Examples

<a id="TOC-Examples"></a>

Packages should clearly document their intended usage. Try to provide a
[runnable example]; examples show up in Godoc. Runnable examples belong in the
test file, not the production source file. See this example ([Godoc], [source]).

[runnable example]: http://blog.golang.org/examples
[Godoc]: https://pkg.go.dev/time#example-Duration
[source]: https://cs.opensource.google/go/go/+/HEAD:src/time/example_test.go

If it isn't feasible to provide a runnable example, example code can be provided
within code comments. As with other code and command-line snippets in comments,
it should follow standard formatting conventions.

<a id="named-result-parameters"></a>

### Named result parameters

<a id="TOC-NamedResultParameters"></a>

When naming parameters, consider how function signatures appear in Godoc. The
name of the function itself and the type of the result parameters are often
sufficiently clear.

```go
// Good:
func (n *Node) Parent1() *Node
func (n *Node) Parent2() (*Node, error)
```

If a function returns two or more parameters of the same type, adding names can
be useful.

```go
// Good:
func (n *Node) Children() (left, right *Node, err error)
```

If the caller must take action on particular result parameters, naming them can
help suggest what the action is:

```go
// Good:
// WithTimeout returns a context that will be canceled no later than d duration
// from now.
//
// The caller must arrange for the returned cancel function to be called when
// the context is no longer needed to prevent a resource leak.
func WithTimeout(parent Context, d time.Duration) (ctx Context, cancel func())
```

In the code above, cancellation is a particular action a caller must take.
However, were the result parameters written as `(Context, func())` alone, it
would be unclear what is meant by "cancel function".

Don't use named result parameters when the names produce
[unnecessary repetition](#repetitive-with-type).

```go
// Bad:
func (n *Node) Parent1() (node *Node)
func (n *Node) Parent2() (node *Node, err error)
```

Don't name result parameters in order to avoid declaring a variable inside the
function. This practice results in unnecessary API verbosity at the cost of
minor implementation brevity.

[Naked returns] are acceptable only in a small function. Once it's a
medium-sized function, be explicit with your returned values. Similarly, do not
name result parameters just because it enables you to use naked returns.
[Clarity](guide#clarity) is always more important than saving a few lines in
your function.

It is always acceptable to name a result parameter if its value must be changed
in a deferred closure.

> **Tip:** Types can often be clearer than names in function signatures.
> [GoTip #38: Functions as Named Types] demonstrates this.
>
> In, [`WithTimeout`] above, the real code uses a [`CancelFunc`] instead of a
> raw `func()` in the result parameter list and requires little effort to
> document.

[Naked returns]: https://tour.golang.org/basics/7
[GoTip #38: Functions as Named Types]: https://google.github.io/styleguide/go/index.html#gotip
[`WithTimeout`]: https://pkg.go.dev/context#WithTimeout
[`CancelFunc`]: https://pkg.go.dev/context#CancelFunc

<a id="package-comments"></a>

### Package comments

<a id="TOC-PackageComments"></a>

Package comments must appear immediately above the package clause with no blank
line between the comment and the package name. Example:

```go
// Good:
// Package math provides basic constants and mathematical functions.
//
// This package does not guarantee bit-identical results across architectures.
package math
```

There must be a single package comment per package. If a package is composed of
multiple files, exactly one of the files should have a package comment.

Comments for `main` packages have a slightly different form, where the name of
the `go_binary` rule in the BUILD file takes the place of the package name.

```go
// Good:
// The seed_generator command is a utility that generates a Finch seed file
// from a set of JSON study configs.
package main
```

Other styles of comment are fine as long as the name of the binary is exactly as
written in the BUILD file. When the binary name is the first word, capitalizing
it is required even though it does not strictly match the spelling of the
command-line invocation.

```go
// Good:
// Binary seed_generator ...
// Command seed_generator ...
// Program seed_generator ...
// The seed_generator command ...
// The seed_generator program ...
// Seed_generator ...
```

Tips:
