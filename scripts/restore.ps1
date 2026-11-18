# Restore a backup created by backup.ps1 or the admin API.
# Usage: .\scripts\restore.ps1 -BackupId fitness-20261116-140000.db -Confirm RESTORE
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupId,
    [Parameter(Mandatory = $true)]
    [string]$Confirm
)

$ErrorActionPreference = "Stop"
if ($Confirm -ne "RESTORE") {
    Write-Error "Refusing restore. Pass -Confirm RESTORE"
}

$Root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "stop.ps1")

$Backend = Join-Path $Root "backend"
$env:APP_DATA_DIR = Join-Path $Root "data"
$env:BACKUP_DIR = Join-Path $Root "backups"
if (-not $env:APP_TIMEZONE) { $env:APP_TIMEZONE = "Asia/Shanghai" }

Push-Location $Backend
try {
    & .\.venv\Scripts\python.exe -c @"
from app.core.database import SessionLocal
from app.services.backup_service import restore_backup
with SessionLocal() as db:
    admin_id = db.execute(__import__('sqlalchemy').text("SELECT id FROM users WHERE role='ADMIN' ORDER BY id LIMIT 1")).scalar()
    result = restore_backup(db, actor_user_id=int(admin_id or 0), backup_id='$BackupId', confirm='RESTORE')
print(result['restored'])
"@
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "Restore finished. Start the service again with scripts/start.ps1"
