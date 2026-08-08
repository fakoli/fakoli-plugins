"""Offline tests for fleet_exec's structural refusals: checked BEFORE any
read/transmit, never a fleet state. Every `_run` call is faked so a refusal
that leaked past the guard would be caught by the "never called" assertion.
"""

from __future__ import annotations

import pytest

from fleet_exec import transport
from fleet_exec.transport import FleetExecRefusal


class FakeRun:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        raise AssertionError("transport._run must not be called for a refused request")


@pytest.fixture
def fake_run(monkeypatch):
    fake = FakeRun()
    monkeypatch.setattr(transport, "_run", fake)
    return fake


# --- run_on_host argv shape ------------------------------------------------


def test_string_command_refused(fake_run):
    with pytest.raises(FleetExecRefusal, match="list argv"):
        transport.run_on_host("host-a", "echo hi")
    assert fake_run.calls == []


# --- secret-shaped argv -----------------------------------------------------


def test_token_equals_refused(fake_run):
    with pytest.raises(FleetExecRefusal):
        transport.run_on_host("host-a", ["TOKEN=abc123"])
    assert fake_run.calls == []


def test_password_flag_refused(fake_run):
    with pytest.raises(FleetExecRefusal):
        transport.run_on_host("host-a", ["--password", "hunter2"])
    assert fake_run.calls == []


def test_45_char_base64_string_refused(fake_run):
    long_base64ish = "A" * 45
    with pytest.raises(FleetExecRefusal):
        transport.run_on_host("host-a", [long_base64ish])
    assert fake_run.calls == []


def test_key_equals_pattern_refused(fake_run):
    with pytest.raises(FleetExecRefusal):
        transport.run_on_host("host-a", ["config", "key=xyz"])
    assert fake_run.calls == []


def test_ordinary_argv_not_refused(monkeypatch):
    import subprocess

    fake = lambda argv, **kwargs: subprocess.CompletedProcess(  # noqa: E731
        args=argv, returncode=0, stdout='{"rc": 0, "stdout": "ok", "stderr": ""}', stderr=""
    )
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["ls", "-la"])
    assert row["state"] == "ok"


# --- sensitive basenames for fetch_text / push_file -------------------------


@pytest.mark.parametrize("basename", [".env", ".env.local", "id_rsa", "x.pem", "credentials"])
def test_fetch_text_refuses_sensitive_basenames(fake_run, basename):
    with pytest.raises(FleetExecRefusal):
        transport.fetch_text("host-a", "/home/user/" + basename)
    assert fake_run.calls == []


@pytest.mark.parametrize("basename", [".env", ".env.local", "id_rsa", "x.pem", "credentials"])
def test_push_file_refuses_sensitive_remote_basenames(fake_run, tmp_path, basename):
    local = tmp_path / "payload.txt"
    local.write_text("data")
    with pytest.raises(FleetExecRefusal):
        transport.push_file("host-a", str(local), "/home/user/" + basename)
    assert fake_run.calls == []


def test_push_file_refuses_sensitive_local_basename(fake_run):
    with pytest.raises(FleetExecRefusal):
        transport.push_file("host-a", "/home/user/id_rsa", "/home/user/backup.txt")
    assert fake_run.calls == []


def test_push_file_refusal_happens_before_any_local_read(fake_run):
    # The local path does not exist -- if the guard ran after open(), this
    # would raise FileNotFoundError instead of FleetExecRefusal.
    with pytest.raises(FleetExecRefusal):
        transport.push_file("host-a", "/does/not/exist/id_rsa", "/home/user/backup.txt")
    assert fake_run.calls == []
