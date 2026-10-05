#!/usr/bin/env python3
"""Read build.prop-style identity files out of ext4 images via debugfs.

The images here are raw ext4 filesystems extracted from super; `debugfs` from
e2fsprogs reads them without mounting, which keeps this strictly read-only.
"""

import re
import subprocess
import sys

KEYS = re.compile(
    r"^(ro\.product\.(device|model|name|marketname|brand|manufacturer)\b"
    r"|ro\.product\.(system|vendor|odm|product|system_ext|mi_ext)\.(device|model|name|marketname)\b"
    r"|ro\.build\.product\b|ro\.build\.fingerprint\b|ro\.(system|vendor|odm|product|system_ext)\.build\.fingerprint\b"
    r"|ro\.build\.version\.incremental\b|ro\.mi\.os\.version\.[a-z]+\b"
    r"|ro\.build\.version\.(release|sdk)\b|ro\.build\.id\b|ro\.build\.date\b"
    r"|ro\.product\.mod_device\b|ro\.vendor\.build\.ab_ota_partitions\b"
    r"|ro\.build\.version\.smr_baseversion\b|ro\.boot\.hardware\b"
    r"|ro\.board\.platform\b|ro\.product\.board\b|ro\.hardware\b"
    r"|ro\.vendor\.build\.date\b|ro\.odm\.build\.fingerprint\b)"
)

PATHS = ["/build.prop", "/etc/build.prop", "/system/build.prop"]


def cat(img, path):
    p = subprocess.run(
        ["debugfs", "-R", "cat %s" % path, img],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if p.returncode != 0 or not p.stdout:
        return None
    return p.stdout.decode("utf-8", "replace")


def main():
    img, label = sys.argv[1], sys.argv[2]
    found = False
    for path in PATHS:
        text = cat(img, path)
        if not text or "ro." not in text:
            continue
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        sel = [l for l in lines if KEYS.match(l)]
        if not sel:
            continue
        found = True
        print("### %s :: %s (%d identity lines)" % (label, path, len(sel)))
        for l in sel:
            print("   " + l)
        print()
    if not found:
        print("### %s :: no readable build.prop found" % label)


if __name__ == "__main__":
    main()
