# ansi-nv

A terminal is driven by **escape sequences**: short runs of bytes that
begin with the ESC character and tell the terminal to move the cursor,
erase part of the screen, or change the colour of the text that comes
after them. The grammar and the standard sequences are specified in
[ECMA-48](https://ecma-international.org/publications-and-standards/standards/ecma-48/),
and the ones terminals in use actually accept are documented in
[xterm's `ctlseqs`](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).
This package is that layer on its own, with no terminal under it.
Seven packages on the registry are built on it:
[termios-nv](https://novo-lang.org/packages/termios-nv),
[tui-nv](https://novo-lang.org/packages/tui-nv),
[clipboard-nv](https://novo-lang.org/packages/clipboard-nv),
[table-nv](https://novo-lang.org/packages/table-nv),
[progress-nv](https://novo-lang.org/packages/progress-nv),
[logging-nv](https://novo-lang.org/packages/logging-nv) and
[logging-core-nv](https://novo-lang.org/packages/logging-core-nv).

## What it is

A stream from a terminal, or to one, is text with escape sequences mixed
into it. ECMA-48 section 5.4 gives the shape of the most common kind, a
**control sequence**: the two bytes `ESC [`, called CSI; then the
**parameters**, decimal numbers separated by semicolons; then zero or
more **intermediate** bytes; then one **final** byte, which says which
function this is. `ESC [ 2 ; 1 H` is a control sequence whose final byte
is `H` and whose parameters are 2 and 1. It puts the cursor on row 2,
column 1.

Two other kinds carry a payload rather than numbers. An **OSC**
(operating system command) begins `ESC ]` and carries a numeric code and
semicolon-separated fields: the window title and the clipboard travel
this way. A **DCS** (device control string) begins `ESC P` and carries a
format of its own, such as a Sixel image. Both end with a **string
terminator**: either ST, the two bytes `ESC \`, or the single byte BEL,
which xterm accepts and most programs send.

**SGR** (select graphic rendition) is the control sequence with final
byte `m`. It is the odd one out, because it does not do anything: it
changes what the text after it will look like. `ESC [ 1 m` turns on
bold. A terminal holds one set of these **attributes** — bold, italic,
underline, a foreground colour, a background colour and six more flags —
and every character written takes the attributes in force when it was
written.

This package parses those sequences and builds them, and does nothing
else. There is no grid of cells, no cursor, no scrollback, and no notion
of what a sequence means. `ESC [ 2 J` arrives as a dispatch on the final
byte `J` with parameter 2, and deciding what to erase is the caller's
business. Nothing here performs input or output: incoming bytes are
arguments, and outgoing sequences are appended to a `[u8]` the caller
owns and writes itself.

The parser is a value that lives in the caller's stack frame. `feed`
takes a parser and one byte and returns the parser after it. What the
byte asked for is read off that parser with `action_of`, and so are the
numbers the sequence came with, through `param_at` and its neighbours.
Feeding a byte allocates nothing.

The parser holds its parameters in buffers of a fixed size, so the
package sets a capacity and the caller sets a ceiling inside it. A
ceiling above the capacity is lowered to it, and `limits_of` answers
what the parser is enforcing.

| Limit | Capacity | `default_limits` | `strict_limits` |
| --- | --- | --- | --- |
| Parameters in one sequence | 16 | 16 | 8 |
| Sub-parameters in one colon group | 16 | 6 | 4 |
| Entries in one sequence, a sub-parameter counting as one | 16 | 16 | 16 |
| Largest value one parameter may hold | 65534 | 65534 | 4095 |
| Intermediate bytes kept | 2 | 2 | 2 |
| Bytes of OSC or DCS payload reported | none | 4096 | 128 |

## Install

```
novo pkg add ansi-nv
```

## Example

One program, both directions: a control sequence read a byte at a time,
and a styled run of text built into a buffer.

```novo
use std.str
use vtparse
use sgr
use seqwrite

fn main() [io]
    // A fresh parser, resting between sequences.
    var p = vtparse.parser_new()

    // The bytes of ESC [ 2 ; 1 H, fed one at a time, as they would
    // arrive from a terminal.
    for b in [0x1B, 0x5B, 0x32, 0x3B, 0x31, 0x48]
        // Keep the parser that comes back; it is the one to feed next.
        p = vtparse.feed(p, b)
        match vtparse.action_of(p)
            // Final byte 0x48 is `H`: put the cursor somewhere.
            AnsiCsiDispatch(0x48) =>
                // The parameters are on the parser the dispatch came
                // with. 1 is the fallback for an omitted one.
                let row = vtparse.param_at(p, 0, 1)
                let col = vtparse.param_at(p, 1, 1)
                println(str.from_int(row) + "," + str.from_int(col))
            // Every other byte of the sequence was consumed silently.
            _ => println("consumed")

    // The attributes a terminal starts in: its own colours, no styling.
    let plain = sgr.attrs_default()
    // The same, with bold on and the foreground set to colour 1, red.
    // SGR 1 is bold and SGR 31 is red, so folding the two on is the
    // same thing a terminal does when it reads `ESC [ 1 ; 31 m`.
    let red = sgr.apply_sgr_one(sgr.apply_sgr_one(plain, 1), 31)

    // Build the sequences into one buffer, starting from an empty list.
    var out = seqwrite.cursor_to([], 2, 1)
    // The shortest sequence that gets from `plain` to `red`.
    out = seqwrite.sgr_change(out, plain, red)
    out = seqwrite.put_text(out, "alert")
    // And back, so the text after this run is unstyled.
    out = seqwrite.sgr_change(out, red, plain)
    // `out` is bytes. Writing them is the program's job.
```

Build and test with `novo pkg build` and `novo test`.

## What the package contains

| Module | Contents |
| --- | --- |
| `vtcore` | The state machine itself: the parser value, the twelve states it rests in, the action reported for one byte, the limits, and the readers for the parameters, the sub-parameters, the intermediates and the private marker. It speaks integers alone, allocates nothing, and is the module that builds for a microcontroller. |
| `vtparse` | The same machine for a program with a heap. `action_of` answers an enum, `state_of` answers an enum, `params_of` copies a dispatch's numbers into a value that outlives the parser, and `drain` runs a whole chunk. The readers are forwarded, so a program on a host uses this module alone. |
| `sgr` | The attribute model: one struct holding everything SGR can say about a character, the colour type covering all three forms, the fold of a parameter list onto a set of attributes, and the inverse. |
| `seqwrite` | The writer: cursor movement, erasing, scrolling, insertion and deletion, the named terminal modes, text, OSC strings, and three escape hatches for sequences this module does not name. Every function appends to a caller's buffer and returns it. |
| `vtquery` | The questions a program can ask a terminal and the answers, as two halves: one builds the question, the other reads a reply out of an ordinary control sequence dispatch. |

## How to choose an entry point

**`vtparse.feed` takes one byte and allocates nothing.** It is the
entry point everything else is written over, and the cheaper of the two.
The parameters of a dispatch are read off the parser it returned.

**`vtcore.feed` is the same function without the enums.** A program with
no heap allocator calls it and reads the action as an integer. A program
on a host may call either, on any byte.

**`vtparse.drain` takes a whole chunk and answers a list.** Each entry
pairs an action with a copy of the parameters it fired with, so a caller
can look at them after the parser has moved on. The copy costs one
allocation per action.

**`seqwrite`'s named functions cover the sequences with names.**
`cursor_to`, `erase_display`, `set_mode` and the rest take the arguments
the sequence takes and get the spelling right.

**`seqwrite.csi` and `seqwrite.esc` write the ones with no name.** The
DEC private space is open-ended. These two take the private marker, the
parameters, the intermediates and the final byte directly.

**`seqwrite.csi_params` writes a sequence that has colon groups in it.**
`csi` takes the parameters as a list of numbers separated by semicolons,
which has nowhere to put a colon. `csi_params` takes the parser's own
`AnsiParams`, so a sequence this package read can be written back out
byte for byte. Rule 14 below says which sequences need it.

## The rules a user needs

1. **A dispatch action carries its final byte and nothing else.** The
   parameters stay on the parser `feed` returned. Read them with
   `param_at`, `sub_at`, `intermediate_at` and `private_marker_of`
   before feeding the next byte, or copy them out with `params_of`.
2. **`param_at` takes the fallback for an omitted parameter as an
   argument, because there is no single default.** ECMA-48 section 5.4.2
   says an omitted parameter takes the default given in the definition
   of that particular function. CUU's default is 1 and ED's is 0. A
   caller that passed the same fallback everywhere would be wrong half
   the time. `PARAM_EMPTY` is what an empty slot holds, so that absent
   and zero stay different answers.
3. **A chunk may split anywhere.** A read from a pseudoterminal ends
   where the kernel says it ends: inside a parameter list, between two
   bytes of one character, halfway through an OSC payload. Every one of
   those is an ordinary rest position. Keep the parser between reads and
   feed the next chunk to it. There is no entry point that takes a whole
   sequence.
4. **The private marker is not an intermediate byte.** `ESC [ ? 1049 h`
   switches to the alternate screen and `ESC [ 1049 h` does not; the
   private modes are listed in xterm's `ctlseqs` under "Functions using
   CSI ? Pm h". `private_marker_of` answers `?`, `<`, `=`, `>` or
   `NO_PRIVATE_MARKER`.
5. **Sub-parameters are separated by colons and belong to the parameter
   before them.** ITU-T T.416 section 13.1.8 defines the colon form of
   the direct-colour parameter, so a 24-bit foreground arrives as either
   `38;2;R;G;B` or `38:2::R:G:B`. `sub_count` and `sub_at` read a group,
   and `sgr.read_extended_color` reports how many parameters it
   consumed, which is what lets a caller resume its walk at the right
   place.
6. **An empty SGR parameter list means a reset.** `ESC [ m` is
   `ESC [ 0 m`: ECMA-48 section 8.3.117 gives SGR the default parameter
   0. `sgr.apply_sgr` applies that rule.
7. **`sgr.sgr_transition` returns an empty list when nothing changed.**
   Appending it writes no bytes. A renderer that emitted a full reset
   before every character would be correct and four times the size.
8. **Text from outside the program goes through
   `seqwrite.put_text_safe`.** It replaces every C0 control, every C1
   control and every ESC with a printable stand-in. A log line, a
   filename or a commit message can contain `ESC ] 52 ; c ;`, which is a
   clipboard write. `put_text` appends bytes unchanged and is for text
   the program made itself.
9. **The parser never fails; it refuses.** Breaking a limit produces an
   `AnsiRefused` action naming which limit, the rest of the sequence is
   consumed, and the machine carries on in the ground state. There is no
   `Result` anywhere in this package. A malformed UTF-8 sequence is an
   `AnsiBadUtf8` refusal followed by `REPLACEMENT_CHAR`, which is
   U+FFFD, as Unicode section 3.9 prescribes.
10. **The payload of an OSC or a DCS is delivered a byte at a time, and
    the buffer it goes into is the caller's.** `AnsiOscStart` says a
    string began, `AnsiOscPut` carries one byte, and `AnsiOscEnd` says
    it ended and which terminator it used. The parser holds no part of
    the payload, so the ceiling on how much to keep is the caller's.
    `AnsiDcsStart`, `AnsiDcsPut` and `AnsiDcsEnd` are the same three for
    a device control string. An OSC's numeric code arrives as the
    payload bytes before the first semicolon, so read it with
    `osc_code`, `osc_field` and `osc_body` once the end has fired.
11. **Report the terminator you were asked with.** `AnsiOscEnd` and
    `AnsiDcsEnd` say whether the string ended with BEL or with ST. A
    program answering an OSC query echoes the terminator it received;
    xterm's own clipboard handling depends on this.
12. **A query's answer may never arrive, and waiting for it is the
    caller's problem.** A terminal that does not implement a query stays
    silent. `vtquery.write_query` builds the question and
    `vtquery.reply_of` recognises an answer among ordinary dispatches.
    Neither reads, waits or times out.
13. **`sgr.indexed_to_rgb` answers `None` for indices below 16.** Colours
    0 to 15 are the user's own theme and no library can know them. The
    values for 16 to 255 are fixed by the specification.
14. **Three of the five underline styles can only be written with a
    colon.** `4:3`, `4:4` and `4:5` — curly, dotted and dashed — have no
    spelling as a plain numbered parameter, so `sgr.sgr_transition` and
    `sgr.sgr_full`, which answer a list of numbers, write a plain `4`
    for all three. `sgr.sgr_transition_sub` and `sgr.sgr_full_sub`
    answer the same thing with the colon groups intact, and
    `seqwrite.csi_params` puts one on the wire.
    `seqwrite.sgr_change` uses them already, so a renderer that calls
    it gets the colon form without doing anything.
15. **A byte at 0x80 or above in ordinary text is UTF-8, not a C1
    control.** The parser decodes it as the first byte of a codepoint.
    The 8-bit forms of CSI, OSC and the rest are therefore not
    recognised; every terminal in use sends the two-byte `ESC [` form.
16. **A payload that passes `osc_bytes_max` or `dcs_bytes_max` is
    truncated, and the string still ends.** The byte at the ceiling is
    reported as `AnsiRefused(AnsiOscTooLong)` or
    `AnsiRefused(AnsiDcsTooLong)`, every byte after it is dropped, and
    `AnsiOscEnd` or `AnsiDcsEnd` fires when the terminator arrives. A
    consumer that has been accumulating therefore always gets the end it
    needs to close its buffer.
17. **The parser is copied wherever it is passed or stored.** It is a
    `@value` struct of seventy-two bytes. `p = vtparse.feed(p, b)`
    copies it. Storing it in a `var` field of a struct, in an optional,
    in a tuple or in an enum payload copies it as well. Keep it in a
    local, or in one field, and feed it in place. A list of parsers
    rebuilt per byte, and a parser passed through an optional on the
    byte path, each pay a copy the program does not need.

## Running on a microcontroller

The `vtcore` module builds for a device with no heap allocator, and
`tests/embedded_probe.nv` is a program that builds for a Cortex-M4,
boots under QEMU and checks the machine's answers there.

```
novo build --target=nrf52-qemu tests/embedded_probe.nv
```

What builds there is `vtcore` and nothing else. The other three modules
speak `Str`, `Bytes` and lists, which the embedded runtime does not
define, and one host-only function anywhere in a compilation unit is an
undefined symbol at link time whether or not the firmware calls it. A
device therefore reads the action as an integer, through `action_kind`
and `action_arg`, and writes its own sequences.

`vtcore.AnsiParser` holds its parameters in fixed-size buffers and lives
in the caller's stack frame rather than on the heap. Feeding one byte
allocates nothing. `tests/alloc_probe.nv` is a program whose compiled
output can be read for allocations, and `tests/alloc_scan.sh` is the
check that fails when one appears. It runs twice more on copies with an
allocation spliced in: the scan has to name that allocation, and the
compiler has to refuse it.

## What is not included

- **A grid, a cursor and a scrollback.** This package answers what a
  byte said, not what the screen looks like.
  [novo-vte](https://novo-lang.org/packages/novo-vte) keeps a grid, and
  [tui-nv](https://novo-lang.org/packages/tui-nv) has the cell buffer a
  program draws into.
- **Terminal detection.** Reading `TERM` and `COLORTERM`, and asking
  whether a descriptor is a terminal, all touch the environment or a
  descriptor. `sgr.downgrade` takes the colour depth as an argument
  instead.
- **The sixteen low palette colours.** They are the user's theme. See
  rule 13.
- **Base64.** OSC 52 carries a base64 payload, and
  `seqwrite.clipboard_write` takes one already encoded.
  [base64-nv](https://novo-lang.org/packages/base64-nv) is the package
  that encodes it.
- **Sixel, ReGIS and the other DCS payload formats.** The parser reports
  the payload bytes of a DCS. Decoding an image out of them is an image
  decoder's work.
- **Key and mouse decoding.** Input is a different state machine and
  lives in [keymap-nv](https://novo-lang.org/packages/keymap-nv).
- **The queries whose reply is a free-form string.** `vtquery` covers
  the six questions whose answer is a parameter list. `seqwrite.csi`
  asks the others, and whoever reads that string parses it.
- **Any function that writes.** See the opening paragraph.

## Related packages

- [novo-vte](https://novo-lang.org/packages/novo-vte) is a terminal
  emulator's model: a grid of cells with a cursor, a scrollback and an
  alternate screen, changed as bytes arrive. It answers what the screen
  looks like now. This package answers what one byte said, returns an
  action instead of changing anything, and has a writing half, which
  novo-vte does not. The state machine here came out of novo-vte, and
  novo-vte will read this package rather than keep a second copy.
- [keymap-nv](https://novo-lang.org/packages/keymap-nv) is the same job
  in the other direction: the bytes a terminal sends when a key is
  pressed or the mouse moves, decoded into events.
- [termios-nv](https://novo-lang.org/packages/termios-nv) owns the file
  descriptor. It writes the sequences this package builds, and puts the
  terminal back afterwards.
- [tui-nv](https://novo-lang.org/packages/tui-nv) is layout, widgets and
  a cell buffer. Its cells carry this package's `SgrAttrs`, so a frame
  diff needs no colour conversion.
- [clipboard-nv](https://novo-lang.org/packages/clipboard-nv) reaches
  the system clipboard, over OSC 52 among other ways, and uses
  `seqwrite.clipboard_write` for the sequence.
- `std.tui` in the standard library writes escape sequences straight to
  standard output. It clears the screen, moves the cursor, wraps a string
  in colour codes and reports the terminal size. It is for a program that
  wants a coloured line, not one that needs a parser or a frame.

## Tests

```bash
novo test --isolate tests/vtcore_tests.nv    # 14 tests: the integer surface a device uses
novo test --isolate tests/vtparse_tests.nv   # 19 tests: the state machine
novo test --isolate tests/sgr_tests.nv       # 15 tests: attributes, writer, queries
novo test --isolate tests/surface_tests.nv   # 14 tests: every signature, called once
novo test --isolate tests/corpus_tests.nv    # 36 tests: novo-vte's cases, every state, every limit
novo test --isolate tests/writer_tests.nv    # 32 tests: the exact bytes of every sequence
bash tests/coverage.sh                       # the merged line coverage over src/
bash tests/alloc_scan.sh                     # nothing on the feed path allocates
```

The sequences the suites assert on come from xterm's `ctlseqs` for the
private modes and the OSC strings, ECMA-48 for the control sequence
grammar and the standard functions, ITU-T T.416 for the colon
sub-parameter form, and Paul Williams' published state diagram for DEC's
ANSI-compatible video terminals for the shape of the machine.

Most cases in `vtparse_tests.nv` feed the bytes one at a time and assert
what the machine is holding in between, because a parser tested only on
whole sequences will be split on its first day in production. The rest
fix a limit and assert the refusal. `sgr_tests.nv` covers the two cases
implementations usually miss: that a transition between two identical
sets of attributes emits nothing, and that a colour read out of a
parameter list reports how many parameters it took. `surface_tests.nv`
calls every published function once, from outside its own module, with
the argument types a consumer would pass.

`corpus_tests.nv` is novo-vte's own parser suite, case by case. Those
tests assert what a grid of cells looked like after a sequence, because
novo-vte's parser changes a grid as it reads. This package has no grid,
so each case is asserted at the layer it tested. That layer is the
dispatch that came out and the parameters it came with. Beside them the
file walks every state the parser publishes and produces every refusal
from the limit it belongs to.

`writer_tests.nv` asserts the exact bytes of every sequence this package
writes. Where a sequence can also be read, it is fed back through this
package's own parser and has to come out as what it was.

`vtcore_tests.nv` drives the machine through the integer surface, which
is what a device has. It reaches the answers the enum surface cannot
ask for: a ceiling above the package's capacity, a parameter count of
zero, a group that does not exist, and a string payload fed past its
ceiling.

Every line of `src/` is executed by the suites: 950 of 950, with no
region excused. `novo test --cov` measures one file at a time, so
`tests/coverage.sh` merges the per-file reports and prints the total.

`tests/bench_parse.nv` feeds one stream through the parser two ways, as
a local and out of a field of a struct, and prints the throughput of
each.

No test opens a descriptor or writes anything.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
