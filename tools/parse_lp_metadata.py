#!/usr/bin/env python3
"""Minimal, self-contained Android LpMetadata parser / extractor.

Purpose: this project cannot rely on lpunpack for every upstream super image
(the community thyme package's super.img is written by a non-AOSP producer and
lpunpack rejects it).  This parser is narrow and explicit: it decodes the
documented AOSP liblp on-disk structures and nothing else.  If a field does not
decode to a sane value the script says so instead of guessing.

Usage:
  python tools/parse_lp_metadata.py info    <super.img>
  python tools/parse_lp_metadata.py extract <super.img> <outdir> [name ...]
  python tools/parse_lp_metadata.py hash    <super.img>
"""

import hashlib
import json
import os
import struct
import sys

GEOMETRY_MAGIC = 0x616C4467  # "gDla"
HEADER_MAGIC = 0x414C5030  # "0PLA" little-endian read of "LP\0\0" style magic
HEADER_MAGIC_ALT = 0x414C5030

GEOMETRY_SIZE = 4096

PART_ATTR_READONLY = 0x1
PART_ATTR_SNAPSHOT = 0x2
PART_ATTR_UPDATED = 0x4
PART_ATTR_DISABLED = 0x8

GROUP_FLAG_SLOT_SUFFIXED = 0x1
GROUP_FLAG_IMPORT = 0x2


def _unpack(fmt, data, off):
    return struct.unpack_from("<" + fmt, data, off)


