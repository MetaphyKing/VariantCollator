# Novelty Engine Score Sheet - VariantCollator

**Mode:** STANDARD (bar 70) · **Seat:** bram · **Scored:** 2026-09-05 20:24Z
**Tool:** VariantCollator - proves every copy of a literal (regex, prompt, constant, SQL) is
byte-identical to the one that actually ships, and names the characters that make a difference
unreadable.

---

## M1 - Prior Art Verification

| # | Closest prior work | Overlap | Differs because |
|---|---|---|---|
| 1 | duplicate-literal / magic-value linters (jscpd, ruff, no-magic-numbers) | 35% | flag duplication as a smell and prescribe "extract a constant"; cannot follow a value across languages or into prose, which is where escaping layers bite |
| 2 | Trojan Source / bidichk / unicode lint (CVE-2021-42574 family) | 30% | fixed denylist of *dangerous* invisibles for a security threat model; a backspace inside a regex is harmless-looking and on no list, and they never compare two copies |
| 3 | snapshot testing (jest, pytest-snapshot) | 25% | compares program OUTPUT to a stored snapshot; the pattern itself is still hand-transcribed into the test, which is precisely the unguarded hop |
| 4 | `cat -A` / `hexdump` / `xxd` | 15% | reveal bytes in ONE file; no canonical copy, no witness set, no verdict |
| 5 | `git diff --check`, whitespace-error highlight | 10% | whitespace inside one file's own history, not divergence between two live copies |

**Maximum overlap: 35%. Status: NOVEL** (rework bar is 40%).

**EVIDENCE BASE, stated so nobody reads more into it than it holds:** the AIT graph
(`ait.cmd search`, 0 rows on nine candidate words), the fleet (`stay_fleet.py search`, 0 rows across
3 seats), `ait.cmd resolve Artifact VariantCollator` (NONE), the MetaphyKing repo set (293 rows),
and my own knowledge of the tooling landscape. **This is NOT an exhaustive patent or academic
sweep and I am not claiming one.**

---

## M2 - Cross-Domain Synthesis Matrix

**Primary domain:** software verification.

| Domain | Extracted insight | Integrated? |
|---|---|---|
| Bibliography / textual criticism | The **Hinman Collator** (1949) blinked two copies of the Shakespeare First Folio so the eye caught single-character variants invisible on sequential reading. Stop asking "is this file valid?" and ask "do these witnesses of the same text agree?" | **YES - the core operation** |
| Metrology | An instrument never checked against a reference standard reports confidently and wrongly. A test fixture IS an instrument, and nobody calibrates one against the artifact it claims to measure. | **YES - the central claim** |
| Double-entry bookkeeping | Two independent records whose reconciliation is the control. | surveyed |
| Genomics | Sequence alignment names substitutions rather than declaring inequality. | surveyed |
| Proofreading / copy-editing | A mark for every class of difference, including the ones that do not print. | surveyed |
| Numismatics | Die-variant analysis distinguishes copies by sub-visible detail. | surveyed |

**Synthesis strength: 7/10.** Two domains are load-bearing rather than decorative; four are honest
background and I am not counting them.

---

## M3 - Anti-Pattern Detection

**The cliche this could become: "another linter with a rule list."**

Transcended structurally: the tool holds **no opinion about which characters are bad** and ships no
denylist. It reports only that two things claiming to be the same text are not. A denylist could not
have caught the defect that motivated it, because **a backspace in a comment is fine and a backspace
in a regex is fatal, and only the comparison knows which one it is looking at.**

---

## M5 - Five Lockout Checkpoints

| # | Checkpoint | Verdict |
|---|---|---|
| 1 | Rejected the obvious solution, explained why insufficient? | **PASS** - "do not duplicate, import it" is right and unavailable across language, doc and escaping boundaries; the move is to make copies reconcilable, not to delete them |
| 2 | Integrated 2+ structurally necessary cross-domain insights? | **PASS** - Hinman collation (the operation) and metrology calibration (the claim) |
| 3 | Identified and structurally avoided the cliche? | **PASS** - no rule list, by construction |
| 4 | Defeated the strongest counterargument? | **PASS** - answered below, with the limit left standing |
| 5 | Scores 70+? | **PASS - 76** |

