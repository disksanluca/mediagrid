$ErrorActionPreference = "Stop"
$installer = Get-ChildItem "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" | Select-Object -First 1
if (-not $installer) { throw "Instalador NSIS não encontrado." }
$installDir = Join-Path $env:RUNNER_TEMP "MediaGridSmokeInstall"
$env:LOCALAPPDATA = Join-Path $env:RUNNER_TEMP "MediaGridSmokeLocal"
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
Write-Host "Instalando $($installer.Name) em $installDir"
$installerProcess = Start-Process $installer.FullName -ArgumentList @("/S", "/D=$installDir") -PassThru
if (-not $installerProcess.WaitForExit(120000)) {
  Stop-Process -Id $installerProcess.Id -Force
  throw "Instalador não concluiu em 120 segundos."
}
if ($installerProcess.ExitCode -ne 0) { throw "Instalador falhou: $($installerProcess.ExitCode)" }
Write-Host "Instalador concluiu com código 0."
$application = Join-Path $installDir "MediaGrid.exe"
if (-not (Test-Path $application)) { throw "MediaGrid.exe não foi encontrado após instalar." }
$dataDir = Join-Path $env:LOCALAPPDATA "MediaGrid\Data"
$runtimeFile = Join-Path $dataDir "runtime.json"
$applicationProcess = Start-Process $application -PassThru
Write-Host "Aguardando Core e worker locais."
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

  $ffmpeg = Get-ChildItem $installDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
  $ffprobe = Get-ChildItem $installDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1
  if (-not $ffmpeg -or -not $ffprobe) { throw "FFmpeg portátil não encontrado na instalação." }
  $sourceImage = Join-Path $env:RUNNER_TEMP "mediagrid-scene.png"
  $sourceVideo = Join-Path $env:RUNNER_TEMP "mediagrid-scene.mp4"
  & $ffmpeg.FullName -hide_banner -loglevel error -y -f lavfi -i "color=c=red:s=320x180:d=1" -frames:v 1 -update 1 $sourceImage
  if ($LASTEXITCODE -ne 0) { throw "FFmpeg portátil não gerou a imagem de teste." }
  & $ffmpeg.FullName -hide_banner -loglevel error -y -f lavfi -i "color=c=green:s=320x180:d=2" -c:v libx264 -pix_fmt yuv420p $sourceVideo
  if ($LASTEXITCODE -ne 0) { throw "FFmpeg portátil não gerou o clipe de teste." }
  $imageAsset = (& curl.exe -sS -f -F "file=@$sourceImage;type=image/png" -F "rights_status=OWNED" "$api/assets" | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0 -or -not $imageAsset.id) { throw "Upload da imagem na instalação falhou." }
  $videoAsset = (& curl.exe -sS -f -F "file=@$sourceVideo;type=video/mp4" -F "rights_status=OWNED" "$api/assets" | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0 -or -not $videoAsset.id) { throw "Upload do clipe na instalação falhou." }
  $scenes = @(
    @{id="intro";duration_seconds=0.5;narration="A";visual_type="image";visual_query="";on_screen_text="MediaGrid";transition="cut";asset_id=$imageAsset.id},
    @{id="end";duration_seconds=0.5;narration="B";visual_type="image";visual_query="";on_screen_text="Teste local";transition="cut";asset_id=$videoAsset.id}
  )
  $planBody = @{hook="Teste local";angle="Validação do instalador";scenes=$scenes} | ConvertTo-Json -Depth 10 -Compress
  Invoke-RestMethod "$api/projects/$($project.id)/plan" -Method Put -ContentType "application/json" -Body $planBody | Out-Null

  $voiceDir = Join-Path $dataDir "voice"
  New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
  $voicePath = Join-Path $voiceDir "$($project.id).wav"
  & $ffmpeg.FullName -y -f lavfi -i "sine=frequency=440:duration=1" -ac 1 -ar 44100 $voicePath 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $voicePath)) { throw "FFmpeg portátil não gerou áudio de teste." }
  $hash = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes("A B"))
  $digest = [Convert]::ToHexString($hash).ToLowerInvariant()
  [System.IO.File]::WriteAllText((Join-Path $voiceDir "$($project.id).sha256"), $digest)

  $queued = Invoke-RestMethod "$api/projects/$($project.id)/render" -Method Post
  Write-Host "Render enfileirado: $($queued.job_id)"
  $rendered = $false
  for ($attempt = 0; $attempt -lt 300; $attempt++) {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod "$api/jobs/$($queued.job_id)"
    if ($attempt % 30 -eq 0) { Write-Host "Render após ${attempt}s: $($job.status)" }
    if ($job.status -eq "FAILED") { throw "Renderização instalada falhou: $($job.error)" }
    if ($job.status -eq "SUCCEEDED") { $rendered = $true; break }
  }
  if (-not $rendered) { throw "Renderização instalada não concluiu em 300 segundos." }
  $video = Join-Path $dataDir "renders\$($project.id).mp4"
  if (-not (Test-Path $video)) { throw "MP4 não foi criado pela instalação." }
  $streamTypes = @(& $ffprobe.FullName -v error -show_entries stream=codec_type -of csv=p=0 $video | ForEach-Object { $_.Trim() })
  if ($streamTypes -notcontains "video" -or $streamTypes -notcontains "audio") { throw "MP4 instalado está sem vídeo ou áudio." }
  $firstPixel = Join-Path $env:RUNNER_TEMP "mediagrid-first.rgb"
  $secondPixel = Join-Path $env:RUNNER_TEMP "mediagrid-second.rgb"
  & $ffmpeg.FullName -hide_banner -loglevel error -y -ss 0.5 -i $video -frames:v 1 -vf "crop=2:2:900:1000" -pix_fmt rgb24 -f rawvideo $firstPixel
  if ($LASTEXITCODE -ne 0) { throw "Não foi possível ler pixels da primeira cena." }
  & $ffmpeg.FullName -hide_banner -loglevel error -y -ss 1.5 -i $video -frames:v 1 -vf "crop=2:2:900:1000" -pix_fmt rgb24 -f rawvideo $secondPixel
  if ($LASTEXITCODE -ne 0) { throw "Não foi possível ler pixels da segunda cena." }
  $red = [System.IO.File]::ReadAllBytes($firstPixel)
  $green = [System.IO.File]::ReadAllBytes($secondPixel)
  if ($red[0] -le 2 * $red[1] -or $green[1] -le 2 * $green[0]) {
    throw "A imagem ou o clipe importado não apareceu no MP4 final."
  }
  Write-Host "Remotion e FFmpeg instalados geraram MP4 com imagem, clipe e áudio."

  # Synthetic CI review verifies the package flow; editorial approval remains a human action.
  $caption = "Legenda de teste para publicação manual."
  $reviewBody = @{
    source_urls = @("https://www.camara.leg.br/")
    facts_confirmed = $true
    rights_confirmed = $true
    notes = "Revisão sintética do instalador no CI"
    caption = $caption
  } | ConvertTo-Json -Depth 5 -Compress
  $approved = Invoke-RestMethod "$api/projects/$($project.id)/review" -Method Post -ContentType "application/json" -Body $reviewBody
  if ($approved.status -ne "APPROVED") { throw "Revisão sintética não aprovou o projeto de teste." }
  $package = Join-Path $env:RUNNER_TEMP "mediagrid-export.zip"
  Invoke-WebRequest "$api/projects/$($project.id)/export" -OutFile $package
  $zip = [System.IO.Compression.ZipFile]::OpenRead($package)
  try {
    $entries = @($zip.Entries | ForEach-Object { $_.FullName })
    foreach ($required in @("video.mp4", "caption.txt", "manifest.json")) {
      if ($entries -notcontains $required) { throw "Pacote exportado sem $required." }
    }
    $reader = [System.IO.StreamReader]::new($zip.GetEntry("caption.txt").Open())
    try { if ($reader.ReadToEnd() -ne $caption) { throw "Legenda exportada está incorreta." } }
    finally { $reader.Dispose() }
  } finally { $zip.Dispose() }
  Write-Host "Revisão sintética e exportação manual geraram vídeo, legenda e manifesto."
} catch {
  Get-ChildItem (Join-Path $dataDir "Logs") -ErrorAction SilentlyContinue | ForEach-Object { Get-Content $_.FullName -Tail 40 }
  throw
} finally {
  if (-not $applicationProcess.HasExited) { Stop-Process -Id $applicationProcess.Id -Force }
  Get-CimInstance Win32_Process -Filter "Name = 'mediagrid-service.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
