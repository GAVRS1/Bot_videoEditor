@echo off
setlocal
cd /d "%~dp0"

echo Creating virtual environment in .venv ...
python -m venv .venv
if errorlevel 1 (
    echo Failed to create virtual environment. Make sure Python 3.11+ is installed and available as python.
    goto error
)

call ".venv\Scripts\activate.bat"

echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 goto error

echo Installing project dependencies from requirements.txt ...
python -m pip install -r requirements.txt
if errorlevel 1 goto error

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: ffmpeg was not found in PATH. Install FFmpeg and add it to PATH before processing videos.
)

echo.
echo Dependencies are installed.
echo Next step: open src\video_editor_bot\config.py, set TELEGRAM_BOT_TOKEN, then run run_project.bat.
goto end

:error
echo.
echo Dependency installation failed. Read the error above, fix it, and run this file again.
pause
exit /b 1

:end
pause
endlocal
