import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/session_stats.py'
SPEC=importlib.util.spec_from_file_location('retro_safety',SCRIPT)
retro=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retro)
class ReportSafetyTests(unittest.TestCase):
    def test_non_object_jsonl_records_are_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'session.jsonl';path.write_text('\ufeff42\nnull\n[]\n'+json.dumps({'type':'user','message':{'content':'synthetic'}})+'\n')
            self.assertEqual(retro.parse(str(path))['user_turns'],['synthetic'])
    def test_missing_requested_input_cannot_be_silently_omitted(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'session.jsonl';path.write_text('{}\n')
            result=subprocess.run([sys.executable,str(SCRIPT),'stats',str(path),str(path)+'missing'],capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertNotIn('main_output_tokens',result.stdout)
    def test_narrative_rejects_executable_link_schemes(self):
        rendered=retro.md_to_html('[open](javascript:alert%281%29)\n[safe](https://example.invalid)')
        self.assertNotIn('javascript:',rendered);self.assertIn('https://example.invalid',rendered)
    def test_html_escapes_untrusted_labels_at_dom_sinks(self):
        # Exercise the exact browser escaping expression used at label sinks.
        import shutil
        if not shutil.which('node'): self.skipTest('Node is unavailable')
        expression=retro.HTML_TEMPLATE.split('const esc = ',1)[1].split(';\n',1)[0]
        output=subprocess.check_output(['node','-e','const esc = '+expression+';process.stdout.write(esc(process.argv[1]));','<img src=x onerror="alert(1)">'],text=True)
        self.assertEqual(output,'&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
    def test_aliases_deduplicate_canonical_paths(self):
        with tempfile.TemporaryDirectory() as root:
            real=Path(root)/'real.jsonl';real.write_text('{}\n');alias=Path(root)/'alias.jsonl';alias.symlink_to(real)
            self.assertEqual(len(retro.expand_paths([str(real),str(alias)])),1)
if __name__=='__main__': unittest.main()
