$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
foreach ($command in @("uv", "node", "npm", "ffmpeg", "ffprobe")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Comando '$command' não encontrado. Instale-o seguindo SETUP.md e tente novamente." }
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
New-Item -ItemType Directory -Force -Path data/assets,data/exports,data/renders,data/temp,data/voice,data/transcripts,data/backups | Out-Null
uv sync --dev --frozen
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências Python." }
npm ci
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências do painel." }
npm exec --workspace @mediagrid/renderer -- remotion browser ensure
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar o navegador local do renderer." }
uv run python -m apps.api.migrate
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar o banco local." }
Write-Host "MediaGrid pronto. Execute .\scripts\dev.ps1 e abra http://localhost:3000"
