"""Tests for the web layer: multipart framing, routing, limits, and the
promises the hosted deployment makes about not keeping anything.

The WSGI shape is what makes these cheap — the whole app is exercised with a
dict and a BytesIO, no socket involved.
"""

import glob
import io
import json
import os
import re
import sys
import tempfile
import unittest
from wsgiref.util import setup_testing_defaults

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vmock_clone import report as report_mod
from vmock_clone.parser import UnreadablePDF, parse_pdf
from vmock_clone.scoring import (
    BENCHMARK_PUBLIC_KEYS,
    _public_benchmark,
    load_benchmark,
    score_document,
)
from vmock_clone.server import resolve_port
from vmock_clone.wsgiapp import MAX_UPLOAD, ScoreApp, parse_multipart

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
BOUNDARY = "----WebKitFormBoundaryTest0123"


def sample(name):
    return os.path.join(SAMPLES, name)


def multipart(payload, filename="resume.pdf", quirks=b"1"):
    head = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode()
    tail = (
        f"\r\n--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="quirks"\r\n\r\n'
    ).encode() + quirks + f"\r\n--{BOUNDARY}--\r\n".encode()
    return head + payload + tail


def call(app, method, path, body=b"", ctype=None, env_extra=None, declared_length=None):
    env = {}
    setup_testing_defaults(env)
    env.update(REQUEST_METHOD=method, PATH_INFO=path)
    env["CONTENT_LENGTH"] = str(len(body) if declared_length is None else declared_length)
    if ctype:
        env["CONTENT_TYPE"] = ctype
    if env_extra:
        env.update(env_extra)
    env["wsgi.input"] = io.BytesIO(body)
    env["wsgi.errors"] = io.StringIO()
    out = {}

    def start_response(status, headers):
        out["status"] = status
        out["headers"] = dict(headers)

    chunks = app(env, start_response)
    return out, b"".join(chunks)


class TestMultipart(unittest.TestCase):
    """The old parser used rstrip(b'\\r\\n'), which is byte-SET stripping and
    silently truncated any PDF whose last bytes were newlines."""

    def _roundtrip(self, payload):
        body = multipart(payload)
        fields = parse_multipart(body, f"multipart/form-data; boundary={BOUNDARY}")
        return fields["file"][0][1]

    def test_byte_exact_for_awkward_tails(self):
        for payload in (
            b"%PDF-1.4 plain",
            b"%PDF-1.4 x\n",
            b"%PDF-1.4 x\r\n",
            b"%PDF-1.4 x\n\n\n",
            b"%PDF-1.4 x\r",
            b"%PDF-1.4 \x00\xff\x0d\x0a",
        ):
            self.assertEqual(self._roundtrip(payload), payload)

    def test_byte_exact_for_a_real_pdf(self):
        with open(sample("strong_resume.pdf"), "rb") as fh:
            data = fh.read()
        self.assertEqual(self._roundtrip(data), data)

    def test_filename_and_extra_fields(self):
        fields = parse_multipart(
            multipart(b"%PDF-1.4", filename="my cv.pdf", quirks=b"0"),
            f"multipart/form-data; boundary={BOUNDARY}",
        )
        self.assertEqual(fields["file"][0][0], "my cv.pdf")
        self.assertEqual(fields["quirks"][0][1], b"0")

    def test_missing_or_absurd_boundary_is_not_a_crash(self):
        self.assertEqual(parse_multipart(b"whatever", "multipart/form-data"), {})
        self.assertEqual(parse_multipart(b"whatever", f"boundary={'x' * 200}"), {})


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = ScoreApp()

    def test_index_is_served_with_a_csp(self):
        out, body = call(self.app, "GET", "/")
        self.assertEqual(out["status"], "200 OK")
        self.assertIn(b"<title>", body)
        self.assertIn("Content-Security-Policy", out["headers"])
        self.assertNotIn("unsafe-inline", out["headers"]["Content-Security-Policy"])

    def test_no_inline_script_in_index(self):
        """The CSP above forbids it, so a regression here would blank the page."""
        with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotRegex(html, r"<script(?![^>]*\ssrc=)[^>]*>\s*\S")

    def test_traversal_is_refused(self):
        for path in ("/../rules.yaml", "/../../etc/passwd", "/..%2frules.yaml"):
            out, _ = call(self.app, "GET", path)
            self.assertEqual(out["status"], "404 Not Found", path)

    def test_unknown_post_and_bad_method(self):
        out, _ = call(self.app, "POST", "/nope")
        self.assertEqual(out["status"], "404 Not Found")
        out, _ = call(self.app, "DELETE", "/")
        self.assertEqual(out["status"], "405 Method Not Allowed")

    def test_head_has_headers_but_no_body(self):
        out, body = call(self.app, "HEAD", "/")
        self.assertEqual(out["status"], "200 OK")
        self.assertEqual(body, b"")


