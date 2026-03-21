"""ElevenLabs TTS engine with streaming playback."""

import os
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path

import httpx

from . import cost

PID_FILE = Path("/tmp/claude-tts.pid")
MAX_CHARS = 4000

# Player detection order
_PLAYERS = [
    ("afplay", []),
    ("mpv", ["--no-terminal"]),
    ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
]


class TTSError(Exception):
    """Base exception for TTS errors."""


class APIKeyMissing(TTSError):
    """ElevenLabs API key not configured."""


class NoPlayerFound(TTSError):
    """No audio player available on this system."""


class APIError(TTSError):
    """ElevenLabs API returned an error."""


def _find_player() -> tuple[str, list[str]] | None:
    for cmd, args in _PLAYERS:
        if shutil.which(cmd):
            return cmd, args
    return None


def _get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise APIKeyMissing("ELEVENLABS_API_KEY not set. Add it to ~/.env")
    return key


def _get_voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")


def _get_model_id() -> str:
    return os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")


def stop() -> None:
    """Stop any running TTS playback."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, OSError):
            pass
        PID_FILE.unlink(missing_ok=True)

    for cmd, _ in _PLAYERS:
        subprocess.run(
            ["pkill", "-f", f"{cmd}.*claude-tts"],
            capture_output=True,
        )


def status() -> dict:
    """Return current TTS status."""
    playing = False
    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            playing = True
        except (ValueError, ProcessLookupError, OSError):
            PID_FILE.unlink(missing_ok=True)

    return {
        "playing": playing,
        "pid": pid if playing else None,
        "voice_id": _get_voice_id(),
        "model_id": _get_model_id(),
    }


def list_voices() -> list[dict]:
    """Fetch available voices from ElevenLabs."""
    api_key = _get_api_key()
    resp = httpx.get(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    voices = resp.json().get("voices", [])
    return [
        {
            "voice_id": v["voice_id"],
            "name": v["name"],
            "accent": v.get("labels", {}).get("accent", "unknown"),
            "gender": v.get("labels", {}).get("gender", "unknown"),
            "use_case": v.get("labels", {}).get("use case", ""),
        }
        for v in voices
    ]


def _cleanup_after_playback(proc: subprocess.Popen, audio_path: str) -> None:
    """Wait for player to finish, then clean up. Runs in daemon thread."""
    proc.wait()
    try:
        os.unlink(audio_path)
    except OSError:
        pass
    PID_FILE.unlink(missing_ok=True)


def speak(text: str) -> dict:
    """Stream TTS audio for the given text. Returns usage info.

    Raises:
        TTSError: On empty text, missing player, missing API key, or API error.
    """
    if not text.strip():
        raise TTSError("Empty text")

    player = _find_player()
    if player is None:
        raise NoPlayerFound("No audio player found (need afplay, mpv, or ffplay)")

    player_cmd, player_args = player
    text = text[:MAX_CHARS]
    char_count = len(text)

    api_key = _get_api_key()
    voice_id = _get_voice_id()
    model_id = _get_model_id()

    stop()

    audio_file = tempfile.NamedTemporaryFile(
        prefix="claude-tts-", suffix=".mp3", delete=False
    )

    playback_started = False
    try:
        with httpx.stream(
            "POST",
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": model_id,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=30,
        ) as resp:
            if resp.status_code != 200:
                body = resp.read().decode(errors="replace")
                raise APIError(
                    f"ElevenLabs API returned HTTP {resp.status_code}: {body}"
                )

            for chunk in resp.iter_bytes():
                audio_file.write(chunk)

        audio_file.close()

        proc = subprocess.Popen(
            [player_cmd, *player_args, audio_file.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        playback_started = True
        PID_FILE.write_text(str(proc.pid))

        entry = cost.record_usage(char_count, voice_id, model_id)

        # Daemon thread cleans up after playback — no fork needed
        cleanup = threading.Thread(
            target=_cleanup_after_playback,
            args=(proc, audio_file.name),
            daemon=True,
        )
        cleanup.start()

        return {
            "characters": char_count,
            "cost_usd": entry["cost_usd"],
            "voice_id": voice_id,
            "model_id": model_id,
        }

    except httpx.HTTPError as e:
        raise APIError(f"API request failed: {e}") from e
    finally:
        if not playback_started:
            try:
                audio_file.close()
                os.unlink(audio_file.name)
            except OSError:
                pass
