"""Deepgram Aura TTS provider.

Endpoint: POST https://api.deepgram.com/v1/speak?model={voice}&encoding=mp3
Auth: Authorization: Token {key}
Body: {"text": text}
IMPORTANT: Deepgram enforces a 2,000-character limit per request. Text is
           truncated to 2,000 characters before submission.

Environment variables:
    DEEPGRAM_API_KEY  — required
    DEEPGRAM_VOICE    — optional, default: aura-asteria-en
"""

from __future__ import annotations

import os

import httpx

from ..protocol import APIError, APIKeyMissing, CostRate, SpeakResult, Voice
from .. import registry

_ENDPOINT = "https://api.deepgram.com/v1/speak"
_DEFAULT_VOICE = "aura-asteria-en"
_MAX_CHARS = 2000

# Static voice list (Aura-1 English)
_STATIC_VOICES: list[tuple[str, str, str, str]] = [
    # (voice_id, gender, accent, description)
    ("aura-asteria-en",  "female",  "en-US", "Clear, confident, energetic — advertising, IVR"),
    ("aura-luna-en",     "female",  "en-US", "Friendly, natural, engaging — IVR"),
    ("aura-stella-en",   "female",  "en-US", "Clear, professional, engaging — customer service"),
    ("aura-athena-en",   "female",  "en-GB", "Calm, smooth, professional — storytelling"),
    ("aura-hera-en",     "female",  "en-US", "Smooth, warm, professional — informative content"),
    ("aura-orion-en",    "male",    "en-US", "Approachable, comfortable, calm — informative content"),
    ("aura-arcas-en",    "male",    "en-US", "Natural, smooth, comfortable — customer service / casual"),
    ("aura-perseus-en",  "male",    "en-US", "Confident, professional, clear — customer service"),
    ("aura-angus-en",    "male",    "en-IE", "Warm, friendly, natural — storytelling"),
    ("aura-orpheus-en",  "male",    "en-US", "Professional, trustworthy, clear — customer service / storytelling"),
    ("aura-helios-en",   "male",    "en-GB", "Professional, clear, confident — customer service"),
    ("aura-zeus-en",     "male",    "en-US", "Deep, trustworthy, smooth — IVR"),
]


class DeepgramProvider:
    """TTS provider backed by the Deepgram Aura API."""

    @property
    def name(self) -> str:
        return "deepgram"

    @property
    def display_name(self) -> str:
        return "Deepgram Aura"

    @property
    def max_chars(self) -> int:
        return 2000

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def _api_key(self) -> str:
        key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not key:
            raise APIKeyMissing(
                "DEEPGRAM_API_KEY is not set. "
                "Retrieve your key from https://console.deepgram.com/ "
                "and add it to your environment."
            )
        return key

    def validate_config(self) -> None:
        """Raise APIKeyMissing if DEEPGRAM_API_KEY is absent."""
        self._api_key()

    def get_voice_id(self) -> str:
        return os.environ.get("DEEPGRAM_VOICE", _DEFAULT_VOICE)

    def get_model_id(self) -> str:
        # For Deepgram, voice and model are the same identifier
        return self.get_voice_id()

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def get_cost_rates(self) -> list[CostRate]:
        return [
            CostRate("aura-1", 0.015),
            CostRate("aura-2", 0.030),
        ]

    def get_default_cost_rate(self) -> CostRate:
        voice_id = self.get_voice_id()
        if voice_id.startswith("aura-2-"):
            return CostRate("aura-2", 0.030)
        return CostRate("aura-1", 0.015)

    # ------------------------------------------------------------------
    # Voice listing
    # ------------------------------------------------------------------

    def list_voices(self) -> list[Voice]:
        """Return the static list of Deepgram Aura voices.

        Deepgram does not expose a public voices listing endpoint; the list
        is sourced from the official documentation.

        Returns:
            A list of :class:`~fakoli_speak.protocol.Voice` instances.
        """
        return [
            Voice(
                voice_id=voice_id,
                name=voice_id,
                language=locale,
                gender=gender,
                description=description,
            )
            for voice_id, gender, locale, description in _STATIC_VOICES
        ]

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, text: str) -> SpeakResult:
        """Convert *text* to MP3 audio via the Deepgram Aura API.

        Text is truncated to 2,000 characters (API hard limit).

        Args:
            text: Plain-text string to synthesize.

        Returns:
            A :class:`~fakoli_speak.protocol.SpeakResult` with MP3 audio bytes.

        Raises:
            APIKeyMissing: If DEEPGRAM_API_KEY is not set.
            APIError: If the API returns a non-200 response.
        """
        api_key = self._api_key()
        voice_id = self.get_voice_id()

        # Deepgram hard limit: 2,000 characters per request
        text = text[:_MAX_CHARS]
        char_count = len(text)

        try:
            resp = httpx.post(
                _ENDPOINT,
                params={"model": voice_id, "encoding": "mp3"},
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise APIError(f"Deepgram TTS request failed: {exc}") from exc

        if resp.status_code != 200:
            raise APIError(
                f"Deepgram API returned HTTP {resp.status_code}: {resp.text}"
            )

        return SpeakResult(
            audio_data=resp.content,
            audio_format="mp3",
            char_count=char_count,
            voice_id=voice_id,
            model_id=voice_id,
        )


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(DeepgramProvider())
