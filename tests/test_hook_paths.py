import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from hook_paths import paths


class HookPathTests(unittest.TestCase):
    def test_quotes_spaces_flags_and_both_host_variables(self):
        self.assertEqual(paths('bash "${CLAUDE_PLUGIN_ROOT}/hooks/a file.sh" --flag'), ['hooks/a file.sh'])
        self.assertEqual(paths("python '${PLUGIN_ROOT}/hooks/read.py'"), ['hooks/read.py'])

    def test_malformed_quotes_fail_without_evaluating_input(self):
        with self.assertRaises(ValueError):
            paths('bash "${PLUGIN_ROOT}/broken.sh')
        self.assertEqual(paths('echo $(touch /must-not-execute)'), [])

    def test_deep_scanner_accepts_quoted_install_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='plugin scanner ') as temp:
            root = Path(temp) / 'sample'
            (root / '.claude-plugin').mkdir(parents=True)
            (root / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'sample', 'version': '1.0.0'}))
            (root / 'hooks').mkdir()
            (root / 'hooks/a file.sh').write_text('#!/bin/sh\nexit 0\n')
            (root / 'hooks/hooks.json').write_text(json.dumps({'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/a file.sh"', 'timeout': 5}]}]}}))
            result = subprocess.run(['bash', str(ROOT / 'scripts/test-path-resolution.sh'), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Script exists: hooks/a file.sh', result.stdout)
            result = subprocess.run(['bash', str(ROOT / 'scripts/validate.sh'), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
