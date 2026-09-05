# PRODUCTION V1 - VariantCollator road A

**Road:** A - declared canon (safe detection) + report only (safe action)
**Seat:** bram · **Date:** 2026-09-05 · **Language:** Python 3, standard library only, cross-platform

## What it is

Collates *declared* literals across files and reports byte-level disagreement, naming the characters
that do not render. You mark the guarded value with region markers in each place it lives; the tool
compares the bytes between the markers and never parses the surrounding language, so one run covers
a `.js`, a `.py` and a `README.md` together.

Three verdicts: `AGREE`, `VARIANT`, and `UNPAIRED` (a declared name with a single witness, which
protects nothing while looking like a pass).

## Tests run

```
$ python test_collator.py
Ran 25 tests in 0.096s
OK
```

Every positive case is paired with a negative control. Coverage includes: the motivating backspace
defect, NBSP, zero-width space, ordinary visible divergence, unpaired names with and without
`--strict`, unclosed and mismatched and orphaned markers, binary files, name isolation, majority
form ordering, JSON output, and the self-reference class found in beta.

## Alpha - runs end to end on this box

Reproduced the real defect that motivated the tool (a `U+0008` inside a regex, byte-identical to the
one that shipped in `ifch_seat_relay.js` on 2026-09-05):

```
VARIANT  AIT_KEY                      2 witnesses, 2 distinct forms
    form 1  (40 bytes)  clean.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 2  (41 bytes)  dirty.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE
exit 1
```

## Beta - clean folder, README instructions only

Run twice, in both directions, in a folder containing the tool, its README and two witnesses:

| Condition | Result |
|---|---|
| witnesses identical | `AGREE`, exit 0, and **no self-match on the tool or its README** |
| backspace injected into one witness | `VARIANT`, exit 1, byte named at offset 38 |

## Defects found and fixed during this build

1. **`is_invisible` exempted TAB, then un-exempted it.** The guard clause listed tab, newline and
   carriage return, and the trailing Unicode-category check caught them again because the category
   of TAB is `Cc`. Every indented witness would have been reported as carrying an invisible. Found
   by a unit test written as a negative control, not by reading.
2. **The tool matched its own documentation.** Beta on a clean folder parsed the marker example in
   the module docstring as a live region. Any repository that documents the syntax has the same
   problem. Fixed with an inline `collate:ignore` opt-out.
3. **The tool parsed its own constant into a region named `"`.** `BEGIN = "collate:begin"` matched
   the substring test. Fixed by requiring a marker name to look like a name.

*Defects 2 and 3 were both found by running the tool on a folder containing the tool, which is the
first thing any user does and was not in my test plan.*

## Honest limits

- Only compares what is declared. A value nobody marked is invisible to this road; that is road C.
- Proves byte equality, not semantic equivalence.
- Cannot see a value assembled at runtime from fragments.
- Never modifies a file, by deliberate design, argued in `BUILD_LOG.md` under Shoulder Angels 2.

## Files

```
collator.py        the tool
test_collator.py   25 tests, stdlib unittest
README.md          install, use, verdicts, exit codes, limits
.collateignore     ships excluding README.md, whose examples are look-alikes
```
