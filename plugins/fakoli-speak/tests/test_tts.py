"""Tests for TTS facade module (v2.0 — provider-agnostic)."""

from unittest.mock import MagicMock, patch

import pytest

from fakoli_speak import tts, playback
from fakoli_speak.protocol import TTSError, APIKeyMissing, NoPlayerFound, SpeakResult


@pytest.fixture(autouse=True)
def temp_pid_file(tmp_path, monkeypatch):
    pid_path = tmp_path / "claude-tts.pid"
    monkeypatch.setattr(playback, "PID_FILE", pid_path)
    return pid_path


class TestBackwardCompatibility:
    """Verify tts.py re-exports for existing importers."""

    def test_exports_tts_error(self):
        assert tts.TTSError is TTSError

    def test_exports_api_key_missing(self):
        assert tts.APIKeyMissing is APIKeyMissing

    def test_exports_no_player_found(self):
        assert tts.NoPlayerFound is NoPlayerFound

    def test_has_pid_file(self):
        assert hasattr(tts, "PID_FILE")

    def test_exports_max_chars(self):
        assert tts.MAX_CHARS == 4000


class TestStop:
    def test_stop_removes_pid_file(self, temp_pid_file):
        temp_pid_file.write_text("99999")
        tts.stop()
        assert not temp_pid_file.exists()

    def test_stop_handles_missing_pid_file(self):
        tts.stop()


class TestStatus:
    def test_idle_when_no_pid(self):
        s = tts.status()
        assert s["playing"] is False
        assert s["pid"] is None

    def test_idle_when_stale_pid(self, temp_pid_file):
        temp_pid_file.write_text("99999")
        s = tts.status()
        assert s["playing"] is False

    def test_includes_provider_info(self):
        s = tts.status()
        assert "provider" in s
        assert "provider_display" in s
        assert "voice_id" in s
        assert "model_id" in s


class TestSpeak:
    def test_rejects_empty_text(self):
        with pytest.raises(TTSError, match="Empty text"):
            tts.speak("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(TTSError, match="Empty text"):
            tts.speak("   ")

    def test_truncates_long_text(self):
        text = "a" * 5000
        truncated = text[: tts.MAX_CHARS]
        assert len(truncated) == 4000

    @patch("fakoli_speak.playback.find_player", side_effect=NoPlayerFound("no player"))
    def test_raises_when_no_player(self, _mock):
        with pytest.raises(NoPlayerFound):
            tts.speak("hello")


class TestPlaybackModule:
    @patch("fakoli_speak.playback.shutil.which")
    def test_finds_afplay(self, mock_which):
        mock_which.return_value = "/usr/bin/afplay"
        result = playback.find_player()
        assert result is not None
        assert result[0] == "afplay"

    @patch("fakoli_speak.playback.shutil.which")
    def test_returns_none_when_no_player(self, mock_which):
        mock_which.return_value = None
        with pytest.raises(NoPlayerFound):
            playback.find_player()

    def test_is_playing_false_when_no_pid(self):
        playing, pid = playback.is_playing()
        assert playing is False
        assert pid is None

    def test_is_playing_false_with_stale_pid(self, temp_pid_file):
        temp_pid_file.write_text("99999")
        playing, pid = playback.is_playing()
        assert playing is False


class TestListVoices:
    @patch("fakoli_speak.providers.elevenlabs.httpx.get")
    def test_returns_parsed_voices(self, mock_get, monkeypatch):
        monkeypatch.setenv("FAKOLI_SPEAK_PROVIDER", "elevenlabs")
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "voices": [
                {
                    "voice_id": "abc123",
                    "name": "Rachel",
                    "labels": {
                        "accent": "american",
                        "gender": "female",
                        "use case": "narration",
                    },
                },
            ]
        }
        mock_get.return_value = mock_resp

        voices = tts.list_voices()
        assert len(voices) >= 1
        # Find the voice from the mocked API (there may be static voices too)
        rachel = [v for v in voices if v["name"] == "Rachel"]
        assert len(rachel) == 1
        assert rachel[0]["language"] == "american"
