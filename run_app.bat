@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    goto error
)

call ".venv\Scripts\activate.bat"

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo Starting local video editor ...
python -m video_editor_bot.gui
if errorlevel 1 goto error

goto end

:error
echo.
echo The app did not start. Read the error above, fix it, and run this file again.
pause
exit /b 1

:end
endlocal
