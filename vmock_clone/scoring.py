"""Orchestrator: parse -> structure -> three modules -> one score."""

from __future__ import annotations

import math
import copy
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .core import BulletFeedback, Config, ModuleScore, reconcile_module
from .modules import competencies as m_comp
from .modules import impact as m_impact
from .modules import presentation as m_pres
from .parser import Document, parse_pdf
from .sections import Structure, build_structure

ZONE_COLORS = {"red": "#d94a4a", "yellow": "#d9a441", "green": "#3fa86b"}


def zone_for(score: float, cfg: Config) -> str:
    """Map a score to its colour band.

    The published bands are integers (red 0-32, yellow 33-85, green 86-100) and
    leave gaps once scores are fractional: 32.3 belongs to neither. Treat each
    band's upper bound as inclusive and everything below the next band's floor
    as belonging to the lower band, so the range is fully tiled.
    """
    zones = cfg.get("meta.zones", {}) or {}
    ordered = [(name, zones.get(name)) for name in ("red", "yellow", "green")]
    for name, rng in ordered:
        if not rng:
            continue
        if score < rng[1] + 1:
            return name
    return "green"


def _normal_cdf(x: float, mean: float, sd: float) -> float:
    if sd <= 0:
        return 0.5
    return 0.5 * (1.0 + math.erf((x - mean) / (sd * math.sqrt(2.0))))


@dataclass
class Report:
    file: str
    filename: str
    generated_at: str
    scored: bool
    overall: float
    zone: str
    modules: List[ModuleScore] = field(default_factory=list)
    bullets: List[BulletFeedback] = field(default_factory=list)
    benchmark: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    preview: Optional[Dict[str, Any]] = None

    @property
    def module_map(self) -> Dict[str, ModuleScore]:
        return {m.key: m for m in self.modules}

    def top_actions(self, n: int = 8) -> List[Dict[str, Any]]:
        rows = []
        for mod in self.modules:
            for f in mod.all_findings:
                if f.points_lost <= 0.01 or f.severity == "good":
                    continue
                rows.append(
                    {
                        "module": mod.label,
                        "module_key": mod.key,
                        "severity": f.severity,
                        "message": f.message,
                        "fix": f.fix,
                        "evidence": f.evidence,
                        "points": round(f.points_lost, 2),
                        "line_index": f.line_index,
                    }
                )
        rows.sort(key=lambda r: -r["points"])
        return rows[:n]


    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "filename": self.filename,
            "generated_at": self.generated_at,
            "scored": self.scored,
            "overall": round(self.overall, 1),
            "zone": self.zone,
            "zone_color": ZONE_COLORS.get(self.zone, "#888"),
            "blockers": self.blockers,
            "modules": [m.to_dict() for m in self.modules],
            "bullets": [b.to_dict() for b in self.bullets],
            "benchmark": self.benchmark,
            "preview": self.preview,
            "top_actions": self.top_actions(10),
            "meta": self.meta,
        }


# A cohort file is built from a folder of real resumes, so it carries the
# operator's own paths and the filenames of people whose PDFs failed to parse.
# Only these keys are score data; everything else stays on the server.
BENCHMARK_PUBLIC_KEYS = (
    "label", "n", "mean", "stdev", "median", "min", "max", "module_means",
)


def _public_benchmark(name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, **{k: raw[k] for k in BENCHMARK_PUBLIC_KEYS if k in raw}}


def load_benchmark(cfg: Config, name: Optional[str] = None) -> Dict[str, Any]:
    name = name or cfg.get("benchmark.default", "general")
    inline = cfg.get(f"benchmark.{name}")
    if isinstance(inline, dict):
        return _public_benchmark(name, inline)
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")
    path = os.path.join(root, f"{name}.json")
    if os.path.exists(path):
        import json

        with open(path, encoding="utf-8") as f:
            return _public_benchmark(name, json.load(f))
    return {"name": "general", "label": "General cohort", "mean": 62.0, "stdev": 14.0, "n": 0}


# 200 dpi renders a letter page at 1700px wide. The preview pane is at most
# 860 CSS px, so on a 2x display that is 1720 device pixels -- i.e. 200 dpi is
# the point where the page stops looking soft on a retina screen and below
# which it always will. It costs about 170KB of base64 per page over 110 dpi;
# palette quantisation was measured and saves under 2%, so this is simply the
# price of a sharp preview.
PREVIEW_DPI = int(os.environ.get("VMOCK_PREVIEW_DPI", "200"))
# Rasterisation is the one step whose cost the uploader controls, so it gets
# two ceilings: how many pages are drawn at all, and how many pixels any one
# page may occupy. Without the pixel bound a legal 100-inch page renders to
# 11000x11000 and takes gigabytes.
MAX_PREVIEW_PAGES = int(os.environ.get("VMOCK_MAX_PREVIEW_PAGES", "3"))
# Room for a legal-size page at 200 dpi (1700x2800 = 4.8M) with headroom.
# Anything larger is drawn at reduced dpi rather than refused.
MAX_RASTER_PX = 12_000_000


