#!/usr/bin/env bash
set -euo pipefail
cd /app
python -m apps.api.migrate
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
npm run start --workspace @mediagrid/web -- --hostname 0.0.0.0 --port 3000 &
web_pid=$!
python -m workers.render.main &
worker_pid=$!
stop() {
  kill "$api_pid" "$web_pid" "$worker_pid" 2>/dev/null || true
  wait "$api_pid" "$web_pid" "$worker_pid" 2>/dev/null || true
}
trap stop EXIT TERM INT
wait -n "$api_pid" "$web_pid" "$worker_pid"
