@echo off
REM ============================================================
REM  Create Sample Data - one-time setup
REM  Builds a practice database (pl_detail.db) so the dashboard
REM  has numbers to show. Safe to run again any time.
REM ============================================================
cd /d "%~dp0"
title Create Sample Data

REM -- Find Python (the "py" launcher first, then "python")
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo  Python is not installed on this PC.
    echo  Please install it once from https://www.python.org/downloads/
    echo  (tick "Add Python to PATH" during install), then run this again.
    echo.
    pause
    exit /b 1
)

echo.
echo  Creating practice data... this takes a few seconds.
echo.
%PY% seed_db.py --force
if errorlevel 1 (
    echo.
    echo  Something went wrong while creating the data.
    pause
    exit /b 1
)

echo.
echo  Done. You can now double-click "Start Dashboard.bat".
echo.
pause
