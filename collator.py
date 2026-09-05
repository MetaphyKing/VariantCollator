#!/usr/bin/env python3
"""VariantCollator v2 - find text that looks identical across your files and is not.

A literal that lives in more than one place can diverge, and when the differing byte does not
render, every tool you would review it with hides the difference. This tool treats the copies as
WITNESSES to one text and reports whether they agree. It holds no opinion about which characters are
good or bad; it reports only that two things claiming to be the same text are not, and it names the
characters that do not print.

TWO DETECTORS, ONE GUARD SET (the shape v2 exists to combine):

  declared   You mark a guarded value with region markers. Detection is EXACT: zero false
             positives, and a write can only ever touch text a human deliberately declared.

  discover   No configuration at all. Every line is a candidate; two lines group when they match
             after invisibles are normalised; a group is a VARIANT when its members differ before
             that normalisation. Detection is LOSSY by design, which is what lets it find copies
             you never knew existed - and why its write path needs a human to accept each group.

Both run by default, because the defect that motivated this tool would never have been declared.

WRITING IS OPTIONAL AND GUARDED. Reporting and editing are different acts, and a tool that silently
repairs a live matcher changes behaviour without saying which behaviour moved. So:
  * no write without --canon (no majority vote, no guessing which copy is right)
  * no write TO a canon that itself carries a non-rendering character, unless you insist
  * no write of a DISCOVERED group without --only naming it (a lossy key may propose; a human
    disposes)
  * dry run is the default, every change is printed, and a .collate-bak sits beside each edit
  * backups are never scanned, because the first version rewrote its own backup on the second run

Exit codes:  0 = nothing to report   1 = a VARIANT or a refusal   2 = usage

stdlib only. Python 3.8+. Windows, macOS, Linux. Author: bram (AIT loop, 2026-09-05).
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
BACKUP_SUFFIX = ".collate-bak"
DEFAULT_MIN = 12

# A marker name must look like a name. Without this, any line that merely MENTIONS the marker string
# is read as a marker: an early build parsed its own `BEGIN = "collate:begin"` constant into a region
# named '"'. Found by running the tool on a folder containing the tool.
NAME_OK = re.compile(r"^[A-Za-z0-9_.:-]+$")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}

NAMED = {
    0x00: "NUL", 0x07: "BEL", 0x08: "BACKSPACE", 0x0B: "VTAB", 0x0C: "FORMFEED",
    0x1B: "ESC", 0x7F: "DEL", 0xA0: "NBSP", 0xAD: "SOFT-HYPHEN",
    0x200B: "ZERO-WIDTH-SPACE", 0x200C: "ZWNJ", 0x200D: "ZWJ", 0x2060: "WORD-JOINER",
    0xFEFF: "BOM", 0x202A: "LRE", 0x202B: "RLE", 0x202D: "LRO", 0x202E: "RLO",
    0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI", 0x2069: "PDI",
}


# ---------------------------------------------------------------- character classification

def is_invisible(cp: int) -> bool:
    """True when the codepoint does not render as itself in an ordinary editor or terminal.

    Tab, newline and carriage return are exempted FIRST and unconditionally. An early build listed
    them in a middle clause and the trailing Unicode-category test caught them again (the category
    of TAB is 'Cc'), silently undoing the exemption. The ORDER of these clauses is the fix.
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


