#!/usr/bin/env python3
"""Audit or remove local ChronoRoute pipeline artifacts.

Default mode is dry-run. Pass --apply to delete ignored local data lake files.
This script never deletes source code, docs, DAGs, or public dashboard artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

LAYER_PATTERNS = {
    "bronze": [DATA_DIR / "bronze"],
    "silver": [DATA_DIR / "silver"],
    "gold": [DATA_DIR / "gold"],
    "legacy_raw": [
        DATA_DIR / "yellow_tripdata_*.parquet",
        DATA_DIR / "green_tripdata_*.parquet",
        DATA_DIR / "fhv_tripdata_*.parquet",
        DATA_DIR / "fhvhv_tripdata_*.parquet",
    ],
}


def iter_files(layer: str) -> list[Path]:
    files: list[Path] = []
    for pattern in LAYER_PATTERNS[layer]:
        if "*" in str(pattern):
            files.extend(path for path in pattern.parent.glob(pattern.name) if path.is_file())
        elif pattern.exists():
            files.extend(path for path in pattern.rglob("*") if path.is_file() and path.name != "README.md")
    return sorted(files)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit or remove local ignored ChronoRoute data artifacts.")
    parser.add_argument(
        "--layers",
        nargs="+",
        choices=sorted(LAYER_PATTERNS),
        default=["bronze", "silver", "legacy_raw"],
        help="Ignored local data layers to audit or delete.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete matching files. Without this, only prints a dry-run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    all_files: list[Path] = []
    for layer in args.layers:
        files = iter_files(layer)
        size = sum(path.stat().st_size for path in files)
        print(f"{layer}: {len(files)} files, {format_bytes(size)}")
        all_files.extend(files)

    total_size = sum(path.stat().st_size for path in all_files)
    action = "Deleting" if args.apply else "Dry-run; would delete"
    print(f"{action}: {len(all_files)} files, {format_bytes(total_size)}")

    if args.apply:
        for path in all_files:
            path.unlink()
    else:
        print("Pass --apply to delete these ignored local files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
