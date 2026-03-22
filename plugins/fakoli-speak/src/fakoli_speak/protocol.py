"""Core protocol and data types for multi-provider TTS.

All TTS providers must satisfy the TTSProvider protocol defined here.
Exceptions are defined here and imported by other modules — never duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TTSError(Exception):
    """Base exception for all TTS errors."""


class APIKeyMissing(TTSError):
    """Required API key is not configured."""


class NoPlayerFound(TTSError):
    """No supported audio player is available on this system."""


class APIError(TTSError):
    """The upstream TTS API returned an error response."""


# ---------------------------------------------------------------------------
# Frozen data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Voice:
    """Immutable descriptor for a single TTS voice."""

    voice_id: str
    name: str
    language: str    # e.g. "en", "fr", "multi"
    gender: str      # "male", "female", "neutral", "unknown"
    description: str  # free-form human-readable text


@dataclass(frozen=True)
class CostRate:
    """Pricing information for a specific model."""

    model_id: str
    cost_per_1k_chars: float


@dataclass(frozen=True)
class SpeakResult:
    """The result of a successful synthesis call."""

    audio_data: bytes
    audio_format: str  # "mp3", "wav", "aiff", "pcm"
    char_count: int
    voice_id: str
    model_id: str


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TTSProvider(Protocol):
    """Contract that every TTS provider implementation must satisfy.

    Structural subtyping — no inheritance required.  A class satisfies this
    protocol as long as it exposes the properties and methods listed below.
    """

    @property
    def name(self) -> str:
        """Short machine-readable identifier, e.g. ``"openai"`` or ``"elevenlabs"``."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable label, e.g. ``"OpenAI TTS"`` or ``"ElevenLabs"``."""
        ...

    def validate_config(self) -> None:
        """Verify that required configuration (API keys, etc.) is present.

        Raises:
            APIKeyMissing: If a required environment variable is not set.
        """
        ...

    def get_voice_id(self) -> str:
        """Return the currently configured voice identifier."""
        ...

    def get_model_id(self) -> str:
        """Return the currently configured model identifier."""
        ...

    def get_cost_rates(self) -> list[CostRate]:
        """Return all known cost rates for this provider's models."""
        ...

    def get_default_cost_rate(self) -> CostRate:
        """Return the cost rate for the currently active model."""
        ...

    def list_voices(self) -> list[Voice]:
        """Fetch and return the list of available voices for this provider."""
        ...

    def synthesize(self, text: str) -> SpeakResult:
        """Convert *text* to audio and return the raw bytes plus metadata.

        Args:
            text: The plain-text string to synthesize.

        Returns:
            A :class:`SpeakResult` containing the audio bytes and metadata.

        Raises:
            APIKeyMissing: If the provider is not properly configured.
            APIError: If the upstream API returns an error.
        """
        ...