def look_alike_key(text: str) -> str:
    """What this text LOOKS like. Two classes, and conflating them was a real defect:

      * zero-width and control characters render as NOTHING, so they are REMOVED.
      * space-like characters (NBSP and the rest of category Zs) render as a SPACE, so they are
        MAPPED TO ONE. Removing them meant `hello<NBSP>world` keyed as `helloworld`, never met
        `hello world`, and the commonest look-alike in real text was missed by the tool built to
        find look-alikes.
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
    """Render for humans: every invisible becomes a visible token, so a report is never blank."""
    s = "".join("<%s>" % describe(ord(c)) if is_invisible(ord(c)) else c for c in text)
    s = s.replace("\n", " / ")
    return s if len(s) <= width else s[: width - 3] + "..."


# ---------------------------------------------------------------- file access

def read_text_reason(path: str):
    """Return (text, reason). `reason` is None on success, else why the file was not read.

    The two failures are NOT equivalent and must not be reported as one. Binary and non-UTF-8 files
    are out of scope by design, so skipping them is correct and quiet. A file that could not be
    OPENED is a hole in coverage, and staying quiet about it means the tool reports a scanned count
    that implies more than it examined - which is precisely the "looks like success" shape this tool
    exists to expose. So unreadable files are counted and named.
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return None, "unreadable: %s" % e.__class__.__name__
    if b"\x00" in data[:8192]:
        return None, "binary"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "not-utf8"


def read_text(path: str):
    """The file's text, or None when it is not decodable text."""
    return read_text_reason(path)[0]


def excluded(path: str, patterns) -> bool:
    if not patterns:
        return False
    posix = path.replace(os.sep, "/")
    base = os.path.basename(path)
    return any(fnmatch.fnmatch(posix, p) or fnmatch.fnmatch(base, p) or fnmatch.fnmatch(path, p)
               for p in patterns)


def load_ignore_file(roots):
    """`.collateignore`: one glob per line, `#` comments."""
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
    """Yield candidate files. Backups are ALWAYS skipped and that is not configurable: a flag to
    disable it is a flag to corrupt your own backups."""
    for root in roots:
        if os.path.isfile(root):
            if not excluded(root, excludes) and not root.endswith(BACKUP_SUFFIX):
                yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not excluded(os.path.join(dirpath, d), excludes)]
            for fn in filenames:
                if fn.endswith(BACKUP_SUFFIX):
                    continue
                p = os.path.join(dirpath, fn)
                if not excluded(p, excludes):
                    yield p


# ---------------------------------------------------------------- witnesses

class Witness:
    __slots__ = ("name", "path", "line", "text", "kind")

    def __init__(self, name, path, line, text, kind):
        self.name, self.path, self.line, self.text, self.kind = name, path, line, text, kind

    @property
    def raw(self) -> bytes:
        return self.text.encode("utf-8")

    def loc(self) -> str:
        return "%s:%d" % (self.path, self.line)


def marker_name(line: str, marker: str) -> str:
    """The token after a marker, trailing comment punctuation removed. '' means 'not a marker'."""
    tail = line.split(marker, 1)[1].strip()
    if not tail:
        return ""
    return tail.split()[0].rstrip("*/-#>)]}").strip()


def extract_declared(path: str):
    """Every declared region in one file. Malformed regions are reported, never guessed."""
    text = read_text(path)
    if text is None:
        return [], []
    out, errors, open_name, buf, start = [], [], None, [], 0
    for n, line in enumerate(text.splitlines(), 1):
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
                out.append(Witness(open_name, path, start, "\n".join(buf), "declared"))
                open_name = None
        elif open_name is not None:
            buf.append(line)
    if open_name is not None:
        errors.append("%s:%d region %r never closed" % (path, start, open_name))
    return out, errors


def interesting(stripped: str, min_len: int) -> bool:
    """The discovery noise floor: too short, or no letters or digits at all."""
    return len(stripped) >= min_len and any(ch.isalnum() for ch in stripped)


def extract_discovered(path: str, min_len: int, skip_lines=()):
    """Candidate lines for discovery.

    `skip_lines` holds line numbers already inside a DECLARED region. Without it, `--mode both`
    reports the same defect twice - once as the declared name and once as an anonymous discovered
    group - and the second copy adds nothing but noise. Declared regions belong to the declared
    detector; discovery covers everything else.
    """
    text = read_text(path)
    if text is None:
        return []
    out = []
    for n, raw_line in enumerate(text.splitlines(), 1):
        if n in skip_lines:
            continue
        stripped = raw_line.strip()
        if interesting(stripped, min_len):
            out.append(Witness(None, path, n, stripped, "discovered"))
    return out


