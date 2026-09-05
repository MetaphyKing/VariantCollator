# VariantCollator (v1-B: declared canon, reconcile)

**Road A plus an action.** It finds disagreement between literals you declared, and with
`--canon FILE --write` it rewrites the other witnesses so they match the canonical one.

## Read this before using `--write`

The author's recorded position is that **reporting and editing are different acts**, and that a tool
which silently repairs a live matcher changes behaviour without telling anyone which behaviour
moved. This road exists to be tested against that objection rather than to win the argument. Three
guards came out of that test, and they are the interesting part of the road:

1. **`--write` does nothing without `--canon`.** There is no majority vote and no guessing which
   copy is right. A human names the authority, or nothing happens.
2. **`--write` refuses a canon that carries a non-rendering character.** Reconciling to a defective
   canon propagates the defect into every witness at once, which is strictly worse than the
   divergence it repairs. `--allow-invisible-canon` overrides it, loudly and on purpose.
3. **Dry run is the default**, every change is printed, and a `.collate-bak` copy is left beside
   each modified file.

## Install

None. One file, Python 3.8 or newer, standard library only, cross-platform.

## Use it

Mark the guarded value in every place it lives, exactly as in road A:

```js
// collate:begin AIT_KEY      collate:ignore
const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
// collate:end AIT_KEY        collate:ignore
```

Report only (identical to road A):

```
python collator.py .
```

See what a reconcile would do:

```
python collator.py . --canon relay.js
would write  fixture.js:1 -> matches relay.js:1

dry run: 1 witness(es) would change. Add --write to apply.
```

Apply it:

```
python collator.py . --canon relay.js --write
WROTE    fixture.js:1 -> matches relay.js:1

1 witness(es) rewritten; a .collate-bak copy sits beside each changed file.
```

Refusal, when the named canon is the defective copy:

```
python collator.py . --canon fixture.js --write
REFUSED  AIT_KEY: canonical text carries 1 non-rendering character(s): BACKSPACE (canon fixture.js:1)
         reconciling to this canon would copy the defect into every witness.
         pass --allow-invisible-canon only if that is genuinely what you mean.
```

## Options

```
--json                     machine-readable output
--strict                   also fail when a declared name has only one witness
--exclude GLOB             skip paths matching GLOB (repeatable)
--canon FILE               the authoritative witness; required for any reconcile
--write                    actually rewrite (default is a dry run)
--allow-invisible-canon    permit reconciling TO a defective canon
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | agreed, or nothing to do |
| `1` | a VARIANT, or a refusal |
| `2` | usage error, missing path, or `--write` without `--canon` |

## Defect found during this build, and why it is worth reading

The first version scanned its **own backups**. After one `--write`, a second run found
`copy.js.collate-bak` as a witness, reported it as a variant against the file it was a backup of,
and rewrote it, **destroying the only artifact that made the write undoable.** The safety mechanism
ate itself.

It was caught by the idempotence test, which is the only test that could have caught it, because it
needs two runs. Backups are now excluded in the file walk, and that exclusion is deliberately **not**
a user-facing option: a flag to disable it is a flag to corrupt your own backups.

## What it does NOT do

- Only touches regions a human declared. A value nobody marked is invisible to this road.
- Proves byte equality, not semantic equivalence.
- Cannot see a value assembled at runtime.
- Will not choose a canon for you, ever.

## Tests

```
python test_collator.py
```

36 tests, standard library only.

## Licence

Part of the Holy Grail AIT loop. Built by seat `bram`, 2026-09-05.
