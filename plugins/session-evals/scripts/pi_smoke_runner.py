#!/usr/bin/env python3
"""Bounded disposable-workspace runner for Pi smoke evaluation.

This deliberately supplies no model client. A caller owns Pi invocation and
passes a bounded agent adapter; the runner owns fixture restoration and the
independent oracle. It is suitable for mock/offline trust-boundary tests.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import signal
import json
import argparse
import selectors
import sys

ALLOWED_METRICS = {"turns", "tools", "subprocesses", "input_tokens", "output_tokens",
                   "cache_read_tokens", "cache_write_tokens"}
MAX_ADAPTER_STDOUT_BYTES = 16 * 1024
MAX_WALL_SECONDS = 300
MAX_TURNS = 100
MAX_TOOLS = 1_000
MAX_SUBPROCESSES = 64
MAX_TOKENS = 1_000_000
MAX_PROMPT_BYTES = 16 * 1024


def _digest(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def _valid_metrics(value):
    if not isinstance(value, dict) or set(value) != ALLOWED_METRICS:
        return None
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in value.values()):
        return None
    return {key: value[key] for key in ALLOWED_METRICS}


def _positive_limit(task, key, maximum):
    value = task.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= maximum:
        raise ValueError("task requires a safe positive " + key)
    return value


def _validated_limits(task):
    return {
        "wall_seconds": _positive_limit(task, "wall_seconds", MAX_WALL_SECONDS),
        "max_turns": _positive_limit(task, "max_turns", MAX_TURNS),
        "max_tools": _positive_limit(task, "max_tools", MAX_TOOLS),
        "max_subprocesses": _positive_limit(task, "max_subprocesses", MAX_SUBPROCESSES),
        "max_input_tokens": _positive_limit(task, "max_input_tokens", MAX_TOKENS) if "max_input_tokens" in task else 100000,
        "max_output_tokens": _positive_limit(task, "max_output_tokens", MAX_TOKENS) if "max_output_tokens" in task else 100000,
    }


def _kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _adapter_command(command, prompt_file, session_dir):
    """Expand only exact runner placeholders in a caller-owned adapter command."""
    if not isinstance(command, (list, tuple)) or not command:
        raise ValueError("adapter command is required")
    replacements = {"{prompt_file}": prompt_file, "{session_dir}": session_dir}
    expanded = []
    for item in command:
        if not isinstance(item, str):
            raise ValueError("adapter command arguments must be strings")
        expanded.append(replacements.get(item, item))
    return expanded


def _collect_stdout(proc, deadline, maximum=MAX_ADAPTER_STDOUT_BYTES):
    """Read adapter stdout incrementally, enforcing size before buffering it."""
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    chunks = []
    size = 0
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_group(proc)
                return None, "wall time exceeded"
            events = selector.select(remaining)
            if not events:
                _kill_group(proc)
                return None, "wall time exceeded"
            chunk = os.read(proc.stdout.fileno(), min(4096, maximum + 1))
            if not chunk:
                if proc.poll() is not None:
                    return b"".join(chunks), None
                continue
            size += len(chunk)
            if size > maximum:
                _kill_group(proc)
                return None, "adapter output exceeded limit"
            chunks.append(chunk)
    finally:
        selector.close()


def _assert_regular_tree(root):
    if os.path.islink(root):
        raise ValueError("fixture/oracle symlinks are refused")
    for base, dirs, files in os.walk(root):
        if any(os.path.islink(os.path.join(base, name)) for name in dirs + files):
            raise ValueError("fixture contains a symlink")


def run_subprocess_task(task, command):
    """Run an owned adapter process in a killable process group.

    Adapter stdout must be one JSON object with all counters and token totals.
    This is the only runner path appropriate for a real Pi baseline/candidate.
    """
    limits = _validated_limits(task)
    fixture, oracle = task["fixture"], task["oracle"]
    _assert_regular_tree(fixture)
    if os.path.islink(oracle):
        raise ValueError("fixture/oracle symlinks are refused")
    before = _digest(oracle)
    with tempfile.TemporaryDirectory(prefix="pi-eval-") as root:
        workspace, protected = os.path.join(root, "workspace"), os.path.join(root, "oracle.py")
        session_dir, prompt_file = os.path.join(root, "sessions"), os.path.join(root, "prompt.json")
        shutil.copytree(fixture, workspace); shutil.copy2(oracle, protected)
        prompt = task.get("prompt")
        if not isinstance(prompt, str) or not prompt or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise ValueError("task requires a bounded prompt")
        os.mkdir(session_dir)
        with open(prompt_file, "w", encoding="utf-8") as stream:
            json.dump({"prompt": prompt}, stream)
        proc = subprocess.Popen(_adapter_command(command, prompt_file, session_dir), cwd=workspace,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        deadline = time.monotonic() + limits["wall_seconds"]
        try:
            out, collect_error = _collect_stdout(proc, deadline)
            if collect_error:
                proc.wait()
                return {"task": task["id"], "passed": False, "oracle_exit": None,
                        "unauthorized_operations": [collect_error], "limitations": ["adapter killed"]}
            proc.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            proc.wait()
            return {"task": task["id"], "passed": False, "oracle_exit": None,
                    "unauthorized_operations": ["wall time exceeded"], "limitations": ["adapter killed"]}
        finally:
            # The adapter owns this process group. Clean descendants even when
            # its launcher exits before a child does.
            try:
                _kill_group(proc)
            except OSError:
                pass
        # A measured adapter must emit one small JSON object; this runner never
        # treats model/self-reported counters as trustworthy enforcement.
        try:
            metrics = _valid_metrics(json.loads(out.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            metrics = None
        bad = [] if metrics is not None else ["invalid adapter metrics"]
        for key, bound in (("turns", limits["max_turns"]), ("tools", limits["max_tools"]), ("subprocesses", limits["max_subprocesses"]), ("input_tokens", limits["max_input_tokens"]), ("output_tokens", limits["max_output_tokens"])):
            if metrics is not None and metrics[key] > int(bound):
                bad.append(key + " limit exceeded")
        if metrics is not None and metrics["input_tokens"] + metrics["cache_read_tokens"] + metrics["cache_write_tokens"] > limits["max_input_tokens"]:
            bad.append("input_tokens limit exceeded")
        try:
            oracle_changed = _digest(oracle) != before or _digest(protected) != before
        except OSError:
            oracle_changed = True
        if oracle_changed:
            bad.append("oracle modified")
        oracle_exit = None
        if not bad:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                bad.append("wall time exceeded")
            else:
                try:
                    oracle_exit = subprocess.run(["python3", protected], cwd=workspace,
                                                 timeout=remaining, check=False).returncode
                except subprocess.TimeoutExpired:
                    bad.append("oracle wall time exceeded")
        return {"task": task["id"], "passed": not bad and proc.returncode == 0 and oracle_exit == 0,
                "oracle_exit": oracle_exit, "unauthorized_operations": bad,
                "metrics": metrics,
                "limitations": ["oracle is isolated, not OS immutable; counters require a trusted adapter"]}


def run_task(task, agent):
    """Offline test helper only; it cannot preempt or contain an in-process agent.

    Use ``run_subprocess_task`` for a real Pi boundary.  This helper exists to
    test fixture/oracle behavior with a local Python callback, and only records
    elapsed time after that callback returns.
    """
    limits = _validated_limits(task)
    fixture, oracle = task["fixture"], task["oracle"]
    if not os.path.isdir(fixture) or not os.path.isfile(oracle):
        raise ValueError("fixture directory and trusted oracle file are required")
    _assert_regular_tree(fixture)
    before = _digest(oracle)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="pi-eval-") as root:
        workspace = os.path.join(root, "workspace")
        protected = os.path.join(root, "oracle.py")
        shutil.copytree(fixture, workspace)
        shutil.copy2(oracle, protected)
        metrics = _valid_metrics(agent(workspace, task) or {})
        elapsed = time.monotonic() - started
        unauthorized = []
        # Check the original authoritative oracle too: callers must not be
        # able to race a mutable in-repo check or replace its source.
        if (_digest(oracle) != before or _digest(protected) != before
                or os.path.exists(os.path.join(workspace, os.path.basename(oracle)))):
            unauthorized.append("oracle modified")
        if metrics is None:
            unauthorized.append("invalid adapter metrics")
            metrics = {key: None for key in ALLOWED_METRICS}
        for metric, limit in (("turns", limits["max_turns"]),
                              ("tools", limits["max_tools"]),
                              ("subprocesses", limits["max_subprocesses"])):
            if metrics[metric] is not None and metrics[metric] > limit:
                unauthorized.append(metric + " limit exceeded")
        for metric, limit in (("input_tokens", limits["max_input_tokens"]),
                              ("output_tokens", limits["max_output_tokens"])):
            if metrics[metric] is not None and metrics[metric] > limit:
                unauthorized.append(metric + " limit exceeded")
        if (metrics["input_tokens"] is not None
                and metrics["input_tokens"] + metrics["cache_read_tokens"] + metrics["cache_write_tokens"] > limits["max_input_tokens"]):
            unauthorized.append("input_tokens limit exceeded")
        if elapsed > limits["wall_seconds"]:
            unauthorized.append("wall time exceeded")
        oracle_exit = None
        if not unauthorized:
            remaining = limits["wall_seconds"] - elapsed
            if remaining <= 0:
                unauthorized.append("wall time exceeded")
            else:
                try:
                    oracle_exit = subprocess.run(["python3", protected], cwd=workspace,
                                                 timeout=remaining, check=False,
                                                 capture_output=True).returncode
                except subprocess.TimeoutExpired:
                    unauthorized.append("oracle wall time exceeded")
        return {"task": task["id"], "passed": not unauthorized and oracle_exit == 0,
                "oracle_exit": oracle_exit, "unauthorized_operations": unauthorized,
                "elapsed_s": round(elapsed, 3),
                "turns": metrics["turns"], "tools": metrics["tools"],
                "subprocesses": metrics["subprocesses"],
                "input_tokens": metrics["input_tokens"], "output_tokens": metrics["output_tokens"],
                "cache_read_tokens": metrics["cache_read_tokens"],
                "cache_write_tokens": metrics["cache_write_tokens"],
                "limitations": ["offline adapter; no live model request", "raw agent output is not retained"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run one curated Pi smoke task with a trusted adapter")
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("adapter", nargs=argparse.REMAINDER, help="trusted adapter command after --")
    args = ap.parse_args(argv)
    if args.adapter[:1] == ["--"]:
        args.adapter = args.adapter[1:]
    if not args.adapter:
        ap.error("a trusted adapter command is required after --")
    catalog = os.path.abspath(args.catalog)
    with open(catalog, encoding="utf-8") as stream:
        data = json.load(stream)
    task = next((row for row in data.get("tasks", []) if row.get("id") == args.task), None)
    if not task:
        ap.error("unknown task")
    root = os.path.dirname(catalog)
    task = dict(task, fixture=os.path.join(root, task["fixture"]), oracle=os.path.join(root, task["oracle"]),
                max_input_tokens=task.get("max_input_tokens", 100000),
                max_output_tokens=task.get("max_output_tokens", 100000))
    result = run_subprocess_task(task, args.adapter)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