def declared_line_span(w: Witness):
    """The line numbers a declared region's BODY occupies, so discovery can stand clear of them."""
    if not w.text:
        return set()
    body_lines = w.text.count("\n") + 1
    return set(range(w.line + 1, w.line + 1 + body_lines))


# ---------------------------------------------------------------- collation

def collate_declared(witnesses):
    groups = {}
    for w in witnesses:
        groups.setdefault(w.name, []).append(w)
    verdicts = []
    for name in sorted(groups):
        ws = groups[name]
        forms = {}
        for w in ws:
            forms.setdefault(w.text, []).append(w)
        # UNPAIRED: a declared name with one witness has nothing to compare and therefore protects
        # nothing, while looking exactly like a name that passed. It must not render as AGREE.
        verdict = "UNPAIRED" if len(ws) == 1 else ("AGREE" if len(forms) == 1 else "VARIANT")
        verdicts.append(_verdict(verdict, name, ws, forms, "declared"))
    return verdicts


def collate_discovered(witnesses):
    groups = {}
    for w in witnesses:
        groups.setdefault(look_alike_key(w.text), []).append(w)
    verdicts = []
    for key in sorted(groups):
        ws = groups[key]
        forms = {}
        for w in ws:
            forms.setdefault(w.text, []).append(w)
        if len(forms) < 2:
            continue  # identical copies, or a single occurrence: nothing to say
        verdicts.append(_verdict("VARIANT", preview(key), ws, forms, "discovered"))
    return verdicts


def _verdict(verdict, name, ws, forms, kind):
    return {
        "name": name,
        "kind": kind,
        "verdict": verdict,
        "witnesses": len(ws),
        "distinct": len(forms),
        "forms": [
            {
                "raw": text,
                "bytes": len(text.encode("utf-8")),
                "locations": [w.loc() for w in group],
                "invisibles": invisibles_in(text),
                "preview": preview(text),
            }
            for text, group in sorted(forms.items(), key=lambda kv: -len(kv[1]))
        ],
    }


# ---------------------------------------------------------------- reconcile

def _backup_and_write(path: str, original: str, new_text: str) -> bool:
    if new_text == original:
        return False
    with open(path + BACKUP_SUFFIX, "w", encoding="utf-8", newline="") as fh:
        fh.write(original)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_text)
    return True


def rewrite_region(path: str, start_line: int, new_body: str) -> bool:
    """Replace the body between the marker lines opening at `start_line`."""
    text = read_text(path)
    if text is None:
        return False
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    end_idx = None
    for i in range(start_line, len(lines)):
        if END in lines[i] and NAME_OK.match(marker_name(lines[i], END)) and IGNORE not in lines[i]:
            end_idx = i
            break
    if end_idx is None:
        return False
    replacement = new_body.split("\n") if new_body != "" else []
    return _backup_and_write(path, text, newline.join(lines[:start_line] + replacement
                                                      + lines[end_idx:]))


def rewrite_line(path: str, line_no: int, new_stripped: str) -> bool:
    """Replace one line's content, preserving its indentation and the file's newline convention."""
    text = read_text(path)
    if text is None:
        return False
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    if line_no - 1 >= len(lines):
        return False
    original = lines[line_no - 1]
    lead = original[: len(original) - len(original.lstrip())]
    trail = original[len(original.rstrip()):]
    lines[line_no - 1] = lead + new_stripped + trail
    return _backup_and_write(path, text, newline.join(lines))


