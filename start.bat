@echo off
setlocal
if /I "%~1"=="--check" goto check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch.ps1"
set "launchResult=%errorlevel%"
if not "%launchResult%"=="0" pause
exit /b %launchResult%
:check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch.ps1" -CheckOnly
exit /b %errorlevel%
