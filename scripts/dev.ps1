$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
Start-Process uv -ArgumentList "run","uvicorn","apps.api.main:app","--reload","--host","127.0.0.1","--port","8000" -NoNewWindow
npm run dev --workspace @mediagrid/web -- --hostname 127.0.0.1 --port 3000
