#Requires -Version 5.1
<#
.SYNOPSIS
    Stop and DESTROY all data volumes. Next start.ps1 will re-init from scratch.
#>
[CmdletBinding()]
param([switch]$Force)

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir     = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $RootDir 'infra\docker-compose.yml'
$EnvFile     = Join-Path $RootDir '.env'
$ProjectName = 'danang-infra'

if (-not $Force) {
    Write-Host ''
    Write-Host '!!! WARNING: This will DELETE ALL DATA of the system !!!' -ForegroundColor Red
    Write-Host '    - PostgreSQL data (DB schema + records)' -ForegroundColor Yellow
    Write-Host '    - MinIO objects (report images, QR, watermarks)' -ForegroundColor Yellow
    Write-Host '    - Redis cache + Celery queue' -ForegroundColor Yellow
    Write-Host '    - Meilisearch index' -ForegroundColor Yellow
    Write-Host ''
    $reply = Read-Host 'Type "RESET" to confirm'
    if ($reply -ne 'RESET') {
        Write-Host 'Cancelled.' -ForegroundColor Green
        exit 0
    }
}

Write-Host '==> Stopping and removing volumes...' -ForegroundColor Cyan

$composeArgs = @('-f', $ComposeFile, '-p', $ProjectName)
if (Test-Path $EnvFile) { $composeArgs += @('--env-file', $EnvFile) }

& docker compose @composeArgs down -v --remove-orphans

if ($LASTEXITCODE -eq 0) {
    Write-Host '    [OK]   Volumes removed. Run .\scripts\start.ps1 to start fresh.' -ForegroundColor Green
} else {
    Write-Host '    [ERR]  Reset failed.' -ForegroundColor Red
    exit 1
}
