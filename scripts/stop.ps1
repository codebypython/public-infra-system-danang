#Requires -Version 5.1
<#
.SYNOPSIS
    Stop all Da Nang Infra services. Data volumes are preserved.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir     = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $RootDir 'infra\docker-compose.yml'
$EnvFile     = Join-Path $RootDir '.env'
$ProjectName = 'danang-infra'

Write-Host '==> Stopping all services...' -ForegroundColor Cyan

$composeArgs = @('-f', $ComposeFile, '-p', $ProjectName)
if (Test-Path $EnvFile) { $composeArgs += @('--env-file', $EnvFile) }

& docker compose @composeArgs down

if ($LASTEXITCODE -eq 0) {
    Write-Host '    [OK]   All containers stopped. Data volumes are preserved.' -ForegroundColor Green
    Write-Host '    Restart with: .\scripts\start.ps1' -ForegroundColor Yellow
} else {
    Write-Host '    [ERR]  Failed to stop services.' -ForegroundColor Red
    exit 1
}
