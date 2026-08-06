Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Test-PythonForTkBuild {
  param([string] $Candidate)

  if (-not (Test-Path $Candidate)) { return $false }

  $pythonRoot = Split-Path $Candidate -Parent
  $tclLibrary = Join-Path $pythonRoot "tcl\tcl8.6"
  $tkLibrary = Join-Path $pythonRoot "tcl\tk8.6"
  if (-not (Test-Path $tclLibrary)) { return $false }
  if (-not (Test-Path $tkLibrary)) { return $false }

  & $Candidate -c "import tkinter, _tkinter" 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Get-BuildPython {
  $candidates = @()
  $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) { $candidates += $venvPython }
  $candidates += (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")

  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) { $candidates += $pythonCommand.Source }

  $pyCommand = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCommand) {
    $pyList = & py -0p 2>$null
    if ($pyList) {
      foreach ($line in $pyList) {
        if ($line -match '\s+(.+\\python\.exe)\s*$') {
          $candidates += $Matches[1].Trim()
        }
      }
    }
  }

  $seen = @{}
  foreach ($candidate in $candidates) {
    if (-not $candidate -or $seen.ContainsKey($candidate)) { continue }
    $seen[$candidate] = $true
    if (Test-PythonForTkBuild $candidate) {
      return $candidate
    }
  }

  throw @"
No se encontro Python apto para compilar AREZONE.
Use Python 3.12 de python.org con carpetas tcl\tcl8.6 y tcl\tk8.6.
Python 3.14 embebido (zipfs) no sirve para PyInstaller + tkinter.
"@
}

function Invoke-PythonStep {
  param([string[]] $Arguments)
  & $pythonExe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Fallo: $pythonExe $($Arguments -join ' ')" }
}

function Test-ExeHasTclData {
  param(
    [Parameter(Mandatory = $true)][string] $ExePath,
    [Parameter(Mandatory = $true)][string] $PythonExe
  )

  $listing = & $PythonExe -m PyInstaller.utils.cliutils.archive_viewer $ExePath --list 2>&1
  if ($LASTEXITCODE -ne 0) { throw "No se pudo inspeccionar el ejecutable generado." }
  return ($listing -match '_tcl_data\\')
}

$pythonExe = Get-BuildPython
$pythonRoot = Split-Path $pythonExe -Parent
$tclLibrary = Join-Path $pythonRoot "tcl\tcl8.6"
$tkLibrary = Join-Path $pythonRoot "tcl\tk8.6"
$iconPath = Join-Path $Root "assets\Arezone.ico"
$configDir = Join-Path $Root "config"
$assetsDir = Join-Path $Root "assets"
$mainScript = Join-Path $Root "main.py"

$env:TCL_LIBRARY = $tclLibrary
$env:TK_LIBRARY = $tkLibrary

Write-Host "Python de compilacion: $pythonExe"

$releaseApp = Join-Path $Root "release\app"
New-Item -ItemType Directory -Force -Path $releaseApp | Out-Null
$pyinstallerArgs = @(
  "-m", "PyInstaller", "--noconfirm", "--clean",
  "--specpath", "build", "--distpath", $releaseApp,
  "--windowed", "--onefile", "--name", "AREZONE",
  "--hidden-import", "tkinter", "--hidden-import", "_tkinter",
  "--hidden-import", "speech_recognition",
  "--add-data", "$configDir;config",
  "--add-data", "$assetsDir;assets"
)

$tclLibraryDir = Join-Path (Split-Path $pythonExe -Parent) "tcl"
if (Test-Path $tclLibraryDir) {
  $pyinstallerArgs += @("--add-data", "$tclLibraryDir;_tcl_data")
}

try {
  & $pythonExe -c "import importlib; importlib.import_module('pyaudio')" > $null 2>&1
  if ($LASTEXITCODE -eq 0) {
    $pyinstallerArgs += @("--hidden-import", "pyaudio")
  }
} catch {
  # PyAudio no está instalado en el entorno de compilación; no se agrega import oculto.
}

if (Test-Path $iconPath) { $pyinstallerArgs += @("--icon", $iconPath) }
$pyinstallerArgs += $mainScript

Invoke-PythonStep $pyinstallerArgs

$builtExe = Join-Path $releaseApp "AREZONE.exe"
if (!(Test-Path $builtExe)) { throw "No se genero AREZONE.exe." }
if (!(Test-ExeHasTclData -ExePath $builtExe -PythonExe $pythonExe)) {
  throw "AREZONE.exe se genero sin datos Tcl/Tk (_tcl_data). Revise la instalacion de Python."
}

Write-Host "EXE: $builtExe"
