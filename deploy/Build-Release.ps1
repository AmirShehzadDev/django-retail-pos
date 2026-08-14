[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Version,
    [string]$OutputDirectory = "releases",
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "PosDeployment.psm1") -Force
Assert-PosVersion -Version $Version
Assert-PosCommand -Name "docker"

$root = Get-PosRoot
$python = Join-Path $root ".venv/Scripts/python.exe"
$ruff = Join-Path $root ".venv/Scripts/ruff.exe"
if (-not $SkipChecks) {
    $dirty = (Invoke-PosNative -FilePath "git" -Arguments @("-C", $root, "status", "--porcelain") | Out-String).Trim()
    if ($dirty) { throw "Refusing a checked release from a dirty Git worktree. Commit the intended release first." }
    if (-not (Test-Path -LiteralPath $python)) { throw "Project virtual environment is missing: $python" }
    Push-Location $root
    try {
        Invoke-PosNative -FilePath "npm" -Arguments @("run", "css:build") | Out-Host
        Invoke-PosNative -FilePath $python -Arguments @("manage.py", "test") | Out-Host
        $javascriptTests = Get-ChildItem -Path (Join-Path $root "static/js") -Filter "*.test.js" | ForEach-Object { $_.FullName }
        Invoke-PosNative -FilePath "node" -Arguments (@("--test") + $javascriptTests) | Out-Host
        Invoke-PosNative -FilePath $ruff -Arguments @("check", ".") | Out-Host
        Invoke-PosNative -FilePath $python -Arguments @("manage.py", "makemigrations", "--check", "--dry-run") | Out-Host
    }
    finally {
        Pop-Location
    }
}

$outputRoot = Resolve-PosSafeDirectory -Path $OutputDirectory -Create
$releaseDirectory = Join-Path $outputRoot "pos-codex-$Version"
if (Test-Path -LiteralPath $releaseDirectory) {
    throw "Release directory already exists: $releaseDirectory"
}
New-Item -ItemType Directory -Path $releaseDirectory | Out-Null
$image = "pos-codex:$Version"
$revision = (Invoke-PosNative -FilePath "git" -Arguments @("-C", $root, "rev-parse", "HEAD") | Out-String).Trim()
Invoke-PosNative -FilePath "docker" -Arguments @("build", "--build-arg", "APP_VERSION=$Version", "--label", "org.opencontainers.image.revision=$revision", "--tag", $image, $root) | Out-Host
Invoke-PosNative -FilePath "docker" -Arguments @(
    "run", "--rm",
    "-e", "DJANGO_SECRET_KEY=release-check-secret-that-is-long-enough-1234567890",
    "-e", "DJANGO_ALLOWED_HOSTS=127.0.0.1",
    "-e", "POS_DB_NAME=release_check",
    "-e", "POS_DB_USER=release_check",
    "-e", "POS_DB_PASSWORD=release_check",
    $image, "python", "manage.py", "check", "--deploy", "--fail-level", "ERROR"
) | Out-Host

$imageFile = "pos-codex-$Version.tar"
$imagePath = Join-Path $releaseDirectory $imageFile
Invoke-PosNative -FilePath "docker" -Arguments @("image", "save", "--output", $imagePath, $image) | Out-Host
$checksum = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash.ToLowerInvariant()
$manifest = [ordered]@{
    schema_version = 1
    app_version = $Version
    image = $image
    image_file = $imageFile
    sha256 = $checksum
    git_revision = $revision
    built_at = (Get-Date).ToUniversalTime().ToString("o")
}
[IO.File]::WriteAllText((Join-Path $releaseDirectory "release.json"), ($manifest | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))

$runtime = Join-Path $releaseDirectory "runtime"
New-Item -ItemType Directory -Path $runtime | Out-Null
Copy-Item -LiteralPath (Join-Path $root "compose.yaml") -Destination $runtime
Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination $runtime
Copy-Item -LiteralPath (Join-Path $root "deploy") -Destination $runtime -Recurse
$postgresRuntime = Join-Path $runtime "docker/postgres"
New-Item -ItemType Directory -Path (Split-Path $postgresRuntime -Parent) -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root "docker/postgres") -Destination $postgresRuntime -Recurse
$zipPath = "$releaseDirectory.zip"
Compress-Archive -Path (Join-Path $releaseDirectory "*") -DestinationPath $zipPath
Write-Host "Release created: $releaseDirectory"
Write-Host "Transfer package: $zipPath"
