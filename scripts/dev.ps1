<#
.SYNOPSIS
    Start, stop, restart, or inspect the local NEXA development stack.

.DESCRIPTION
    Manages four local processes:
      - LiveKit (Docker Compose)
      - FastAPI API (uvicorn)
      - Voice worker (livekit-agents)
      - Voice demo static server (http.server)

    Logs and PID files are written under .dev/ and are intentionally git-ignored.

.EXAMPLE
    .\scripts\dev.ps1 start

.EXAMPLE
    .\scripts\dev.ps1 status

.EXAMPLE
    .\scripts\dev.ps1 stop
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot "venv\Scripts\python.exe"
$ComposeFile = Join-Path $RepoRoot "voice\docker-compose.livekit.yml"
$DevDir = Join-Path $RepoRoot ".dev"
$PidDir = Join-Path $DevDir "pids"
$LogDir = Join-Path $DevDir "logs"

$ApiPort = 8000
$DemoPort = 5500
$LiveKitPort = 7880

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "  [ok]   $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [warn] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [fail] $Message" -ForegroundColor Red
}

function Invoke-NativeQuiet {
    param([scriptblock]$Command)

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command 2>&1 | Out-Null
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Ensure-Directories {
    foreach ($directory in @($DevDir, $PidDir, $LogDir)) {
        if (-not (Test-Path $directory)) {
            New-Item -ItemType Directory -Path $directory | Out-Null
        }
    }
}

function Test-Port {
    param(
        [int]$Port,
        [int]$TimeoutMs = 400
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-ForPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds,
        [string]$Name
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

function Get-ApiHealth {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 3
    }
    catch {
        return $null
    }
}

function Wait-ForApi {
    param([int]$TimeoutSeconds = 45)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $health = Get-ApiHealth
        if ($health -and $health.status -eq "ok") {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-PidFile {
    param([string]$Name)
    return (Join-Path $PidDir "$Name.pid")
}

function Read-Pid {
    param([string]$Name)

    $pidFile = Get-PidFile -Name $Name
    if (-not (Test-Path $pidFile)) {
        return $null
    }

    $raw = Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $raw) {
        return $null
    }

    try {
        return [int]$raw
    }
    catch {
        return $null
    }
}

function Find-ServiceProcess {
    param([string]$Pattern)

    return @(
        Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and $_.CommandLine -match $Pattern
            }
    )
}

function Get-PortOwner {
    param([int]$Port)

    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($connection) {
        return [int]$connection.OwningProcess
    }
    return $null
}

function Start-ManagedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$OutLog,
        [string]$ErrLog
    )

    $pidFile = Get-PidFile -Name $Name
    if (Test-Path $pidFile) {
        Remove-Item $pidFile -Force
    }

    $process = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -PassThru `
        -WindowStyle Hidden

    Set-Content -Path $pidFile -Value $process.Id -Encoding ASCII
    return $process
}

function Show-LogTail {
    param(
        [string]$Name,
        [int]$Lines = 30
    )

    foreach ($file in @(
        (Join-Path $LogDir "$Name.out.log"),
        (Join-Path $LogDir "$Name.err.log")
    )) {
        if (Test-Path $file) {
            $tail = Get-Content -Path $file -Tail $Lines -ErrorAction SilentlyContinue
            if ($tail) {
                Write-Host "--- $file ---" -ForegroundColor DarkGray
                $tail | ForEach-Object { Write-Host $_ }
            }
        }
    }
}

function Start-LiveKit {
    Write-Step "LiveKit"

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not found. Install Docker Desktop and ensure 'docker' is on PATH."
    }

    $dockerExit = Invoke-NativeQuiet { docker info }
    if ($dockerExit -ne 0) {
        throw "Docker Desktop is not running. Start Docker Desktop and retry."
    }

    if (-not (Test-Path $ComposeFile)) {
        throw "LiveKit compose file not found: $ComposeFile"
    }

    $container = & docker ps --filter "name=nexa-livekit" --format "{{.Names}}" 2>$null
    if ($container) {
        Write-Ok "LiveKit container is already running"
    }
    else {
        $composeExit = Invoke-NativeQuiet { docker compose -f $ComposeFile up -d }
        if ($composeExit -ne 0) {
            throw "Failed to start LiveKit. Run: docker compose -f $ComposeFile up -d"
        }
        Write-Ok "LiveKit container started"
    }

    if (-not (Wait-ForPort -Port $LiveKitPort -TimeoutSeconds 30 -Name "LiveKit")) {
        throw "LiveKit did not open port $LiveKitPort. Check: docker logs nexa-livekit"
    }

    Write-Ok "LiveKit is reachable at ws://127.0.0.1:$LiveKitPort"
}

function Start-Api {
    Write-Step "API"

    if (-not (Test-Path $Python)) {
        throw "Python virtual environment not found: $Python. Run: python -m venv venv"
    }

    if (Test-Port -Port $ApiPort) {
        $health = Get-ApiHealth
        if ($health -and $health.status -eq "ok") {
            Write-Ok "API is already healthy at http://127.0.0.1:$ApiPort"
            return
        }
        throw "Port $ApiPort is in use, but /health is not healthy. Stop the other process and retry."
    }

    $outLog = Join-Path $LogDir "api.out.log"
    $errLog = Join-Path $LogDir "api.err.log"
    $process = Start-ManagedProcess `
        -Name "api" `
        -FilePath $Python `
        -Arguments @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$ApiPort") `
        -OutLog $outLog `
        -ErrLog $errLog

    if (-not (Wait-ForApi -TimeoutSeconds 45)) {
        Show-LogTail -Name "api"
        throw "API failed to become healthy. See $outLog and $errLog"
    }

    Write-Ok "API started (PID $($process.Id)) at http://127.0.0.1:$ApiPort"
}

function Start-Worker {
    Write-Step "Voice worker"

    $existing = Find-ServiceProcess -Pattern "voice\.worker"
    if ($existing.Count -gt 0) {
        Write-Ok "Voice worker is already running (PID $($existing[0].ProcessId))"
        return
    }

    if (-not (Test-Port -Port $LiveKitPort)) {
        throw "LiveKit is not reachable on port $LiveKitPort. Start LiveKit first."
    }

    $outLog = Join-Path $LogDir "worker.out.log"
    $errLog = Join-Path $LogDir "worker.err.log"
    $process = Start-ManagedProcess `
        -Name "worker" `
        -FilePath $Python `
        -Arguments @("-u", "-m", "voice.worker", "dev") `
        -OutLog $outLog `
        -ErrLog $errLog

    Start-Sleep -Seconds 5

    if (-not (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
        Show-LogTail -Name "worker"
        throw "Voice worker exited during startup. See $outLog and $errLog"
    }

    $registered = $false
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if ((Select-String -Path $outLog -Pattern "registered worker|worker connected" -Quiet -ErrorAction SilentlyContinue)) {
            $registered = $true
            break
        }
        if (-not (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
            Show-LogTail -Name "worker"
            throw "Voice worker exited before registering with LiveKit. See $outLog and $errLog"
        }
        Start-Sleep -Milliseconds 500
    }

    if ($registered) {
        Write-Ok "Voice worker registered with LiveKit (PID $($process.Id))"
    }
    else {
        Write-Warn "Voice worker is running (PID $($process.Id)), but registration is not confirmed yet."
        Write-Warn "Check: $outLog"
    }
}

function Start-Demo {
    Write-Step "Voice demo"

    if (Test-Port -Port $DemoPort) {
        Write-Ok "Demo server is already running at http://127.0.0.1:$DemoPort"
        return
    }

    $outLog = Join-Path $LogDir "demo.out.log"
    $errLog = Join-Path $LogDir "demo.err.log"
    $process = Start-ManagedProcess `
        -Name "demo" `
        -FilePath $Python `
        -Arguments @("-m", "http.server", "$DemoPort", "--bind", "127.0.0.1") `
        -OutLog $outLog `
        -ErrLog $errLog

    if (-not (Wait-ForPort -Port $DemoPort -TimeoutSeconds 15 -Name "Demo")) {
        Show-LogTail -Name "demo"
        throw "Demo server failed to start. See $outLog and $errLog"
    }

    Write-Ok "Demo started (PID $($process.Id)) at http://127.0.0.1:$DemoPort/voice/demo.html"
}

function Stop-ManagedProcess {
    param(
        [string]$Name,
        [string]$Pattern
    )

    Write-Step "Stopping $Name"

    $processId = Read-Pid -Name $Name
    if (-not $processId) {
        $existing = Find-ServiceProcess -Pattern $Pattern
        if ($existing.Count -gt 0) {
            Write-Warn "$Name is running but was not started by this script (PID $($existing[0].ProcessId)); leaving it alone."
        }
        else {
            Write-Ok "$Name is not running"
        }
        return
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item (Get-PidFile -Name $Name) -Force -ErrorAction SilentlyContinue
        Write-Ok "$Name is already stopped"
        return
    }

    if ($process.CommandLine -notmatch $Pattern) {
        Write-Warn "PID $processId does not match $Name; leaving it alone. Remove the stale PID file manually if needed."
        return
    }

    $taskkillExit = Invoke-NativeQuiet { taskkill /PID $processId /T /F }
    if ($taskkillExit -eq 0) {
        Remove-Item (Get-PidFile -Name $Name) -Force -ErrorAction SilentlyContinue
        Write-Ok "$Name stopped"
    }
    else {
        Write-Warn "Could not stop $Name (PID $processId)."
    }
}

function Stop-LiveKit {
    Write-Step "Stopping LiveKit"

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warn "Docker CLI not found; skipping LiveKit."
        return
    }

    $dockerExit = Invoke-NativeQuiet { docker info }
    if ($dockerExit -ne 0) {
        Write-Warn "Docker Desktop is not running; LiveKit is already stopped."
        return
    }

    $container = & docker ps -a --filter "name=nexa-livekit" --format "{{.Names}}" 2>$null
    if (-not $container) {
        Write-Ok "LiveKit container is not present"
        return
    }

    $composeExit = Invoke-NativeQuiet { docker compose -f $ComposeFile stop }
    if ($composeExit -eq 0) {
        Write-Ok "LiveKit stopped"
    }
    else {
        Write-Warn "Could not stop LiveKit."
    }
}

function Show-Status {
    Write-Step "NEXA development stack"

    $rows = @()
    $dockerAvailable = $false
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        $dockerExit = Invoke-NativeQuiet { docker info }
        $dockerAvailable = ($dockerExit -eq 0)
    }

    $containerStatus = $null
    if ($dockerAvailable) {
        $containerStatus = & docker ps --filter "name=nexa-livekit" --format "{{.Status}}" 2>$null
    }

    if ($containerStatus) {
        $rows += [pscustomobject]@{
            Service = "LiveKit"
            State   = "running"
            Details = "$containerStatus; ws://127.0.0.1:$LiveKitPort"
        }
    }
    elseif (Test-Port -Port $LiveKitPort) {
        $rows += [pscustomobject]@{
            Service = "LiveKit"
            State   = "unknown"
            Details = "port $LiveKitPort is open, but container is not visible"
        }
    }
    else {
        $rows += [pscustomobject]@{
            Service = "LiveKit"
            State   = "stopped"
            Details = "run: .\scripts\dev.ps1 start"
        }
    }

    $health = Get-ApiHealth
    if ($health -and $health.status -eq "ok") {
        $owner = Get-PortOwner -Port $ApiPort
        $details = "http://127.0.0.1:$ApiPort"
        if ($owner) { $details += " (PID $owner)" }
        $rows += [pscustomobject]@{
            Service = "API"
            State   = "healthy"
            Details = $details
        }
    }
    elseif (Test-Port -Port $ApiPort) {
        $rows += [pscustomobject]@{
            Service = "API"
            State   = "degraded"
            Details = "port $ApiPort is open, but /health is not ok"
        }
    }
    else {
        $rows += [pscustomobject]@{
            Service = "API"
            State   = "stopped"
            Details = "http://127.0.0.1:$ApiPort"
        }
    }

    $workers = Find-ServiceProcess -Pattern "voice\.worker"
    if ($workers.Count -gt 0) {
        $rows += [pscustomobject]@{
            Service = "Voice worker"
            State   = "running"
            Details = "PID $($workers[0].ProcessId); log: $LogDir\worker.out.log"
        }
    }
    else {
        $rows += [pscustomobject]@{
            Service = "Voice worker"
            State   = "stopped"
            Details = "start only when testing voice"
        }
    }

    if (Test-Port -Port $DemoPort) {
        $owner = Get-PortOwner -Port $DemoPort
        $details = "http://127.0.0.1:$DemoPort/voice/demo.html"
        if ($owner) { $details += " (PID $owner)" }
        $rows += [pscustomobject]@{
            Service = "Voice demo"
            State   = "running"
            Details = $details
        }
    }
    else {
        $rows += [pscustomobject]@{
            Service = "Voice demo"
            State   = "stopped"
            Details = "http://127.0.0.1:$DemoPort/voice/demo.html"
        }
    }

    $rows | Format-Table -AutoSize

    Write-Host "Logs: $LogDir" -ForegroundColor DarkGray
    Write-Host "Docs: http://127.0.0.1:$ApiPort/docs" -ForegroundColor DarkGray
}

function Invoke-Start {
    Ensure-Directories
    Write-Host "Starting NEXA development stack..." -ForegroundColor White

    Start-LiveKit
    Start-Api
    Start-Worker
    Start-Demo

    Write-Host ""
    Show-Status
}

function Invoke-Stop {
    Ensure-Directories
    Write-Host "Stopping NEXA development stack..." -ForegroundColor White

    Stop-ManagedProcess -Name "worker" -Pattern "voice\.worker"
    Stop-ManagedProcess -Name "demo" -Pattern "http\.server\s+$DemoPort"
    Stop-ManagedProcess -Name "api" -Pattern "uvicorn\s+main:app"
    Stop-LiveKit

    Write-Host ""
    Show-Status
}

function Invoke-Restart {
    Invoke-Stop
    Start-Sleep -Seconds 2
    Invoke-Start
}

switch ($Action) {
    "start" { Invoke-Start }
    "stop" { Invoke-Stop }
    "restart" { Invoke-Restart }
    "status" { Show-Status }
}
