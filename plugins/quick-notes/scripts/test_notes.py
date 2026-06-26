#!/usr/bin/env python3
"""Unit tests for notes_lib (the v2 op-log core).

All tests operate on a temporary log file; the real notes.jsonl is never
touched. Run with:  python3 test_notes.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import notes_lib


class NotesLibTest(unittest.TestCase):
    def setUp(self):
        # Fresh temp log per test so cases are isolated.
        self.tmpdir = tempfile.TemporaryDirectory()
        self.log = Path(self.tmpdir.name) / "notes.jsonl"

    def tearDown(self):
        self.tmpdir.cleanup()

    # -- helpers -----------------------------------------------------------
    def _write_raw(self, lines):
        """Write raw text lines (used to simulate legacy/corrupt content)."""
        self.log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # -- add + tag extraction ---------------------------------------------
    def test_add_extracts_tags(self):
        op = notes_lib.add_note("ship the #Release with #work #Work", log=self.log)
        self.assertEqual(op["op"], "add")
        # Case-insensitive and de-duplicated, order preserved.
        self.assertEqual(op["tags"], ["release", "work"])
        # Tags remain in the note text.
        self.assertIn("#Release", op["note"])

        notes = notes_lib.current_notes(self.log)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note"], "ship the #Release with #work #Work")

    def test_add_no_tags(self):
        op = notes_lib.add_note("a plain note", log=self.log)
        self.assertEqual(op["tags"], [])

    # -- edit folds correctly ---------------------------------------------
    def test_edit_folds(self):
        added = notes_lib.add_note("original #a", log=self.log)
        notes_lib.edit_note(added["id"], "rewritten #b #c", log=self.log)

        notes = notes_lib.current_notes(self.log)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note"], "rewritten #b #c")
        # Tags re-extracted from the edited text.
        self.assertEqual(notes[0]["tags"], ["b", "c"])
        # Id is stable across the edit.
        self.assertEqual(notes[0]["id"], added["id"])

    def test_edit_unknown_target_is_noop(self):
        notes_lib.add_note("keep me", log=self.log)
        notes_lib.edit_note("deadbeef", "ghost edit", log=self.log)
        notes = notes_lib.current_notes(self.log)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note"], "keep me")

    # -- delete folds correctly -------------------------------------------
    def test_delete_folds(self):
        a = notes_lib.add_note("first", log=self.log)
        b = notes_lib.add_note("second", log=self.log)
        notes_lib.delete_note(a["id"], log=self.log)

        notes = notes_lib.current_notes(self.log)
        self.assertEqual([n["id"] for n in notes], [b["id"]])

    def test_delete_then_edit_target_is_noop(self):
        a = notes_lib.add_note("doomed", log=self.log)
        notes_lib.delete_note(a["id"], log=self.log)
        notes_lib.edit_note(a["id"], "resurrect?", log=self.log)
        # Edit after delete does nothing; note stays gone.
        self.assertEqual(notes_lib.current_notes(self.log), [])

    # -- legacy no-op line treated as add ---------------------------------
    def test_legacy_line_treated_as_add(self):
        legacy = {"ts": "2026-05-01T10:00:00+00:00", "id": "11111111",
                  "note": "legacy #old note"}
        self._write_raw([json.dumps(legacy)])

        notes = notes_lib.current_notes(self.log)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], "11111111")
        # Tags backfilled for legacy adds.
        self.assertEqual(notes[0]["tags"], ["old"])

    def test_legacy_add_then_modern_edit(self):
        legacy = {"ts": "2026-05-01T10:00:00+00:00", "id": "22222222",
                  "note": "legacy text"}
        self._write_raw([json.dumps(legacy)])
        notes_lib.edit_note("22222222", "modern rewrite", log=self.log)

        notes = notes_lib.current_notes(self.log)
        self.assertEqual(notes[0]["note"], "modern rewrite")

    def test_corrupt_line_skipped(self):
        self._write_raw(["not json at all", json.dumps(
            {"ts": "2026-05-01T10:00:00+00:00", "id": "33333333", "note": "ok"})])
        notes = notes_lib.current_notes(self.log)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], "33333333")

    # -- keyword AND search -----------------------------------------------
    def test_keyword_and_search(self):
        notes_lib.add_note("retry with backoff", log=self.log)
        notes_lib.add_note("retry only", log=self.log)
        notes_lib.add_note("backoff only", log=self.log)

        notes = notes_lib.current_notes(self.log)
        matched = notes_lib.filter_notes(notes, keywords=["retry", "backoff"])
        self.assertEqual([n["note"] for n in matched], ["retry with backoff"])

    def test_keyword_case_insensitive(self):
        notes_lib.add_note("Deploy the Service", log=self.log)
        notes = notes_lib.current_notes(self.log)
        matched = notes_lib.filter_notes(notes, keywords=["deploy"])
        self.assertEqual(len(matched), 1)

    # -- tag filter --------------------------------------------------------
    def test_tag_filter(self):
        notes_lib.add_note("a #work item", log=self.log)
        notes_lib.add_note("a #home item", log=self.log)
        notes = notes_lib.current_notes(self.log)

        # Plain name, with '#', and different case all match.
        self.assertEqual(len(notes_lib.filter_notes(notes, tag="work")), 1)
        self.assertEqual(len(notes_lib.filter_notes(notes, tag="#work")), 1)
        self.assertEqual(len(notes_lib.filter_notes(notes, tag="WORK")), 1)
        self.assertEqual(len(notes_lib.filter_notes(notes, tag="missing")), 0)

    # -- since filter ------------------------------------------------------
    def test_since_filter(self):
        old = {"ts": "2020-01-01T00:00:00+00:00", "id": "aaaaaaaa",
               "op": "add", "note": "old", "tags": []}
        new = {"ts": "2026-06-02T12:00:00+00:00", "id": "bbbbbbbb",
               "op": "add", "note": "new", "tags": []}
        self._write_raw([json.dumps(old), json.dumps(new)])
        notes = notes_lib.current_notes(self.log)
        matched = notes_lib.filter_notes(notes, since="2026-01-01")
        self.assertEqual([n["id"] for n in matched], ["bbbbbbbb"])

    def test_since_bad_format_raises(self):
        notes_lib.add_note("x", log=self.log)
        notes = notes_lib.current_notes(self.log)
        with self.assertRaises(ValueError):
            notes_lib.filter_notes(notes, since="06/02/2026")

    # -- stats -------------------------------------------------------------
    def test_stats(self):
        notes_lib.add_note("one #x", log=self.log)
        notes_lib.add_note("two #x #y", log=self.log)
        notes = notes_lib.current_notes(self.log)
        s = notes_lib.stats(notes)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["last_7_days"], 2)  # just added
        self.assertEqual(s["top_tags"][0], ("x", 2))

    # -- export output -----------------------------------------------------
    def test_export_output(self):
        a = notes_lib.add_note("morning #plan", log=self.log)
        b = notes_lib.add_note("to be removed", log=self.log)
        notes_lib.delete_note(b["id"], log=self.log)

        out = Path(self.tmpdir.name) / "notes.md"
        count = notes_lib.export_markdown(out, log=self.log)
        self.assertEqual(count, 1)

        text = out.read_text(encoding="utf-8")
        self.assertIn("# Notes", text)
        self.assertIn("## ", text)            # a date heading
        self.assertIn(f"[{a['id']}]", text)   # the live note's id
        self.assertIn("morning #plan", text)
        # Deleted note must not appear.
        self.assertNotIn(b["id"], text)
        self.assertNotIn("to be removed", text)

    def test_export_groups_by_day_newest_first(self):
        day1 = {"ts": "2026-06-01T09:00:00+00:00", "id": "d1111111",
                "op": "add", "note": "day one", "tags": []}
        day2 = {"ts": "2026-06-02T09:00:00+00:00", "id": "d2222222",
                "op": "add", "note": "day two", "tags": []}
        self._write_raw([json.dumps(day1), json.dumps(day2)])
        out = Path(self.tmpdir.name) / "notes.md"
        notes_lib.export_markdown(out, log=self.log)
        text = out.read_text(encoding="utf-8")
        # Newest day heading appears before the older one.
        self.assertLess(text.index("## 2026-06-02"), text.index("## 2026-06-01"))

    def test_export_survives_multiple_unparseable_timestamps(self):
        # Two notes whose ts cannot be parsed both land in the "unknown-date"
        # bucket; the intra-day sort must not compare None < None (TypeError).
        bad1 = {"ts": "not-a-date", "id": "badd0001",
                "op": "add", "note": "first bad", "tags": []}
        bad2 = {"ts": "", "id": "badd0002",
                "op": "add", "note": "second bad", "tags": []}
        self._write_raw([json.dumps(bad1), json.dumps(bad2)])
        out = Path(self.tmpdir.name) / "notes.md"
        # Must not raise.
        count = notes_lib.export_markdown(out, log=self.log)
        self.assertEqual(count, 2)
        text = out.read_text(encoding="utf-8")
        self.assertIn("## unknown-date", text)
        self.assertIn("first bad", text)
        self.assertIn("second bad", text)

    def test_non_utc_timestamp_grouped_in_utc(self):
        # 23:30 at -05:00 is 04:30 UTC the *next* day; the export heading must
        # use the UTC date so it agrees with the --since/--today filters.
        local = {"ts": "2026-06-02T23:30:00-05:00", "id": "tzaaaaaa",
                 "op": "add", "note": "late night local", "tags": []}
        self._write_raw([json.dumps(local)])
        out = Path(self.tmpdir.name) / "notes.md"
        notes_lib.export_markdown(out, log=self.log)
        text = out.read_text(encoding="utf-8")
        self.assertIn("## 2026-06-03", text)
        self.assertNotIn("## 2026-06-02", text)

    def test_export_wrapper_writes_markdown_next_to_notes_log(self):
        notes_lib.add_note("keep data outside plugin code", log=self.log)
        expected_out = self.log.with_name("notes.md")
        script = Path(__file__).with_name("export-notes.py")

        env = os.environ.copy()
        env["NOTES_LOG"] = str(self.log)
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=script.parent,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(expected_out.exists())
        self.assertIn("keep data outside plugin code", expected_out.read_text(encoding="utf-8"))

    def test_today_filter(self):
        old = {"ts": "2020-01-01T00:00:00+00:00", "id": "old00001",
               "op": "add", "note": "ancient", "tags": []}
        self._write_raw([json.dumps(old)])
        fresh = notes_lib.add_note("today's note", log=self.log)
        notes = notes_lib.current_notes(self.log)
        matched = notes_lib.filter_notes(notes, today=True)
        self.assertEqual([n["id"] for n in matched], [fresh["id"]])

    def test_tag_boundary_and_unicode(self):
        # Mid-token '#' is not a tag; whitespace/start-anchored '#' is.
        # \w is Unicode-aware so accented/CJK tags work.
        op = notes_lib.add_note(
            "C#sharp and abc#123 and #café and # alone and #real-tag",
            log=self.log,
        )
        self.assertEqual(op["tags"], ["café", "real-tag"])

    def test_unicode_note_roundtrip(self):
        text = "launch 🚀 with 日本語 notes and emoji ✅"
        notes_lib.add_note(text, log=self.log)
        notes = notes_lib.current_notes(self.log)
        self.assertEqual(notes[0]["note"], text)

    def test_source_field_roundtrip(self):
        notes_lib.add_note("dictated thought", source="dictation", log=self.log)
        notes = notes_lib.current_notes(self.log)
        self.assertEqual(notes[0].get("source"), "dictation")

    def test_delete_nonexistent_is_noop(self):
        a = notes_lib.add_note("survivor", log=self.log)
        notes_lib.delete_note("ffffffff", log=self.log)
        notes = notes_lib.current_notes(self.log)
        self.assertEqual([n["id"] for n in notes], [a["id"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
