    // A Watcher reports the health of some entity (usually a backend service).
    //
    // Watcher methods are safe for simultaneous use by multiple goroutines.
    type Watcher interface {
        // Watch sends true on the passed-in channel when the Watcher's
        // status has changed.
        Watch(changed chan<- bool) (unwatch func())

        // Health returns nil if the entity being watched is healthy, or a
        // non-nil error explaining why the entity is not healthy.
        Health() error
    }
    ```

    Why? Whether an API is safe for use by multiple goroutines is part of its
    contract.

<a id="documentation-conventions-cleanup"></a>

#### Cleanup

Document any explicit cleanup requirements that the API has. Otherwise, callers
won't use the API correctly, leading to resource leaks and other possible bugs.

Call out cleanups that are up to the caller:

```go
// Good:
// NewTicker returns a new Ticker containing a channel that will send the
// current time on the channel after each tick.
//
// Call Stop to release the Ticker's associated resources when done.
func NewTicker(d Duration) *Ticker

func (*Ticker) Stop()
```

If it is potentially unclear how to clean up the resources, explain how:

```go
// Good:
// Get issues a GET to the specified URL.
//
// When err is nil, resp always contains a non-nil resp.Body.
// Caller should close resp.Body when done reading from it.
//
//    resp, err := http.Get("http://example.com/")
//    if err != nil {
//        // handle error
//    }
//    defer resp.Body.Close()
//    body, err := io.ReadAll(resp.Body)
func (c *Client) Get(url string) (resp *Response, err error)
```

See also:

*   [GoTip #110: Don’t Mix Exit With Defer]

[GoTip #110: Don’t Mix Exit With Defer]: https://google.github.io/styleguide/go/index.html#gotip

<a id="documentation-conventions-errors"></a>

#### Errors

Document significant error sentinel values or error types that your functions
return to callers so that callers can anticipate what types of conditions they
can handle in their code.

```go
// Good:
package os

