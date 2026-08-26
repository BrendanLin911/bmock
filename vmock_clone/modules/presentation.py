"""
PRESENTATION  /30

Sub-parameters follow VMock's own UI labels. "Overall Format" carries most of
the weight, matching the observed behaviour where fixing format alone was worth
"17 of the possible 18 remaining points".

Everything here is geometric or lexical - margins, alignment, font sizes,
spacing, date grammar, dictionary lookups. No model, no inference.
"""

from __future__ import annotations

import re
import statistics
from typing import List

from ..core import Config, Finding, ModuleScore, SubScore, clamp
from ..lexicons import DISCOURAGED_SECTIONS, ESSENTIAL_SECTIONS
from ..parser import PT_PER_IN, Document, Line
from ..sections import (
    EMAIL_RE,
    GITHUB_RE,
    LINKEDIN_RE,
    LOCATION_RE,
    NUMERIC_DATE_RE,
    PHONE_PARENS_RE,
    PHONE_RE,
    URL_RE,
    Structure,
    ampersand_issue,
    parse_dates,
)
from .. import spell


REFERENCES_RE = re.compile(r"references?\s+(available|upon|on)\s+request", re.I)
EXPECTED_LIKE_RE = re.compile(r"\b(incoming|expected|anticipated|present|current)\b", re.I)
MONTH_YEAR_OK_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|"
    r"april|june|july|august|september|october|november|december)\.?\s+(19|20)\d{2}\b",
    re.I,
)


def _date_x1(line: Line, raw: str):
    """Right edge of the date text inside a line, for right-alignment checks."""
    tokens = [t for t in re.split(r"\s+", raw.strip()) if t]
    if not tokens:
        return None
    last = tokens[-1].lower().strip(".,")
    for w in reversed(line.words):
        if w.text.lower().strip(".,") == last:
            return w.x1
    return None


FULL_MONTHS = {"january", "february", "march", "april", "june", "july",
               "august", "september", "october", "november", "december"}
ABBREV_MONTHS = {"jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
                 "sept", "oct", "nov", "dec"}


def _month_token_style(tok: str):
    """full | abbrev | None.  "May" is ambiguous and carries no style."""
    low = tok.lower().strip(".")
    if low in FULL_MONTHS:
        return "full"
    if low in ABBREV_MONTHS:
        return "abbrev"
    return None


def _date_style(raw: str) -> str:
    low = raw.lower()
    if NUMERIC_DATE_RE.search(low):
        return "numeric"
    # "May" is spelled the same abbreviated or not, so it has to be tested with
    # the full names -- otherwise "May 2026" alongside "December 2027" reads as
    # two competing styles and a clean resume loses points for nothing.
    if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", low):
        return "full-month"
    if re.search(r"\b(jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b", low):
        return "abbrev-month"
    if re.search(r"\b(19|20)\d{2}\b", low):
        return "year-only"
    return "other"


# ---------------------------------------------------------------------------
# OVERALL FORMAT — VMock's own 11 named checks
# ---------------------------------------------------------------------------
# Read directly off the real UI. VMock presents Overall Format as a pass/fail
# checklist, not a graded score.
#
# CMU Masters - Technical Resumes (11 checks, 2026-08-26):
#   FAILING   Bullet Alignment · Bullet Check · Bullet Count · Date Formatting
#   PASSING   Font Size Check · References · Page Margins ·
#             Objective/Summary Length · Section Styling · Image Check ·
#             Section Spacing
#
# CMU Resumes (9 checks, read off the 77 report):
#   FAILING   Bullet Check
#   PASSING   Bullet Alignment · Date Formatting · Font Size Check ·
#             References · Page Margins · Section Styling · Image Check ·
#             Section Spacing
#
# The 9-check list is complete as read, so the two checks the CMU Resumes
# benchmark drops are Bullet Count and Objective/Summary Length. That is
# arithmetic on an observed list, not an inference about behaviour.
#
# Rule text was read verbatim for every check seen failing, plus Section
# Styling. For the rest only the NAME was observed -- the threshold behind each
# is unknown and is marked below. Nothing here is a guessed rule dressed up as
# a real one.


