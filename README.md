# ansi-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

The escape-sequence layer of a terminal, with **no terminal under it**.
Four things, and nothing else:

- the VT/xterm state machine as a parser you feed one byte at a time
  and that hands back one typed action;
- the SGR attribute model — the flags, all three colour forms, and the
  arithmetic that turns a `CSI m` into a style and a style change back
  into the shortest `CSI m`;
- a writer that **builds** sequences into a byte buffer the caller
  owns, and never writes one;
- the queries a program asks a terminal, and the replies read back off
  the ordinary parser.

There is no grid, no cursor, no scrollback and no idea of what a
sequence means. `CSI 2 J` arrives as a dispatch on `J` with parameter
2, and what to erase is the caller's model to change.

```
novo pkg add ansi-nv
novo pkg build
novo test
```

## The one example that will work

A byte off a pty, parsed; and a style change, written. The whole
package is these two halves.

```novo
use std.str
use vtparse
use sgr
use seqwrite

fn main() [io]
    // Reading: ESC [ 2 ; 1 H — put the cursor on row 2, column 1.
    var p = vtparse.parser_new()
    for b in [0x1B, 0x5B, 0x32, 0x3B, 0x31, 0x48]
        let step = vtparse.feed_byte(p, b)
        p = step.parser
        match step.action
            AnsiCsiDispatch(0x48) =>
                let row = vtparse.param_at(step.parser, 0, 1)
                let col = vtparse.param_at(step.parser, 1, 1)
                println(str.from_int(row) + "," + str.from_int(col))
            _ => println("consumed")

    // Writing: the same move, plus a bold red run and its end, built
    // into one buffer the caller writes once.
    let plain = sgr.attrs_default()
    var red = plain
    red.bold = true
    red.fg = AnsiIndexed(1)

    var out = seqwrite.cursor_to([], 2, 1)
    out = seqwrite.sgr_change(out, plain, red)
    out = seqwrite.put_text(out, "alert")
    out = seqwrite.sgr_change(out, red, plain)
    // `out` is bytes.  Writing them is the program's job — see § The
    // layer, and why.
```

## The load-bearing interface

```novo ignore
pub fn feed_byte(p: AnsiParser, b: Int) -> AnsiStep
pub struct AnsiStep
    parser: AnsiParser         // the parser AFTER the byte
    action: AnsiAction         // at most one integer; no lists

pub fn param_at(p: AnsiParser, i: Int, fallback: Int) -> Int
```

**The parser is a value, and a dispatch action carries no parameters.**
Those two decisions are one decision, and everything else in the
package follows from it.

- An action is small — `AnsiCsiDispatch(final_byte)` and nothing more —
  so the hot path allocates nothing. A byte in, a variant out.
- The numbers the dispatch came with stay on the parser. Because
  `feed_byte` **returns** a parser instead of mutating one, the value it
  hands back still holds them: a caller may keep `step.parser`, dispatch
  on `step.action`, and read the parameters afterwards. A mutable
  parser cannot promise that, and every consumer of one ends up copying
  the parameters out defensively.
- `param_at` takes the fallback as an argument rather than defaulting to
  zero, because ECMA-48 does not have one default. CUU's omitted
  parameter means 1 and ED's means 0, and a parser that picked either
  is wrong half the time.
- A chunk may split **anywhere** — inside a parameter list, between the
  two bytes of a codepoint, halfway through an OSC payload. There is no
  "give me a whole sequence" entry point, because a read from a pty
  ends where the kernel says it ends.

The cost, stated: a caller that wants a whole chunk's worth of actions
as a list cannot have the parameters for free. `feed` gives it a list of
`AnsiCall`s, each pairing an action with an `AnsiParams` **copied** at
the moment of the dispatch — one allocation per dispatch, which is
exactly the difference between the two entry points and why a device
uses the byte one.

## The layer, and why

`core` — no effects. A terminal library is the one place where "a
library does not print" is hardest to keep and matters most, so nothing
here does: `seqwrite`'s functions take the `[u8]` they should append to
and return it, and the program decides what to do with the bytes.

That is not asceticism. It is what lets the same calls build a screen
update for a pty, a golden file for a test, a frame for a serial
console and a recording nobody will ever display — and it is what lets
a caller batch a whole frame into one buffer and write it **once**,
which is a correctness property rather than an optimisation: a screen
update split across two writes is one a reader can see tear.

**The device claim is made and built.** `tests/embedded_probe.nv` links
for `--target=nrf52-qemu`; the audit's `core-embedded` row is green. A
device driving a serial console needs exactly this package and can
afford nothing more, so `strict_limits()` is a real configuration and
not a gesture — its OSC ceiling is 128 bytes, because an OSC 52 paste
from a hostile peer is unbounded and on a microcontroller there is
nowhere to put it.

