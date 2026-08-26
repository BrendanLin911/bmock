#!/usr/bin/env bash
# Restart the local scorer. Run this from your own Terminal on the Mac:
#     cd ~/Desktop/VMOCK\ Clone && ./restart.sh
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8420}"

python3 - <<'PY' || { echo "Installing dependencies..."; python3 -m pip install --quiet pdfplumber PyYAML reportlab; }
import pdfplumber, yaml  # noqa
PY

if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti "tcp:${PORT}" 2>/dev/null || true)
  if [ -n "${PIDS}" ]; then
    echo "Stopping whatever is on port ${PORT} (${PIDS})"
    kill ${PIDS} 2>/dev/null || true
    sleep 1
  fi
fi

echo "Running tests..."
python3 -m unittest discover -s tests -q 2>&1 | tail -3

echo
echo "Starting on http://127.0.0.1:${PORT}  (Ctrl-C to stop)"
exec python3 run.py --port "${PORT}"
