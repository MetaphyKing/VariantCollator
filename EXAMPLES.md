# VariantCollator - worked examples

Every output below was **captured from a real run on 2026-09-05**, not written by hand. The sample
tree is four files:

```
relay.js     a declared AIT_KEY region, clean
fixture.js   the same declared region, carrying a U+0008 BACKSPACE
notes.md     an undeclared sentence quoting the same pattern, clean
notes2.md    the same sentence, carrying a U+200B ZERO-WIDTH-SPACE
```

`relay.js` and `fixture.js` look identical in every editor. So do `notes.md` and `notes2.md`.

---

## 1. The default run: both detectors

```
$ python collator.py .
```

```
VARIANT  [1] AIT_KEY                  2 witnesses, 2 distinct forms
    form 1  (41 bytes)  .\fixture.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE
    form 2  (40 bytes)  .\relay.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
VARIANT  [2] discovered  2 witnesses, 2 distinct forms, identical once invisibles are removed
    looks like:  we quote the key here: const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 1  (63 bytes)  .\notes.md:1
        we quote the key here: const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;
    form 2  (66 bytes)  .\notes2.md:1
        we quote the key here: const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<ZERO-WIDTH-SPACE>/;
        ^ offset 61  U+200B ZERO-WIDTH-SPACE

4 file(s) scanned, 2 group(s), 2 variant(s), 0 unpaired
```

**exit 1.**

Group 1 was declared. Group 2 was not, and nobody would have thought to declare a sentence in a
markdown file. That is the case discovery exists for.

---

## 2. Machine-readable output

```
$ python collator.py . --mode declared --json
```

```json
{
  "verdicts": [
    {
      "name": "AIT_KEY",
      "kind": "declared",
      "verdict": "VARIANT",
      "witnesses": 2,
      "distinct": 2,
      "forms": [
        {
          "raw": "const AIT_KEY = /\\[AIT-(NEXT|CONTINUE)\b/;",
          "bytes": 41,
          "locations": [".\\fixture.js:1"],
          "invisibles": [
            {"offset": 38, "codepoint": "U+0008", "name": "BACKSPACE"}
          ]
        }
      ]
    }
  ]
}
```

**exit 1.** Note that `raw` in the JSON carries the actual byte. The `invisibles` array is what you
read, because the raw string will render as a lie in any terminal that prints it.

---

## 3. The guard that matters most: a defective canon is refused

Here the file named as authoritative is the one carrying the defect.

```
$ python collator.py . --mode declared --canon fixture.js --write
```

```
VARIANT  [1] AIT_KEY                  2 witnesses, 2 distinct forms
    form 1  (41 bytes)  .\fixture.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)<BACKSPACE>/;
        ^ offset 38  U+0008 BACKSPACE
    form 2  (40 bytes)  .\relay.js:1
        const AIT_KEY = /\[AIT-(NEXT|CONTINUE)/;

4 file(s) scanned, 1 group(s), 1 variant(s), 0 unpaired
REFUSED  [1] AIT_KEY: canonical text carries 1 non-rendering character(s): BACKSPACE
         reconciling to this canon would copy the defect into every witness.
         pass --allow-invisible-canon only if that is genuinely what you mean.
```

**exit 1, and `relay.js` is untouched.** Reconciling to this canon would have copied the backspace
into every witness at once, which is worse than the divergence it repairs.

---

## 4. A dry run against the correct canon

```
$ python collator.py . --mode declared --canon relay.js
```

```
would write [1]  .\fixture.js:1

dry run: 1 witness(es) would change. Add --write to apply.
```

Dry run is the default. Add `--write` and a `.collate-bak` is left beside every file that changes.

---

## 5. Discovery cannot be written without a person accepting the grouping

```
$ python collator.py . --canon relay.js --write
```

```
--write needs --only N for discovered groups: discovery GROUPS by a lossy key, so a
human must accept each grouping before anything is rewritten. Run without --write to
see the numbers.
```

**exit 2, nothing written.** A deliberate fixture and a real defect are the same bytes to a lossy
key, so the tool refuses to decide which one it is looking at.

To proceed you name the group from the report:

```
$ python collator.py . --canon relay.js --only 2 --write
```

---

## 6. A path that does not exist

```
$ python collator.py /tmp/nope-here
```

```
no such path: /tmp/nope-here
```

**exit 2.** No traceback, here or on any other usage error.

---

## Exit codes at a glance

| Code | Meaning |
|---|---|
| `0` | nothing disagrees |
| `1` | a VARIANT, a refusal, or an UNPAIRED name under `--strict` |
| `2` | usage error, missing path, or a write whose guards are not satisfied |
