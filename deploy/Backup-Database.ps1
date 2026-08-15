[CmdletBinding()]
param(
    [string]$Destination,
    [string]$ExternalCopyDestination,
    [ValidateRange(1, 365)][int]$RetentionDays = 0,
    [string]$Purpose = "daily",
    [switch]$SkipDeploymentLock
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force
$lock = if ($SkipDeploymentLock) { $null } else { Enter-PosDeploymentLock }
$containerTemp = "/tmp/pos-backup-$PID.dump"
$hostTemp = $null

try {
    Assert-PosPrerequisites
    if ([string]::IsNullOrWhiteSpace($Destination)) {
        $Destination = Get-PosEnvValue -Name "POS_BACKUP_DIR"
        if ([string]::IsNullOrWhiteSpace($Destination)) { $Destination = "var/backups" }
    }
    if ($RetentionDays -eq 0) {
        $configuredRetention = Get-PosEnvValue -Name "POS_BACKUP_RETENTION_DAYS"
        $RetentionDays = if ($configuredRetention) { [int]$configuredRetention } else { 7 }
    }
    $backupDirectory = Resolve-PosSafeDirectory -Path $Destination -Create
    $logDirectory = Resolve-PosSafeDirectory -Path "var/log" -Create
    $logPath = Join-Path $logDirectory "backup.log"
    $safePurpose = ($Purpose -replace "[^A-Za-z0-9_-]", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($safePurpose)) { $safePurpose = "manual" }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $finalPath = Join-Path $backupDirectory "pos-$stamp-$safePurpose.dump"
    $hostTemp = "$finalPath.partial"

    Invoke-PosCompose -Arguments @("up", "-d", "db") | Out-Host
    Wait-PosDatabase
    $containerId = Get-PosDatabaseContainer
    $dumpCommand = 'rm -f "$1" && PGPASSWORD="$POS_DB_PASSWORD" pg_dump --username="$POS_DB_USER" --dbname="$POS_DB_NAME" --format=custom --file="$1" && pg_restore --list "$1" >/dev/null'
    Invoke-PosCompose -Arguments @("exec", "-T", "db", "sh", "-c", $dumpCommand, "--", $containerTemp) | Out-Null
    Invoke-PosNative -FilePath "docker" -Arguments @("cp", "${containerId}:${containerTemp}", $hostTemp) | Out-Null
    if (-not (Test-Path -LiteralPath $hostTemp -PathType Leaf) -or (Get-Item -LiteralPath $hostTemp).Length -eq 0) {
        throw "Backup transfer did not create a non-empty file."
    }
    Move-Item -LiteralPath $hostTemp -Destination $finalPath
    $hostTemp = $null

    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem -LiteralPath $backupDirectory -File -Filter "pos-*.dump" |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force

    if (-not [string]::IsNullOrWhiteSpace($ExternalCopyDestination)) {
        $externalDirectory = Resolve-PosSafeDirectory -Path $ExternalCopyDestination -Create
        Copy-Item -LiteralPath $finalPath -Destination (Join-Path $externalDirectory (Split-Path $finalPath -Leaf))
    }
    "$(Get-Date -Format o) SUCCESS $finalPath" | Out-File -LiteralPath $logPath -Append -Encoding utf8
    Write-Host "Verified backup created: $finalPath"
    return $finalPath
}
catch {
    $fallbackLog = Join-Path (Get-PosRoot) "var/log/backup.log"
    $fallbackDirectory = Split-Path $fallbackLog -Parent
    if (-not (Test-Path -LiteralPath $fallbackDirectory)) { New-Item -ItemType Directory -Path $fallbackDirectory -Force | Out-Null }
    "$(Get-Date -Format o) FAILURE $($_.Exception.Message)" | Out-File -LiteralPath $fallbackLog -Append -Encoding utf8
    throw
}
finally {
    if ($hostTemp -and (Test-Path -LiteralPath $hostTemp)) { Remove-Item -LiteralPath $hostTemp -Force }
    try { Invoke-PosCompose -Arguments @("exec", "-T", "db", "rm", "-f", $containerTemp) | Out-Null } catch { }
    if ($lock) { $lock.Dispose() }
}