class Check:
    """One named Overall Format check. passed=None means 'not implemented'."""

    def __init__(self, key, label, passed, message="", evidence="", observed_rule=True):
        self.key, self.label = key, label
        self.passed, self.message, self.evidence = passed, message, evidence
        self.observed_rule = observed_rule


def _chk_bullet_alignment(doc, st, cfg):
    """OBSERVED rule: "All bullets must be consistently aligned"."""
    bullets = st.all_bullets
    if not bullets:
        # A two-column layout still breaks alignment even when no bullet glyphs
        # were recovered from it.
        return Check("bullet_alignment", "Bullet Alignment", not doc.two_column,
                     "All bullets must be consistently aligned",
                     "two-column layout detected" if doc.two_column else "")
    indents = sorted({round(b.indent, 0) for b in bullets})
    ok = len(indents) <= 1 and not doc.two_column
    why = f"bullets start at {len(indents)} different indents: {indents[:8]}"
    if doc.two_column:
        why = "two-column layout detected; " + why
    return Check("bullet_alignment", "Bullet Alignment", ok,
                 "All bullets must be consistently aligned", why)


def _chk_bullet_check(doc, st, cfg):
    """OBSERVED rule: "Consistent use of periods; Only solid round (bullet)
    symbols should be used"."""
    bullets = st.all_bullets
    if not bullets:
        return Check("bullet_check", "Bullet Check", True)
    glyphs = {b.bullet_glyph for b in bullets if b.bullet_glyph}
    non_round = sorted(g for g in glyphs if g not in "\u2022\u25cf\u25aa")
    prose = [b for b in bullets if b.word_count >= 4]
    ended = [b for b in prose if b.body_text.rstrip().endswith((".", "!", "?"))]
    mixed = bool(prose) and 0 < len(ended) < len(prose)
    ok = not non_round and not mixed
    why = []
    if non_round:
        why.append("non-round bullet symbols: " + " ".join(non_round))
    if mixed:
        why.append(f"{len(ended)} of {len(prose)} bullets end with a period")
    return Check("bullet_check", "Bullet Check", ok,
                 "Consistent use of periods; Only solid round (\u2022) bullet symbols "
                 "should be used", "; ".join(why))


def _chk_bullet_count(doc, st, cfg):
    """OBSERVED rule: "CMU recommends that bullets points should not be
    included in \"Skills\" section"."""
    offenders = [sec for sec in st.sections
                 if sec.canonical in ("skills", "coursework") and sec.bullets]
    ok = not offenders
    return Check("bullet_count", "Bullet Count", ok,
                 'CMU recommends that bullets points should not be included in '
                 '"Skills" section',
                 ", ".join(f"{s.raw_heading} ({len(s.bullets)} bullets)"
                           for s in offenders[:3]))


def _chk_date_formatting(doc, st, cfg):
    """OBSERVED rule: "Consistent date format throughout the section (Acceptable
    format in Education Section: Month YYYY; Acceptable formats for other
    sections: Month YYYY, Month YYYY - Month YYYY ...)" (UI text truncated)."""
    bad = []
    for sec in st.sections:
        for entry in sec.entries:
            for span in entry.dates:
                if span.bad_abbrev:
                    bad.append(span.raw)
                elif sec.canonical == "education" and span.is_range and not span.is_present:
                    pass
        for line in sec.lines + [l for e in sec.entries for l in e.header_lines]:
            if EXPECTED_LIKE_RE.search(line.text) and not MONTH_YEAR_OK_RE.search(line.text):
                bad.append(line.text.strip()[:40])
    # OBSERVED rule headline: "Consistent date format throughout the section".
    # Ziqi's resume writes "Aug"/"Jul"/"Sep"/"Jan" everywhere but "June 2026"
    # on one entry, and VMock FAILS it; Yuxuan / Ryan / Brendan-93 each use one
    # month style throughout and pass.  "May" is spelled the same either way,
    # so it can never be evidence of a style, and neither can a bare year.
    styles = {}
    for sec in st.sections:
        for entry in sec.entries:
            for span in entry.dates:
                for tok in re.findall(r"[A-Za-z]+", span.raw):
                    style = _month_token_style(tok)
                    if style:
                        styles.setdefault(style, []).append(tok)
    if len(styles) > 1:
        bad.append("mixed month styles: " + "; ".join(
            f"{k} ({', '.join(dict.fromkeys(v))})" for k, v in styles.items()))

    bad = list(dict.fromkeys(bad))
    return Check("date_formatting", "Date Formatting", not bad,
                 "Consistent date format throughout the section (Acceptable format "
                 "in Education Section: Month YYYY; Acceptable formats for other "
                 "sections: Month YYYY, Month YYYY - Month YYYY)",
                 "; ".join(bad[:4]))


