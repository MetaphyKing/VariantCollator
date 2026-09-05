#!/usr/bin/env python3
"""VariantCollator v1-A - declared canon, report only.

A literal that lives in more than one place can diverge, and when the differing byte does not
render, every tool you would review it with hides the difference. This tool treats the copies as
WITNESSES to one text and reports whether they agree.

Road A is the conservative design: you DECLARE what is guarded, with region markers in the files
themselves. No guessing, no false positives, and no knowledge of any language is required, because
the tool never parses one - it compares bytes between two markers.

    # collate:begin AIT_KEY     collate:ignore  <- documentation, not a live marker
    const AIT_KEY = /\\[AIT-(NEXT|CONTINUE)/;
    # collate:end AIT_KEY       collate:ignore

The marker may be inside a comment in any language, or in prose. Only the bytes BETWEEN the marker
lines are the witness.

Note the `collate:ignore` above: a file that DOCUMENTS the syntax contains look-alike markers, and
this tool's own source is the first such file. Found by running it on a folder containing itself.

Exit codes:  0 = every declared name agrees   1 = at least one VARIANT   2 = usage / no input

stdlib only. Cross-platform. Author: bram (AIT loop, 2026-09-05).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import unicodedata

BEGIN = "collate:begin"
END = "collate:end"
IGNORE = "collate:ignore"

# A marker name must look like a name. Without this, any line that merely MENTIONS the marker
# string is read as a marker: the beta run on a clean folder parsed this file's own
# `BEGIN = "collate:begin"` constant into a region called '"'. Found by running the tool on a
# directory containing the tool, which is the first thing any real user does.
NAME_OK = re.compile(r"^[A-Za-z0-9_.:-]+$")

# Characters that carry meaning but render as nothing (or as something else). The tool holds NO
# opinion about whether these are bad - it names them so a reported difference is readable.
NAMED = {
    0x00: "NUL", 0x07: "BEL", 0x08: "BACKSPACE", 0x0B: "VTAB", 0x0C: "FORMFEED",
    0x1B: "ESC", 0x7F: "DEL", 0xA0: "NBSP", 0xAD: "SOFT-HYPHEN",
    0x200B: "ZERO-WIDTH-SPACE", 0x200C: "ZWNJ", 0x200D: "ZWJ", 0x2060: "WORD-JOINER",
    0xFEFF: "BOM", 0x202A: "LRE", 0x202B: "RLE", 0x202D: "LRO", 0x202E: "RLO",
    0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI", 0x2069: "PDI",
}


def is_invisible(cp: int) -> bool:
    """True when the codepoint does not render as itself in an ordinary editor or terminal.

    Tab, newline and carriage return are exempted FIRST and unconditionally. They were originally
    exempted in the middle clause, and the trailing Unicode-category check then caught them again
    (category of TAB is 'Cc'), so the exemption was silently undone by the line below it and every
    indented witness would have been reported as carrying an invisible. Caught by
    test_is_invisible_agrees_with_itself_on_ordinary_text. The order of these clauses is the fix.
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


class Witness:
    """One occurrence of a declared name, and the exact bytes found there."""

    __slots__ = ("name", "path", "line", "text")

    def __init__(self, name: str, path: str, line: int, text: str) -> None:
        self.name, self.path, self.line, self.text = name, path, line, text

    @property
    def raw(self) -> bytes:
        return self.text.encode("utf-8")

    def loc(self) -> str:
        return "%s:%d" % (self.path, self.line)


def marker_name(line: str, marker: str) -> str:
    """The token after a marker, with any trailing comment punctuation removed.

    Returns '' when there is nothing name-shaped there, which the caller treats as 'not a marker'.
    """
    tail = line.split(marker, 1)[1].strip()
    if not tail:
        return ""
    token = tail.split()[0]
    return token.rstrip("*/-#>)]}").strip()


