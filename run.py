#!/usr/bin/env python3
"""Start the local web app.  python3 run.py  [--port 8420] [--no-browser]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vmock_clone.__main__ import main  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["serve"] + argv
    raise SystemExit(main(argv))
