# COMPLETION REPORT - VariantCollator

**Builder:** seat `bram` · **Date:** 2026-09-05 · **Loop:** Holy Grail AIT, first iteration on BOOP_I7
**Start token block:** `[AIT seat=bram]` (all defaults)

```json
{"novelty": "on", "depth": "standard", "difficulty": "3", "category": "any",
 "audience": "ai-engineer", "lang": "python", "combo": "none", "deps": "stdlib",
 "platform": "xplat", "visibility": "public", "builds": "4", "timebox": "0",
 "loop": "inf", "seat": "bram"}
```

## What was built, and why

A CLI that finds text which looks identical across files and is not, naming the characters that do
not render.

**The why is not abstract.** Earlier the same day, a `U+0008` BACKSPACE sat inside a live regex in
this machine's message relay. `sed`, `diff`, `cat` and the editor all render that byte as nothing,
so the pattern was read and transcribed into a test fixture *without* it. The fixture passed every
case against a matcher that could not match a single input, and the certification was published
before the defect was found. **The instrument normalised away the exact defect it was pointed at.**

A denylist cannot fix that: a backspace in a comment is harmless and a backspace in a regex is
fatal, and only a comparison knows which one it is looking at. So the tool holds no opinion about
characters. It reports that two things claiming to be the same text are not.

## Novelty

Novelty Engine, STANDARD mode, **scored 76/100** (bar 70), recorded in `NOVELTY_SCORE.md`.
Maximum prior-art overlap 35% against five closest neighbours. Two cross-domain insights are
structural rather than decorative: **Hinman collation** from bibliography (compare witnesses, do not
validate a file) and **calibration** from metrology (a test fixture is an instrument and nobody
calibrates one against the artifact it measures).

## The four roads and the combine

| Road | Detection | Action | Tests |
|---|---|---|---|
| v1-A | declared regions (exact) | report only | 25 |
| v1-B | declared regions | reconcile with guards | 36 |
| v1-C | discovery (lossy key) | report only | 22 |
| v1-D | discovery | reconcile, per-group acceptance | 33 |
| **v2** | **both detectors** | **one guarded write path** | **60** |

**The finding road D produced:** making discovery's write path safe required a person to accept each
group, and at that point road D had become road B by a longer path. The bold action road, made safe,
converges on the safe one. That is why v2 ships one write path with one guard set feeding two
detectors, and it is recorded in `BUILD_LOG.md` rather than presented as a feature.

Two things were dropped in the combine, both duplicates of a better sibling, both named in the build
log rather than quietly not carried forward.

## Six quality gates

| Gate | Result | Evidence |
|---|---|---|
| TEST | **PASS** | `python test_collator.py` -> 60 tests, OK; four road suites pass independently |
| DOCUMENTATION | **PASS** | README driven from a clean folder in the beta stage, both directions |
| EXAMPLES | **PASS** | `EXAMPLES.md`, six examples, every output captured from a real run |
| ERROR HANDLING | **PASS** | nine error paths measured, all clear messages, **no traceback anywhere** |
| CODE QUALITY | **PASS** | no machine paths, no secrets, no unused imports, no dead functions, 586 lines |
| INTEGRATION | **PASS** | Team Brain section in README; Artifact card text written |

## Defects found during the build

Six, and the pattern in them is the point:

1. `is_invisible` exempted TAB in one clause and the trailing Unicode-category check caught it
   again, silently undoing the exemption.
2. The tool matched its **own documentation** as live markers.
3. The tool parsed its **own constant** into a region named `"`.
4. Non-breaking space was removed instead of mapped to a space, so the commonest look-alike in real
   text was silently missed.
5. The tool **rewrote its own backup** on a second run, destroying the only artifact that made a
   write undoable.
6. `--only` naming a group that does not exist was a silent no-op.

**Four of the six were found by running the tool against real material rather than fixtures, and two
of those by running it on itself.** Defect 5 was caught by the idempotence test, the only test that
could catch it, because it needs two runs.

## Measured, not claimed

| Measurement | Value |
|---|---|
| real tree scanned (unseen by the tool) | 207 files, 0.76 s |
| findings on that tree | 1 |
| incorrect findings | **0** |
| tests, combined build | 60 |
| tests, four roads | 25 / 36 / 22 / 33 |

The single finding on the unseen tree was a genuine byte-level divergence and was also a deliberate
fixture pair belonging to another seat's tool. The tool cannot know intent and does not claim to;
that limit is stated in the README and is why the discovery write path requires human acceptance.

## Time

Roughly **70 minutes** from the start token to this report, inside a session that was also handling
comms-infrastructure work. The stop token arrived from OmniLad mid-build and was recorded with
`gate.py stop`; this is the tool in hand, finished through Task 6 as the protocol requires.

## Honest notes

- `01_MR.md` governs the loop and names five mandatory protocols plus a subagent tool. **None of
  them exist on this box.** I followed the stage list Task 2 prints, which is self-contained, and
  said so rather than claiming to have applied protocols I could not read.
- Shoulder Angels refused at both forks: `ANTHROPIC_API_KEY` is not set and is the operator's to
  place. The exact refusal is recorded, and my own safe and bold strategies with the pick and the
  reasoning stand in its place, per the ruling of 2026-09-05 21:19Z.
- A sibling tool, `AsWritten`, was built the same afternoon by seat `cael` from the same incident.
  Overlap measured at 35-40%, which sits on my own rework bar rather than under it. Raised publicly
  rather than settled privately; the ruling was to mint both cards with a `Related` line.
