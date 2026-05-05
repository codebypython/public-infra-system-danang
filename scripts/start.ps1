#Requires -Version 5.1
<#
.SYNOPSIS
    One-command launcher for Da Nang Public Infrastructure System.

.DESCRIPTION
    Auto-detects Docker, generates .env, builds and starts ALL services
    (PostgreSQL+PostGIS, Redis, MinIO, Meilisearch, MailHog, FastAPI backend,
    AI service, Next.js frontend, Celery worker + beat), runs migrations,
    seeds Da Nang baseline data, then prints URLs and demo accounts.

.PARAMETER InstallDocker
    Auto-install Docker Desktop via winget (silent).

.PARAMETER NoSeed
    Skip seeding sample data.

.PARAMETER Rebuild
    Force rebuild Docker images without cache.

.PARAMETER Detached
    Run containers detached (default true). Set $false to follow logs in foreground.

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -Rebuild
    .\scripts\start.ps1 -InstallDocker
#>
[CmdletBinding()]
param(
    [switch]$InstallDocker,
    [switch]$NoSeed,
    [switch]$Rebuild,
    [switch]$Detached = $true
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir     = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$ComposeFile = Join-Path $RootDir 'infra\docker-compose.yml'
$EnvFile     = Join-Path $RootDir '.env'
$EnvExample  = Join-Path $RootDir '.env.example'
$ProjectName = 'danang-infra'

function Write-Step  { param([string]$Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "    [OK]   $Msg" -ForegroundColor Green }
function Write-Warn2 { param([string]$Msg) Write-Host "    [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err2  { param([string]$Msg) Write-Host "    [ERR]  $Msg" -ForegroundColor Red }

Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Magenta
Write-Host '|   Da Nang Public Infrastructure System  -  DEV Launcher    |' -ForegroundColor Magenta
Write-Host '+============================================================+' -ForegroundColor Magenta

# ============================================================
# STEP 1: Detect / Install Docker
# ============================================================
Write-Step 'Checking Docker Desktop'

function Test-DockerAvailable {
    try {
        $null = Get-Command docker -ErrorAction Stop
        $null = & docker info 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Install-DockerViaWinget {
    Write-Step 'Installing Docker Desktop via winget'

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Err2 'winget not available. Please install Docker Desktop manually:'
        Write-Host  '    https://www.docker.com/products/docker-desktop/' -ForegroundColor White
        exit 1
    }

    $isAdmin = ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Warn2 'Current session is NOT elevated.'
        Write-Host  '    Spawning elevated PowerShell to run winget install ...' -ForegroundColor Yellow
        $cmd = 'winget install -e --id Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements; Read-Host "Done. Press Enter, then RESTART your machine and re-run start.ps1"'
        Start-Process powershell -Verb RunAs -Wait -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd
        )
    } else {
        & winget install -e --id Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements
    }

    Write-Host ''
    Write-Warn2 'Docker Desktop installed. Next steps:'
    Write-Host  '      1) RESTART your computer.' -ForegroundColor White
    Write-Host  '      2) Launch Docker Desktop and finish setup (use WSL2 backend).' -ForegroundColor White
    Write-Host  '      3) Re-run:  .\scripts\start.ps1' -ForegroundColor White
    exit 0
}

if (-not (Test-DockerAvailable)) {
    Write-Warn2 'Docker not installed or Docker Desktop is not running.'
    Write-Host  '      System needs Docker to run PostgreSQL+PostGIS, Redis, MinIO.' -ForegroundColor Yellow

    if ($InstallDocker) {
        Install-DockerViaWinget
    } else {
        $reply = Read-Host '      Auto-install Docker Desktop via winget? (y/N)'
        if ($reply -match '^[yY]') {
            Install-DockerViaWinget
        } else {
            Write-Host ''
            Write-Host '      Please install Docker Desktop from:' -ForegroundColor Yellow
            Write-Host '        https://www.docker.com/products/docker-desktop/' -ForegroundColor White
            Write-Host '      Then re-run this script.' -ForegroundColor Yellow
            exit 1
        }
    }
}

Write-Ok ('Docker available: ' + (& docker --version))
try {
    $null = & docker compose version 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'compose missing' }
    Write-Ok ('Docker Compose: ' + ((& docker compose version) -join ' '))
} catch {
    Write-Err2 'Docker Compose plugin missing. Update Docker Desktop.'
    exit 1
}

# ============================================================
# STEP 2: Bootstrap .env
# ============================================================
Write-Step 'Preparing .env file'

if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    $secret = -join ((48..57) + (97..122) + (65..90) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
    $content = (Get-Content $EnvFile -Raw) -replace 'change-me-to-a-random-64-char-hex-string-for-jwt-signing', $secret
    Set-Content -Path $EnvFile -Value $content -NoNewline
    Write-Ok '.env created from .env.example (SECRET_KEY auto-generated)'
} else {
    Write-Ok '.env already exists'
}

# ============================================================
# STEP 3: Build + Up
# ============================================================
Write-Step 'Building and starting containers'

$composeArgs = @('-f', $ComposeFile, '-p', $ProjectName, '--env-file', $EnvFile)

if ($Rebuild) {
    Write-Host '    -Rebuild flag: docker compose build --no-cache ...' -ForegroundColor Yellow
    & docker compose @composeArgs build --no-cache
    if ($LASTEXITCODE -ne 0) { Write-Err2 'Build failed.'; exit 1 }
}

$upArgs = @('up', '--build')
if ($Detached) { $upArgs += '-d' }

& docker compose @composeArgs @upArgs
if ($LASTEXITCODE -ne 0) {
    Write-Err2 'docker compose up failed.'
    Write-Host  '    See logs:  .\scripts\logs.ps1' -ForegroundColor Yellow
    exit 1
}
Write-Ok 'All containers started.'

if (-not $Detached) { return }

# ============================================================
# STEP 4: Wait for PostgreSQL
# ============================================================
Write-Step 'Waiting for PostgreSQL to be ready'

$maxWait = 120
$elapsed = 0
$dbReady = $false
while ($elapsed -lt $maxWait) {
    & docker compose @composeArgs exec -T db pg_isready -U infra -d danang_infra 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dbReady = $true; break }
    Start-Sleep -Seconds 2
    $elapsed += 2
    Write-Host '.' -NoNewline -ForegroundColor DarkGray
}
Write-Host ''

