# Build (if needed), start an isolated production server, run Playwright E2E, then stop.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$E2eDir = Join-Path $Root "e2e"
$Port = 18080
if ($env:E2E_PORT) { $Port = [int]$env:E2E_PORT }

$DataDir = Join-Path $Root "data\e2e"
$BackupDir = Join-Path $Root "backups\e2e"
$PidFile = Join-Path $DataDir "fitmanager-e2e.pid"
$BaseUrl = "http://127.0.0.1:$Port"

function Stop-E2eServer {
    if (Test-Path $PidFile) {
        $processId = Get-Content $PidFile | Select-Object -First 1
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $processId -Force
            Write-Host "Stopped E2E server PID $processId"
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "=== FitManager Windows T6 E2E ==="

if (-not (Test-Path (Join-Path $Backend ".venv\Scripts\python.exe"))) {
    Write-Host "Missing backend venv — running build.ps1"
    & (Join-Path $Root "scripts\build.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (-not (Test-Path (Join-Path $Root "frontend\dist\index.html"))) {
    Write-Host "Missing frontend/dist — running build.ps1"
    & (Join-Path $Root "scripts\build.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Stop-E2eServer
if (Test-Path $DataDir) { Remove-Item -Recurse -Force $DataDir }
if (Test-Path $BackupDir) { Remove-Item -Recurse -Force $BackupDir }
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$busy = netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING"
if ($busy) {
    Write-Error "Port $Port is already in use. Stop the other process or set E2E_PORT."
}

$env:APP_ENV = "production"
$env:APP_HOST = "127.0.0.1"
$env:APP_PORT = "$Port"
$env:APP_TIMEZONE = "Asia/Shanghai"
$env:APP_DATA_DIR = $DataDir
$env:BACKUP_DIR = $BackupDir
$env:SCHEDULE_HORIZON_DAYS = "60"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"

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
    "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port"
) -WorkingDirectory $Backend -PassThru -WindowStyle Minimized
Set-Content -Path $PidFile -Value $proc.Id
Write-Host "E2E server started PID $($proc.Id) at $BaseUrl"

$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "$BaseUrl/api/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        # still starting
    }
}
if (-not $healthy) {
    Stop-E2eServer
    Write-Error "E2E server did not become healthy on $BaseUrl/api/health"
}

Push-Location $E2eDir
$exitCode = 1
try {
    if (-not (Test-Path "node_modules")) {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }
    npx playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "playwright browser install failed" }

    $env:E2E_BASE_URL = $BaseUrl
    npx playwright test
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
    Stop-E2eServer
}

if ($exitCode -ne 0) {
    Write-Error "Playwright E2E failed with exit code $exitCode"
}
Write-Host "Playwright E2E passed."
exit 0
