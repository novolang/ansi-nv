# Changelog

All notable changes to ansi-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

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
