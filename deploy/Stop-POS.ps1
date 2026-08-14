[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force

Assert-PosCommand -Name "docker"
Invoke-PosCompose -Arguments @("stop", "web", "db") | Out-Host
Write-Host "Retail POS containers stopped. Data and backups were retained."
