<a id="level-of-detail"></a>

### Level of detail

The conventional failure message, which is suitable for most Go tests, is
`YourFunc(%v) = %v, want %v`. However, there are cases that may call for more or
less detail:

*   Tests performing complex interactions should describe the interactions too.
    For example, if the same `YourFunc` is called several times, identify which
    call failed the test. If it's important to know any extra state of the
    system, include that in the failure output (or at least in the logs).
*   If the data is a complex struct with significant boilerplate, it is
    acceptable to describe only the important parts in the message, but do not
    overly obscure the data.
*   Setup failures do not require the same level of detail. If a test helper
    populates a Spanner table but Spanner was down, you probably don't need to
    include which test input you were going to store in the database.
    `t.Fatalf("Setup: Failed to set up test database: %s", err)` is usually
    helpful enough to resolve the issue.

**Tip:** Make your failure mode trigger during development. Review what the
failure message looks like and whether a maintainer can effectively deal with
the failure.

There are some techniques for reproducing test inputs and outputs clearly:

*   When printing string data, [`%q` is often useful](#use-percent-q) to
    emphasize that the value is important and to more easily spot bad values.
*   When printing (small) structs, `%+v` can be more useful than `%v`.
*   When validation of larger values fails, [printing a diff](#print-diffs) can
    make it easier to understand the failure.

<a id="print-diffs"></a>

### Print diffs

If your function returns large output then it can be hard for someone reading
the failure message to find the differences when your test fails. Instead of
printing both the returned value and the wanted value, make a diff.

To compute diffs for such values, `cmp.Diff` is preferred, particularly for new
tests and new code, but other tools may be used. See [types of equality] for
guidance regarding the strengths and weaknesses of each function.

*   [`cmp.Diff`]

*   [`pretty.Compare`]

You can use the [`diff`] package to compare multi-line strings or lists of
strings. You can use this as a building block for other kinds of diffs.

[types of equality]: #types-of-equality
[`diff`]: https://pkg.go.dev/github.com/kylelemons/godebug/diff
[`pretty.Compare`]: https://pkg.go.dev/github.com/kylelemons/godebug/pretty#Compare

Add some text to your failure message explaining the direction of the diff.

<!--
The reversed order of want and got in these examples is intentional, as this is
the prevailing order across the Google codebase. The lack of a stance on which
order to use is also intentional, as there is no consensus which is
"most readable."


-->

*   Something like `diff (-want +got)` is good when you're using the `cmp`,
    `pretty`, and `diff` packages (if you pass `(want, got)` to the function),
    because the `-` and `+` that you add to your format string will match the
    `-` and `+` that actually appear at the beginning of the diff lines. If you
    pass `(got, want)` to your function, the correct key would be `(-got +want)`
    instead.

*   The `messagediff` package uses a different output format, so the message
    `diff (want -> got)` is appropriate when you're using it (if you pass
    `(want, got)` to the function), because the direction of the arrow will
    match the direction of the arrow in the "modified" lines.

The diff will span multiple lines, so you should print a newline before you
print the diff.

<a id="test-error-semantics"></a>

### Test error semantics

When a unit test performs string comparisons or uses a vanilla `cmp` to check
that particular kinds of errors are returned for particular inputs, you may find
that your tests are brittle if any of those error messages are reworded in the
future. Since this has the potential to turn your unit test into a change
detector (see [TotT: Change-Detector Tests Considered Harmful][tott-350] ),
don't use string comparison to check what type of error your function returns.
However, it is permissible to use string comparisons to check that error
messages coming from the package under test satisfy certain properties, for
example, that it includes the parameter name.

Error values in Go typically have a component intended for human eyes and a
component intended for semantic control flow. Tests should seek to only test
semantic information that can be reliably observed, rather than display
information that is intended for human debugging, as this is often subject to
future changes. For guidance on constructing errors with semantic meaning see
[best-practices regarding errors](best-practices#error-handling). If an error
with insufficient semantic information is coming from a dependency outside your
control, consider filing a bug against the owner to help improve the API, rather
than relying on parsing the error message.

Within unit tests, it is common to only care whether an error occurred or not.
If so, then it is sufficient to only test whether the error was non-nil when you
expected an error. If you would like to test that the error semantically matches
some other error, then consider using [`errors.Is`] or `cmp` with
[`cmpopts.EquateErrors`].

> **Note:** If a test uses [`cmpopts.EquateErrors`] but all of its `wantErr`
> values are either `nil` or `cmpopts.AnyError`, then using `cmp` is
> [unnecessary mechanism](guide#least-mechanism). Simplify the code by making
> the want field a `bool`. You can then use a simple comparison with `!=`.
>
> ```go
> // Good:
> err := f(test.input)
> if gotErr := err != nil; gotErr != test.wantErr {
>     t.Errorf("f(%q) = %v, want error presence = %v", test.input, err, test.wantErr)
> }
> ```

See also
[GoTip #13: Designing Errors for Checking](https://google.github.io/styleguide/go/index.html#gotip).

[tott-350]: https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html
[`cmpopts.EquateErrors`]: https://pkg.go.dev/github.com/google/go-cmp/cmp/cmpopts#EquateErrors
[`errors.Is`]: https://pkg.go.dev/errors#Is

<a id="test-structure"></a>

## Test structure

<a id="subtests"></a>

### Subtests

The standard Go testing library offers a facility to [define subtests]. This
allows flexibility in setup and cleanup, controlling parallelism, and test
filtering. Subtests can be useful (particularly for table-driven tests), but
using them is not mandatory. See also the
[Go blog post about subtests](https://blog.golang.org/subtests).

Subtests should not depend on the execution of other cases for success or
initial state, because subtests are expected to be able to be run individually
with using `go test -run` flags or with Bazel [test filter] expressions.

[define subtests]: https://pkg.go.dev/testing#hdr-Subtests_and_Sub_benchmarks
[test filter]: https://bazel.build/docs/user-manual#test-filter

<a id="subtest-names"></a>

#### Subtest names

Name your subtest such that it is readable in test output and useful on the
command line for users of test filtering. When you use `t.Run` to create a
subtest, the first argument is used as a descriptive name for the test. To
ensure that test results are legible to humans reading the logs, choose subtest
names that will remain useful and readable after escaping. Think of subtest
names more like a function identifier than a prose description.

The test runner replaces spaces with underscores, and escapes non-printing
characters. To ensure accurate correlation between test logs and source code, it
is recommended to avoid using these characters in subtest names.

If your test data benefits from a longer description, consider putting the
description in a separate field (perhaps to be printed using `t.Log` or
alongside failure messages).

Subtests may be run individually using flags to the [Go test runner] or Bazel
[test filter], so choose descriptive names that are also easy to type.

> **Warning:** Slash characters are particularly unfriendly in subtest names,
> since they have [special meaning for test filters].
>
> > ```sh
> > # Bad:
> > # Assuming TestTime and t.Run("America/New_York", ...)
> > bazel test :mytest --test_filter="Time/New_York"    # Runs nothing!
> > bazel test :mytest --test_filter="Time//New_York"   # Correct, but awkward.
> > ```

To [identify the inputs] of the function, include them in the test's failure
messages, where they won't be escaped by the test runner.

```go
// Good:
func TestTranslate(t *testing.T) {
    data := []struct {
        name, desc, srcLang, dstLang, srcText, wantDstText string
    }{
        {
            name:        "hu=en_bug-1234",
            desc:        "regression test following bug 1234. contact: cleese",
            srcLang:     "hu",
            srcText:     "cigarettát és egy öngyújtót kérek",
            dstLang:     "en",
            wantDstText: "cigarettes and a lighter please",
        }, // ...
    }
    for _, d := range data {
        t.Run(d.name, func(t *testing.T) {
            got := Translate(d.srcLang, d.dstLang, d.srcText)
            if got != d.wantDstText {
                t.Errorf("%s\nTranslate(%q, %q, %q) = %q, want %q",
                    d.desc, d.srcLang, d.dstLang, d.srcText, got, d.wantDstText)
            }
        })
    }
}
```

Here are a few examples of things to avoid:

```go
// Bad:
// Too wordy.
t.Run("check that there is no mention of scratched records or hovercrafts", ...)
// Slashes cause problems on the command line.
t.Run("AM/PM confusion", ...)
```

See also
[Go Tip #117: Subtest Names](https://google.github.io/styleguide/go/index.html#gotip).

[Go test runner]: https://golang.org/cmd/go/#hdr-Testing_flags
[identify the inputs]: #identify-the-input
[special meaning for test filters]: https://blog.golang.org/subtests#:~:text=Perhaps%20a%20bit,match%20any%20tests

<a id="table-driven-tests"></a>

### Table-driven tests

Use table-driven tests when many different test cases can be tested using
similar testing logic.

*   When testing whether the actual output of a function is equal to the
    expected output. For example, the many [tests of `fmt.Sprintf`] or the
    minimal snippet below.
*   When testing whether the outputs of a function always conform to the same
    set of invariants. For example, [tests for `net.Dial`].

[tests of `fmt.Sprintf`]: https://cs.opensource.google/go/go/+/master:src/fmt/fmt_test.go
[tests for `net.Dial`]: https://cs.opensource.google/go/go/+/master:src/net/dial_test.go;l=318;drc=5b606a9d2b7649532fe25794fa6b99bd24e7697c

Here is the minimal structure of a table-driven test. If needed, you may use
different names or add extra facilities such as subtests or setup and cleanup
functions. Always keep [useful test failures](#useful-test-failures) in mind.

```go
// Good:
func TestCompare(t *testing.T) {
    compareTests := []struct {
        a, b string
        want int
    }{
        {"", "", 0},
        {"a", "", 1},
        {"", "a", -1},
        {"abc", "abc", 0},
        {"ab", "abc", -1},
        {"abc", "ab", 1},
        {"x", "ab", 1},
        {"ab", "x", -1},
        {"x", "a", 1},
        {"b", "x", -1},
        // test runtime·memeq's chunked implementation
        {"abcdefgh", "abcdefgh", 0},
        {"abcdefghi", "abcdefghi", 0},
        {"abcdefghi", "abcdefghj", -1},
    }

    for _, test := range compareTests {
        got := Compare(test.a, test.b)
        if got != test.want {
            t.Errorf("Compare(%q, %q) = %v, want %v", test.a, test.b, got, test.want)
        }
    }
}
```

**Note**: The failure messages in this example above fulfill the guidance to
[identify the function](#identify-the-function) and
[identify the input](#identify-the-input). There's no need to
[identify the row numerically](#table-tests-identifying-the-row).

When some test cases need to be checked using different logic from other test
cases, it is appropriate to write multiple test functions, as explained in
[GoTip #50: Disjoint Table Tests].

When the additional test cases are simple (e.g., basic error checking) and don't
introduce conditionalized code flow in the table test's loop body, it's
permissible to include that case in the existing test, though be careful using
logic like this. What starts simple today can organically grow into something
unmaintainable.

For example:

```go
func TestDivide(t *testing.T) {
    tests := []struct {
        dividend, divisor int
        want              int
        wantErr           bool
    }{
        {
            dividend: 4,
            divisor:  2,
            want:     2,
        },
        {
            dividend: 10,
            divisor:  2,
            want:     5,
        },
        {
            dividend: 1,
            divisor:  0,
            wantErr:  true,
        },
    }

    for _, test := range tests {
        got, err := Divide(test.dividend, test.divisor)
        if (err != nil) != test.wantErr {
            t.Errorf("Divide(%d, %d) error = %v, want error presence = %t", test.dividend, test.divisor, err, test.wantErr)
        }

        // In this example, we're only testing the value result when the tested function didn't fail.
        if err != nil {
            continue
        }

        if got != test.want {
            t.Errorf("Divide(%d, %d) = %d, want %d", test.dividend, test.divisor, got, test.want)
        }
    }
}
```

More complicated logic in your test code, like complex error checking based on
conditional differences in test setup (often based on table test input
parameters), can be [difficult to understand](guide#maintainability) when each
entry in a table has specialized logic based on the inputs. If test cases have
different logic but identical setup, a sequence of [subtests](#subtests) within
a single test function might be more readable. A test helper may also be useful
for simplifying test setup in order to maintain the readability of a test body.

You can combine table-driven tests with multiple test functions. For example,
when testing that a function's output exactly matches the expected output and
that the function returns a non-nil error for an invalid input, then writing two
separate table-driven test functions is the best approach: one for normal
non-error outputs, and one for error outputs.

[GoTip #50: Disjoint Table Tests]: https://google.github.io/styleguide/go/index.html#gotip

<a id="table-tests-data-driven"></a>

#### Data-driven test cases

Table test rows can sometimes become complicated, with the row values dictating
conditional behavior inside the test case. The extra clarity from the
duplication between the test cases is necessary for readability.

```go
// Good:
type decodeCase struct {
    name   string
    input  string
    output string
    err    error
}

func TestDecode(t *testing.T) {
    // setupCodex is slow as it creates a real Codex for the test.
    codex := setupCodex(t)

    var tests []decodeCase // rows omitted for brevity

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

func TestDecodeWithFake(t *testing.T) {
    // A fakeCodex is a fast approximation of a real Codex.
    codex := newFakeCodex()

    var tests []decodeCase // rows omitted for brevity