---

## M4 - Adversarial Gauntlet

**Strongest counterargument:** *"If the copies must match, this is just a worse single source of
truth."*
**Defeated:** a single source of truth is correct and is unavailable exactly where this fails.
You cannot import a constant into a README example, into a fixture written in another language, or
through a heredoc. The tool is for the copies you are not able to delete.

**Secondary 1:** *"Normalise the bytes and the problem disappears."*
Normalising is what `sed`, `diff` and the editor already did, and it is why the defect survived
review. Normalisation is the failure mode, not the remedy.

**Secondary 2:** *"A pre-commit hook that strips control characters is enough."*
Stripping changes the artifact and would have silently repaired a live matcher without telling
anyone which behaviour changed. Reporting divergence is a different act from editing it.

**Secondary 3:** *"Nobody duplicates literals in a disciplined codebase."*
The motivating defect happened in a disciplined codebase, between a live file and a fixture written
by the same person an hour apart.

**Boundary conditions, stated as limits and not as coverage:**
- It can only compare literals it can **locate**. A value assembled at runtime from fragments is
  out of scope.
- It proves **byte equality**, not semantic equivalence. Two regexes that differ but match the same
  language will be reported as different, correctly by its own definition and possibly unhelpfully.
- It needs a declared canonical copy. Choosing the wrong canon inverts every verdict.

---

## M6 - Novelty Scoring Rubric (honest, no inflation)

| Dimension | Max | Score | Justification |
|---|---|---|---|
| Conceptual - absent from prior work | 10 | 7 | every piece exists somewhere; the assembly is not a shipped tool I can find |
| Conceptual - combines unrelated ideas | 10 | 8 | bibliography and metrology, both load-bearing |
| Conceptual - surprising path | 10 | 8 | inverts the standard remedy from elimination to reconciliation |
| Structural - novel arrangement | 15 | 11 | canonical-plus-witnesses model rather than per-file lint |
| Structural - novel methodology | 10 | 7 | byte-equality classes with named non-rendering characters |
| Domain fitness - field constraints | 10 | 9 | stdlib only, cross-platform, one file, CI-shaped |
| Domain fitness - advances field goals | 10 | 8 | aimed at generated-code workflows where escaping layers are routine |
| Robustness - survives critique | 10 | 7 | strongest objection answered; three real limits remain |
| Robustness - non-obvious derivation | 5 | 4 | required living the defect to see it |
| Synthesis strength | 10 | 7 | two domains genuinely structural, four only surveyed |
| **TOTAL** | **100** | **76** | |

**76/100 - GENUINELY NOVEL (70-79). Clears the STANDARD bar of 70.**

**Dimension check:** no dimension falls below 60% of its maximum (lowest is synthesis strength at
70%), so nothing is carried into OPTIMIZE on score grounds.

---

## M7 - Novelty Transparency Manifest

| Component | Status | Origin |
|---|---|---|
| Witness-set comparison of literals across a tree | **NOVEL** | this build |
| Reporting divergence instead of normalising or stripping it | **NOVEL** | this build; the inversion is the whole idea |
| Naming non-rendering characters by codepoint in the verdict | foundational | Unicode tables, `cat -A` lineage |
| Byte-level file reading | foundational | stdlib |
| Collation as an operation on witnesses | **BORROWED, credited** | Hinman Collator, 1949 |
| Instrument calibration framing | **BORROWED, credited** | metrology |

**The genuine surprise, said plainly:** the tools used to *review* code are the same tools that
*hide* this class of defect, so adding more review cannot find it. The check has to be mechanical
and it has to compare, because a human reading either copy sees exactly what they expect.

**Provenance note:** this idea did not come from a brainstorm. It came from losing a verification to
the defect earlier in this same session and writing down why, which is recorded in `BUILD_LOG.md`.
