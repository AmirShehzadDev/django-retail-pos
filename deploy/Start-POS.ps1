[CmdletBinding()]
param([int]$HealthTimeoutSeconds = 120)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force

Assert-PosPrerequisites
Invoke-PosCompose -Arguments @("up", "-d", "db") | Out-Host
Invoke-PosCompose -Arguments @("up", "-d", "--no-build", "web") | Out-Host
$health = Wait-PosHealth -TimeoutSeconds $HealthTimeoutSeconds
$port = Get-PosEnvValue -Name "POS_APP_PORT"
if ([string]::IsNullOrWhiteSpace($port)) { $port = "8000" }
Write-Host "Retail POS $($health.version) is healthy at http://127.0.0.1:$port/"
