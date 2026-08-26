"""The web app, as a WSGI application.

This is the single request path: `python3 run.py` serves it through wsgiref
and the container serves it through gunicorn, so there is no second adapter
to drift out of sync.

Nothing an uploader sends is written to disk. The PDF is read into memory,
handed to the scorer as a stream, and dropped when the response is built.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import traceback
from http import HTTPStatus
from typing import Dict, List, Optional, Tuple

from .core import Config
from .parser import UnreadablePDF
from .scoring import score_document

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

# A resume is a few hundred KB. The old 25MB ceiling admitted a ~400-page
# document and made every buffer in this file 3x larger for nothing.
MAX_UPLOAD = int(os.environ.get("VMOCK_MAX_UPLOAD", 8 * 1024 * 1024))
READ_CHUNK = 65536
DRAIN_LIMIT = 2 * 1024 * 1024

CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}
JSON_CT = "application/json; charset=utf-8"
TEXT_CT = "text/plain; charset=utf-8"

# The page loads its own script and stylesheet, shows data: image previews and
# talks only to itself. Nothing here needs 'unsafe-inline' -- the bootstrap
# lives in web/boot.js precisely so it does not have to.
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'"
)


class RequestTooLarge(Exception):
    pass


_BOUNDARY_RE = re.compile(r'boundary=(?:"([^"]+)"|([^\s;]+))', re.I)
_NAME_RE = re.compile(r'name="([^"]*)"')
_FILENAME_RE = re.compile(r'filename="([^"]*)"')


def parse_multipart(
    body: bytes, content_type: str
) -> Dict[str, List[Tuple[Optional[str], bytes]]]:
    """Minimal multipart/form-data parser (the stdlib `cgi` module is gone).

    The CRLF before a delimiter belongs to the delimiter, so it is folded into
    the split pattern rather than stripped afterwards. Stripping was subtly
    wrong: `data.rstrip(b"\\r\\n")` removes *every* trailing CR and LF, so any
    PDF whose last bytes were newlines lost them and reached the parser
    truncated.
    """
    m = _BOUNDARY_RE.search(content_type or "")
    if not m:
        return {}
    raw = m.group(1) or m.group(2)
    if not 1 <= len(raw) <= 70:          # RFC 2046: a boundary is 1-70 chars
        return {}
    boundary = raw.encode("latin-1", "replace")

    if body.startswith(b"--" + boundary):    # the first delimiter has no CRLF
        body = b"\r\n" + body
    fields: Dict[str, List[Tuple[Optional[str], bytes]]] = {}
    for part in body.split(b"\r\n--" + boundary)[1:]:
        if part.startswith(b"--"):           # closing delimiter; ignore epilogue
            break
        if part.startswith(b"\r\n"):
            part = part[2:]
        else:                                # transport padding after boundary
            _, sep, part = part.partition(b"\r\n")
            if not sep:
                continue
        head, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = head.decode("utf-8", "replace")
        name = _NAME_RE.search(headers)
        if not name:
            continue
        filename = _FILENAME_RE.search(headers)
        fields.setdefault(name.group(1), []).append(
            (filename.group(1) if filename else None, data)
        )
    return fields


def read_body(environ) -> bytes:
    """Read exactly CONTENT_LENGTH bytes from wsgi.input.

    Never call `.read()` with no argument: PEP 3333 does not promise the stream
    signals EOF, and wsgiref hands over the raw socket, so a bare read blocks
    until the peer gives up. Never read past CONTENT_LENGTH either -- on a
    keep-alive connection the bytes after the body are the next request.
    """
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        return b""
    if length <= 0:
        return b""
    if length > MAX_UPLOAD:
        raise RequestTooLarge(length)
    stream = environ["wsgi.input"]
    chunks: List[bytes] = []
    remaining = length
    while remaining > 0:
        chunk = stream.read(min(READ_CHUNK, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)      # join once: `body += chunk` is quadratic


def _drain(environ, limit: int = DRAIN_LIMIT) -> None:
    """Swallow a bounded part of an oversized body.

    Answering 413 without reading anything is invisible on loopback but resets
    the connection over a real network, and the browser reports a transport
    error instead of showing the message.
    """
    stream = environ.get("wsgi.input")
    if stream is None:
        return
    drained = 0
    try:
        while drained < limit:
            chunk = stream.read(min(READ_CHUNK, limit - drained))
            if not chunk:
                break
            drained += len(chunk)
    except Exception:            # noqa: BLE001 - draining is best-effort
        pass


class Response:
    __slots__ = ("code", "body", "ctype", "extra")

    def __init__(self, code: int, body: bytes, ctype: str, extra=()):
        self.code, self.body, self.ctype, self.extra = code, body, ctype, list(extra)

    @property
    def status(self) -> str:
        return f"{self.code} {HTTPStatus(self.code).phrase}"

    def headers(self) -> List[Tuple[str, str]]:
        out = [
            ("Content-Type", self.ctype),
            ("Content-Length", str(len(self.body))),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
        ]
        out.extend(self.extra)
        return out


def json_response(code: int, obj, extra=()) -> Response:
    return Response(
        code,
        json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        JSON_CT,
        list(extra) + [("Cache-Control", "no-store")],
    )


def _clean_filename(raw: Optional[str]) -> str:
    """A bare filename, from something a browser was willing to send."""
    name = os.path.basename((raw or "").replace("\\", "/")) or "resume.pdf"
    name = re.sub(r"[\r\n\x00]", "", name).strip()
    return name[:120] or "resume.pdf"


class ScoreApp:
    """Routes: GET static files out of web/, POST /api/score."""

    def __init__(self, rules: Optional[str] = None, benchmark: Optional[str] = None):
        # gunicorn cannot pass constructor arguments through `module:app`, so
        # both settings also read the environment.
        self.rules = rules or os.environ.get("VMOCK_RULES") or None
        self.benchmark = benchmark or os.environ.get("VMOCK_BENCHMARK") or None
        self.allowed_origins = {
            o.strip().rstrip("/")
            for o in (os.environ.get("VMOCK_ALLOWED_ORIGINS") or "").split(",")
            if o.strip()
        }

    # -- helpers ---------------------------------------------------------
    def _config(self, quirks_on: bool) -> Config:
        cfg = Config.load(self.rules)
        cfg.data.setdefault("quirks", {})["strict_vmock_quirks"] = quirks_on
        return cfg

    def _origin_ok(self, environ) -> bool:
        """Same-origin posts only.

        multipart/form-data is CORS-safelisted, so any page anywhere can make a
        visitor's browser POST here. The response is unreadable to them, but
        scoring is expensive and they do not need to read it to waste it.
        """
        origin = environ.get("HTTP_ORIGIN")
        if not origin:
            return True              # same-origin fetches often omit it
        origin = origin.rstrip("/")
        if origin in self.allowed_origins:
            return True
        host = environ.get("HTTP_HOST", "")
        scheme = environ.get("wsgi.url_scheme", "http")
        return origin in (f"{scheme}://{host}", f"http://{host}", f"https://{host}")

    def _log(self, environ, message: str) -> None:
        errors = environ.get("wsgi.errors") or sys.stderr
        try:
            errors.write(message.rstrip() + "\n")
        except Exception:            # noqa: BLE001 - logging must never raise
            pass

    # -- routes ----------------------------------------------------------
    def static(self, path: str) -> Response:
        name = "index.html" if path in ("/", "/index.html") else os.path.basename(path)
        full = os.path.join(WEB, name)
        # basename() already flattened any traversal; realpath additionally
        # refuses a symlink inside web/ that points out of it.
        if not os.path.isfile(full) or os.path.dirname(os.path.realpath(full)) != os.path.realpath(WEB):
            return Response(404, b"not found", TEXT_CT)
        with open(full, "rb") as fh:
            body = fh.read()
        ctype = CTYPES.get(os.path.splitext(name)[1], "application/octet-stream")
        extra = [("Cache-Control", "no-cache")]
        if ctype.startswith("text/html"):
            extra.append(("Content-Security-Policy", CSP))
        return Response(200, body, ctype, extra)

    def score(self, environ) -> Response:
        if not self._origin_ok(environ):
            _drain(environ)
            return json_response(403, {"error": "cross-origin upload rejected"})
        try:
            body = read_body(environ)
        except RequestTooLarge:
            _drain(environ)
            return json_response(
                413, {"error": f"file too large (limit {MAX_UPLOAD // (1024 * 1024)} MB)"}
            )
        if not body:
            return json_response(400, {"error": "empty upload"})

        fields = parse_multipart(body, environ.get("CONTENT_TYPE", ""))
        del body                      # the upload exists once, as `data`, below
        files = fields.get("file") or []
        if not files or not files[0][1]:
            return json_response(400, {"error": "no file received"})
        raw_name, data = files[0]
        if not data.startswith(b"%PDF"):
            return json_response(400, {"error": "that does not look like a PDF"})
        filename = _clean_filename(raw_name)

        quirks_on = True
        if fields.get("quirks"):
            quirks_on = fields["quirks"][0][1].strip() not in (b"0", b"false", b"")

        try:
            cfg = self._config(quirks_on)
            report = score_document(
                io.BytesIO(data),
                cfg=cfg,
                benchmark=self.benchmark,
                include_preview=True,
                display_name=filename,
            )
            return json_response(200, report.to_dict())
        except UnreadablePDF as exc:
            return json_response(400, {"error": str(exc)})
        except MemoryError:
            return json_response(503, {"error": "this document was too large to analyse"})
        except Exception as exc:      # noqa: BLE001
            # The detail stays on the server: exception strings carry paths and
            # fragments of whatever was being parsed.
            self._log(environ, f"score failed: {type(exc).__name__}: {exc}")
            if os.environ.get("VMOCK_VERBOSE"):
                self._log(environ, traceback.format_exc())
            return json_response(500, {"error": "could not analyse this document"})

    # -- WSGI ------------------------------------------------------------
    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/") or "/"
        if method in ("GET", "HEAD"):
            resp = self.static(path)
            if method == "HEAD":
                resp = Response(resp.code, b"", resp.ctype, resp.extra)
        elif method == "POST":
            if path != "/api/score":
                _drain(environ)
                resp = json_response(404, {"error": "unknown endpoint"})
            else:
                resp = self.score(environ)
        else:
            resp = json_response(405, {"error": "method not allowed"},
                                 extra=[("Allow", "GET, HEAD, POST")])
        start_response(resp.status, resp.headers())
        return [resp.body]
