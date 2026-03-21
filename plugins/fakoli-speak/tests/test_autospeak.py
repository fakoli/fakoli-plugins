"""Tests for autospeak module."""

import pytest

from fakoli_speak import autospeak


@pytest.fixture(autouse=True)
def temp_toggle(tmp_path, monkeypatch):
    toggle = tmp_path / "autospeak.enabled"
    monkeypatch.setattr(autospeak, "TOGGLE_FILE", toggle)
    return toggle


class TestToggle:
    def test_disabled_by_default(self):
        assert autospeak.is_enabled() is False

    def test_enable(self):
        autospeak.enable()
        assert autospeak.is_enabled() is True

    def test_disable(self):
        autospeak.enable()
        autospeak.disable()
        assert autospeak.is_enabled() is False

    def test_disable_when_already_disabled(self):
        autospeak.disable()  # Should not raise


class TestStripMarkdown:
    def test_removes_code_blocks(self):
        text = "Hello\n```python\nprint('hi')\n```\nworld"
        assert "print" not in autospeak.strip_markdown(text)
        assert "Hello" in autospeak.strip_markdown(text)
        assert "world" in autospeak.strip_markdown(text)

    def test_removes_inline_code(self):
        result = autospeak.strip_markdown("Use `git status` to check")
        assert "`" not in result
        assert "Use" in result

    def test_removes_markdown_links(self):
        result = autospeak.strip_markdown("See [docs](https://example.com)")
        assert "docs" in result
        assert "https" not in result

    def test_removes_table_rows(self):
        text = "| Col1 | Col2 |\n| --- | --- |\n| a | b |"
        result = autospeak.strip_markdown(text)
        assert "|" not in result

    def test_removes_heading_markers(self):
        result = autospeak.strip_markdown("## My Heading")
        assert result == "My Heading"

    def test_removes_bold_italic(self):
        result = autospeak.strip_markdown("This is **bold** and *italic*")
        assert "**" not in result
        assert "*" not in result
        assert "bold" in result
        assert "italic" in result

    def test_removes_blockquotes(self):
        result = autospeak.strip_markdown("> quoted text")
        assert ">" not in result
        assert "quoted text" in result

    def test_removes_bullet_markers(self):
        result = autospeak.strip_markdown("- item one\n- item two")
        assert "- " not in result
        assert "item one" in result

    def test_removes_html_tags(self):
        result = autospeak.strip_markdown("Hello <br> world")
        assert "<br>" not in result

    def test_collapses_whitespace(self):
        result = autospeak.strip_markdown("Hello\n\n\n\n\nworld")
        assert "\n\n\n" not in result


class TestExtractTextFromHook:
    def test_extracts_from_result_field(self):
        hook = {"result": "x" * 200}
        text = autospeak.extract_text_from_hook(hook)
        assert text is not None
        assert len(text) >= 100

    def test_extracts_from_response_field(self):
        hook = {"response": "y" * 200}
        text = autospeak.extract_text_from_hook(hook)
        assert text is not None

    def test_extracts_from_content_field(self):
        hook = {"content": "z" * 200}
        text = autospeak.extract_text_from_hook(hook)
        assert text is not None

    def test_returns_none_for_short_text(self):
        hook = {"result": "OK"}
        text = autospeak.extract_text_from_hook(hook)
        assert text is None

    def test_returns_none_for_empty_hook(self):
        text = autospeak.extract_text_from_hook({})
        assert text is None

    def test_strips_markdown_from_result(self):
        hook = {"result": "# Header\n```code```\n" + "Real content. " * 20}
        text = autospeak.extract_text_from_hook(hook)
        assert text is not None
        assert "#" not in text
        assert "```" not in text

    def test_extracts_from_transcript_messages(self):
        hook = {
            "transcript_messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "a" * 200},
            ]
        }
        text = autospeak.extract_text_from_hook(hook)
        assert text is not None

    def test_skips_non_string_content(self):
        hook = {"result": 12345}
        text = autospeak.extract_text_from_hook(hook)
        assert text is None
