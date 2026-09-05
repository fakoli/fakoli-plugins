import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/gate_router.py'
class RouterSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.git('init','-q','-b','main'); self.git('config','user.name','Synthetic'); self.git('config','user.email','test@example.invalid')
        (self.root/'seed').write_text('seed'); self.git('add','.'); self.git('commit','-qm','initial')
        (self.root/'.claude').mkdir()
        self.config=self.root/'.claude/gate-router.local.md'
        self.config.write_text('---\nrules:\n  - **/*.py => printf "%s\\n" {files}\n  - ** => printf "%s\\n" {files}\n---\n')
    def git(self,*args): return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True)
    def run_cli(self,*args): return subprocess.run([sys.executable,str(SCRIPT),str(self.root),*args],capture_output=True,text=True)
    def test_unicode_and_control_names_are_exact_and_deduplicated(self):
        names=['café.py','line\nname.py','tab\tname.py']
        for name in names: (self.root/name).write_text('pass')
        self.git('add',*names)
        result=self.run_cli('--json'); self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(set(data['gates'][0]['files']),set(names))
        self.assertEqual(len(data['gates'][0]['files']),3)
        self.assertEqual(data['changed'],3)
    def test_unknown_base_is_an_error_not_empty_success(self):
        result=self.run_cli('--base','missing-branch','--json')
        self.assertEqual(result.returncode,2); self.assertIn('failed',result.stderr)
    def test_unclosed_config_is_rejected(self):
        self.config.write_text('---\nrules:\n  - ** => true\n')
        self.assertEqual(self.run_cli().returncode,2)
    def test_quoted_placeholder_rejected(self):
        self.config.write_text('---\nrules:\n  - ** => printf "%s" "{files}"\n---\n')
        self.assertEqual(self.run_cli().returncode,2)
    def test_run_json_conflict_and_help(self):
        self.assertEqual(self.run_cli('--run','--json').returncode,2)
        self.assertEqual(self.run_cli('--help').returncode,0)
    def test_shell_gate_checks_every_file_and_skips_deleted_paths(self):
        self.config.write_text('---\nrules:\n  - **/*.sh => for file in {files}; do test ! -f "$file" || bash -n "$file" || exit; done\n---\n')
        (self.root/'deleted.sh').write_text('echo old\n')
        self.git('add','deleted.sh'); self.git('commit','-qm','tracked shell')
        (self.root/'deleted.sh').unlink()
        (self.root/'first.sh').write_text('echo valid\n')
        (self.root/'second.sh').write_text('if\n')
        result=self.run_cli('--run')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('second.sh',result.stderr)

if __name__=='__main__': unittest.main()

