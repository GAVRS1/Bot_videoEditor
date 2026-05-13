@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    goto error
)

call ".venv\Scripts\activate.bat"

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo Starting Telegram video editor bot ...
python -m video_editor_bot.main
if errorlevel 1 goto error

goto end

:error
echo.
echo The bot did not start. Read the error above, fix it, and run this file again.
echo Most often you need to open src\video_editor_bot\config.py and set TELEGRAM_BOT_TOKEN.
pause
exit /b 1

:end
pause
endlocal
