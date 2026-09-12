import importlib.util
import json
import os
import sys
import time


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
        return {"turns": 1, "tools": 1, "subprocesses": 0, "input_tokens": 3, "output_tokens": 2}

    evidence = runner.run_task(task, agent)
    assert evidence["passed"] is True
    assert evidence["oracle_exit"] == 0
    assert (fixture / "answer.txt").read_text(encoding="utf-8") == "broken\n"

    def cheating_agent(workspace, task):
        open(os.path.join(workspace, os.path.basename(task["oracle"])), "w").write("pass\n")
        return {"turns": 1, "tools": 1, "subprocesses": 0}

    blocked = runner.run_task(task, cheating_agent)
    assert blocked["passed"] is False
    assert blocked["unauthorized_operations"] == ["oracle modified"]


def test_subprocess_runner_rejects_forged_or_missing_metrics_and_times_out(tmp_path):
    fixture = tmp_path / "f"; fixture.mkdir(); (fixture / "x").write_text("x")
    oracle = tmp_path / "o.py"; oracle.write_text("pass\n")
    task = {"id": "t", "fixture": str(fixture), "oracle": str(oracle), "wall_seconds": 1,
            "max_turns": 1, "max_tools": 1, "max_subprocesses": 1}
    forged = [sys.executable, "-c", "print('{\"passed\":true,\"unauthorized_operations\":[],\"turns\":0}')"]
    got = runner.run_subprocess_task(task, forged)
    assert not got["passed"] and got["unauthorized_operations"] == ["invalid adapter metrics"]
    hanging = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert runner.run_subprocess_task(task, hanging)["unauthorized_operations"] == ["wall time exceeded"]


def test_subprocess_runner_handles_nonobject_output_oracle_deletion_and_large_output(tmp_path):
    fixture = tmp_path / "f"; fixture.mkdir(); (fixture / "x").write_text("x")
    oracle = tmp_path / "o.py"; oracle.write_text("pass\n")
    task = {"id": "t", "fixture": str(fixture), "oracle": str(oracle), "wall_seconds": 2,
            "max_turns": 1, "max_tools": 1, "max_subprocesses": 1}
    for body in ("print('[]')", "print('x')", "print('x'*17000)"):
        assert not runner.run_subprocess_task(task, [sys.executable, "-c", body])["passed"]
    deleting = [sys.executable, "-c", "import os; os.unlink(%r); print('{\"turns\":0,\"tools\":0,\"subprocesses\":0,\"input_tokens\":0,\"output_tokens\":0}')" % str(oracle)]
    got = runner.run_subprocess_task(task, deleting)
    assert not got["passed"] and "oracle modified" in got["unauthorized_operations"]
