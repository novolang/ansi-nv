#!/usr/bin/env python3
"""What allocates on the feed path, read off the emitted LLVM.

It has crypto-nv's shape.  `tests/alloc_probe.nv` is built at `--opt=0`,
so that every function is still there to attribute an allocation to.
This reads `_novo/alloc_probe.ll` and prints the `novo_alloc*` call
count per function of this package.

    novo build --opt=0 tests/alloc_probe.nv -o /tmp/alloc_probe
    python3 scripts/alloc_scan.py

`tests/alloc_probe.nv` says what the numbers mean and why they are not
zero.
"""
import os, re, sys, collections

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ll = os.path.join(root, "_novo", "alloc_probe.ll")
if not os.path.exists(ll):
    sys.exit("no %s — build tests/alloc_probe.nv at --opt=0 first" % ll)

cur = None
hits = collections.Counter()
seen = set()
for line in open(ll):
    m = re.match(r'define .*@"?([A-Za-z0-9_.$]+)"?\(', line)
    if m:
        cur = m.group(1)
        seen.add(cur)
    elif "call" in line and "novo_alloc" in line and cur:
        hits[cur] += 1

ours = [f for f in sorted(seen)
        if f.startswith(("novo_user_vtparse_", "novo_user_sgr_",
                         "novo_user_seqwrite_", "novo_user_vtquery_",
                         "novo_user_ground_path", "novo_user_param_path"))]
for f in ours:
    print("%-48s %d" % (f.replace("novo_user_", ""), hits[f]))
print("--- %d of this package's %d functions in the probe's IR allocate"
      % (sum(1 for f in ours if hits[f]), len(ours)))
