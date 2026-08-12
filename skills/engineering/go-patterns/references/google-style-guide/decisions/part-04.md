> generally not worth using the `if`-with-initializer style. In these cases, it
> is usually better to move the declaration out and use a standard `if`
> statement:
>
> ```go
> // Good:
> x, err := f()
> if err != nil {
>   // error handling
>   return
> }
> // lots of code that uses x
> // across multiple lines
> ```
>
> ```go
> // Bad:
> if x, err := f(); err != nil {
>   // error handling
>   return
> } else {
>   // lots of code that uses x
>   // across multiple lines
> }
> ```

See [Go Tip #1: Line of Sight] and
[TotT: Reduce Code Complexity by Reducing Nesting](https://testing.googleblog.com/2017/06/code-health-reduce-nesting-reduce.html)
for more details.

[Go Tip #1: Line of Sight]: https://google.github.io/styleguide/go/index.html#gotip

<a id="language"></a>

## Language

<a id="literal-formatting"></a>

### Literal formatting

Go has an exceptionally powerful [composite literal syntax], with which it is
possible to express deeply-nested, complicated values in a single expression.
Where possible, this literal syntax should be used instead of building values
field-by-field. The `gofmt` formatting for literals is generally quite good, but
there are some additional rules for keeping these literals readable and
maintainable.

[composite literal syntax]: https://golang.org/ref/spec#Composite_literals

<a id="literal-field-names"></a>

#### Field names

Struct literals must specify **field names** for types defined outside the
current package.

*   Include field names for types from other packages.

    ```go
    // Good:
    // https://pkg.go.dev/encoding/csv#Reader
    r := csv.Reader{
      Comma: ',',
      Comment: '#',
      FieldsPerRecord: 4,
    }
    ```

    The position of fields in a struct and the full set of fields (both of which
    are necessary to get right when field names are omitted) are not usually
    considered to be part of a struct's public API; specifying the field name is
    needed to avoid unnecessary coupling.

    ```go
    // Bad:
    r := csv.Reader{',', '#', 4, false, false, false, false}
    ```

*   For package-local types, field names are optional.

    ```go
    // Good:
    okay := Type{42}
    also := internalType{4, 2}
    ```

    Field names should still be used if it makes the code clearer, and it is
    very common to do so. For example, a struct with a large number of fields
    should almost always be initialized with field names.

    <!-- TODO: Maybe a better example here that doesn't have many fields. -->

    ```go
    // Good:
    okay := StructWithLotsOfFields{
      field1: 1,
      field2: "two",
      field3: 3.14,
      field4: true,
    }
    ```

<a id="literal-matching-braces"></a>

#### Matching braces

The closing half of a brace pair should always appear on a line with the same
amount of indentation as the opening brace. One-line literals necessarily have
this property. When the literal spans multiple lines, maintaining this property
keeps the brace matching for literals the same as brace matching for common Go
syntactic constructs like functions and `if` statements.

The most common mistake in this area is putting the closing brace on the same
line as a value in a multi-line struct literal. In these cases, the line should
end with a comma and the closing brace should appear on the next line.

```go
// Good:
good := []*Type{{Key: "value"}}
```

```go
// Good:
good := []*Type{
    {Key: "multi"},
    {Key: "line"},
}
```

```go
// Bad:
bad := []*Type{
    {Key: "multi"},
    {Key: "line"}}
```

```go
// Bad:
bad := []*Type{
    {
        Key: "value"},
}
```

<a id="literal-cuddled-braces"></a>

#### Cuddled braces

Dropping whitespace between braces (aka "cuddling" them) for slice and array
literals is only permitted when both of the following are true.

*   The [indentation matches](#literal-matching-braces)
*   The inner values are also literals or proto builders (i.e. not a variable or
    other expression)

```go
// Good:
good := []*Type{
    { // Not cuddled
        Field: "value",
    },
    {
        Field: "value",
    },
}
```

```go
// Good:
good := []*Type{{ // Cuddled correctly
    Field: "value",
}, {
    Field: "value",
}}
```

```go
// Good:
good := []*Type{
    first, // Can't be cuddled
    {Field: "second"},
}
```

```go
// Good:
okay := []*pb.Type{pb.Type_builder{
    Field: "first", // Proto Builders may be cuddled to save vertical space
}.Build(), pb.Type_builder{
    Field: "second",
}.Build()}
```

```go
// Bad:
bad := []*Type{
    first,
    {
        Field: "second",
    }}
```

<a id="literal-repeated-type-names"></a>

#### Repeated type names

Repeated type names may be omitted from slice and map literals. This can be
helpful in reducing clutter. A reasonable occasion for repeating the type names
explicitly is when dealing with a complex type that is not common in your
project, when the repetitive type names are on lines that are far apart and can
remind the reader of the context.

```go
// Good:
good := []*Type{
    {A: 42},
    {A: 43},
}
```

```go
// Bad:
repetitive := []*Type{
    &Type{A: 42},
    &Type{A: 43},
}
```

```go
// Good:
good := map[Type1]*Type2{
    {A: 1}: {B: 2},
    {A: 3}: {B: 4},
}
```

```go
// Bad:
repetitive := map[Type1]*Type2{
    Type1{A: 1}: &Type2{B: 2},
    Type1{A: 3}: &Type2{B: 4},
}
```

**Tip:** If you want to remove repetitive type names in struct literals, you can
run `gofmt -s`.

<a id="literal-zero-value-fields"></a>

#### Zero-value fields

[Zero-value] fields may be omitted from struct literals when clarity is not lost
as a result.

Well-designed APIs often employ zero-value construction for enhanced
readability. For example, omitting the three zero-value fields from the
following struct draws attention to the only option that is being specified.

[Zero-value]: https://golang.org/ref/spec#The_zero_value

```go
// Bad:
import (
  "github.com/golang/leveldb"
  "github.com/golang/leveldb/db"
)

ldb := leveldb.Open("/my/table", &db.Options{
    BlockSize: 1<<16,
    ErrorIfDBExists: true,

    // These fields all have their zero values.
    BlockRestartInterval: 0,
    Comparer: nil,
    Compression: nil,
    FileSystem: nil,
    FilterPolicy: nil,
    MaxOpenFiles: 0,
    WriteBufferSize: 0,
    VerifyChecksums: false,
})
```

```go
// Good:
import (
  "github.com/golang/leveldb"
  "github.com/golang/leveldb/db"
)

ldb := leveldb.Open("/my/table", &db.Options{
    BlockSize: 1<<16,
    ErrorIfDBExists: true,
})
```

Structs within table-driven tests often benefit from [explicit field names],
especially when the test struct is not trivial. This allows the author to omit
the zero-valued fields entirely when the fields in question are not related to
the test case. For example, successful test cases should omit any error-related
or failure-related fields. In cases where the zero value is necessary to
understand the test case, such as testing for zero or `nil` inputs, the field
names should be specified.

[explicit field names]: #literal-field-names

**Concise**

```go
tests := []struct {
    input      string
    wantPieces []string
    wantErr    error
}{
    {
        input:      "1.2.3.4",
        wantPieces: []string{"1", "2", "3", "4"},
    },
    {
        input:   "hostname",
        wantErr: ErrBadHostname,
    },
}
```

**Explicit**

```go
tests := []struct {
    input    string
    wantIPv4 bool
    wantIPv6 bool
    wantErr  bool
}{
    {
        input:    "1.2.3.4",
        wantIPv4: true,
        wantIPv6: false,
    },
    {
        input:    "1:2::3:4",
        wantIPv4: false,
        wantIPv6: true,
    },
    {
        input:    "hostname",
        wantIPv4: false,
        wantIPv6: false,
        wantErr:  true,
    },
}
```

<a id="nil-slices"></a>

### Nil slices

For most purposes, there is no functional difference between `nil` and the empty
slice. Built-in functions like `len` and `cap` behave as expected on `nil`
slices.

```go
// Good:
import "fmt"

var s []int         // nil

fmt.Println(s)      // []
fmt.Println(len(s)) // 0
fmt.Println(cap(s)) // 0
for range s {...}   // no-op

s = append(s, 42)
fmt.Println(s)      // [42]
```

If you declare an empty slice as a local variable (especially if it can be the
source of a return value), prefer the nil initialization to reduce the risk of
bugs by callers.

```go
// Good:
var t []string
```

```go
// Bad:
t := []string{}
```

Do not create APIs that force their clients to make distinctions between nil and
the empty slice.

```go
// Good:
// Ping pings its targets.
// Returns hosts that successfully responded.
func Ping(hosts []string) ([]string, error) { ... }
```

