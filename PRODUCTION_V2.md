# PRODUCTION V2 - VariantCollator (combined)

**Seat:** bram · **Date:** 2026-09-05 · **Language:** Python 3, standard library only, cross-platform

## What ships

One tool, two detectors, one guarded write path.

- **`discover`** finds look-alike divergence with no configuration. Contributed by road C.
- **`declared`** compares only regions a human marked, with zero false positives. Contributed by
  road A, including the `UNPAIRED` verdict, marker-name validation and `collate:ignore`.
- **one reconcile path** serving both, carrying road B's guards (named canon, defective-canon
  refusal, backup, backups never scanned) and road D's `--only` per-group acceptance.

Both detectors run by default. A declared region is reported once, by the declared detector.

## Tests run

```
$ python test_collator.py
Ran 58 tests in 0.426s
OK
```

Carries every case from the four v1 suites plus the ones the combine creates. A large share assert
**silence**, because a detector that reports everything is not a detector.

## Alpha

Four files, one invocation, both detectors: a declared `AIT_KEY` region diverging by a `U+0008`, and
an undeclared markdown sentence diverging by a `U+200B`. Both reported, each once, with the byte
named and its offset given. Exit 1.

## Beta and measured noise floor

Run against a real mixed tree the tool had never seen:

| Files scanned | Time | Findings | Incorrect findings |
|---|---|---|---|
| 207 | 0.76 s | 1 | **0** |

The single finding is a genuine byte-level divergence and is also a deliberate fixture pair
belonging to another seat's tool, which this tool cannot know. That is the documented
"cannot know intent" limit, not a false positive, and the README says so in those words.

## Break stage - adversarial inputs, all survived

Empty file · a file containing only markers · a 200,000-character line · CRLF files (line endings
preserved through a rewrite, verified byte-wise) · a UTF-8 BOM · a five-level nested directory · a
non-ASCII filename (`é中文.txt`) · binary blobs · unknown `--mode` · negative `--min-length` ·
missing paths. **No traceback in any case; usage errors exit 2 with a message.**

## Defects found and fixed across v1 and v2

1. **`is_invisible` exempted TAB, then un-exempted it.** The trailing Unicode-category test caught
   what the guard clause had just excused. Order of clauses was the fix. (road A)
2. **The tool matched its own documentation** and **parsed its own constant into a region named
   `"`.** Both found by running it on a folder containing it, which was not in the test plan.
   (road A)
3. **Non-breaking space was removed instead of mapped to a space**, so `hello<NBSP>world` never met
   `hello world` and the commonest look-alike in real text was silently missed. (road C)
4. **The tool rewrote its own backup on the second run**, destroying the only artifact that made a
   write undoable. Caught by the idempotence test, the only test that could catch it. (road B)
5. **`--only` naming a group that does not exist was a silent no-op.** An instruction that is
   ignored without comment looks exactly like one that succeeded. Now warns. (v2)
6. **`--mode both` reported the same defect twice**, once per detector. Discovery now stands clear
   of declared regions. (v2)

*Four of the six were found by running the tool against real material rather than fixtures, and two
of those were found by running it on itself.*

## The finding road D contributed

Making discovery's write path safe required a person to accept each group. **At that point road D
had become road B by a longer path.** The bold action road, made safe, converges on the safe one.
That is why v2 has one write path with one guard set rather than two.

## Limits

Stated in full in the README: cannot know intent; the discovery unit is the line; recall is bought
with a threshold; byte equality is not semantic equivalence; runtime-assembled values are out of
scope; `.collateignore` is read from the paths you name.

## Files

```
collator.py        the combined tool
test_collator.py   58 tests, stdlib unittest
README.md          install, both detectors, worked example, measured noise floor, guards, limits
BUILD_LOG.md       tokens, prior art, Shoulder Angels, score table, pivots, drops
NOVELTY_SCORE.md   Novelty Engine STANDARD, scored 76/100
builds/v1-A..D     the four roads, each at production v1 with its own tests and stamp
```
