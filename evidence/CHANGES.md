# Clone vs VMock — what changed, what's left

Status after diffing against three real VMock reports.

## Scoreboard

| Resume | Benchmark | VMock | Clone | Impact | Presentation | Competencies |
|---|---|---|---|---|---|---|
| Resume_Masters_1 | CMU Masters – Technical | **61** | **64.4** | 26 → 25.5 | 12 → 12.1 | 23 → **26.8** |
| Yuxuan_Cai_Resume_Aug | CMU Masters – Technical | **93** | **88.0** | 34 → **30.3** | 29 → 30.0 | 30 → **27.7** |
| Resume_Masters_2 | CMU Resumes | **93** | **82.5** | 34 → 31.8 | 30 → **20.7** | 29 → 30.0 |

---

## DONE — changes already made from observation

1. **Impact sub-parameters replaced with VMock's real set.**
   Deleted the two this project invented — *Bullet Length & Density*,
   *Career Progression*. Now: Action Oriented · Specifics · Overuse ·
   Avoided Words. All four status chips on Masters_1 match VMock exactly.

2. **Overall Format rebuilt as VMock's 11 named checks** (was 4, of which 3
   were invented names). **11/11 checklist agreement on Masters_1.**
   Bullet Alignment · Bullet Check · Bullet Count · Date Formatting ·
   Font Size Check · References · Page Margins · Objective/Summary Length ·
   Section Styling · Photo Check · Section Spacing

3. **Overuse rewritten to the observed rule** — fires at **3** occurrences,
   groups inflections ("Provided/Providing"), counts **verbs only**, over
   **bullets only**. Previously counted exact tokens at >3 and never fired.

4. **Avoided Words rewritten as VMock's two lists** — filler words *and*
   personal pronouns, reported separately, scanned across the **whole
   document including the summary**, which the clone used to skip entirely.
   Articles are counted (VMock flagged "The 5").

5. **Section Specific rebuilt** as Personal Details / Education / Experience
   with the four observed Personal Details checks. Phone rule is now
   verbatim: `(XXX) XXX-XXXX` **is accepted**; the `+1` country code is the
   failure. This kills the "15-point parenthesis penalty" folklore for good.

6. **Specifics** now counts GPA ratios, roman numerals and spelled-out
   numbers, which VMock highlights as specifics.

7. **Action verb weights raised** (standard 0.65 → 0.92) — VMock rates a
   resume of ordinary past-tense verbs "Good Job!". Added missing verbs
   (Achieved, Owned, Ranked, Replaced, Walk, Set …).

8. **Checks whose rule text was never read cannot fail.** Section Styling,
   Objective/Summary Length and Section Spacing are reported but never
   penalised, because any threshold would be fabricated.

---

## TO DO — known gaps, in priority order

### 1. Competencies is structurally wrong  — biggest remaining error
Masters_1 **+3.8**, Yuxuan **−2.3**, Masters_2 **+1.0**. Not an offset; the
model is wrong. My "facet breadth" requirement appears to be something VMock
does not do — its Analytical panel simply said *"You are doing a great job
reflecting your analytical skills"* and offered suggested experiences.
**Blocked on:** Communication / Leadership / Teamwork / Initiative panels.

### 2. The check set is benchmark-dependent
"CMU Masters – Technical" shows **11** format checks and **4** Impact
sub-parameters. "CMU Resumes" shows **9** checks and **5** Impact
sub-parameters (it has *Extra-curriculars*). Masters_2's 9.3-point
Presentation error is largely my Masters-Technical rules being applied to a
CMU Resumes report. **The engine needs a benchmark profile**, defaulting to
the one we actually observed.

### 3. Overuse over-fires on a strong resume
Yuxuan: 1.33/8 while VMock gave her Impact 34/40. The per-flag cost or the
verb-grouping is too aggressive on a longer resume. Needs her Overuse panel.

### 4. Never observed at all
- Spell Check panel
- Section Specific → Education and Experience group checks
- Extra-curriculars rule text
- Four of five Competencies panels
- Per-check point values (VMock never displays them — the cost-per-failed-check
  in `rules.yaml` is **fitted to one data point** and labelled as such)

---

# Round 4 update — Competencies rebuilt on the observed model

## Replaced (was wrong)
The "facet breadth" model was **invented by this project**. VMock does not do it.

