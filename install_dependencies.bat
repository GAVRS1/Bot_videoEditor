@echo off
setlocal
cd /d "%~dp0"
set "EXIT_CODE=0"

echo Creating virtual environment in .venv ...
python -m venv .venv
if errorlevel 1 (
    echo Failed to create virtual environment. Make sure Python 3.11+ is installed and available as python.
    set "EXIT_CODE=1"
    goto finish
)

call ".venv\Scripts\activate.bat"

echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
    set "EXIT_CODE=1"
    goto finish
)

echo Installing project dependencies from requirements.txt ...
python -m pip install -r requirements.txt
if errorlevel 1 (
    set "EXIT_CODE=1"
    goto finish
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: ffmpeg was not found in PATH. Install FFmpeg and add it to PATH before processing videos.
)

echo.
echo Dependencies are installed. Set TELEGRAM_BOT_TOKEN and run run_project.bat to start the bot.

:finish
echo.
pause
endlocal & exit /b %EXIT_CODE%
