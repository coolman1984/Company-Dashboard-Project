@echo off
REM ============================================================
REM  Creates a clean portable copy of the Company Dashboard
REM  containing ONLY what is needed to run it on another PC.
REM  Excludes: source Excel (72MB), Python build scripts, dev logs.
REM ============================================================
setlocal
title Make Portable Copy
cd /d "%~dp0"

echo.
echo  This will create a portable copy of the Company Dashboard.
echo  Size needed at destination: about 700 MB (mostly the database).
echo.
set /p DEST=  Destination folder (e.g. E:\CompanyDashboard):
if "%DEST%"=="" (
    echo  No destination given. Cancelled.
    pause
    exit /b 1
)

echo.
echo  Copying core files...
robocopy "%~dp0." "%DEST%" server.js app.js index.html package.json package-lock.json "Start Dashboard.bat" "Stop Dashboard.bat" README-PORTABLE.md pl_detail.db /NJH /NJS /NDL >nul

echo  Copying bundled Node.js runtime...
robocopy "%~dp0runtime" "%DEST%\runtime" /E /NJH /NJS /NDL >nul

echo  Copying dependencies (node_modules)...
robocopy "%~dp0node_modules" "%DEST%\node_modules" /E /NJH /NJS /NDL >nul

echo  Copying JSON fallback cache (api_data)...
robocopy "%~dp0api_data" "%DEST%\api_data" /E /NJH /NJS /NDL >nul

if exist "%DEST%\Start Dashboard.bat" (
    echo.
    echo  DONE. Portable copy created at: %DEST%
    echo  On the target PC: double-click "Start Dashboard.bat" - that is all.
) else (
    echo.
    echo  Something went wrong - check the destination folder.
)
echo.
pause
exit /b 0
