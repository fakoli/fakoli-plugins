"""Offline installed-path and locked CLI help contracts; never authenticate/query."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NotebookCLI(unittest.TestCase):
    def test_wrapper_uses_own_lock_and_preserves_notebook_and_cwd(self):
        with tempfile.TemporaryDirectory(prefix='notebook wrapper ') as folder:
            temp = Path(folder)
            fake = temp / 'uv'
            fake.write_text('#!/usr/bin/env python3\nimport os,json,sys\nprint(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd()}))\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=str(temp) + os.pathsep + os.environ['PATH'])
            output = subprocess.check_output(['bash', str(ROOT / 'scripts/notebooklm.sh'), 'ask', 'question with spaces', '--notebook', 'full-id'], cwd=temp, env=env, text=True, timeout=5)
            payload = json.loads(output)
            self.assertEqual(payload['args'][:4], ['run', '--frozen', '--project', str(ROOT / 'scripts')])
            self.assertEqual(payload['args'][-2:], ['--notebook', 'full-id'])
            self.assertEqual(Path(payload['cwd']).resolve(), temp.resolve())

    def test_locked_help_supports_explicit_ids_and_bounded_operations(self):
        with tempfile.TemporaryDirectory(prefix='notebook-help-') as folder:
            env = dict(os.environ, NOTEBOOKLM_HOME=folder)
            env.pop('NOTEBOOKLM_AUTH_JSON', None)
            for command, flags in [(['ask'], ['--notebook', '--conversation-id', '--request-timeout']),
                                   (['artifact', 'wait'], ['--notebook', '--timeout', '--interval']),
                                   (['research', 'wait'], ['--run-id', '--timeout']),
                                   (['download', 'audio'], ['--artifact', '--no-clobber'])]:
                result = subprocess.run(['bash', str(ROOT / 'scripts/notebooklm.sh'), *command, '--help'], env=env, text=True, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                for flag in flags: self.assertIn(flag, result.stdout)


if __name__ == '__main__': unittest.main()
