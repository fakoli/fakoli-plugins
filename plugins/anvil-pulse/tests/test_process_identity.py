"""Hermetic tests for stop/check process ownership and option parsing."""
import os
import hashlib
import time
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProcessOwnership(unittest.TestCase):
    def test_malformed_pid_never_signals_current_process(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = project / '.anvil-pulse'
            state.mkdir()
            for pid in ['-1', '0', str(os.getpid())]:
                (state / 'server.pid').write_text(pid)
                result = subprocess.run(['bash', str(ROOT / 'scripts/stop-server.sh'), '--project-dir', str(project)], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('no process signalled', result.stdout)

    def test_unrelated_node_process_is_not_stopped(self):
        proc = subprocess.Popen(['node', '-e', 'setInterval(()=>{}, 1000)'])
        try:
            with tempfile.TemporaryDirectory() as temp:
                state = Path(temp) / '.anvil-pulse'
                state.mkdir()
                (state / 'server.pid').write_text(str(proc.pid))
                result = subprocess.run(['bash', str(ROOT / 'scripts/stop-server.sh'), '--project-dir', temp], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0)
                self.assertIsNone(proc.poll())
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_missing_argument_does_not_loop(self):
        for script in ['start-server.sh', 'check-server.sh', 'stop-server.sh']:
            result = subprocess.run(['bash', str(ROOT / 'scripts' / script), '--project-dir'], capture_output=True, text=True, timeout=3)
            self.assertNotEqual(result.returncode, 0)

    def test_slow_statusline_returns_stale_cache_within_deadline(self):
        with tempfile.TemporaryDirectory(prefix='pulse-statusline-') as temp:
            folder = Path(temp)
            project = folder / 'project'
            project.mkdir()
            binaries = folder / 'bin'
            binaries.mkdir()
            fake = binaries / 'anvil'
            fake.write_text("#!/bin/sh\nexec python3 -c 'import time; time.sleep(30)'\n")
            fake.chmod(0o755)
            cache = folder / '.cache/anvil-pulse'
            cache.mkdir(parents=True)
            key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()
            cached = cache / f'statusline-{key}.txt'
            cached.write_text('anvil cached status')
            os.utime(cached, (time.time() - 60, time.time() - 60))
            env = dict(os.environ, HOME=temp, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', str(ROOT / 'scripts/statusline-segment.sh'), str(project)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'anvil cached status')

    def test_server_behavior_with_fake_anvil(self):
        subprocess.run(['bash', str(ROOT / 'tests/test-server.sh')], check=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
