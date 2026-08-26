"""
PDF -> structured document with geometry.

The Presentation module needs real coordinates (margins, right-alignment of
dates, indent consistency, font sizes, blank-line spacing), so we keep every
word's bounding box and font rather than flattening to plain text.

This mirrors what VMock's patent describes: margins are "matched against best
case margins pulled from database" and formatting "is analyzed to ensure
alignment of all resume elements". It is text-layout analysis, not vision.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

import pdfplumber

from .lexicons import AMBIGUOUS_GLYPHS, BULLET_GLYPHS

PT_PER_IN = 72.0
LINE_TOLERANCE_PT = 2.6
DASHES = "-\u2013\u2014"
DATE_DASH_RE = re.compile(r"^[-\u2013\u2014]\s*\d")

# Font-name patterns that mean "bold". The LaTeX families matter: Computer
# Modern ships bold as CMBX/SFBX and Nimbus as "-Medi", none of which contain
# the string "bold", so a naive check reports every LaTeX heading as regular.
ITALIC_FONT_RE = re.compile(r"(italic|oblique|cmti|cmmi|-it\b|,i$|ti\d)", re.I)
BOLD_FONT_RE = re.compile(
    r"(bold|black|heavy|semib|demi|medi|cmbx|sfbx|cmssbx|-bd|,b$|-b$)", re.I
)


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    font: str

    @property
    def bold(self) -> bool:
        return bool(BOLD_FONT_RE.search(self.font))

    @property
    def italic(self) -> bool:
        return bool(ITALIC_FONT_RE.search(self.font))


@dataclass
class Line:
    page: int
    words: List[Word]
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    space_above: float = 0.0
    is_bullet: bool = False
    bullet_glyph: str = ""
    indent: float = 0.0

    @property
    def size(self) -> float:
        """Modal font size on the line."""
        if not self.words:
            return 0.0
        sizes = [round(w.size, 1) for w in self.words]
        return max(set(sizes), key=sizes.count)

    @property
    def max_size(self) -> float:
        return max((w.size for w in self.words), default=0.0)

    @property
    def bold_ratio(self) -> float:
        if not self.words:
            return 0.0
        return sum(1 for w in self.words if w.bold) / len(self.words)

    @property
    def all_caps(self) -> bool:
        letters = [c for c in self.text if c.isalpha()]
        return bool(letters) and all(c.isupper() for c in letters)

    @property
    def body_text(self) -> str:
        """Line text with any leading bullet glyph stripped."""
        t = self.text
        while t and (t[0] in BULLET_GLYPHS or t[0].isspace()):
            t = t[1:]
        return t.strip()

    @property
    def word_count(self) -> int:
        return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'/&.+-]*", self.body_text))


@dataclass
class PageGeom:
    number: int
    width: float
    height: float
    left_margin: float
    right_margin: float
    top_margin: float
    bottom_margin: float
    content_bottom: float
    n_images: int = 0
    n_rects: int = 0
    n_curves: int = 0
    two_column: bool = False
    gutter: Optional[tuple] = None

    @property
    def fill_ratio(self) -> float:
        usable = self.height - self.top_margin
        if usable <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.content_bottom - self.top_margin) / usable))


@dataclass
class Document:
    path: str
    pages: List[PageGeom] = field(default_factory=list)
    lines: List[Line] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)

    @property
    def n_pages(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    @property
    def word_count(self) -> int:
        return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'/&.+-]*", self.text))

    @property
    def has_graphics(self) -> bool:
        return any(p.n_images > 0 for p in self.pages)

    @property
    def two_column(self) -> bool:
        return any(p.two_column for p in self.pages)

    @property
    def effective_pages(self) -> float:
        """Page count where a barely-used final page counts fractionally."""
        if not self.pages:
            return 0.0
        last = self.pages[-1]
        return (len(self.pages) - 1) + max(0.05, last.fill_ratio)


# Some PDFs (LaTeX, reportlab, older Word exports) emit glyphs with no
# ToUnicode map; pdfplumber surfaces those as "(cid:NNN)". Bullets are the
# usual casualty, so decode the ones that matter rather than dropping them.
CID_RE = re.compile(r"\(cid:(\d+)\)")
CID_MAP = {
    127: "\u2022", 149: "\u2022", 8226: "\u2022", 8259: "\u2043",
    183: "\u00b7", 9679: "\u25cf", 9642: "\u25aa", 9702: "\u25e6",
    8211: "\u2013", 8212: "\u2014", 8217: "\u2019", 8216: "\u2018",
    8220: '\u201c', 8221: '\u201d',
}


def _decode_cid(match) -> str:
    n = int(match.group(1))
    if n in CID_MAP:
        return CID_MAP[n]
    if 32 <= n < 127:
        return chr(n)
    return ""


def _norm(s: str) -> str:
    if "(cid:" in s:
        s = CID_RE.sub(_decode_cid, s)
    s = unicodedata.normalize("NFKC", s)
    return s.replace("\u00a0", " ").replace("\ufb01", "fi").replace("\ufb02", "fl")


def _merge_smallcaps(words: List[Word]) -> List[Word]:
    """Rejoin LaTeX small-caps runs: "E" + "DUCATION" -> "EDUCATION".

    \\textsc{Education} sets the capital at full size and the rest at about
    80%, as two separate glyph runs with no gap. Left split, the heading never
    matches a section name and both fragments land in the spell checker.
    """
    if len(words) < 2:
        return words
    out: List[Word] = []
    for w in words:
        prev = out[-1] if out else None
        if (
            prev is not None
            and len(prev.text) <= 2
            and prev.text.isupper()
            and w.text.isupper()
            and len(w.text) >= 2
            and prev.size > w.size + 0.4
            and abs(w.x0 - prev.x1) <= 1.2
            and abs(w.bottom - prev.bottom) <= 1.5
        ):
            merged = Word(
                text=prev.text + w.text, x0=prev.x0, x1=w.x1,
                top=min(prev.top, w.top), bottom=max(prev.bottom, w.bottom),
                size=prev.size, font=prev.font,
            )
            out[-1] = merged
        else:
            out.append(w)
    return out


def _group_words_into_lines(words: List[Word], page_no: int) -> List[Line]:
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(w.top, 1), w.x0))
    lines: List[List[Word]] = []
    current: List[Word] = [words[0]]
    for w in words[1:]:
        ref = current[0]
        # Box overlap is the wrong test. A 25pt name and the 10pt contact line
        # beneath it overlap vertically, and so do two 10pt lines set with
        # tight LaTeX leading -- merging either interleaves two rows of text
        # and scrambles the document. Compare baselines relative to glyph size.
        size = min(w.size, ref.size) or max(w.size, ref.size) or 10.0
        same_row = abs(w.top - ref.top) <= max(LINE_TOLERANCE_PT, 0.30 * size)
        if not same_row:
            h_w, h_ref = w.bottom - w.top, ref.bottom - ref.top
            small = min(h_w, h_ref)
            same_row = small > 0 and abs(
                (w.top + w.bottom) / 2.0 - (ref.top + ref.bottom) / 2.0
            ) <= 0.35 * small
        if same_row:
            current.append(w)
        else:
            lines.append(current)
            current = [w]
    lines.append(current)

    out: List[Line] = []
    for group in lines:
        group.sort(key=lambda w: w.x0)
        group = _merge_smallcaps(group)
        text = _norm(" ".join(w.text for w in group)).strip()
        if not text:
            continue
        ln = Line(
            page=page_no,
            words=group,
            text=text,
            x0=min(w.x0 for w in group),
            x1=max(w.x1 for w in group),
            top=min(w.top for w in group),
            bottom=max(w.bottom for w in group),
        )
        first = text[0]
        if first in BULLET_GLYPHS:
            if first in AMBIGUOUS_GLYPHS:
                # "o", "*", ">" and the dashes are ordinary characters far more
                # often than they are bullets, so they only count with
                # whitespace after them -- otherwise "of the team" loses its
                # first letter and is scored as a bullet with no action verb.
                is_bullet = len(text) > 1 and text[1] in " \t"
                if is_bullet and first in DASHES and DATE_DASH_RE.match(text):
                    is_bullet = False          # a date range, not a bullet
            else:
                is_bullet = len(text) == 1 or text[1] in " \t" or text[1].isalnum()
            if is_bullet:
                ln.is_bullet = True
                ln.bullet_glyph = first
        out.append(ln)
    out.sort(key=lambda l: l.top)
    return out


def _y_bands(words: List[Word], tol: float = 3.0) -> List[List[Word]]:
    if not words:
        return []
    ws = sorted(words, key=lambda w: w.top)
    bands: List[List[Word]] = [[ws[0]]]
    for w in ws[1:]:
        if abs(w.top - bands[-1][0].top) <= tol:
            bands[-1].append(w)
        else:
            bands.append([w])
    return bands


def _detect_gutter(words: List[Word], width: float, height: float):
    """Find a vertical band that no word crosses, with real content on both sides.

    Runs on words rather than assembled lines: in a two-column layout the two
    columns share y-coordinates, so line assembly would already have fused them
    and destroyed the signal.

    The decisive test is not the width of the empty band -- a right-aligned date
    column produces one of those too -- but how many horizontal rows carry text
    on *both* sides of it.
    """
    body = [w for w in words if w.text.strip()]
    if len(body) < 20:
        return None
    bands = _y_bands(body)
    if len(bands) < 6:
        return None
    lo, hi = width * 0.20, width * 0.80
    best = None
    best_shared = 0
    # Sweep the word intervals rather than stepping a fixed grid across the
    # page. The grid cost (0.6 * width / step) * len(words) is driven by the
    # MediaBox, which the uploader controls: a page declaring width=200000
    # turned this into tens of millions of comparisons and pinned a core.
    # Walking the sorted intervals is O(n log n) whatever the page width, and
    # it finds exact gap edges instead of 2pt-quantised ones.
    spans = sorted((w.x0, w.x1) for w in body if w.x1 > lo and w.x0 < hi)
    gaps = []
    cursor = lo
    for x0, x1 in spans:
        if x0 > cursor:
            gaps.append((cursor, min(x0, hi)))
        cursor = max(cursor, x1)
        if cursor >= hi:
            break
    if cursor < hi:
        gaps.append((cursor, hi))

    for start, end in gaps:
        span = end - start
        if span < 0.28 * PT_PER_IN:
            continue
        mid = (start + end) / 2.0
        shared = sum(
            1
            for band in bands
            if any(w.x1 <= mid for w in band) and any(w.x0 >= mid for w in band)
        )
        left_only = sum(1 for band in bands if all(w.x1 <= mid for w in band))
        right_only = sum(1 for band in bands if all(w.x0 >= mid for w in band))
        # A real second column owns rows of its own. A date column never does.
        if shared < 4 or shared < len(bands) * 0.20:
            continue
        if left_only == 0 and right_only == 0:
            continue
        if shared > best_shared or (shared == best_shared and best and span > best[1] - best[0]):
            best, best_shared = (start, end), shared
    return best


DATE_TAIL_RE = re.compile(
    r"(19|20)\d{2}\s*$|present\s*$|current\s*$", re.I
)


def _merge_wrapped_bullets(lines: List[Line], page_left: float) -> List[Line]:
    """Fold a bullet's wrapped continuation lines back into the bullet.

    A bullet that runs onto a second printed line produces a second Line with no
    glyph. Left alone it is read as a new entry header, which invents undated
    entries, breaks bullet word counts and skews every downstream count. The
    continuation is recognised by indentation: it starts at or to the right of
    the bullet it follows, sits directly beneath it, and carries no heading
    styling or trailing date of its own.
    """
    if not lines:
        return lines
    out: List[Line] = []
    for line in lines:
        prev = out[-1] if out else None
        if (
            prev is not None
            and prev.is_bullet
            and not line.is_bullet
            and line.x0 >= prev.x0 - 1.0
            and line.x0 > page_left + 3.0
            and line.bold_ratio < 0.5
            and abs(line.size - prev.size) < 0.6
            and (line.top - prev.bottom) <= max(6.0, prev.size * 0.9)
            and not DATE_TAIL_RE.search(line.text)
        ):
            prev.words.extend(line.words)
            # LaTeX hyphenates across line breaks; joining with a space would
            # leave "pendu- lum" and hand the spell checker two non-words.
            if prev.text.endswith("-") and line.text[:1].islower():
                prev.text = (prev.text[:-1] + line.text).strip()
            else:
                prev.text = (prev.text + " " + line.text).strip()
            prev.x1 = max(prev.x1, line.x1)
            prev.bottom = max(prev.bottom, line.bottom)
            continue
        out.append(line)
    return out


class UnreadablePDF(Exception):
    """The file is not a PDF we can open at all."""


GLUE_TOKEN_RE = re.compile(r"[A-Za-z]{22,}")
WORD_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")


def _glue_ratio(words) -> float:
    """Fraction of alphabetic tokens that are implausibly long.

    LaTeX and some Word exports write no space characters at all -- words are
    separated only by a kerning gap of about 0.25 em. pdfplumber's default
    3pt tolerance is wider than that gap at 10pt, so every word on the line
    fuses into one token ("CarnegieMellonUniversity"). Nothing downstream can
    recover from that, so detect it and re-extract.
    """
    tokens = [t for w in words for t in WORD_TOKEN_RE.findall(w.get("text", ""))]
    if len(tokens) < 12:
        return 0.0
    return sum(1 for t in tokens if len(t) >= 22) / len(tokens)


def _fix_zero_width_chars(page) -> int:
    """Give ligature glyphs that report no advance width a sortable position.

    Some LaTeX/Times PDFs emit "fi", "fl" and friends as a single char whose x0
    equals its x1, drawn at the x of the glyph AFTER it. pdfplumber sorts chars
    left to right, so a zero-width "fi" sitting a fraction to the right of the
    "v" that follows it turns "five" into "vfi e" -- wrong text for every
    downstream check, and a spurious "misspelling" on top.

    Document order is correct in these files, so a zero-width char is pinned
    immediately to the left of its successor.
    """
    try:
        chars = page.chars
    except Exception:
        return 0
    fixed = 0
    for i, c in enumerate(chars):
        try:
            if c["x1"] - c["x0"] > 0.01 or not str(c.get("text", "")):
                continue
        except (KeyError, TypeError):
            continue
        nxt = chars[i + 1] if i + 1 < len(chars) else None
        if not nxt or abs(nxt.get("top", 0) - c.get("top", 0)) > 1.0:
            continue
        c["x1"] = nxt["x0"]
        c["x0"] = nxt["x0"] - 0.01
        fixed += 1
    return fixed


def _extract_words_adaptive(page, doc: "Document"):
    """Extract words, tightening the split tolerance if the page comes back glued.

    x_tolerance_ratio scales the tolerance with font size (0.18 em), which is
    below a normal inter-word gap and above inter-letter kerning. The absolute
    fallbacks handle chars that report no size.
    """
    _fix_zero_width_chars(page)
    attempts = [
        {"x_tolerance_ratio": 0.18, "x_tolerance": 1.5},
        {"x_tolerance_ratio": 0.12, "x_tolerance": 1.0},
        {"x_tolerance": 0.8},
    ]
    best, best_ratio = None, 1.0
    for idx, kwargs in enumerate(attempts):
        try:
            words = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=False,
                extra_attrs=["size", "fontname"],
                **kwargs,
            )
        except TypeError:
            words = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=False,
                extra_attrs=["size", "fontname"],
                x_tolerance=kwargs.get("x_tolerance", 1.5),
            )
        ratio = _glue_ratio(words)
        if best is None or ratio < best_ratio:
            best, best_ratio = words, ratio
        if ratio <= 0.02:
            if idx:
                doc.parse_warnings.append(
                    f"page {page.page_number}: text had no space characters; "
                    "re-extracted with a tighter word-split tolerance."
                )
            return words
    doc.parse_warnings.append(
        f"page {page.page_number}: could not cleanly separate words "
        f"({best_ratio:.0%} of tokens look fused). Scores will be unreliable."
    )
    return best or []


# Limits on what counts as a resume at all. Both are enforced before any
# per-page work, because both are attacker-controlled and cheap to declare:
# a 48KB file can claim 300 pages, and a 2KB file can claim a 100-inch page
# that rasterises to gigabytes.
MAX_PAGES = 30
MAX_PAGE_PT = 3400          # ~47in; the PDF spec allows 200in


def parse_pdf(src) -> Document:
    """Parse a PDF from a path or any binary file-like object.

    Accepting a stream is what lets the web app score an upload without ever
    writing it to disk.
    """
    name = src if isinstance(src, (str, bytes, os.PathLike)) else ""
    doc = Document(path=str(name))
    if hasattr(src, "seek"):
        src.seek(0)
    try:
        pdf_ctx = pdfplumber.open(src)
    except Exception as exc:                # noqa: BLE001 - any pdfminer failure
        raise UnreadablePDF(
            "This file could not be opened as a PDF. Re-export it from Word or "
            f"your editor and try again.  ({type(exc).__name__})"
        ) from exc
    with pdf_ctx as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise UnreadablePDF(
                f"This document has {len(pdf.pages)} pages. A resume is one or two; "
                f"this tool reads at most {MAX_PAGES}."
            )
        for i, page in enumerate(pdf.pages, start=1):
            if float(page.width) > MAX_PAGE_PT or float(page.height) > MAX_PAGE_PT:
                raise UnreadablePDF(
                    f"Page {i} measures {float(page.width) / 72:.0f}x"
                    f"{float(page.height) / 72:.0f} inches, which is not a page "
                    "size this tool can read."
                )
            try:
                raw = _extract_words_adaptive(page, doc)
            except Exception as exc:  # pragma: no cover - malformed pdf
                doc.parse_warnings.append(f"page {i}: extract_words failed ({exc})")
                raw = []
            words = [
                Word(
                    text=_norm(w["text"]),
                    x0=float(w["x0"]),
                    x1=float(w["x1"]),
                    top=float(w["top"]),
                    bottom=float(w["bottom"]),
                    size=float(w.get("size") or 0.0),
                    font=str(w.get("fontname") or ""),
                )
                for w in raw
            ]
            gutter = _detect_gutter(words, float(page.width), float(page.height))
            if gutter:
                split = (gutter[0] + gutter[1]) / 2.0
                page_lines = _group_words_into_lines(
                    [w for w in words if w.x1 <= split], i
                ) + _group_words_into_lines([w for w in words if w.x0 >= split], i)
            else:
                page_lines = _group_words_into_lines(words, i)

            w_, h_ = float(page.width), float(page.height)
            if page_lines:
                left = min(l.x0 for l in page_lines)
                right = w_ - max(l.x1 for l in page_lines)
                top = min(l.top for l in page_lines)
                content_bottom = max(l.bottom for l in page_lines)
                bottom = h_ - content_bottom
            else:
                left = right = top = bottom = 0.0
                content_bottom = 0.0

            geom = PageGeom(
                number=i,
                width=w_,
                height=h_,
                left_margin=left,
                right_margin=right,
                top_margin=top,
                bottom_margin=bottom,
                content_bottom=content_bottom,
                n_images=len(page.images or []),
                n_rects=len(page.rects or []),
                n_curves=len(page.curves or []),
                two_column=gutter is not None,
                gutter=gutter,
            )
            doc.pages.append(geom)

            page_lines = _merge_wrapped_bullets(page_lines, left)

            for link in (page.hyperlinks or []):
                uri = link.get("uri")
                if uri:
                    doc.links.append(uri)

            doc.lines.extend(page_lines)

    # vertical gap above each line, and indent relative to the page's left margin
    by_page = {}
    for l in doc.lines:
        by_page.setdefault(l.page, []).append(l)
    for pno, group in by_page.items():
        geom = doc.pages[pno - 1]
        if not geom.two_column:
            group.sort(key=lambda l: l.top)
        prev_bottom = None
        for l in group:
            l.indent = round(l.x0 - geom.left_margin, 1)
            l.space_above = 0.0 if prev_bottom is None else round(l.top - prev_bottom, 1)
            prev_bottom = l.bottom

    if doc.n_pages and not doc.lines:
        doc.parse_warnings.append(
            "No extractable text. Scanned image or non-embedded fonts - "
            "VMock cannot score this either."
        )
    return doc
