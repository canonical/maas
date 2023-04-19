# MAAS Go style guide

This document represents a set of idiomatic conventions in Go code that MAAS
contributors should follow. A lot of these are general guidelines for Go, while
others extend upon external resources and popular practices among Go community:

1. [Effective Go](https://golang.org/doc/effective_go.html)
2. [Go Common Mistakes](https://github.com/golang/go/wiki/CommonMistakes)
3. [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
4. [Go Style Guide](https://google.github.io/styleguide/go/index#about)
5. [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md)

This document is not exhaustive and will grow over time. Where the style guide
is contrary to common sense or there is a better way of doing things, it should
be discussed within MAAS team and the document should be updated accordingly.

# WHY?

Code can have a long lifetime; the effort to maintain and adapt it in the future
can be much larger than the original effort to produce the first version of it.
To keep the codebase readable and understandable, we must be consistent and
refer to a set of applicable conventions.

Consistent code is easier to maintain, it requires less cognitive overhead, and
is easier to migrate or update as new conventions emerge or classes of bugs are
fixed.

# HOW?

This document addresses two main topics: [coding style](#style) and
[best practices](#best-practices). The former aims to ensure that our codebase
remains easy to read and understand, while the latter focuses on writing code
that is reliable and performs well.

# Style

## Naming conventions

To a large extent we follow
[golang naming conventions](https://go.dev/doc/effective_go#names):

- Names should strike a balance between concision and clarity, where for a local
  variable more weight might be put on concision while for an exported name
  clarity might have a larger weight.

- Consistency is important in a somewhat large and long lived project, it is
  always a good idea to check whether there are similar entities or concepts in
  the code from which to borrow terminology or naming patterns, especially in
  the neighbourhood of the new code. For example when using a verb in a method
  name, it is good to check whether the verb is used for similar behaviour in
  other names or some other verb is more common for the usage.

### Underscores

Names in Go should in general not contain underscores. There are three
exceptions to this principle:

- Package names that are only imported by generated code may contain
  underscores. See package names for more detail around how to choose multi-word
  package names.

- Test, Benchmark and Example function names within `*_test.go` files may
  include underscores.

- Low-level libraries that interoperate with the operating system or `cgo` may
  reuse identifiers, as is done in
  [syscall](https://pkg.go.dev/syscall#pkg-constants). This is expected to be
  very rare in most codebases.

### Receiver names

[Receiver](https://golang.org/ref/spec#Method_declarations) variable names must
be:

- Short (usually one or two letters in length)
- Abbreviations for the type itself
- Applied consistently to every receiver for that type

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
func (tray Tray)
func (info *ResearchInfo)
func (this *ReportWriter)
func (self *Scanner)
```

</td><td>

```go
func (t Tray)
func (ri *ResearchInfo)
func (w *ReportWriter)
func (s *Scanner)
```

</td></tr>
</tbody></table>

### Constant names

We follow the Go community's convention and use
[MixedCaps](https://google.github.io/styleguide/go/guide#mixed-caps).
[Exported](https://tour.golang.org/basics/3) constants start with uppercase,
while unexported constants start with lowercase.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
const MAX_PACKET_SIZE = 512
const kMaxBufferSize = 1024
const KMaxUsersPergroup = 500
```

</td><td>

```go
const MaxPacketSize = 512
const (
    ExecuteBit = 1 << iota
    WriteBit
    ReadBit
)
```

</td></tr>
</tbody></table>

Name constants based on their role, not their values. If a constant does not
have a role apart from its value, then it is unnecessary to define it as a
constant.

<table>
<thead><tr><th>Bad</th></tr></thead>
<tbody>
<tr><td>

```go
const FortyTwo = 42
const (
    UserNameColumn = "username"
    GroupColumn    = "group"
)
```

</td></tr>
</tbody></table>

### Function signatures

We try to follow certain kind of ordering for parameters of functions and
methods:

- `context.Context` if it makes sense for the function implementation
- Long lived/ambient objects
- The main entities the function or method operates on
- Any optional and ancillary parameters in some order of relevance

Return parameters should be in some order of importance with `error` being last
as per Go conventions. Consistency is important, so parallel/similar
functions/methods should try to have the same/any shared parameters in the same
order.

We do not recommend using named result parameters as
[naked returns](https://go.dev/tour/basics/7) can lead to bugs and also make
code harder to follow.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
func (f *Foo) Temperature() (temp float64, err error) {
    ...
    ...
    if ... {
        // unclear what exactly is returned
        // also unclear what values of temp and err could be returned
        return
    }
    ...
}
```

</td><td>

```go
func (f *Foo) Temperature() (float64, error) {
    ...
    ...
    if ... {
        // here you have to be explicit with values returned
        // Otherwise you will get a compile-time error
        // ./prog.go: not enough return values
        //   have ()
        //   want (int, int)
        return 0, nil
    }
    ...
}
```

</td></tr>
</tbody></table>

### Getters

Function and method names should not use a `Get` or `get` prefix, unless the
underlying concept uses the word “get” (e.g. an HTTP GET). Prefer starting the
name with the noun directly, for example use `Counts` over `GetCounts`.

If the function involves performing a complex computation or executing a remote
call, a different word like `Compute` or `Fetch` can be used in place of `Get`,
to make it clear to a reader that the function call may take time and could
block or fail.

### Repetition

A piece of Go source code should avoid unnecessary repetition. One common source
of this is repetitive names, which often include unnecessary words or repeat
their context or type. Code itself can also be unnecessarily repetitive if the
same or a similar code segment appears multiple times in close proximity.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
widget.NewWidget
widget.NewWidgetWithName
db.LoadFromDatabase
```

</td><td>

```go
widget.New
widget.NewWithName
db.Load
```

</td></tr>
</tbody></table>

The compiler always knows the type of a variable, and in most cases it is also
clear to the reader what type a variable is by how it is used. It is only
necessary to clarify the type of a variable if its value appears twice in the
same scope.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
var numUsers int
var nameString string
var primaryProject *Project
```

</td><td>

```go
var users int
var name string
var primary *Project
```

</td></tr>
</tbody></table>

## Reduce Nesting

Code should reduce nesting where possible by handling error cases/special
conditions first and returning early or continuing the loop. Reduce the amount
of code that is nested multiple levels.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
for _, v := range data {
  if v.Foo == 1 {
    v = process(v)
    if err := v.Call(); err == nil {
      v.Send()
    } else {
      return err
    }
  } else {
    log.Printf("Invalid v: %v", v)
  }
}
```

</td><td>

```go
for _, v := range data {
  if v.Foo != 1 {
    log.Printf("Invalid v: %v", v)
    continue
  }

  v = process(v)
  if err := v.Call(); err != nil {
    return err
  }
  v.Send()
}
```

</td></tr>
</tbody></table>

## Unnecessary Else

If a variable is set in both branches of an `if`, it can be replaced with a
single `if`. However, this is not recommended when allocating memory or calling
heavy initializers. Note, this only when initializing the variable is cheap and
has no side-effects. (true for basic types, false when allocating memory or
calling heavy initializers)

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
var a int

if b {
  a = 100
} else {
  a = 10
}
```

</td><td>

```go
a := 10
if b {
  a = 100
}
```

</td></tr>
</tbody></table>

## Local Variable Declarations

Short variable declarations (`:=`) should be used if a variable is being set to
some value explicitly.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
var s = "foo"
```

</td><td>

```go
s := "foo"
```

</td></tr>
</tbody></table>

However, the default value is clearer when the var keyword is used.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
i := 0
t := Type{}
```

</td><td>

```go
var i int
var t Type
```

</td></tr>
</tbody></table>

### Declaring Empty Slices

These two approaches on declaring a slice are functionally equivalent. Their
`len` and `cap` are both zero. But declaring a `nil` slice makes possible to
differentiate between a collection that doesn't exist and collection that is
empty.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
s := []string{}
s == nil // false
```

</td><td>

```go
var s []string
s == nil // true
```

</td></tr>
</tbody></table>

## Comments

Ideally all exported names should have doc comments for them following
[Go conventions](https://go.dev/doc/comment).

Inline code comments should usually address non-obvious or unexpected parts of
the code. Repeating what the code does is not usually very informative.

Code comments should:

- Address the why something is done
- Clarify the more abstract impact of the low-level manipulation in the code

It might be appropriate and useful also to give proper doc comments even to
complex unexported helpers.

## Start Enums at One

The standard way of introducing enumerations in Go is to declare a custom type
and a `const` group with `iota`. Since variables have a 0 default value, you
should usually start your enums on a non-zero value.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
type Color int

const (
  Red Color = iota
  Green
  Blue
)

// Red=0, Green=1, Blue=2
```

</td><td>

```go
type Color int

const (
  Red Color = iota + 1
  Green
  Blue
)

// Red=1, Green=2, Blue=3
```

</td></tr>
</tbody></table>

There are cases where using the zero value makes sense, for example when the
zero value case is the desirable default behavior.

```go
type LogOutput int

const (
    LogToStdout LogOutput = iota
    LogToFile
    LogToRemote

    LogDefault = LogToStdout
)

// LogToStdout=0, LogToFile=1, LogToRemote=2
```

# Best practices

## Building strings

Each time the `+` operator is used, Go creates a new string and copies the
contents of the previous strings into the new string, which can be
time-consuming and memory-intensive.

So if you need to build a string in a loop, consider using
[strings.Builder](https://pkg.go.dev/strings#Builder)

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
var s string

for i := 0; i < 10; i++ {
	s += strconv.Itoa(i)
}
```

</td><td>

```go
b = strings.Builder{}

for i := 0; i < 10; i++ {
	builder.WriteString(strconv.Itoa(i))
}

builder.String()
```

</td></tr>
</tbody></table>

## Prefer strconv over fmt

When converting primitives to/from strings in a hot path,
[strconv](https://pkg.go.dev/strconv) is almost always faster than
[fmt](https://pkg.go.dev/fmt). When in doubt, do the benchmark.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
for i := 0; i < b.N; i++ {
  s := fmt.Sprint(rand.Int())
}
```

</td><td>

```go
for i := 0; i < b.N; i++ {
  s := strconv.Itoa(rand.Int())
}
```

</td></tr>
<tr><td>

```plain
BenchmarkFmtSprint-4    143 ns/op    2 allocs/op
```

</td><td>

```plain
BenchmarkStrconv-4    64.2 ns/op    1 allocs/op
```

</td></tr>
</tbody></table>

## Prefer Specifying Container Capacity

Specify container capacity where possible in order to allocate memory for the
container up front. This minimizes subsequent allocations (by copying and
resizing of the container) as elements are added.

### Specifying Map Capacity Hints

Where possible, provide capacity hints when initializing maps with `make()`.

```go
make(map[T1]T2, hint)
```

Providing a capacity hint to `make()` tries to right-size the map at
initialization time, which reduces the need for growing the map and allocations
as elements are added to the map.

Note that, unlike slices, map capacity hints do not guarantee complete,
preemptive allocation, but are used to approximate the number of hashmap buckets
required. Consequently, allocations may still occur when adding elements to the
map, even up to the specified capacity.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
// `m` is created without a size hint; there may be more
// allocations at assignment time.
m := make(map[string]os.FileInfo)

files, _ := os.ReadDir("./files")
for _, f := range files {
    m[f.Name()] = f
}
```

</td><td>

```go
files, _ := os.ReadDir("./files")

// `m` is created with a size hint; there may be fewer
// allocations at assignment time.
m := make(map[string]os.DirEntry, len(files))
for _, f := range files {
    m[f.Name()] = f
}
```

</td></tr>
</tbody></table>

### Specifying Slice Capacity

Where possible, provide capacity hints when initializing slices with `make()`,
particularly when appending.

```go
make([]T, length, capacity)
```

Unlike maps, slice capacity is not a hint: the compiler will allocate enough
memory for the capacity of the slice as provided to `make()`, which means that
subsequent `append()` operations will incur zero allocations (until the length
of the slice matches the capacity, after which any appends will require a resize
to hold additional elements).

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
for n := 0; n < b.N; n++ {
  data := make([]int, 0)
  for k := 0; k < size; k++{
    data = append(data, k)
  }
}
```

</td><td>

```go
for n := 0; n < b.N; n++ {
  data := make([]int, 0, size)
  for k := 0; k < size; k++{
    data = append(data, k)
  }
}
```

</td></tr>
<tr><td>

```plain
BenchmarkBad-4    100000000    2.48s
```

</td><td>

```plain
BenchmarkGood-4   100000000    0.21s
```

</td></tr>
</tbody></table>

## Errors

#TODO: errors wrap, error types, %w, errors chan

## Testing

Depending on a situation you might want to put your `*_test.go` files into
`foo_test` package (black-box testing) or `foo` package (white-box testing).

Black-box testing will ensure you're only using the exported identifiers.
White-box Testing is ood for unit tests that require access to non-exported
variables, functions, and methods.

We definitely prefer to write black-box tests, but there might be helpers and
unexported details that sometimes warrant testing, in which case we use
re-assignment or type aliasing in conventional `export_test.go` or
`export_foo_test.go` files in the package under test, to get access to what we
need to test. Here is a good
[example](https://go.dev/src/net/http/export_test.go) from the standard library.
This is usually needed if there is algorithmic complexity or error handling
behaviour that is hard to explore through the exported API, or is important to
illustrate the chosen behaviour of the helper in itself.

#TODO: mocks (mockgen), testify, fixtures, integration tests

## Table-driven tests

Table-driven tests are easy to read and maintain. This format also makes it easy
to add or remove test cases, as well as modify existing ones.

By using a single test function that takes input and expected output from a
table, you can avoid writing repetitive test code for each combination.

While there are several techiques to declare test cases, the prefered way is to
use map literal syntax. While

One advantage of using maps is that the "name" of each test case can simply be
the map key. But more importantly, map iteration order is undefined, hence
testing order doesn't impact results.

```go
package main

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestFoo(t *testing.T) {
	testcases := map[string]struct {
		input string
		want  string
	}{
		"test a": {input: "foo", want: "foo"},
		"test b": {input: "foo", want: "bar"},
		"test c": {input: "foo", want: "buz"},
	}
	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			got := Foo(tc.input)
			require.Equal(t, tc.want, got)
		})
	}
}
```

## Handle Type Assertion Failures

The single return value form of a
[type assertion](https://golang.org/ref/spec#Type_assertions) will panic on an
incorrect type. Therefore, always use the "comma ok" idiom.

<table>
<thead><tr><th>Bad</th><th>Good</th></tr></thead>
<tbody>
<tr><td>

```go
t := i.(string)
```

</td><td>

```go
t, ok := i.(string)
if !ok {
  // handle the error gracefully
}
```

</td></tr>
</tbody></table>

## Functional Options

When it comes to creating an extensible API in Go, there are limited options
available. One common approach is to use a configuration struct that allows for
the addition of new fields in a backward-compatible manner. However, providing
default values for these fields might be confusing and passing around a
structure "for all options" is not perfect.

Use this pattern for optional arguments in constructors and other public APIs
that you foresee needing to expand, especially if you already have three or more
arguments on those functions.

```go
type Relay struct {
	server net.UDPAddr // DHCP server address

	riface net.Interface
	riaddr net.IP
}

type RelayOption func(r *Relay)

func WithRemoteInterface(riface net.Interface, riaddr net.IP) RelayOption {
   return func(r *Relay) {
      r.riface = riface
      r.riaddr = riaddr
   }
}

func NewRelay(server net.UDPAddr, opts ...RelayOption) *Relay {
	r := &Relay{
		server: server,
	}

	for _, opt := range opts {
		opt(r)
	}

	return r
}

// ...

func main() {
	relay := NewRelay(dhcpServer,
		WithRemoteInterface(...),
	)
}
```

# Linting

We use [golangci-lint](https://github.com/golangci/golangci-lint) which has
various linters available.

Linters can catch most common issues and help to maintain code quality. However,
we should use linters judiciously and only enable those that are truly helpful
in improving code quality, rather than blindly enforcing rules that may not make
sense in a particular context.
