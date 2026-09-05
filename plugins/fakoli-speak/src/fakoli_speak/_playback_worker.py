"""Standalone player supervisor; outlives the invoking short-lived CLI."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


def main():
    record, audio, *player = sys.argv[1:]
    record = Path(record)
    proc = None
    stopping = False
    def stop(_signal, _frame):
        nonlocal stopping
        stopping = True
        if proc is not None:
            proc.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        if stopping:
            return
        proc = subprocess.Popen([*player, audio], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if stopping:
            proc.terminate()
        with tempfile.NamedTemporaryFile(mode='w', dir=record.parent, delete=False) as state:
            json.dump({'pid': os.getpid(), 'audio_path': audio}, state)
        os.replace(state.name, record)
        while True:
            try:
                proc.wait(timeout=2 if stopping else 0.2)
                break
            except subprocess.TimeoutExpired:
                if stopping:
                    proc.kill()
                    proc.wait()
                    break
    finally:
        Path(audio).unlink(missing_ok=True)
        try:
            if json.loads(record.read_text()).get('pid') == os.getpid():
                record.unlink(missing_ok=True)
        except (OSError, ValueError, AttributeError):
            pass


if __name__ == '__main__':
    main()
