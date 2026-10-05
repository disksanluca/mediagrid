#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/mediagrid-uv-cache}"
export npm_config_cache="${npm_config_cache:-${TMPDIR:-/tmp}/mediagrid-npm-cache}"
pids=()
stop() {
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap stop EXIT INT TERM
setsid uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port "${API_PORT:-8000}" &
pids+=("$!")
setsid npm run dev --workspace @mediagrid/web -- --hostname 127.0.0.1 --port "${WEB_PORT:-3000}" &
pids+=("$!")
setsid uv run python -m workers.render.main &
pids+=("$!")
wait
