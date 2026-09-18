#!/usr/bin/env python3
"""Union line coverage over src/, merged across the suites.

`novo test --cov` measures one suite file at a time on novo 0.9.1, and
docs/publishing.md Test coverage says a package-wide mode is on the way.
This package's five suites each reach a different part of `src/`, and
the publish rule is about the package.  This therefore merges the
per-suite lcov files `--report=lcov` leaves in `_novo/` and reports the
union, counting only lines under `src/`.

    for f in tests/*_tests.nv; do
        novo test "$f" --cov --report=lcov >/dev/null
    done
    python3 scripts/coverage.py

It exits non-zero while any line of `src/` is unexecuted, so it can be
the gate as well as the report.
"""
import glob, os, sys, collections

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hits = collections.defaultdict(dict)   # file -> {line: hit}
for path in sorted(glob.glob(os.path.join(root, "_novo", "*.lcov.info"))):
    cur = None
    for line in open(path):
        line = line.strip()
        if line.startswith("SF:"):
            cur = line[3:]
        elif line.startswith("DA:") and cur:
            n, h = line[3:].split(",")
            n, h = int(n), int(h)
            d = hits[cur]
            d[n] = max(d.get(n, 0), h)

total = 0
covered = 0
missing = collections.defaultdict(list)
for f, d in sorted(hits.items()):
    if "/src/" not in f:
        continue
    for n, h in sorted(d.items()):
        total += 1
        if h:
            covered += 1
        else:
            missing[os.path.basename(f)].append(n)

pct = (100.0 * covered / total) if total else 0.0
print("src/ lines: %d/%d executed — %.1f%%" % (covered, total, pct))
for f in sorted(missing):
    print("  %s: %s" % (f, " ".join(str(n) for n in missing[f])))
sys.exit(0 if not missing else 1)
