<!--* toc_depth: 3 *-->

# Go Style Best Practices

https://google.github.io/styleguide/go/best-practices

[Overview](index) | [Guide](guide) | [Decisions](decisions) |
[Best practices](best-practices)

<!--

-->

{% raw %}

**Note:** This is part of a series of documents that outline [Go Style](index)
at Google. This document is **neither [normative](index#normative) nor
[canonical](index#canonical)**, and is an auxiliary document to the
[core style guide](guide). See [the overview](index#about) for more information.

<a id="about"></a>

## About

This file documents **guidance about how to best apply the Go Style Guide**.
This guidance is intended for common situations that arise frequently, but may
not apply in every circumstance. Where possible, multiple alternative approaches
are discussed along with the considerations that go into the decision about when
and when not to apply them.

See [the overview](index#about) for the full set of Style Guide documents.

<a id="naming"></a>

## Naming

<a id="function-names"></a>

### Function and method names

<a id="function-name-repetition"></a>

#### Avoid repetition

When choosing the name for a function or method, consider the context in which
the name will be read. Consider the following recommendations to avoid excess
[repetition](decisions#repetition) at the call site:

*   The following can generally be omitted from function and method names:

    *   The types of the inputs and outputs (when there is no collision)
    *   The type of a method's receiver
    *   Whether an input or output is a pointer

*   For functions, do not
    [repeat the name of the package](decisions#repetitive-with-package).

    ```go
    // Bad:
    package yamlconfig

    func ParseYAMLConfig(input string) (*Config, error)
    ```

    ```go
    // Good:
    package yamlconfig

    func Parse(input string) (*Config, error)
    ```

*   For methods, do not repeat the name of the method receiver.

    ```go
    // Bad:
    func (c *Config) WriteConfigTo(w io.Writer) (int64, error)
    ```

    ```go
    // Good:
    func (c *Config) WriteTo(w io.Writer) (int64, error)
    ```

*   Do not repeat the names of variables passed as parameters.

    ```go
    // Bad:
    func OverrideFirstWithSecond(dest, source *Config) error
    ```

    ```go
    // Good:
    func Override(dest, source *Config) error
    ```

*   Do not repeat the names and types of the return values.

    ```go
    // Bad:
    func TransformToJSON(input *Config) *jsonconfig.Config
    ```

    ```go
    // Good:
    func Transform(input *Config) *jsonconfig.Config
    ```

When it is necessary to disambiguate functions of a similar name, it is
acceptable to include extra information.

```go
// Good:
func (c *Config) WriteTextTo(w io.Writer) (int64, error)
func (c *Config) WriteBinaryTo(w io.Writer) (int64, error)
```

<a id="function-name-conventions"></a>

#### Naming conventions

There are some other common conventions when choosing names for functions and
methods:

*   Functions that return something are given noun-like names.

    ```go
    // Good:
    func (c *Config) JobName(key string) (value string, ok bool)
    ```

    A corollary of this is that function and method names should
    [avoid the prefix `Get`](decisions#getters).

    ```go
    // Bad:
    func (c *Config) GetJobName(key string) (value string, ok bool)
    ```

*   Functions that do something are given verb-like names.

    ```go
    // Good:
    func (c *Config) WriteDetail(w io.Writer) (int64, error)
    ```

*   Identical functions that differ only by the types involved include the name
    of the type at the end of the name.

    ```go
    // Good:
    func ParseInt(input string) (int, error)
    func ParseInt64(input string) (int64, error)
    func AppendInt(buf []byte, value int) []byte
    func AppendInt64(buf []byte, value int64) []byte
    ```

    If there is a clear "primary" version, the type can be omitted from the name
    for that version:

    ```go
    // Good:
    func (c *Config) Marshal() ([]byte, error)
    func (c *Config) MarshalText() (string, error)
    ```

<a id="naming-doubles"></a>

### Test double and helper packages

There are several disciplines you can apply to [naming] packages and types that
provide test helpers and especially [test doubles]. A test double could be a
stub, fake, mock, or spy.

These examples mostly use stubs. Update your names accordingly if your code uses
fakes or another kind of test double.

[naming]: guide#naming
[test doubles]: https://abseil.io/resources/swe-book/html/ch13.html#basic_concepts

Suppose you have a well-focused package providing production code similar to
this:

```go
package creditcard

import (
    "errors"

    "path/to/money"
)

// ErrDeclined indicates that the issuer declines the charge.
var ErrDeclined = errors.New("creditcard: declined")

// Card contains information about a credit card, such as its issuer,
// expiration, and limit.
type Card struct {
    // omitted
}

// Service allows you to perform operations with credit cards against external
// payment processor vendors like charge, authorize, reimburse, and subscribe.
type Service struct {
    // omitted
}

func (s *Service) Charge(c *Card, amount money.Money) error { /* omitted */ }
```

<a id="naming-doubles-helper-package"></a>

#### Creating test helper packages

Suppose you want to create a package that contains test doubles for another.
We'll use `package creditcard` (from above) for this example:

One approach is to introduce a new Go package based on the production one for
testing. A safe choice is to append the word `test` to the original package name
("creditcard" + "test"):

```go
// Good:
package creditcardtest
```

Unless stated explicitly otherwise, all examples in the sections below are in
`package creditcardtest`.

<a id="naming-doubles-simple"></a>

#### Simple case

You want to add a set of test doubles for `Service`. Because `Card` is
effectively a dumb data type, similar to a Protocol Buffer message, it needs no
special treatment in tests, so no double is required. If you anticipate only
test doubles for one type (like `Service`), you can take a concise approach to
naming the doubles:

```go
// Good:
import (
    "path/to/creditcard"
    "path/to/money"
)

// Stub stubs creditcard.Service and provides no behavior of its own.
type Stub struct{}

func (Stub) Charge(*creditcard.Card, money.Money) error { return nil }
```

This is strictly preferable to a naming choice like `StubService` or the very
poor `StubCreditCardService`, because the base package name and its domain types
imply what `creditcardtest.Stub` is.

Finally, if the package is built with Bazel, make sure the new `go_library` rule
for the package is marked as `testonly`:

```build
# Good:
go_library(
    name = "creditcardtest",
    srcs = ["creditcardtest.go"],
    deps = [
        ":creditcard",
        ":money",
    ],
    testonly = True,
)
```

The approach above is conventional and will be reasonably well understood by
other engineers.

See also:

*   [Go Tip #42: Authoring a Stub for Testing](https://google.github.io/styleguide/go/index.html#gotip)

<a id="naming-doubles-multiple-behaviors"></a>

#### Multiple test double behaviors

When one kind of stub is not enough (for example, you also need one that always
fails), we recommend naming the stubs according to the behavior they emulate.
Here we rename `Stub` to `AlwaysCharges` and introduce a new stub called
`AlwaysDeclines`:

```go
// Good:
// AlwaysCharges stubs creditcard.Service and simulates success.
type AlwaysCharges struct{}

func (AlwaysCharges) Charge(*creditcard.Card, money.Money) error { return nil }

// AlwaysDeclines stubs creditcard.Service and simulates declined charges.
type AlwaysDeclines struct{}

func (AlwaysDeclines) Charge(*creditcard.Card, money.Money) error {
    return creditcard.ErrDeclined
}
```

<a id="naming-doubles-multiple-types"></a>

#### Multiple doubles for multiple types

But now suppose that `package creditcard` contains multiple types worth creating
doubles for, as seen below with `Service` and `StoredValue`:

```go
package creditcard

type Service struct {
    // omitted
}

type Card struct {
    // omitted
}

// StoredValue manages customer credit balances.  This applies when returned
// merchandise is credited to a customer's local account instead of processed
// by the credit issuer.  For this reason, it is implemented as a separate
// service.
type StoredValue struct {
    // omitted
}

func (s *StoredValue) Credit(c *Card, amount money.Money) error { /* omitted */ }
```

In this case, more explicit test double naming is sensible:

```go
// Good:
type StubService struct{}

func (StubService) Charge(*creditcard.Card, money.Money) error { return nil }

type StubStoredValue struct{}

func (StubStoredValue) Credit(*creditcard.Card, money.Money) error { return nil }
```

<a id="naming-doubles-local-variables"></a>

#### Local variables in tests

When variables in your tests refer to doubles, choose a name that most clearly
differentiates the double from other production types based on context. Consider
some production code you want to test:

```go
package payment

import (
    "path/to/creditcard"
    "path/to/money"
)

type CreditCard interface {
    Charge(*creditcard.Card, money.Money) error
}

type Processor struct {
    CC CreditCard
}

var ErrBadInstrument = errors.New("payment: instrument is invalid or expired")

func (p *Processor) Process(c *creditcard.Card, amount money.Money) error {
    if c.Expired() {
        return ErrBadInstrument
    }
    return p.CC.Charge(c, amount)
}
```

In the tests, a test double called a "spy" for `CreditCard` is juxtaposed
against production types, so prefixing the name may improve clarity.

```go
// Good:
package payment

import "path/to/creditcardtest"

func TestProcessor(t *testing.T) {
    var spyCC creditcardtest.Spy
    proc := &Processor{CC: spyCC}

    // declarations omitted: card and amount
    if err := proc.Process(card, amount); err != nil {
        t.Errorf("proc.Process(card, amount) = %v, want nil", err)
    }

    charges := []creditcardtest.Charge{
        {Card: card, Amount: amount},
    }

