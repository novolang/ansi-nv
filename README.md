# ansi-nv

A terminal is driven by **escape sequences**: short runs of bytes that
begin with the ESC character and tell the terminal to move the cursor,
erase part of the screen, or change the colour of the text that comes
after them. The grammar and the standard sequences are specified in
[ECMA-48](https://ecma-international.org/publications-and-standards/standards/ecma-48/),
and the ones terminals in use actually accept are documented in
[xterm's `ctlseqs`](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).
This package is that layer on its own, with no terminal under it.
Three packages on the registry are built on it:
[termios-nv](https://novo-lang.org/packages/termios-nv),
[clipboard-nv](https://novo-lang.org/packages/clipboard-nv) and
[tui-nv](https://novo-lang.org/packages/tui-nv).

**Status: implemented, and new.** Every function has a body and the
suites are green. The parser is the one
[novo-vte](https://novo-lang.org/packages/novo-vte) has read terminal
output with since 2026: the same state machine, moved out from under
its grid of cells and given the writing half it did not have. novo-vte
will depend on this package rather than carry its own copy. The API is
marked experimental because it was designed before it was implemented
and no program outside this package has used it yet.

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

The parser is a value. `feed_byte` takes a parser and one byte and
returns a new parser and one action. The action names the final byte and
nothing else; the numbers the sequence came with stay on the parser that
is returned with it, and are read back afterwards with `param_at` and
its neighbours.

Every ceiling the parser enforces is a number the caller sets, in an
`AnsiLimits` value. Two are provided.

| Limit | `default_limits` | `strict_limits` |
| --- | --- | --- |
| Parameters in one sequence | 32 | 8 |
| Sub-parameters in one colon group | 6 | 4 |
| Largest value one parameter may hold | 65535 | 4095 |
| Intermediate bytes kept | 2 | 2 |
| Bytes of OSC or DCS payload reported | 4096 | 128 |

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
        let step = vtparse.feed_byte(p, b)
        // Keep the parser the step returned; it is the one to feed next.
        p = step.parser
        match step.action
            // Final byte 0x48 is `H`: put the cursor somewhere.
            AnsiCsiDispatch(0x48) =>
                // The parameters are still on the parser the dispatch
                // came with. 1 is the fallback for an omitted one.
                let row = vtparse.param_at(step.parser, 0, 1)
                let col = vtparse.param_at(step.parser, 1, 1)
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
| `vtparse` | The state machine: the parser value, the twelve states it rests in, the action returned for one byte, the caller-set limits, and the readers for the parameters, the sub-parameters, the intermediates and the private marker. |
| `sgr` | The attribute model: one struct holding everything SGR can say about a character, the colour type covering all three forms, the fold of a parameter list onto a set of attributes, and the inverse. |
| `seqwrite` | The writer: cursor movement, erasing, scrolling, insertion and deletion, the named terminal modes, text, OSC strings, and three escape hatches for sequences this module does not name. Every function appends to a caller's buffer and returns it. |
| `vtquery` | The questions a program can ask a terminal and the answers, as two halves: one builds the question, the other reads a reply out of an ordinary control sequence dispatch. |

## How to choose an entry point

**`vtparse.feed_byte` takes one byte and allocates nothing.** It is the
entry point everything else is written over, and the one a device uses.
The parameters of a dispatch are read off the parser it returned.

**`vtparse.feed` takes a whole chunk and answers a list.** Each entry
pairs an action with a copy of the parameters it fired with, so a caller
can look at them after the parser has moved on. The copy costs one
allocation per dispatch.

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
   parameters stay on the parser returned beside it. Read them with
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
10. **An OSC's numeric code is not known when the string starts.** It
    arrives as the payload bytes before the first semicolon. Accumulate
    the bytes reported by `AnsiOscPut`, and once `AnsiOscEnd` has fired
    read them with `osc_code` and `osc_field`.
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
    **`seqwrite.sgr_change` already uses them**, so a renderer that
    calls it gets the colon form without doing anything.
15. **A byte at 0x80 or above in ordinary text is UTF-8, not a C1
    control.** The parser decodes it as the first byte of a codepoint.
    The 8-bit forms of CSI, OSC and the rest are therefore not
    recognised; every terminal in use sends the two-byte `ESC [` form.

## Running on a microcontroller

novo-lang lets a package state which of its modules can run on a device
with no heap allocator, and the compiler checks that claim on every
build. **This package makes no such claim in version 0.1.0, and the
reason is worth stating plainly.**

A device with no heap allocator may not use a container that grows.
Three fields of `AnsiParser` — the parameters, their groups and the
intermediate bytes — are lists, which grow. The compiler also stores a
structure on the stack only when every one of its fields is a fixed-size
value, so a structure with a list field lives on the heap: feeding one
byte allocates two of them, the parser that comes back and the step that
carries it.

The 0.0.1 release shipped a program that built for an nRF52 board, and
it built because every function was an unimplemented stub. With the
functions written, it does not.

What has to change is those three fields: a fixed-capacity buffer, of
the kind [heapless-nv](https://novo-lang.org/packages/heapless-nv)
provides, in place of each list. That changes a type every program using
this package can see, so it is a release of its own rather than a patch.
Nothing else in the package stands in the way: no function here reads a
clock, opens a file or performs input or output of any kind.

`tests/alloc_probe.nv` is a small program whose compiled output can be
read for allocations, and `scripts/alloc_scan.py` prints one count per
function. They are how the two allocations above were counted, and how
a reader can check the number for themselves.

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
- **Any function that writes.** See the opening paragraph.

## Related packages

- [novo-vte](https://novo-lang.org/packages/novo-vte) is a terminal
  emulator's model: a grid of cells with a cursor, a scrollback and an
  alternate screen, which its parser mutates as bytes arrive. It answers
  what the screen looks like now. This package answers what one byte
  said, returns an action instead of changing anything, and has a
  writing half, which novo-vte does not.
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
novo test --isolate tests/vtparse_tests.nv   # 18 tests: the state machine
novo test --isolate tests/sgr_tests.nv       # 15 tests: attributes, writer, queries
novo test --isolate tests/surface_tests.nv   # 13 tests: every signature, called once
novo test --isolate tests/corpus_tests.nv    # 36 tests: novo-vte's cases, every state, every limit
novo test --isolate tests/writer_tests.nv    # 32 tests: the exact bytes of every sequence
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
novo-vte's parser changes a grid as it reads; this package has no grid,
so each case is asserted at the layer it actually tested — the dispatch
that came out and the parameters it came with. Beside them the file
walks every state the parser publishes and produces every refusal from
the limit it belongs to.

`writer_tests.nv` asserts the exact bytes of every sequence this package
writes. Where a sequence can also be read, it is fed back through this
package's own parser and has to come out as what it was.

Every line of `src/` is executed by the suites: 836 of 836, with no
region excused. `novo test --cov` measures one file at a time, so
`scripts/coverage.py` merges the per-file reports and prints the total.

No test opens a descriptor or writes anything.

## Implementation status

Everything the package declares has a body. The table says what each
module does and what it deliberately leaves to the caller.

| Module | Implemented | Not implemented, on purpose |
| --- | --- | --- |
| `vtparse` | The whole state machine: twelve states, colon sub-parameters, the private marker, UTF-8 in the ground state, OSC and DCS payloads, both string terminators, and a refusal for every limit. | The 8-bit forms of the control characters. See rule 15. |
| `sgr` | The attribute model, the fold of a parameter list onto it in both the semicolon and the colon spelling, the shortest transition between two sets of attributes, the 240 palette colours the specification fixes, and the reduction to 256 or 16 colours. | The sixteen colours a user's theme owns. See rule 13. |
| `seqwrite` | Every named sequence, text, OSC strings, and three escape hatches. | Nothing. |
| `vtquery` | Six queries, six replies, both directions, and the matching of a reply to the query it answers. | The queries whose reply is a free-form string. `seqwrite.csi` is how those are asked. |

Two functions were added in 0.1.0 beside published ones that could not
express a colon group, and the published ones still work: see rule 14.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