def read_text(path: str):
    """Return the file's text, or None when it is not decodable text."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None  # binary
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def extract(path: str):
    """Pull every declared region out of one file. Unclosed regions are reported, never guessed."""
    text = read_text(path)
    if text is None:
        return [], []
    out, errors, open_name, buf, start = [], [], None, [], 0
    for n, line in enumerate(text.splitlines(), 1):
        # A line that documents the syntax opts out. Documentation is the single biggest source of
        # look-alike markers, starting with this tool's own README.
        if IGNORE in line:
            if open_name is not None:
                buf.append(line)
            continue
        if BEGIN in line and NAME_OK.match(marker_name(line, BEGIN)):
            if open_name is not None:
                errors.append("%s:%d nested %s inside open %r" % (path, n, BEGIN, open_name))
            open_name, buf, start = marker_name(line, BEGIN), [], n
        elif END in line and NAME_OK.match(marker_name(line, END)):
            closing = marker_name(line, END)
            if open_name is None:
                errors.append("%s:%d %s %r with no open region" % (path, n, END, closing))
            elif closing != open_name:
                errors.append("%s:%d %s %r closes %r" % (path, n, END, closing, open_name))
                open_name = None
            else:
                out.append(Witness(open_name, path, start, "\n".join(buf)))
                open_name = None
        elif open_name is not None:
            buf.append(line)
    if open_name is not None:
        errors.append("%s:%d region %r never closed" % (path, start, open_name))
    return out, errors


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}


def excluded(path: str, patterns) -> bool:
    """True when a path matches any exclude glob, tested against both the raw and posix form."""
    if not patterns:
        return False
    posix = path.replace(os.sep, "/")
    base = os.path.basename(path)
    for pat in patterns:
        if fnmatch.fnmatch(posix, pat) or fnmatch.fnmatch(base, pat) or fnmatch.fnmatch(path, pat):
            return True
    return False


def load_ignore_file(roots):
    """Read `.collateignore` (one glob per line, # comments) from any root directory given."""
    pats = []
    for root in roots:
        d = root if os.path.isdir(root) else os.path.dirname(root) or "."
        f = os.path.join(d, ".collateignore")
        if not os.path.isfile(f):
            continue
        txt = read_text(f) or ""
        for line in txt.splitlines():
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


def collate(witnesses):
    """Group witnesses by declared name and decide AGREE or VARIANT for each."""
    groups = {}
    for w in witnesses:
        groups.setdefault(w.name, []).append(w)
    verdicts = []
    for name in sorted(groups):
        ws = groups[name]
        distinct = {}
        for w in ws:
            distinct.setdefault(w.raw, []).append(w)
        # UNPAIRED was not in the frozen design; it was added during build because a declared name
        # with a single witness has nothing to compare and therefore protects nothing, while looking
        # exactly like a name that passed. A guard that cannot fail is the defect this tool exists
        # for, so it must not render as AGREE.
        if len(ws) == 1:
            verdict = "UNPAIRED"
        elif len(distinct) == 1:
            verdict = "AGREE"
        else:
            verdict = "VARIANT"
        verdicts.append({
            "name": name,
            "verdict": verdict,
            "witnesses": len(ws),
            "distinct": len(distinct),
            "forms": [
                {
                    "bytes": len(raw),
                    "locations": [w.loc() for w in group],
                    "invisibles": invisibles_in(group[0].text),
                    "preview": preview(group[0].text),
                }
                for raw, group in sorted(distinct.items(), key=lambda kv: -len(kv[1]))
            ],
        })
    return verdicts


def invisibles_in(text: str):
    found = []
    for i, ch in enumerate(text):
        if is_invisible(ord(ch)):
            found.append({"offset": i, "codepoint": "U+%04X" % ord(ch), "name": describe(ord(ch))})
    return found


def preview(text: str, width: int = 96) -> str:
    """Render for humans: every invisible becomes a visible token, so a report is never a blank."""
    out = []
    for ch in text:
        cp = ord(ch)
        out.append("<%s>" % describe(cp) if is_invisible(cp) else ch)
    s = "".join(out).replace("\n", " / ")
    return s if len(s) <= width else s[: width - 3] + "..."


def render(verdicts, errors, as_json: bool, strict: bool = False) -> int:
    variants = [v for v in verdicts if v["verdict"] == "VARIANT"]
    unpaired = [v for v in verdicts if v["verdict"] == "UNPAIRED"]
    if as_json:
        json.dump({"verdicts": verdicts, "errors": errors,
                   "summary": {"names": len(verdicts), "variants": len(variants),
                               "unpaired": len(unpaired)}},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for e in errors:
            print("ERROR  %s" % e)
        for v in verdicts:
            if v["verdict"] == "AGREE":
                print("AGREE    %-28s %d witnesses, identical" % (v["name"], v["witnesses"]))
                continue
            if v["verdict"] == "UNPAIRED":
                print("UNPAIRED %-28s only 1 witness (%s) - nothing to compare, so this name is "
                      "not guarded" % (v["name"], v["forms"][0]["locations"][0]))
                continue
            print("VARIANT  %-28s %d witnesses, %d distinct forms"
                  % (v["name"], v["witnesses"], v["distinct"]))
            for i, form in enumerate(v["forms"], 1):
                print("    form %d  (%d bytes)  %s" % (i, form["bytes"], ", ".join(form["locations"])))
                print("        %s" % form["preview"])
                for inv in form["invisibles"]:
                    print("        ^ offset %d  %s %s" % (inv["offset"], inv["codepoint"], inv["name"]))
        if not verdicts:
            print("no declared regions found (mark them with %s NAME / %s NAME)" % (BEGIN, END))
        print("\n%d name(s), %d variant(s), %d unpaired"
              % (len(verdicts), len(variants), len(unpaired)))
    if variants:
        return 1
    return 1 if (strict and unpaired) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="collator",
        description="Collate declared literals across files and report byte-level disagreement.")
    ap.add_argument("paths", nargs="*", default=["."], help="files or directories (default: .)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true",
                    help="also fail (exit 1) when a declared name has only one witness")
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="skip paths matching GLOB (repeatable); .collateignore is read too")
    args = ap.parse_args(argv)
    paths = args.paths or ["."]
    for p in paths:
        if not os.path.exists(p):
            print("no such path: %s" % p, file=sys.stderr)
            return 2
    excludes = list(args.exclude) + load_ignore_file(paths)
    witnesses, errors = [], []
    for f in walk(paths, excludes):
        w, e = extract(f)
        witnesses.extend(w)
        errors.extend(e)
    return render(collate(witnesses), errors, args.json, args.strict)


if __name__ == "__main__":
    sys.exit(main())
