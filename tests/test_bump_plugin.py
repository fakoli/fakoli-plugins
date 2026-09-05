"""Isolated release-helper tests; all generator, validator, and Git calls are fakes.

Run: python3 -m unittest discover -s tests -p 'test_bump_plugin.py' -v
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parents[1]
GENERATED = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "registry/index.json",
    "registry/categories.json",
    "registry/tags.json",
)
FAKE_COMMAND = r"""
import json, os, pathlib, sys
root = pathlib.Path.cwd()
kind = pathlib.Path(sys.argv[0]).name
control = json.loads((root / "controls.json").read_text())
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps({"kind": kind, "argv": sys.argv[1:], "cwd": str(root),
                             "index": os.environ.get("GIT_INDEX_FILE")}) + "\n")
if kind == "generate-index.sh":
    for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json",
                     "registry/index.json", "registry/categories.json", "registry/tags.json"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"generated": True}))
elif kind == "git":
    real = root / ".git/index"
    if sys.argv[1] == "rev-parse":
        print(os.environ.get("GIT_INDEX_FILE", str(real)))
    elif sys.argv[1] == "add":
        target = pathlib.Path(os.environ["GIT_INDEX_FILE"])
        assert target != real, "real index must never be passed to git add"
        data = target.read_bytes() if target.exists() else b""
        target.write_bytes(data + b"\nSTAGED")
        if control.get("concurrent_index"):
            real.write_bytes(b"CONCURRENT USER STAGING")
    else:
        sys.exit("unexpected Git mutation")
if kind == control.get("fail"):
    print("fixture failure: " + kind, file=sys.stderr)
    sys.exit(7)
