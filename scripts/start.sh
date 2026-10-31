#!/usr/bin/env bash
set -euo pipefail

exec uv run --no-sync gunicorn mychatbot.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --threads "${WEB_THREADS:-2}" \
  --access-logfile - \
  --error-logfile - \
  --timeout 75
