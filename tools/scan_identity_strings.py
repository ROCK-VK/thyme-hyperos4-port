#!/usr/bin/env python3
"""Scan a raw image for ASCII identity strings (read-only, bounded output)."""

import re
import sys

NEEDLES = [b"madrid", b"missi", b"thyme", b"Mi 18 Pro Max", b"18 Pro Max", b"marketname"]


def scan(path, needles, limit_per_needle=12, block=32 << 20):
    pats = [(n, re.compile(re.escape(n))) for n in needles]
    hits = {n: [] for n in needles}
    total = 0
    with open(path, "rb") as f:
        carry = b""
        while True:
            buf = f.read(block)
            if not buf:
                break
            data = carry + buf
            base = total - len(carry)
            for n, p in pats:
                if len(hits[n]) >= limit_per_needle:
                    continue
                for m in p.finditer(data):
                    if len(hits[n]) >= limit_per_needle:
                        break
                    off = base + m.start()
                    lo = max(0, m.start() - 60)
                    hi = min(len(data), m.end() + 60)
                    ctx = data[lo:hi]
                    ctx = bytes(c if 32 <= c < 127 else 0x2E for c in ctx)
                    hits[n].append((off, ctx.decode("ascii", "replace")))
            total += len(buf)
            carry = data[-64:]
    return total, hits


if __name__ == "__main__":
    path = sys.argv[1]
    needles = [a.encode() for a in sys.argv[2:]] or NEEDLES
    total, hits = scan(path, needles)
    print("scanned %s (%d bytes)" % (path, total))
    for n, hs in hits.items():
        print("\n=== %s : %d hit(s) shown ===" % (n.decode(), len(hs)))
        for off, ctx in hs:
            print("  0x%08x  %s" % (off, ctx))
