import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/skill_spec_lint.py'
SPEC=importlib.util.spec_from_file_location('spec_linter',SCRIPT)
lint=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(lint)
class YamlContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.skill=Path(self.temp.name)/'skills/a'; self.skill.mkdir(parents=True)
    def check_text(self,text):
        (self.skill/'SKILL.md').write_text('---\n'+text+'\n---\nbody')
        return lint.validate_skill(self.skill)
    def test_wrong_scalar_and_nested_types(self):
        for text in ('name: 1\ndescription: x','name: a\ndescription: true','name: a\ndescription: [x]','name: a\ndescription: x\nmetadata:\n  version: 1','name: a\ndescription: x\ncompatibility: null'):
            with self.subTest(text=text): self.assertTrue(any(f.level=='ERROR' for f in self.check_text(text)))
    def test_duplicate_keys_rejected(self):
        self.assertTrue(self.check_text('name: a\nname: a\ndescription: x'))
    def test_indented_fence_is_block_scalar_data(self):
        self.assertEqual(self.check_text('name: a\ndescription: |\n  ---\n  ordinary text'),[])
    def test_direct_file_and_overlapping_roots_deduplicate(self):
        self.check_text('name: a\ndescription: x')
        findings,count=lint.lint([self.skill,self.skill/'SKILL.md',self.skill.parent.parent])
        self.assertEqual(findings,[]); self.assertEqual(count,1)
    def test_help_and_length_recommendation(self):
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as result: lint.main(['--help'])
        self.assertEqual(result.exception.code,0)
        self.check_text('name: a\ndescription: x')
        path=self.skill/'SKILL.md';path.write_text(path.read_text()+'\nline'*501)
        findings=lint.validate_skill(self.skill)
        self.assertTrue(any(f.level=='WARN' and 'body' in f.message for f in findings))
        self.assertFalse(any(f.level=='ERROR' for f in findings))
if __name__=='__main__': unittest.main()
