`q.Context`, for all pairs of packages `p` and `q`. This is impractical and
error-prone for humans, and it makes automated refactorings that add context
parameters nearly impossible.

If you have application data to pass around, put it in a parameter, in the
receiver, in globals, or in a `Context` value if it truly belongs there.
Creating your own context type is not acceptable since it undermines the ability
of the Go team to make Go programs work properly in production.

<a id="crypto-rand"></a>

### crypto/rand

<a id="TOC-CryptoRand"></a>

Do not use package `math/rand` to generate keys, even throwaway ones. If
unseeded, the generator is completely predictable. Seeded with
`time.Nanoseconds()`, there are just a few bits of entropy. Instead, use
`crypto/rand`'s Reader, and if you need text, print to hexadecimal or base64.

```go
// Good:
import (
    "crypto/rand"
    // "encoding/base64"
    // "encoding/hex"
    "fmt"

    // ...
)

func Key() string {
    buf := make([]byte, 16)
    if _, err := rand.Read(buf); err != nil {
        log.Fatalf("Out of randomness, should never happen: %v", err)
    }
    return fmt.Sprintf("%x", buf)
    // or hex.EncodeToString(buf)
    // or base64.StdEncoding.EncodeToString(buf)
}
```

**Note:** `log.Fatalf` is not the standard library log. See [#logging].

<a id="useful-test-failures"></a>

## Useful test failures

<a id="TOC-UsefulTestFailures"></a>

It should be possible to diagnose a test's failure without reading the test's
source. Tests should fail with helpful messages detailing:

*   What caused the failure
*   What inputs resulted in an error
*   The actual result
*   What was expected

Specific conventions for achieving this goal are outlined below.

<a id="assert"></a>

### Assertion libraries

<a id="TOC-Assert"></a>

Do not create "assertion libraries" as helpers for testing.

Assertion libraries are libraries that attempt to combine the validation and
production of failure messages within a test (though the same pitfalls can apply
to other test helpers as well). For more on the distinction between test helpers
and assertion libraries, see [best practices](best-practices#test-functions).

```go
// Bad:
var obj BlogPost

assert.IsNotNil(t, "obj", obj)
assert.StringEq(t, "obj.Type", obj.Type, "blogPost")
assert.IntEq(t, "obj.Comments", obj.Comments, 2)
assert.StringNotEq(t, "obj.Body", obj.Body, "")
```

Assertion libraries tend to either stop the test early (if `assert` calls
`t.Fatalf` or `panic`) or omit relevant information about what the test got
right:

```go
// Bad:
package assert

func IsNotNil(t *testing.T, name string, val any) {
    if val == nil {
        t.Fatalf("Data %s = nil, want not nil", name)
    }
}

func StringEq(t *testing.T, name, got, want string) {
    if got != want {
        t.Fatalf("Data %s = %q, want %q", name, got, want)
    }
}
```

Complex assertion functions often do not provide [useful failure messages] and
context that exists within the test function. Too many assertion functions and
libraries lead to a fragmented developer experience: which assertion library
should I use, what style of output format should it emit, etc.? Fragmentation
produces unnecessary confusion, especially for library maintainers and authors
of large-scale changes, who are responsible for fixing potential downstream
breakages. Instead of creating a domain-specific language for testing, use Go
itself.

Assertion libraries often factor out comparisons and equality checks. Prefer
using standard libraries such as [`cmp`] and [`fmt`] instead:

```go
// Good:
var got BlogPost

want := BlogPost{
    Comments: 2,
    Body:     "Hello, world!",
}

if !cmp.Equal(got, want) {
    t.Errorf("Blog post = %v, want = %v", got, want)
}
```

For more domain-specific comparison helpers, prefer returning a value or an
error that can be used in the test's failure message instead of passing
`*testing.T` and calling its error reporting methods:

```go
// Good:
func postLength(p BlogPost) int { return len(p.Body) }

func TestBlogPost_VeritableRant(t *testing.T) {
    post := BlogPost{Body: "I am Gunnery Sergeant Hartman, your senior drill instructor."}

    if got, want := postLength(post), 60; got != want {
        t.Errorf("Length of post = %v, want %v", got, want)
    }
}
```

**Best Practice:** Were `postLength` non-trivial, it would make sense to test it
directly, independently of any tests that use it.

See also:

*   [Equality comparison and diffs](#types-of-equality)
*   [Print diffs](#print-diffs)
*   For more on the distinction between test helpers and assertion helpers, see
    [best practices](best-practices#test-functions)
*   [Go FAQ] section on [testing frameworks] and their opinionated absence

[useful failure messages]: #useful-test-failures
[`fmt`]: https://golang.org/pkg/fmt/
[marking test helpers]: #mark-test-helpers
[Go FAQ]: https://go.dev/doc/faq
[testing frameworks]: https://go.dev/doc/faq#testing_framework

<a id="identify-the-function"></a>

### Identify the function

In most tests, failure messages should include the name of the function that
failed, even though it seems obvious from the name of the test function.
Specifically, your failure message should be `YourFunc(%v) = %v, want %v`
instead of just `got %v, want %v`.

<a id="identify-the-input"></a>

### Identify the input

In most tests, failure messages should include the function inputs if they are
short. If the relevant properties of the inputs are not obvious (for example,
because the inputs are large or opaque), you should name your test cases with a
description of what's being tested and print the description as part of your
error message.

<a id="got-before-want"></a>

### Got before want

Test outputs should include the actual value that the function returned before
printing the value that was expected. A standard format for printing test
outputs is `YourFunc(%v) = %v, want %v`. Where you would write "actual" and
"expected", prefer using the words "got" and "want", respectively.

For diffs, directionality is less apparent, and as such it is important to
include a key to aid in interpreting the failure. See the
[section on printing diffs]. Whichever diff order you use in your failure
messages, you should explicitly indicate it as a part of the failure message,
because existing code is inconsistent about the ordering.

[section on printing diffs]: #print-diffs

<a id="compare-full-structures"></a>

### Full structure comparisons

If your function returns a struct (or any data type with multiple fields such as
slices, arrays, and maps), avoid writing test code that performs a hand-coded
field-by-field comparison of the struct. Instead, construct the data that you're
expecting your function to return, and compare directly using a
[deep comparison].

**Note:** This does not apply if your data contains irrelevant fields that
obscure the intention of the test.

If your struct needs to be compared for approximate (or equivalent kind of
semantic) equality or it contains fields that cannot be compared for equality
(e.g., if one of the fields is an `io.Reader`), tweaking a [`cmp.Diff`] or
[`cmp.Equal`] comparison with [`cmpopts`] options such as
[`cmpopts.IgnoreInterfaces`] may meet your needs
([example](https://play.golang.org/p/vrCUNVfxsvF)).

If your function returns multiple return values, you don't need to wrap those in
a struct before comparing them. Just compare the return values individually and
print them.

```go
// Good:
val, multi, tail, err := strconv.UnquoteChar(`\"Fran & Freddie's Diner\"`, '"')
if err != nil {
  t.Fatalf(...)
}
if val != `"` {
  t.Errorf(...)
}
if multi {
  t.Errorf(...)
}
if tail != `Fran & Freddie's Diner"` {
  t.Errorf(...)
}
```

[deep comparison]: #types-of-equality
[`cmpopts`]: https://pkg.go.dev/github.com/google/go-cmp/cmp/cmpopts
[`cmpopts.IgnoreInterfaces`]: https://pkg.go.dev/github.com/google/go-cmp/cmp/cmpopts#IgnoreInterfaces

<a id="compare-stable-results"></a>

### Compare stable results

Avoid comparing results that may depend on output stability of a package that
you do not own. Instead, the test should compare on semantically relevant
information that is stable and resistant to changes in dependencies. For
functionality that returns a formatted string or serialized bytes, it is
generally not safe to assume that the output is stable.

For example, [`json.Marshal`] can change (and has changed in the past) the
specific bytes that it emits. Tests that perform string equality on the JSON
string may break if the `json` package changes how it serializes the bytes.
Instead, a more robust test would parse the contents of the JSON string and
ensure that it is semantically equivalent to some expected data structure.

[`json.Marshal`]: https://golang.org/pkg/encoding/json/#Marshal

<a id="keep-going"></a>

### Keep going

Tests should keep going for as long as possible, even after a failure, in order
to print out all of the failed checks in a single run. This way, a developer who
is fixing the failing test doesn't have to re-run the test after fixing each bug
to find the next bug.

Prefer calling `t.Error` over `t.Fatal` for reporting a mismatch. When comparing
several different properties of a function's output, use `t.Error` for each of
those comparisons.

```go
// Good:
gotMean, gotVariance, err := MyDistribution(input)
if err != nil {
  t.Fatalf("MyDistribution(%v) returned unexpected error: %v", input, err)
}
if diff := cmp.Diff(wantMean, gotMean); diff != "" {
  t.Errorf("MyDistribution(%v) returned unexpected difference in mean value (-want +got):\n%s", input, diff)
}
if diff := cmp.Diff(wantVariance, gotVariance); diff != "" {
  t.Errorf("MyDistribution(%v) returned unexpected difference in variance value (-want +got):\n%s", input, diff)
}
```

Calling `t.Fatal` is primarily useful for reporting an unexpected condition
(such as an error or output mismatch) when subsequent failures would be
meaningless or even mislead the investigator. Note how the code below calls
`t.Fatalf` and *then* `t.Errorf`:

```go
// Good:
gotEncoded := Encode(input)
if gotEncoded != wantEncoded {
  t.Fatalf("Encode(%q) = %q, want %q", input, gotEncoded, wantEncoded)
  // It doesn't make sense to decode from unexpected encoded input.
}
gotDecoded, err := Decode(gotEncoded)
if err != nil {
  t.Fatalf("Decode(%q) returned unexpected error: %v", gotEncoded, err)
}
if gotDecoded != input {
  t.Errorf("Decode(%q) = %q, want %q", gotEncoded, gotDecoded, input)
}
```

For table-driven test, consider using subtests and use `t.Fatal` rather than
`t.Error` and `continue`. See also
[GoTip #25: Subtests: Making Your Tests Lean](https://google.github.io/styleguide/go/index.html#gotip).

**Best practice:** For more discussion about when `t.Fatal` should be used, see
[best practices](best-practices#t-fatal).

<a id="types-of-equality"></a>

### Equality comparison and diffs

The `==` operator evaluates equality using [language-defined comparisons].
Scalar values (numbers, booleans, etc) are compared based on their values, but
only some structs and interfaces can be compared in this way. Pointers are
compared based on whether they point to the same variable, rather than based on
the equality of the values to which they point.

The [`cmp`] package can compare more complex data structures not appropriately
handled by `==`, such as slices. Use [`cmp.Equal`] for equality comparison and
[`cmp.Diff`] to obtain a human-readable diff between objects.

```go
// Good:
want := &Doc{
    Type:     "blogPost",
    Comments: 2,
    Body:     "This is the post body.",
    Authors:  []string{"isaac", "albert", "emmy"},
}
if !cmp.Equal(got, want) {
    t.Errorf("AddPost() = %+v, want %+v", got, want)
}
```

As a general-purpose comparison library, `cmp` may not know how to compare
certain types. For example, it can only compare protocol buffer messages if
passed the [`protocmp.Transform`] option.

<!-- The order of want and got here is deliberate. See comment in #print-diffs. -->

```go
// Good:
if diff := cmp.Diff(want, got, protocmp.Transform()); diff != "" {
    t.Errorf("Foo() returned unexpected difference in protobuf messages (-want +got):\n%s", diff)
}
```

Although the `cmp` package is not part of the Go standard library, it is
maintained by the Go team and should produce stable equality results over time.
It is user-configurable and should serve most comparison needs.

[language-defined comparisons]: http://golang.org/ref/spec#Comparison_operators
[`cmp`]: https://pkg.go.dev/github.com/google/go-cmp/cmp
[`cmp.Equal`]: https://pkg.go.dev/github.com/google/go-cmp/cmp#Equal
[`cmp.Diff`]: https://pkg.go.dev/github.com/google/go-cmp/cmp#Diff
[`protocmp.Transform`]: https://pkg.go.dev/google.golang.org/protobuf/testing/protocmp#Transform

Existing code may make use of the following older libraries, and may continue
using them for consistency:

*   [`pretty`] produces aesthetically pleasing difference reports. However, it
    quite deliberately considers values that have the same visual representation
    as equal. In particular, `pretty` does not catch differences between nil
    slices and empty ones, is not sensitive to different interface
    implementations with identical fields, and it is possible to use a nested
    map as the basis for comparison with a struct value. It also serializes the
    entire value into a string before producing a diff, and as such is not a
    good choice for comparing large values. By default, it compares unexported
    fields, which makes it sensitive to changes in implementation details in
    your dependencies. For this reason, it is not appropriate to use `pretty` on
    protobuf messages.

[`pretty`]: https://pkg.go.dev/github.com/kylelemons/godebug/pretty

Prefer using `cmp` for new code, and it is worth considering updating older code
to use `cmp` where and when it is practical to do so.

Older code may use the standard library `reflect.DeepEqual` function to compare
complex structures. `reflect.DeepEqual` should not be used for checking
equality, as it is sensitive to changes in unexported fields and other
implementation details. Code that is using `reflect.DeepEqual` should be updated
to one of the above libraries.

**Note:** The `cmp` package is designed for testing, rather than production use.
As such, it may panic when it suspects that a comparison is performed
incorrectly to provide instruction to users on how to improve the test to be
less brittle. Given cmp's propensity towards panicking, it makes it unsuitable
for code that is used in production as a spurious panic may be fatal.

