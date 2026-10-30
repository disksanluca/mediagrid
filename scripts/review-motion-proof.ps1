param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')]
    [string]$Run,
    [ValidateRange(1, 65535)] [int]$ApiPort = 8180,
    [ValidateRange(1, 65535)] [int]$WebPort = 3180
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$base = (Resolve-Path (Join-Path $root 'data/m4-complete-proof')).Path
$data = Join-Path $base $Run
if (-not (Test-Path (Join-Path $data 'workspace.db'))) {
    throw 'Prova isolada inexistente. Execute proof_motion_engine.py primeiro.'
}
if ((Get-Item -LiteralPath $data).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'A pasta da prova nao pode ser um link.'
}
if (-not (Resolve-Path -LiteralPath $data).Path.StartsWith(
    $base + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase)) {
    throw 'A prova precisa permanecer na pasta isolada.'
}
if ($ApiPort -eq $WebPort) { throw 'As portas devem ser diferentes.' }
foreach ($port in @($ApiPort, $WebPort)) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try { $listener.Start() } catch { throw "A porta $port ja esta em uso." } finally { $listener.Stop() }
}
$uv = (Get-Command uv -ErrorAction Stop).Source
$node = (Get-Command node -ErrorAction Stop).Source
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $data 'workspace.db').Replace('\', '/'))
$env:MEDIAGRID_DATA_DIR = $data
$env:MEDIAGRID_MODE = 'LOCAL'
$env:MEDIAGRID_PUBLIC_URL = ''
$env:MEDIAGRID_ADMIN_PASSWORD = ''
$env:MEDIAGRID_SESSION_SECRET = ''
$env:MEDIAGRID_API_PORT = [string]$ApiPort
$env:MEDIAGRID_LOCAL_WEB_PORT = [string]$WebPort
$env:NEXT_PUBLIC_API_URL = '/api/v1'
$env:MEDIAGRID_RENDERER_ROOT = Join-Path $root 'apps/renderer'
$env:MEDIAGRID_NODE_PATH = $node
$processes = @()

function Wait-Ready([string]$url) {
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        foreach ($process in $processes) {
            if ($process.HasExited) { throw "Processo encerrou. Consulte os logs em $data." }
        }
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Seconds 1 }
    }
    throw "Nao respondeu: $url"
}

try {
    Push-Location (Join-Path $root 'apps/web')
    try {
        & $node (Join-Path $root 'node_modules/next/dist/bin/next') build
        if ($LASTEXITCODE -ne 0) { throw 'Build web falhou.' }
    } finally { Pop-Location }
    $processes += Start-Process -FilePath $uv -ArgumentList @('run','uvicorn','apps.api.main:app','--host','127.0.0.1','--port',[string]$ApiPort) -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'review-api.out.log') -RedirectStandardError (Join-Path $data 'review-api.err.log')
    Wait-Ready "http://127.0.0.1:$ApiPort/api/v1/system/health"
    $processes += Start-Process -FilePath $uv -ArgumentList @('run','python','-m','workers.render.main') -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'review-worker.out.log') -RedirectStandardError (Join-Path $data 'review-worker.err.log')
    $processes += Start-Process -FilePath $node -ArgumentList @((Join-Path $root 'node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',[string]$WebPort) -WorkingDirectory (Join-Path $root 'apps/web') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'review-web.out.log') -RedirectStandardError (Join-Path $data 'review-web.err.log')
    Wait-Ready "http://127.0.0.1:$WebPort/api/v1/auth/session"
    Write-Host "Prova isolada: http://127.0.0.1:$WebPort"
    Write-Host 'Ctrl+C encerra API, worker e painel.'
    while ($true) { Start-Sleep -Seconds 2 }
} finally {
    foreach ($process in $processes) {
        if ($process -and -not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        }
    }
}
