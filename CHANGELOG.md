# Changelog

All notable changes to ansi-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-09-18

First implementation of the interface published as 0.0.1. Every `pub
fn` has a body; no `todo()` is left under `src/`.

### Added

- **The parser is novo-vte's, moved.** `orbit/novo-vte/src/parser.nv`
  has been the shared VT parser novoterm and novomux read since 2026.
  Its state machine, its UTF-8 lead-byte table, its OSC accumulation
  and terminator handling, its DCS / SOS / PM / APC consumption and
  its SGR walk — where 38, 48 and 58 consume the parameters after them
  — are what `vtparse` and `sgr` are. What did not come is the
  terminal: the grid of cells, the cursor, the scroll region, the
  alternate screen, the palette lookups through the C runtime, the
  reply queue and the mouse-mode bitmask all stay in novo-vte, which
  is where a screen belongs. novo-vte will depend on this package
  rather than keep its own copy.
- **`seqwrite.csi_params`**, beside `csi`. `csi` takes
  `params: [Int]`, a list of semicolon-separated parameters, which
  cannot express a colon group — so `CSI 4:3 m` and
  `CSI 38:2::R:G:B m` were unreachable through the published surface.
  `csi_params` takes `vtparse.AnsiParams`, whose flat values-and-groups
  pair carries them, so a sequence this package parsed can be written
  back byte for byte. An empty slot is written as nothing between two
  colons, which is what it was.
- **`sgr.sgr_transition_sub` and `sgr.sgr_full_sub`**, beside
  `sgr_transition` and `sgr_full`, for the same reason and answering
  `AnsiParams`. The published pair is those two flattened — one entry
  per group, its first value — and is unchanged.
  `seqwrite.sgr_change` uses the unflattened pair, so a renderer gets
  the colon form without asking for it.

### Behaviour worth knowing

Every item here is a decision the interface did not settle, not a
change to something it did.

- **A byte at 0x80 or above in the ground state is UTF-8, not a C1
  control.** `AnsiExecute`'s comment says it carries "the 8-bit forms",
  and it cannot: 0x80..0x9F are continuation bytes in a UTF-8 stream,
  and a parser that executed them would print two replacement
  characters for every accented letter. novo-vte read them the same
  way. The 7-bit forms — `ESC [`, `ESC ]`, `ESC P` — are what every
  terminal in use sends.
- **`AnsiBadUtf8` is the whole action, and `REPLACEMENT_CHAR` is the
  caller's to substitute.** The README said the refusal is "followed
  by `REPLACEMENT_CHAR`". `feed_byte` answers one action per byte and
  has no second one to give, so the constant is published for the
  caller to print. Nothing else changed: the refusal fires where the
  README said it would.
- **A truncated codepoint does not swallow the byte that ended it.** A
  byte that is not a continuation aborts the partial codepoint and is
  read again from the ground state — novo-vte's own recovery, and
  xterm's. The cost is that the abort itself is not reported when the
  byte is something else; losing an ESC instead would print a control
  sequence as text.
- **`ESC ( B` is an escape dispatch with `(` as its intermediate.**
  novo-vte consumed the charset byte with a hand-rolled one-byte state
  and reported nothing. Williams' grammar makes `(` an ordinary
  intermediate and `B` an ordinary final, which is what this package
  does, so a caller that wants to honour a charset designation can.
- **A colon-only underline style flattens to a plain `4`.** See
  `sgr_transition_sub` above. `sgr_transition` emits `4` for curly,
  dotted, dashed and double, which is a plain underline — safe, and
  what a terminal without the extension would have drawn. It never
  emits a bare `3` that a terminal would read as italics.
- **`sgr.downgrade` at 16 colours derives the index from the channel
  values** — bit 0 red, bit 1 green, bit 2 blue, bit 3 bright — rather
  than matching against a palette. Indices 0..15 are the user's theme
  and this package has no table for them, which is the same reason
  `indexed_to_rgb` answers `None` below 16.
- **`set_title` ends with BEL and `clipboard_write` with ST.** Both are
  accepted everywhere; a program answering a query echoes the
  terminator it was asked with, which is what `AnsiOscEnd` reports.
- **`seqwrite.put_text_safe` writes `^` and a letter for a C0 control
  or DEL, and `~` and a letter for a C1 control.** Two different
  stand-ins so that `ESC` and the 8-bit CSI it stands for are
  distinguishable in the output.
- **A count at or below zero is written `0`.** ECMA-48 section 5.4.2
  gives an omitted or zero parameter the function's own default, so
  `cursor_up(out, 0)` moves one row rather than none.
- **`AnsiCsiIgnore` is also where an escape sequence goes** when it
  breaks the intermediate limit. Its behaviour is the same in both
  cases: consume to the final byte, dispatch nothing, return to the
  ground state.
- **`AnsiParser.utf8_owed` carries the pending ESC of a string
  sequence** while the machine is inside an OSC, a DCS or a consumed
  string. No codepoint is in flight there and the published struct has
  no field of its own for it. It is stated here because the field is
  `pub` and a reader may look at it.

### Fixed in the tests the interface shipped

Both of these asserted something no implementation could satisfy.

- `vtparse_tests.nv`'s OSC case counted one start, one end, three
  payload bytes and two actions with nothing to do — seven actions out
  of a six-byte sequence. It now counts one, and asserts that the four
  figures add up to the number of bytes fed.
