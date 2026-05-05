#Requires -Version 5.1
<#
.SYNOPSIS
    Switch the machine to Dev Mode (Docker / WSL2 / Hyper-V available).

.DESCRIPTION
    Disables Riot Vanguard kernel driver (vgk) and service (vgc) so Hyper-V /
    WSL2 / Docker Desktop can use the hypervisor. A reboot is required for the
    change to take effect because vgk is a boot-time driver.

    After reboot:
      - Vanguard is INACTIVE (Valorant cannot launch)
      - Docker Desktop, WSL2 distros, Hyper-V VMs work normally
      - Run .\start.cmd to start the Da Nang system

.PARAMETER NoRestart
    Skip the auto-reboot prompt. You must reboot manually for the change to take effect.

.EXAMPLE
    .\scripts\dev-mode.ps1
    .\scripts\dev-mode.ps1 -NoRestart
#>
[CmdletBinding()]
param([switch]$NoRestart)

$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step  { param([string]$Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "    [OK]   $Msg" -ForegroundColor Green }
function Write-Info  { param([string]$Msg) Write-Host "    [INFO] $Msg" -ForegroundColor White }
function Write-Warn2 { param([string]$Msg) Write-Host "    [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err2  { param([string]$Msg) Write-Host "    [ERR]  $Msg" -ForegroundColor Red }

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Err2 'This script needs Administrator privileges (controls kernel services).'
    Write-Host '    Right-click Start > Terminal (Admin) and re-run.' -ForegroundColor Yellow
    exit 1
}

Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Cyan
Write-Host '|   Switching to DEV MODE (Vanguard OFF, Docker/WSL2 ON)     |' -ForegroundColor Cyan
Write-Host '+============================================================+' -ForegroundColor Cyan

# ============================================================
# STEP 1: Detect Vanguard
# ============================================================
Write-Step 'Checking Vanguard install status'

$vgServices = Get-Service vgc, vgk -ErrorAction SilentlyContinue
if (-not $vgServices) {
    Write-Ok 'Vanguard is NOT installed. You are already in Dev mode.'
    Write-Host ''
    Write-Info 'Next:'
    Write-Host '       cd D:\Development\projects\public-infra-system-for-Danangcity' -ForegroundColor DarkGray
    Write-Host '       .\start.cmd' -ForegroundColor DarkGray
    exit 0
}

Write-Ok ('Vanguard detected: ' + ($vgServices | ForEach-Object { "$($_.Name)=$($_.Status)/$($_.StartType)" }) -join ', ')

# ============================================================
# STEP 2: Stop services + disable boot driver
# ============================================================
Write-Step 'Stopping Vanguard service + disabling boot driver'

foreach ($svc in 'vgc', 'vgk') {
    & sc.exe stop $svc 2>&1 | Out-Null
    & sc.exe config $svc start= disabled 2>&1 | Out-Null
}

# Verify
$after = Get-Service vgc, vgk -ErrorAction SilentlyContinue
foreach ($s in $after) {
    Write-Ok "$($s.Name): Status=$($s.Status), StartType=$($s.StartType)"
}

# ============================================================
# STEP 3: Stop any running Vanguard processes
# ============================================================
Write-Step 'Killing any running Vanguard processes'
$vgProcs = Get-Process | Where-Object { $_.ProcessName -match '^(vgc|vgk|vgtray)$' }
if ($vgProcs) {
    $vgProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Ok ("Killed: $($vgProcs.ProcessName -join ', ')")
} else {
    Write-Ok 'No running Vanguard processes.'
}

# ============================================================
# STEP 4: Reboot prompt
# ============================================================
Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Yellow
Write-Host '|   IMPORTANT: REBOOT REQUIRED                               |' -ForegroundColor Yellow
Write-Host '+============================================================+' -ForegroundColor Yellow
Write-Host ''
Write-Host '  vgk.sys is a boot-time driver. It is already loaded in the' -ForegroundColor White
Write-Host '  current kernel. You must REBOOT for Vanguard to be truly off' -ForegroundColor White
Write-Host '  and for Docker/WSL2 hypervisor to work properly.' -ForegroundColor White
Write-Host ''
Write-Host '  After reboot:' -ForegroundColor Yellow
Write-Host '    cd D:\Development\projects\public-infra-system-for-Danangcity' -ForegroundColor White
Write-Host '    .\start.cmd' -ForegroundColor White
Write-Host ''

if ($NoRestart) {
    Write-Warn2 '-NoRestart flag set. Reboot manually before using Docker.'
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
