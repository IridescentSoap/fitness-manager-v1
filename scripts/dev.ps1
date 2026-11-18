# FitManager T0 development helper
# Usage:
#   .\scripts\dev.ps1 backend
#   .\scripts\dev.ps1 frontend
#   .\scripts\dev.ps1 test
#   .\scripts\dev.ps1 setup

param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "backend", "frontend", "test", "migrate")]
    [string]$Command = "setup"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$env:APP_DATA_DIR = Join-Path $Root "data"
$env:BACKUP_DIR = Join-Path $Root "backups"
if (-not $env:APP_TIMEZONE) { $env:APP_TIMEZONE = "Asia/Shanghai" }

function Ensure-PythonVenv {
    Push-Location $Backend
    try {
        if (-not (Test-Path ".venv")) {
            Write-Host "Creating Python 3.12 venv..."
            py -3.12 -m venv .venv
        }
        & .\.venv\Scripts\python.exe -m pip install -U pip
        & .\.venv\Scripts\pip.exe install -e ".[dev]"
    }
    finally {
        Pop-Location
    }
}

function Ensure-FrontendDeps {
    Push-Location $Frontend
    try {
        if (-not (Test-Path "node_modules")) {
            npm ci
            if ($LASTEXITCODE -ne 0) {
                npm install
            }
        }
    }
    finally {
        Pop-Location
    }
}

switch ($Command) {
    "setup" {
        if (-not (Test-Path (Join-Path $Root ".env"))) {
            Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
            Write-Host "Created .env from .env.example"
        }
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "backups") | Out-Null
        Ensure-PythonVenv
        Ensure-FrontendDeps
        Write-Host "T0 setup complete."
    }
    "migrate" {
        Push-Location $Backend
        try {
            & .\.venv\Scripts\alembic.exe upgrade head
        }
        finally {
            Pop-Location
        }
    }
    "backend" {
        Ensure-PythonVenv
        Push-Location $Backend
        try {
            & .\.venv\Scripts\alembic.exe upgrade head
            # Keep API on loopback; Vite proxies /api. LAN clients hit the Vite host.
            & .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
        }
        finally {
            Pop-Location
        }
    }
    "frontend" {
        Ensure-FrontendDeps
        Push-Location $Frontend
        try {
            Write-Host "Vite listens on 0.0.0.0:5173 (LAN: http://<this-pc-ip>:5173)."
            try {
                $lan = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
                    Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" } |
                    Select-Object -First 3 -ExpandProperty IPAddress
                foreach ($ip in $lan) {
                    Write-Host "  try  http://${ip}:5173"
                }
            } catch {}
            npm run dev -- --host 0.0.0.0 --port 5173
        }
        finally {
            Pop-Location
        }
    }
    "test" {
        Ensure-PythonVenv
        Push-Location $Backend
        try {
            & .\.venv\Scripts\pytest.exe -q
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        finally {
            Pop-Location
        }
        Ensure-FrontendDeps
        Push-Location $Frontend
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            if (Get-Command npm -ErrorAction SilentlyContinue) {
                npm run test --if-present
            }
        }
        finally {
            Pop-Location
        }
    }
}
