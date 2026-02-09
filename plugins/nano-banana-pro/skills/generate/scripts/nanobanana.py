#!/usr/bin/env python3
"""
Nano Banana Pro CLI (Gemini 3 Pro Image Preview) - Python version

- Key lookup: settings file, GEMINI_API_KEY, then .env in cwd, then ~/.env
- Commands: gen, edit, remix-url
- Stdlib-only (urllib + base64 + regex)

REST endpoint (Google Gemini API):
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent
Header: x-goog-api-key: $GEMINI_API_KEY

Remix mode (enhanced):
- Extracts:
  - Title + description
  - Theme colors: meta theme-color + CSS variable hexes
  - Typography hints: Google Fonts + font-family in inline CSS
  - Reference images: og:image / twitter:image / favicon
- Passes extracted hints + up to N reference images to the model to help match style.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, Optional, List, Tuple

from dotenv import dotenv_values


MODEL_MAP = {
    "pro": "gemini-3-pro-image-preview",
    "flash": "gemini-2.0-flash-preview-image-generation",
}


def get_endpoint(model_name: str) -> str:
    model_id = MODEL_MAP.get(model_name, MODEL_MAP["pro"])
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"


def parse_settings_file(path: pathlib.Path) -> Dict[str, str]:
    """Parse a .claude/*.local.md settings file with YAML frontmatter."""
    if not path.exists():
        return {}

    content = path.read_text(encoding="utf-8", errors="ignore")

    # Extract YAML frontmatter between --- markers
    if not content.startswith("---"):
        return {}

    lines = content.split("\n")
    frontmatter_lines = []
    in_frontmatter = False

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            break
        if in_frontmatter:
            frontmatter_lines.append(line)

    # Simple YAML parsing (key: value pairs only)
    settings: Dict[str, str] = {}
    for line in frontmatter_lines:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        # Remove quotes
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        settings[k] = v

    return settings


def load_api_key() -> Optional[str]:
    """Load API key from settings file, env var, or .env files."""

    # 1. Check settings file: .claude/nano-banana-pro.local.md
    settings_path = pathlib.Path(os.getcwd()) / ".claude" / "nano-banana-pro.local.md"
    settings = parse_settings_file(settings_path)
    if settings.get("gemini_api_key"):
        return settings["gemini_api_key"]

    # 2. Environment variable
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

    # 3. Workspace .env
    cwd_env = pathlib.Path(os.getcwd()) / ".env"
    if cwd_env.exists():
        env = dotenv_values(cwd_env)
        if env.get("GEMINI_API_KEY"):
            return env["GEMINI_API_KEY"]

    # 4. Home .env
    home_env = pathlib.Path.home() / ".env"
    if home_env.exists():
        env = dotenv_values(home_env)
        if env.get("GEMINI_API_KEY"):
            return env["GEMINI_API_KEY"]

    return None


def load_settings() -> Dict[str, str]:
    """Load all settings from the settings file."""
    settings_path = pathlib.Path(os.getcwd()) / ".claude" / "nano-banana-pro.local.md"
    return parse_settings_file(settings_path)


def ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def infer_out_path(out_arg: Optional[str], settings: Optional[Dict[str, str]] = None) -> pathlib.Path:
    if out_arg:
        return pathlib.Path(out_arg)

    # Check settings for custom output dir
    output_dir = "./.nanobanana/out"
    if settings and settings.get("output_dir"):
        output_dir = settings["output_dir"]

    out_dir = pathlib.Path(os.getcwd()) / output_dir.lstrip("./")
    ensure_dir(out_dir)
    stamp = datetime.datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
    return out_dir / f"nanobanana-{stamp}.png"


def guess_mime_from_url(url: str) -> str:
    u = url.lower()
    if u.endswith(".png"):
        return "image/png"
    if u.endswith(".jpg") or u.endswith(".jpeg"):
        return "image/jpeg"
    if u.endswith(".webp"):
        return "image/webp"
    if u.endswith(".gif"):
        return "image/gif"
    if u.endswith(".svg"):
        return "image/svg+xml"
    if u.endswith(".ico"):
        return "image/x-icon"
    return "application/octet-stream"


def file_to_inline_part(file_path: str) -> Dict[str, Any]:
    p = pathlib.Path(file_path)
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return {"inline_data": {"mime_type": "image/png", "data": b64}}


def http_get_bytes(url: str, max_bytes: int) -> Tuple[bytes, Dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "nanobanana/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError(f"Downloaded content exceeds max_bytes={max_bytes} for {url}")
        return data, headers


def http_get_text(url: str) -> str:
    data, headers = http_get_bytes(url, max_bytes=2_000_000)
    # naive encoding handling; fallback to utf-8
    return data.decode("utf-8", errors="ignore")


def extract_page_hints(html: str, url: str) -> Dict[str, Any]:
    # Title
    title_m = re.search(r"<title[^>]*>([^<]*)</title>", html, re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else ""

    # Meta description (standard + OG)
    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not desc_m:
        desc_m = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
    desc = desc_m.group(1).strip() if desc_m else ""

    # Theme color
    theme_m = re.search(
        r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    theme_color = theme_m.group(1).strip() if theme_m else ""

    # OG/Twitter images
    og_images = re.findall(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    tw_images = re.findall(
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    # Favicon(s)
    icons = re.findall(
        r'<link[^>]+rel=["\'](?:icon|shortcut icon|apple-touch-icon)["\'][^>]*href=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    # Typography hints: Google Fonts link + font-family in inline styles
    google_fonts = re.findall(
        r'https?://fonts\.googleapis\.com/css[^"\']+',
        html,
        re.IGNORECASE,
    )

    # Pull some inline style blocks and search for font-family
    font_families: List[str] = []
    for style_block in re.findall(r"<style[^>]*>(.*?)</style>", html, re.IGNORECASE | re.DOTALL):
        for fam in re.findall(r"font-family\s*:\s*([^;}{]+)", style_block, re.IGNORECASE):
            cleaned = re.sub(r"\s+", " ", fam).strip()
            if cleaned and cleaned not in font_families:
                font_families.append(cleaned)
            if len(font_families) >= 5:
                break
        if len(font_families) >= 5:
            break

    # Palette hints: hex colors in CSS variables / :root blocks
    # Capture some hex codes, but keep it small.
    hexes = re.findall(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", html)
    palette: List[str] = []
    if theme_color and theme_color.startswith("#"):
        palette.append(theme_color)
    for h in hexes:
        if h.lower() not in [x.lower() for x in palette]:
            palette.append(h)
        if len(palette) >= 6:
            break

    # Normalize asset URLs relative to page
    def absolutize(u: str) -> str:
        return urllib.parse.urljoin(url, u)

    image_urls: List[str] = []
    for u in og_images + tw_images:
        u = u.strip()
        if u:
            image_urls.append(absolutize(u))
    icon_urls: List[str] = []
    for u in icons:
        u = u.strip()
        if u:
            icon_urls.append(absolutize(u))

    # Deduplicate while preserving order
    def dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in seq:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    return {
        "url": url,
        "title": title,
        "description": desc,
        "theme_color": theme_color,
        "palette": palette,
        "google_fonts": dedupe(google_fonts)[:3],
        "font_families": font_families[:5],
        "image_urls": dedupe(image_urls),
        "icon_urls": dedupe(icon_urls),
    }


def download_images_as_parts(urls: List[str], max_images: int, max_bytes: int) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = []
    count = 0
    for u in urls:
        if count >= max_images:
            break
        try:
            data, headers = http_get_bytes(u, max_bytes=max_bytes)
            mime = headers.get("content-type", "").split(";")[0].strip().lower() or guess_mime_from_url(u)
            # Only pass actual images; skip HTML or unknown
            if not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(data).decode("ascii")
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})
            count += 1
        except Exception:
            # Best-effort: ignore broken or oversized images
            continue
    return parts


def call_gemini(
    api_key: str,
    parts: List[Dict[str, Any]],
    aspect: str,
    size: Optional[str],
    use_search: bool,
    model: str = "pro",
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect},
        },
    }
    if size:
        body["generationConfig"]["imageConfig"]["imageSize"] = size

    if use_search:
        body["tools"] = [{"google_search": {}}]

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        get_endpoint(model),
        method="POST",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"Gemini API error {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}") from e


def extract_first_image_b64(resp: Dict[str, Any]) -> Optional[str]:
    candidates = resp.get("candidates") or []
    if not candidates:
        return None
    content = (candidates[0].get("content") or {})
    parts = content.get("parts") or []
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and isinstance(inline, dict):
            data = inline.get("data")
            if data:
                return data
    return None


def write_image_from_b64(b64: str, out_path: pathlib.Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))


def process_and_save_result(resp: Dict[str, Any], out_path: pathlib.Path) -> int:
    """Extract image from response, save to disk, print path."""
    b64 = extract_first_image_b64(resp)
    if not b64:
        raise RuntimeError("No image returned (missing inlineData).")
    write_image_from_b64(b64, out_path)
    print(str(out_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nanobanana", description="Nano Banana Pro CLI (Gemini 3 Pro Image)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--aspect", default=None, help='Aspect ratio like "1:1", "16:9", "4:3" (default from settings or 1:1)')
        sp.add_argument("--size", default=None, choices=["1K", "2K", "4K"], help="Image size tier (optional, default from settings)")
        sp.add_argument("--search", action="store_true", help="Enable Google Search grounding (if available)")
        sp.add_argument("--model", default=None, choices=["pro", "flash"], help="Gemini model (pro or flash, default from settings or pro)")

    gen = sub.add_parser("gen", help="Generate an image from a prompt")
    gen.add_argument("--prompt", required=True, help="Text prompt")
    gen.add_argument("--out", default=None, help="Output path (PNG)")
    add_common(gen)

    edit = sub.add_parser("edit", help="Edit an image with a prompt + input image")
    edit.add_argument("--prompt", required=True, help="Edit instructions")
    edit.add_argument("--in", dest="in_path", required=True, help="Input image path (PNG recommended)")
    edit.add_argument("--out", default=None, help="Output path (PNG)")
    add_common(edit)

    remix = sub.add_parser("remix-url", help="Fetch a webpage and remix it into an image")
    remix.add_argument("--url", required=True, help="Webpage URL")
    remix.add_argument("--prompt", required=True, help="What to create from the page")
    remix.add_argument("--out", default=None, help="Output path (PNG)")
    remix.add_argument("--max-images", type=int, default=2, help="Max reference images to download and pass")
    remix.add_argument("--max-bytes", type=int, default=4_000_000, help="Max bytes per reference image")
    add_common(remix)

    return p


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)

    api_key = load_api_key()
    if not api_key:
        sys.stderr.write("Missing GEMINI_API_KEY (settings file, env, .env, or ~/.env)\n")
        return 2

    # Load settings for defaults
    settings = load_settings()

    # Apply defaults from settings
    aspect = getattr(args, "aspect", None) or settings.get("default_aspect", "1:1")
    size = getattr(args, "size", None) or settings.get("default_size", None)
    use_search = bool(getattr(args, "search", False))
    model = getattr(args, "model", None) or settings.get("default_model", "pro")

    if args.cmd == "gen":
        out_path = infer_out_path(args.out, settings)
        resp = call_gemini(
            api_key=api_key,
            parts=[{"text": str(args.prompt)}],
            aspect=aspect,
            size=size,
            use_search=use_search,
            model=model,
        )
        return process_and_save_result(resp, out_path)

    if args.cmd == "edit":
        out_path = infer_out_path(args.out, settings)
        image_part = file_to_inline_part(str(args.in_path))
        resp = call_gemini(
            api_key=api_key,
            parts=[{"text": str(args.prompt)}, image_part],
            aspect=aspect,
            size=size,
            use_search=use_search,
            model=model,
        )
        return process_and_save_result(resp, out_path)

    if args.cmd == "remix-url":
        out_path = infer_out_path(args.out, settings)
        html = http_get_text(str(args.url))
        hints = extract_page_hints(html, str(args.url))

        # Reference images: prefer og/twitter images; fall back to icons
        ref_urls: List[str] = []
        ref_urls.extend(hints.get("image_urls", []))
        # Add first icon only if no OG/Twitter images, or as a secondary reference
        icon_urls = hints.get("icon_urls", [])
        if icon_urls:
            ref_urls.extend(icon_urls[:1])

        max_images_setting = int(settings.get("max_remix_images", str(getattr(args, "max_images", 2))))
        image_parts = download_images_as_parts(
            urls=ref_urls,
            max_images=max_images_setting,
            max_bytes=int(getattr(args, "max_bytes", 4_000_000)),
        )

        palette = hints.get("palette") or []
        fonts = hints.get("google_fonts") or []
        fams = hints.get("font_families") or []

        style_hints = []
        if hints.get("theme_color"):
            style_hints.append(f"Theme color: {hints.get('theme_color')}")
        if palette:
            style_hints.append("Palette candidates: " + ", ".join(palette[:6]))
        if fonts:
            style_hints.append("Google Fonts CSS: " + " | ".join(fonts[:3]))
        if fams:
            style_hints.append("font-family hints: " + " | ".join(fams[:5]))

        combined_prompt = f"""
You are generating a new visual asset inspired by a webpage.
Do NOT copy exact copyrighted imagery; use the page only as style direction.

Webpage URL: {hints.get("url","")}
Title: {hints.get("title","")}
Description: {hints.get("description","")}

Extracted style hints:
{chr(10).join("- " + s for s in style_hints) if style_hints else "- (none found)"}

User request:
{str(args.prompt)}

Design requirements:
- Clean, slide-ready composition
- Clear typography (avoid tiny text)
- Consistent margins and alignment
- If you include text, reproduce it exactly as specified by the user
- Use the extracted palette/typography as inspiration
""".strip()

        parts: List[Dict[str, Any]] = [{"text": combined_prompt}]
        # Provide reference images (if any) after the text instructions.
        parts.extend(image_parts)

        resp = call_gemini(
            api_key=api_key,
            parts=parts,
            aspect=aspect,
            size=size,
            use_search=use_search,
            model=model,
        )
        return process_and_save_result(resp, out_path)

    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as e:
        sys.stderr.write((str(e) + "\n"))
        raise
