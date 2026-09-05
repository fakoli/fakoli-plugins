"""Validate all skill contracts and execute shared shell examples against a fake CLI."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class SharedConventions(unittest.TestCase):
    def test_all_skills_have_unique_valid_frontmatter_and_local_links(self):
        names = set()
        for skill in (ROOT / 'skills').glob('*/SKILL.md'):
            source = skill.read_text()
            self.assertTrue(source.startswith('---\n'), str(skill))
            meta = yaml.safe_load(source.split('---', 2)[1])
            self.assertEqual(meta['name'], skill.parent.name)
            self.assertTrue(meta['description'].strip())
            self.assertNotIn(meta['name'], names)
            names.add(meta['name'])
            for target in re.findall(r'\]\(([^)]+)\)', source):
                if not re.match(r'https?://|#', target):
                    self.assertTrue((skill.parent / target.split('#')[0]).exists(), (skill, target))
        self.assertEqual(len(names), 100)

    def test_documented_quoted_arguments_survive_bash_and_zsh(self):
        source = (ROOT / 'skills/gws-shared/SKILL.md').read_text()
        commands = re.findall(r'^gws (?:sheets|drive).*$', source, re.M)
        with tempfile.TemporaryDirectory(prefix='gws-args-') as directory:
            folder = Path(directory)
            fake = folder / 'gws'
            fake.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=str(folder) + os.pathsep + os.environ['PATH'])
            for shell in ('bash', 'zsh'):
                if not shutil.which(shell): continue
                for command in commands:
                    result = subprocess.run([shell, '-f', '-c', command], env=env, text=True, capture_output=True, check=True, timeout=5)
                    args = json.loads(result.stdout)
                    if '--range' in args:
                        self.assertEqual(args[-1], 'Sheet1!A1:D10')
                    else:
                        self.assertEqual(json.loads(args[-1]), {'pageSize': 5})


if __name__ == '__main__': unittest.main()