## Now implemented (observed)
Competencies are **banded, not continuous**:

| Band | Points | Message |
|---|---|---|
| Good Job! | **6.0** | "You are doing a great job reflecting your `<x>` skills!" |
| On Track! | **2.5** | "We recommend you to add more experiences which reflect your `<x>` skills well." |
| Needs Work! | 0.0 | same wording as On Track |

Derived from: Yuxuan 30/30 = 5 x Good Job; Masters_1 23/30 = 3 x Good Job +
2 x On Track. `Resume_Masters_1` now scores **exactly 23.0/30**.

Scanning covers the **whole document** — the Analytical highlights on the 93
resume cover the Education degree lines and the entire Skills block, not just
bullets, despite the tooltip saying "bullets highlighted".

## OPEN GAP — competency detection lexicon
The band arithmetic is right; the detector feeding it is not. Chip agreement is
currently 6/10 across the two resumes:

| | VMock | Clone |
|---|---|---|
| Masters_1 Leadership | Good Job! | On Track! (3 units found) |
| Masters_1 Teamwork | On Track! | Good Job! (7 units found) |
| Yuxuan Communication | Good Job! | On Track! (2 units) |
| Yuxuan Leadership | Good Job! | On Track! (2) |
| Yuxuan Teamwork | Good Job! | On Track! (3) |

No threshold fixes this — Leadership under-fires while Teamwork over-fires, so
the *ranking* is wrong, not the cutoff. VMock's patent claims a database of
"over 10,000 skills with corresponding keywords, phrases, patterns" mapped to
competencies; a 378-term hand lexicon cannot stand in for it.

**What would close it:** per-competency highlight screenshots. Each one gives
the exact set of lines VMock attributes to that competency, which is ground
truth for the mapping. Currently held: Masters_1 Teamwork (4 lines) and
Masters_1 Initiative (1 line) only.

---

# Round 5 — three more resumes (Brendan Lin, "CMU Resumes" benchmark)

| Resume | VMock | Impact | Presentation | Competencies |
|---|---|---|---|---|
| Brendan_Lin_Resume_3 | 93 | 34 | 30 | 29 |
| Brendan_Lin_Resume_2 | 77 | 34 | 14 | 29 |
| Brendan_Lin_Resume_1 | 69 | 30 | 10 | 29 |

## DONE this round

1. **Spell Check red/yellow — exact rule found and implemented.**
   Unknown token containing any uppercase -> "Re-examine", **no deduction**.
   Entirely lowercase -> "misspelled", **deducts**. Verified 9/9 against the
   real red/yellow split, and again on 17 words from a second resume. Locked
   by `TestSpellClassification`.
2. **Section Specific -> Education -> Degree Styling** — "No italics, not
   abbreviated" (CMU Resumes) / "Consistent Styling, not abbreviated"
   (CMU Masters - Technical). Rule text is benchmark-specific and now lives in
   the profile.
3. **Section Specific -> Experience -> Job Title Styling** — "Consistent Styling".
4. **Italic detection** now understands LaTeX font names (CMTI/CMMI), without
   which the italics half of Degree Styling could never fire.
5. **CMU Resumes profile** records 9 checks with the 3 known by name
   (Bullet Check, Date Formatting, Font Size Check); the other 6 are left
   unnamed rather than guessed.

## OPEN — Competencies has a band we have not seen

All three of Brendan's resumes score Competencies **29/30**. That number is
**arithmetically impossible** from the two observed bands:

```
29 from {6.0, 2.5, 0.0} over 5 competencies -> IMPOSSIBLE
29 from {6.0, 5.0, 2.5, 0.0}                -> (6,6,6,6,5)
23 from {6.0, 2.5, 0.0}                     -> (6,6,6,2.5,2.5)   [Masters_1]
30 from {6.0, 2.5, 0.0}                     -> (6,6,6,6,6)       [Yuxuan]
```

So either there is a third band around 5.0, or scoring is continuous within a
band and the chip is only a display. **Cannot be resolved without seeing the
five chips on one of Brendan's resumes.**

Separately, the detector still mis-ranks: on Masters_1 VMock rates Leadership
"Good Job" and Teamwork "On Track", while the clone finds more Teamwork
evidence than Leadership. No threshold fixes an inverted ranking.

## Current calibration (5 real resumes)
mean absolute error **7.7 points**, almost entirely Competencies.
