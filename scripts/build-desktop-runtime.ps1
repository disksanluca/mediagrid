$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
$runtime = Join-Path $projectRoot "apps\desktop\src-tauri\runtime"
$renderer = Join-Path $runtime "renderer"
if (Test-Path $runtime) { Remove-Item $runtime -Recurse -Force }
New-Item -ItemType Directory -Force -Path $renderer | Out-Null

$node = (Get-Command node.exe -ErrorAction Stop).Source
Copy-Item $node (Join-Path $runtime "node.exe")
Copy-Item "apps\desktop\runtime\renderer\package.json" $renderer
Copy-Item "apps\desktop\runtime\renderer\package-lock.json" $renderer
Copy-Item "apps\renderer\src" (Join-Path $renderer "src") -Recurse
npm ci --prefix $renderer --omit=dev --no-audit --no-fund --workspaces=false
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar Remotion no runtime portátil." }

Set-Location $renderer
$ffmpeg = & (Join-Path $runtime "node.exe") -e "console.log(require('@ffmpeg-installer/ffmpeg').path)"
$ffprobe = & (Join-Path $runtime "node.exe") -e "console.log(require('@ffprobe-installer/ffprobe').path)"
if (-not (Test-Path $ffmpeg) -or -not (Test-Path $ffprobe)) { throw "FFmpeg portátil não foi instalado." }
New-Item -ItemType Directory -Force -Path (Join-Path $runtime "bin") | Out-Null
Copy-Item $ffmpeg (Join-Path $runtime "bin\ffmpeg.exe")
Copy-Item $ffprobe (Join-Path $runtime "bin\ffprobe.exe")

& (Join-Path $runtime "node.exe") "node_modules\@remotion\cli\remotion-cli.js" browser ensure
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar o navegador local do renderer." }
$browser = Get-ChildItem (Join-Path $renderer "node_modules\.remotion") -Filter "chrome-headless-shell.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $browser) { throw "Navegador local do renderer não foi encontrado no pacote." }
$browserRelativePath = $browser.FullName.Substring($renderer.Length + 1)
Set-Content -Path (Join-Path $runtime "browser-path.txt") -Value $browserRelativePath -NoNewline
Write-Host "Runtime local pronto: Node, Remotion, FFmpeg, FFprobe e Chromium."
