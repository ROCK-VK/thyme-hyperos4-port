#!/usr/bin/env python3
"""Add metadata for files intentionally added during candidate adaptation.

The Android donor canned configs describe the donor tree exactly.  A bounded
thyme adaptation may add a small number of target-specific files; this helper
updates only those explicit additions and refuses to rewrite an unrelated
config silently.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def insert_after(lines: list[str], needle: str, addition: str, path: Path) -> list[str]:
    if addition in lines:
        return lines
    try:
        index = lines.index(needle)
    except ValueError as exc:
        raise SystemExit(f"{path}: missing anchor {needle!r}") from exc
    lines.insert(index + 1, addition)
    return lines


def patch_product(candidate: Path, configs: Path) -> None:
    product_root = candidate / "userspace/product/product"
    feature = product_root / "etc/device_features/thyme.xml"
    if not feature.is_file():
        raise SystemExit(f"missing adapted feature file: {feature}")

    fs_config = configs / "product/fs_config"
    fs_lines = fs_config.read_text(encoding="utf-8").splitlines()
    fs_lines = insert_after(
        fs_lines,
        "product/etc/device_features/dada.xml 0 0 0644",
        "product/etc/device_features/thyme.xml 0 0 0644",
        fs_config,
    )
    fs_config.write_text("\n".join(fs_lines) + "\n", encoding="utf-8")

    contexts = configs / "product/file_contexts"
    context_lines = contexts.read_text(encoding="utf-8").splitlines()
    context_lines = insert_after(
        context_lines,
        "/product/etc/device_features/dada\\.xml u:object_r:system_file:s0",
        "/product/etc/device_features/thyme\\.xml u:object_r:system_file:s0",
        contexts,
    )
    contexts.write_text("\n".join(context_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("configs", type=Path)
    args = parser.parse_args()
    patch_product(args.candidate_root.resolve(), args.configs.resolve())
    print("patched product thyme feature metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
