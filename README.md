# VMock Clone — rule-based resume scorer

A working reimplementation of VMock's **SMART Resume** scoring engine: upload a
resume PDF, get a 0–100 score split across **Impact (40) · Presentation (30) ·
Competencies (30)**, red/yellow/green zones, sub-parameter breakdowns,
line-by-line bullet feedback, and a peer benchmark curve.

**No language model is involved anywhere.** Every point is a deterministic
function of the weights in `rules.yaml` and the lexicons in
`vmock_clone/lexicons.py`. Run it twice, get the same number.

That is not a shortcut — it is what VMock actually does. VMock's granted patent
**US11120403B2, "Career Analytics Platform"** publishes the formulas outright:

> Presentation = `wp × (w₁α₁rm + w₂α₂rs₁ + w₃α₃rms + w₄α₄rf + w₅α₅rse)`

…where the terms are margins, section layout, section count, formatting
consistency and spelling errors. It describes "a weighted action verb
repository" where "strong action verbs have higher weights", and a skills
database of "over 10,000 skills with corresponding keywords, phrases, patterns".
Classical NLP, hand-built lexicons and weighted feature sums. No LLM appears in
any VMock patent, filing, or user guide.

---

## Calibrated against the real thing

Two resumes were scored by the actual VMock (CMU benchmark) and used as ground
truth. The engine was tuned until it reproduced them:

| Resume | VMock | This clone | Impact | Presentation | Competencies |
|---|---|---|---|---|---|
| Masters&nbsp;2 | **93** | **94.1** | 36 vs 34 | 29 vs 30 | 29 vs 29 |
| Masters&nbsp;1 | **77** | **72.3** | 27 vs 34 | 19 vs 14 | 27 vs 29 |

Mean absolute error: **2.9 points**. Two data points is a small sample -- treat
the agreement as encouraging, not proven.

That exercise overturned several rules taken from published career-centre
guides, and those corrections are the most valuable thing in this repo:

- **The 15-point phone-parenthesis penalty does not fire.** A resume carrying
  `(555) 010-0199` scored **30/30** on Presentation. Now off by default.
- **`Sept.` and `Aug.` are accepted.** Same resume, same 30/30.
- **Articles are not filler.** A resume using "a"/"the" freely was marked green
  on Avoided Words.
- **Technical vocabulary is not spell-checked to death.** `WebSocket`, `JSONL`
  and `ASR` passed cleanly.
- **Bullets can be long.** VMock told a resume whose bullets ran 35-50 words
  that some were *too short*. The 10-26 word target from the guides is wrong.
- **A rule the guides omit entirely:** bullets must be consistent about
  terminal punctuation. *"CMU template recommends that either all bullet points
  should end with a period/full-stop or none of them."* This was the single
  largest Presentation difference between the two resumes (30/30 vs 14/30).

## The quality ladder

`samples/make_ladder.py` builds five resumes spanning the range, and the test
suite asserts the engine ranks them in order:

| Tier | Score | Zone | Impact | Presentation | Competencies |
|---|---|---|---|---|---|
| 1 dogwater | 32.3 | red | 11.3 | 15.0 | 6.0 |
| 2 rough | 51.5 | yellow | 16.2 | 20.9 | 14.4 |
| 3 average | 83.3 | yellow | 28.2 | 30.0 | 25.0 |
| 4 strong | 95.6 | green | 36.9 | 28.7 | 30.0 |
| 5 magnum opus | 96.5 | green | 36.9 | 29.6 | 30.0 |

Building it caught six real bugs, including numbers not counting toward bullet
length (so the most quantified bullets were flagged "too short") and a score of
32.3 falling into neither the red nor the yellow band.

## Quick start

```bash
pip install -r requirements.txt          # pdfplumber, PyYAML (+ reportlab for samples)

python3 run.py                           # local web app at http://127.0.0.1:8420
python3 -m vmock_clone resume.pdf         # CLI: terminal summary + out/…_report.html
```

Nothing leaves the machine. The server binds `127.0.0.1`, parses in-process, and
deletes the temp file.

### Everything the CLI does

```bash
python3 -m vmock_clone resume.pdf                     # score + HTML report
python3 -m vmock_clone resume.pdf --json              # machine-readable
python3 -m vmock_clone resume.pdf --no-quirks         # drop VMock's arbitrary rules
python3 -m vmock_clone resume.pdf --pages 2           # two-page benchmark
python3 -m vmock_clone diff v1.pdf v2.pdf             # what your edit actually bought
python3 -m vmock_clone benchmark ./resumes -n mba     # build a real cohort curve
python3 -m vmock_clone serve --port 9000              # web app on another port
python3 samples/make_samples.py                       # regenerate the example PDFs
python3 -m unittest discover -s tests -v              # 31 tests
```

