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

**Status: NOT IMPLEMENTED — interface only.** Every function is declared
with its full signature, but every body is a `todo()` that panics when
called. The package is published so its design can be reviewed and
depended on before it is implemented. Version 0.1.0 will be the first
working release.

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
    var red = plain
    red.bold = true
    red.fg = AnsiIndexed(1)

    // Build the sequences into one buffer, starting from an empty list.
    var out = seqwrite.cursor_to([], 2, 1)
    // The shortest parameter list that gets from `plain` to `red`.
    out = seqwrite.sgr_change(out, plain, red)
    out = seqwrite.put_text(out, "alert")
    // And back, so the text after this run is unstyled.
    out = seqwrite.sgr_change(out, red, plain)
    // `out` is bytes. Writing them is the program's job.
```

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a
`not implemented: ansi-nv.<module>.<fn>` panic. The tests are the
specification the implementation will have to satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `vtparse` | The state machine: the parser value, the twelve states it rests in, the action returned for one byte, the caller-set limits, and the readers for the parameters, the sub-parameters, the intermediates and the private marker. |
| `sgr` | The attribute model: one struct holding everything SGR can say about a character, the colour type covering all three forms, the fold of a parameter list onto a set of attributes, and the inverse. |
| `seqwrite` | The writer: cursor movement, erasing, scrolling, insertion and deletion, the named terminal modes, text, OSC strings, and two escape hatches for sequences this module does not name. Every function appends to a caller's buffer and returns it. |
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

## Running on a microcontroller

novo-lang lets a package state which of its modules can run on a device
with no heap allocator, and the compiler checks that claim on every
build. Here the claim covers the whole package: there is no host-only
half, because nothing in it performs input or output. A device driving a
serial console over UART is the audience.

```bash
novo build --target=nrf52-qemu tests/embedded_probe.nv
```

That command builds a Cortex-M4 executable today, and the probe names
`vtparse`, `seqwrite`, `sgr` and `vtquery`.

**What links today is the signatures, not the storage.** Every body is a
`todo()`, so the probe proves that the types and the effect rows are
acceptable at this target, and no more. `AnsiParser` keeps its
parameters, its groups and its intermediates in `[Int]` fields, and
those have to become fixed-capacity buffers —
[heapless-nv](https://novo-lang.org/packages/heapless-nv)'s — before any
of it runs on a device.

`strict_limits` is the configuration for this case. Its payload ceiling
is 128 bytes, because an OSC 52 paste from the other end of the link is
unbounded and a device has nowhere to put it.

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

No test opens a descriptor or writes anything. The tests compile today
and fail at run, each on the `not implemented: ansi-nv.<module>.<fn>`
panic that is its body. That is the expected state of an interface
release. They turn green one at a time as bodies land.

`tests/embedded_probe.nv` is the program that shows this package builds
for a microcontroller with no heap allocator. It is compiled for the
nRF52 target and either builds or does not. See "Running on a
microcontroller".

## Implementation status

| Item | Implemented |
| --- | --- |
| `vtparse.PARAM_EMPTY`, `.NO_PRIVATE_MARKER`, `.REPLACEMENT_CHAR` | yes (they are constants) |
| `vtparse.default_limits`, `.strict_limits`, `.parser_new`, `.parser_with` | no |
| `vtparse.feed_byte`, `.feed`, `.reset` | no |
| `vtparse.state_of`, `.is_settled` | no |
| `vtparse.param_count`, `.param_at`, `.sub_count`, `.sub_at` | no |
| `vtparse.intermediate_count`, `.intermediate_at`, `.private_marker_of` | no |
| `vtparse.params_of`, `.params_empty`, `.params_count`, `.params_at`, `.params_sub_count`, `.params_sub_at` | no |
| `vtparse.osc_code`, `.osc_field` | no |
| `sgr.attrs_default`, `.attrs_eq` | no |
| `sgr.apply_sgr`, `.apply_sgr_one`, `.read_extended_color` | no |
| `sgr.sgr_transition`, `.sgr_full`, `.color_params` | no |
| `sgr.indexed_to_rgb`, `.nearest_index`, `.downgrade` | no |
| `seqwrite`'s eleven cursor functions, and `cursor_shape` | no |
| `seqwrite.erase_display`, `.erase_line`, `.erase_chars` | no |
| `seqwrite.scroll_region`, `.scroll_region_reset`, `.scroll_up`, `.scroll_down` | no |
| `seqwrite.insert_lines`, `.delete_lines`, `.insert_chars`, `.delete_chars` | no |
| `seqwrite.set_mode`, `.reset_mode`, `.mode_number`, `.mode_is_private` | no |
| `seqwrite.sgr`, `.sgr_reset`, `.sgr_change` | no |
| `seqwrite.put_codepoint`, `.put_text`, `.put_text_safe` | no |
| `seqwrite.osc`, `.set_title`, `.clipboard_write` | no |
| `seqwrite.csi`, `.esc` | no |
| `vtquery.write_query`, `.reply_of`, `.reply_of_params`, `.answers`, `.write_reply` | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
