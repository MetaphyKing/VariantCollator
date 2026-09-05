#!/usr/bin/env python3
"""Tests for VariantCollator v2 (combined).

Carries every case from the four v1 roads plus the ones the combine itself creates: two detectors
sharing one write path, and group numbering that spans both.

The suite is built so a BROKEN tool cannot pass it. Every positive case has a negative control, and
a large share of the discovery tests assert SILENCE, because a detector that reports everything is
not a detector.

Run:  python test_collator.py
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collator  # noqa: E402

BS = chr(8)
NBSP = chr(0xA0)
ZWSP = chr(0x200B)
BOM = chr(0xFEFF)


class Harness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="collate-v2-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, body):
        path = os.path.join(self.dir, name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        return path

    def read(self, name):
        with io.open(os.path.join(self.dir, name), encoding="utf-8") as fh:
            return fh.read()

    def region(self, name, body):
        return "// collate:begin %s\n%s\n// collate:end %s\n" % (name, body, name)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = collator.main([self.dir] + list(args))
        return code, out.getvalue() + err.getvalue()


# ---------------------------------------------------------------- the motivating defect

class TestTheMotivatingDefect(Harness):
    def test_declared_mode_catches_and_names_it(self):
        clean = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        self.write("relay.js", self.region("AIT_KEY", clean))
        self.write("fixture.js", self.region("AIT_KEY", clean + BS))
        code, out = self.run_cli("--mode", "declared")
        self.assertEqual(code, 1)
        self.assertIn("VARIANT", out)
        self.assertIn("BACKSPACE", out)

    def test_discovery_catches_it_with_no_markers_at_all(self):
        line = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        self.write("relay.js", line + "\n")
        self.write("fixture.js", line + BS + "\n")
        code, out = self.run_cli("--mode", "discover")
        self.assertEqual(code, 1)
        self.assertIn("BACKSPACE", out)

    def test_control_identical_copies_agree_in_both_modes(self):
        line = "const AIT_KEY = /[AIT-(NEXT|CONTINUE)/;"
        self.write("relay.js", self.region("AIT_KEY", line))
        self.write("fixture.js", self.region("AIT_KEY", line))
        for mode in ("declared", "discover", "both"):
            code, out = self.run_cli("--mode", mode)
            self.assertEqual(code, 0, mode)
            self.assertNotIn("VARIANT", out, mode)


# ---------------------------------------------------------------- declared detector

class TestDeclared(Harness):
    def test_unpaired_is_not_agree(self):
        self.write("only.js", self.region("LONELY", "value"))
        code, out = self.run_cli("--mode", "declared")
        self.assertEqual(code, 0)
        self.assertIn("UNPAIRED", out)
        self.assertNotIn("AGREE", out)

    def test_strict_fails_unpaired(self):
        self.write("only.js", self.region("LONELY", "value"))
        code, _ = self.run_cli("--mode", "declared", "--strict")
        self.assertEqual(code, 1)

    def test_strict_does_not_invent_failure(self):
        self.write("a.js", self.region("P", "v"))
        self.write("b.js", self.region("P", "v"))
        code, _ = self.run_cli("--mode", "declared", "--strict")
        self.assertEqual(code, 0)

    def test_unclosed_region_reported(self):
        self.write("bad.js", "// collate:begin OPEN\ntext\n")
        _, out = self.run_cli("--mode", "declared")
        self.assertIn("never closed", out)

    def test_mismatched_end_reported(self):
        self.write("bad.js", "// collate:begin A\nx\n// collate:end B\n")
        _, out = self.run_cli("--mode", "declared")
        self.assertIn("closes", out)

    def test_orphan_end_reported(self):
        self.write("bad.js", "// collate:end ORPHAN\n")
        _, out = self.run_cli("--mode", "declared")
        self.assertIn("no open region", out)

    def test_constant_definition_is_not_a_marker(self):
        self.write("consts.py", 'BEGIN = "collate:begin"\nEND = "collate:end"\n')
        code, out = self.run_cli("--mode", "declared")
        self.assertEqual(code, 0)
        self.assertIn("nothing disagrees", out)

    def test_ignore_suppresses_documentation(self):
        self.write("README.md", "like this: // collate:begin NAME  collate:ignore\n"
                                "and:       // collate:end NAME    collate:ignore\n")
        code, out = self.run_cli("--mode", "declared")
        self.assertEqual(code, 0)
        self.assertIn("nothing disagrees", out)

    def test_control_a_real_marker_is_still_found(self):
        self.write("a.js", self.region("REAL", "v"))
        self.write("b.js", self.region("REAL", "v"))
        code, out = self.run_cli("--mode", "declared")
        self.assertIn("AGREE", out)

    def test_distinct_names_do_not_cross_contaminate(self):
        self.write("a.js", self.region("ONE", "alpha") + self.region("TWO", "beta"))
        self.write("b.js", self.region("ONE", "alpha") + self.region("TWO", "beta"))
        code, out = self.run_cli("--mode", "declared")
        self.assertEqual(code, 0)


# ---------------------------------------------------------------- discovery silence

class TestSilenceIsTheFeature(Harness):
    def test_visible_difference_is_silent_in_discovery(self):
        self.write("a.py", "timeout_seconds = 30\n")
        self.write("b.py", "timeout_seconds = 60\n")
        code, out = self.run_cli("--mode", "discover")
        self.assertEqual(code, 0)

    def test_single_occurrence_is_silent(self):
        self.write("a.py", "a_unique_line_of_code = 1\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 0)

    def test_reindented_copies_are_silent(self):
        self.write("a.py", "    value = compute_the_thing()\n")
        self.write("b.py", "        value = compute_the_thing()\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 0)

    def test_short_lines_below_the_floor(self):
        self.write("a.py", "x = 1\n")
        self.write("b.py", "x = 1" + BS + "\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 0)

    def test_but_min_length_one_catches_it(self):
        self.write("a.py", "x = 1\n")
        self.write("b.py", "x = 1" + BS + "\n")
        code, out = self.run_cli("--mode", "discover", "--min-length", "1")
        self.assertEqual(code, 1)

    def test_punctuation_only_lines_ignored(self):
        self.write("a.md", "-----------------------\n")
        self.write("b.md", "-----------------------" + BS + "\n")
        code, _ = self.run_cli("--mode", "discover", "--min-length", "3")
        self.assertEqual(code, 0)


# ---------------------------------------------------------------- invisibles

class TestInvisibles(Harness):
    def test_nbsp_against_a_real_space_is_caught(self):
        self.write("a.py", "the quick brown fox jumps\n")
        self.write("b.py", "the quick brown" + NBSP + "fox jumps\n")
        code, out = self.run_cli("--mode", "discover")
        self.assertEqual(code, 1)
        self.assertIn("NBSP", out)

    def test_nbsp_where_there_was_no_space_is_silent(self):
        """Control proving NBSP is mapped to a space, not deleted."""
        self.write("a.py", "authorization_header_value_here\n")
        self.write("b.py", "authorization_header" + NBSP + "_value_here\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 0)

    def test_zero_width_space(self):
        self.write("a.py", "api_key_placeholder_value\n")
        self.write("b.py", "api_key_placeholder" + ZWSP + "_value\n")
        code, out = self.run_cli("--mode", "discover")
        self.assertEqual(code, 1)
        self.assertIn("ZERO-WIDTH-SPACE", out)

    def test_bom_mid_line(self):
        self.write("a.py", "configuration_key_name = 1\n")
        self.write("b.py", "configuration_key" + BOM + "_name = 1\n")
        code, out = self.run_cli("--mode", "discover")
        self.assertEqual(code, 1)
        self.assertIn("BOM", out)

    def test_tab_is_not_invisible(self):
        self.assertFalse(collator.is_invisible(0x09))
        self.assertFalse(collator.is_invisible(0x0A))
        self.assertFalse(collator.is_invisible(0x0D))
        self.assertTrue(collator.is_invisible(0x08))
        self.assertTrue(collator.is_invisible(0xFEFF))

    def test_preview_never_blank(self):
        self.assertEqual(collator.preview("a" + BS + "b"), "a<BACKSPACE>b")
        self.assertNotIn(BS, collator.preview("a" + BS + "b"))

    def test_look_alike_key_leaves_ordinary_text_alone(self):
        self.assertEqual(collator.look_alike_key("hello\tworld"), "hello\tworld")
        self.assertEqual(collator.look_alike_key("hel" + BS + "lo"), "hello")
        self.assertEqual(collator.look_alike_key("a" + NBSP + "b"), "a b")


# ---------------------------------------------------------------- reconcile, both detectors

class TestReconcile(Harness):
    def _declared_pair(self):
        clean = "const K = /x_marks_the_spot/;"
        a = self.write("canon.js", self.region("K", clean))
        b = self.write("copy.js", self.region("K", clean + BS))
        return a, b, clean

    def _discovered_pair(self):
        line = "const K = /x_marks_the_spot/;"
        a = self.write("canon.js", line + "\n")
        b = self.write("copy.js", line + BS + "\n")
        return a, b, line

    def test_write_requires_canon(self):
        self._declared_pair()
        code, _ = self.run_cli("--write")
        self.assertEqual(code, 2)

    def test_missing_canon_exits_two(self):
        self._declared_pair()
        code, _ = self.run_cli("--canon", os.path.join(self.dir, "nope.js"))
        self.assertEqual(code, 2)

    def test_dry_run_is_default(self):
        a, b, clean = self._declared_pair()
        code, out = self.run_cli("--mode", "declared", "--canon", a)
        self.assertIn("would write", out)
        self.assertIn(BS, self.read("copy.js"))

    def test_declared_write_needs_no_only_flag(self):
        """Declared detection is exact, so a human already marked the text. No extra gate."""
        a, b, clean = self._declared_pair()
        code, out = self.run_cli("--mode", "declared", "--canon", a, "--write")
        self.assertIn("WROTE", out)
        self.assertNotIn(BS, self.read("copy.js"))

    def test_discovered_write_REQUIRES_only(self):
        """Discovery groups by a lossy key, so a human must accept the grouping."""
        a, b, line = self._discovered_pair()
        code, out = self.run_cli("--mode", "discover", "--canon", a, "--write")
        self.assertEqual(code, 2)
        self.assertIn(BS, self.read("copy.js"), "nothing may be written")

    def test_discovered_write_with_only(self):
        a, b, line = self._discovered_pair()
        code, out = self.run_cli("--mode", "discover", "--canon", a, "--only", "1", "--write")
        self.assertIn("WROTE", out)
        self.assertNotIn(BS, self.read("copy.js"))

    def test_backup_holds_the_original(self):
        a, b, clean = self._declared_pair()
        self.run_cli("--mode", "declared", "--canon", a, "--write")
        self.assertTrue(os.path.exists(b + ".collate-bak"))
        with io.open(b + ".collate-bak", encoding="utf-8") as fh:
            self.assertIn(BS, fh.read())

    def test_backup_is_never_scanned(self):
        """An early build rewrote its own backup on the second run, destroying the undo."""
        a, b, clean = self._declared_pair()
        self.run_cli("--mode", "declared", "--canon", a, "--write")
        bak = b + ".collate-bak"
        with io.open(bak, encoding="utf-8") as fh:
            before = fh.read()
        self.run_cli("--mode", "declared", "--canon", a, "--write")
        with io.open(bak, encoding="utf-8") as fh:
            self.assertEqual(before, fh.read())

    def test_reconcile_is_idempotent(self):
        a, b, clean = self._declared_pair()
        self.run_cli("--mode", "declared", "--canon", a, "--write")
        code, out = self.run_cli("--mode", "declared", "--canon", a, "--write")
        self.assertNotIn("WROTE", out)

    def test_rest_of_file_preserved(self):
        clean = "const K = /x_marks_the_spot/;"
        a = self.write("canon.js", self.region("K", clean))
        self.write("copy.js", "header kept\n" + self.region("K", clean + BS) + "footer kept\n")
        self.run_cli("--mode", "declared", "--canon", a, "--write")
        after = self.read("copy.js")
        self.assertIn("header kept", after)
        self.assertIn("footer kept", after)

    def test_indentation_preserved_on_line_rewrite(self):
        line = "const K = /x_marks_the_spot/;"
        a = self.write("canon.js", line + "\n")
        self.write("copy.js", "        " + line + BS + "\n")
        self.run_cli("--mode", "discover", "--canon", a, "--only", "1", "--write")
        after = self.read("copy.js")
        self.assertTrue(after.startswith("        "))
        self.assertNotIn(BS, after)

    def test_REFUSES_a_canon_carrying_the_defect(self):
        clean = "const K = /x_marks_the_spot/;"
        bad = self.write("canon.js", self.region("K", clean + BS))
        self.write("copy.js", self.region("K", clean))
        code, out = self.run_cli("--mode", "declared", "--canon", bad, "--write")
        self.assertIn("REFUSED", out)
        self.assertIn("BACKSPACE", out)
        self.assertEqual(code, 1)
        self.assertNotIn(BS, self.read("copy.js"), "the clean witness must not be infected")

    def test_the_override_is_explicit_and_does_propagate(self):
        clean = "const K = /x_marks_the_spot/;"
        bad = self.write("canon.js", self.region("K", clean + BS))
        self.write("copy.js", self.region("K", clean))
        code, out = self.run_cli("--mode", "declared", "--canon", bad, "--write",
                                 "--allow-invisible-canon")
        self.assertNotIn("REFUSED", out)
        self.assertIn(BS, self.read("copy.js"))

    def test_canon_with_no_witness_in_group_is_refused(self):
        a, b, clean = self._declared_pair()
        other = self.write("unrelated.js", "nothing marked here at all\n")
        code, out = self.run_cli("--mode", "declared", "--canon", other, "--write")
        self.assertIn("REFUSED", out)

    def test_only_naming_a_missing_group_warns(self):
        """A write request that is silently ignored looks exactly like one that succeeded."""
        a, b, line = self._discovered_pair()
        code, out = self.run_cli("--mode", "discover", "--canon", a, "--only", "99", "--write")
        self.assertIn("WARNING", out)
        self.assertIn("names no group", out)
        self.assertIn(BS, self.read("copy.js"), "and nothing was written")

    def test_control_a_valid_only_does_not_warn(self):
        a, b, line = self._discovered_pair()
        code, out = self.run_cli("--mode", "discover", "--canon", a, "--only", "1", "--write")
        self.assertNotIn("WARNING", out)

    def test_only_scopes_the_write(self):
        one = "first_shared_line_of_interest"
        two = "second_shared_line_of_interest"
        a = self.write("canon.js", one + "\n" + two + "\n")
        self.write("copy.js", one + BS + "\n" + two + BS + "\n")
        self.run_cli("--mode", "discover", "--canon", a, "--only", "1", "--write")
        self.assertEqual(self.read("copy.js").count(BS), 1)


class TestTheHazard(Harness):
    """A deliberate fixture pair is indistinguishable from a defect to a lossy key."""

    def test_fixture_pair_is_grouped_by_discovery(self):
        self.write("expected_clean.txt", "const K = /x_marks_the_spot/;\n")
        self.write("fixture_with_defect.js", "const K = /x_marks_the_spot" + BS + "/;\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 1, "it correctly groups them; it cannot know the intent")

    def test_and_the_only_gate_is_what_stands_between(self):
        clean = self.write("expected_clean.txt", "const K = /x_marks_the_spot/;\n")
        self.write("fixture_with_defect.js", "const K = /x_marks_the_spot" + BS + "/;\n")
        code, _ = self.run_cli("--mode", "discover", "--canon", clean, "--write")
        self.assertEqual(code, 2)
        self.assertIn(BS, self.read("fixture_with_defect.js"), "fixture intact")


# ---------------------------------------------------------------- scope, output, usage

class TestScopeAndOutput(Harness):
    def test_binary_files_skipped(self):
        with open(os.path.join(self.dir, "blob.bin"), "wb") as fh:
            fh.write(bytes([0, 1, 2]) * 128)
        self.write("a.py", "a_long_enough_line_here\n")
        code, _ = self.run_cli()
        self.assertEqual(code, 0)

    def test_exclude_glob(self):
        line = "shared_constant_value_x"
        self.write("a.py", line + "\n")
        self.write("vendor.py", line + BS + "\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 1)
        code, _ = self.run_cli("--mode", "discover", "--exclude", "vendor.py")
        self.assertEqual(code, 0)

    def test_collateignore_file(self):
        line = "shared_constant_value_x"
        self.write("a.py", line + "\n")
        self.write("vendor.py", line + BS + "\n")
        self.write(".collateignore", "# comment\nvendor.py\n")
        code, _ = self.run_cli("--mode", "discover")
        self.assertEqual(code, 0)

    def test_exclude_matching_nothing_hides_nothing(self):
        line = "shared_constant_value_x"
        self.write("a.py", line + "\n")
        self.write("b.py", line + BS + "\n")
        code, _ = self.run_cli("--mode", "discover", "--exclude", "*.nomatch")
        self.assertEqual(code, 1)

    def test_majority_form_first(self):
        line = "the_shared_line_of_interest"
        self.write("a.py", line + "\n")
        self.write("b.py", line + "\n")
        self.write("c.py", line + BS + "\n")
        code, out = self.run_cli("--mode", "discover")
        self.assertLess(out.index("form 1"), out.index("form 2"))
        self.assertIn("3 witnesses", out)

    def test_json_valid_and_carries_finding(self):
        line = "the_shared_line_of_interest"
        self.write("a.py", line + "\n")
        self.write("b.py", line + BS + "\n")
        code, out = self.run_cli("--mode", "discover", "--json")
        self.assertEqual(code, 1)
        doc = json.loads(out)
        self.assertEqual(doc["summary"]["variants"], 1)
        self.assertIn("BACKSPACE", json.dumps(doc))

    def test_both_modes_run_together(self):
        """The combine itself: a declared name and an undeclared line, one invocation."""
        self.write("a.js", self.region("K", "declared_value_here") + "loose_shared_line_here\n")
        self.write("b.js", self.region("K", "declared_value_here" + BS) + "loose_shared_line_here"
                   + BS + "\n")
        code, out = self.run_cli("--mode", "both")
        self.assertEqual(code, 1)
        self.assertGreaterEqual(out.count("VARIANT"), 2, "both detectors should report")

    def test_both_modes_do_not_report_the_same_defect_twice(self):
        """A declared region must not also surface as an anonymous discovered group."""
        clean = "const AIT_KEY = /x_marks_the_spot/;"
        self.write("a.js", self.region("K", clean))
        self.write("b.js", self.region("K", clean + BS))
        code, out = self.run_cli("--mode", "both")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("VARIANT"), 1, "one defect, one report")
        self.assertNotIn("discovered", out)

    def test_but_undeclared_lines_in_the_same_file_are_still_discovered(self):
        """Control: standing clear of declared regions must not blind discovery to the rest."""
        clean = "const AIT_KEY = /x_marks_the_spot/;"
        loose = "another_shared_line_entirely"
        self.write("a.js", self.region("K", clean) + loose + "\n")
        self.write("b.js", self.region("K", clean + BS) + loose + BS + "\n")
        code, out = self.run_cli("--mode", "both")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("VARIANT"), 2)
        self.assertIn("discovered", out)

    def test_nothing_disagrees_is_a_clean_exit(self):
        self.write("plain.txt", "one ordinary line of prose here\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("nothing disagrees", out)


class TestCoverageHonesty(Harness):
    """A file the tool could not open is a hole in coverage. Staying quiet about it means the
    scanned count implies more than was examined, which is the exact shape this tool exposes."""

    def test_unreadable_file_is_named_not_silently_skipped(self):
        self.write("ok.txt", "an ordinary shared line here\n")
        self.write("locked.txt", "another ordinary line here\n")
        real = collator.read_text_reason

        def fake(path):
            if path.endswith("locked.txt"):
                return None, "unreadable: PermissionError"
            return real(path)

        collator.read_text_reason = fake
        try:
            code, out = self.run_cli()
        finally:
            collator.read_text_reason = real
        self.assertIn("could not open", out)
        self.assertIn("locked.txt", out)
        self.assertIn("NOT examined", out)

    def test_binary_files_stay_quiet_because_they_are_out_of_scope(self):
        """Control: the warning must be about coverage holes, not about every skipped file."""
        with open(os.path.join(self.dir, "blob.bin"), "wb") as fh:
            fh.write(bytes([0, 1, 2]) * 128)
        self.write("ok.txt", "an ordinary shared line here\n")
        code, out = self.run_cli()
        self.assertNotIn("could not open", out)


class TestUsage(unittest.TestCase):
    def _run(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = collator.main(args)
        return code, out.getvalue() + err.getvalue()

    def test_missing_path_exits_two(self):
        code, _ = self._run([os.path.join(tempfile.gettempdir(), "nope-xyz-123")])
        self.assertEqual(code, 2)

    def test_bad_min_length_exits_two(self):
        code, _ = self._run([tempfile.gettempdir(), "--min-length", "0"])
        self.assertEqual(code, 2)

    def test_no_traceback_on_any_usage_error(self):
        for args in ([os.path.join(tempfile.gettempdir(), "nope")],
                     [tempfile.gettempdir(), "--min-length", "-5"]):
            code, out = self._run(args)
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
