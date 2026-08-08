"""Stdio JSON-RPC MCP server for fleet-exec.

Hand-rolled (stdlib only, no `mcp` package): reads newline-delimited
JSON-RPC 2.0 requests from stdin, writes responses to stdout. stdout is the
JSON-RPC channel -- log to stderr only, a stray print corrupts the protocol.
"""

from __future__ import annotations

import json
import os
import sys

from . import transport

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "fleet-exec", "version": "1.0.0"}

# Ceilings, not just defaults: an LLM caller can ask for timeout_s=86400 or
# max_bytes=1e9 and get a hung ssh call or a whole remote file inlined into one
# JSON-RPC line. Clamp rather than refuse -- an over-large request still has an
# obvious intent, and the clamped result is reported honestly.
MAX_TIMEOUT_S = 600
MAX_FETCH_BYTES = 1_000_000

TOOLS = [
    {
        "name": "run_on_host",
        "description": "Run a command (list argv, never a shell string) on a remote host over ssh.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "argv": {"type": "array", "items": {"type": "string"}},
                "timeout_s": {"type": "integer", "default": 30, "minimum": 1, "maximum": MAX_TIMEOUT_S},
            },
            "required": ["host", "argv"],
        },
    },
    {
        "name": "fetch_text",
        "description": "Read a remote text file, truncated to max_bytes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "default": 256000, "minimum": 1, "maximum": MAX_FETCH_BYTES},
            },
            "required": ["host", "path"],
        },
    },
    {
        "name": "push_file",
        "description": "Write a local file to a remote host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "local_path": {"type": "string"},
                "remote_path": {"type": "string"},
            },
            "required": ["host", "local_path", "remote_path"],
        },
    },
    {
        "name": "host_facts",
        "description": "Collect os family, python launcher, and home dir facts from a remote host.",
        "inputSchema": {
            "type": "object",
            "properties": {"host": {"type": "string"}},
            "required": ["host"],
        },
    },
]


def _default_timeout() -> int:
    return int(os.environ.get("FLEET_EXEC_TIMEOUT", "30"))


def _default_max_bytes() -> int:
    return int(os.environ.get("FLEET_EXEC_MAX_BYTES", "256000"))


def _clamp(value, ceiling: int) -> int:
    return max(1, min(int(value), ceiling))


_HANDLERS = {
    "run_on_host": lambda args: transport.run_on_host(
        args["host"], args["argv"], _clamp(args.get("timeout_s", _default_timeout()), MAX_TIMEOUT_S)
    ),
    "fetch_text": lambda args: transport.fetch_text(
        args["host"], args["path"], _clamp(args.get("max_bytes", _default_max_bytes()), MAX_FETCH_BYTES)
    ),
    "push_file": lambda args: transport.push_file(args["host"], args["local_path"], args["remote_path"]),
    "host_facts": lambda args: transport.host_facts(args["host"]),
}


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _write(response: dict) -> None:
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _tool_error(kind: str, reason: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"error": {"kind": kind, "reason": reason}})}], "isError": True}


def _call_tool(name, arguments) -> dict:
    handler = _HANDLERS.get(name)
    if handler is None:
        return _tool_error("refused", "unknown tool: %s" % name)
    try:
        row = handler(arguments or {})
    except transport.FleetExecRefusal as exc:
        # Refusals are never a fleet state -- keep the four host states pure.
        return _tool_error("refused", str(exc))
    except (KeyError, TypeError) as exc:
        return _tool_error("refused", "missing or malformed argument: %s" % exc)
    except OSError as exc:
        # Local I/O errors (e.g. push_file's local_path missing) aren't a
        # host condition either -- they never reached the network.
        return _tool_error("error", str(exc))
    return {"content": [{"type": "text", "text": json.dumps(row)}]}


def _handle_request(request: dict):
    method = request.get("method")
    req_id = request.get("id")

    # JSON-RPC 2.0 4.1: a request without an id is a notification and MUST NOT
    # be answered -- including ones we do not implement. Gating on the id (not
    # on a list of known notification method names) is what keeps
    # notifications/cancelled and notifications/progress from drawing a
    # spurious -32601 reply with a null id.
    if "id" not in request:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = request.get("params") or {}
        result = _call_tool(params.get("name"), params.get("arguments"))
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "method not found: %s" % method},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError as exc:
            _log("fleet-exec: malformed JSON-RPC line: %s" % exc)
            continue
        try:
            response = _handle_request(request)
        except Exception as exc:  # keep the stdio loop alive on unexpected errors
            _log("fleet-exec: unhandled error: %s" % exc)
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32603, "message": str(exc)},
            }
        if response is not None:
            _write(response)


if __name__ == "__main__":
    main()
