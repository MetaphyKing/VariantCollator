# PRODUCTION V1 - VariantCollator road B

**Road:** B - declared canon (safe detection) + reconcile (bold action)
**Seat:** bram · **Date:** 2026-09-05 · **Language:** Python 3, standard library only, cross-platform

## What it is

Road A plus a write path. With `--canon FILE --write` it rewrites non-canonical witnesses of a
declared name so they match the canonical one, byte for byte, preserving everything else in the file
and its newline convention.

Built to be tested against the author's own recorded objection that reporting and editing are
different acts. Three guards are the result: no write without a named canon, no write **to** a canon
that carries a non-rendering character, and dry-run by default with a `.collate-bak` beside every
modified file.

## Tests run

```
$ python test_collator.py
Ran 36 tests in 0.152s
OK
```

Includes all 25 of road A plus eleven for the action path: canon required, missing canon, dry run
inertness, write correctness, backup fidelity, rest-of-file preservation, the defective-canon
refusal **and** its explicit override, idempotence, backup protection, and a no-op when the canon
holds no witness.

## Alpha and beta

Alpha: reconciled a real backspace defect from a named canon, verified the witness was fixed, the
surrounding file untouched, and the backup held the original bytes.

Beta: second and third runs are no-ops; the backup survives them byte-identical; backups are absent
from plain reporting too.

## The defect this road found, which is the reason to read it

**The tool scanned its own backups.** After one `--write`, a second run found `copy.js.collate-bak`
as a witness, reported it as a VARIANT against the file it was a backup *of*, and rewrote it.

**The safety mechanism ate itself.** The one artifact that made the write undoable was destroyed by
the second invocation, silently, with an exit code of 1 that looked like an ordinary finding.

Caught by the idempotence test, which is the only test that could have caught it because it requires
two runs. Fixed by excluding `*.collate-bak` in the file walk, and that exclusion is deliberately
**not** exposed as an option: a flag to disable it is a flag to corrupt your own backups.

## Honest limits

- Only touches regions a human declared.
- Will not choose a canon; that is the user's call and there is no fallback.
- `--allow-invisible-canon` genuinely does propagate a defect to every witness. It is tested doing
  exactly that, so the override is documented by its own test rather than by a promise.
- Proves byte equality, not semantic equivalence.
- Cannot see a value assembled at runtime.

## Files

```
collator.py        the tool
test_collator.py   36 tests, stdlib unittest
README.md          install, use, the three guards, worked refusals
.collateignore     ships excluding README.md, whose examples are look-alikes
```
