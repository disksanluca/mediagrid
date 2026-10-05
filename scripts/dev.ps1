$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
if (-not (Test-Path ".env")) { throw "Execute .\scripts\bootstrap.ps1 antes de iniciar." }
foreach ($command in @("uv", "npm")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Comando '$command' não encontrado. Veja SETUP.md." }
}
$processes = @()
try {
    $processes += Start-Process -FilePath "uv" -ArgumentList @("run", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $projectRoot -PassThru -NoNewWindow
    $processes += Start-Process -FilePath "uv" -ArgumentList @("run", "python", "-m", "workers.render.main") -WorkingDirectory $projectRoot -PassThru -NoNewWindow
    $processes += Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm run dev --workspace @mediagrid/web -- --hostname 127.0.0.1 --port 3000") -WorkingDirectory $projectRoot -PassThru -NoNewWindow
    Write-Host "MediaGrid local: http://localhost:3000"
    Write-Host "API local: http://localhost:8000/docs"
    Write-Host "Mantenha esta janela aberta. Pressione Ctrl+C para encerrar."
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        foreach ($process in $processes) {
            if ($process.HasExited) { throw "Um componente do MediaGrid encerrou. Verifique as mensagens acima." }
        }
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw "O painel não respondeu em http://localhost:3000" }
    try { Start-Process "http://localhost:3000" } catch { Write-Host "Abra http://localhost:3000 no navegador." }
    while ($true) {
        foreach ($process in $processes) {
            if ($process.HasExited) { throw "Um componente do MediaGrid encerrou. Verifique as mensagens acima." }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    foreach ($process in $processes) {
        if (-not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
}
