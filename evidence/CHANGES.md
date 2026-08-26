# Clone vs VMock — what changed, what's left

Status after diffing against **five** real VMock reports across two benchmark
profiles.

## Scoreboard

| Resume | Benchmark | VMock | Clone | Δ | Impact | Presentation | Competencies |
|---|---|---|---|---|---|---|---|
| Brendan 69 | CMU Resumes | **69** | **67.6** | −1.4 | 30 → 30.1 | 10 → 10.0 | 29 → 27.5 |
| Brendan 77 | CMU Resumes | **77** | **77.1** | +0.1 | 34 → 34.1 | 14 → 14.0 | 29 → 29.0 |
| Brendan 93 | CMU Resumes | **93** | **93.1** | +0.1 | 34 → 34.1 | 30 → 30.0 | 29 → 29.0 |
| Resume_Masters_1 | CMU Masters – Technical | **61** | **60.4** | −0.6 | 26 → 25.4 | 12 → 12.0 | 23 → 23.0 |
| Yuxuan_Cai_Resume_Aug | CMU Masters – Technical | **93** | **94.2** | +1.2 | 34 → 35.2 | 29 → 30.0 | 30 → 29.0 |

**Worst error 1.4 points. Mean absolute error 0.68.**

Beyond the totals, the engine now reproduces the *panels*:

- **Spell Check reproduces its lists word for word** on both resumes where the
  panel was read — the 69's red `rebasing · webhook · idempotency` and both
  resumes' yellow `Soniox · JSONL · DEFINER · Duffing · WebSockets · Supabase`,
  with the same chip (Needs Work! / On Track!).
- **Section Specific fails on exactly the checks VMock failed** — Degree
  Styling and Job Title Styling on the 69 with Personal Details clean, Phone
  Number alone on Masters_1.
- **"Good Job!" panels carry praise and nothing else**, as VMock's do.

- **Every Overall Format checklist matches check for check.** 69 → the same 3
  failures out of 9; 77 → the same 1 out of 9; 93 → 9/9 pass; Masters_1 → the
  same 4 failures out of 11; Yuxuan → 11/11 pass.
- **Every observed status chip matches.** Masters_1's Impact reads Good Job! /
  On Track! / On Track! / Needs Work! exactly as VMock printed it.
- **Overuse reproduces VMock's chips verbatim** — `Analyzed 3`,
  `Provided/Providing 3` on Masters_1; `Developed 3`, `Support/Supporting 3`
  on Yuxuan's.
- **Avoided Words reproduces the counts** — `The`, `Have`, `That` and `I 7`,
  `My 4`, `I Am 3`, `I Will 1`, `I Have 1` on Masters_1.

---

## DONE — changes made from observation

1. **Impact sub-parameters replaced with VMock's real set.** Deleted the two
   this project invented — *Bullet Length & Density*, *Career Progression*.
   Now: Action Oriented · Specifics · Overuse · Avoided Words, plus
   **Extra-curriculars** on the CMU Resumes profile.

2. **Extra-curriculars weighted from arithmetic, not invention.** Brendan's 77
   and 93 are clean on all four shared sub-parameters and still score Impact
   34/40, and they carry no section outside Education / Work Experience /
   Projects / Skills. 40 − 34 = 6. Declared weights sum to 46 on that profile
   and are rescaled by 40/46, which reproduces 34/40 to the decimal.

3. **Presentation is ALL-OR-NOTHING per sub-parameter.** The decisive evidence:
   two byte-identical resumes differing only in whether 14 or 19 bullets end in
   a period score 14 and 30. Solving the five observed Presentation totals for
   integer weights gave a unique solution — Overall Format 16, Number of Pages
   1, Essential Sections 9, Section Specific 1, Spell Check 3.

4. **Overall Format is VMock's own named checklist**, and the benchmark decides
   which checks run: 11 on CMU Masters – Technical, 9 on CMU Resumes. The
   9-member list was read in full off the 77 report, so the two the smaller
   benchmark drops are known by subtraction: **Bullet Count** and
   **Objective/Summary Length**.

5. **"Image Check", not "Photo Check"** — renamed to the name on screen.

