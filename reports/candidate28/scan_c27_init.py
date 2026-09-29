#!/usr/bin/env python3
"""Read-only, targeted scan of init rc files shipped by Candidate 27."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BUILD = Path("/root/10s_os4_build")
C27_TREE = BUILD / "c27_netd_zygote_cycle_break_20260929_run1/system_tree"
EXTRACT = BUILD / "c28_c27_lp_rc_audit_20260929"
DUMP = ROOT / "tools/erofs-utils/wsl/dump.erofs"
PATTERN = re.compile(
    r"reboot.?recovery|reboot_on_failure|boot-recovery|sys\.powerctl|"
    r"restart zygote|critical|on shutdown|\breboot\b|powerctl",
    re.IGNORECASE,
)


def erofs_children(image: Path, path: str) -> list[tuple[int, str]]:
    result = subprocess.run(
        [str(DUMP), "--ls", f"--path={path}", str(image)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    entries: list[tuple[int, str]] = []
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        match = re.match(r"^\s*\d+\s+(\d+)\s+(.+?)\s*$", line)
        if not match:
            continue
        kind, name = int(match.group(1)), match.group(2)
        if name not in (".", ".."):
            entries.append((kind, name))
    return entries


def erofs_rc_files(image: Path, base: str = "/etc/init") -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    pending = [base]
    while pending:
        directory = pending.pop()
        for kind, name in erofs_children(image, directory):
            path = directory.rstrip("/") + "/" + name
            if kind == 2:
                pending.append(path)
            elif name.endswith(".rc"):
                content = subprocess.run(
                    [str(DUMP), "--cat", f"--path={path}", str(image)],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout
                found[path] = content
    return found


def ext4_rc_files(image: Path, base: str = "/etc/init") -> dict[str, bytes]:
    with tempfile.TemporaryDirectory(prefix="c27-init-rdump-") as temp:
        destination = Path(temp) / "init"
        destination.mkdir()
        subprocess.run(
            ["debugfs", "-R", f"rdump {base} {destination}", str(image)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        found: dict[str, bytes] = {}
        if destination.exists():
            for path in destination.rglob("*.rc"):
                relative = path.relative_to(destination).as_posix()
                found[base.rstrip("/") + "/" + relative] = path.read_bytes()
        return found


def tree_rc_files(root: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for path in root.rglob("*.rc"):
        if path.is_file():
            found["/system/etc/init/" + path.relative_to(root).as_posix()] = path.read_bytes()
    return found


def describe_partition(name: str, image: Path, reader) -> tuple[dict[str, bytes], dict[str, object]]:
    digest = hashlib.sha256()
    with image.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    files = reader(image)
    lines: list[str] = []
    for path, raw in sorted(files.items()):
        text = raw.decode("utf-8", "replace")
        for number, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                lines.append(f"{path}:{number}: {line.strip()}")
    return files, {
        "image": str(image),
        "bytes": image.stat().st_size,
        "sha256": digest.hexdigest().upper(),
        "rc_file_count": len(files),
        "hits": lines,
    }


def main() -> None:
    parts = {
        "system": (C27_TREE / "system/etc/init", None),
        "system_ext": (EXTRACT / "system_ext_a.img", erofs_rc_files),
        "product": (EXTRACT / "product_a.img", erofs_rc_files),
        "vendor": (EXTRACT / "vendor_a.img", ext4_rc_files),
        "odm": (EXTRACT / "odm_a.img", ext4_rc_files),
        "mi_ext": (EXTRACT / "mi_ext_a.img", erofs_rc_files),
    }
    result: dict[str, object] = {}
    for name, (source, reader) in parts.items():
        if name == "system":
            files = tree_rc_files(source)
            lines: list[str] = []
            for path, raw in sorted(files.items()):
                for number, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
                    if PATTERN.search(line):
                        lines.append(f"{path}:{number}: {line.strip()}")
            result[name] = {
                "source": str(source),
                "rc_file_count": len(files),
                "hits": lines,
            }
        else:
            if not source.is_file():
                raise FileNotFoundError(source)
            _, result[name] = describe_partition(name, source, reader)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
