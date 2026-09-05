"""Portable generation runs offline and never overwrites hand-written output."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "portable_generate", Path(__file__).parents[1] / "scripts/generate.py"
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def tree():
    return {
        "cli": {"name": "demo", "binary": "/private/author/bin/demo"},
        "groups": [{"name": "list", "path": ["list"], "summary": "List entries"}],
    }


def test_generates_both_manifests_and_removes_machine_path(tmp_path):
    output = tmp_path / "bundle"
    assert generator.generate(tree(), output) == ["demo-list"]
    native = json.loads((output / ".codex-plugin/plugin.json").read_text())
    legacy = json.loads((output / ".claude-plugin/plugin.json").read_text())
    assert native["name"] == legacy["name"] == "demo"
    assert native["skills"] == "./skills/"
    assert "binary" not in json.loads((output / "references/help-tree.json").read_text())["cli"]
    assert (output / "skills/demo-list/references/help.json").is_file()


def test_existing_output_is_untouched(tmp_path):
    output = tmp_path / "bundle"
    output.mkdir()
    sentinel = output / "handwritten.md"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        generator.generate(tree(), output)
    assert sentinel.read_text() == "keep"
    assert list(output.iterdir()) == [sentinel]


@pytest.mark.parametrize("path", [[".."], ["x;touch pwned"], ["/outside"], ["x/y"], []])
def test_unsafe_group_tokens_fail_before_output(tmp_path, path):
    payload = tree()
    payload["groups"][0]["path"] = path
    with pytest.raises(ValueError):
        generator.generate(payload, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_normalization_collision_rejected(tmp_path):
    payload = tree()
    payload["groups"] = [{"name": "a_b", "path": ["a_b"]}, {"name": "a-b", "path": ["a-b"]}]
    with pytest.raises(ValueError, match="Duplicate"):
        generator.generate(payload, tmp_path / "out")


def test_unknown_selection_rejected(tmp_path):
    with pytest.raises(ValueError, match="absent"):
        generator.generate(tree(), tmp_path / "out", ["unknown"])


def test_cli_selects_group_and_reports_output(tmp_path, monkeypatch, capsys):
    payload = tree()
    payload["groups"].append({"name": "show", "path": ["show"]})
    source = tmp_path / "help.json"
    source.write_text(json.dumps(payload))
    output = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv", ["generate", "--tree", str(source), "--out", str(output), "--group", "show"]
    )
    generator.main()
    assert (output / "skills/demo-show/SKILL.md").is_file()
    assert not (output / "skills/demo-list").exists()
    assert "Generated 1 portable skills" in capsys.readouterr().out


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"cli": {}, "groups": []},
        {"cli": {"name": "!!!"}, "groups": []},
        {"cli": {"name": "demo"}, "groups": []},
        {"cli": {"name": "demo"}, "groups": [{"name": []}]},
    ],
)
def test_cli_bad_tree_reports_failure_without_partial_output(
    tmp_path, monkeypatch, capsys, payload
):
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(payload))
    output = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["generate", "--tree", str(source), "--out", str(output)])
    with pytest.raises(SystemExit) as error:
        generator.main()
    assert error.value.code == 1
    assert "generation failed:" in capsys.readouterr().err
    assert not output.exists()