class TestUploadPath(unittest.TestCase):
    def setUp(self):
        self.app = ScoreApp()
        with open(sample("strong_resume.pdf"), "rb") as fh:
            self.pdf = fh.read()

    def post(self, body, **kw):
        return call(
            self.app, "POST", "/api/score", body,
            f"multipart/form-data; boundary={BOUNDARY}", **kw
        )

    def test_scores_an_upload(self):
        out, body = self.post(multipart(self.pdf, filename="strong_resume.pdf"))
        self.assertEqual(out["status"], "200 OK")
        data = json.loads(body)
        self.assertGreater(data["overall"], 0)
        self.assertEqual(data["filename"], "strong_resume.pdf")

    def test_http_score_matches_the_library_score(self):
        out, body = self.post(multipart(self.pdf))
        direct = score_document(sample("strong_resume.pdf"))
        self.assertAlmostEqual(json.loads(body)["overall"], round(direct.overall, 1), places=1)

    def test_empty_and_non_pdf_are_rejected(self):
        out, body = self.post(b"")
        self.assertEqual(out["status"], "400 Bad Request")
        out, body = self.post(multipart(b"MZ this is an exe"))
        self.assertEqual(out["status"], "400 Bad Request")
        self.assertIn("PDF", json.loads(body)["error"])

    def test_oversize_is_refused_before_it_is_buffered(self):
        out, body = self.post(b"x" * 64, declared_length=MAX_UPLOAD + 1)
        # Assert the code, not the phrase: CPython renamed 413's reason text.
        self.assertTrue(out["status"].startswith("413 "), out["status"])
        self.assertIn("too large", json.loads(body)["error"])

    def test_cross_origin_upload_is_refused(self):
        out, _ = self.post(multipart(self.pdf),
                           env_extra={"HTTP_ORIGIN": "https://evil.example"})
        self.assertEqual(out["status"], "403 Forbidden")

    def test_same_origin_upload_is_allowed(self):
        out, _ = self.post(
            multipart(self.pdf),
            env_extra={"HTTP_ORIGIN": "http://testserver", "HTTP_HOST": "testserver"},
        )
        self.assertEqual(out["status"], "200 OK")

    def test_windows_path_is_reduced_to_a_bare_filename(self):
        out, body = self.post(multipart(self.pdf, filename=r"C:\Users\bob\my resume.pdf"))
        self.assertEqual(json.loads(body)["filename"], "my resume.pdf")