def _chk_font_size(doc, st, cfg):
    """Name observed; threshold NOT observed."""
    heading_ids = {id(s.heading_line) for s in st.sections if s.heading_line}
    body = [l for l in doc.lines if l.word_count >= 4 and id(l) not in heading_ids]
    sizes = sorted({round(l.size, 1) for l in body if l.size})
    limit = int(cfg.get("presentation.geometry.max_distinct_body_font_sizes", 2))
    return Check("font_size_check", "Font Size Check", len(sizes) <= limit,
                 "", f"body font sizes: {sizes}", observed_rule=False)


def _chk_references(doc, st, cfg):
    """Name observed; threshold NOT observed. Implemented as the presence of a
    references line, which is what the name plainly denotes."""
    hit = REFERENCES_RE.search(doc.text)
    return Check("references", "References", not hit, "",
                 hit.group(0)[:60] if hit else "", observed_rule=False)


def _chk_page_margins(doc, st, cfg):
    """Name observed; threshold NOT observed."""
    lo = float(cfg.get("presentation.geometry.margin_min_in", 0.35)) * PT_PER_IN
    bad = []
    for page in doc.pages:
        for k, v in (("left", page.left_margin), ("right", page.right_margin),
                     ("top", page.top_margin), ("bottom", page.bottom_margin)):
            if v < lo - 2:
                bad.append(f"p{page.number} {k} {v/PT_PER_IN:.2f}\u2033")
    return Check("page_margins", "Page Margins", not bad, "", ", ".join(bad[:4]),
                 observed_rule=False)


def _chk_objective_length(doc, st, cfg):
    """Name observed. Threshold NOT observed -- a 219-word Personal Statement
    PASSED this check on the real product, so any word limit we picked would be
    a fabrication. Measured and reported, never failed."""
    sec = st.get("summary")
    words = sum(l.word_count for l in sec.lines) if sec else 0
    return Check("objective_summary_length", "Objective/Summary Length", True,
                 "", f"{words} words" if words else "", observed_rule=False)


SECTION_STYLING_RULE = ("Bold, no Italics, Consistent in Title case/Caps, "
                       "Consistent in alignment")


def _heading_case(text: str) -> str:
    """caps | title | other -- the two case styles the rule text names."""
    words = [w for w in re.split(r"[^A-Za-z&/]+", text) if w]
    letters = [c for c in text if c.isalpha()]
    if not letters or not words:
        return "other"
    if all(c.isupper() for c in letters):
        return "caps"
    # Title case tolerates lowercase joiners ("Skills and Interests"), which is
    # how the style is conventionally written.
    minor = {"and", "of", "in", "the", "a", "an", "for", "to", "or", "&"}
    if all(w[0].isupper() or w.lower() in minor for w in words):
        return "title"
    return "other"


def _heading_alignment(line: Line, page) -> str:
    """left | center | right, measured against the page's own content box."""
    if page is None:
        return "left"
    left_gap = line.x0 - page.left_margin
    right_gap = (page.width - page.right_margin) - line.x1
    if left_gap <= 6:
        return "left"
    if right_gap <= 6 and left_gap > 6:
        return "right"
    if abs(left_gap - right_gap) <= max(12.0, 0.06 * (right_gap + left_gap)):
        return "center"
    return "indented"


