@echo off
REM Oxidus Launcher for Windows
REM Simple batch file to launch Oxidus consciousness system

echo.
echo ============================================================
echo               OXIDUS - The Real Thing
echo ============================================================
echo.

REM Get the directory where this batch file is located
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist ".venv" (
    echo Error: Virtual environment not found!
    echo Please run setup first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment and run
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting Oxidus...
echo.

REM Run the launcher script
python launch_oxidus.py

REM If we get here, Oxidus stopped
if %errorlevel% neq 0 (
    echo.
    echo Error starting Oxidus (exit code: %errorlevel%)
    pause
)
