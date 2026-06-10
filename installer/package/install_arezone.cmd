@echo off
setlocal

set "APP_DIR=%ProgramFiles%\ArezOne"
set "EXE_NAME=AREZONE.exe"

if not exist "%APP_DIR%" mkdir "%APP_DIR%"
copy /Y "%~dp0%EXE_NAME%" "%APP_DIR%\%EXE_NAME%" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $start=[Environment]::GetFolderPath('Programs'); $target=Join-Path $env:ProgramFiles 'ArezOne\AREZONE.exe'; $lnk=$shell.CreateShortcut((Join-Path $desktop 'AREZONE.lnk')); $lnk.TargetPath=$target; $lnk.WorkingDirectory=(Split-Path $target); $lnk.Save(); $folder=Join-Path $start 'AREZONE'; New-Item -ItemType Directory -Force -Path $folder | Out-Null; $lnk2=$shell.CreateShortcut((Join-Path $folder 'AREZONE.lnk')); $lnk2.TargetPath=$target; $lnk2.WorkingDirectory=(Split-Path $target); $lnk2.Save()"

echo AREZONE instalado correctamente.
start "" "%APP_DIR%\%EXE_NAME%"
endlocal
