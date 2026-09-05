# VariantCollator (v1-A: declared canon, report only)

**A literal that lives in more than one place can diverge, and when the differing byte does not
render, every tool you would review it with hides the difference.**

VariantCollator treats the copies as *witnesses* to one text and tells you whether they agree. It
holds no opinion about which characters are good or bad. It reports only that two things claiming to
be the same text are not, and it names the characters that do not print.

## Why this exists

On 2026-09-05 a `U+0008` BACKSPACE sat inside a live regex. `sed`, `diff`, `cat` and the editor all
render that byte as nothing, so the pattern was transcribed into a test fixture *without* it. The
fixture scored 11/11 against a matcher that could not match a single input. **The instrument
normalised away the exact defect it was pointed at.**

That is the class this tool is for: **you cannot find it by reading, because reading is what hides
it.**

## Install

None. One file, Python 3.8 or newer, standard library only, Windows/macOS/Linux.

```
python collator.py [PATH ...]
```

## Use it

Mark the same guarded value in every place it lives. The marker goes in a comment in any language,
or in plain prose:

```js
// collate:begin AIT_KEY      collate:ignore
const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
// collate:end AIT_KEY        collate:ignore
```

```python
# collate:begin AIT_KEY       collate:ignore
AIT_KEY = r"\[AIT-(NEXT|CONTINUE)"
# collate:end AIT_KEY         collate:ignore
```

Only the bytes **between** the marker lines are the witness. The tool never parses the surrounding
language, which is why it works in a `.js`, a `.py` and a `README.md` at the same time.

Then run it:

```
$ python collator.py .
VARIANT  AIT_KEY                      2 witnesses, 2 distinct forms
    form 1  (40 bytes)  ./relay.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 2  (41 bytes)  ./fixture.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE

1 name(s), 1 variant(s), 0 unpaired
```

## Verdicts

| Verdict | Meaning |
|---|---|
| `AGREE` | every witness for this name is byte-identical |
| `VARIANT` | witnesses disagree; each distinct form is listed, most common first |
| `UNPAIRED` | only one witness exists, so there is nothing to compare and **this name is not guarded** |

`UNPAIRED` matters more than it looks. A declared name with one witness protects nothing while
looking exactly like a name that passed, which is the same silent-success shape the tool exists to
catch.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | no variants (use in CI as a pass) |
| `1` | at least one VARIANT, or an UNPAIRED name when `--strict` is given |
| `2` | a path you named does not exist |

## Options

```
--json      machine-readable output, same findings
--strict    also fail when a declared name has only one witness
```

## In CI

```yaml
- run: python collator.py .
```

Any divergence fails the step and prints which files disagree and at what byte offset.

## What it does NOT do

Stated plainly, because a tool that implies coverage it does not have is worse than no tool:

- **It never modifies a file.** It reports; you decide. Rewriting a witness to match would silently
  change a live matcher without telling anyone which behaviour moved.
- **It only compares what you declare.** A value you never marked is invisible to this road. If you
  want divergence found *without* declaring it first, that is road C (discovery).
- **It proves byte equality, not meaning.** Two regexes that differ but match the same language are
  reported as different. That is correct by its definition and may not be what you wanted.
- **It cannot see a value assembled at runtime** from fragments.

## Tests

```
python test_collator.py
```

25 tests, standard library only. Every positive case is paired with a negative control, because a
detector that has only ever seen positives is untested. The suite found a real bug during the build:
`is_invisible` exempted TAB in one clause and the trailing Unicode-category check caught it again,
so the exemption was silently undone.

## Licence

Part of the Holy Grail AIT loop. Built by seat `bram`, 2026-09-05.
