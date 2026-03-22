"""Google Gemini TTS provider.

Endpoint: POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}
Auth: API key as URL query parameter
Response: base64-encoded raw PCM (24 kHz, 16-bit, mono) — NOT playable as-is.
          A WAV header (44 bytes) is prepended before returning audio_data so
          the result is a valid PCM-in-WAV file.

Environment variables:
    GEMINI_API_KEY       — required
    GEMINI_TTS_VOICE     — optional, default: Kore
    GEMINI_TTS_MODEL     — optional, default: gemini-2.5-flash-preview-tts
"""

from __future__ import annotations

import base64
import os
import struct

import httpx

from ..protocol import APIError, APIKeyMissing, CostRate, SpeakResult, Voice
from .. import registry

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_DEFAULT_VOICE = "Kore"
_DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"

# PCM audio parameters returned by the Gemini TTS API
_SAMPLE_RATE = 24_000
_NUM_CHANNELS = 1
_BITS_PER_SAMPLE = 16

# Static voice list (from official documentation; 30 voices total but listing
# the commonly used subset plus all names for completeness)
_STATIC_VOICES: list[tuple[str, str]] = [
    ("Zephyr",          "Bright"),
    ("Puck",            "Upbeat"),
    ("Charon",          "Informative"),
    ("Kore",            "Firm"),
    ("Fenrir",          "Excitable"),
    ("Leda",            "Youthful"),
    ("Orus",            "Firm"),
    ("Aoede",           "Breezy"),
    ("Callirrhoe",      "Easy-going"),
    ("Autonoe",         "Bright"),
    ("Enceladus",       "Breathy"),
    ("Iapetus",         "Clear"),
    ("Umbriel",         "Easy-going"),
    ("Algieba",         "Smooth"),
    ("Despina",         "Smooth"),
    ("Erinome",         "Clear"),
    ("Algenib",         "Gravelly"),
    ("Rasalgethi",      "Informative"),
    ("Laomedeia",       "Upbeat"),
    ("Achernar",        "Soft"),
    ("Alnilam",         "Firm"),
    ("Schedar",         "Even"),
    ("Gacrux",          "Mature"),
    ("Pulcherrima",     "Forward"),
    ("Achird",          "Friendly"),
    ("Zubenelgenubi",   "Casual"),
    ("Vindemiatrix",    "Gentle"),
    ("Sadachbia",       "Lively"),
    ("Sadaltager",      "Knowledgeable"),
    ("Sulafat",         "Warm"),
]


