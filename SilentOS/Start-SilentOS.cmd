@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-SilentOS.ps1" %*
if errorlevel 1 pause
