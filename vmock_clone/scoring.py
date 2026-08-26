"""Orchestrator: parse -> structure -> three modules -> one score."""

from __future__ import annotations

import math
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
                        "quirk": f.quirk,
                        "line_index": f.line_index,
                    }
                )
        rows.sort(key=lambda r: -r["points"])
        return rows[:n]

    def quirk_cost(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for mod in self.modules:
            for f in mod.all_findings:
                if f.quirk and f.points_lost > 0:
                    out[f.quirk] = round(out.get(f.quirk, 0.0) + f.points_lost, 2)
        return out

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
            "quirk_cost": self.quirk_cost(),
            "meta": self.meta,
        }


def load_benchmark(cfg: Config, name: Optional[str] = None) -> Dict[str, Any]:
    name = name or cfg.get("benchmark.default", "general")
    inline = cfg.get(f"benchmark.{name}")
    if isinstance(inline, dict):
        return {"name": name, **inline}
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")
    path = os.path.join(root, f"{name}.json")
    if os.path.exists(path):
        import json

        with open(path, encoding="utf-8") as f:
            return {"name": name, **json.load(f)}
    return {"name": "general", "label": "General cohort", "mean": 62.0, "stdev": 14.0, "n": 0}


PREVIEW_DPI = 110


def build_preview(path: str, doc: Document, dpi: int = PREVIEW_DPI) -> Optional[Dict[str, Any]]:
    """Page rasters plus line geometry, so the UI can show the real resume.

    VMock puts your actual page on the left and pins its feedback to the line
    that earned it. Everything here is derived from the same parse the score
    comes from, so a pin can never drift from what was measured.
    """
    try:
        import base64
        import io as _io

        import pdfplumber

        pages = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                im = page.to_image(resolution=dpi)
                buf = _io.BytesIO()
                im.save(buf, format="PNG")
                pages.append(
                    {
                        "index": i,
                        "w_pt": round(float(page.width), 2),
                        "h_pt": round(float(page.height), 2),
                        "png": "data:image/png;base64,"
                        + base64.b64encode(buf.getvalue()).decode("ascii"),
                    }
                )
    except Exception:       # noqa: BLE001 - a preview is a nicety, not the score
        return None
    return {
        "dpi": dpi,
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
    path: str,
    cfg: Optional[Config] = None,
    benchmark: Optional[str] = None,
    include_preview: bool = False,
) -> Report:
    cfg = cfg or Config.load()
    doc: Document = parse_pdf(path)
    st: Structure = build_structure(doc)

    rep = Report(
        file=os.path.abspath(path),
        filename=os.path.basename(path),
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        scored=True,
        overall=0.0,
        zone="red",
    )
    rep.preview = build_preview(path, doc) if include_preview else None
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
        "rules_file": cfg.path,
        "quirks_enabled": bool(cfg.get("quirks.strict_vmock_quirks", True)),
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

    bm = load_benchmark(cfg, benchmark)
    pct = _normal_cdf(rep.overall, float(bm.get("mean", 62)), float(bm.get("stdev", 14)))
    rep.benchmark = {
        **bm,
        "percentile": round(pct * 100, 1),
        "delta_from_mean": round(rep.overall - float(bm.get("mean", 62)), 1),
    }
    return rep
