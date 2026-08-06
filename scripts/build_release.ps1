Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Stop-ArezoneProcesses {
  $processes = Get-Process -Name "AREZONE" -ErrorAction SilentlyContinue
  if (-not $processes) { return }

  Write-Host "Cerrando AREZONE en ejecucion..."
  $processes | Stop-Process -Force
  Start-Sleep -Seconds 1
}

function Copy-ReleaseFile {
  param(
    [Parameter(Mandatory = $true)][string] $Source,
    [Parameter(Mandatory = $true)][string] $Destination
  )

  for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
      Copy-Item -Force -Path $Source -Destination $Destination
      return
    } catch {
      if ($attempt -eq 3) { throw }
      Stop-ArezoneProcesses
      Start-Sleep -Seconds 1
    }
  }
}

Stop-ArezoneProcesses

& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_exe.ps1")
if ($LASTEXITCODE -ne 0) { throw "No se pudo generar AREZONE.exe." }
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_installer_dotnet.ps1")
if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el instalador." }

$releaseRoot = Join-Path $Root "release"
$appDir = Join-Path $releaseRoot "app"
$instDir = Join-Path $releaseRoot "instalador"
New-Item -ItemType Directory -Force -Path $appDir, $instDir | Out-Null

Stop-ArezoneProcesses

if (!(Test-Path (Join-Path $Root "release\app\AREZONE.exe"))) {
  throw "No existe AREZONE.exe en release\\app. Revise scripts/build_exe.ps1"
}
Copy-ReleaseFile `
  -Source (Join-Path $Root "installer\output\Instalador_AREZONE.exe") `
  -Destination (Join-Path $instDir "Instalador_AREZONE.exe")

Write-Host ""
Write-Host "EXE listos:"
Write-Host "  POS:       $appDir\AREZONE.exe"
Write-Host "  Setup:     $instDir\Instalador_AREZONE.exe"
