#!/usr/bin/env pwsh
param(
    [string]$cmd,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$rest
)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$Routes = "/ app · /admin · /status (dev tool links live in the app nav)"
$HealthUrl = "http://localhost:8000/api/health"

function Test-PortInUse([int]$port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $port)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function New-Secret {
    -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
}

function Set-EnvValue([string]$key, [string]$val) {
    $lines = @()
    if (Test-Path .env) {
        $lines = @(Get-Content .env | Where-Object { $_ -notmatch "^$([regex]::Escape($key))=" })
    }
    $lines += "$key=$val"
    [System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot ".env"), $lines)
}

function Save-CorpCerts {
    $dir = Join-Path $PSScriptRoot "deploy/certs"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $pem = New-Object System.Text.StringBuilder
    foreach ($c in Get-ChildItem Cert:\LocalMachine\Root) {
        [void]$pem.AppendLine("-----BEGIN CERTIFICATE-----")
        [void]$pem.AppendLine([Convert]::ToBase64String($c.RawData, 'InsertLineBreaks'))
        [void]$pem.AppendLine("-----END CERTIFICATE-----")
    }
    [System.IO.File]::WriteAllText((Join-Path $dir "corp-ca.crt"), $pem.ToString())
    Write-Host "  OK - company certificates saved to deploy/certs/corp-ca.crt" -ForegroundColor Green
}

function Wait-ForHealth {
    Write-Host "Waiting for the app to become healthy (first build can take ~3-5 min)..."
    $deadline = (Get-Date).AddSeconds(300)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 5 *> $null
            Write-Host "Up -> http://localhost:8000  ( $Routes )" -ForegroundColor Green
            Write-Host "(logs: manage.cmd logs | stop: manage.cmd down)"
            return
        } catch {
            Start-Sleep -Seconds 3
        }
    }
    Write-Warning "still starting - check: manage.cmd logs"
}

function Test-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "X  Docker is not installed." -ForegroundColor Red
        Write-Host "   Install one of these (any works), start it, then run manage.cmd again:"
        Write-Host "     - Rancher Desktop (free for work):  https://rancherdesktop.io"
        Write-Host "     - Docker Desktop:                   https://www.docker.com/products/docker-desktop"
        Write-Host "     - OrbStack (Mac, fast):             https://orbstack.dev"
        return $false
    }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "X  Docker is installed but not running." -ForegroundColor Red
        Write-Host "   Start Docker/Rancher Desktop, wait until it says 'running', then run manage.cmd again."
        return $false
    }
    Write-Host "OK - Docker is running" -ForegroundColor Green
    $memTotal = docker info --format '{{.MemTotal}}'
    if ($memTotal -match '^\d+$' -and [int64]$memTotal -lt 4294967296) {
        Write-Host "!  Docker has <4GB RAM; raise it in Settings > Resources for best results." -ForegroundColor Yellow
    }
    if (Test-PortInUse 8000) {
        Write-Host "!  Port 8000 is in use; the app may not start. Close whatever is using it." -ForegroundColor Yellow
    }
    return $true
}

function Set-EnvInteractive {
    Copy-Item .env.example .env -Force

    $appName = Read-Host "App name [Genesis]"
    if (-not $appName) { $appName = "Genesis" }
    Set-EnvValue "APP_NAME" $appName

    Write-Host ""
    Write-Host "AI chat setup:"
    Write-Host "  [1] OpenRouter  - one key, easiest (recommended)"
    Write-Host "  [2] Portkey     - your gateway + a provider key"
    Write-Host "  [3] Skip        - add later"
    $llm = Read-Host ">"
    switch ($llm) {
        "1" {
            $k = Read-Host "Paste your OpenRouter key"
            Set-EnvValue "LLM_API_KEY" $k
            Set-EnvValue "LLM_BASE_URL" "https://openrouter.ai/api/v1"
            Set-EnvValue "LLM_MODEL" "openai/gpt-4o-mini"
        }
        "2" {
            $gw = Read-Host "Portkey gateway URL (e.g. https://your-gateway.portkey.ai/v1)"
            $pk = Read-Host "Portkey API key"
            $prov = Read-Host "Provider (openai/anthropic/google)"
            $provkey = Read-Host "Provider API key"
            Set-EnvValue "LLM_API_KEY" $provkey
            Set-EnvValue "LLM_BASE_URL" $gw
            Set-EnvValue "LLM_EXTRA_HEADERS" ("{{""x-portkey-api-key"":""{0}"",""x-portkey-provider"":""{1}""}}" -f $pk, $prov)
        }
        default { Write-Host "Skipping AI for now (add it to .env later)." }
    }

    Write-Host ""
    $dbPass = Read-Host "Database password [Enter = auto-generate a strong one]"
    if (-not $dbPass) { $dbPass = New-Secret }
    Set-EnvValue "POSTGRES_PASSWORD" $dbPass

    $adminPass = Read-Host "Dashboard admin password [Enter = auto-generate]"
    if (-not $adminPass) { $adminPass = New-Secret }
    Set-EnvValue "O2_ROOT_PASSWORD" $adminPass

    Write-Host ""
    $corp = Read-Host "Are you on a corporate network with a security proxy? [y/N]"
    if ($corp -match '^[yY]') { Save-CorpCerts }

    Write-Host "OK - .env configured" -ForegroundColor Green
    Write-Host ""
    Write-Host "Save these - they log you into the built-in dashboards (also stored in .env):" -ForegroundColor Cyan
    Write-Host "  Database password:  $dbPass"
    Write-Host "  Dashboard login:    admin@genesis.local  /  $adminPass"
}

function Invoke-Doctor {
    Write-Host "=============================================="
    Write-Host "  Genesis setup"
    Write-Host "=============================================="
    if (-not (Test-Docker)) { return }

    $reconfig = "y"
    if (Test-Path .env) {
        $reconfig = Read-Host "A .env already exists. Reconfigure it? [y/N]"
    }
    if ($reconfig -match '^[yY]') { Set-EnvInteractive } else { Write-Host "Keeping existing .env." }

    Write-Host ""
    $start = Read-Host "Start the app now? [Y/n]"
    if ($start -match '^[nN]') { Write-Host "When you're ready: manage.cmd dev" } else { Start-Dev }

    Write-Host ""
    Read-Host "Press Enter to close" | Out-Null
}

function Start-Dev {
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
    Write-Host "Starting DEV (hot-reload backend)..."
    docker compose --profile dev up -d --build
    Wait-ForHealth
}

function Invoke-Genesis([string[]]$Arguments) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $env:PYTHONPATH = "$PSScriptRoot\tools\genesis"
        & python -m genesis_cli.cli @Arguments
        exit $LASTEXITCODE
    }
    if (Get-Command uvx -ErrorAction SilentlyContinue) {
        & uvx --no-cache --from ./tools/genesis genesis @Arguments
        exit $LASTEXITCODE
    }
    Write-Host "The genesis CLI needs uv (https://astral.sh/uv) or python on PATH." -ForegroundColor Red
    exit 1
}

switch ($cmd) {
    ""        { Invoke-Doctor }
    "doctor"  { Invoke-Doctor }
    "setup"   { Invoke-Doctor }
    "certs"   { Save-CorpCerts }
    default   { Invoke-Genesis (@($cmd) + $rest) }
}
