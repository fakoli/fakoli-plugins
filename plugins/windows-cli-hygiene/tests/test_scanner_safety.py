import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/scan_cli_hygiene.py'
class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
    def run_cli(self,*args): return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True)
    def test_quoted_heredoc_is_literal_and_unquoted_expansion_reported(self):
        path=self.root/'script.sh'
        path.write_text("cat <<'EOF'\n$(literal)\\n\nEOF\ncat <<EOF\n$(expanded)\nEOF\n")
        rows=json.loads(self.run_cli(path,'--json').stdout)['findings']
        self.assertEqual([(r['line'],r['rule']) for r in rows],[(5,'UNQUOTED_HEREDOC')])
    def test_unusual_filename_roundtrips_json_and_gate_status(self):
        path=self.root/'tab\tline\n.py'; path.write_text('print("arrow →")')
        result=self.run_cli(path,'--json','--fail-on-findings')
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stdout)['findings'][0]['file'],str(path))
    def test_missing_path_and_help(self):
        self.assertEqual(self.run_cli(self.root/'missing').returncode,2)
        self.assertEqual(self.run_cli('--help').returncode,0)
    def test_combined_and_named_errexit(self):
        (self.root/'hooks').mkdir(); path=self.root/'hooks/entry.sh'
        path.write_text('set -euo pipefail\nset -o errexit\nset -uo pipefail\n')
        self.assertEqual(json.loads(self.run_cli(path,'--json').stdout)['count'],2)
if __name__=='__main__': unittest.main()
