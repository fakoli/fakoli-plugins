"""Offline tests for fleet_exec.transport: payload prep, launcher probe,
stderr hygiene, the four states, hostname matching, and the JSON-RPC
server's protocol basics. Every `_run` call is faked -- no real ssh/network.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys

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


# --- the generated wrapper's OWN error handling ----------------------------
#
# Every other test fakes `_run`, which sits OUTSIDE the generated wrapper
# script -- so no other test ever executes the wrapper's source. That blind
# spot is exactly how a missing `except OSError` shipped: a reachable host
# running a nonexistent binary crashed the wrapper, produced no JSON, and got
# reported as `unreachable`. These tests run the real payload through a real
# interpreter locally. No ssh, no network.


def _exec_generated_payload(monkeypatch, call):
    """Capture the script a tool generates, then run it locally and parse it."""
    captured = {}

    def capture(argv, **kwargs):
        captured["payload"] = argv[-1]
        return _cp(0, stdout='{"rc": 0, "stdout": "", "stderr": ""}')

    monkeypatch.setattr(transport, "_run", capture)
    call()
    # argv[-1] is the client-side-quoted payload; strip the wrapping quotes and
    # recover the base64'd script the remote interpreter would actually run.
    quoted = captured["payload"]
    assert quoted.startswith('"') and quoted.endswith('"')
    encoded = quoted.split("'")[1]
    script = base64.b64decode(encoded).decode("utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_generated_wrapper_survives_a_missing_remote_binary(monkeypatch):
    out = _exec_generated_payload(
        monkeypatch,
        lambda: transport.run_on_host("host-a", ["definitely-not-a-real-binary-xyz"]),
    )
    # The transport worked; only the requested command was absent.
    assert out["rc"] == 127
    assert out["stdout"] == ""
    assert out["stderr"]
    assert "timeout" not in out


def test_generated_wrapper_reports_a_real_nonzero_exit(monkeypatch):
    out = _exec_generated_payload(
        monkeypatch,
        lambda: transport.run_on_host("host-a", [sys.executable, "-c", "raise SystemExit(3)"]),
    )
    assert out["rc"] == 3


def test_generated_fetch_wrapper_reports_a_missing_file(monkeypatch):
    out = _exec_generated_payload(
        monkeypatch,
        lambda: transport.fetch_text("host-a", "/no/such/path/at/all.txt"),
    )
    assert out["rc"] == 1
    assert out["stderr"]


# --- server bounds ----------------------------------------------------------


def test_server_clamps_an_oversized_timeout(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        transport, "run_on_host", lambda host, argv, timeout_s: seen.setdefault("t", timeout_s)
    )
    server._call_tool("run_on_host", {"host": "host-a", "argv": ["ls"], "timeout_s": 86400})
    assert seen["t"] == server.MAX_TIMEOUT_S


def test_server_clamps_an_oversized_max_bytes(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        transport, "fetch_text", lambda host, path, max_bytes: seen.setdefault("m", max_bytes)
    )
    server._call_tool("fetch_text", {"host": "host-a", "path": "/tmp/x", "max_bytes": 10**9})
    assert seen["m"] == server.MAX_FETCH_BYTES


# --- host id matching ----------------------------------------------------


def test_local_hostname_matches_bare_token():
    assert transport.local_hostname_matches("alpha", "site-alpha") is True


def test_local_hostname_matches_with_domain_suffix():
    assert transport.local_hostname_matches("alpha", "site-alpha.local") is True


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


def test_server_unimplemented_notification_produces_no_response():
    # JSON-RPC 4.1: an id-less request is a notification and must never draw a
    # reply -- not even the -32601 one. Real MCP clients send this.
    response = server._handle_request(
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}
    )
    assert response is None


def test_server_unknown_method_returns_minus_32601():
    response = server._handle_request({"jsonrpc": "2.0", "id": 7, "method": "not/a/method"})
    assert response["error"]["code"] == -32601
