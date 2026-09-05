#!/usr/bin/env python3
"""Tests for VariantCollator v1-C (discovery).

Discovery buys recall with false positives, so this suite spends most of its weight on what the
tool must STAY SILENT about. A detector that reports everything is not a detector.

Run:  python test_collator.py
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collator  # noqa: E402

BS = chr(8)
NBSP = chr(0xA0)
ZWSP = chr(0x200B)
BOM = chr(0xFEFF)


class Harness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="collate-c-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, body):
        path = os.path.join(self.dir, name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        return path

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = collator.main([self.dir] + list(args))
        return code, buf.getvalue()


class TestTheMotivatingDefect(Harness):
    def test_finds_the_backspace_without_being_told_to_look(self):
        """No markers, no config. The whole point of this road."""
        line = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        self.write("relay.js", line + "\n")
        self.write("fixture.js", line.replace("CONTINUE)", "CONTINUE)" + BS) + "\n")
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("VARIANT", out)
        self.assertIn("BACKSPACE", out)

    def test_control_identical_copies_are_silent(self):
        line = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        self.write("relay.js", line + "\n")
        self.write("fixture.js", line + "\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertNotIn("VARIANT", out)


class TestSilenceIsTheFeature(Harness):
    """Everything this tool must NOT report. Recall is worthless if the output is unreadable."""

    def test_ordinary_visible_difference_is_silent(self):
        """A plain diff already shows these. Reporting them would drown the real finding."""
        self.write("a.py", "timeout_seconds = 30\n")
        self.write("b.py", "timeout_seconds = 60\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertNotIn("VARIANT", out)

    def test_a_line_that_appears_once_is_silent(self):
        self.write("a.py", "a_unique_line_of_code = 1\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)

    def test_reindented_identical_copies_are_silent(self):
        """Leading whitespace is not a variant; copies get re-indented legitimately."""
        self.write("a.py", "    value = compute_the_thing()\n")
        self.write("b.py", "        value = compute_the_thing()\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertNotIn("VARIANT", out)

    def test_short_lines_are_below_the_noise_floor(self):
        self.write("a.py", "x = 1\n")
        self.write("b.py", "x = 1" + BS + "\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0, "default min-length should suppress this")

    def test_but_min_length_one_does_catch_it(self):
        """Control for the test above: the filter is a threshold, not a blind spot."""
        self.write("a.py", "x = 1\n")
        self.write("b.py", "x = 1" + BS + "\n")
        code, out = self.run_cli("--min-length", "1")
        self.assertEqual(code, 1)
        self.assertIn("BACKSPACE", out)

    def test_punctuation_only_lines_are_ignored(self):
        self.write("a.md", "-----------------------\n")
        self.write("b.md", "-----------------------" + BS + "\n")
        code, _ = self.run_cli("--min-length", "3")
        self.assertEqual(code, 0, "a ruler line carries no alphanumerics and is not interesting")


class TestOtherInvisibles(Harness):
    def test_nbsp_against_a_real_space_is_caught(self):
        """The commonest look-alike in real text: NBSP renders exactly like a space."""
        self.write("a.py", "the quick brown fox jumps\n")
        self.write("b.py", "the quick brown" + NBSP + "fox jumps\n")
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("NBSP", out)

    def test_nbsp_where_there_was_no_space_is_silent(self):
        """Control. These two are visibly DIFFERENT (one has a gap), so grouping them would be a
        false positive. This is the case that proves NBSP is mapped to a space, not deleted."""
        self.write("a.py", "authorization_header_value_here\n")
        self.write("b.py", "authorization_header" + NBSP + "_value_here\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertNotIn("VARIANT", out)

    def test_zero_width_space_is_caught(self):
        self.write("a.py", "api_key_placeholder_value\n")
        self.write("b.py", "api_key_placeholder" + ZWSP + "_value\n")
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("ZERO-WIDTH-SPACE", out)

    def test_bom_in_the_middle_is_caught(self):
        self.write("a.py", "configuration_key_name = 1\n")
        self.write("b.py", "configuration_key" + BOM + "_name = 1\n")
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("BOM", out)


class TestScopeAndSafety(Harness):
    def test_binary_files_are_skipped(self):
        with open(os.path.join(self.dir, "blob.bin"), "wb") as fh:
            fh.write(bytes([0, 1, 2]) * 128)
        self.write("a.py", "a_long_enough_line_here\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)

    def test_exclude_glob(self):
        line = "shared_constant_value_x"
        self.write("a.py", line + "\n")
        self.write("vendor.py", line + BS + "\n")
        code, _ = self.run_cli()
        self.assertEqual(code, 1)
        code, _ = self.run_cli("--exclude", "vendor.py")
        self.assertEqual(code, 0)

    def test_collateignore_file(self):
        line = "shared_constant_value_x"
        self.write("a.py", line + "\n")
        self.write("vendor.py", line + BS + "\n")
        self.write(".collateignore", "vendor.py\n")
        code, _ = self.run_cli()
        self.assertEqual(code, 0)

    def test_three_copies_majority_first(self):
        line = "the_shared_line_of_interest"
        self.write("a.py", line + "\n")
        self.write("b.py", line + "\n")
        self.write("c.py", line + BS + "\n")
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertLess(out.index("form 1"), out.index("form 2"))
        self.assertIn("3 witnesses", out)


class TestMachineOutput(Harness):
    def test_json_valid_and_carries_finding(self):
        line = "the_shared_line_of_interest"
        self.write("a.py", line + "\n")
        self.write("b.py", line + BS + "\n")
        code, out = self.run_cli("--json")
        self.assertEqual(code, 1)
        doc = json.loads(out)
        self.assertEqual(doc["summary"]["variants"], 1)
        self.assertIn("BACKSPACE", json.dumps(doc))

    def test_preview_never_blank(self):
        self.assertEqual(collator.preview("a" + BS + "b"), "a<BACKSPACE>b")


class TestReconcileGuards(Harness):
    """Road D's action path. Detection here is a HEURISTIC, so a false positive becomes data loss.
    These tests are almost entirely about the guards refusing, which is the point of the road."""

    def _pair(self):
        line = "const AIT_KEY = /x_marks_the_spot/;"
        a = self.write("canon.js", line + "\n")
        b = self.write("copy.js", line.replace("spot", "spot" + BS) + "\n")
        return a, b, line

    def test_write_requires_canon(self):
        self._pair()
        code, _ = self.run_cli("--write")
        self.assertEqual(code, 2)

    def test_write_requires_only_because_grouping_is_a_heuristic(self):
        a, b, line = self._pair()
        code, _ = self.run_cli("--canon", a, "--write")
        self.assertEqual(code, 2, "a lossy key may propose; only a human may accept")

    def test_dry_run_changes_nothing(self):
        a, b, line = self._pair()
        code, out = self.run_cli("--canon", a, "--only", "1")
        self.assertIn("would write", out)
        with io.open(b, encoding="utf-8") as fh:
            self.assertIn(BS, fh.read())

    def test_write_with_explicit_group_reconciles_and_backs_up(self):
        a, b, line = self._pair()
        code, out = self.run_cli("--canon", a, "--only", "1", "--write")
        self.assertIn("WROTE", out)
        with io.open(b, encoding="utf-8") as fh:
            self.assertNotIn(BS, fh.read())
        self.assertTrue(os.path.exists(b + ".collate-bak"))

    def test_write_preserves_indentation(self):
        line = "const AIT_KEY = /x_marks_the_spot/;"
        a = self.write("canon.js", line + "\n")
        b = self.write("copy.js", "        " + line.replace("spot", "spot" + BS) + "\n")
        code, _ = self.run_cli("--canon", a, "--only", "1", "--write")
        with io.open(b, encoding="utf-8") as fh:
            after = fh.read()
        self.assertTrue(after.startswith("        "), "original indentation must survive")
        self.assertNotIn(BS, after)

    def test_refuses_a_canon_carrying_the_defect(self):
        line = "const AIT_KEY = /x_marks_the_spot/;"
        bad = self.write("canon.js", line.replace("spot", "spot" + BS) + "\n")
        self.write("copy.js", line + "\n")
        code, out = self.run_cli("--canon", bad, "--only", "1", "--write")
        self.assertIn("REFUSED", out)
        self.assertEqual(code, 1)
        with io.open(os.path.join(self.dir, "copy.js"), encoding="utf-8") as fh:
            self.assertNotIn(BS, fh.read(), "the clean copy must not be infected")

    def test_unselected_groups_are_untouched(self):
        """The --only guard must actually scope the write, not merely gate it."""
        one = "first_shared_line_of_interest"
        two = "second_shared_line_of_interest"
        self.write("canon.js", one + "\n" + two + "\n")
        b = self.write("copy.js", one + BS + "\n" + two + BS + "\n")
        code, out = self.run_cli("--canon", os.path.join(self.dir, "canon.js"),
                                 "--only", "1", "--write")
        with io.open(b, encoding="utf-8") as fh:
            after = fh.read()
        self.assertEqual(after.count(BS), 1, "exactly one of the two groups should have been fixed")

    def test_canon_with_no_witness_in_the_group_is_refused(self):
        a, b, line = self._pair()
        other = self.write("unrelated.js", "a completely different line here\n")
        code, out = self.run_cli("--canon", other, "--only", "1", "--write")
        self.assertIn("REFUSED", out)

    def test_backup_is_never_scanned(self):
        a, b, line = self._pair()
        self.run_cli("--canon", a, "--only", "1", "--write")
        bak = b + ".collate-bak"
        with io.open(bak, encoding="utf-8") as fh:
            before = fh.read()
        self.run_cli("--canon", a, "--only", "1", "--write")
        with io.open(bak, encoding="utf-8") as fh:
            self.assertEqual(before, fh.read(), "the backup must survive a second run intact")


class TestTheHazardThisRoadCarries(Harness):
    """The reason road D is documented as the dangerous road. Not hypothetical: this exact shape
    existed twice on this machine on the day it was written."""

    def test_a_deliberate_fixture_pair_is_grouped_and_would_be_destroyed(self):
        """A fixture that is SUPPOSED to contain a hidden byte, beside the clean text it is
        compared against, is indistinguishable from a defect to a lossy key."""
        clean = self.write("expected_clean.txt", "const K = /x_marks_the_spot/;\n")
        fixture = self.write("fixture_with_defect.js", "const K = /x_marks_the_spot" + BS + "/;\n")
        code, out = self.run_cli()
        self.assertEqual(code, 1, "discovery correctly groups them; it cannot know the intent")
        code, out = self.run_cli("--canon", clean, "--only", "1", "--write")
        with io.open(fixture, encoding="utf-8") as fh:
            self.assertNotIn(BS, fh.read())
        # The fixture is now destroyed. That is the documented hazard, and the reason --only exists:
        # without a human accepting group 1, this write is unreachable.

    def test_and_the_guard_is_what_stands_between(self):
        clean = self.write("expected_clean.txt", "const K = /x_marks_the_spot/;\n")
        fixture = self.write("fixture_with_defect.js", "const K = /x_marks_the_spot" + BS + "/;\n")
        code, _ = self.run_cli("--canon", clean, "--write")
        self.assertEqual(code, 2, "without --only the destructive path is simply unreachable")
        with io.open(fixture, encoding="utf-8") as fh:
            self.assertIn(BS, fh.read(), "fixture intact")


class TestUsage(unittest.TestCase):
    def test_missing_path_exits_two(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = collator.main([os.path.join(tempfile.gettempdir(), "nope-xyz-123")])
        self.assertEqual(code, 2)

    def test_bad_min_length_exits_two(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = collator.main([tempfile.gettempdir(), "--min-length", "0"])
        self.assertEqual(code, 2)

    def test_tab_is_not_invisible(self):
        """Road A shipped this bug; road C must not inherit it."""
        self.assertFalse(collator.is_invisible(0x09))
        self.assertFalse(collator.is_invisible(0x0A))
        self.assertTrue(collator.is_invisible(0x08))

    def test_strip_invisibles_leaves_ordinary_text_alone(self):
        self.assertEqual(collator.strip_invisibles("hello\tworld"), "hello\tworld")
        self.assertEqual(collator.strip_invisibles("hel" + BS + "lo"), "hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)
