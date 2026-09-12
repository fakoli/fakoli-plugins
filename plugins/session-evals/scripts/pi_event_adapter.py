#!/usr/bin/env python3
"""Trusted Pi JSON-event adapter for the smoke runner; never retains messages.

This adapter only launches an explicitly selected composition. It disables
discovered extensions and Pi's built-in filesystem tools, then loads the
reviewed fixture-scoped read/edit/write implementation by path. The launcher
is caller-owned; this process does not claim to sandbox an arbitrary launcher.
"""
import argparse
import json
import os
import subprocess
import sys


SAFE_ENV = {"HOME", "PATH", "TMPDIR", "TEMP", "TMP", "PI_CODING_AGENT_DIR"}
DROP = ("KEY", "TOKEN", "SECRET", "PASSWORD", "ANTHROPIC", "OPENAI", "GEMINI")
MAX_EVENT_LINE_BYTES = 64 * 1024
MAX_EVENT_STREAM_BYTES = 1024 * 1024
ALLOWED_TOOLS = {"read", "edit", "write"}
FAILED_STOPS = {"error", "failed", "cancelled", "canceled", "length", "max_tokens"}


def _strict_nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid " + label)
    return value


def _strict_positive(value, label):
    value = _strict_nonnegative(value, label)
    if not value:
        raise ValueError("invalid " + label)
    return value


def _usage(message):
    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
        raise ValueError("assistant message missing usage")
    usage = message["usage"]
    aliases = {
        "input_tokens": ("input", "inputTokens"),
        "output_tokens": ("output", "outputTokens"),
        "cache_read_tokens": ("cacheRead", "cache_read", "cacheReadTokens"),
        "cache_write_tokens": ("cacheWrite", "cache_write", "cacheWriteTokens"),
    }
    values = {}
    for target, names in aliases.items():
        raw = next((usage[name] for name in names if name in usage), None)
        if raw is None:
            raise ValueError("assistant usage missing " + target)
        values[target] = _strict_nonnegative(raw, "usage " + target)
    return values


def _terminal_failure(event, message):
    if event.get("type") in {"error", "agent_error", "cancelled", "canceled"}:
        return True
    if event.get("error") or (isinstance(message, dict) and message.get("error")):
        return True
    value = event.get("stopReason", event.get("finishReason"))
    if value is None and isinstance(message, dict):
        value = message.get("stopReason", message.get("finishReason"))
    return isinstance(value, str) and value.lower() in FAILED_STOPS


def _tool_id(event):
    value = event.get("toolCallId", event.get("tool_call_id", event.get("id")))
    if not isinstance(value, str) or not value:
        raise ValueError("tool event missing call id")
    return value


def _validate_limits(limits):
    expected = {"turns", "tools", "subprocesses", "input_tokens", "output_tokens"}
    if not isinstance(limits, dict) or set(limits) != expected:
        raise ValueError("invalid limits")
    return {name: _strict_positive(limits[name], name) for name in limits}


