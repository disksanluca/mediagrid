$ErrorActionPreference = "Stop"
$installer = Get-ChildItem "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" | Select-Object -First 1
if (-not $installer) { throw "Instalador NSIS não encontrado." }
$installDir = Join-Path $env:RUNNER_TEMP "MediaGridSmokeInstall"
$env:LOCALAPPDATA = Join-Path $env:RUNNER_TEMP "MediaGridSmokeLocal"
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
$installerProcess = Start-Process $installer.FullName -ArgumentList @("/S", "/D=$installDir") -PassThru
if (-not $installerProcess.WaitForExit(120000)) {
  Stop-Process -Id $installerProcess.Id -Force
  throw "Instalador não concluiu em 120 segundos."
}
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

  $api = "http://127.0.0.1:$($runtime.api_port)/api/v1"
  $channelBody = @{name="Canal de teste";slug="smoke-windows";niche="Teste";default_engine="geo"} | ConvertTo-Json -Compress
  $channel = Invoke-RestMethod "$api/channels" -Method Post -ContentType "application/json" -Body $channelBody
  $projectBody = @{channel_id=$channel.id;title="Vídeo de teste";topic="Renderização local no Windows";format="vertical"} | ConvertTo-Json -Compress
  $project = Invoke-RestMethod "$api/projects" -Method Post -ContentType "application/json" -Body $projectBody
  $scenes = @(
    @{id="intro";duration_seconds=0.5;narration="A";visual_type="headline";visual_query="";on_screen_text="MediaGrid";transition="cut"},
    @{id="end";duration_seconds=0.5;narration="B";visual_type="outro";visual_query="";on_screen_text="Teste local";transition="cut"}
  )
  $planBody = @{hook="Teste local";angle="Validação do instalador";scenes=$scenes} | ConvertTo-Json -Depth 10 -Compress
  Invoke-RestMethod "$api/projects/$($project.id)/plan" -Method Put -ContentType "application/json" -Body $planBody | Out-Null

  $ffmpeg = Get-ChildItem $installDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
  $ffprobe = Get-ChildItem $installDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1
  if (-not $ffmpeg -or -not $ffprobe) { throw "FFmpeg portátil não encontrado na instalação." }
  $voiceDir = Join-Path $dataDir "voice"
  New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
  $voicePath = Join-Path $voiceDir "$($project.id).wav"
  & $ffmpeg.FullName -y -f lavfi -i "sine=frequency=440:duration=1" -ac 1 -ar 44100 $voicePath 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $voicePath)) { throw "FFmpeg portátil não gerou áudio de teste." }
  $hash = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes("A B"))
  $digest = [Convert]::ToHexString($hash).ToLowerInvariant()
  [System.IO.File]::WriteAllText((Join-Path $voiceDir "$($project.id).sha256"), $digest)

  $queued = Invoke-RestMethod "$api/projects/$($project.id)/render" -Method Post
  $rendered = $false
  for ($attempt = 0; $attempt -lt 300; $attempt++) {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod "$api/jobs/$($queued.job_id)"
    if ($job.status -eq "FAILED") { throw "Renderização instalada falhou: $($job.error)" }
    if ($job.status -eq "SUCCEEDED") { $rendered = $true; break }
  }
  if (-not $rendered) { throw "Renderização instalada não concluiu em 300 segundos." }
  $video = Join-Path $dataDir "renders\$($project.id).mp4"
  if (-not (Test-Path $video)) { throw "MP4 não foi criado pela instalação." }
  $streamTypes = @(& $ffprobe.FullName -v error -show_entries stream=codec_type -of csv=p=0 $video | ForEach-Object { $_.Trim() })
  if ($streamTypes -notcontains "video" -or $streamTypes -notcontains "audio") { throw "MP4 instalado está sem vídeo ou áudio." }
  Write-Host "Remotion e FFmpeg instalados geraram MP4 com vídeo e áudio."
} catch {
  Get-ChildItem (Join-Path $dataDir "Logs") -ErrorAction SilentlyContinue | ForEach-Object { Get-Content $_.FullName -Tail 40 }
  throw
} finally {
  if (-not $applicationProcess.HasExited) { Stop-Process -Id $applicationProcess.Id -Force }
  Get-CimInstance Win32_Process -Filter "Name = 'mediagrid-service.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
