# Stop the FitManager process started by scripts/start.ps1.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root "data\fitmanager.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "FitManager is not running (no pid file)."
    exit 0
}

$processId = Get-Content $PidFile | Select-Object -First 1
$proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($proc) {
    Stop-Process -Id $processId -Force
    Write-Host "Stopped FitManager PID $processId"
} else {
    Write-Host "Process $processId was already gone."
}
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