def _chk_section_styling(doc, st, cfg):
    """OBSERVED rule: "Bold, no Italics, Consistent in Title case/Caps,
    Consistent in alignment"."""
    heads = [s_ for s_ in st.sections if s_.heading_line is not None]
    if not heads:
        return Check("section_styling", "Section Styling", True,
                     SECTION_STYLING_RULE, "")

    pages = {p.number: p for p in doc.pages}
    why = []

    not_bold = [s_.raw_heading for s_ in heads
                if s_.heading_line.bold_ratio < 0.5]
    if not_bold:
        why.append("not bold: " + ", ".join(not_bold[:4]))

    italic = [s_.raw_heading for s_ in heads
              if any(w.italic for w in s_.heading_line.words)]
    if italic:
        why.append("italicised: " + ", ".join(italic[:4]))

    cases = {}
    for s_ in heads:
        cases.setdefault(_heading_case(s_.raw_heading), []).append(s_.raw_heading)
    if len(cases) > 1:
        why.append("mixed case styles: " +
                   "; ".join(f"{k} ({', '.join(v[:2])})" for k, v in cases.items()))

    aligns = {}
    for s_ in heads:
        a = _heading_alignment(s_.heading_line, pages.get(s_.heading_line.page))
        aligns.setdefault(a, []).append(s_.raw_heading)
    if len(aligns) > 1:
        why.append("mixed alignment: " +
                   "; ".join(f"{k} ({', '.join(v[:2])})" for k, v in aligns.items()))

    return Check("section_styling", "Section Styling", not why,
                 SECTION_STYLING_RULE, "; ".join(why))


def _chk_image(doc, st, cfg):
    """Name observed ("Image Check", read off the 77 report); threshold NOT
    observed."""
    n = sum(p.n_images for p in doc.pages)
    return Check("image_check", "Image Check", n == 0, "",
                 f"{n} embedded image(s)" if n else "", observed_rule=False)


def _chk_section_spacing(doc, st, cfg):
    """Name observed; threshold NOT observed."""
    gaps = [l.space_above for l in doc.lines if 0 < l.space_above < 40]
    if not gaps or not st.sections:
        return Check("section_spacing", "Section Spacing", True, observed_rule=False)
    typical = statistics.median(gaps)
    tight = [s for s in st.sections
             if s.heading_line is not None and 0 < s.heading_line.space_above < typical * 1.35]
    # Threshold NOT observed: this resume has visibly uneven section gaps and
    # still PASSED on the real product. Reported, not penalised.
    return Check("section_spacing", "Section Spacing", True, "",
                 ", ".join(s.raw_heading for s in tight[:3]), observed_rule=False)


OVERALL_FORMAT_CHECKS = [
    _chk_bullet_alignment, _chk_bullet_check, _chk_bullet_count, _chk_date_formatting,
    _chk_font_size, _chk_references, _chk_page_margins, _chk_objective_length,
    _chk_section_styling, _chk_image, _chk_section_spacing,
]


def _overall_format(doc: Document, st: Structure, cfg: Config) -> SubScore:
    mx = float(cfg.get("presentation.overall_format", 17))
    sub = SubScore("overall_format", "Overall Format", mx, mx)
    per_fail = float(cfg.get("presentation.points_per_failed_format_check", 3.1))

    profile = cfg.get("benchmark_profiles.default", "cmu_masters_technical")
    allowed = cfg.get(f"benchmark_profiles.{profile}.format_checks")
    results = [fn(doc, st, cfg) for fn in OVERALL_FORMAT_CHECKS]
    if allowed:
        order = {k: i for i, k in enumerate(allowed)}
        results = sorted((c for c in results if c.key in order),
                         key=lambda c: order[c.key])
    failed = [c for c in results if c.passed is False]
    sub.points = clamp(mx - per_fail * len(failed), 0, mx)

    for c in failed:
        sub.findings.append(
            Finding("error", c.label, per_fail, evidence=c.evidence,
                    fix=c.message or "Rule text not yet read from VMock.")
        )
    passed = [c for c in results if c.passed is not False]
    sub.findings.append(
        Finding("good", f"{len(passed)} Checks meet guidelines",
                0.0, evidence=", ".join(c.label for c in passed))
    )
    sub.detail = {
        "checks": [
            {"key": c.key, "label": c.label, "passed": c.passed,
             "rule_observed": c.observed_rule, "evidence": c.evidence}
            for c in results
        ],
        "failed": len(failed),
        "total": len(results),
    }
    return sub


