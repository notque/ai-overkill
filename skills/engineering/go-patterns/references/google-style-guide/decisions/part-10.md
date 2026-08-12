
    for _, test := range tests {
        t.Run(test.name, func(t *testing.T) {
            output, err := Decode(test.input, codex)
            if got, want := output, test.output; got != want {
                t.Errorf("Decode(%q) = %v, want %v", test.input, got, want)
            }
            if got, want := err, test.err; !cmp.Equal(got, want) {
                t.Errorf("Decode(%q) err %q, want %q", test.input, got, want)
            }
        })
    }
}
```

In the counterexample below, note how hard it is to distinguish between which
type of `Codex` is used per test case in the case setup. (The highlighted parts
run afoul of the advice from [TotT: Data Driven Traps!][tott-97] .)

```go
// Bad:
type decodeCase struct {
  name   string
  input  string
  codex  testCodex
  output string
  err    error
}

type testCodex int

const (
  fake testCodex = iota
  prod
)

func TestDecode(t *testing.T) {
  var tests []decodeCase // rows omitted for brevity

  for _, test := tests {
    t.Run(test.name, func(t *testing.T) {
      var codex Codex
      switch test.codex {
      case fake:
        codex = newFakeCodex()
      case prod:
        codex = setupCodex(t)
      default:
        t.Fatalf("Unknown codex type: %v", codex)
      }
      output, err := Decode(test.input, codex)
      if got, want := output, test.output; got != want {
        t.Errorf("Decode(%q) = %q, want %q", test.input, got, want)
      }
      if got, want := err, test.err; !cmp.Equal(got, want) {
        t.Errorf("Decode(%q) err %q, want %q", test.input, got, want)
      }
    })
  }
}
```

[tott-97]: https://testing.googleblog.com/2008/09/tott-data-driven-traps.html

<a id="table-tests-identifying-the-row"></a>

#### Identifying the row

Do not use the index of the test in the test table as a substitute for naming
your tests or printing the inputs. Nobody wants to go through your test table
and count the entries in order to figure out which test case is failing.

```go
// Bad:
tests := []struct {
    input, want string
}{
    {"hello", "HELLO"},
    {"wORld", "WORLD"},
}
for i, d := range tests {
    if strings.ToUpper(d.input) != d.want {
        t.Errorf("Failed on case #%d", i)
    }
}
```

Add a test description to your test struct and print it along failure messages.
When using subtests, your subtest name should be effective in identifying the
row.

**Important:** Even though `t.Run` scopes the output and execution, you must
always [identify the input]. The table test row names must follow the
[subtest naming] guidance.

[identify the input]: #identify-the-input
[subtest naming]: #subtest-names

<a id="mark-test-helpers"></a>

### Test helpers

A test helper is a function that performs a setup or cleanup task. All failures
that occur in test helpers are expected to be failures of the environment (not
from the code under test) — for example when a test database cannot be started
because there are no more free ports on this machine.

If you pass a `*testing.T`, call [`t.Helper`] to attribute failures in the test
helper to the line where the helper is called. This parameter should come after
a [context](#contexts) parameter, if present, and before any remaining
parameters.

```go
// Good:
func TestSomeFunction(t *testing.T) {
    golden := readFile(t, "testdata/golden-result.txt")
    // ... tests against golden ...
}

// readFile returns the contents of a data file.
// It must only be called from the same goroutine as started the test.
func readFile(t *testing.T, filename string) string {
    t.Helper()
    contents, err := runfiles.ReadFile(filename)
    if err != nil {
        t.Fatal(err)
    }
    return string(contents)
}
```

Do not use this pattern when it obscures the connection between a test failure
and the conditions that led to it. Specifically, the guidance about
[assert libraries](#assert) still applies, and [`t.Helper`] should not be used
to implement such libraries.

**Tip:** For more on the distinction between test helpers and assertion helpers,
see [best practices](best-practices#test-functions).

Although the above refers to `*testing.T`, much of the advice stays the same for
benchmark and fuzz helpers.

[`t.Helper`]: https://pkg.go.dev/testing#T.Helper

<a id="test-package"></a>

### Test package

<a id="TOC-TestPackage"></a>

<a id="test-same-package"></a>

#### Tests in the same package

Tests may be defined in the same package as the code being tested.

To write a test in the same package:

*   Place the tests in a `foo_test.go` file
*   Use `package foo` for the test file
*   Do not explicitly import the package to be tested

```build
# Good:
go_library(
    name = "foo",
    srcs = ["foo.go"],
    deps = [
        ...
    ],
)

