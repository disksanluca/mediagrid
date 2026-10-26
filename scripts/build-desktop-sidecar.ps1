$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$motionData = @("--add-data", "contracts/motion/recipes:contracts/motion/recipes")
# Source bytes are deliberately bundled for the immutable plan's runtime hashes.
foreach ($folder in @("apps/api/creative", "apps/api/motion_contracts")) {
    Get-ChildItem -LiteralPath $folder -Filter "*.py" | ForEach-Object {
        $motionData += @("--add-data", "$($_.FullName):$folder")
    }
}
foreach ($source in @("creative_motion.py", "remotion_runtime.py")) {
    $motionData += @("--add-data", "workers/render/${source}:workers/render")
}
uv run --extra asr --with pyinstaller pyinstaller --noconfirm --clean --onefile --name mediagrid-service --paths . --collect-submodules apps --collect-submodules workers --collect-submodules alembic --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers --collect-all av --add-data "alembic.ini:." --add-data "migrations:migrations" --add-data "scripts/speak.ps1:scripts" --add-data "scripts/transcribe.ps1:scripts" --add-data "workers/render/blender_narrative.py:workers/render" @motionData scripts/desktop_service.py
if ($LASTEXITCODE -ne 0) { throw "Falha ao empacotar o serviço local." }

$targetDir = Join-Path $projectRoot "apps\desktop\src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item "dist\mediagrid-service.exe" (Join-Path $targetDir "mediagrid-service-x86_64-pc-windows-msvc.exe") -Force
Write-Host "Serviço local preparado para Tauri."
