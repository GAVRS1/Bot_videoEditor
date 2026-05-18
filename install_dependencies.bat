@echo off
setlocal
cd /d "%~dp0"

echo Checking Python ...
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.11+ and check "Add python.exe to PATH".
    goto error
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer is required.
    python --version
    goto error
)

if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        goto error
    )
) else (
    echo Virtual environment already exists.
)

call ".venv\Scripts\activate.bat"

echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 goto error

echo Installing project dependencies from requirements.txt ...
python -m pip install -r requirements.txt
if errorlevel 1 goto error

echo Checking FFmpeg support ...
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo FFmpeg was not found in PATH, but the bot can use the bundled imageio-ffmpeg package.
    echo If video processing fails on this PC, install FFmpeg and add it to PATH.
    python -c "import imageio_ffmpeg; print('Bundled FFmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"
    if errorlevel 1 goto error
) else (
    ffmpeg -version | findstr /i "ffmpeg version"
)

echo.
echo Dependencies are installed.
echo Next step: run run_app.bat
goto end

:error
echo.
echo Dependency installation failed. Read the error above, fix it, and run this file again.
pause
exit /b 1

:end
pause
endlocal