One honest qualification on that claim: what links today is the
**signatures**, because every body is a `todo()`. `AnsiParser`'s
parameter storage is `[Int]` and will have to become a fixed-capacity
buffer — heapless-nv's — before any of it runs on a device. That is a
known cost of the implementation step, written down here rather than
discovered in it.

## How this differs from novo-vte

[`novo-vte`](https://novo-lang.org/packages/novo-vte) is on the
registry already and parses the same sequences. They are not the same
package and neither replaces the other.

| | `novo-vte` | `ansi-nv` |
| --- | --- | --- |
| what it is | a terminal emulator's **model** | the escape-sequence **layer** |
| what a byte changes | a `Grid` — cells, cursor, scrollback, alt screen | nothing; it returns an action |
| layer | `host` | `core` |
| storage | two packed 64-bit words per cell, behind `std.array` handles | values |
| the writing half | none — novoterm and novomux each have their own | `seqwrite`, and it is half the package |
| runs on a device | no | yes |

`novo-vte` answers "what does the screen look like now". `ansi-nv`
answers "what did this byte say". A terminal emulator wants both, and
the natural shape after the split is novo-vte's grid **over** this
parser — which is the split this interface is written to make possible
and deliberately does not perform.

## Where the names come from, and the ones that were taken

Public type and variant names are unique across the whole assembly, so
a package's names have to be unique across the registry too.

| here | the obvious name | why not |
| --- | --- | --- |
| `AnsiParser` | `Parser` | novo-vte declares `Parser`, and a program with both is refused |
| `AnsiAction`, `AnsiState`, `AnsiFault` | `Action`, `State`, `Error` | `Error` is a standard-library trait; the other two are the kind of noun three packages will each want |
| `SgrAttrs`, `AnsiColor` | `Style`, `Color` | both are certain to collide, and a `Style` that meant "SGR only" would be the wrong promise anyway |
| `AnsiPrint`, `AnsiExecute`, … | `Print`, `Execute`, … | enum **variants** collide by bare name across the assembly |
| `AnsiTerminator` / `AnsiStringEnd` | one type for both | reporting what arrived and choosing what to send are different decisions; see `seqwrite.AnsiStringEnd` |
| module `vtparse` | `parser` | novo-vte ships `src/parser.nv`, and two dependencies may not both ship a module of one name |
| module `sgr`, `seqwrite`, `vtquery` | `style`, `writer`, `query` | all three are names another terminal package will want |

## The reference implementations

**xterm's `ctlseqs`** for what every sequence means, and for the DEC
private modes — it is the document a terminal is actually compatible
with. **Paul Williams' DEC parser** for the state machine's shape.
**ECMA-48** for the standard functions and the parameter grammar.
**ITU-T T.416** for the colon sub-parameter form, which is how a curly
underline and its colour arrive. **`vte`** (the Rust crate under
Alacritty) for the decision to report a dispatch rather than interpret
it, and **`ansi-term`** and **colorama** for the attribute vocabulary.

Deliberately left out, and where it went instead:

- **A grid, a cursor, a scrollback.** novo-vte has them today; tui-nv
  has the cell buffer a program draws into.
- **Terminal detection** — `TERM`, `COLORTERM`, `isatty`. All three read
  the environment, which is `[io]`, which is a `host` package.
  `sgr.downgrade` takes the depth as an argument for exactly that
  reason.
- **The low sixteen palette colours.** They are the user's theme and no
  library can know them. `sgr.indexed_to_rgb` answers for 16..255,
  where the values are fixed by the specification, and returns `None`
  below that.
- **base64.** OSC 52's payload needs it and `seqwrite.clipboard_write`
  takes it already encoded, because a `core` package that grew an
  encoder for one sequence would carry it for every consumer that never
  writes a clipboard. base64-nv is a row of its own.
- **Sixel, ReGIS, and the DCS payload formats.** The parser reports DCS
  bytes; what they mean is an image decoder's question.
- **Key and mouse decoding.** That is the input direction, it is a
  different state machine, and it is `keymap-nv`.

## Status

Every function is `todo()`. Three suites, all red, all for the same
reason — every assertion reaches `not implemented: ansi-nv.<fn>`, which
is the expected result until the bodies land.

```
novo test --isolate tests/vtparse_tests.nv   # the state machine, chunk splits included
novo test --isolate tests/sgr_tests.nv       # the attribute model, the writer, the queries
novo test --isolate tests/surface_tests.nv   # the rest of the surface, called once each
```

`novo doc` renders and its six examples compile.
