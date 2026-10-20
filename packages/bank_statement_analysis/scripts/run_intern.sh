#!/usr/bin/env bash
# Bind the intern-testing webapp beyond loopback. Refuses to start without
# WEBAPP_AUTH_PASSWORD — same fail-closed rule as docker compose.
set -euo pipefail

if [[ -z "${WEBAPP_AUTH_PASSWORD:-}" ]]; then
  echo "Set WEBAPP_AUTH_PASSWORD before exposing the intern stack." >&2
  echo "Example: WEBAPP_AUTH_PASSWORD=... $0" >&2
  exit 2
fi

export WEBAPP_HOST="${WEBAPP_HOST:-0.0.0.0}"
export WEBAPP_PORT="${WEBAPP_PORT:-5000}"
export WEBAPP_AUTH_USER="${WEBAPP_AUTH_USER:-intern}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m webapp.app
fi
exec python3 -m webapp.app
