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

# Explicit modes. The working tree has rules.yaml at 0600 and run.py at 0711;
# COPY preserves source modes, so without --chmod the non-root user cannot read
# the rules and every request 500s — after the container has already started
# and passed its health check, which makes it look like an app bug.
COPY --chmod=0644 requirements-runtime.txt /app/requirements-runtime.txt
COPY --chmod=0644 rules.yaml               /app/rules.yaml
COPY --chmod=0644 gunicorn.conf.py         /app/gunicorn.conf.py
COPY --chmod=0644 web/                     /app/web/
COPY --chmod=0644 vmock_clone/             /app/vmock_clone/

# Fail the build rather than the first request: prove the wheels import, the
# rules parse, and a page actually rasterises, as the user the CMD runs as.
USER 10001:10001
RUN python -c "\
import vmock_clone.wsgi as w, pdfplumber, PIL, pypdfium2;\
from vmock_clone.core import Config;\
assert callable(w.application);\
assert Config.load().data;\
print('wheels import, rules readable, app callable')"

EXPOSE 8080

# Shell form so $PORT is expanded at runtime; the platform picks the port and
# routes to that one only.
CMD exec gunicorn --config /app/gunicorn.conf.py vmock_clone.wsgi:application
