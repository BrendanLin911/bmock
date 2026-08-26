"""
Structure detection: contact block, section headings, entries, bullets, dates.

VMock's "Essential Sections" and "Section Specific" checks run on exactly this
layer, and its competency scan reads *all* of it -- position titles, degree
program, coursework and skills, not only the experience bullets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .lexicons import (
    AMPERSAND_PREFERRED,
    MONTHS_ABBR,
    MONTHS_BAD_ABBR,
    MONTHS_FULL,
    SECTION_SYNONYMS,
    SENIORITY_LADDER,
)
from .parser import Document, Line

# --------------------------------------------------------------------------
# regexes
# --------------------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.\-]?)?(\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}")
PHONE_PARENS_RE = re.compile(r"\(\s*\d{3}\s*\)")
LINKEDIN_RE = re.compile(r"linkedin\.com/[A-Za-z0-9/_\-%.]+", re.I)
GITHUB_RE = re.compile(r"github\.com/[A-Za-z0-9/_\-%.]+", re.I)
URL_RE = re.compile(r"(https?://|www\.)[A-Za-z0-9./_\-%?=&#]+", re.I)
LOCATION_RE = re.compile(
    r"\b([A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+)*),\s*"
    r"([A-Z]{2}\b|[A-Z][a-z]+\b)"
)
GPA_RE = re.compile(r"\bGPA\b[:\s]*([0-4]\.\d{1,2})\s*(?:/\s*([0-5]\.?\d*))?", re.I)

_MONTH_ALT = "|".join(MONTHS_FULL + MONTHS_ABBR + ["sept"])
MONTH_YEAR_RE = re.compile(
    rf"\b(?P<month>{_MONTH_ALT})\.?\s*(?P<year>(19|20)\d{{2}})\b", re.I
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
PRESENT_RE = re.compile(r"\b(present|current|ongoing|now|to date)\b", re.I)
EXPECTED_RE = re.compile(r"\b(expected|anticipated|in progress)\b", re.I)
NUMERIC_DATE_RE = re.compile(r"\b(0?[1-9]|1[0-2])[/\-](19|20)?\d{2}\b")
_DATE_PART = rf"(?:(?:{_MONTH_ALT})\.?(?:\s*(?:19|20)\d{{2}})?|(?:19|20)\d{{2}})"
DATE_RANGE_RE = re.compile(
    rf"(?P<a>{_DATE_PART})"
    r"(?P<sep>\s*[-\u2013\u2014]\s*|\s+to\s+|\s+until\s+)"
    rf"(?P<b>{_DATE_PART}|present|current|now|ongoing)",
    re.I,
)
MONTH_INDEX = {m: i + 1 for i, m in enumerate(MONTHS_FULL)}
MONTH_INDEX.update({m: i + 1 for i, m in enumerate(MONTHS_ABBR)})
MONTH_INDEX["sept"] = 9


def normalize_heading(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[|:•·\-–—_]+$", "", t).strip()
    t = re.sub(r"^[|:•·\-–—_]+", "", t).strip()
    t = re.sub(r"[.,;:]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


_SYNONYM_INDEX: Dict[str, str] = {}
# Second index keyed on the heading with all spaces removed. LaTeX small-caps
# headings arrive as "E DUCATION" / "T ECHNICAL S KILLS" because the large
# first letter and the small remainder are separate glyph runs.
_SQUASHED_INDEX: Dict[str, str] = {}
for canon, variants in SECTION_SYNONYMS.items():
    for v in variants:
        n = normalize_heading(v)
        _SYNONYM_INDEX[n] = canon
        _SQUASHED_INDEX.setdefault(re.sub(r"\s+", "", n), canon)


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9&]+", "", normalize_heading(text))


@dataclass
class DateSpan:
    raw: str
    start_year: Optional[int] = None
    start_month: Optional[int] = None
    end_year: Optional[int] = None
    end_month: Optional[int] = None
    is_present: bool = False
    is_range: bool = False
    separator: Optional[str] = None
    bad_abbrev: Optional[str] = None
    is_expected: bool = False

    @property
    def separator_spacing_ok(self) -> bool:
        """VMock requires space-hyphen-space: "Jun - Aug 2017"."""
        if not self.is_range or self.separator is None:
            return True
        s = self.separator
        if s.strip().lower() in ('to', 'until'):
            return True
        return bool(re.match(r'^\s[-\u2013\u2014]\s$', s))

    @property
    def start_ord(self) -> Optional[int]:
        if self.start_year is None:
            return None
        return self.start_year * 12 + (self.start_month or 1)

    @property
    def end_ord(self) -> Optional[int]:
        if self.is_present:
            return 9999 * 12
        if self.end_year is None:
            return self.start_ord
        return self.end_year * 12 + (self.end_month or 12)


@dataclass
class Entry:
    header_lines: List[Line] = field(default_factory=list)
    bullets: List[Line] = field(default_factory=list)
    dates: List[DateSpan] = field(default_factory=list)

    @property
    def header_text(self) -> str:
        return " | ".join(l.text for l in self.header_lines)

    @property
    def seniority(self) -> int:
        text = self.header_text.lower()
        best = 0
        for level, terms in SENIORITY_LADDER:
            for t in terms:
                if re.search(rf"\b{re.escape(t)}\b", text):
                    best = max(best, level)
        return best


@dataclass
class Section:
    canonical: Optional[str]
    raw_heading: str
    heading_line: Optional[Line]
    lines: List[Line] = field(default_factory=list)
    entries: List[Entry] = field(default_factory=list)

    @property
    def bullets(self) -> List[Line]:
        return [l for l in self.lines if l.is_bullet]

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)


@dataclass
class Structure:
    contact_lines: List[Line] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    name: str = ""
    body_font_size: float = 0.0
    heading_font_size: float = 0.0

    def get(self, canonical: str) -> Optional[Section]:
        for s in self.sections:
            if s.canonical == canonical:
                return s
        return None

    @property
    def canonicals(self) -> List[str]:
        return [s.canonical for s in self.sections if s.canonical]

    @property
    def all_bullets(self) -> List[Line]:
        return [l for s in self.sections for l in s.bullets]

    @property
    def all_entries(self) -> List[Entry]:
        return [e for s in self.sections for e in s.entries]

    @property
    def contact_text(self) -> str:
        return " ".join(l.text for l in self.contact_lines)


# --------------------------------------------------------------------------
# date parsing
# --------------------------------------------------------------------------
def _parse_part(part: str):
    """Return (month, year, is_present) for one side of a date expression."""
    if part is None:
        return None, None, False
    if PRESENT_RE.search(part):
        return None, None, True
    mm = MONTH_YEAR_RE.search(part)
    if mm:
        return MONTH_INDEX.get(mm.group("month").lower()), int(mm.group("year")), False
    bare_month = re.match(rf"\s*({_MONTH_ALT})\.?\s*$", part, re.I)
    if bare_month:
        return MONTH_INDEX.get(bare_month.group(1).lower()), None, False
    ym = YEAR_RE.search(part)
    if ym:
        return None, int(ym.group(0)), False
    return None, None, False


def parse_dates(text: str) -> List[DateSpan]:
    spans: List[DateSpan] = []
    consumed = []
    for m in DATE_RANGE_RE.finditer(text):
        sep = m.group("sep")
        span = DateSpan(raw=m.group(0), is_range=True, separator=sep)
        sm, sy, _ = _parse_part(m.group("a"))
        em, ey, present = _parse_part(m.group("b"))
        span.start_month, span.start_year = sm, sy
        span.end_month, span.end_year, span.is_present = em, ey, present
        # "Jun - Aug 2017": the left side inherits the right side's year
        if span.start_year is None and span.end_year is not None:
            span.start_year = span.end_year
        spans.append(span)
        consumed.append((m.start(), m.end()))

    def _inside(i):
        return any(a <= i < b for a, b in consumed)

    for m in MONTH_YEAR_RE.finditer(text):
        if not _inside(m.start()):
            spans.append(
                DateSpan(
                    raw=m.group(0),
                    start_month=MONTH_INDEX.get(m.group("month").lower()),
                    start_year=int(m.group("year")),
                )
            )
    if not spans:
        for m in YEAR_RE.finditer(text):
            spans.append(DateSpan(raw=m.group(0), start_year=int(m.group(0))))

    low = text.lower()
    expected = bool(EXPECTED_RE.search(text))
    for span in spans:
        span.is_expected = expected
        for bad in MONTHS_BAD_ABBR:
            if re.search(rf"(?<![a-z]){re.escape(bad)}(?![a-z])", low):
                span.bad_abbrev = bad
                break
    return spans


# --------------------------------------------------------------------------
# heading detection
# --------------------------------------------------------------------------
def _modal_size(lines: List[Line]) -> float:
    sizes = [round(l.size, 1) for l in lines if l.size]
    if not sizes:
        return 0.0
    return max(set(sizes), key=sizes.count)


def looks_like_heading(line: Line, body_size: float) -> bool:
    if line.is_bullet:
        return False
    text = line.text.strip()
    if not text or len(text) > 60 or line.word_count > 7:
        return False
    if text.endswith((".", ",", ";")):
        return False
    if EMAIL_RE.search(text) or PHONE_RE.search(text) or URL_RE.search(text):
        return False
    norm = normalize_heading(text)
    known = norm in _SYNONYM_INDEX or squash(text) in _SQUASHED_INDEX
    # A banner-sized line is usually the candidate's name -- but not if it
    # literally reads "Education", and LaTeX templates set section headings
    # well above body size, so this guard only applies to unrecognised text.
    if not known and body_size and line.size >= body_size * 1.35:
        return False
    styled = (
        line.all_caps
        or line.bold_ratio >= 0.6
        or (body_size and line.size >= body_size + 0.6)
    )
    if known and (styled or line.word_count <= 4):
        return True
    # unknown heading text, but visually styled like one
    emphasised = line.bold_ratio >= 0.6 or (body_size and line.size >= body_size + 0.6)
    if emphasised and line.all_caps and line.word_count <= 5 and not re.search(r"\d", text):
        return True
    return False


def build_structure(doc: Document) -> Structure:
    st = Structure()
    lines = doc.lines
    if not lines:
        return st

    body_size = _modal_size([l for l in lines if l.word_count >= 4]) or _modal_size(lines)
    st.body_font_size = body_size

    heading_idx = [i for i, l in enumerate(lines) if looks_like_heading(l, body_size)]
    first_heading = heading_idx[0] if heading_idx else len(lines)

    st.contact_lines = lines[:first_heading]
    if st.contact_lines:
        biggest = max(st.contact_lines, key=lambda l: (l.max_size, l.bold_ratio))
        cand = biggest.text.strip()
        cand = EMAIL_RE.sub("", cand)
        cand = re.sub(r"[|•·]+", " ", cand).strip()
        st.name = cand[:80]
    st.heading_font_size = _modal_size([lines[i] for i in heading_idx]) if heading_idx else 0.0

    bounds = heading_idx + [len(lines)]
    for pos, start in enumerate(heading_idx):
        end = bounds[pos + 1]
        head_line = lines[start]
        norm = normalize_heading(head_line.text)
        canon = _SYNONYM_INDEX.get(norm) or _SQUASHED_INDEX.get(squash(head_line.text))
        if canon is None:
            for key, c in _SYNONYM_INDEX.items():
                if key and (key in norm or norm in key) and abs(len(key) - len(norm)) <= 6:
                    canon = c
                    break
        sec = Section(
            canonical=canon,
            raw_heading=head_line.text.strip(),
            heading_line=head_line,
            lines=lines[start + 1 : end],
        )
        sec.entries = _build_entries(sec.lines)
        st.sections.append(sec)
    return st


def _starts_new_entry(line: Line, current: "Entry") -> bool:
    """Does this non-bullet line begin a new entry, or continue the current one?

    Splitting purely on a header-line count invents entries: a four-line
    education block (school / degree / coursework / honours) becomes two, and
    the orphan is then reported as "entry has no date". Require an actual
    signal instead - a date, or entry-title styling.
    """
    if not current.header_lines:
        return False
    if len(current.header_lines) >= 6:
        return True
    dates = parse_dates(line.text)
    if dates:
        # A line that is *only* a date ("Sept. 2022 - May 2026", "Expected
        # Fall 2026") belongs to the entry above it. Requiring real content
        # alongside the date stops every date line becoming a dateless entry.
        residue = line.text
        for d in dates:
            residue = residue.replace(d.raw, " ")
        residue = re.sub(r"[^A-Za-z]+", " ", residue).strip()
        if len(residue.split()) >= 3:
            return True
    first = current.header_lines[0]
    if line.bold_ratio >= 0.5 and line.bold_ratio >= first.bold_ratio - 0.05:
        return True
    return False


def _build_entries(lines: List[Line]) -> List[Entry]:
    entries: List[Entry] = []
    current: Optional[Entry] = None
    for line in lines:
        # Stray single glyphs (rule fragments, orphaned ligatures) would
        # otherwise become entries and get reported as "entry has no date".
        if len(re.sub(r"[^A-Za-z0-9]", "", line.body_text)) < 2:
            continue
        if line.is_bullet:
            if current is None:
                current = Entry()
                entries.append(current)
            current.bullets.append(line)
        else:
            if current is None or current.bullets or _starts_new_entry(line, current):
                current = Entry()
                entries.append(current)
            current.header_lines.append(line)
            current.dates.extend(parse_dates(line.text))
    return [e for e in entries if e.header_lines or e.bullets]


def ampersand_issue(raw_heading: str) -> Optional[str]:
    """Return the preferred '&' spelling if this heading uses 'and'."""
    norm = normalize_heading(raw_heading)
    if norm in AMPERSAND_PREFERRED:
        return AMPERSAND_PREFERRED[norm]
    sq = squash(raw_heading)
    for k, v in AMPERSAND_PREFERRED.items():
        if re.sub(r"[^a-z0-9&]+", "", k) == sq:
            return v
    return None
