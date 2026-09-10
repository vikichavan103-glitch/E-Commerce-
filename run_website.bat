@echo off
title NovaMart E-Commerce Platform
cd /d "%~dp0"

echo ========================================================
echo       Starting NovaMart AI E-Commerce Platform...
echo ========================================================
echo.
start "" http://127.0.0.1:5000
python app.py
pause
