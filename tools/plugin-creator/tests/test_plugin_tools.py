"""Isolated regression tests. Never installs plugins or touches real marketplaces."""
# ruff: noqa: E402 -- CLI helpers are imported after adding their sibling directory.

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from create_basic_plugin import build_plugin_json
from json_io import local_source_path, marketplace_root
from update_plugin_cachebuster import default_cachebuster, with_cachebuster
from validate_plugin import validate_plugin


class PluginToolsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="plugin-creator-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.parent = self.root / "custom bundles"
        self.plugin = self.parent / "demo"
        self.marketplace = self.root / ".agents" / "plugins" / "marketplace.json"

    def run_tool(self, name, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *map(str, args)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def scaffold(self, *args, expected=0):
        return self.run_tool(
            "create_basic_plugin.py",
            "demo",
            "--path",
            self.parent,
            *args,
            expected=expected,
        )

    def write(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def manifest_path(self):
        return self.plugin / ".codex-plugin" / "plugin.json"

    def minimal(self, **components):
        self.write(self.manifest_path, {"name": "demo", **components})

    def skill(self, name="demo-skill", **frontmatter):
        import yaml

        path = self.plugin / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": name,
            "description": "Summarize a document when asked for a summary.",
            **frontmatter,
        }
        path.write_text(
            "---\n"
            + yaml.safe_dump(payload)
            + "---\n\nSummarize the supplied document.\n",
            encoding="utf-8",
        )
        return path

    def test_minimal_default_has_no_dangling_components(self):
        self.scaffold()
        self.assertNotIn("skills", self.read(self.manifest_path))
        self.assertEqual(validate_plugin(self.plugin), [])
        self.assertEqual(validate_plugin(self.plugin, profile="catalog"), [])

    def test_full_scaffold_and_actual_marketplace_path(self):
        self.scaffold(
            "--with-skills",
            "--with-hooks",
            "--with-mcp",
            "--with-apps",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
        )
        self.assertEqual(validate_plugin(self.plugin, profile="catalog"), [])
        entry = self.read(self.marketplace)["plugins"][0]
        self.assertEqual(entry["source"]["path"], "./custom bundles/demo")
        self.assertEqual(self.read(self.plugin / "hooks" / "hooks.json"), {"hooks": {}})
        self.assertEqual(
            self.read(self.manifest_path)["interface"]["defaultPrompt"],
            ["Help me use Demo."],
        )

    def test_marketplace_roots_for_personal_repo_legacy_and_direct(self):
        self.assertEqual(marketplace_root(self.marketplace), self.root)
        self.assertEqual(
            marketplace_root(self.root / ".claude-plugin" / "marketplace.json"),
            self.root,
        )
        self.assertEqual(marketplace_root(self.root / "marketplace.json"), self.root)
        home = Path.home().resolve()
        personal = home / ".agents/plugins/marketplace.json"
        self.assertEqual(
            local_source_path(home / ".codex/plugins/demo", personal),
            "./.codex/plugins/demo",
        )

    def test_outside_marketplace_fails_before_creating_plugin(self):
        result = self.scaffold(
            "--with-marketplace",
            "--marketplace-path",
            self.root / "other" / "marketplace.json",
            expected=1,
        )
        self.assertIn("must be inside marketplace root", result.stderr)
        self.assertFalse(self.plugin.exists())

    def test_force_preserves_all_existing_configuration_and_order(self):
        self.scaffold(
            "--with-mcp",
            "--with-apps",
            "--with-hooks",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
        )
        manifest = self.read(self.manifest_path)
        manifest.update(
            {
                "version": "3.2.1",
                "description": "My real description",
                "privateExtension": {"keep": True},
            }
        )
        self.write(self.manifest_path, manifest)
        companions = {
            ".mcp.json": {"mcpServers": {"real": {"command": "local-tool"}}},
            ".app.json": {"apps": {"real": {"id": "registered-test-id"}}},
            "hooks/hooks.json": {"hooks": {"SessionStart": []}},
        }
        for path, data in companions.items():
            self.write(self.plugin / path, data)
        catalog = self.read(self.marketplace)
        catalog["interface"]["displayName"] = "Custom marketplace"
        entry = catalog["plugins"][0]
        entry["policy"].update(
            {
                "installation": "NOT_AVAILABLE",
                "authentication": "ON_USE",
                "products": ["codex"],
            }
        )
        entry["extra"] = {"retained": True}
        catalog["plugins"].append(
            {
                "name": "unrelated",
                "source": {
                    "source": "git-subdir",
                    "url": "https://example.com/repo.git",
                    "path": "./plugin",
                    "sha": "abc",
                },
            }
        )
        self.write(self.marketplace, catalog)
        self.scaffold(
            "--force",
            "--with-skills",
            "--with-mcp",
            "--with-apps",
            "--with-hooks",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
        )
        expected = {**manifest, "skills": "./skills/"}
        self.assertEqual(self.read(self.manifest_path), expected)
        self.assertEqual(self.read(self.marketplace), catalog)
        for path, data in companions.items():
            self.assertEqual(self.read(self.plugin / path), data)

    def test_marketplace_explicit_policy_only_updates_requested_value(self):
        self.scaffold("--with-marketplace", "--marketplace-path", self.marketplace)
        catalog = self.read(self.marketplace)
        catalog["plugins"][0]["policy"].update(
            {"products": ["codex"], "authentication": "ON_USE"}
        )
        self.write(self.marketplace, catalog)
        self.scaffold(
            "--marketplace-only",
            "--force",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
            "--install-policy",
            "NOT_AVAILABLE",
        )
        policy = self.read(self.marketplace)["plugins"][0]["policy"]
        self.assertEqual(
            policy,
            {
                "installation": "NOT_AVAILABLE",
                "authentication": "ON_USE",
                "products": ["codex"],
            },
        )

    def test_marketplace_only_keeps_existing_plugin_byte_for_byte(self):
        self.minimal(version="1.2.3")
        before = self.manifest_path.read_bytes()
        self.scaffold(
            "--marketplace-only",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
        )
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertFalse((self.plugin / "skills").exists())

    def test_existing_plugin_identifier_is_not_renormalized(self):
        existing = self.parent / "my_plugin.v2"
        self.write(existing / ".codex-plugin/plugin.json", {"name": "my_plugin.v2"})
        self.run_tool(
            "create_basic_plugin.py",
            "my_plugin.v2",
            "--path",
            self.parent,
            "--marketplace-only",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
        )
        self.assertEqual(
            self.read(self.marketplace)["plugins"][0]["name"], "my_plugin.v2"
        )

    def test_force_preserves_plain_string_source(self):
        self.minimal()
        self.write(
            self.marketplace,
            {
                "name": "personal",
                "plugins": [{"name": "demo", "source": "./custom bundles/demo"}],
            },
        )
        self.scaffold(
            "--marketplace-only",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
            "--force",
        )
        self.assertEqual(
            self.read(self.marketplace)["plugins"][0]["source"], "./custom bundles/demo"
        )

    def test_existing_source_mismatch_fails_before_mutation_even_force(self):
        self.minimal()
        self.write(
            self.marketplace,
            {
                "name": "personal",
                "plugins": [
                    {
                        "name": "demo",
                        "source": {
                            "source": "url",
                            "url": "https://example.com/source.git",
                        },
                    }
                ],
            },
        )
        before = self.marketplace.read_bytes(), self.manifest_path.read_bytes()
        self.scaffold(
            "--force",
            "--with-skills",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
            expected=1,
        )
        self.assertEqual(
            before, (self.marketplace.read_bytes(), self.manifest_path.read_bytes())
        )
        self.assertFalse((self.plugin / "skills").exists())

    def test_duplicate_entry_fails_before_creating_plugin(self):
        self.write(
            self.marketplace,
            {"name": "personal", "plugins": [{"name": "demo"}, {"name": "demo"}]},
        )
        self.scaffold(
            "--force",
            "--with-marketplace",
            "--marketplace-path",
            self.marketplace,
            expected=1,
        )
        self.assertFalse(self.plugin.exists())

    def test_invalid_marketplace_does_not_create_partial_scaffold(self):
        self.write(self.marketplace, {"name": "invalid name", "plugins": []})
        self.scaffold(
            "--with-marketplace", "--marketplace-path", self.marketplace, expected=1
        )
        self.assertFalse(self.plugin.exists())

    def test_companion_conflict_leaves_existing_manifest_untouched(self):
        self.minimal(description="Keep this")
        before = self.manifest_path.read_bytes()
        (self.plugin / ".mcp.json").mkdir()
        self.scaffold("--force", "--with-skills", "--with-mcp", expected=1)
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertFalse((self.plugin / "skills").exists())

    def test_scaffold_refuses_symlinked_manifest_directory(self):
        self.plugin.mkdir(parents=True)
        outside = self.root / "outside-manifests"
        outside.mkdir()
        (self.plugin / ".codex-plugin").symlink_to(outside, target_is_directory=True)
        self.scaffold(expected=1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_local_minimal_manifest_does_not_require_catalog_metadata(self):
        self.minimal()
        self.assertEqual(validate_plugin(self.plugin), [])
        self.assertTrue(validate_plugin(self.plugin, profile="catalog"))

    def test_missing_declared_component_is_rejected(self):
        for field, path in [
            ("skills", "./skills/"),
            ("apps", "./.app.json"),
            ("mcpServers", "./.mcp.json"),
            ("hooks", "./hooks/hooks.json"),
        ]:
            with self.subTest(field=field):
                self.minimal(**{field: path})
                self.assertTrue(validate_plugin(self.plugin))

    def test_invalid_utf8_reports_error_instead_of_crashing(self):
        self.minimal()
        self.manifest_path.write_bytes(b"\xff")
        self.assertTrue(validate_plugin(self.plugin))

    def test_component_paths_reject_escape_and_missing_prefix(self):
        for value in ["skills", "../skills", "./../skills", "/tmp/skills", ".\\skills"]:
            with self.subTest(value=value):
                self.minimal(skills=value)
                self.assertTrue(validate_plugin(self.plugin))

    def test_component_symlink_cannot_escape(self):
        self.minimal(skills="./skills/")
        outside = self.root / "outside"
        outside.mkdir()
        (self.plugin / "skills").symlink_to(outside, target_is_directory=True)
        self.assertTrue(validate_plugin(self.plugin))

    def test_custom_skill_path_and_policy_only_agent_yaml(self):
        self.minimal(skills="./workflows/")
        skill = self.skill()
        (self.plugin / "skills").rename(self.plugin / "workflows")
        agent = self.plugin / "workflows" / skill.parent.name / "agents" / "openai.yaml"
        agent.parent.mkdir()
        agent.write_text(
            "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
        )
        self.assertEqual(validate_plugin(self.plugin), [])

    def test_agent_skills_name_description_and_metadata_constraints(self):
        self.minimal()
        for value in ["Uppercase", "double--hyphen", "different", "a" * 65]:
            with self.subTest(name=value):
                self.skill(**{"name": "demo-skill"})
                path = self.plugin / "skills/demo-skill/SKILL.md"
                path.write_text(
                    f"---\nname: {value}\ndescription: Read a file\n---\nRead it.\n",
                    encoding="utf-8",
                )
                self.assertTrue(validate_plugin(self.plugin))
        self.skill(description="x" * 1025)
        self.assertTrue(validate_plugin(self.plugin))
        self.skill(
            metadata={"version": "1.0"},
            compatibility="Requires Python",
            **{"allowed-tools": "Read"},
        )
        self.assertEqual(validate_plugin(self.plugin), [])

    def test_all_mcp_companion_map_forms(self):
        server = {"docs": {"command": "docs-mcp", "args": ["--stdio"]}}
        for payload in [server, {"mcpServers": server}]:
            with self.subTest(payload=payload):
                self.minimal(mcpServers="./config/server.json")
                self.write(self.plugin / "config/server.json", payload)
                self.assertEqual(validate_plugin(self.plugin), [])
        self.write(
            self.plugin / "config/server.json", {"mcpServers": {}, "mcp_servers": {}}
        )
        self.assertTrue(validate_plugin(self.plugin))

    def test_snake_case_is_not_a_native_mcp_wrapper(self):
        self.minimal(mcpServers="./config/server.json")
        path = self.plugin / "config/server.json"
        self.write(path, {"mcp_servers": {"docs": {"command": "docs-mcp"}}})
        self.assertTrue(any("does not support" in error for error in validate_plugin(self.plugin)))
        # A direct server can still have this literal name.
        self.write(path, {"mcp_servers": {"command": "docs-mcp"}})
        self.assertEqual(validate_plugin(self.plugin), [])

    def test_native_mcp_relative_cwd_and_optional_args(self):
        self.minimal(mcpServers="./config/server.json")
        self.write(self.plugin / "config/server.json", {
            "mcpServers": {"docs": {"command": "bash", "args": ["scripts/server.sh"], "cwd": "."},
                           "without-args": {"command": "docs-mcp"}}
        })
        self.assertEqual(validate_plugin(self.plugin), [])

    def test_hooks_paths_inline_arrays_and_default_discovery(self):
        hooks = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ${PLUGIN_ROOT}/hook.py",
                            }
                        ]
                    }
                ]
            }
        }
        self.write(self.plugin / "hooks/hooks.json", hooks)
        for value in ["./hooks/hooks.json", ["./hooks/hooks.json"], hooks, [hooks]]:
            with self.subTest(value=value):
                self.minimal(hooks=value)
                self.assertEqual(validate_plugin(self.plugin), [])
        self.minimal()
        self.assertEqual(validate_plugin(self.plugin), [])
        # Explicit hooks replace the default. An invalid unused default is ignored.
        self.write(self.plugin / "hooks/hooks.json", {"hooks": 42})
        self.minimal(hooks={"hooks": {}})
        self.assertEqual(validate_plugin(self.plugin), [])
        self.minimal()
        self.assertTrue(validate_plugin(self.plugin))

    def test_hook_malformed_groups_are_rejected(self):
        self.minimal(
            hooks={
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": ""}]}]
                }
            }
        )
        self.assertTrue(validate_plugin(self.plugin))

    def test_prompt_types_and_catalog_display_limits(self):
        for prompt in ["Try this", ["Try this"]]:
            self.minimal(interface={"defaultPrompt": prompt})
            self.assertEqual(validate_plugin(self.plugin), [])
        self.minimal(interface={"defaultPrompt": 123})
        self.assertTrue(validate_plugin(self.plugin))
        payload = build_plugin_json(
            "demo", with_mcp=False, with_apps=False, with_skills=False
        )
        payload["interface"]["defaultPrompt"] = ["x" * 129]
        self.write(self.manifest_path, payload)
        self.assertEqual(validate_plugin(self.plugin), [])
        self.assertTrue(validate_plugin(self.plugin, profile="catalog"))

    def test_cachebuster_dry_run_and_lossless_metadata(self):
        payload = {
            "name": "demo",
            "version": "1.2.3-beta.1+old.build",
            "interface": {"displayName": "Résumé"},
            "extension": {"keep": True},
        }
        self.write(self.manifest_path, payload)
        self.manifest_path.chmod(0o600)
        before = self.manifest_path.read_bytes()
        self.run_tool(
            "update_plugin_cachebuster.py",
            self.plugin,
            "--cachebuster",
            "New Token",
            "--dry-run",
        )
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.run_tool(
            "update_plugin_cachebuster.py", self.plugin, "--cachebuster", "New Token"
        )
        self.assertEqual(
            self.read(self.manifest_path),
            {**payload, "version": "1.2.3-beta.1+codex.new-token"},
        )
        self.run_tool(
            "update_plugin_cachebuster.py", self.plugin, "--cachebuster", "next"
        )
        self.assertEqual(
            self.read(self.manifest_path)["version"], "1.2.3-beta.1+codex.next"
        )
        self.assertEqual(self.manifest_path.stat().st_mode & 0o777, 0o600)

    def test_cachebuster_invalid_inputs_leave_manifest_untouched(self):
        self.minimal(version="1.2.3")
        for token in ["", "!!!"]:
            before = self.manifest_path.read_bytes()
            self.run_tool(
                "update_plugin_cachebuster.py",
                self.plugin,
                "--cachebuster",
                token,
                expected=1,
            )
            self.assertEqual(self.manifest_path.read_bytes(), before)
        self.minimal(version="dev-build")
        self.run_tool("update_plugin_cachebuster.py", self.plugin, expected=1)
        self.run_tool(
            "update_plugin_cachebuster.py",
            self.plugin,
            "--allow-non-semver",
            "--cachebuster",
            "legacy",
        )
        self.assertEqual(
            self.read(self.manifest_path)["version"], "dev-build+codex.legacy"
        )

    def test_cachebuster_default_and_prefix_compatibility(self):
        self.assertRegex(default_cachebuster(), r"^\d{20}$")
        self.assertEqual(
            with_cachebuster("1.2.3-rc.1+codex.old", "new"), "1.2.3-rc.1+codex.new"
        )

    def test_cachebuster_refuses_symlink_manifest(self):
        self.minimal(version="1.0.0")
        outside = self.root / "source.json"
        self.manifest_path.rename(outside)
        self.manifest_path.symlink_to(outside)
        before = outside.read_bytes()
        self.run_tool("update_plugin_cachebuster.py", self.plugin, expected=1)
        self.assertEqual(outside.read_bytes(), before)

    def test_read_marketplace_name_can_verify_local_source(self):
        self.scaffold("--with-marketplace", "--marketplace-path", self.marketplace)
        result = self.run_tool(
            "read_marketplace_name.py",
            "--marketplace-path",
            self.marketplace,
            "--plugin-path",
            self.plugin,
        )
        self.assertEqual(result.stdout.strip(), "personal")
        payload = self.read(self.marketplace)
        payload["plugins"][0]["source"]["path"] = "./elsewhere"
        self.write(self.marketplace, payload)
        self.run_tool(
            "read_marketplace_name.py",
            "--marketplace-path",
            self.marketplace,
            "--plugin-path",
            self.plugin,
            expected=1,
        )


if __name__ == "__main__":
    unittest.main()
