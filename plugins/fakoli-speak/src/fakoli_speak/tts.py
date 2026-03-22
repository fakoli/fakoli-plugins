"""Multi-provider TTS facade for fakoli-speak.

This module is a thin delegation layer over the provider registry and
playback subsystem.  It re-exports the legacy exception and constant names
so that callers that import them from here continue to work unchanged.
"""

from . import cost, playback, registry

# ---------------------------------------------------------------------------
# Re-exports for backward compatibility
# ---------------------------------------------------------------------------

# Exceptions — originally defined here; now live in protocol.py
from .protocol import APIError, APIKeyMissing, NoPlayerFound, TTSError

# Constants — originally defined here; now live in playback.py
PID_FILE = playback.PID_FILE
MAX_CHARS: int = 4000

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def stop() -> None:
    """Stop any running TTS playback."""
    playback.stop()


def status() -> dict:
    """Return current TTS status including active provider details."""
    playing, pid = playback.is_playing()
    provider = registry.get_provider()
    return {
        "playing": playing,
        "pid": pid,
        "provider": provider.name,
        "provider_display": provider.display_name,
        "voice_id": provider.get_voice_id(),
        "model_id": provider.get_model_id(),
    }


def list_voices() -> list[dict]:
    """List available voices for the active provider."""
    provider = registry.get_provider()
    voices = provider.list_voices()
    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "language": v.language,
            "gender": v.gender,
            "description": v.description,
        }
        for v in voices
    ]


def speak(text: str) -> dict:
    """Synthesize *text* and begin playback. Returns usage metadata.

    Raises:
        TTSError: On empty text.
        NoPlayerFound: If no supported audio player is available.
        APIKeyMissing: If the active provider is not configured.
        APIError: If the upstream API returns an error.
    """
    if not text.strip():
        raise TTSError("Empty text")

    playback.find_player()  # pre-check before making the API call

    text = text[:MAX_CHARS]
    provider = registry.get_provider()
    provider.validate_config()
    playback.stop()

    result = provider.synthesize(text)
    playback.play_audio(result.audio_data, result.audio_format)

    entry = cost.record_usage(
        chars=result.char_count,
        voice_id=result.voice_id,
        model_id=result.model_id,
        provider=provider.name,
    )

    return {
        "characters": result.char_count,
        "cost_usd": entry["cost_usd"],
        "voice_id": result.voice_id,
        "model_id": result.model_id,
        "provider": provider.name,
    }
