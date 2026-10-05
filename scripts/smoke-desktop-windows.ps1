$ErrorActionPreference = "Stop"
$installer = Get-ChildItem "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" | Select-Object -First 1
if (-not $installer) { throw "Instalador NSIS não encontrado." }
$installDir = Join-Path $env:RUNNER_TEMP "MediaGridSmokeInstall"
$env:LOCALAPPDATA = Join-Path $env:RUNNER_TEMP "MediaGridSmokeLocal"
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
$installerProcess = Start-Process $installer.FullName -ArgumentList @("/S", "/D=$installDir") -Wait -PassThru
if ($installerProcess.ExitCode -ne 0) { throw "Instalador falhou: $($installerProcess.ExitCode)" }
$application = Join-Path $installDir "MediaGrid.exe"
if (-not (Test-Path $application)) { throw "MediaGrid.exe não foi encontrado após instalar." }
$dataDir = Join-Path $env:LOCALAPPDATA "MediaGrid\Data"
$runtimeFile = Join-Path $dataDir "runtime.json"
$applicationProcess = Start-Process $application -PassThru
try {
  $ready = $false
  for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Seconds 1
    if ($applicationProcess.HasExited) { throw "MediaGrid.exe encerrou antes de iniciar os serviços." }
    if (-not (Test-Path $runtimeFile)) { continue }
    $runtime = Get-Content $runtimeFile -Raw | ConvertFrom-Json
    try {
      $health = Invoke-RestMethod "http://127.0.0.1:$($runtime.api_port)/api/v1/system/health" -TimeoutSec 2
      if ($health.status -ne "ok") { continue }
    } catch { continue }
    if (-not (Test-Path (Join-Path $dataDir "Database\mediagrid.db"))) { continue }
    $worker = Get-CimInstance Win32_Process -Filter "Name = 'mediagrid-service.exe'" | Where-Object { $_.CommandLine -match '\bworker\b' }
    if (-not $worker) { continue }
    $ready = $true
    Write-Host "Instalação limpa iniciou aplicativo, Core, SQLite e worker local na porta $($runtime.api_port)."
    break
  }
  if (-not $ready) {
    Get-ChildItem (Join-Path $dataDir "Logs") -ErrorAction SilentlyContinue | ForEach-Object { Get-Content $_.FullName -Tail 30 }
    throw "Aplicativo instalado não iniciou serviços locais em 120 segundos."
  }
} finally {
  if (-not $applicationProcess.HasExited) { Stop-Process -Id $applicationProcess.Id -Force }
  Get-CimInstance Win32_Process -Filter "Name = 'mediagrid-service.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
