"""Validated image input and atomic, format-correct output shared by the CLIs."""
from __future__ import annotations

import io
import os
from pathlib import Path
import tempfile

from PIL import Image, ImageOps

OUTPUT_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
INPUT_MIMES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
MAX_INPUT_BYTES = 12 * 1024 * 1024


def validate_output(path: Path, overwrite: bool = False) -> None:
    if path.suffix.lower() not in OUTPUT_FORMATS:
        raise ValueError("Output must end in .png, .jpg, .jpeg, or .webp")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}; choose another path or use --overwrite")
    if path.is_dir():
        raise IsADirectoryError(str(path))


def image_mime(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        mime = INPUT_MIMES.get(img.format)
        if not mime or getattr(img, "n_frames", 1) != 1:
            raise ValueError("Input must be a static PNG, JPEG, or WebP image")
        img.verify()
    return mime


def open_image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as img:
        if getattr(img, "n_frames", 1) != 1:
            raise ValueError("Animated images are unsupported; choose a static frame first")
        return ImageOps.exif_transpose(img).copy()


def encode_image(img: Image.Image, suffix: str) -> bytes:
    fmt = OUTPUT_FORMATS[suffix.lower()]
    if fmt == "JPEG":
        rgba = img.convert("RGBA")
        img = Image.new("RGB", rgba.size, "white")
        img.paste(rgba, mask=rgba.getchannel("A"))
    elif img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA")
    buffer = io.BytesIO()
    options = {"quality": 90} if fmt in ("JPEG", "WEBP") else {}
    img.save(buffer, format=fmt, optimize=True, **options)
    return buffer.getvalue()


def atomic_write(data: bytes, path: Path, overwrite: bool = False) -> None:
    """Publish a complete file, never clobber an existing path unless requested."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        if overwrite:
            os.replace(temp, path)
        else:
            os.link(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