"""


class BumpPluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bump-plugin-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.plugin = self.root / "plugins/demo-plugin"
        (self.root / "scripts").mkdir()
        for name in ("bump-plugin.sh", "bump_plugin.py"):
            shutil.copy2(REPO / "scripts" / name, self.root / "scripts" / name)
        for name in ("generate-index.sh", "check-registry-drift.sh", "validate.sh", "git"):
            path = self.root / "scripts" / name
            path.write_text(f"#!{sys.executable}\n" + FAKE_COMMAND)
            path.chmod(0o755)
        self.write("controls.json", "{}")
        for host in ("claude", "codex", "cursor"):
            self.write_manifest(host, "1.2.3")
        for index, name in enumerate(GENERATED):
            self.write(name, json.dumps({"original": index}) + "\n")
        self.write(".git/index", "PREEXISTING STAGED CHANGES")
        self.write("plugins/demo-plugin/README.md", "user changes already here\n")
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith("GIT_"):
                self.env.pop(key)
        self.env["PATH"] = str(self.root / "scripts") + os.pathsep + self.env["PATH"]

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def write_manifest(self, host, version, name="demo-plugin"):
        return self.write(
            f"plugins/demo-plugin/.{host}-plugin/plugin.json",
            json.dumps(
                {
                    "name": name,
                    "nested": {"version": version},
                    "version": version,
                    "description": "Preserve me",
                },
                indent=4,
            )
            + "\n",
        )

    def project(self, relative="bin", name="demo-plugin", version="1.2.3"):
        prefix = "plugins/demo-plugin" + ("/" + relative if relative else "")
        self.write(
            prefix + "/pyproject.toml",
            f"# Keep this comment\n[project]\nname = {name!r}\nversion = '{version}' # release\n"
            "dependencies = ['dependency==1.2.3']\n[tool.example]\nversion = '9.8.7'\n",
        )
        self.write(
            prefix + "/uv.lock",
            f'version = 1\n\n[[package]]\nname = "{name}"\nversion = "{version}"\n'
            'source = { editable = "." }\n[package.metadata]\nrequires-dist = []\n\n'
            '[[package]]\nname = "dependency"\nversion = "1.2.3"\n'
            'source = { registry = "https://pypi.org/simple" }\n',
        )
        self.write(prefix + "/src/demo_plugin/__init__.py", f'__version__ = "{version}"\n')
        return self.root / prefix

    def run_bump(self, *args, success=True):
        result = subprocess.run(
            [str(self.root / "scripts/bump-plugin.sh"), *args],
            cwd=self.root.parent,
            env=self.env,
            text=True,
            capture_output=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def inventory(self):
        return {
            str(path.relative_to(self.root)): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for path in self.root.rglob("*")
            if path.is_file() and path.name != "calls.jsonl"
        }

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def assert_versions(self, expected):
        for host in ("claude", "codex", "cursor"):
            data = json.loads((self.plugin / f".{host}-plugin/plugin.json").read_text())
            self.assertEqual(data["version"], expected)
            self.assertEqual(data["nested"]["version"], "1.2.3")

    def test_default_stages_complete_release_without_losing_existing_index(self):
        self.project()
        self.run_bump("demo-plugin", "patch")
        self.assert_versions("1.2.4")
        self.assertEqual(
            (self.root / ".git/index").read_bytes(), b"PREEXISTING STAGED CHANGES\nSTAGED"
        )
        calls = self.calls()
        self.assertEqual(
            [c["kind"] for c in calls],
            ["generate-index.sh", "check-registry-drift.sh", "validate.sh", "git", "git"],
        )
        self.assertEqual(
            calls[-1]["argv"],
            [
                "add",
                "--",
                "plugins/demo-plugin",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                "registry",
            ],
        )
        self.assertTrue(all(c["cwd"] == str(self.root) for c in calls))
        self.assertEqual(calls[2]["argv"], ["plugins/demo-plugin"])
        self.assertFalse((self.root / ".bump-plugin.lock").exists())
        self.assertEqual(list((self.root / ".git").iterdir()), [self.root / ".git/index"])

    def test_no_stage_updates_nested_python_release_sources_only(self):
        project = self.project()
        nested = self.project("skills/generate/scripts", "demo-plugin-cli")
        independent = self.project("independent", "separate-library", "8.0.0")
        self.write("plugins/demo-plugin/VERSION", "1.2.3\n")
        ignored = self.project(".venv", "demo-plugin", "0.0.1")
        before_independent = (independent / "pyproject.toml").read_bytes()
        before_ignored = (ignored / "pyproject.toml").read_bytes()
        self.run_bump("demo-plugin", "minor", "--no-stage")
        self.assert_versions("1.3.0")
        for path in (project, nested):
            data = tomllib.loads((path / "pyproject.toml").read_text())
            self.assertEqual(data["project"]["version"], "1.3.0")
            self.assertEqual(data["tool"]["example"]["version"], "9.8.7")
            self.assertIn("# Keep this comment", (path / "pyproject.toml").read_text())
            self.assertIn("# release", (path / "pyproject.toml").read_text())
            packages = tomllib.loads((path / "uv.lock").read_text())["package"]
            self.assertEqual([p["version"] for p in packages], ["1.3.0", "1.2.3"])
            self.assertEqual(
                (path / "src/demo_plugin/__init__.py").read_text(), '__version__ = "1.3.0"\n'
            )
        self.assertEqual((self.plugin / "VERSION").read_text(), "1.3.0\n")
        self.assertEqual((independent / "pyproject.toml").read_bytes(), before_independent)
        self.assertEqual((ignored / "pyproject.toml").read_bytes(), before_ignored)
        self.assertEqual((self.root / ".git/index").read_text(), "PREEXISTING STAGED CHANGES")
        self.assertFalse(any(c["kind"] == "git" for c in self.calls()))

    def test_dry_run_preflights_but_changes_nothing_and_runs_no_commands(self):
        self.project()
        before = self.inventory()
        result = self.run_bump("demo-plugin", "patch", "--dry-run", "--no-stage")
        self.assertIn("would edit plugins/demo-plugin/bin/uv.lock", result.stdout)
        self.assertIn("staging skipped (--no-stage)", result.stdout)
        self.assertNotIn("would stage", result.stdout)
        self.assertEqual(before, self.inventory())
        self.assertEqual(self.calls(), [])

    def test_failed_generator_drift_validation_or_git_restores_every_byte_and_mode(self):
        self.project()
        (self.plugin / ".codex-plugin/plugin.json").chmod(0o640)
        for failing in ("generate-index.sh", "check-registry-drift.sh", "validate.sh", "git"):
            with self.subTest(failing=failing):
                self.write("controls.json", json.dumps({"fail": failing}))
                before = self.inventory()
                result = self.run_bump("demo-plugin", "patch", success=False)
                self.assertIn("fixture failure", result.stderr)
                self.assertEqual(before, self.inventory())

    def test_git_add_failure_after_partial_candidate_write_preserves_real_index(self):
        # Fail only add, after the fake has written its temporary index.
        git = self.root / "scripts/git"
        git.write_text(
            git.read_text().replace(
                'kind == control.get("fail")',
                'kind == control.get("fail") and sys.argv[1] == "add"',
            )
        )
        self.write("controls.json", '{"fail": "git"}')
        before = self.inventory()
        self.run_bump("demo-plugin", "patch", success=False)
        self.assertEqual(before, self.inventory())

    def test_rollback_removes_new_generated_files_and_directories(self):
        shutil.rmtree(self.root / ".agents")
        shutil.rmtree(self.root / "registry")
        self.write("controls.json", '{"fail": "validate.sh"}')
        before = self.inventory()
        self.run_bump("demo-plugin", "patch", "--no-stage", success=False)
        self.assertEqual(before, self.inventory())
        self.assertFalse((self.root / ".agents").exists())
        self.assertFalse((self.root / "registry").exists())

    def test_preexisting_transaction_or_index_lock_is_preserved(self):
        for relative in (".bump-plugin.lock", ".git/index.lock"):
            with self.subTest(relative=relative):
                path = self.write(relative, "another operation owns this")
                before = self.inventory()
                self.run_bump("demo-plugin", "patch", success=False)
                self.assertEqual(before, self.inventory())
                path.unlink()

    def test_concurrent_staging_survives_and_release_files_roll_back(self):
        self.write("controls.json", '{"concurrent_index": true}')
        before = self.inventory()
        result = self.run_bump("demo-plugin", "patch", success=False)
        self.assertIn("changed concurrently", result.stderr)
        before[".git/index"] = (b"CONCURRENT USER STAGING", before[".git/index"][1])
        self.assertEqual(before, self.inventory())

    def test_manifest_name_and_version_drift_fail_before_any_edits(self):
        for version, name in (("0.0.1", "demo-plugin"), ("1.2.3", "other-plugin")):
            self.write_manifest("codex", version, name)
            before = self.inventory()
            self.run_bump("demo-plugin", "patch", success=False)
            self.assertEqual(before, self.inventory())
            self.assertEqual(self.calls(), [])

    def test_python_metadata_drift_fails_before_edits(self):
        project = self.project()
        for relative in ("pyproject.toml", "uv.lock", "src/demo_plugin/__init__.py"):
            with self.subTest(relative=relative):
                path = project / relative
                original = path.read_text()
                path.write_text(original.replace("1.2.3", "1.0.0", 1))
                before = self.inventory()
                self.run_bump("demo-plugin", "patch", success=False)
                self.assertEqual(before, self.inventory())
                path.write_text(original)

    def test_names_cannot_escape_plugin_root(self):
        before = self.inventory()
        for name in (
            "../demo-plugin",
            "/tmp/demo-plugin",
            ".",
            "Demo",
            "demo_plugin",
            "demo--plugin",
        ):
            self.run_bump(name, "patch", success=False)
        self.assertEqual(before, self.inventory())

    def test_symlink_manifest_metadata_and_catalog_are_rejected(self):
        project = self.project()
        for path in (
            self.plugin / ".codex-plugin/plugin.json",
            project / "pyproject.toml",
            project / "uv.lock",
            self.root / GENERATED[1],
        ):
            with self.subTest(path=path):
                external = self.write("outside", path.read_text())
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(external)
                result = self.run_bump("demo-plugin", "patch", success=False)
                self.assertIn("symlink", result.stderr)
                self.assertEqual(external.read_bytes(), original)
                path.unlink()
                path.write_bytes(original)

    def test_symlink_plugin_directory_is_rejected(self):
        moved = self.root / "outside-plugin"
        self.plugin.rename(moved)
        self.plugin.symlink_to(moved, target_is_directory=True)
        result = self.run_bump("demo-plugin", "patch", success=False)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(
            json.loads((moved / ".claude-plugin/plugin.json").read_text())["version"], "1.2.3"
        )

    def test_invalid_semver_and_downgrade_are_rejected(self):
        before = self.inventory()
        for version in ("1.2", "01.2.3", "1.2.4-01", "1.2.4+", "garbage", "1.2.2", "1.2.3-rc.1"):
            self.run_bump("demo-plugin", version, "--dry-run", success=False)
        self.assertEqual(before, self.inventory())
        self.run_bump("demo-plugin", "1.2.2", "--allow-downgrade", "--no-stage")
        self.assert_versions("1.2.2")

    def test_prerelease_build_maps_python_metadata_and_can_promote(self):
        project = self.project()
        self.run_bump("demo-plugin", "1.3.0-rc.2+BUILD.7", "--no-stage")
        self.assert_versions("1.3.0-rc.2+BUILD.7")
        self.assertEqual(
            tomllib.loads((project / "pyproject.toml").read_text())["project"]["version"],
            "1.3.0rc2+build.7",
        )
        self.assertEqual(
            tomllib.loads((project / "uv.lock").read_text())["package"][0]["version"],
            "1.3.0rc2+build.7",
        )
        self.run_bump("demo-plugin", "1.3.0", "--no-stage")
        self.assert_versions("1.3.0")

    def test_prerelease_ordering_is_numeric_and_final_release_is_later(self):
        self.run_bump("demo-plugin", "1.3.0-rc.2", "--no-stage")
        self.run_bump("demo-plugin", "1.3.0-rc.10", "--no-stage")
        self.run_bump("demo-plugin", "1.3.0-rc.3", "--no-stage", success=False)
        self.run_bump("demo-plugin", "1.3.0", "--no-stage")
        self.assert_versions("1.3.0")

    def test_non_python_semver_labels_are_valid_but_not_for_python_projects(self):
        self.run_bump("demo-plugin", "1.3.0-preview.feature", "--dry-run")
        self.project()
        before = self.inventory()
        result = self.run_bump("demo-plugin", "1.3.0-preview.feature", success=False)
        self.assertIn("cannot map to Python", result.stderr)
        self.assertEqual(before, self.inventory())

    def test_same_version_is_true_noop(self):
        before = self.inventory()
        self.run_bump("demo-plugin", "1.2.3")
        self.assertEqual(before, self.inventory())
        self.assertEqual(self.calls(), [])

    def test_absent_index_is_initialized_only_after_success(self):
        (self.root / ".git/index").unlink()
        self.run_bump("demo-plugin", "patch")
        self.assertEqual((self.root / ".git/index").read_bytes(), b"\nSTAGED")

    def test_explicit_index_is_honored_without_changing_default_index(self):
        explicit = self.write(".git/custom-index", "CUSTOM INDEX")
        self.env["GIT_INDEX_FILE"] = str(explicit)
        self.run_bump("demo-plugin", "patch")
        self.assertEqual(explicit.read_bytes(), b"CUSTOM INDEX\nSTAGED")
        self.assertEqual((self.root / ".git/index").read_bytes(), b"PREEXISTING STAGED CHANGES")

    def test_native_validator_failure_rolls_back_before_staging(self):
        self.write("scripts/validate.py", "# host validator exists\n")
        uv = self.write("scripts/uv", f"#!{sys.executable}\n" + FAKE_COMMAND)
        uv.chmod(0o755)
        self.write("controls.json", '{"fail": "uv"}')
        before = self.inventory()
        result = self.run_bump("demo-plugin", "patch", success=False)
        self.assertIn("uv failed", result.stderr)
        self.assertEqual(before, self.inventory())
        self.assertEqual(
            self.calls()[-1]["argv"],
            ["run", "--script", "scripts/validate.py", "plugins/demo-plugin"],
        )
        self.assertFalse(any(c["kind"] == "git" for c in self.calls()))

    def test_root_version_file_stays_semver_while_python_prerelease_is_pep440(self):
        self.project("")
        self.write("plugins/demo-plugin/VERSION", "1.2.3\n")
        self.run_bump("demo-plugin", "1.3.0-rc.1", "--no-stage")
        self.assertEqual((self.plugin / "VERSION").read_text(), "1.3.0-rc.1\n")
        self.assertEqual(
            tomllib.loads((self.plugin / "pyproject.toml").read_text())["project"]["version"],
            "1.3.0rc1",
        )
        self.run_bump("demo-plugin", "1.3.0", "--no-stage")
        self.assertEqual((self.plugin / "VERSION").read_text(), "1.3.0\n")

    def test_manifest_formatting_survives_and_only_top_level_version_changes(self):
        path = self.plugin / ".claude-plugin/plugin.json"
        source = path.read_text()
        self.run_bump("demo-plugin", "patch", "--no-stage")
        expected = source.replace('\n    "version": "1.2.3"', '\n    "version": "1.2.4"')
        self.assertEqual(path.read_text(), expected)


if __name__ == "__main__":
    unittest.main()
