# VariantCollator (v1-C: discovery, report only)

**Finds text that looks identical across your files and is not, without being told what to look
for.**

Road A guards values you *declared*. This road is for the case that actually bites: nobody writes a
config entry for a regex they are about to transcribe by hand an hour later. The whole failure is
that you do not know the copy exists.

## Install

None. One file, Python 3.8 or newer, standard library only, Windows/macOS/Linux.

```
python collator.py [PATH ...]
```

## What it reports, and what it stays silent about

The tool reports **exactly one thing**: text that looks the same and is not.

| Situation | Reported? | Why |
|---|---|---|
| two lines identical after invisibles are removed, but different in bytes | **YES** | this is the whole tool |
| two lines that differ visibly | no | any diff already shows you |
| two lines that are byte-identical | no | nothing to say |
| the same line re-indented | no | leading and trailing whitespace is normalised first |
| a line that appears once | no | nothing to compare |
| lines shorter than `--min-length` (default 12) | no | noise floor |
| lines with no letters or digits | no | rulers and punctuation |

## How it decides

1. Every line of every text file is a candidate, stripped of leading and trailing whitespace.
2. Two lines share a **group** when they are identical after normalising: zero-width and control
   characters are removed, and space-like characters (non-breaking space and the rest of Unicode
   category `Zs`) are mapped to a single ordinary space.
3. A group is a **VARIANT** when its members are not identical *before* that normalisation.

The space-like rule is not cosmetic. Removing a non-breaking space instead of mapping it meant
`hello<NBSP>world` keyed as `helloworld`, never met `hello world`, and the commonest look-alike in
real text was silently missed. That was a real defect, caught in test.

## Worked example

```
$ python collator.py .
VARIANT  2 witnesses, 2 distinct forms, identical once invisibles are removed
    looks like:  const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 1  (41 bytes)  ./fixture.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE
    form 2  (40 bytes)  ./relay.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;

2 file(s) scanned, 1 variant(s)
```

No markers. No configuration. Two files and a question.

## Measured noise floor

Run against a real, mixed tree that the tool had never seen (`C:\dev\ait`, 2026-09-05):

| Files scanned | Time | Variants | False positives |
|---|---|---|---|
| 179 | 0.47 s | 1 | **0** |

The single variant was genuine. **A discovery tool that has only been shown its own fixtures is
untested, so this number is published rather than the fixture count.**

## Options

```
--json              machine-readable output
--min-length N      ignore lines shorter than N characters (default 12)
--exclude GLOB      skip paths matching GLOB (repeatable); .collateignore is read too
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | no variants |
| `1` | at least one VARIANT |
| `2` | a path does not exist, or `--min-length` is below 1 |

## In CI

```yaml
- run: python collator.py .
```

## What it does NOT do

- **It never modifies a file.** It reports; you decide.
- **The unit is the line, not the parsed literal.** That is what makes it language-agnostic, and it
  is also the limit: a literal split across two lines is compared as two witnesses, not one.
- **It proves byte equality, not meaning.**
- **It cannot see a value assembled at runtime.**
- **Recall is bought with a threshold.** Below `--min-length` the tool is deliberately blind. Lower
  it and the false-positive count rises; that trade is yours to set, and it is why the default is
  printed in `--help` rather than hidden.

## Tests

```
python test_collator.py
```

22 tests. Most of the suite is about what the tool must stay **silent** about, because a detector
that reports everything is not a detector.

## Licence

Part of the Holy Grail AIT loop. Built by seat `bram`, 2026-09-05.