---

## How the score is built

### Impact — 40

| Sub-parameter | Pts | What it measures |
|---|---|---|
| Action Oriented | 11 | Weighted verb repository. `Spearheaded` (strong, ×1.0) → `Analyzed` (standard, ×0.65) → `Helped` (weak, ×0.2) → `Responsible for` / noun phrase (×0.0). Handles irregular pasts (`Led`→lead) and compounds (`Co-authored`→author). |
| Specifics | 11 | Share of bullets carrying a real number (calendar years excluded) and share naming a tool or method. Passive voice deducts. |
| Overusage | 5 | Same opening verb more than twice; content words repeated across bullets. |
| Avoided Words | 5 | Filler adverbs, vague quantifiers, weasel phrases, pronouns, buzzwords — scored as density, not raw count. |
| Bullet Length | 4 | 10–26 words is the target band; also flags entries with too few or too many bullets. |
| Career Progression | 4 | Seniority ladder across dated roles, plus gaps over 6 months. |

### Presentation — 30

| Sub-parameter | Pts |
|---|---|
| **Overall Format** | **17** — Date Formatting 6 · Section Spacing 4 · Bullet Check 4 · Font & Margins 3 |
| Number of Pages | 4 |
| Essential Sections | 4 |
| Personal Details | 3 |
| Spell Check | 2 |

Overall Format dominates because it does in the real thing: a student sitting at
12/30 was told that fixing format alone would return *"17 of the possible 18
remaining points."*

This module is genuinely geometric. `pdfplumber` gives every word an x/y box and
a font, so margins, right-aligned date columns, indent consistency, blank-line
spacing, font-size sprawl and two-column layouts are all *measured*, not guessed.

### Competencies — 30

Five NACE competencies at 6 points each — **Analytical, Communication,
Leadership, Teamwork, Initiative** — each broken into named facets (Analytical =
Research · Analysis/Evaluation · Technical · Financial, and so on).

Two rules matter, and both mirror real VMock:

1. **It scans everything.** Position titles, degree program, coursework, skills
   lists — not just experience bullets. A keyword in a coursework line scores.
2. **Facet spread beats repetition.** Writing "led" ten times maxes one facet,
   not the competency. Full marks need evidence across distinct facets.

### Zones

`Red 0–32 · Yellow 33–85 · Green 86–100` — VMock's published bands.

There is also a hard floor: under **200 words** the report is marked unscored,
because VMock's own SMART Editor guide says *"You must have at least 200 words
for you to receive a score."*

---

## The quirks system

Real VMock applies rules that are arbitrary, US-specific, or documented as
outright buggy. Reproducing them faithfully is the only way to predict a real
VMock score — but you should not have to live with them.

So every one is individually switchable in `rules.yaml`, and the report tells
you exactly how many points they cost you.

| `quirks.…` | What it reproduces |
|---|---|
| `quirks.…` | Default | What it reproduces |
|---|---|---|
| `phone_parens_penalty` | **off** | −15 points for `(617) 555-0123`. Documented by BU, **contradicted by measurement**. |
| `strict_month_abbreviations` | **off** | Rejects `Sept`. Contradicted by measurement. |
| `articles_are_filler` | **off** | Counts `a`, `the`, `that` as filler. Contradicted by measurement. |
| `aggressive_spellcheck` | **off** | Flags correctly spelled product names. Contradicted by measurement. |
| `heading_ampersand_strict` | on | `Leadership & Activities` passes; `Leadership and Activities` fails. |
| `strict_date_range_spacing` | on | Requires `Jun 2024 - Aug 2024`, not `Jun 2024-Aug 2024`. |
| `email_lowercase` | on | Requires the email address in all lowercase. |

The four defaulted **off** are the ones real VMock output disproved. They are
kept, fully implemented, because they are what the published guides say — flip
them on to see what the folklore would have cost you.

```yaml
quirks:
  strict_vmock_quirks: false     # kill all of them at once
```

Every finding the report shows carries the deduction it actually caused: the
"+N points available" figures are rescaled to the real deficit, so the numbers
in "Biggest wins available" can never add up to more than you have left to
gain. A test enforces this.

---

## Benchmarking

