Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:PosRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Get-PosRoot {
    return $script:PosRoot
}

function Assert-PosCommand {
    param([Parameter(Mandatory)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found."
    }
}

function Invoke-PosNative {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter()][string[]]$Arguments = @()
    )
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 wraps native stderr as ErrorRecord objects. Compose writes normal
        # progress to stderr, so use the native exit code as the authority instead of terminating on
        # those progress records.
        $ErrorActionPreference = "Continue"
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    $normalizedOutput = @(
        $output | ForEach-Object {
            if ($_ -is [Management.Automation.ErrorRecord]) {
                $_.Exception.Message
            }
            else {
                $_.ToString()
            }
        }
    )
    if ($exitCode -ne 0) {
        $details = ($normalizedOutput | Out-String).Trim()
        throw "Command failed ($exitCode): $FilePath $($Arguments -join ' ')`n$details"
    }
    return $normalizedOutput
}

function Invoke-PosCompose {
    param([Parameter()][string[]]$Arguments = @())
    Push-Location $script:PosRoot
    try {
        return Invoke-PosNative -FilePath "docker" -Arguments (@("compose") + $Arguments)
    }
    finally {
        Pop-Location
    }
}

function Get-PosEnvPath {
    $path = Join-Path $script:PosRoot ".env"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Production configuration is missing: $path"
    }
    return $path
}

function Get-PosEnvValue {
    param(
        [Parameter(Mandatory)][string]$Name,
        [switch]$Required
    )
    $path = Get-PosEnvPath
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        if ($line -match "^\s*$([regex]::Escape($Name))=(.*)$") {
            $value = $Matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            if ($Required -and [string]::IsNullOrWhiteSpace($value)) {
                throw "Required configuration value $Name is empty."
            }
            return $value
        }
    }
    if ($Required) {
        throw "Required configuration value $Name is missing from $path."
    }
    return $null
}

function Set-PosEnvValue {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Value
    )
    if ($Value -match "[`r`n]") {
        throw "Configuration values cannot contain newlines."
    }
    $path = Get-PosEnvPath
    $lines = [Collections.Generic.List[string]]::new()
    $found = $false
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        if ($line -match "^\s*$([regex]::Escape($Name))=") {
            if (-not $found) {
                $lines.Add("$Name=$Value")
                $found = $true
            }
        }
        else {
            $lines.Add($line)
        }
    }
    if (-not $found) {
        $lines.Add("$Name=$Value")
    }
    [IO.File]::WriteAllLines($path, $lines, $script:Utf8NoBom)
}

function Assert-PosVersion {
    param([Parameter(Mandatory)][string]$Version)
    if ($Version -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
        throw "Invalid version '$Version'. Use 1-64 letters, numbers, dots, underscores, or hyphens."
    }
}

function Resolve-PosSafeDirectory {
    param(
        [Parameter(Mandatory)][string]$Path,
        [switch]$Create
    )
    $candidate = $Path
    if (-not [IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $script:PosRoot $candidate
    }
    $resolved = [IO.Path]::GetFullPath($candidate).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $driveRoot = [IO.Path]::GetPathRoot($resolved).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $userRoot = [IO.Path]::GetFullPath([Environment]::GetFolderPath("UserProfile")).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $repoRoot = $script:PosRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($resolved -eq $driveRoot -or $resolved -eq $userRoot -or $resolved -eq $repoRoot) {
        throw "Refusing broad operational directory: $resolved"
    }
    if ($Create -and -not (Test-Path -LiteralPath $resolved)) {
        New-Item -ItemType Directory -Path $resolved -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "Directory does not exist: $resolved"
    }
    return $resolved
}

function Get-PosDatabaseContainer {
    $result = Invoke-PosCompose -Arguments @("ps", "-q", "db")
    $containerId = (($result | Out-String).Trim() -split "`r?`n")[0]
    if ([string]::IsNullOrWhiteSpace($containerId)) {
        throw "The POS database container is not running."
    }
    return $containerId
}

function Wait-PosHealth {
    param([int]$TimeoutSeconds = 120)
    $port = Get-PosEnvValue -Name "POS_APP_PORT"
    if ([string]::IsNullOrWhiteSpace($port)) { $port = "8000" }
    $uri = "http://127.0.0.1:$port/health/"
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                return ($response.Content | ConvertFrom-Json)
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "POS did not become healthy at $uri within $TimeoutSeconds seconds."
}

function Enter-PosDeploymentLock {
    $stateDir = Resolve-PosSafeDirectory -Path "var/deployment" -Create
    $lockPath = Join-Path $stateDir "operation.lock"
    try {
        return [IO.File]::Open($lockPath, "OpenOrCreate", "ReadWrite", "None")
    }
    catch {
        throw "Another POS deployment operation is already running."
    }
}

function Write-PosDeploymentState {
    param([Parameter(Mandatory)][hashtable]$State)
    $stateDir = Resolve-PosSafeDirectory -Path "var/deployment" -Create
    $path = Join-Path $stateDir "state.json"
    $json = $State | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($path, $json, $script:Utf8NoBom)
}

function Read-PosRelease {
    param([Parameter(Mandatory)][string]$ReleaseDirectory)
    $directory = Resolve-Path -LiteralPath $ReleaseDirectory -ErrorAction Stop
    $manifestPath = Join-Path $directory.Path "release.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Release manifest not found: $manifestPath"
    }
    $release = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($release.schema_version -ne 1) { throw "Unsupported release manifest schema." }
    Assert-PosVersion -Version ([string]$release.app_version)
    $imagePath = [IO.Path]::GetFullPath((Join-Path $directory.Path ([string]$release.image_file)))
    $prefix = $directory.Path.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $imagePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Release image path escapes its package directory."
    }
    if (-not (Test-Path -LiteralPath $imagePath -PathType Leaf)) {
        throw "Release image not found: $imagePath"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$release.sha256).ToLowerInvariant()) {
        throw "Release image checksum does not match release.json."
    }
    return [pscustomobject]@{
        Directory = $directory.Path
        Version = [string]$release.app_version
        Image = [string]$release.image
        ImagePath = $imagePath
        Manifest = $release
    }
}

function Import-PosReleaseImage {
    param([Parameter(Mandatory)]$Release)
    Invoke-PosNative -FilePath "docker" -Arguments @("image", "load", "--input", $Release.ImagePath) | Out-Host
    Invoke-PosNative -FilePath "docker" -Arguments @("image", "inspect", $Release.Image) | Out-Null
}

function Assert-PosPrerequisites {
    Assert-PosCommand -Name "docker"
    Invoke-PosNative -FilePath "docker" -Arguments @("version", "--format", "{{.Server.Version}}") | Out-Null
    Invoke-PosNative -FilePath "docker" -Arguments @("compose", "version") | Out-Null
    Get-PosEnvPath | Out-Null
    foreach ($name in @("DJANGO_SECRET_KEY", "POSTGRES_ADMIN_USER", "POSTGRES_ADMIN_PASSWORD", "POS_DB_NAME", "POS_DB_USER", "POS_DB_PASSWORD")) {
        Get-PosEnvValue -Name $name -Required | Out-Null
    }
}

Export-ModuleMember -Function *-Pos*
