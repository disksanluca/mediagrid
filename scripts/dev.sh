#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT INT TERM
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port "${API_PORT:-8000}" &
npm run dev --workspace @mediagrid/web -- --hostname 127.0.0.1 --port "${WEB_PORT:-3000}" &
wait

