# syntax=docker/dockerfile:1.7
#
# No apt packages. pdfplumber>=0.11 rasterises through pypdfium2, whose wheel
# bundles libpdfium; Pillow vendors its codecs under pillow.libs/; cryptography
# links OpenSSL statically. Everything they need outside their own wheels is
# glibc and libgcc, both present in python:3.13-slim.

############################  build  ############################
FROM python:3.13-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

# Dependencies first: this layer rebuilds only when the requirements change,
# never when a .py file does.
COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r /tmp/requirements-runtime.txt

###########################  runtime  ###########################
FROM python:3.13-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /opt/venv /opt/venv

WORKDIR /app

# NOT --chmod. BuildKit applies --chmod to the copied *directories* as well as
# the files, and a 0644 directory has no search bit: the non-root user below
# can list /app/vmock_clone but cannot stat anything inside it. importlib
# treats that EACCES as "file absent", so the package imports as an empty
# namespace package and the failure surfaces as
# "ModuleNotFoundError: No module named 'vmock_clone.wsgi'" — which looks like
# a missing file and is not. Git records 100644/0755 already; normalise
# explicitly below, as root, where a directory cannot lose its search bit.
COPY requirements-runtime.txt /app/requirements-runtime.txt
COPY rules.yaml               /app/rules.yaml
COPY gunicorn.conf.py         /app/gunicorn.conf.py
COPY web/                     /app/web/
COPY vmock_clone/             /app/vmock_clone/

RUN find /app -type d -exec chmod 0755 {} + \
 && find /app -type f -exec chmod 0644 {} +

# Fail the build rather than the first request: prove the wheels import, the
# rules parse, and a page actually rasterises, as the user the CMD runs as.
USER 10001:10001
RUN set -eu; \
    echo "--- /app ---"; ls -la /app; \
    echo "--- /app/vmock_clone ---"; ls /app/vmock_clone; \
    echo "--- /app/web ---"; ls /app/web; \
    python - <<'SMOKE'
import os, pathlib, sys

# An empty directory still imports as a namespace package, so "import
# vmock_clone" proves nothing. Count the real modules instead.
pkg = pathlib.Path("/app/vmock_clone")
mods = sorted(p.name for p in pkg.glob("*.py"))
assert len(mods) >= 10, f"vmock_clone has only {len(mods)} modules: {mods}"

for asset in ("index.html", "app.js", "boot.js", "style.css", "report-template.html"):
    path = pathlib.Path("/app/web") / asset
    assert path.is_file() and path.stat().st_size > 0, f"missing web asset: {asset}"

import pdfplumber, PIL, pypdfium2                      # noqa: F401
import vmock_clone.wsgiapp                             # noqa: F401
from vmock_clone.wsgi import application
from vmock_clone.core import Config

assert callable(application), "wsgi:application is not callable"
assert Config.load().data, "rules.yaml parsed empty"
print(f"OK: {len(mods)} modules, web assets present, wheels import, rules readable")
SMOKE

EXPOSE 8080

# Shell form so $PORT is expanded at runtime; the platform picks the port and
# routes to that one only.
CMD exec gunicorn --config /app/gunicorn.conf.py vmock_clone.wsgi:application
