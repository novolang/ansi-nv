# Changelog

All notable changes to ansi-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.1 — 2026-09-18

The documentation and comments in plain prose; no signature changed.

## 0.1.0 — 2026-09-18

The VT/xterm state machine as a byte-at-a-time parser, the SGR
attribute model with all three colour forms, a writer that builds
sequences into a caller's buffer, and six query and reply pairs.

### Added

- The parser is novo-vte's, moved. `orbit/novo-vte/src/parser.nv` has
  been the shared VT parser novoterm and novomux read since 2026. Its
  state machine, its UTF-8 lead-byte table, its OSC accumulation and
  terminator handling, its consumption of DCS, SOS, PM and APC, and its
  SGR walk, where 38, 48 and 58 consume the parameters after them, are
  what `vtparse` and `sgr` are. What did not come is the terminal. The
  grid of cells, the cursor, the scroll region, the alternate screen,
  the palette lookups through the C runtime, the reply queue and the
  mouse-mode bitmask all stay in novo-vte, which is where a screen
  belongs. novo-vte will depend on this package rather than keep its
  own copy.
- `seqwrite.csi_params`, beside `csi`. `csi` takes `params: [Int]`, a
  list of semicolon-separated parameters, which cannot express a colon
  group, so `CSI 4:3 m` and `CSI 38:2::R:G:B m` have no spelling
  through it. `csi_params` takes `vtparse.AnsiParams`, whose flat
  values-and-groups pair carries them, so a sequence this package
  parsed can be written back byte for byte. An empty slot is written as
  nothing between two colons, which is what it was.
- `sgr.sgr_transition_sub` and `sgr.sgr_full_sub`, beside
  `sgr_transition` and `sgr_full`, for the same reason and answering
  `AnsiParams`. The `[Int]` pair is those two flattened, one entry per
  group and its first value. `seqwrite.sgr_change` uses the unflattened
  pair, so a renderer gets the colon form without asking for it.

### Behaviour worth knowing

- A byte at 0x80 or above in the ground state is UTF-8, not a C1
  control. The bytes 0x80 to 0x9F are continuation bytes in a UTF-8
  stream, and a parser that executed them would print two replacement
  characters for every accented letter. novo-vte read them the same
  way. The 7-bit forms `ESC [`, `ESC ]` and `ESC P` are what every
  terminal in use sends, and `AnsiExecute` therefore carries a C0
  control only.
- `AnsiBadUtf8` is the whole action, and `REPLACEMENT_CHAR` is the
  caller's to substitute. `feed_byte` answers one action per byte and
  has no second one to give, so the constant is published for the
  caller to print.
- A truncated codepoint does not swallow the byte that ended it. A byte
  that is not a continuation aborts the partial codepoint and is read
  again from the ground state, which is novo-vte's own recovery and
  xterm's. The cost is that the abort itself is not reported when the
  byte is something else. Losing an ESC instead would print a control
  sequence as text.
- `ESC ( B` is an escape dispatch with `(` as its intermediate.
  novo-vte consumed the charset byte with a hand-rolled one-byte state
  and reported nothing. Williams' grammar makes `(` an ordinary
  intermediate and `B` an ordinary final, which is what this package
  does, so a caller that wants to honour a charset designation can.
- A colon-only underline style flattens to a plain `4`. See
  `sgr_transition_sub` above. `sgr_transition` emits `4` for curly,
  dotted, dashed and double, which is a plain underline, safe, and what
  a terminal without the extension would have drawn. It never emits a
  bare `3` that a terminal would read as italics.
- `sgr.downgrade` at 16 colours derives the index from the channel
  values rather than matching against a palette. Bit 0 is red, bit 1
  green, bit 2 blue and bit 3 bright. Indices 0 to 15 are the user's
  theme and this package has no table for them, which is the same
  reason `indexed_to_rgb` answers `None` below 16.
- `set_title` ends with BEL and `clipboard_write` with ST. Both are
  accepted everywhere. A program answering a query echoes the
  terminator it was asked with, which is what `AnsiOscEnd` reports.
- `seqwrite.put_text_safe` writes `^` and a letter for a C0 control or
  DEL, and `~` and a letter for a C1 control. Two different stand-ins
  keep `ESC` and the 8-bit CSI it stands for distinguishable in the
  output.
- A count at or below zero is written `0`. ECMA-48 section 5.4.2 gives
  an omitted or zero parameter the function's own default, so
  `cursor_up(out, 0)` moves one row rather than none.
- `AnsiCsiIgnore` is also where an escape sequence goes when it breaks
  the intermediate limit. Its behaviour is the same in both cases.
  Consume to the final byte, dispatch nothing, and return to the ground
  state.