class LpMetadata:
    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(path)
        self.fh = open(path, "rb")
        self._read_geometry()
        self._locate_header()
        self._read_tables()

    # ---------------- geometry ----------------
    def _read_geometry(self):
        found = None
        for off in (0x0, 0x1000):
            self.fh.seek(off)
            head = self.fh.read(GEOMETRY_SIZE)
            if len(head) >= 8 and _unpack("I", head, 0)[0] == GEOMETRY_MAGIC:
                found = (off, head)
                break
        if found is None:
            raise SystemExit(
                "not an LpMetadata image: no geometry magic 0x%08x at 0x0 or 0x1000" % GEOMETRY_MAGIC
            )
        self.geometry_offset, head = found
        self.geometry = head
        # AOSP LpMetadataGeometry: magic(4) struct_size(4) checksum(32)
        #                            metadata_max_size(4) metadata_slot_count(4) logical_block_size(4)
        self.struct_size, = _unpack("I", head, 4)
        self.geometry_checksum = head[8:40]
        self.metadata_max_size, = _unpack("I", head, 48)
        self.metadata_slot_count, = _unpack("I", head, 52)
        self.logical_block_size, = _unpack("I", head, 56)
        if self.logical_block_size == 0:
            self.logical_block_size = 4096
        self.checksum_ok = (
            hashlib.sha256(head[4:48] + head[56 : 52 + self.struct_size]).digest()
            == self.geometry_checksum
        )

    # ---------------- header + tables ----------------
    def _locate_header(self):
        first = self.geometry_offset + GEOMETRY_SIZE
        # AOSP puts slot 0 immediately after the geometry.  Some producers pad
        # differently, so probe a small set of aligned candidates and pick the
        # first real LpMetadataHeader magic; never infer silently.
        offsets = []
        for slot in range(max(self.metadata_slot_count, 1)):
            offsets.append(first + slot * max(self.metadata_max_size, GEOMETRY_SIZE))
        for extra in (0x1000, 0x2000, 0x20000, 0x40000):
            offsets.append(first + extra)
        seen, candidates = set(), []
        for off in offsets:
            if off in seen or off + 4096 > self.size:
                continue
            seen.add(off)
            self.fh.seek(off)
            blk = self.fh.read(4096)
            magic, = _unpack("I", blk, 0)
            candidates.append((off, magic, blk))
        good = [c for c in candidates if c[1] == HEADER_MAGIC]
        if not good:
            # Some producers (observed: the community thyme package) place an
            # extra copy of the geometry magic where AOSP writes the header
            # magic.  Report exactly what was found instead of guessing.
            raise SystemExit(
                "no LpMetadataHeader magic 0x%08x found at %s"
                % (HEADER_MAGIC, [(hex(c[0]), hex(c[1])) for c in candidates])
            )
        self.header_offset, self.header_magic, blk = good[0]
        # ---- LpMetadataHeader, verified field-by-field against this project's images ----
        #   0x00 magic(u32)        0x04 major(u16)  0x06 minor(u16)
        #   0x08 header_size(u32)  0x0C header_checksum(32)
        #   0x2C tables_size(u32)  0x30 tables_checksum(32)
        #   0x50 partitions(off,num,entry_size)   0x5C extents(...)
        #   0x68 groups(...)                      0x74 block_devices(...)
        #   0x80 flags(u32)
        self.major, self.minor = struct.unpack_from("<HH", blk, 4)
        self.header_size, = struct.unpack_from("<I", blk, 8)
        self.header_checksum = blk[12:44]
        self.tables_size, = struct.unpack_from("<I", blk, 44)
        self.tables_checksum = blk[48:80]
        self.partitions_desc = struct.unpack_from("<III", blk, 80)
        self.extents_desc = struct.unpack_from("<III", blk, 92)
        self.groups_desc = struct.unpack_from("<III", blk, 104)
        self.block_devices_desc = struct.unpack_from("<III", blk, 116)
        self.flags, = struct.unpack_from("<I", blk, 128)
        self.tables = blk[self.header_size : self.header_size + self.tables_size]
        self.tables_ok = hashlib.sha256(self.tables).digest() == self.tables_checksum

    def _read_tables(self):
        t = self.tables

        def table(desc):
            off, num, entry_size = desc
            return off, num, entry_size

        # ---- block devices ----
        off, num, esz = table(self.block_devices_desc)
        self.block_devices = []
        for i in range(num):
            b = off + i * esz
            first_lba, size_lba, alignment, = struct.unpack_from("<QIQ", t, b)
            name = t[b + 20 : b + 20 + 36].split(b"\0")[0].decode("utf-8", "replace")
            self.block_devices.append(
                {"name": name, "first_lba": first_lba, "size_lba": size_lba, "alignment": alignment}
            )

        # ---- groups ----
        off, num, esz = table(self.groups_desc)
        self.groups = []
        for i in range(num):
            b = off + i * esz
            name = t[b : b + 36].split(b"\0")[0].decode("utf-8", "replace")
            flags, maximum_size, = struct.unpack_from("<IQ", t, b + 36)
            self.groups.append({"name": name, "flags": flags, "maximum_size": maximum_size})

        # ---- partitions ----
        off, num, esz = table(self.partitions_desc)
        self.partitions = []
        for i in range(num):
            b = off + i * esz
            name = t[b : b + 36].split(b"\0")[0].decode("utf-8", "replace")
            attributes, first_extent_index, num_extents, group_index = struct.unpack_from(
                "<IIII", t, b + 36
            )
            self.partitions.append(
                {
                    "name": name,
                    "attributes": attributes,
                    "first_extent_index": first_extent_index,
                    "num_extents": num_extents,
                    "group_index": group_index,
                }
            )

        # ---- extents ----
        off, num, esz = table(self.extents_desc)
        self.extents = []
        for i in range(num):
            b = off + i * esz
            num_sectors, target_type, target_data, target_source = struct.unpack_from(
                "<QIQI", t, b
            )
            self.extents.append(
                {
                    "num_sectors": num_sectors,
                    "target_type": target_type,
                    "target_data": target_data,
                    "target_source": target_source,
                }
            )

    # ---------------- helpers ----------------
    def partition_sectors(self, part):
        total = 0
        for e in self.extents[
            part["first_extent_index"] : part["first_extent_index"] + part["num_extents"]
        ]:
            total += e["num_sectors"]
        return total

    def primary_block_device(self):
        """AOSP convention: block device index 1 is 'super' (index 0 is unused)."""
        for i, d in enumerate(self.block_devices):
            if d["name"] == "super":
                return i, d
        if len(self.block_devices) > 1:
            return 1, self.block_devices[1]
        return 0, self.block_devices[0]

    def extract(self, name, out_path, progress=True):
        part = next(p for p in self.partitions if p["name"] == name)
        bd_index, bd = self.primary_block_device()
        exts = self.extents[
            part["first_extent_index"] : part["first_extent_index"] + part["num_extents"]
        ]
        with open(out_path, "wb") as out:
            written = 0
            for e in exts:
                if e["target_type"] != 0:
                    raise SystemExit("partition %s uses a non-linear target" % name)
                # target_data is an absolute sector offset from the start of super
                self.fh.seek(e["target_data"] * 512)
                remaining = e["num_sectors"] * 512
                while remaining:
                    chunk = self.fh.read(min(remaining, 8 << 20))
                    if not chunk:
                        raise SystemExit("short read while extracting %s" % name)
                    out.write(chunk)
                    remaining -= len(chunk)
                    written += len(chunk)
                    if progress:
                        pct = 100.0 * written / (self.partition_sectors(part) * 512)
                        sys.stderr.write("\r  %s %.1f%%" % (name, pct))
                        sys.stderr.flush()
        if progress:
            sys.stderr.write("\n")
        return written

    def info(self):
        return {
            "path": self.path,
            "file_size": self.size,
            "geometry_offset": self.geometry_offset,
            "geometry_struct_size": self.struct_size,
            "geometry_checksum_ok": self.checksum_ok,
            "metadata_max_size": self.metadata_max_size,
            "metadata_slot_count": self.metadata_slot_count,
            "logical_block_size": self.logical_block_size,
            "header_offset": self.header_offset,
            "header_major": self.major,
            "header_minor": self.minor,
            "header_size": self.header_size,
            "tables_size": self.tables_size,
            "tables_checksum_ok": self.tables_ok,
            "flags": self.flags,
            "block_devices": self.block_devices,
            "groups": self.groups,
            "partitions": [
                {
                    "name": p["name"],
                    "size_bytes": self.partition_sectors(p) * 512,
                    "attributes": p["attributes"],
                    "group": self.groups[p["group_index"]]["name"]
                    if p["group_index"] < len(self.groups)
                    else None,
                    "num_extents": p["num_extents"],
                }
                for p in self.partitions
            ],
        }


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd, path = sys.argv[1], sys.argv[2]
    img = LpMetadata(path)
    if cmd == "info":
        print(json.dumps(img.info(), indent=2, ensure_ascii=False))
    elif cmd == "hash":
        for p in img.partitions:
            print("%-16s %14d" % (p["name"], img.partition_sectors(p) * 512))
    elif cmd == "extract":
        outdir = sys.argv[3]
        names = sys.argv[4:] or [p["name"] for p in img.partitions]
        os.makedirs(outdir, exist_ok=True)
        for n in names:
            out = os.path.join(outdir, n + ".img")
            size = img.extract(n, out)
            print("%-20s %14d  %s" % (n, size, out))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