def build_preview(src, doc: Document, dpi: int = PREVIEW_DPI) -> Optional[Dict[str, Any]]:
    """Page rasters plus line geometry, so the UI can show the real resume.

    VMock puts your actual page on the left and pins its feedback to the line
    that earned it. Everything here is derived from the same parse the score
    comes from, so a pin can never drift from what was measured.

    `src` is a path or a binary stream: the web app passes the upload straight
    through so it never reaches disk.
    """
    try:
        import base64
        import io as _io
        import math

        import pdfplumber

        if hasattr(src, "seek"):
            src.seek(0)
        pages = []
        with pdfplumber.open(src) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages[:MAX_PREVIEW_PAGES]):
                w_pt, h_pt = float(page.width), float(page.height)
                # Scale the resolution down rather than refusing to draw, so an
                # unusually large page still previews, just at fewer dots.
                page_dpi = dpi
                if w_pt > 0 and h_pt > 0:
                    px = (w_pt * dpi / 72.0) * (h_pt * dpi / 72.0)
                    if px > MAX_RASTER_PX:
                        page_dpi = max(20, int(72.0 * math.sqrt(MAX_RASTER_PX / (w_pt * h_pt))))
                im = page.to_image(resolution=page_dpi)
                buf = _io.BytesIO()
                im.save(buf, format="PNG")
                pages.append(
                    {
                        "index": i,
                        "w_pt": round(w_pt, 2),
                        "h_pt": round(h_pt, 2),
                        "dpi": page_dpi,
                        "png": "data:image/png;base64,"
                        + base64.b64encode(buf.getvalue()).decode("ascii"),
                    }
                )
    except Exception:       # noqa: BLE001 - a preview is a nicety, not the score
        return None
    return {
        "dpi": dpi,
        "pages_total": total,
        "pages_rendered": len(pages),
        "pages": pages,
        "lines": [
            {
                "page": l.page,
                "text": l.text,
                "x0": round(l.x0, 2),
                "x1": round(l.x1, 2),
                "top": round(l.top, 2),
                "bottom": round(l.bottom, 2),
                "bullet": bool(l.is_bullet),
            }
            for l in doc.lines
        ],
    }


def score_document(
    src,
    cfg: Optional[Config] = None,
    benchmark: Optional[str] = None,
    include_preview: bool = False,
    display_name: Optional[str] = None,
) -> Report:
    """Score a resume from a path or a binary stream.

    The web app passes an in-memory stream and a display name, so an uploaded
    PDF is never written to disk and no server path can reach the response.
    """
    cfg = cfg or Config.load()
    # The benchmark selects which checks exist at all: "CMU Resumes" runs 9
    # Overall Format checks and 5 Impact sub-parameters, "CMU Masters -
    # Technical" runs 11 and 4. Copy before overriding so a caller's Config is
    # not left pointing at someone else's benchmark.
    if benchmark and cfg.get(f"benchmark_profiles.{benchmark}"):
        cfg = copy.copy(cfg)
        cfg.data = dict(cfg.data)
        cfg.data["benchmark_profiles"] = dict(cfg.data.get("benchmark_profiles", {}))
        cfg.data["benchmark_profiles"]["default"] = benchmark
    is_path = isinstance(src, (str, bytes, os.PathLike))
    doc: Document = parse_pdf(src)
    st: Structure = build_structure(doc)

    shown = display_name or (os.path.basename(src) if is_path else "resume.pdf")
    rep = Report(
        file=os.path.abspath(src) if is_path and not display_name else shown,
        filename=shown,
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        scored=True,
        overall=0.0,
        zone="red",
    )
    rep.preview = build_preview(src, doc) if include_preview else None
    rep.meta = {
        "name": st.name,
        "pages": doc.n_pages,
        "word_count": doc.word_count,
        "bullet_count": len(st.all_bullets),
        "entry_count": len(st.all_entries),
        "sections": [
            {"heading": s.raw_heading, "canonical": s.canonical,
             "entries": len(s.entries), "bullets": len(s.bullets)}
            for s in st.sections
        ],
        "two_column": doc.two_column,
        "body_font_pt": st.body_font_size,
        "parse_warnings": doc.parse_warnings,
        # Basename only: the absolute path is server state, and on a hosted
        # deployment it would hand every visitor the install layout.
        "rules_file": os.path.basename(cfg.path or "rules.yaml"),
        # The red / yellow / green cutoffs, so the UI can draw the zone band
        # against the same numbers the score was judged by.
        "zones": cfg.get("meta.zones", {"red": [0, 32], "yellow": [33, 85], "green": [86, 100]}),
    }

    min_words = int(cfg.get("meta.min_words_for_score", 200))
    if doc.word_count < min_words:
        rep.scored = False
        rep.blockers.append(
            f"Only {doc.word_count} words. VMock requires at least {min_words} before "
            f"it will return a score at all - add {min_words - doc.word_count} more."
        )
    if not doc.lines:
        rep.scored = False
        rep.blockers.append(
            "No extractable text: this looks like a scanned image or has non-embedded fonts."
        )

    pres = m_pres.score(doc, st, cfg)
    imp, bullets = m_impact.score(doc, st, cfg)
    comp = m_comp.score(doc, st, cfg)
    for mod in (imp, pres, comp):
        reconcile_module(mod)
    rep.modules = [imp, pres, comp]
    rep.bullets = bullets
    rep.overall = round(sum(m.points for m in rep.modules), 1)
    rep.zone = zone_for(rep.overall, cfg)

    # `benchmark` names a check-set profile, not a peer cohort. Passing it
    # straight through meant asking for the "standard_resumes" check set also
    # asked for a cohort curve of that name, which does not exist -- so the
    # peer curve silently fell back to a hard-coded mean of 62 instead of the
    # 70 in rules.yaml. Only use it here if a cohort of that name really exists.
    cohort = benchmark if benchmark and cfg.get(f"benchmark.{benchmark}") else None
    bm = load_benchmark(cfg, cohort)
    pct = _normal_cdf(rep.overall, float(bm.get("mean", 62)), float(bm.get("stdev", 14)))
    rep.benchmark = {
        **bm,
        "percentile": round(pct * 100, 1),
        "delta_from_mean": round(rep.overall - float(bm.get("mean", 62)), 1),
    }
    return rep
