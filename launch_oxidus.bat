@echo off
REM Oxidus Launcher Batch Script
REM Double-click this file to launch Oxidus with automatic venv activation

echo ============================================================
echo Starting Oxidus...
echo ============================================================
echo.

REM Change to the project directory
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please create the virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Virtual environment activated: .venv
echo.

REM Launch Oxidus
echo Launching Oxidus...
python launch_oxidus.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Oxidus exited with an error.
    pause
)
