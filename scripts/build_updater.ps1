Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$SourceExe = Join-Path $Root "release\app\AREZONE.exe"
$TargetDir = Join-Path $Root "release\app\update"
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
if (!(Test-Path $SourceExe)) {
  throw "No existe $SourceExe. Ejecute primero scripts/build_exe.ps1"
}
Copy-Item $SourceExe -Destination (Join-Path $TargetDir "AREZONE.exe") -Force
$pythonExe = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $pythonExe)) { throw "No existe $pythonExe." }
& $pythonExe -m PyInstaller --noconfirm --clean --distpath $TargetDir --workpath (Join-Path $Root "build\updater") --specpath (Join-Path $Root "build") --windowed --onefile --name AREZONE_Updater "scripts\updater.py"
Write-Host "Updater listo en $TargetDir"
