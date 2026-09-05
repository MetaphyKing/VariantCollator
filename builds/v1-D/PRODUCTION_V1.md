# PRODUCTION V1 - VariantCollator road D

**Road:** D - discovery (bold detection) + reconcile (bold action)
**Seat:** bram · **Date:** 2026-09-05 · **Language:** Python 3, standard library only, cross-platform

## What it is

Road C plus a write path, and the most dangerous of the four roads. It discovers look-alike
divergence with no configuration, then can rewrite the lines it grouped.

**Reached production v1 rather than being abandoned, but its central finding is a warning, not a
feature.**

## The hazard, named rather than buried

Road B rewrites regions a human **marked**, so detection is exact and a write can only touch text
somebody deliberately declared. Road D rewrites lines a **heuristic** grouped, so a false positive in
detection becomes silent data loss.

This is not hypothetical: a deliberate fixture pair, a file that is *supposed* to contain a hidden
character beside the clean text it is compared against, is indistinguishable from a defect to a
lossy key. **Two such pairs existed on this machine the day this was written, one of them belonging
to another seat.** Road C found one of them as its first result on an unseen tree.

## The guards, and the finding they produce

1. `--write` requires `--canon FILE`.
2. `--write` refuses a canon carrying a non-rendering character, unless `--allow-invisible-canon`.
3. `--write` also requires `--only N`, naming each group from the report.

**THE FINDING: once a human confirms every group, this road has become road B by a longer path.**
The bold action road, made safe, converges on the safe one. That is recorded here and in
`BUILD_LOG.md` rather than presented as a feature, and it is the main thing road D contributes to
the Task 3 combine.

## Tests run

```
$ python test_collator.py
Ran 33 tests in 0.174s
OK
```

Includes all 22 of road C plus eleven for the action path, of which **two exist purely to document
the hazard**: one demonstrates that a deliberate fixture pair *is* grouped and *would* be destroyed,
and its partner proves that the destructive path is unreachable without `--only`. The rest cover
canon and group requirements, dry-run inertness, write correctness, indentation preservation, the
defective-canon refusal, group scoping (an unselected group must remain untouched), a canon with no
witness in the group, and backup protection across two runs.

## Alpha and beta

Alpha: discovered and reconciled a real backspace defect with no markers and no config, from a named
canon and a named group.

Beta: verified indentation and newline convention survive a rewrite; verified a second run leaves
the first run's backup byte-identical; verified that selecting group 1 leaves group 2 alone.

## Honest limits

- **It cannot know intent.** A deliberate fixture and a real defect are the same bytes.
- The unit is the line, not the parsed literal.
- Recall is bought with a threshold; below `--min-length` the tool is blind by choice.
- Proves byte equality, not semantic equivalence.
- Cannot see a value assembled at runtime.

## Files

```
collator.py        the tool
test_collator.py   33 tests, stdlib unittest
README.md          install, the hazard first, guards, worked examples and refusals
```
