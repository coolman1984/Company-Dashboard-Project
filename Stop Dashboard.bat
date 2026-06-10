@echo off
REM Stops the Company Dashboard server started from THIS folder only.
REM Other node.exe processes on the PC are not touched.
setlocal
title Stop Company Dashboard
set "DASHDIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$dir = $env:DASHDIR.TrimEnd('\');" ^
  "$procs = Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -like '*server.js*' -and ($_.CommandLine -like ($dir + '*') -or $_.ExecutablePath -like ($dir + '*')) };" ^
  "if ($procs) { $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('Stopped PID ' + $_.ProcessId) } } else { Write-Host 'Dashboard server is not running.' }"
ping -n 3 127.0.0.1 >nul
exit /b 0
