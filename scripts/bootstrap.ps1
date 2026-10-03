$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path data/assets,data/exports,data/renders,data/temp | Out-Null
uv sync --dev --frozen
npm ci
uv run python -m apps.api.migrate
Write-Host "MediaGrid is ready. Run ./scripts/dev.ps1"

