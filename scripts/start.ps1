# Start FitManager on the LAN port. Run scripts/build.ps1 first.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$PidFile = Join-Path $Root "data\fitmanager.pid"
$Port = 8080
if ($env:APP_PORT) { $Port = [int]$env:APP_PORT }

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "backups") | Out-Null

$busy = netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING"
if ($busy) {
    Write-Error "Port $Port is already in use. Run scripts/stop.ps1 or change APP_PORT."
}

if (-not (Test-Path (Join-Path $Backend ".venv\Scripts\python.exe"))) {
    Write-Error "Python venv missing. Run scripts/build.ps1 first."
}
if (-not (Test-Path (Join-Path $Root "frontend\dist\index.html"))) {
    Write-Error "frontend/dist missing. Run scripts/build.ps1 first."
}

function Get-LanIPv4 {
    $found = @()
    $cfg = & ipconfig | Out-String
    foreach ($m in [regex]::Matches($cfg, "(?m)^\s*IPv4.*?:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)")) {
        $ip = $m.Groups[1].Value
        if ($ip -like "127.*" -or $ip -like "169.254.*") { continue }
        if ($found -notcontains $ip) { $found += $ip }
    }
    return $found
}

$lanIps = @(Get-LanIPv4)
$hostList = @("localhost", "127.0.0.1") + $lanIps
if ($env:ALLOWED_HOSTS) {
    $hostList += ($env:ALLOWED_HOSTS -split ",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
$env:ALLOWED_HOSTS = (($hostList | Where-Object { $_ } | Select-Object -Unique) -join ",")

$env:APP_ENV = "production"
$env:APP_HOST = "0.0.0.0"
if (-not $env:APP_PORT) { $env:APP_PORT = "$Port" }
if (-not $env:APP_TIMEZONE) { $env:APP_TIMEZONE = "Asia/Shanghai" }
$env:APP_DATA_DIR = Join-Path $Root "data"
$env:BACKUP_DIR = Join-Path $Root "backups"
if (-not $env:SCHEDULE_HORIZON_DAYS) { $env:SCHEDULE_HORIZON_DAYS = "365" }

$firewallName = "FitManager LAN $Port"
$existing = Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall: rule already present ($firewallName)."
} else {
    try {
        New-NetFirewallRule `
            -DisplayName $firewallName `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort $Port `
            -Profile Private `
            -ErrorAction Stop |
            Out-Null
        Write-Host "Firewall: allowed inbound TCP $Port on Private profile ($firewallName)."
    } catch {
        Write-Host "Firewall: NOT opened (Access denied). Run as Administrator:"
        Write-Host "          .\scripts\open-lan-firewall.ps1"
    }
}

Push-Location $Backend
try {
    & .\.venv\Scripts\alembic.exe upgrade head
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

$python = Join-Path $Backend ".venv\Scripts\python.exe"
$proc = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$Port"
) -WorkingDirectory $Backend -PassThru -WindowStyle Minimized
Set-Content -Path $PidFile -Value $proc.Id

Write-Host "FitManager started. PID $($proc.Id)"
Write-Host "Local:  http://127.0.0.1:$Port"
Write-Host "First admin setup must be opened from this PC: http://127.0.0.1:$Port"
Write-Host "ALLOWED_HOSTS=$($env:ALLOWED_HOSTS)"
if ($lanIps.Count -gt 0) {
    foreach ($ip in $lanIps) {
        Write-Host "LAN:    http://${ip}:$Port   <-- other devices must use THIS host IP, not the client IP"
    }
} else {
    Write-Host "Could not list LAN IPv4 addresses. Check ipconfig."
}
Write-Host "The service stops when this process is killed, the PC sleeps, or scripts/stop.ps1 runs."
