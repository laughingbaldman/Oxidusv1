@echo off
REM Silent Oxidus Launcher - No console window remains open
REM Use this if you want Oxidus to launch without keeping the command window open

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    msg "%username%" "Virtual environment not found! Please run: python -m venv .venv"
    exit /b 1
)

REM Launch Oxidus using venv Python directly (bypass activation for silent mode)
start "Oxidus" /B .venv\Scripts\python.exe launch_oxidus.py