def measured_events(lines, limits, *, max_line_bytes=MAX_EVENT_LINE_BYTES,
                    max_stream_bytes=MAX_EVENT_STREAM_BYTES):
    """Measure a complete Pi event stream and reject failed/incomplete turns.

    A turn is a completed assistant message, not a generic ``turn_end`` event.
    Tool-start/result pairs are required, so a repair cannot transform a final
    invocation into an apparently successful earlier call.
    """
    limits = _validate_limits(limits)
    max_line_bytes = _strict_positive(max_line_bytes, "max event line bytes")
    max_stream_bytes = _strict_positive(max_stream_bytes, "max event stream bytes")
    counts = {"turns": 0, "tools": 0, "subprocesses": 1, "input_tokens": 0,
              "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    outstanding, stream_bytes = set(), 0
    agent_end_index = None
    last_assistant_stop = None
    last_assistant_index = None
    for index, line in enumerate(lines):
        if not isinstance(line, str):
            raise ValueError("invalid Pi event")
        size = len(line.encode("utf-8"))
        if size > max_line_bytes:
            raise ValueError("Pi event line exceeded limit")
        stream_bytes += size
        if stream_bytes > max_stream_bytes:
            raise ValueError("Pi event stream exceeded limit")
        try:
            event = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            raise ValueError("truncated or invalid Pi event") from None
        if not isinstance(event, dict):
            raise ValueError("invalid Pi event")
        message = event.get("message")
        if _terminal_failure(event, message):
            raise ValueError("Pi model failed, was cancelled, or hit its length limit")
        kind = event.get("type")
        if kind == "tool_execution_start":
            if event.get("toolName") not in ALLOWED_TOOLS:
                raise ValueError("disallowed Pi tool")
            call_id = _tool_id(event)
            if call_id in outstanding:
                raise ValueError("duplicate tool call")
            outstanding.add(call_id)
            counts["tools"] += 1
        elif kind in {"tool_execution_end", "tool_result"}:
            call_id = _tool_id(event)
            if call_id not in outstanding:
                raise ValueError("unpaired tool result")
            if event.get("isError"):
                raise ValueError("Pi tool failed")
            outstanding.remove(call_id)
        elif kind == "message_end" and isinstance(message, dict) and message.get("role") == "assistant":
            usage = _usage(message)
            for name, value in usage.items():
                counts[name] += value
            counts["turns"] += 1
            last_assistant_stop = message.get("stopReason", message.get("finishReason"))
            last_assistant_index = index
        elif kind == "agent_end":
            agent_end_index = index
        if (counts["turns"] > limits["turns"] or counts["tools"] > limits["tools"]
                or counts["subprocesses"] > limits["subprocesses"]
                or counts["output_tokens"] > limits["output_tokens"]
                or counts["input_tokens"] + counts["cache_read_tokens"] + counts["cache_write_tokens"] > limits["input_tokens"]):
            raise ValueError("Pi event limit exceeded")
    if not counts["turns"]:
        raise ValueError("missing completed assistant message")
    if outstanding:
        raise ValueError("unpaired tool call")
    if agent_end_index is None:
        raise ValueError("missing agent_end")
    if last_assistant_index is None or agent_end_index <= last_assistant_index:
        raise ValueError("agent_end did not follow final assistant message")
    if last_assistant_stop != "stop":
        raise ValueError("final assistant message did not stop successfully")
    return counts


def _extension(path, label):
    path = os.path.abspath(path)
    if not os.path.isfile(path) or os.path.islink(path):
        raise ValueError(label + " must be a regular file")
    return path


def _bounded_event_lines(stream):
    """Yield decoded JSONL records without first buffering an arbitrary line."""
    pending = bytearray()
    stream_bytes = 0
    while True:
        chunk = os.read(stream.fileno(), 4096)
        if not chunk:
            break
        stream_bytes += len(chunk)
        if stream_bytes > MAX_EVENT_STREAM_BYTES:
            raise ValueError("Pi event stream exceeded limit")
        pending.extend(chunk)
        while b"\n" in pending:
            raw, _, rest = pending.partition(b"\n")
            pending = bytearray(rest)
            if len(raw) > MAX_EVENT_LINE_BYTES:
                raise ValueError("Pi event line exceeded limit")
            try:
                yield raw.decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError("truncated or invalid Pi event") from None
        if len(pending) > MAX_EVENT_LINE_BYTES:
            raise ValueError("Pi event line exceeded limit")
    if pending:
        if len(pending) > MAX_EVENT_LINE_BYTES:
            raise ValueError("Pi event line exceeded limit")
        try:
            yield pending.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("truncated or invalid Pi event") from None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure one explicitly controlled Pi smoke run")
    ap.add_argument("--launcher", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--session-dir", required=True)
    ap.add_argument("--restricted-tools-extension", required=True)
    ap.add_argument("--reviewed-extension", action="append", default=[])
    ap.add_argument("--max-turns", type=int, required=True)
    ap.add_argument("--max-tools", type=int, required=True)
    ap.add_argument("--max-input-tokens", type=int, default=100000)
    ap.add_argument("--max-output-tokens", type=int, default=100000)
    args = ap.parse_args(argv)
    try:
        limits = _validate_limits({"turns": args.max_turns, "tools": args.max_tools,
                                   "subprocesses": 1, "input_tokens": args.max_input_tokens,
                                   "output_tokens": args.max_output_tokens})
        with open(args.prompt_file, encoding="utf-8") as stream:
            prompt = json.load(stream)
        if not isinstance(prompt, dict) or not isinstance(prompt.get("prompt"), str):
            raise ValueError("prompt file needs prompt text")
        guard = _extension(args.restricted_tools_extension, "restricted tools extension")
        reviewed = [_extension(path, "reviewed extension") for path in args.reviewed_extension]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        ap.error(str(exc))
    env = {key: value for key, value in os.environ.items()
           if key in SAFE_ENV and not any(marker in key.upper() for marker in DROP)}
    cmd = [args.launcher, "--mode", "json", "--no-builtin-tools", "--no-extensions",
           "--extension", guard]
    for extension in reviewed:
        cmd.extend(["--extension", extension])
    cmd.extend(["--tools", "read,edit,write", "--no-approve", "--no-context-files",
                "--no-skills", "--no-prompt-templates", "--session-dir", args.session_dir,
                "-p", prompt["prompt"]])
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    try:
        lines = _bounded_event_lines(proc.stdout) if hasattr(proc.stdout, "fileno") else proc.stdout
        counts = measured_events(lines, limits)
    except ValueError as exc:
        proc.kill()
        proc.wait()
        print(json.dumps({"error": str(exc)}))
        return 1
    if proc.wait() != 0:
        return 1
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
