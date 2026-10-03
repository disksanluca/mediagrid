#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/mediagrid-uv-cache}"
export npm_config_cache="${npm_config_cache:-${TMPDIR:-/tmp}/mediagrid-npm-cache}"
mkdir -p data/{assets,exports,renders,temp}
uv sync --dev --frozen
npm ci
uv run python -m apps.api.migrate
echo "MediaGrid is ready. Run ./scripts/dev.sh"
