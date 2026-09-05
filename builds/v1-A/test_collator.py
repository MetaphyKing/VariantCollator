#!/usr/bin/env python3
"""Tests for VariantCollator v1-A.

Written with the code, not after it. The suite is deliberately built so that a BROKEN tool cannot
pass it: every positive case is paired with a negative control, because a detector that has only
ever seen positives is untested. The motivating case is first - a backspace inside a regex, the
exact byte that made a real 11/11 fixture run meaningless on 2026-09-05.

Run:  python test_collator.py        (stdlib unittest, no dependencies)
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

BS = chr(8)          # the byte that started all of this
NBSP = chr(0xA0)
ZWSP = chr(0x200B)


class Harness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="collate-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, body):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(name) else None
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        return path

    def region(self, name, body):
        return "// collate:begin %s\n%s\n// collate:end %s\n" % (name, body, name)

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = collator.main([self.dir] + list(args))
        return code, buf.getvalue()


class TestTheMotivatingDefect(Harness):
    def test_backspace_inside_a_regex_is_caught_and_named(self):
        """The real one. Two copies that render identically; one carries U+0008."""
        clean = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        dirty = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)%s/;" % BS
        self.write("relay.js", self.region("AIT_KEY", clean))
        self.write("fixture.js", self.region("AIT_KEY", dirty))
        code, out = self.run_cli()
        self.assertEqual(code, 1, "a real divergence must fail the run")
        self.assertIn("VARIANT", out)
        self.assertIn("BACKSPACE", out, "the invisible byte must be NAMED, not just counted")

    def test_the_negative_control_identical_copies_agree(self):
        """Same text, both files. If this fails, the VARIANT above proves nothing."""
        same = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        self.write("relay.js", self.region("AIT_KEY", same))
        self.write("fixture.js", self.region("AIT_KEY", same))
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("AGREE", out)
        self.assertNotIn("VARIANT", out)


class TestOtherInvisibles(Harness):
    def test_nbsp_against_a_real_space(self):
        self.write("a.md", self.region("GREETING", "hello world"))
        self.write("b.md", self.region("GREETING", "hello%sworld" % NBSP))
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("NBSP", out)

    def test_zero_width_space(self):
        self.write("a.py", self.region("TOKEN", "api-key-placeholder"))
        self.write("b.py", self.region("TOKEN", "api-key%splaceholder" % ZWSP))
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("ZERO-WIDTH-SPACE", out)

    def test_visible_difference_is_still_a_variant(self):
        """The tool is not only about invisibles; ordinary disagreement must report too."""
        self.write("a.txt", self.region("N", "timeout = 30"))
        self.write("b.txt", self.region("N", "timeout = 60"))
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("VARIANT", out)


class TestUnpaired(Harness):
    def test_single_witness_is_unpaired_not_agree(self):
        """A guard with nothing to compare protects nothing and must not read as a pass."""
        self.write("only.js", self.region("LONELY", "value"))
        code, out = self.run_cli()
        self.assertEqual(code, 0, "unpaired is a warning by default, not a failure")
        self.assertIn("UNPAIRED", out)
        self.assertNotIn("AGREE", out)

    def test_strict_makes_unpaired_fail(self):
        self.write("only.js", self.region("LONELY", "value"))
        code, _ = self.run_cli("--strict")
        self.assertEqual(code, 1)

    def test_strict_does_not_invent_failure_when_everything_pairs(self):
        same = "value"
        self.write("a.js", self.region("PAIRED", same))
        self.write("b.js", self.region("PAIRED", same))
        code, _ = self.run_cli("--strict")
        self.assertEqual(code, 0)


class TestMalformedInput(Harness):
    def test_unclosed_region_is_reported_not_guessed(self):
        self.write("bad.js", "// collate:begin OPEN\nsome text\n")
        code, out = self.run_cli()
        self.assertIn("never closed", out)

    def test_mismatched_end_name_is_reported(self):
        self.write("bad.js", "// collate:begin A\nx\n// collate:end B\n")
        code, out = self.run_cli()
        self.assertIn("closes", out)

    def test_end_with_no_begin_is_reported(self):
        self.write("bad.js", "// collate:end ORPHAN\n")
        code, out = self.run_cli()
        self.assertIn("no open region", out)


class TestScopeAndSafety(Harness):
    def test_binary_files_are_skipped_not_crashed_on(self):
        path = os.path.join(self.dir, "blob.bin")
        with open(path, "wb") as fh:
            fh.write(bytes([0, 1, 2, 3]) * 64)
        same = "v"
        self.write("a.js", self.region("K", same))
        self.write("b.js", self.region("K", same))
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("AGREE", out)

    def test_distinct_names_do_not_cross_contaminate(self):
        """Two unrelated guarded values, each internally consistent, must both pass."""
        self.write("a.js", self.region("ONE", "alpha") + self.region("TWO", "beta"))
        self.write("b.js", self.region("ONE", "alpha") + self.region("TWO", "beta"))
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertNotIn("VARIANT", out)

    def test_three_witnesses_majority_form_is_listed_first(self):
        same = "keep"
        self.write("a.js", self.region("M", same))
        self.write("b.js", self.region("M", same))
        self.write("c.js", self.region("M", "keep%s" % BS))
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        first = out.index("form 1")
        second = out.index("form 2")
        self.assertLess(first, second)
        self.assertIn("2 distinct forms", out)

    def test_no_regions_at_all_is_a_clean_exit(self):
        self.write("plain.txt", "nothing marked here\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("no declared regions", out)


class TestMachineOutput(Harness):
    def test_json_is_valid_and_carries_the_finding(self):
        self.write("a.js", self.region("K", "x"))
        self.write("b.js", self.region("K", "x%s" % BS))
        code, out = self.run_cli("--json")
        self.assertEqual(code, 1)
        doc = json.loads(out)
        self.assertEqual(doc["summary"]["variants"], 1)
        names = [v["name"] for v in doc["verdicts"]]
        self.assertIn("K", names)
        blob = json.dumps(doc)
        self.assertIn("BACKSPACE", blob)

    def test_preview_never_renders_an_invisible_as_nothing(self):
        """The whole point: a report of this defect must not itself be blank."""
        self.assertEqual(collator.preview("a%sb" % BS), "a<BACKSPACE>b")
        self.assertNotIn(BS, collator.preview("a%sb" % BS))


class TestSelfReference(Harness):
    """Found by the beta run: the tool matched its own documentation and its own constants.

    Any repository that DOCUMENTS the marker syntax contains look-alike markers, starting with this
    tool's own README. These are the fixes for that, each with a control proving the fix did not
    simply disable detection.
    """

    def test_a_constant_definition_is_not_a_marker(self):
        """`BEGIN = "collate:begin"` parsed into a region named '"' during beta."""
        self.write("consts.py", 'BEGIN = "collate:begin"\nEND = "collate:end"\n')
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertNotIn('"', out.replace("witnesses", ""))
        self.assertIn("no declared regions", out)

    def test_ignore_marker_suppresses_a_documentation_example(self):
        doc = ("Mark it like this:  // collate:begin NAME   collate:ignore\n"
               "and close it:       // collate:end NAME     collate:ignore\n")
        self.write("README.md", doc)
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("no declared regions", out)

    def test_control_a_real_marker_without_ignore_is_still_found(self):
        """If the ignore mechanism swallowed everything, the test above would prove nothing."""
        self.write("a.js", self.region("REAL", "v"))
        self.write("b.js", self.region("REAL", "v"))
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("AGREE", out)

    def test_exclude_glob_skips_a_file(self):
        self.write("a.js", self.region("K", "v"))
        self.write("docs.md", self.region("K", "DIFFERENT"))
        code, _ = self.run_cli()
        self.assertEqual(code, 1, "without the exclude this is a genuine variant")
        code, out = self.run_cli("--exclude", "*.md")
        self.assertEqual(code, 0, "excluding the doc leaves one witness")
        self.assertIn("UNPAIRED", out)

    def test_collateignore_file_is_honoured(self):
        self.write("a.js", self.region("K", "v"))
        self.write("docs.md", self.region("K", "DIFFERENT"))
        self.write(".collateignore", "# comment line\n*.md\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("UNPAIRED", out)

    def test_exclude_that_matches_nothing_does_not_hide_a_variant(self):
        self.write("a.js", self.region("K", "v"))
        self.write("b.js", self.region("K", "w"))
        code, _ = self.run_cli("--exclude", "*.nomatch")
        self.assertEqual(code, 1)


class TestUsage(unittest.TestCase):
    def test_missing_path_exits_two(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = collator.main([os.path.join(tempfile.gettempdir(), "definitely-not-here-xyz")])
        self.assertEqual(code, 2)

    def test_is_invisible_agrees_with_itself_on_ordinary_text(self):
        for ch in "abcXYZ019 \t\n":
            self.assertFalse(collator.is_invisible(ord(ch)), repr(ch))
        for cp in (8, 0xA0, 0x200B, 0xFEFF):
            self.assertTrue(collator.is_invisible(cp), hex(cp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
