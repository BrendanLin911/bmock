"""
Local web app. Standard library only - no Flask, no build step.

Binds to 127.0.0.1 by default: uploaded resumes are parsed in-process and
never leave the machine.
"""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

from .core import Config
from .parser import UnreadablePDF
from .scoring import score_document

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
MAX_UPLOAD = 25 * 1024 * 1024
CTYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".js": "application/javascript; charset=utf-8", ".ico": "image/x-icon"}


# ---------------------------------------------------------------------------
def parse_multipart(body: bytes, content_type: str) -> Dict[str, List[Tuple[Optional[str], bytes]]]:
    """Minimal multipart/form-data parser (the stdlib `cgi` module is deprecated)."""
    m = re.search(r'boundary="?([^";]+)"?', content_type or "", re.I)
    if not m:
        return {}
    boundary = b"--" + m.group(1).encode()
    fields: Dict[str, List[Tuple[Optional[str], bytes]]] = {}
    for part in body.split(boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        head, _, data = part.partition(b"\r\n\r\n")
        if not _:
            continue
        headers = head.decode("utf-8", "replace")
        name = re.search(r'name="([^"]*)"', headers)
        if not name:
            continue
        filename = re.search(r'filename="([^"]*)"', headers)
        fields.setdefault(name.group(1), []).append(
            (filename.group(1) if filename else None, data.rstrip(b"\r\n"))
        )
    return fields


class Handler(BaseHTTPRequestHandler):
    server_version = "VMockClone/1.0"
    protocol_version = "HTTP/1.1"

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):
        if os.environ.get("VMOCK_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    # -- routes ------------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0]
        name = "index.html" if path in ("/", "/index.html") else os.path.basename(path)
        full = os.path.join(WEB, name)
        if not os.path.isfile(full) or os.path.dirname(os.path.abspath(full)) != os.path.abspath(WEB):
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        with open(full, "rb") as f:
            body = f.read()
        self._send(200, body, CTYPES.get(os.path.splitext(name)[1], "application/octet-stream"))

    def do_POST(self):
        if self.path.split("?")[0] != "/api/score":
            self._json(404, {"error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._json(400, {"error": "empty upload"})
            return
        if length > MAX_UPLOAD:
            self._json(413, {"error": f"file too large (limit {MAX_UPLOAD // (1024*1024)} MB)"})
            return

        body = b""
        while len(body) < length:
            chunk = self.rfile.read(min(65536, length - len(body)))
            if not chunk:
                break
            body += chunk

        fields = parse_multipart(body, self.headers.get("Content-Type", ""))
        files = fields.get("file") or []
        if not files or not files[0][1]:
            self._json(400, {"error": "no file received"})
            return
        filename, data = files[0]
        filename = os.path.basename(filename or "resume.pdf")
        if not data.startswith(b"%PDF"):
            self._json(400, {"error": "that does not look like a PDF"})
            return

        quirks_on = True
        if fields.get("quirks"):
            quirks_on = fields["quirks"][0][1].strip() not in (b"0", b"false", b"")

        cfg = Config.load(self.server.rules_path)
        cfg.data.setdefault("quirks", {})["strict_vmock_quirks"] = quirks_on

        # mkstemp: unpredictable name, mode 0600, never follows a symlink.
        fd, tmp = tempfile.mkstemp(prefix="vmock_", suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            report = score_document(
                tmp, cfg=cfg, benchmark=self.server.benchmark, include_preview=True
            )
            payload = report.to_dict()
            payload["filename"] = filename
            payload["file"] = filename          # never leak the temp path
            self._json(200, payload)
        except UnreadablePDF as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:                # noqa: BLE001 - surfaced to the UI
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _free_port(preferred: int, host: str) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 40)):
        with socket.socket() as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return 0


def serve(host: str = "127.0.0.1", port: int = 8420, rules: Optional[str] = None,
          benchmark: Optional[str] = None, open_browser: bool = True):
    port = _free_port(port, host)
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.rules_path = rules
    httpd.benchmark = benchmark
    url = f"http://{host}:{port}"
    print(f"  VMock Clone running at  {url}")
    print("  Drop a resume PDF on the page. Nothing leaves this machine.")
    print("  Ctrl-C to stop.\n")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        httpd.server_close()
