[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ReleaseDirectory,
    [switch]$InstallDailyBackupTask,
    [string]$BackupTime = "23:00"
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force
$lock = Enter-PosDeploymentLock
$priorVersion = $null

try {
    Assert-PosPrerequisites
    $release = Read-PosRelease -ReleaseDirectory $ReleaseDirectory
    $priorVersion = Get-PosEnvValue -Name "POS_APP_VERSION"
    Import-PosReleaseImage -Release $release
    Set-PosEnvValue -Name "POS_APP_VERSION" -Value $release.Version

    Invoke-PosCompose -Arguments @("up", "-d", "db") | Out-Host
    Invoke-PosCompose -Arguments @("run", "--rm", "web", "python", "manage.py", "migrate", "--noinput") | Out-Host
    Invoke-PosCompose -Arguments @("run", "--rm", "web", "python", "manage.py", "check", "--deploy") | Out-Host
    Invoke-PosCompose -Arguments @("up", "-d", "--no-build", "web") | Out-Host
    $health = Wait-PosHealth
    Write-PosDeploymentState -State @{
        status = "installed"
        current_version = $release.Version
        installed_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    if ($InstallDailyBackupTask) {
        & (Join-Path $PSScriptRoot "Install-BackupTask.ps1") -At $BackupTime
    }
    Write-Host "Retail POS $($health.version) installed and healthy."
    Write-Host "Create the first owner separately if this is a new database: docker compose run --rm web python manage.py createsuperuser"
}
catch {
    if (-not [string]::IsNullOrWhiteSpace($priorVersion)) {
        Set-PosEnvValue -Name "POS_APP_VERSION" -Value $priorVersion
    }
    throw
}
finally {
    $lock.Dispose()
}
