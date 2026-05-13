@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    exit /b 1
)

call ".venv\Scripts\activate.bat"

if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo TELEGRAM_BOT_TOKEN is not set.
    echo Example:
    echo   set TELEGRAM_BOT_TOKEN=123456:telegram-token
    echo   run_project.bat
    exit /b 1
)

echo Starting Telegram video editor bot ...
python -m video_editor_bot.main
endlocal
