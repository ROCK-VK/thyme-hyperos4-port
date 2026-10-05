#!/usr/bin/env python3
"""Extract dynamic partitions from the community thyme super.img.

Why this exists instead of lpunpack:
  The community "Mi18pm HyperOS 4.0.15 for thyme" package ships a super.img whose
  metadata is written in a non-AOSP layout (AOSP places the primary metadata
  header immediately after the geometry; this image carries an extra copy of the
  geometry block there and the real LpMetadataHeader 0x1000 bytes later).  Both
  lpdump and lpunpack therefore reject it.  The structures themselves are
  standard, so this script decodes them field-by-field and reports what it
  actually found rather than assuming.

Layout actually observed in that image (all values read from the file):
  0x0000  zero padding
  0x1000  LpMetadataGeometry  magic 0x616c4467
  0x2000  duplicate copy of the geometry block
  0x3000  LpMetadataHeader    magic 0x414c5030 ("0PLA"), header_size 256
  0x3100  partitions table (12 entries x 52 bytes)
  0x3700  extents table    ( 6 entries x 24 bytes)
  0x3a00  groups table     ( 3 entries x 48 bytes)
  0x3b90  block_devices    ( 1 entry   x 64 bytes)

Extent semantics: `num_sectors` is the size in 512-byte sectors and
`target_data` is the absolute LBA from the start of super, so the byte offset is
target_data * 512.  That is verified here by filesystem magic probes rather than
assumed.
"""

import argparse
import hashlib
import json
import os
import struct
import sys

SECTOR = 512
CHUNK = 8 << 20

EROFS_MAGIC = 0xE0F5E1E2
EXT4_MAGIC = 0xEF53
F2FS_MAGIC = 0xF2F52010


def read_at(fh, off, size):
    fh.seek(off)
    return fh.read(size)


def parse(path):
    size = os.path.getsize(path)
    fh = open(path, "rb")

    geom = read_at(fh, 0x1000, 4096)
    if struct.unpack_from("<I", geom, 0)[0] != 0x616C4467:
        raise SystemExit("geometry magic not found at 0x1000")

    hdr_off = None
    for cand in (0x2000, 0x3000, 0x4000, 0x1000):
        b = read_at(fh, cand, 4096)
        if struct.unpack_from("<I", b, 0)[0] == 0x414C5030:
            hdr_off = cand
            hdr = b
            break
    if hdr_off is None:
        raise SystemExit("LpMetadataHeader magic not found")

    major, minor = struct.unpack_from("<HH", hdr, 4)
    header_size, = struct.unpack_from("<I", hdr, 8)
    tables_size, = struct.unpack_from("<I", hdr, 44)
    tables_checksum = hdr[48:80]
    p_desc = struct.unpack_from("<III", hdr, 80)
    e_desc = struct.unpack_from("<III", hdr, 92)
    g_desc = struct.unpack_from("<III", hdr, 104)
    b_desc = struct.unpack_from("<III", hdr, 116)
    flags, = struct.unpack_from("<I", hdr, 128)
    tables = hdr[header_size : header_size + tables_size]

    partitions = []
    off, num, esz = p_desc
    for i in range(num):
        e = tables[off + i * esz : off + (i + 1) * esz]
        name = e[:36].split(b"\0")[0].decode()
        attributes, first_extent_index, num_extents, group_index = struct.unpack_from(
            "<IIII", e, 36
        )
        partitions.append(
            dict(
                name=name,
                attributes=attributes,
                first_extent_index=first_extent_index,
                num_extents=num_extents,
                group_index=group_index,
            )
        )

    extents = []
    off, num, esz = e_desc
    for i in range(num):
        e = tables[off + i * esz : off + (i + 1) * esz]
        num_sectors, target_type, target_data, target_source = struct.unpack_from("<QIQI", e, 0)
        extents.append(
            dict(
                num_sectors=num_sectors,
                target_type=target_type,
                target_data=target_data,
                target_source=target_source,
            )
        )

    groups = []
    off, num, esz = g_desc
    for i in range(num):
        e = tables[off + i * esz : off + (i + 1) * esz]
        name = e[:36].split(b"\0")[0].decode()
        gflags, maximum_size = struct.unpack_from("<IQ", e, 36)
        groups.append(dict(name=name, flags=gflags, maximum_size=maximum_size))

    block_devices = []
    off, num, esz = b_desc
    for i in range(num):
        e = tables[off + i * esz : off + (i + 1) * esz]
        first_lba, size_lba, alignment = struct.unpack_from("<QIQ", e, 0)
        name = e[28:].split(b"\0")[0].decode(errors="replace")
        block_devices.append(dict(name=name, first_lba=first_lba, size_lba=size_lba, alignment=alignment))

    return dict(
        path=path,
        file_size=size,
        fh=fh,
        header_offset=hdr_off,
        major=major,
        minor=minor,
        header_size=header_size,
        tables_size=tables_size,
        tables_checksum_ok=hashlib.sha256(tables).digest() == tables_checksum,
        flags=flags,
        partitions=partitions,
        extents=extents,
        groups=groups,
        block_devices=block_devices,
    )


