@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    goto error
)

call ".venv\Scripts\activate.bat"

echo Building VideoEditor.exe ...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name VideoEditor ^
    --add-data "assets;assets" ^
    --collect-all imageio_ffmpeg ^
    --collect-all faster_whisper ^
    --hidden-import video_editor_bot.gui ^
    "src\video_editor_bot\gui.py"
if errorlevel 1 goto error

echo.
echo Build complete: dist\VideoEditor\VideoEditor.exe
echo To build the installer, install Inno Setup and run build_installer.bat.
goto end

:error
echo.
echo EXE build failed. Read the error above and try again.
pause
exit /b 1

:end
pause
endlocal