def _number_of_pages(doc: Document, st: Structure, cfg: Config) -> SubScore:
    mx = float(cfg.get("presentation.number_of_pages", 4))
    sub = SubScore("number_of_pages", "Number of Pages", mx, mx)
    limit = int(cfg.get("presentation.geometry.page_limit", 1))
    grace = float(cfg.get("presentation.geometry.page_limit_grace", 0.15))
    n = doc.n_pages
    last_fill = doc.pages[-1].fill_ratio if doc.pages else 0.0

    if n <= limit:
        sub.points = mx
        sub.findings.append(Finding("good", f"{n} page(s) - within the {limit}-page benchmark."))
    elif n == limit + 1 and last_fill <= grace:
        sub.points = mx * 0.5
        sub.findings.append(
            Finding("error",
                    f"Page {n} holds only {last_fill*100:.0f}% of a page of content.",
                    mx * 0.5,
                    fix="Delete the trailing page. A near-empty final page counts as a full page.")
        )
    else:
        sub.points = 0.0
        sub.findings.append(
            Finding("error", f"{n} pages against a {limit}-page benchmark.", mx,
                    fix=f"Cut to {limit} page(s): drop the weakest bullets and tighten wording.")
        )
    sub.detail = {"pages": n, "limit": limit, "last_page_fill": round(last_fill, 3)}
    return sub


def _essential_sections(doc: Document, st: Structure, cfg: Config) -> SubScore:
    mx = float(cfg.get("presentation.essential_sections", 4))
    sub = SubScore("essential_sections", "Essential Sections", mx, mx)
    present = set(st.canonicals)
    per = mx / max(1, len(ESSENTIAL_SECTIONS))
    lost = 0.0
    for need in ESSENTIAL_SECTIONS:
        if need not in present:
            lost += per
            sub.findings.append(
                Finding("error", f"Missing required section: {need.title()}.", per,
                        fix=f"Add a clearly titled {need.title()} section.")
            )

    per_unknown = float(cfg.get("presentation.points_per_unknown_section", 1.0))
    cap_unknown = float(cfg.get("presentation.max_unknown_section_loss", 2.0))
    unknown_lost = 0.0
    for sec in st.sections:
        if sec.canonical is None:
            unknown_lost = min(cap_unknown, unknown_lost + per_unknown)
            sub.findings.append(
                Finding("error", f"Section heading not recognised: “{sec.raw_heading}”",
                        per_unknown,
                        fix="Use a conventional heading so the section maps to a "
                            "standard resume section.")
            )
    lost += unknown_lost

    if cfg.quirk("heading_ampersand_strict"):
        pts = cfg.quirk_points("heading_ampersand_strict", 3)
        for sec in st.sections:
            pref = ampersand_issue(sec.raw_heading)
            if pref:
                lost += pts
                sub.findings.append(
                    Finding("error", f"Heading “{sec.raw_heading}” is not on the allowlist.",
                            pts, quirk="heading_ampersand_strict",
                            fix=f"Rename it to “{pref}” - the ampersand spelling is the accepted one.")
                )

    for sec in st.sections:
        if sec.canonical in DISCOURAGED_SECTIONS:
            sub.findings.append(
                Finding("warn", f"“{sec.raw_heading}” rarely earns its space on a student resume.",
                        0.0, fix="Cut it and use the room for quantified experience bullets.")
            )

    if len(st.sections) > 8:
        lost += mx * 0.15
        sub.findings.append(
            Finding("warn", f"{len(st.sections)} sections is a lot for one page.", mx * 0.15,
                    fix="Merge related sections; VMock penalises section sprawl.")
        )

    sub.points = clamp(mx - lost, 0, mx)
    if not sub.findings:
        sub.findings.append(Finding("good", "All essential sections present and correctly titled."))
    sub.detail = {"present": sorted(x for x in present if x), "count": len(st.sections)}
    return sub


# ---------------------------------------------------------------------------
# SECTION SPECIFIC — observed as three groups of named checks
# ---------------------------------------------------------------------------
# OBSERVED (CMU Masters - Technical, 2026-08-26): three group chips —
#   Personal Details (FAILING) · Education (pass) · Experience (pass)
# Personal Details contains four checks:
#   Phone Number (FAIL) · Font Size Check · Name Check · Email Address
# The Education and Experience group checks were NOT opened, so they are not
# implemented here.

