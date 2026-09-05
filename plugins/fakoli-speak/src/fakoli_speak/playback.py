"""Owned playback processes; never kill global audio players or trust bare PIDs."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from .protocol import NoPlayerFound

PID_FILE = Path(os.environ.get('FAKOLI_SPEAK_PID_FILE', str(Path.home() / '.cache/fakoli-speak/playback.json')))
_PLAYERS = [('afplay', []), ('mpv', ['--no-terminal']), ('ffplay', ['-nodisp', '-autoexit', '-loglevel', 'quiet'])]
_FORMAT_SUFFIX = {'mp3': '.mp3', 'wav': '.wav', 'aiff': '.aiff', 'aif': '.aiff', 'pcm': '.pcm', 'ogg': '.ogg', 'opus': '.opus', 'flac': '.flac'}


def find_player():
    for command, arguments in _PLAYERS:
        if shutil.which(command):
            return command, arguments
    raise NoPlayerFound('No audio player found on PATH. Install one of: afplay, mpv, ffplay.')


def _record():
    try:
        data = json.loads(PID_FILE.read_text())
        if not isinstance(data, dict) or type(data.get('pid')) is not int or data['pid'] <= 1:
            return None
        if not isinstance(data.get('audio_path'), str) or not data['audio_path']:
            return None
        return data
    except (OSError, ValueError):
        return None


def _owned(data):
    try:
        result = subprocess.run(['ps', '-p', str(data['pid']), '-o', 'args='], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and '_playback_worker.py' in result.stdout and data['audio_path'] in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def is_playing():
    data = _record()
    if data and _owned(data):
        return True, data['pid']
    PID_FILE.unlink(missing_ok=True)
    return False, None


def stop():
    data = _record()
    if data and _owned(data):
        try:
            os.kill(data['pid'], signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    PID_FILE.unlink(missing_ok=True)


def play_audio(audio_data: bytes, audio_format: str = 'mp3') -> int:
    command, args = find_player()
    suffix = _FORMAT_SUFFIX.get(audio_format.lower(), '.audio')
    with tempfile.NamedTemporaryFile(prefix='fakoli-tts-', suffix=suffix, delete=False) as audio:
        audio.write(audio_data)
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('_playback_worker.py')),
                                 str(PID_FILE), audio.name, command, *args],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        # The worker writes and owns its record; no cleanup thread dies with the CLI.
        return proc.pid
    except BaseException:
        Path(audio.name).unlink(missing_ok=True)
        raise
