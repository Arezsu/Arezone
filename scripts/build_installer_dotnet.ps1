Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$DistExe = Join-Path $Root "release\app\AREZONE.exe"
$OutputDir = Join-Path $Root "installer\output"
$OutputExe = Join-Path $OutputDir "Instalador_AREZONE.exe"
$Source = Join-Path $Root "installer\InstallerStub.cs"
$Manifest = Join-Path $Root "installer\installer.manifest"
$Rsp = Join-Path $OutputDir "installer_build.rsp"
$IconPath = Join-Path $Root "assets\Arezone.ico"
$Csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (!(Test-Path $Csc)) { $Csc = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe" }
if (!(Test-Path $Csc)) { throw "No se encontro csc.exe." }
if (!(Test-Path $DistExe)) { throw "Falta AREZONE.exe. Ejecute 3_COMPILAR_INSTALADOR.bat o scripts\build_exe.ps1" }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

@(
  "/nologo", "/target:winexe", "/optimize+",
  "/out:`"$OutputExe`"",
  "/resource:`"$DistExe`",AREZONE.exe",
  "/win32manifest:`"$Manifest`"",
  "/reference:System.Windows.Forms.dll",
  "`"$Source`""
) | Set-Content -Path $Rsp -Encoding ASCII
if (Test-Path $IconPath) { Add-Content -Path $Rsp -Value "/win32icon:`"$IconPath`"" }
& $Csc "@$Rsp"
if (!(Test-Path $OutputExe)) { throw "No se genero: $OutputExe" }

Write-Host "Instalador: $OutputExe"
