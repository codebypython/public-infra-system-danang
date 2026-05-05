#Requires -Version 5.1
<#
.SYNOPSIS
    Show current machine state: Vanguard ON/OFF, Docker, WSL2, project containers.
    Read-only — does not modify anything.

.EXAMPLE
    .\scripts\mode-status.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

function Show-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host "--- $Title ---" -ForegroundColor Cyan
}

function Show-OK   { param([string]$Msg) Write-Host "  [ON]  $Msg" -ForegroundColor Green }
function Show-Off  { param([string]$Msg) Write-Host "  [OFF] $Msg" -ForegroundColor DarkGray }
function Show-Warn { param([string]$Msg) Write-Host "  [WARN] $Msg" -ForegroundColor Yellow }
function Show-Err  { param([string]$Msg) Write-Host "  [ERR] $Msg" -ForegroundColor Red }

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Magenta
Write-Host '|   Da Nang Infra - Machine Mode Status                      |' -ForegroundColor Magenta
Write-Host '+============================================================+' -ForegroundColor Magenta

# ============================================================
# OS info
# ============================================================
Show-Section 'OS / Build'
$os = Get-ComputerInfo
$majorMarker = if ([int]$os.OsBuildNumber -ge 22000) { 'Windows 11' } else { 'Windows 10' }
$edition = $os.WindowsProductName -replace '^Windows 10', $majorMarker
Write-Host "  Edition : $edition"
Write-Host "  Version : $($os.WindowsVersion)"
Write-Host "  Build   : $($os.OsBuildNumber).$($os.OsHardwareAbstractionLayer.Split('.')[-1])"
if (-not $isAdmin) {
    Write-Host '  Admin   : NO (re-run "as Administrator" for full info)' -ForegroundColor Yellow
} else {
    Write-Host '  Admin   : YES' -ForegroundColor DarkGray
}

# Check Insider channel — try both UI selection and Applicability paths
$ip = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsSelfHost\UI\Selection' -ErrorAction SilentlyContinue
$ip2 = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsSelfHost\Applicability' -ErrorAction SilentlyContinue
$branch = $null
if ($ip -and $ip.UIBranch)   { $branch = $ip.UIBranch }
elseif ($ip2 -and $ip2.BranchName) { $branch = $ip2.BranchName }
if ($branch) {
    Write-Host "  Insider : $branch" -ForegroundColor Yellow
} else {
    Write-Host '  Insider : not enrolled' -ForegroundColor DarkGray
}

# ============================================================
# Vanguard
# ============================================================
Show-Section 'Vanguard (Riot anti-cheat)'
$vg = Get-Service vgc, vgk -ErrorAction SilentlyContinue
if (-not $vg) {
    Show-Off 'Not installed.  -> Currently in DEV MODE (Docker friendly)'
} else {
    $statusList = ($vg | ForEach-Object { "$($_.Name)=$($_.Status)/$($_.StartType)" }) -join ', '
    $running = $vg | Where-Object Status -eq 'Running'
    if ($running) {
        Show-OK "Running. Currently in GAME MODE (Docker will fail). Status: $statusList"
    } else {
        $startTypes = $vg | ForEach-Object { $_.StartType.ToString() }
        if ($startTypes -contains 'Disabled') {
            Show-Off "Installed but DISABLED. Currently in DEV MODE. Status: $statusList"
        } else {
            Show-Warn 'Installed, services stopped but auto-start enabled. After next reboot, will be Game mode.'
            $vg | ForEach-Object { Write-Host "       $($_.Name): Status=$($_.Status), StartType=$($_.StartType)" }
        }
    }
}

# Check vgk driver loaded in kernel right now
$vgkLoaded = & driverquery /fo csv 2>$null | Select-String -Pattern '^\"vgk\"'
if ($vgkLoaded) {
    Show-Warn 'vgk.sys is currently LOADED in kernel (will affect hypervisor until next reboot)'
}

# ============================================================
# Windows Optional Features
# ============================================================
Show-Section 'Windows Features (need for Docker)'
if (-not $isAdmin) {
    Write-Host '  (Admin required to query features. Re-run as Administrator.)' -ForegroundColor Yellow
} else {
    foreach ($name in 'VirtualMachinePlatform', 'Microsoft-Windows-Subsystem-Linux', 'HypervisorPlatform') {
        try {
            $f = Get-WindowsOptionalFeature -Online -FeatureName $name -ErrorAction Stop
            $statusColor = if ($f.State -eq 'Enabled') { 'Green' } else { 'Red' }
            Write-Host ("  {0,-40} {1}" -f $f.FeatureName, $f.State) -ForegroundColor $statusColor
        } catch {
            Write-Host ("  {0,-40} {1}" -f $name, 'query failed') -ForegroundColor DarkGray
        }
    }
}