def probe_fs(fh, byte_off):
    """Return the filesystem type whose magic is present at `byte_off`."""
    if byte_off + 1080 > os.fstat(fh.fileno()).st_size:
        return "out-of-range"
    sb = read_at(fh, byte_off + 1024, 4)
    if len(sb) < 4:
        return "short"
    v, = struct.unpack("<I", sb)
    if v == EROFS_MAGIC:
        return "erofs"
    if v == F2FS_MAGIC:
        return "f2fs"
    if v == EXT4_MAGIC:
        return "ext4"
    # ext4 has its magic at offset 0x438 from the superblock start
    if byte_off + 0x438 + 2 <= os.fstat(fh.fileno()).st_size:
        m = read_at(fh, byte_off + 0x438, 2)
        if len(m) == 2 and struct.unpack("<H", m)[0] == EXT4_MAGIC:
            return "ext4"
    return "unknown(0x%08x)" % v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("super_img")
    ap.add_argument("outdir")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()

    m = parse(args.super_img)
    fh = m["fh"]
    os.makedirs(args.outdir, exist_ok=True)

    # extent -> which partitions reference it
    refs = {}
    for p in m["partitions"]:
        for i in range(p["first_extent_index"], p["first_extent_index"] + p["num_extents"]):
            refs.setdefault(i, []).append(p["name"])

    print("header @0x%x  LP %d.%d  tables_checksum_ok=%s  flags=0x%x"
          % (m["header_offset"], m["major"], m["minor"], m["tables_checksum_ok"], m["flags"]))
    print("\n%-3s %-14s %14s %10s  %-9s %s" % ("idx", "used-by", "size_bytes", "size_MiB", "fs", "absolute offset"))
    for i, e in enumerate(m["extents"]):
        boff = e["target_data"] * SECTOR
        size = e["num_sectors"] * SECTOR
        print("%-3d %-14s %14d %10.2f  %-9s lba=%d (0x%x)"
              % (i, ",".join(refs.get(i, [])), size, size / 1048576,
                 probe_fs(fh, boff), e["target_data"], boff))

    wanted = args.names or [p["name"] for p in m["partitions"]]
    manifest = []
    for p in m["partitions"]:
        if p["name"] not in wanted:
            continue
        if p["num_extents"] != 1:
            print("SKIP %s: %d extents (ambiguous A/B sharing)" % (p["name"], p["num_extents"]), file=sys.stderr)
            continue
        e = m["extents"][p["first_extent_index"]]
        boff = e["target_data"] * SECTOR
        size = e["num_sectors"] * SECTOR
        fstype = probe_fs(fh, boff)
        out = os.path.join(args.outdir, p["name"] + ".img")
        h = hashlib.sha256()
        fh.seek(boff)
        remaining = size
        with open(out, "wb") as w:
            while remaining:
                chunk = fh.read(min(remaining, CHUNK))
                if not chunk:
                    raise SystemExit("short read on %s" % p["name"])
                w.write(chunk)
                h.update(chunk)
                remaining -= len(chunk)
        rec = dict(
            name=p["name"],
            size=size,
            fs=fstype,
            super_byte_offset=boff,
            sha256=h.hexdigest().upper(),
            source="super.img extent %d (lba %d, %d sectors)"
            % (p["first_extent_index"], e["target_data"], e["num_sectors"]),
        )
        manifest.append(rec)
        print("extracted %-16s %12d bytes  %-9s sha256=%s" % (p["name"], size, fstype, rec["sha256"][:16]))

    with open(os.path.join(args.outdir, "EXTRACT_MANIFEST.json"), "w") as w:
        json.dump(dict(super=m["path"], super_size=m["file_size"], parts=manifest), w, indent=2)
    print("\nmanifest written")


if __name__ == "__main__":
    main()
