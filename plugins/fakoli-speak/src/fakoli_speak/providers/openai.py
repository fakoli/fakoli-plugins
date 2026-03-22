"""OpenAI TTS provider.

Endpoint: POST https://api.openai.com/v1/audio/speech
Auth: Authorization: Bearer {key}
Default model: tts-1
Default voice: nova
Response: raw MP3 bytes (no JSON envelope)

Environment variables:
    OPENAI_API_KEY     — required
    OPENAI_TTS_VOICE   — optional, default: nova
    OPENAI_TTS_MODEL   — optional, default: tts-1
"""

from __future__ import annotations

import os

import httpx

from ..protocol import APIError, APIKeyMissing, CostRate, SpeakResult, Voice
from .. import registry

_ENDPOINT = "https://api.openai.com/v1/audio/speech"
_DEFAULT_VOICE = "nova"
_DEFAULT_MODEL = "tts-1"

# Cost per 1,000 characters (USD)
_COST_RATES: dict[str, float] = {
    "tts-1": 0.015,
    "tts-1-hd": 0.030,
    # gpt-4o-mini-tts is token-based; approximate via character cost at $0.60/1M input tokens
    "gpt-4o-mini-tts": 0.0006,
}

# Static voice list: tts-1 / tts-1-hd support the first 9 (alloy through shimmer).
# gpt-4o-mini-tts supports all 13.
_STATIC_VOICES: list[tuple[str, str]] = [
    ("alloy",   "Neutral and balanced; works as masculine or feminine"),
    ("ash",     "Clear and articulate; expressive, good for style-prompted use"),
    ("coral",   "Vibrant and warm; expressive"),
    ("echo",    "Resonant and clear; masculine presentation"),
    ("fable",   "Expressive and warm; masculine presentation"),
    ("onyx",    "Deep and authoritative; masculine presentation"),
    ("nova",    "Bright and energetic; feminine presentation"),
    ("sage",    "Calm and measured; expressive"),
    ("shimmer", "Bright and cheerful; feminine presentation"),
    # gpt-4o-mini-tts exclusive
    ("ballad",  "Smooth and melodic"),
    ("verse",   "Expressive; style-tunable"),
    ("marin",   "High quality; recommended for gpt-4o-mini-tts"),
    ("cedar",   "High quality; recommended for gpt-4o-mini-tts"),
]


class OpenAIProvider:
    """TTS provider backed by the OpenAI audio/speech API."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI TTS"

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def _api_key(self) -> str:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise APIKeyMissing(
                "OPENAI_API_KEY is not set. "
                "Retrieve your key from https://platform.openai.com/api-keys "
                "and add it to your environment."
            )
        return key

    def validate_config(self) -> None:
        """Raise APIKeyMissing if OPENAI_API_KEY is absent."""
        self._api_key()

    def get_voice_id(self) -> str:
        return os.environ.get("OPENAI_TTS_VOICE", _DEFAULT_VOICE)

    def get_model_id(self) -> str:
        return os.environ.get("OPENAI_TTS_MODEL", _DEFAULT_MODEL)

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def get_cost_rates(self) -> list[CostRate]:
        return [
            CostRate(model_id=model_id, cost_per_1k_chars=rate)
            for model_id, rate in _COST_RATES.items()
        ]

    def get_default_cost_rate(self) -> CostRate:
        model_id = self.get_model_id()
        rate = _COST_RATES.get(model_id, _COST_RATES[_DEFAULT_MODEL])
        return CostRate(model_id=model_id, cost_per_1k_chars=rate)

    # ------------------------------------------------------------------
    # Voice listing
    # ------------------------------------------------------------------

    def list_voices(self) -> list[Voice]:
        """Return the static list of OpenAI TTS voices.

        OpenAI does not expose a voices API endpoint; the list is hardcoded
        from the official documentation.

        Returns:
            A list of :class:`~fakoli_speak.protocol.Voice` instances.
        """
        return [
            Voice(
                voice_id=voice_id,
                name=voice_id.capitalize(),
                language="multi",
                gender="unknown",
                description=description,
            )
            for voice_id, description in _STATIC_VOICES
        ]

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, text: str) -> SpeakResult:
        """Convert *text* to MP3 audio via the OpenAI TTS API.

        The input is truncated to 4096 characters (API limit).

        Args:
            text: Plain-text string to synthesize.

        Returns:
            A :class:`~fakoli_speak.protocol.SpeakResult` with MP3 audio bytes.

        Raises:
            APIKeyMissing: If OPENAI_API_KEY is not set.
            APIError: If the API returns a non-200 response.
        """
        api_key = self._api_key()
        voice_id = self.get_voice_id()
        model_id = self.get_model_id()

        # API hard limit: 4,096 characters per request
        text = text[:4096]
        char_count = len(text)

        try:
            resp = httpx.post(
                _ENDPOINT,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "input": text,
                    "voice": voice_id,
                    "response_format": "mp3",
                },
                timeout=60,
            )
        except httpx.HTTPError as exc:
            raise APIError(f"OpenAI TTS request failed: {exc}") from exc

        if resp.status_code != 200:
            raise APIError(
                f"OpenAI TTS API returned HTTP {resp.status_code}: {resp.text}"
            )

        return SpeakResult(
            audio_data=resp.content,
            audio_format="mp3",
            char_count=char_count,
            voice_id=voice_id,
            model_id=model_id,
        )


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(OpenAIProvider())
