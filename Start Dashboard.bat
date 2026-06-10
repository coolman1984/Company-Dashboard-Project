@echo off
REM ============================================================
REM  Company Dashboard - One-Click Launcher (fully portable)
REM  Uses the bundled Node.js runtime (runtime\node.exe) so this
REM  works on any Windows 11 PC with no installation required.
REM ============================================================
setlocal EnableDelayedExpansion
title Company Dashboard Launcher
cd /d "%~dp0"

REM -- Pick the Node runtime: bundled first, system Node as fallback
set "NODE=%~dp0runtime\node.exe"
if not exist "!NODE!" (
    where node >nul 2>nul
    if errorlevel 1 (
        echo.
        echo  ERROR: runtime\node.exe is missing and Node.js is not installed.
        echo  Restore the runtime folder or install Node.js from nodejs.org
        echo.
        pause
        exit /b 1
    )
    set "NODE=node"
)

REM -- Sanity check: required files present
if not exist "%~dp0server.js" (
    echo  ERROR: server.js not found next to this launcher.
    pause
    exit /b 1
)
if not exist "%~dp0pl_detail.db" (
    echo  WARNING: pl_detail.db not found - dashboard will use cached JSON only.
    ping -n 3 127.0.0.1 >nul
)

REM -- If the dashboard is already running, just open the browser
call :CHECK_UP
if not errorlevel 1 goto OPEN

echo  Starting Company Dashboard server...
start "Company Dashboard Server" /min "%NODE%" server.js

REM -- Wait for the server to come up (max 30s; big DB can take a moment)
set /a tries=0
:WAIT
set /a tries+=1
call :CHECK_UP
if not errorlevel 1 goto OPEN
if !tries! geq 30 (
    echo.
    echo  Server did not respond after 30 seconds.
    echo  Check the minimized "Company Dashboard Server" window for errors.
    echo.
    pause
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto WAIT

:OPEN
start "" "http://localhost:3001"
exit /b 0

:CHECK_UP
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing 'http://localhost:3001/' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
exit /b %errorlevel%