6. **Section Styling implemented** against its now-observed rule text: *"Bold,
   no Italics, Consistent in Title case/Caps, Consistent in alignment"*. It was
   previously a never-fails placeholder.

7. **Overuse fires on a short list of community-common verbs.** Everything
   VMock has been seen to flag: analyze, provide, develop, support. Everything
   that cleared the 3-occurrence threshold and was *not* flagged: Applied (4),
   Lead/Leading (3), Engineered (3), benchmarking (3), model (7). The list in
   `rules.yaml` holds exactly what has been observed and grows only when
   another flag is read off the product.

8. **The filler vocabulary is the three observed words** — `the`, `that`,
   `have`. `A`, `An` and vague quantifiers are gone: VMock's Masters_1 panel
   showed three items at counts 1, 1 and 5, so nothing was truncated, and it
   listed none of them. The 69 → 77 rewrite confirms it — every `the`, `that`
   and `their` was deleted, `a` was left alone, and Impact rose by exactly the
   +4 VMock had promised.

9. **Roman numerals are not pronouns.** VMock green-highlights `I-III` and `II`
   as quantification, so a bare `I` counts only when a lowercase word follows.
   Masters_1 now reports `I 7`, VMock's exact count.

10. **Competencies are continuous in 0.5 steps, not three fixed bands.** A
    {6.0, 2.5, 0.0} band model was refuted by a resume scoring 29/30, which no
    combination of those values over five competencies can produce. Masters_1's
    tooltips ("4 bullets highlighted", "1 bullet highlighted") plus its three
    full competencies give 6+6+6+4+1 = 23, so points track highlighted units
    one for one.

11. **Section Specific rebuilt** as Personal Details / Education / Experience
    with the observed checks. Phone rule verbatim: `(XXX) XXX-XXXX` **is
    accepted**; the `+1` country code is the failure. Job Title Styling now
    styles the title text rather than the whole entry line, so a right-aligned
    date can no longer make two identical entries read as two stylings.

12. **Spell Check: red deducts, yellow never does.** The discriminator is
    capitalisation — an unknown all-lowercase token is a misspelling, an
    unknown token carrying any capital is a proper noun, surfaced free of
    charge.

---

## Known gaps

### Competency detection is a lexicon, not VMock's skill database
VMock resolves competencies through a database its patent describes as ~10,000
skills, and its panels offer "Experiences you can consider" chips drawn from
it. This clone matches a lexicon and recovers fewer units per resume, so the
ramp is calibrated to reach full credit at 5 of *its own* units rather than
VMock's 6. That is a calibration of this detector, not a claim about VMock's.
It is the largest single residual (Brendan's 69, −1.5).

### VMock's GPA parse bug is not replicated
Yuxuan's resume reads `GPA: 3.7/4.0`; VMock's own rendering shows
`GPA: 3.7  4.0` and then fails the check that demands a `/`. That single lost
point is the whole of her Presentation gap (29 vs our 30). Reproducing a parser
defect is not the same as reproducing a rule, so it stays unreplicated.

### Three reason-level differences remain
- **Masters_1's filler count for "The"** reads 8 here, 5 on VMock. Every other
  item on that panel matches exactly, `That 1` and `Have 1` and all five
  pronoun entries included.
- **Yuxuan's re-examine list runs longer than VMock's twelve.** The two agree
  on eleven words; this clone also surfaces ECE, ViT, MCP, DSP, MMD, VLM, UCSF
  and SFT. VMock flags BFCL, CNMAT and DAFx, so it is not simply
  acronym-tolerant — either its dictionary carries the others or its panel caps
  at twelve. Nothing observed settles it.
- **Masters_1's competency chips are attributed differently** (see above): the
  module total is exact, the per-competency split is not.

### Rules still unread
- Extra-curriculars panel text — its weight is arithmetic, its rule is a guess
  narrowed to what the data forces (no Leadership / Honors / Awards /
  Volunteer / Publications section → 0).
- Thresholds behind Font Size Check, References, Page Margins,
  Objective/Summary Length, Image Check, Section Spacing. These are measured
  and reported; only the ones with observed rule text can fail.
- Section Specific → the rest of the Education and Experience group checks.
- Communication / Leadership / Teamwork / Initiative panels.
