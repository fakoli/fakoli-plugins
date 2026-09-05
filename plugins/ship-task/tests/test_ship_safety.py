"""Run the real shell loop against deterministic git/gh/sleep executables."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SHIP = Path(__file__).resolve().parents[1] / "scripts/ship.sh"


class ShipSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ship-safety-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "calls"
        self.env = {
            **os.environ,
            "SHIP_TEST_LOG": str(self.log),
            "SHIP_TEST_CI": "pass",
            "SHIP_TEST_STATE": "MERGED",
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
        }
        self.stub(
            "git",
            """case "$*" in
  "rev-parse --is-inside-work-tree") echo true;;
  "branch --show-current") echo feature;;
  "rev-parse HEAD"|"rev-parse feature") echo abc123;;
esac
exit 0
""",
        )
        self.stub(
            "gh",
            """case "$*" in
  *defaultBranchRef*) echo main;;
  *nameWithOwner*) echo owner/repo;;
  *"--json number"*) echo 42;;
  *"--json url"*) echo https://example.test/pr/42;;
  *"--json state"*) echo "$SHIP_TEST_STATE";;
  *"--json mergeCommit"*) echo merged123;;
  "pr checks"*)
    case "$SHIP_TEST_CI" in
      unavailable) exit 1;;
      unknown) printf 'new-bucket\\tcheck\\n';;
      pending) printf 'pending\\tcheck\\n'; exit 8;;
      fail) printf 'fail\\tcheck\\n'; exit 1;;
      empty) :;;
      *) printf 'pass\\tcheck\\n';;
    esac;;
esac
exit 0
""",
        )
        self.stub("sleep", "exit 0\n")

    def stub(self, name, body):
        path = self.root / name
        path.write_text(
            '#!/usr/bin/env bash\nprintf "%s %s\\n" "${0##*/}" "$*" >> "$SHIP_TEST_LOG"\n' + body
        )
        path.chmod(0o755)

    def run_ship(self, *args):
        return subprocess.run(
            ["bash", str(SHIP), *args],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=3,
        )

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_missing_value_and_invalid_timing_terminate_before_git(self):
        for args in [
            ("--body",),
            ("--poll-secs", "0", "title"),
            ("--timeout-secs", "bad", "title"),
        ]:
            with self.subTest(args=args):
                self.assertEqual(self.run_ship(*args).returncode, 1)
        self.assertEqual(self.calls(), "")

    def test_failed_and_unknown_ci_never_merge(self):
        for status in ["unavailable", "unknown", "fail"]:
            with self.subTest(status=status):
                self.log.unlink(missing_ok=True)
                self.env["SHIP_TEST_CI"] = status
                result = self.run_ship("title")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("gh pr merge", self.calls())

    def test_registration_wait_obeys_total_timeout(self):
        self.env["SHIP_TEST_CI"] = "empty"
        result = self.run_ship("--timeout-secs", "1", "title")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("sleep 1", self.calls())
        self.assertNotIn("gh pr merge", self.calls())

    def test_pending_exit_eight_is_waited_then_times_out(self):
        self.env["SHIP_TEST_CI"] = "pending"
        result = self.run_ship("--timeout-secs", "1", "title")
        self.assertEqual(result.returncode, 2)
        self.assertIn("CI timeout", result.stdout)

    def test_merge_is_pinned_to_pushed_commit(self):
        result = self.run_ship("title")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--match-head-commit abc123", self.calls())

    def test_queued_merge_does_not_sync_or_run_then(self):
        self.env["SHIP_TEST_STATE"] = "OPEN"
        marker = self.root / "post-merge"
        result = self.run_ship("--then", f"touch '{marker}'", "title")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertNotIn("git checkout", self.calls())
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