def reconcile(verdicts, canon_path, only, do_write, allow_bad_canon):
    """One write path for BOTH detectors. Discovered groups additionally require --only."""
    actions, refusals = [], []
    canon_real = os.path.realpath(canon_path)
    for idx, v in enumerate(verdicts, 1):
        if v["verdict"] != "VARIANT":
            continue
        if v["kind"] == "discovered" and idx not in only:
            continue
        if v["kind"] == "declared" and only and idx not in only:
            continue
        canon_form = None
        for form in v["forms"]:
            if any(os.path.realpath(loc.rsplit(":", 1)[0]) == canon_real
                   for loc in form["locations"]):
                canon_form = form
                break
        if canon_form is None:
            refusals.append({"group": idx, "name": v["name"],
                             "reason": "the canon file holds no witness in this group"})
            continue
        bad = canon_form["invisibles"]
        if bad and not allow_bad_canon:
            refusals.append({
                "group": idx, "name": v["name"],
                "reason": "canonical text carries %d non-rendering character(s): %s"
                          % (len(bad), ", ".join(b["name"] for b in bad))})
            continue
        for form in v["forms"]:
            if form["raw"] == canon_form["raw"]:
                continue
            for loc in form["locations"]:
                p, n = loc.rsplit(":", 1)
                if do_write:
                    changed = (rewrite_region(p, int(n), canon_form["raw"])
                               if v["kind"] == "declared"
                               else rewrite_line(p, int(n), canon_form["raw"]))
                else:
                    changed = True
                actions.append({"group": idx, "target": loc, "written": bool(do_write and changed)})
    return actions, refusals


# ---------------------------------------------------------------- output

