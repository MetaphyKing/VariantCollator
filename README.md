# VariantCollator

**Finds text that looks identical across your files and is not.**

A literal that lives in more than one place can diverge, and when the differing byte does not render,
**every tool you would review it with hides the difference.** `sed`, `diff`, `cat`, your editor and
your code-review UI all agree that the two copies look the same, because rendering them is exactly
what removes the evidence.

VariantCollator treats the copies as **witnesses** to one text and reports whether they agree. It
holds no opinion about which characters are good or bad and it ships no denylist. It reports one
thing: two things claiming to be the same text are not, and here is the character that does not
print.

## Why it exists

On 2026-09-05 a `U+0008` BACKSPACE sat inside a live regex. The pattern was read, transcribed into a
test fixture, and the fixture passed 25 of 25 against a matcher that could not match a single input.
**The instrument normalised away the exact defect it was pointed at.** A denylist would not have
helped: a backspace in a comment is harmless and a backspace in a regex is fatal, and only a
comparison knows which one it is looking at.

## Install

None. One file, Python 3.8 or newer, standard library only. Windows, macOS, Linux.

```
python collator.py [PATH ...]
```

## Two detectors

**`discover`** needs nothing from you. Every line is a candidate witness; two lines group when they
match after invisibles are normalised; a group is a VARIANT when its members differ before that
normalisation. This is the detector that catches what nobody declared.

**`declared`** is exact. Mark a guarded value with region markers and only those regions are
compared, with zero false positives:

```js
// collate:begin AIT_KEY
const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
// collate:end AIT_KEY
```

The marker sits in a comment in any language, or in prose. Only the bytes *between* the marker lines
are the witness, and the tool never parses the surrounding language, so a `.js`, a `.py` and a
`README.md` are all comparable in one pass.

**Both run by default.** A declared region is reported once, by the declared detector; discovery
covers everything else.

Writing about the markers in your own documentation? Put `collate:ignore` on the line, or list the
file in `.collateignore`. This README does the first.

## Worked example

```
$ python collator.py .
VARIANT  [1] AIT_KEY                  2 witnesses, 2 distinct forms
    form 1  (41 bytes)  ./fixture.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE
    form 2  (40 bytes)  ./relay.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
VARIANT  [2] discovered  2 witnesses, 2 distinct forms, identical once invisibles are removed
    looks like:  we also quote it here: const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 1  (63 bytes)  ./notes.md:1
    form 2  (66 bytes)  ./notes2.md:1
        we also quote it here: const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<ZERO-WIDTH-SPACE>/;
        ^ offset 61  U+200B ZERO-WIDTH-SPACE

4 file(s) scanned, 2 group(s), 2 variant(s), 0 unpaired
```

Group 2 is a zero-width space in a markdown sentence that nobody declared and nobody would have.

## Verdicts

| Verdict | Meaning |
|---|---|
| `AGREE` | every witness for this declared name is byte-identical |
| `VARIANT` | witnesses disagree; each distinct form is listed, most common first |
| `UNPAIRED` | a declared name with one witness. Nothing to compare, so **it is not guarded** |

`UNPAIRED` matters more than it looks. A guard that cannot fail is indistinguishable from a guard
that passed.

## What it stays silent about

Silence is a feature. A detector that reports everything is not a detector.

| Situation | Reported? |
|---|---|
| identical after normalising, different in bytes | **yes, this is the tool** |
| differ visibly | no, any diff shows you |
| byte-identical | no |
| the same line re-indented | no |
| a line that appears once | no |
| shorter than `--min-length` (default 12) | no |
| no letters or digits (rulers, punctuation) | no |

## Measured noise floor

Against a real mixed tree the tool had never seen:

| Files scanned | Time | Findings | Incorrect findings |
|---|---|---|---|
| 207 | 0.76 s | 1 | **0** |

The single finding was a genuine byte-level divergence. It was also a **deliberate fixture pair**
belonging to another tool, which the tool cannot know and does not claim to: see the limits below.
This number is published instead of a fixture count, because a detector that has only been shown its
own tests is untested.

## Reconciling (optional, guarded)

`--canon FILE --write` rewrites non-canonical witnesses to match the canonical one. Reporting and
editing are different acts, so the write path is deliberately hard to reach:

1. **No write without `--canon`.** No majority vote, no guessing which copy is right.
2. **No write to a canon that itself carries a non-rendering character**, unless
   `--allow-invisible-canon`. Reconciling to a defective canon copies the defect into every witness.
3. **No write of a discovered group without `--only N`.** A lossy key may propose a grouping; only a
   person may accept one. Declared regions need no `--only`, because a human already marked them.
4. **Dry run is the default**, every change is printed, and a `.collate-bak` sits beside each edit.
   Backups are never scanned, and that is not configurable.

```
$ python collator.py . --canon relay.js
would write [1]  ./fixture.js:1
dry run: 1 witness(es) would change. Add --write to apply.

$ python collator.py . --canon fixture.js --write
REFUSED  [1] AIT_KEY: canonical text carries 1 non-rendering character(s): BACKSPACE
         reconciling to this canon would copy the defect into every witness.
```

## Options

```
--mode declared|discover|both   which detector to run (default: both)
--json                          machine-readable output
--strict                        also fail when a declared name has only one witness
--min-length N                  discovery ignores lines shorter than N (default 12)
--exclude GLOB                  skip paths matching GLOB (repeatable)
--canon FILE                    the authoritative witness; required for any reconcile
--only N                        reconcile only group N (repeatable); required for discovered groups
--write                         actually rewrite (default is a dry run)
--allow-invisible-canon         permit reconciling TO a defective canon
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | nothing disagrees |
| `1` | a VARIANT, a refusal, or an UNPAIRED name under `--strict` |
| `2` | usage error, missing path, or a write without the guards satisfied |

## In CI

```yaml
- run: python collator.py .
```

## For a Team Brain seat

Before you publish *"the pattern is this"*, or commit a fixture labelled verbatim, run this over the
tree. If `sed` and `diff` showed you nothing, that is the condition under which this tool is worth
running, not evidence that there is nothing to find. Pair it with
`~/.claude/wake/tools/ctlscan.js` when you want a single file's control bytes listed rather than
compared.

## Limits, stated plainly

- **It cannot know intent.** A deliberate fixture and a real defect are the same bytes. That is why
  the discovery write path is gated on a person naming each group.
- **The discovery unit is the line, not the parsed literal.** That is what makes it
  language-agnostic; a literal split across two lines is compared as two witnesses.
- **Recall is bought with a threshold.** Below `--min-length` the tool is blind by choice.
- **It proves byte equality, not meaning.** Two regexes that differ but match the same language are
  reported as different.
- **It cannot see a value assembled at runtime** from fragments.
- **`.collateignore` is read from the paths you name**, not from every directory walked.

## Tests

```
python test_collator.py
```

58 tests, standard library only. Every positive has a negative control, and a large share assert
silence.

## Licence

Part of the Holy Grail AIT loop. Built by seat `bram`, 2026-09-05.
