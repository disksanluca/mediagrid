param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')]
    [string]$WorkspaceName = 'review',
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 8180,
    [ValidateRange(1, 65535)]
    [int]$WebPort = 3180
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$web = Join-Path $root 'apps/web'
$base = Join-Path $root 'data/mobile-companion'
$data = Join-Path $base $WorkspaceName
$processes = @()
$serveStarted = $false

function Assert-PortFree([int]$port) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try { $listener.Start() } catch { throw "A porta $port ja esta em uso." } finally { $listener.Stop() }
}

function Wait-Ready([string]$url, [int]$seconds) {
    for ($attempt = 0; $attempt -lt $seconds; $attempt++) {
        foreach ($process in $processes) {
            if ($process.HasExited) { throw "Um processo encerrou antes de responder. Consulte $data/logs." }
        }
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return $response }
        } catch { Start-Sleep -Seconds 1 }
    }
    throw "O servico nao respondeu: $url. Consulte $data/logs."
}

try {
    $storageRoot = Join-Path $root 'data'
    if (-not (Test-Path -LiteralPath $storageRoot)) {
        New-Item -ItemType Directory -Path $storageRoot | Out-Null
    }
    if ((Get-Item -LiteralPath $storageRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'A pasta de dados do repositorio nao pode ser um link.'
    }
    if (Test-Path -LiteralPath $base) {
        $baseItem = Get-Item -LiteralPath $base
    } else {
        $baseItem = New-Item -ItemType Directory -Path $base
    }
    if ($baseItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'A pasta de workspaces nao pode ser um link.'
    }
    if (Test-Path -LiteralPath $data) {
        if ((Get-Item -LiteralPath $data).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'O workspace nao pode ser um link.'
        }
        if (-not (Resolve-Path -LiteralPath $data).Path.StartsWith(
            (Resolve-Path -LiteralPath $base).Path + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
            throw 'O workspace precisa permanecer na pasta isolada.'
        }
    }
    if ($ApiPort -eq $WebPort) { throw 'As portas da API e da web devem ser diferentes.' }
    Assert-PortFree $ApiPort
    Assert-PortFree $WebPort
    $uv = (Get-Command uv -ErrorAction Stop).Source
    $node = (Get-Command node -ErrorAction Stop).Source
    $tailscale = (Get-Command tailscale -ErrorAction Stop).Source
    if (-not (Test-Path (Join-Path $root 'node_modules/next/dist/bin/next'))) {
        throw 'Dependencias web ausentes. Instale as dependencias do repositorio primeiro.'
    }
    $state = & $tailscale status --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $state.BackendState -ne 'Running' -or -not $state.Self.Online -or -not $state.Self.DNSName) {
        throw 'Conecte este PC ao Tailscale antes de iniciar o acesso privado.'
    }
    if (-not $state.Self.DNSName.TrimEnd('.').EndsWith('.ts.net')) {
        throw 'O endereco DNS do Tailscale nao e valido para o modo privado.'
    }
    $currentServe = (& $tailscale serve status --json 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or ($currentServe -and $currentServe -notin @('{}', 'null'))) {
        throw 'Tailscale Serve ja possui configuracao. Esta rotina nao altera servicos existentes.'
    }
    $origin = 'https://' + $state.Self.DNSName.TrimEnd('.')
    if ($env:MEDIAGRID_COMPANION_PASSWORD) {
        $password = $env:MEDIAGRID_COMPANION_PASSWORD
        Remove-Item Env:MEDIAGRID_COMPANION_PASSWORD
    } else {
        $secure = Read-Host 'Escolha a senha do estudio privado' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
    if ($password.Length -lt 16) { throw 'Use uma senha com pelo menos 16 caracteres.' }
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $bytes = New-Object byte[] 48
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $env:MEDIAGRID_MODE = 'LOCAL'
    $env:MEDIAGRID_ADMIN_PASSWORD = $password
    $env:MEDIAGRID_SESSION_SECRET = [Convert]::ToBase64String($bytes)
    $env:MEDIAGRID_PUBLIC_URL = $origin
    $env:ALLOW_PAID_AI = 'false'
    $env:DRY_RUN = 'true'
    $env:MEDIAGRID_DATA_DIR = $data
    $env:DATABASE_URL = 'sqlite:///' + ((Join-Path $data 'workspace.db').Replace('\', '/'))
    $env:MEDIAGRID_RENDERER_ROOT = Join-Path $root 'apps/renderer'
    $env:MEDIAGRID_NODE_PATH = $node
    $env:MEDIAGRID_API_PORT = [string]$ApiPort
    $env:MEDIAGRID_LOCAL_WEB_PORT = [string]$WebPort
    $env:NEXT_PUBLIC_API_URL = '/api/v1'
    New-Item -ItemType Directory -Force -Path (Join-Path $data 'logs') | Out-Null

    Push-Location $web
    try {
        & $node (Join-Path $root 'node_modules/next/dist/bin/next') build
        if ($LASTEXITCODE -ne 0) { throw 'Build web falhou.' }
    } finally { Pop-Location }

    $processes += Start-Process -FilePath $uv -ArgumentList @('run','uvicorn','apps.api.main:app','--host','127.0.0.1','--port',[string]$ApiPort) -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'logs/api.out.log') -RedirectStandardError (Join-Path $data 'logs/api.err.log')
    Wait-Ready "http://127.0.0.1:$ApiPort/api/v1/system/health" 60 | Out-Null
    $processes += Start-Process -FilePath $uv -ArgumentList @('run','python','-m','workers.render.main') -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'logs/worker.out.log') -RedirectStandardError (Join-Path $data 'logs/worker.err.log')
    $processes += Start-Process -FilePath $node -ArgumentList @((Join-Path $root 'node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',[string]$WebPort) -WorkingDirectory $web -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'logs/web.out.log') -RedirectStandardError (Join-Path $data 'logs/web.err.log')
    Wait-Ready "http://127.0.0.1:$WebPort/api/v1/auth/session" 60 | Out-Null

    & $tailscale serve --bg --https=443 "http://127.0.0.1:$WebPort"
    if ($LASTEXITCODE -ne 0) { throw 'Tailscale Serve nao iniciou.' }
    $serveStarted = $true
    $remote = Wait-Ready "$origin/api/v1/auth/session" 30
    if (-not ($remote.Content | ConvertFrom-Json).login_required) {
        throw 'A interface remota respondeu sem exigir login.'
    }
    Write-Host "Estudio privado: $origin"
    Write-Host "Dados isolados: $data"
    Write-Host 'Mantenha esta janela aberta. Ctrl+C encerra o acesso privado.'
    while ($true) {
        $currentTailnet = & $tailscale status --json | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or $currentTailnet.BackendState -ne 'Running' -or
            -not $currentTailnet.Self.DNSName -or
            $currentTailnet.Self.DNSName.TrimEnd('.') -ne $state.Self.DNSName.TrimEnd('.')) {
            throw 'A rede Tailscale mudou; acesso privado encerrado. Inicie novamente no perfil desejado.'
        }
        foreach ($process in $processes) {
            if ($process.HasExited) { throw "Um processo encerrou. Consulte $data/logs." }
        }
        Start-Sleep -Seconds 2
    }
} finally {
    if ($serveStarted) { & $tailscale serve --https=443 off | Out-Null }
    foreach ($process in $processes) {
        if ($process -and -not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        }
    }
    Remove-Item Env:MEDIAGRID_ADMIN_PASSWORD,Env:MEDIAGRID_SESSION_SECRET -ErrorAction SilentlyContinue
}
