Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$pythonExe = $null
$preferredPythonCandidates = @(
  "C:\Users\arezs\AppData\Local\Python\pythoncore-3.14-64\python.exe",
  (Join-Path $env:LOCALAPPDATA "Python\pythoncore-3.14-64\python.exe")
)
foreach ($candidate in $preferredPythonCandidates) {
  if (Test-Path $candidate) {
    $pythonExe = $candidate
    break
  }
}
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { $pythonCommand = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pythonCommand) {
  $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (Test-Path $codexPython) { $pythonExe = $codexPython }
}
if (-not $pythonExe -and $pythonCommand) { $pythonExe = $pythonCommand.Source }
if (-not $pythonExe) { throw "No se encontro Python. Instale Python 3.12+." }

& $pythonExe -c "import tkinter, _tkinter"
if ($LASTEXITCODE -ne 0) { throw "Python sin Tkinter. Use python.org." }

function Invoke-PythonStep {
  param([string[]] $Arguments)
  & $pythonExe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Fallo: $pythonExe $($Arguments -join ' ')" }
}

$pythonRoot = Split-Path $pythonExe -Parent
$tclRoot = Join-Path $pythonRoot "tcl"
$tclLibrary = Join-Path $tclRoot "tcl8.6"
$tkLibrary = Join-Path $tclRoot "tk8.6"
$tclDll = Join-Path $pythonRoot "DLLs\tcl86t.dll"
$tkDll = Join-Path $pythonRoot "DLLs\tk86t.dll"
$iconPath = Join-Path $Root "assets\Arezone.ico"
$configDir = Join-Path $Root "config"
$assetsDir = Join-Path $Root "assets"
$mainScript = Join-Path $Root "main.py"
$hooksDir = Join-Path $Root "hooks"
if (Test-Path $tclLibrary) { $env:TCL_LIBRARY = $tclLibrary }
if (Test-Path $tkLibrary) { $env:TK_LIBRARY = $tkLibrary }
if (!(Test-Path $tclLibrary) -or !(Test-Path $tkLibrary)) {
  throw "No se encontraron Tcl/Tk en $tclRoot."
}

$stagingDir = Join-Path $Root "build_output\staging\app"
New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null

$pyinstallerArgs = @(
  "-m", "PyInstaller", "--noconfirm", "--clean",
  "--specpath", "build", "--distpath", $stagingDir,
  "--additional-hooks-dir", $hooksDir,
  "--windowed", "--onefile", "--name", "AREZONE",
  "--hidden-import", "tkinter", "--hidden-import", "_tkinter"
)
if (Test-Path $tclDll) { $pyinstallerArgs += @("--add-binary", "$tclDll;.") }
if (Test-Path $tkDll) { $pyinstallerArgs += @("--add-binary", "$tkDll;.") }
if (Test-Path $tclLibrary) { $pyinstallerArgs += @("--add-data", "$tclLibrary;_tcl_data") }
if (Test-Path $tkLibrary) { $pyinstallerArgs += @("--add-data", "$tkLibrary;_tk_data") }
if (Test-Path $iconPath) { $pyinstallerArgs += @("--icon", $iconPath) }
$pyinstallerArgs += @(
  "--add-data", "$configDir;config",
  "--add-data", "$assetsDir;assets",
  $mainScript
)
Invoke-PythonStep $pyinstallerArgs
Write-Host "EXE: $stagingDir\AREZONE.exe"
