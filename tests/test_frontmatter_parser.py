import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('frontmatter', Path(__file__).resolve().parents[1] / 'scripts/lint-frontmatter.py')
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)


class FrontmatterTests(unittest.TestCase):
    def check(self, body, close=True):
        with tempfile.TemporaryDirectory() as temp:
            skill = Path(temp) / 'valid-skill' / 'SKILL.md'
            skill.parent.mkdir()
            skill.write_text('---\n' + body + ('\n---\nText\n' if close else ''))
            return lint.check(str(skill))

    def test_yaml_strings_and_comments_are_parsed(self):
        self.assertIsNone(self.check('name: "valid-skill" # comment\ndescription: "Use --- within a description."'))

    def test_fake_delimiters_do_not_close_frontmatter(self):
        self.assertIn('never closed', self.check('name: valid-skill\ndescription: "---"', close=False))

    def test_required_description_has_semantic_type_and_size(self):
        for value in ['[]', 'false', 'null', '42', '""', '"' + 'a' * 1025 + '"']:
            self.assertIn('description', self.check('name: valid-skill\ndescription: ' + value))

    def test_name_is_not_coerced_from_yaml(self):
        self.assertIn('string', self.check('name: false\ndescription: Inspect data.'))