if (-not $dbReady) {
    Write-Err2 'PostgreSQL not ready after 120s. Check:  .\scripts\logs.ps1 db'
    exit 1
}
Write-Ok 'PostgreSQL ready'

# ============================================================
# STEP 5: Migrations
# ============================================================
Write-Step 'Running Alembic migrations'

& docker compose @composeArgs exec -T backend alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Err2 'Migrations failed. See:  .\scripts\logs.ps1 backend'
    exit 1
}
Write-Ok 'Migrations applied'

# ============================================================
# STEP 6: Seed Da Nang baseline (idempotent)
# ============================================================
if (-not $NoSeed) {
    Write-Step 'Seeding Da Nang baseline data (idempotent)'
    & docker compose @composeArgs exec -T backend python -m app.scripts.seed_danang
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 'Seed failed or already seeded - skipping.'
    } else {
        Write-Ok 'Seed complete'
    }
} else {
    Write-Warn2 '-NoSeed: skipping data seed'
}

# ============================================================
# STEP 7: Done
# ============================================================
Write-Host ''
Write-Host '+============================================================+' -ForegroundColor Green
Write-Host '|   SYSTEM READY                                             |' -ForegroundColor Green
Write-Host '+============================================================+' -ForegroundColor Green
Write-Host ''
Write-Host '  Frontend (Next.js)        : ' -NoNewline; Write-Host 'http://localhost:3000'      -ForegroundColor Cyan
Write-Host '  Backend API (FastAPI)     : ' -NoNewline; Write-Host 'http://localhost:8000'      -ForegroundColor Cyan
Write-Host '  API Docs (Swagger)        : ' -NoNewline; Write-Host 'http://localhost:8000/docs' -ForegroundColor Cyan
Write-Host '  AI Service                : ' -NoNewline; Write-Host 'http://localhost:8001/docs' -ForegroundColor Cyan
Write-Host '  MinIO Console             : ' -NoNewline; Write-Host 'http://localhost:9001'      -ForegroundColor Cyan
Write-Host '                              (login: minioadmin / minioadmin)' -ForegroundColor DarkGray
Write-Host '  MailHog (catch-all email) : ' -NoNewline; Write-Host 'http://localhost:8025'      -ForegroundColor Cyan
Write-Host '  Meilisearch               : ' -NoNewline; Write-Host 'http://localhost:7700'      -ForegroundColor Cyan
Write-Host ''
Write-Host '  Demo accounts:' -ForegroundColor Yellow
Write-Host '    admin@danang.gov.vn      / Admin@123     (admin)' -ForegroundColor White
Write-Host '    operator@danang.gov.vn   / Op@12345      (operator)' -ForegroundColor White
Write-Host '    tech@danang.gov.vn       / Tech@123      (taskforce)' -ForegroundColor White
Write-Host '    citizen@danang.gov.vn    / User@123      (citizen)' -ForegroundColor White
Write-Host ''
Write-Host '  Useful commands:' -ForegroundColor Yellow
Write-Host '    .\scripts\logs.ps1                tail logs of all services' -ForegroundColor White
Write-Host '    .\scripts\logs.ps1 backend        tail one service' -ForegroundColor White
Write-Host '    .\scripts\stop.ps1                stop all (keep data)' -ForegroundColor White
Write-Host '    .\scripts\reset.ps1               stop and DELETE all data volumes' -ForegroundColor White
Write-Host ''