def render(verdicts, errors, scanned, as_json, strict):
    variants = [v for v in verdicts if v["verdict"] == "VARIANT"]
    unpaired = [v for v in verdicts if v["verdict"] == "UNPAIRED"]
    if as_json:
        json.dump({"verdicts": verdicts, "errors": errors,
                   "summary": {"files_scanned": scanned, "names": len(verdicts),
                               "variants": len(variants), "unpaired": len(unpaired)}},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for e in errors:
            print("ERROR  %s" % e)
        for idx, v in enumerate(verdicts, 1):
            if v["verdict"] == "AGREE":
                print("AGREE    [%d] %-24s %d witnesses, identical" % (idx, v["name"], v["witnesses"]))
                continue
            if v["verdict"] == "UNPAIRED":
                print("UNPAIRED [%d] %-24s only 1 witness (%s) - nothing to compare, so this name "
                      "is not guarded" % (idx, v["name"], v["forms"][0]["locations"][0]))
                continue
            if v["kind"] == "declared":
                print("VARIANT  [%d] %-24s %d witnesses, %d distinct forms"
                      % (idx, v["name"], v["witnesses"], v["distinct"]))
            else:
                print("VARIANT  [%d] discovered  %d witnesses, %d distinct forms, identical once "
                      "invisibles are removed" % (idx, v["witnesses"], v["distinct"]))
                print("    looks like:  %s" % v["name"])
            for i, form in enumerate(v["forms"], 1):
                print("    form %d  (%d bytes)  %s" % (i, form["bytes"], ", ".join(form["locations"])))
                print("        %s" % form["preview"])
                for inv in form["invisibles"]:
                    print("        ^ offset %d  %s %s" % (inv["offset"], inv["codepoint"], inv["name"]))
        print("\n%d file(s) scanned, %d group(s), %d variant(s), %d unpaired"
              % (scanned, len(verdicts), len(variants), len(unpaired)))
        if not verdicts:
            print("nothing disagrees")
    if variants:
        return 1
    return 1 if (strict and unpaired) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="collator",
        description="Find text that looks identical across files and is not, byte for byte.")
    ap.add_argument("paths", nargs="*", default=["."], help="files or directories (default: .)")
    ap.add_argument("--mode", choices=("declared", "discover", "both"), default="both",
                    help="which detector to run (default: both)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true",
                    help="also fail when a declared name has only one witness")
    ap.add_argument("--min-length", type=int, default=DEFAULT_MIN, metavar="N",
                    help="discovery ignores lines shorter than N characters (default %d)" % DEFAULT_MIN)
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="skip paths matching GLOB (repeatable); .collateignore is read too")
    ap.add_argument("--canon", metavar="FILE",
                    help="the authoritative witness file; required for any reconcile")
    ap.add_argument("--only", action="append", type=int, default=[], metavar="N",
                    help="reconcile only group N from the report (repeatable); "
                         "required to write a DISCOVERED group")
    ap.add_argument("--write", action="store_true",
                    help="actually rewrite non-canonical witnesses (default is a dry run)")
    ap.add_argument("--allow-invisible-canon", action="store_true",
                    help="permit reconciling TO a canon that carries non-rendering characters")
    args = ap.parse_args(argv)

    paths = args.paths or ["."]
    for p in paths:
        if not os.path.exists(p):
            print("no such path: %s" % p, file=sys.stderr)
            return 2
    if args.min_length < 1:
        print("--min-length must be 1 or more", file=sys.stderr)
        return 2
    if args.write and not args.canon:
        print("--write requires --canon: this tool will not guess which copy is authoritative",
              file=sys.stderr)
        return 2
    if args.canon and not os.path.exists(args.canon):
        print("no such canon file: %s" % args.canon, file=sys.stderr)
        return 2

    excludes = list(args.exclude) + load_ignore_file(paths)
    declared, discovered, errors, scanned = [], [], [], 0
    unreadable = []
    for f in walk(paths, excludes):
        text, reason = read_text_reason(f)
        if text is None:
            if reason and reason.startswith("unreadable"):
                unreadable.append((f, reason))
            continue
        scanned += 1
        covered = set()
        if args.mode in ("declared", "both"):
            w, e = extract_declared(f)
            declared.extend(w)
            errors.extend(e)
            if args.mode == "both":
                for wit in w:
                    covered |= declared_line_span(wit)
        if args.mode in ("discover", "both"):
            discovered.extend(extract_discovered(f, args.min_length, covered))

    verdicts = []
    if args.mode in ("declared", "both"):
        verdicts.extend(collate_declared(declared))
    if args.mode in ("discover", "both"):
        verdicts.extend(collate_discovered(discovered))

    for f, why in unreadable:
        print("WARNING  could not open %s (%s) - it was NOT examined" % (f, why), file=sys.stderr)
    if unreadable:
        print("WARNING  %d file(s) could not be opened; the scanned count below excludes them."
              % len(unreadable), file=sys.stderr)

    code = render(verdicts, errors, scanned, args.json, args.strict)
    if not args.canon:
        return code

    has_discovered_variant = any(v["kind"] == "discovered" and v["verdict"] == "VARIANT"
                                 for v in verdicts)
    if args.write and has_discovered_variant and not args.only:
        print("--write needs --only N for discovered groups: discovery GROUPS by a lossy key, so a\n"
              "human must accept each grouping before anything is rewritten. Run without --write to\n"
              "see the numbers.", file=sys.stderr)
        return 2

    # An --only value naming no group used to vanish without comment: the write request simply did
    # not happen and nothing said so. An instruction that is silently ignored looks exactly like an
    # instruction that succeeded, which is the class of failure this whole tool exists to catch.
    for n in sorted(set(args.only)):
        if not 1 <= n <= len(verdicts):
            print("WARNING  --only %d names no group; this report has %d."
                  % (n, len(verdicts)), file=sys.stderr)

    actions, refusals = reconcile(verdicts, args.canon, set(args.only), args.write,
                                  args.allow_invisible_canon)
    for r in refusals:
        print("REFUSED  [%d] %s: %s" % (r["group"], r["name"], r["reason"]))
        if "non-rendering" in r["reason"]:
            print("         reconciling to this canon would copy the defect into every witness.")
            print("         pass --allow-invisible-canon only if that is genuinely what you mean.")
    for a in actions:
        print("%s [%d]  %s" % ("WROTE   " if a["written"] else "would write", a["group"], a["target"]))
    if actions and not args.write:
        print("\ndry run: %d witness(es) would change. Add --write to apply." % len(actions))
    elif actions:
        print("\n%d witness(es) rewritten; a %s copy sits beside each changed file."
              % (len(actions), BACKUP_SUFFIX))
    return 1 if refusals else code


if __name__ == "__main__":
    sys.exit(main())
