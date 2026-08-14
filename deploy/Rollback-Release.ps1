[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PreviousVersion,
    [Parameter(Mandatory)][string]$PreUpdateBackup,
    [Parameter(Mandatory)][switch]$ConfirmRollback
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force
$lock = Enter-PosDeploymentLock

try {
    if (-not $ConfirmRollback) { throw "Rollback requires -ConfirmRollback." }
    Assert-PosPrerequisites
    Assert-PosVersion -Version $PreviousVersion
    $imageName = Get-PosEnvValue -Name "POS_APP_IMAGE"
    if ([string]::IsNullOrWhiteSpace($imageName)) { $imageName = "pos-codex" }
    $image = "${imageName}:${PreviousVersion}"
    Invoke-PosNative -FilePath "docker" -Arguments @("image", "inspect", $image) | Out-Null

    $failedVersion = Get-PosEnvValue -Name "POS_APP_VERSION"
    Set-PosEnvValue -Name "POS_APP_VERSION" -Value $PreviousVersion
    & (Join-Path $PSScriptRoot "Restore-Database.ps1") -BackupPath $PreUpdateBackup -ConfirmDataReplacement -SkipDeploymentLock
    if ($LASTEXITCODE -ne 0) { throw "The restore command failed during rollback." }
    Write-PosDeploymentState -State @{
        status = "rolled_back"
        current_version = $PreviousVersion
        failed_version = $failedVersion
        restored_backup = (Resolve-Path -LiteralPath $PreUpdateBackup).Path
        changed_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    Write-Host "Rollback complete. Version $PreviousVersion is healthy."
}
finally {
    $lock.Dispose()
}
