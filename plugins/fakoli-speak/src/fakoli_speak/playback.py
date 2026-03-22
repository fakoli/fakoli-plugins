"""Audio playback primitives for fakoli-speak.

Handles player detection, subprocess-based playback, PID-file lifecycle
management, and post-playback cleanup via a daemon thread.

Exceptions are imported from protocol — never defined here.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path

from .protocol import NoPlayerFound

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PID_FILE = Path("/tmp/claude-tts.pid")

# Tried in order; first available player wins.
_PLAYERS: list[tuple[str, list[str]]] = [
    ("afplay", []),
    ("mpv", ["--no-terminal"]),
    ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
]

# Maps audio_format names to the file-extension used for the temp file.
_FORMAT_SUFFIX: dict[str, str] = {
    "mp3": ".mp3",
    "wav": ".wav",
    "aiff": ".aiff",
    "aif": ".aiff",
    "pcm": ".pcm",
    "ogg": ".ogg",
    "opus": ".opus",
    "flac": ".flac",
}


# ---------------------------------------------------------------------------
# Player discovery
# ---------------------------------------------------------------------------


def find_player() -> tuple[str, list[str]]:
    """Return *(command, extra_args)* for the first available audio player.

    Raises:
        NoPlayerFound: If none of the known players are present on PATH.
    """
    for cmd, args in _PLAYERS:
        if shutil.which(cmd):
            return cmd, args
    raise NoPlayerFound(
        "No audio player found on PATH. Install one of: afplay, mpv, ffplay."
    )


# ---------------------------------------------------------------------------
# Playback status & stop
# ---------------------------------------------------------------------------


def is_playing() -> tuple[bool, int | None]:
    """Check whether a TTS playback process is currently running.

    Returns:
        A ``(playing, pid)`` tuple.  *pid* is ``None`` when not playing.
    """
    if not PID_FILE.exists():
        return False, None

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # signal 0 — existence check only
        return True, pid
    except (ValueError, ProcessLookupError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return False, None


def stop() -> None:
    """Terminate any active TTS playback process.

    Sends SIGTERM to the PID recorded in :data:`PID_FILE`, removes the PID
    file, and runs ``pkill`` to catch any stragglers launched under the
    ``claude-tts`` temp-file prefix.
    """
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


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------


def _cleanup_after_playback(proc: subprocess.Popen, audio_path: str) -> None:
    """Wait for the player process to exit, then remove the temp file.

    Designed to run in a daemon thread so the caller is not blocked.
    """
    proc.wait()
    try:
        os.unlink(audio_path)
    except OSError:
        pass
    PID_FILE.unlink(missing_ok=True)


def play_audio(audio_data: bytes, audio_format: str = "mp3") -> int:
    """Write *audio_data* to a temp file and launch a player subprocess.

    The function returns immediately after the player process is started.
    A daemon thread handles waiting for the process to finish and removing
    the temporary file.

    Args:
        audio_data:   Raw audio bytes to play.
        audio_format: Format hint used to choose the temp-file extension.
                      Defaults to ``"mp3"``.

    Returns:
        The PID of the launched player process.

    Raises:
        NoPlayerFound: If no supported player binary is on PATH.
    """
    player_cmd, player_args = find_player()
    suffix = _FORMAT_SUFFIX.get(audio_format.lower(), f".{audio_format.lower()}")

    audio_file = tempfile.NamedTemporaryFile(
        prefix="claude-tts-", suffix=suffix, delete=False
    )
    try:
        audio_file.write(audio_data)
        audio_file.close()

        proc = subprocess.Popen(
            [player_cmd, *player_args, audio_file.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        PID_FILE.write_text(str(proc.pid))

        cleanup = threading.Thread(
            target=_cleanup_after_playback,
            args=(proc, audio_file.name),
            daemon=True,
        )
        cleanup.start()

        return proc.pid

    except Exception:
        # Ensure temp file is removed if we never managed to start playback.
        try:
            audio_file.close()
            os.unlink(audio_file.name)
        except OSError:
            pass
        raise
