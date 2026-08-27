"""
COMPETENCIES  /30

Five NACE-aligned competencies at 6 points each: Analytical, Communication,
Leadership, Teamwork, Initiative.

Two rules matter and both come straight from how VMock behaves:

1. It scans ALL content -- "not only the experience described in your bullet
   points, but also position titles, degree program, any courses, languages,
   software programs". So a keyword planted in a coursework line or a job title
   scores.

2. Full marks need evidence across a competency's distinct facets. Writing
   "led" ten times will not max out Leadership; it will max out one facet.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from ..core import Config, Finding, ModuleScore, SubScore, clamp
from ..lexicons import (
    COMPETENCY_LABELS,
    COMPETENCY_LEXICON,
    FACET_LABELS,
    SPOKEN_LANGUAGES,
)
from ..parser import Document
from ..sections import Structure

# Sections whose content is scanned. "all" per VMock, but headings themselves
# are excluded so a section literally titled "Leadership" cannot self-award.
_SKIP_SECTION_KINDS = ("summary",)


def _compile(term: str) -> re.Pattern:
    if " " in term or "/" in term:
        return re.compile(re.escape(term), re.I)
    return re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.I)


_PATTERNS: Dict[str, Dict[str, List]] = {
    comp: {facet: [(t, _compile(t)) for t in terms] for facet, terms in facets.items()}
    for comp, facets in COMPETENCY_LEXICON.items()
}


_LANG_LABEL_RE = re.compile(r"\b(spoken\s+)?languages?\b\s*[:\u2013\u2014-]", re.I)


def _language_evidence(st: Structure):
    """(count, text) for a line or section naming two or more spoken languages.

    VMock's guide says it scans "position titles, degree program, any courses,
    languages, software programs". Someone operating in three languages is
    showing interpersonal range that no verb in the bullet points will match.
    """
    best = (0, "")
    for sec in st.sections:
        for line in sec.lines:
            text = line.text or ""
            labelled = sec.canonical == "languages" or _LANG_LABEL_RE.search(text)
            if not labelled:
                continue
            found = {
                w.lower()
                for w in re.findall(r"[A-Za-z]+", text)
                if w.lower() in SPOKEN_LANGUAGES
            }
            if len(found) > best[0]:
                best = (len(found), text[:110])
    return best


_DATE_ONLY_RE = re.compile(
    r"^[\s\-\u2013\u2014|,.]*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
    r"|\d{4}|\d{1,2}|present|current|to|now|[\s\-\u2013\u2014|,.])+$",
    re.I,
)


def _is_date_only(text: str) -> bool:
    """A line that is nothing but a date range demonstrates no skill.

    "June 2026 - Present" was matching the Communication term `present` and
    scoring the competency once per dated entry.
    """
    return bool(_DATE_ONLY_RE.match((text or "").strip()))


def _collect_units(st: Structure):
    """(text, source_label, weight_class) tuples covering the whole document."""
    units = []
    bullet_rank = 0
    for sec in st.sections:
        if sec.canonical in _SKIP_SECTION_KINDS:
            continue
        label = sec.raw_heading
        for entry in sec.entries:
            for hl in entry.header_lines:
                units.append((hl.text, f"{label} · entry", "header", None))
            for b in entry.bullets:
                units.append((b.body_text, label, "bullet", bullet_rank))
                bullet_rank += 1
        # loose lines (skills lists, coursework) that are not inside an entry
        seen = {id(l) for e in sec.entries for l in (e.header_lines + e.bullets)}
        for line in sec.lines:
            if id(line) not in seen:
                units.append((line.text, label, "line", None))
    return units


def score(doc: Document, st: Structure, cfg: Config) -> ModuleScore:
    """Band-scored competencies, matching the observed model.

    OBSERVED (two reports, CMU Masters - Technical):
        Yuxuan  30/30 = five "Good Job!"           -> Good Job = 6.0
        Masters_1 23/30 = three "Good Job!" + two "On Track!"
                                                   -> On Track = 2.5
    The band is driven by how many BULLETS exhibit the competency -- VMock's
    tooltip reads "<Competency> bullets highlighted" and the highlighted count
    tracks the band (1 bullet -> On Track, 4 -> On Track, ~15 -> Good Job).

    The "facet breadth" requirement this project previously used does not exist
    in VMock and has been removed.
    """
    mx = float(cfg.get("modules.competencies", 30))
    good_pts = float(cfg.get("competencies.points_each", 6.0))
    good_at = float(cfg.get("competencies.units_for_full_credit", 4))
    step = float(cfg.get("competencies.rounding_step", 0.5))
    good_chip = float(cfg.get("competencies.chip_good_job_at", 5.0))
    track_chip = float(cfg.get("competencies.chip_on_track_at", 2.5))
    # OBSERVED: although the tooltip says "<Competency> bullets highlighted",
    # the Analytical highlights on the 93 resume cover the EDUCATION degree
    # lines and the entire SKILLS block as well as the bullets. Competencies
    # are therefore scanned across the whole document.
    skip = set(cfg.get("competencies.skip_sections", []) or [])
    distinct_evidence = bool(cfg.get("competencies.distinct_evidence", False))
    bullets = []
    for sec in st.sections:
        if sec.canonical in skip:
            continue
        seen = set()
        for entry in sec.entries:
            for hl in entry.header_lines:
                if not _is_date_only(hl.body_text):
                    bullets.append(hl.body_text)
                seen.add(id(hl))
            for b in entry.bullets:
                bullets.append(b.body_text)
                seen.add(id(b))
        for line in sec.lines:
            if id(line) not in seen:
                bullets.append(line.body_text)

    wanted = cfg.get("competencies.list", list(COMPETENCY_LEXICON)) or []
    known = [c for c in wanted if c in COMPETENCY_LEXICON] or list(COMPETENCY_LEXICON)

    subs: List[SubScore] = []
    for comp in known:
        facets = _PATTERNS.get(comp, {})
        hits = []
        distinct = set()
        for text in bullets:
            found = {
                term
                for pats in facets.values()
                for term, pat in pats
                if pat.search(text)
            }
            if found:
                hits.append(text)
                distinct |= found

        # Four bullets that all open "Supported" are one skill shown four
        # times, not four skills. VMock resolves competency evidence against a
        # skills database, and on the same resume its Overuse panel flags the
        # very words that were inflating this count. Counting lines instead of
        # skills let a narrow resume saturate every competency.
        units = len(distinct) if distinct_evidence else len(hits)

        label = COMPETENCY_LABELS.get(comp, comp.title())
        noun = label.lower()
        # Continuous, quantised to `step`. The earlier three-band model was an
        # over-reading of two reports: a third resume scored Competencies 29/30,
        # which no combination of {6.0, 2.5, 0.0} over five competencies can
        # produce. Fine-grained scoring reproduces 30, 29 and 23 alike.
        raw = good_pts * min(1.0, units / good_at) if good_at else good_pts
        pts = round(raw / step) * step
        status = ("Good Job!" if pts >= good_chip
                  else "On Track!" if pts >= track_chip else "Needs Work!")
        # The chip and the points are separate judgements: a competency can
        # read as the top chip and still sit under full marks. Praise is for
        # full marks only -- otherwise the missing point goes unexplained.
        if pts >= good_pts - 0.005:
            sev = "good"
            msg = f"You are doing a great job reflecting your {noun} skills!"
        else:
            sev = "warn" if pts >= track_chip else "error"
            msg = (f"We recommend you to add more experiences which reflect "
                   f"your {noun} skills well.")

        sub = SubScore(comp, f"{label} Skills", pts, good_pts)
        sub.status = status
        sub.findings.append(
            Finding(sev, msg, max(0.0, good_pts - pts),
                    evidence=hits[0][:110] if hits else "",
                    fix="" if sev == "good" else
                        "Add a bullet describing an experience that demonstrates it.")
        )
        sub.detail = {
            "bullets_highlighted": len(hits),
            "units_for_full_credit": good_at,
            "distinct_skills": len(distinct),
            "examples": hits[:6],
            # VMock also shows "Experiences you can consider" chips drawn from
            # its ~10,000-skill database. Not reproducible from a lexicon and
            # deliberately not faked here.
            "suggested_experiences": None,
        }
        subs.append(sub)

    total = sum(x.points for x in subs)
    declared = sum(x.max_points for x in subs)
    if declared and abs(declared - mx) > 0.01:
        total *= mx / declared
    mod = ModuleScore("competencies", "Competencies", clamp(total, 0, mx), mx, subs)
    if not bullets:
        mod.findings.append(Finding("error", "No bullets to scan for competencies.", 0.0))
    return mod
