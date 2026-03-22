"""ElevenLabs TTS provider.

Endpoint: POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
Auth: xi-api-key header
Default model: eleven_flash_v2_5
Default voice: 21m00Tcm4TlvDq8ikWAM (Rachel)

Environment variables:
    ELEVENLABS_API_KEY   — required
    ELEVENLABS_VOICE_ID  — optional, default: 21m00Tcm4TlvDq8ikWAM
    ELEVENLABS_MODEL_ID  — optional, default: eleven_flash_v2_5
"""

from __future__ import annotations

import os

import httpx

from ..protocol import APIError, APIKeyMissing, CostRate, SpeakResult, Voice
from .. import registry

# Cost per 1,000 characters (USD)
_COST_RATES: dict[str, float] = {
    "eleven_flash_v2_5": 0.15,
    "eleven_flash_v2": 0.15,
    "eleven_multilingual_v2": 0.30,
    "eleven_v3": 0.30,
}

_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
_DEFAULT_MODEL_ID = "eleven_flash_v2_5"
_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


class ElevenLabsProvider:
    """TTS provider backed by the ElevenLabs streaming API."""

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def display_name(self) -> str:
        return "ElevenLabs"

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def _api_key(self) -> str:
        key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not key:
            raise APIKeyMissing(
                "ELEVENLABS_API_KEY is not set. "
                "Retrieve your key from https://elevenlabs.io/app/settings/api-keys "
                "and add it to your environment."
            )
        return key

    def validate_config(self) -> None:
        """Raise APIKeyMissing if ELEVENLABS_API_KEY is absent."""
        self._api_key()  # raises if missing

    def get_voice_id(self) -> str:
        return os.environ.get("ELEVENLABS_VOICE_ID", _DEFAULT_VOICE_ID)

    def get_model_id(self) -> str:
        return os.environ.get("ELEVENLABS_MODEL_ID", _DEFAULT_MODEL_ID)

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
        rate = _COST_RATES.get(model_id, _COST_RATES[_DEFAULT_MODEL_ID])
        return CostRate(model_id=model_id, cost_per_1k_chars=rate)

    # ------------------------------------------------------------------
    # Voice listing
    # ------------------------------------------------------------------

    def list_voices(self) -> list[Voice]:
        """Fetch available voices from the ElevenLabs API.

        Returns:
            A list of :class:`~fakoli_speak.protocol.Voice` instances.

        Raises:
            APIKeyMissing: If ELEVENLABS_API_KEY is not set.
            APIError: If the API returns a non-200 response.
        """
        api_key = self._api_key()
        try:
            resp = httpx.get(
                _VOICES_URL,
                headers={"xi-api-key": api_key},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise APIError(f"ElevenLabs voices request failed: {exc}") from exc

        if resp.status_code != 200:
            raise APIError(
                f"ElevenLabs API returned HTTP {resp.status_code}: {resp.text}"
            )

        voices: list[Voice] = []
        for v in resp.json().get("voices", []):
            labels = v.get("labels") or {}
            voices.append(
                Voice(
                    voice_id=v["voice_id"],
                    name=v["name"],
                    language=labels.get("accent", "multi"),
                    gender=labels.get("gender", "unknown"),
                    description=labels.get("use case", v.get("description", "")),
                )
            )
        return voices

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, text: str) -> SpeakResult:
        """Convert *text* to MP3 audio via the ElevenLabs streaming endpoint.

        Args:
            text: Plain-text string to synthesize.

        Returns:
            A :class:`~fakoli_speak.protocol.SpeakResult` with MP3 audio bytes.

        Raises:
            APIKeyMissing: If ELEVENLABS_API_KEY is not set.
            APIError: If the API returns a non-200 response.
        """
        api_key = self._api_key()
        voice_id = self.get_voice_id()
        model_id = self.get_model_id()
        char_count = len(text)

        url = _TTS_URL.format(voice_id=voice_id)
        try:
            with httpx.stream(
                "POST",
                url,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
                timeout=30,
            ) as resp:
                if resp.status_code != 200:
                    body = resp.read().decode(errors="replace")
                    raise APIError(
                        f"ElevenLabs API returned HTTP {resp.status_code}: {body}"
                    )
                audio_data = b"".join(resp.iter_bytes())
        except httpx.HTTPError as exc:
            raise APIError(f"ElevenLabs request failed: {exc}") from exc

        return SpeakResult(
            audio_data=audio_data,
            audio_format="mp3",
            char_count=char_count,
            voice_id=voice_id,
            model_id=model_id,
        )


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(ElevenLabsProvider())
