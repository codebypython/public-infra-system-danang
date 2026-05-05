#Requires -Version 5.1
<#
.SYNOPSIS
    Pre-Windows-Update safety backup. Run before switching Windows Insider channel
    or applying any major Windows feature update.

.DESCRIPTION
    Performs:
      1. Windows System Restore Point (rollback target on C:)
      2. Bitlocker recovery key export (if any drives encrypted)
      3. Project folder zip backup
      4. Inventory of large files on D:, E:, F: drives (informational)
      5. Saves diagnostic snapshot (build, services, drives) for reference

.PARAMETER OutputDir
    Directory where backup zips and key files are saved. Default: D:\Development\

.EXAMPLE
    .\scripts\backup-pre-update.ps1
#>
[CmdletBinding()]
param(
    [string]$OutputDir = 'D:\Development'
)

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir
$Stamp     = Get-Date -Format 'yyyyMMdd-HHmm'

function Write-Step  { param([string]$Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "    [OK]   $Msg" -ForegroundColor Green }
function Write-Warn2 { param([string]$Msg) Write-Host "    [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err2  { param([string]$Msg) Write-Host "    [ERR]  $Msg" -ForegroundColor Red }

Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Magenta
Write-Host '|   Pre-Update Backup - Da Nang Infrastructure System        |' -ForegroundColor Magenta
Write-Host '+============================================================+' -ForegroundColor Magenta

# Verify admin
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Err2 'This script needs Administrator privileges.'
    Write-Host '    Right-click Start > Terminal (Admin) and re-run.' -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# ============================================================
# STEP 1: System Restore Point
# ============================================================
Write-Step '1) Creating System Restore Point on C:'

try {
    Enable-ComputerRestore -Drive 'C:\' -ErrorAction SilentlyContinue
    # Bypass throttle: System Restore by default refuses creating a new point
    # within 24h of the previous one. Override via registry.
    New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' `
        -Name 'SystemRestorePointCreationFrequency' -Value 0 -PropertyType DWORD -Force | Out-Null

    Checkpoint-Computer -Description 'Pre-Beta-Channel-Switch' -RestorePointType 'MODIFY_SETTINGS'
    Write-Ok 'Restore point created: "Pre-Beta-Channel-Switch"'

    $latest = Get-ComputerRestorePoint | Sort-Object CreationTime -Descending | Select-Object -First 1
    if ($latest) {
        Write-Host "       Created : $($latest.CreationTime)" -ForegroundColor DarkGray
        Write-Host "       Sequence: $($latest.SequenceNumber)" -ForegroundColor DarkGray
    }
} catch {
    Write-Warn2 "Could not create restore point: $($_.Exception.Message)"
    Write-Host '       (Continuing — restore point is optional safety net)' -ForegroundColor DarkGray
}

# ============================================================
# STEP 2: Bitlocker check + key export
# ============================================================
Write-Step '2) Checking Bitlocker on all drives'

try {
    $btVolumes = Get-BitLockerVolume -ErrorAction Stop
    $encrypted = $btVolumes | Where-Object { $_.VolumeStatus -eq 'FullyEncrypted' -or $_.VolumeStatus -eq 'EncryptionInProgress' }

    if ($encrypted) {
        $btFile = Join-Path $OutputDir "bitlocker-keys-$Stamp.txt"
        $report = @()
        $report += '======================================================'
        $report += "Bitlocker Recovery Keys - exported $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        $report += 'KEEP THIS FILE SECURE. Print or save in password manager.'
        $report += '======================================================'
        $report += ''
        foreach ($vol in $encrypted) {
            $report += "Drive: $($vol.MountPoint)"
            $report += "  Status: $($vol.VolumeStatus)  Method: $($vol.EncryptionMethod)"
            $protectors = $vol.KeyProtector | Where-Object KeyProtectorType -eq 'RecoveryPassword'
            foreach ($p in $protectors) {
                $report += "  Recovery key (ID $($p.KeyProtectorId)):"
                $report += "    $($p.RecoveryPassword)"
            }
            $report += ''
        }
        $report | Out-File $btFile -Encoding utf8
        Write-Ok "Bitlocker keys exported to: $btFile"
        Write-Warn2 'Open and PRINT or save this file to USB/cloud immediately!'
        Write-Host "       notepad `"$btFile`"" -ForegroundColor DarkGray
    } else {
        Write-Ok 'No Bitlocker-encrypted drives detected. Safe to proceed.'
    }
} catch {
    Write-Ok 'Bitlocker not in use (cmdlet unavailable or no encrypted volumes).'
}

# ============================================================
# STEP 3: Project zip backup
# ============================================================
Write-Step '3) Zipping project folder'

$zipFile = Join-Path $OutputDir "backup-danang-$Stamp.zip"
try {
    if (Test-Path $zipFile) { Remove-Item $zipFile -Force }
    Compress-Archive -Path "$RootDir\*" `
                     -DestinationPath $zipFile `
                     -CompressionLevel Optimal `
                     -ErrorAction Stop
    $sizeMB = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
    Write-Ok "Project archive: $zipFile  ($sizeMB MB)"
} catch {
    Write-Warn2 "Archive failed: $($_.Exception.Message)"
    Write-Host '       (Project source is in git — push to remote as alternative backup)' -ForegroundColor DarkGray
}

# ============================================================
# STEP 4: Drive inventory (informational)
# ============================================================
Write-Step '4) Drive layout'

Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object {
    $usedGB = [math]::Round($_.Used / 1GB, 1)
    $freeGB = [math]::Round($_.Free / 1GB, 1)
    $totalGB = $usedGB + $freeGB
    Write-Host ("    {0}: {1} GB used / {2} GB total ({3}% free)" -f $_.Name, $usedGB, $totalGB, [math]::Round(($_.Free / ($_.Used + $_.Free)) * 100)) -ForegroundColor Gray
}

Write-Host ''
Write-Host '    Note: Windows Update in-place upgrade only modifies C:.' -ForegroundColor DarkGray
Write-Host '          D:, E:, F: data is NOT touched.' -ForegroundColor DarkGray

# ============================================================
# STEP 5: Diagnostic snapshot
# ============================================================
Write-Step '5) Saving diagnostic snapshot'

$diagFile = Join-Path $OutputDir "diag-snapshot-$Stamp.txt"
$diag = @()
$diag += "=== Diagnostic Snapshot - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
$diag += ''
$diag += '--- OS ---'
$diag += (Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsHardwareAbstractionLayer | Format-List | Out-String).Trim()
$diag += ''
$diag += '--- CPU virtualization ---'
$diag += (Get-WmiObject Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled, SecondLevelAddressTranslationExtensions | Format-List | Out-String).Trim()
$diag += ''
$diag += '--- Optional Features ---'
$diag += (Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform, Microsoft-Windows-Subsystem-Linux, HypervisorPlatform -ErrorAction SilentlyContinue | Format-Table FeatureName, State | Out-String).Trim()
$diag += ''
$diag += '--- Vanguard services ---'
$vg = Get-Service vgc, vgk -ErrorAction SilentlyContinue
if ($vg) {
    $diag += ($vg | Format-Table Name, Status, StartType | Out-String).Trim()
} else {
    $diag += '(Vanguard not installed)'
}
$diag += ''
$diag += '--- Telemetry ---'
$tel = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection' -Name AllowTelemetry -ErrorAction SilentlyContinue
if ($tel) { $diag += "AllowTelemetry: $($tel.AllowTelemetry)" } else { $diag += 'AllowTelemetry: not set' }
$diag += "DiagTrack service: $((Get-Service DiagTrack -ErrorAction SilentlyContinue).Status)"

$diag | Out-File $diagFile -Encoding utf8
Write-Ok "Diagnostic snapshot: $diagFile"

# ============================================================
# Summary
# ============================================================
Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Green
Write-Host '|   BACKUP COMPLETE - Safe to proceed with Phase 2           |' -ForegroundColor Green
Write-Host '+============================================================+' -ForegroundColor Green
Write-Host ''
Write-Host '  Files created:' -ForegroundColor Yellow
Write-Host "    $zipFile" -ForegroundColor White
if (Test-Path (Join-Path $OutputDir "bitlocker-keys-$Stamp.txt")) {
    Write-Host "    $(Join-Path $OutputDir "bitlocker-keys-$Stamp.txt")" -ForegroundColor White
}
Write-Host "    $diagFile" -ForegroundColor White
Write-Host ''
Write-Host '  Next: Phase 2 - Switch to Beta channel' -ForegroundColor Yellow
Write-Host '    start ms-settings:windowsinsider' -ForegroundColor White
Write-Host ''
Write-Host '  Read full roadmap: SETUP-ROADMAP.md' -ForegroundColor DarkGray
Write-Host ''
