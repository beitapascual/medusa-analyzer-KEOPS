param(
    [switch]$SkipInstall,
    [switch]$NoZip
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$venvDir = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Set-Location $projectRoot

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating .venv with Python 3.13..."
    & py -3.13 -m venv $venvDir
}

$pythonVersion = & $venvPython --version
& $venvPython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The build environment must use Python 3.13. Current .venv uses $pythonVersion."
}

if (-not $SkipInstall) {
    Write-Host "Installing runtime dependencies..."
    & $venvPython -m pip install -r requirements.txt

    Write-Host "Installing build dependencies..."
    & $venvPython -m pip install -r requirements-build.txt
}

Write-Host "Building MedusaAnalyzer..."
& $venvPython -m PyInstaller --clean --noconfirm main.spec

$distDir = Join-Path $projectRoot "dist\MedusaAnalyzer"
$exePath = Join-Path $distDir "MedusaAnalyzer.exe"
if (-not (Test-Path $exePath)) {
    throw "Build finished, but $exePath was not created."
}

if (-not $NoZip) {
    $zipPath = Join-Path $projectRoot "dist\MedusaAnalyzer-windows-x64.zip"
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $distDir "*") -DestinationPath $zipPath
    Write-Host "Package created: $zipPath"
}

Write-Host "Executable created: $exePath"
