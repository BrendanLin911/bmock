"""Self-contained HTML report: the same renderer as the web app, inlined."""

from __future__ import annotations

import html
import json
import os
from typing import Any, Dict

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resume Score - {filename}</title>
<style>
{css}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand"><i></i> Resume Score</div>
  <span class="badge">rule-based &middot; no LLM</span>
  <span class="fname">{filename}</span>
</div>
<div id="report"></div>
<script>
{js}
</script>
<script>
var __DATA__ = {data};
window.VMockReport.render(__DATA__, document.getElementById("report"));
</script>
</body>
</html>
"""


def _read(name: str) -> str:
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def render_html(report_dict: Dict[str, Any]) -> str:
    payload = json.dumps(report_dict, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")          # keep it out of </script>
    return TEMPLATE.format(
        filename=html.escape(str(report_dict.get("filename", "resume.pdf")), quote=True),
        css=_read("style.css"),
        js=_read("app.js"),
        data=payload,
    )


def write_html(report_dict: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(report_dict))
    return path


def text_summary(report_dict: Dict[str, Any], width: int = 78) -> str:
    """Terminal summary."""
    d = report_dict
    zone = d["zone"].upper()
    out = []
    out.append("=" * width)
    out.append(f"  {d['filename']}")
    out.append(f"  OVERALL  {d['overall']:.1f} / 100     {zone} ZONE"
               f"     {d['benchmark'].get('percentile', 0):.0f}th percentile")
    out.append("=" * width)
    for m in d["modules"]:
        filled = int(round(m["ratio"] * 28))
        out.append(f"  {m['label']:<14} {m['points']:5.1f} / {m['max_points']:<4.0f} "
                   f"[{'#' * filled}{'.' * (28 - filled)}]")
        def emit(s, depth=0):
            def count(node):
                n = sum(1 for f in node["findings"] if f["severity"] in ("error", "warn"))
                return n + sum(count(c) for c in node.get("children", []))
            issues = count(s)
            flag = f"  ({issues} issue{'s' if issues != 1 else ''})" if issues else ""
            pad = "      " + "  " * depth
            label = ("- " if depth else "") + s["label"]
            width = max(10, 30 - 2 * depth - (len(pad) - 6))
            out.append(f"{pad}{label:<{width}}{s['points']:5.1f} / "
                       f"{s['max_points']:<4.0f}{flag}")
            for c in s.get("children", []):
                emit(c, depth + 1)

        for s in m["subscores"]:
            emit(s)
    if d.get("blockers"):
        out.append("")
        out.append("  BLOCKERS")
        for b in d["blockers"]:
            out.append(f"    ! {b}")
    out.append("")
    out.append("  BIGGEST WINS AVAILABLE")
    for a in d.get("top_actions", [])[:8]:
        tag = " [quirk]" if a.get("quirk") else ""
        out.append(f"    +{a['points']:<5.1f} {a['message']}{tag}")
        if a.get("fix"):
            out.append(f"           -> {a['fix']}")
    qc = d.get("quirk_cost") or {}
    if qc:
        total = sum(qc.values())
        out.append("")
        out.append(f"  QUIRK COST  {total:.1f} points lost to reproduced VMock quirks")
        for k, v in sorted(qc.items(), key=lambda kv: -kv[1]):
            out.append(f"    quirks.{k:<28} -{v:.1f}")
    out.append("=" * width)
    return "\n".join(out)
