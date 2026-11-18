# Create a consistent SQLite backup via the online backup API.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$env:APP_DATA_DIR = Join-Path $Root "data"
$env:BACKUP_DIR = Join-Path $Root "backups"
if (-not $env:APP_TIMEZONE) { $env:APP_TIMEZONE = "Asia/Shanghai" }
New-Item -ItemType Directory -Force -Path $env:APP_DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:BACKUP_DIR | Out-Null

Push-Location $Backend
try {
    & .\.venv\Scripts\python.exe -c @"
from app.core.database import SessionLocal
from app.services.backup_service import create_backup
with SessionLocal() as db:
    meta = create_backup(db, actor_user_id=None, reason='script')
print(meta['filename'])
"@
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