# OBSERVED rule, verbatim: "Phone number should be included and it must be in
# (XXX) XXX-XXXX or XXX-XXX-XXXX or XXX.XXX.XXXX format".
# The failure it flagged was "+1 (555) 010-0199" — so parentheses are ACCEPTED
# and the country-code prefix is what breaks it. This is the direct refutation
# of the "15-point parenthesis penalty" reported by career-centre guides.
# OBSERVED rule, verbatim: 'GPA, if included, must contain either "/" or
# "out of" to ensure that you are writing the associated scale'.
GPA_VALUE_RE = re.compile(r"\bGPA\b[^\n]{0,28}", re.I)
DEGREE_RE = re.compile(
    r"\b(B\.?A|B\.?S|B\.?Sc|H\.?B\.?Sc|M\.?A|M\.?S|M\.?Sc|M\.?Eng|MBA|Ph\.?D|"
    r"Bachelor|Master|Doctor|Associate)\b", re.I)
DEGREE_ABBREV_RE = re.compile(
    r"\b(B\.?A|B\.?S|B\.?Sc|H\.?B\.?Sc|M\.?A|M\.?S|M\.?Sc|M\.?Eng|Ph\.?D)\.?\b")
GPA_SCALE_RE = re.compile(r"/|out\s+of", re.I)

PHONE_OK_RE = re.compile(
    r"^(?:\(\d{3}\)\s?\d{3}-\d{4}|\d{3}-\d{3}-\d{4}|\d{3}\.\d{3}\.\d{4})$"
)
PHONE_ANY_RE = re.compile(r"(\+?\d{1,3}[\s.\-]*)?(\(\s*\d{3}\s*\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}")


