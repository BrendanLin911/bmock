"""Local development server.

Runs the same WSGI application the container runs (`vmock_clone.wsgiapp`)
through the standard library's wsgiref, so what you test locally and what
ships behind gunicorn are one code path rather than two that drift.

Uploaded resumes are parsed from memory and never written to disk. Bound to
127.0.0.1 by default, so on a laptop nothing leaves the machine at all.
"""

from __future__ import annotations

import os
import socket
import threading
import webbrowser
from typing import Optional
from wsgiref.simple_server import WSGIRequestHandler, make_server

from .wsgiapp import ScoreApp

# Re-exported for anything that imported them from here.
from .wsgiapp import CTYPES, MAX_UPLOAD, WEB, parse_multipart  # noqa: F401


class _DevHandler(WSGIRequestHandler):
    """Quiet by default; keep-alive on, since every response sets a length."""

    protocol_version = "HTTP/1.1"
    server_version = "VMockClone/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        if os.environ.get("VMOCK_VERBOSE"):
            super().log_message(fmt, *args)

    def address_string(self):
        # Never write a visitor's IP to the log, even in verbose mode.
        return "-"


def _free_port(preferred: int, host: str) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 40)):
        with socket.socket() as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return 0


def resolve_port(port: Optional[int], host: str) -> int:
    """Scan for a free port only when nobody named one.

    A port that arrived from $PORT or from --port is a contract: bind it, or
    fail where someone can see the error. Silently landing on the next port up
    is undiagnosable behind a platform health check, which routes to $PORT and
    nowhere else.
    """
    env_port = os.environ.get("PORT")
    if port is not None:
        return int(port)
    if env_port:
        return int(env_port)
    return _free_port(8420, host) or 8420


def serve(host: Optional[str] = None, port: Optional[int] = None,
          rules: Optional[str] = None, benchmark: Optional[str] = None,
          open_browser: bool = True):
    host = host or os.environ.get("HOST") or "127.0.0.1"
    named = port is not None or bool(os.environ.get("PORT"))
    port = resolve_port(port, host)

    app = ScoreApp(rules=rules, benchmark=benchmark)
    httpd = make_server(host, port, app, handler_class=_DevHandler)

    url = f"http://{host}:{port}"
    print(f"  VMock Clone running at  {url}")
    print("  Drop a resume PDF on the page. It is parsed in memory and never written to disk.")
    print("  Ctrl-C to stop.\n")
    # A platform that named the port is not a person with a browser.
    if open_browser and not named:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        httpd.server_close()
