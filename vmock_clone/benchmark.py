"""
Build a cohort benchmark from a folder of resumes.

VMock's bell curve is not a universal standard: each institution uploads its
own historical resumes and students are plotted against that population
("benchmarked against your peers at Northwestern"). This reproduces the
mechanic - point it at a folder of PDFs and it writes benchmarks/<name>.json.
"""

from __future__ import annotations

import glob
import json
import os
import statistics
from typing import List, Optional

from .core import Config
from .scoring import score_document

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")


def build(folder: str, name: str, cfg: Optional[Config] = None, label: str = "") -> dict:
    cfg = cfg or Config.load()
    pdfs = sorted(glob.glob(os.path.join(folder, "**", "*.pdf"), recursive=True))
    if not pdfs:
        raise SystemExit(f"no PDFs found under {folder}")

    scores: List[float] = []
    per_module = {"impact": [], "presentation": [], "competencies": []}
    skipped = []
    for path in pdfs:
        try:
            rep = score_document(path, cfg=cfg)
        except Exception as exc:                # noqa: BLE001
            skipped.append((os.path.basename(path), str(exc)[:120]))
            print(f"  skip   {os.path.basename(path)}  ({type(exc).__name__})")
            continue
        scores.append(rep.overall)
        for m in rep.modules:
            per_module[m.key].append(m.points)
        print(f"  {rep.overall:5.1f}  {os.path.basename(path)}")

    if len(scores) < 2:
        raise SystemExit("need at least 2 scoreable resumes to build a benchmark")

    data = {
        "label": label or f"{name} cohort ({len(scores)} resumes)",
        "n": len(scores),
        "mean": round(statistics.mean(scores), 2),
        "stdev": round(statistics.pstdev(scores), 2) or 1.0,
        "median": round(statistics.median(scores), 2),
        "min": round(min(scores), 1),
        "max": round(max(scores), 1),
        "module_means": {k: round(statistics.mean(v), 2) for k, v in per_module.items() if v},
        "source_folder": os.path.abspath(folder),
        "skipped": skipped,
    }
    os.makedirs(ROOT, exist_ok=True)
    out = os.path.join(ROOT, f"{name}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"\n  n={data['n']}  mean={data['mean']}  sd={data['stdev']}  -> {out}")
    if skipped:
        print(f"  skipped {len(skipped)} file(s)")
    return data