def _section_specific(doc: Document, st: Structure, cfg: Config) -> SubScore:
    mx = float(cfg.get("presentation.section_specific", 3))
    sub = SubScore("section_specific", "Section Specific", mx, mx)
    per_fail = float(cfg.get("presentation.points_per_failed_detail_check", 1.5))
    blob = st.contact_text or doc.text[:400]

    checks = []

    m = PHONE_ANY_RE.search(blob)
    raw = m.group(0).strip() if m else ""
    phone_ok = bool(raw) and bool(PHONE_OK_RE.match(raw))
    checks.append(Check(
        "phone_number", "Phone Number", phone_ok,
        "Phone number should be included and it must be in (XXX) XXX-XXXX or "
        "XXX-XXX-XXXX or XXX.XXX.XXXX format",
        raw or "no phone number found"))

    # This one sits inside the PERSONAL DETAILS group, so it is about the name
    # and contact block -- not the document body, which Overall Format's own
    # Font Size Check already covers. Measuring the body here double-counted:
    # the 69 resume failed Overall Format's Font Size Check on its Technical
    # Skills block and VMock still PASSED its Personal Details group.
    #
    # Its rule text has never been read, and every resume observed passed it,
    # including ones whose name is set several points larger than the contact
    # line. So it is measured and reported, never failed -- the same treatment
    # the other unread checks get.
    contact_sizes = sorted({round(l.size, 1) for l in st.contact_lines if l.size})
    checks.append(Check("font_size_check", "Font Size Check", True,
                        "", f"contact block font sizes: {contact_sizes}",
                        observed_rule=False))

    checks.append(Check("name_check", "Name Check", bool(st.name), "",
                        st.name or "could not identify a name", observed_rule=False))

    em = EMAIL_RE.search(blob)
    checks.append(Check("email_address", "Email Address", bool(em), "",
                        em.group(0) if em else "no email address found",
                        observed_rule=False))

    # --- Education group (OBSERVED on the 93 resume) ------------------------
    edu_checks = []
    edu = st.get("education")
    edu_text = edu.text if edu else ""
    gpa = GPA_VALUE_RE.search(edu_text)
    if gpa:
        scale_ok = bool(GPA_SCALE_RE.search(gpa.group(0)))
        edu_checks.append(Check(
            "gpa_check", "GPA Check", scale_ok,
            'GPA, if included, must contain either "/" or "out of" to ensure '
            "that you are writing the associated scale",
            gpa.group(0).strip()))
    # OBSERVED rule text, benchmark-specific:
    #   CMU Resumes             -> "No italics, not abbreviated"
    #   CMU Masters - Technical -> "Consistent Styling, not abbreviated"
    profile = cfg.get("benchmark_profiles.default", "cmu_masters_technical")
    degree_rule = (cfg.get(f"benchmark_profiles.{profile}.degree_styling_rule")
                   or cfg.get("presentation.degree_styling_rule",
                              "No italics, not abbreviated"))
    forbid_italics = "italic" in degree_rule.lower()
    require_consistent = "consistent" in degree_rule.lower()
    deg_bad = []
    deg_styles = set()
    if edu is not None:
        for entry in edu.entries:
            for line in entry.header_lines:
                text = line.body_text
                if not DEGREE_RE.search(text):
                    continue
                if line.words:
                    w0 = line.words[0]
                    deg_styles.add((round(line.size, 1), w0.bold, w0.italic))
                if forbid_italics and any(w.italic for w in line.words):
                    deg_bad.append(text[:60])
                elif DEGREE_ABBREV_RE.search(text):
                    deg_bad.append(text[:60])
    # "Consistent Styling" is the CMU Masters - Technical wording. It asks the
    # degree lines to match each other; it says nothing about italics, and
    # Masters_1 -- whose degree lines ARE italicised -- passed it.
    if require_consistent and len(deg_styles) > 1:
        deg_bad.append(f"{len(deg_styles)} different degree stylings")
    edu_checks.append(Check("degree_styling", "Degree Styling", not deg_bad,
                            degree_rule, "; ".join(deg_bad[:2])))
    edu_checks.append(Check("university_name", "University Name", True, "", "",
                            observed_rule=False))
    edu_checks.append(Check("university_styling", "University Styling", True, "", "",
                            observed_rule=False))
    # --- Experience group (OBSERVED) ---------------------------------------
    exp_checks = []
    exp = st.get("experience")
    titles = []
    if exp is not None:
        for entry in exp.entries:
            for line in entry.header_lines[:1]:
                titles.append(line)
    # Style the TITLE TEXT, not the whole line. An entry header usually fuses a
    # left-aligned title with a right-aligned date, so a whole-line bold ratio
    # swings on how many words the date happens to have -- two identically
    # styled entries would read as two different stylings. The first word of
    # the line is the styling the reader actually sees.
    styles = set()
    for l in titles:
        if not l.words:
            continue
        w0 = l.words[0]
        styles.add((round(l.size, 1), w0.bold, w0.italic))
    exp_checks.append(Check(
        "job_title_styling", "Job Title Styling", len(styles) <= 1,
        "Consistent Styling",
        f"{len(styles)} different title stylings across {len(titles)} entries"))

    checks = checks + edu_checks + exp_checks

    failed = [c for c in checks if c.passed is False]
    sub.points = clamp(mx - per_fail * len(failed), 0, mx)
    for c in failed:
        sub.findings.append(
            Finding("error", c.label, per_fail, evidence=c.evidence,
                    fix=c.message or "Rule text not yet read from VMock."))
    passed = [c for c in checks if c.passed is not False]
    if passed:
        sub.findings.append(
            Finding("good", f"{len(passed)} Checks meet guidelines", 0.0,
                    evidence=", ".join(c.label for c in passed)))
    sub.detail = {
        "groups": ["Personal Details", "Education", "Experience"],
        "personal_details": [
            {"key": c.key, "label": c.label, "passed": c.passed,
             "rule_observed": c.observed_rule, "evidence": c.evidence} for c in checks
        ],
        "note": "Education and Experience group checks not yet observed",
    }
    return sub


