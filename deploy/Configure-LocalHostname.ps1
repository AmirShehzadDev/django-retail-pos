[CmdletBinding()]
param(
    [switch]$SkipDesktopLauncher,
    [switch]$NoWebRestart,
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Add-PosCsvSetting {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Value
    )
    $existing = Get-PosEnvValue -Name $Name
    $items = @(
        $existing -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    )
    if ($items -notcontains $Value) {
        Set-PosEnvValue -Name $Name -Value (($items + $Value) -join ",")
    }
}

if (-not (Test-Administrator)) {
    if ($Elevated) {
        throw "Administrator approval is required to configure the Windows hosts file."
    }
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-Elevated"
    )
    if ($SkipDesktopLauncher) { $arguments += "-SkipDesktopLauncher" }
    if ($NoWebRestart) { $arguments += "-NoWebRestart" }
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Verb RunAs -Wait -PassThru
    exit $process.ExitCode
}

Assert-PosEnvironmentFile
$hostname = Get-PosEnvValue -Name "POS_LOCAL_HOSTNAME"
if ([string]::IsNullOrWhiteSpace($hostname)) { $hostname = "retailpos" }
$hostname = $hostname.Trim().ToLowerInvariant()
if ($hostname -notmatch "^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$") {
    throw "POS_LOCAL_HOSTNAME must be a lowercase single-label hostname."
}

$port = Get-PosEnvValue -Name "POS_APP_PORT"
if ([string]::IsNullOrWhiteSpace($port)) { $port = "8000" }
if ($port -notmatch "^[0-9]{1,5}$" -or [int]$port -lt 1 -or [int]$port -gt 65535) {
    throw "POS_APP_PORT must be a valid TCP port."
}

$hostsPath = Join-Path $env:SystemRoot "System32/drivers/etc/hosts"
$hostsContent = [IO.File]::ReadAllText($hostsPath)
$matchingAddresses = [Collections.Generic.List[string]]::new()
foreach ($line in ($hostsContent -split "`r?`n")) {
    $content = ($line -split "#", 2)[0].Trim()
    if (-not $content) { continue }
    $parts = @($content -split "\s+" | Where-Object { $_ })
    if ($parts.Count -lt 2) { continue }
    foreach ($name in $parts[1..($parts.Count - 1)]) {
        if ($name.Equals($hostname, [StringComparison]::OrdinalIgnoreCase)) {
            $matchingAddresses.Add($parts[0])
        }
    }
}

$conflicts = @($matchingAddresses | Where-Object { $_ -ne "127.0.0.1" })
if ($conflicts.Count -gt 0) {
    throw "The hostname '$hostname' is already mapped to another address in the Windows hosts file."
}
if ($matchingAddresses.Count -eq 0) {
    $separator = if ($hostsContent -and -not $hostsContent.EndsWith("`n")) { "`r`n" } else { "" }
    [IO.File]::AppendAllText(
        $hostsPath,
        "${separator}127.0.0.1`t$hostname`t# Retail POS`r`n",
        (New-Object Text.UTF8Encoding($false))
    )
}

Set-PosEnvValue -Name "POS_LOCAL_HOSTNAME" -Value $hostname
Add-PosCsvSetting -Name "DJANGO_ALLOWED_HOSTS" -Value $hostname
Add-PosCsvSetting -Name "DJANGO_CSRF_TRUSTED_ORIGINS" -Value "http://${hostname}:$port"
Invoke-PosNative -FilePath "ipconfig" -Arguments @("/flushdns") | Out-Null

if (-not $SkipDesktopLauncher) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        throw "The Windows Desktop folder could not be resolved."
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "Start-Retail-POS.cmd") `
        -Destination (Join-Path $desktop "Start Retail POS.cmd") -Force
}

$webRestarted = $false
if (-not $NoWebRestart) {
    try {
        Invoke-PosNative -FilePath "docker" -Arguments @("info") | Out-Null
        $webOutput = Invoke-PosCompose -Arguments @("ps", "-q", "web")
        $webIds = @(
            $webOutput | ForEach-Object { $_.Trim() } |
                Where-Object { $_ -match "^[0-9a-fA-F]{12,64}$" }
        )
        if ($webIds.Count -gt 0) {
            Invoke-PosCompose -Arguments @("up", "-d", "--no-build", "--force-recreate", "web") | Out-Host
            Wait-PosHealth | Out-Null
            $webRestarted = $true
        }
    }
    catch {
        Write-Warning "Hostname configuration succeeded, but the running web container was not restarted: $($_.Exception.Message)"
    }
}

Write-Host "Local POS hostname configured: http://${hostname}:$port"
if (-not $SkipDesktopLauncher) { Write-Host "Desktop launcher installed: Start Retail POS.cmd" }
if ($webRestarted) { Write-Host "The POS web container was recreated and is healthy." }

