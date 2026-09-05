"""Offline behavioral regressions. No real credentials or API endpoints are used."""
from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "generate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import image_io
import nanobanana as nano
import optimize as opt


def image_bytes(fmt="PNG", color="red", size=(80, 40)):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format=fmt)
    return stream.getvalue()


def image_response(data=None):
    return {"candidates": [{"content": {"parts": [{"inlineData": {
        "mimeType": "image/png", "data": base64.b64encode(data or image_bytes()).decode()}}]}}]}


class IsolatedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        self.enterContext(patch.dict(os.environ, {"HOME": str(self.root / "home")}, clear=True))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected network request")))
        self.enterContext(patch("urllib.request.build_opener", side_effect=AssertionError("Unexpected network request")))

    def config(self, content, path=None):
        path = path or nano.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content))
        return path

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_main(self, *args):
        with redirect_stdout(io.StringIO()) as output:
            result = nano.main(list(args))
        return result, output.getvalue()


class ConfigTests(IsolatedTest):
    def test_config_init_is_private_nonsecret_and_idempotent(self):
        _, output = self.run_main("config", "--init")
        path = Path(output.strip())
        self.assertTrue(path.is_relative_to(self.root / "home"))
        self.assertNotIn("gemini_api_key", json.loads(path.read_text()))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        path.write_text('{"default_model":"flash"}')
        self.run_main("config", "--init")
        self.assertEqual(json.loads(path.read_text()), {"default_model": "flash"})

    def test_legacy_yaml_comments_and_global_precedence(self):
        self.config({"default_model": "pro", "default_size": "2K"})
        legacy = self.write(".claude/nano-banana-pro.local.md", b'---\ndefault_model: flash # local\nmax_remix_images: 0\n---\nBody')
        self.assertEqual(nano.load_settings(), {"default_model": "flash", "default_size": "2K", "max_remix_images": 0})
        explicit = self.config({"default_model": "gemini-2.5-flash-image"}, self.root / "custom.json")
        self.assertEqual(nano.load_settings(str(explicit)), {"default_model": "gemini-2.5-flash-image"})
        self.assertEqual(nano.parse_settings_file(legacy)["max_remix_images"], 0)

    def test_invalid_config_does_not_echo_legacy_key(self):
        path = self.write("invalid.md", b'---\ngemini_api_key: [secret-value\n---\n')
        with self.assertRaises(ValueError) as context:
            nano.parse_settings_file(path)
        self.assertNotIn("secret-value", str(context.exception))

    def test_missing_explicit_config_fails(self):
        with self.assertRaises(FileNotFoundError):
            nano.load_settings("missing.json")

    def test_api_key_precedence_and_placeholder(self):
        self.write(".env", b'GEMINI_API_KEY="project-value"\n')
        self.write("home/.env", b'GEMINI_API_KEY="home-value"\n')
        with patch.dict(os.environ, {"GEMINI_API_KEY": "environment-value"}):
            self.assertEqual(nano.load_api_key({"gemini_api_key": "legacy-value"}), "environment-value")
        self.assertEqual(nano.load_api_key({"gemini_api_key": "legacy-value"}), "project-value")
        (self.root / ".env").unlink()
        self.assertEqual(nano.load_api_key(), "home-value")
        (self.root / "home/.env").unlink()
        self.assertIsNone(nano.load_api_key({"gemini_api_key": "YOUR_API_KEY_HERE"}))

    def test_absolute_tilde_and_parent_output_paths(self):
        self.assertEqual(nano.infer_out_path(None, {"output_dir": str(self.root / "absolute")}).parent, self.root / "absolute")
        self.assertEqual(nano.infer_out_path(None, {"output_dir": "~/images"}).parent, self.root / "home/images")
        self.assertEqual(nano.infer_out_path(None, {"output_dir": "../images"}).resolve().parent, self.root.parent / "images")
        self.assertFalse((self.root / "absolute").exists())


