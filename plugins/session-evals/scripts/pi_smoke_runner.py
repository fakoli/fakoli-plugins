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


def _digest(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def run_task(task, agent):
    """Run one task with a trusted oracle outside the writable workspace."""
    limits = {key: int(task.get(key, 0)) for key in
              ("wall_seconds", "max_turns", "max_tools", "max_subprocesses")}
    if any(value <= 0 for value in limits.values()):
        raise ValueError("task requires positive wall/tool/turn/subprocess bounds")
    fixture, oracle = task["fixture"], task["oracle"]
    if not os.path.isdir(fixture) or not os.path.isfile(oracle):
        raise ValueError("fixture directory and trusted oracle file are required")
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
