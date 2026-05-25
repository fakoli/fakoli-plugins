"""
test_override_merge.py — Tests for override.py's merge_override function.

Covers:
- skip group
- rename description (override summary)
- append extra_guidance
- pre-specify meta_skills
- halt on unknown group with suggestion
- warn on unknown command
- skip command within a group
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import override.py as a module
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_OVERRIDE_PATH = _SCRIPTS_DIR / "override.py"

spec = importlib.util.spec_from_file_location("override", _OVERRIDE_PATH)
override_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(override_mod)

merge_override = override_mod.merge_override
OverrideError = override_mod.OverrideError


# ---------------------------------------------------------------------------
# Shared test tree
# ---------------------------------------------------------------------------

def make_tree() -> dict:
    """Return a minimal help-tree dict for testing."""
    return {
        "cli": {"name": "mycli", "binary": "/usr/local/bin/mycli"},
        "groups": [
            {
                "name": "pr",
                "path": ["pr"],
                "summary": "Manage pull requests",
                "commands": [
                    {"name": "list", "path": ["pr", "list"], "summary": "List PRs"},
                    {"name": "create", "path": ["pr", "create"], "summary": "Create a PR"},
                    {"name": "view", "path": ["pr", "view"], "summary": "View a PR"},
                ],
            },
            {
                "name": "issue",
                "path": ["issue"],
                "summary": "Manage issues",
                "commands": [
                    {"name": "list", "path": ["issue", "list"], "summary": "List issues"},
                    {"name": "create", "path": ["issue", "create"], "summary": "Create an issue"},
                ],
            },
            {
                "name": "repo",
                "path": ["repo"],
                "summary": "Work with repositories",
                "commands": [
                    {"name": "clone", "path": ["repo", "clone"], "summary": "Clone a repo"},
                ],
            },
        ],
        "discovery": {
            "depth_reached": 2,
            "commands_walked": 10,
            "elapsed_ms": 0,
            "warnings": [],
        },
    }


# ===========================================================================
# No-op / identity
# ===========================================================================

class TestNoOp:
    def test_empty_override_returns_equivalent_tree(self):
        tree = make_tree()
        result = merge_override(tree, {})
        assert result["groups"] == tree["groups"]
        assert result["cli"] == tree["cli"]

    def test_none_override_returns_equivalent_tree(self):
        tree = make_tree()
        result = merge_override(tree, None)
        assert result["groups"] == tree["groups"]

    def test_does_not_mutate_original_tree(self):
        tree = make_tree()
        original_groups_count = len(tree["groups"])
        merge_override(tree, {"groups": [{"name": "pr", "skip": True}]})
        # Original must be unchanged
        assert len(tree["groups"]) == original_groups_count


# ===========================================================================
# Skip group
# ===========================================================================

class TestSkipGroup:
    def test_skip_removes_group_from_result(self):
        tree = make_tree()
        result = merge_override(tree, {"groups": [{"name": "pr", "skip": True}]})
        names = [g["name"] for g in result["groups"]]
        assert "pr" not in names

    def test_skip_leaves_other_groups_intact(self):
        tree = make_tree()
        result = merge_override(tree, {"groups": [{"name": "pr", "skip": True}]})
        names = [g["name"] for g in result["groups"]]
        assert "issue" in names
        assert "repo" in names

    def test_skip_multiple_groups(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [
                {"name": "pr", "skip": True},
                {"name": "issue", "skip": True},
            ]
        })
        names = [g["name"] for g in result["groups"]]
        assert "pr" not in names
        assert "issue" not in names
        assert "repo" in names


# ===========================================================================
# Rename description (overrides summary)
# ===========================================================================

class TestRenameDescription:
    def test_description_overrides_summary(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{"name": "pr", "description": "All things pull request"}]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        assert pr_group["summary"] == "All things pull request"

    def test_description_does_not_affect_other_groups(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{"name": "pr", "description": "New description"}]
        })
        issue_group = next(g for g in result["groups"] if g["name"] == "issue")
        assert issue_group["summary"] == "Manage issues"

    def test_description_without_existing_summary(self):
        tree = make_tree()
        # Remove summary from pr group
        tree["groups"][0].pop("summary")
        result = merge_override(tree, {
            "groups": [{"name": "pr", "description": "Added description"}]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        assert pr_group["summary"] == "Added description"


# ===========================================================================
# Append extra_guidance
# ===========================================================================

class TestExtraGuidance:
    def test_extra_guidance_stored_on_group(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{"name": "pr", "extra_guidance": "Always draft first"}]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        assert pr_group["extra_guidance"] == "Always draft first"

    def test_extra_guidance_does_not_modify_summary(self):
        tree = make_tree()
        original_summary = tree["groups"][0]["summary"]
        result = merge_override(tree, {
            "groups": [{"name": "pr", "extra_guidance": "Always draft first"}]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        assert pr_group["summary"] == original_summary

    def test_extra_guidance_absent_when_not_set(self):
        tree = make_tree()
        result = merge_override(tree, {})
        for g in result["groups"]:
            assert "extra_guidance" not in g


# ===========================================================================
# Pre-specify meta_skills
# ===========================================================================

class TestMetaSkills:
    def test_meta_skills_added_to_tree(self):
        tree = make_tree()
        meta = [{"name": "pr-workflow", "description": "Full PR workflow"}]
        result = merge_override(tree, {"meta_skills": meta})
        assert result["meta_skills"] == meta

    def test_meta_skills_not_added_when_absent(self):
        tree = make_tree()
        result = merge_override(tree, {})
        assert "meta_skills" not in result

    def test_meta_skills_multiple_entries(self):
        tree = make_tree()
        meta = [
            {"name": "quick-pr", "description": "Quick PR flow"},
            {"name": "release-flow", "description": "Full release cycle"},
        ]
        result = merge_override(tree, {"meta_skills": meta})
        assert len(result["meta_skills"]) == 2
        names = [m["name"] for m in result["meta_skills"]]
        assert "quick-pr" in names
        assert "release-flow" in names


# ===========================================================================
# Halt on unknown group with suggestion
# ===========================================================================

class TestUnknownGroupError:
    def test_raises_override_error_for_unknown_group(self):
        tree = make_tree()
        with pytest.raises(OverrideError) as exc_info:
            merge_override(tree, {"groups": [{"name": "nonexistent", "skip": True}]})
        assert "nonexistent" in str(exc_info.value)

    def test_error_includes_suggestion_for_close_match(self):
        tree = make_tree()
        # "prr" is close to "pr"
        with pytest.raises(OverrideError) as exc_info:
            merge_override(tree, {"groups": [{"name": "prr", "skip": True}]})
        err_msg = str(exc_info.value)
        # Should suggest "pr" as a close match
        assert "pr" in err_msg
        assert "did you mean" in err_msg.lower()

    def test_error_reports_no_close_match_when_very_different(self):
        tree = make_tree()
        with pytest.raises(OverrideError) as exc_info:
            merge_override(tree, {"groups": [{"name": "zzz_totally_different", "skip": True}]})
        err_msg = str(exc_info.value)
        assert "zzz_totally_different" in err_msg

    def test_raises_on_first_unknown_group(self):
        tree = make_tree()
        # First group is valid, second is unknown
        with pytest.raises(OverrideError):
            merge_override(tree, {
                "groups": [
                    {"name": "pr", "description": "Valid"},
                    {"name": "unknown_group", "skip": True},
                ]
            })


# ===========================================================================
# Warn on unknown command
# ===========================================================================

class TestUnknownCommandWarning:
    def test_warns_on_unknown_command(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [{"name": "nonexistent-cmd", "skip": True}]
            }]
        })
        warnings = result.get("warnings", [])
        assert any("nonexistent-cmd" in w for w in warnings), (
            f"Expected warning about 'nonexistent-cmd', got: {warnings}"
        )

    def test_warning_includes_group_name(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [{"name": "bogus", "skip": True}]
            }]
        })
        warnings = result.get("warnings", [])
        assert any("pr" in w for w in warnings)

    def test_known_group_unknown_command_does_not_raise(self):
        """Unknown command in known group is a warning, not an error."""
        tree = make_tree()
        # Must not raise OverrideError
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [{"name": "unknown-cmd", "skip": True}]
            }]
        })
        assert "groups" in result

    def test_no_warnings_when_commands_known(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [{"name": "list", "skip": True}]
            }]
        })
        warnings = result.get("warnings", [])
        # No spurious warnings
        assert len(warnings) == 0


# ===========================================================================
# Skip command within a group
# ===========================================================================

class TestSkipCommand:
    def test_skip_command_removes_it_from_group(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [{"name": "create", "skip": True}]
            }]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        cmd_names = [c["name"] for c in pr_group.get("commands", [])]
        assert "create" not in cmd_names

    def test_skip_command_leaves_other_commands(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [{"name": "create", "skip": True}]
            }]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        cmd_names = [c["name"] for c in pr_group.get("commands", [])]
        assert "list" in cmd_names
        assert "view" in cmd_names

    def test_skip_multiple_commands(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "commands": [
                    {"name": "create", "skip": True},
                    {"name": "view", "skip": True},
                ]
            }]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        cmd_names = [c["name"] for c in pr_group.get("commands", [])]
        assert "create" not in cmd_names
        assert "view" not in cmd_names
        assert "list" in cmd_names


# ===========================================================================
# Combined overrides
# ===========================================================================

class TestCombinedOverrides:
    def test_skip_group_and_add_meta_skills(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{"name": "pr", "skip": True}],
            "meta_skills": [{"name": "issue-workflow", "description": "Issue flow"}],
        })
        names = [g["name"] for g in result["groups"]]
        assert "pr" not in names
        assert "meta_skills" in result

    def test_description_and_extra_guidance_together(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "pr",
                "description": "PR management",
                "extra_guidance": "Focus on draft PRs",
            }]
        })
        pr_group = next(g for g in result["groups"] if g["name"] == "pr")
        assert pr_group["summary"] == "PR management"
        assert pr_group["extra_guidance"] == "Focus on draft PRs"

    def test_description_and_skip_command(self):
        tree = make_tree()
        result = merge_override(tree, {
            "groups": [{
                "name": "issue",
                "description": "Issue tracker",
                "commands": [{"name": "create", "skip": True}],
            }]
        })
        issue_group = next(g for g in result["groups"] if g["name"] == "issue")
        assert issue_group["summary"] == "Issue tracker"
        cmd_names = [c["name"] for c in issue_group.get("commands", [])]
        assert "create" not in cmd_names
        assert "list" in cmd_names
