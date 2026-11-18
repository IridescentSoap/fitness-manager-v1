# Allow FitManager LAN ports on the Private firewall profile.
# Run this once in an elevated PowerShell (右键“以管理员身份运行”).
$ErrorActionPreference = "Stop"

$ports = @(8080, 5173)
if ($env:APP_PORT) {
    $ports = @([int]$env:APP_PORT) + $ports | Select-Object -Unique
}

foreach ($port in $ports) {
    $name = "FitManager LAN $port"
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Already present: $name"
        continue
    }
    New-NetFirewallRule `
        -DisplayName $name `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $port `
        -Profile Private |
        Out-Null
    Write-Host "Created: $name (Private / TCP $port inbound)"
}

Write-Host ""
Write-Host "Other devices should open the SERVICE PC IP, for example:"
$cfg = & ipconfig | Out-String
$shown = $false
foreach ($m in [regex]::Matches($cfg, "(?m)^\s*IPv4.*?:\s*(192\.168\.[0-9.]+|10\.[0-9.]+)")) {
    Write-Host ("  http://{0}:8080" -f $m.Groups[1].Value)
    $shown = $true
}
if (-not $shown) {
    Write-Host "  (run ipconfig and use this PC WLAN/Ethernet IPv4)"
}