go_test(
    name = "foo_test",
    size = "small",
    srcs = ["foo_test.go"],
    library = ":foo",
    deps = [
        ...
    ],
)
```

A test in the same package can access unexported identifiers in the package.
This may enable better test coverage and more concise tests. Be aware that any
[examples] declared in the test will not have the package names that a user will
need in their code.

[`library`]: https://github.com/bazelbuild/rules_go/blob/master/docs/go/core/rules.md#go_library
[examples]: #examples

<a id="test-different-package"></a>

#### Tests in a different package

It is not always appropriate or even possible to define a test in the same
package as the code being tested. In these cases, use a package name with the
`_test` suffix. This is an exception to the "no underscores" rule to
[package names](#package-names). For example:

*   If an integration test does not have an obvious library that it belongs to

    ```go
    // Good:
    package gmailintegration_test

    import "testing"
    ```

*   If defining the tests in the same package results in circular dependencies

    ```go
    // Good:
    package fireworks_test

    import (
      "fireworks"
      "fireworkstestutil" // fireworkstestutil also imports fireworks
    )
    ```

<a id="use-package-testing"></a>

### Use package `testing`

The Go standard library provides the [`testing` package]. This is the only
testing framework permitted for Go code in the Google codebase. In particular,
[assertion libraries](#assert) and third-party testing frameworks are not
allowed.

The `testing` package provides a minimal but complete set of functionality for
writing good tests:

*   Top-level tests
*   Benchmarks
*   [Runnable examples](https://blog.golang.org/examples)
*   Subtests
*   Logging
*   Failures and fatal failures

These are designed to work cohesively with core language features like
[composite literal] and [if-with-initializer] syntax to enable test authors to
write [clear, readable, and maintainable tests].

[`testing` package]: https://pkg.go.dev/testing
[composite literal]: https://go.dev/ref/spec#Composite_literals
[if-with-initializer]: https://go.dev/ref/spec#If_statements

<a id="non-decisions"></a>

## Non-decisions

A style guide cannot enumerate positive prescriptions for all matters, nor can
it enumerate all matters about which it does not offer an opinion. That said,
here are a few things where the readability community has previously debated and
has not achieved consensus about.

*   **Local variable initialization with zero value**. `var i int` and `i := 0`
    are equivalent. See also [initialization best practices].
*   **Empty composite literal vs. `new` or `make`**. `&File{}` and `new(File)`
    are equivalent. So are `map[string]bool{}` and `make(map[string]bool)`. See
    also [composite declaration best practices].
*   **got, want argument ordering in cmp.Diff calls**. Be locally consistent,
    and [include a legend](#print-diffs) in your failure message.
*   **`errors.New` vs `fmt.Errorf` on non-formatted strings**.
    `errors.New("foo")` and `fmt.Errorf("foo")` may be used interchangeably.

If there are special circumstances where they come up again, the readability
mentor might make an optional comment, but in general the author is free to pick
the style they prefer in the given situation.

Naturally, if anything not covered by the style guide does need more discussion,
authors are welcome to ask -- either in the specific review, or on internal
message boards.

[composite declaration best practices]: https://google.github.io/styleguide/go/best-practices#vardeclcomposite
[initialization best practices]: https://google.github.io/styleguide/go/best-practices#vardeclinitialization

<!--

-->

{% endraw %}