def _spell_check(doc: Document, st: Structure, cfg: Config) -> SubScore:
    """OBSERVED: two classes of unknown word, only one of which costs points.

    Red ("misspelled") deducts and drives "Needs Work!"; yellow ("re-examine")
    is explicitly free: "Words highlighted in yellow will not result in any
    deduction of marks." The discriminator is capitalisation -- see
    spell.classify().
    """
    mx = float(cfg.get("presentation.spell_check", 2))
    sub = SubScore("spell_check", "Spell Check", mx, mx)
    cw = bool(cfg.get("presentation.spell.commonwealth_ok", True))
    per_red = float(cfg.get("presentation.points_per_misspelling", 1.0))

    # OBSERVED: VMock never surfaces the candidate's own name. Yuxuan Cai's
    # resume produced twelve words to re-examine and "Yuxuan" -- the first
    # unknown token on the page -- was not one of them.
    own = {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'\-]+", st.name or "")}
    hits = spell.check_with_context(doc.lines, aggressive=True,
                                    commonwealth_ok=cw, extra_ok=own)
    red, yellow = [], []
    for word, _ in hits:
        (red if spell.classify(word) == "red" else yellow).append(word)

    sub.points = clamp(mx - per_red * len(red), 0, mx)
    if red:
        sub.status = "Needs Work!"
        sub.findings.append(
            Finding("error",
                    "We found some spelling errors in your resume. Please "
                    "reconsider the highlighted words.",
                    min(mx, per_red * len(red)),
                    evidence="  ".join(red[:12]),
                    fix="The words highlighted in Red are misspelled.")
        )
    elif yellow:
        sub.status = "On Track!"
    else:
        sub.status = "Good Job!"
        sub.findings.append(Finding("good", "We did not find any spelling errors in the resume."))
    if yellow:
        sub.findings.append(
            Finding("info", "Re-examine the spellings.", 0.0,
                    evidence="  ".join(yellow[:14]),
                    fix="Words highlighted in yellow will not result in any "
                        "deduction of marks.")
        )
    sub.detail = {"misspelled": red[:30], "re_examine": yellow[:30],
                  "deducts_for": len(red)}
    return sub


# ---------------------------------------------------------------------------
def score(doc: Document, st: Structure, cfg: Config) -> ModuleScore:
    mx = float(cfg.get("modules.presentation", 30))
    subs = [_overall_format(doc, st, cfg)] + [
        _number_of_pages(doc, st, cfg),
        _essential_sections(doc, st, cfg),
        _section_specific(doc, st, cfg),
        _spell_check(doc, st, cfg),
    ]
    graded = set(cfg.get("presentation.graded_subs",
                         ["essential_sections", "spell_check"]) or [])
    if cfg.get("presentation.all_or_nothing", True):
        # A sub-parameter is full marks or nothing: see the note in rules.yaml.
        for sub in subs:
            failed = any(f.severity == "error" and f.points_lost > 0
                         for f in sub.all_findings)
            if sub.key not in graded:
                sub.points = 0.0 if failed else sub.max_points
            if failed:
                sub.status = "Needs Work!"
            elif sub.status != "On Track!":
                # OBSERVED: Spell Check reads "On Track!" at FULL marks when the
                # resume contains words to re-examine -- "Words highlighted in
                # yellow will not result in any deduction of marks." A chip is
                # not a score, so a sub-parameter that set one for itself keeps
                # it.
                sub.status = "Good Job!"

    # OBSERVED: at "Good Job!" VMock's panel shows the praise line and nothing
    # else. Its Action Oriented panel on Masters_1 -- a resume with a bullet
    # that opens on a noun and another that opens on "Provided" -- said only
    # "You have done a good job of using action-oriented language in your
    # resume". Findings that cost nothing stay: the yellow spell list is shown
    # under "On Track!" and is explicitly free.
    for sub in subs:
        if sub.status == "Good Job!":
            sub.findings = [f for f in sub.findings
                            if f.severity in ("good", "info")]

    declared = sum(s.max_points for s in subs)
    total = sum(s.points for s in subs)
    if declared and abs(declared - mx) > 0.01:
        total *= mx / declared
    mod = ModuleScore("presentation", "Presentation", total, mx, subs)

    # ---- quirk: the 15-point phone-parenthesis deduction -------------------
    if cfg.quirk("phone_parens_penalty"):
        blob = st.contact_text or doc.text[:400]
        if PHONE_PARENS_RE.search(blob):
            pts = cfg.quirk_points("phone_parens_penalty", 15)
            mod.points = clamp(mod.points - pts, 0, mx)
            mod.findings.append(
                Finding("error",
                        f"Phone number written with parentheses around the area code (-{pts:g} points).",
                        pts, evidence=PHONE_PARENS_RE.search(blob).group(0),
                        quirk="phone_parens_penalty",
                        fix="Write it as 415-555-0182. This single rule is the largest formatting "
                            "deduction VMock applies, and it is documented by Boston University.")
            )

    if doc.parse_warnings:
        for w in doc.parse_warnings:
            mod.findings.append(Finding("error", w, 0.0))

    mod.points = clamp(mod.points, 0, mx)
    return mod
