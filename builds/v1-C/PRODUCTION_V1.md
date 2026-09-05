# PRODUCTION V1 - VariantCollator road C

**Road:** C - discovery (bold detection) + report only (safe action)
**Seat:** bram · **Date:** 2026-09-05 · **Language:** Python 3, standard library only, cross-platform

## What it is

Finds text that looks identical across a tree and is not, **with no configuration and no markers**.
Every line is a candidate witness; two lines group when they match after normalising invisibles; a
group is a VARIANT when its members differ before that normalisation. The tool reports exactly one
thing, text that looks the same and is not, and is deliberately silent about everything else.

This is the road picked at Shoulder Angels fork 1, because the defect that motivated the tool would
never have been declared.

## Tests run

```
$ python test_collator.py
Ran 22 tests in 0.099s
OK
```

Most of the suite is about **silence**: ordinary visible differences, single occurrences,
re-indented copies, sub-threshold lines and punctuation-only lines must all produce nothing. A
detector that reports everything is not a detector.

## Alpha - runs end to end on this box

Two files, no markers, no config, one carrying the real `U+0008` from `ifch_seat_relay.js`:

```
VARIANT  2 witnesses, 2 distinct forms, identical once invisibles are removed
    looks like:  const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 1  (41 bytes)  ./fixture.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE
    form 2  (40 bytes)  ./relay.js:1
exit 1
```

## Beta and measured noise floor

Run against a real mixed tree the tool had never seen, `C:\dev\ait`:

| Files scanned | Time | Variants | False positives |
|---|---|---|---|
| 179 | 0.47 s | 1 | **0** |

Also run against its own source directory: **0 variants, 0 false positives.**

**The single variant was genuine** and was in `AsWritten\`, a sibling tool built the same afternoon
by seat `cael`. The tool's first find on an unseen tree was a real one. That measurement is what
triggered the redundancy re-check recorded in `BUILD_LOG.md`.

## Defect found and fixed during this build

**Non-breaking space was being removed instead of mapped to a space.** The grouping key is meant to
answer *what does this look like*, and NBSP looks like a space, not like nothing. Removing it meant
`hello<NBSP>world` keyed as `helloworld`, never met `hello world`, and **the commonest look-alike in
real text was silently missed by the tool built to find look-alikes.**

Found because a badly-written test of mine failed. The test was wrong and the code was also wrong,
in a way the wrong test happened to expose. Both fixed, and the control case (an NBSP where there
was no space, which is a genuine visible difference and must stay silent) is now a test in its own
right.

## Honest limits

- **The unit is the line, not the parsed literal.** That is what makes it language-agnostic and it
  is also the limit: a literal split across two lines is compared as two witnesses.
- **Recall is bought with a threshold.** Below `--min-length` (default 12) the tool is deliberately
  blind; lowering it raises the false-positive count. The trade is the user's and it is printed in
  `--help` rather than hidden.
- Proves byte equality, not semantic equivalence.
- Cannot see a value assembled at runtime.
- Never modifies a file.

## Files

```
collator.py        the tool
test_collator.py   22 tests, stdlib unittest
README.md          install, method, worked example, measured noise floor, limits
```