VMock's bell curve is not a universal standard. Each institution uploads its own
historical resumes and students are plotted against *that* population
("benchmarked against your peers at Northwestern"). The default curve here is
synthetic and labelled as such. Build a real one:

```bash
python3 -m vmock_clone benchmark ./folder_of_resumes -n mba --label "MBA class of 2027"
python3 -m vmock_clone resume.pdf --benchmark mba
```

---

## Layout

```
run.py                     launcher for the web app
rules.yaml                 every weight, threshold and quirk toggle
requirements.txt
vmock_clone/
  parser.py                PDF → words/lines with geometry; two-column and
                           wrapped-bullet handling, (cid:NNN) glyph decoding
  sections.py              contact block, headings, entries, date grammar
  lexicons.py              verbs, fillers, competency facets, seniority ladder
  spell.py                 dictionary lookup, no dependency
  modules/impact.py        Impact /40 + per-bullet analysis
  modules/presentation.py  Presentation /30
  modules/competencies.py  Competencies /30
  scoring.py               orchestration, zones, benchmark percentile
  report.py                self-contained HTML + terminal summary
  server.py                stdlib-only local web app
  benchmark.py             build a cohort curve from a folder of PDFs
  data/en_us_words.txt     163k-word dictionary (see below)
tools/build_wordlist.py    hunspell .aff/.dic affix expander
web/                       index.html · app.js · style.css (shared renderer)
samples/make_samples.py    generates strong / weak / two-column test resumes
tests/test_engine.py       31 tests
```

### The dictionary

`data/en_us_words.txt` is expanded from the system hunspell dictionary by
`tools/build_wordlist.py`. Hunspell stores words affix-compressed —
`search/AZGMDRS` encodes *search, searches, searching, searcher, research,
researched* — so reading the `.dic` naively makes very common words look
missing. The expander applies the prefix/suffix rules, giving 163k forms with no
runtime dependency. Commonwealth spellings (`honours`, `organised`) are accepted
by default; set `presentation.spell.commonwealth_ok: false` to get VMock's
US-only behaviour.

---

## Parsing notes

Real resumes are mostly LaTeX and Word exports, and both break naive parsers.
Handled explicitly, each after being caught on an actual file:

- **PDFs with no space characters.** LaTeX positions glyphs by kerning; word
  gaps are ~0.25 em, narrower than pdfplumber's default 3pt split tolerance, so
  a whole line fuses into `CarnegieMellonUniversity`. The parser uses a
  size-relative tolerance and re-extracts automatically if the page still looks
  glued.
- **Small-caps section headings.** `\textsc{Education}` emits `E` + `DUCATION`
  as separate runs; rejoined before matching.
- **Overlapping line boxes.** A 25pt name and the 10pt contact line beneath it
  overlap vertically. Lines are grouped by baseline proximity, not box overlap.
- **Wrapped bullets**, including words hyphenated across the break.
- **Two-column layouts**, detected by counting rows with text on both sides of
  a gutter, then parsed column by column and penalised.
- **`(cid:NNN)` glyphs** from fonts with no ToUnicode map.
- **Ambiguous bullet characters**: a line starting "of the team" is not a
  bullet, however much `o` looks like one.

## What this does *not* do

Deliberate limits, stated plainly:

- **Not an ATS simulator.** VMock's SMART Resume score compares you to a cohort
  of resumes, not to a job posting. Keyword-matching against a specific job
  description is a separate VMock module (Resume Optimizer) and is not built
  here.
- **No fact checking.** Like VMock, it rewards the *presence* of a number, not
  its truth.
- **No claim to predict interviews.** No published evidence exists that a VMock
  score correlates with callbacks, and none is claimed for this.
- **Tuned to 1–2 page industry resumes.** Academic CVs with publication lists
  score badly here, exactly as they do in the real product.
- **PDF only.** Export from Word; do not upload a scanned image.
- **Resume module only.** VMock also sells SMART Editor, Resume Optimizer, Cover
  Letter, Elevator Pitch, Mock/SMART Interview, Aspire (LinkedIn) and Career
  Fit. None of those are in scope.

## Provenance

Scoring structure and rule specifics were reconstructed from: VMock patent
US11120403B2; VMock-authored user guides distributed by FIU, Bentley, SJSU,
High Point, UQ and others; Boston University College of Engineering's published
VMock rule sheet; the University of Windsor tip sheet; and reporting in *Inside
Higher Ed* (Dec 2019) and Illinois Tech's *TechNews* (Feb 2025).

Independent project, not affiliated with or endorsed by VMock Inc.
