import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('handoff_hook',ROOT/'hooks/session-start.py')
hook=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(hook)
class HookSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.project=self.root/'café'; self.project.mkdir()
        self.data=self.root/'data'; self.env=dict(os.environ,HANDOFF_DATA_DIR=str(self.data))
    def path(self):
        result=subprocess.run(['bash',str(ROOT/'scripts/handoff-path.sh'),str(self.project)],env=self.env,capture_output=True,text=True,check=True)
        return Path(result.stdout.strip())
    def run_hook(self):
        result=subprocess.run([sys.executable,str(ROOT/'hooks/session-start.py')],cwd=self.root,env=self.env,input=json.dumps({'cwd':str(self.project)}),capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    def test_non_ascii_key_matches_shell_and_payload_cwd(self):
        path=self.path(); path.write_text('resume synthetic task')
        self.assertEqual(path.parent.name,hook.handoff_key(self.project.name,str(self.project.resolve())))
        self.assertIn('resume synthetic task',self.run_hook()['hookSpecificOutput']['additionalContext'])
    def test_missing_context_creates_no_state(self):
        self.assertEqual(self.run_hook(),{})
        self.assertFalse(self.data.exists())
    def test_preview_is_bounded_and_strips_crlf_metadata(self):
        path=self.path(); path.write_bytes(b'---\r\nhead: hidden\r\n---\r\n'+b'x'*30000)
        text=self.run_hook()['hookSpecificOutput']['additionalContext']
        self.assertLess(len(text),17000); self.assertNotIn('head: hidden',text); self.assertIn('truncated',text)
    def test_invalid_project_does_not_create_handoff(self):
        result=subprocess.run(['bash',str(ROOT/'scripts/handoff-path.sh'),str(self.root/'missing')],env=self.env,capture_output=True)
        self.assertEqual(result.returncode,2); self.assertFalse(self.data.exists())
    def test_unclosed_metadata_is_unavailable(self):
        self.path().write_text('---\nsaved_at: 2000-01-01T00:00:00Z\nprose')
        result=subprocess.run(['bash',str(ROOT/'scripts/handoff-freshness.sh'),str(self.project),'--json'],env=self.env,capture_output=True,text=True)
        self.assertFalse(json.loads(result.stdout)['available'])
if __name__=='__main__': unittest.main()
