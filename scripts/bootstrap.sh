#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/{assets,exports,renders,temp}
uv sync --dev --frozen
npm ci
uv run python -m apps.api.migrate
echo "MediaGrid is ready. Run ./scripts/dev.sh"

