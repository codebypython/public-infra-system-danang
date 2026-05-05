#Requires -Version 5.1
<#
.SYNOPSIS
    Xem log của 1 hoặc tất cả services (tail follow).

.PARAMETER Service
    Tên service. Bỏ trống để xem tất cả.
    Ví dụ: backend | frontend | ai-service | db | redis | worker | beat

.EXAMPLE
    PS> .\scripts\logs.ps1
    PS> .\scripts\logs.ps1 backend
    PS> .\scripts\logs.ps1 frontend -Lines 200
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Service,

    [int]$Lines = 100
)

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir     = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $RootDir 'infra\docker-compose.yml'
$EnvFile     = Join-Path $RootDir '.env'
$ProjectName = 'danang-infra'

$composeArgs = @('-f', $ComposeFile, '-p', $ProjectName)
if (Test-Path $EnvFile) { $composeArgs += @('--env-file', $EnvFile) }

$logArgs = @('logs', '-f', '--tail', $Lines.ToString())
if ($Service) { $logArgs += $Service }

Write-Host "==> Tailing logs (Ctrl+C to exit)..." -ForegroundColor Cyan
& docker compose @composeArgs @logArgs
