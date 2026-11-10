"""Exercise source binding and evidence refusal with an actual temporary Git repo."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts/verify-delivery.py"
spec = importlib.util.spec_from_file_location("delivery", SCRIPT)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.packet = self.root / "delivery.json"
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture Author")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.checkout / "code.txt").write_text("qualified\n")
        self.git("add", "code.txt")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")
        record = self.artifact("evidence.txt", "retained evidence\n")
        self.data = {
            "schema": "ship-loop.delivery.v1",
            "source": {"commit": self.commit, "tree": self.tree, "authors": ["author"]},
            "verifications": [{"source_tree": self.tree, "argv": ["python3", "check.py"],
                               "exit_code": 0, "log": record}],
            "reviews": [{"reviewer": "reviewer", "source_tree": self.tree,
                         "verdict": "pass", "record": record}],
            "ci": {"head_commit": self.commit, "tested_commit": self.commit,
                   "tested_tree": self.tree, "conclusion": "success", "record": record},
            "custody": {"status": "stopped", "record": record},
            "retained_failures": [self.artifact("failed.log", "earlier failure\n")],
            "merge_commit": self.commit,
        }

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.checkout), *arguments], text=True).strip()

    def artifact(self, name, content):
        path = self.root / name
        path.write_text(content)
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def verify(self, required=1):
        self.packet.write_text(json.dumps(self.data))
        return delivery.verify(self.packet, self.checkout, required)

    def test_consistent_packet_retains_failure_and_verifies_real_git(self):
        result = self.verify()
        self.assertTrue(result["consistent"])
        self.assertEqual(result["retained_failures"], 1)
        self.assertEqual(result["source_tree"], self.tree)

    def test_failure_stale_bindings_unknown_custody_and_false_exit_are_refused(self):
        original = copy.deepcopy(self.data)
        for section, field, value in [
            ("ci", "head_commit", "0" * 40), ("ci", "tested_tree", "0" * 40),
            ("ci", "conclusion", "pending"), ("custody", "status", "unknown"),
            ("verifications", "exit_code", 1), ("verifications", "exit_code", False),
            ("verifications", "source_tree", "0" * 40),
            ("reviews", "source_tree", "0" * 40), ("reviews", "verdict", "blocked"),
            ("reviews", "reviewer", "author"),
        ]:
            with self.subTest(section=section, field=field, value=value):
                self.data = copy.deepcopy(original)
                target = self.data[section]
                if isinstance(target, list):
                    target = target[0]
                target[field] = value
                with self.assertRaises(ValueError):
                    self.verify()

    def test_repository_review_count_is_explicit_and_duplicate_names_do_not_count(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            self.verify(required=2)
        self.data["reviews"] *= 2
        with self.assertRaisesRegex(ValueError, "Reviewer must"):
            self.verify(required=2)

    def test_modified_missing_and_external_artifacts_are_refused(self):
        original = copy.deepcopy(self.data)
        for path, digest in [("evidence.txt", "0" * 64), ("missing.log", "0" * 64),
                             ("../outside.log", "0" * 64), (str(self.root / "evidence.txt"), "0" * 64)]:
            with self.subTest(path=path):
                self.data = copy.deepcopy(original)
                self.data["verifications"][0]["log"] = {"path": path, "sha256": digest}
                with self.assertRaises((ValueError, OSError)):
                    self.verify()

    def test_untracked_worktree_content_and_changed_merge_tree_are_refused(self):
        (self.checkout / "extra.txt").write_text("unreviewed")
        with self.assertRaisesRegex(ValueError, "clean"):
            self.verify()
        self.git("add", "extra.txt")
        self.git("commit", "-qm", "different tree")
        other = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", self.commit)
        self.data["merge_commit"] = other
        with self.assertRaisesRegex(ValueError, "Merged tree"):
            self.verify()
        self.data["merge_commit"] = self.commit
        self.data["ci"]["tested_commit"] = other
        with self.assertRaisesRegex(ValueError, "CI tested commit"):
            self.verify()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO probe")
    def test_non_regular_evidence_is_refused_without_waiting_for_a_writer(self):
        path = self.root / "pipe"
        os.mkfifo(path)
        self.data["verifications"][0]["log"]["path"] = "pipe"
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.verify()

    def test_cli_failure_returns_json_and_nonzero(self):
        self.data["ci"]["conclusion"] = "failure"
        self.packet.write_text(json.dumps(self.data))
        result = subprocess.run([os.sys.executable, str(SCRIPT), str(self.packet),
                                 "--checkout", str(self.checkout), "--required-reviewers", "1"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["consistent"])


if __name__ == "__main__":
    unittest.main()
