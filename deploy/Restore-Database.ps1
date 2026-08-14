[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BackupPath,
    [Parameter(Mandatory)][switch]$ConfirmDataReplacement,
    [int]$HealthTimeoutSeconds = 120,
    [switch]$SkipDeploymentLock
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force
$lock = if ($SkipDeploymentLock) { $null } else { Enter-PosDeploymentLock }
$containerTemp = "/tmp/pos-restore-$PID.dump"

try {
    if (-not $ConfirmDataReplacement) {
        throw "Restore requires -ConfirmDataReplacement because it replaces the configured POS database."
    }
    Assert-PosPrerequisites
    $resolvedBackup = (Resolve-Path -LiteralPath $BackupPath -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath $resolvedBackup -PathType Leaf)) {
        throw "Backup file does not exist: $resolvedBackup"
    }
    $databaseName = Get-PosEnvValue -Name "POS_DB_NAME" -Required
    $databaseUser = Get-PosEnvValue -Name "POS_DB_USER" -Required
    foreach ($identifier in @($databaseName, $databaseUser)) {
        if ($identifier -notmatch "^[A-Za-z_][A-Za-z0-9_]{0,62}$") {
            throw "Database names and roles must be safe PostgreSQL identifiers before restore."
        }
    }

    Invoke-PosCompose -Arguments @("up", "-d", "db") | Out-Host
    $containerId = Get-PosDatabaseContainer
    Invoke-PosNative -FilePath "docker" -Arguments @("cp", $resolvedBackup, "${containerId}:${containerTemp}") | Out-Null
    Invoke-PosCompose -Arguments @("exec", "-T", "db", "pg_restore", "--list", $containerTemp) | Out-Null

    Invoke-PosCompose -Arguments @("stop", "web") | Out-Host
    $restoreCommand = 'PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" dropdb --username="$POSTGRES_ADMIN_USER" --force --if-exists "$POS_DB_NAME" && PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" createdb --username="$POSTGRES_ADMIN_USER" --owner="$POS_DB_USER" "$POS_DB_NAME" && PGPASSWORD="$POS_DB_PASSWORD" pg_restore --username="$POS_DB_USER" --dbname="$POS_DB_NAME" --exit-on-error --no-owner "$1"'
    Invoke-PosCompose -Arguments @("exec", "-T", "db", "sh", "-c", $restoreCommand, "--", $containerTemp) | Out-Null
    Invoke-PosCompose -Arguments @("run", "--rm", "web", "python", "manage.py", "migrate", "--noinput") | Out-Host
    Invoke-PosCompose -Arguments @("up", "-d", "--no-build", "web") | Out-Host
    $health = Wait-PosHealth -TimeoutSeconds $HealthTimeoutSeconds
    Write-Host "Database restored from $resolvedBackup. Retail POS $($health.version) is healthy."
}
catch {
    Write-Host "Restore failed. The web container remains stopped until the database is recovered: $($_.Exception.Message)" -ForegroundColor Red
    try { Invoke-PosCompose -Arguments @("stop", "web") | Out-Null } catch { }
    throw
}
finally {
    try { Invoke-PosCompose -Arguments @("exec", "-T", "db", "rm", "-f", $containerTemp) | Out-Null } catch { }
    if ($lock) { $lock.Dispose() }
}