# ============================================================
# WSL
# ============================================================
Show-Section 'WSL2'
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    # WSL outputs UTF-16; coerce to ASCII to avoid mangled glyphs
    $prevOutput = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::Unicode
        $wslStatus = (& wsl --status 2>&1) -replace "`0", ''
        if ($LASTEXITCODE -eq 0) {
            $wslStatus | Where-Object { $_.Trim() } | Select-Object -First 6 | ForEach-Object {
                Write-Host "  $($_.Trim())"
            }
        } else {
            Show-Off 'WSL2 not initialized — VMP feature likely disabled'
            $wslStatus | Where-Object { $_.Trim() -match 'virtualization|VirtualMachine|Platform|enabled' } |
                Select-Object -First 2 | ForEach-Object { Write-Host "    $($_.Trim())" -ForegroundColor DarkGray }
        }
    } finally {
        [Console]::OutputEncoding = $prevOutput
    }
} else {
    Show-Off 'wsl command not found (WSL not installed)'
}

# ============================================================
# Docker
# ============================================================
Show-Section 'Docker'
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dv = & docker --version 2>&1
    Write-Host "  $dv"
    & docker info >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Show-OK 'Docker daemon RUNNING'
        $containers = & docker compose -f (Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) 'infra\docker-compose.yml') -p danang-infra ps --format "table {{.Name}}\t{{.Status}}" 2>$null
        if ($containers -and $LASTEXITCODE -eq 0) {
            $lines = $containers -split "`n" | Where-Object { $_ -and $_ -notmatch '^NAME' }
            if ($lines) {
                Write-Host ''
                Write-Host '  Project containers:' -ForegroundColor Yellow
                foreach ($line in $lines) {
                    if ($line.Trim()) {
                        $color = if ($line -match 'Up|healthy') { 'Green' } elseif ($line -match 'Exited \(0\)') { 'DarkGray' } else { 'Red' }
                        Write-Host "    $line" -ForegroundColor $color
                    }
                }
            } else {
                Write-Host '  Project containers: not running (run .\start.cmd)' -ForegroundColor DarkGray
            }
        }
    } else {
        Show-Off 'Docker daemon NOT RUNNING (start Docker Desktop)'
    }
} else {
    Show-Off 'Docker not installed'
}

# ============================================================
# Project endpoints
# ============================================================
Show-Section 'Project endpoints (probe)'
$endpoints = @(
    @{ Name = 'Frontend';   Url = 'http://localhost:3000' }
    @{ Name = 'Backend API'; Url = 'http://localhost:8000/health' }
    @{ Name = 'AI service'; Url = 'http://localhost:8001/health' }
    @{ Name = 'MinIO';      Url = 'http://localhost:9001' }
    @{ Name = 'MailHog';    Url = 'http://localhost:8025' }
)
foreach ($ep in $endpoints) {
    try {
        $r = Invoke-WebRequest -Uri $ep.Url -Method Head -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        Show-OK ("{0,-12} {1} ({2})" -f $ep.Name, $ep.Url, $r.StatusCode)
    } catch {
        Show-Off ("{0,-12} {1} (unreachable)" -f $ep.Name, $ep.Url)
    }
}

# ============================================================
# Summary recommendation
# ============================================================
Show-Section 'Recommendation'

$mode = 'UNKNOWN'
if (-not $vg) { $mode = 'DEV (Vanguard not installed)' }
elseif (($vg | Where-Object StartType -eq 'Disabled').Count -ge 2) { $mode = 'DEV (Vanguard disabled)' }
elseif ($running) { $mode = 'GAME (Vanguard active)' }
else { $mode = 'TRANSITION (reboot pending)' }

Write-Host "  Current mode: $mode" -ForegroundColor Yellow
Write-Host ''
Write-Host '  Switch to Dev mode  : .\scripts\dev-mode.ps1' -ForegroundColor White
Write-Host '  Switch to Game mode : .\scripts\game-mode.ps1' -ForegroundColor White
Write-Host '  Start project       : .\start.cmd' -ForegroundColor White
Write-Host '  Stop project        : .\stop.cmd' -ForegroundColor White
Write-Host ''
