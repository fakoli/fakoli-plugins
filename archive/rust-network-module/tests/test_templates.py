#!/usr/bin/env python3
"""Render every shipped template and compile/test it in a disposable crate."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'skills/rust-network-module/assets'


def main():
    with tempfile.TemporaryDirectory(prefix='rust-network-template-') as directory:
        crate = Path(directory)
        (crate / 'src').mkdir()
        substitutions = {'__NAME__': 'example', '__TYPE__': 'Example',
                         '__PRIMARY__': 'protocol', '__DESCRIPTION__': 'Template verification crate.'}
        def render(filename):
            source = (ASSETS / filename).read_text()
            for key, value in substitutions.items():
                source = source.replace(key, value)
            if re.search(r'__[A-Z_]+__', source):
                raise ValueError(f'Unresolved template token in {filename}')
            return source
        (crate / 'Cargo.toml').write_text('''[package]
name = "network-template-verification"
version = "0.0.0"
edition = "2021"
[dependencies]
tokio = { version = "1", features = ["rt", "macros", "net", "io-util", "time", "sync"] }
tracing = "0.1"
''')
        (crate / 'src/lib.rs').write_text(render('mod.rs.tmpl') + '\npub mod listener;\n')
        (crate / 'src/listener.rs').write_text(render('listener.rs.tmpl') + '\n' + (ROOT / 'tests/listener_tests.rs').read_text())
        (crate / 'src/protocol.rs').write_text(render('protocol.rs.tmpl') + '\n' + render('tests.rs.tmpl'))
        env = os.environ.copy()
        env['CARGO_TARGET_DIR'] = str(crate / 'target')
        if os.getenv("NETWORK_TEMPLATE_ALLOW_FETCH") == "1":
            subprocess.run(["cargo", "fetch"], cwd=crate, env=env, check=True, timeout=180)
        for command in (["cargo", "test", "--offline"],
                        ["cargo", "clippy", "--offline", "--all-targets", "--", "-D", "warnings"]):
            subprocess.run(command, cwd=crate, env=env, check=True, timeout=180)


class TemplateBehavior(unittest.TestCase):
    def test_rendered_templates_compile_and_behave(self):
        main()


if __name__ == '__main__':
    unittest.main()
