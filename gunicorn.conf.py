"""Gunicorn settings, sized from measurements rather than rules of thumb.

Warm, per scoring request: ~0.13s CPU, ~120-150MB peak RSS, ~50-60MB resident
baseline (the 163k-word spell dictionary is most of it).
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"

# gthread, not sync: sync gives one request per process, so every concurrent
# request would duplicate the ~50MB baseline. Threads share it. Not gevent —
# the work is CPU inside C extensions, which monkeypatching cannot yield around.
worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = int(os.environ.get("WEB_THREADS", "4"))

# Scoring is bounded now (page and page-size caps in the parser), so this is a
# backstop that should never fire, not a control. Keep it well above the worst
# real document; the platform's own request timeout is the user-visible one.
timeout = 120
graceful_timeout = 30
keepalive = 5

# Rasterisation accretes memory across many requests; recycle to stay flat.
max_requests = 400
max_requests_jitter = 50

# Import the app before forking so the wordlist and rules parse happen once.
preload_app = True

accesslog = "-" if os.environ.get("VMOCK_VERBOSE") else None
errorlog = "-"
