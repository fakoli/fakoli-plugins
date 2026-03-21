"""Tests for TTS engine module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fakoli_speak import tts


@pytest.fixture(autouse=True)
def temp_pid_file(tmp_path, monkeypatch):
    pid_path = tmp_path / "claude-tts.pid"
    monkeypatch.setattr(tts, "PID_FILE", pid_path)
    return pid_path


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-123")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")


class TestStop:
    def test_stop_removes_pid_file(self, temp_pid_file):
        temp_pid_file.write_text("99999")
        tts.stop()
        assert not temp_pid_file.exists()

    def test_stop_handles_missing_pid_file(self):
        tts.stop()  # Should not raise


class TestStatus:
    def test_idle_when_no_pid(self):
        s = tts.status()
        assert s["playing"] is False
        assert s["pid"] is None

    def test_idle_when_stale_pid(self, temp_pid_file):
        temp_pid_file.write_text("99999")  # Very unlikely to be a real PID
        s = tts.status()
        assert s["playing"] is False

    def test_returns_voice_and_model(self, mock_env):
        s = tts.status()
        assert s["voice_id"] == "test-voice"
        assert s["model_id"] == "eleven_turbo_v2_5"


class TestListVoices:
    @patch("fakoli_speak.tts.httpx.get")
    def test_returns_parsed_voices(self, mock_get, mock_env):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
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
                {
                    "voice_id": "def456",
                    "name": "Adam",
                    "labels": {"accent": "british", "gender": "male"},
                },
            ]
        }
        mock_get.return_value = mock_resp

        voices = tts.list_voices()
        assert len(voices) == 2
        assert voices[0]["name"] == "Rachel"
        assert voices[0]["accent"] == "american"
        assert voices[1]["gender"] == "male"

    @patch("fakoli_speak.tts.httpx.get")
    def test_handles_missing_labels(self, mock_get, mock_env):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "voices": [{"voice_id": "x", "name": "Test"}]
        }
        mock_get.return_value = mock_resp

        voices = tts.list_voices()
        assert voices[0]["accent"] == "unknown"
        assert voices[0]["gender"] == "unknown"


class TestSpeak:
    def test_rejects_empty_text(self, mock_env):
        with pytest.raises(SystemExit):
            tts.speak("")

    def test_rejects_whitespace_only(self, mock_env):
        with pytest.raises(SystemExit):
            tts.speak("   ")

    def test_truncates_long_text(self):
        text = "a" * 5000
        truncated = text[: tts.MAX_CHARS]
        assert len(truncated) == 4000

    @patch("fakoli_speak.tts._find_player", return_value=None)
    def test_exits_when_no_player(self, _mock, mock_env):
        with pytest.raises(SystemExit):
            tts.speak("hello")


class TestFindPlayer:
    @patch("subprocess.run")
    def test_finds_afplay(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = tts._find_player()
        assert result is not None
        assert result[0] == "afplay"

    @patch("subprocess.run")
    def test_returns_none_when_no_player(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = tts._find_player()
        assert result is None


class TestGetApiKey:
    def test_exits_when_missing(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            tts._get_api_key()

    def test_returns_key(self, mock_env):
        assert tts._get_api_key() == "test-key-123"
