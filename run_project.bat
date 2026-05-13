@echo off
setlocal
cd /d "%~dp0"
set "EXIT_CODE=0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    set "EXIT_CODE=1"
    goto finish
)

call ".venv\Scripts\activate.bat"

if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo TELEGRAM_BOT_TOKEN is not set.
    echo Example:
    echo   set TELEGRAM_BOT_TOKEN=123456:telegram-token
    echo   run_project.bat
    set "EXIT_CODE=1"
    goto finish
)

echo Starting Telegram video editor bot ...
python -m video_editor_bot.main
set "EXIT_CODE=%ERRORLEVEL%"

:finish
echo.
pause
endlocal & exit /b %EXIT_CODE%
