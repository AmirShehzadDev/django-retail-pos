[CmdletBinding()]
param([Parameter(Mandatory)][string]$ReleaseDirectory)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force
$lock = Enter-PosDeploymentLock
$backupPath = $null
$priorVersion = $null
$migrationAttempted = $false

try {
    Assert-PosPrerequisites
    $release = Read-PosRelease -ReleaseDirectory $ReleaseDirectory
    $priorVersion = Get-PosEnvValue -Name "POS_APP_VERSION"
    if ($priorVersion -eq $release.Version) {
        Write-Host "Retail POS $($release.Version) is already selected; no update was applied."
        return
    }
    Import-PosReleaseImage -Release $release
    $backupPath = & (Join-Path $PSScriptRoot "Backup-Database.ps1") -Purpose "pre-update-$($release.Version)" -SkipDeploymentLock
    if (-not $backupPath) { throw "The mandatory pre-update backup did not return a file path." }

    Invoke-PosCompose -Arguments @("stop", "web") | Out-Host
    Set-PosEnvValue -Name "POS_APP_VERSION" -Value $release.Version
    $migrationAttempted = $true
    Invoke-PosCompose -Arguments @("run", "--rm", "web", "python", "manage.py", "migrate", "--noinput") | Out-Host
    Invoke-PosCompose -Arguments @("up", "-d", "--no-build", "web") | Out-Host
    $health = Wait-PosHealth
    Write-PosDeploymentState -State @{
        status = "updated"
        previous_version = $priorVersion
        current_version = $release.Version
        pre_update_backup = [string]$backupPath
        changed_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    Write-Host "Update complete. Retail POS $($health.version) is healthy."
    Write-Host "Pre-update backup retained: $backupPath"
}
catch {
    if (-not [string]::IsNullOrWhiteSpace($priorVersion)) {
        Set-PosEnvValue -Name "POS_APP_VERSION" -Value $priorVersion
    }
    try { Invoke-PosCompose -Arguments @("stop", "web") | Out-Null } catch { }
    Write-Host "Update failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($migrationAttempted -and $backupPath) {
        Write-Host "The prior version was reselected but was not started because a migration was attempted."
        Write-Host "Recover with: .\deploy\Rollback-Release.ps1 -PreviousVersion '$priorVersion' -PreUpdateBackup '$backupPath' -ConfirmRollback"
    }
    elseif (-not [string]::IsNullOrWhiteSpace($priorVersion)) {
        Write-Host "No migration was attempted. Start the prior version with: .\deploy\Start-POS.ps1"
    }
    throw
}
finally {
    $lock.Dispose()
}
