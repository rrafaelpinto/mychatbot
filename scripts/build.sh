#!/usr/bin/env bash
set -euo pipefail

uv sync --locked --no-dev
uv run python manage.py collectstatic --noinput