- `sgr_tests.nv`'s extended-colour case read its parameter list off
  `params_of(parser_new())`, a snapshot of a parser that had never been
  fed and therefore held no parameters. It now feeds
  `CSI 38;2;10;20;30 m`.
- `embedded_probe.nv` compared its score against 7 while the score it
  computes could reach 6: it asked whether a machine that had just read
  an ESC was settled. The check now asks the question that has an
  answer.

### Tests

Five suites, 114 assertions' worth of cases, and every line of `src/`
executed — 834 of 834, with no region excused by a marker.
`tests/corpus_tests.nv` is novo-vte's own parser suite ported case by
case, plus a walk through every state the parser publishes and one case
per limit. `tests/writer_tests.nv` asserts the exact bytes of every
sequence, and feeds each of them back through this package's parser
where both directions exist. `scripts/coverage.py` merges the per-suite
coverage reports, because `novo test --cov` measures one file at a time
on toolchain 0.9.1.

### Known

- **Feeding one byte allocates two refcounted boxes**, on every path
  including the ground state: the `AnsiParser` the step answers and the
  `AnsiStep` itself. novo-lang stores a struct on the stack only when
  it is `@value`, and `@value` forbids list fields (SPEC section 14.2);
  `AnsiParser.values`, `.groups` and `.intermediates` are `[Int]`,
  which is the shape 0.0.1 published. Nothing else allocates until a
  control sequence's parameters arrive, at which point those three
  lists grow. `tests/alloc_probe.nv` and `scripts/alloc_scan.py` are
  where that is measured rather than claimed. Making the three fields
  heapless-nv's fixed-capacity buffer removes both allocations and lets
  the struct be `@value`; it changes a type seven packages depend on,
  so it waits for the release that makes it. The 0.0.1 CHANGELOG said
  this would be the cost, and it is.
- **The minimum toolchain is now 0.9.1**, which is what this release
  was built, tested and measured on. 0.0.x claimed 0.8.9, which was
  never checked against a body.
- **No `Result` anywhere, still on purpose.** See the 0.0.1 entry.

## 0.0.2 — 2026-09-15

README rewritten to the package README style guide
(docs/writing-a-readme.md); no change to the interface.

## 0.0.1 — 2026-09-10

The **interface**: every signature and every effect row, and no bodies.
`stability = "draft"`, and the release is recorded `implemented = false`.

### Added

- `vtparse` — the VT/xterm state machine as a value. `feed_byte` takes
  a parser and a byte and returns the parser and one action; the action
  carries at most one integer and the numbers a dispatch came with stay
  on the parser it came with. A chunk may split anywhere, including
  inside a parameter list and inside an OSC payload. Colon
  sub-parameters, the private marker kept apart from the intermediates,
  UTF-8 in the ground state, and a caller-set ceiling on everything the
  parser has to remember.
- `sgr` — the attribute model: the flags, the five underline styles,
  and one `AnsiColor` covering the named sixteen, the 256-colour cube
  and 24-bit. `apply_sgr` folds a whole parameter list on, because 38,
  48 and 58 consume what follows them in either spelling.
  `sgr_transition` is the inverse and the half most implementations
  skip — the shortest parameter list that gets from one style to
  another, and empty when nothing changed.
- `seqwrite` — the writer, and it writes nothing: every function takes
  the `[u8]` it should append to and returns it. Cursor movement,
  erasing, scrolling, the named modes and the two escape hatches for
  the ones nobody named. `put_text_safe` strips the escapes out of
  text from outside the program, and there is no flag to turn it off.
- `vtquery` — the queries and their replies as two halves that never
  meet: `write_query` builds the question, `reply_of` reads the answer
  off an ordinary CSI dispatch. Nothing waits, because a terminal that
  does not implement a query answers with silence and only the caller
  knows how long to wait.

### Known

- **The device claim covers the signatures, not yet the storage.**
  `tests/embedded_probe.nv` links for `--target=nrf52-qemu` today
  because every body is a `todo()`. `AnsiParser` holds its parameters
  in `[Int]`, which will have to become a fixed-capacity buffer —
  heapless-nv's — before the implementation runs on a device.
- **No `Result` anywhere, on purpose.** A malformed sequence is an
  action (`AnsiRefused`), a missing answer is `None`. `Result<T, E>`
  does not build at `@tier(embedded)`, and shaping the package around
  `?T` and a payload-carrying enum costs nothing here because the
  parser genuinely never fails — it only refuses.

### Design notes

Public type and variant names are unique across a whole program, so a
package's names have to be unique across the registry too. That is why
every type here is prefixed. `Parser` was unavailable because novo-vte
declares it, `Error` is a standard-library trait, and `Action`, `State`,
`Style` and `Color` are names several terminal packages would each want.
Enum variants collide by their bare name, so `AnsiPrint` and
`AnsiExecute` carry the prefix as well. The modules are named `vtparse`,
`sgr`, `seqwrite` and `vtquery` for the same reason: novo-vte ships
`src/parser.nv`, and two dependencies of one program may not both ship a
module of the same name.

`AnsiTerminator` and `seqwrite.AnsiStringEnd` are two types for the two
endings a string sequence can have, because reporting what arrived and
choosing what to send are different decisions.
