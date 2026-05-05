#Requires -Version 5.1
<#
.SYNOPSIS
    Switch the machine to Game Mode (Vanguard ON, ready to play Valorant).

.DESCRIPTION
    Re-enables Riot Vanguard kernel driver (vgk) and service (vgc). Stops Docker
    Desktop to avoid hypervisor conflicts. A reboot is required because vgk is a
    boot-time driver and must initialize during system startup.

    After reboot:
      - Vanguard ACTIVE (Valorant can launch)
      - Docker Desktop will fail to start (hypervisor locked by Vanguard)
      - WSL2 distros may fail to launch

.PARAMETER NoRestart
    Skip the auto-reboot prompt.

.EXAMPLE
    .\scripts\game-mode.ps1
#>
[CmdletBinding()]
param([switch]$NoRestart)

$ErrorActionPreference = 'Continue'

function Write-Step  { param([string]$Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "    [OK]   $Msg" -ForegroundColor Green }
function Write-Info  { param([string]$Msg) Write-Host "    [INFO] $Msg" -ForegroundColor White }
function Write-Warn2 { param([string]$Msg) Write-Host "    [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err2  { param([string]$Msg) Write-Host "    [ERR]  $Msg" -ForegroundColor Red }

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Err2 'This script needs Administrator privileges.'
    exit 1
}

Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Magenta
Write-Host '|   Switching to GAME MODE (Vanguard ON, Docker disabled)    |' -ForegroundColor Magenta
Write-Host '+============================================================+' -ForegroundColor Magenta

# ============================================================
# STEP 1: Stop Docker Desktop gracefully
# ============================================================
Write-Step 'Stopping Docker Desktop'

$dockerProc = Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue
if ($dockerProc) {
    $dockerProc | Stop-Process -Force
    Write-Ok 'Docker Desktop stopped.'
} else {
    Write-Ok 'Docker Desktop not running.'
}

Stop-Service com.docker.service -Force -ErrorAction SilentlyContinue
Stop-Process -Name 'com.docker.backend', 'com.docker.proxy', 'vpnkit' -Force -ErrorAction SilentlyContinue 2>$null

# Stop project containers if any
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $RootDir 'infra\docker-compose.yml'
if (Test-Path $ComposeFile) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        & docker compose -f $ComposeFile -p danang-infra down 2>$null | Out-Null
    }
}

# ============================================================
# STEP 2: Enable + start Vanguard
# ============================================================
Write-Step 'Enabling Vanguard services'

$vgServices = Get-Service vgc, vgk -ErrorAction SilentlyContinue
if (-not $vgServices) {
    Write-Warn2 'Vanguard NOT installed on this machine.'
    Write-Host ''
    Write-Host '  To play Valorant, you need to:' -ForegroundColor Yellow
    Write-Host '    1) Open Valorant launcher (Riot Client)' -ForegroundColor White
    Write-Host '    2) The launcher will auto-download and install Vanguard (~50MB)' -ForegroundColor White
    Write-Host '    3) Reboot when prompted' -ForegroundColor White
    Write-Host '    4) Launch Valorant' -ForegroundColor White
    Write-Host ''
    Write-Host '  Opening Riot Client now...' -ForegroundColor Cyan

    $riotPaths = @(
        "$env:ProgramData\Riot Games\Riot Client\RiotClientServices.exe",
        "${env:ProgramFiles(x86)}\Riot Games\Riot Client\RiotClientServices.exe",
        "$env:ProgramFiles\Riot Games\Riot Client\RiotClientServices.exe"
    )
    $launcher = $riotPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($launcher) {
        Start-Process $launcher
        Write-Ok 'Riot Client launched. It will install Vanguard automatically.'
    } else {
        Write-Warn2 'Riot Client not found. Download Valorant from https://playvalorant.com/'
    }
    exit 0
}

# Enable services for next boot
& sc.exe config vgc start= auto    2>&1 | Out-Null
& sc.exe config vgk start= system  2>&1 | Out-Null
Write-Ok 'vgc: StartType=Automatic'
Write-Ok 'vgk: StartType=System  (boot-time driver)'

# Try start vgc now (won't fully work without reboot since vgk needs boot init)
& sc.exe start vgc 2>&1 | Out-Null

# ============================================================
# STEP 3: Reboot prompt
# ============================================================
Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Yellow
Write-Host '|   IMPORTANT: REBOOT REQUIRED                               |' -ForegroundColor Yellow
Write-Host '+============================================================+' -ForegroundColor Yellow
Write-Host ''
Write-Host '  vgk.sys must be loaded at boot. Vanguard will not be fully' -ForegroundColor White
Write-Host '  initialized until you reboot.' -ForegroundColor White
Write-Host ''
Write-Host '  After reboot:' -ForegroundColor Yellow
Write-Host '    Open Valorant via Riot Client. It will work normally.' -ForegroundColor White
Write-Host ''
Write-Host '  When you want to dev again:' -ForegroundColor Yellow
Write-Host '    .\scripts\dev-mode.ps1' -ForegroundColor White
Write-Host ''

if ($NoRestart) {
    Write-Warn2 '-NoRestart flag set. Reboot manually before launching Valorant.'
    exit 0
}

$reply = Read-Host '  Reboot now? (Y/n)'
if ($reply -eq '' -or $reply -match '^[yY]') {
    Write-Host ''
    Write-Host '  Restarting in 10 seconds. Save your work...' -ForegroundColor Red
    Start-Sleep -Seconds 10
    Restart-Computer -Force
} else {
    Write-Warn2 'Reboot skipped. Run "Restart-Computer" when ready.'
}