- `AnsiParser.utf8_owed` carries the pending ESC of a string sequence
  while the machine is inside an OSC, a DCS or a consumed string. No
  codepoint is in flight there and the published struct has no field of
  its own for it. It is stated here because the field is `pub` and a
  reader may look at it.

### Tests

Five suites, 114 assertions' worth of cases, and every line of `src/`
executed, 836 of 836, with no region excused by a marker.
`tests/corpus_tests.nv` is novo-vte's own parser suite ported case by
case, plus a walk through every state the parser publishes and one case
per limit. `tests/writer_tests.nv` asserts the exact bytes of every
sequence, and feeds each of them back through this package's parser
where both directions exist. `scripts/coverage.py` merges the per-suite
coverage reports, because `novo test --cov` measures one file at a time
on toolchain 0.9.1.

### Known

- No module builds for a device with no heap allocator, and the package
  ships no `tests/embedded_probe.nv`. `@tier(embedded)` refuses a list
  literal, `list.push`, `list.get` and a boxed struct literal, and
  `AnsiParser` is a boxed struct with three list fields. The README
  says what has to change, and that change is a release of its own.
- Feeding one byte allocates two refcounted boxes on every path,
  including the ground state. They are the `AnsiParser` the step
  answers and the `AnsiStep` itself. novo-lang stores a struct on the
  stack only when it is `@value`, and `@value` forbids list fields
  (SPEC section 14.2), while `AnsiParser.values`, `.groups` and
  `.intermediates` are `[Int]`. Nothing else allocates until a control
  sequence's parameters arrive, at which point those three lists grow.
  `tests/alloc_probe.nv` and `scripts/alloc_scan.py` are where that is
  measured rather than claimed. Making the three fields heapless-nv's
  fixed-capacity buffer removes both allocations and lets the struct be
  `@value`. It changes a type seven packages depend on, so it waits for
  the release that makes it.
- A dependent's constraint has to move. The seven packages that depend
  on this one are termios-nv, tui-nv, clipboard-nv, table-nv,
  progress-nv, logging-nv and logging-core-nv. Each declares
  `ansi-nv = "^0.0.1"`, and under the pre-1.0 rule `^0.0.1` does not
  admit `0.1.0`. Each of them needs `^0.1.0` before it resolves against
  this release.
- The minimum toolchain is 0.9.1, which is what this release was built,
  tested and measured on.
- No `Result` anywhere, on purpose. See the 0.0.1 entry.

## 0.0.2 — 2026-09-15

README rewritten to the package README style guide
(docs/writing-a-readme.md); no change to the published surface.

## 0.0.1 — 2026-09-10

The declarations: every signature and every effect row, with no
function bodies.

### Added

- `vtparse`, the VT/xterm state machine as a value. `feed_byte` takes a
  parser and a byte and returns the parser and one action. The action
  carries at most one integer, and the numbers a dispatch came with
  stay on the parser it came with. A chunk may split anywhere,
  including inside a parameter list and inside an OSC payload. Colon
  sub-parameters, the private marker kept apart from the intermediates,
  UTF-8 in the ground state, and a caller-set ceiling on everything the
  parser has to remember.
- `sgr`, the attribute model: the flags, the five underline styles, and
  one `AnsiColor` covering the named sixteen, the 256-colour cube and
  24-bit. `apply_sgr` folds a whole parameter list on, because 38, 48
  and 58 consume what follows them in either spelling. `sgr_transition`
  is the inverse and the half most implementations skip. It is the
  shortest parameter list that gets from one style to another, and it
  is empty when nothing changed.
- `seqwrite`, the writer, and it writes nothing. Every function takes
  the `[u8]` it should append to and returns it. Cursor movement,
  erasing, scrolling, the named modes and the two escape hatches for
  the ones nobody named. `put_text_safe` strips the escapes out of text
  from outside the program, and there is no flag to turn it off.
- `vtquery`, the queries and their replies as two halves that never
  meet. `write_query` builds the question and `reply_of` reads the
  answer off an ordinary CSI dispatch. Nothing waits, because a
  terminal that does not implement a query answers with silence and
  only the caller knows how long to wait.

### Known

- `AnsiParser` holds its parameters in `[Int]`, which has to become a
  fixed-capacity buffer, heapless-nv's, before the package builds for a
  device with no heap allocator.
- No `Result` anywhere, on purpose. A malformed sequence is an action,
  `AnsiRefused`, and a missing answer is `None`. `Result<T, E>` does
  not build at `@tier(embedded)`, and shaping the package around `?T`
  and a payload-carrying enum costs nothing here, because the parser
  never fails and only refuses.

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
