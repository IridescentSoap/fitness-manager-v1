# Build the frontend and prepare the backend for a local Windows run.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Created .env from .env.example. Set ALLOWED_HOSTS to this PC's LAN IP before sharing."
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "backups") | Out-Null

Push-Location $Backend
try {
    if (-not (Test-Path ".venv")) {
        py -3.12 -m venv .venv
    }
    & .\.venv\Scripts\python.exe -m pip install -U pip
    & .\.venv\Scripts\pip.exe install -e ".[dev]"
    & .\.venv\Scripts\alembic.exe upgrade head
}
finally {
    Pop-Location
}

Push-Location $Frontend
try {
    if (Test-Path "package-lock.json") {
        npm ci
        if ($LASTEXITCODE -ne 0) {
            Write-Host "npm ci failed; falling back to npm install"
            npm install
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
    } else {
        npm install
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "Build complete. Frontend dist is ready for the production server."
