#!/usr/bin/env bash
set -euo pipefail

uv sync --locked --no-dev
uv run --no-sync python manage.py collectstatic --noinput
