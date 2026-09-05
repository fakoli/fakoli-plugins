"""No provider calls/audio output: private fixtures and fake playback binaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
import pytest
from fakoli_speak import autospeak, cost, playback


def test_stop_hook_current_field_and_malformed_input():
    text = 'A substantial assistant response. ' * 10
    assert autospeak.extract_text_from_hook({'last_assistant_message': text}) == text.strip()
    assert autospeak.extract_text_from_hook({'last_assistant_message': text, 'stop_hook_active': True}) is None
    assert autospeak.extract_text_from_hook(['not an event']) is None


def test_stop_never_signals_a_bare_or_negative_pid(tmp_path, monkeypatch):
    pidfile = tmp_path / 'playback.json'
    monkeypatch.setattr(playback, 'PID_FILE', pidfile)
    for value in ['-1', '0', str(os.getpid()), '{"pid": -1, "audio_path": "/tmp/audio"}']:
        pidfile.write_text(value)
        with patch.object(playback.os, 'kill') as kill:
            playback.stop()
            kill.assert_not_called()


def test_stop_preserves_unrelated_process(tmp_path, monkeypatch):
    pidfile = tmp_path / 'playback.json'
    monkeypatch.setattr(playback, 'PID_FILE', pidfile)
    pidfile.write_text(json.dumps({'pid': os.getpid(), 'audio_path': '/never-owned.wav'}))
    with patch.object(playback.os, 'kill') as kill:
        playback.stop()
        kill.assert_not_called()


def test_worker_finishes_and_cleans_after_parent_cli_exits(tmp_path):
    record = tmp_path / 'playback.json'
    audio = tmp_path / 'fixture.wav'
    audio.write_bytes(b'fake audio')
    fake_player = tmp_path / 'fake_player.py'
    fake_player.write_text('import time; time.sleep(0.1)')
    worker = Path(playback.__file__).with_name('_playback_worker.py')
    proc = subprocess.Popen([sys.executable, str(worker), str(record), str(audio), sys.executable, str(fake_player)])
    try:
        assert proc.wait(timeout=5) == 0
        assert not audio.exists()
        assert not record.exists()
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()


def test_old_worker_does_not_delete_new_playback_record(tmp_path):
    record = tmp_path / 'playback.json'
    audio = tmp_path / 'fixture.wav'
    audio.write_bytes(b'fake')
    fake = tmp_path / 'fake.py'
    fake.write_text('import time; time.sleep(0.3)')
    worker = Path(playback.__file__).with_name('_playback_worker.py')
    proc = subprocess.Popen([sys.executable, str(worker), str(record), str(audio), sys.executable, str(fake)])
    try:
        deadline = time.monotonic() + 3
        while not record.exists() and time.monotonic() < deadline: time.sleep(0.01)
        assert record.exists()
        record.write_text(json.dumps({'pid': 987654, 'audio_path': 'new'}))
        assert proc.wait(timeout=5) == 0
        assert json.loads(record.read_text())['pid'] == 987654
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()


def test_active_provider_cost_override_is_used_in_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(cost, 'COST_LOG_PATH', tmp_path / 'cost.json')
    monkeypatch.setenv('FAKOLI_SPEAK_PROVIDER', 'openai')
    cost.set_cost_rate(0.42)
    assert cost.get_summary()['cost_per_1k_chars'] == 0.42
    with pytest.raises(ValueError): cost.set_cost_rate(float('nan'))


def test_worker_stops_a_player_that_ignores_termination(tmp_path):
    record = tmp_path / 'playback.json'
    audio = tmp_path / 'fixture.wav'
    audio.write_bytes(b'fake')
    ready = tmp_path / 'player-ready'
    fake = tmp_path / 'stubborn.py'
    fake.write_text('import signal,time\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nPath(' + repr(str(ready)) + ').touch()\ntime.sleep(30)\n')
    worker = Path(playback.__file__).with_name('_playback_worker.py')
    proc = subprocess.Popen([sys.executable, str(worker), str(record), str(audio), sys.executable, str(fake)])
    try:
        deadline = time.monotonic() + 3
        while not ready.exists() and time.monotonic() < deadline: time.sleep(0.01)
        assert ready.exists()
        proc.terminate()
        assert proc.wait(timeout=4) == 0
        assert not audio.exists()
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
