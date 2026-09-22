#!/usr/bin/env python3
"""Read the emitted LLVM for ansi-nv's allocation probe and say whether
any function in `vtcore` can put a cell on the heap.

Run by tests/alloc_scan.sh three times: once on the package as it
stands, and twice on copies with an allocation spliced into the core.
Those two copies are what the scan and the compiler respectively have to
catch, because a check that cannot fail is not a check.

The IR is emitted at `--opt=0` on purpose.  At the default optimisation
level the whole probe inlines into `novo_main`, there is no function
left to attribute an allocation to, and the scan would pass over an
empty file.
"""
import re
import sys

# Every way a function can put a cell on the heap.  `novo_alloc*` is the
# direct one.  The others allocate inside the runtime, so a search for
# the first alone would call a per-byte boxing loop allocation-free.
# `novo_dup_v` is here because a whole-array field copy of a `@value`
# struct is lowered through it on this toolchain (novo bug
# codegen/value-array-field-copy-calls-dup): it probes the four bytes
# before a stack address for a heap header, and where it finds one it
# calls the reference counter.
BOXERS = ['novo_alloc', 'novo_some_int', 'novo_some_float', 'novo_dup_v',
          'novo_str_byte_at(', 'novo_bytes_byte_at(']

# `vtparse`, `sgr`, `seqwrite` and `vtquery` are not matched.  They
# allocate, which is what a written buffer and a parameter snapshot are,
# and the module that runs on a device is the one this scan is about.
CORE = re.compile(r'^novo_user_vtcore_')

FNS = re.compile(r'^define[^\n]*?@([A-Za-z0-9_.]+)\([^\n]*\{\n(.*?)\n\}',
                 re.S | re.M)

# `vtcore` has twenty `pub fn`s and the probe reaches every one, plus
# the machine behind them.  Fewer than this in the IR means the probe or
# the name scheme moved, and that the scan is measuring nothing.
FLOOR = 20


def main(path):
    src = open(path).read()
    seen, offenders = 0, []
    for m in FNS.finditer(src):
        name, body = m.group(1), m.group(2)
        if not CORE.match(name):
            continue
        seen += 1
        for boxer in BOXERS:
            if 'call' in body and ('@' + boxer) in body:
                offenders.append('%s: %s' % (name, boxer.rstrip('(')))
    if seen < FLOOR:
        print('FAIL only %d function(s) of vtcore in the IR, expected at '
              'least %d — the probe or the name scheme moved, and this check '
              'was measuring nothing' % (seen, FLOOR))
    elif offenders:
        print('FAIL ' + '; '.join(sorted(set(offenders))))
    else:
        print('OK %d function(s) in vtcore, zero heap cells' % seen)


if __name__ == '__main__':
    main(sys.argv[1])
