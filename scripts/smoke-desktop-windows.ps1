$ErrorActionPreference = "Stop"
$installer = Get-ChildItem "apps\desktop\src-tauri\target\release\bundle\nsis" -Filter "*.exe" | Select-Object -First 1
if (-not $installer) { throw "Instalador NSIS não encontrado." }
$installDir = Join-Path $env:RUNNER_TEMP "MediaGridSmokeInstall"
$env:LOCALAPPDATA = Join-Path $env:RUNNER_TEMP "MediaGridSmokeLocal"
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
Write-Host "Instalando $($installer.Name) em $installDir"
$installerProcess = Start-Process $installer.FullName -ArgumentList @("/S", "/D=$installDir") -PassThru -WindowStyle Hidden
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
$applicationProcess = Start-Process $application -PassThru -WindowStyle Hidden
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
  & $ffmpeg.FullName -hide_banner -loglevel error -y -f lavfi -i "color=c=green:s=320x180:d=2" -f lavfi -i "sine=frequency=440:duration=2" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest $sourceVideo
  if ($LASTEXITCODE -ne 0) { throw "FFmpeg portátil não gerou o clipe de teste." }
  $imageAsset = (& curl.exe -sS -f -F "file=@$sourceImage;type=image/png" -F "rights_status=OWNED" "$api/assets" | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0 -or -not $imageAsset.id) { throw "Upload da imagem na instalação falhou." }
  $videoAsset = (& curl.exe -sS -f -F "file=@$sourceVideo;type=video/mp4" -F "rights_status=OWNED" "$api/assets" | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0 -or -not $videoAsset.id) { throw "Upload do clipe na instalação falhou." }
  $scenes = @(
    @{id="intro";duration_seconds=0.5;narration="A";visual_type="image";visual_query="";on_screen_text="MediaGrid";transition="cut";asset_id=$imageAsset.id},
    @{id="end";duration_seconds=0.5;narration="B";visual_type="image";visual_query="";on_screen_text="Teste local";transition="cut";asset_id=$videoAsset.id;clip_start_seconds=0.5;clip_end_seconds=1.5}
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

  $motionProjectBody = @{channel_id=$channel.id;title="Cartão de motion";topic="Validação local do cartão";format="vertical"} | ConvertTo-Json -Compress
  $motionProject = Invoke-RestMethod "$api/projects" -Method Post -ContentType "application/json" -Body $motionProjectBody
  $motionScenes = @(
    @{id="intro";duration_seconds=3.5;narration="Cartão";visual_type="image";visual_query="";on_screen_text="Início";transition="cut";asset_id=$imageAsset.id},
    @{id="end";duration_seconds=3.5;narration="Fim";visual_type="image";visual_query="";on_screen_text="Final";transition="cut";asset_id=$imageAsset.id}
  )
  $motionPlanBody = @{hook="Cartão";angle="Prova instalada";scenes=$motionScenes} | ConvertTo-Json -Depth 10 -Compress
  Invoke-RestMethod "$api/projects/$($motionProject.id)/plan" -Method Put -ContentType "application/json" -Body $motionPlanBody | Out-Null
  $motionTimeline = Invoke-RestMethod "$api/projects/$($motionProject.id)/edl-v2"
  $motionFrames = @(
    @{at_ms=0;x=0.5;y=0.5;opacity=0;scale=0.85},
    @{at_ms=500;x=0.5;y=0.5;opacity=1;scale=1},
    @{at_ms=3000;x=0.5;y=0.5;opacity=1;scale=1}
  )
  $motionCard = @{id="smoke-motion-card";start_ms=0;duration_ms=3000;z_index=15;preset="motion_card_v1";params=@{label="MOTION";text="Cartão real";body="Prévia e MP4 da instalação.";color="#dcf769";layout="stack";keyframes=$motionFrames}}
  $flowFrames = @(
    @{at_ms=0;x=0.5;y=0.5;opacity=0;scale=0.85},
    @{at_ms=500;x=0.5;y=0.5;opacity=1;scale=1},
    @{at_ms=3000;x=0.5;y=0.5;opacity=1;scale=1}
  )
  $flow = @{id="smoke-flow";start_ms=3500;duration_ms=3000;z_index=16;preset="flow_path_v1";params=@{text="Ideia ao quadro";steps=@("Pesquisa","Roteiro","Vídeo");color="#dcf769";source_label=$null;keyframes=$flowFrames}}
  $motionTimeline.edl.tracks = @($motionTimeline.edl.tracks) + @(
    @{id="motion-cards";kind="caption";items=@($motionCard)},
    @{id="flow-diagrams";kind="caption";items=@($flow)}
  )
  $motionEDLBody = @{expected_revision=$motionTimeline.revision;expected_legacy_sha256=$motionTimeline.legacy_sha256;edl=$motionTimeline.edl} | ConvertTo-Json -Depth 20 -Compress
  Invoke-RestMethod "$api/projects/$($motionProject.id)/edl-v2" -Method Put -ContentType "application/json" -Body $motionEDLBody | Out-Null
  $motionPreview = Invoke-RestMethod "$api/projects/$($motionProject.id)/preview"
  if ($motionPreview.props.overlays[0].preset -ne "motion_card_v1") { throw "Cartão não chegou à prévia instalada." }
  if ($motionPreview.props.overlays[1].preset -ne "flow_path_v1") { throw "Diagrama não chegou à prévia instalada." }
  $motionVoicePath = Join-Path $voiceDir "$($motionProject.id).wav"
  & $ffmpeg.FullName -hide_banner -loglevel error -y -f lavfi -i "sine=frequency=550:duration=1" -ac 1 -ar 44100 $motionVoicePath
  if ($LASTEXITCODE -ne 0) { throw "Áudio sintético do cartão não foi criado." }
  $motionHash = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes("Cartão Fim"))
  [System.IO.File]::WriteAllText((Join-Path $voiceDir "$($motionProject.id).sha256"), [Convert]::ToHexString($motionHash).ToLowerInvariant())
  $motionJob = Invoke-RestMethod "$api/projects/$($motionProject.id)/render" -Method Post
  $motionDone = $false
  for ($attempt = 0; $attempt -lt 180; $attempt++) {
    Start-Sleep -Seconds 1
    $motionState = Invoke-RestMethod "$api/jobs/$($motionJob.job_id)"
    if ($motionState.status -eq "FAILED") { throw "Render do cartão instalado falhou: $($motionState.error)" }
    if ($motionState.status -eq "SUCCEEDED") { $motionDone = $true; break }
  }
  if (-not $motionDone) { throw "Render do cartão não concluiu em 180 segundos." }
  $motionVideo = Join-Path $dataDir "renders\$($motionProject.id).mp4"
  $motionStreams = @(& $ffprobe.FullName -v error -show_entries stream=codec_type -of csv=p=0 $motionVideo | ForEach-Object { $_.Trim() })
  if ($motionStreams -notcontains "video" -or $motionStreams -notcontains "audio") { throw "Cartão instalado sem vídeo ou áudio." }
  Write-Host "Instalação validou cartão e diagrama na prévia e em MP4 com áudio."

  $asrStatus = Invoke-RestMethod "$api/assets/asr-status"
  if (-not $asrStatus.word_asr_available) { throw "Modelo ASR offline não ficou disponível na instalação." }
  $transcriptBody = @{
    expected_revision = 0
    language = "pt"
    words = @(@{start_ms=100;end_ms=600;text="Teste"})
    cues = @(@{start_ms=100;end_ms=600;text="Teste"})
  } | ConvertTo-Json -Depth 8 -Compress
  $timed = Invoke-RestMethod "$api/assets/$($videoAsset.id)/transcript-v2" -Method Put -ContentType "application/json" -Body $transcriptBody
  $approvalBody = @{expected_revision=$timed.revision} | ConvertTo-Json -Compress
  $captions = Invoke-RestMethod "$api/assets/$($videoAsset.id)/captions/approve" -Method Post -ContentType "application/json" -Body $approvalBody
  $renderBody = @{expected_revision=$captions.revision} | ConvertTo-Json -Compress
  $captionJob = Invoke-RestMethod "$api/assets/$($videoAsset.id)/captions/render" -Method Post -ContentType "application/json" -Body $renderBody
  $captionDone = $false
  for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Seconds 1
    $captionState = Invoke-RestMethod "$api/jobs/$($captionJob.job_id)"
    if ($captionState.status -eq "FAILED") { throw "MP4 legendado falhou na instalação: $($captionState.error)" }
    if ($captionState.status -eq "SUCCEEDED") { $captionDone = $true; break }
  }
  if (-not $captionDone) { throw "MP4 legendado não concluiu em 120 segundos." }
  $captionedVideo = Join-Path $env:RUNNER_TEMP "mediagrid-captioned.mp4"
  Invoke-WebRequest "$api/assets/$($videoAsset.id)/captions/render/$($captionJob.job_id)" -OutFile $captionedVideo
  if (-not (Test-Path $captionedVideo)) { throw "MP4 legendado não foi baixado da instalação." }
  $captionedStreams = @(& $ffprobe.FullName -v error -show_entries stream=codec_type -of csv=p=0 $captionedVideo | ForEach-Object { $_.Trim() })
  if ($captionedStreams -notcontains "video" -or $captionedStreams -notcontains "audio") { throw "MP4 legendado sem vídeo ou áudio." }
  Write-Host "Instalação validou modelo ASR offline e MP4 legendado com revisão humana."

  $clipSource = Join-Path $env:RUNNER_TEMP "mediagrid-clip-source.mp4"
  & $ffmpeg.FullName -hide_banner -loglevel error -y -f lavfi -i "color=c=blue:s=1280x720:r=15:d=20" -f lavfi -i "sine=frequency=330:duration=20" -c:v libx264 -preset ultrafast -c:a aac -shortest $clipSource
  if ($LASTEXITCODE -ne 0) { throw "FFmpeg portátil não criou fonte longa para corte." }
  $clipAsset = (& curl.exe -sS -f -F "file=@$clipSource;type=video/mp4" -F "rights_status=OWNED" "$api/assets" | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0 -or -not $clipAsset.id) { throw "Upload da fonte de corte falhou." }
  $clipWords = @()
  for ($i = 0; $i -lt 20; $i++) {
    $wordText = if ($i -eq 9 -or $i -eq 19) { "frase." } else { "palavra" }
    $clipWords += @{start_ms=$i*1000;end_ms=$i*1000+900;text=$wordText}
  }
  $clipCues = @(
    @{start_ms=0;end_ms=9900;text="Primeira frase de teste."},
    @{start_ms=10000;end_ms=19900;text="Segunda frase de teste."}
  )
  $clipTranscriptBody = @{expected_revision=0;language="pt";words=$clipWords;cues=$clipCues} | ConvertTo-Json -Depth 10 -Compress
  $clipTranscript = Invoke-RestMethod "$api/assets/$($clipAsset.id)/transcript-v2" -Method Put -ContentType "application/json" -Body $clipTranscriptBody
  $clipApproveBody = @{expected_revision=$clipTranscript.revision} | ConvertTo-Json -Compress
  Invoke-RestMethod "$api/assets/$($clipAsset.id)/captions/approve" -Method Post -ContentType "application/json" -Body $clipApproveBody | Out-Null
  $analysisJob = Invoke-RestMethod "$api/assets/$($clipAsset.id)/clips/analyze" -Method Post
  $analysisDone = $false
  for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Seconds 1
    $analysisState = Invoke-RestMethod "$api/jobs/$($analysisJob.job_id)"
    if ($analysisState.status -eq "FAILED") { throw "Análise de cortes falhou: $($analysisState.error)" }
    if ($analysisState.status -eq "SUCCEEDED") { $analysisDone = $true; break }
  }
  if (-not $analysisDone) { throw "Análise de cortes não concluiu em 120 segundos." }
  $clipCandidates = @(Invoke-RestMethod "$api/assets/$($clipAsset.id)/clips")
  if ($clipCandidates.Count -lt 1) { throw "Nenhum candidato de corte foi persistido." }
  $candidate = $clipCandidates[0]
  $editBody = @{expected_revision=$candidate.revision;action="edit";aspect="vertical";focus_x=0.6} | ConvertTo-Json -Compress
  $candidate = Invoke-RestMethod "$api/assets/$($clipAsset.id)/clips/$($candidate.id)" -Method Patch -ContentType "application/json" -Body $editBody
  $selectBody = @{expected_revision=$candidate.revision;action="select"} | ConvertTo-Json -Compress
  $candidate = Invoke-RestMethod "$api/assets/$($clipAsset.id)/clips/$($candidate.id)" -Method Patch -ContentType "application/json" -Body $selectBody
  $clipRenderBody = @{expected_revision=$candidate.revision} | ConvertTo-Json -Compress
  $cutJob = Invoke-RestMethod "$api/assets/$($clipAsset.id)/clips/$($candidate.id)/render" -Method Post -ContentType "application/json" -Body $clipRenderBody
  $cutDone = $false
  for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Seconds 1
    $cutState = Invoke-RestMethod "$api/jobs/$($cutJob.job_id)"
    if ($cutState.status -eq "FAILED") { throw "Render do corte falhou: $($cutState.error)" }
    if ($cutState.status -eq "SUCCEEDED") { $cutDone = $true; break }
  }
  if (-not $cutDone) { throw "Render do corte não concluiu em 120 segundos." }
  $cutVideo = Join-Path $env:RUNNER_TEMP "mediagrid-cut.mp4"
  Invoke-WebRequest "$api/assets/$($clipAsset.id)/clips/$($candidate.id)/render/$($cutJob.job_id)" -OutFile $cutVideo
  $cutWidth = & $ffprobe.FullName -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 $cutVideo
  $cutHeight = & $ffprobe.FullName -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 $cutVideo
  if ($cutWidth.Trim() -ne "1080" -or $cutHeight.Trim() -ne "1920") { throw "Corte instalado não saiu em 1080x1920." }
  Write-Host "Instalação validou análise, seleção humana e render de corte vertical."

  $footballChannelBody = @{name="Football Smoke";slug="football-smoke";niche="Football";default_engine="football"} | ConvertTo-Json -Compress
  $footballChannel = Invoke-RestMethod "$api/channels" -Method Post -ContentType "application/json" -Body $footballChannelBody
  $footballProjectBody = @{channel_id=$footballChannel.id;title="Lances manuais";topic="Mídia sintética para teste";format="horizontal"} | ConvertTo-Json -Compress
  $footballProject = Invoke-RestMethod "$api/projects" -Method Post -ContentType "application/json" -Body $footballProjectBody
  $footballUrl = "$api/projects/$($footballProject.id)/football"
  $footballBody = @{expected_revision=0;aspect="horizontal";shots=@(
    @{asset_id=$clipAsset.id;in_ms=0;out_ms=1200;role="action";verified_event_id="smoke-event-1";focus_x=0.5;focus_y=0.5},
    @{asset_id=$clipAsset.id;in_ms=0;out_ms=1200;role="replay";verified_event_id="smoke-event-1";focus_x=0.5;focus_y=0.5}
  );score_label=$null;score_source_url=$null} | ConvertTo-Json -Depth 10 -Compress
  $footballSequence = Invoke-RestMethod $footballUrl -Method Put -ContentType "application/json" -Body $footballBody
  if ($footballSequence.status -ne "REVIEW_REQUIRED" -or $footballSequence.shots.Count -ne 2) { throw "Lances não persistidos para revisão." }
  $footballApproval = @{expected_revision=$footballSequence.revision;events_verified=$true;rights_confirmed=$true;score_verified=$false} | ConvertTo-Json -Compress
  Invoke-RestMethod "$footballUrl/approve" -Method Post -ContentType "application/json" -Body $footballApproval | Out-Null
  $footballJob = Invoke-RestMethod "$footballUrl/render" -Method Post
  $footballDone = $false
  for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Seconds 1
    $footballState = Invoke-RestMethod "$api/jobs/$($footballJob.job_id)"
    if ($footballState.status -eq "FAILED") { throw "Football Edit instalado falhou: $($footballState.error)" }
    if ($footballState.status -eq "SUCCEEDED") { $footballDone = $true; break }
  }
  if (-not $footballDone) { throw "Football Edit não concluiu em 120 segundos." }
  if ($footballState.result.replay_count -ne 1) { throw "Replay não foi registrado no MP4." }
  $footballVideo = Join-Path $env:RUNNER_TEMP "mediagrid-football.mp4"
  Invoke-WebRequest "$footballUrl/render/$($footballJob.job_id)" -OutFile $footballVideo
  $footballStreams = @(& $ffprobe.FullName -v error -show_entries stream=codec_type -of csv=p=0 $footballVideo | ForEach-Object { $_.Trim() })
  if ($footballStreams -notcontains "video" -or $footballStreams -notcontains "audio") { throw "Football Edit instalado sem vídeo ou áudio." }
  Write-Host "Instalação validou eventos manuais, revisão e Football Edit MP4 com replay."

  # Synthetic citation exercises the installed claim gate; it is not factual editorial evidence.
  $claimBody = @{scene_id="intro";text="Alegação sintética para verificar o gate do instalador.";source_url="https://example.com/";source_title="Fonte sintética de CI";published_at="2025-01-01";support_excerpt="Trecho fictício usado somente em um teste técnico local."} | ConvertTo-Json -Compress
  $claim = Invoke-RestMethod "$api/projects/$($project.id)/claims" -Method Post -ContentType "application/json" -Body $claimBody
  if ($claim.status -ne "REVIEW_REQUIRED") { throw "A alegação não aguardou revisão humana." }
  $claimApproval = @{expected_revision=$claim.revision;source_opened=$true;excerpt_matches=$true;context_checked=$true} | ConvertTo-Json -Compress
  $claim = Invoke-RestMethod "$api/projects/$($project.id)/claims/$($claim.id)/approve" -Method Post -ContentType "application/json" -Body $claimApproval
  if ($claim.status -ne "APPROVED") { throw "Alegação sintética não foi aprovada no CI." }

  # Synthetic CI review verifies the package flow; editorial approval remains a human action.
  $caption = "Legenda de teste para publicação manual."
  $reviewBody = @{
    source_urls = @("https://example.com/")
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
    $manifestReader = [System.IO.StreamReader]::new($zip.GetEntry("manifest.json").Open())
    try { $manifest = $manifestReader.ReadToEnd() | ConvertFrom-Json }
    finally { $manifestReader.Dispose() }
    if ($manifest.knowledge_claims[0].id -ne $claim.id -or -not $manifest.approved_review.claim_digest) { throw "Pacote sem alegação e hash da revisão." }
  } finally { $zip.Dispose() }
  Write-Host "Revisão sintética e exportação manual geraram vídeo, legenda e manifesto."
} catch {
  Get-ChildItem (Join-Path $dataDir "Logs") -ErrorAction SilentlyContinue | ForEach-Object { Get-Content $_.FullName -Tail 40 }
  throw
} finally {
  if (-not $applicationProcess.HasExited) { Stop-Process -Id $applicationProcess.Id -Force }
  Get-CimInstance Win32_Process -Filter "Name = 'mediagrid-service.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# Exercise the packaged backup sidecar only on this disposable CI installation.
$service = Join-Path $installDir "mediagrid-service.exe"
if (-not (Test-Path $service)) { throw "Serviço local empacotado não encontrado." }
$archive = Join-Path $env:RUNNER_TEMP "mediagrid-installed-backup.mgrid"
$env:MEDIAGRID_DATA_DIR = $dataDir
& $service backup --path $archive --include-assets --include-renders
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $archive)) { throw "Backup pela instalação falhou." }
$restoredData = Join-Path $env:RUNNER_TEMP "MediaGridSmokeRestored"
$env:MEDIAGRID_DATA_DIR = $restoredData
& $service restore --path $archive
if ($LASTEXITCODE -ne 0) { throw "Restauração pela instalação falhou." }
foreach ($restored in @("Database\mediagrid.db", "renders\$($project.id).mp4", "football-renders\$($footballSequence.id)-r$($footballSequence.revision).mp4", "assets\$($imageAsset.id)", "assets\$($videoAsset.id)")) {
  if (-not (Test-Path (Join-Path $restoredData $restored))) { throw "Restauração sem $restored." }
}
Write-Host "Backup e restauração do app instalado preservaram SQLite, MP4 e mídias importadas."
