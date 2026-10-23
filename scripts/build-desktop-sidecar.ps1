$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

uv run --extra asr --with pyinstaller pyinstaller --noconfirm --clean --onefile --name mediagrid-service --paths . --collect-submodules apps --collect-submodules workers --collect-submodules alembic --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers --collect-all av --add-data "alembic.ini:." --add-data "migrations:migrations" --add-data "scripts/speak.ps1:scripts" --add-data "scripts/transcribe.ps1:scripts" scripts/desktop_service.py
if ($LASTEXITCODE -ne 0) { throw "Falha ao empacotar o serviço local." }

$targetDir = Join-Path $projectRoot "apps\desktop\src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item "dist\mediagrid-service.exe" (Join-Path $targetDir "mediagrid-service-x86_64-pc-windows-msvc.exe") -Force
Write-Host "Serviço local preparado para Tauri."
