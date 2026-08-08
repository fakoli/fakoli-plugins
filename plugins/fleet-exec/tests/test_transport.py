"""Offline tests for fleet_exec.transport: payload prep, launcher probe,
stderr hygiene, the four states, hostname matching, and the JSON-RPC
server's protocol basics. Every `_run` call is faked -- no real ssh/network.
"""

from __future__ import annotations

import base64
import json
import subprocess

import pytest

from fleet_exec import server, transport


class FakeRun:
    """Queue of canned subprocess.run results/exceptions; records every call."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _cp(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["ssh"], returncode=returncode, stdout=stdout, stderr=stderr)


def _ok_cp(rc=0, stdout="hi", stderr=""):
    return _cp(0, stdout=json.dumps({"rc": rc, "stdout": stdout, "stderr": stderr}))


# --- payload preparation ---------------------------------------------------


def test_spaced_payload_is_client_side_quoted():
    payload = transport.prepare_remote_python("print('hello world')")
    assert payload.startswith('"') and payload.endswith('"')
    # exactly the two outer quotes -- a single shell-inert token
    assert payload.count('"') == 2


def test_multiline_payload_round_trips_through_base64():
    script = "import sys\nprint('a')\nprint('b')\n"
    payload = transport.prepare_remote_python(script)
    inner = payload[1:-1]
    encoded = inner.split("b64decode('")[1].split("')")[0]
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert decoded == script


# --- launcher fallback -------------------------------------------------


def test_fallback_fires_on_not_recognized(monkeypatch):
    fake = FakeRun(
        [
            _cp(1, stderr="'python3' is not recognized as an internal or external command"),
            _ok_cp(),
        ]
    )
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert len(fake.calls) == 2
    assert row["state"] == "ok"


def test_fallback_fires_on_not_found(monkeypatch):
    fake = FakeRun(
        [
            _cp(127, stderr="bash: python3: command not found"),
            _ok_cp(),
        ]
    )
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert len(fake.calls) == 2
    assert row["state"] == "ok"


def test_fallback_does_not_fire_on_other_nonzero_rc(monkeypatch):
    fake = FakeRun([_cp(1, stderr="permission denied")])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert len(fake.calls) == 1
    assert row["state"] == "unreachable"


# --- stderr hygiene ----------------------------------------------------


def test_client_banner_never_appears_in_detail_or_stderr(monkeypatch):
    stderr = (
        "** WARNING: server certificate uses a deprecated post-quantum key exchange\n"
        "connection refused"
    )
    fake = FakeRun([_cp(255, stderr=stderr)])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert "** " not in row["detail"]
    assert "** " not in row["stderr"]
    assert "post-quantum" not in row["detail"]
    assert "post-quantum" not in row["stderr"]
    assert row["state"] == "unreachable"


# --- the four states -----------------------------------------------------


def test_state_ok_on_rc_zero(monkeypatch):
    fake = FakeRun([_ok_cp(rc=0, stdout="hi")])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert row["state"] == "ok"
    assert row["rc"] == 0
    assert row["stdout"] == "hi"


def test_state_ok_preserves_nonzero_inner_command_rc(monkeypatch):
    fake = FakeRun([_ok_cp(rc=3, stdout="", stderr="boom")])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["false"])
    assert row["state"] == "ok"
    assert row["rc"] == 3


def test_state_timeout(monkeypatch):
    fake = FakeRun([subprocess.TimeoutExpired(cmd=["ssh"], timeout=30)])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert row["state"] == "timeout"


def test_state_unreachable_ssh_binary_missing(monkeypatch):
    fake = FakeRun([FileNotFoundError("ssh")])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert row["state"] == "unreachable"
    assert "ssh is not available" in row["detail"]


def test_state_unreachable_connection_refused(monkeypatch):
    fake = FakeRun([_cp(255, stderr="ssh: connect to host host-a port 22: Connection refused")])
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert row["state"] == "unreachable"


def test_state_not_installed_launcher_exhausted(monkeypatch):
    fake = FakeRun(
        [
            _cp(1, stderr="python3: command not found"),
            _cp(1, stderr="python: command not found"),
        ]
    )
    monkeypatch.setattr(transport, "_run", fake)
    row = transport.run_on_host("host-a", ["echo", "hi"])
    assert row["state"] == "not-installed"


# --- host id matching ----------------------------------------------------


def test_local_hostname_matches_bare_token():
    assert transport.local_hostname_matches("dark", "fakoli-dark") is True


def test_local_hostname_matches_with_domain_suffix():
    assert transport.local_hostname_matches("dark", "fakoli-dark.local") is True


def test_local_hostname_matches_rejects_bare_containment():
    assert transport.local_hostname_matches("w", "elsewhere") is False


# --- server: tools/list, notifications, unknown method ---------------------


def test_server_tools_list_returns_all_four_tools():
    response = server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {"run_on_host", "fetch_text", "push_file", "host_facts"}


def test_server_notifications_initialized_produces_no_response():
    response = server._handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert response is None


def test_server_unknown_method_returns_minus_32601():
    response = server._handle_request({"jsonrpc": "2.0", "id": 7, "method": "not/a/method"})
    assert response["error"]["code"] == -32601
