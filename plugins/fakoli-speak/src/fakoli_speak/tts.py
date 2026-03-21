"""ElevenLabs TTS engine with streaming playback."""

import os
import signal
import subprocess
import sys
import tempfile
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


def _find_player() -> tuple[str, list[str]] | None:
    for cmd, args in _PLAYERS:
        if subprocess.run(
            ["which", cmd], capture_output=True, text=True
        ).returncode == 0:
            return cmd, args
    return None


def _get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        print("Error: ELEVENLABS_API_KEY not set. Add it to ~/.env", file=sys.stderr)
        sys.exit(1)
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

    # Also kill by pattern
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
            os.kill(pid, 0)  # Check if process exists
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


def speak(text: str) -> dict:
    """Stream TTS audio for the given text. Returns usage info."""
    if not text.strip():
        print("Error: Empty text.", file=sys.stderr)
        sys.exit(1)

    player = _find_player()
    if player is None:
        print(
            "Error: No audio player found (need afplay, mpv, or ffplay)",
            file=sys.stderr,
        )
        sys.exit(1)

    player_cmd, player_args = player

    # Truncate
    text = text[:MAX_CHARS]
    char_count = len(text)

    api_key = _get_api_key()
    voice_id = _get_voice_id()
    model_id = _get_model_id()

    # Stop any current playback
    stop()

    # Stream audio from ElevenLabs
    audio_file = tempfile.NamedTemporaryFile(
        prefix="claude-tts-", suffix=".mp3", delete=False
    )

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
                print(
                    f"Error: ElevenLabs API returned HTTP {resp.status_code}: {body}",
                    file=sys.stderr,
                )
                sys.exit(1)

            for chunk in resp.iter_bytes():
                audio_file.write(chunk)

        audio_file.close()

        # Play in background
        proc = subprocess.Popen(
            [player_cmd, *player_args, audio_file.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        PID_FILE.write_text(str(proc.pid))

        # Record cost
        entry = cost.record_usage(char_count, voice_id, model_id)

        # Spawn cleanup waiter (non-blocking)
        if os.fork() == 0:
            # Child process: wait for player, then clean up
            proc.wait()
            try:
                os.unlink(audio_file.name)
            except OSError:
                pass
            PID_FILE.unlink(missing_ok=True)
            os._exit(0)

        return {
            "characters": char_count,
            "cost_usd": entry["cost_usd"],
            "voice_id": voice_id,
            "model_id": model_id,
        }

    except httpx.HTTPError as e:
        print(f"Error: API request failed: {e}", file=sys.stderr)
        try:
            os.unlink(audio_file.name)
        except OSError:
            pass
        sys.exit(1)
