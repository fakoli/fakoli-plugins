#!/usr/bin/env python3
"""
Image optimizer for nano-banana-pro plugin.

Cross-platform support:
- macOS: Uses sips (built-in, zero dependencies)
- Other platforms: Uses Pillow

Usage:
    optimize.py <image> [--preset github|slack|web|thumbnail] [--max-size 500KB] [--width 800] [--out path.png]
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Optional

# Presets: max_size_kb, max_width
PRESETS = {
    "github":    {"max_size_kb": 500, "max_width": 1280},
    "slack":     {"max_size_kb": 128, "max_width": 800},
    "web":       {"max_size_kb": 200, "max_width": 1200},
    "thumbnail": {"max_size_kb": 50,  "max_width": 400},
}


def parse_size(size_str: str) -> int:
    """Parse size string like '500KB' or '1MB' to bytes."""
    size_str = size_str.upper().strip()
    if size_str.endswith("KB"):
        return int(float(size_str[:-2]) * 1024)
    elif size_str.endswith("MB"):
        return int(float(size_str[:-2]) * 1024 * 1024)
    elif size_str.endswith("B"):
        return int(size_str[:-1])
    return int(size_str)


class ImageOptimizer(ABC):
    """Abstract base for image optimizers."""

    @abstractmethod
    def get_dimensions(self, path: pathlib.Path) -> tuple[int, int]:
        """Return (width, height) of image."""
        pass

    @abstractmethod
    def resize(self, src: pathlib.Path, dst: pathlib.Path, max_width: int) -> None:
        """Resize image to max_width, preserving aspect ratio."""
        pass

    def optimize(
        self,
        src: pathlib.Path,
        dst: pathlib.Path,
        max_size_kb: Optional[int] = None,
        max_width: Optional[int] = None,
    ) -> pathlib.Path:
        """Optimize image to meet size/dimension constraints."""
        # Start with a copy
        working = dst.with_suffix(".tmp.png")
        shutil.copy2(src, working)

        current_width, _ = self.get_dimensions(working)

        # Apply max_width constraint first
        if max_width and current_width > max_width:
            self.resize(working, working, max_width)

        # Iteratively reduce size if needed
        if max_size_kb:
            max_bytes = max_size_kb * 1024
            attempts = 0
            while working.stat().st_size > max_bytes and attempts < 10:
                current_width, _ = self.get_dimensions(working)
                new_width = int(current_width * 0.8)  # Reduce by 20%
                if new_width < 100:
                    break
                self.resize(working, working, new_width)
                attempts += 1

        # Move to final destination
        shutil.move(working, dst)
        return dst


class SipsOptimizer(ImageOptimizer):
    """macOS sips-based optimizer."""

    def get_dimensions(self, path: pathlib.Path) -> tuple[int, int]:
        result = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.strip().split("\n")
        width = height = 0
        for line in lines:
            if "pixelWidth" in line:
                width = int(line.split(":")[-1].strip())
            elif "pixelHeight" in line:
                height = int(line.split(":")[-1].strip())
        return width, height

    def resize(self, src: pathlib.Path, dst: pathlib.Path, max_width: int) -> None:
        # sips -Z resizes to fit within max dimension, preserving aspect ratio
        subprocess.run(
            ["sips", "-Z", str(max_width), str(src), "--out", str(dst)],
            capture_output=True,
            check=True,
        )


class PillowOptimizer(ImageOptimizer):
    """Pillow-based optimizer for non-macOS platforms."""

    def get_dimensions(self, path: pathlib.Path) -> tuple[int, int]:
        from PIL import Image
        with Image.open(path) as img:
            return img.size

    def resize(self, src: pathlib.Path, dst: pathlib.Path, max_width: int) -> None:
        from PIL import Image
        with Image.open(src) as img:
            # Calculate new height maintaining aspect ratio
            width, height = img.size
            if width <= max_width:
                if src != dst:
                    img.save(dst, "PNG", optimize=True)
                return
            ratio = max_width / width
            new_height = int(height * ratio)
            # Use LANCZOS for high-quality downsampling
            resized = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            resized.save(dst, "PNG", optimize=True)


def get_optimizer() -> ImageOptimizer:
    """Return platform-appropriate optimizer."""
    if sys.platform == "darwin":
        return SipsOptimizer()
    return PillowOptimizer()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="optimize",
        description="Optimize images for GitHub, Slack, web, etc.",
    )
    p.add_argument("image", help="Path to image to optimize")
    p.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        help="Use a named preset (github, slack, web, thumbnail)",
    )
    p.add_argument(
        "--max-size",
        help="Maximum file size (e.g., 500KB, 1MB)",
    )
    p.add_argument(
        "--width",
        type=int,
        help="Maximum width in pixels",
    )
    p.add_argument(
        "--out",
        help="Output path (default: <original>-optimized.png)",
    )
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    src = pathlib.Path(args.image)
    if not src.exists():
        sys.stderr.write(f"Error: File not found: {src}\n")
        return 1

    # Determine constraints
    max_size_kb: Optional[int] = None
    max_width: Optional[int] = None

    if args.preset:
        preset = PRESETS[args.preset]
        max_size_kb = preset["max_size_kb"]
        max_width = preset["max_width"]

    # Custom options override preset
    if args.max_size:
        max_size_kb = parse_size(args.max_size) // 1024
    if args.width:
        max_width = args.width

    # Default to github preset if nothing specified
    if max_size_kb is None and max_width is None:
        preset = PRESETS["github"]
        max_size_kb = preset["max_size_kb"]
        max_width = preset["max_width"]

    # Determine output path
    if args.out:
        dst = pathlib.Path(args.out)
    else:
        dst = src.with_stem(f"{src.stem}-optimized")

    # Get original size for reporting
    original_size = src.stat().st_size

    # Optimize
    optimizer = get_optimizer()
    result = optimizer.optimize(src, dst, max_size_kb, max_width)

    # Report results
    new_size = result.stat().st_size
    reduction = ((original_size - new_size) / original_size) * 100

    print(f"Optimized: {result}")
    print(f"Size: {original_size // 1024}KB → {new_size // 1024}KB ({reduction:.0f}% reduction)")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
