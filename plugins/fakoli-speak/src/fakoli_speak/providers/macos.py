"""macOS ``say`` TTS provider.

Uses the built-in macOS ``say`` command to synthesize speech locally.
No API key, network access, or third-party dependency is required.

Output format: AIFF (default for ``say -o``).
Registration is skipped on non-Darwin platforms.

Environment variables:
    MACOS_SAY_VOICE  — optional, default: Samantha
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import tempfile

from ..protocol import APIError, CostRate, SpeakResult, TTSError, Voice
from .. import registry

_DEFAULT_VOICE = "Samantha"


class MacOSProvider:
    """TTS provider backed by the macOS ``say`` command-line tool."""

    @property
    def name(self) -> str:
        return "macos"

    @property
    def display_name(self) -> str:
        return "macOS say"

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """No-op: macOS ``say`` requires no API key.

        Raises:
            TTSError: If ``say`` is not found on PATH (should never happen on macOS).
        """
        import shutil
        if shutil.which("say") is None:
            raise TTSError(
                "macOS 'say' command not found. "
                "This provider requires macOS with the Speech Synthesis framework."
            )

    def get_voice_id(self) -> str:
        return os.environ.get("MACOS_SAY_VOICE", _DEFAULT_VOICE)

    def get_model_id(self) -> str:
        # macOS say has no model concept; return the voice name as the model ID
        return self.get_voice_id()

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def get_cost_rates(self) -> list[CostRate]:
        return [CostRate(model_id="macos-say", cost_per_1k_chars=0.0)]

    def get_default_cost_rate(self) -> CostRate:
        return CostRate(model_id=self.get_voice_id(), cost_per_1k_chars=0.0)

    # ------------------------------------------------------------------
    # Voice listing
    # ------------------------------------------------------------------

    def list_voices(self) -> list[Voice]:
        """Parse available voices from ``say -v '?'`` output.

        Each output line has the format::

            VoiceName       lang_LOCALE    # Sample sentence.

        Voice names containing spaces (e.g., ``Eddy (English (US))``) are
        preserved in full.

        Returns:
            A list of :class:`~fakoli_speak.protocol.Voice` instances,
            one per installed system voice.

        Raises:
            APIError: If the ``say`` subprocess exits with a non-zero status.
        """
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise APIError(
                f"'say -v ?' exited with status {exc.returncode}: {exc.stderr}"
            ) from exc
        except FileNotFoundError as exc:
            raise APIError("'say' command not found on PATH") from exc

        voices: list[Voice] = []
        # Pattern: capture voice name (anything up to locale), locale, and sample text
        # Line format: "VoiceName   en_US    # Sample text."
        line_re = re.compile(
            r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2,3})\s+#\s*(.*)$"
        )

        for line in result.stdout.splitlines():
            line = line.rstrip()
            match = line_re.match(line)
            if not match:
                continue
            voice_name = match.group(1).strip()
            locale = match.group(2)          # e.g. "en_US"
            sample = match.group(3).strip()  # sample sentence

            # Derive a BCP-47 language tag (e.g. "en_US" -> "en-US")
            language = locale.replace("_", "-")

            voices.append(
                Voice(
                    voice_id=voice_name,
                    name=voice_name,
                    language=language,
                    gender="unknown",
                    description=sample,
                )
            )

        return voices

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, text: str) -> SpeakResult:
        """Synthesize *text* to AIFF audio using ``say``.

        ``say`` is invoked with ``-o <tmpfile>`` to write AIFF output.
        The resulting bytes are read, the temp file is removed, and
        the bytes are returned inside a :class:`~fakoli_speak.protocol.SpeakResult`.

        For long text (beyond typical shell argument limits), a temporary
        input file is used with ``-f`` so that ARG_MAX is not exceeded.

        Args:
            text: Plain-text string to synthesize.

        Returns:
            A :class:`~fakoli_speak.protocol.SpeakResult` with AIFF audio bytes.

        Raises:
            TTSError: If the ``say`` subprocess fails.
        """
        voice_id = self.get_voice_id()
        char_count = len(text)

        with tempfile.NamedTemporaryFile(
            prefix="fakoli-tts-", suffix=".aiff", delete=False
        ) as out_f:
            out_path = out_f.name

        # Use a text input file to avoid ARG_MAX issues with long strings
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="fakoli-tts-input-",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as txt_f:
            txt_path = txt_f.name
            txt_f.write(text)

        try:
            result = subprocess.run(
                ["say", "-v", voice_id, "-o", out_path, "-f", txt_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise TTSError(
                    f"'say' exited with status {result.returncode}: {result.stderr}"
                )

            with open(out_path, "rb") as f:
                audio_data = f.read()
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass
            try:
                os.unlink(txt_path)
            except OSError:
                pass

        return SpeakResult(
            audio_data=audio_data,
            audio_format="aiff",
            char_count=char_count,
            voice_id=voice_id,
            model_id=voice_id,
        )


# ---------------------------------------------------------------------------
# Self-registration — macOS only
# ---------------------------------------------------------------------------

if platform.system() == "Darwin":
    registry.register(MacOSProvider())
