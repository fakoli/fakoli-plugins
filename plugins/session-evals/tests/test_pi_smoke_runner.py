import importlib.util
import json
import os
import sys
import time

import pytest


HERE = os.path.dirname(__file__)
SCRIPTS = os.path.join(HERE, "..", "scripts")
spec = importlib.util.spec_from_file_location("pi_smoke_runner", os.path.join(SCRIPTS, "pi_smoke_runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_mock_runner_restores_baseline_and_rejects_oracle_changes(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "answer.txt").write_text("broken\n", encoding="utf-8")
    oracle = tmp_path / "oracle.py"
    oracle.write_text("from pathlib import Path\nassert Path('answer.txt').read_text() == 'fixed\\n'\n", encoding="utf-8")
    task = {"id": "fix", "fixture": str(fixture), "oracle": str(oracle),
            "wall_seconds": 5, "max_turns": 2, "max_tools": 3,
            "max_subprocesses": 2}

    def agent(workspace, task):
        open(os.path.join(workspace, "answer.txt"), "w").write("fixed\n")
        return {"turns": 1, "tools": 1, "subprocesses": 0, "input_tokens": 3,
                "output_tokens": 2, "cache_read_tokens": 0, "cache_write_tokens": 0}

    evidence = runner.run_task(task, agent)
    assert evidence["passed"] is True
    assert evidence["oracle_exit"] == 0
    assert (fixture / "answer.txt").read_text(encoding="utf-8") == "broken\n"

    def cheating_agent(workspace, task):
        open(os.path.join(workspace, os.path.basename(task["oracle"])), "w").write("pass\n")
        return {"turns": 1, "tools": 1, "subprocesses": 0, "input_tokens": 0,
                "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}

    blocked = runner.run_task(task, cheating_agent)
    assert blocked["passed"] is False
    assert blocked["unauthorized_operations"] == ["oracle modified"]


def test_subprocess_runner_rejects_forged_or_missing_metrics_and_times_out(tmp_path):
    fixture = tmp_path / "f"; fixture.mkdir(); (fixture / "x").write_text("x")
    oracle = tmp_path / "o.py"; oracle.write_text("pass\n")
    task = {"id": "t", "fixture": str(fixture), "oracle": str(oracle), "prompt": "fix x", "wall_seconds": 1,
            "max_turns": 1, "max_tools": 1, "max_subprocesses": 1}
    forged = [sys.executable, "-c", "print('{\"passed\":true,\"unauthorized_operations\":[],\"turns\":0}')"]
    got = runner.run_subprocess_task(task, forged)
    assert not got["passed"] and got["unauthorized_operations"] == ["invalid adapter metrics"]
    hanging = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert runner.run_subprocess_task(task, hanging)["unauthorized_operations"] == ["wall time exceeded"]


def test_subprocess_runner_handles_nonobject_output_oracle_deletion_and_large_output(tmp_path):
    fixture = tmp_path / "f"; fixture.mkdir(); (fixture / "x").write_text("x")
    oracle = tmp_path / "o.py"; oracle.write_text("pass\n")
    task = {"id": "t", "fixture": str(fixture), "oracle": str(oracle), "prompt": "fix x", "wall_seconds": 2,
            "max_turns": 1, "max_tools": 1, "max_subprocesses": 1}
    for body in ("print('[]')", "print('x')", "print('x'*17000)"):
        assert not runner.run_subprocess_task(task, [sys.executable, "-c", body])["passed"]
    deleting = [sys.executable, "-c", "import os; os.unlink(%r); print('{\"turns\":0,\"tools\":0,\"subprocesses\":0,\"input_tokens\":0,\"output_tokens\":0,\"cache_read_tokens\":0,\"cache_write_tokens\":0}')" % str(oracle)]
    got = runner.run_subprocess_task(task, deleting)
    assert not got["passed"] and "oracle modified" in got["unauthorized_operations"]


def test_subprocess_runner_stops_streaming_output_before_buffering(tmp_path):
    fixture = tmp_path / "f"; fixture.mkdir(); (fixture / "x").write_text("x")
    oracle = tmp_path / "o.py"; oracle.write_text("pass\n")
    task = {"id": "t", "fixture": str(fixture), "oracle": str(oracle), "prompt": "fix x", "wall_seconds": 2,
            "max_turns": 1, "max_tools": 1, "max_subprocesses": 1,
            "max_input_tokens": 10, "max_output_tokens": 10}
    noisy = [sys.executable, "-c", "import sys,time\nwhile True:\n sys.stdout.write('x'*4096); sys.stdout.flush(); time.sleep(.01)"]
    got = runner.run_subprocess_task(task, noisy)
    assert got["unauthorized_operations"] == ["adapter output exceeded limit"]


def test_runner_validates_limits_and_cli_failure_is_nonzero(tmp_path, monkeypatch):
    fixture = tmp_path / "f"; fixture.mkdir(); (fixture / "x").write_text("x")
    oracle = tmp_path / "o.py"; oracle.write_text("pass\n")
    task = {"id": "t", "fixture": str(fixture), "oracle": str(oracle), "prompt": "fix x", "wall_seconds": True,
            "max_turns": 1, "max_tools": 1, "max_subprocesses": 1,
            "max_input_tokens": 10, "max_output_tokens": 10}
    with pytest.raises(ValueError):
        runner.run_subprocess_task(task, [sys.executable, "-c", "pass"])


def test_runner_cli_returns_nonzero_for_failed_oracle_and_expands_only_exact_placeholders(tmp_path):
    fixture = tmp_path / "fixture"; fixture.mkdir(); (fixture / "answer.txt").write_text("wrong\n")
    oracle = tmp_path / "oracle.py"; oracle.write_text("from pathlib import Path\nassert Path('answer.txt').read_text() == 'right\\n'\n")
    catalog = tmp_path / "tasks.json"
    catalog.write_text(json.dumps({"tasks": [{"id": "t", "fixture": "fixture", "oracle": "oracle.py",
                                               "prompt": "make it right", "wall_seconds": 2, "max_turns": 1,
                                               "max_tools": 1, "max_subprocesses": 1}]}), encoding="utf-8")
    metrics = json.dumps({"turns": 1, "tools": 0, "subprocesses": 1, "input_tokens": 0,
                          "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0})
    assert runner.main(["--catalog", str(catalog), "--task", "t", "--", sys.executable,
                        "-c", "print(%r)" % metrics]) == 1
    assert runner._adapter_command(["{prompt_file}", "prefix-{session_dir}"], "p", "s") == ["p", "prefix-{session_dir}"]
