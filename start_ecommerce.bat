@echo off
setlocal enabledelayedexpansion
title NovaMart AI E-Commerce Platform
cd /d "%~dp0"

echo =======================================================================
echo               NOVAMART AI E-COMMERCE PLATFORM LAUNCHER
echo =======================================================================
echo.

:: 1. Detect Python Command
set PYCMD=
where python >nul 2>&1 && set PYCMD=python
if "%PYCMD%"=="" (
    where py >nul 2>&1 && set PYCMD=py
)
if "%PYCMD%"=="" (
    where python3 >nul 2>&1 && set PYCMD=python3
)

if "%PYCMD%"=="" (
    echo [ERROR] Python is not installed or not added to PATH on this PC!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo NOTE: Make sure to check the box "Add Python to PATH" during installation.
    echo.
    echo =======================================================================
    pause
    exit /b 1
)

echo [1/3] Using Python: %PYCMD%
%PYCMD% --version
echo.

:: 2. Check and Install Required Packages
echo [2/3] Verifying dependencies (Flask, pandas, scikit-learn)...
%PYCMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Dependency install had issues. Attempting to install core Flask...
    %PYCMD% -m pip install flask
)
echo.

:: 3. Launch App
echo [3/3] Starting NovaMart Web Server...
echo.
echo =======================================================================
echo   Server is running!
echo   Local URL:    http://127.0.0.1:5000
echo   Admin Login:  admin@ecommerce.com / admin123
echo   Customer:     john@example.com / john123
echo =======================================================================
echo.
echo Opening browser...
start "" http://127.0.0.1:5000

%PYCMD% app.py

if errorlevel 1 (
    echo.
    echo [ERROR] The server stopped unexpectedly.
    echo See error details above.
)

echo.
pause
