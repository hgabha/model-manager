@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "PORT=9999"

cd /d "%SCRIPT_DIR%"

:: Create venv if it doesn't exist
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Setting up virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Make sure Python is installed and on your PATH.
        pause
        exit /b 1
    )
)

:: Activate venv
call "%VENV_DIR%\Scripts\activate.bat"

:: Install/upgrade dependencies
echo Checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Open browser after a short delay (runs in background)
start "" cmd /c "timeout /t 2 >nul && start http://localhost:%PORT%"

echo Starting Model Manager on http://localhost:%PORT%
echo Press Ctrl+C to stop.
echo.
python model_manager_by_wwaa.py

endlocal
pause
