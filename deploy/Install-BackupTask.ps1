[CmdletBinding()]
param(
    [ValidatePattern("^(?:[01]\d|2[0-3]):[0-5]\d$")][string]$At = "23:00",
    [string]$TaskName = "Retail POS Daily Backup"
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force

Assert-PosCommand -Name "powershell.exe"
foreach ($command in @("New-ScheduledTaskAction", "New-ScheduledTaskTrigger", "New-ScheduledTaskPrincipal", "Register-ScheduledTask")) {
    Assert-PosCommand -Name $command
}

$backupScript = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "Backup-Database.ps1")).Path
$arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$backupScript`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory (Get-PosRoot)
$scheduledTime = [DateTime]::ParseExact($At, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
$trigger = New-ScheduledTaskTrigger -Daily -At $scheduledTime
$userId = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Write-Host "Scheduled '$TaskName' daily at $At for $userId."
Write-Warning "The Windows account must remain signed in and Docker Desktop must be running at backup time. Run the task once now and verify its output."
