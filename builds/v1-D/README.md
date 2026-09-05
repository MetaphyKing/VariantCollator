# VariantCollator (v1-D: discovery, reconcile)

**Road C plus an action, and the most dangerous of the four roads.** It discovers text that looks
identical across a tree and is not, then with `--canon`, `--only` and `--write` it can rewrite the
lines it grouped.

## Why this road is the dangerous one, stated first

| | Road B | Road D |
|---|---|---|
| what it rewrites | regions a human **marked** | lines a **heuristic** grouped |
| detection | exact | lossy by design |
| a detection error becomes | nothing; nothing is marked | **silent data loss** |

**That is not hypothetical.** A deliberate fixture pair, a file that is *supposed* to contain a
hidden character sitting beside the clean text it is compared against, is exactly what this tool
groups, and reconciling it destroys the fixture. Two such pairs already existed on this machine on
the day this was written, and one of them belonged to another seat.

## The guards, and the honest cost of them

1. **`--write` requires `--canon FILE`.** No majority vote.
2. **`--write` refuses a canon carrying a non-rendering character**, unless
   `--allow-invisible-canon`.
3. **`--write` also requires `--only N`**, naming each group from the report. A lossy key may
   *propose* a grouping; only a human may *accept* one.

**The cost, said plainly rather than hidden behind a flag: once a human confirms every group, this
road has become road B by a longer path.** That is the honest finding of building it, and it is
recorded in `BUILD_LOG.md` rather than presented as a feature.

## Install

None. One file, Python 3.8 or newer, standard library only, cross-platform.

## Use it

Discover (identical to road C, and the safe way to run this tool):

```
python collator.py .
VARIANT  [group 1]  2 witnesses, 2 distinct forms, identical once invisibles are removed
    looks like:  const AIT_KEY = /x_marks_the_spot/;
    form 1  (36 bytes)  ./copy.js:1
        const AIT_KEY = /x_marks_the_spot<BACKSPACE>/;
        ^ offset 33  U+0008 BACKSPACE
    form 2  (35 bytes)  ./canon.js:1
```

Reconcile one named group, dry run first:

```
python collator.py . --canon canon.js --only 1
would write group 1  ./copy.js:1

dry run: 1 line(s) would change. Add --write with the same --only to apply.
```

```
python collator.py . --canon canon.js --only 1 --write
WROTE    group 1  ./copy.js:1

1 line(s) rewritten; a .collate-bak copy sits beside each changed file.
```

Attempting to write without naming groups:

```
python collator.py . --canon canon.js --write
--write requires --only N: discovery GROUPS by a lossy key, so a human must accept
each grouping before anything is rewritten. Run without --write to see the numbers.
```

## Options

```
--json                     machine-readable output
--min-length N             ignore lines shorter than N characters (default 12)
--exclude GLOB             skip paths matching GLOB (repeatable)
--canon FILE               the authoritative witness file
--only N                   reconcile only group N (repeatable); required to write
--write                    actually rewrite (default is a dry run)
--allow-invisible-canon    permit reconciling TO a defective canon
```

Rewrites preserve each line's original indentation and the file's newline convention. Backups are
never scanned, so a second run cannot destroy the first run's backup.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | nothing to report and nothing to do |
| `1` | a VARIANT, or a refusal |
| `2` | usage error, missing path, `--write` without `--canon`, or `--write` without `--only` |

## What it does NOT do

- **It cannot know intent.** A deliberate fixture and a real defect are the same bytes to it. That
  is why the write path is gated on a human naming each group.
- The unit is the line, not the parsed literal.
- Proves byte equality, not semantic equivalence.
- Cannot see a value assembled at runtime.

## Tests

```
python test_collator.py
```

33 tests. Two of them exist purely to document the hazard: one demonstrates that a deliberate
fixture pair *is* grouped and *would* be destroyed, and its partner proves the destructive path is
simply unreachable without `--only`.

## Licence

Part of the Holy Grail AIT loop. Built by seat `bram`, 2026-09-05.
