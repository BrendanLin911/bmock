# Hosting this

The service is stateless: a visitor uploads a PDF, it is scored in memory, and
the response is the only thing that survives. There is no database, no session,
no queue, and nothing written to disk. That is what makes it cheap to run and
simple to reason about.

Measured, warm, per scoring request: **~0.13s CPU, ~120–150MB peak RSS**, with a
~50–60MB resident baseline (most of it the 163k-word spell dictionary).

---

## Google Cloud Run

Scales to zero, so an idle service costs nothing, and at this workload a
low-traffic deployment sits inside the perpetual free allowance.

```bash
gcloud run deploy vmock-clone \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --cpu=1 --memory=1Gi \
  --concurrency=4 \
  --timeout=60s \
  --max-instances=10 --min-instances=0 \
  --cpu-boost
```

Why those numbers:

| Flag | Reason |
|---|---|
| `--concurrency=4` | Matches `threads = 4` in `gunicorn.conf.py`. Cloud Run's concurrency is the only real cap on in-flight work. |
| `--memory=1Gi` | 4 concurrent × ~90MB peak + baseline leaves 512Mi with no headroom, and an OOM kills the *instance*, taking every in-flight request with it. |
| `--timeout=60s` | Sits under gunicorn's 120s backstop, so the client gets a clean 504 rather than a killed worker. |
| `--max-instances=10` | Bounds the spend. ~77 req/s of capacity. |
| `--cpu-boost` | Cold start is dominated by image pull and interpreter start. |

Leave `--execution-environment` at the default: nothing here needs gen2, and
gen1 cold-starts faster. Do **not** set `--no-cpu-throttling` — the work is
request-scoped.

### Environment variables

| Variable | Effect |
|---|---|
| `PORT` | Injected by the platform. The server binds exactly this and never scans. |
| `VMOCK_ALLOWED_ORIGINS` | Comma-separated extra origins allowed to POST `/api/score`. Same-origin always works; set this only if the page is served from a different host than the API. |
| `VMOCK_MAX_UPLOAD` | Upload ceiling in bytes. Default 8MB. |
| `VMOCK_MAX_PREVIEW_PAGES` | How many pages get rasterised into the response. Default 3. |
| `VMOCK_BENCHMARK` | Cohort name to plot against. |
| `VMOCK_VERBOSE` | Turns on request logging and tracebacks. Visitor IPs are never logged either way. |

---

## Other hosts

Anything that can run a container or a Python process works. The WSGI target is
`vmock_clone.wsgi:application`:

```bash
gunicorn --config gunicorn.conf.py vmock_clone.wsgi:application
```

**Hugging Face Spaces (Docker SDK)** is the cheapest path with no credit card:
push this repo with the `Dockerfile`, and the free CPU tier runs it. It sleeps
when idle.

Avoid free tiers that spin down with a ~50s cold start — the first visitor
concludes the site is broken.

---

## Before you point real people at it

Verify the image ships no resumes. `.dockerignore` denies everything and
re-admits only `vmock_clone/`, `web/`, `rules.yaml` and
`requirements-runtime.txt`, but check rather than trust it:

```bash
docker run --rm IMAGE sh -c 'find / -name "*.pdf" -not -path "/proc/*" 2>/dev/null; ls /app'
```

Expect zero PDFs and exactly `rules.yaml  vmock_clone  web  gunicorn.conf.py`.

`samples/real/`, `out/`, `evidence/` and `benchmarks/` hold real people's
resumes and reports derived from them. They are gitignored and dockerignored;
keep it that way.

If you build a cohort benchmark, note that `benchmarks/*.json` is read straight
into the API response. Only whitelisted score fields are published
(`BENCHMARK_PUBLIC_KEYS` in `scoring.py`), and `benchmark.py` no longer records
the source folder or the names of resumes that failed to parse.

---

## What the service promises, and what it does not

**It does not store your resume.** The upload is parsed from an in-memory
stream — `score_document` takes a `BytesIO`, never a path — so there is no temp
file to leak on a redeploy, and no cleanup step that can fail. The response is
the only copy, and it goes to the uploader.

**What is outside this codebase's control:** your host's own access logs, and
whatever a reverse proxy in front of it retains. Cloud Run logs request
metadata (timestamp, status, latency, and the client IP) unless you configure
otherwise. That is worth saying out loud on the page if you make a privacy
claim in your own words.

**There is no authentication and no rate limiting in the app.** `--concurrency`
and `--max-instances` bound the damage, and `/api/score` refuses cross-origin
posts so a third-party page cannot launder load through visitors' browsers. If
the service gets abused, the cheapest next step is Cloud Armor or a proxy-level
`limit_req`, not application code — instances are ephemeral, so an in-process
per-IP counter resets on every cold start.

---

## Resource limits

A PDF's declared geometry is attacker-controlled and free to inflate, so both
are capped at ingest (`parser.py`):

| Limit | Value | What it stops |
|---|---|---|
| `MAX_PAGES` | 30 | A 48KB file declaring 300 pages, which produced a 6.7MB response. |
| `MAX_PAGE_PT` | 3400pt (~47in) | A 623-byte file declaring a 100in page, which rasterised to **2.1GB RSS**. |
| `MAX_RASTER_PX` | 4M px/page | Backstop: oversized pages render at reduced DPI rather than at full scale. |
| `MAX_PREVIEW_PAGES` | 3 | Bounds the response size and the memory spike. |
| `MAX_UPLOAD` | 8MB | Was 25MB, which admitted a ~400-page document. |

All five are exercised by `tests/test_server.py`.
