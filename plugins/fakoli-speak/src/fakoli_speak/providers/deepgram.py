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

# Cost per 1,000 characters (USD) — Aura-1 pay-as-you-go rate
_COST_RATES: dict[str, float] = {
    # Aura-1 voices
    "aura-asteria-en":  0.015,
    "aura-luna-en":     0.015,
    "aura-stella-en":   0.015,
    "aura-athena-en":   0.015,
    "aura-hera-en":     0.015,
    "aura-orion-en":    0.015,
    "aura-arcas-en":    0.015,
    "aura-perseus-en":  0.015,
    "aura-angus-en":    0.015,
    "aura-orpheus-en":  0.015,
    "aura-helios-en":   0.015,
    "aura-zeus-en":     0.015,
    # Aura-2 voices
    "aura-2-thalia-en":    0.030,
    "aura-2-andromeda-en": 0.030,
    "aura-2-helena-en":    0.030,
    "aura-2-apollo-en":    0.030,
    "aura-2-arcas-en":     0.030,
    "aura-2-aries-en":     0.030,
}

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
        # Deduplicate by rate value to avoid returning 12 identical entries
        seen: set[float] = set()
        rates: list[CostRate] = []
        for model_id, rate in _COST_RATES.items():
            if rate not in seen:
                rates.append(CostRate(model_id=model_id, cost_per_1k_chars=rate))
                seen.add(rate)
        return rates

    def get_default_cost_rate(self) -> CostRate:
        voice_id = self.get_voice_id()
        rate = _COST_RATES.get(voice_id, 0.015)
        return CostRate(model_id=voice_id, cost_per_1k_chars=rate)

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