def _build_wav_header(pcm_data: bytes) -> bytes:
    """Construct a 44-byte RIFF/WAV header for the given raw PCM data.

    Audio parameters are fixed at 24 kHz, 16-bit, mono — matching the
    Gemini TTS API output format (``audio/L16;codec=pcm;rate=24000``).

    Args:
        pcm_data: Raw L16 (signed 16-bit little-endian) PCM bytes.

    Returns:
        A 44-byte bytes object containing the complete RIFF/WAV header.
        Concatenate this with *pcm_data* to produce a valid WAV file.
    """
    data_size = len(pcm_data)
    byte_rate = _SAMPLE_RATE * _NUM_CHANNELS * (_BITS_PER_SAMPLE // 8)
    block_align = _NUM_CHANNELS * (_BITS_PER_SAMPLE // 8)
    chunk_size = 36 + data_size  # entire file minus the 8-byte "RIFF" preamble

    # RIFF chunk descriptor (12 bytes)
    # fmt sub-chunk (24 bytes)
    # data sub-chunk header (8 bytes)
    # Total: 44 bytes
    header = struct.pack(
        "<4sI4s"   # ChunkID="RIFF", ChunkSize, Format="WAVE"
        "4sIHHIIHH"  # Subchunk1ID="fmt ", Subchunk1Size=16, AudioFormat=1 (PCM),
                     # NumChannels, SampleRate, ByteRate, BlockAlign, BitsPerSample
        "4sI",     # Subchunk2ID="data", Subchunk2Size
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,                 # PCM fmt chunk is always 16 bytes
        1,                  # AudioFormat: 1 = PCM (no compression)
        _NUM_CHANNELS,
        _SAMPLE_RATE,
        byte_rate,
        block_align,
        _BITS_PER_SAMPLE,
        b"data",
        data_size,
    )
    return header


class GoogleProvider:
    """TTS provider backed by the Google Gemini generateContent API."""

    @property
    def name(self) -> str:
        return "google"

    @property
    def display_name(self) -> str:
        return "Google Gemini TTS"

    @property
    def max_chars(self) -> int:
        return 5000

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def _api_key(self) -> str:
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise APIKeyMissing(
                "GEMINI_API_KEY is not set. "
                "Retrieve your key from https://aistudio.google.com/app/apikey "
                "and add it to your environment."
            )
        return key

    def validate_config(self) -> None:
        """Raise APIKeyMissing if GEMINI_API_KEY is absent."""
        self._api_key()

    def get_voice_id(self) -> str:
        return os.environ.get("GEMINI_TTS_VOICE", _DEFAULT_VOICE)

    def get_model_id(self) -> str:
        return os.environ.get("GEMINI_TTS_MODEL", _DEFAULT_MODEL)

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def get_cost_rates(self) -> list[CostRate]:
        # Free tier — cost is effectively 0 for most users
        return [
            CostRate(model_id="gemini-2.5-flash-preview-tts", cost_per_1k_chars=0.0),
            CostRate(model_id="gemini-2.5-pro-preview-tts",   cost_per_1k_chars=0.0),
        ]

    def get_default_cost_rate(self) -> CostRate:
        return CostRate(model_id=self.get_model_id(), cost_per_1k_chars=0.0)

    # ------------------------------------------------------------------
    # Voice listing
    # ------------------------------------------------------------------

    def list_voices(self) -> list[Voice]:
        """Return the static list of Gemini TTS voices.

        Language is auto-detected by the API; all voices are multi-lingual.

        Returns:
            A list of :class:`~fakoli_speak.protocol.Voice` instances.
        """
        return [
            Voice(
                voice_id=voice_name,
                name=voice_name,
                language="multi",
                gender="unknown",
                description=style,
            )
            for voice_name, style in _STATIC_VOICES
        ]

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, text: str) -> SpeakResult:
        """Convert *text* to WAV audio via the Google Gemini TTS API.

        The API returns raw PCM (L16, 24 kHz, mono) encoded as base64.
        This method decodes the PCM data and prepends a proper WAV header
        so that the returned bytes form a valid, playable WAV file.

        Args:
            text: Plain-text string to synthesize.

        Returns:
            A :class:`~fakoli_speak.protocol.SpeakResult` with WAV audio bytes.

        Raises:
            APIKeyMissing: If GEMINI_API_KEY is not set.
            APIError: If the API returns a non-200 response or an unexpected
                      response structure.
        """
        api_key = self._api_key()
        voice_id = self.get_voice_id()
        model_id = self.get_model_id()
        char_count = len(text)

        url = _BASE_URL.format(model=model_id)
        payload = {
            "contents": [
                {"parts": [{"text": text}]}
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_id,
                        }
                    }
                },
            },
        }

        try:
            resp = httpx.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                json=payload,
                timeout=60,
            )
        except httpx.HTTPError as exc:
            raise APIError(f"Google Gemini TTS request failed: {exc}") from exc

        if resp.status_code != 200:
            raise APIError(
                f"Google Gemini API returned HTTP {resp.status_code}: {resp.text}"
            )

        try:
            body = resp.json()
            inline_data = (
                body["candidates"][0]["content"]["parts"][0]["inlineData"]
            )
            b64_audio: str = inline_data["data"]
        except (KeyError, IndexError, TypeError) as exc:
            raise APIError(
                f"Unexpected Google Gemini TTS response structure: {exc}. "
                f"Body: {resp.text[:500]}"
            ) from exc

        try:
            pcm_data = base64.b64decode(b64_audio)
        except Exception as exc:
            raise APIError(f"Failed to decode audio from Gemini response: {exc}") from exc
        wav_header = _build_wav_header(pcm_data)
        audio_data = wav_header + pcm_data

        return SpeakResult(
            audio_data=audio_data,
            audio_format="wav",
            char_count=char_count,
            voice_id=voice_id,
            model_id=model_id,
        )


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(GoogleProvider())
