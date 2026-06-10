Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_exe.ps1")
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_installer_dotnet.ps1")

$releaseRoot = Join-Path $Root "release"
$appDir = Join-Path $releaseRoot "app"
$instDir = Join-Path $releaseRoot "instalador"
New-Item -ItemType Directory -Force -Path $appDir, $instDir | Out-Null

Copy-Item -Force (Join-Path $Root "build_output\staging\app\AREZONE.exe") (Join-Path $appDir "AREZONE.exe")
Copy-Item -Force (Join-Path $Root "installer\output\Instalador_AREZONE.exe") (Join-Path $instDir "Instalador_AREZONE.exe")

Write-Host ""
Write-Host "EXE listos:"
Write-Host "  POS:       $appDir\AREZONE.exe"
Write-Host "  Setup:     $instDir\Instalador_AREZONE.exe"
