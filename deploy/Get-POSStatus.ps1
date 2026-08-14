[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force

Assert-PosPrerequisites
Invoke-PosCompose -Arguments @("ps") | Out-Host
$selected = Get-PosEnvValue -Name "POS_APP_VERSION"
if ([string]::IsNullOrWhiteSpace($selected)) { $selected = "development" }
Write-Host "Selected version: $selected"

$backupSetting = Get-PosEnvValue -Name "POS_BACKUP_DIR"
if ([string]::IsNullOrWhiteSpace($backupSetting)) { $backupSetting = "var/backups" }
$backupDirectory = Resolve-PosSafeDirectory -Path $backupSetting -Create
$lastBackup = Get-ChildItem -LiteralPath $backupDirectory -File -Filter "pos-*.dump" |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($lastBackup) {
    Write-Host "Latest backup: $($lastBackup.FullName) ($($lastBackup.LastWriteTime))"
}
else {
    Write-Warning "No verified POS backup was found in $backupDirectory"
}

try {
    $health = Wait-PosHealth -TimeoutSeconds 5
    Write-Host "Application health: OK ($($health.version))"
}
catch {
    Write-Warning "Application health: unavailable"
    exit 1
}