// Read reads up to len(b) bytes from the File and stores them in b. It returns
// the number of bytes read and any error encountered.
//
// At end of file, Read returns 0, io.EOF.
func (*File) Read(b []byte) (n int, err error) {
```

When a function returns a specific error type, correctly note whether the error
is a pointer receiver or not:

```go
// Good:
package os

type PathError struct {
    Op   string
    Path string
    Err  error
}

// Chdir changes the current working directory to the named directory.
//
// If there is an error, it will be of type *PathError.
func Chdir(dir string) error {
```

Documenting whether the values returned are pointer receivers enables callers to
correctly compare the errors using [`errors.Is`], [`errors.As`], and
[`package cmp`]. This is because a non-pointer value is not equivalent to a
pointer value.

**Note:** In the `Chdir` example, the return type is written as `error` rather
than `*PathError` due to
[how nil interface values work](https://go.dev/doc/faq#nil_error).

Document overall error conventions in the
[package's documentation](decisions#package-comments) when the behavior is
applicable to most errors found in the package:

```go
// Good:
// Package os provides a platform-independent interface to operating system
// functionality.
//
// Often, more information is available within the error. For example, if a
// call that takes a file name fails, such as Open or Stat, the error will
// include the failing file name when printed and will be of type *PathError,
// which may be unpacked for more information.
package os
```

Thoughtful application of these approaches can add
[extra information to errors](#error-extra-info) without much effort and help
callers avoid adding redundant annotations.

See also:

*   [Go Tip #106: Error Naming Conventions](https://google.github.io/styleguide/go/index.html#gotip)
*   [Go Tip #89: When to Use Canonical Status Codes as Errors](https://google.github.io/styleguide/go/index.html#gotip)

<a id="documentation-preview"></a>

### Preview

Go features a
[documentation server](https://pkg.go.dev/golang.org/x/pkgsite/cmd/pkgsite). It
is recommended to preview the documentation your code produces both before and
during the code review process. This helps to validate that the
[godoc formatting] is rendered correctly.

[godoc formatting]: #godoc-formatting

<a id="godoc-formatting"></a>

### Godoc formatting

[Godoc] provides some specific syntax to [format documentation].

*   A blank line is required to separate paragraphs:

    ```go
    // Good:
    // LoadConfig reads a configuration out of the named file.
    //
    // See some/shortlink for config file format details.
    ```

*   Test files can contain [runnable examples] that appear attached to the
    corresponding documentation in godoc:

    ```go
    // Good:
    func ExampleConfig_WriteTo() {
      cfg := &Config{
        Name: "example",
      }
      if err := cfg.WriteTo(os.Stdout); err != nil {
        log.Exitf("Failed to write config: %s", err)
      }
      // Output:
      // {
      //   "name": "example"
      // }
    }
    ```

*   Indenting lines by an additional two spaces formats them verbatim:

    ```go
    // Good:
    // Update runs the function in an atomic transaction.
    //
    // This is typically used with an anonymous TransactionFunc:
    //
    //   if err := db.Update(func(state *State) { state.Foo = bar }); err != nil {
    //     //...
    //   }
    ```

    Note, however, that it can often be more appropriate to put code in a
    runnable example instead of including it in a comment.

    This verbatim formatting can be leveraged for formatting that is not native
    to godoc, such as lists and tables:

    ```go
    // Good:
    // LoadConfig reads a configuration out of the named file.
    //
    // LoadConfig treats the following keys in special ways:
    //   "import" will make this configuration inherit from the named file.
    //   "env" if present will be populated with the system environment.
    ```

*   A single line that begins with a capital letter, contains no punctuation
    except parentheses and commas, and is followed by another paragraph, is
    formatted as a header:

    ```go
    // Good:
    // The following line is formatted as a heading.
    //
    // Using headings
    //
    // Headings come with autogenerated anchor tags for easy linking.
    ```

[Godoc]: https://pkg.go.dev/
[format documentation]: https://go.dev/doc/comment
[runnable examples]: decisions#examples

<a id="signal-boost"></a>

### Signal boosting

Sometimes a line of code looks like something common, but actually isn't. One of
the best examples of this is an `err == nil` check (since `err != nil` is much
more common). The following two conditional checks are hard to distinguish:

```go
// Good:
if err := doSomething(); err != nil {
    // ...
}
```

```go
// Bad:
if err := doSomething(); err == nil {
    // ...
}
```

You can instead "boost" the signal of the conditional by adding a comment:

```go
// Good:
if err := doSomething(); err == nil { // if NO error
    // ...
}
```

The comment draws attention to the difference in the conditional.

<a id="vardecls"></a>

## Variable declarations

<a id="vardeclinitialization"></a>

### Initialization

For consistency, prefer `:=` over `var` when initializing a new variable with a
non-zero value.

```go
// Good:
i := 42
```

```go
// Bad:
var i = 42
```

<a id="vardeclzero"></a>

### Declaring variables with zero values

The following declarations use the [zero value]:

```go
// Good:
var (
    coords Point
    magic  [4]byte
    primes []int
)
```

[zero value]: https://golang.org/ref/spec#The_zero_value

You should declare values using the zero value when you want to convey an empty
value that **is ready for later use**. Using composite literals with explicit
initialization can be clunky:

```go
// Bad:
var (
    coords = Point{X: 0, Y: 0}
    magic  = [4]byte{0, 0, 0, 0}
    primes = []int(nil)
)
```

A common application of zero value declaration is when using a variable as the
output when unmarshalling:

```go
// Good:
var coords Point
if err := json.Unmarshal(data, &coords); err != nil {
```

It is also okay to use the zero value in the following form when you need a
variable of a pointer type:

```go
// Good:
msg := new(pb.Bar) // or "&pb.Bar{}"
if err := proto.Unmarshal(data, msg); err != nil {
```

If you need a lock or other field that [must not be copied](decisions#copying)
in your struct, you can make it a value type to take advantage of zero value
initialization. It does mean that the containing type must now be passed via a
pointer and not a value. Methods on the type must take pointer receivers.

```go
// Good:
type Counter struct {
    // This field does not have to be "*sync.Mutex". However,
    // users must now pass *Counter objects between themselves, not Counter.
    mu   sync.Mutex
    data map[string]int64
}

// Note this must be a pointer receiver to prevent copying.
func (c *Counter) IncrementBy(name string, n int64)
```

It's acceptable to use value types for local variables of composites (such as
structs and arrays) even if they contain such uncopyable fields. However, if the
composite is returned by the function, or if all accesses to it end up needing
to take an address anyway, prefer declaring the variable as a pointer type at
the outset. Similarly, protobuf messages should be declared as pointer types.

```go
// Good:
func NewCounter(name string) *Counter {
    c := new(Counter) // "&Counter{}" is also fine.
    registerCounter(name, c)
    return c
}

var msg = new(pb.Bar) // or "&pb.Bar{}".
```

This is because `*pb.Something` satisfies [`proto.Message`] while `pb.Something`
does not.

```go
// Bad:
func NewCounter(name string) *Counter {
    var c Counter
    registerCounter(name, &c)
    return &c
}

var msg = pb.Bar{}
```

[`proto.Message`]: https://pkg.go.dev/google.golang.org/protobuf/proto#Message

> **Important:** Map types must be explicitly initialized before they can be
> modified. However, reading from zero-value maps is perfectly fine.
>
> For map and slice types, if the code is particularly performance sensitive and
> if you know the sizes in advance, see the [size hints](#vardeclsize) section.

<a id="vardeclcomposite"></a>

### Composite literals

The following are [composite literal] declarations:

```go
// Good:
var (
    coords   = Point{X: x, Y: y}
    magic    = [4]byte{'I', 'W', 'A', 'D'}
    primes   = []int{2, 3, 5, 7, 11}
    captains = map[string]string{"Kirk": "James Tiberius", "Picard": "Jean-Luc"}
)
```

You should declare a value using a composite literal when you know initial
