#!/usr/bin/env python3
"""VariantCollator v1-C - discovery, report only.

Road A finds disagreement between copies you DECLARED. This road finds it in copies you never knew
existed, which is the case that actually bites: nobody writes a config entry for a regex they are
about to transcribe by hand an hour later.

HOW IT WORKS, stated plainly because the method is the whole claim:

  1. Every line of every text file is a candidate witness, stripped of leading and trailing
     whitespace so that re-indented copies are not treated as different.
  2. Two witnesses belong to the same GROUP when they are identical AFTER every non-rendering
     character is removed. That is a deliberately LOSSY key.
  3. A group is a VARIANT when its members are not identical BEFORE that removal.

So the tool reports exactly one thing: text that looks the same and is not. It is silent about
lines that merely differ, because those are visible to any diff, and silent about lines that agree,
because there is nothing to say.

The unit is the line rather than the parsed literal on purpose: a line needs no knowledge of any
language, so a regex in a .js, the same regex quoted in a .py test, and the same regex again in a
README are all comparable in one pass. The cost is stated in the README.

Exit codes:  0 = no variants   1 = at least one VARIANT   2 = usage / no input

stdlib only. Cross-platform. Author: bram (AIT loop, 2026-09-05).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import unicodedata

NAMED = {
    0x00: "NUL", 0x07: "BEL", 0x08: "BACKSPACE", 0x0B: "VTAB", 0x0C: "FORMFEED",
    0x1B: "ESC", 0x7F: "DEL", 0xA0: "NBSP", 0xAD: "SOFT-HYPHEN",
    0x200B: "ZERO-WIDTH-SPACE", 0x200C: "ZWNJ", 0x200D: "ZWJ", 0x2060: "WORD-JOINER",
    0xFEFF: "BOM", 0x202A: "LRE", 0x202B: "RLE", 0x202D: "LRO", 0x202E: "RLO",
    0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI", 0x2069: "PDI",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}
DEFAULT_MIN = 12


def is_invisible(cp: int) -> bool:
    """True when the codepoint does not render as itself in an ordinary editor or terminal.

    Tab, newline and carriage return are exempted FIRST and unconditionally, because the trailing
    Unicode-category test would otherwise catch them again (the category of TAB is 'Cc') and undo
    the exemption. That ordering bug was real in road A and is fixed here by construction.
    """
    if cp in (0x09, 0x0A, 0x0D):
        return False
    if cp in NAMED:
        return True
    if cp < 0x20:
        return True
    return unicodedata.category(chr(cp)) in ("Cf", "Cc")


def describe(cp: int) -> str:
    return NAMED.get(cp) or unicodedata.name(chr(cp), "U+%04X" % cp)


def strip_invisibles(text: str) -> str:
    """The lossy grouping key: what this text LOOKS like.

    Two classes, and conflating them was a real defect caught in test:

      * zero-width and control characters render as NOTHING, so they are REMOVED.
      * space-like characters (NBSP and the rest of Unicode category Zs) render as a SPACE, so they
        are MAPPED TO ONE, not removed. Removing them meant `hello<NBSP>world` keyed as
        `helloworld`, which never met `hello world` in a group, and the single most common
        look-alike in real text was silently missed by the tool built to find look-alikes.
    """
    out = []
    for ch in text:
        cp = ord(ch)
        if cp in (0x09, 0x0A, 0x0D):
            out.append(ch)
        elif cp != 0x20 and unicodedata.category(ch) == "Zs":
            out.append(" ")
        elif is_invisible(cp):
            continue
        else:
            out.append(ch)
    return "".join(out)


def invisibles_in(text: str):
    return [{"offset": i, "codepoint": "U+%04X" % ord(ch), "name": describe(ord(ch))}
            for i, ch in enumerate(text) if is_invisible(ord(ch))]


def preview(text: str, width: int = 100) -> str:
    """Render for humans: every invisible becomes a visible token, so a report is never a blank."""
    out = []
    for ch in text:
        cp = ord(ch)
        out.append("<%s>" % describe(cp) if is_invisible(cp) else ch)
    s = "".join(out)
    return s if len(s) <= width else s[: width - 3] + "..."


class Witness:
    __slots__ = ("path", "line", "text")

    def __init__(self, path: str, line: int, text: str) -> None:
        self.path, self.line, self.text = path, line, text

    def loc(self) -> str:
        return "%s:%d" % (self.path, self.line)


def read_text(path: str):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def interesting(stripped: str, min_len: int) -> bool:
    """Filter the noise floor: too short, or no letters/digits at all (pure punctuation, rulers)."""
    if len(stripped) < min_len:
        return False
    return any(ch.isalnum() for ch in stripped)


def excluded(path: str, patterns) -> bool:
    if not patterns:
        return False
    posix = path.replace(os.sep, "/")
    base = os.path.basename(path)
    return any(fnmatch.fnmatch(posix, p) or fnmatch.fnmatch(base, p) or fnmatch.fnmatch(path, p)
               for p in patterns)


def load_ignore_file(roots):
    pats = []
    for root in roots:
        d = root if os.path.isdir(root) else os.path.dirname(root) or "."
        f = os.path.join(d, ".collateignore")
        if os.path.isfile(f):
            for line in (read_text(f) or "").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    pats.append(line)
    return pats


def walk(roots, excludes=()):
    for root in roots:
        if os.path.isfile(root):
            if not excluded(root, excludes):
                yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not excluded(os.path.join(dirpath, d), excludes)]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                if not excluded(p, excludes):
                    yield p


def discover(paths, min_len, excludes=()):
    """Bucket every interesting line by its invisible-stripped form."""
    groups = {}
    scanned = 0
    for f in walk(paths, excludes):
        text = read_text(f)
        if text is None:
            continue
        scanned += 1
        for n, raw_line in enumerate(text.splitlines(), 1):
            stripped = raw_line.strip()
            if not interesting(stripped, min_len):
                continue
            groups.setdefault(strip_invisibles(stripped), []).append(Witness(f, n, stripped))
    return groups, scanned


def collate(groups):
    """A group is a VARIANT only when its members differ BEFORE normalisation."""
    verdicts = []
    for key in sorted(groups):
        ws = groups[key]
        forms = {}
        for w in ws:
            forms.setdefault(w.text, []).append(w)
        if len(forms) < 2:
            continue  # identical copies, or a single occurrence: nothing to report
        verdicts.append({
            "looks_like": preview(key),
            "witnesses": len(ws),
            "distinct": len(forms),
            "verdict": "VARIANT",
            "forms": [
                {
                    "bytes": len(text.encode("utf-8")),
                    "locations": [w.loc() for w in group],
                    "invisibles": invisibles_in(text),
                    "preview": preview(text),
                }
                for text, group in sorted(forms.items(), key=lambda kv: -len(kv[1]))
            ],
        })
    return verdicts


def render(verdicts, scanned, as_json: bool) -> int:
    if as_json:
        json.dump({"verdicts": verdicts,
                   "summary": {"files_scanned": scanned, "variants": len(verdicts)}},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1 if verdicts else 0
    for v in verdicts:
        print("VARIANT  %d witnesses, %d distinct forms, identical once invisibles are removed"
              % (v["witnesses"], v["distinct"]))
        print("    looks like:  %s" % v["looks_like"])
        for i, form in enumerate(v["forms"], 1):
            print("    form %d  (%d bytes)  %s" % (i, form["bytes"], ", ".join(form["locations"])))
            print("        %s" % form["preview"])
            for inv in form["invisibles"]:
                print("        ^ offset %d  %s %s" % (inv["offset"], inv["codepoint"], inv["name"]))
    print("\n%d file(s) scanned, %d variant(s)" % (scanned, len(verdicts)))
    if not verdicts:
        print("no text that looks the same while differing in bytes")
    return 1 if verdicts else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="collator",
        description="Discover text that looks identical across files but is not, byte for byte.")
    ap.add_argument("paths", nargs="*", default=["."], help="files or directories (default: .)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--min-length", type=int, default=DEFAULT_MIN, metavar="N",
                    help="ignore lines shorter than N characters (default %d)" % DEFAULT_MIN)
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="skip paths matching GLOB (repeatable); .collateignore is read too")
    args = ap.parse_args(argv)
    paths = args.paths or ["."]
    for p in paths:
        if not os.path.exists(p):
            print("no such path: %s" % p, file=sys.stderr)
            return 2
    if args.min_length < 1:
        print("--min-length must be 1 or more", file=sys.stderr)
        return 2
    excludes = list(args.exclude) + load_ignore_file(paths)
    groups, scanned = discover(paths, args.min_length, excludes)
    return render(collate(groups), scanned, args.json)


if __name__ == "__main__":
    sys.exit(main())
