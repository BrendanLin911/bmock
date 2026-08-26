"""
Command line interface.

    python3 -m vmock_clone resume.pdf                 score + write out/report.html
    python3 -m vmock_clone resume.pdf --json          machine-readable
    python3 -m vmock_clone resume.pdf --no-quirks     drop VMock's arbitrary rules
    python3 -m vmock_clone serve                      local web app
    python3 -m vmock_clone benchmark ./resumes -n mba build a cohort bell curve
    python3 -m vmock_clone diff a.pdf b.pdf           compare two versions
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .core import Config
from .report import text_summary, write_html
from .scoring import score_document


def _cfg(args) -> Config:
    cfg = Config.load(getattr(args, "rules", None))
    if getattr(args, "no_quirks", False):
        cfg.data.setdefault("quirks", {})["strict_vmock_quirks"] = False
    if getattr(args, "pages", None):
        cfg.data.setdefault("presentation", {}).setdefault("geometry", {})["page_limit"] = args.pages
    return cfg


def cmd_score(args) -> int:
    if not os.path.isfile(args.pdf):
        print(f"no such file: {args.pdf}", file=sys.stderr)
        return 2
    from .parser import UnreadablePDF

    try:
        rep = score_document(
            args.pdf, cfg=_cfg(args), benchmark=args.benchmark,
            # The standalone HTML report shows the page; --json stays lean.
            include_preview=not (args.json or args.no_html),
        )
    except UnreadablePDF as exc:
        print(f"{args.pdf}: {exc}", file=sys.stderr)
        return 3
    data = rep.to_dict()

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(text_summary(data))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n  json    -> {args.json_out}")
    if not args.no_html:
        out = args.out or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out",
            os.path.splitext(os.path.basename(args.pdf))[0] + "_report.html",
        )
        os.makedirs(os.path.dirname(out), exist_ok=True)
        write_html(data, out)
        print(f"  report  -> {out}")
    return 0


def cmd_serve(args) -> int:
    from .server import serve

    serve(host=args.host, port=args.port, rules=args.rules,
          benchmark=args.benchmark, open_browser=not args.no_browser)
    return 0


def cmd_benchmark(args) -> int:
    from .benchmark import build

    build(args.folder, args.name, cfg=_cfg(args), label=args.label)
    return 0


def cmd_diff(args) -> int:
    from .parser import UnreadablePDF

    cfg = _cfg(args)
    try:
        a = score_document(args.before, cfg=cfg).to_dict()
        b = score_document(args.after, cfg=cfg).to_dict()
    except UnreadablePDF as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(f"  {'':<16}{'before':>10}{'after':>10}{'delta':>10}")
    print("  " + "-" * 46)
    print(f"  {'OVERALL':<16}{a['overall']:>10.1f}{b['overall']:>10.1f}"
          f"{b['overall'] - a['overall']:>+10.1f}")
    am = {m["key"]: m for m in a["modules"]}
    for m in b["modules"]:
        prev = am.get(m["key"], {}).get("points", 0.0)
        print(f"  {m['label']:<16}{prev:>10.1f}{m['points']:>10.1f}{m['points'] - prev:>+10.1f}")
    fixed = {f["message"] for mm in a["modules"] for f in mm["findings"]}
    print()
    for m in b["modules"]:
        for s in m["subscores"]:
            prev = next((x for x in am.get(m["key"], {}).get("subscores", [])
                         if x["key"] == s["key"]), None)
            if prev and abs(prev["points"] - s["points"]) > 0.05:
                print(f"  {s['label']:<28}{prev['points']:>7.1f} -> {s['points']:<7.1f}"
                      f"{s['points'] - prev['points']:>+7.1f}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vmock_clone",
                                description="Rule-based resume scorer modelled on VMock.")
    p.add_argument("--rules", help="path to an alternative rules.yaml")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("score", help="score one resume (default)")
    s.add_argument("pdf")
    s.add_argument("--json", action="store_true", help="print JSON to stdout")
    s.add_argument("--json-out", help="also write JSON here")
    s.add_argument("--out", help="path for the HTML report")
    s.add_argument("--no-html", action="store_true")
    s.add_argument("--no-quirks", action="store_true", help="disable VMock's arbitrary rules")
    s.add_argument("--benchmark", help="benchmark name from benchmarks/")
    s.add_argument("--pages", type=int, help="override the page limit")
    s.set_defaults(func=cmd_score)

    v = sub.add_parser("serve", help="run the local web app")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8420)
    v.add_argument("--benchmark")
    v.add_argument("--no-browser", action="store_true")
    v.set_defaults(func=cmd_serve)

    b = sub.add_parser("benchmark", help="build a cohort bell curve from a folder of PDFs")
    b.add_argument("folder")
    b.add_argument("-n", "--name", default="cohort")
    b.add_argument("--label", default="")
    b.add_argument("--no-quirks", action="store_true")
    b.set_defaults(func=cmd_benchmark)

    d = sub.add_parser("diff", help="compare two versions of a resume")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--no-quirks", action="store_true")
    d.set_defaults(func=cmd_diff)

    argv = list(sys.argv[1:] if argv is None else argv)
    # bare `python3 -m vmock_clone resume.pdf` implies `score`
    if argv and not argv[0].startswith("-") and argv[0] not in {"score", "serve", "benchmark", "diff"}:
        argv.insert(0, "score")
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
