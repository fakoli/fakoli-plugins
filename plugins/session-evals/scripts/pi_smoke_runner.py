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


def _digest(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


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
    fixture, oracle = task["fixture"], task["oracle"]
    _assert_regular_tree(fixture)
    if os.path.islink(oracle):
        raise ValueError("fixture/oracle symlinks are refused")
    before = _digest(oracle)
    with tempfile.TemporaryDirectory(prefix="pi-eval-") as root:
        workspace, protected = os.path.join(root, "workspace"), os.path.join(root, "oracle.py")
        shutil.copytree(fixture, workspace); shutil.copy2(oracle, protected)
        proc = subprocess.Popen(command, cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        try:
            out, _ = proc.communicate(timeout=int(task["wall_seconds"]))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.communicate()
            return {"task": task["id"], "passed": False, "oracle_exit": None,
                    "unauthorized_operations": ["wall time exceeded"], "limitations": ["adapter killed"]}
        try:
            metrics = json.loads(out)
        except (json.JSONDecodeError, TypeError):
            metrics = {}
        required = {"turns", "tools", "subprocesses", "input_tokens", "output_tokens"}
        bad = [] if required <= set(metrics) else ["missing adapter metrics"]
        for key, bound in (("turns", task["max_turns"]), ("tools", task["max_tools"]), ("subprocesses", task["max_subprocesses"]), ("input_tokens", task.get("max_input_tokens", 100000)), ("output_tokens", task.get("max_output_tokens", 100000))):
            if key in metrics and (not isinstance(metrics[key], int) or metrics[key] < 0 or metrics[key] > int(bound)):
                bad.append(key + " limit exceeded")
        if _digest(oracle) != before or _digest(protected) != before:
            bad.append("oracle modified")
        oracle_exit = None if bad else subprocess.run(["python3", protected], cwd=workspace, timeout=int(task["wall_seconds"])).returncode
        return {"task": task["id"], "passed": not bad and proc.returncode == 0 and oracle_exit == 0,
                "oracle_exit": oracle_exit, "unauthorized_operations": bad, **metrics,
                "limitations": ["oracle is isolated, not OS immutable; manual review required"]}


def run_task(task, agent):
    """Run one task with a trusted oracle outside the writable workspace."""
    limits = {key: int(task.get(key, 0)) for key in
              ("wall_seconds", "max_turns", "max_tools", "max_subprocesses")}
    if any(value <= 0 for value in limits.values()):
        raise ValueError("task requires positive wall/tool/turn/subprocess bounds")
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
        metrics = agent(workspace, task) or {}
        elapsed = time.monotonic() - started
        unauthorized = []
        # Check the original authoritative oracle too: callers must not be
        # able to race a mutable in-repo check or replace its source.
        if (_digest(oracle) != before or _digest(protected) != before
                or os.path.exists(os.path.join(workspace, os.path.basename(oracle)))):
            unauthorized.append("oracle modified")
        for metric, limit in (("turns", limits["max_turns"]),
                              ("tools", limits["max_tools"]),
                              ("subprocesses", limits["max_subprocesses"])):
            if int(metrics.get(metric, 0)) > limit:
                unauthorized.append(metric + " limit exceeded")
        if elapsed > limits["wall_seconds"]:
            unauthorized.append("wall time exceeded")
        oracle_exit = None
        if not unauthorized:
            oracle_exit = subprocess.run(["python3", protected], cwd=workspace,
                                         timeout=limits["wall_seconds"], check=False,
                                         capture_output=True).returncode
        return {"task": task["id"], "passed": not unauthorized and oracle_exit == 0,
                "oracle_exit": oracle_exit, "unauthorized_operations": unauthorized,
                "elapsed_s": round(elapsed, 3),
                "turns": metrics.get("turns"), "tools": metrics.get("tools"),
                "subprocesses": metrics.get("subprocesses"),
                "input_tokens": metrics.get("input_tokens"),
                "output_tokens": metrics.get("output_tokens"),
                "limitations": ["offline adapter; no live model request", "raw agent output is not retained"]}