class TestKeepsNothing(unittest.TestCase):
    """The hosted promise: scored in memory, nothing written, no server state
    in the response."""

    def setUp(self):
        self.app = ScoreApp()
        with open(sample("strong_resume.pdf"), "rb") as fh:
            self.pdf = fh.read()

    def test_upload_never_touches_disk(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "*")))
        call(self.app, "POST", "/api/score", multipart(self.pdf),
             f"multipart/form-data; boundary={BOUNDARY}")
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "*")))
        self.assertEqual(after - before, set())

    def test_response_carries_no_server_paths(self):
        out, body = call(self.app, "POST", "/api/score", multipart(self.pdf),
                         f"multipart/form-data; boundary={BOUNDARY}")
        payload = json.loads(body)
        self.assertNotIn("/", payload["file"])
        self.assertEqual(payload["meta"]["rules_file"], "rules.yaml")
        self.assertNotIn(ROOT, body.decode("utf-8"))

    def test_scoring_from_a_stream_needs_no_path(self):
        rep = score_document(io.BytesIO(self.pdf), display_name="x.pdf")
        self.assertEqual(rep.file, "x.pdf")
        self.assertEqual(rep.filename, "x.pdf")

    def test_benchmark_file_fields_are_whitelisted(self):
        """A cohort JSON is built from real people's resumes, so only score
        data may reach the client. Tested against the whitelist directly: an
        earlier version wrote a probe file into benchmarks/ and left it behind
        when unlink failed, which then got committed."""
        hostile = {
            "label": "probe", "n": 5, "mean": 70, "stdev": 9,
            "source_folder": "/home/deploy/private_resumes",
            "skipped": [["Jane_Doe_Resume.pdf", "boom"]],
        }
        public = _public_benchmark("probe", hostile)
        self.assertEqual(public["label"], "probe")
        self.assertEqual(public["n"], 5)
        self.assertNotIn("source_folder", public)
        self.assertNotIn("skipped", public)

    def test_benchmark_writer_records_no_names_or_paths(self):
        """Belt and braces: the fields must not be written in the first place."""
        with open(os.path.join(ROOT, "vmock_clone", "benchmark.py"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn('"source_folder"', source)
        self.assertNotIn('"skipped": skipped', source)

    def test_default_benchmark_ships_only_score_data(self):
        from vmock_clone.core import Config

        bm = load_benchmark(Config.load())
        self.assertLessEqual(set(bm) - {"name"}, set(BENCHMARK_PUBLIC_KEYS))

    def test_server_error_detail_is_not_returned_to_the_client(self):
        app = ScoreApp()
        app._config = lambda quirks_on: (_ for _ in ()).throw(
            RuntimeError("/secret/path/rules.yaml exploded")
        )
        out, body = call(app, "POST", "/api/score", multipart(self.pdf),
                         f"multipart/form-data; boundary={BOUNDARY}")
        self.assertEqual(out["status"], "500 Internal Server Error")
        self.assertNotIn("secret", body.decode("utf-8"))


class TestResourceLimits(unittest.TestCase):
    """A PDF's declared geometry is attacker-controlled and free to inflate."""

    @staticmethod
    def build(npages, width=612, height=792):
        content = b"BT /F1 10 Tf 72 720 Td (Engineered a pipeline) Tj ET"
        objs, kids, n = [], [], 4
        for _ in range(npages):
            cid, pid, n = n, n + 1, n + 2
            objs.append((cid, b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)))
            objs.append((pid, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
                              b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
                              % (width, height, cid)))
            kids.append(pid)
        objs.insert(0, (3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
        objs.insert(0, (2, b"<< /Type /Pages /Kids [%s] /Count %d >>"
                           % (b" ".join(b"%d 0 R" % k for k in kids), npages)))
        objs.insert(0, (1, b"<< /Type /Catalog /Pages 2 0 R >>"))
        objs.sort()
        out, offs = b"%PDF-1.4\n", {}
        for num, body in objs:
            offs[num] = len(out)
            out += b"%d 0 obj\n%s\nendobj\n" % (num, body)
        start, mx = len(out), max(offs) + 1
        out += b"xref\n0 %d\n0000000000 65535 f \n" % mx
        for i in range(1, mx):
            out += b"%010d 00000 n \n" % offs.get(i, 0)
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (mx, start)
        return out

    def test_oversized_page_is_rejected(self):
        """A 623-byte file declaring a 100in page rasterised to 2.1GB."""
        with self.assertRaises(UnreadablePDF):
            parse_pdf(io.BytesIO(self.build(1, 7200, 7200)))

    def test_extremely_wide_page_is_rejected(self):
        """Page width drove the gutter sweep, which pinned a core for hours."""
        with self.assertRaises(UnreadablePDF):
            parse_pdf(io.BytesIO(self.build(1, 20000, 792)))

    def test_page_count_is_capped(self):
        with self.assertRaises(UnreadablePDF):
            parse_pdf(io.BytesIO(self.build(300)))

    def test_a_normal_document_still_parses(self):
        doc = parse_pdf(io.BytesIO(self.build(2)))
        self.assertEqual(doc.n_pages, 2)

    def test_hostile_pdf_returns_400_not_500(self):
        app = ScoreApp()
        out, body = call(app, "POST", "/api/score", multipart(self.build(1, 7200, 7200)),
                         f"multipart/form-data; boundary={BOUNDARY}")
        self.assertEqual(out["status"], "400 Bad Request")
        self.assertIn("error", json.loads(body))

    def test_preview_page_count_is_bounded(self):
        rep = score_document(io.BytesIO(self.build(10)), include_preview=True,
                             display_name="many.pdf")
        preview = rep.to_dict()["preview"]
        self.assertEqual(preview["pages_total"], 10)
        self.assertLessEqual(preview["pages_rendered"], 3)


class TestDownloadableReport(unittest.TestCase):
    def setUp(self):
        with open(sample("strong_resume.pdf"), "rb") as fh:
            self.data = score_document(io.BytesIO(fh.read()),
                                       include_preview=True,
                                       display_name="strong_resume.pdf").to_dict()

    def test_report_is_self_contained(self):
        """A saved report opens from file://, where every fetch is blocked."""
        html = report_mod.render_html(self.data)
        self.assertNotIn('src="/', html)
        self.assertNotIn('href="/', html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("{{", html)

    def test_renderer_makes_no_network_calls(self):
        """app.js is inlined into every saved report, so it must stay offline."""
        with open(os.path.join(ROOT, "web", "app.js"), encoding="utf-8") as fh:
            js = fh.read()
        for forbidden in ("fetch(", "XMLHttpRequest", "import(", "navigator.sendBeacon"):
            self.assertNotIn(forbidden, js)

    def test_payload_cannot_break_out_of_the_script_tag(self):
        hostile = dict(self.data)
        hostile["filename"] = '"><img src=x onerror=alert(1)>.pdf'
        hostile["blockers"] = ["</script><!--<script> $& $` gotcha"]
        html = report_mod.render_html(hostile)
        self.assertNotIn("<img", html)
        self.assertNotIn("</script><!--", html)
        self.assertEqual(html.count("</script>"), 2)

    def test_payload_is_still_valid_json_after_escaping(self):
        html = report_mod.render_html(self.data)
        match = re.search(r"var __DATA__ = (.*?);\nwindow\.VMockReport", html, re.S)
        self.assertIsNotNone(match)
        self.assertAlmostEqual(json.loads(match.group(1))["overall"], self.data["overall"])

    def test_browser_and_server_escape_identically(self):
        """boot.js mirrors report.py; the two must not drift."""
        with open(os.path.join(ROOT, "web", "boot.js"), encoding="utf-8") as fh:
            js = fh.read()
        self.assertIn("jsonForScript", js)
        self.assertIn("report-template.html", js)
        self.assertEqual(report_mod.json_for_script("a</script>b"), "a\\u003c/script\\u003eb")


class TestPortBinding(unittest.TestCase):
    """Silently binding a different port is undiagnosable behind a health check
    that only ever probes $PORT."""

    def tearDown(self):
        os.environ.pop("PORT", None)

    def test_explicit_port_is_honoured(self):
        self.assertEqual(resolve_port(9123, "127.0.0.1"), 9123)

    def test_env_port_wins_when_none_given(self):
        os.environ["PORT"] = "8080"
        self.assertEqual(resolve_port(None, "127.0.0.1"), 8080)

    def test_explicit_port_beats_env(self):
        os.environ["PORT"] = "8080"
        self.assertEqual(resolve_port(9123, "127.0.0.1"), 9123)


if __name__ == "__main__":
    unittest.main()
