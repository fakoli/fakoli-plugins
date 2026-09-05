#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow>=10,<13"]
# ///
"""Optimize static images with consistent Pillow behavior on every platform."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from PIL import Image

from image_io import atomic_write, encode_image, open_image, validate_output

PRESETS = {
    "github": {"max_size_kb": 500, "max_width": 1280},
    "slack": {"max_size_kb": 128, "max_width": 800},
    "web": {"max_size_kb": 200, "max_width": 1200},
    "thumbnail": {"max_size_kb": 50, "max_width": 400},
}


def parse_size(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(B|KB|MB)?\s*", value, re.IGNORECASE)
    if not match:
        raise ValueError("Size must be positive bytes, KB, or MB (for example 500KB)")
    size = int(float(match[1]) * {"B": 1, "KB": 1024, "MB": 1024**2}[str(match[2] or "B").upper()])
    if size < 1:
        raise ValueError("Size must be at least one byte")
    return size


def optimize(src: Path, dst: Path, max_bytes: int | None, max_width: int | None,
             overwrite: bool = False) -> Path:
    validate_output(dst, overwrite)
    if max_bytes is not None and max_bytes < 1 or max_width is not None and max_width < 1:
        raise ValueError("Size and width constraints must be positive")
    original = open_image(src.read_bytes())
    width = min(original.width, max_width or original.width)
    # Bound work and measure encoded bytes, including targets below 1 KiB.
    for _ in range(64):
        height = max(1, round(original.height * width / original.width))
        resized = original if (width, height) == original.size else original.resize((width, height), Image.Resampling.LANCZOS)
        data = encode_image(resized, dst.suffix)
        if max_bytes is None or len(data) <= max_bytes:
            atomic_write(data, dst, overwrite)
            return dst
        if width == 1:
            break
        width = max(1, min(width - 1, int(width * 0.8)))
    raise ValueError(f"Cannot meet {max_bytes}-byte limit in {dst.suffix} format; no output written")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optimize", description=__doc__)
    parser.add_argument("image", help="Static input image")
    parser.add_argument("--preset", choices=PRESETS)
    parser.add_argument("--max-size", help="Positive maximum bytes, KB, or MB")
    parser.add_argument("--width", type=int, help="Maximum width, preserving aspect ratio")
    parser.add_argument("--out", help="Output path; defaults to <stem>-optimized.png")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.image).expanduser()
    preset = PRESETS.get(args.preset or "")
    if not preset and args.max_size is None and args.width is None:
        preset = PRESETS["github"]
    max_bytes = parse_size(args.max_size) if args.max_size is not None else (preset["max_size_kb"] * 1024 if preset else None)
    max_width = args.width if args.width is not None else (preset["max_width"] if preset else None)
    dst = Path(args.out).expanduser() if args.out else src.with_name(f"{src.stem}-optimized.png")
    original_size = src.stat().st_size
    result = optimize(src, dst, max_bytes, max_width, args.overwrite)
    new_size = result.stat().st_size
    print(f"Optimized: {result.absolute()}")
    print(f"Size: {original_size}B → {new_size}B ({(1 - new_size / original_size) * 100:.0f}% reduction)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        raise SystemExit(1)