class GenerationTests(IsolatedTest):
    def test_dry_run_no_key_no_output_or_request(self):
        result, output = self.run_main("gen", "--prompt", "A mountain", "--model", "flash", "--dry-run")
        payload = json.loads(output)
        self.assertEqual(result, 0)
        self.assertIn("/v1/models/gemini-3.1-flash-image:", payload["endpoint"])
        self.assertFalse(Path(payload["output"]).parent.exists())

    def test_flash_small_size_uses_documented_rest_value(self):
        for size in ("512", "512px"):
            body = nano.build_request([{"text": "test"}], "1:1", size, False, "flash")
            self.assertEqual(body["generationConfig"]["imageConfig"]["imageSize"], "512")

    def test_search_grounding_metadata_is_preserved_for_attribution(self):
        response = image_response()
        metadata = {"groundingChunks": [{"web": {"uri": "https://example.com/source", "title": "Source"}}],
                    "searchEntryPoint": {"renderedContent": "<div>Suggestions</div>"}}
        response["candidates"][0]["groundingMetadata"] = metadata
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as output:
            nano.process_and_save_result(response, self.root / "grounded.png")
        self.assertIn(json.dumps(metadata), output.getvalue())

    def test_raw_model_override_and_unknown_name(self):
        self.assertIn("gemini-3-pro-image-preview", nano.get_endpoint("models/gemini-3-pro-image-preview"))
        self.assertIn("/v1beta/", nano.get_endpoint("gemini-3-pro-image-preview"))
        with self.assertRaises(ValueError):
            nano.get_endpoint("prro")
        with self.assertRaises(ValueError):
            nano.get_endpoint("gemini-foo?key=secret")

    def test_invalid_options_rejected_before_paid_call(self):
        for args in [("--model", "pro", "--size", "512px"),
                     ("--model", "gemini-2.5-flash-image", "--search"),
                     ("--timeout", "0")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.run_main("gen", "--prompt", "image", *args)

    def test_edit_uses_actual_mime_and_dryrun_omits_image_data(self):
        path = self.write("misnamed.png", image_bytes("JPEG"))
        result, output = self.run_main("edit", "--in", str(path), "--prompt", "Make it blue", "--dry-run")
        part = json.loads(output)["request"]["contents"][0]["parts"][1]["inlineData"]
        self.assertEqual(part["mimeType"], "image/jpeg")
        self.assertIn("omitted", part["data"])
        self.assertEqual(result, 0)

    def test_generation_saves_requested_format_after_one_call(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only"}), patch.object(nano, "call_gemini", return_value=image_response()) as call:
            result, output = self.run_main("gen", "--prompt", "Test", "--out", "nested/image.jpg")
        call.assert_called_once()
        self.assertEqual(result, 0)
        with Image.open(output.strip()) as image:
            self.assertEqual(image.format, "JPEG")

    def test_existing_output_rejected_before_paid_call(self):
        self.write("existing.png", b"keep")
        with patch.object(nano, "call_gemini") as call, self.assertRaises(FileExistsError):
            self.run_main("gen", "--prompt", "Test", "--out", "existing.png")
        call.assert_not_called()
        self.assertEqual((self.root / "existing.png").read_bytes(), b"keep")

    def test_no_image_leaves_existing_output_unchanged(self):
        path = self.write("existing.png", b"keep")
        with self.assertRaisesRegex(RuntimeError, "SAFETY"):
            nano.process_and_save_result({"promptFeedback": {"blockReason": "SAFETY"}}, path, True)
        self.assertEqual(path.read_bytes(), b"keep")

    def test_thought_image_is_skipped(self):
        response = image_response(image_bytes(color="blue"))
        parts = response["candidates"][0]["content"]["parts"]
        parts.insert(0, {"thought": True, "inlineData": {"mimeType": "image/png", "data": "thought-only"}})
        self.assertEqual(nano.extract_first_image_b64(response), parts[1]["inlineData"]["data"])

    def test_invalid_image_data_does_not_write_output(self):
        response = image_response()
        response["candidates"][0]["content"]["parts"][0]["inlineData"]["data"] = "%%%%"
        with self.assertRaises(ValueError):
            nano.process_and_save_result(response, self.root / "bad.png")
        self.assertFalse((self.root / "bad.png").exists())

    def test_timeout_does_not_retry(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError) as call:
            with self.assertRaisesRegex(RuntimeError, "Completion is unknown"):
                nano.call_gemini("test-key", [{"text": "test"}], "1:1", None, False)
        call.assert_called_once()

    def test_http_error_does_not_echo_server_body_or_retry(self):
        error = urllib.error.HTTPError("https://example.com", 429, "error", {}, io.BytesIO(b"secret-echo"))
        with patch("urllib.request.urlopen", side_effect=error) as call:
            with self.assertRaises(RuntimeError) as caught:
                nano.call_gemini("test-key", [{"text": "test"}], "1:1", None, False)
        self.assertNotIn("secret-echo", str(caught.exception))
        self.assertIn("429", str(caught.exception))
        call.assert_called_once()

    def test_response_read_is_bounded(self):
        response = Mock()
        response.read.return_value = b'{}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("urllib.request.urlopen", return_value=response):
            nano.call_gemini("test-key", [{"text": "test"}], "1:1", None, False)
        response.read.assert_called_once_with(nano.MAX_RESPONSE_BYTES + 1)

    def test_request_body_is_bounded(self):
        with patch.object(nano, "MAX_REQUEST_BYTES", 30), self.assertRaisesRegex(ValueError, "20 MB"):
            nano.build_request([{"text": "large"}], "1:1", None, False, "pro")

    def test_cli_errors_have_no_traceback(self):
        process = subprocess.run([sys.executable, str(SCRIPTS / "nanobanana.py"), "gen", "--prompt", "test", "--timeout", "0"], text=True, capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertNotIn("Traceback", process.stderr)


class RemixTests(IsolatedTest):
    def test_extracts_metadata_regardless_of_attribute_order(self):
        hints = nano.extract_page_hints('''<title>Colors &amp; Style</title>
<meta content="Our &quot;brand&quot;" name="description">
<meta content="/asset.png" property="og:image">
<link href="/icon.png" rel="icon">
<style>:root { --accent: #123456; --alpha: #aabbccdd; color: #fff; font-family: Inter, sans-serif; }</style>''', "https://example.com/page")
        self.assertEqual(hints["title"], "Colors & Style")
        self.assertEqual(hints["description"], 'Our "brand"')
        self.assertEqual(hints["image_urls"], ["https://example.com/asset.png"])
        self.assertEqual(hints["palette"], ["#123456", "#aabbccdd", "#fff"])

    def test_cli_reference_count_overrides_settings_including_zero(self):
        self.config({"max_remix_images": 4})
        with patch.object(nano, "http_get_text", return_value="<title>Brand</title>"), patch.object(nano, "download_images_as_parts", return_value=[]) as download:
            self.run_main("remix-url", "--url", "https://example.com", "--prompt", "banner", "--max-images", "0", "--dry-run")
        self.assertEqual(download.call_args.args[1], 0)

    def test_invalid_remix_count_rejected_without_network(self):
        for count in ("-1", "5"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.run_main("remix-url", "--url", "https://example.com", "--prompt", "banner", "--max-images", count, "--dry-run")

    def test_reference_attempts_bounded_and_html_rejected(self):
        with patch.object(nano, "http_get_bytes", return_value=(b"<html>not an image</html>", {"content-type": "image/png"})) as call:
            self.assertEqual(nano.download_images_as_parts([f"https://example.com/{i}" for i in range(100)], 2, 1000), [])
        self.assertEqual(call.call_count, 6)

    def test_reference_mime_comes_from_bytes(self):
        with patch.object(nano, "http_get_bytes", return_value=(image_bytes("WEBP"), {"content-type": "image/png"})):
            parts = nano.download_images_as_parts(["https://example.com/image"], 1, 4000000)
        self.assertEqual(parts[0]["inlineData"]["mimeType"], "image/webp")

    def test_url_schemes_and_credentials_rejected(self):
        for url in ("file:///etc/passwd", "data:image/png,xx", "https://user:password@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                nano.http_get_bytes(url, 100)


class OptimizerTests(IsolatedTest):
    def test_sub_kib_byte_limits_not_truncated(self):
        self.assertEqual(opt.parse_size("500B"), 500)
        self.assertEqual(opt.parse_size("0.5KB"), 512)
        for size in ("0", "-4KB", "NaN", "1GB", "0.001B"):
            with self.subTest(size=size), self.assertRaises(ValueError):
                opt.parse_size(size)

    def test_real_width_and_size_constraints_and_source_preservation(self):
        source = Image.frombytes("RGB", (500, 700), random.Random(42).randbytes(500 * 700 * 3))
        source.save(self.root / "source.png")
        before = (self.root / "source.png").read_bytes()
        result = opt.optimize(self.root / "source.png", self.root / "new/nested.png", 10000, 120)
        with Image.open(result) as image:
            self.assertLessEqual(image.width, 120)
            self.assertAlmostEqual(image.height / image.width, 1.4, delta=0.03)
        self.assertLessEqual(result.stat().st_size, 10000)
        self.assertEqual((self.root / "source.png").read_bytes(), before)

    def test_png_output_matches_suffix_for_jpeg_source(self):
        src = self.write("source.jpg", image_bytes("JPEG"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(opt.main([str(src)]), 0)
        with Image.open(self.root / "source-optimized.png") as image:
            self.assertEqual(image.format, "PNG")

    def test_impossible_constraint_fails_without_clobber(self):
        src = self.write("source.png", image_bytes())
        dst = self.write("existing.webp", b"keep")
        with self.assertRaisesRegex(ValueError, "Cannot meet"):
            opt.optimize(src, dst, 1, None, True)
        self.assertEqual(dst.read_bytes(), b"keep")
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_zero_width_is_rejected(self):
        src = self.write("source.png", image_bytes())
        with self.assertRaises(ValueError):
            opt.optimize(src, self.root / "out.png", None, 0)

    def test_transparency_preserved_and_jpeg_flattened(self):
        image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        for suffix in (".png", ".webp"):
            with Image.open(io.BytesIO(image_io.encode_image(image, suffix))) as result:
                self.assertEqual(result.convert("RGBA").getpixel((0, 0))[3], 0)
        with Image.open(io.BytesIO(image_io.encode_image(image, ".jpg"))) as result:
            self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))

    def test_animation_rejected_instead_of_dropping_frames(self):
        src = self.root / "animated.gif"
        Image.new("RGB", (10, 10), "red").save(src, save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")], duration=100)
        before = src.read_bytes()
        with self.assertRaisesRegex(ValueError, "Animated"):
            opt.optimize(src, self.root / "out.png", None, 5)
        self.assertEqual(src.read_bytes(), before)

    def test_atomic_write_refuses_clobber_and_cleans_temp(self):
        dst = self.write("out.png", b"keep")
        with self.assertRaises(FileExistsError):
            image_io.atomic_write(b"new", dst)
        self.assertEqual(dst.read_bytes(), b"keep")
        self.assertEqual(list(self.root.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
