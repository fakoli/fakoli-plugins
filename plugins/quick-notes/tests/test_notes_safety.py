import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import notes_lib as notes

class NotesSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / 'notes.jsonl'

    def test_no_newline_tail_is_preserved_and_new_note_readable(self):
        self.log.write_text(json.dumps({'id':'legacy', 'note':'original'}))
        notes.add_note('new', log=self.log)
        self.assertEqual([row['note'] for row in notes.current_notes(self.log)], ['original','new'])

    def test_wrong_types_skip_without_crashing_or_erasing(self):
        raw = '\n'.join(json.dumps(x) for x in ([], 2, None, {'id':'bad','note':[]}, {'id':'good','note':'kept'}))
        self.log.write_text(raw)
        self.assertEqual([row['id'] for row in notes.current_notes(self.log)], ['good'])
        self.assertEqual(self.log.read_text(), raw)

    def test_duplicate_add_cannot_duplicate_or_resurrect(self):
        original={'id':'one','note':'first'}
        self.assertEqual(len(notes.fold([original, original])), 1)
        self.assertEqual(notes.fold([original, {'op':'delete','target':'one'}, original]), [])

    def test_cli_precondition_is_checked_under_lock(self):
        row=notes.add_note('first',log=self.log)
        notes.delete_note(row['id'],log=self.log)
        before=self.log.read_bytes()
        with self.assertRaises(ValueError):
            notes.edit_note(row['id'],'stale update',log=self.log,require_existing=True)
        self.assertEqual(self.log.read_bytes(),before)

    def test_contended_writer_fails_without_an_append(self):
        notes.add_note('first',log=self.log)
        self.log.with_name('notes.jsonl.lock').mkdir()
        before=self.log.read_bytes()
        with patch.object(notes.time,'monotonic',side_effect=[0,6]):
            with self.assertRaises(OSError): notes.add_note('second',log=self.log)
        self.assertEqual(self.log.read_bytes(),before)

    def test_export_cannot_replace_log(self):
        notes.add_note('first',log=self.log)
        before=self.log.read_bytes()
        with self.assertRaises(ValueError): notes.export_markdown(self.log,log=self.log)
        self.assertEqual(self.log.read_bytes(),before)

if __name__ == '__main__': unittest.main()
